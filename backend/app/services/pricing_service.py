"""Салбарын үйлчлэх (effective) үнэ.

Дүрэм: тухайн салбарт ``branch_prices`` override мөр байвал ТЭР үнэ,
байхгүй бол суурь үнэ (``fuels.price_per_liter`` / ``products.price``).
Override зөвхөн ``price_change_service``-ийн батлах урсгалаар бичигдэнэ.

Энэ модуль ``db.commit()`` дуудахгүй — ``get_db`` эзэмшинэ (CONTRACTS.md §1).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fuel import Fuel
from app.models.pricing import BranchPrice
from app.models.product import Product
from app.money import q2

ZERO = Decimal("0.00")


async def fuel_price_override(
    db: AsyncSession, fuel_id: uuid.UUID, branch_id: uuid.UUID | None
) -> Decimal | None:
    """Салбарын түлшний override үнэ (байхгүй бол None)."""
    if branch_id is None:
        return None
    price = await db.scalar(
        select(BranchPrice.price).where(
            BranchPrice.branch_id == branch_id, BranchPrice.fuel_id == fuel_id
        )
    )
    return q2(price) if price is not None else None


async def effective_fuel_price(
    db: AsyncSession, fuel: Fuel, branch_id: uuid.UUID | None
) -> Decimal:
    override = await fuel_price_override(db, fuel.id, branch_id)
    return override if override is not None else q2(Decimal(fuel.price_per_liter or ZERO))


async def product_price_override(
    db: AsyncSession, product_id: uuid.UUID, branch_id: uuid.UUID | None
) -> Decimal | None:
    if branch_id is None:
        return None
    price = await db.scalar(
        select(BranchPrice.price).where(
            BranchPrice.branch_id == branch_id, BranchPrice.product_id == product_id
        )
    )
    return q2(price) if price is not None else None


async def effective_product_price(
    db: AsyncSession, product: Product, branch_id: uuid.UUID | None
) -> Decimal:
    override = await product_price_override(db, product.id, branch_id)
    return override if override is not None else q2(Decimal(product.price or ZERO))


async def fuel_price_map(db: AsyncSession, branch_id: uuid.UUID | None) -> dict[uuid.UUID, Decimal]:
    """Салбарын түлшний override-уудын толь: fuel_id → үнэ."""
    if branch_id is None:
        return {}
    rows = (
        await db.execute(
            select(BranchPrice.fuel_id, BranchPrice.price).where(
                BranchPrice.branch_id == branch_id, BranchPrice.fuel_id.is_not(None)
            )
        )
    ).all()
    return {fuel_id: q2(price) for fuel_id, price in rows}


async def product_price_map(
    db: AsyncSession, branch_id: uuid.UUID | None
) -> dict[uuid.UUID, Decimal]:
    """Салбарын барааны override-уудын толь: product_id → үнэ."""
    if branch_id is None:
        return {}
    rows = (
        await db.execute(
            select(BranchPrice.product_id, BranchPrice.price).where(
                BranchPrice.branch_id == branch_id, BranchPrice.product_id.is_not(None)
            )
        )
    ).all()
    return {product_id: q2(price) for product_id, price in rows}


async def set_branch_price(
    db: AsyncSession,
    branch_id: uuid.UUID,
    *,
    fuel_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    price: Decimal,
) -> BranchPrice:
    """Салбарын үнийг тавина (байвал шинэчилнэ). Зөвхөн батлах урсгалаас дуудагдана."""
    conditions = [BranchPrice.branch_id == branch_id]
    if fuel_id is not None:
        conditions.append(BranchPrice.fuel_id == fuel_id)
    else:
        conditions.append(BranchPrice.product_id == product_id)

    row = await db.scalar(select(BranchPrice).where(*conditions))
    if row is None:
        row = BranchPrice(branch_id=branch_id, fuel_id=fuel_id, product_id=product_id, price=q2(price))
        db.add(row)
    else:
        row.price = q2(price)
    await db.flush()
    return row
