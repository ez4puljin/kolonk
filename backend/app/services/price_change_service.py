"""Үнийн өөрчлөлтийн батлах урсгал (WP7).

Түлш болон барааны зарах үнэ **зөвхөн** энэ урсгалаар солигдоно: менежер
хүсэлт гаргаж (``prices.request``), эзэн батална (``prices.approve``).
Ингэснээр үнэ хэн, хэзээ, ямар шалтгаанаар өөрчилснийг аудитаас бүрэн харна.

Энэ модуль ``db.commit()`` дуудахгүй — ``get_db`` эзэмшинэ (CONTRACTS.md §1).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalStatus
from app.models.approval import PriceChange
from app.models.branch import Branch
from app.models.fuel import Fuel
from app.models.product import Product
from app.models.user import User
from app.money import q2
from app.services import pricing_service
from app.services.audit_service import audit
from app.services.outbox_service import emit

ZERO = Decimal("0.00")

TARGET_FUEL = "fuel"
TARGET_PRODUCT = "product"


def _d(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def load_target(db: AsyncSession, pc: PriceChange) -> Fuel | Product:
    """Хүсэлтийн зорилтыг (түлш эсвэл бараа) ачаална."""
    if str(pc.target_type) == TARGET_FUEL:
        if pc.fuel_id is None:
            raise HTTPException(status_code=422, detail="Түлш сонгогдоогүй байна")
        fuel = await db.scalar(select(Fuel).where(Fuel.id == pc.fuel_id))
        if fuel is None:
            raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
        return fuel

    if pc.product_id is None:
        raise HTTPException(status_code=422, detail="Бараа сонгогдоогүй байна")
    product = await db.scalar(select(Product).where(Product.id == pc.product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    return product


def _current_price(target: Fuel | Product) -> Decimal:
    return q2(_d(target.price_per_liter if isinstance(target, Fuel) else target.price))


async def _effective_price(
    db: AsyncSession, target: Fuel | Product, branch_id: uuid.UUID | None
) -> Decimal:
    """Тухайн салбарт одоо мөрдөж буй үнэ (override эсвэл суурь)."""
    if isinstance(target, Fuel):
        return await pricing_service.effective_fuel_price(db, target, branch_id)
    return await pricing_service.effective_product_price(db, target, branch_id)


def _target_label(target: Fuel | Product) -> str:
    return f"{target.code} {target.name_mn}" if isinstance(target, Fuel) else f"{target.sku} {target.name_mn}"


async def request_change(db: AsyncSession, user: User, payload: Any) -> PriceChange:
    """Үнэ өөрчлөх хүсэлт үүсгэнэ (төлөв: хүлээгдэж буй).

    ``payload`` — ``PriceChangeCreate`` (эсвэл ижил талбартай объект):
    ``target_type``, ``fuel_id``/``product_id``, ``new_price``, ``reason``.
    """
    target_type = str(getattr(payload, "target_type", TARGET_FUEL))
    if target_type not in (TARGET_FUEL, TARGET_PRODUCT):
        raise HTTPException(status_code=422, detail="Үнийн өөрчлөлтийн төрөл буруу байна")

    fuel_id: uuid.UUID | None = getattr(payload, "fuel_id", None)
    product_id: uuid.UUID | None = getattr(payload, "product_id", None)
    branch_id: uuid.UUID | None = getattr(payload, "branch_id", None)
    new_price = q2(_d(getattr(payload, "new_price", None)))

    if branch_id is not None:
        branch = await db.scalar(select(Branch).where(Branch.id == branch_id))
        if branch is None:
            raise HTTPException(status_code=404, detail="Салбар олдсонгүй")

    if new_price < ZERO:
        raise HTTPException(status_code=422, detail="Үнэ сөрөг байж болохгүй")

    if target_type == TARGET_FUEL:
        product_id = None
        if fuel_id is None:
            raise HTTPException(status_code=422, detail="Түлш сонгогдоогүй байна")
    else:
        fuel_id = None
        if product_id is None:
            raise HTTPException(status_code=422, detail="Бараа сонгогдоогүй байна")

    draft = PriceChange(
        target_type=target_type,
        branch_id=branch_id,
        fuel_id=fuel_id,
        product_id=product_id,
        old_price=ZERO,
        new_price=new_price,
        reason=(getattr(payload, "reason", None) or None),
        # Хоосон бол батламагц шууд; ирээдүйн огноо бол тэр өдрөөс хэрэгжинэ.
        effective_date=getattr(payload, "effective_date", None),
        status=str(ApprovalStatus.PENDING),
        requested_by=user.id,
    )
    target = await load_target(db, draft)
    old_price = await _effective_price(db, target, branch_id)

    if new_price == old_price:
        raise HTTPException(status_code=422, detail="Шинэ үнэ одоогийн үнэтэй ижил байна")

    pending = await db.scalar(
        select(PriceChange).where(
            PriceChange.status == str(ApprovalStatus.PENDING),
            (PriceChange.fuel_id == fuel_id) if fuel_id is not None else (PriceChange.product_id == product_id),
            (PriceChange.branch_id == branch_id) if branch_id is not None else PriceChange.branch_id.is_(None),
        )
    )
    if pending is not None:
        raise HTTPException(status_code=422, detail="Энэ нэр төрөлд шийдэгдээгүй хүсэлт байна")

    draft.old_price = old_price
    db.add(draft)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="price_change.request",
        entity_type="price_change",
        entity_id=draft.id,
        before={"price": str(old_price)},
        after={
            "price": str(new_price),
            "target_type": target_type,
            "target": _target_label(target),
            "reason": draft.reason,
        },
    )
    return draft


async def _apply_price(db: AsyncSession, pc: PriceChange) -> None:
    """Батлагдсан хүсэлтийн шинэ үнийг зорилтод бодитоор тавина."""
    target = await load_target(db, pc)
    new_price = q2(_d(pc.new_price))
    if pc.branch_id is not None:
        # Зөвхөн тухайн салбарт үйлчлэх үнэ — суурь үнэ хөдлөхгүй.
        await pricing_service.set_branch_price(
            db,
            pc.branch_id,
            fuel_id=pc.fuel_id if isinstance(target, Fuel) else None,
            product_id=pc.product_id if not isinstance(target, Fuel) else None,
            price=new_price,
        )
    elif isinstance(target, Fuel):
        target.price_per_liter = new_price
    else:
        target.price = new_price
    pc.applied_at = datetime.now(UTC)


async def apply_due_changes(db: AsyncSession) -> int:
    """Хугацаа нь болсон хойшлуулсан үнийн өөрчлөлтүүдийг хэрэгжүүлнэ.

    «Тосны үнийн өөрчлөлт маргаашнаас» — батлагдсан ч ``effective_date`` нь
    ирээгүй өөрчлөлт үнэд нөлөөлөхгүй хүлээж, worker өдөр бүр энэ функцээр
    хугацаа болсныг нь тавьдаг.
    """
    from app.stationtime import today_local

    due = (
        await db.scalars(
            select(PriceChange).where(
                PriceChange.status == str(ApprovalStatus.APPROVED),
                PriceChange.applied_at.is_(None),
                PriceChange.effective_date.is_not(None),
                PriceChange.effective_date <= today_local(),
            )
        )
    ).all()
    for pc in due:
        await _apply_price(db, pc)
    await db.flush()
    return len(due)


async def approve(db: AsyncSession, owner: User, pc: PriceChange) -> PriceChange:
    """Хүсэлтийг батлана.

    ``effective_date`` нь ирээдүйд бол үнэ ХАРААХАН солигдохгүй — worker
    хугацаа болмогц хэрэгжүүлнэ (өнөөдрийн борлуулалт хуучин үнээрээ явна).
    """
    if str(pc.status) != str(ApprovalStatus.PENDING):
        raise HTTPException(status_code=422, detail="Энэ хүсэлт аль хэдийн шийдэгдсэн байна")

    from app.stationtime import today_local

    target = await load_target(db, pc)
    old_price = await _effective_price(db, target, pc.branch_id)
    new_price = q2(_d(pc.new_price))

    deferred = pc.effective_date is not None and pc.effective_date > today_local()
    if not deferred:
        await _apply_price(db, pc)

    pc.old_price = old_price
    pc.status = str(ApprovalStatus.APPROVED)
    pc.decided_by = owner.id
    pc.decided_at = datetime.now(UTC)
    await db.flush()

    await emit(
        db,
        aggregate_type="price_change",
        aggregate_id=pc.id,
        event_type="PRICE_CHANGE_APPROVED",
        payload={
            "price_change_id": str(pc.id),
            "target_type": str(pc.target_type),
            "branch_id": str(pc.branch_id) if pc.branch_id else None,
            "fuel_id": str(pc.fuel_id) if pc.fuel_id else None,
            "product_id": str(pc.product_id) if pc.product_id else None,
            "old_price": str(old_price),
            "new_price": str(new_price),
            "decided_by": str(owner.id),
            "decided_at": pc.decided_at.isoformat(),
        },
    )

    await audit(
        db,
        user_id=owner.id,
        action="price_change.approve",
        entity_type="price_change",
        entity_id=pc.id,
        before={"price": str(old_price), "status": str(ApprovalStatus.PENDING)},
        after={
            "price": str(new_price),
            "status": str(ApprovalStatus.APPROVED),
            "target": _target_label(target),
        },
    )
    return pc


async def reject(db: AsyncSession, owner: User, pc: PriceChange, note: str | None = None) -> PriceChange:
    """Хүсэлтээс татгалзана — үнэ хөдлөхгүй."""
    if str(pc.status) != str(ApprovalStatus.PENDING):
        raise HTTPException(status_code=422, detail="Энэ хүсэлт аль хэдийн шийдэгдсэн байна")

    pc.status = str(ApprovalStatus.REJECTED)
    pc.decided_by = owner.id
    pc.decided_at = datetime.now(UTC)
    pc.decision_note = (note or "").strip() or None
    await db.flush()

    await emit(
        db,
        aggregate_type="price_change",
        aggregate_id=pc.id,
        event_type="PRICE_CHANGE_REJECTED",
        payload={
            "price_change_id": str(pc.id),
            "target_type": str(pc.target_type),
            "fuel_id": str(pc.fuel_id) if pc.fuel_id else None,
            "product_id": str(pc.product_id) if pc.product_id else None,
            "new_price": str(q2(_d(pc.new_price))),
            "decided_by": str(owner.id),
            "decided_at": pc.decided_at.isoformat(),
            "decision_note": pc.decision_note,
        },
    )

    await audit(
        db,
        user_id=owner.id,
        action="price_change.reject",
        entity_type="price_change",
        entity_id=pc.id,
        before={"status": str(ApprovalStatus.PENDING)},
        after={"status": str(ApprovalStatus.REJECTED), "decision_note": pc.decision_note},
    )
    return pc
