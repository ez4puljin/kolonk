"""Pumps and nozzles: configuration plus the POS authorize/stop commands.

The DB holds the configuration and the last known status; the live status comes
from ``request.app.state.pump_manager`` and is merged over it, so a POS that
reconnects mid-fueling immediately sees the real state of the forecourt.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import require_permission
from app.enums import PresetType, PumpStatus, ShiftStatus
from app.hardware.pump_driver import Preset, Telemetry
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank, TotalizerReading
from app.models.shift import Shift
from app.models.user import User
from app.money import q2, q3
from app.schemas.fuel import (
    AuthorizeIn,
    AuthorizeOut,
    NozzleCreate,
    NozzleOut,
    NozzleUpdate,
    PumpActionOut,
    PumpCreate,
    PumpListOut,
    PumpOut,
    PumpUpdate,
    TelemetryOut,
)
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["pumps"])

ZERO = Decimal("0")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _manager(request: Request):
    return getattr(request.app.state, "pump_manager", None)


async def _branch_names(db: AsyncSession) -> dict:
    """Салбарын id → нэр (хариултад салбарын нэр харуулахад)."""
    from app.models.branch import Branch

    return dict((await db.execute(select(Branch.id, Branch.name))).all())


def _schedule_refresh(request: Request, background: BackgroundTasks) -> None:
    """Re-sync the drivers after config changes — runs once the request's
    transaction has been committed, so the manager reads fresh rows."""
    manager = _manager(request)
    if manager is not None:
        background.add_task(manager.refresh)


def _nozzle_out(nozzle: PumpNozzle, price_overrides: dict | None = None) -> NozzleOut:
    # Түгээгүүрийн салбарт өөр үнэ мөрдөж байвал түүнийг харуулна.
    override = (price_overrides or {}).get(nozzle.fuel_id)
    return NozzleOut(
        id=nozzle.id,
        pump_id=nozzle.pump_id,
        nozzle_number=nozzle.nozzle_number,
        fuel_id=nozzle.fuel_id,
        fuel_code=nozzle.fuel.code,
        fuel_name=nozzle.fuel.name_mn,
        price_per_liter=override if override is not None else nozzle.fuel.price_per_liter,
        color_hex=nozzle.fuel.color_hex,
        tank_id=nozzle.tank_id,
        tank_name=nozzle.tank.name,
        tank_current_l=q3(nozzle.tank.current_l or ZERO),
        totalizer=nozzle.totalizer,
    )


def _telemetry_out(telemetry: Telemetry) -> TelemetryOut:
    return TelemetryOut(
        pump_id=telemetry.pump_id,
        nozzle_id=telemetry.nozzle_id,
        status=str(telemetry.status),
        liters=q3(telemetry.liters),
        amount=q2(telemetry.amount),
        flow_lpm=q2(telemetry.flow_lpm),
        authorization_id=telemetry.authorization_id,
    )


def _pump_out(
    pump: Pump,
    live: Telemetry | None,
    price_overrides: dict | None = None,
    branch_names: dict | None = None,
) -> PumpOut:
    nozzles = sorted(pump.nozzles, key=lambda n: n.nozzle_number)
    return PumpOut(
        id=pump.id,
        number=pump.number,
        name=pump.name,
        branch_id=pump.branch_id,
        branch_name=(branch_names or {}).get(pump.branch_id),
        position_x=int(pump.position_x or 0),
        position_y=int(pump.position_y or 0),
        status=str(live.status) if live is not None else pump.status,
        driver=pump.driver,
        is_active=pump.is_active,
        nozzles=[_nozzle_out(n, price_overrides) for n in nozzles],
        live=_telemetry_out(live) if live is not None else None,
        created_at=pump.created_at,
        updated_at=pump.updated_at,
    )


def _snapshot(pump: Pump) -> dict:
    return {
        "number": pump.number,
        "name": pump.name,
        "branch_id": str(pump.branch_id) if pump.branch_id else None,
        "position": f"{pump.position_x},{pump.position_y}",
        "driver": pump.driver,
        "status": pump.status,
        "is_active": pump.is_active,
    }


def _nozzle_snapshot(nozzle: PumpNozzle) -> dict:
    return {
        "pump_id": str(nozzle.pump_id),
        "nozzle_number": nozzle.nozzle_number,
        "fuel_id": str(nozzle.fuel_id),
        "tank_id": str(nozzle.tank_id),
        "totalizer": str(nozzle.totalizer),
    }


def _pump_query():
    return select(Pump).options(
        selectinload(Pump.nozzles).selectinload(PumpNozzle.fuel),
        selectinload(Pump.nozzles).selectinload(PumpNozzle.tank),
    )


async def _load_pump(db: AsyncSession, pump_id: uuid.UUID) -> Pump:
    pump = await db.scalar(_pump_query().where(Pump.id == pump_id))
    if pump is None:
        raise HTTPException(status_code=404, detail="Түгээгүүр олдсонгүй")
    return pump


async def _reload_pump(db: AsyncSession, pump_id: uuid.UUID) -> Pump:
    """Re-read a pump the request itself just wrote, forcing the freshly
    inserted nozzle rows into the already-tracked instance."""
    pump = await db.scalar(
        _pump_query().where(Pump.id == pump_id).execution_options(populate_existing=True)
    )
    if pump is None:
        raise HTTPException(status_code=404, detail="Түгээгүүр олдсонгүй")
    return pump


async def _validate_nozzle_link(
    db: AsyncSession, fuel_id: uuid.UUID, tank_id: uuid.UUID
) -> tuple[Fuel, Tank]:
    fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
    if fuel is None:
        raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
    tank = await db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Сав олдсонгүй")
    if tank.fuel_id != fuel_id:
        raise HTTPException(status_code=422, detail="Савны түлш хошууны түлштэй таарахгүй байна")
    return fuel, tank


# --------------------------------------------------------------------------- #
# Read
# --------------------------------------------------------------------------- #


@router.get("/pumps", response_model=PumpListOut)
async def list_pumps(
    request: Request,
    active_only: bool = Query(default=False),
    branch_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("pumps.view", "pumps.manage")),
) -> PumpListOut:
    # Салбартай хэрэглэгч (түгээгч) зөвхөн өөрийн салбарын түгээгүүрийг харна —
    # хүсэлтэд өөр салбар заасан ч үл хэрэгснэ.
    scope_branch = getattr(_user, "branch_id", None) or branch_id

    stmt = _pump_query()
    if active_only:
        stmt = stmt.where(Pump.is_active.is_(True))
    if scope_branch is not None:
        stmt = stmt.where(Pump.branch_id == scope_branch)
    # Талбай дахь байршлаар эрэмбэлнэ — ПОС бодит зохион байгуулалтаар харагдана.
    pumps = (await db.scalars(stmt.order_by(Pump.position_y, Pump.position_x, Pump.number))).all()

    manager = _manager(request)
    live: dict[uuid.UUID, Telemetry] = {}
    if manager is not None:
        live = {t.pump_id: t for t in manager.snapshot()}

    from app.models.branch import Branch
    from app.services.pricing_service import fuel_price_map

    override_cache: dict[uuid.UUID | None, dict] = {}

    async def overrides_for(bid: uuid.UUID | None) -> dict:
        if bid not in override_cache:
            override_cache[bid] = await fuel_price_map(db, bid)
        return override_cache[bid]

    branch_names = dict((await db.execute(select(Branch.id, Branch.name))).all())
    return PumpListOut(
        items=[
            _pump_out(p, live.get(p.id), await overrides_for(p.branch_id), branch_names)
            for p in pumps
        ],
        total=len(pumps),
    )


@router.get("/pumps/{pump_id}", response_model=PumpOut)
async def get_pump(
    pump_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("pumps.view", "pumps.manage")),
) -> PumpOut:
    pump = await _load_pump(db, pump_id)
    manager = _manager(request)
    live = manager.telemetry_for(pump_id) if manager is not None else None

    from app.services.pricing_service import fuel_price_map

    return _pump_out(pump, live, await fuel_price_map(db, pump.branch_id), await _branch_names(db))


# --------------------------------------------------------------------------- #
# Pump CRUD
# --------------------------------------------------------------------------- #


@router.post("/pumps", response_model=PumpOut, status_code=201)
async def create_pump(
    payload: PumpCreate,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("pumps.manage")),
) -> PumpOut:
    from app.services.branch_service import resolve_branch_id

    branch_id = await resolve_branch_id(db, user, payload.branch_id)
    # Дугаар зөвхөн ТУХАЙН САЛБАР дотроо давхардахгүй — салбар бүр өөрийн
    # «1-р түгээгүүр»-тэй байна.
    clash = await db.scalar(
        select(func.count())
        .select_from(Pump)
        .where(Pump.number == payload.number, Pump.branch_id == branch_id)
    )
    if clash:
        raise HTTPException(
            status_code=422, detail="Энэ салбарт ийм дугаартай түгээгүүр бүртгэгдсэн байна"
        )

    pump = Pump(
        number=payload.number,
        name=payload.name.strip(),
        branch_id=branch_id,
        position_x=payload.position_x,
        position_y=payload.position_y,
        driver=payload.driver,
        status=PumpStatus.IDLE,
        is_active=payload.is_active,
    )
    db.add(pump)
    await db.flush()

    seen: set[int] = set()
    for spec in payload.nozzles:
        if spec.nozzle_number in seen:
            raise HTTPException(status_code=422, detail="Хошууны дугаар давхардсан байна")
        seen.add(spec.nozzle_number)
        await _validate_nozzle_link(db, spec.fuel_id, spec.tank_id)
        db.add(
            PumpNozzle(
                pump_id=pump.id,
                nozzle_number=spec.nozzle_number,
                fuel_id=spec.fuel_id,
                tank_id=spec.tank_id,
                totalizer=q3(spec.totalizer),
            )
        )
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="pump.create",
        entity_type="pump",
        entity_id=pump.id,
        after=_snapshot(pump),
        ip=_client_ip(request),
    )

    _schedule_refresh(request, background)
    pump = await _reload_pump(db, pump.id)
    return _pump_out(pump, None, None, await _branch_names(db))


@router.patch("/pumps/{pump_id}", response_model=PumpOut)
async def update_pump(
    pump_id: uuid.UUID,
    payload: PumpUpdate,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("pumps.manage")),
) -> PumpOut:
    pump = await _load_pump(db, pump_id)
    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(pump)

    if changes.get("number") is not None and changes["number"] != pump.number:
        target_branch = changes.get("branch_id", pump.branch_id)
        clash = await db.scalar(
            select(func.count())
            .select_from(Pump)
            .where(Pump.number == changes["number"], Pump.branch_id == target_branch)
        )
        if clash:
            raise HTTPException(
                status_code=422, detail="Энэ салбарт ийм дугаартай түгээгүүр бүртгэгдсэн байна"
            )

    if changes.get("name") is not None:
        changes["name"] = str(changes["name"]).strip()

    for field, value in changes.items():
        if value is not None:
            setattr(pump, field, value)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="pump.update",
        entity_type="pump",
        entity_id=pump.id,
        before=before,
        after=_snapshot(pump),
        ip=_client_ip(request),
    )

    _schedule_refresh(request, background)
    manager = _manager(request)
    live = manager.telemetry_for(pump_id) if manager is not None else None
    return _pump_out(pump, live, None, await _branch_names(db))


@router.delete("/pumps/{pump_id}", status_code=204, response_model=None)
async def delete_pump(
    pump_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("pumps.manage")),
) -> None:
    pump = await _load_pump(db, pump_id)

    nozzle_ids = [n.id for n in pump.nozzles]
    if nozzle_ids:
        readings = await db.scalar(
            select(func.count())
            .select_from(TotalizerReading)
            .where(TotalizerReading.nozzle_id.in_(nozzle_ids))
        )
        if readings:
            raise HTTPException(
                status_code=422,
                detail="Уншилт бүртгэгдсэн тул устгах боломжгүй. Идэвхгүй болгоно уу",
            )

    before = _snapshot(pump)
    await db.delete(pump)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="pump.delete",
        entity_type="pump",
        entity_id=pump_id,
        before=before,
        ip=_client_ip(request),
    )
    _schedule_refresh(request, background)


# --------------------------------------------------------------------------- #
# Nozzle CRUD
# --------------------------------------------------------------------------- #


@router.post("/pumps/{pump_id}/nozzles", response_model=NozzleOut, status_code=201)
async def create_nozzle(
    pump_id: uuid.UUID,
    payload: NozzleCreate,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("pumps.manage")),
) -> NozzleOut:
    pump = await _load_pump(db, pump_id)
    if any(n.nozzle_number == payload.nozzle_number for n in pump.nozzles):
        raise HTTPException(status_code=422, detail="Ийм дугаартай хошуу энэ түгээгүүрт бүртгэгдсэн байна")

    fuel, tank = await _validate_nozzle_link(db, payload.fuel_id, payload.tank_id)

    nozzle = PumpNozzle(
        pump_id=pump.id,
        nozzle_number=payload.nozzle_number,
        fuel_id=payload.fuel_id,
        tank_id=payload.tank_id,
        totalizer=q3(payload.totalizer),
    )
    db.add(nozzle)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="nozzle.create",
        entity_type="pump_nozzle",
        entity_id=nozzle.id,
        after=_nozzle_snapshot(nozzle),
        ip=_client_ip(request),
    )

    _schedule_refresh(request, background)
    nozzle.fuel = fuel
    nozzle.tank = tank
    return _nozzle_out(nozzle)


@router.patch("/pumps/{pump_id}/nozzles/{nozzle_id}", response_model=NozzleOut)
async def update_nozzle(
    pump_id: uuid.UUID,
    nozzle_id: uuid.UUID,
    payload: NozzleUpdate,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("pumps.manage")),
) -> NozzleOut:
    nozzle = await db.scalar(
        select(PumpNozzle)
        .options(selectinload(PumpNozzle.fuel), selectinload(PumpNozzle.tank))
        .where(PumpNozzle.id == nozzle_id, PumpNozzle.pump_id == pump_id)
    )
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Хошуу олдсонгүй")

    changes = payload.model_dump(exclude_unset=True)
    before = _nozzle_snapshot(nozzle)

    if changes.get("nozzle_number") is not None and changes["nozzle_number"] != nozzle.nozzle_number:
        clash = await db.scalar(
            select(func.count())
            .select_from(PumpNozzle)
            .where(
                PumpNozzle.pump_id == pump_id,
                PumpNozzle.nozzle_number == changes["nozzle_number"],
            )
        )
        if clash:
            raise HTTPException(status_code=422, detail="Ийм дугаартай хошуу энэ түгээгүүрт бүртгэгдсэн байна")

    fuel_id = changes.get("fuel_id") or nozzle.fuel_id
    tank_id = changes.get("tank_id") or nozzle.tank_id
    if fuel_id != nozzle.fuel_id or tank_id != nozzle.tank_id:
        await _validate_nozzle_link(db, fuel_id, tank_id)

    if changes.get("totalizer") is not None:
        totalizer = q3(changes["totalizer"])
        if totalizer < 0:
            raise HTTPException(status_code=422, detail="Тоолуурын утга сөрөг байж болохгүй")
        changes["totalizer"] = totalizer

    for field, value in changes.items():
        if value is not None:
            setattr(nozzle, field, value)
    await db.flush()
    await db.refresh(nozzle, ["fuel", "tank"])

    await audit(
        db,
        user_id=user.id,
        action="nozzle.update",
        entity_type="pump_nozzle",
        entity_id=nozzle.id,
        before=before,
        after=_nozzle_snapshot(nozzle),
        ip=_client_ip(request),
    )
    _schedule_refresh(request, background)
    return _nozzle_out(nozzle)


@router.delete("/pumps/{pump_id}/nozzles/{nozzle_id}", status_code=204, response_model=None)
async def delete_nozzle(
    pump_id: uuid.UUID,
    nozzle_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("pumps.manage")),
) -> None:
    nozzle = await db.scalar(
        select(PumpNozzle).where(PumpNozzle.id == nozzle_id, PumpNozzle.pump_id == pump_id)
    )
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Хошуу олдсонгүй")

    readings = await db.scalar(
        select(func.count()).select_from(TotalizerReading).where(TotalizerReading.nozzle_id == nozzle_id)
    )
    if readings:
        raise HTTPException(
            status_code=422, detail="Уншилт бүртгэгдсэн тул устгах боломжгүй. Идэвхгүй болгоно уу"
        )

    before = _nozzle_snapshot(nozzle)
    await db.delete(nozzle)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="nozzle.delete",
        entity_type="pump_nozzle",
        entity_id=nozzle_id,
        before=before,
        ip=_client_ip(request),
    )
    _schedule_refresh(request, background)


# --------------------------------------------------------------------------- #
# Forecourt commands
# --------------------------------------------------------------------------- #


@router.post("/pumps/{pump_id}/authorize", response_model=AuthorizeOut)
async def authorize_pump(
    pump_id: uuid.UUID,
    payload: AuthorizeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("sales.create")),
) -> AuthorizeOut:
    open_shift = await db.scalar(select(Shift.id).where(Shift.status == ShiftStatus.OPEN).limit(1))
    if open_shift is None:
        raise HTTPException(status_code=422, detail="Ээлж нээгээгүй байна")

    pump = await _load_pump(db, pump_id)
    if not pump.is_active:
        raise HTTPException(status_code=422, detail="Түгээгүүр идэвхгүй байна")

    nozzle = next((n for n in pump.nozzles if n.id == payload.nozzle_id), None)
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Хошуу олдсонгүй")

    preset_type = PresetType(payload.preset_type)
    value: Decimal | None = None
    if preset_type in (PresetType.LITERS, PresetType.AMOUNT):
        if payload.preset_value is None:
            raise HTTPException(status_code=422, detail="Урьдчилсан утга оруулна уу")
        value = q3(payload.preset_value) if preset_type == PresetType.LITERS else q2(payload.preset_value)
        if value <= 0:
            raise HTTPException(status_code=422, detail="Урьдчилсан утга 0-ээс их байх ёстой")

    manager = _manager(request)
    if manager is None or not manager.has_pump(pump_id):
        raise HTTPException(status_code=422, detail="Түгээгүүр холбогдоогүй байна")

    try:
        authorization_id = await manager.authorize(
            pump_id, payload.nozzle_id, Preset(type=preset_type, value=value)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        db,
        user_id=user.id,
        action="pump.authorize",
        entity_type="pump",
        entity_id=pump_id,
        after={
            "nozzle_id": str(payload.nozzle_id),
            "preset_type": str(preset_type),
            "preset_value": str(value) if value is not None else None,
            "authorization_id": str(authorization_id),
            "shift_id": str(open_shift),
        },
        ip=_client_ip(request),
    )
    return AuthorizeOut(authorization_id=authorization_id)


@router.post("/pumps/{pump_id}/stop", response_model=PumpActionOut)
async def stop_pump(
    pump_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("sales.create")),
) -> PumpActionOut:
    await _load_pump(db, pump_id)

    manager = _manager(request)
    if manager is None or not manager.has_pump(pump_id):
        raise HTTPException(status_code=422, detail="Түгээгүүр холбогдоогүй байна")

    try:
        await manager.halt(pump_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    telemetry = manager.telemetry_for(pump_id)

    await audit(
        db,
        user_id=user.id,
        action="pump.stop",
        entity_type="pump",
        entity_id=pump_id,
        after={"status": str(telemetry.status) if telemetry else PumpStatus.IDLE},
        ip=_client_ip(request),
    )
    return PumpActionOut(
        ok=True,
        pump_id=pump_id,
        status=str(telemetry.status) if telemetry else str(PumpStatus.IDLE),
    )
