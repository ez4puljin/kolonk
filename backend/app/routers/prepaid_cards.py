"""Урьдчилсан төлбөрт картын API (WP6).

Карт нээх/цэнэглэх/хаахад ``instruments.manage`` эрх шаардана. ПОС дэлгэц
төлбөр авахын өмнө үлдэгдэл хардаг тул ``/lookup/{card_no}``-д ``sales.create``
эрх ч хангалттай.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import CardStatus
from app.models.instrument import PrepaidCard
from app.models.partner import Customer
from app.models.user import User
from app.schemas.partner import (
    CardBlockIn,
    CardOperationOut,
    CardTopupIn,
    CardTxListOut,
    CardTxOut,
    PrepaidCardCreate,
    PrepaidCardListOut,
    PrepaidCardOut,
)
from app.services import instrument_service

router = APIRouter(prefix="/api", tags=["prepaid_cards"])

CanManage = Depends(require_permission("instruments.manage"))
CanUse = Depends(require_permission("sales.create", "instruments.manage"))


async def _names(db: AsyncSession, rows: list[PrepaidCard]) -> dict[uuid.UUID, str]:
    ids = {row.customer_id for row in rows if row.customer_id is not None}
    if not ids:
        return {}
    result = (await db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(ids)))).all()
    return {r[0]: r[1] for r in result}


@router.get("/prepaid-cards", response_model=PrepaidCardListOut)
async def list_cards(
    search: str | None = Query(default=None, description="Дугаар эсвэл эзэмшигчийн нэр"),
    status: CardStatus | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> PrepaidCardListOut:
    conditions: list = []
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(or_(PrepaidCard.card_no.ilike(pattern), PrepaidCard.holder_name.ilike(pattern)))
    if status is not None:
        conditions.append(PrepaidCard.status == str(status))
    if customer_id is not None:
        conditions.append(PrepaidCard.customer_id == customer_id)

    total = await db.scalar(select(func.count()).select_from(PrepaidCard).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(PrepaidCard).where(*conditions).order_by(PrepaidCard.card_no).limit(limit).offset(offset)
        )
    ).all()
    names = await _names(db, list(rows))
    return PrepaidCardListOut(
        items=[
            PrepaidCardOut(**instrument_service.card_out(row, customer_name=names.get(row.customer_id)))
            for row in rows
        ],
        total=int(total),
    )


@router.post("/prepaid-cards", response_model=CardOperationOut, status_code=201)
async def create_card(
    payload: PrepaidCardCreate,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> CardOperationOut:
    card = await instrument_service.create_card(
        db,
        user,
        card_no=payload.card_no,
        holder_name=payload.holder_name,
        customer_id=payload.customer_id,
    )

    tx = None
    entry_id = None
    if payload.initial_amount > 0:
        tx, entry_id = await instrument_service.topup_card(
            db, user, card, payload.initial_amount, str(payload.tender_method)
        )

    name = await instrument_service.customer_name(db, card.customer_id)
    return CardOperationOut(
        card=PrepaidCardOut(**instrument_service.card_out(card, customer_name=name)),
        transaction=CardTxOut(**instrument_service.card_tx_out(tx)) if tx is not None else None,
        journal_entry_id=entry_id,
    )


@router.get("/prepaid-cards/lookup/{card_no}", response_model=PrepaidCardOut)
async def lookup_card(
    card_no: str,
    db: AsyncSession = Depends(get_db),
    _user: User = CanUse,
) -> PrepaidCardOut:
    card = await instrument_service.lookup_card(db, card_no)
    name = await instrument_service.customer_name(db, card.customer_id)
    return PrepaidCardOut(**instrument_service.card_out(card, customer_name=name))


@router.get("/prepaid-cards/{card_id}", response_model=PrepaidCardOut)
async def get_card(
    card_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> PrepaidCardOut:
    card = await instrument_service.get_card(db, card_id)
    name = await instrument_service.customer_name(db, card.customer_id)
    return PrepaidCardOut(**instrument_service.card_out(card, customer_name=name))


@router.get("/prepaid-cards/{card_id}/transactions", response_model=CardTxListOut)
async def card_transactions(
    card_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> CardTxListOut:
    await instrument_service.get_card(db, card_id)
    return CardTxListOut(**await instrument_service.card_transactions(db, card_id, limit=limit, offset=offset))


@router.post("/prepaid-cards/{card_id}/topup", response_model=CardOperationOut)
async def topup_card(
    card_id: uuid.UUID,
    payload: CardTopupIn,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> CardOperationOut:
    card = await instrument_service.get_card(db, card_id, lock=True)
    tx, entry_id = await instrument_service.topup_card(
        db, user, card, payload.amount, str(payload.tender_method)
    )
    name = await instrument_service.customer_name(db, card.customer_id)
    return CardOperationOut(
        card=PrepaidCardOut(**instrument_service.card_out(card, customer_name=name)),
        transaction=CardTxOut(**instrument_service.card_tx_out(tx)),
        journal_entry_id=entry_id,
    )


@router.post("/prepaid-cards/{card_id}/block", response_model=PrepaidCardOut)
async def block_card(
    card_id: uuid.UUID,
    payload: CardBlockIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> PrepaidCardOut:
    card = await instrument_service.get_card(db, card_id, lock=True)
    card = await instrument_service.block_card(db, user, card, reason=payload.reason if payload else None)
    name = await instrument_service.customer_name(db, card.customer_id)
    return PrepaidCardOut(**instrument_service.card_out(card, customer_name=name))
