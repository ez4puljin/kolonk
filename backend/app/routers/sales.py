"""Борлуулалтын API (WP6).

``POST /api/sales`` бол системийн гол цэг: олон төлбөрийн хэрэгсэл, насосны
таталтын баталгаажуулалт, нөөцийн хасалт, журналын бичилт, И-баримтын дараалал
бүгд нэг транзакцад хийгдэнэ.

Энгийн түгээгч зөвхөн **өөрийн одоогийн ээлжийн** борлуулалтыг хардаг;
``sales.view_all`` эрхтэй хүн бүгдийг хардаг.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission, user_permissions
from app.enums import PaymentMethod
from app.models.user import User
from app.schemas.sale import ReceiptOut, SaleCreate, SaleCreatedOut, SaleListOut, SaleOut
from app.services import sale_service, shift_service

router = APIRouter(prefix="/api", tags=["sales"])

CanCreate = Depends(require_permission("sales.create"))
CanView = Depends(require_permission("sales.view", "sales.view_all"))


def _sees_all(user: User) -> bool:
    return "sales.view_all" in user_permissions(user)


@router.post("/sales", response_model=SaleCreatedOut, status_code=201)
async def create_sale(
    payload: SaleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = CanCreate,
) -> SaleCreatedOut:
    # Тохиргоонд ПОС унтраалттай бол кассын борлуулалт хаалттай — түгээгчийн
    # горимд бүх борлуулалт өдрийн хаалтаар (attendant_service) бүртгэгдэнэ.
    # Тэр урсгал sale_service.create_sale-ийг дотроос нь дууддаг тул шалгалт
    # зөвхөн энэ гадаад цэгт байна.
    if await shift_service.attendant_mode(db):
        raise HTTPException(
            status_code=409,
            detail="Тохиргоонд ПОС борлуулалт унтраалттай байна. Өдрийн хаалтаар бүртгэнэ үү",
        )
    sale = await sale_service.create_sale(db, user, payload)
    detail = await sale_service.sale_detail(db, sale)
    receipt = await sale_service.receipt_payload(db, sale)
    return SaleCreatedOut(sale=SaleOut(**detail), receipt=ReceiptOut(**receipt))


@router.get("/sales", response_model=SaleListOut)
async def list_sales(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    shift_id: uuid.UUID | None = Query(default=None),
    method: PaymentMethod | None = Query(default=None),
    customer_id: uuid.UUID | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None, description="Зөвхөн энэ салбарын борлуулалт"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> SaleListOut:
    cashier_id: uuid.UUID | None = None
    if not _sees_all(user):
        # Түгээгч зөвхөн өөрийн одоогийн нээлттэй ээлжийн борлуулалтыг хардаг.
        cashier_id = user.id
        if shift_id is None:
            shift = await sale_service.get_open_shift(db, user)
            if shift is None:
                return SaleListOut(items=[], total=0)
            shift_id = shift.id
    elif branch_id is None and getattr(user, "branch_id", None) is not None:
        # Салбартай хэрэглэгч (жишээ нь салбарын менежер) зөвхөн өөрийн салбарыг.
        branch_id = user.branch_id

    result = await sale_service.list_sales(
        db,
        date_from=date_from,
        date_to=date_to,
        shift_id=shift_id,
        method=str(method) if method else None,
        customer_id=customer_id,
        cashier_id=cashier_id,
        branch_id=branch_id,
        limit=limit,
        offset=offset,
    )
    return SaleListOut(**result)


@router.get("/sales/{sale_id}", response_model=SaleOut)
async def get_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> SaleOut:
    sale = await sale_service.get_sale(db, sale_id)
    if not _sees_all(user) and sale.cashier_id != user.id:
        raise HTTPException(status_code=403, detail="Танд бусдын борлуулалт харах эрх байхгүй байна")
    return SaleOut(**await sale_service.sale_detail(db, sale))


@router.get("/sales/{sale_id}/receipt", response_model=ReceiptOut)
async def get_receipt(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = CanView,
) -> ReceiptOut:
    sale = await sale_service.get_sale(db, sale_id)
    if not _sees_all(user) and sale.cashier_id != user.id:
        raise HTTPException(status_code=403, detail="Танд бусдын борлуулалт харах эрх байхгүй байна")
    return ReceiptOut(**await sale_service.receipt_payload(db, sale))
