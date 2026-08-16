"""Ваучерын API (WP6).

Ваучер хэвлэх/зарах/хүчингүй болгоход ``instruments.manage`` эрх шаардана.
ПОС дэлгэц төлбөр авахын өмнө ваучерыг шалгах тул ``/validate/{code}``-д
``sales.create`` эрх ч хангалттай.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import VoucherStatus
from app.models.instrument import Voucher
from app.models.partner import Customer
from app.models.user import User
from app.schemas.partner import (
    VoucherIssueIn,
    VoucherListOut,
    VoucherOut,
    VoucherSellIn,
    VoucherValidateOut,
    VoucherVoidIn,
)
from app.services import instrument_service

router = APIRouter(prefix="/api", tags=["vouchers"])

CanManage = Depends(require_permission("instruments.manage"))
CanUse = Depends(require_permission("sales.create", "instruments.manage"))


async def _names(db: AsyncSession, rows: list[Voucher]) -> dict[uuid.UUID, str]:
    ids = {row.customer_id for row in rows if row.customer_id is not None}
    if not ids:
        return {}
    result = (await db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(ids)))).all()
    return {r[0]: r[1] for r in result}


@router.get("/vouchers", response_model=VoucherListOut)
async def list_vouchers(
    status: VoucherStatus | None = Query(default=None),
    code: str | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> VoucherListOut:
    conditions: list = []
    if status is not None:
        conditions.append(Voucher.status == str(status))
    if code:
        conditions.append(Voucher.code.ilike(f"%{code.strip().upper()}%"))
    if customer_id is not None:
        conditions.append(Voucher.customer_id == customer_id)

    total = await db.scalar(select(func.count()).select_from(Voucher).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(Voucher)
            .where(*conditions)
            .order_by(Voucher.created_at.desc(), Voucher.code)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    names = await _names(db, list(rows))
    return VoucherListOut(
        items=[
            VoucherOut(**instrument_service.voucher_out(row, customer_name=names.get(row.customer_id)))
            for row in rows
        ],
        total=int(total),
    )


@router.post("/vouchers/issue-batch", response_model=VoucherListOut, status_code=201)
async def issue_batch(
    payload: VoucherIssueIn,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> VoucherListOut:
    vouchers = await instrument_service.issue_vouchers(
        db,
        user,
        count=payload.count,
        face_value=payload.face_value,
        expires_at=payload.expires_at,
        customer_id=payload.customer_id,
    )
    return VoucherListOut(
        items=[VoucherOut(**instrument_service.voucher_out(v)) for v in vouchers], total=len(vouchers)
    )


@router.get("/vouchers/validate/{code}", response_model=VoucherValidateOut)
async def validate_voucher(
    code: str,
    db: AsyncSession = Depends(get_db),
    _user: User = CanUse,
) -> VoucherValidateOut:
    voucher = await instrument_service.validate_voucher(db, code)
    name = await instrument_service.customer_name(db, voucher.customer_id)
    return VoucherValidateOut(
        valid=True,
        message="Ваучер хүчинтэй",
        voucher=VoucherOut(**instrument_service.voucher_out(voucher, customer_name=name)),
    )


@router.get("/vouchers/{voucher_id}", response_model=VoucherOut)
async def get_voucher(
    voucher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = CanManage,
) -> VoucherOut:
    voucher = await instrument_service.get_voucher(db, voucher_id)
    name = await instrument_service.customer_name(db, voucher.customer_id)
    return VoucherOut(**instrument_service.voucher_out(voucher, customer_name=name))


@router.post("/vouchers/{voucher_id}/sell", response_model=VoucherOut)
async def sell_voucher(
    voucher_id: uuid.UUID,
    payload: VoucherSellIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> VoucherOut:
    data = payload or VoucherSellIn()
    voucher, _entry_id = await instrument_service.sell_voucher(
        db, user, voucher_id, str(data.tender_method), customer_id=data.customer_id
    )
    name = await instrument_service.customer_name(db, voucher.customer_id)
    return VoucherOut(**instrument_service.voucher_out(voucher, customer_name=name))


@router.post("/vouchers/{voucher_id}/void", response_model=VoucherOut)
async def void_voucher(
    voucher_id: uuid.UUID,
    payload: VoucherVoidIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> VoucherOut:
    voucher = await instrument_service.void_voucher(
        db, user, voucher_id, reason=payload.reason if payload else None
    )
    name = await instrument_service.customer_name(db, voucher.customer_id)
    return VoucherOut(**instrument_service.voucher_out(voucher, customer_name=name))
