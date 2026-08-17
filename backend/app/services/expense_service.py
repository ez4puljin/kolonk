"""Үйл ажиллагааны зардлын баримт — үүсгэх, бүртгэх, жагсаах.

Дүрэм: энэ модуль **хэзээ ч** `db.commit()` дуудахгүй — `get_db` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import DocStatus, EventType, InvoiceStatus, ShiftStatus, SourceType
from app.models.accounting import Account, ApInvoice
from app.models.bank import BankAccount
from app.models.expense import Expense
from app.models.partner import Supplier
from app.models.shift import Shift
from app.models.user import User
from app.money import q2
from app.services.audit_service import audit
from app.services.coa import ACC
from app.services.outbox_service import emit
from app.services.posting import posting
from app.services.posting_rules import build_expense_lines
from app.stationtime import day_end, day_start, today_local

ZERO = Decimal("0.00")
PAYMENT_TERM_DAYS = 30

#: Зардлыг ямар эх үүсвэрээс төлж болох вэ.
PAYMENT_METHODS: dict[str, str] = {
    "cash": "Кассаас бэлнээр",
    "bank": "Харилцахаас",
    "credit": "Нийлүүлэгчийн өглөгөөр",
}


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _user_id(user: User | None) -> uuid.UUID | None:
    return getattr(user, "id", None) if user else None


async def list_categories(db: AsyncSession) -> list[dict[str, Any]]:
    """Зардал бүртгэх боломжтой данснууд (дэлгэцийн плиткууд)."""
    rows = (
        await db.scalars(
            select(Account)
            .where(Account.code.in_(ACC.OPERATING_EXPENSES))
            .order_by(Account.sort_order)
        )
    ).all()
    return [{"code": a.code, "name_mn": a.name_mn} for a in rows]


async def _open_shift_id(
    db: AsyncSession, branch_id: uuid.UUID | None = None
) -> uuid.UUID | None:
    """Бэлнээр төлсөн зардлыг хавсаргах нээлттэй ээлж.

    Салбар заавал шүүнэ — эс бөгөөс өөр салбарын нээлттэй ээлжид хавсарч,
    тэр ээлжийн кассын зөрүүг хуурамчаар гажуудуулна."""
    stmt = select(Shift.id).where(Shift.status == str(ShiftStatus.OPEN))
    if branch_id is not None:
        stmt = stmt.where(Shift.branch_id == branch_id)
    return await db.scalar(stmt.order_by(Shift.opened_at.desc()).limit(1))


async def create_expense(
    db: AsyncSession,
    user: User | None,
    *,
    account_code: str,
    amount: Decimal | str,
    payment_method: str,
    expense_date: date | None = None,
    has_vat: bool = False,
    supplier_id: uuid.UUID | None = None,
    bank_account_id: uuid.UUID | None = None,
    invoice_no: str | None = None,
    description: str | None = None,
    branch_id: uuid.UUID | None = None,
    post_now: bool = True,
) -> Expense:
    """Зардлын баримт үүсгэж, шууд ерөнхий дэвтэрт бичнэ.

    `amount` нь **төлсөн нийт дүн**. `has_vat=True` үед НӨАТ дүнд шингэсэн гэж
    үзэж (`vat = нийт / 11`) салгана — борлуулалттай ижил дүрэм.

    `branch_id` заагаагүй бол хэрэглэгчийн (эсвэл үндсэн) салбарт бичигдэнэ —
    салбаргүй зардал ямар ч салбарын цэвэр ашигт харагдахгүй үлддэг.
    """
    if account_code not in ACC.OPERATING_EXPENSES:
        raise HTTPException(status_code=422, detail="Зардлын данс биш байна")

    method = str(payment_method or "cash")
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="Төлбөрийн хэлбэр буруу байна")

    total = q2(_d(amount))
    if total <= ZERO:
        raise HTTPException(status_code=422, detail="Зардлын дүн 0-ээс их байх ёстой")

    if method == "credit" and supplier_id is None:
        raise HTTPException(
            status_code=422, detail="Өглөгөөр бүртгэхэд нийлүүлэгч заавал шаардлагатай"
        )

    # Харилцахаас төлсөн бол аль данснаас гарсныг мэдэх шаардлагатай — эс
    # бөгөөс дансны үлдэгдэл хөтлөгдөхгүй.  Данс бүртгээгүй бол алгасна.
    if method == "bank" and bank_account_id is not None:
        account_row = await db.get(BankAccount, bank_account_id)
        if account_row is None:
            raise HTTPException(status_code=404, detail="Харилцах данс олдсонгүй")
        if not account_row.is_active:
            raise HTTPException(status_code=422, detail="Харилцах данс идэвхгүй байна")
    elif method != "bank":
        bank_account_id = None

    supplier: Supplier | None = None
    if supplier_id is not None:
        supplier = await db.get(Supplier, supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")

    if has_vat:
        rate = Decimal(str(settings.vat_rate))
        vat = q2(total * rate / (Decimal("1") + rate))
    else:
        vat = ZERO
    subtotal = q2(total - vat)

    exp_date = expense_date or today_local()

    from app.services.branch_service import resolve_branch_id

    target_branch = await resolve_branch_id(db, user, branch_id)
    expense = Expense(
        expense_date=exp_date,
        branch_id=target_branch,
        account_code=account_code,
        payment_method=method,
        subtotal=subtotal,
        vat_amount=vat,
        total=total,
        supplier_id=supplier_id,
        shift_id=await _open_shift_id(db, target_branch) if method == "cash" else None,
        bank_account_id=bank_account_id,
        invoice_no=(invoice_no or "").strip() or None,
        description=(description or "").strip() or None,
        status=str(DocStatus.DRAFT),
        created_by=_user_id(user),
    )
    db.add(expense)
    await db.flush()

    if post_now:
        await post_expense(db, user, expense, supplier=supplier)
    return expense


async def post_expense(
    db: AsyncSession,
    user: User | None,
    expense: Expense,
    *,
    supplier: Supplier | None = None,
) -> Expense:
    """Ноорог зардлыг ерөнхий дэвтэрт бичиж, өглөгөөр бол нэхэмжлэх үүсгэнэ."""
    if str(expense.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Аль хэдийн бүртгэгдсэн")

    # Account-ийн үндсэн түлхүүр нь `id` (UUID) тул `db.get` ашиглаж болохгүй —
    # дансыг кодоор нь хайна.
    account = await db.scalar(select(Account).where(Account.code == expense.account_code))
    name = account.name_mn if account else expense.account_code

    # Өглөгөөр төлөх бол нийлүүлэгчийн нэхэмжлэх үүснэ.
    if str(expense.payment_method) == "credit":
        if supplier is None and expense.supplier_id is not None:
            supplier = await db.get(Supplier, expense.supplier_id)
        invoice = ApInvoice(
            supplier_id=expense.supplier_id,
            invoice_no=(expense.invoice_no or f"EX-{expense.number}"),
            invoice_date=expense.expense_date,
            due_date=expense.expense_date + timedelta(days=PAYMENT_TERM_DAYS),
            source_type=str(SourceType.EXPENSE),
            source_id=expense.id,
            amount_gross=expense.total,
            amount_paid=ZERO,
            status=str(InvoiceStatus.OPEN),
        )
        db.add(invoice)
        await db.flush()
        expense.ap_invoice_id = invoice.id

    await posting.post(
        db,
        event_type=str(EventType.EXPENSE_POSTED),
        source_type=str(SourceType.EXPENSE),
        source_id=expense.id,
        entry_date=expense.expense_date,
        description=f"Зардал №{expense.number} — {name}",
        lines=build_expense_lines(expense),
        posted_by=_user_id(user),
    )

    expense.status = str(DocStatus.POSTED)
    expense.posted_by = _user_id(user)
    expense.posted_at = datetime.now(UTC)
    await db.flush()

    await emit(
        db,
        aggregate_type="expense",
        aggregate_id=expense.id,
        event_type=str(EventType.EXPENSE_POSTED),
        payload={
            "expense_id": str(expense.id),
            "number": expense.number,
            "account_code": expense.account_code,
            "total": str(expense.total),
            "payment_method": expense.payment_method,
            "expense_date": expense.expense_date.isoformat(),
        },
    )
    await audit(
        db,
        user_id=_user_id(user),
        action="expense.create",
        entity_type="expense",
        entity_id=expense.id,
        after={
            "number": expense.number,
            "account_code": expense.account_code,
            "total": str(expense.total),
            "payment_method": expense.payment_method,
        },
    )
    return expense


async def list_expenses(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    payment_method: str | None = None,
    branch_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    filters = []
    if date_from is not None:
        filters.append(Expense.expense_date >= date_from)
    if date_to is not None:
        filters.append(Expense.expense_date <= date_to)
    if account_code:
        filters.append(Expense.account_code == account_code)
    if payment_method:
        filters.append(Expense.payment_method == payment_method)
    if branch_id is not None:
        filters.append(Expense.branch_id == branch_id)

    total_count = await db.scalar(select(func.count()).select_from(Expense).where(*filters)) or 0
    total_amount = (
        await db.scalar(
            select(func.coalesce(func.sum(Expense.total), ZERO)).where(
                *filters, Expense.status == str(DocStatus.POSTED)
            )
        )
        or ZERO
    )

    rows = (
        await db.scalars(
            select(Expense)
            .where(*filters)
            .order_by(Expense.expense_date.desc(), Expense.number.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    names = {a["code"]: a["name_mn"] for a in await list_categories(db)}
    supplier_ids = {e.supplier_id for e in rows if e.supplier_id}
    suppliers: dict[uuid.UUID, str] = {}
    if supplier_ids:
        suppliers = {
            s.id: s.name
            for s in (await db.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))).all()
        }

    bank_ids = {e.bank_account_id for e in rows if e.bank_account_id}
    banks: dict[uuid.UUID, str] = {}
    if bank_ids:
        banks = {
            b.id: f"{b.bank_name} · {b.account_number}"
            for b in (
                await db.scalars(select(BankAccount).where(BankAccount.id.in_(bank_ids)))
            ).all()
        }

    # Дансаар нь бүлэглэсэн задаргаа (дэлгэцийн хураангуй хэсэгт).
    by_account_rows = (
        await db.execute(
            select(Expense.account_code, func.coalesce(func.sum(Expense.total), ZERO))
            .where(*filters, Expense.status == str(DocStatus.POSTED))
            .group_by(Expense.account_code)
            .order_by(func.coalesce(func.sum(Expense.total), ZERO).desc())
        )
    ).all()

    return {
        "items": [
            {
                "id": e.id,
                "number": e.number,
                "expense_date": e.expense_date,
                "account_code": e.account_code,
                "account_name": names.get(e.account_code, e.account_code),
                "payment_method": e.payment_method,
                "payment_method_name": PAYMENT_METHODS.get(e.payment_method, e.payment_method),
                "subtotal": q2(_d(e.subtotal)),
                "vat_amount": q2(_d(e.vat_amount)),
                "total": q2(_d(e.total)),
                "supplier_id": e.supplier_id,
                "supplier_name": suppliers.get(e.supplier_id) if e.supplier_id else None,
                "bank_account_id": e.bank_account_id,
                "bank_account_name": banks.get(e.bank_account_id) if e.bank_account_id else None,
                "invoice_no": e.invoice_no,
                "description": e.description,
                "status": e.status,
            }
            for e in rows
        ],
        "total": total_count,
        "total_amount": q2(_d(total_amount)),
        "by_account": [
            {
                "account_code": code,
                "account_name": names.get(code, code),
                "amount": q2(_d(amount)),
            }
            for code, amount in by_account_rows
        ],
    }


async def expense_total(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> Decimal:
    """Тухайн хугацааны бүртгэгдсэн зардлын нийт дүн (самбарт ашиглана).

    ``branch_id`` өгвөл зөвхөн тэр салбарын зардал — эс бөгөөс салбар бүрийн
    цэвэр ашиг компанийн бүх зардлыг өөр дээрээ авч буруу гарна."""
    conditions = [
        Expense.status == str(DocStatus.POSTED),
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    ]
    if branch_id is not None:
        conditions.append(Expense.branch_id == branch_id)
    value = await db.scalar(select(func.coalesce(func.sum(Expense.total), ZERO)).where(*conditions))
    return q2(_d(value))
