"""Fuel master data.

Reading the fuel list is open to any signed-in user (the POS keypad needs it);
writing requires ``products.manage``.  The price is **not** editable here — it
only moves through the price-change approval flow (`/api/price-changes`).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.fuel import Fuel
from app.models.user import User
from app.schemas.fuel import FuelCreate, FuelListOut, FuelOut, FuelUpdate
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["fuels"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _snapshot(fuel: Fuel) -> dict:
    return {
        "code": fuel.code,
        "name_mn": fuel.name_mn,
        "price_per_liter": str(fuel.price_per_liter),
        "color_hex": fuel.color_hex,
        "sort_order": fuel.sort_order,
        "is_active": fuel.is_active,
    }


@router.get("/fuels", response_model=FuelListOut)
async def list_fuels(
    active_only: bool = Query(default=False, description="Зөвхөн идэвхтэй түлш"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> FuelListOut:
    stmt = select(Fuel)
    if active_only:
        stmt = stmt.where(Fuel.is_active.is_(True))
    stmt = stmt.order_by(Fuel.sort_order, Fuel.code)

    fuels = (await db.scalars(stmt)).all()
    return FuelListOut(items=[FuelOut.model_validate(f) for f in fuels], total=len(fuels))


@router.get("/fuels/{fuel_id}", response_model=FuelOut)
async def get_fuel(
    fuel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> FuelOut:
    fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
    if fuel is None:
        raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
    return FuelOut.model_validate(fuel)


@router.post("/fuels", response_model=FuelOut, status_code=201)
async def create_fuel(
    payload: FuelCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> FuelOut:
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="Түлшний код хоосон байж болохгүй")

    exists = await db.scalar(select(func.count()).select_from(Fuel).where(Fuel.code == code))
    if exists:
        raise HTTPException(status_code=422, detail="Ийм кодтой түлш бүртгэгдсэн байна")

    if payload.price_per_liter < 0:
        raise HTTPException(status_code=422, detail="Үнэ сөрөг байж болохгүй")

    fuel = Fuel(
        code=code,
        name_mn=payload.name_mn.strip(),
        price_per_liter=payload.price_per_liter,
        color_hex=payload.color_hex,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(fuel)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel.create",
        entity_type="fuel",
        entity_id=fuel.id,
        after=_snapshot(fuel),
        ip=_client_ip(request),
    )
    return FuelOut.model_validate(fuel)


@router.patch("/fuels/{fuel_id}", response_model=FuelOut)
async def update_fuel(
    fuel_id: uuid.UUID,
    payload: FuelUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> FuelOut:
    fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
    if fuel is None:
        raise HTTPException(status_code=404, detail="Түлш олдсонгүй")

    changes = payload.model_dump(exclude_unset=True)

    # The price is owned by the approval flow — never by this endpoint.
    if "price_per_liter" in changes:
        new_price = changes.pop("price_per_liter")
        if new_price is not None and new_price != fuel.price_per_liter:
            raise HTTPException(
                status_code=422,
                detail="Үнийг зөвхөн үнийн өөрчлөлтийн хүсэлтээр солино",
            )

    if "code" in changes and changes["code"] is not None:
        code = str(changes["code"]).strip()
        if not code:
            raise HTTPException(status_code=422, detail="Түлшний код хоосон байж болохгүй")
        if code != fuel.code:
            clash = await db.scalar(select(func.count()).select_from(Fuel).where(Fuel.code == code))
            if clash:
                raise HTTPException(status_code=422, detail="Ийм кодтой түлш бүртгэгдсэн байна")
        changes["code"] = code

    if "name_mn" in changes and changes["name_mn"] is not None:
        changes["name_mn"] = str(changes["name_mn"]).strip()

    before = _snapshot(fuel)
    for field, value in changes.items():
        if value is not None:
            setattr(fuel, field, value)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel.update",
        entity_type="fuel",
        entity_id=fuel.id,
        before=before,
        after=_snapshot(fuel),
        ip=_client_ip(request),
    )
    return FuelOut.model_validate(fuel)
