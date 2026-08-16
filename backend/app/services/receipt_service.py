"""Нийлүүлэлтийн баримт бүртгэх хөдөлгүүр — шатахууны таталт ба барааны
худалдан авалт (WP7).

Нэг бизнес үйлдэл = нөөцийн хөдөлгөөн + өглөгийн нэхэмжлэх + журналын бичилт +
outbox + audit.  Бүгд **нэг** transaction дотор явагдана; энэ модуль хэзээ ч
``db.commit()`` дуудахгүй (CONTRACTS.md §1).

НӨАТ: нийлүүлэгчийн баримт НӨАТ-**гүй** дүнгээр ирдэг тул НӨАТ нь дүн дээр
**нэмэгдэнэ** (орох НӨАТ 1402) — CONTRACTS.md §2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import DocStatus, EventType, InvoiceStatus, SourceType
from app.models.accounting import ApInvoice
from app.models.fuel import Tank
from app.models.partner import Supplier
from app.models.procurement import FuelReceipt, Purchase, PurchaseItem
from app.models.product import Product
from app.models.user import User
from app.money import q2, q3, q6
from app.services import inventory_service, tank_service
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import posting
from app.services.posting_rules import build_fuel_receipt_lines, build_purchase_lines

ZERO = Decimal("0")

#: Нийлүүлэгчийн өглөгийн стандарт төлбөрийн хугацаа (хоног).
PAYMENT_TERM_DAYS = 30

VAT_RATE: Decimal = settings.vat_rate


# --------------------------------------------------------------------------- #
# Туслах
# --------------------------------------------------------------------------- #
def _d(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def _document_number(db: AsyncSession, doc: FuelReceipt | Purchase) -> int | None:
    """Дарааллаас (sequence) олгогдсон дугаарыг найдвартай уншина."""
    try:
        return doc.number
    except Exception:  # noqa: BLE001 — flush хийгдээгүй/хугацаа дууссан атрибут
        try:
            await db.refresh(doc, ["number"])
            return doc.number
        except Exception:  # noqa: BLE001
            return None


async def _load_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    supplier = await db.scalar(select(Supplier).where(Supplier.id == supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")
    return supplier


def _user_id(user: User | None) -> uuid.UUID | None:
    return getattr(user, "id", None)


# --------------------------------------------------------------------------- #
# Шатахууны таталт
# --------------------------------------------------------------------------- #
async def post_fuel_receipt(
    db: AsyncSession,
    user: User | None,
    receipt: FuelReceipt,
) -> FuelReceipt:
    """Шатахууны таталтыг бүртгэнэ (ноорог → бүртгэсэн).

    * ``subtotal`` = литр · нэгж өртөг + тээвэр (НӨАТ-гүй);
    * ``vat_amount`` = subtotal · 10% (**нэмэгдэнэ**);
    * ``landed_unit_cost`` = subtotal / литр — сав руу энэ өртгөөр орно;
    * нийлүүлэгчийн өглөгийн нэхэмжлэх нээгдэнэ;
    * ``FUEL_RECEIPT_POSTED`` журналын бичилт хийгдэнэ.
    """
    if str(receipt.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Аль хэдийн бүртгэгдсэн")

    liters = q3(_d(receipt.liters))
    if liters <= ZERO:
        raise HTTPException(status_code=422, detail="Татсан литр 0-ээс их байх ёстой")

    unit_cost = q6(_d(receipt.unit_cost))
    if unit_cost < ZERO:
        raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")

    freight = q2(_d(receipt.freight_cost))
    if freight < ZERO:
        raise HTTPException(status_code=422, detail="Тээврийн зардал сөрөг байж болохгүй")

    supplier = await _load_supplier(db, receipt.supplier_id)

    tank = await db.scalar(select(Tank).where(Tank.id == receipt.tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Сав олдсонгүй")
    if receipt.fuel_id != tank.fuel_id:
        raise HTTPException(status_code=422, detail="Савны түлш баримтын түлштэй таарахгүй байна")

    capacity = q3(_d(tank.capacity_l))
    if capacity > ZERO and q3(_d(tank.current_l) + liters) > capacity:
        raise HTTPException(status_code=422, detail="Савны багтаамжаас хэтэрч байна")

    subtotal = q2(q2(liters * unit_cost) + freight)
    vat_amount = q2(subtotal * VAT_RATE)
    total_gross = q2(subtotal + vat_amount)
    landed_unit_cost = q6(subtotal / liters)

    receipt.liters = liters
    receipt.unit_cost = unit_cost
    receipt.freight_cost = freight
    receipt.subtotal = subtotal
    receipt.vat_amount = vat_amount
    receipt.total_gross = total_gross
    receipt.landed_unit_cost = landed_unit_cost

    # 1. Савны нөөц — хөдлөх дундаж өртгөөр.
    await tank_service.receive_fuel(
        db,
        tank,
        liters,
        landed_unit_cost,
        ref_type=str(SourceType.FUEL_RECEIPT),
        ref_id=receipt.id,
    )

    number = await _document_number(db, receipt)

    # 2. Нийлүүлэгчийн өглөг.
    invoice = ApInvoice(
        supplier_id=receipt.supplier_id,
        invoice_no=((receipt.invoice_no or "").strip() or f"FR-{number if number is not None else str(receipt.id)[:8]}"),
        invoice_date=receipt.receipt_date,
        due_date=receipt.receipt_date + timedelta(days=PAYMENT_TERM_DAYS),
        source_type=str(SourceType.FUEL_RECEIPT),
        source_id=receipt.id,
        amount_gross=total_gross,
        amount_paid=Decimal("0.00"),
        status=str(InvoiceStatus.OPEN),
    )
    db.add(invoice)
    await db.flush()
    receipt.ap_invoice_id = invoice.id

    # 3. Журналын бичилт: 1301 + 1402 / 2101.
    entry = await posting.post(
        db,
        event_type=str(EventType.FUEL_RECEIPT_POSTED),
        source_type=str(SourceType.FUEL_RECEIPT),
        source_id=receipt.id,
        entry_date=receipt.receipt_date,
        description=f"Шатахуун таталт №{number} — {supplier.name}",
        lines=build_fuel_receipt_lines(receipt),
        posted_by=_user_id(user),
    )

    # 4. Баримтын төлөв.
    receipt.status = str(DocStatus.POSTED)
    receipt.posted_by = _user_id(user)
    receipt.posted_at = datetime.now(UTC)
    await db.flush()

    await emit(
        db,
        aggregate_type="fuel_receipt",
        aggregate_id=receipt.id,
        event_type=str(EventType.FUEL_RECEIPT_POSTED),
        payload={
            "fuel_receipt_id": str(receipt.id),
            "number": number,
            "supplier_id": str(receipt.supplier_id),
            "tank_id": str(receipt.tank_id),
            "fuel_id": str(receipt.fuel_id),
            "receipt_date": receipt.receipt_date.isoformat(),
            "liters": str(liters),
            "unit_cost": str(unit_cost),
            "freight_cost": str(freight),
            "subtotal": str(subtotal),
            "vat_amount": str(vat_amount),
            "total_gross": str(total_gross),
            "landed_unit_cost": str(landed_unit_cost),
            "ap_invoice_id": str(invoice.id),
            "journal_entry_id": str(entry.id) if entry is not None else None,
            "posted_at": receipt.posted_at.isoformat(),
        },
    )

    await audit(
        db,
        user_id=_user_id(user),
        action="fuel_receipt.post",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        before={"status": str(DocStatus.DRAFT)},
        after={
            "status": str(DocStatus.POSTED),
            "liters": str(liters),
            "subtotal": str(subtotal),
            "vat_amount": str(vat_amount),
            "total_gross": str(total_gross),
            "landed_unit_cost": str(landed_unit_cost),
            "tank_balance_l": str(tank.current_l),
            "tank_avg_cost": str(tank.avg_cost),
            "ap_invoice_id": str(invoice.id),
        },
    )
    return receipt


# --------------------------------------------------------------------------- #
# Барааны худалдан авалт
# --------------------------------------------------------------------------- #
async def post_purchase(
    db: AsyncSession,
    user: User | None,
    purchase: Purchase,
) -> Purchase:
    """Барааны худалдан авалтыг бүртгэнэ (ноорог → бүртгэсэн).

    Мөр бүрийн дүн = тоо хэмжээ · нэгж өртөг (НӨАТ-гүй).  Нийт дүн дээр НӨАТ
    нэмэгдэж өглөг үүснэ, бараа бүр хөдлөх дундаж өртгөөр нөөцөд орно.
    """
    if str(purchase.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Аль хэдийн бүртгэгдсэн")

    items: list[PurchaseItem] = list(purchase.items or [])
    if not items:
        raise HTTPException(status_code=422, detail="Худалдан авалтад бараа оруулаагүй байна")

    supplier = await _load_supplier(db, purchase.supplier_id)

    product_ids = {item.product_id for item in items}
    products = {
        p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
    }
    missing = product_ids - set(products)
    if missing:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")

    subtotal = ZERO
    for item in items:
        qty = q3(_d(item.qty))
        if qty <= ZERO:
            raise HTTPException(status_code=422, detail="Барааны тоо хэмжээ 0-ээс их байх ёстой")
        unit_cost = q6(_d(item.unit_cost))
        if unit_cost < ZERO:
            raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")
        amount = q2(qty * unit_cost)
        item.qty = qty
        item.unit_cost = unit_cost
        item.amount = amount
        subtotal = q2(subtotal + amount)

    vat_amount = q2(subtotal * VAT_RATE)
    total_gross = q2(subtotal + vat_amount)

    purchase.subtotal = subtotal
    purchase.vat_amount = vat_amount
    purchase.total_gross = total_gross

    # 1. Нөөц — бараа тус бүр хөдлөх дундаж өртгөөр, худалдан авалтын салбарт.
    from app.services.branch_service import resolve_branch_id

    branch_id = await resolve_branch_id(db, branch_id=purchase.branch_id)
    purchase.branch_id = branch_id
    for item in items:
        await inventory_service.receive_product(
            db,
            products[item.product_id],
            item.qty,
            item.unit_cost,
            ref_type=str(SourceType.PURCHASE),
            ref_id=purchase.id,
            branch_id=branch_id,
        )

    number = await _document_number(db, purchase)

    # 2. Нийлүүлэгчийн өглөг.
    invoice = ApInvoice(
        supplier_id=purchase.supplier_id,
        invoice_no=(
            (purchase.invoice_no or "").strip() or f"PU-{number if number is not None else str(purchase.id)[:8]}"
        ),
        invoice_date=purchase.purchase_date,
        due_date=purchase.purchase_date + timedelta(days=PAYMENT_TERM_DAYS),
        source_type=str(SourceType.PURCHASE),
        source_id=purchase.id,
        amount_gross=total_gross,
        amount_paid=Decimal("0.00"),
        status=str(InvoiceStatus.OPEN),
    )
    db.add(invoice)
    await db.flush()
    purchase.ap_invoice_id = invoice.id

    # 3. Журналын бичилт: 1302 + 1402 / 2101.
    entry = await posting.post(
        db,
        event_type=str(EventType.PURCHASE_POSTED),
        source_type=str(SourceType.PURCHASE),
        source_id=purchase.id,
        entry_date=purchase.purchase_date,
        description=f"Худалдан авалт №{number} — {supplier.name}",
        lines=build_purchase_lines(purchase),
        posted_by=_user_id(user),
    )

    # 4. Баримтын төлөв.
    purchase.status = str(DocStatus.POSTED)
    purchase.posted_by = _user_id(user)
    purchase.posted_at = datetime.now(UTC)
    await db.flush()

    await emit(
        db,
        aggregate_type="purchase",
        aggregate_id=purchase.id,
        event_type=str(EventType.PURCHASE_POSTED),
        payload={
            "purchase_id": str(purchase.id),
            "number": number,
            "supplier_id": str(purchase.supplier_id),
            "purchase_date": purchase.purchase_date.isoformat(),
            "subtotal": str(subtotal),
            "vat_amount": str(vat_amount),
            "total_gross": str(total_gross),
            "ap_invoice_id": str(invoice.id),
            "journal_entry_id": str(entry.id) if entry is not None else None,
            "posted_at": purchase.posted_at.isoformat(),
            "items": [
                {
                    "product_id": str(item.product_id),
                    "qty": str(item.qty),
                    "unit_cost": str(item.unit_cost),
                    "amount": str(item.amount),
                }
                for item in items
            ],
        },
    )

    await audit(
        db,
        user_id=_user_id(user),
        action="purchase.post",
        entity_type="purchase",
        entity_id=purchase.id,
        before={"status": str(DocStatus.DRAFT)},
        after={
            "status": str(DocStatus.POSTED),
            "item_count": len(items),
            "subtotal": str(subtotal),
            "vat_amount": str(vat_amount),
            "total_gross": str(total_gross),
            "ap_invoice_id": str(invoice.id),
        },
    )
    return purchase
