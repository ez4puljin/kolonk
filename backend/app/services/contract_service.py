"""B2B гэрээний үйлчилгээ — зээлийн лимит, сар бүрийн нэхэмжлэх, төлбөр, акт (WP6).

Гэрээгээр төлсөн борлуулалт бүр борлуулалтын үед аль хэдийн ``1201 Авлага``
данс руу бичигдсэн байдаг тул нэхэмжлэх үүсгэхэд журналын бичилт **хийхгүй** —
зөвхөн төлбөр хүлээн авахад ``AR_RECEIPT`` бичилт үүснэ.

Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй — ``get_db`` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    CashAccount,
    ContractStatus,
    EventType,
    InvoiceStatus,
    PaymentMethod,
    SaleStatus,
    SourceType,
)
from app.models.accounting import ArInvoice, ArPayment
from app.models.partner import Contract, Customer
from app.models.sale import Payment, Sale
from app.models.user import User
from app.money import q2
from app.stationtime import day_end, day_start
from app.services import posting_rules
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import UnbalancedEntryError, posting

ZERO = Decimal("0.00")

CONTRACT_STATUS_MN: dict[str, str] = {
    ContractStatus.ACTIVE: "Идэвхтэй",
    ContractStatus.SUSPENDED: "Түдгэлзсэн",
    ContractStatus.CLOSED: "Хаагдсан",
}

INVOICE_STATUS_MN: dict[str, str] = {
    InvoiceStatus.OPEN: "Нээлттэй",
    InvoiceStatus.PARTIAL: "Хэсэгчлэн төлөгдсөн",
    InvoiceStatus.PAID: "Төлөгдсөн",
}

STATEMENT_KIND_MN: dict[str, str] = {
    "opening": "Эхний үлдэгдэл",
    "sale": "Борлуулалт",
    "payment": "Төлбөр",
}


def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _rel(obj: Any, name: str) -> Any:
    """Ачаалагдсан relationship-ийг буцаана.

    Ачаалагдаагүй бол ``None`` — async орчинд санамсаргүй lazy-load хийж
    ``MissingGreenlet`` алдаа гаргахаас сэргийлнэ.
    """
    from sqlalchemy import inspect as sa_inspect

    try:
        if name in sa_inspect(obj).unloaded:
            return None
    except Exception:  # noqa: BLE001 — ORM объект биш бол шууд уншина
        return getattr(obj, name, None)
    return getattr(obj, name, None)


def _day_start(value: date) -> datetime:
    return day_start(value)


def _day_end(value: date) -> datetime:
    return day_end(value)


# --------------------------------------------------------------------------- #
# Зээлийн лимит
# --------------------------------------------------------------------------- #
def credit_available(contract: Contract) -> Decimal:
    """Гэрээгээр ашиглаж болох үлдсэн лимит."""
    return q2(_dec(contract.credit_limit) - _dec(contract.balance))


def assert_credit(contract: Contract, amount: Decimal) -> None:
    """``balance + amount <= credit_limit`` эсэхийг шалгана."""
    value = q2(_dec(amount))
    if value <= ZERO:
        raise HTTPException(status_code=422, detail="Дүн 0-ээс их байх ёстой")
    if str(contract.status) != str(ContractStatus.ACTIVE):
        raise HTTPException(status_code=422, detail="Гэрээ идэвхгүй байна")
    if q2(_dec(contract.balance) + value) > q2(_dec(contract.credit_limit)):
        raise HTTPException(status_code=422, detail="Гэрээний зээлийн лимит хэтэрсэн байна")


def contract_out(contract: Contract, *, customer_name: str | None = None) -> dict[str, Any]:
    """``ContractOut``-д тохирсон dict."""
    name = customer_name
    if name is None:
        customer = _rel(contract, "customer")
        name = customer.name if customer is not None else None
    return {
        "id": contract.id,
        "customer_id": contract.customer_id,
        "customer_name": name,
        "contract_no": contract.contract_no,
        "credit_limit": q2(_dec(contract.credit_limit)),
        "balance": q2(_dec(contract.balance)),
        "credit_available": credit_available(contract),
        "price_discount_per_l": q2(_dec(contract.price_discount_per_l)),
        "billing_day": int(contract.billing_day or 1),
        "status": str(contract.status),
        "status_name": CONTRACT_STATUS_MN.get(str(contract.status), str(contract.status)),
        "created_at": contract.created_at,
        "updated_at": contract.updated_at,
    }


def invoice_out(invoice: ArInvoice, *, contract_no: str | None = None) -> dict[str, Any]:
    customer = _rel(invoice, "customer")
    return {
        "id": invoice.id,
        "customer_id": invoice.customer_id,
        "customer_name": customer.name if customer is not None else None,
        "contract_id": invoice.contract_id,
        "contract_no": contract_no,
        "invoice_no": invoice.invoice_no,
        "period_start": invoice.period_start,
        "period_end": invoice.period_end,
        "issued_at": invoice.issued_at,
        "amount": q2(_dec(invoice.amount)),
        "amount_paid": q2(_dec(invoice.amount_paid)),
        "amount_due": q2(_dec(invoice.amount) - _dec(invoice.amount_paid)),
        "status": str(invoice.status),
        "status_name": INVOICE_STATUS_MN.get(str(invoice.status), str(invoice.status)),
        "lines": list(invoice.lines or []),
    }


async def get_contract(db: AsyncSession, contract_id: uuid.UUID, *, lock: bool = False) -> Contract:
    stmt = select(Contract).where(Contract.id == contract_id)
    if lock:
        stmt = stmt.with_for_update()
    contract = await db.scalar(stmt)
    if contract is None:
        raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
    return contract


# --------------------------------------------------------------------------- #
# Гэрээгээр төлөгдсөн борлуулалтууд
# --------------------------------------------------------------------------- #
async def _contract_sales(
    db: AsyncSession,
    contract_id: uuid.UUID,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    """Тухайн гэрээгээр төлөгдсөн борлуулалтын мөрүүд (огноогоор)."""
    conditions: list[Any] = [
        Payment.method == str(PaymentMethod.CONTRACT),
        Payment.contract_id == contract_id,
        Sale.status != str(SaleStatus.DRAFT),
    ]
    if date_from is not None:
        conditions.append(Sale.completed_at >= date_from)
    if date_to is not None:
        conditions.append(Sale.completed_at <= date_to)

    rows = (
        await db.execute(
            select(Sale.id, Sale.number, Sale.completed_at, Payment.amount)
            .select_from(Payment)
            .join(Sale, Payment.sale_id == Sale.id)
            .where(*conditions)
            .order_by(Sale.completed_at, Sale.number)
        )
    ).all()
    return [
        {
            "sale_id": str(row[0]),
            "sale_number": int(row[1]) if row[1] is not None else None,
            "date": row[2].isoformat() if row[2] is not None else None,
            "amount": str(q2(_dec(row[3]))),
            "_completed_at": row[2],
            "_amount": q2(_dec(row[3])),
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# Нэхэмжлэх үүсгэх
# --------------------------------------------------------------------------- #
def invoice_number(period_start: date, contract_no: str) -> str:
    return f"AR-{period_start:%Y%m}-{contract_no}"


async def generate_invoices(
    db: AsyncSession,
    period_start: date,
    period_end: date,
    contract_id: uuid.UUID | None = None,
) -> list[ArInvoice]:
    """Тухайн үеийн гэрээт борлуулалтаас нэхэмжлэх үүсгэнэ.

    ``(contract_id, period_start)``-аар идемпотент — давхардвал байгаа
    нэхэмжлэхээ буцаана.
    """
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Хугацааны эцэс эхлэлээсээ өмнө байж болохгүй")

    stmt = select(Contract)
    if contract_id is not None:
        stmt = stmt.where(Contract.id == contract_id)
    else:
        stmt = stmt.where(Contract.status == str(ContractStatus.ACTIVE))
    contracts = (await db.scalars(stmt.order_by(Contract.contract_no))).all()
    if contract_id is not None and not contracts:
        raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")

    date_from = _day_start(period_start)
    date_to = _day_end(period_end)

    invoices: list[ArInvoice] = []
    for contract in contracts:
        existing = await db.scalar(
            select(ArInvoice).where(
                ArInvoice.contract_id == contract.id,
                ArInvoice.period_start == period_start,
            )
        )
        if existing is not None:
            invoices.append(existing)
            continue

        rows = await _contract_sales(db, contract.id, date_from=date_from, date_to=date_to)
        if not rows:
            continue
        amount = q2(sum((row["_amount"] for row in rows), ZERO))
        if amount <= ZERO:
            continue

        invoice = ArInvoice(
            customer_id=contract.customer_id,
            contract_id=contract.id,
            invoice_no=invoice_number(period_start, contract.contract_no),
            period_start=period_start,
            period_end=period_end,
            issued_at=datetime.now(UTC),
            amount=amount,
            amount_paid=ZERO,
            status=str(InvoiceStatus.OPEN),
            lines=[
                {
                    "sale_id": row["sale_id"],
                    "sale_number": row["sale_number"],
                    "date": row["date"],
                    "amount": row["amount"],
                }
                for row in rows
            ],
        )
        db.add(invoice)
        invoices.append(invoice)

    await db.flush()
    return invoices


# --------------------------------------------------------------------------- #
# Төлбөр хүлээн авах
# --------------------------------------------------------------------------- #
async def record_payment(
    db: AsyncSession,
    user: User,
    *,
    contract_id: uuid.UUID,
    amount: Decimal,
    received_to: str = "bank",
    bank_account_id: uuid.UUID | None = None,
    ar_invoice_id: uuid.UUID | None = None,
    payment_date: date | None = None,
    note: str | None = None,
) -> tuple[ArPayment, Contract, ArInvoice | None, uuid.UUID | None]:
    """Гэрээт авлагын төлбөр — ``ArPayment`` + үлдэгдэл + нэхэмжлэх + AR_RECEIPT."""
    value = q2(_dec(amount))
    if value <= ZERO:
        raise HTTPException(status_code=422, detail="Төлбөрийн дүн 0-ээс их байх ёстой")

    where_to = str(received_to or "bank").strip().lower()
    if where_to not in (str(CashAccount.BANK), str(CashAccount.CASH)):
        raise HTTPException(status_code=422, detail="Хүлээн авах данс зөвхөн 'bank' эсвэл 'cash' байна")

    contract = await get_contract(db, contract_id, lock=True)
    pay_date = payment_date or datetime.now(UTC).date()

    invoice: ArInvoice | None = None
    if ar_invoice_id is not None:
        invoice = await db.scalar(select(ArInvoice).where(ArInvoice.id == ar_invoice_id).with_for_update())
        if invoice is None:
            raise HTTPException(status_code=404, detail="Нэхэмжлэх олдсонгүй")
        if invoice.contract_id != contract.id:
            raise HTTPException(status_code=422, detail="Нэхэмжлэх энэ гэрээнд хамаарахгүй байна")
        due = q2(_dec(invoice.amount) - _dec(invoice.amount_paid))
        if due <= ZERO:
            raise HTTPException(status_code=422, detail="Энэ нэхэмжлэх бүрэн төлөгдсөн байна")
        if value > due:
            raise HTTPException(status_code=422, detail=f"Төлбөрийн дүн үлдэгдлээс ({due}) их байна")

    before = {"balance": str(q2(_dec(contract.balance)))}

    payment = ArPayment(
        ar_invoice_id=invoice.id if invoice is not None else None,
        bank_account_id=(bank_account_id if where_to == str(CashAccount.BANK) else None),
        customer_id=contract.customer_id,
        contract_id=contract.id,
        amount=value,
        received_to=where_to,
        payment_date=pay_date,
        note=note,
        created_by=user.id,
    )
    db.add(payment)
    await db.flush()

    contract.balance = q2(_dec(contract.balance) - value)

    if invoice is not None:
        invoice.amount_paid = q2(_dec(invoice.amount_paid) + value)
        invoice.status = (
            str(InvoiceStatus.PAID)
            if invoice.amount_paid >= q2(_dec(invoice.amount))
            else str(InvoiceStatus.PARTIAL)
        )

    try:
        entry = await posting.post(
            db,
            event_type=str(EventType.AR_RECEIPT),
            source_type=str(SourceType.AR_PAYMENT),
            source_id=payment.id,
            entry_date=pay_date,
            description=f"Гэрээт авлагын төлбөр — {contract.contract_no}",
            lines=posting_rules.build_ar_receipt_lines(payment),
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=f"Журналын бичилт тэнцэхгүй байна: {exc}") from exc

    await emit(
        db,
        aggregate_type="ar_payment",
        aggregate_id=payment.id,
        event_type=str(EventType.AR_RECEIPT),
        payload={
            "ar_payment_id": str(payment.id),
            "contract_id": str(contract.id),
            "customer_id": str(contract.customer_id),
            "ar_invoice_id": str(invoice.id) if invoice is not None else None,
            "amount": str(value),
            "received_to": where_to,
            "payment_date": pay_date.isoformat(),
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="contract.payment",
        entity_type="contract",
        entity_id=contract.id,
        before=before,
        after={
            "balance": str(q2(_dec(contract.balance))),
            "amount": str(value),
            "received_to": where_to,
            "ar_invoice_id": str(invoice.id) if invoice is not None else None,
        },
    )
    await db.flush()

    return payment, contract, invoice, (entry.id if entry is not None else None)


# --------------------------------------------------------------------------- #
# Тооцоо нийлэх акт
# --------------------------------------------------------------------------- #
async def statement(
    db: AsyncSession,
    contract: Contract,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """Эхний үлдэгдэл → борлуулалт → төлбөр → эцсийн үлдэгдэл."""
    start = _day_start(date_from) if date_from is not None else None
    end = _day_end(date_to) if date_to is not None else None

    # --- Эхний үлдэгдэл ---
    opening = ZERO
    if start is not None:
        sales_before = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), ZERO))
            .select_from(Payment)
            .join(Sale, Payment.sale_id == Sale.id)
            .where(
                Payment.method == str(PaymentMethod.CONTRACT),
                Payment.contract_id == contract.id,
                Sale.status != str(SaleStatus.DRAFT),
                Sale.completed_at < start,
            )
        )
        payments_before = await db.scalar(
            select(func.coalesce(func.sum(ArPayment.amount), ZERO)).where(
                ArPayment.contract_id == contract.id,
                ArPayment.payment_date < date_from,
            )
        )
        opening = q2(_dec(sales_before) - _dec(payments_before))

    rows: list[dict[str, Any]] = []
    balance = opening
    rows.append(
        {
            "date": start,
            "kind": "opening",
            "kind_name": STATEMENT_KIND_MN["opening"],
            "ref": None,
            "description": "Эхний үлдэгдэл",
            "debit": ZERO,
            "credit": ZERO,
            "balance": balance,
        }
    )

    sale_rows = await _contract_sales(db, contract.id, date_from=start, date_to=end)
    payment_conditions: list[Any] = [ArPayment.contract_id == contract.id]
    if date_from is not None:
        payment_conditions.append(ArPayment.payment_date >= date_from)
    if date_to is not None:
        payment_conditions.append(ArPayment.payment_date <= date_to)
    payment_rows = (
        await db.scalars(
            select(ArPayment).where(*payment_conditions).order_by(ArPayment.payment_date, ArPayment.created_at)
        )
    ).all()

    events: list[tuple[datetime, str, dict[str, Any]]] = []
    for row in sale_rows:
        when = row["_completed_at"] or datetime.now(UTC)
        events.append((when, "sale", row))
    for pay in payment_rows:
        when = _day_start(pay.payment_date)
        events.append((when, "payment", {"payment": pay}))
    events.sort(key=lambda ev: ev[0])

    sales_total = ZERO
    payments_total = ZERO
    for when, kind, data in events:
        if kind == "sale":
            amount = data["_amount"]
            sales_total = q2(sales_total + amount)
            balance = q2(balance + amount)
            rows.append(
                {
                    "date": when,
                    "kind": "sale",
                    "kind_name": STATEMENT_KIND_MN["sale"],
                    "ref": f"№{data['sale_number']}" if data["sale_number"] is not None else None,
                    "description": "Гэрээгээр авсан түлш/бараа",
                    "debit": amount,
                    "credit": ZERO,
                    "balance": balance,
                }
            )
        else:
            pay: ArPayment = data["payment"]
            amount = q2(_dec(pay.amount))
            payments_total = q2(payments_total + amount)
            balance = q2(balance - amount)
            rows.append(
                {
                    "date": when,
                    "kind": "payment",
                    "kind_name": STATEMENT_KIND_MN["payment"],
                    "ref": pay.note,
                    "description": "Төлбөр хүлээн авсан"
                    + (" (касс)" if str(pay.received_to) == str(CashAccount.CASH) else " (данс)"),
                    "debit": ZERO,
                    "credit": amount,
                    "balance": balance,
                }
            )

    customer_name = await db.scalar(select(Customer.name).where(Customer.id == contract.customer_id))

    return {
        "contract": contract_out(contract, customer_name=customer_name),
        "date_from": date_from,
        "date_to": date_to,
        "opening_balance": opening,
        "sales_total": sales_total,
        "payments_total": payments_total,
        "closing_balance": balance,
        "rows": rows,
    }
