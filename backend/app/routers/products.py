"""Барааны каталог ба ангилал (WP7).

Жагсаалт унших нь нэвтэрсэн бүх хэрэглэгчид нээлттэй (POS-д хэрэгтэй),
өөрчлөх нь ``products.manage`` эрхтэй.  **Зарах үнийг энд засах боломжгүй** —
үнэ зөвхөн үнийн өөрчлөлтийн хүсэлтээр (``/api/price-changes``) солигдоно,
яг түлштэй адил дүрэм.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.product import Product, ProductCategory
from app.models.user import User
from app.money import q2, q3
from app.enums import ProductSaleMode
from app.schemas.product import (
    SALE_MODE_NAMES_MN,
    ProductCategoryCreate,
    ProductCategoryListOut,
    ProductCategoryOut,
    ProductCategoryUpdate,
    ProductCreate,
    ProductListOut,
    ProductOut,
    ProductUpdate,
)
from app.services import inventory_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["products"])

ZERO = Decimal("0")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _to_out(
    product: Product,
    category_name: str | None = None,
    *,
    stock_override: Decimal | None = None,
    price_override: Decimal | None = None,
    bulk_name: str | None = None,
    bulk_unit: str | None = None,
) -> ProductOut:
    # Салбарын горимд үлдэгдэл/үнэ нь тухайн салбарынхаар харагдана.
    stock = q3(stock_override if stock_override is not None else (product.stock_qty or ZERO))
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
        price=q2(price_override if price_override is not None else (product.price or ZERO)),
        avg_cost=avg_cost,
        stock_qty=stock,
        min_stock=min_stock,
        stock_value=q2(stock * avg_cost),
        is_low=stock <= min_stock,
        is_active=product.is_active,
        sale_mode=sale_mode,
        sale_mode_name=SALE_MODE_NAMES_MN.get(sale_mode, sale_mode),
        bulk_product_id=product.bulk_product_id,
        bulk_product_name=bulk_name,
        bulk_product_unit=bulk_unit,
        bulk_factor=bulk_factor,
        is_convertible=(
            sale_mode == str(ProductSaleMode.PIECE)
            and product.bulk_product_id is not None
            and bulk_factor > ZERO
        ),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _snapshot(product: Product) -> dict:
    return {
        "sku": product.sku,
        "barcode": product.barcode,
        "name_mn": product.name_mn,
        "category_id": str(product.category_id),
        "unit": product.unit,
        "price": str(product.price),
        "avg_cost": str(product.avg_cost),
        "stock_qty": str(product.stock_qty),
        "min_stock": str(product.min_stock),
        "is_active": product.is_active,
        "sale_mode": str(product.sale_mode),
        "bulk_product_id": (str(product.bulk_product_id) if product.bulk_product_id else None),
        "bulk_factor": str(product.bulk_factor),
    }


def _category_snapshot(category: ProductCategory) -> dict:
    return {
        "name_mn": category.name_mn,
        "icon": category.icon,
        "sort_order": category.sort_order,
    }


def _category_out(category: ProductCategory, product_count: int = 0) -> ProductCategoryOut:
    return ProductCategoryOut(
        id=category.id,
        name_mn=category.name_mn,
        icon=category.icon,
        sort_order=category.sort_order,
        product_count=product_count,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


async def _load_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.scalar(
        select(Product).options(selectinload(Product.category)).where(Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    return product


async def _bulk_names(
    db: AsyncSession, products: list[Product]
) -> dict[uuid.UUID, tuple[str, str]]:
    """Задлалтын зорилтын нэр, нэгж — нэг асуулгаар."""
    ids = {p.bulk_product_id for p in products if p.bulk_product_id is not None}
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(Product.id, Product.name_mn, Product.unit).where(Product.id.in_(ids))
        )
    ).all()
    return {pid: (name, unit) for pid, name, unit in rows}


async def _one_out(
    db: AsyncSession, product: Product, category_name: str | None = None
) -> ProductOut:
    names = await _bulk_names(db, [product])
    hit = names.get(product.bulk_product_id) if product.bulk_product_id else None
    return _to_out(
        product,
        category_name,
        bulk_name=hit[0] if hit else None,
        bulk_unit=hit[1] if hit else None,
    )


async def _check_bulk_link(
    db: AsyncSession,
    *,
    sale_mode: str,
    bulk_product_id: uuid.UUID | None,
    bulk_factor: Decimal,
    self_id: uuid.UUID | None,
) -> None:
    """Задлалтын холбоосыг шалгана.

    Грам бүтээгдэхүүн өөрөө дахин задрахгүй; задлалтын зорилт нь заавал грам
    бүтээгдэхүүн байх ёстой, эс бөгөөс кассын талбайд гарч ирэхгүй.
    """
    if bulk_product_id is None:
        return
    if sale_mode != str(ProductSaleMode.PIECE):
        raise HTTPException(
            status_code=422, detail="Зөвхөн ширхэг бараанд задлалтын бараа зааж болно"
        )
    if self_id is not None and bulk_product_id == self_id:
        raise HTTPException(status_code=422, detail="Бараа өөрөө рүүгээ задрахгүй")
    if bulk_factor <= ZERO:
        raise HTTPException(status_code=422, detail="1 ширхэгээс гарах хэмжээ 0-ээс их байх ёстой")

    target = await db.scalar(select(Product).where(Product.id == bulk_product_id))
    if target is None:
        raise HTTPException(status_code=404, detail="Задлалтын бараа олдсонгүй")
    if str(target.sale_mode) != str(ProductSaleMode.BULK):
        raise HTTPException(
            status_code=422, detail="Задлалтын бараа нь грам бүтээгдэхүүн байх ёстой"
        )


async def _load_category(db: AsyncSession, category_id: uuid.UUID) -> ProductCategory:
    category = await db.scalar(select(ProductCategory).where(ProductCategory.id == category_id))
    if category is None:
        raise HTTPException(status_code=404, detail="Ангилал олдсонгүй")
    return category


# --------------------------------------------------------------------------- #
# Ангилал
# --------------------------------------------------------------------------- #
@router.get("/product-categories", response_model=ProductCategoryListOut)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProductCategoryListOut:
    rows = (
        await db.execute(
            select(ProductCategory, func.count(Product.id))
            .outerjoin(Product, Product.category_id == ProductCategory.id)
            .group_by(ProductCategory.id)
            .order_by(ProductCategory.sort_order, ProductCategory.name_mn)
        )
    ).all()

    items = [_category_out(category, int(count or 0)) for category, count in rows]
    return ProductCategoryListOut(items=items, total=len(items))


@router.post("/product-categories", response_model=ProductCategoryOut, status_code=201)
async def create_category(
    payload: ProductCategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> ProductCategoryOut:
    name = payload.name_mn.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Ангиллын нэр хоосон байж болохгүй")

    clash = await db.scalar(
        select(func.count()).select_from(ProductCategory).where(ProductCategory.name_mn == name)
    )
    if clash:
        raise HTTPException(status_code=422, detail="Ийм нэртэй ангилал бүртгэгдсэн байна")

    category = ProductCategory(
        name_mn=name,
        icon=(payload.icon or "").strip() or None,
        sort_order=payload.sort_order,
    )
    db.add(category)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="product_category.create",
        entity_type="product_category",
        entity_id=category.id,
        after=_category_snapshot(category),
        ip=_client_ip(request),
    )
    return _category_out(category, 0)


@router.patch("/product-categories/{category_id}", response_model=ProductCategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: ProductCategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> ProductCategoryOut:
    category = await _load_category(db, category_id)
    changes = payload.model_dump(exclude_unset=True)
    before = _category_snapshot(category)

    if changes.get("name_mn") is not None:
        name = str(changes["name_mn"]).strip()
        if not name:
            raise HTTPException(status_code=422, detail="Ангиллын нэр хоосон байж болохгүй")
        if name != category.name_mn:
            clash = await db.scalar(
                select(func.count()).select_from(ProductCategory).where(ProductCategory.name_mn == name)
            )
            if clash:
                raise HTTPException(status_code=422, detail="Ийм нэртэй ангилал бүртгэгдсэн байна")
        changes["name_mn"] = name

    for field, value in changes.items():
        if field == "icon" or value is not None:
            setattr(category, field, value)
    await db.flush()

    count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.category_id == category.id)
    )

    await audit(
        db,
        user_id=user.id,
        action="product_category.update",
        entity_type="product_category",
        entity_id=category.id,
        before=before,
        after=_category_snapshot(category),
        ip=_client_ip(request),
    )
    return _category_out(category, int(count or 0))


@router.delete("/product-categories/{category_id}", status_code=204, response_model=None)
async def delete_category(
    category_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> None:
    category = await _load_category(db, category_id)

    used = await db.scalar(
        select(func.count()).select_from(Product).where(Product.category_id == category.id)
    )
    if used:
        raise HTTPException(status_code=422, detail="Бараатай ангиллыг устгах боломжгүй")

    before = _category_snapshot(category)
    await db.delete(category)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="product_category.delete",
        entity_type="product_category",
        entity_id=category_id,
        before=before,
        ip=_client_ip(request),
    )


# --------------------------------------------------------------------------- #
# Бараа — унших
# --------------------------------------------------------------------------- #
@router.get("/products", response_model=ProductListOut)
async def list_products(
    search: str | None = Query(default=None, description="Нэр / SKU / штрих код"),
    category_id: uuid.UUID | None = Query(default=None),
    branch_id: uuid.UUID | None = Query(
        default=None, description="Үлдэгдэл, үнийг энэ салбарынхаар харуулна (ПОС)"
    ),
    is_active: bool | None = Query(default=None),
    low_stock: bool = Query(default=False, description="Зөвхөн доод хязгаараас доош"),
    sale_mode: ProductSaleMode | None = Query(
        default=None, description="ширхэг (piece) эсвэл задлан (bulk)"
    ),
    convertible: bool = Query(default=False, description="Зөвхөн задлан хөрвүүлж болох бараа"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProductListOut:
    conditions = []
    if sale_mode is not None:
        conditions.append(Product.sale_mode == str(sale_mode))
    if convertible:
        conditions.append(Product.sale_mode == str(ProductSaleMode.PIECE))
        conditions.append(Product.bulk_product_id.is_not(None))
        conditions.append(Product.bulk_factor > 0)
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

    total = await db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
    products = (
        await db.scalars(
            select(Product)
            .options(selectinload(Product.category))
            .where(*conditions)
            .order_by(Product.name_mn)
            .limit(limit)
            .offset(offset)
        )
    ).all()

    bulk_names = await _bulk_names(db, list(products))

    def out(p: Product, **extra: Decimal | None) -> ProductOut:
        hit = bulk_names.get(p.bulk_product_id) if p.bulk_product_id else None
        return _to_out(
            p,
            bulk_name=hit[0] if hit else None,
            bulk_unit=hit[1] if hit else None,
            **extra,  # type: ignore[arg-type]
        )

    if branch_id is None:
        return ProductListOut(items=[out(p) for p in products], total=int(total))

    # Салбарын горим: үлдэгдэл + үнэ тухайн салбарынхаар.
    from app.models.product import ProductBranchStock
    from app.services.pricing_service import product_price_map

    ids = [p.id for p in products]
    stocks: dict[uuid.UUID, Decimal] = {}
    if ids:
        stock_rows = (
            await db.execute(
                select(ProductBranchStock.product_id, ProductBranchStock.qty).where(
                    ProductBranchStock.branch_id == branch_id,
                    ProductBranchStock.product_id.in_(ids),
                )
            )
        ).all()
        stocks = {pid: q3(qty or ZERO) for pid, qty in stock_rows}
    prices = await product_price_map(db, branch_id)

    return ProductListOut(
        items=[
            out(p, stock_override=stocks.get(p.id, Decimal("0")), price_override=prices.get(p.id))
            for p in products
        ],
        total=int(total),
    )


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProductOut:
    return await _one_out(db, await _load_product(db, product_id))


# --------------------------------------------------------------------------- #
# Бараа — бичих
# --------------------------------------------------------------------------- #
@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> ProductOut:
    category = await _load_category(db, payload.category_id)

    sku = payload.sku.strip()
    if not sku:
        raise HTTPException(status_code=422, detail="SKU хоосон байж болохгүй")
    clash = await db.scalar(select(func.count()).select_from(Product).where(Product.sku == sku))
    if clash:
        raise HTTPException(status_code=422, detail="Ийм SKU-тай бараа бүртгэгдсэн байна")

    barcode = (payload.barcode or "").strip() or None
    if barcode:
        used = await db.scalar(select(func.count()).select_from(Product).where(Product.barcode == barcode))
        if used:
            raise HTTPException(status_code=422, detail="Ийм штрих кодтой бараа бүртгэгдсэн байна")

    sale_mode = str(payload.sale_mode)
    bulk_factor = q3(payload.bulk_factor)
    await _check_bulk_link(
        db,
        sale_mode=sale_mode,
        bulk_product_id=payload.bulk_product_id,
        bulk_factor=bulk_factor,
        self_id=None,
    )

    product = Product(
        sku=sku,
        barcode=barcode,
        name_mn=payload.name_mn.strip(),
        category_id=category.id,
        unit=payload.unit.strip() or "ш",
        price=q2(payload.price),
        avg_cost=Decimal("0"),
        stock_qty=Decimal("0"),
        min_stock=q3(payload.min_stock),
        is_active=payload.is_active,
        sale_mode=sale_mode,
        bulk_product_id=payload.bulk_product_id,
        bulk_factor=bulk_factor if payload.bulk_product_id is not None else Decimal("0"),
    )
    product.category = category
    db.add(product)
    await db.flush()

    # Эхний үлдэгдлийг жинхэнэ нөөцийн хөдөлгөөнөөр оруулна — ингэснээр
    # дэвтэр ба үлдэгдэл эхнээсээ таарна.
    opening = q3(payload.opening_qty)
    if opening > 0:
        from app.services.branch_service import resolve_branch_id

        await inventory_service.receive_product(
            db,
            product,
            opening,
            payload.opening_cost,
            ref_type="opening_balance",
            ref_id=product.id,
            branch_id=await resolve_branch_id(db, user),
        )
        await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="product.create",
        entity_type="product",
        entity_id=product.id,
        after=_snapshot(product),
        ip=_client_ip(request),
    )
    return await _one_out(db, product, category.name_mn)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> ProductOut:
    product = await _load_product(db, product_id)
    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(product)

    # Үнэ бол батлах урсгалын өмч — энэ endpoint хэзээ ч хөдөлгөхгүй.
    if "price" in changes:
        new_price = changes.pop("price")
        if new_price is not None and q2(new_price) != q2(product.price or ZERO):
            raise HTTPException(
                status_code=422,
                detail="Үнийг зөвхөн үнийн өөрчлөлтийн хүсэлтээр солино",
            )

    category: ProductCategory | None = None
    if changes.get("category_id") is not None and changes["category_id"] != product.category_id:
        category = await _load_category(db, changes["category_id"])

    if changes.get("sku") is not None:
        sku = str(changes["sku"]).strip()
        if not sku:
            raise HTTPException(status_code=422, detail="SKU хоосон байж болохгүй")
        if sku != product.sku:
            clash = await db.scalar(select(func.count()).select_from(Product).where(Product.sku == sku))
            if clash:
                raise HTTPException(status_code=422, detail="Ийм SKU-тай бараа бүртгэгдсэн байна")
        changes["sku"] = sku

    if "barcode" in changes:
        barcode = (changes["barcode"] or "").strip() or None
        if barcode and barcode != product.barcode:
            used = await db.scalar(
                select(func.count()).select_from(Product).where(Product.barcode == barcode)
            )
            if used:
                raise HTTPException(status_code=422, detail="Ийм штрих кодтой бараа бүртгэгдсэн байна")
        changes["barcode"] = barcode

    if changes.get("name_mn") is not None:
        changes["name_mn"] = str(changes["name_mn"]).strip()
    if changes.get("unit") is not None:
        changes["unit"] = str(changes["unit"]).strip() or "ш"
    if changes.get("min_stock") is not None:
        changes["min_stock"] = q3(changes["min_stock"])

    # Задлалтын холбоос — гурван талбар хоорондоо тохирсон эсэхийг цуг шалгана.
    sale_mode = str(changes.get("sale_mode") or product.sale_mode)
    if "bulk_product_id" in changes:
        bulk_product_id = changes["bulk_product_id"]
    else:
        bulk_product_id = product.bulk_product_id
    bulk_factor = q3(
        changes["bulk_factor"] if changes.get("bulk_factor") is not None else (product.bulk_factor or ZERO)
    )
    if sale_mode == str(ProductSaleMode.BULK):
        # Грам бүтээгдэхүүн өөрөө задрахгүй — холбоосыг цэвэрлэнэ.
        bulk_product_id = None
        bulk_factor = Decimal("0")
    await _check_bulk_link(
        db,
        sale_mode=sale_mode,
        bulk_product_id=bulk_product_id,
        bulk_factor=bulk_factor,
        self_id=product.id,
    )
    changes.pop("sale_mode", None)
    changes.pop("bulk_product_id", None)
    changes.pop("bulk_factor", None)
    product.sale_mode = sale_mode
    product.bulk_product_id = bulk_product_id
    product.bulk_factor = bulk_factor if bulk_product_id is not None else Decimal("0")

    for field, value in changes.items():
        if field == "barcode" or value is not None:
            setattr(product, field, value)
    if category is not None:
        product.category = category
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="product.update",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after=_snapshot(product),
        ip=_client_ip(request),
    )
    return await _one_out(db, product)


@router.delete("/products/{product_id}", status_code=204, response_model=None)
async def deactivate_product(
    product_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("products.manage")),
) -> None:
    """Бараа хэзээ ч бодитоор устгагдахгүй — нөөц, борлуулалтын түүх бүрэн
    үлдэх ёстой тул зөвхөн идэвхгүй болгоно."""
    product = await _load_product(db, product_id)

    before = _snapshot(product)
    product.is_active = False
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="product.deactivate",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after=_snapshot(product),
        ip=_client_ip(request),
    )
