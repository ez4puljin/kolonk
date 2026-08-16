"""Fuel tank ledger — the single place where ``Tank.current_l`` / ``Tank.avg_cost``
change and where ``TankMovement`` rows are written.

Rules (CONTRACTS.md §1, §2, §6):
  * never ``db.commit()`` here — ``get_db`` owns the single commit.
  * Decimal only.  Liters ``q3``, unit costs ``q6``, money ``q2``.
  * Moving average costing: only receipts move ``avg_cost``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import TankMovementType
from app.models.fuel import Tank, TankMovement
from app.money import q2, q3, q6

# A tank may be driven a hair below zero by rounding of individual fuelings;
# anything worse than this is a real shortage and must be refused.
NEGATIVE_TOLERANCE = Decimal("-0.001")

ZERO = Decimal("0")


def _record(
    db: AsyncSession,
    tank: Tank,
    *,
    movement_type: str,
    liters: Decimal,
    balance_after_l: Decimal,
    unit_cost: Decimal,
    ref_type: str | None,
    ref_id: uuid.UUID | None,
    note: str | None = None,
) -> TankMovement:
    movement = TankMovement(
        tank_id=tank.id,
        movement_type=str(movement_type),
        liters=q3(liters),
        balance_after_l=q3(balance_after_l),
        unit_cost=q6(unit_cost),
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
    )
    db.add(movement)
    return movement


async def consume_fuel(
    db: AsyncSession,
    tank: Tank,
    liters: Decimal,
    *,
    ref_type: str,
    ref_id: uuid.UUID | None = None,
) -> Decimal:
    """Take ``liters`` out of the tank and return the COGS at the moving average.

    Raises 422 if the tank cannot cover the volume.
    """
    liters = q3(liters)
    if liters <= ZERO:
        raise HTTPException(status_code=422, detail="Түлшний хэмжээ 0-ээс их байх ёстой")

    avg_cost = q6(tank.avg_cost or ZERO)
    balance_after = q3(Decimal(tank.current_l or ZERO) - liters)
    if balance_after < NEGATIVE_TOLERANCE:
        raise HTTPException(status_code=422, detail="Савны үлдэгдэл хүрэлцэхгүй байна")

    cogs = q2(liters * avg_cost)
    tank.current_l = balance_after
    _record(
        db,
        tank,
        movement_type=TankMovementType.SALE,
        liters=-liters,
        balance_after_l=balance_after,
        unit_cost=avg_cost,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    return cogs


async def receive_fuel(
    db: AsyncSession,
    tank: Tank,
    liters: Decimal,
    landed_unit_cost: Decimal,
    *,
    ref_type: str,
    ref_id: uuid.UUID | None = None,
) -> None:
    """Book a delivery.  Moving average:

        new_avg = (old_l · old_avg + liters · landed_unit_cost) / (old_l + liters)

    ``landed_unit_cost`` is the VAT-free cost per liter including freight.
    """
    liters = q3(liters)
    if liters <= ZERO:
        raise HTTPException(status_code=422, detail="Хүлээн авах хэмжээ 0-ээс их байх ёстой")

    landed_unit_cost = q6(landed_unit_cost)
    if landed_unit_cost < ZERO:
        raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")

    old_l = Decimal(tank.current_l or ZERO)
    old_avg = Decimal(tank.avg_cost or ZERO)
    denominator = old_l + liters

    if denominator > ZERO:
        new_avg = q6((old_l * old_avg + liters * landed_unit_cost) / denominator)
    else:
        # Tank was at (or below) zero — the delivery defines the cost outright.
        new_avg = landed_unit_cost

    balance_after = q3(denominator)
    tank.current_l = balance_after
    tank.avg_cost = new_avg

    _record(
        db,
        tank,
        movement_type=TankMovementType.RECEIPT,
        liters=liters,
        balance_after_l=balance_after,
        unit_cost=landed_unit_cost,
        ref_type=ref_type,
        ref_id=ref_id,
    )


async def adjust_fuel(
    db: AsyncSession,
    tank: Tank,
    liters: Decimal,
    *,
    movement_type: str = TankMovementType.ADJUSTMENT,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    note: str | None = None,
) -> None:
    """Apply a signed delta (dip variance, manual correction, opening balance).

    Never touches ``avg_cost`` — a gain is valued at the current average and a
    loss is written off at the current average.
    """
    liters = q3(liters)
    if liters == ZERO:
        raise HTTPException(status_code=422, detail="Тохируулгын хэмжээ 0 байж болохгүй")

    balance_after = q3(Decimal(tank.current_l or ZERO) + liters)
    if balance_after < NEGATIVE_TOLERANCE:
        raise HTTPException(status_code=422, detail="Савны үлдэгдэл хүрэлцэхгүй байна")

    tank.current_l = balance_after
    _record(
        db,
        tank,
        movement_type=movement_type,
        liters=liters,
        balance_after_l=balance_after,
        unit_cost=q6(tank.avg_cost or ZERO),
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
    )
