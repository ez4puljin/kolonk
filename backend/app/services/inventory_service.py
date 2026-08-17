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
    *,
    in_unit_cost: Decimal | None = None,
) -> None:
    """Салбарын үлдэгдлийг ``delta``-гаар хөдөлгөнө.

    Нийт ``product.stock_qty``-г дуудагч аль хэдийн шинэчилсэн байх ёстой,
    ингэснээр Σ(салбар) == нийт инвариант хадгалагдана.  Салбарын үлдэгдэл
    хүрэлцэхгүй бол 422 — өөр салбарын бараагаар зарж болохгүй.

    ``in_unit_cost`` өгвөл (орлого) тухайн салбарын хөдлөх дунджийг дахин
    бодно; зарлагад дундаж хөдлөхгүй."""
    if branch_id is None:
        return
    row = await _branch_stock(db, product.id, branch_id)
    old_qty = q3(_d(row.qty))
    balance = q3(old_qty + delta)
    if balance < ZERO:
        raise HTTPException(
            status_code=422, detail="Энэ салбарт барааны үлдэгдэл хүрэлцэхгүй байна"
        )
    if in_unit_cost is not None and delta > ZERO:
        old_avg = q6(_d(row.avg_cost))
        row.avg_cost = (
            q6((old_qty * old_avg + delta * q6(in_unit_cost)) / balance)
            if balance > ZERO
            else q6(in_unit_cost)
        )
    row.qty = balance


async def branch_unit_cost(
    db: AsyncSession, product: Product, branch_id: uuid.UUID | None
) -> Decimal:
    """Тухайн салбарын нэгж өртөг. Салбар/өртөг тодорхойгүй бол глобал дундаж.

    Салбар бүр өөр үнээр татдаг тул борлуулалтын өртөг, тохируулга,
    задлалт бүгд ЭНЭ утгыг ашиглана."""
    if branch_id is None:
        return q6(_d(product.avg_cost))
    row = await db.scalar(
        select(ProductBranchStock).where(
            ProductBranchStock.product_id == product.id,
            ProductBranchStock.branch_id == branch_id,
        )
    )
    cost = q6(_d(row.avg_cost)) if row is not None else ZERO
    return cost if cost > ZERO else q6(_d(product.avg_cost))


async def sync_product_cost(db: AsyncSession, product: Product) -> None:
    """Нийт дундаж өртгийг салбаруудын жигнэсэн дунджаар дахин бодно.

        avg_cost = Σ(qty_салбар × cost_салбар) / Σ(qty_салбар)

    Ингэснээр «нийт үлдэгдэл × дундаж өртөг» нь салбаруудын үнэлгээний
    нийлбэртэй таарна.  Салбарын мөр огт байхгүй (эсвэл нийт үлдэгдэл 0)
    бол өмнөх утгыг хөндөхгүй."""
    rows = (
        await db.scalars(
            select(ProductBranchStock).where(ProductBranchStock.product_id == product.id)
        )
    ).all()
    if not rows:
        return
    total_qty = ZERO
    total_value = ZERO
    for row in rows:
        qty = q3(_d(row.qty))
        total_qty += qty
        total_value += qty * q6(_d(row.avg_cost))
    if total_qty <= ZERO:
        return
    product.avg_cost = q6(total_value / total_qty)


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

    # Өртөг нь ЗАРСАН САЛБАРЫНХ — салбар бүр өөр үнээр татсан байж болно.
    avg_cost = await branch_unit_cost(db, product, branch_id)
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
    # Салбарын хөдлөх дундаж — таталт тухайн салбарын өртгийг хөдөлгөнө.
    await _move_branch_stock(db, product, branch_id, qty, in_unit_cost=unit_cost)
    await sync_product_cost(db, product)

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

    # --- Зарлага: ширхэг бараа (задалж буй САЛБАРЫН өртгөөр) ---
    unit_cost = await branch_unit_cost(db, source, branch_id)
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
    await _move_branch_stock(db, target, branch_id, out_qty, in_unit_cost=in_unit_cost)
    await sync_product_cost(db, source)
    await sync_product_cost(db, target)
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


async def transfer_product(
    db: AsyncSession,
    product: Product,
    qty: Decimal,
    *,
    from_branch_id: uuid.UUID,
    to_branch_id: uuid.UUID,
    note: str | None = None,
    ref_type: str = "branch_transfer",
    ref_id: uuid.UUID | None = None,
) -> tuple[InventoryTransaction, InventoryTransaction]:
    """Салбар хооронд бараа шилжүүлнэ.

    Нийт ``product.stock_qty`` ХӨДӨЛӨХГҮЙ — бараа компанийн дотор л
    байрлалаа сольж байгаа тул 1302 дансны үлдэгдэл өөрчлөгдөхгүй, журналын
    бичилт шаардлагагүй.  Өртөг бүрэн шилжинэ: өгсөн салбарын дундаж
    өртгөөр үнэлж, авсан салбарын хөдлөх дунджийг дахин бодно.

    Буцаана: (гарсан мөр, орсон мөр).
    """
    if from_branch_id == to_branch_id:
        raise HTTPException(status_code=422, detail="Ижил салбар руу шилжүүлэх боломжгүй")

    qty = q3(qty)
    if qty <= ZERO:
        raise HTTPException(status_code=422, detail="Шилжүүлэх тоо хэмжээ 0-ээс их байх ёстой")

    unit_cost = await branch_unit_cost(db, product, from_branch_id)
    total_qty = q3(_d(product.stock_qty))

    # --- Гарах салбар (үлдэгдэл хүрэлцэхгүй бол _move_branch_stock 422 өгнө) ---
    await _move_branch_stock(db, product, from_branch_id, -qty)
    source_row = await _branch_stock(db, product.id, from_branch_id)
    tx_out = _record(
        db,
        product,
        tx_type=InventoryTxType.TRANSFER_OUT,
        qty=-qty,
        unit_cost=unit_cost,
        balance_after=q3(_d(source_row.qty)),
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
        branch_id=from_branch_id,
    )

    # --- Орох салбар: хөдлөх дундаж шилжсэн өртгөөр ---
    await _move_branch_stock(db, product, to_branch_id, qty, in_unit_cost=unit_cost)
    dest_row = await _branch_stock(db, product.id, to_branch_id)
    tx_in = _record(
        db,
        product,
        tx_type=InventoryTxType.TRANSFER_IN,
        qty=qty,
        unit_cost=unit_cost,
        balance_after=q3(_d(dest_row.qty)),
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
        branch_id=to_branch_id,
    )

    # Нийт үлдэгдэл хэвээр; дундаж өртөг салбаруудаас дахин бодогдоно.
    product.stock_qty = total_qty
    await sync_product_cost(db, product)
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

    # Тохируулгыг тухайн салбарын өртгөөр үнэлнэ (дундаж хөдлөхгүй).
    unit_cost = await branch_unit_cost(db, product, branch_id)
    product.stock_qty = balance_after
    await _move_branch_stock(db, product, branch_id, qty)
    return _record(
        db,
        product,
        tx_type=InventoryTxType.ADJUSTMENT,
        qty=qty,
        unit_cost=unit_cost,
        balance_after=balance_after,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
        branch_id=branch_id,
    )
