"""Барааны нөөцийн дэвтэр (CONTRACTS.md §6).

``Product.stock_qty`` / ``Product.avg_cost`` **зөвхөн энд** өөрчлөгдөж,
``InventoryTransaction`` мөр бүр энд бичигдэнэ.  Ингэснээр нөөцийн үлдэгдэл
болон дэвтрийн нийлбэр үргэлж таарна.

Дүрэм:
  * энэ модуль **хэзээ ч** ``db.commit()`` дуудахгүй — ``get_db`` эзэмшинэ;
  * зөвхөн ``Decimal``.  Тоо хэмжээ ``q3``, нэгж өртөг ``q6``, мөнгө ``q2``;
  * хөдлөх дундаж өртөг: зөвхөн худалдан авалт ``avg_cost``-ыг хөдөлгөнө.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.enums import InventoryTxType
from app.models.product import InventoryTransaction, Product, ProductBranchStock
from app.money import q2, q3, q6

ZERO = Decimal("0")


def _d(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _record(
    db: AsyncSession,
    product: Product,
    *,
    tx_type: str,
    qty: Decimal,
    unit_cost: Decimal,
    balance_after: Decimal,
    ref_type: str | None,
    ref_id: uuid.UUID | None,
    note: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> InventoryTransaction:
    """Нөөцийн дэвтэрт нэг мөр бичнэ (``qty`` тэмдэгтэй: + орлого, − зарлага)."""
    tx = InventoryTransaction(
        product_id=product.id,
        branch_id=branch_id,
        tx_type=str(tx_type),
        qty=q3(qty),
        unit_cost=q6(unit_cost),
        balance_after=q3(balance_after),
        ref_type=(str(ref_type) if ref_type is not None else None),
        ref_id=ref_id,
        note=(note[:255] if note else None),
    )
    db.add(tx)
    return tx


async def _branch_stock(
    db: AsyncSession, product_id: uuid.UUID, branch_id: uuid.UUID
) -> ProductBranchStock:
    """Салбарын үлдэгдлийн мөр (байхгүй бол 0-ээр үүсгэнэ). Мөрийг түгжинэ."""
    row = await db.scalar(
        select(ProductBranchStock)
        .where(
            ProductBranchStock.product_id == product_id,
            ProductBranchStock.branch_id == branch_id,
        )
        .with_for_update()
    )
    if row is None:
        row = ProductBranchStock(product_id=product_id, branch_id=branch_id, qty=Decimal("0"))
        db.add(row)
        await db.flush()
    return row


async def _move_branch_stock(
    db: AsyncSession,
    product: Product,
    branch_id: uuid.UUID | None,
    delta: Decimal,
) -> None:
    """Салбарын үлдэгдлийг ``delta``-гаар хөдөлгөнө.

    Нийт ``product.stock_qty``-г дуудагч аль хэдийн шинэчилсэн байх ёстой,
    ингэснээр Σ(салбар) == нийт инвариант хадгалагдана.  Салбарын үлдэгдэл
    хүрэлцэхгүй бол 422 — өөр салбарын бараагаар зарж болохгүй."""
    if branch_id is None:
        return
    row = await _branch_stock(db, product.id, branch_id)
    balance = q3(_d(row.qty) + delta)
    if balance < ZERO:
        raise HTTPException(
            status_code=422, detail="Энэ салбарт барааны үлдэгдэл хүрэлцэхгүй байна"
        )
    row.qty = balance


async def consume_product(
    db: AsyncSession,
    product: Product,
    qty: Decimal,
    *,
    ref_type: str,
    ref_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> Decimal:
    """Борлуулалтад ``qty`` ширхэг зарлагадаж, өртгийг (``qty · avg_cost``) буцаана.

    Үлдэгдэл хүрэлцэхгүй бол 422.
    """
    qty = q3(qty)
    if qty <= ZERO:
        raise HTTPException(status_code=422, detail="Барааны тоо хэмжээ 0-ээс их байх ёстой")

    stock = q3(_d(product.stock_qty))
    if qty > stock:
        raise HTTPException(status_code=422, detail="Барааны үлдэгдэл хүрэлцэхгүй байна")

    avg_cost = q6(_d(product.avg_cost))
    balance_after = q3(stock - qty)
    cogs = q2(qty * avg_cost)

    product.stock_qty = balance_after
    await _move_branch_stock(db, product, branch_id, -qty)
    _record(
        db,
        product,
        tx_type=InventoryTxType.SALE,
        qty=-qty,
        unit_cost=avg_cost,
        balance_after=balance_after,
        ref_type=ref_type,
        ref_id=ref_id,
        branch_id=branch_id,
    )
    return cogs


async def receive_product(
    db: AsyncSession,
    product: Product,
    qty: Decimal,
    unit_cost: Decimal,
    *,
    ref_type: str,
    ref_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> None:
    """Худалдан авалт.  Хөдлөх дундаж өртөг:

        new_avg = (old_qty · old_avg + qty · unit_cost) / (old_qty + qty)

    ``unit_cost`` нь НӨАТ-гүй нэгж өртөг.  Хуваарь 0 (эсвэл сөрөг) бол шинэ
    таталт өртгийг шууд тодорхойлно.
    """
    qty = q3(qty)
    if qty <= ZERO:
        raise HTTPException(status_code=422, detail="Хүлээн авах тоо хэмжээ 0-ээс их байх ёстой")

    unit_cost = q6(unit_cost)
    if unit_cost < ZERO:
        raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")

    old_qty = q3(_d(product.stock_qty))
    old_avg = q6(_d(product.avg_cost))
    denominator = old_qty + qty

    if denominator > ZERO:
        new_avg = q6((old_qty * old_avg + qty * unit_cost) / denominator)
    else:
        # Үлдэгдэл 0 (эсвэл сөрөг) байсан — таталт өртгийг шууд тогтооно.
        new_avg = unit_cost

    balance_after = q3(denominator)
    product.stock_qty = balance_after
    product.avg_cost = new_avg
    await _move_branch_stock(db, product, branch_id, qty)

    _record(
        db,
        product,
        tx_type=InventoryTxType.PURCHASE,
        qty=qty,
        unit_cost=unit_cost,
        balance_after=balance_after,
        ref_type=ref_type,
        ref_id=ref_id,
        branch_id=branch_id,
    )


async def restock_product(
    db: AsyncSession,
    product: Product,
    qty: Decimal,
    unit_cost: Decimal,
    *,
    ref_type: str,
    ref_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> None:
    """Буцаалтаар нөөцийг сэргээнэ.

    Дундаж өртгийг **өөрчлөхгүй** — бараа анх зарагдсан өртгөөрөө буцаж ирж
    байгаа тул ``avg_cost`` хөдлөх ёсгүй.
    """
    qty = q3(qty)
    if qty <= ZERO:
        raise HTTPException(status_code=422, detail="Буцаах тоо хэмжээ 0-ээс их байх ёстой")

    balance_after = q3(_d(product.stock_qty) + qty)
    product.stock_qty = balance_after
    await _move_branch_stock(db, product, branch_id, qty)

    _record(
        db,
        product,
        tx_type=InventoryTxType.REFUND,
        qty=qty,
        unit_cost=q6(unit_cost),
        balance_after=balance_after,
        ref_type=ref_type,
        ref_id=ref_id,
        branch_id=branch_id,
    )


async def convert_to_bulk(
    db: AsyncSession,
    source: Product,
    target: Product,
    qty: Decimal,
    out_qty: Decimal,
    *,
    ref_type: str = "bulk_conversion",
    ref_id: uuid.UUID | None = None,
    note: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> tuple[InventoryTransaction, InventoryTransaction]:
    """Ширхэг барааг задалж грам бүтээгдэхүүн рүү шилжүүлнэ.

    Жишээ: «5W-30 5л» савнаас 1 ширхэгийг задлахад «5W-30 задлан» бүртгэлд
    5.000 л нэмэгдэнэ.

    Өртөг **бүрэн хадгалагдана**: гарсан ширхэгийн ``qty · avg_cost``-ыг яг
    тэр чигээр нь грам бүтээгдэхүүн рүү шилжүүлж, хүлээн авагчийн хөдлөх
    дунджийг дахин бодно.  Хоёр бараа хоёулаа 1302 дансанд байдаг тул
    журналын бичилт хийх шаардлагагүй — ерөнхий дэвтэр хөдлөхгүй.
    """
    if source.id == target.id:
        raise HTTPException(status_code=422, detail="Бараа өөрөө рүүгээ хөрвөхгүй")

    qty = q3(qty)
    out_qty = q3(out_qty)
    if qty <= ZERO:
        raise HTTPException(status_code=422, detail="Задлах тоо хэмжээ 0-ээс их байх ёстой")
    if out_qty <= ZERO:
        raise HTTPException(status_code=422, detail="Гарах хэмжээ 0-ээс их байх ёстой")

    stock = q3(_d(source.stock_qty))
    if qty > stock:
        raise HTTPException(status_code=422, detail="Барааны үлдэгдэл хүрэлцэхгүй байна")

    # --- Зарлага: ширхэг бараа ---
    unit_cost = q6(_d(source.avg_cost))
    total_cost = qty * unit_cost  # бүтэн нарийвчлалаар — дугуйлалт хийхгүй
    source_balance = q3(stock - qty)
    source.stock_qty = source_balance
    await _move_branch_stock(db, source, branch_id, -qty)
    tx_out = _record(
        db,
        source,
        tx_type=InventoryTxType.CONVERT_OUT,
        qty=-qty,
        unit_cost=unit_cost,
        balance_after=source_balance,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note or f"{target.name_mn} → {out_qty} {target.unit}",
        branch_id=branch_id,
    )

    # --- Орлого: грам бүтээгдэхүүн (хөдлөх дундаж) ---
    old_qty = q3(_d(target.stock_qty))
    old_avg = q6(_d(target.avg_cost))
    denominator = old_qty + out_qty
    in_unit_cost = q6(total_cost / out_qty)
    if denominator > ZERO:
        target.avg_cost = q6((old_qty * old_avg + total_cost) / denominator)
    else:
        target.avg_cost = in_unit_cost

    target_balance = q3(denominator)
    target.stock_qty = target_balance
    await _move_branch_stock(db, target, branch_id, out_qty)
    tx_in = _record(
        db,
        target,
        tx_type=InventoryTxType.CONVERT_IN,
        qty=out_qty,
        unit_cost=in_unit_cost,
        balance_after=target_balance,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note or f"{source.name_mn} × {qty}",
        branch_id=branch_id,
    )
    return tx_out, tx_in


async def adjust_product(
    db: AsyncSession,
    product: Product,
    qty: Decimal,
    *,
    note: str | None = None,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> InventoryTransaction:
    """Тооллого/гар тохируулга.  ``qty`` тэмдэгтэй (+ илүүдэл, − дутагдал).

    Дундаж өртгийг өөрчлөхгүй: илүүдлийг одоогийн дунджаар үнэлж, дутагдлыг
    мөн одоогийн дунджаар данснаас хасна.
    """
    qty = q3(qty)
    if qty == ZERO:
        raise HTTPException(status_code=422, detail="Тохируулгын хэмжээ 0 байж болохгүй")

    balance_after = q3(_d(product.stock_qty) + qty)
    if balance_after < ZERO:
        raise HTTPException(status_code=422, detail="Барааны үлдэгдэл хүрэлцэхгүй байна")

    product.stock_qty = balance_after
    await _move_branch_stock(db, product, branch_id, qty)
    return _record(
        db,
        product,
        tx_type=InventoryTxType.ADJUSTMENT,
        qty=qty,
        unit_cost=q6(_d(product.avg_cost)),
        balance_after=balance_after,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
        branch_id=branch_id,
    )
