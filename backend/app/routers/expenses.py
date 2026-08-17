"""Үйл ажиллагааны зардал — цалин, цахилгаан, түрээс, засвар г.м.

Борлуулалттай шууд холбоогүй зардлыг энд бүртгэснээр орлого зардлын тайлан
цэвэр ашгийг үнэн зөв харуулна. Бэлнээр төлсөн зардал ээлжийн байвал зохих
кассаас автоматаар хасагдана (`shift_service._other_cash_movement`).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import (
    ExpenseCategoryOut,
    ExpenseCreate,
    ExpenseListOut,
    ExpenseOut,
)
from app.services import expense_service

router = APIRouter(prefix="/api", tags=["expenses"])


@router.get("/expense-categories", response_model=list[ExpenseCategoryOut])
async def expense_categories(
    db: AsyncSession = Depends(get_db),
    # Түгээгч өдрийн хаалтад зарлага бүртгэдэг тул shifts.close-той нээлттэй.
    _: User = Depends(require_permission("expenses.manage", "shifts.close")),
):
    """Зардал бүртгэх боломжтой данснууд (дэлгэцийн том плиткууд)."""
    return await expense_service.list_categories(db)


@router.get("/expense-payment-methods")
async def expense_payment_methods(
    _: User = Depends(require_permission("expenses.manage", "shifts.close")),
):
    return [{"code": k, "name_mn": v} for k, v in expense_service.PAYMENT_METHODS.items()]


@router.get("/expenses", response_model=ExpenseListOut)
async def list_expenses(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    account_code: str | None = Query(default=None),
    payment_method: str | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None, description="Зөвхөн энэ салбарын зардал"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("expenses.manage")),
):
    return await expense_service.list_expenses(
        db,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
        payment_method=payment_method,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
    )


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("expenses.manage")),
):
    expense = await expense_service.create_expense(
        db,
        user,
        account_code=payload.account_code,
        amount=payload.amount,
        payment_method=payload.payment_method,
        expense_date=payload.expense_date,
        has_vat=payload.has_vat,
        supplier_id=payload.supplier_id,
        bank_account_id=payload.bank_account_id,
        invoice_no=payload.invoice_no,
        description=payload.description,
        branch_id=payload.branch_id,
    )
    return await _one(db, expense.id)


@router.get("/expenses/{expense_id}", response_model=ExpenseOut)
async def get_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("expenses.manage")),
):
    return await _one(db, expense_id)


async def _one(db: AsyncSession, expense_id: uuid.UUID) -> dict:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Зардал олдсонгүй")
    page = await expense_service.list_expenses(db, limit=500)
    for row in page["items"]:
        if row["id"] == expense_id:
            return row
    raise HTTPException(status_code=404, detail="Зардал олдсонгүй")
