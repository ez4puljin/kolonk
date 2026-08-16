"""Fuel tanks: levels, movements ledger and manual adjustments."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.deps import require_permission
from app.enums import TankMovementType
from app.models.fuel import Fuel, PumpNozzle, Tank, TankMovement
from app.models.user import User
from app.money import q2, q3
from app.schemas.fuel import (
    FuelBrief,
    TankAdjustmentIn,
    TankCreate,
    TankListOut,
    TankMovementListOut,
    TankMovementOut,
    TankOut,
    TankUpdate,
)
from app.services import tank_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["tanks"])

ZERO = Decimal("0")

try:
    STATION_TZ = ZoneInfo(settings.tz)
except Exception:  # noqa: BLE001 — missing tzdata on a dev box
    STATION_TZ = timezone(timedelta(hours=8))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=STATION_TZ)


def _to_out(tank: Tank, branch_names: dict | None = None) -> TankOut:
    capacity = Decimal(tank.capacity_l or ZERO)
    current = Decimal(tank.current_l or ZERO)
    fill_pct = q2(current / capacity * 100) if capacity > 0 else Decimal("0.00")
    return TankOut(
        id=tank.id,
        name=tank.name,
        branch_id=tank.branch_id,
        branch_name=branch_names.get(tank.branch_id) if branch_names else None,
        fuel_id=tank.fuel_id,
        fuel=FuelBrief.model_validate(tank.fuel),
        capacity_l=q3(capacity),
        current_l=q3(current),
        avg_cost=tank.avg_cost,
        min_level_l=q3(tank.min_level_l or ZERO),
        is_active=tank.is_active,
        fill_pct=fill_pct,
        is_low=current <= Decimal(tank.min_level_l or ZERO),
        stock_value=q2(current * Decimal(tank.avg_cost or ZERO)),
        created_at=tank.created_at,
        updated_at=tank.updated_at,
    )


def _snapshot(tank: Tank) -> dict:
    return {
        "name": tank.name,
        "fuel_id": str(tank.fuel_id),
        "capacity_l": str(tank.capacity_l),
        "current_l": str(tank.current_l),
        "avg_cost": str(tank.avg_cost),
        "min_level_l": str(tank.min_level_l),
        "is_active": tank.is_active,
    }


async def _branch_names(db: AsyncSession) -> dict:
    """Салбарын id → нэр."""
    from app.models.branch import Branch

    return dict((await db.execute(select(Branch.id, Branch.name))).all())


async def _load_tank(db: AsyncSession, tank_id: uuid.UUID) -> Tank:
    tank = await db.scalar(select(Tank).options(selectinload(Tank.fuel)).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Сав олдсонгүй")
    return tank


# --------------------------------------------------------------------------- #
# Read
# --------------------------------------------------------------------------- #


@router.get("/tanks", response_model=TankListOut)
async def list_tanks(
    fuel_id: uuid.UUID | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("tanks.view", "tanks.manage")),
) -> TankListOut:
    # Салбартай хэрэглэгч зөвхөн өөрийн салбарын савыг харна.
    scope_branch = getattr(_user, "branch_id", None) or branch_id

    stmt = select(Tank).options(selectinload(Tank.fuel))
    if fuel_id is not None:
        stmt = stmt.where(Tank.fuel_id == fuel_id)
    if scope_branch is not None:
        stmt = stmt.where(Tank.branch_id == scope_branch)
    if active_only:
        stmt = stmt.where(Tank.is_active.is_(True))
    stmt = stmt.order_by(Tank.name)

    tanks = (await db.scalars(stmt)).all()

    from app.models.branch import Branch

    branch_names = dict((await db.execute(select(Branch.id, Branch.name))).all())
    return TankListOut(items=[_to_out(t, branch_names) for t in tanks], total=len(tanks))


@router.get("/tanks/{tank_id}", response_model=TankOut)
async def get_tank(
    tank_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("tanks.view", "tanks.manage")),
) -> TankOut:
    return _to_out(await _load_tank(db, tank_id), await _branch_names(db))


@router.get("/tanks/{tank_id}/movements", response_model=TankMovementListOut)
async def list_movements(
    tank_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    movement_type: TankMovementType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("tanks.view", "tanks.manage")),
) -> TankMovementListOut:
    await _load_tank(db, tank_id)

    conditions = [TankMovement.tank_id == tank_id]
    if date_from is not None:
        conditions.append(TankMovement.created_at >= _day_start(date_from))
    if date_to is not None:
        conditions.append(TankMovement.created_at < _day_start(date_to) + timedelta(days=1))
    if movement_type is not None:
        conditions.append(TankMovement.movement_type == str(movement_type))

    total = await db.scalar(select(func.count()).select_from(TankMovement).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(TankMovement)
            .where(*conditions)
            .order_by(TankMovement.created_at.desc(), TankMovement.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return TankMovementListOut(items=[TankMovementOut.model_validate(r) for r in rows], total=int(total))


# --------------------------------------------------------------------------- #
# Write
# --------------------------------------------------------------------------- #


@router.post("/tanks", response_model=TankOut, status_code=201)
async def create_tank(
    payload: TankCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("tanks.manage")),
) -> TankOut:
    fuel = await db.scalar(select(Fuel).where(Fuel.id == payload.fuel_id))
    if fuel is None:
        raise HTTPException(status_code=404, detail="Түлш олдсонгүй")

    capacity = q3(payload.capacity_l)
    if capacity <= 0:
        raise HTTPException(status_code=422, detail="Савны багтаамж 0-ээс их байх ёстой")

    opening = q3(payload.current_l)
    if opening < 0:
        raise HTTPException(status_code=422, detail="Эхний үлдэгдэл сөрөг байж болохгүй")
    if opening > capacity:
        raise HTTPException(status_code=422, detail="Эхний үлдэгдэл савны багтаамжаас их байна")
    if payload.avg_cost < 0:
        raise HTTPException(status_code=422, detail="Дундаж өртөг сөрөг байж болохгүй")
    if payload.min_level_l < 0:
        raise HTTPException(status_code=422, detail="Доод хязгаар сөрөг байж болохгүй")

    tank = Tank(
        branch_id=payload.branch_id,
        name=payload.name.strip(),
        fuel_id=payload.fuel_id,
        capacity_l=capacity,
        current_l=ZERO,
        avg_cost=payload.avg_cost,
        min_level_l=q3(payload.min_level_l),
        is_active=payload.is_active,
    )
    db.add(tank)
    await db.flush()

    # An opening balance is a real movement so the ledger starts consistent.
    if opening > 0:
        await tank_service.adjust_fuel(
            db,
            tank,
            opening,
            movement_type=TankMovementType.ADJUSTMENT,
            ref_type="opening_balance",
            ref_id=tank.id,
            note="Эхний үлдэгдэл",
        )
        await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="tank.create",
        entity_type="tank",
        entity_id=tank.id,
        after=_snapshot(tank),
        ip=_client_ip(request),
    )

    tank.fuel = fuel
    return _to_out(tank, await _branch_names(db))


@router.patch("/tanks/{tank_id}", response_model=TankOut)
async def update_tank(
    tank_id: uuid.UUID,
    payload: TankUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("tanks.manage")),
) -> TankOut:
    tank = await _load_tank(db, tank_id)
    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(tank)

    if changes.get("fuel_id") is not None and changes["fuel_id"] != tank.fuel_id:
        fuel = await db.scalar(select(Fuel).where(Fuel.id == changes["fuel_id"]))
        if fuel is None:
            raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
        if Decimal(tank.current_l or ZERO) != 0:
            raise HTTPException(status_code=422, detail="Үлдэгдэлтэй савны түлшийг солих боломжгүй")

    if changes.get("capacity_l") is not None:
        capacity = q3(changes["capacity_l"])
        if capacity <= 0:
            raise HTTPException(status_code=422, detail="Савны багтаамж 0-ээс их байх ёстой")
        if capacity < Decimal(tank.current_l or ZERO):
            raise HTTPException(status_code=422, detail="Багтаамж одоогийн үлдэгдлээс бага байж болохгүй")
        changes["capacity_l"] = capacity

    if changes.get("min_level_l") is not None:
        min_level = q3(changes["min_level_l"])
        if min_level < 0:
            raise HTTPException(status_code=422, detail="Доод хязгаар сөрөг байж болохгүй")
        changes["min_level_l"] = min_level

    if changes.get("name") is not None:
        changes["name"] = str(changes["name"]).strip()

    for field, value in changes.items():
        if value is not None:
            setattr(tank, field, value)
    await db.flush()
    await db.refresh(tank, ["fuel"])

    await audit(
        db,
        user_id=user.id,
        action="tank.update",
        entity_type="tank",
        entity_id=tank.id,
        before=before,
        after=_snapshot(tank),
        ip=_client_ip(request),
    )
    return _to_out(tank, await _branch_names(db))


@router.post("/tanks/{tank_id}/adjustments", response_model=TankOut)
async def adjust_tank(
    tank_id: uuid.UUID,
    payload: TankAdjustmentIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("tanks.manage")),
) -> TankOut:
    tank = await _load_tank(db, tank_id)

    liters = q3(payload.liters)
    if liters == 0:
        raise HTTPException(status_code=422, detail="Тохируулгын хэмжээ 0 байж болохгүй")

    new_balance = q3(Decimal(tank.current_l or ZERO) + liters)
    if new_balance > Decimal(tank.capacity_l or ZERO):
        raise HTTPException(status_code=422, detail="Тохируулсан үлдэгдэл багтаамжаас их байна")

    before = _snapshot(tank)
    await tank_service.adjust_fuel(
        db,
        tank,
        liters,
        movement_type=TankMovementType.ADJUSTMENT,
        ref_type="manual_adjustment",
        ref_id=tank.id,
        note=(payload.note or "").strip() or None,
    )
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="tank.adjust",
        entity_type="tank",
        entity_id=tank.id,
        before=before,
        after={**_snapshot(tank), "adjustment_l": str(liters), "note": payload.note},
        ip=_client_ip(request),
    )
    return _to_out(tank, await _branch_names(db))


@router.delete("/tanks/{tank_id}", status_code=204, response_model=None)
async def deactivate_tank(
    tank_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("tanks.manage")),
) -> None:
    """Tanks are never hard-deleted — the fuel ledger must stay intact."""
    tank = await _load_tank(db, tank_id)

    linked = await db.scalar(
        select(func.count()).select_from(PumpNozzle).where(PumpNozzle.tank_id == tank_id)
    )
    if linked:
        raise HTTPException(status_code=422, detail="Хошуутай холбоотой савыг идэвхгүй болгох боломжгүй")

    before = _snapshot(tank)
    tank.is_active = False
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="tank.deactivate",
        entity_type="tank",
        entity_id=tank.id,
        before=before,
        after=_snapshot(tank),
        ip=_client_ip(request),
    )
