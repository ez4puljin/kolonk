"""Нийлүүлэгчийн бүртгэл ба өглөгийн тооцоо (WP7).

``GET /api/suppliers/{id}/ledger`` нь нийлүүлэгч тус бүрийн нэхэмжлэх, төлөлт,
үлдэгдлийг нэг дор өгнө: ``үлдэгдэл = Σ(нийт дүн − төлсөн)`` нээлттэй болон
хэсэгчлэн төлсөн нэхэмжлэхээр.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import InvoiceStatus
from app.models.accounting import ApInvoice, ApPayment
from app.models.partner import Supplier
from app.models.user import User
from app.money import q2
from app.schemas.procurement import (
    INVOICE_STATUS_NAMES_MN,
    ApInvoiceRow,
    ApPaymentRow,
    SupplierCreate,
    SupplierLedgerOut,
    SupplierListOut,
    SupplierOut,
    SupplierUpdate,
)
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["suppliers"])

ZERO = Decimal("0.00")

#: Үлдэгдэл тооцоход орох нэхэмжлэхийн төлвүүд.
OPEN_STATUSES = (str(InvoiceStatus.OPEN), str(InvoiceStatus.PARTIAL))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_out(supplier: Supplier, balance: Decimal = ZERO) -> SupplierOut:
    return SupplierOut(
        id=supplier.id,
        name=supplier.name,
        register_no=supplier.register_no,
        phone=supplier.phone,
        bank_account=supplier.bank_account,
        address=supplier.address,
        is_active=supplier.is_active,
        balance=q2(balance),
        created_at=supplier.created_at,
        updated_at=supplier.updated_at,
    )


def _snapshot(supplier: Supplier) -> dict:
    return {
        "name": supplier.name,
        "register_no": supplier.register_no,
        "phone": supplier.phone,
        "bank_account": supplier.bank_account,
        "address": supplier.address,
        "is_active": supplier.is_active,
    }


async def _load_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    supplier = await db.scalar(select(Supplier).where(Supplier.id == supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")
    return supplier


async def _balance_of(db: AsyncSession, supplier_id: uuid.UUID) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(ApInvoice.amount_gross - ApInvoice.amount_paid), 0)).where(
            ApInvoice.supplier_id == supplier_id,
            ApInvoice.status.in_(OPEN_STATUSES),
        )
    )
    return q2(Decimal(value or 0))


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
@router.get("/suppliers", response_model=SupplierListOut)
async def list_suppliers(
    search: str | None = Query(default=None, description="Нэр / регистр / утас"),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("suppliers.manage")),
) -> SupplierListOut:
    conditions = []
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Supplier.name.ilike(pattern),
                Supplier.register_no.ilike(pattern),
                Supplier.phone.ilike(pattern),
            )
        )
    if is_active is not None:
        conditions.append(Supplier.is_active.is_(is_active))

    total = await db.scalar(select(func.count()).select_from(Supplier).where(*conditions)) or 0
    suppliers = (
        await db.scalars(
            select(Supplier).where(*conditions).order_by(Supplier.name).limit(limit).offset(offset)
        )
    ).all()

    balances: dict[uuid.UUID, Decimal] = {}
    ids = [s.id for s in suppliers]
    if ids:
        rows = (
            await db.execute(
                select(
                    ApInvoice.supplier_id,
                    func.coalesce(func.sum(ApInvoice.amount_gross - ApInvoice.amount_paid), 0),
                )
                .where(ApInvoice.supplier_id.in_(ids), ApInvoice.status.in_(OPEN_STATUSES))
                .group_by(ApInvoice.supplier_id)
            )
        ).all()
        balances = {supplier_id: q2(Decimal(value or 0)) for supplier_id, value in rows}

    return SupplierListOut(
        items=[_to_out(s, balances.get(s.id, ZERO)) for s in suppliers],
        total=int(total),
    )


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("suppliers.manage")),
) -> SupplierOut:
    supplier = await _load_supplier(db, supplier_id)
    return _to_out(supplier, await _balance_of(db, supplier_id))


@router.get("/suppliers/{supplier_id}/ledger", response_model=SupplierLedgerOut)
async def supplier_ledger(
    supplier_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("suppliers.manage")),
) -> SupplierLedgerOut:
    supplier = await _load_supplier(db, supplier_id)

    invoice_conditions = [ApInvoice.supplier_id == supplier_id]
    payment_conditions = [ApPayment.supplier_id == supplier_id]
    if date_from is not None:
        invoice_conditions.append(ApInvoice.invoice_date >= date_from)
        payment_conditions.append(ApPayment.payment_date >= date_from)
    if date_to is not None:
        invoice_conditions.append(ApInvoice.invoice_date <= date_to)
        payment_conditions.append(ApPayment.payment_date <= date_to)

    invoices = (
        await db.scalars(
            select(ApInvoice)
            .where(*invoice_conditions)
            .order_by(ApInvoice.invoice_date.desc(), ApInvoice.created_at.desc())
        )
    ).all()
    payments = (
        await db.scalars(
            select(ApPayment)
            .where(*payment_conditions)
            .order_by(ApPayment.payment_date.desc(), ApPayment.created_at.desc())
        )
    ).all()

    invoice_no_by_id = {inv.id: inv.invoice_no for inv in invoices}
    today = date.today()

    invoice_rows: list[ApInvoiceRow] = []
    invoiced_total = ZERO
    balance = ZERO
    for inv in invoices:
        gross = q2(Decimal(inv.amount_gross or 0))
        paid = q2(Decimal(inv.amount_paid or 0))
        due = q2(gross - paid)
        invoiced_total = q2(invoiced_total + gross)
        if str(inv.status) in OPEN_STATUSES:
            balance = q2(balance + due)
        invoice_rows.append(
            ApInvoiceRow(
                id=inv.id,
                invoice_no=inv.invoice_no,
                invoice_date=inv.invoice_date,
                due_date=inv.due_date,
                source_type=inv.source_type,
                source_id=inv.source_id,
                amount_gross=gross,
                amount_paid=paid,
                amount_due=due,
                status=inv.status,
                status_name=INVOICE_STATUS_NAMES_MN.get(str(inv.status), str(inv.status)),
                is_overdue=(
                    inv.due_date is not None and inv.due_date < today and str(inv.status) in OPEN_STATUSES
                ),
                created_at=inv.created_at,
            )
        )

    payment_rows: list[ApPaymentRow] = []
    paid_total = ZERO
    for pay in payments:
        amount = q2(Decimal(pay.amount or 0))
        paid_total = q2(paid_total + amount)
        payment_rows.append(
            ApPaymentRow(
                id=pay.id,
                ap_invoice_id=pay.ap_invoice_id,
                invoice_no=invoice_no_by_id.get(pay.ap_invoice_id),
                amount=amount,
                paid_from=pay.paid_from,
                payment_date=pay.payment_date,
                note=pay.note,
                created_at=pay.created_at,
            )
        )

    return SupplierLedgerOut(
        supplier=_to_out(supplier, balance),
        invoices=invoice_rows,
        payments=payment_rows,
        invoiced_total=invoiced_total,
        paid_total=paid_total,
        balance=balance,
    )


# --------------------------------------------------------------------------- #
# Бичих
# --------------------------------------------------------------------------- #
@router.post("/suppliers", response_model=SupplierOut, status_code=201)
async def create_supplier(
    payload: SupplierCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> SupplierOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Нийлүүлэгчийн нэр хоосон байж болохгүй")

    clash = await db.scalar(select(func.count()).select_from(Supplier).where(Supplier.name == name))
    if clash:
        raise HTTPException(status_code=422, detail="Ийм нэртэй нийлүүлэгч бүртгэгдсэн байна")

    register_no = (payload.register_no or "").strip() or None
    if register_no:
        used = await db.scalar(
            select(func.count()).select_from(Supplier).where(Supplier.register_no == register_no)
        )
        if used:
            raise HTTPException(status_code=422, detail="Ийм регистртэй нийлүүлэгч бүртгэгдсэн байна")

    supplier = Supplier(
        name=name,
        register_no=register_no,
        phone=(payload.phone or "").strip() or None,
        bank_account=(payload.bank_account or "").strip() or None,
        address=(payload.address or "").strip() or None,
        is_active=payload.is_active,
    )
    db.add(supplier)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="supplier.create",
        entity_type="supplier",
        entity_id=supplier.id,
        after=_snapshot(supplier),
        ip=_client_ip(request),
    )
    return _to_out(supplier)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> SupplierOut:
    supplier = await _load_supplier(db, supplier_id)
    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(supplier)

    if changes.get("name") is not None:
        name = str(changes["name"]).strip()
        if not name:
            raise HTTPException(status_code=422, detail="Нийлүүлэгчийн нэр хоосон байж болохгүй")
        if name != supplier.name:
            clash = await db.scalar(
                select(func.count()).select_from(Supplier).where(Supplier.name == name)
            )
            if clash:
                raise HTTPException(status_code=422, detail="Ийм нэртэй нийлүүлэгч бүртгэгдсэн байна")
        changes["name"] = name

    if "register_no" in changes:
        register_no = (changes["register_no"] or "").strip() or None
        if register_no and register_no != supplier.register_no:
            used = await db.scalar(
                select(func.count()).select_from(Supplier).where(Supplier.register_no == register_no)
            )
            if used:
                raise HTTPException(status_code=422, detail="Ийм регистртэй нийлүүлэгч бүртгэгдсэн байна")
        changes["register_no"] = register_no

    for field in ("phone", "bank_account", "address"):
        if field in changes:
            changes[field] = (changes[field] or "").strip() or None

    for field, value in changes.items():
        if field in ("register_no", "phone", "bank_account", "address") or value is not None:
            setattr(supplier, field, value)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="supplier.update",
        entity_type="supplier",
        entity_id=supplier.id,
        before=before,
        after=_snapshot(supplier),
        ip=_client_ip(request),
    )
    return _to_out(supplier, await _balance_of(db, supplier.id))


@router.delete("/suppliers/{supplier_id}", status_code=204, response_model=None)
async def deactivate_supplier(
    supplier_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("suppliers.manage")),
) -> None:
    """Нийлүүлэгч устгагдахгүй — түүх, өглөгийн бичилт хэвээр үлдэнэ."""
    supplier = await _load_supplier(db, supplier_id)

    balance = await _balance_of(db, supplier_id)
    if balance > 0:
        raise HTTPException(
            status_code=422,
            detail="Төлөгдөөгүй өглөгтэй нийлүүлэгчийг идэвхгүй болгох боломжгүй",
        )

    before = _snapshot(supplier)
    supplier.is_active = False
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="supplier.deactivate",
        entity_type="supplier",
        entity_id=supplier.id,
        before=before,
        after=_snapshot(supplier),
        ip=_client_ip(request),
    )
