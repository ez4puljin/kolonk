"""Хяналтын самбарын API — түгээгч ба эзэн (WP8)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.report import CashierDashboardOut, OwnerDashboardOut
from app.services import report_service

router = APIRouter(prefix="/api", tags=["dashboards"])

CanViewOwner = Depends(require_permission("dashboard.owner"))


@router.get("/dashboards/cashier", response_model=CashierDashboardOut)
async def cashier_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Түгээгчийн нүүр — нээлттэй ээлж, өнөөдрийн дүн, савны түвшин, насосны төлөв."""
    return await report_service.cashier_dashboard(db, user)


@router.get("/dashboards/branch-shifts")
async def branch_shifts(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    """Салбар бүрийн нээлттэй түгээгчийн ээлж — миль дээр суурилсан явц."""
    return await report_service.branch_shift_overview(db)


@router.get("/dashboards/fuel-trend")
async def fuel_trend(
    days: int = Query(default=7, ge=1, le=31),
    branch_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Салбар бүрийн сүүлийн хоногуудын түлшний зарлага — хошууны милээр."""
    return await report_service.fuel_mile_trend(db, days=days, branch_id=branch_id)


@router.get("/dashboards/owner", response_model=OwnerDashboardOut)
async def owner_dashboard(
    branch_id: uuid.UUID | None = Query(default=None, description="Зөвхөн энэ салбарын дүн"),
    db: AsyncSession = Depends(get_db),
    user: User = CanViewOwner,
) -> dict:
    """Эзний хяналтын самбар — өдөр/сар/жилийн дүн, ашиг, авлага өглөг."""
    return await report_service.owner_dashboard(db, branch_id)
