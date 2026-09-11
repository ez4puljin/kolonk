"""Салбарын тооцооны үйлчилгээ — өр (charge) ба төлбөрийн (payment) дэвтэр.

Өр нь ачилтын түгээлтээс автоматаар үүснэ (``shipment_service.deliver``).
Энэ модуль үлдэгдлийг тоолж, төлбөр бүртгэнэ.  Төлбөр нь мөнгөний бодит
хөдөлгөөн (салбарын касс → толгойн харилцах) тул `BRANCH_SETTLEMENT_PAID`
журналын бичилт хийгдэнэ.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventType, SettlementEntryType, SourceType
from app.models.bank import BankAccount
from app.models.branch import Branch
from app.models.settlement import BranchSettlement
from app.models.user import User
from app.money import q2
from app.services.audit_service import audit
from app.services.posting import posting
from app.services.posting_rules import build_branch_settlement_lines

ZERO = Decimal("0")


async def balances(db: AsyncSession) -> list[dict[str, Any]]:
    """Салбар бүрийн тооцооны үлдэгдэл: Σ өр − Σ төлбөр."""
    charge_sum = func.coalesce(
        func.sum(
            case(
                (BranchSettlement.entry_type == str(SettlementEntryType.CHARGE), BranchSettlement.amount),
                else_=0,
            )
        ),
        0,
    )
    payment_sum = func.coalesce(
        func.sum(
            case(
                (BranchSettlement.entry_type == str(SettlementEntryType.PAYMENT), BranchSettlement.amount),
                else_=0,
            )
        ),
        0,
    )
    rows = (
        await db.execute(
            select(
                Branch.id,
                Branch.name,
                Branch.code,
                charge_sum.label("charged"),
                payment_sum.label("paid"),
            )
            .outerjoin(BranchSettlement, BranchSettlement.branch_id == Branch.id)
            .where(Branch.is_active.is_(True))
            .group_by(Branch.id, Branch.name, Branch.code)
            .order_by(Branch.sort_order, Branch.name)
        )
    ).all()
    return [
        {
            "branch_id": row.id,
            "branch_name": row.name,
            "branch_code": row.code,
            "charged": q2(row.charged),
            "paid": q2(row.paid),
            "balance": q2(Decimal(row.charged) - Decimal(row.paid)),
        }
        for row in rows
    ]


async def record_payment(
    db: AsyncSession,
    user: User | None,
    *,
    branch_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    paid_from: str = "cash",
    from_bank_account_id: uuid.UUID | None = None,
    to_bank_account_id: uuid.UUID | None = None,
    note: str | None = None,
) -> BranchSettlement:
    """Салбараас толгойн данс руу төлсөн төлбөрийг бүртгэнэ."""
    amount = q2(Decimal(str(amount)))
    if amount <= ZERO:
        raise HTTPException(status_code=422, detail="Дүн 0-ээс их байх ёстой")

    branch = await db.scalar(select(Branch).where(Branch.id == branch_id))
    if branch is None:
        raise HTTPException(status_code=404, detail="Салбар олдсонгүй")

    if paid_from not in ("cash", "bank"):
        raise HTTPException(status_code=422, detail="Төлбөрийн хэлбэр cash эсвэл bank байна")

    if to_bank_account_id is None:
        raise HTTPException(status_code=422, detail="Мөнгө орсон дансыг сонгоно уу")
    to_account = await db.scalar(select(BankAccount).where(BankAccount.id == to_bank_account_id))
    if to_account is None:
        raise HTTPException(status_code=404, detail="Хүлээн авах данс олдсонгүй")

    if paid_from == "bank" and from_bank_account_id is not None:
        from_account = await db.scalar(
            select(BankAccount).where(BankAccount.id == from_bank_account_id)
        )
        if from_account is None:
            raise HTTPException(status_code=404, detail="Төлсөн данс олдсонгүй")

    settlement = BranchSettlement(
        branch_id=branch_id,
        entry_type=str(SettlementEntryType.PAYMENT),
        entry_date=entry_date,
        amount=amount,
        paid_from=paid_from,
        from_bank_account_id=from_bank_account_id if paid_from == "bank" else None,
        to_bank_account_id=to_bank_account_id,
        note=(note or "").strip() or None,
        created_by=getattr(user, "id", None),
    )
    db.add(settlement)
    await db.flush()

    await posting.post(
        db,
        event_type=str(EventType.BRANCH_SETTLEMENT_PAID),
        source_type=str(SourceType.BRANCH_SETTLEMENT),
        source_id=settlement.id,
        entry_date=entry_date,
        description=f"Салбарын тооцоо — {branch.name}",
        lines=build_branch_settlement_lines(settlement),
        posted_by=getattr(user, "id", None),
    )

    await audit(
        db,
        user_id=getattr(user, "id", None),
        action="branch_settlement.pay",
        entity_type="branch_settlement",
        entity_id=settlement.id,
        after={
            "branch_id": str(branch_id),
            "amount": str(amount),
            "paid_from": paid_from,
            "to_bank_account_id": str(to_bank_account_id),
        },
    )
    return settlement
