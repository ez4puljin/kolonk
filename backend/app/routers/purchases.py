"""Дэлгүүрийн барааны худалдан авалт (WP7).

Шатахууны таталттай яг ижил урсгал: ноорог → бүртгэх.  Бүртгэсэн үед бараа
бүр хөдлөх дундаж өртгөөр нөөцөд орж, нийлүүлэгчийн өглөг нээгдэж,
``PURCHASE_POSTED`` журналын бичилт хийгдэнэ (``receipt_service``).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.deps import require_permission
from app.enums import DocStatus
from app.models.partner import Supplier
from app.models.procurement import Purchase, PurchaseItem
from app.models.product import Product
from app.models.user import User
from app.money import q2, q3, q6
from app.schemas.procurement import (
    DOC_STATUS_NAMES_MN,
    PurchaseCreate,
    PurchaseItemIn,
    PurchaseItemOut,
    PurchaseListOut,
    PurchaseOut,
    PurchaseUpdate,
)
from app.services import receipt_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["purchases"])

ZERO = Decimal("0")

VAT_RATE: Decimal = settings.vat_rate


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _number(purchase: Purchase) -> int | None:
    try:
        return purchase.number
    except Exception:  # noqa: BLE001
        return None


async def _ensure_number(db: AsyncSession, purchase: Purchase) -> None:
    if _number(purchase) is None:
        try:
            await db.refresh(purchase, ["number"])
        except Exception:  # noqa: BLE001
            pass


def _item_out(item: PurchaseItem, product: Product | None = None) -> PurchaseItemOut:
    product = product if product is not None else item.product
    return PurchaseItemOut(
        id=item.id,
        product_id=item.product_id,
        product_name=product.name_mn if product is not None else None,
        sku=product.sku if product is not None else None,
        unit=product.unit if product is not None else None,
        qty=q3(item.qty or ZERO),
        unit_cost=Decimal(item.unit_cost or ZERO),
        amount=q2(item.amount or ZERO),
    )


def _to_out(
    purchase: Purchase,
    supplier_name: str | None = None,
    products: dict[uuid.UUID, Product] | None = None,
) -> PurchaseOut:
    products = products or {}
    return PurchaseOut(
        id=purchase.id,
        number=_number(purchase),
        supplier_id=purchase.supplier_id,
        supplier_name=supplier_name,
        branch_id=purchase.branch_id,
        purchase_date=purchase.purchase_date,
        invoice_no=purchase.invoice_no,
        subtotal=q2(purchase.subtotal or ZERO),
        vat_amount=q2(purchase.vat_amount or ZERO),
        total_gross=q2(purchase.total_gross or ZERO),
        status=purchase.status,
        status_name=DOC_STATUS_NAMES_MN.get(str(purchase.status), str(purchase.status)),
        posted_by=purchase.posted_by,
        posted_at=purchase.posted_at,
        ap_invoice_id=purchase.ap_invoice_id,
        note=purchase.note,
        items=[_item_out(item, products.get(item.product_id)) for item in (purchase.items or [])],
        created_at=purchase.created_at,
        updated_at=purchase.updated_at,
    )


def _snapshot(purchase: Purchase) -> dict:
    return {
        "supplier_id": str(purchase.supplier_id),
        "purchase_date": purchase.purchase_date.isoformat(),
        "invoice_no": purchase.invoice_no,
        "subtotal": str(purchase.subtotal),
        "vat_amount": str(purchase.vat_amount),
        "total_gross": str(purchase.total_gross),
        "item_count": len(purchase.items or []),
        "status": str(purchase.status),
    }


def _recalculate(purchase: Purchase) -> None:
    subtotal = ZERO
    for item in purchase.items or []:
        item.amount = q2(q3(item.qty or ZERO) * q6(item.unit_cost or ZERO))
        subtotal = q2(subtotal + item.amount)
    purchase.subtotal = subtotal
    purchase.vat_amount = q2(subtotal * VAT_RATE)
    purchase.total_gross = q2(subtotal + purchase.vat_amount)


def _base_query():
    return (
        select(Purchase, Supplier.name)
        .join(Supplier, Supplier.id == Purchase.supplier_id)
        .options(selectinload(Purchase.items).selectinload(PurchaseItem.product))
    )


async def _load_row(db: AsyncSession, purchase_id: uuid.UUID) -> Row:
    row = (await db.execute(_base_query().where(Purchase.id == purchase_id))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Худалдан авалт олдсонгүй")
    return row


async def _load_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    supplier = await db.scalar(select(Supplier).where(Supplier.id == supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")
    return supplier


async def _load_products(db: AsyncSession, items: list[PurchaseItemIn]) -> dict[uuid.UUID, Product]:
    ids = {item.product_id for item in items}
    products = {p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(ids)))).all()}
    if ids - set(products):
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    return products


def _build_items(
    payload_items: list[PurchaseItemIn],
    products: dict[uuid.UUID, Product],
) -> list[PurchaseItem]:
    rows: list[PurchaseItem] = []
    for entry in payload_items:
        qty = q3(entry.qty)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Барааны тоо хэмжээ 0-ээс их байх ёстой")
        unit_cost = q6(entry.unit_cost)
        if unit_cost < 0:
            raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")
        item = PurchaseItem(
            product_id=entry.product_id,
            qty=qty,
            unit_cost=unit_cost,
            amount=q2(qty * unit_cost),
        )
        item.product = products[entry.product_id]
        rows.append(item)
    return rows


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
@router.get("/purchases", response_model=PurchaseListOut)
async def list_purchases(
    status: DocStatus | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("purchases.manage")),
) -> PurchaseListOut:
    conditions = []
    if status is not None:
        conditions.append(Purchase.status == str(status))
    if supplier_id is not None:
        conditions.append(Purchase.supplier_id == supplier_id)
    if date_from is not None:
        conditions.append(Purchase.purchase_date >= date_from)
    if date_to is not None:
        conditions.append(Purchase.purchase_date <= date_to)

    total = await db.scalar(select(func.count()).select_from(Purchase).where(*conditions)) or 0
    rows = (
        await db.execute(
            _base_query()
            .where(*conditions)
            .order_by(Purchase.purchase_date.desc(), Purchase.number.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return PurchaseListOut(
        items=[_to_out(purchase, supplier_name) for purchase, supplier_name in rows],
        total=int(total),
    )


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("purchases.manage")),
) -> PurchaseOut:
    purchase, supplier_name = await _load_row(db, purchase_id)
    return _to_out(purchase, supplier_name)


# --------------------------------------------------------------------------- #
# Бичих
# --------------------------------------------------------------------------- #
@router.post("/purchases", response_model=PurchaseOut, status_code=201)
async def create_purchase(
    payload: PurchaseCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("purchases.manage")),
) -> PurchaseOut:
    supplier = await _load_supplier(db, payload.supplier_id)
    products = await _load_products(db, payload.items)

    purchase = Purchase(
        supplier_id=supplier.id,
        branch_id=payload.branch_id,
        purchase_date=payload.purchase_date or date.today(),
        invoice_no=(payload.invoice_no or "").strip() or None,
        status=str(DocStatus.DRAFT),
        note=(payload.note or "").strip() or None,
    )
    purchase.items = _build_items(payload.items, products)
    _recalculate(purchase)

    db.add(purchase)
    await db.flush()
    await _ensure_number(db, purchase)

    await audit(
        db,
        user_id=user.id,
        action="purchase.create",
        entity_type="purchase",
        entity_id=purchase.id,
        after=_snapshot(purchase),
        ip=_client_ip(request),
    )
    return _to_out(purchase, supplier.name, products)


@router.patch("/purchases/{purchase_id}", response_model=PurchaseOut)
async def update_purchase(
    purchase_id: uuid.UUID,
    payload: PurchaseUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("purchases.manage")),
) -> PurchaseOut:
    purchase, supplier_name = await _load_row(db, purchase_id)
    if str(purchase.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Бүртгэсэн баримтыг засах боломжгүй")

    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(purchase)
    products: dict[uuid.UUID, Product] = {}

    if changes.get("supplier_id") is not None and changes["supplier_id"] != purchase.supplier_id:
        supplier = await _load_supplier(db, changes["supplier_id"])
        purchase.supplier_id = supplier.id
        supplier_name = supplier.name

    if changes.get("purchase_date") is not None:
        purchase.purchase_date = changes["purchase_date"]
    if "invoice_no" in changes:
        purchase.invoice_no = (changes["invoice_no"] or "").strip() or None
    if "note" in changes:
        purchase.note = (changes["note"] or "").strip() or None

    if payload.items is not None:
        products = await _load_products(db, payload.items)
        purchase.items = _build_items(payload.items, products)

    _recalculate(purchase)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="purchase.update",
        entity_type="purchase",
        entity_id=purchase.id,
        before=before,
        after=_snapshot(purchase),
        ip=_client_ip(request),
    )
    return _to_out(purchase, supplier_name, products)


@router.post("/purchases/{purchase_id}/post", response_model=PurchaseOut)
async def post_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("purchases.manage")),
) -> PurchaseOut:
    """Ноорог худалдан авалтыг бүртгэнэ: нөөц + өглөг + журналын бичилт."""
    purchase, supplier_name = await _load_row(db, purchase_id)

    await receipt_service.post_purchase(db, user, purchase)

    await audit(
        db,
        user_id=user.id,
        action="purchase.post_request",
        entity_type="purchase",
        entity_id=purchase.id,
        after={"status": str(purchase.status)},
        ip=_client_ip(request),
    )
    return _to_out(purchase, supplier_name)


@router.delete("/purchases/{purchase_id}", status_code=204, response_model=None)
async def delete_purchase(
    purchase_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("purchases.manage")),
) -> None:
    """Зөвхөн ноорог устгагдана — бүртгэсэн баримт НББ-д бичигдсэн байна."""
    purchase, _supplier_name = await _load_row(db, purchase_id)
    if str(purchase.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Бүртгэсэн баримтыг устгах боломжгүй")

    before = _snapshot(purchase)
    await db.delete(purchase)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="purchase.delete",
        entity_type="purchase",
        entity_id=purchase_id,
        before=before,
        ip=_client_ip(request),
    )
