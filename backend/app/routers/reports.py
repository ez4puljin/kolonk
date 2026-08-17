"""Тайлангийн API — борлуулалт, түлш, төлбөр, савны хорогдол, Excel экспорт (WP8)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.report import (
    FuelReportOut,
    SalesDetailOut,
    SalesReportOut,
    TankLossOut,
    TenderBreakdownOut,
    TopCustomerRow,
    TopProductRow,
)
from app.services import excel_service, report_service, statement_service

router = APIRouter(prefix="/api", tags=["reports"])

CanView = Depends(require_permission("reports.view"))


def _range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    """Огноо заагаагүй бол сарын эхнээс өнөөдрийг хүртэл."""
    end = date_to or report_service.today_local()
    start = date_from or end.replace(day=1)
    return start, end


# --------------------------------------------------------------------------- #
# JSON тайлангууд
# --------------------------------------------------------------------------- #
#: Тайлан бүр салбараар шүүгдэнэ — олон салбартай станцад зайлшгүй.
BranchFilter = Query(default=None, description="Зөвхөн энэ салбарын дүн")


@router.get("/reports/sales", response_model=SalesReportOut)
async def sales_report(
    granularity: str = Query(default="day", description="day | month | year"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    start, end = _range(date_from, date_to)
    return await report_service.sales_summary(db, start, end, granularity, branch_id)


@router.get("/reports/sales/detail", response_model=SalesDetailOut)
async def sales_detail_report(
    day: date | None = Query(default=None, alias="date"),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    return await report_service.sales_detail(
        db, day or report_service.today_local(), branch_id
    )


@router.get("/reports/fuel", response_model=FuelReportOut)
async def fuel_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    start, end = _range(date_from, date_to)
    return await report_service.fuel_report(db, start, end, branch_id)


@router.get("/reports/tender", response_model=TenderBreakdownOut)
async def tender_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    start, end = _range(date_from, date_to)
    return await report_service.tender_breakdown(db, start, end, branch_id)


@router.get("/reports/tank-loss", response_model=TankLossOut)
async def tank_loss_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> dict:
    start, end = _range(date_from, date_to)
    return await report_service.tank_loss_report(db, start, end, branch_id)


@router.get("/reports/top-products", response_model=list[TopProductRow])
async def top_products_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> list[dict]:
    start, end = _range(date_from, date_to)
    return await report_service.top_products(db, start, end, limit, branch_id)


@router.get("/reports/top-customers", response_model=list[TopCustomerRow])
async def top_customers_report(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> list[dict]:
    start, end = _range(date_from, date_to)
    return await report_service.top_customers(db, start, end, limit, branch_id)


# --------------------------------------------------------------------------- #
# Excel экспорт
# --------------------------------------------------------------------------- #
@router.get("/reports/sales.xlsx")
async def sales_report_xlsx(
    granularity: str = Query(default="day", description="day | month | year"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> StreamingResponse:
    start, end = _range(date_from, date_to)
    data = await report_service.sales_summary(db, start, end, granularity, branch_id)
    content = excel_service.sales_report_xlsx(data)
    return excel_service.xlsx_response(content, f"Борлуулалт_{start}_{end}.xlsx")


@router.get("/reports/fuel.xlsx")
async def fuel_report_xlsx(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: uuid.UUID | None = BranchFilter,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> StreamingResponse:
    start, end = _range(date_from, date_to)
    data = await report_service.fuel_report(db, start, end, branch_id)
    content = excel_service.fuel_report_xlsx(data)
    return excel_service.xlsx_response(content, f"Түлш_{start}_{end}.xlsx")


@router.get("/reports/inventory.xlsx")
async def inventory_report_xlsx(
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> StreamingResponse:
    data = await statement_service.inventory_valuation(db)
    content = excel_service.inventory_xlsx(data)
    return excel_service.xlsx_response(
        content, f"Нөөц_{report_service.today_local()}.xlsx"
    )
