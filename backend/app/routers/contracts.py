"""B2B гэрээ, авлагын нэхэмжлэх, төлбөрийн API (WP6)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import ContractStatus, InvoiceStatus
from app.models.accounting import ArInvoice
from app.models.partner import Contract, Customer
from app.models.user import User
from app.schemas.partner import (
    ArInvoiceListOut,
    ArInvoiceOut,
    ArPaymentIn,
    ArPaymentOut,
    ArPaymentResultOut,
    ContractCreate,
    ContractListOut,
    ContractOut,
    ContractUpdate,
    InvoiceGenerateIn,
    StatementOut,
)
from app.services import contract_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["contracts"])

CanManage = Depends(require_permission("contracts.manage"))
CanRead = Depends(require_permission("contracts.manage", "sales.create"))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _snapshot(contract: Contract) -> dict:
    return {
        "contract_no": contract.contract_no,
        "credit_limit": str(contract.credit_limit),
        "balance": str(contract.balance),
        "price_discount_per_l": str(contract.price_discount_per_l),
        "billing_day": contract.billing_day,
        "status": str(contract.status),
    }


async def _contract_numbers(db: AsyncSession, contract_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not contract_ids:
        return {}
    rows = (
        await db.execute(select(Contract.id, Contract.contract_no).where(Contract.id.in_(contract_ids)))
    ).all()
    return {row[0]: row[1] for row in rows}


# --------------------------------------------------------------------------- #
# Гэрээ
# --------------------------------------------------------------------------- #
@router.get("/contracts", response_model=ContractListOut)
async def list_contracts(
    customer_id: uuid.UUID | None = Query(default=None),
    status: ContractStatus | None = Query(default=None),
    search: str | None = Query(default=None, description="Гэрээний дугаар, харилцагчийн нэр"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanRead,
) -> ContractListOut:
    conditions: list = []
    if customer_id is not None:
        conditions.append(Contract.customer_id == customer_id)
    if status is not None:
        conditions.append(Contract.status == str(status))
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Contract.contract_no.ilike(pattern),
                Contract.customer_id.in_(select(Customer.id).where(Customer.name.ilike(pattern))),
            )
        )

    total = await db.scalar(select(func.count()).select_from(Contract).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(Contract).where(*conditions).order_by(Contract.contract_no).limit(limit).offset(offset)
        )
    ).all()
    return ContractListOut(
        items=[ContractOut(**contract_service.contract_out(row)) for row in rows], total=int(total)
    )


@router.get("/contracts/{contract_id}", response_model=ContractOut)
async def get_contract(
    contract_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = CanRead,
) -> ContractOut:
    contract = await contract_service.get_contract(db, contract_id)
    return ContractOut(**contract_service.contract_out(contract))


@router.post("/contracts", response_model=ContractOut, status_code=201)
async def create_contract(
    payload: ContractCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> ContractOut:
    customer = await db.scalar(select(Customer).where(Customer.id == payload.customer_id))
    if customer is None:
        raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй")
    if not customer.is_active:
        raise HTTPException(status_code=422, detail="Идэвхгүй харилцагчид гэрээ үүсгэх боломжгүй")

    contract_no = payload.contract_no.strip()
    if not contract_no:
        raise HTTPException(status_code=422, detail="Гэрээний дугаар хоосон байж болохгүй")
    clash = await db.scalar(
        select(func.count()).select_from(Contract).where(Contract.contract_no == contract_no)
    )
    if clash:
        raise HTTPException(status_code=422, detail="Ийм дугаартай гэрээ бүртгэгдсэн байна")

    contract = Contract(
        customer_id=customer.id,
        contract_no=contract_no,
        credit_limit=payload.credit_limit,
        balance=Decimal("0.00"),
        price_discount_per_l=payload.price_discount_per_l,
        billing_day=payload.billing_day,
        status=str(payload.status),
    )
    db.add(contract)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="contract.create",
        entity_type="contract",
        entity_id=contract.id,
        after=_snapshot(contract),
        ip=_client_ip(request),
    )
    return ContractOut(**contract_service.contract_out(contract, customer_name=customer.name))


@router.patch("/contracts/{contract_id}", response_model=ContractOut)
async def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> ContractOut:
    contract = await contract_service.get_contract(db, contract_id, lock=True)
    before = _snapshot(contract)
    changes = payload.model_dump(exclude_unset=True)

    if "contract_no" in changes and changes["contract_no"] is not None:
        contract_no = str(changes["contract_no"]).strip()
        if not contract_no:
            raise HTTPException(status_code=422, detail="Гэрээний дугаар хоосон байж болохгүй")
        if contract_no != contract.contract_no:
            clash = await db.scalar(
                select(func.count())
                .select_from(Contract)
                .where(Contract.contract_no == contract_no, Contract.id != contract.id)
            )
            if clash:
                raise HTTPException(status_code=422, detail="Ийм дугаартай гэрээ бүртгэгдсэн байна")
        contract.contract_no = contract_no
    if changes.get("credit_limit") is not None:
        contract.credit_limit = changes["credit_limit"]
    if changes.get("price_discount_per_l") is not None:
        contract.price_discount_per_l = changes["price_discount_per_l"]
    if changes.get("billing_day") is not None:
        contract.billing_day = int(changes["billing_day"])
    if changes.get("status") is not None:
        contract.status = str(changes["status"])

    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="contract.update",
        entity_type="contract",
        entity_id=contract.id,
        before=before,
        after=_snapshot(contract),
        ip=_client_ip(request),
    )
    return ContractOut(**contract_service.contract_out(contract))


# --------------------------------------------------------------------------- #
# Тооцоо нийлэх акт / нэхэмжлэх үүсгэх
# --------------------------------------------------------------------------- #
@router.get("/contracts/{contract_id}/statement", response_model=StatementOut)
async def contract_statement(
    contract_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> StatementOut:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise HTTPException(status_code=422, detail="Хугацааны эцэс эхлэлээсээ өмнө байж болохгүй")
    contract = await contract_service.get_contract(db, contract_id)
    return StatementOut(**await contract_service.statement(db, contract, date_from, date_to))


@router.post("/contracts/{contract_id}/invoices/generate", response_model=ArInvoiceListOut, status_code=201)
async def generate_contract_invoices(
    contract_id: uuid.UUID,
    payload: InvoiceGenerateIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> ArInvoiceListOut:
    contract = await contract_service.get_contract(db, contract_id)
    invoices = await contract_service.generate_invoices(
        db, payload.period_start, payload.period_end, contract.id
    )

    await audit(
        db,
        user_id=user.id,
        action="contract.invoice_generate",
        entity_type="contract",
        entity_id=contract.id,
        after={
            "period_start": payload.period_start.isoformat(),
            "period_end": payload.period_end.isoformat(),
            "invoices": len(invoices),
        },
        ip=_client_ip(request),
    )
    return ArInvoiceListOut(
        items=[
            ArInvoiceOut(**contract_service.invoice_out(inv, contract_no=contract.contract_no))
            for inv in invoices
        ],
        total=len(invoices),
    )


# --------------------------------------------------------------------------- #
# Авлагын нэхэмжлэх / төлбөр
# --------------------------------------------------------------------------- #
@router.get("/ar-invoices", response_model=ArInvoiceListOut)
async def list_ar_invoices(
    contract_id: uuid.UUID | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    status: InvoiceStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> ArInvoiceListOut:
    conditions: list = []
    if contract_id is not None:
        conditions.append(ArInvoice.contract_id == contract_id)
    if customer_id is not None:
        conditions.append(ArInvoice.customer_id == customer_id)
    if status is not None:
        conditions.append(ArInvoice.status == str(status))

    total = await db.scalar(select(func.count()).select_from(ArInvoice).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(ArInvoice)
            .where(*conditions)
            .order_by(ArInvoice.period_start.desc(), ArInvoice.invoice_no)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    numbers = await _contract_numbers(db, {row.contract_id for row in rows})
    return ArInvoiceListOut(
        items=[
            ArInvoiceOut(**contract_service.invoice_out(row, contract_no=numbers.get(row.contract_id)))
            for row in rows
        ],
        total=int(total),
    )


@router.post("/ar-payments", response_model=ArPaymentResultOut, status_code=201)
async def create_ar_payment(
    payload: ArPaymentIn,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> ArPaymentResultOut:
    payment, contract, invoice, entry_id = await contract_service.record_payment(
        db,
        user,
        contract_id=payload.contract_id,
        amount=payload.amount,
        received_to=payload.received_to,
        ar_invoice_id=payload.ar_invoice_id,
        payment_date=payload.payment_date,
        note=payload.note,
    )
    return ArPaymentResultOut(
        payment=ArPaymentOut.model_validate(payment),
        contract=ContractOut(**contract_service.contract_out(contract)),
        invoice=(
            ArInvoiceOut(**contract_service.invoice_out(invoice, contract_no=contract.contract_no))
            if invoice is not None
            else None
        ),
        journal_entry_id=entry_id,
    )
