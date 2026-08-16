"""Ажилтан ба цалингийн тооцоо.

Урсгал: `POST /api/payroll/periods` (сар үүсгэх, ноорог) → мөр засах →
`POST /api/payroll/periods/{id}/approve` (журналд бичигдэнэ) →
`POST /api/payroll/periods/{id}/pay` (цалин/ХХОАТ/НДШ тус тусад нь).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.payroll import Employee, PayrollLine, PayrollPeriod
from app.models.user import User
from app.schemas.payroll import (
    AdvanceCreate,
    AdvanceListOut,
    AdvanceOut,
    EmployeeCreate,
    EmployeeListOut,
    EmployeeOut,
    EmployeeUpdate,
    PayrollLineUpdate,
    PayrollPayRequest,
    PayrollPeriodCreate,
    PayrollPeriodListOut,
    PayrollPeriodOut,
)
from app.services import payroll_service

router = APIRouter(prefix="/api", tags=["payroll"])

CanManage = Depends(require_permission("payroll.manage"))
CanApprove = Depends(require_permission("payroll.approve"))


# --------------------------------------------------------------------------- #
# Ажилтан
# --------------------------------------------------------------------------- #
@router.get("/employees", response_model=EmployeeListOut)
async def list_employees(
    active_only: bool = Query(default=False),
    is_active: bool | None = Query(default=None, description="True=ажиллаж буй, False=гарсан"),
    search: str | None = Query(default=None, description="Бүх мэдээллээр хайх"),
    branch_id: uuid.UUID | None = Query(default=None),
    hired_from: date | None = Query(default=None, description="Ажилд орсон огноо (эхлэх)"),
    hired_to: date | None = Query(default=None, description="Ажилд орсон огноо (дуусах)"),
    created_from: date | None = Query(default=None, description="Бүртгэсэн огноо (эхлэх)"),
    created_to: date | None = Query(default=None, description="Бүртгэсэн огноо (дуусах)"),
    db: AsyncSession = Depends(get_db),
    _: User = CanManage,
):
    return await payroll_service.list_employees(
        db,
        active_only=active_only,
        is_active=is_active,
        search=search,
        branch_id=branch_id,
        hired_from=hired_from,
        hired_to=hired_to,
        created_from=created_from,
        created_to=created_to,
    )


@router.post("/employees", response_model=EmployeeOut, status_code=201)
async def create_employee(
    payload: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    return await payroll_service.create_employee(db, user, **payload.model_dump(exclude_unset=True))


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Ажилтан олдсонгүй")
    return await payroll_service.update_employee(
        db, user, employee, **payload.model_dump(exclude_unset=True)
    )


# --------------------------------------------------------------------------- #
# Цалингийн хугацаа
# --------------------------------------------------------------------------- #
@router.get("/payroll/periods", response_model=PayrollPeriodListOut)
async def list_periods(
    db: AsyncSession = Depends(get_db),
    _: User = CanManage,
):
    return await payroll_service.list_periods(db)


@router.post("/payroll/periods", response_model=PayrollPeriodOut, status_code=201)
async def create_period(
    payload: PayrollPeriodCreate,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    """Тухайн сарын тооцоог үүсгэнэ (аль хэдийн байвал түүнийг буцаана)."""
    period = await payroll_service.get_or_create_period(
        db, user, payload.year, payload.month, payload.employee_ids
    )
    return await payroll_service.period_detail(db, period)


async def _period_or_404(db: AsyncSession, period_id: uuid.UUID) -> PayrollPeriod:
    period = await db.get(PayrollPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Цалингийн хугацаа олдсонгүй")
    return period


@router.get("/payroll/periods/{period_id}", response_model=PayrollPeriodOut)
async def get_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = CanManage,
):
    return await payroll_service.period_detail(db, await _period_or_404(db, period_id))


@router.delete("/payroll/periods/{period_id}", status_code=204, response_class=Response)
async def cancel_draft_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    """Ноорог тооцоог цуцална. Батлагдсан тооцоог цуцлах боломжгүй."""
    period = await _period_or_404(db, period_id)
    await payroll_service.delete_draft(db, user, period)
    return Response(status_code=204)


@router.patch("/payroll/lines/{line_id}", response_model=PayrollPeriodOut)
async def update_line(
    line_id: uuid.UUID,
    payload: PayrollLineUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = CanManage,
):
    line = await db.get(PayrollLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Цалингийн мөр олдсонгүй")
    period = await _period_or_404(db, line.period_id)
    await payroll_service.update_line(db, period, line, **payload.model_dump(exclude_unset=True))
    return await payroll_service.period_detail(db, period)


@router.post("/payroll/periods/{period_id}/recalculate", response_model=PayrollPeriodOut)
async def recalculate(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = CanManage,
):
    period = await _period_or_404(db, period_id)
    await payroll_service.recalculate(db, period)
    return await payroll_service.period_detail(db, period)


@router.post("/payroll/periods/{period_id}/approve", response_model=PayrollPeriodOut)
async def approve_period(
    period_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = CanApprove,
):
    period = await _period_or_404(db, period_id)
    await payroll_service.approve(db, user, period)
    return await payroll_service.period_detail(db, period)


@router.post("/payroll/periods/{period_id}/pay", response_model=PayrollPeriodOut)
async def pay_period(
    period_id: uuid.UUID,
    payload: PayrollPayRequest,
    db: AsyncSession = Depends(get_db),
    user: User = CanApprove,
):
    period = await _period_or_404(db, period_id)
    await payroll_service.pay(
        db,
        user,
        period,
        target=payload.target,
        amount=payload.amount,
        paid_from=payload.paid_from,
        payment_date=payload.payment_date,
    )
    return await payroll_service.period_detail(db, period)


# --------------------------------------------------------------------------- #
# Урьдчилгаа
# --------------------------------------------------------------------------- #
@router.get("/payroll/advances", response_model=AdvanceListOut)
async def list_advances(
    employee_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = CanManage,
):
    return await payroll_service.list_advances(db, employee_id=employee_id)


@router.post("/payroll/advances", response_model=AdvanceOut, status_code=201)
async def give_advance(
    payload: AdvanceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
):
    """Ажилтанд урьдчилгаа олгоно — 1205 дансанд авлага үүсч, цалингаас суутгагдана."""
    row = await payroll_service.give_advance(
        db,
        user,
        employee_id=payload.employee_id,
        amount=payload.amount,
        paid_from=payload.paid_from,
        advance_date=payload.advance_date,
        note=payload.note,
    )
    page = await payroll_service.list_advances(db, employee_id=payload.employee_id)
    for item in page["items"]:
        if item["id"] == row.id:
            return item
    raise HTTPException(status_code=500, detail="Урьдчилгаа үүсгэхэд алдаа гарлаа")

