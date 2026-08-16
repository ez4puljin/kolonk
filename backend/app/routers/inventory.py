"""Барааны нөөц: үлдэгдэл, хөдөлгөөний дэвтэр, гар тохируулга (WP7).

Үлдэгдэл харах нь ``products.view`` эрхтэй бүх хэрэглэгчид нээлттэй, харин
тохируулга хийх нь ``inventory.manage`` эрх шаардана — нөөцийн тоо хэмжээ
шууд мөнгө учраас.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.deps import require_permission
from app.enums import InventoryTxType, ProductSaleMode
from app.models.branch import Branch
from app.models.product import (
    InventoryTransaction,
    Product,
    ProductBranchStock,
    ProductCategory,
)
from app.models.user import User
from app.money import q2, q3
from app.schemas.product import (
    INVENTORY_TX_NAMES_MN,
    SALE_MODE_NAMES_MN,
    BranchQty,
    BulkConversionIn,
    BulkConversionOut,
    InventoryAdjustmentIn,
    InventoryAdjustmentOut,
    InventoryListOut,
    InventoryRow,
    InventoryTotals,
    InventoryTxListOut,
    InventoryTxOut,
    ProductOut,
)
from app.services import inventory_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["inventory"])

ZERO = Decimal("0")

try:
    STATION_TZ = ZoneInfo(settings.tz)
except Exception:  # noqa: BLE001 — dev машинд tzdata байхгүй байж болно
    STATION_TZ = timezone(timedelta(hours=8))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=STATION_TZ)


def _product_out(product: Product, category_name: str | None = None) -> ProductOut:
    stock = q3(product.stock_qty or ZERO)
    avg_cost = Decimal(product.avg_cost or ZERO)
    min_stock = q3(product.min_stock or ZERO)
    if category_name is None:
        category = product.category
        category_name = category.name_mn if category is not None else None
    sale_mode = str(product.sale_mode or ProductSaleMode.PIECE)
    bulk_factor = q3(product.bulk_factor or ZERO)
    return ProductOut(
        id=product.id,
        sku=product.sku,
        barcode=product.barcode,
        name_mn=product.name_mn,
        category_id=product.category_id,
        category_name=category_name,
        unit=product.unit,
        price=q2(product.price or ZERO),
        avg_cost=avg_cost,
        stock_qty=stock,
        min_stock=min_stock,
        stock_value=q2(stock * avg_cost),
        is_low=stock <= min_stock,
        is_active=product.is_active,
        sale_mode=sale_mode,
        sale_mode_name=SALE_MODE_NAMES_MN.get(sale_mode, sale_mode),
        bulk_product_id=product.bulk_product_id,
        bulk_factor=bulk_factor,
        is_convertible=(
            sale_mode == str(ProductSaleMode.PIECE)
            and product.bulk_product_id is not None
            and bulk_factor > ZERO
        ),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _tx_out(tx: InventoryTransaction, product: Product | None = None) -> InventoryTxOut:
    product = product if product is not None else tx.product
    qty = q3(tx.qty or ZERO)
    unit_cost = Decimal(tx.unit_cost or ZERO)
    return InventoryTxOut(
        id=tx.id,
        product_id=tx.product_id,
        product_name=product.name_mn if product is not None else None,
        sku=product.sku if product is not None else None,
        unit=product.unit if product is not None else None,
        tx_type=tx.tx_type,
        tx_type_name=INVENTORY_TX_NAMES_MN.get(str(tx.tx_type), str(tx.tx_type)),
        qty=qty,
        unit_cost=unit_cost,
        balance_after=q3(tx.balance_after or ZERO),
        amount=q2(qty * unit_cost),
        ref_type=tx.ref_type,
        ref_id=tx.ref_id,
        note=tx.note,
        created_at=tx.created_at,
    )


# --------------------------------------------------------------------------- #
# Үлдэгдэл
# --------------------------------------------------------------------------- #
@router.get("/inventory", response_model=InventoryListOut)
async def inventory_snapshot(
    search: str | None = Query(default=None, description="Нэр / SKU / штрих код"),
    category_id: uuid.UUID | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(default=None, description="Зөвхөн энэ салбарын үлдэгдэл"),
    is_active: bool | None = Query(default=None),
    low_stock: bool = Query(default=False, description="Зөвхөн доод хязгаараас доош"),
    sale_mode: ProductSaleMode | None = Query(
        default=None, description="ширхэг (piece) эсвэл задлан (bulk)"
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("products.view", "inventory.manage")),
) -> InventoryListOut:
    conditions = []
    if sale_mode is not None:
        conditions.append(Product.sale_mode == str(sale_mode))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Product.name_mn.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.barcode.ilike(pattern),
            )
        )
    if category_id is not None:
        conditions.append(Product.category_id == category_id)
    if is_active is not None:
        conditions.append(Product.is_active.is_(is_active))
    if low_stock:
        conditions.append(Product.stock_qty <= Product.min_stock)

    rows = (
        await db.execute(
            select(Product, ProductCategory.name_mn)
            .join(ProductCategory, ProductCategory.id == Product.category_id)
            .where(*conditions)
            .order_by(Product.name_mn)
            .limit(limit)
            .offset(offset)
        )
    ).all()

    # Салбар тус бүрийн задаргаа — нэг асуулгаар бүх барааных.
    product_ids = [product.id for product, _ in rows]
    branch_rows: dict[uuid.UUID, list[BranchQty]] = {}
    branch_qty: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
    if product_ids:
        stock_rows = (
            await db.execute(
                select(ProductBranchStock.product_id, ProductBranchStock.branch_id, Branch.name, ProductBranchStock.qty)
                .join(Branch, Branch.id == ProductBranchStock.branch_id)
                .where(ProductBranchStock.product_id.in_(product_ids))
                .order_by(Branch.sort_order, Branch.name)
            )
        ).all()
        for pid, bid, branch_name, qty in stock_rows:
            branch_rows.setdefault(pid, []).append(
                BranchQty(branch_id=bid, branch_name=branch_name, qty=q3(qty or ZERO))
            )
            branch_qty[(pid, bid)] = q3(qty or ZERO)

    items: list[InventoryRow] = []
    for product, category_name in rows:
        # Салбар сонгосон бол тухайн салбарын үлдэгдэл, үгүй бол нийт.
        if branch_id is not None:
            stock = branch_qty.get((product.id, branch_id), Decimal("0"))
        else:
            stock = q3(product.stock_qty or ZERO)
        avg_cost = Decimal(product.avg_cost or ZERO)
        min_stock = q3(product.min_stock or ZERO)
        row_mode = str(product.sale_mode or ProductSaleMode.PIECE)
        items.append(
            InventoryRow(
                product_id=product.id,
                sku=product.sku,
                name_mn=product.name_mn,
                category_id=product.category_id,
                category_name=category_name,
                unit=product.unit,
                price=q2(product.price or ZERO),
                stock_qty=stock,
                avg_cost=avg_cost,
                value=q2(stock * avg_cost),
                min_stock=min_stock,
                is_low=stock <= min_stock,
                is_active=product.is_active,
                sale_mode=row_mode,
                sale_mode_name=SALE_MODE_NAMES_MN.get(row_mode, row_mode),
                branches=branch_rows.get(product.id, []),
            )
        )

    aggregate = (
        await db.execute(
            select(
                func.count(Product.id),
                func.coalesce(func.sum(Product.stock_qty), 0),
                func.coalesce(func.sum(Product.stock_qty * Product.avg_cost), 0),
            ).where(*conditions)
        )
    ).one()
    low_count = await db.scalar(
        select(func.count())
        .select_from(Product)
        .where(*conditions, Product.stock_qty <= Product.min_stock)
    )

    if branch_id is not None:
        # Салбарын горимд нийлбэрүүдийг харагдаж буй мөрүүдээс бодно.
        totals = InventoryTotals(
            product_count=int(aggregate[0] or 0),
            low_count=sum(1 for row in items if row.is_low),
            total_qty=q3(sum((row.stock_qty for row in items), Decimal("0"))),
            total_value=q2(sum((row.value for row in items), Decimal("0"))),
        )
    else:
        totals = InventoryTotals(
            product_count=int(aggregate[0] or 0),
            low_count=int(low_count or 0),
            total_qty=q3(Decimal(aggregate[1] or 0)),
            total_value=q2(Decimal(aggregate[2] or 0)),
        )
    return InventoryListOut(items=items, total=totals.product_count, totals=totals)


# --------------------------------------------------------------------------- #
# Хөдөлгөөний дэвтэр
# --------------------------------------------------------------------------- #
@router.get("/inventory/transactions", response_model=InventoryTxListOut)
async def list_transactions(
    product_id: uuid.UUID | None = Query(default=None),
    tx_type: InventoryTxType | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("products.view", "inventory.manage")),
) -> InventoryTxListOut:
    conditions = []
    if product_id is not None:
        conditions.append(InventoryTransaction.product_id == product_id)
    if tx_type is not None:
        conditions.append(InventoryTransaction.tx_type == str(tx_type))
    if date_from is not None:
        conditions.append(InventoryTransaction.created_at >= _day_start(date_from))
    if date_to is not None:
        conditions.append(InventoryTransaction.created_at < _day_start(date_to) + timedelta(days=1))

    total = (
        await db.scalar(select(func.count()).select_from(InventoryTransaction).where(*conditions)) or 0
    )
    rows = (
        await db.execute(
            select(InventoryTransaction, Product)
            .join(Product, Product.id == InventoryTransaction.product_id)
            .where(*conditions)
            .order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return InventoryTxListOut(
        items=[_tx_out(tx, product) for tx, product in rows],
        total=int(total),
    )


# --------------------------------------------------------------------------- #
# Гар тохируулга
# --------------------------------------------------------------------------- #
@router.post("/inventory/adjustments", response_model=InventoryAdjustmentOut, status_code=201)
async def create_adjustment(
    payload: InventoryAdjustmentIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("inventory.manage")),
) -> InventoryAdjustmentOut:
    """Тооллогын зөрүү, гэмтэл, хугацаа дууссан барааг нөөцөөс тохируулна.

    ``qty`` тэмдэгтэй: + илүүдэл, − хорогдол.  Дундаж өртөг хөдлөхгүй.
    """
    product = await db.scalar(
        select(Product).options(selectinload(Product.category)).where(Product.id == payload.product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")

    qty = q3(payload.qty)
    if qty == 0:
        raise HTTPException(status_code=422, detail="Тохируулгын хэмжээ 0 байж болохгүй")

    before = {
        "stock_qty": str(product.stock_qty),
        "avg_cost": str(product.avg_cost),
    }
    note = (payload.note or "").strip() or None

    from app.services.branch_service import resolve_branch_id

    branch_id = await resolve_branch_id(db, user, payload.branch_id)
    tx = await inventory_service.adjust_product(
        db,
        product,
        qty,
        note=note,
        ref_type="manual_adjustment",
        ref_id=product.id,
        branch_id=branch_id,
    )
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="inventory.adjust",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after={
            "stock_qty": str(product.stock_qty),
            "avg_cost": str(product.avg_cost),
            "adjustment_qty": str(qty),
            "note": note,
        },
        ip=_client_ip(request),
    )

    return InventoryAdjustmentOut(product=_product_out(product), transaction=_tx_out(tx, product))


# --------------------------------------------------------------------------- #
# Задлан хөрвүүлэлт (ширхэг → грам)
# --------------------------------------------------------------------------- #
@router.post("/inventory/conversions", response_model=BulkConversionOut, status_code=201)
async def create_conversion(
    payload: BulkConversionIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("inventory.convert", "inventory.manage")),
) -> BulkConversionOut:
    """Ширхэг барааг задалж грам бүтээгдэхүүн рүү шилжүүлнэ.

    Жишээ: «5W-30 5л» савнаас 1 ширхэг задлахад «5W-30 задлан» бүртгэлд
    5.000 л нэмэгдэж, талбай дээр литр/дүнгээр зарагдана.  Ерөнхий дэвтэр
    хөдлөхгүй (хоёр бараа хоёулаа 1302) — зөвхөн нөөцийн дэвтэрт бичигдэнэ.
    """
    source = await db.scalar(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == payload.product_id)
        .with_for_update()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    if str(source.sale_mode) != str(ProductSaleMode.PIECE):
        raise HTTPException(status_code=422, detail="Зөвхөн ширхэг барааг задална")
    if source.bulk_product_id is None or q3(source.bulk_factor or ZERO) <= ZERO:
        raise HTTPException(
            status_code=422, detail="Энэ бараанд задлалтын тохиргоо хийгээгүй байна"
        )

    target = await db.scalar(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == source.bulk_product_id)
        .with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Задлалтын бараа олдсонгүй")
    if not target.is_active:
        raise HTTPException(status_code=422, detail="Задлалтын бараа идэвхгүй байна")

    qty = q3(payload.qty)
    factor = q3(source.bulk_factor or ZERO)
    out_qty = q3(qty * factor)
    note = (payload.note or "").strip() or None

    before = {
        "source_stock": str(source.stock_qty),
        "target_stock": str(target.stock_qty),
        "target_avg_cost": str(target.avg_cost),
    }

    from app.services.branch_service import resolve_branch_id

    branch_id = await resolve_branch_id(db, user, payload.branch_id)
    cost = q2(qty * Decimal(source.avg_cost or ZERO))
    tx_out, tx_in = await inventory_service.convert_to_bulk(
        db,
        source,
        target,
        qty,
        out_qty,
        ref_id=source.id,
        note=note,
        branch_id=branch_id,
    )
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="inventory.convert",
        entity_type="product",
        entity_id=source.id,
        before=before,
        after={
            "source_stock": str(source.stock_qty),
            "target_id": str(target.id),
            "target_stock": str(target.stock_qty),
            "target_avg_cost": str(target.avg_cost),
            "qty": str(qty),
            "out_qty": str(out_qty),
            "cost": str(cost),
            "note": note,
        },
        ip=_client_ip(request),
    )

    return BulkConversionOut(
        source=_product_out(source),
        target=_product_out(target),
        qty=qty,
        out_qty=out_qty,
        cost=cost,
        out_transaction=_tx_out(tx_out, source),
        in_transaction=_tx_out(tx_in, target),
    )
