"""Үнийн өөрчлөлтийн хүсэлт ба батлалт (WP7).

Түлш болон барааны зарах үнэ **зөвхөн** энэ урсгалаар солигдоно:
``prices.request`` эрхтэй хүн хүсэлт гаргаж, ``prices.approve`` эрхтэй эзэн
батална.  Батлагдмагц үнэ тухайн секундэд хүчин төгөлдөр болно.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.database import get_db
from app.deps import require_permission
from app.enums import ApprovalStatus
from app.models.approval import PriceChange
from app.models.branch import Branch
from app.models.fuel import Fuel
from app.models.product import Product
from app.models.user import User
from app.money import q2
from app.schemas.product import (
    APPROVAL_STATUS_NAMES_MN,
    PRICE_TARGET_NAMES_MN,
    PriceChangeCreate,
    PriceChangeDecisionIn,
    PriceChangeListOut,
    PriceChangeOut,
)
from app.services import price_change_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["price_changes"])

ZERO = Decimal("0.00")

Requester = aliased(User)
Decider = aliased(User)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _row_to_out(row: Row) -> PriceChangeOut:
    (pc, fuel_name, fuel_code, product_name, product_sku, requested_name, decided_name, branch_name) = row

    old_price = q2(pc.old_price or ZERO)
    new_price = q2(pc.new_price or ZERO)
    diff = q2(new_price - old_price)
    diff_pct = q2(diff / old_price * 100) if old_price > 0 else ZERO
    is_fuel = str(pc.target_type) == price_change_service.TARGET_FUEL

    return PriceChangeOut(
        id=pc.id,
        target_type=pc.target_type,
        target_type_name=PRICE_TARGET_NAMES_MN.get(str(pc.target_type), str(pc.target_type)),
        branch_id=pc.branch_id,
        branch_name=branch_name,
        fuel_id=pc.fuel_id,
        product_id=pc.product_id,
        target_id=pc.fuel_id if is_fuel else pc.product_id,
        target_name=fuel_name if is_fuel else product_name,
        target_code=fuel_code if is_fuel else product_sku,
        old_price=old_price,
        new_price=new_price,
        diff=diff,
        diff_pct=diff_pct,
        reason=pc.reason,
        status=pc.status,
        status_name=APPROVAL_STATUS_NAMES_MN.get(str(pc.status), str(pc.status)),
        requested_by=pc.requested_by,
        requested_by_name=requested_name,
        decided_by=pc.decided_by,
        decided_by_name=decided_name,
        decided_at=pc.decided_at,
        decision_note=pc.decision_note,
        created_at=pc.created_at,
    )


def _base_query():
    return (
        select(
            PriceChange,
            Fuel.name_mn,
            Fuel.code,
            Product.name_mn,
            Product.sku,
            Requester.full_name,
            Decider.full_name,
            Branch.name,
        )
        .outerjoin(Fuel, Fuel.id == PriceChange.fuel_id)
        .outerjoin(Product, Product.id == PriceChange.product_id)
        .outerjoin(Requester, Requester.id == PriceChange.requested_by)
        .outerjoin(Decider, Decider.id == PriceChange.decided_by)
        .outerjoin(Branch, Branch.id == PriceChange.branch_id)
    )


async def _load_row(db: AsyncSession, price_change_id: uuid.UUID) -> Row:
    row = (await db.execute(_base_query().where(PriceChange.id == price_change_id))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Үнийн өөрчлөлтийн хүсэлт олдсонгүй")
    return row


async def _load_pc(db: AsyncSession, price_change_id: uuid.UUID) -> PriceChange:
    pc = await db.scalar(select(PriceChange).where(PriceChange.id == price_change_id))
    if pc is None:
        raise HTTPException(status_code=404, detail="Үнийн өөрчлөлтийн хүсэлт олдсонгүй")
    return pc


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
@router.get("/price-changes", response_model=PriceChangeListOut)
async def list_price_changes(
    status: ApprovalStatus | None = Query(default=None),
    target_type: str | None = Query(default=None, description="'fuel' эсвэл 'product'"),
    fuel_id: uuid.UUID | None = Query(default=None),
    product_id: uuid.UUID | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("products.view", "prices.request", "prices.approve")),
) -> PriceChangeListOut:
    conditions = []
    if status is not None:
        conditions.append(PriceChange.status == str(status))
    if target_type is not None:
        if target_type not in (price_change_service.TARGET_FUEL, price_change_service.TARGET_PRODUCT):
            raise HTTPException(status_code=422, detail="Үнийн өөрчлөлтийн төрөл буруу байна")
        conditions.append(PriceChange.target_type == target_type)
    if fuel_id is not None:
        conditions.append(PriceChange.fuel_id == fuel_id)
    if product_id is not None:
        conditions.append(PriceChange.product_id == product_id)
    if branch_id is not None:
        conditions.append(PriceChange.branch_id == branch_id)

    total = await db.scalar(select(func.count()).select_from(PriceChange).where(*conditions)) or 0
    rows = (
        await db.execute(
            _base_query()
            .where(*conditions)
            .order_by(PriceChange.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return PriceChangeListOut(items=[_row_to_out(r) for r in rows], total=int(total))


@router.get("/price-changes/{price_change_id}", response_model=PriceChangeOut)
async def get_price_change(
    price_change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("products.view", "prices.request", "prices.approve")),
) -> PriceChangeOut:
    return _row_to_out(await _load_row(db, price_change_id))


# --------------------------------------------------------------------------- #
# Хүсэлт гаргах
# --------------------------------------------------------------------------- #
@router.post("/price-changes", response_model=PriceChangeOut, status_code=201)
async def request_price_change(
    payload: PriceChangeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("prices.request")),
) -> PriceChangeOut:
    pc = await price_change_service.request_change(db, user, payload)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="price_change.request_http",
        entity_type="price_change",
        entity_id=pc.id,
        after={"new_price": str(pc.new_price), "target_type": str(pc.target_type)},
        ip=_client_ip(request),
    )
    return _row_to_out(await _load_row(db, pc.id))


# --------------------------------------------------------------------------- #
# Шийдвэр
# --------------------------------------------------------------------------- #
@router.post("/price-changes/{price_change_id}/approve", response_model=PriceChangeOut)
async def approve_price_change(
    price_change_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    owner: User = Depends(require_permission("prices.approve")),
) -> PriceChangeOut:
    pc = await _load_pc(db, price_change_id)
    await price_change_service.approve(db, owner, pc)

    await audit(
        db,
        user_id=owner.id,
        action="price_change.approve_http",
        entity_type="price_change",
        entity_id=pc.id,
        after={"status": str(pc.status), "new_price": str(pc.new_price)},
        ip=_client_ip(request),
    )
    return _row_to_out(await _load_row(db, pc.id))


@router.post("/price-changes/{price_change_id}/reject", response_model=PriceChangeOut)
async def reject_price_change(
    price_change_id: uuid.UUID,
    request: Request,
    payload: PriceChangeDecisionIn | None = None,
    db: AsyncSession = Depends(get_db),
    owner: User = Depends(require_permission("prices.approve")),
) -> PriceChangeOut:
    pc = await _load_pc(db, price_change_id)
    note = payload.note if payload is not None else None
    await price_change_service.reject(db, owner, pc, note)

    await audit(
        db,
        user_id=owner.id,
        action="price_change.reject_http",
        entity_type="price_change",
        entity_id=pc.id,
        after={"status": str(pc.status), "decision_note": pc.decision_note},
        ip=_client_ip(request),
    )
    return _row_to_out(await _load_row(db, pc.id))
