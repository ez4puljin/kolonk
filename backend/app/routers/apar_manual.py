"""Өглөг, авлагыг ГАРААР үүсгэх (Санхүү → Өглөг, авлага).

* ``POST /contracts/{id}/charges`` — харилцагчийн гэрээнд авлага нэмэх/хасах:
  гэрээний ``opening_balance``, ``balance`` өөрчлөгдөж (тооцооны хуулгад
  «Эхний үлдэгдэл»-д орно), журналд Дт 1201 (харилцагчийн хэмжүүр) / Кт 3101
  (эхний үлдэгдэл, залруулга) эсвэл Кт 4903 (бусад орлого). Сөрөг дүн — буцаж.
* ``POST /ap-invoices`` — нийлүүлэгчийн өглөгийн нэхэмжлэх гараар: Кт 2101
  (нийлүүлэгчийн хэмжүүр) / Дт 3101 (эхний үлдэгдэл) эсвэл зардлын данс.
  Төлбөрийг ердийн «Өглөг төлөх» урсгалаар хаана.

Хоёулаа идемпотент биш (гар үйлдэл бүр шинэ бичилт) тул ``source_id`` санамсаргүй.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import EventType, InvoiceStatus, SourceType
from app.models.accounting import ApInvoice
from app.models.partner import Contract, Customer, Supplier
from app.models.user import User
from app.money import q2
from app.schemas.accounting import ApInvoiceOut
from app.schemas.partner import ContractOut
from app.services import contract_service
from app.services.audit_service import audit
from app.services.coa import ACC
from app.services.posting import Dims, LineSpec, posting

router = APIRouter(prefix="/api", tags=["accounting"])

ZERO = Decimal("0")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --------------------------------------------------------------------------- #
# Авлага (гэрээ)
# --------------------------------------------------------------------------- #
class ArChargeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Нэмэх (+) эсвэл хасах (−) дүн — 0 биш.
    amount: Decimal
    charge_date: date | None = None
    #: opening — эхний үлдэгдэл/залруулга (3101); income — бусад орлого (4903).
    kind: str = Field(default="opening", pattern="^(opening|income)$")
    note: str | None = Field(default=None, max_length=255)
    #: Эхний үлдэгдлийн огноог ЭНЭ утгаар солино (буруу оруулсныг засахад);
    #: өгөхгүй бол charge_date-ээс эрт л бол шинэчилнэ.
    opening_date: date | None = None


@router.post("/contracts/{contract_id}/charges", response_model=ContractOut, status_code=201)
async def create_ar_charge(
    contract_id: uuid.UUID,
    payload: ArChargeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("contracts.manage")),
) -> ContractOut:
    contract = await db.scalar(select(Contract).where(Contract.id == contract_id).with_for_update())
    if contract is None:
        raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
    return await _apply_charge(db, user, request, contract, payload)


@router.post("/customers/{customer_id}/charges", response_model=ContractOut, status_code=201)
async def create_customer_charge(
    customer_id: uuid.UUID,
    payload: ArChargeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("contracts.manage")),
) -> ContractOut:
    """Гэрээгүй харилцагчид авлага үүсгэх — идэвхтэй гэрээг олох эсвэл автоматаар нээнэ."""
    from app.services.attendant_service import _contract_for_customer

    contract = await _contract_for_customer(db, user, customer_id)
    contract = await db.scalar(select(Contract).where(Contract.id == contract.id).with_for_update())
    return await _apply_charge(db, user, request, contract, payload)


async def _apply_charge(
    db: AsyncSession, user: User, request: Request, contract: Contract, payload: ArChargeIn
) -> ContractOut:
    amount = q2(payload.amount)
    if amount == ZERO:
        raise HTTPException(status_code=422, detail="Дүн 0 байж болохгүй")
    customer = await db.scalar(select(Customer).where(Customer.id == contract.customer_id))
    balance_after = q2(Decimal(contract.balance or ZERO) + amount)
    if balance_after < ZERO:
        raise HTTPException(status_code=422, detail=f"Авлага сөрөг болж байна (одоо {q2(contract.balance)})")

    as_of = payload.charge_date or datetime.now(UTC).date()
    before = {"balance": str(q2(contract.balance)), "opening_balance": str(q2(contract.opening_balance or ZERO))}

    # Тооцооны хуулга борлуулалт/төлбөрөөс тоологддог тул гар авлага эхний
    # үлдэгдлээр л илэрхийлэгдэнэ (харилцагчийн эцсийн үлдэгдэлтэй таарна).
    contract.opening_balance = q2(Decimal(contract.opening_balance or ZERO) + amount)
    if payload.opening_date is not None:
        contract.opening_date = payload.opening_date
    elif contract.opening_date is None or as_of < contract.opening_date:
        contract.opening_date = as_of
    contract.balance = balance_after
    if q2(Decimal(contract.credit_limit or ZERO)) < balance_after:
        contract.credit_limit = balance_after
        if customer is not None and q2(Decimal(customer.credit_limit or ZERO)) < balance_after:
            customer.credit_limit = balance_after

    counter = ACC.OWNER_CAPITAL if payload.kind == "opening" else ACC.OTHER_INCOME
    event = EventType.OPENING_BALANCE_POSTED if payload.kind == "opening" else EventType.MANUAL_ENTRY
    source = SourceType.OPENING_BALANCE if payload.kind == "opening" else SourceType.MANUAL
    label = "Гараар үүсгэсэн авлага" if amount > ZERO else "Авлагын залруулга (хасалт)"
    memo = f"{label} — {customer.name if customer else ''} ({contract.contract_no})"
    if payload.note:
        memo = f"{memo} · {payload.note.strip()}"
    memo = memo[:255]
    value = abs(amount)
    dims = Dims(customer_id=contract.customer_id)
    lines = (
        [
            LineSpec(account_code=ACC.AR_CONTRACT, debit=value, memo=memo, dims=dims),
            LineSpec(account_code=counter, credit=value, memo=memo),
        ]
        if amount > ZERO
        else [
            LineSpec(account_code=counter, debit=value, memo=memo),
            LineSpec(account_code=ACC.AR_CONTRACT, credit=value, memo=memo, dims=dims),
        ]
    )
    await posting.post(
        db,
        event_type=str(event),
        source_type=str(source),
        source_id=uuid.uuid4(),
        entry_date=as_of,
        description=memo,
        lines=lines,
        posted_by=user.id,
    )
    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="contract.charge",
        entity_type="contract",
        entity_id=contract.id,
        before=before,
        after={"amount": str(amount), "kind": payload.kind, "date": as_of.isoformat(), "balance": str(contract.balance)},
        ip=_client_ip(request),
    )
    return ContractOut(**contract_service.contract_out(contract, customer_name=customer.name if customer else None))


# --------------------------------------------------------------------------- #
# Өглөг (нийлүүлэгч)
# --------------------------------------------------------------------------- #
class ApInvoiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    invoice_date: date | None = None
    due_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    #: opening — эхний үлдэгдэл (Дт 3101); expense — зардлын данс (Дт 5xxx).
    kind: str = Field(default="opening", pattern="^(opening|expense)$")
    expense_account_code: str | None = Field(default=None, max_length=16)
    note: str | None = Field(default=None, max_length=255)


async def _next_invoice_no(db: AsyncSession, prefix: str) -> str:
    count = await db.scalar(
        select(func.count()).select_from(ApInvoice).where(ApInvoice.invoice_no.like(f"{prefix}-%"))
    )
    seq = int(count or 0) + 1
    while True:
        candidate = f"{prefix}-{seq:03d}"
        clash = await db.scalar(select(func.count()).select_from(ApInvoice).where(ApInvoice.invoice_no == candidate))
        if not clash:
            return candidate
        seq += 1


@router.post("/ap-invoices", response_model=ApInvoiceOut, status_code=201)
async def create_ap_invoice(
    payload: ApInvoiceIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("purchases.manage", "expenses.manage")),
) -> ApInvoiceOut:
    supplier = await db.scalar(select(Supplier).where(Supplier.id == payload.supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")
    amount = q2(payload.amount)
    as_of = payload.invoice_date or datetime.now(UTC).date()

    if payload.kind == "expense":
        debit_account = (payload.expense_account_code or "").strip()
        if debit_account not in ACC.OPERATING_EXPENSES:
            raise HTTPException(status_code=422, detail="Зардлын данс сонгоно уу")
        event, source = EventType.MANUAL_ENTRY, SourceType.MANUAL
    else:
        debit_account = ACC.OWNER_CAPITAL
        event, source = EventType.OPENING_BALANCE_POSTED, SourceType.OPENING_BALANCE

    invoice_no = (payload.invoice_no or "").strip() or await _next_invoice_no(db, f"ГАР-{as_of:%Y%m%d}")
    clash = await db.scalar(select(func.count()).select_from(ApInvoice).where(ApInvoice.invoice_no == invoice_no))
    if clash:
        raise HTTPException(status_code=422, detail="Ийм дугаартай нэхэмжлэх бүртгэгдсэн байна")

    source_id = uuid.uuid4()
    invoice = ApInvoice(
        supplier_id=supplier.id,
        invoice_no=invoice_no,
        invoice_date=as_of,
        due_date=payload.due_date,
        source_type=str(source),
        source_id=source_id,
        amount_gross=amount,
        amount_paid=ZERO,
        status=str(InvoiceStatus.OPEN),
    )
    db.add(invoice)
    await db.flush()

    label = "Гараар үүсгэсэн өглөг" if payload.kind == "opening" else "Зардлын өглөг (гараар)"
    memo = f"{label} — {supplier.name} · {invoice_no}"
    if payload.note:
        memo = f"{memo} · {payload.note.strip()}"
    memo = memo[:255]
    await posting.post(
        db,
        event_type=str(event),
        source_type=str(source),
        source_id=source_id,
        entry_date=as_of,
        description=memo,
        lines=[
            LineSpec(account_code=debit_account, debit=amount, memo=memo, dims=Dims(supplier_id=supplier.id)),
            LineSpec(account_code=ACC.AP_SUPPLIER, credit=amount, memo=memo, dims=Dims(supplier_id=supplier.id)),
        ],
        posted_by=user.id,
    )
    await audit(
        db,
        user_id=user.id,
        action="ap_invoice.manual",
        entity_type="ap_invoice",
        entity_id=invoice.id,
        after={"supplier_id": str(supplier.id), "amount": str(amount), "kind": payload.kind, "invoice_no": invoice_no},
        ip=_client_ip(request),
    )
    return ApInvoiceOut(
        id=invoice.id,
        supplier_id=invoice.supplier_id,
        supplier_name=supplier.name,
        invoice_no=invoice.invoice_no,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        source_type=invoice.source_type,
        source_id=invoice.source_id,
        amount_gross=q2(invoice.amount_gross),
        amount_paid=ZERO,
        amount_due=q2(invoice.amount_gross),
        status=invoice.status,
    )
