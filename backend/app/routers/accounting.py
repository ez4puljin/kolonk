"""НББ-ийн API — данс, журнал, гар бичилт, санхүүгийн тайлан, өглөгийн тооцоо."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import CashAccount, EventType, InvoiceStatus, SourceType
from app.models.accounting import Account, ApInvoice, ApPayment, JournalEntry
from app.models.user import User
from app.money import q2
from app.schemas.accounting import (
    AccountOut,
    ApInvoiceList,
    ApInvoiceOut,
    ApPaymentIn,
    ApPaymentOut,
    ApPaymentResultOut,
    BalanceSheetOut,
    CashFlowOut,
    IncomeStatementOut,
    IntegrityCheckOut,
    InventoryValuationOut,
    JournalEntryList,
    JournalEntryOut,
    ManualEntryIn,
    SettlementIn,
    SettlementOut,
    TrialBalanceOut,
)
from app.services import statement_service
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import Dims, LineSpec, UnbalancedEntryError, posting
from app.services.posting_rules import (
    build_ap_payment_lines,
    build_settlement_lines,
    settlement_event,
)

router = APIRouter(prefix="/api", tags=["accounting"])

ZERO = Decimal("0")

CanView = Depends(require_permission("accounting.view"))
CanManage = Depends(require_permission("accounting.manage"))
# Нийлүүлэгчийн төлбөр нь худалдан авалтын үйл ажиллагааны хэсэг тул
# менежер ч хийж чадна (журналын гар бичилт нь эзний эрх хэвээр).
CanPaySupplier = Depends(require_permission("accounting.manage", "purchases.manage"))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ap_invoice_out(invoice: ApInvoice) -> ApInvoiceOut:
    return ApInvoiceOut(
        id=invoice.id,
        supplier_id=invoice.supplier_id,
        supplier_name=invoice.supplier.name if invoice.supplier is not None else None,
        invoice_no=invoice.invoice_no,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        source_type=invoice.source_type,
        source_id=invoice.source_id,
        amount_gross=q2(invoice.amount_gross),
        amount_paid=q2(invoice.amount_paid),
        amount_due=q2(Decimal(invoice.amount_gross) - Decimal(invoice.amount_paid)),
        status=invoice.status,
    )


# --------------------------------------------------------------------------- #
# Данс
# --------------------------------------------------------------------------- #
@router.get("/accounting/accounts", response_model=list[AccountOut])
async def list_accounts(
    postable_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> list[Account]:
    stmt = select(Account).order_by(Account.sort_order, Account.code)
    if postable_only:
        stmt = stmt.where(Account.is_postable.is_(True))
    return list((await db.scalars(stmt)).all())


# --------------------------------------------------------------------------- #
# Журнал
# --------------------------------------------------------------------------- #
@router.get("/accounting/journal", response_model=JournalEntryList)
async def list_journal(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    source_type: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> JournalEntryList:
    conditions = []
    if date_from is not None:
        conditions.append(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        conditions.append(JournalEntry.entry_date <= date_to)
    if source_type:
        conditions.append(JournalEntry.source_type == source_type)
    if event_type:
        conditions.append(JournalEntry.event_type == event_type)

    total = await db.scalar(select(func.count()).select_from(JournalEntry).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(JournalEntry)
            .where(*conditions)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.entry_no.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return JournalEntryList(
        items=[JournalEntryOut.model_validate(row) for row in rows],
        total=int(total),
    )


@router.get("/accounting/journal/{entry_id}", response_model=JournalEntryOut)
async def get_journal_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> JournalEntry:
    entry = await db.scalar(select(JournalEntry).where(JournalEntry.id == entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="Журналын бичилт олдсонгүй")
    return entry


# --------------------------------------------------------------------------- #
# Гар бичилт
# --------------------------------------------------------------------------- #
@router.post("/accounting/manual-entries", response_model=JournalEntryOut, status_code=201)
async def create_manual_entry(
    payload: ManualEntryIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> JournalEntry:
    codes = {line.account_code for line in payload.lines}
    accounts = {
        acc.code: acc for acc in (await db.scalars(select(Account).where(Account.code.in_(codes)))).all()
    }
    for code in sorted(codes):
        account = accounts.get(code)
        if account is None:
            raise HTTPException(status_code=422, detail=f"'{code}' дансны код олдсонгүй")
        if not account.is_postable:
            raise HTTPException(status_code=422, detail=f"'{code}' данс руу шууд бичилт хийх боломжгүй")

    specs: list[LineSpec] = []
    for line in payload.lines:
        debit = q2(line.debit or ZERO)
        credit = q2(line.credit or ZERO)
        if debit > 0 and credit > 0:
            raise HTTPException(
                status_code=422, detail="Нэг мөрөнд дебит ба кредит зэрэг дүнтэй байж болохгүй"
            )
        specs.append(
            LineSpec(account_code=line.account_code, debit=debit, credit=credit, memo=line.memo, dims=Dims())
        )

    source_id = uuid.uuid4()
    try:
        entry = await posting.post(
            db,
            event_type=EventType.MANUAL_ENTRY,
            source_type=SourceType.MANUAL,
            source_id=source_id,
            entry_date=payload.entry_date,
            description=payload.description,
            lines=specs,
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if entry is None:
        raise HTTPException(status_code=422, detail="Бичих дүнтэй мөр алга байна")

    await emit(
        db,
        aggregate_type="journal_entry",
        aggregate_id=entry.id,
        event_type=str(EventType.MANUAL_ENTRY),
        payload={"source_id": str(source_id), "description": payload.description},
    )
    await audit(
        db,
        user_id=user.id,
        action="accounting.manual_entry",
        entity_type="journal_entry",
        entity_id=entry.id,
        after={"description": payload.description, "lines": len(specs)},
        ip=_client_ip(request),
    )
    return entry


# --------------------------------------------------------------------------- #
# Тайлангууд
# --------------------------------------------------------------------------- #
@router.get("/accounting/trial-balance", response_model=TrialBalanceOut)
async def get_trial_balance(
    as_of: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    return await statement_service.trial_balance(db, as_of)


@router.get("/accounting/integrity", response_model=list[IntegrityCheckOut])
async def get_integrity(
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> list[dict]:
    return await statement_service.integrity_check(db)


@router.get("/accounting/statements/pnl", response_model=IncomeStatementOut)
async def get_pnl(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Дуусах огноо эхлэх огнооноос өмнө байж болохгүй")
    return await statement_service.income_statement(db, date_from, date_to)


@router.get("/accounting/statements/balance-sheet", response_model=BalanceSheetOut)
async def get_balance_sheet(
    as_of: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    return await statement_service.balance_sheet(db, as_of)


@router.get("/accounting/statements/cash-flow", response_model=CashFlowOut)
async def get_cash_flow(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Дуусах огноо эхлэх огнооноос өмнө байж болохгүй")
    return await statement_service.cash_flow(db, date_from, date_to)


@router.get("/accounting/statements/inventory-valuation", response_model=InventoryValuationOut)
async def get_inventory_valuation(
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    return await statement_service.inventory_valuation(db)


# --------------------------------------------------------------------------- #
# Эквайрингийн тооцоо
# --------------------------------------------------------------------------- #
@router.post("/accounting/settlements", response_model=SettlementOut, status_code=201)
async def create_settlement(
    payload: SettlementIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> SettlementOut:
    method = payload.method.lower().strip()
    if method not in ("card", "qr"):
        raise HTTPException(status_code=422, detail="Тооцооны төрөл зөвхөн 'card' эсвэл 'qr' байна")

    amount = q2(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Тооцооны дүн 0-ээс их байх ёстой")

    source_id = uuid.uuid4()
    event_type = settlement_event(method)
    label = "Картын" if method == "card" else "QR"
    try:
        entry = await posting.post(
            db,
            event_type=event_type,
            source_type=SourceType.SETTLEMENT,
            source_id=source_id,
            entry_date=payload.settlement_date,
            description=f"{label} эквайрингийн тооцоо",
            lines=build_settlement_lines(method, amount),
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if entry is None:
        raise HTTPException(status_code=422, detail="Тооцооны дүн 0-ээс их байх ёстой")

    await emit(
        db,
        aggregate_type="settlement",
        aggregate_id=source_id,
        event_type=event_type,
        payload={"method": method, "amount": str(amount), "date": payload.settlement_date.isoformat()},
    )
    await audit(
        db,
        user_id=user.id,
        action="accounting.settlement",
        entity_type="journal_entry",
        entity_id=entry.id,
        after={"method": method, "amount": str(amount)},
        ip=_client_ip(request),
    )
    return SettlementOut(
        journal_entry_id=entry.id,
        entry_no=entry.entry_no,
        method=method,
        amount=amount,
        settlement_date=payload.settlement_date,
    )


# --------------------------------------------------------------------------- #
# Нийлүүлэгчийн өглөг
# --------------------------------------------------------------------------- #
@router.get("/ap-invoices", response_model=ApInvoiceList)
async def list_ap_invoices(
    status: str | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> ApInvoiceList:
    conditions = []
    if status:
        conditions.append(ApInvoice.status == status)
    if supplier_id is not None:
        conditions.append(ApInvoice.supplier_id == supplier_id)

    total = await db.scalar(select(func.count()).select_from(ApInvoice).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(ApInvoice)
            .where(*conditions)
            .order_by(ApInvoice.invoice_date.desc(), ApInvoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return ApInvoiceList(items=[_ap_invoice_out(row) for row in rows], total=int(total))


@router.post("/ap-payments", response_model=ApPaymentResultOut, status_code=201)
async def create_ap_payment(
    payload: ApPaymentIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanPaySupplier,
) -> ApPaymentResultOut:
    invoice = await db.scalar(select(ApInvoice).where(ApInvoice.id == payload.ap_invoice_id))
    if invoice is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгчийн нэхэмжлэх олдсонгүй")

    paid_from = payload.paid_from.lower().strip()
    if paid_from not in (str(CashAccount.BANK), str(CashAccount.CASH)):
        raise HTTPException(status_code=422, detail="Төлбөрийн эх үүсвэр зөвхөн 'bank' эсвэл 'cash' байна")

    amount = q2(payload.amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Төлбөрийн дүн 0-ээс их байх ёстой")

    due = q2(Decimal(invoice.amount_gross) - Decimal(invoice.amount_paid))
    if due <= 0:
        raise HTTPException(status_code=422, detail="Энэ нэхэмжлэх бүрэн төлөгдсөн байна")
    if amount > due:
        raise HTTPException(status_code=422, detail=f"Төлбөрийн дүн үлдэгдлээс ({due}) их байна")

    before = {"amount_paid": str(q2(invoice.amount_paid)), "status": invoice.status}

    payment = ApPayment(
        ap_invoice_id=invoice.id,
        supplier_id=invoice.supplier_id,
        amount=amount,
        paid_from=paid_from,
        payment_date=payload.payment_date,
        note=payload.note,
        created_by=user.id,
    )
    db.add(payment)
    await db.flush()

    invoice.amount_paid = q2(Decimal(invoice.amount_paid) + amount)
    invoice.status = (
        str(InvoiceStatus.PAID)
        if invoice.amount_paid >= q2(invoice.amount_gross)
        else str(InvoiceStatus.PARTIAL)
    )

    try:
        entry = await posting.post(
            db,
            event_type=EventType.AP_PAYMENT,
            source_type=SourceType.AP_PAYMENT,
            source_id=payment.id,
            entry_date=payload.payment_date,
            description=f"Нийлүүлэгчид төлсөн — нэхэмжлэх {invoice.invoice_no}",
            lines=build_ap_payment_lines(payment),
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await emit(
        db,
        aggregate_type="ap_payment",
        aggregate_id=payment.id,
        event_type=str(EventType.AP_PAYMENT),
        payload={
            "ap_invoice_id": str(invoice.id),
            "supplier_id": str(invoice.supplier_id),
            "amount": str(amount),
            "paid_from": paid_from,
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="accounting.ap_payment",
        entity_type="ap_invoice",
        entity_id=invoice.id,
        before=before,
        after={"amount_paid": str(invoice.amount_paid), "status": invoice.status, "paid": str(amount)},
        ip=_client_ip(request),
    )

    return ApPaymentResultOut(
        payment=ApPaymentOut.model_validate(payment),
        invoice=_ap_invoice_out(invoice),
        journal_entry_id=entry.id if entry is not None else None,
    )
