"""Банкны данс — бүртгэл ба үлдэгдэл.

Ерөнхий дэвтэрт бүх харилцах данс ``1110 Банк``-т нэгтгэгддэг.  Данс тус
бүрийн үлдэгдлийг ``journal_lines.dim_bank_account_id`` хэмжүүрээр гаргана:

    үлдэгдэл = эхний үлдэгдэл + Σ(дебит − кредит)

Хэмжүүргүй 1110 мөрүүд (жишээ нь нийлүүлэгчид шилжүүлсэн төлбөр) «хуваарилаагүй»
болж тайланд тусдаа мөрөөр гарна — ингэснээр Σ(данс) + хуваарилаагүй нь 1110-тэй
үргэлж таарна.

Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй — ``get_db`` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventType
from app.models.accounting import JournalEntry, JournalLine
from app.models.bank import BankAccount
from app.money import q2
from app.services.coa import ACC

ZERO = Decimal("0.00")


def _d(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


async def get_account(db: AsyncSession, account_id: uuid.UUID) -> BankAccount:
    account = await db.get(BankAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Харилцах данс олдсонгүй")
    return account


async def movement_map(db: AsyncSession, *, opening_only: bool = False) -> dict[uuid.UUID, Decimal]:
    """Данс бүрийн ерөнхий дэвтэр дэх цэвэр хөдөлгөөн (дебит − кредит).

    ``opening_only`` — зөвхөн эхний үлдэгдлийн бичилтүүд (BANK_OPENING_POSTED).
    """
    stmt = (
        select(
            JournalLine.dim_bank_account_id,
            func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0),
        )
        .where(
            JournalLine.account_code == ACC.BANK,
            JournalLine.dim_bank_account_id.is_not(None),
        )
        .group_by(JournalLine.dim_bank_account_id)
    )
    if opening_only:
        stmt = stmt.join(JournalEntry, JournalEntry.id == JournalLine.entry_id).where(
            JournalEntry.event_type == str(EventType.BANK_OPENING_POSTED)
        )
    rows = (await db.execute(stmt)).all()
    return {row[0]: q2(_d(row[1])) for row in rows}


async def posted_opening(db: AsyncSession, account_id: uuid.UUID) -> Decimal:
    """Тухайн дансны журналд бичигдсэн эхний үлдэгдэл (залруулгыг оруулаад)."""
    return (await movement_map(db, opening_only=True)).get(account_id, ZERO)


async def unassigned_movement(db: AsyncSession) -> Decimal:
    """Аль ч данстай холбогдоогүй 1110 хөдөлгөөн."""
    value = await db.scalar(
        select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).where(
            JournalLine.account_code == ACC.BANK,
            JournalLine.dim_bank_account_id.is_(None),
        )
    )
    return q2(_d(value))


async def list_accounts(
    db: AsyncSession, *, active_only: bool = False, branch_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    """Данснуудыг үлдэгдэлтэй нь буцаана."""
    conditions = []
    if active_only:
        conditions.append(BankAccount.is_active.is_(True))
    if branch_id is not None:
        conditions.append(BankAccount.branch_id == branch_id)

    accounts = (
        await db.scalars(
            select(BankAccount)
            .where(*conditions)
            .order_by(BankAccount.sort_order, BankAccount.bank_name)
        )
    ).all()
    moves = await movement_map(db)
    openings = await movement_map(db, opening_only=True)

    return [_to_dict(a, moves.get(a.id, ZERO), openings.get(a.id, ZERO)) for a in accounts]


def _to_dict(
    account: BankAccount, total_movement: Decimal = ZERO, posted_opening: Decimal = ZERO
) -> dict[str, Any]:
    """Үлдэгдэл = эхний үлдэгдэл + (журналын хөдөлгөөн − журналд бичигдсэн эхний үлдэгдэл).

    Эхний үлдэгдэл журналд бүрэн бичигдсэн бол энэ нь яг 1110-ийн тухайн
    дансны хэмжүүрийн үлдэгдэлтэй тэнцэнэ; бичигдээгүй хуучин данс ч зөв гарна.
    """
    opening = q2(_d(account.opening_balance))
    movement = q2(total_movement - posted_opening)
    return {
        "id": account.id,
        "branch_id": account.branch_id,
        "bank_name": account.bank_name,
        "account_number": account.account_number,
        "holder_name": account.holder_name,
        "currency": account.currency,
        "opening_balance": opening,
        "movement": movement,
        "balance": q2(opening + movement),
        "is_fee_default": account.is_fee_default,
        "is_active": account.is_active,
        "note": account.note,
        "sort_order": account.sort_order,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


async def account_out(db: AsyncSession, account: BankAccount) -> dict[str, Any]:
    moves = await movement_map(db)
    openings = await movement_map(db, opening_only=True)
    return _to_dict(account, moves.get(account.id, ZERO), openings.get(account.id, ZERO))


async def clear_fee_default(db: AsyncSession, keep_id: uuid.UUID | None = None) -> None:
    """Шимтгэлийн анхдагч данс зөвхөн нэг байна."""
    rows = (
        await db.scalars(select(BankAccount).where(BankAccount.is_fee_default.is_(True)))
    ).all()
    for row in rows:
        if keep_id is None or row.id != keep_id:
            row.is_fee_default = False


async def find_by_number(db: AsyncSession, account_number: str) -> BankAccount | None:
    """Хуулгын дансны дугаараар манай дансыг олно."""
    number = (account_number or "").strip()
    if not number:
        return None
    return await db.scalar(select(BankAccount).where(BankAccount.account_number == number))


async def fee_default_account(db: AsyncSession) -> BankAccount | None:
    return await db.scalar(
        select(BankAccount).where(
            BankAccount.is_fee_default.is_(True), BankAccount.is_active.is_(True)
        )
    )
