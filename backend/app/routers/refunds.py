"""Буцаалтын API (WP6) — түгээгч хүсэлт гаргаж, эзэн/менежер батална."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import ApprovalStatus
from app.models.user import User
from app.schemas.sale import RefundCreate, RefundDecisionIn, RefundListOut, RefundOut, RefundResultOut
from app.services import refund_service

router = APIRouter(prefix="/api", tags=["refunds"])

CanRequest = Depends(require_permission("sales.refund.request", "sales.refund.approve"))
CanApprove = Depends(require_permission("sales.refund.approve"))


@router.post("/refunds", response_model=RefundOut, status_code=201)
async def create_refund(
    payload: RefundCreate,
    db: AsyncSession = Depends(get_db),
    user: User = CanRequest,
) -> RefundOut:
    refund = await refund_service.request_refund(
        db,
        user,
        sale_id=payload.sale_id,
        refund_type=str(payload.refund_type),
        items=payload.items,
        amount=payload.amount,
        reason=payload.reason,
        restock=payload.restock,
        refund_method=str(payload.refund_method) if payload.refund_method else None,
    )
    return RefundOut(**await refund_service.refund_detail(db, refund))


@router.get("/refunds", response_model=RefundListOut)
async def list_refunds(
    status: ApprovalStatus | None = Query(default=None),
    sale_id: uuid.UUID | None = Query(default=None),
    shift_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = CanRequest,
) -> RefundListOut:
    result = await refund_service.list_refunds(
        db,
        status=str(status) if status else None,
        sale_id=sale_id,
        shift_id=shift_id,
        limit=limit,
        offset=offset,
    )
    return RefundListOut(**result)


@router.get("/refunds/{refund_id}", response_model=RefundOut)
async def get_refund(
    refund_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = CanRequest,
) -> RefundOut:
    refund = await refund_service.get_refund(db, refund_id)
    return RefundOut(**await refund_service.refund_detail(db, refund))


@router.post("/refunds/{refund_id}/approve", response_model=RefundResultOut)
async def approve_refund(
    refund_id: uuid.UUID,
    payload: RefundDecisionIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = CanApprove,
) -> RefundResultOut:
    refund = await refund_service.get_refund(db, refund_id, lock=True)
    refund, sale, entry_id = await refund_service.approve_refund(
        db, user, refund, note=payload.note if payload else None
    )
    return RefundResultOut(
        refund=RefundOut(**await refund_service.refund_detail(db, refund)),
        sale_status=str(sale.status),
        journal_entry_id=entry_id,
    )


@router.post("/refunds/{refund_id}/reject", response_model=RefundResultOut)
async def reject_refund(
    refund_id: uuid.UUID,
    payload: RefundDecisionIn | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = CanApprove,
) -> RefundResultOut:
    refund = await refund_service.get_refund(db, refund_id, lock=True)
    refund = await refund_service.reject_refund(db, user, refund, note=payload.note if payload else None)
    return RefundResultOut(
        refund=RefundOut(**await refund_service.refund_detail(db, refund)),
        sale_status=None,
        journal_entry_id=None,
    )
