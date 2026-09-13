"""Салбарын эхний үлдэгдэл — НЭГ УДАА (Админ панел → Салбарын тохиргоо).

Системд шилжих мөчид савны бодит үлдэгдэл (литр, нэгж өртөг) ба хошуу
бүрийн тоолуурын одоогийн заалтыг шууд оруулна:

* сав → ``tank_service.receive_fuel`` (хөдөлгөөн + дундаж өртөг) ба журналд
  Дт 1301 (түлш/сав/салбарын хэмжүүр) / Кт 3101 эзний хөрөнгө — барааны эхний
  үлдэгдэлтэй ижил дүрэм;
* хошуу → ``totalizer`` шууд тавигдаж, ``TotalizerReading`` (manual) үлдэнэ —
  дараагийн ээлжийн нээлт яг энэ заалтаас эхэлнэ.

``branches.opening_done_at`` бөглөгдмөгц дахин дуудахад 409 — ажлын явцад
савны үлдэгдэл, милийг «эхний үлдэгдэл» нэрээр өөрчлөх боломжгүй; дараа нь
зөвхөн хүлээн авалт, тохируулга, ээлжийн нээлтээр хөдөлнө.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import EventType, ReadingType, SourceType
from app.models.branch import Branch
from app.models.fuel import Pump, PumpNozzle, Tank, TotalizerReading
from app.models.user import User
from app.money import q2, q3, q6
from app.services import tank_service
from app.services.audit_service import audit
from app.services.coa import ACC
from app.services.posting import Dims, LineSpec, posting

router = APIRouter(prefix="/api", tags=["branches"])

ZERO = Decimal("0")


class OpeningTankIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tank_id: uuid.UUID
    liters: Decimal = Field(default=ZERO, ge=0)
    #: Литрийн өртөг (НӨАТ-гүй) — нөөцийн үнэлгээ, борлуулалтын өртөгт ашиглагдана.
    unit_cost: Decimal = Field(default=ZERO, ge=0)


class OpeningNozzleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nozzle_id: uuid.UUID
    totalizer: Decimal = Field(ge=0)


class BranchOpeningIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Журналын огноо (хоосон бол өнөөдөр).
    as_of: date | None = None
    tanks: list[OpeningTankIn] = Field(default_factory=list)
    nozzles: list[OpeningNozzleIn] = Field(default_factory=list)


class BranchOpeningOut(BaseModel):
    branch_id: uuid.UUID
    opening_done_at: datetime
    tanks_set: int
    nozzles_set: int
    fuel_value: Decimal
    journal_entry_id: uuid.UUID | None = None


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/branches/{branch_id}/opening", response_model=BranchOpeningOut, status_code=201)
async def set_branch_opening(
    branch_id: uuid.UUID,
    payload: BranchOpeningIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("settings.manage")),
) -> BranchOpeningOut:
    branch = await db.scalar(select(Branch).where(Branch.id == branch_id).with_for_update())
    if branch is None:
        raise HTTPException(status_code=404, detail="Салбар олдсонгүй")
    if branch.opening_done_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Энэ салбарын эхний үлдэгдэл аль хэдийн оруулагдсан — дахин оруулах боломжгүй",
        )
    if not payload.tanks and not payload.nozzles:
        raise HTTPException(status_code=422, detail="Сав эсвэл хошууны заалт оруулна уу")

    as_of = payload.as_of or datetime.now(UTC).date()
    memo = f"Эхний үлдэгдэл — {branch.name} — {as_of.isoformat()}"

    # ---------------- Сав ----------------
    tanks = {
        t.id: t
        for t in (await db.scalars(select(Tank).where(Tank.branch_id == branch.id))).all()
    }
    seen_tanks: set[uuid.UUID] = set()
    fuel_lines: list[LineSpec] = []
    fuel_value = ZERO
    tanks_set = 0
    for spec in payload.tanks:
        tank = tanks.get(spec.tank_id)
        if tank is None:
            raise HTTPException(status_code=404, detail="Сав энэ салбарынх биш байна")
        if spec.tank_id in seen_tanks:
            raise HTTPException(status_code=422, detail=f"«{tank.name}» сав давхардсан байна")
        seen_tanks.add(spec.tank_id)
        liters = q3(spec.liters)
        if liters <= ZERO:
            continue
        if Decimal(tank.current_l or ZERO) > ZERO:
            raise HTTPException(
                status_code=422,
                detail=f"«{tank.name}» саванд аль хэдийн үлдэгдэл бүртгэгдсэн — эхний үлдэгдэл оруулах боломжгүй",
            )
        if liters > Decimal(tank.capacity_l or ZERO):
            raise HTTPException(status_code=422, detail=f"«{tank.name}» савны багтаамжаас их байна")
        unit_cost = q6(spec.unit_cost)
        await tank_service.receive_fuel(
            db, tank, liters, unit_cost, ref_type=str(SourceType.OPENING_BALANCE), ref_id=tank.id
        )
        value = q2(liters * unit_cost)
        fuel_value = q2(fuel_value + value)
        tanks_set += 1
        if value > ZERO:
            fuel_lines.append(
                LineSpec(
                    account_code=ACC.INV_FUEL,
                    debit=value,
                    memo=memo,
                    dims=Dims(fuel_id=tank.fuel_id, tank_id=tank.id, branch_id=branch.id),
                )
            )

    # ---------------- Хошууны миль ----------------
    nozzles = {
        n.id: n
        for n in (
            await db.scalars(
                select(PumpNozzle).join(Pump, Pump.id == PumpNozzle.pump_id).where(Pump.branch_id == branch.id)
            )
        ).all()
    }
    now = datetime.now(UTC)
    nozzles_set = 0
    for spec in payload.nozzles:
        nozzle = nozzles.get(spec.nozzle_id)
        if nozzle is None:
            raise HTTPException(status_code=404, detail="Хошуу энэ салбарынх биш байна")
        reading = q3(spec.totalizer)
        previous = q3(Decimal(nozzle.totalizer or ZERO))
        nozzle.totalizer = reading
        db.add(
            TotalizerReading(
                nozzle_id=nozzle.id,
                shift_id=None,
                reading=reading,
                prev_reading=previous,
                reading_type=ReadingType.MANUAL,
                recorded_by=user.id,
                recorded_at=now,
            )
        )
        nozzles_set += 1

    # ---------------- Журнал ----------------
    entry_id: uuid.UUID | None = None
    if fuel_lines:
        lines = [*fuel_lines, LineSpec(account_code=ACC.OWNER_CAPITAL, credit=fuel_value, memo=memo)]
        entry = await posting.post(
            db,
            event_type=str(EventType.OPENING_BALANCE_POSTED),
            source_type=str(SourceType.OPENING_BALANCE),
            # Салбар бүрд нэг л удаа — source_id = салбар (идемпотент).
            source_id=branch.id,
            entry_date=as_of,
            description=memo,
            lines=lines,
            posted_by=user.id,
        )
        entry_id = getattr(entry, "id", None)

    branch.opening_done_at = now
    branch.opening_done_by = user.id
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="branch.opening",
        entity_type="branch",
        entity_id=branch.id,
        after={
            "as_of": as_of.isoformat(),
            "tanks": [{"tank_id": str(s.tank_id), "liters": str(s.liters), "unit_cost": str(s.unit_cost)} for s in payload.tanks],
            "nozzles": [{"nozzle_id": str(s.nozzle_id), "totalizer": str(s.totalizer)} for s in payload.nozzles],
            "fuel_value": str(fuel_value),
        },
        ip=_client_ip(request),
    )
    return BranchOpeningOut(
        branch_id=branch.id,
        opening_done_at=now,
        tanks_set=tanks_set,
        nozzles_set=nozzles_set,
        fuel_value=fuel_value,
        journal_entry_id=entry_id,
    )
