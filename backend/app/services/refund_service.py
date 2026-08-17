"""Буцаалтын үйлчилгээ — хүсэлт → батламж → журнал (WP6).

Түгээгч буцаалт **хүснэ**, эзэн/менежер **батална**. Батлагдсан үед л:
  * борлуулалтын мөрийн ``refunded_qty`` нэмэгдэж,
  * борлуулалтын төлөв ``refunded``/``partial_refund`` болж,
  * ``restock=True`` үед барааны нөөц сэргэж (**түлш хэзээ ч сэргэхгүй**),
  * ``REFUND_POSTED`` журналын бичилт үүснэ.

Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй — ``get_db`` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import (
    ApprovalStatus,
    EventType,
    ItemType,
    PaymentMethod,
    RefundType,
    SaleStatus,
    SourceType,
)
from app.models.approval import Refund, RefundItem
from app.models.partner import Contract
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.user import User
from app.money import q2, q3, vat_from_gross
from app.services import posting_rules, sale_service
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import UnbalancedEntryError, posting

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")

#: Буцаалт хийх боломжтой төлбөрийн хэрэгслүүд.
REFUNDABLE_METHODS: tuple[str, ...] = (
    str(PaymentMethod.CASH),
    str(PaymentMethod.CARD),
    str(PaymentMethod.QR),
    str(PaymentMethod.CONTRACT),
)

REFUND_STATUS_MN: dict[str, str] = {
    ApprovalStatus.PENDING: "Хүлээгдэж буй",
    ApprovalStatus.APPROVED: "Батлагдсан",
    ApprovalStatus.REJECTED: "Татгалзсан",
}


def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _get(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    value = getattr(source, key, default)
    return default if value is None else value


def refundable_qty(item: SaleItem) -> Decimal:
    """Тухайн мөрөөс үлдсэн буцаах боломжтой тоо хэмжээ."""
    return q3(_dec(item.qty, ZERO_L) - _dec(item.refunded_qty, ZERO_L))


def line_share(total: Decimal, qty: Decimal, full_qty: Decimal) -> Decimal:
    """Мөрийн дүнг тоо хэмжээний хувиар хуваарилна (дугуйлалт 2 орон)."""
    full = _dec(full_qty, ZERO_L)
    if full <= 0:
        return ZERO
    return q2(_dec(total) * _dec(qty) / full)


def refund_method_for(sale: Sale) -> str:
    """Хамгийн их дүнтэй төлбөрийн хэрэгслээр буцаана (боломжтой бол)."""
    best_method = str(PaymentMethod.CASH)
    best_amount = Decimal("-1")
    for payment in sale.payments:
        method = str(payment.method)
        if method not in REFUNDABLE_METHODS:
            continue
        amount = q2(_dec(payment.amount))
        if amount > best_amount:
            best_amount = amount
            best_method = method
    return best_method


def refund_out(
    refund: Refund,
    *,
    sale_number: int | None = None,
    names: Mapping[uuid.UUID, str] | None = None,
    item_names: Mapping[uuid.UUID, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    names = names or {}
    item_names = item_names or {}
    return {
        "id": refund.id,
        "sale_id": refund.sale_id,
        "sale_number": sale_number,
        "refund_type": str(refund.refund_type),
        "amount": q2(_dec(refund.amount)),
        "vat_amount": q2(_dec(refund.vat_amount)),
        "cogs_amount": q2(_dec(refund.cogs_amount)),
        "reason": refund.reason,
        "restock": bool(refund.restock),
        "refund_method": str(refund.refund_method),
        "refund_method_name": sale_service.method_label(refund.refund_method),
        "status": str(refund.status),
        "status_name": REFUND_STATUS_MN.get(str(refund.status), str(refund.status)),
        "requested_by": refund.requested_by,
        "requested_by_name": names.get(refund.requested_by),
        "decided_by": refund.decided_by,
        "decided_by_name": names.get(refund.decided_by) if refund.decided_by else None,
        "decided_at": refund.decided_at,
        "decision_note": refund.decision_note,
        "shift_id": refund.shift_id,
        "items": [
            {
                "id": item.id,
                "sale_item_id": item.sale_item_id,
                "name": item_names.get(item.sale_item_id, ("", ""))[0],
                "item_type": item_names.get(item.sale_item_id, ("", ""))[1],
                "qty": q3(_dec(item.qty)),
                "amount": q2(_dec(item.amount)),
                "cogs_amount": q2(_dec(item.cogs_amount)),
            }
            for item in refund.items
        ],
        "created_at": refund.created_at,
    }


async def get_refund(db: AsyncSession, refund_id: uuid.UUID, *, lock: bool = False) -> Refund:
    stmt = select(Refund).where(Refund.id == refund_id)
    if lock:
        stmt = stmt.with_for_update()
    refund = await db.scalar(stmt)
    if refund is None:
        raise HTTPException(status_code=404, detail="Буцаалтын хүсэлт олдсонгүй")
    return refund


async def _load_sale(db: AsyncSession, sale_id: uuid.UUID) -> Sale:
    sale = await db.scalar(select(Sale).where(Sale.id == sale_id))
    if sale is None:
        raise HTTPException(status_code=404, detail="Борлуулалт олдсонгүй")
    return sale


async def _pending_qty(db: AsyncSession, sale_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    """Хараахан батлагдаагүй хүсэлтэд заагдсан тоо хэмжээ (давхар буцаахаас сэргийлнэ)."""
    rows = (
        await db.execute(
            select(RefundItem.sale_item_id, func.coalesce(func.sum(RefundItem.qty), ZERO))
            .select_from(RefundItem)
            .join(Refund, RefundItem.refund_id == Refund.id)
            .where(Refund.sale_id == sale_id, Refund.status == str(ApprovalStatus.PENDING))
            .group_by(RefundItem.sale_item_id)
        )
    ).all()
    return {row[0]: q2(_dec(row[1])) for row in rows}


async def _sale_item_names(db: AsyncSession, sale_item_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[str, str]]:
    if not sale_item_ids:
        return {}
    rows = (
        await db.execute(
            select(SaleItem.id, SaleItem.name_snapshot, SaleItem.item_type).where(
                SaleItem.id.in_(list(sale_item_ids))
            )
        )
    ).all()
    return {row[0]: (row[1], str(row[2])) for row in rows}


async def user_names(db: AsyncSession, ids: Sequence[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = (await db.execute(select(User.id, User.full_name).where(User.id.in_(wanted)))).all()
    return {row[0]: row[1] for row in rows}


# --------------------------------------------------------------------------- #
# Хүсэлт
# --------------------------------------------------------------------------- #
async def request_refund(
    db: AsyncSession,
    user: User,
    *,
    sale_id: uuid.UUID,
    refund_type: str = RefundType.FULL,
    items: Sequence[Any] | None = None,
    amount: Decimal | None = None,
    reason: str | None = None,
    restock: bool = False,
    refund_method: str | None = None,
) -> Refund:
    """Буцаалтын хүсэлт үүсгэнэ (төлөв ``pending``, нөөц/журнал хараахан хөдлөхгүй)."""
    shift = await sale_service.require_open_shift(db, user)
    sale = await _load_sale(db, sale_id)

    status = str(sale.status)
    if status == str(SaleStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Ноорог борлуулалтыг буцаах боломжгүй")
    if status == str(SaleStatus.REFUNDED):
        raise HTTPException(status_code=422, detail="Энэ борлуулалт бүрэн буцаагдсан байна")
    if status not in (str(SaleStatus.COMPLETED), str(SaleStatus.PARTIAL_REFUND)):
        raise HTTPException(status_code=422, detail="Зөвхөн хийгдсэн борлуулалтыг буцаана")

    sale_items = {item.id: item for item in sale.items}
    pending = await _pending_qty(db, sale.id)

    requested: list[tuple[SaleItem, Decimal]] = []
    raw_items = list(items or [])
    if raw_items:
        seen: set[uuid.UUID] = set()
        for raw in raw_items:
            raw_id = _get(raw, "sale_item_id")
            item_id = raw_id if isinstance(raw_id, uuid.UUID) else None
            if item_id is None:
                try:
                    item_id = uuid.UUID(str(raw_id))
                except (ValueError, TypeError) as exc:
                    raise HTTPException(status_code=422, detail="Буцаах мөр буруу байна") from exc
            if item_id in seen:
                raise HTTPException(status_code=422, detail="Нэг мөр давхардаж бүртгэгдсэн байна")
            seen.add(item_id)
            sale_item = sale_items.get(item_id)
            if sale_item is None:
                raise HTTPException(status_code=422, detail="Буцаах мөр энэ борлуулалтад хамаарахгүй байна")
            # Тоо хэмжээ ЛИТР — 3 оронтой. q2 болговол 31.034 л → 31.03 болж
            # бүтэн буцаалтын дүн борлуулалтынхаас зөрнө.
            qty = q3(_dec(_get(raw, "qty"), ZERO))
            if qty <= ZERO:
                raise HTTPException(status_code=422, detail="Буцаах тоо хэмжээ 0-ээс их байх ёстой")
            available = q3(refundable_qty(sale_item) - pending.get(sale_item.id, ZERO))
            if qty > available:
                raise HTTPException(
                    status_code=422,
                    detail=f"Буцаах тоо хэмжээ боломжтой хэмжээнээс ({available}) их байна",
                )
            requested.append((sale_item, qty))
    else:
        # Мөр заагаагүй бол үлдсэн бүх хэмжээг буцаана.
        for sale_item in sale.items:
            available = q3(refundable_qty(sale_item) - pending.get(sale_item.id, ZERO))
            if available > ZERO:
                requested.append((sale_item, available))

    if not requested:
        raise HTTPException(status_code=422, detail="Буцаах боломжтой мөр байхгүй байна")

    total_amount = ZERO
    total_cogs = ZERO
    lines: list[tuple[SaleItem, Decimal, Decimal, Decimal]] = []
    for sale_item, qty in requested:
        line_amount = line_share(_dec(sale_item.amount), qty, _dec(sale_item.qty, ZERO_L))
        line_cogs = line_share(_dec(sale_item.cogs_amount), qty, _dec(sale_item.qty, ZERO_L))
        total_amount = q2(total_amount + line_amount)
        total_cogs = q2(total_cogs + line_cogs)
        lines.append((sale_item, qty, line_amount, line_cogs))

    if total_amount <= ZERO:
        raise HTTPException(status_code=422, detail="Буцаалтын дүн 0-ээс их байх ёстой")
    if amount is not None and q2(_dec(amount)) != total_amount:
        raise HTTPException(
            status_code=422,
            detail=f"Буцаалтын дүн тооцоолсон дүнтэй ({total_amount}) тохирохгүй байна",
        )

    method = str(refund_method) if refund_method else refund_method_for(sale)
    if method not in REFUNDABLE_METHODS:
        raise HTTPException(status_code=422, detail="Энэ төлбөрийн хэрэгслээр буцаалт хийх боломжгүй")

    # Энэ хүсэлт батлагдвал борлуулалт бүрэн буцаагдах уу?
    requested_map = {sale_item.id: qty for sale_item, qty, _, _ in lines}
    fully = all(
        q3(refundable_qty(item) - pending.get(item.id, ZERO) - requested_map.get(item.id, ZERO)) <= ZERO
        for item in sale.items
    )
    resolved_type = str(RefundType.FULL if fully else RefundType.PARTIAL)
    if str(refund_type or "") == str(RefundType.PARTIAL):
        resolved_type = str(RefundType.PARTIAL)

    refund = Refund(
        sale_id=sale.id,
        refund_type=resolved_type,
        amount=total_amount,
        vat_amount=vat_from_gross(total_amount, settings.vat_rate),
        cogs_amount=total_cogs,
        reason=(reason or "").strip() or None,
        restock=bool(restock),
        refund_method=method,
        status=str(ApprovalStatus.PENDING),
        requested_by=user.id,
        shift_id=shift.id,
    )
    db.add(refund)
    await db.flush()

    for sale_item, qty, line_amount, line_cogs in lines:
        db.add(
            RefundItem(
                refund_id=refund.id,
                sale_item_id=sale_item.id,
                qty=qty,
                amount=line_amount,
                cogs_amount=line_cogs,
            )
        )
    await db.flush()

    await emit(
        db,
        aggregate_type="refund",
        aggregate_id=refund.id,
        event_type="REFUND_REQUESTED",
        payload={
            "refund_id": str(refund.id),
            "sale_id": str(sale.id),
            "amount": str(total_amount),
            "vat_amount": str(refund.vat_amount),
            "cogs_amount": str(total_cogs),
            "refund_method": method,
            "restock": bool(restock),
            "items": [
                {"sale_item_id": str(si.id), "qty": str(qty), "amount": str(amt)}
                for si, qty, amt, _ in lines
            ],
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="refund.request",
        entity_type="refund",
        entity_id=refund.id,
        after={
            "sale_id": str(sale.id),
            "amount": str(total_amount),
            "refund_method": method,
            "restock": bool(restock),
            "reason": refund.reason,
        },
    )
    # ``items`` цуглуулгыг тодорхой ачаална (async lazy-load-оос сэргийлнэ).
    await db.refresh(refund)
    return refund


# --------------------------------------------------------------------------- #
# Батлах / татгалзах
# --------------------------------------------------------------------------- #
async def approve_refund(
    db: AsyncSession,
    owner: User,
    refund: Refund,
    *,
    note: str | None = None,
) -> tuple[Refund, Sale, uuid.UUID | None]:
    """Буцаалтыг батлах — нөөц, төлөв, журналын бичилт бүгд энд хийгдэнэ."""
    if str(refund.status) != str(ApprovalStatus.PENDING):
        raise HTTPException(status_code=422, detail="Энэ хүсэлт аль хэдийн шийдвэрлэгдсэн байна")

    sale = await _load_sale(db, refund.sale_id)
    sale_items = {item.id: item for item in sale.items}

    refund_items = list(refund.items)
    if not refund_items:
        raise HTTPException(status_code=422, detail="Буцаалтын мөр байхгүй байна")

    restock_cogs = ZERO
    for line in refund_items:
        sale_item = sale_items.get(line.sale_item_id)
        if sale_item is None:
            raise HTTPException(status_code=422, detail="Буцаах мөр борлуулалтад олдсонгүй")
        qty = q3(_dec(line.qty))
        if qty > q3(refundable_qty(sale_item)):
            raise HTTPException(
                status_code=422,
                detail="Буцаах тоо хэмжээ боломжтой хэмжээнээс их байна",
            )
        sale_item.refunded_qty = q3(_dec(sale_item.refunded_qty, ZERO_L) + qty)

        if refund.restock and str(sale_item.item_type) == str(ItemType.PRODUCT):
            # Барааны нөөцийг WP7-ийн inventory_service эзэмшинэ. Түлш хэзээ ч сэргэхгүй.
            from app.services.inventory_service import restock_product

            product = await db.scalar(
                select(Product).where(Product.id == sale_item.product_id).with_for_update()
            )
            if product is None:
                raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
            await restock_product(
                db,
                product,
                qty,
                _dec(sale_item.unit_cost),
                ref_type=str(SourceType.REFUND),
                ref_id=refund.id,
                branch_id=getattr(sale, "branch_id", None),
            )
            restock_cogs = q2(restock_cogs + q2(_dec(line.cogs_amount)))

    fully_refunded = all(refundable_qty(item) <= ZERO_L for item in sale.items)
    sale.status = str(SaleStatus.REFUNDED if fully_refunded else SaleStatus.PARTIAL_REFUND)

    # Гэрээгээр буцаах үед авлагын үлдэгдэл буурна (журналд 1201 кредит бичигдэнэ).
    if str(refund.refund_method) == str(PaymentMethod.CONTRACT) and sale.contract_id is not None:
        contract = await db.scalar(
            select(Contract).where(Contract.id == sale.contract_id).with_for_update()
        )
        if contract is not None:
            contract.balance = q2(_dec(contract.balance) - q2(_dec(refund.amount)))

    now = datetime.now(UTC)
    refund.status = str(ApprovalStatus.APPROVED)
    refund.decided_by = owner.id
    refund.decided_at = now
    refund.decision_note = (note or "").strip() or None
    await db.flush()

    try:
        entry = await posting.post(
            db,
            event_type=str(EventType.REFUND_POSTED),
            source_type=str(SourceType.REFUND),
            source_id=refund.id,
            entry_date=now.date(),
            description=f"Буцаалт — борлуулалт №{sale.number}",
            lines=posting_rules.build_refund_lines(
                q2(_dec(refund.amount)),
                q2(_dec(refund.vat_amount)),
                restock_cogs,
                bool(refund.restock) and restock_cogs > ZERO,
                str(refund.refund_method),
            ),
            posted_by=owner.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=f"Журналын бичилт тэнцэхгүй байна: {exc}") from exc

    await emit(
        db,
        aggregate_type="refund",
        aggregate_id=refund.id,
        event_type=str(EventType.REFUND_POSTED),
        payload={
            "refund_id": str(refund.id),
            "sale_id": str(sale.id),
            "sale_status": str(sale.status),
            "amount": str(q2(_dec(refund.amount))),
            "vat_amount": str(q2(_dec(refund.vat_amount))),
            "restock": bool(refund.restock),
            "restock_cogs": str(restock_cogs),
            "refund_method": str(refund.refund_method),
            "decided_at": now.isoformat(),
        },
    )
    await audit(
        db,
        user_id=owner.id,
        action="refund.approve",
        entity_type="refund",
        entity_id=refund.id,
        before={"status": str(ApprovalStatus.PENDING)},
        after={
            "status": str(refund.status),
            "sale_status": str(sale.status),
            "amount": str(q2(_dec(refund.amount))),
            "note": refund.decision_note,
        },
    )
    await db.flush()
    return refund, sale, (entry.id if entry is not None else None)


async def reject_refund(
    db: AsyncSession,
    owner: User,
    refund: Refund,
    *,
    note: str | None = None,
) -> Refund:
    """Буцаалтын хүсэлтээс татгалзах — домэйнд ямар ч өөрчлөлт гарахгүй."""
    if str(refund.status) != str(ApprovalStatus.PENDING):
        raise HTTPException(status_code=422, detail="Энэ хүсэлт аль хэдийн шийдвэрлэгдсэн байна")

    refund.status = str(ApprovalStatus.REJECTED)
    refund.decided_by = owner.id
    refund.decided_at = datetime.now(UTC)
    refund.decision_note = (note or "").strip() or None
    await db.flush()

    await emit(
        db,
        aggregate_type="refund",
        aggregate_id=refund.id,
        event_type="REFUND_REJECTED",
        payload={
            "refund_id": str(refund.id),
            "sale_id": str(refund.sale_id),
            "amount": str(q2(_dec(refund.amount))),
            "note": refund.decision_note,
        },
    )
    await audit(
        db,
        user_id=owner.id,
        action="refund.reject",
        entity_type="refund",
        entity_id=refund.id,
        before={"status": str(ApprovalStatus.PENDING)},
        after={"status": str(refund.status), "note": refund.decision_note},
    )
    return refund


# --------------------------------------------------------------------------- #
# Жагсаалт
# --------------------------------------------------------------------------- #
async def list_refunds(
    db: AsyncSession,
    *,
    status: str | None = None,
    sale_id: uuid.UUID | None = None,
    shift_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conditions: list[Any] = []
    if status:
        conditions.append(Refund.status == str(status))
    if sale_id is not None:
        conditions.append(Refund.sale_id == sale_id)
    if shift_id is not None:
        conditions.append(Refund.shift_id == shift_id)

    total = await db.scalar(select(func.count()).select_from(Refund).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(Refund)
            .options(selectinload(Refund.items))
            .where(*conditions)
            .order_by(Refund.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    sale_ids = {row.sale_id for row in rows}
    numbers: dict[uuid.UUID, int] = {}
    if sale_ids:
        result = (await db.execute(select(Sale.id, Sale.number).where(Sale.id.in_(sale_ids)))).all()
        numbers = {r[0]: int(r[1]) for r in result}

    names = await user_names(db, [row.requested_by for row in rows] + [row.decided_by for row in rows])
    item_ids = [item.sale_item_id for row in rows for item in row.items]
    item_names = await _sale_item_names(db, item_ids)

    return {
        "items": [
            refund_out(row, sale_number=numbers.get(row.sale_id), names=names, item_names=item_names)
            for row in rows
        ],
        "total": int(total),
    }


async def refund_detail(db: AsyncSession, refund: Refund) -> dict[str, Any]:
    sale_number = await db.scalar(select(Sale.number).where(Sale.id == refund.sale_id))
    names = await user_names(db, [refund.requested_by, refund.decided_by])
    item_names = await _sale_item_names(db, [item.sale_item_id for item in refund.items])
    return refund_out(
        refund,
        sale_number=int(sale_number) if sale_number is not None else None,
        names=names,
        item_names=item_names,
    )
