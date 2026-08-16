"""Банкны хуулгын гүйлгээг манай бүртгэлд буулгах.

    Орлого (кредит) → гэрээт харилцагчийн авлагын төлбөр (``AR_RECEIPT``)
    Зарлага (дебит) → үйл ажиллагааны зардал (``EXPENSE_POSTED``)

Төлбөр/зардлыг өөрсдийнх нь үйлчилгээгээр үүсгэдэг — ингэснээр дансны
үлдэгдэл, харилцагчийн өр, авлагын дэвтэр бүгд зөв хөдөлнө.  Энэ модуль
зөвхөн хуулгын мөрийг үүссэн баримттай холбоно.

Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй — ``get_db`` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import EventType, InvoiceStatus, SourceType
from app.models.accounting import Account, ArInvoice, ArPayment
from app.models.bank import BankAccount, BankStatement, BankStatementConfig, BankTransaction
from app.models.expense import Expense
from app.models.partner import Contract, Customer
from app.models.user import User
from app.money import q2
from app.services import bank_service, contract_service, expense_service
from app.services.audit_service import audit
from app.services.posting import posting
from app.services.bank_statement_parser import (
    is_pos_income,
    parse_statement,
    settlement_description,
)
from app.services.coa import ACC

ZERO = Decimal("0.00")


def _d(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _amount_of(txn: BankTransaction) -> tuple[Decimal, bool]:
    """Мөрийн дүн ба чиглэл.  Хоёул утгатай бол илүү нь голлоно."""
    credit = q2(_d(txn.credit))
    debit = q2(_d(txn.debit))
    if credit > ZERO:
        return credit, True
    return debit, False


def _missing_fields(txn: BankTransaction) -> list[str]:
    """Мөр бүртгэхэд бэлэн эсэх — дутуу талбаруудыг нэрлэнэ."""
    missing: list[str] = []
    _, income = _amount_of(txn)
    if income:
        if txn.contract_id is None:
            missing.append("target")
    elif not txn.expense_account_code:
        missing.append("target")
    if not (txn.description or "").strip():
        missing.append("desc")
    return missing


# --------------------------------------------------------------------------- #
# Тохиргоо (нэг мөр)
# --------------------------------------------------------------------------- #
async def get_config(db: AsyncSession) -> BankStatementConfig:
    config = await db.scalar(select(BankStatementConfig).limit(1))
    if config is None:
        config = BankStatementConfig()
        db.add(config)
        await db.flush()
    return config


async def update_config(
    db: AsyncSession,
    *,
    settlement_customer_id: uuid.UUID | None = None,
    settlement_contract_id: uuid.UUID | None = None,
    settlement_description_text: str | None = None,
    fee_account_code: str | None = None,
    fee_description: str | None = None,
    touched: frozenset[str] = frozenset(),
) -> BankStatementConfig:
    config = await get_config(db)

    if "settlement_contract_id" in touched:
        if settlement_contract_id is not None:
            contract = await db.get(Contract, settlement_contract_id)
            if contract is None:
                raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
            config.settlement_contract_id = contract.id
            config.settlement_customer_id = contract.customer_id
        else:
            config.settlement_contract_id = None
            config.settlement_customer_id = None
    elif "settlement_customer_id" in touched:
        config.settlement_customer_id = settlement_customer_id

    if "fee_account_code" in touched:
        if fee_account_code and fee_account_code not in ACC.OPERATING_EXPENSES:
            raise HTTPException(status_code=422, detail="Зардлын данс биш байна")
        config.fee_account_code = fee_account_code or None

    if settlement_description_text is not None:
        config.settlement_description = settlement_description_text.strip()
    if fee_description is not None:
        config.fee_description = fee_description.strip()

    await db.flush()
    return config


# --------------------------------------------------------------------------- #
# Хуулга оруулах
# --------------------------------------------------------------------------- #
async def upload(
    db: AsyncSession, user: User | None, *, content: bytes, filename: str
) -> BankStatement:
    """Excel хуулгыг задалж, мөрүүдийг тохиргооны дагуу урьдчилж бөглөнө."""
    parsed = parse_statement(content, filename)
    if not parsed.transactions:
        raise HTTPException(
            status_code=422,
            detail="Хуулгаас гүйлгээ олдсонгүй. Банкны Excel хуулга мөн эсэхийг шалгана уу.",
        )

    config = await get_config(db)
    # Дансны дугаараар манай данстай холбоно — бүртгэхэд аль данснаас мөнгө
    # хөдөлснийг мэдэх шаардлагатай.
    account = await bank_service.find_by_number(db, parsed.account_number)

    statement = BankStatement(
        account_number=parsed.account_number,
        currency=parsed.currency,
        date_from=parsed.date_from,
        date_to=parsed.date_to,
        filename=parsed.filename,
        uploaded_by=getattr(user, "id", None),
        bank_account_id=account.id if account else None,
    )
    db.add(statement)
    await db.flush()

    for index, row in enumerate(parsed.transactions):
        txn = BankTransaction(
            statement_id=statement.id,
            txn_date=row.txn_date,
            debit=q2(row.debit),
            credit=q2(row.credit),
            bank_description=row.bank_description,
            bank_counterpart=row.bank_counterpart,
            is_fee=row.is_fee,
            sort_order=index,
        )
        # Шимтгэл болон ПОС мөрийг тохиргооны дагуу урьдчилж бөглөнө.
        if row.is_fee:
            txn.expense_account_code = config.fee_account_code
            txn.description = config.fee_description or ""
        elif row.credit > ZERO and is_pos_income(row.bank_description):
            txn.customer_id = config.settlement_customer_id
            txn.contract_id = config.settlement_contract_id
            txn.description = settlement_description(
                config.settlement_description, row.bank_description
            )
        db.add(txn)

    await db.flush()
    return statement


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
async def _load(db: AsyncSession, statement_id: uuid.UUID) -> BankStatement:
    """Хуулгыг мөрүүдтэй нь ачаална.

    ``db.get`` нь identity map-аас шууд буцаадаг тул саяхан үүсгэсэн объектын
    ``transactions`` цуглуулга ачаалагдаагүй үлдэж, async орчинд lazy load нь
    ``MissingGreenlet`` өгдөг.  Иймд үргэлж тодорхой асуулгаар шинэчилнэ.
    """
    statement = await db.scalar(
        select(BankStatement)
        .where(BankStatement.id == statement_id)
        .options(selectinload(BankStatement.transactions))
        .execution_options(populate_existing=True)
    )
    if statement is None:
        raise HTTPException(status_code=404, detail="Хуулга олдсонгүй")
    return statement


async def _names(db: AsyncSession, statements: list[BankStatement]) -> dict[str, Any]:
    """Дэлгэцэнд харуулах нэрсийг нэг дор ачаална."""
    bank_ids = {s.bank_account_id for s in statements if s.bank_account_id}
    fee_ids = {s.fee_expense_id for s in statements if s.fee_expense_id}
    banks: dict[uuid.UUID, BankAccount] = {}
    fees: dict[uuid.UUID, Expense] = {}
    if bank_ids:
        banks = {
            b.id: b
            for b in (
                await db.scalars(select(BankAccount).where(BankAccount.id.in_(bank_ids)))
            ).all()
        }
    if fee_ids:
        fees = {
            e.id: e
            for e in (await db.scalars(select(Expense).where(Expense.id.in_(fee_ids)))).all()
        }
    return {"banks": banks, "fees": fees}


def _statement_out(
    statement: BankStatement,
    transactions: list[BankTransaction],
    *,
    banks: dict[uuid.UUID, BankAccount],
    fees: dict[uuid.UUID, Expense],
) -> dict[str, Any]:
    # Шимтгэлийг нийлбэрээр нь тусад нь хаадаг тул үндсэн тооцоонд оруулахгүй.
    rows = [t for t in transactions if not t.is_fee]
    fee_rows = [t for t in transactions if t.is_fee]

    missing = {"target": 0, "desc": 0}
    ready = 0
    posted = 0
    for txn in rows:
        if txn.posted_at is not None:
            posted += 1
            continue
        gaps = _missing_fields(txn)
        if not gaps:
            ready += 1
        else:
            for key in gaps:
                missing[key] += 1

    bank = banks.get(statement.bank_account_id) if statement.bank_account_id else None
    fee_expense = fees.get(statement.fee_expense_id) if statement.fee_expense_id else None
    fee_total = q2(sum((_d(t.debit) - _d(t.credit) for t in fee_rows), ZERO))

    return {
        "id": statement.id,
        "account_number": statement.account_number,
        "currency": statement.currency,
        "date_from": statement.date_from,
        "date_to": statement.date_to,
        "filename": statement.filename,
        "uploaded_at": statement.created_at,
        "bank_account_id": statement.bank_account_id,
        "bank_name": (f"{bank.bank_name} · {bank.account_number}" if bank else None),
        "txn_count": len(rows),
        "total_credit": q2(sum((_d(t.credit) for t in rows), ZERO)),
        "total_debit": q2(sum((_d(t.debit) for t in rows), ZERO)),
        "posted_count": posted,
        "ready_count": ready,
        "missing": missing,
        "fee": {
            "count": len(fee_rows),
            "total": fee_total,
            "posted": statement.fee_expense_id is not None,
            "expense_number": fee_expense.number if fee_expense else None,
        },
    }


def _txn_out(
    txn: BankTransaction,
    *,
    customers: dict[uuid.UUID, str],
    contracts: dict[uuid.UUID, str],
    accounts: dict[str, str],
) -> dict[str, Any]:
    credit = q2(_d(txn.credit))
    return {
        "id": txn.id,
        "txn_date": txn.txn_date,
        "debit": q2(_d(txn.debit)),
        "credit": credit,
        "bank_description": txn.bank_description,
        "bank_counterpart": txn.bank_counterpart,
        "is_fee": txn.is_fee,
        "description": txn.description,
        "customer_id": txn.customer_id,
        "customer_name": customers.get(txn.customer_id) if txn.customer_id else None,
        "contract_id": txn.contract_id,
        "contract_no": contracts.get(txn.contract_id) if txn.contract_id else None,
        "expense_account_code": txn.expense_account_code,
        "expense_account_name": (
            accounts.get(txn.expense_account_code) if txn.expense_account_code else None
        ),
        "ar_payment_id": txn.ar_payment_id,
        "expense_id": txn.expense_id,
        "posted_at": txn.posted_at,
        "is_income": credit > ZERO,
        "is_settlement": credit > ZERO and is_pos_income(txn.bank_description),
        "missing": _missing_fields(txn),
    }


async def list_statements(
    db: AsyncSession, *, date_from: date | None = None, date_to: date | None = None
) -> list[dict[str, Any]]:
    conditions = []
    if date_from is not None:
        conditions.append(BankStatement.date_from >= date_from)
    if date_to is not None:
        conditions.append(BankStatement.date_from <= date_to)

    statements = (
        await db.scalars(
            select(BankStatement)
            .options(selectinload(BankStatement.transactions))
            .where(*conditions)
            .order_by(BankStatement.date_from.desc().nullslast(), BankStatement.created_at.desc())
        )
    ).all()
    names = await _names(db, list(statements))
    return [
        _statement_out(s, list(s.transactions), banks=names["banks"], fees=names["fees"])
        for s in statements
    ]


async def get_statement(db: AsyncSession, statement_id: uuid.UUID) -> dict[str, Any]:
    statement = await _load(db, statement_id)
    transactions = sorted(statement.transactions, key=lambda t: (t.sort_order, t.id.hex))
    names = await _names(db, [statement])

    customer_ids = {t.customer_id for t in transactions if t.customer_id}
    contract_ids = {t.contract_id for t in transactions if t.contract_id}
    customers: dict[uuid.UUID, str] = {}
    contracts: dict[uuid.UUID, str] = {}
    if customer_ids:
        customers = {
            c.id: c.name
            for c in (await db.scalars(select(Customer).where(Customer.id.in_(customer_ids)))).all()
        }
    if contract_ids:
        contracts = {
            c.id: c.contract_no
            for c in (await db.scalars(select(Contract).where(Contract.id.in_(contract_ids)))).all()
        }
    accounts = {a["code"]: a["name_mn"] for a in await expense_service.list_categories(db)}

    head = _statement_out(statement, transactions, banks=names["banks"], fees=names["fees"])
    head["transactions"] = [
        _txn_out(t, customers=customers, contracts=contracts, accounts=accounts)
        for t in transactions
    ]
    return head


async def calendar(db: AsyncSession, year: int, month: int) -> dict[str, Any]:
    """Сарын өдөр бүрд хэдэн хуулга, хэр бүртгэгдсэнийг тоолж хуанлид өгнө."""
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1)
    statements = (
        await db.scalars(
            select(BankStatement)
            .options(selectinload(BankStatement.transactions))
            .where(BankStatement.date_from >= start, BankStatement.date_from < end)
        )
    ).all()

    days: dict[str, dict[str, int]] = {}
    for statement in statements:
        if statement.date_from is None:
            continue
        key = statement.date_from.isoformat()
        rows = [t for t in statement.transactions if not t.is_fee]
        entry = days.setdefault(key, {"count": 0, "posted": 0, "total": 0})
        entry["count"] += 1
        entry["posted"] += sum(1 for t in rows if t.posted_at is not None)
        entry["total"] += len(rows)
    return {"year": year, "month": month, "days": days}


# --------------------------------------------------------------------------- #
# Засварлах
# --------------------------------------------------------------------------- #
async def _get_txn(
    db: AsyncSession, statement_id: uuid.UUID, txn_id: uuid.UUID
) -> BankTransaction:
    txn = await db.get(BankTransaction, txn_id)
    if txn is None or txn.statement_id != statement_id:
        raise HTTPException(status_code=404, detail="Гүйлгээ олдсонгүй")
    return txn


async def update_transaction(
    db: AsyncSession,
    statement_id: uuid.UUID,
    txn_id: uuid.UUID,
    *,
    description: str | None = None,
    contract_id: uuid.UUID | None = None,
    expense_account_code: str | None = None,
    touched: frozenset[str] = frozenset(),
) -> None:
    txn = await _get_txn(db, statement_id, txn_id)
    if txn.posted_at is not None:
        raise HTTPException(
            status_code=422, detail="Бүртгэсэн гүйлгээг засахын тулд эхлээд буцаана уу"
        )

    if description is not None:
        txn.description = description.strip()

    if "contract_id" in touched:
        if contract_id is not None:
            contract = await db.get(Contract, contract_id)
            if contract is None:
                raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
            txn.contract_id = contract.id
            txn.customer_id = contract.customer_id
        else:
            txn.contract_id = None
            txn.customer_id = None

    if "expense_account_code" in touched:
        if expense_account_code and expense_account_code not in ACC.OPERATING_EXPENSES:
            raise HTTPException(status_code=422, detail="Зардлын данс биш байна")
        txn.expense_account_code = expense_account_code or None

    await db.flush()


async def fill_descriptions(db: AsyncSession, statement_id: uuid.UUID) -> int:
    """Гүйлгээний утга хоосон мөрүүдийг банкны утгаар нөхнө."""
    statement = await _load(db, statement_id)
    filled = 0
    for txn in statement.transactions:
        if txn.posted_at is None and not (txn.description or "").strip():
            bank_text = (txn.bank_description or "").strip()
            if bank_text:
                txn.description = bank_text
                filled += 1
    await db.flush()
    return filled


async def swap_debit_credit(db: AsyncSession, statement_id: uuid.UUID) -> None:
    """Дебит/Кредит баганыг солино.

    Зарим хуулгад багана солигдож ирдэг ба оруулсны дараа л мэдэгддэг.
    """
    statement = await _load(db, statement_id)
    if statement.fee_expense_id is not None or any(
        t.posted_at is not None for t in statement.transactions
    ):
        raise HTTPException(
            status_code=422, detail="Бүртгэсэн мөртэй үед багана солих боломжгүй"
        )
    for txn in statement.transactions:
        txn.debit, txn.credit = txn.credit, txn.debit
    await db.flush()


async def set_bank_account(
    db: AsyncSession, statement_id: uuid.UUID, bank_account_id: uuid.UUID | None
) -> None:
    """Хуулгыг манай аль данстай холбохыг гараар зааж өгнө."""
    statement = await _load(db, statement_id)
    if statement.fee_expense_id is not None or any(
        t.posted_at is not None for t in statement.transactions
    ):
        raise HTTPException(
            status_code=422, detail="Бүртгэсэн мөртэй хуулгын дансыг солих боломжгүй"
        )
    if bank_account_id is not None:
        await bank_service.get_account(db, bank_account_id)
    statement.bank_account_id = bank_account_id
    await db.flush()


async def remove(db: AsyncSession, statement_id: uuid.UUID) -> None:
    statement = await _load(db, statement_id)
    posted = sum(1 for t in statement.transactions if t.posted_at is not None)
    if posted:
        # Бүртгэсэн мөр байвал устгахаас өмнө буцаах ёстой — эс бөгөөс төлбөр,
        # зардал нь эзэнгүй үлдэж, дансны үлдэгдэл буруу болно.
        raise HTTPException(
            status_code=422, detail=f"{posted} мөр бүртгэгдсэн байна. Эхлээд буцаана уу"
        )
    if statement.fee_expense_id is not None:
        raise HTTPException(
            status_code=422, detail="Шимтгэлийн зардал бүртгэлтэй байна. Эхлээд буцаана уу"
        )
    await db.execute(delete(BankStatement).where(BankStatement.id == statement_id))
    await db.flush()


# --------------------------------------------------------------------------- #
# Бүртгэх / буцаах
# --------------------------------------------------------------------------- #
async def _post_one(db: AsyncSession, user: User, txn: BankTransaction) -> None:
    if txn.posted_at is not None:
        raise HTTPException(status_code=422, detail="Энэ мөр аль хэдийн бүртгэгдсэн байна")
    if txn.is_fee:
        raise HTTPException(status_code=422, detail="Шимтгэлийг нийлбэрээр нь нэг дор бүртгэнэ")

    statement = await _load(db, txn.statement_id)
    if statement.bank_account_id is None:
        raise HTTPException(status_code=422, detail="Хуулгын дансыг эхлээд сонгоно уу")

    amount, income = _amount_of(txn)
    if amount <= ZERO:
        raise HTTPException(status_code=422, detail="Гүйлгээний дүн тэг байна")

    at = (txn.txn_date or datetime.now(UTC)).date()
    note = (txn.description or "").strip() or (txn.bank_description or "").strip()

    if income:
        if txn.contract_id is None:
            raise HTTPException(status_code=422, detail="Харилцагч сонгоогүй байна")
        payment, _contract, _invoice, _entry = await contract_service.record_payment(
            db,
            user,
            contract_id=txn.contract_id,
            amount=amount,
            received_to="bank",
            bank_account_id=statement.bank_account_id,
            payment_date=at,
            note=note or "Банкны хуулга",
        )
        txn.ar_payment_id = payment.id
    else:
        if not txn.expense_account_code:
            raise HTTPException(status_code=422, detail="Зардлын ангилал сонгоогүй байна")
        expense = await expense_service.create_expense(
            db,
            user,
            account_code=txn.expense_account_code,
            amount=amount,
            payment_method="bank",
            expense_date=at,
            bank_account_id=statement.bank_account_id,
            description=note or "Банкны хуулга",
        )
        txn.expense_id = expense.id

    txn.posted_at = datetime.now(UTC)
    await db.flush()


async def post_transaction(
    db: AsyncSession, user: User, statement_id: uuid.UUID, txn_id: uuid.UUID
) -> None:
    txn = await _get_txn(db, statement_id, txn_id)
    await _post_one(db, user, txn)


async def post_all(db: AsyncSession, user: User, statement_id: uuid.UUID) -> dict[str, Any]:
    """Бэлэн болсон бүх мөрийг нэг дор бүртгэнэ.

    Шимтгэлийн мөрийг оруулахгүй — тэдгээрийг нийлбэрээр нь тусад нь хаана.
    Нэг мөр бүтэлгүйтсэн ч бусдыг үргэлжлүүлж, шалтгааныг буцаана.
    """
    statement = await _load(db, statement_id)
    rows = sorted(
        (t for t in statement.transactions if t.posted_at is None and not t.is_fee),
        key=lambda t: t.sort_order,
    )

    posted = 0
    skipped: list[dict[str, str]] = []
    for txn in rows:
        if _missing_fields(txn):
            skipped.append({"id": str(txn.id), "reason": "Мэдээлэл дутуу"})
            continue
        try:
            await _post_one(db, user, txn)
            posted += 1
        except HTTPException as exc:
            skipped.append({"id": str(txn.id), "reason": str(exc.detail)})
    return {"posted": posted, "skipped": skipped}


async def post_fees(
    db: AsyncSession,
    user: User,
    statement_id: uuid.UUID,
    account_code: str | None = None,
) -> None:
    """Хуулгын бүх шимтгэлийг нэгтгэж ганц зардал болгож хаана.

    Шимтгэл нь өдөрт хэдэн ч удаа, бага дүнгээр суудаг тул мөр бүрээр нь
    зардал үүсгэвэл бүртгэл хэрэггүй олон бичилтээр дүүрнэ.
    """
    statement = await _load(db, statement_id)
    if statement.fee_expense_id is not None:
        raise HTTPException(status_code=422, detail="Шимтгэл аль хэдийн бүртгэгдсэн байна")
    if statement.bank_account_id is None:
        raise HTTPException(status_code=422, detail="Хуулгын дансыг эхлээд сонгоно уу")

    fees = [t for t in statement.transactions if t.is_fee]
    if not fees:
        raise HTTPException(status_code=422, detail="Шимтгэлийн мөр алга")

    # Шимтгэл нь зарлага.  Буцаалт (кредит) байвал нийлбэрээс хасна.
    total = q2(sum((_d(t.debit) - _d(t.credit) for t in fees), ZERO))
    if total <= ZERO:
        raise HTTPException(status_code=422, detail="Шимтгэлийн нийлбэр тэг байна")

    config = await get_config(db)
    code = account_code or config.fee_account_code or ACC.EXP_BANK_FEE
    if code not in ACC.OPERATING_EXPENSES:
        raise HTTPException(status_code=422, detail="Зардлын данс биш байна")

    # Огноо — хамгийн эртний шимтгэлийн огноо, эс бөгөөс хуулгын эхлэл.
    dates = [t.txn_date for t in fees if t.txn_date is not None]
    at = min(dates).date() if dates else (statement.date_from or datetime.now(UTC).date())

    expense = await expense_service.create_expense(
        db,
        user,
        account_code=code,
        amount=total,
        payment_method="bank",
        expense_date=at,
        bank_account_id=statement.bank_account_id,
        description=f"{config.fee_description or 'Банкны шимтгэл'} ({len(fees)} гүйлгээ)",
    )

    now = datetime.now(UTC)
    statement.fee_expense_id = expense.id
    for txn in fees:
        txn.posted_at = now
        txn.expense_account_code = code
    await db.flush()


async def unpost_fees(db: AsyncSession, user: User, statement_id: uuid.UUID) -> None:
    statement = await _load(db, statement_id)
    if statement.fee_expense_id is None:
        raise HTTPException(status_code=422, detail="Шимтгэл бүртгэгдээгүй байна")

    expense_id = statement.fee_expense_id
    # Холбоосыг эхлээд салгана — эс бөгөөс FK нь устгалыг зогсооно.
    statement.fee_expense_id = None
    for txn in statement.transactions:
        if txn.is_fee:
            txn.posted_at = None
    await db.flush()
    await _delete_expense(db, user, expense_id)


async def unpost_transaction(
    db: AsyncSession, user: User, statement_id: uuid.UUID, txn_id: uuid.UUID
) -> None:
    """Бүртгэлийг буцаана — үүссэн төлбөр/зардлыг устгаж нөлөөг сэргээнэ."""
    txn = await _get_txn(db, statement_id, txn_id)
    if txn.posted_at is None:
        raise HTTPException(status_code=422, detail="Энэ мөр бүртгэгдээгүй байна")

    ar_payment_id = txn.ar_payment_id
    expense_id = txn.expense_id
    # Холбоосыг эхлээд салгана — эс бөгөөс FK нь устгалыг зогсооно.
    txn.ar_payment_id = None
    txn.expense_id = None
    txn.posted_at = None
    await db.flush()

    if ar_payment_id is not None:
        await _delete_ar_payment(db, user, ar_payment_id)
    if expense_id is not None:
        await _delete_expense(db, user, expense_id)


# --------------------------------------------------------------------------- #
# Буцаалт — үүсгэсэн баримт ба журналын бичилтийг цуцлана
# --------------------------------------------------------------------------- #
async def _delete_expense(db: AsyncSession, user: User | None, expense_id: uuid.UUID) -> None:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        return
    before = {
        "number": expense.number,
        "account_code": expense.account_code,
        "total": str(expense.total),
    }
    # Журналын бичилтийг баримттай нь хамт цуцална — хуулгын мөр буруу
    # бүртгэгдсэн тохиолдолд ул мөр үлдээх нь ашиггүй.  Хэн буцаасныг
    # аудит лог хөтөлнө.
    await posting.reverse(
        db,
        event_type=str(EventType.EXPENSE_POSTED),
        source_type=str(SourceType.EXPENSE),
        source_id=expense.id,
    )
    await db.delete(expense)
    await db.flush()
    await audit(
        db,
        user_id=getattr(user, "id", None),
        action="bank_statement.unpost_expense",
        entity_type="expense",
        entity_id=expense_id,
        before=before,
    )


async def _delete_ar_payment(db: AsyncSession, user: User | None, payment_id: uuid.UUID) -> None:
    payment = await db.get(ArPayment, payment_id)
    if payment is None:
        return

    # Гэрээний үлдэгдлийг сэргээнэ (төлбөр авахад буурсан байсан).
    contract = await db.get(Contract, payment.contract_id)
    if contract is not None:
        contract.balance = q2(_d(contract.balance) + _d(payment.amount))

    if payment.ar_invoice_id is not None:
        invoice = await db.get(ArInvoice, payment.ar_invoice_id)
        if invoice is not None:
            invoice.amount_paid = q2(_d(invoice.amount_paid) - _d(payment.amount))
            invoice.status = str(
                InvoiceStatus.OPEN
                if invoice.amount_paid <= ZERO
                else (
                    InvoiceStatus.PAID
                    if invoice.amount_paid >= _d(invoice.amount)
                    else InvoiceStatus.PARTIAL
                )
            )

    before = {
        "amount": str(payment.amount),
        "contract_id": str(payment.contract_id),
        "payment_date": payment.payment_date.isoformat(),
    }
    await posting.reverse(
        db,
        event_type=str(EventType.AR_RECEIPT),
        source_type=str(SourceType.AR_PAYMENT),
        source_id=payment.id,
    )
    await db.delete(payment)
    await db.flush()
    await audit(
        db,
        user_id=getattr(user, "id", None),
        action="bank_statement.unpost_receipt",
        entity_type="ar_payment",
        entity_id=payment_id,
        before=before,
    )


async def statement_count(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(BankStatement)) or 0)


async def account_name_map(db: AsyncSession) -> dict[str, str]:
    rows = (await db.scalars(select(Account).where(Account.code.in_(ACC.OPERATING_EXPENSES)))).all()
    return {a.code: a.name_mn for a in rows}
