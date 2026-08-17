"""Бараа материалын тайлан /өртгөөр/ — шүүлт, тайлан, Excel.

Шүүлтийн сонголтуудыг `/api/inventory-report/options`-оос авч цонхыг дүүргэнэ.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.models.branch import Branch
from app.models.fuel import Fuel, Tank
from app.models.product import Product, ProductCategory
from app.models.user import User
from app.schemas.inventory_report import InventoryFilterOptions, InventoryReportOut
from app.services import excel_service, inventory_report_service as svc

router = APIRouter(prefix="/api", tags=["inventory-report"])

CanView = Depends(require_permission("reports.view"))


@router.get("/inventory-report/options", response_model=InventoryFilterOptions)
async def filter_options(
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    """Шүүлтийн цонхны бүх сонголт — нэг дуудлагаар."""
    tanks = (await db.scalars(select(Tank).order_by(Tank.name))).all()
    fuels = (await db.scalars(select(Fuel).order_by(Fuel.sort_order))).all()
    categories = (
        await db.scalars(select(ProductCategory).order_by(ProductCategory.sort_order))
    ).all()
    products = (await db.scalars(select(Product).order_by(Product.name_mn))).all()
    branches = (
        await db.scalars(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.name))
    ).all()

    return {
        "accounts": [
            {"code": code, "name": name} for code, name in svc.ACCOUNT_NAMES.items()
        ],
        "branches": [{"id": str(b.id), "code": b.code, "name": b.name} for b in branches],
        "locations": [
            {"id": str(t.id), "code": t.name, "name": t.name, "account_code": svc.ACC.INV_FUEL}
            for t in tanks
        ],
        "fuels": [{"id": str(f.id), "code": f.code, "name": f.name_mn} for f in fuels],
        "categories": [{"id": str(c.id), "name": c.name_mn} for c in categories],
        "products": [
            {"id": str(p.id), "code": p.sku, "name": p.name_mn, "category_id": str(p.category_id) if p.category_id else None}
            for p in products
        ],
        "group_by": [{"code": k, "name": v} for k, v in svc.GROUP_BY_LABELS.items()],
        "tx_types": [{"code": k, "name": v} for k, v in svc.TX_TYPE_LABELS.items()],
    }


def _params(
    date_from: date = Query(...),
    date_to: date = Query(...),
    account_code: str | None = Query(default=None),
    tank_id: uuid.UUID | None = Query(default=None),
    fuel_id: uuid.UUID | None = Query(default=None),
    product_id: uuid.UUID | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None),
    group_by: str = Query(default="account_location_item"),
    tx_type: str = Query(default="all"),
    note_search: str | None = Query(default=None),
    include_details: bool = Query(default=False),
    skip_empty: bool = Query(default=True),
) -> dict:
    return {
        "date_from": date_from,
        "date_to": date_to,
        "account_code": account_code or None,
        "tank_id": tank_id,
        "fuel_id": fuel_id,
        "product_id": product_id,
        "category_id": category_id,
        "branch_id": branch_id,
        "group_by": group_by,
        "tx_type": tx_type,
        "note_search": note_search,
        "include_details": include_details,
        "skip_empty": skip_empty,
    }


@router.get("/inventory-report", response_model=InventoryReportOut)
async def inventory_report(
    params: dict = Depends(_params),
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    return await svc.inventory_movement_report(db, **params)


@router.get("/inventory-report.xlsx")
async def inventory_report_xlsx(
    params: dict = Depends(_params),
    db: AsyncSession = Depends(get_db),
    _: User = CanView,
):
    data = await svc.inventory_movement_report(db, **params)
    content = excel_service.inventory_movement_xlsx(data)
    name = f"Бараа_материал_{params['date_from']}_{params['date_to']}.xlsx"
    return excel_service.xlsx_response(content, name)
