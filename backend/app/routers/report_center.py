"""Тайлангийн төв — тайлангийн төрөл сонгож, олон утгатай шүүлтээр гаргана.

Шүүлт бүр давтагдах query параметр (`?account_code=1101&account_code=1102`).
Юу ч дамжуулаагүй бол "Бүгд" гэсэн утгатай.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.services import (
    excel_service,
    report_center_service as rcs,
    transaction_detail_service as tds,
)

router = APIRouter(prefix="/api", tags=["report-center"])

CanView = Depends(require_permission("reports.view"))


@router.get("/report-center/options")
async def options(
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    """Тайлангийн жагсаалт ба бүх шүүлтийн сонголт — нэг дуудлагаар."""
    return await rcs.filter_options(db)


def _params(
    report: str = Query(default="turnover"),
    date_from: date = Query(...),
    date_to: date = Query(...),
    account_code: list[str] = Query(default=[]),
    branch_id: list[uuid.UUID] = Query(default=[]),
    fuel_id: list[uuid.UUID] = Query(default=[]),
    category_id: list[uuid.UUID] = Query(default=[]),
    employee_id: list[uuid.UUID] = Query(default=[]),
    tx_type: list[str] = Query(default=[]),
    group_by: list[str] = Query(default=[]),
    include_details: bool = Query(default=False),
) -> dict:
    return {
        "report": report,
        "date_from": date_from,
        "date_to": date_to,
        "account_codes": account_code or None,
        "branch_ids": branch_id or None,
        "fuel_ids": fuel_id or None,
        "category_ids": category_id or None,
        "employee_ids": employee_id or None,
        "tx_types": tx_type or None,
        "group_by": group_by or None,
        "include_details": include_details,
    }


@router.get("/report-center/run")
async def run(
    params: dict = Depends(_params),
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    return await rcs.run_report(db, **params)


@router.get("/report-center/run.xlsx")
async def run_xlsx(
    params: dict = Depends(_params),
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    data = await rcs.run_report(db, **params)
    content = excel_service.report_center_xlsx(data)
    name = f"{data['report_name']}_{params['date_from']}_{params['date_to']}.xlsx"
    return excel_service.xlsx_response(content, name)


@router.get("/report-center/drill")
async def drill(
    path: list[str] = Query(default=[]),
    limit: int = Query(default=500, ge=1, le=2000),
    params: dict = Depends(_params),
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    """Тайлангийн мөрийн задаргаа — мөр дээр давхар товшиход дуудагдана.

    `path` нь тухайн мөрийн бүрэн зам (дээд түвшнээс, давтагдах параметр).
    """
    args = {k: v for k, v in params.items() if k != "include_details"}
    return await rcs.drill_group(db, path=path, limit=limit, **args)


@router.get("/transactions/{source_type}/{source_id}")
async def transaction_detail(
    source_type: str,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    """Задаргааны мөр дээр давхар товшиход нээгдэх гүйлгээний дэлгэрэнгүй."""
    return await tds.transaction_detail(db, source_type, source_id)
