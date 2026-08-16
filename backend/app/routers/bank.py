"""Харилцах данс ба банкны хуулга (эзэн, менежер).

Хуулгын гүйлгээ манай бүртгэлд шууд буудаг тул ``bank.manage`` эрх шаардана —
төлбөр, зардал үүсгэх нь мөнгөн дүнтэй шууд холбоотой.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.accounting import JournalLine
from app.models.bank import BankAccount
from app.models.partner import Contract, Customer
from app.models.user import User
from app.money import q2
from app.schemas.bank import (
    BankAccountCreate,
    BankAccountListOut,
    BankAccountOut,
    BankAccountUpdate,
    BankStatementDetailOut,
    BankStatementListOut,
    PostAllOut,
    PostFeesIn,
    SetBankAccountIn,
    StatementCalendarOut,
    StatementConfigIn,
    StatementConfigOut,
    TransactionUpdateIn,
)
from app.services import bank_service, bank_statement_service, expense_service
from app.services.audit_service import audit
from app.services.coa import ACC

router = APIRouter(prefix="/api", tags=["bank"])

ZERO = Decimal("0.00")

#: Хуулгын Excel файлын дээд хэмжээ — 10 МБ (сарын хуулга ~200 КБ).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# --------------------------------------------------------------------------- #
# Харилцах данс
# --------------------------------------------------------------------------- #
@router.get("/bank-accounts", response_model=BankAccountListOut)
async def list_bank_accounts(
    active_only: bool = Query(default=False),
    branch_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage", "accounting.view")),
) -> BankAccountListOut:
    items = await bank_service.list_accounts(db, active_only=active_only, branch_id=branch_id)
    unassigned = await bank_service.unassigned_movement(db)
    ledger = await db.scalar(
        select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).where(
            JournalLine.account_code == ACC.BANK
        )
    )
    return BankAccountListOut(
        items=[BankAccountOut(**row) for row in items],
        total=len(items),
        unassigned=unassigned,
        ledger_balance=q2(Decimal(str(ledger or 0))),
    )


async def _check_number(
    db: AsyncSession, account_number: str, *, exclude: uuid.UUID | None = None
) -> None:
    existing = await bank_service.find_by_number(db, account_number)
    if existing is not None and existing.id != exclude:
        raise HTTPException(status_code=422, detail="Ийм дугаартай данс бүртгэгдсэн байна")


@router.post("/bank-accounts", response_model=BankAccountOut, status_code=201)
async def create_bank_account(
    payload: BankAccountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankAccountOut:
    number = payload.account_number.strip()
    await _check_number(db, number)

    account = BankAccount(
        branch_id=payload.branch_id,
        bank_name=payload.bank_name.strip(),
        account_number=number,
        holder_name=payload.holder_name.strip(),
        currency=payload.currency.strip().upper(),
        opening_balance=q2(payload.opening_balance),
        is_fee_default=payload.is_fee_default,
        is_active=payload.is_active,
        note=(payload.note or "").strip() or None,
        sort_order=payload.sort_order,
    )
    db.add(account)
    await db.flush()
    if account.is_fee_default:
        await bank_service.clear_fee_default(db, keep_id=account.id)

    await audit(
        db,
        user_id=user.id,
        action="bank_account.create",
        entity_type="bank_account",
        entity_id=account.id,
        after={"bank_name": account.bank_name, "account_number": account.account_number},
        ip=_client_ip(request),
    )
    return BankAccountOut(**await bank_service.account_out(db, account))


@router.patch("/bank-accounts/{account_id}", response_model=BankAccountOut)
async def update_bank_account(
    account_id: uuid.UUID,
    payload: BankAccountUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankAccountOut:
    account = await bank_service.get_account(db, account_id)
    changes = payload.model_dump(exclude_unset=True)
    before = {"bank_name": account.bank_name, "account_number": account.account_number}

    if "account_number" in changes and changes["account_number"]:
        number = str(changes["account_number"]).strip()
        await _check_number(db, number, exclude=account.id)
        account.account_number = number
    if changes.get("bank_name"):
        account.bank_name = str(changes["bank_name"]).strip()
    if "holder_name" in changes:
        account.holder_name = str(changes["holder_name"] or "").strip()
    if changes.get("currency"):
        account.currency = str(changes["currency"]).strip().upper()
    if changes.get("opening_balance") is not None:
        account.opening_balance = q2(changes["opening_balance"])
    if "branch_id" in changes:
        account.branch_id = changes["branch_id"]
    if "note" in changes:
        account.note = (changes["note"] or "").strip() or None
    if changes.get("sort_order") is not None:
        account.sort_order = int(changes["sort_order"])
    if changes.get("is_active") is not None:
        account.is_active = bool(changes["is_active"])
    if changes.get("is_fee_default") is not None:
        account.is_fee_default = bool(changes["is_fee_default"])
        if account.is_fee_default:
            await bank_service.clear_fee_default(db, keep_id=account.id)

    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="bank_account.update",
        entity_type="bank_account",
        entity_id=account.id,
        before=before,
        after={"bank_name": account.bank_name, "account_number": account.account_number},
        ip=_client_ip(request),
    )
    return BankAccountOut(**await bank_service.account_out(db, account))


@router.delete("/bank-accounts/{account_id}", status_code=204, response_class=Response)
async def deactivate_bank_account(
    account_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> Response:
    """Данс хэзээ ч бодитоор устгагдахгүй — гүйлгээний түүх бүрэн үлдэнэ."""
    account = await bank_service.get_account(db, account_id)
    account.is_active = False
    account.is_fee_default = False
    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="bank_account.deactivate",
        entity_type="bank_account",
        entity_id=account.id,
        ip=_client_ip(request),
    )
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Тохиргоо
# --------------------------------------------------------------------------- #
async def _config_out(db: AsyncSession) -> StatementConfigOut:
    config = await bank_statement_service.get_config(db)
    customer_name = None
    contract_no = None
    if config.settlement_customer_id:
        customer = await db.get(Customer, config.settlement_customer_id)
        customer_name = customer.name if customer else None
    if config.settlement_contract_id:
        contract = await db.get(Contract, config.settlement_contract_id)
        contract_no = contract.contract_no if contract else None
    names = {a["code"]: a["name_mn"] for a in await expense_service.list_categories(db)}
    return StatementConfigOut(
        settlement_customer_id=config.settlement_customer_id,
        settlement_customer_name=customer_name,
        settlement_contract_id=config.settlement_contract_id,
        settlement_contract_no=contract_no,
        settlement_description=config.settlement_description,
        fee_account_code=config.fee_account_code,
        fee_account_name=(
            names.get(config.fee_account_code) if config.fee_account_code else None
        ),
        fee_description=config.fee_description,
    )


# «config» гэдгийг ID гэж үзэхээс сэргийлж тодорхой замуудыг эхэнд бүртгэнэ.
@router.get("/bank-statements/config", response_model=StatementConfigOut)
async def get_statement_config(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> StatementConfigOut:
    return await _config_out(db)


@router.put("/bank-statements/config", response_model=StatementConfigOut)
async def update_statement_config(
    payload: StatementConfigIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> StatementConfigOut:
    touched = frozenset(payload.model_dump(exclude_unset=True).keys())
    await bank_statement_service.update_config(
        db,
        settlement_contract_id=payload.settlement_contract_id,
        settlement_description_text=payload.settlement_description,
        fee_account_code=payload.fee_account_code,
        fee_description=payload.fee_description,
        touched=touched,
    )
    await audit(
        db,
        user_id=user.id,
        action="bank_statement.config",
        entity_type="bank_statement_config",
        entity_id=user.id,
        after=payload.model_dump(mode="json", exclude_unset=True),
        ip=_client_ip(request),
    )
    return await _config_out(db)


@router.get("/bank-statements/calendar", response_model=StatementCalendarOut)
async def statement_calendar(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> StatementCalendarOut:
    return StatementCalendarOut(**await bank_statement_service.calendar(db, year, month))


# --------------------------------------------------------------------------- #
# Хуулга
# --------------------------------------------------------------------------- #
@router.post("/bank-statements/upload", response_model=BankStatementDetailOut, status_code=201)
async def upload_statement(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Файл хоосон байна")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=422, detail="Файл хэт том байна (10 МБ хүртэл)")

    try:
        statement = await bank_statement_service.upload(
            db, user, content=content, filename=file.filename or "statement.xlsx"
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await audit(
        db,
        user_id=user.id,
        action="bank_statement.upload",
        entity_type="bank_statement",
        entity_id=statement.id,
        after={"filename": statement.filename, "account_number": statement.account_number},
        ip=_client_ip(request),
    )
    return BankStatementDetailOut(
        **await bank_statement_service.get_statement(db, statement.id)
    )


@router.get("/bank-statements", response_model=BankStatementListOut)
async def list_statements(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> BankStatementListOut:
    items = await bank_statement_service.list_statements(db, date_from=date_from, date_to=date_to)
    return BankStatementListOut(items=items, total=len(items))


@router.get("/bank-statements/{statement_id}", response_model=BankStatementDetailOut)
async def get_statement(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.delete("/bank-statements/{statement_id}", status_code=204, response_class=Response)
async def delete_statement(
    statement_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> Response:
    await bank_statement_service.remove(db, statement_id)
    await audit(
        db,
        user_id=user.id,
        action="bank_statement.delete",
        entity_type="bank_statement",
        entity_id=statement_id,
        ip=_client_ip(request),
    )
    return Response(status_code=204)


@router.put("/bank-statements/{statement_id}/bank-account", response_model=BankStatementDetailOut)
async def set_statement_account(
    statement_id: uuid.UUID,
    payload: SetBankAccountIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.set_bank_account(db, statement_id, payload.bank_account_id)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.post(
    "/bank-statements/{statement_id}/fill-descriptions", response_model=BankStatementDetailOut
)
async def fill_descriptions(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.fill_descriptions(db, statement_id)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.post(
    "/bank-statements/{statement_id}/swap-debit-credit", response_model=BankStatementDetailOut
)
async def swap_debit_credit(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.swap_debit_credit(db, statement_id)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.patch(
    "/bank-statements/{statement_id}/transactions/{txn_id}",
    response_model=BankStatementDetailOut,
)
async def update_transaction(
    statement_id: uuid.UUID,
    txn_id: uuid.UUID,
    payload: TransactionUpdateIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    touched = frozenset(payload.model_dump(exclude_unset=True).keys())
    await bank_statement_service.update_transaction(
        db,
        statement_id,
        txn_id,
        description=payload.description,
        contract_id=payload.contract_id,
        expense_account_code=payload.expense_account_code,
        touched=touched,
    )
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.post(
    "/bank-statements/{statement_id}/transactions/{txn_id}/post",
    response_model=BankStatementDetailOut,
)
async def post_transaction(
    statement_id: uuid.UUID,
    txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.post_transaction(db, user, statement_id, txn_id)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.post(
    "/bank-statements/{statement_id}/transactions/{txn_id}/unpost",
    response_model=BankStatementDetailOut,
)
async def unpost_transaction(
    statement_id: uuid.UUID,
    txn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.unpost_transaction(db, user, statement_id, txn_id)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.post("/bank-statements/{statement_id}/post-all", response_model=PostAllOut)
async def post_all(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> PostAllOut:
    result = await bank_statement_service.post_all(db, user, statement_id)
    statement = await bank_statement_service.get_statement(db, statement_id)
    return PostAllOut(
        posted=result["posted"],
        skipped=result["skipped"],
        statement=BankStatementDetailOut(**statement),
    )


@router.post("/bank-statements/{statement_id}/post-fees", response_model=BankStatementDetailOut)
async def post_fees(
    statement_id: uuid.UUID,
    payload: PostFeesIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.post_fees(db, user, statement_id, payload.expense_account_code)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))


@router.post("/bank-statements/{statement_id}/unpost-fees", response_model=BankStatementDetailOut)
async def unpost_fees(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("bank.manage")),
) -> BankStatementDetailOut:
    await bank_statement_service.unpost_fees(db, user, statement_id)
    return BankStatementDetailOut(**await bank_statement_service.get_statement(db, statement_id))
