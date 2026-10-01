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
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    CashAccount,
    ContractStatus,
    CustomerType,
    ItemType,
    PaymentMethod,
    ReadingType,
    SaleType,
    ShiftStatus,
)
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
from app.services.pricing_service import effective_fuel_price, effective_product_price
from app.stationtime import STATION_TZ, day_end, day_start

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")
#: Дүнгээр оруулсан зээлийн хамгийн бага литр (1 мл) — литр 0 болж дүн алга болохгүй.
MIN_L = Decimal("0.001")


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _fmt(value: Decimal) -> str:
    """Мессежид — бүхэл бол бутархайгүй, үгүй бол 2 оронтой."""
    value = q2(value)
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}"


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
    db: AsyncSession,
    shift: Shift,
    closing_readings: dict[uuid.UUID, Decimal],
    marks: list[Any] | None = None,
) -> list[NozzleCalc]:
    """Хошуу бүрийн түгээлтийг үнийн сегментээр бодно.

    ``closing_readings`` — хаалтын миль (хошуу бүрд).  Нээлтийн заалтгүй
    хошууг алгасна (ээлжийн дундуур нэмэгдсэн насос гэх мэт).
    ``marks`` — DB-гийн оронд эдгээр үнийн тэмдэглэлээр (``nozzle_id``,
    ``reading``, ``new_price``) бодно: админы засварын урьдчилсан тооцоо.
    """
    opens = (
        await db.scalars(
            select(TotalizerReading)
            .where(
                TotalizerReading.shift_id == shift.id,
                TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
            )
            # Тогтвортой дараалал: зээлийн литрийг хуваарилах дараалал preview
            # (түгээгчийн тулгалт) ба хаалт хоёрт яг ижил байх ёстой.
            .order_by(TotalizerReading.created_at, TotalizerReading.nozzle_id)
        )
    ).all()
    if not opens:
        return []

    if marks is None:
        marks = list(
            (
                await db.scalars(
                    select(ShiftPriceMark)
                    .where(ShiftPriceMark.shift_id == shift.id)
                    .order_by(ShiftPriceMark.reading)
                )
            ).all()
        )
    else:
        marks = sorted(marks, key=lambda m: q3(_d(m.reading, ZERO_L)))
    marks_by_nozzle: dict[uuid.UUID, list[Any]] = {}
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


class _SegmentSlots:
    """Милийн зөрүүний сегментүүд — савтайгаа хамт.

    Зээлээр өгсөн литрийг эндээс «сүүлийн сегментээс эхлэн» хасаж хуваарилдаг
    тул сав бүрийн нийт зарлага = тухайн савны хошуудын милийн зөрүү гэсэн
    инвариант хадгалагдана (зээл + нэгдсэн борлуулалт хоёул зөв савнаас гарна).

    Ээлжийн дундуур үнэ өөрчлөгдсөн түлшний зээлд түгээгч «аль үнээр авсан»-ыг
    (``unit_price``) заавал сонгоно — литр зөвхөн тэр үнийн сегментүүдээс
    хасагдана. Урьд нь сүүлийн (шинэ үнийн) сегментээс эхэлж хасдаг тул үнэ
    өөрчлөгдөхөөс ӨМНӨ авсан харилцагч шинэ үнээр нэхэмжлэгдэж, түгээгчийн
    бодит бэлэн мөнгө тулгалтаас зөрдөг байв.
    """

    def __init__(self, calcs: list[NozzleCalc], fuel_names: dict[uuid.UUID, str] | None = None) -> None:
        #: (calc, seg, үлдэгдэл литр) — calc бүрийн сегментүүд дарааллаараа.
        self.slots: list[dict[str, Any]] = [
            # remaining_amount — сегментийн үлдсэн ДҮН (хөнгөлөлтгүй); зээл хасагдсаны
            # дараах үлдэгдлийг нэгдсэн борлуулалт яг энэ дүнгээр авна → дугуйлалтын
            # зөрүүгүйгээр зээл + нэгдсэн = миль×үнэ.
            {"calc": calc, "seg": seg, "remaining": seg.liters, "remaining_amount": seg.amount}
            for calc in calcs
            for seg in calc.segments
        ]
        self.fuel_names = fuel_names or {}

    def prices(self, fuel_id: uuid.UUID) -> list[Decimal]:
        """Тухайн түлшний энэ ээлжид түгээсэн үнүүд (литртэй сегментүүд), дарааллаар."""
        out: list[Decimal] = []
        for slot in self.slots:
            seg = slot["seg"]
            if slot["calc"].nozzle.fuel_id == fuel_id and seg.liters > ZERO_L and seg.price not in out:
                out.append(seg.price)
        return out

    def _label(self, fuel_id: uuid.UUID) -> str:
        return self.fuel_names.get(fuel_id) or "Түлш"

    def _price_filter(self, fuel_id: uuid.UUID, unit_price: Decimal | None) -> Decimal | None:
        """Зээлийн мөрийн үнийг шалгана — ээлжид олон үнэ байвал сонголт заавал."""
        prices = self.prices(fuel_id)
        listed = " / ".join(f"{_fmt(p)}₮" for p in prices)
        if unit_price is None:
            if len(prices) > 1:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{self._label(fuel_id)}: энэ ээлжид үнэ өөрчлөгдсөн ({listed}) — "
                        "зээлийн мөр бүрд аль үнээр (өөрчлөгдөхөөс өмнө/дараа) авсныг сонгоно уу"
                    ),
                )
            return None
        price = q2(_d(unit_price))
        if price not in prices:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{self._label(fuel_id)}: {_fmt(price)}₮ үнээр энэ ээлжид түгээгээгүй "
                    f"(ээлжийн үнэ: {listed or 'түгээлт алга'})"
                ),
            )
        return price

    def _credit_slots(self, fuel_id: uuid.UUID, unit_price: Decimal | None = None):
        """Тухайн түлшний үлдэгдэлтэй сегментүүд — СҮҮЛЭЭС нь (хамгийн сүүлийн үнэ эхэнд).

        ``unit_price`` өгвөл зөвхөн тэр үнийн сегментүүд.
        """
        for slot in reversed(self.slots):
            if (
                slot["calc"].nozzle.fuel_id == fuel_id
                and slot["remaining"] > ZERO_L
                and (unit_price is None or slot["seg"].price == unit_price)
            ):
                yield slot

    def _short(self, fuel_id: uuid.UUID, unit_price: Decimal | None, what: str) -> HTTPException:
        if unit_price is not None:
            return HTTPException(
                status_code=422,
                detail=(
                    f"{self._label(fuel_id)}: {_fmt(unit_price)}₮ үнээр түгээсэн {what} зээлд "
                    "хүрэлцэхгүй — үнийн тэмдэглэлийн миль эсвэл зээлийн үнийн сонголтыг шалгана уу"
                ),
            )
        return HTTPException(
            status_code=422,
            detail=f"Зээлээр өгсөн {what} милийн зөрүүнээс их байна — милээ шалгана уу",
        )

    @staticmethod
    def _merge(parts: list[tuple[uuid.UUID, Decimal, Decimal, Decimal]]):
        """(сав, үнэ)-ээр нэгтгэнэ — нэг сав, нэг үнэ нэг мөр: (сав, үнэ, литр, дүн)."""
        merged: dict[tuple[uuid.UUID, Decimal], list[Decimal]] = {}
        for tank_id, price, liters, amount in parts:
            row = merged.setdefault((tank_id, price), [ZERO_L, ZERO])
            row[0] = q3(row[0] + liters)
            row[1] = q2(row[1] + amount)
        return [(tank, price, row[0], row[1]) for (tank, price), row in merged.items()]

    def take_credit(
        self,
        fuel_id: uuid.UUID,
        liters: Decimal,
        unit_price: Decimal | None = None,
    ) -> list[tuple[uuid.UUID, Decimal, Decimal, Decimal]]:
        """``liters``-ийг тухайн түлшний сегментүүдээс (сүүлээс нь) хасна.

        Литр бүр ӨӨРИЙН сегментийн үнээр үнэлэгдэнэ — ингэснээр зээл +
        нэгдсэн борлуулалт = миль×үнэ яг таарна.
        """
        price_filter = self._price_filter(fuel_id, unit_price)
        need = q3(liters)
        parts: list[tuple[uuid.UUID, Decimal, Decimal, Decimal]] = []
        for slot in self._credit_slots(fuel_id, price_filter):
            if need <= ZERO_L:
                break
            price = slot["seg"].price
            take = min(slot["remaining"], need)
            amount = slot["remaining_amount"] if take >= slot["remaining"] else q2(take * price)
            slot["remaining"] = q3(slot["remaining"] - take)
            slot["remaining_amount"] = q2(slot["remaining_amount"] - amount)
            need = q3(need - take)
            parts.append((slot["calc"].nozzle.tank_id, price, take, amount))
        if need > ZERO_L:
            raise self._short(fuel_id, price_filter, "литр")
        return self._merge(parts)

    def take_credit_amount(
        self,
        fuel_id: uuid.UUID,
        amount: Decimal,
        unit_price: Decimal | None = None,
    ) -> list[tuple[uuid.UUID, Decimal, Decimal, Decimal]]:
        """Дүнгээр оруулсан зээл — ``amount`` нь колонкийн дэлгэц дээрх дүн.

        Литр = дүн ÷ сегментийн үнэ; оруулсан дүн яг хадгалагдана.
        """
        price_filter = self._price_filter(fuel_id, unit_price)
        left = q2(amount)
        parts: list[tuple[uuid.UUID, Decimal, Decimal, Decimal]] = []
        for slot in self._credit_slots(fuel_id, price_filter):
            if left <= ZERO:
                break
            price = slot["seg"].price
            capacity = slot["remaining_amount"]
            if left >= capacity:
                take, gross = slot["remaining"], capacity
            else:
                take = min(max(q3(left / price), MIN_L), slot["remaining"])
                gross = capacity if take >= slot["remaining"] else left
            slot["remaining"] = q3(slot["remaining"] - take)
            slot["remaining_amount"] = q2(slot["remaining_amount"] - gross)
            left = q2(left - gross)
            parts.append((slot["calc"].nozzle.tank_id, price, take, gross))
        if left > ZERO:
            raise self._short(fuel_id, price_filter, "дүн")
        return self._merge(parts)


async def _next_contract_no(db: AsyncSession, prefix: str) -> str:
    """``ЗЭ-20260912-01`` маягийн давхардахгүй гэрээний дугаар."""
    pattern = f"{prefix}-%"
    count = await db.scalar(
        select(func.count()).select_from(Contract).where(Contract.contract_no.like(pattern))
    )
    seq = int(count or 0) + 1
    while True:
        candidate = f"{prefix}-{seq:02d}"
        clash = await db.scalar(
            select(func.count()).select_from(Contract).where(Contract.contract_no == candidate)
        )
        if not clash:
            return candidate
        seq += 1


async def _contract_for_customer(
    db: AsyncSession, user: User, customer_id: uuid.UUID
) -> Contract:
    """Бүртгэлтэй боловч гэрээгүй харилцагч — идэвхтэй гэрээг нь олно, үгүй бол нээнэ.

    Харилцагч цэснээс гэрээгүйгээр үүсгэсэн хүнд түгээгч зээлээр өгөх, төлбөр
    авахад гэрээг автоматаар (ЗЭ-YYYYMMDD-NN) нээж, лимитийг зээлийн дүнгээр
    тогтооно (нягтлан дараа нь засна).
    """
    customer = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.is_active.is_(True))
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй эсвэл идэвхгүй")
    contract = await db.scalar(
        select(Contract)
        .where(Contract.customer_id == customer.id, Contract.status == str(ContractStatus.ACTIVE))
        .order_by(Contract.created_at)
    )
    if contract is not None:
        return contract
    today = datetime.now(STATION_TZ).date()
    contract = Contract(
        customer=customer,
        contract_no=await _next_contract_no(db, f"ЗЭ-{today:%Y%m%d}"),
        credit_limit=q2(_d(customer.credit_limit)),
        balance=ZERO,
        billing_day=1,
        status=str(ContractStatus.ACTIVE),
    )
    db.add(contract)
    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action="contract.create",
        entity_type="contract",
        entity_id=contract.id,
        after={"contract_no": contract.contract_no, "customer_id": str(customer.id), "source": "daily_close"},
    )
    return contract


async def _contract_for_new_customer(
    db: AsyncSession,
    user: User,
    payload: Any,
    cache: dict[tuple[str, str], Contract],
    branch_id: uuid.UUID | None = None,
) -> Contract:
    """Хаалтын үед шинэ харилцагч + гэрээ үүсгэнэ (эсвэл байгааг нь олно).

    * Нэг хаалтад нэг харилцагчийг олон мөрөнд оруулсан бол нэг л гэрээ.
    * Утас (эсвэл регистр) бүртгэлтэй идэвхтэй харилцагчтай таарвал шинээр
      үүсгэхгүй — түүний идэвхтэй гэрээг ашиглана, гэрээгүй бол нээнэ.
    """
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Шинэ харилцагчийн нэр хоосон байж болохгүй")
    last_name = (payload.last_name or "").strip() or None
    phone = (payload.phone or "").strip() or None
    register_no = (payload.register_no or "").strip() or None
    key = (name.lower(), phone or register_no or "")
    cached = cache.get(key)
    if cached is not None:
        return cached

    customer: Customer | None = None
    if register_no:
        customer = await db.scalar(
            select(Customer).where(Customer.register_no == register_no, Customer.is_active.is_(True))
        )
    if customer is None and phone:
        customer = await db.scalar(
            select(Customer).where(Customer.phone == phone, Customer.is_active.is_(True))
        )

    created_customer = customer is None
    if customer is None:
        customer = Customer(
            credit_unlimited=True,
            branch_id=branch_id,
            last_name=last_name,
            name=name,
            register_no=register_no,
            phone=phone,
            credit_limit=q2(_d(payload.credit_limit)),
            type=str(CustomerType.INDIVIDUAL if last_name or not register_no else CustomerType.B2B),
            is_active=True,
        )
        db.add(customer)
        await db.flush()
        await audit(
            db,
            user_id=user.id,
            action="customer.create",
            entity_type="customer",
            entity_id=customer.id,
            after={"name": name, "phone": phone, "source": "daily_close"},
        )

    contract = None
    if not created_customer:
        contract = await db.scalar(
            select(Contract)
            .where(Contract.customer_id == customer.id, Contract.status == str(ContractStatus.ACTIVE))
            .order_by(Contract.created_at)
        )
    if contract is None:
        today = datetime.now(STATION_TZ).date()
        contract = Contract(
            customer=customer,
            contract_no=await _next_contract_no(db, f"ЗЭ-{today:%Y%m%d}"),
            credit_limit=q2(_d(payload.credit_limit)),
            balance=ZERO,
            billing_day=1,
            status=str(ContractStatus.ACTIVE),
        )
        db.add(contract)
        await db.flush()
        await audit(
            db,
            user_id=user.id,
            action="contract.create",
            entity_type="contract",
            entity_id=contract.id,
            after={"contract_no": contract.contract_no, "customer_id": str(customer.id), "source": "daily_close"},
        )

    cache[key] = contract
    return contract


async def product_price_chains(
    db: AsyncSession, shift: Shift, product_ids: set[uuid.UUID] | None = None
) -> dict[uuid.UUID, dict[str, Any]]:
    """Ээлжийн хугацаанд үнэ нь өөрчлөгдсөн бараанууд — үеүдээр (өмнө/дараа).

    Батлагдаж хэрэгжсэн үнийн өөрчлөлтийн хуучин/шинэ үнээс сэргээнэ: салбарын
    тусгай үнийн өөрчлөлт, эсвэл салбарт тусгай үнэгүй үед суурь үнийн
    өөрчлөлт. Зөвхөн 2+ өөр үнэтэй барааг буцаана:
    ``{product_id: {"product_id", "name", "current", "periods": [{"price", "from", "until"}]}}``.
    """
    from app.enums import ApprovalStatus  # noqa: PLC0415
    from app.models.approval import PriceChange  # noqa: PLC0415
    from app.services.pricing_service import product_price_map  # noqa: PLC0415

    if product_ids is not None and not product_ids:
        return {}
    window_end = shift.closed_at or datetime.now(UTC)
    branch_cond = (
        or_(PriceChange.branch_id == shift.branch_id, PriceChange.branch_id.is_(None))
        if shift.branch_id is not None
        else PriceChange.branch_id.is_(None)
    )
    stmt = (
        select(PriceChange)
        .where(
            PriceChange.product_id.is_not(None),
            PriceChange.status == str(ApprovalStatus.APPROVED),
            PriceChange.applied_at.is_not(None),
            PriceChange.applied_at >= shift.opened_at,
            PriceChange.applied_at <= window_end,
            branch_cond,
        )
        .order_by(PriceChange.applied_at)
    )
    if product_ids is not None:
        stmt = stmt.where(PriceChange.product_id.in_(list(product_ids)))
    changes = (await db.scalars(stmt)).all()
    if not changes:
        return {}
    overrides = await product_price_map(db, shift.branch_id)
    by_product: dict[uuid.UUID, list[Any]] = {}
    for pc in changes:
        by_product.setdefault(pc.product_id, []).append(pc)
    products = {
        p.id: p
        for p in (await db.scalars(select(Product).where(Product.id.in_(list(by_product))))).all()
    }

    out: dict[uuid.UUID, dict[str, Any]] = {}
    for pid, rows in by_product.items():
        product = products.get(pid)
        if product is None:
            continue
        branch_rows = [r for r in rows if r.branch_id is not None]
        # Суурь үнийн өөрчлөлт салбарт тусгай үнэгүй үед л үйлчилнэ (тусгай үнэ
        # дараа нь энэ ээлжийн дотор тавигдсан бол өмнөх нь суурь үнээр явсан).
        relevant = [
            r
            for r in rows
            if r.branch_id is not None
            or pid not in overrides
            or any(b.applied_at > r.applied_at for b in branch_rows)
        ]
        if not relevant:
            continue
        periods: list[dict[str, Any]] = [
            {"price": q2(_d(relevant[0].old_price)), "from": None, "until": relevant[0].applied_at}
        ]
        for i, r in enumerate(relevant):
            until = relevant[i + 1].applied_at if i + 1 < len(relevant) else None
            periods.append({"price": q2(_d(r.new_price)), "from": r.applied_at, "until": until})
        merged: list[dict[str, Any]] = []
        for per in periods:
            if merged and merged[-1]["price"] == per["price"]:
                merged[-1]["until"] = per["until"]
            else:
                merged.append(dict(per))
        current = overrides.get(pid, q2(_d(product.price)))
        if current not in {per["price"] for per in merged}:
            merged.append({"price": current, "from": None, "until": None})
        if len({per["price"] for per in merged}) < 2:
            continue
        out[pid] = {"product_id": pid, "name": product.name_mn, "current": current, "periods": merged}
    return out


async def _goods_unit_price(
    db: AsyncSession,
    shift: Shift,
    product: Product,
    raw_price: Any,
    chains: dict[uuid.UUID, dict[str, Any]],
) -> Decimal:
    """Хаалтын барааны мөрийн нэгж үнэ — салбарын мөрдөж буй үнэ.

    Ээлжийн дундуур үнэ өөрчлөгдсөн барааг түгээгч «аль үнээр зарсан»-аар
    сонгоно (өмнөх/шинэ); сонголт ээлжид мөрдсөн үнүүдийн нэг байх ёстой.
    Урьд нь суурь үнээр (салбарын тусгай үнийг үл тоон) бичигдэж, зээлийн
    бараа төлбөрийн дүнтэй зөрж хаалт унадаг байв.
    """
    current = await effective_product_price(db, product, shift.branch_id)
    chain = chains.get(product.id)
    allowed = [per["price"] for per in chain["periods"]] if chain else [current]
    if current not in allowed:
        allowed.append(current)
    listed = " / ".join(f"{_fmt(p)}₮" for p in allowed)
    if raw_price is None:
        if len(allowed) > 1:
            raise HTTPException(
                status_code=422,
                detail=f"{product.name_mn}: энэ ээлжид үнэ өөрчлөгдсөн ({listed}) — аль үнээр зарсныг сонгоно уу",
            )
        return current
    price = q2(_d(raw_price))
    if price not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"{product.name_mn}: {_fmt(price)}₮ үнэ энэ ээлжид мөрдөгдөөгүй (ээлжийн үнэ: {listed})",
        )
    return price


async def _create_credit_sales(
    db: AsyncSession,
    user: User,
    shift: Shift,
    credit_lines: list[Any],
    slots: _SegmentSlots,
    new_by_key: dict[tuple[str, str], Contract] | None = None,
    chains: dict[uuid.UUID, dict[str, Any]] | None = None,
) -> tuple[Decimal, list[uuid.UUID], Decimal]:
    """Зээлийн (гэрээт) борлуулалтуудыг үүсгэнэ.

    Түлшний литрийг милийн зөрүүний сегментүүдээс хуваарилж авдаг тул сав
    хэд байхаас үл хамааран зөв савнаас хасагдана.

    Буцаана: (харилцагчдад нэхэмжилсэн нийт дүн, sale_id-ууд, зээлийн түлшний дүн).
    """
    total = ZERO
    fuel_gross = ZERO
    sale_ids: list[uuid.UUID] = []
    chains = chains or {}

    #: Энэ хаалтад шинээр нээсэн гэрээнүүд → лимит автоматаар (True) эсвэл
    #: түгээгчийн оруулсан лимит (False — хэтэрвэл ердийн лимитийн алдаа).
    opened: dict[uuid.UUID, bool] = {}
    if new_by_key is None:
        new_by_key = {}

    for line in credit_lines or []:
        new_customer = getattr(line, "new_customer", None)
        if new_customer is not None:
            contract = await _contract_for_new_customer(
                db, user, new_customer, new_by_key, branch_id=shift.branch_id
            )
            if contract.id not in opened:
                opened[contract.id] = q2(_d(new_customer.credit_limit)) <= ZERO
        elif getattr(line, "customer_id", None) is not None:
            # Гэрээгүй бүртгэлтэй харилцагч — гэрээ нээгдэж, лимит нь зээлээ багтаана.
            contract = await _contract_for_customer(db, user, line.customer_id)
            if contract.id not in opened:
                opened[contract.id] = True
        else:
            contract = await db.scalar(select(Contract).where(Contract.id == line.contract_id))
            if contract is None:
                raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
        items: list[SaleItemIn] = []
        line_total = ZERO
        for item in line.items:
            if item.fuel_id is not None:
                # Литр (эсвэл дүн)-ийг милийн зөрүүний сегментүүдээс зөв савнаас
                # нь, ТЭР сегментийн үнээр авна (хаалтын мөчийн жагсаалтын үнээр биш).
                unit_price = getattr(item, "unit_price", None)
                if item.amount is not None and _d(item.amount) > ZERO:
                    splits = slots.take_credit_amount(item.fuel_id, q2(_d(item.amount)), unit_price)
                elif item.qty is not None and _d(item.qty) > ZERO_L:
                    splits = slots.take_credit(item.fuel_id, q3(_d(item.qty)), unit_price)
                else:
                    raise HTTPException(
                        status_code=422, detail="Зээлийн түлшний литр эсвэл дүнг оруулна уу"
                    )
                for tank_id, price, liters, amount in splits:
                    if liters <= ZERO_L:
                        continue
                    fuel_gross = q2(fuel_gross + amount)
                    items.append(
                        SaleItemIn(
                            item_type=ItemType.FUEL,
                            fuel_id=item.fuel_id,
                            tank_id=tank_id,
                            qty=liters,
                            unit_price=price,
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
                unit = await _goods_unit_price(
                    db, shift, product, getattr(item, "unit_price", None), chains
                )
                amount = q2(qty * unit)
                items.append(
                    SaleItemIn(
                        item_type=ItemType.PRODUCT,
                        product_id=product.id,
                        qty=qty,
                        unit_price=unit,
                        amount=amount,
                    )
                )
                line_total = q2(line_total + amount)
            else:
                raise HTTPException(status_code=422, detail="Зээлийн мөр хоосон байна")

        if not items:
            continue

        # Шинэ гэрээний лимит: түгээгч лимит оруулаагүй бол хаалтын үед өгсөн
        # зээлээ багтаана; оруулсан бол түүнийг хадгална (хэтэрвэл 422).
        if opened.get(contract.id):
            needed = q2(_d(contract.balance) + line_total)
            if q2(_d(contract.credit_limit)) < needed:
                contract.credit_limit = needed
                customer = await db.scalar(select(Customer).where(Customer.id == contract.customer_id))
                if customer is not None and q2(_d(customer.credit_limit)) < needed:
                    customer.credit_limit = needed
            await db.flush()

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
        sale = await sale_service.create_sale(db, user, payload, shift=shift, exact_amounts=True)
        sale_ids.append(sale.id)
        total = q2(total + line_total)

    return total, sale_ids, fuel_gross


async def _default_transfer_account(db: AsyncSession, branch_id: uuid.UUID | None) -> uuid.UUID | None:
    """Шилжүүлгийн орлого АЛЬ банкны дансанд орсон бэ — санхүүгийн хэмжүүр.

    Түгээгч хаалт дээр данс сонгоогүй бол салбарын харилцах данс, тэр ч
    байхгүй бол шимтгэлийн анхдагч данс. Урьд нь 1110 дансны мөр
    ``dim_bank_account_id``-гүй үлдэж, банкны данс бүрийн үлдэгдэл буруу
    гардаг байв.
    """
    from app.models.bank import BankAccount
    from app.services import bank_service

    if branch_id is not None:
        account = await db.scalar(
            select(BankAccount)
            .where(BankAccount.branch_id == branch_id, BankAccount.is_active.is_(True))
            .order_by(BankAccount.sort_order)
            .limit(1)
        )
        if account is not None:
            return account.id
    fallback = await bank_service.fee_default_account(db)
    return fallback.id if fallback else None


def _noncash_payments(
    total: Decimal,
    card_amount: Decimal,
    transfer_amount: Decimal,
    bank_account_id: uuid.UUID | None = None,
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
            PaymentIn(
                method=PaymentMethod.TRANSFER,
                amount=transfer,
                ref_no="TRANSFER",
                bank_account_id=bank_account_id,
            )
        )
    cash = q2(total - card - transfer)
    if cash > ZERO:
        payments.append(PaymentIn(method=PaymentMethod.CASH, amount=cash, received=cash))
    return payments, card, transfer


async def _create_oil_sale(
    db: AsyncSession,
    user: User,
    shift: Shift,
    oil_lines: list[Any],
    *,
    chains: dict[uuid.UUID, dict[str, Any]],
    card_amount: Decimal,
    transfer_amount: Decimal = ZERO,
    transfer_bank_account_id: uuid.UUID | None = None,
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
        unit = await _goods_unit_price(db, shift, product, line.unit_price, chains)
        amount = q2(qty * unit)
        items.append(
            SaleItemIn(
                item_type=ItemType.PRODUCT, product_id=product.id, qty=qty, unit_price=unit, amount=amount
            )
        )
        total = q2(total + amount)

    if total <= ZERO:
        return ZERO, ZERO, ZERO, None

    payments, card, transfer = _noncash_payments(
        total, card_amount, transfer_amount, transfer_bank_account_id
    )

    sale = await sale_service.create_sale(
        db,
        user,
        SaleCreate(sale_type=SaleType.STORE, items=items, payments=payments),
        shift=shift,
        exact_amounts=True,
    )
    return total, card, transfer, sale.id


async def _create_fuel_sale(
    db: AsyncSession,
    user: User,
    shift: Shift,
    slots: _SegmentSlots,
    *,
    card_amount: Decimal,
    transfer_amount: Decimal = ZERO,
    transfer_bank_account_id: uuid.UUID | None = None,
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
        # Сегментийн үлдсэн дүн — зээлд очсон дүнг хассан яг үлдэгдэл.
        amount = q2(slot["remaining_amount"])
        items.append(
            SaleItemIn(
                item_type=ItemType.FUEL,
                fuel_id=calc.nozzle.fuel_id,
                nozzle_id=calc.nozzle.id,
                tank_id=calc.nozzle.tank_id,
                qty=liters,
                unit_price=seg.price,
                amount=amount,
            )
        )
        total = q2(total + amount)

    if total <= ZERO:
        return ZERO, ZERO, ZERO, None

    payments, card, transfer = _noncash_payments(
        total, card_amount, transfer_amount, transfer_bank_account_id
    )

    sale = await sale_service.create_sale(
        db,
        user,
        SaleCreate(sale_type=SaleType.FUEL, items=items, payments=payments),
        shift=shift,
        exact_amounts=True,
    )
    return total, card, transfer, sale.id


async def _day_cash(db: AsyncSession, shift: Shift) -> dict[str, Decimal]:
    """Хаалтаас өмнө ээлжийн кассад аль хэдийн нөлөөлсөн гүйлгээ.

    * ``day_cash_sales`` — өдрийн турш бүртгэсэн бэлэн борлуулалт (ихэвчлэн 0);
    * ``refunds_cash`` — ээлжийн хугацаанд батлагдсан бэлэн буцаалт;
    * ``other_cash`` — түгээгчийн өдрийн турш хийсэн бусад кассын гүйлгээ
      (хаалтын цонхоос гадуур бүртгэсэн өглөг төлөлт, зарлага гэх мэт).

    Түгээгчийн тулгалт эдгээрийг оруулснаар серверийн «байвал зохих» дүнтэй
    яг таарна; урьд нь тулгалтад ороогүй тул тайланд зөрүү гардаг байв.
    """
    cash_sales, refunds_cash = await shift_service._cash_flows(db, shift)
    other_cash = await shift_service._other_cash_movement(db, shift)
    return {"day_cash_sales": cash_sales, "refunds_cash": refunds_cash, "other_cash": other_cash}


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
        **(await _day_cash(db, shift)),
        "price_alerts": await price_alerts(db, shift),
    }


async def price_options(db: AsyncSession, shift: Shift) -> dict[str, Any]:
    """Ээлжийн үнийн сонголтууд — зээл, барааны мөрөнд «аль үнээр» сонгуулахад.

    * ``fuels`` — түлш бүрийн энэ ээлжийн үнүүд: хошуудын нээлтийн үнэ +
      үнийн тэмдэглэлүүдийн шинэ үнэ (2+ үнэтэй түлш л);
    * ``products`` — ээлжийн хугацаанд үнэ нь өөрчлөгдсөн бараанууд.
    """
    opens = (
        await db.scalars(
            select(TotalizerReading)
            .where(
                TotalizerReading.shift_id == shift.id,
                TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
            )
            .order_by(TotalizerReading.created_at, TotalizerReading.nozzle_id)
        )
    ).all()
    marks = (
        await db.scalars(
            select(ShiftPriceMark)
            .where(ShiftPriceMark.shift_id == shift.id)
            .order_by(ShiftPriceMark.created_at, ShiftPriceMark.reading)
        )
    ).all()
    nozzle_ids = {o.nozzle_id for o in opens} | {m.nozzle_id for m in marks}
    nozzles = {
        n.id: n
        for n in (
            await db.scalars(select(PumpNozzle).where(PumpNozzle.id.in_(list(nozzle_ids))))
        ).all()
    } if nozzle_ids else {}

    fuels: dict[uuid.UUID, dict[str, Any]] = {}

    def add(nozzle: PumpNozzle | None, price: Decimal, kind: str, at: Any = None, reading: Any = None) -> None:
        if nozzle is None or price <= ZERO:
            return
        row = fuels.setdefault(
            nozzle.fuel_id,
            {"fuel_id": nozzle.fuel_id, "name": nozzle.fuel.name_mn if nozzle.fuel else "", "prices": []},
        )
        if any(p["price"] == price for p in row["prices"]):
            return
        row["prices"].append({"price": price, "kind": kind, "at": at, "reading": reading})

    for o in opens:
        nozzle = nozzles.get(o.nozzle_id)
        add(nozzle, q2(_d(o.price_per_liter)), "open")
    for m in marks:
        add(nozzles.get(m.nozzle_id), q2(_d(m.new_price)), "mark", m.created_at, q3(_d(m.reading, ZERO_L)))

    chains = await product_price_chains(db, shift)
    return {
        "fuels": [f for f in fuels.values() if len(f["prices"]) > 1],
        "products": list(chains.values()),
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

    # Үнэ батлагдсан ч үнийн тэмдэглэл ороогүй хошуу байвал хаахгүй: тэр
    # хошууны шинэ үнээр түгээсэн литр хуучин үнээр бодогдож, зөрүү нь
    # кассын дутагдал/илүүдэл болж харагдана.
    alerts = [a for a in await price_alerts(db, shift) if a["blocking"]]
    if alerts:
        listed = "; ".join(
            f"{a['pump_name']} · хошуу {a['nozzle_number']} ({a['fuel_name']}: "
            f"{_fmt(a['used_price'])}₮ → {_fmt(a['current_price'])}₮)"
            for a in alerts
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Үнэ батлагдсан ч үнийн тэмдэглэл ороогүй хошуу байна: {listed}. "
                "Хошуу бүрд шинэ үнэ эхэлсэн милийг тэмдэглэнэ үү (колонкийн үнийг "
                "өнөөдөр солиогүй бол хаалтын милээр) — дараа нь дахин илгээнэ үү."
            ),
        )

    # Түгээгч «Шалгах» алхамд харсан тооцоо хаах мөчид өөрчлөгдсөн бол (өөр
    # хүн буцаалт баталсан, эхний үлдэгдэл зассан гэх мэт) хаахгүй — тулгалтыг
    # шинэчилж дахин харуулна. Урьд нь түгээгчийн «зөрүүгүй» тулгалт тайланд
    # зөрүүтэй болж гардаг байв.
    mile_total = q2(sum((c.amount for c in calcs), ZERO))
    day = await _day_cash(db, shift)
    server_view = {
        "preview_fuel_total": ("миль×үнэ", mile_total),
        "preview_opening_cash": ("эхний үлдэгдэл", q2(_d(shift.opening_cash))),
        "preview_refunds_cash": ("бэлэн буцаалт", day["refunds_cash"]),
        "preview_other_cash": ("бусад кассын гүйлгээ", day["other_cash"]),
        "preview_day_cash_sales": ("өдрийн бэлэн борлуулалт", day["day_cash_sales"]),
    }
    changed = []
    for key, (label, value) in server_view.items():
        seen = getattr(payload, key, None)
        if seen is not None and q2(_d(seen)) != value:
            changed.append(f"{label} {_fmt(_d(seen))}₮ → {_fmt(value)}₮")
    if changed:
        raise HTTPException(
            status_code=409,
            detail=(
                "Тулгалтыг шалгаснаас хойш тооцоо өөрчлөгдсөн: " + "; ".join(changed)
                + ". Тулгалтыг шинэчилсэн — дахин шалгаад илгээнэ үү."
            ),
        )

    settlement_vat = q2(_d(payload.settlement_vat))
    settlement_novat = q2(_d(payload.settlement_novat))
    # Терминалын ганц дүн (НӨАТ-тэй/гүй хуваахгүй) ирвэл түүнийг ашиглана.
    single_settlement = getattr(payload, "settlement_total", None)
    if single_settlement is not None:
        settlement_vat = q2(_d(single_settlement))
        settlement_novat = ZERO
    transfer_total = q2(_d(getattr(payload, "transfer_total", ZERO)))
    if settlement_vat < ZERO or settlement_novat < ZERO or transfer_total < ZERO:
        raise HTTPException(status_code=422, detail="Тушаалтын дүн сөрөг байж болохгүй")
    settlement_total = q2(settlement_vat + settlement_novat)

    # Түгээгчийн мэдүүлсэн терминал/шилжүүлгийн дүнд харилцагчийн ӨГЛӨГ ТӨЛӨЛТ
    # (карт, шилжүүлгээр төлсөн) багтсан байдаг — тэр хэсэг борлуулалт биш
    # авлагын төлбөр тул түлш/барааны борлуулалтад хуваарилахгүй.
    ar_card = ZERO
    ar_transfer = ZERO
    for pay in payload.ar_payments or []:
        method = str(getattr(pay, "method", None) or "cash")
        if method == "card":
            ar_card = q2(ar_card + q2(_d(pay.amount)))
        elif method == "transfer":
            ar_transfer = q2(ar_transfer + q2(_d(pay.amount)))
    if ar_card > settlement_total:
        raise HTTPException(
            status_code=422,
            detail="Өглөг төлөлтийн терминалын дүн тушаасан терминалын нийт дүнгээс их байна",
        )
    if ar_transfer > transfer_total:
        raise HTTPException(
            status_code=422,
            detail="Өглөг төлөлтийн шилжүүлгийн дүн тушаасан шилжүүлгийн нийт дүнгээс их байна",
        )
    sales_card = q2(settlement_total - ar_card)
    sales_transfer = q2(transfer_total - ar_transfer)

    # Миль×үнэ-ээр бодогдсон нийт түгээлт (``mile_total``, дээр) — тайланд ЭНЭ
    # дүн харагдана (зээлээр өгсөн литр ч түгээгдсэн тул хасахгүй).

    # Сегментүүдийг нэг санд хийнэ: зээлийн литр эндээс зөв савнаас нь
    # хуваарилагдаж, үлдэгдэл нь нэгдсэн борлуулалт болно.
    slots = _SegmentSlots(
        calcs, {c.nozzle.fuel_id: c.nozzle.fuel.name_mn for c in calcs if c.nozzle.fuel is not None}
    )
    # Ээлжийн дундуур үнэ нь өөрчлөгдсөн бараа — мөр бүр аль үнээр зарсан.
    chains = await product_price_chains(db, shift)

    # --- 1. Зээлийн борлуулалтууд ---
    #: Энэ хаалтад шинээр үүсгэсэн харилцагчдын гэрээ — «Өглөг төлөлт» алхамд
    #: тэр хүнээс мөнгө авсан бол нэг л гэрээ рүү бүртгэнэ.
    new_customers: dict[tuple[str, str], Contract] = {}
    credit_total, credit_sale_ids, credit_fuel_gross = await _create_credit_sales(
        db, user, shift, payload.credit_lines, slots, new_by_key=new_customers, chains=chains
    )

    # Шилжүүлгийн орлого аль банкны дансанд орсон бэ — түгээгч сонгоогүй бол
    # салбарын харилцах данс (эсвэл шимтгэлийн анхдагч данс).
    transfer_account = payload.transfer_bank_account_id or await _default_transfer_account(
        db, shift.branch_id
    )

    # --- 2. Нэгдсэн түлшний борлуулалт (карт/шилжүүлэг эхлээд түлшинд) ---
    fuel_total, fuel_card, fuel_transfer, fuel_sale_id = await _create_fuel_sale(
        db,
        user,
        shift,
        slots,
        card_amount=sales_card,
        transfer_amount=sales_transfer,
        transfer_bank_account_id=transfer_account,
    )

    # --- 3. Тос, барааны борлуулалт (үлдсэн карт/шилжүүлгээр) ---
    card_left = q2(sales_card - fuel_card)
    transfer_left = q2(sales_transfer - fuel_transfer)
    oil_total, oil_card, oil_transfer, oil_sale_id = await _create_oil_sale(
        db,
        user,
        shift,
        payload.oil_lines,
        chains=chains,
        card_amount=card_left,
        transfer_amount=transfer_left,
        transfer_bank_account_id=transfer_account,
    )
    card_left = q2(card_left - oil_card)
    transfer_left = q2(transfer_left - oil_transfer)
    if card_left > ZERO or transfer_left > ZERO:
        # Тоотой тайлбар — түгээгч аль дүн зөрснийг шууд харна.
        available = q2(fuel_total + oil_total)
        given = q2(sales_card + sales_transfer)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Тушаасан терминал + шилжүүлэг {given:,.0f}₮ (өглөг төлөлтийн {q2(ar_card + ar_transfer):,.0f}₮-ийг "
                f"хассан) нь өдрийн бэлэн бус борлуулалтаас их байна: түлш (миль×үнэ − зээлээр өгсөн) "
                f"{fuel_total:,.0f}₮ + тос, бараа {oil_total:,.0f}₮ = {available:,.0f}₮; илүү {q2(given - available):,.0f}₮. "
                "Шалгах: өглөг төлөлтийн мөрүүдийн төлбөрийн хэлбэр (терминал/шилжүүлгээр ирсэн бол «Бэлэн мөнгө» биш), "
                "терминал/шилжүүлгийн дүнд өнөөдрийн борлуулалтаас өөр мөнгө орсон эсэх, зээлийн литр."
            ),
        )

    # --- 4. Авлагын төлбөрүүд (өглөг) ---
    ar_total = ZERO
    for pay in payload.ar_payments or []:
        # Бэлэн → касс, карт/шилжүүлэг → банк. Хэлбэрийг тэмдэглэлд үлдээнэ.
        method = str(pay.method or "cash")
        received_to = str(CashAccount.CASH) if method == "cash" else str(CashAccount.BANK)
        method_name = {"cash": "бэлэн", "card": "карт", "transfer": "шилжүүлэг"}.get(method, method)
        contract_id = pay.contract_id
        if getattr(pay, "new_customer", None) is not None:
            # Зээлийн алхамд нэмсэн шинэ харилцагч — ижил нэр/утсаар нэг гэрээ.
            contract = await _contract_for_new_customer(
                db, user, pay.new_customer, new_customers, branch_id=shift.branch_id
            )
            contract_id = contract.id
        elif getattr(pay, "customer_id", None) is not None:
            contract_id = (await _contract_for_customer(db, user, pay.customer_id)).id
        await contract_service.record_payment(
            db,
            user,
            contract_id=contract_id,
            amount=q2(_d(pay.amount)),
            received_to=received_to,
            note=f"Өдрийн хаалт — {method_name}" + (f" · {pay.note}" if pay.note else ""),
        )
        ar_total = q2(ar_total + q2(_d(pay.amount)))

    # --- 5. Зарлагууд ---
    expense_total = ZERO
    for exp in payload.expenses or []:
        # Түгээгч тушаалтын сувгаар нь заана: бэлэн / банкны терминал / шилжүүлэг.
        # Терминал, шилжүүлэг хоёулаа харилцахаас гардаг тул «bank»; хэлбэрийг нь
        # тайлбарт үлдээнэ.
        raw_method = str(exp.payment_method or "cash")
        method = "cash" if raw_method == "cash" else "bank"
        method_label = {"card": "банкны терминал", "transfer": "шилжүүлэг"}.get(raw_method)
        description = (exp.description or "").strip() or "Өдрийн хаалт"
        if method_label:
            description = f"{description} · {method_label}"
        await expense_service.create_expense(
            db,
            user,
            account_code=exp.account_code,
            amount=q2(_d(exp.amount)),
            payment_method=method,
            description=description[:255],
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
        # Түгээгч юу бөглөж, ямар тулгалт харсныг хадгална — дараа нь тайланд
        # серверийн бүртгэлтэй харьцуулж, зөрүү хаанаас гарсныг олно.
        close_input={
            "payload": payload.model_dump(mode="json", exclude={"client_snapshot"})
            if hasattr(payload, "model_dump")
            else None,
            "client": getattr(payload, "client_snapshot", None),
        },
    )
    db.add(closing)
    # Өдрийн турш бөглөсөн ноорог хаалтад орсон тул цэвэрлэнэ.
    shift.close_draft = None
    shift.close_draft_at = None
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
            "credit_fuel_gross": str(credit_fuel_gross),
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


async def price_alerts(db: AsyncSession, shift: Shift) -> list[dict[str, Any]]:
    """Нээлттэй ээлжид үнэ батлагдсан ч тэмдэглэл ороогүй хошуунууд.

    Ээлж нээхэд хошуу бүрийн үнэ хөлддөг; ээлжийн дундуур батлагдсан үнэ зөвхөн
    түгээгчийн «үнийн тэмдэглэл»-ээр миль×үнэ тооцоонд орно. Хошууны одоо
    бодогдож буй үнэ (сүүлийн тэмдэглэл, эсвэл нээлтийн үнэ) мөрдөж буй үнээс
    өөр бол анхааруулна — тэмдэглэлгүй бол үнийн зөрүү кассын зөрүү болно.
    """
    if shift.status != str(ShiftStatus.OPEN):
        return []
    opens = (
        await db.scalars(
            select(TotalizerReading).where(
                TotalizerReading.shift_id == shift.id,
                TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
                TotalizerReading.price_per_liter.is_not(None),
            )
        )
    ).all()
    if not opens:
        return []
    marks = (
        await db.scalars(
            select(ShiftPriceMark)
            .where(ShiftPriceMark.shift_id == shift.id)
            .order_by(ShiftPriceMark.reading, ShiftPriceMark.created_at)
        )
    ).all()
    last_mark: dict[uuid.UUID, ShiftPriceMark] = {}
    for mark in marks:
        last_mark[mark.nozzle_id] = mark

    rows = (
        await db.execute(
            select(PumpNozzle, Pump)
            .join(Pump, PumpNozzle.pump_id == Pump.id)
            .where(PumpNozzle.id.in_([o.nozzle_id for o in opens]))
        )
    ).all()
    pairs = {nozzle.id: (nozzle, pump) for nozzle, pump in rows}
    effective: dict[uuid.UUID, Decimal] = {}
    overridden: dict[uuid.UUID, bool] = {}

    from app.services.pricing_service import fuel_price_override  # noqa: PLC0415

    from app.enums import ApprovalStatus  # noqa: PLC0415
    from app.models.approval import PriceChange  # noqa: PLC0415

    out: list[dict[str, Any]] = []
    for open_row in opens:
        pair = pairs.get(open_row.nozzle_id)
        if pair is None:
            continue
        nozzle, pump = pair
        fuel = nozzle.fuel
        if fuel is None:
            continue
        if fuel.id not in effective:
            effective[fuel.id] = await effective_fuel_price(db, fuel, shift.branch_id)
            overridden[fuel.id] = (
                await fuel_price_override(db, fuel.id, shift.branch_id)
            ) is not None
        now_price = effective[fuel.id]
        mark = last_mark.get(nozzle.id)
        used_price = q2(_d(mark.new_price)) if mark is not None else q2(_d(open_row.price_per_liter))
        if used_price == now_price:
            continue
        # Салбарын тусгай үнэтэй бол суурь үнийн өөрчлөлт энэ салбарт хамаарахгүй.
        scope = (
            PriceChange.branch_id == shift.branch_id
            if overridden[fuel.id]
            else (PriceChange.branch_id == shift.branch_id) | PriceChange.branch_id.is_(None)
        )
        change = await db.scalar(
            select(PriceChange)
            .where(
                PriceChange.fuel_id == fuel.id,
                PriceChange.status == str(ApprovalStatus.APPROVED),
                PriceChange.applied_at.is_not(None),
                scope,
            )
            .order_by(PriceChange.applied_at.desc())
            .limit(1)
        )
        # Тэмдэглэлгүй хошууны үнэ ээлж нээснээс хойш өөрчлөгдсөн, эсвэл
        # сүүлийн тэмдэглэлээс хойш дахин үнэ батлагдсан бол хаалтыг зогсооно.
        # Тэмдэглэлийн үнэ батлагдаагүй (хүсэлт хүлээгдэж буй) бол анхааруулна.
        blocking = mark is None or (
            change is not None
            and change.applied_at is not None
            and change.applied_at > mark.created_at
        )
        out.append(
            {
                "nozzle_id": nozzle.id,
                "nozzle_number": nozzle.nozzle_number,
                "pump_name": pump.name,
                "fuel_id": fuel.id,
                "fuel_name": fuel.name_mn,
                "used_price": used_price,
                "current_price": now_price,
                "approved_at": change.applied_at if change is not None else None,
                "has_mark": mark is not None,
                "blocking": blocking,
            }
        )
    out.sort(key=lambda r: (r["pump_name"], r["nozzle_number"]))
    return out


async def open_shift_price_alerts(db: AsyncSession) -> list[dict[str, Any]]:
    """Бүх нээлттэй ээлжийн үнийн анхааруулга — админ/нягтлангийн самбарт."""
    shifts = (
        await db.scalars(
            select(Shift).where(Shift.status == str(ShiftStatus.OPEN)).order_by(Shift.opened_at)
        )
    ).all()
    out: list[dict[str, Any]] = []
    for shift in shifts:
        alerts = await price_alerts(db, shift)
        if not alerts:
            continue
        attendant = await db.scalar(select(User).where(User.id == shift.opened_by))
        branch = (
            await db.scalar(select(Branch).where(Branch.id == shift.branch_id))
            if shift.branch_id
            else None
        )
        out.append(
            {
                "shift_id": shift.id,
                "shift_number": shift.number,
                "branch_id": shift.branch_id,
                "branch_name": branch.name if branch else "",
                "attendant": (attendant.full_name or attendant.username) if attendant else "",
                "opened_at": shift.opened_at,
                "alerts": alerts,
            }
        )
    return out


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
    # Дараалал — ээлжийн АЖИЛЛАСАН огноогоор (батлахдаа зассан бол тэр).
    worked_date = func.coalesce(
        ShiftClosing.business_date, func.date(func.timezone(str(STATION_TZ), Shift.opened_at))
    )
    stmt = (
        select(ShiftClosing, Shift)
        .join(Shift, Shift.id == ShiftClosing.shift_id)
        .order_by(worked_date.desc(), Shift.opened_at.desc())
    )
    if branch_ids:
        stmt = stmt.where(Shift.branch_id.in_(branch_ids))
    if attendant_ids:
        stmt = stmt.where(Shift.opened_by.in_(attendant_ids))
    # Огноогоор шүүхдээ зассан бизнес огноог (байвал) харна.
    if date_from is not None:
        stmt = stmt.where(
            or_(
                ShiftClosing.business_date >= date_from,
                and_(ShiftClosing.business_date.is_(None), Shift.opened_at >= day_start(date_from)),
            )
        )
    if date_to is not None:
        stmt = stmt.where(
            or_(
                ShiftClosing.business_date <= date_to,
                and_(ShiftClosing.business_date.is_(None), Shift.opened_at <= day_end(date_to)),
            )
        )
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

    # Хадгалсан «байвал зохих» дүн одоогийн дүрмээр бодсоноос өөр (хуучин
    # дүрмээр хаагдсан) ээлж — жагсаалтад тэмдэглэж, бөөнөөр дахин бодуулна.
    fresh = await shift_service.expected_cash_map(db, [shift for _, shift in rows])
    # Үнэ батлагдсан ч тэмдэглэлгүй хаасан ээлж — админ миль, үнийг засна.
    from app.services.closing_admin_service import price_hint_map  # noqa: PLC0415

    price_hints = await price_hint_map(db, [shift for _, shift in rows])

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
                "date": closing.business_date or shift.opened_at.astimezone(STATION_TZ).date(),
                "opened_date": shift.opened_at.astimezone(STATION_TZ).date(),
                "closed_date": shift.closed_at.astimezone(STATION_TZ).date() if shift.closed_at else None,
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
                "needs_recalc": shift_service.needs_recalc(shift, fresh),
                "expected_recalc": fresh.get(shift.id) if shift_service.needs_recalc(shift, fresh) else None,
                #: Админы гар засвар (системийн алдаа) ба түгээгчийн дэлгэц дээрх зөрүү.
                "cash_adjustment": q2(_d(shift.cash_adjustment)),
                "cash_adjustment_note": shift.cash_adjustment_note,
                "client_diff": shift_service._client_diff(closing),
                "mile_gap_l": gaps.get(shift.id, (ZERO_L, 0))[0],
                "mile_gap_nozzles": gaps.get(shift.id, (ZERO_L, 0))[1],
                "price_hints": len(price_hints.get(shift.id, [])),
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
    business_date: date | None = None,
) -> dict[str, Any]:
    """Хаалтыг батлах / батламжийг буцаах. ``business_date`` — ээлжийн огноог засна."""
    closing, shift = await _closing_for(db, shift_id)
    if approved and closing.approved_at is not None:
        raise HTTPException(status_code=422, detail="Энэ хаалт аль хэдийн батлагдсан байна")
    if not approved and closing.approved_at is None:
        raise HTTPException(status_code=422, detail="Энэ хаалт батлагдаагүй байна")

    closing.approved_by = user.id if approved else None
    closing.approved_at = datetime.now(UTC) if approved else None
    closing.approval_note = (note or "").strip()[:500] or None
    if approved and business_date is not None:
        if business_date > shift.opened_at.astimezone(STATION_TZ).date():
            raise HTTPException(status_code=422, detail="Ээлжийн огноо нээсэн огнооноос хойш байж болохгүй")
        closing.business_date = business_date
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="shift.closing_approved" if approved else "shift.closing_unapproved",
        entity_type="shift",
        entity_id=shift.id,
        after={"approved": approved, "note": note, "business_date": str(business_date) if business_date else None},
    )
    return {
        "shift_id": shift.id,
        "approved": approved,
        "business_date": closing.business_date,
        "approved_at": closing.approved_at,
        "approved_by_name": user.full_name if approved else "",
        "approval_note": closing.approval_note,
    }
