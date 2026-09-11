"""Салбарын тооцооны API — өр/төлбөрийн дэвтэр, үлдэгдэл, төлбөр бүртгэх."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.bank import BankAccount
from app.models.branch import Branch
from app.models.settlement import BranchSettlement
from app.models.user import User
from app.money import q2
from app.schemas.shipment import (
    SETTLEMENT_TYPE_NAMES_MN,
    SettlementBalanceRow,
    SettlementEntryListOut,
    SettlementEntryOut,
    SettlementPaymentCreate,
)
from app.services import settlement_service

router = APIRouter(prefix="/api", tags=["branch_settlements"])


@router.get("/branch-settlements/balances", response_model=list[SettlementBalanceRow])
async def balances(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settlements.manage")),
) -> list[SettlementBalanceRow]:
    """Салбар бүрийн тооцооны үлдэгдэл."""
    return [SettlementBalanceRow(**row) for row in await settlement_service.balances(db)]


@router.get("/branch-settlements", response_model=SettlementEntryListOut)
async def list_entries(
    branch_id: uuid.UUID | None = Query(default=None),
    entry_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("settlements.manage")),
) -> SettlementEntryListOut:
    conditions = []
    if branch_id is not None:
        conditions.append(BranchSettlement.branch_id == branch_id)
    if entry_type in ("charge", "payment"):
        conditions.append(BranchSettlement.entry_type == entry_type)
    if date_from is not None:
        conditions.append(BranchSettlement.entry_date >= date_from)
    if date_to is not None:
        conditions.append(BranchSettlement.entry_date <= date_to)

    total = (
        await db.scalar(select(func.count()).select_from(BranchSettlement).where(*conditions))
    ) or 0
    rows = (
        await db.execute(
            select(BranchSettlement, Branch.name, BankAccount.bank_name, BankAccount.account_number)
            .join(Branch, Branch.id == BranchSettlement.branch_id)
            .outerjoin(BankAccount, BankAccount.id == BranchSettlement.to_bank_account_id)
            .where(*conditions)
            .order_by(BranchSettlement.entry_date.desc(), BranchSettlement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    items = [
        SettlementEntryOut(
            id=entry.id,
            branch_id=entry.branch_id,
            branch_name=branch_name,
            entry_type=str(entry.entry_type),
            entry_type_name=SETTLEMENT_TYPE_NAMES_MN.get(str(entry.entry_type), str(entry.entry_type)),
            entry_date=entry.entry_date,
            amount=q2(entry.amount),
            ref_type=entry.ref_type,
            ref_id=entry.ref_id,
            paid_from=entry.paid_from,
            to_bank_account_id=entry.to_bank_account_id,
            to_bank_account_name=(
                f"{bank_name} {account_number}" if bank_name else None
            ),
            note=entry.note,
            created_at=entry.created_at,
        )
        for entry, branch_name, bank_name, account_number in rows
    ]
    return SettlementEntryListOut(items=items, total=int(total))


@router.post("/branch-settlements/payments", response_model=SettlementEntryOut, status_code=201)
async def record_payment(
    payload: SettlementPaymentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("settlements.manage")),
) -> SettlementEntryOut:
    """Салбараас толгойн данс руу төлсөн төлбөрийг бүртгэнэ."""
    settlement = await settlement_service.record_payment(
        db,
        user,
        branch_id=payload.branch_id,
        amount=payload.amount,
        entry_date=payload.entry_date or date.today(),
        paid_from=payload.paid_from,
        from_bank_account_id=payload.from_bank_account_id,
        to_bank_account_id=payload.to_bank_account_id,
        note=payload.note,
    )
    branch_name = await db.scalar(select(Branch.name).where(Branch.id == settlement.branch_id))
    account = await db.scalar(
        select(BankAccount).where(BankAccount.id == settlement.to_bank_account_id)
    )
    return SettlementEntryOut(
        id=settlement.id,
        branch_id=settlement.branch_id,
        branch_name=branch_name,
        entry_type=str(settlement.entry_type),
        entry_type_name=SETTLEMENT_TYPE_NAMES_MN.get(str(settlement.entry_type)),
        entry_date=settlement.entry_date,
        amount=q2(settlement.amount),
        paid_from=settlement.paid_from,
        to_bank_account_id=settlement.to_bank_account_id,
        to_bank_account_name=(
            f"{account.bank_name} {account.account_number}" if account else None
        ),
        note=settlement.note,
        created_at=settlement.created_at,
    )
