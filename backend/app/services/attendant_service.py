"""Түгээгчийн өдрийн ээлж — миль×үнэ тооцоо ба өдрийн хаалт.

ПОС унтраалттай станцад түгээгч өглөө бэлэн мөнгө + насос бүрийн миль
(тоолуурын заалт) зурагтай бүртгэж ээлжээ нээгээд, орой нэг дор хаадаг:

    хүлээгдэх түлшний орлого = Σ хошуу (хаалтын миль − нээлтийн миль) × үнэ

Үнэ өдрийн дундуур өөрчлөгдвөл ``ShiftPriceMark`` тэмдэглэл сегментчилнэ:
нээлтийн миль → тэмдэглэлийн миль хуучин үнээр, цааш шинэ үнээр.

Хаалт дараах баримтуудыг НЭГ transaction-д үүсгэнэ (бүгд ердийн
борлуулалт/зардал/төлбөрийн үйлчилгээгээр — журнал, нөөц, авлага өөрөө зөв):

    1. Зээлийн борлуулалтууд — гэрээт харилцагч тус бүрд нэг Sale;
    2. Тос, барааны борлуулалт — нэг Sale (бэлэн + шаардлагатай бол карт);
    3. Нэгдсэн түлшний борлуулалт — сегмент тус бүр нэг мөр, төлбөр нь
       settlement (карт) + үлдэгдэл бэлэн;
    4. Авлагын төлбөрүүд (өглөг) — ``contract_service.record_payment``;
    5. Зарлагууд — ``expense_service.create_expense``;
    6. Ердийн ``close_shift`` — кассын зөрүү өөрөө бодогдоно.

Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй — ``get_db`` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CashAccount, ItemType, PaymentMethod, ReadingType, SaleType, ShiftStatus
from app.models.branch import Branch
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank, TotalizerReading
from app.models.partner import Contract, Customer
from app.models.product import Product
from app.models.shift import Shift, ShiftClosing, ShiftPriceMark
from app.models.user import User
from app.money import q2, q3
from app.schemas.sale import PaymentIn, SaleCreate, SaleItemIn
from app.services import contract_service, expense_service, sale_service, shift_service
from app.services.audit_service import audit
from app.services.pricing_service import effective_fuel_price
from app.stationtime import STATION_TZ, day_end, day_start

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


# --------------------------------------------------------------------------- #
# Үнийн тэмдэглэл (өдрийн дундуур үнэ өөрчлөгдөх)
# --------------------------------------------------------------------------- #
async def _open_reading(db: AsyncSession, shift: Shift, nozzle_id: uuid.UUID) -> TotalizerReading | None:
    return await db.scalar(
        select(TotalizerReading).where(
            TotalizerReading.shift_id == shift.id,
            TotalizerReading.nozzle_id == nozzle_id,
            TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
        )
    )


async def add_price_mark(
    db: AsyncSession,
    user: User,
    shift: Shift,
    *,
    nozzle_id: uuid.UUID,
    reading: Decimal,
    new_price: Decimal,
    note: str | None = None,
) -> ShiftPriceMark:
    """Хошууны аль мильд шинэ үнэ эхэлснийг тэмдэглэнэ."""
    if shift.status != str(ShiftStatus.OPEN):
        raise HTTPException(status_code=422, detail="Ээлж нээлттэй биш байна")

    nozzle = await db.scalar(select(PumpNozzle).where(PumpNozzle.id == nozzle_id))
    if nozzle is None:
        raise HTTPException(status_code=404, detail="Хошуу олдсонгүй")

    reading = q3(_d(reading, ZERO_L))
    new_price = q2(_d(new_price))
    if new_price <= ZERO:
        raise HTTPException(status_code=422, detail="Шинэ үнэ 0-ээс их байх ёстой")

    opened = await _open_reading(db, shift, nozzle_id)
    if opened is not None and reading < _d(opened.reading, ZERO_L):
        raise HTTPException(
            status_code=422, detail="Тэмдэглэлийн миль нээлтийн мильээс бага байж болохгүй"
        )

    # Өмнөх сегментийн үнэ: сүүлийн тэмдэглэлийн шинэ үнэ → нээлтийн snapshot →
    # одоогийн жагсаалтын үнэ (аль эхэнд олдсоноор).
    last_mark = await db.scalar(
        select(ShiftPriceMark)
        .where(ShiftPriceMark.shift_id == shift.id, ShiftPriceMark.nozzle_id == nozzle_id)
        .order_by(ShiftPriceMark.reading.desc())
        .limit(1)
    )
    if last_mark is not None:
        if reading < _d(last_mark.reading, ZERO_L):
            raise HTTPException(
                status_code=422, detail="Тэмдэглэлийн миль өмнөх тэмдэглэлээс бага байж болохгүй"
            )
        old_price = q2(_d(last_mark.new_price))
    elif opened is not None and opened.price_per_liter is not None:
        old_price = q2(_d(opened.price_per_liter))
    else:
        fuel = await db.scalar(select(Fuel).where(Fuel.id == nozzle.fuel_id))
        old_price = await effective_fuel_price(db, fuel, shift.branch_id) if fuel else ZERO

    mark = ShiftPriceMark(
        shift_id=shift.id,
        nozzle_id=nozzle_id,
        reading=reading,
        old_price=old_price,
        new_price=new_price,
        note=(note or "").strip() or None,
        created_by=user.id,
    )
    db.add(mark)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="shift.price_mark",
        entity_type="shift",
        entity_id=shift.id,
        after={
            "nozzle_id": str(nozzle_id),
            "reading": str(reading),
            "old_price": str(old_price),
            "new_price": str(new_price),
        },
    )
    return mark


# --------------------------------------------------------------------------- #
# Миль×үнэ сегментчилсэн тооцоо
# --------------------------------------------------------------------------- #
@dataclass
class Segment:
    """Нэг хошууны нэг үнийн сегмент."""

    liters: Decimal
    price: Decimal
    amount: Decimal


@dataclass
class NozzleCalc:
    nozzle: PumpNozzle
    open_reading: Decimal
    close_reading: Decimal
    segments: list[Segment] = field(default_factory=list)

    @property
    def liters(self) -> Decimal:
        return q3(sum((s.liters for s in self.segments), ZERO_L))

    @property
    def amount(self) -> Decimal:
        return q2(sum((s.amount for s in self.segments), ZERO))


async def compute_dispensed(
    db: AsyncSession, shift: Shift, closing_readings: dict[uuid.UUID, Decimal]
) -> list[NozzleCalc]:
    """Хошуу бүрийн түгээлтийг үнийн сегментээр бодно.

    ``closing_readings`` — хаалтын миль (хошуу бүрд).  Нээлтийн заалтгүй
    хошууг алгасна (ээлжийн дундуур нэмэгдсэн насос гэх мэт).
    """
    opens = (
        await db.scalars(
            select(TotalizerReading).where(
                TotalizerReading.shift_id == shift.id,
                TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
            )
        )
    ).all()
    if not opens:
        return []

    marks = (
        await db.scalars(
            select(ShiftPriceMark)
            .where(ShiftPriceMark.shift_id == shift.id)
            .order_by(ShiftPriceMark.reading)
        )
    ).all()
    marks_by_nozzle: dict[uuid.UUID, list[ShiftPriceMark]] = {}
    for mark in marks:
        marks_by_nozzle.setdefault(mark.nozzle_id, []).append(mark)

    nozzle_ids = [r.nozzle_id for r in opens]
    nozzles = {
        n.id: n
        for n in (
            await db.scalars(select(PumpNozzle).where(PumpNozzle.id.in_(nozzle_ids)))
        ).all()
    }

    out: list[NozzleCalc] = []
    for open_row in opens:
        nozzle = nozzles.get(open_row.nozzle_id)
        if nozzle is None:
            continue
        close_val = closing_readings.get(open_row.nozzle_id)
        if close_val is None:
            raise HTTPException(
                status_code=422, detail="Бүх хошууны хаалтын миль оруулна уу"
            )
        open_val = q3(_d(open_row.reading, ZERO_L))
        close_val = q3(_d(close_val, ZERO_L))
        if close_val < open_val:
            raise HTTPException(
                status_code=422,
                detail="Хаалтын миль нээлтийн мильээс бага байж болохгүй",
            )

        calc = NozzleCalc(nozzle=nozzle, open_reading=open_val, close_reading=close_val)

        # Сегментүүд: нээлтийн үнэ → тэмдэглэл бүрийн шинэ үнэ.
        base_price = q2(_d(open_row.price_per_liter))
        if base_price <= ZERO:
            fuel = await db.scalar(select(Fuel).where(Fuel.id == nozzle.fuel_id))
            base_price = await effective_fuel_price(db, fuel, shift.branch_id) if fuel else ZERO

        cursor = open_val
        price = base_price
        for mark in marks_by_nozzle.get(open_row.nozzle_id, []):
            point = min(max(q3(_d(mark.reading, ZERO_L)), open_val), close_val)
            liters = q3(point - cursor)
            if liters > ZERO_L:
                calc.segments.append(
                    Segment(liters=liters, price=price, amount=q2(liters * price))
                )
            cursor = point
            price = q2(_d(mark.new_price))
        liters = q3(close_val - cursor)
        if liters > ZERO_L:
            calc.segments.append(Segment(liters=liters, price=price, amount=q2(liters * price)))

        out.append(calc)
    return out


def _calc_out(calc: NozzleCalc) -> dict[str, Any]:
    return {
        "nozzle_id": calc.nozzle.id,
        "pump_id": calc.nozzle.pump_id,
        "nozzle_number": calc.nozzle.nozzle_number,
        "fuel_id": calc.nozzle.fuel_id,
        "tank_id": calc.nozzle.tank_id,
        "open_reading": calc.open_reading,
        "close_reading": calc.close_reading,
        "liters": calc.liters,
        "amount": calc.amount,
        "segments": [
            {"liters": s.liters, "price": s.price, "amount": s.amount} for s in calc.segments
        ],
    }


# --------------------------------------------------------------------------- #
# Өдрийн хаалт
# --------------------------------------------------------------------------- #
def _readings_map(items: list[Any]) -> dict[uuid.UUID, Decimal]:
    out: dict[uuid.UUID, Decimal] = {}
    for item in items or []:
        nozzle_id = item.nozzle_id if hasattr(item, "nozzle_id") else uuid.UUID(str(item["nozzle_id"]))
        reading = _d(item.reading if hasattr(item, "reading") else item["reading"], ZERO_L)
        out[nozzle_id] = q3(reading)
    return out


async def _load_contract_prices(
    db: AsyncSession, shift: Shift, fuel_ids: set[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    prices: dict[uuid.UUID, Decimal] = {}
    if not fuel_ids:
        return prices
    fuels = (await db.scalars(select(Fuel).where(Fuel.id.in_(fuel_ids)))).all()
    for fuel in fuels:
        prices[fuel.id] = await effective_fuel_price(db, fuel, shift.branch_id)
    return prices


class _SegmentSlots:
    """Милийн зөрүүний сегментүүд — савтайгаа хамт.

    Зээлээр өгсөн литрийг эндээс «сүүлийн сегментээс эхлэн» хасаж хуваарилдаг
    тул сав бүрийн нийт зарлага = тухайн савны хошуудын милийн зөрүү гэсэн
    инвариант хадгалагдана (зээл + нэгдсэн борлуулалт хоёул зөв савнаас гарна).
    """

    def __init__(self, calcs: list[NozzleCalc]) -> None:
        #: (calc, seg, үлдэгдэл литр) — calc бүрийн сегментүүд дарааллаараа.
        self.slots: list[dict[str, Any]] = [
            {"calc": calc, "seg": seg, "remaining": seg.liters}
            for calc in calcs
            for seg in calc.segments
        ]

    def take_credit(self, fuel_id: uuid.UUID, liters: Decimal) -> list[tuple[uuid.UUID, Decimal]]:
        """``liters``-ийг тухайн түлшний сегментүүдээс (сүүлээс нь) хасаж,
        аль савнаас хэдэн литр гарснийг буцаана."""
        need = q3(liters)
        taken: dict[uuid.UUID, Decimal] = {}
        for slot in reversed(self.slots):
            if need <= ZERO_L:
                break
            if slot["calc"].nozzle.fuel_id != fuel_id or slot["remaining"] <= ZERO_L:
                continue
            take = min(slot["remaining"], need)
            slot["remaining"] = q3(slot["remaining"] - take)
            need = q3(need - take)
            tank_id = slot["calc"].nozzle.tank_id
            taken[tank_id] = q3(taken.get(tank_id, ZERO_L) + take)
        if need > ZERO_L:
            raise HTTPException(
                status_code=422,
                detail="Зээлээр өгсөн литр милийн зөрүүнээс их байна — милээ шалгана уу",
            )
        return list(taken.items())


async def _create_credit_sales(
    db: AsyncSession,
    user: User,
    shift: Shift,
    credit_lines: list[Any],
    slots: _SegmentSlots,
) -> tuple[Decimal, list[uuid.UUID]]:
    """Зээлийн (гэрээт) борлуулалтуудыг үүсгэнэ.

    Түлшний литрийг милийн зөрүүний сегментүүдээс хуваарилж авдаг тул сав
    хэд байхаас үл хамааран зөв савнаас хасагдана.

    Буцаана: (нийт дүн, sale_id-ууд).
    """
    total = ZERO
    sale_ids: list[uuid.UUID] = []

    fuel_ids = {
        uuid.UUID(str(item.fuel_id))
        for line in credit_lines or []
        for item in line.items
        if item.fuel_id is not None
    }
    base_prices = await _load_contract_prices(db, shift, fuel_ids)

    for line in credit_lines or []:
        contract = await db.scalar(select(Contract).where(Contract.id == line.contract_id))
        if contract is None:
            raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
        discount = q2(_d(contract.price_discount_per_l))

        items: list[SaleItemIn] = []
        line_total = ZERO
        for item in line.items:
            if item.fuel_id is not None:
                base = base_prices.get(item.fuel_id, ZERO)
                unit = q2(base - discount)
                if unit <= ZERO:
                    raise HTTPException(status_code=422, detail="Түлшний үнэ тодорхойгүй байна")
                entered_amount: Decimal | None = None
                if item.amount is not None and _d(item.amount) > ZERO:
                    entered_amount = q2(_d(item.amount))
                    qty = q3(entered_amount / unit)
                elif item.qty is not None and _d(item.qty) > ZERO_L:
                    qty = q3(_d(item.qty))
                else:
                    raise HTTPException(
                        status_code=422, detail="Зээлийн түлшний литр эсвэл дүнг оруулна уу"
                    )

                # Литрийг милийн зөрүүний сегментүүдээс зөв савнаас нь авна.
                splits = slots.take_credit(item.fuel_id, qty)
                split_amounts = [q2(liters * unit) for _tank, liters in splits]
                if entered_amount is not None and split_amounts:
                    # Оруулсан дүнг яг барина: зөрүүг сүүлийн мөрөнд шингээнэ.
                    drift = q2(entered_amount - sum(split_amounts, ZERO))
                    split_amounts[-1] = q2(split_amounts[-1] + drift)
                for (tank_id, liters), amount in zip(splits, split_amounts, strict=True):
                    items.append(
                        SaleItemIn(
                            item_type=ItemType.FUEL,
                            fuel_id=item.fuel_id,
                            tank_id=tank_id,
                            qty=liters,
                            unit_price=base,
                            amount=amount,
                        )
                    )
                    line_total = q2(line_total + amount)
            elif item.product_id is not None:
                product = await db.scalar(select(Product).where(Product.id == item.product_id))
                if product is None:
                    raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
                qty = q3(_d(item.qty, ZERO_L))
                if qty <= ZERO_L:
                    raise HTTPException(status_code=422, detail="Барааны тоо 0-ээс их байх ёстой")
                unit = q2(_d(product.price))
                items.append(
                    SaleItemIn(item_type=ItemType.PRODUCT, product_id=product.id, qty=qty)
                )
                line_total = q2(line_total + q2(qty * unit))
            else:
                raise HTTPException(status_code=422, detail="Зээлийн мөр хоосон байна")

        if not items:
            continue

        payload = SaleCreate(
            sale_type=SaleType.MIXED if len({i.item_type for i in items}) > 1 else (
                SaleType.FUEL if items[0].item_type == ItemType.FUEL else SaleType.STORE
            ),
            items=items,
            payments=[
                PaymentIn(
                    method=PaymentMethod.CONTRACT, amount=line_total, contract_id=contract.id
                )
            ],
            contract_id=contract.id,
        )
        sale = await sale_service.create_sale(db, user, payload)
        sale_ids.append(sale.id)
        total = q2(total + line_total)

    return total, sale_ids


def _noncash_payments(
    total: Decimal, card_amount: Decimal, transfer_amount: Decimal
) -> tuple[list[PaymentIn], Decimal, Decimal]:
    """Өдрийн борлуулалтын төлбөрийг 3 сувагт хуваана.

    Эхлээд карт (терминалын тооцоо), дараа нь шилжүүлэг, үлдсэн нь бэлэн.
    Буцаана: (төлбөрүүд, ашигласан карт, ашигласан шилжүүлэг).
    """
    card = min(q2(card_amount), total)
    transfer = min(q2(transfer_amount), q2(total - card))
    payments: list[PaymentIn] = []
    if card > ZERO:
        payments.append(PaymentIn(method=PaymentMethod.CARD, amount=card, ref_no="SETTLEMENT"))
    if transfer > ZERO:
        payments.append(
            PaymentIn(method=PaymentMethod.TRANSFER, amount=transfer, ref_no="TRANSFER")
        )
    cash = q2(total - card - transfer)
    if cash > ZERO:
        payments.append(PaymentIn(method=PaymentMethod.CASH, amount=cash, received=cash))
    return payments, card, transfer


async def _create_oil_sale(
    db: AsyncSession,
    user: User,
    oil_lines: list[Any],
    *,
    card_amount: Decimal,
    transfer_amount: Decimal = ZERO,
) -> tuple[Decimal, Decimal, Decimal, uuid.UUID | None]:
    """Тос, барааны өдрийн борлуулалт — нэг Sale (карт/шилжүүлэг + бэлэн үлдэгдэл).

    Буцаана: (нийт дүн, ашигласан карт, ашигласан шилжүүлэг, sale_id).
    """
    if not oil_lines:
        return ZERO, ZERO, ZERO, None

    items: list[SaleItemIn] = []
    total = ZERO
    for line in oil_lines:
        product = await db.scalar(select(Product).where(Product.id == line.product_id))
        if product is None:
            raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
        qty = q3(_d(line.qty, ZERO_L))
        if qty <= ZERO_L:
            raise HTTPException(status_code=422, detail="Барааны тоо 0-ээс их байх ёстой")
        unit = q2(_d(line.unit_price)) if line.unit_price is not None else q2(_d(product.price))
        items.append(
            SaleItemIn(item_type=ItemType.PRODUCT, product_id=product.id, qty=qty, unit_price=unit)
        )
        total = q2(total + q2(qty * unit))

    if total <= ZERO:
        return ZERO, ZERO, ZERO, None

    payments, card, transfer = _noncash_payments(total, card_amount, transfer_amount)

    sale = await sale_service.create_sale(
        db, user, SaleCreate(sale_type=SaleType.STORE, items=items, payments=payments)
    )
    return total, card, transfer, sale.id


async def _create_fuel_sale(
    db: AsyncSession,
    user: User,
    slots: _SegmentSlots,
    *,
    card_amount: Decimal,
    transfer_amount: Decimal = ZERO,
) -> tuple[Decimal, Decimal, Decimal, uuid.UUID | None]:
    """Нэгдсэн түлшний борлуулалт — сегмент бүрийн ҮЛДЭГДЭЛ нэг мөр.

    Зээлээр өгсөн литр аль хэдийн сегментүүдээс хасагдсан тул энд юу үлдсэн
    нь бэлэн/картаар зарагдсан түлш.  Мөр бүр хошууныхоо савнаас хасагдана —
    сав бүрийн нийт зарлага милийн зөрүүтэйгээ яг таарна.

    Буцаана: (нийт дүн, ашигласан карт, ашигласан шилжүүлэг, sale_id).
    """
    items: list[SaleItemIn] = []
    total = ZERO

    for slot in slots.slots:
        liters = slot["remaining"]
        if liters <= ZERO_L:
            continue
        calc, seg = slot["calc"], slot["seg"]
        amount = q2(liters * seg.price)
        items.append(
            SaleItemIn(
                item_type=ItemType.FUEL,
                fuel_id=calc.nozzle.fuel_id,
                nozzle_id=calc.nozzle.id,
                tank_id=calc.nozzle.tank_id,
                qty=liters,
                unit_price=seg.price,
            )
        )
        total = q2(total + amount)

    if total <= ZERO:
        return ZERO, ZERO, ZERO, None

    payments, card, transfer = _noncash_payments(total, card_amount, transfer_amount)

    sale = await sale_service.create_sale(
        db, user, SaleCreate(sale_type=SaleType.FUEL, items=items, payments=payments)
    )
    return total, card, transfer, sale.id


async def daily_preview(
    db: AsyncSession, shift: Shift, closing_readings: list[Any]
) -> dict[str, Any]:
    """Хаалтын өмнөх тулгалт — миль×үнэ тооцоог харуулна (юу ч бичихгүй)."""
    calcs = await compute_dispensed(db, shift, _readings_map(closing_readings))
    return {
        "nozzles": [_calc_out(c) for c in calcs],
        "fuel_total": q2(sum((c.amount for c in calcs), ZERO)),
        "fuel_liters": q3(sum((c.liters for c in calcs), ZERO_L)),
        "opening_cash": q2(_d(shift.opening_cash)),
    }


async def daily_close(
    db: AsyncSession,
    user: User,
    shift: Shift,
    payload: Any,
) -> dict[str, Any]:
    """Өдрийн хаалт — бүх бүртгэл + ээлж хаах нэг transaction-д."""
    if shift.status != str(ShiftStatus.OPEN):
        raise HTTPException(status_code=422, detail="Энэ ээлж аль хэдийн хаагдсан байна")
    existing = await db.scalar(select(ShiftClosing).where(ShiftClosing.shift_id == shift.id))
    if existing is not None:
        raise HTTPException(status_code=422, detail="Өдрийн хаалт аль хэдийн хийгдсэн байна")

    readings = _readings_map(payload.totalizer_readings)
    calcs = await compute_dispensed(db, shift, readings)

    settlement_vat = q2(_d(payload.settlement_vat))
    settlement_novat = q2(_d(payload.settlement_novat))
    transfer_total = q2(_d(getattr(payload, "transfer_total", ZERO)))
    if settlement_vat < ZERO or settlement_novat < ZERO or transfer_total < ZERO:
        raise HTTPException(status_code=422, detail="Тушаалтын дүн сөрөг байж болохгүй")
    settlement_total = q2(settlement_vat + settlement_novat)

    # Миль×үнэ-ээр бодогдсон нийт түгээлт — тайланд ЭНЭ дүн харагдана
    # (зээлээр өгсөн литр ч түгээгдсэн тул хасахгүй).
    mile_total = q2(sum((c.amount for c in calcs), ZERO))

    # Сегментүүдийг нэг санд хийнэ: зээлийн литр эндээс зөв савнаас нь
    # хуваарилагдаж, үлдэгдэл нь нэгдсэн борлуулалт болно.
    slots = _SegmentSlots(calcs)

    # --- 1. Зээлийн борлуулалтууд ---
    credit_total, credit_sale_ids = await _create_credit_sales(
        db, user, shift, payload.credit_lines, slots
    )

    # --- 2. Нэгдсэн түлшний борлуулалт (карт/шилжүүлэг эхлээд түлшинд) ---
    fuel_total, fuel_card, fuel_transfer, fuel_sale_id = await _create_fuel_sale(
        db, user, slots, card_amount=settlement_total, transfer_amount=transfer_total
    )

    # --- 3. Тос, барааны борлуулалт (үлдсэн карт/шилжүүлгээр) ---
    card_left = q2(settlement_total - fuel_card)
    transfer_left = q2(transfer_total - fuel_transfer)
    oil_total, oil_card, oil_transfer, oil_sale_id = await _create_oil_sale(
        db,
        user,
        payload.oil_lines,
        card_amount=card_left,
        transfer_amount=transfer_left,
    )
    card_left = q2(card_left - oil_card)
    transfer_left = q2(transfer_left - oil_transfer)
    if card_left > ZERO or transfer_left > ZERO:
        raise HTTPException(
            status_code=422,
            detail="Тушаасан карт/шилжүүлгийн дүн өдрийн борлуулалтаас их байна — дүнгээ шалгана уу",
        )

    # --- 4. Авлагын төлбөрүүд (өглөг) ---
    ar_total = ZERO
    for pay in payload.ar_payments or []:
        # Бэлэн → касс, карт/шилжүүлэг → банк. Хэлбэрийг тэмдэглэлд үлдээнэ.
        method = str(pay.method or "cash")
        received_to = str(CashAccount.CASH) if method == "cash" else str(CashAccount.BANK)
        method_name = {"cash": "бэлэн", "card": "карт", "transfer": "шилжүүлэг"}.get(method, method)
        await contract_service.record_payment(
            db,
            user,
            contract_id=pay.contract_id,
            amount=q2(_d(pay.amount)),
            received_to=received_to,
            note=f"Өдрийн хаалт — {method_name}" + (f" · {pay.note}" if pay.note else ""),
        )
        ar_total = q2(ar_total + q2(_d(pay.amount)))

    # --- 5. Зарлагууд ---
    expense_total = ZERO
    for exp in payload.expenses or []:
        await expense_service.create_expense(
            db,
            user,
            account_code=exp.account_code,
            amount=q2(_d(exp.amount)),
            payment_method=str(exp.payment_method or "cash"),
            description=(exp.description or "").strip() or "Өдрийн хаалт",
            # Зарлага ээлжийн салбарт бичигдэнэ — эс бөгөөс салбарын цэвэр
            # ашигт харагдахгүй үлдэнэ.
            branch_id=shift.branch_id,
        )
        expense_total = q2(expense_total + q2(_d(exp.amount)))

    # --- 6. Хаалтын баримт ---
    closing = ShiftClosing(
        shift_id=shift.id,
        settlement_vat=settlement_vat,
        settlement_novat=settlement_novat,
        transfer_total=transfer_total,
        fuel_total=mile_total,
        credit_total=credit_total,
        oil_total=oil_total,
        fuel_sale_id=fuel_sale_id,
        oil_sale_id=oil_sale_id,
        note=(payload.note or "").strip() or None,
        created_by=user.id,
    )
    db.add(closing)
    await db.flush()

    # --- 7. Ээлж хаах (кассын зөрүү, савны зөрүү автоматаар) ---
    report = await shift_service.close_shift(
        db,
        user,
        shift=shift,
        declared_cash=q2(_d(payload.declared_cash)),
        tank_dips=payload.tank_dips or [],
        totalizer_readings=payload.totalizer_readings,
        note=payload.note,
    )

    await audit(
        db,
        user_id=user.id,
        action="shift.daily_close",
        entity_type="shift",
        entity_id=shift.id,
        after={
            "fuel_total": str(fuel_total),
            "credit_total": str(credit_total),
            "oil_total": str(oil_total),
            "settlement": str(settlement_total),
            "transfer": str(transfer_total),
            "ar_total": str(ar_total),
            "expense_total": str(expense_total),
            "credit_sales": len(credit_sale_ids),
        },
    )

    report["daily"] = await closing_out(db, shift)
    return report


async def closing_out(db: AsyncSession, shift: Shift) -> dict[str, Any] | None:
    """Хаалтын баримт + миль тооцооны тайлангийн дүрслэл."""
    closing = await db.scalar(select(ShiftClosing).where(ShiftClosing.shift_id == shift.id))
    if closing is None:
        return None

    # Хаалтын заалтуудаас тооцоог сэргээнэ (тайлан дахин үзэхэд).
    close_rows = (
        await db.scalars(
            select(TotalizerReading).where(
                TotalizerReading.shift_id == shift.id,
                TotalizerReading.reading_type == str(ReadingType.SHIFT_CLOSE),
            )
        )
    ).all()
    nozzle_rows: list[dict[str, Any]] = []
    tank_rows: list[dict[str, Any]] = []
    if close_rows:
        readings = {r.nozzle_id: q3(_d(r.reading, ZERO_L)) for r in close_rows}
        calcs = await compute_dispensed(db, shift, readings)
        # Насос, түлш, савны нэрсийг нэг нэг асуулгаар.
        pump_ids = {c.nozzle.pump_id for c in calcs}
        fuel_ids = {c.nozzle.fuel_id for c in calcs}
        tank_ids = {c.nozzle.tank_id for c in calcs}
        pumps = {
            p.id: p for p in (await db.scalars(select(Pump).where(Pump.id.in_(pump_ids)))).all()
        }
        fuels = {
            f.id: f for f in (await db.scalars(select(Fuel).where(Fuel.id.in_(fuel_ids)))).all()
        }
        tanks = {
            t.id: t for t in (await db.scalars(select(Tank).where(Tank.id.in_(tank_ids)))).all()
        }

        # Сав тус бүрийн зарлага = тухайн савны хошуудын милийн зөрүүний нийлбэр.
        tank_agg: dict[uuid.UUID, dict[str, Decimal]] = {}
        for calc in calcs:
            entry = tank_agg.setdefault(
                calc.nozzle.tank_id, {"liters": ZERO_L, "amount": ZERO}
            )
            entry["liters"] = q3(entry["liters"] + calc.liters)
            entry["amount"] = q2(entry["amount"] + calc.amount)
        for tank_id, entry in tank_agg.items():
            tank = tanks.get(tank_id)
            tank_rows.append(
                {
                    "tank_id": tank_id,
                    "tank_name": tank.name if tank else "",
                    "liters": entry["liters"],
                    "amount": entry["amount"],
                }
            )
        tank_rows.sort(key=lambda r: r["tank_name"])

        for calc in calcs:
            row = _calc_out(calc)
            pump = pumps.get(calc.nozzle.pump_id)
            fuel = fuels.get(calc.nozzle.fuel_id)
            tank = tanks.get(calc.nozzle.tank_id)
            row["pump_name"] = pump.name if pump else ""
            row["fuel_name"] = fuel.name_mn if fuel else ""
            row["tank_name"] = tank.name if tank else ""
            nozzle_rows.append(row)

    settlement_total = q2(_d(closing.settlement_vat) + _d(closing.settlement_novat))
    return {
        "settlement_vat": q2(_d(closing.settlement_vat)),
        "settlement_novat": q2(_d(closing.settlement_novat)),
        "settlement_total": settlement_total,
        "transfer_total": q2(_d(closing.transfer_total)),
        "fuel_total": q2(_d(closing.fuel_total)),
        "credit_total": q2(_d(closing.credit_total)),
        "oil_total": q2(_d(closing.oil_total)),
        "note": closing.note,
        "nozzles": nozzle_rows,
        "tanks": tank_rows,
    }


async def price_marks_out(db: AsyncSession, shift: Shift) -> list[dict[str, Any]]:
    marks = (
        await db.scalars(
            select(ShiftPriceMark)
            .where(ShiftPriceMark.shift_id == shift.id)
            .order_by(ShiftPriceMark.created_at)
        )
    ).all()
    if not marks:
        return []
    nozzle_ids = {m.nozzle_id for m in marks}
    nozzles = {
        n.id: n
        for n in (await db.scalars(select(PumpNozzle).where(PumpNozzle.id.in_(nozzle_ids)))).all()
    }
    fuels = {
        f.id: f
        for f in (
            await db.scalars(
                select(Fuel).where(Fuel.id.in_({n.fuel_id for n in nozzles.values()}))
            )
        ).all()
    }
    out = []
    for mark in marks:
        nozzle = nozzles.get(mark.nozzle_id)
        fuel = fuels.get(nozzle.fuel_id) if nozzle else None
        out.append(
            {
                "id": mark.id,
                "nozzle_id": mark.nozzle_id,
                "nozzle_number": nozzle.nozzle_number if nozzle else None,
                "fuel_name": fuel.name_mn if fuel else "",
                "reading": q3(_d(mark.reading, ZERO_L)),
                "old_price": q2(_d(mark.old_price)),
                "new_price": q2(_d(mark.new_price)),
                "note": mark.note,
                "created_at": mark.created_at,
            }
        )
    return out


async def daily_closings_list(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_ids: list[uuid.UUID] | None = None,
    attendant_ids: list[uuid.UUID] | None = None,
    status: str | None = None,
    only_variance: bool = False,
) -> list[dict[str, Any]]:
    """Ээлжийн тайлан — хаагдсан түгээгчийн ээлжүүд (сүүлийнх нь эхэндээ).

    Мөр бүр нэг хаалт: миль×үнэ орлого, зээл, тос/бараа, тушаалтын 3 суваг,
    кассын зөрүү, батламжийн төлөв. Нягтлан салбар, ажилтан, огноо, төлвөөр
    шүүж, зөрүүтэйг нь шүүн хардаг.

    ``status``: ``approved`` (батлагдсан) / ``pending`` (хүлээгдэж буй).
    ``only_variance``: зөвхөн кассын зөрүүтэй мөрүүд.
    """
    stmt = (
        select(ShiftClosing, Shift)
        .join(Shift, Shift.id == ShiftClosing.shift_id)
        .order_by(Shift.opened_at.desc())
    )
    if branch_ids:
        stmt = stmt.where(Shift.branch_id.in_(branch_ids))
    if attendant_ids:
        stmt = stmt.where(Shift.opened_by.in_(attendant_ids))
    if date_from is not None:
        stmt = stmt.where(Shift.opened_at >= day_start(date_from))
    if date_to is not None:
        stmt = stmt.where(Shift.opened_at <= day_end(date_to))
    if status == "approved":
        stmt = stmt.where(ShiftClosing.approved_at.is_not(None))
    elif status == "pending":
        stmt = stmt.where(ShiftClosing.approved_at.is_(None))
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    user_ids = {shift.opened_by for _, shift in rows}
    user_ids |= {c.approved_by for c, _ in rows if c.approved_by is not None}
    users = {
        u.id: u for u in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()
    }
    # Милийн залгамжийн зөрүү — ээлж бүрд нээлтийн заалт vs өмнөх хаалт.
    shift_ids = [shift.id for _, shift in rows]
    gap_rows = (
        await db.execute(
            select(
                TotalizerReading.shift_id,
                func.sum(TotalizerReading.reading - TotalizerReading.prev_reading),
                func.count(),
            )
            .where(
                TotalizerReading.shift_id.in_(shift_ids),
                TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
                TotalizerReading.prev_reading.is_not(None),
                TotalizerReading.reading != TotalizerReading.prev_reading,
            )
            .group_by(TotalizerReading.shift_id)
        )
    ).all()
    gaps = {row[0]: (q3(_d(row[1], ZERO_L)), int(row[2])) for row in gap_rows}

    branch_ids_seen = {shift.branch_id for _, shift in rows if shift.branch_id is not None}
    branches = (
        {
            b.id: b
            for b in (
                await db.scalars(select(Branch).where(Branch.id.in_(branch_ids_seen)))
            ).all()
        }
        if branch_ids_seen
        else {}
    )

    out: list[dict[str, Any]] = []
    for closing, shift in rows:
        over_short = _d(shift.cash_over_short) if shift.cash_over_short is not None else None
        if only_variance and (over_short is None or over_short == ZERO):
            continue
        attendant = users.get(shift.opened_by)
        approver = users.get(closing.approved_by) if closing.approved_by else None
        branch = branches.get(shift.branch_id) if shift.branch_id else None
        settlement_total = q2(_d(closing.settlement_vat) + _d(closing.settlement_novat))
        out.append(
            {
                "shift_id": shift.id,
                "shift_number": shift.number,
                "date": shift.opened_at.astimezone(STATION_TZ).date(),
                "attendant": attendant.full_name if attendant else "",
                "attendant_id": shift.opened_by,
                "branch_id": shift.branch_id,
                "branch_name": branch.name if branch else "",
                "opening_cash": q2(_d(shift.opening_cash)),
                "fuel_total": q2(_d(closing.fuel_total)),
                "credit_total": q2(_d(closing.credit_total)),
                "oil_total": q2(_d(closing.oil_total)),
                "settlement_total": settlement_total,
                "transfer_total": q2(_d(closing.transfer_total)),
                "declared_cash": q2(_d(shift.declared_cash)) if shift.declared_cash is not None else None,
                "expected_cash": q2(_d(shift.expected_cash)) if shift.expected_cash is not None else None,
                "cash_over_short": q2(over_short) if over_short is not None else None,
                "mile_gap_l": gaps.get(shift.id, (ZERO_L, 0))[0],
                "mile_gap_nozzles": gaps.get(shift.id, (ZERO_L, 0))[1],
                "approved": closing.approved_at is not None,
                "approved_at": closing.approved_at,
                "approved_by_name": approver.full_name if approver else "",
                "approval_note": closing.approval_note,
                "note": closing.note,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Нягтлангийн хяналт — засах, батлах
# --------------------------------------------------------------------------- #
async def _closing_for(db: AsyncSession, shift_id: uuid.UUID) -> tuple[ShiftClosing, Shift]:
    shift = await shift_service.get_shift(db, shift_id)
    closing = await db.scalar(select(ShiftClosing).where(ShiftClosing.shift_id == shift_id))
    if closing is None:
        raise HTTPException(status_code=404, detail="Өдрийн хаалт олдсонгүй")
    return closing, shift


async def correct_declared_cash(
    db: AsyncSession,
    user: User,
    *,
    shift_id: uuid.UUID,
    declared_cash: Decimal,
    note: str | None = None,
) -> dict[str, Any]:
    """Тоолсон бэлэн мөнгийг засаж, кассын зөрүүг дахин бичнэ.

    Байвал зохих бэлэн мөнгө нь бодит борлуулалтаас гардаг тул хэвээр —
    зөвхөн тоолсон дүн засагдаж, зөрүүний журналын бичилт дахин үүснэ.
    Батлагдсан хаалтыг засахаас өмнө батламжийг буцаана.
    """
    closing, shift = await _closing_for(db, shift_id)
    if closing.approved_at is not None:
        raise HTTPException(
            status_code=422, detail="Батлагдсан хаалт — эхлээд батламжийг буцаана уу"
        )

    declared = q2(_d(declared_cash))
    if declared < ZERO:
        raise HTTPException(status_code=422, detail="Тоолсон дүн сөрөг байж болохгүй")

    before = {
        "declared_cash": str(_d(shift.declared_cash)),
        "cash_over_short": str(_d(shift.cash_over_short)),
    }
    expected = q2(_d(shift.expected_cash))
    over_short = q2(declared - expected)

    # Хуучин зөрүүний бичилтийг цуцалж, шинээр бичнэ (аль аль нь SHIFT эх сурвалж).
    await shift_service.repost_cash_difference(db, user, shift=shift, over_short=over_short)

    shift.declared_cash = declared
    shift.cash_over_short = over_short
    if note:
        closing.note = (note or "").strip()[:500] or closing.note
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="shift.closing_corrected",
        entity_type="shift",
        entity_id=shift.id,
        before=before,
        after={"declared_cash": str(declared), "cash_over_short": str(over_short), "note": note},
    )
    return {
        "shift_id": shift.id,
        "declared_cash": declared,
        "expected_cash": expected,
        "cash_over_short": over_short,
    }


async def set_closing_approval(
    db: AsyncSession,
    user: User,
    *,
    shift_id: uuid.UUID,
    approved: bool,
    note: str | None = None,
) -> dict[str, Any]:
    """Хаалтыг батлах / батламжийг буцаах."""
    closing, shift = await _closing_for(db, shift_id)
    if approved and closing.approved_at is not None:
        raise HTTPException(status_code=422, detail="Энэ хаалт аль хэдийн батлагдсан байна")
    if not approved and closing.approved_at is None:
        raise HTTPException(status_code=422, detail="Энэ хаалт батлагдаагүй байна")

    closing.approved_by = user.id if approved else None
    closing.approved_at = datetime.now(UTC) if approved else None
    closing.approval_note = (note or "").strip()[:500] or None
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="shift.closing_approved" if approved else "shift.closing_unapproved",
        entity_type="shift",
        entity_id=shift.id,
        after={"approved": approved, "note": note},
    )
    return {
        "shift_id": shift.id,
        "approved": approved,
        "approved_at": closing.approved_at,
        "approved_by_name": user.full_name if approved else "",
        "approval_note": closing.approval_note,
    }
