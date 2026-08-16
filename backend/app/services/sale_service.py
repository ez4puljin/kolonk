"""Борлуулалтын үйлчилгээ — системийн зүрх (WP6).

Нэг борлуулалт = мөрүүдийг шийдвэрлэх → нийт дүн → төлбөр шалгах → нөөц хасах →
Sale/SaleItem/Payment бичих → журналын бичилт → И-баримтын дараалал → outbox+audit.
Бүгд **нэг транзакцад**. Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй —
``get_db`` нэг л commit хийнэ (CONTRACTS.md §1).

Тестлэх боломжтой математикийг доорх **цэвэр функцүүдэд** салгасан:
``line_amount``, ``discounted_price``, ``compute_totals``, ``payments_total``,
``validate_payment_total``, ``compute_change``, ``credit_available``,
``fits_credit_limit``, ``liters_match``.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import (
    CardStatus,
    CardTxType,
    ContractStatus,
    EbarimtStatus,
    EventType,
    ItemType,
    PaymentMethod,
    SaleStatus,
    SaleType,
    ShiftStatus,
    SourceType,
    VoucherStatus,
)
from app.models.fuel import Fuel, PumpNozzle, Tank
from app.models.instrument import PrepaidCard, PrepaidCardTransaction, Voucher
from app.models.partner import Contract, Customer
from app.models.product import Product
from app.models.sale import Payment, Sale, SaleItem
from app.models.shift import Shift
from app.models.system import EbarimtQueue
from app.models.user import User
from app.money import q2, q3, q6, vat_from_gross
from app.stationtime import day_end, day_start
from app.services import posting_rules, settings_service
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import UnbalancedEntryError, posting
from app.services.tank_service import consume_fuel

log = logging.getLogger("kolonk.sale")

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")

VAT_RATE: Decimal = settings.vat_rate

#: Насосны заалт vs кассын оруулгын зөвшөөрөгдөх зөрүү (литр).
AUTH_TOLERANCE = Decimal("0.01")

PAYMENT_METHOD_MN: dict[str, str] = dict(posting_rules.PAYMENT_METHOD_MN)

SALE_STATUS_MN: dict[str, str] = {
    SaleStatus.DRAFT: "Ноорог",
    SaleStatus.COMPLETED: "Хийгдсэн",
    SaleStatus.REFUNDED: "Буцаагдсан",
    SaleStatus.PARTIAL_REFUND: "Хэсэгчлэн буцаагдсан",
}

EBARIMT_STATUS_MN: dict[str, str] = {
    EbarimtStatus.PENDING: "Хүлээгдэж буй",
    EbarimtStatus.SENT: "Илгээгдсэн",
    EbarimtStatus.FAILED: "Амжилтгүй",
}


# =========================================================================== #
# Цэвэр функцүүд (DB хэрэггүй — нэгжийн тестээр бүрэн шалгагдана)
# =========================================================================== #
def to_decimal(value: Any, default: Decimal = ZERO) -> Decimal:
    """Ямар ч оролтыг ``Decimal`` болгоно. float хэзээ ч хүлээж авахгүй."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):  # pragma: no cover — API талд ирэх ёсгүй
        raise HTTPException(status_code=422, detail="Мөнгөн дүнг бутархай тоогоор дамжуулах боломжгүй")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Тоон утга буруу байна") from exc


def line_amount(qty: Decimal, unit_price: Decimal) -> Decimal:
    """Мөрийн дүн = тоо хэмжээ × нэгж үнэ (2 орон)."""
    return q2(to_decimal(qty) * to_decimal(unit_price))


def discounted_price(unit_price: Decimal, discount_per_l: Decimal) -> Decimal:
    """Гэрээний литр тутмын хөнгөлөлт. Сөрөг үнэ гарахыг зөвшөөрөхгүй."""
    price = q2(to_decimal(unit_price) - to_decimal(discount_per_l))
    return price if price > ZERO else ZERO


def compute_totals(amounts: Iterable[Decimal], rate: Decimal = VAT_RATE) -> tuple[Decimal, Decimal, Decimal]:
    """``(subtotal, vat_amount, total)``.

    НӨАТ борлуулалтын үнэд **шингэсэн**: ``vat = total/11`` (10%-ийн үед).
    """
    total = q2(sum((q2(to_decimal(a)) for a in amounts), ZERO))
    vat = vat_from_gross(total, rate)
    return q2(total - vat), vat, total


def payments_total(amounts: Iterable[Decimal]) -> Decimal:
    return q2(sum((q2(to_decimal(a)) for a in amounts), ZERO))


def validate_payment_total(total: Decimal, amounts: Iterable[Decimal]) -> Decimal:
    """Төлбөрийн нийлбэр борлуулалтын нийт дүнтэй **яг** тэнцэх ёстой."""
    paid = payments_total(amounts)
    if paid != q2(to_decimal(total)):
        raise HTTPException(status_code=422, detail="Төлбөрийн дүн нийт дүнтэй тохирохгүй байна")
    return paid


def compute_change(amount: Decimal, received: Decimal | None) -> Decimal:
    """Бэлэн төлбөрийн хариулт. ``received`` өгөөгүй бол хариулт 0."""
    amount = q2(to_decimal(amount))
    if received is None:
        return ZERO
    received = q2(to_decimal(received))
    if received < amount:
        raise HTTPException(status_code=422, detail="Хүлээн авсан бэлэн мөнгө төлбөрийн дүнгээс бага байна")
    return q2(received - amount)


def credit_available(credit_limit: Decimal, balance: Decimal) -> Decimal:
    """Гэрээгээр ашиглаж болох үлдсэн лимит."""
    return q2(to_decimal(credit_limit) - to_decimal(balance))


def fits_credit_limit(credit_limit: Decimal, balance: Decimal, amount: Decimal) -> bool:
    """``balance + amount <= credit_limit`` эсэх."""
    return q2(to_decimal(balance) + q2(to_decimal(amount))) <= q2(to_decimal(credit_limit))


def liters_match(a: Decimal, b: Decimal, tolerance: Decimal = AUTH_TOLERANCE) -> bool:
    """Хоёр литрийн заалт хүлцэх зөрүүнд багтаж байна уу."""
    return abs(q3(to_decimal(a)) - q3(to_decimal(b))) <= to_decimal(tolerance)


def resolve_sale_type(item_types: Sequence[str]) -> str:
    """Мөрүүдээс борлуулалтын төрлийг тодорхойлно."""
    kinds = {str(t) for t in item_types}
    if kinds == {str(ItemType.FUEL)}:
        return str(SaleType.FUEL)
    if kinds == {str(ItemType.PRODUCT)}:
        return str(SaleType.STORE)
    return str(SaleType.MIXED)


def method_label(method: str) -> str:
    return PAYMENT_METHOD_MN.get(str(method), str(method))


# =========================================================================== #
# Дотоод бүтцүүд
# =========================================================================== #
@dataclass
class AuthRecord:
    """Redis-д хадгалагдсан дууссан таталтын мэдээлэл (``auth:{id}``)."""

    pump_id: uuid.UUID | None = None
    nozzle_id: uuid.UUID | None = None
    fuel_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    liters: Decimal = ZERO_L
    amount: Decimal | None = None
    unit_price: Decimal | None = None


@dataclass
class ResolvedLine:
    item_type: str
    name: str
    qty: Decimal
    unit_price: Decimal
    amount: Decimal
    fuel_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    pump_id: uuid.UUID | None = None
    nozzle_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    tank: Tank | None = None
    product: Product | None = None


@dataclass
class ResolvedTender:
    method: str
    amount: Decimal
    received: Decimal | None = None
    change: Decimal | None = None
    ref_no: str | None = None
    contract: Contract | None = None
    voucher: Voucher | None = None
    card: PrepaidCard | None = None


def _get(source: Any, key: str, default: Any = None) -> Any:
    """Оролт нь ``dict`` эсвэл Pydantic объект аль нь ч байж болно."""
    if isinstance(source, Mapping):
        return source.get(key, default)
    value = getattr(source, key, default)
    return default if value is None else value


def _uuid(value: Any) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# =========================================================================== #
# 1. Ээлж
# =========================================================================== #
async def get_open_shift(db: AsyncSession) -> Shift | None:
    """Одоо нээлттэй байгаа ээлж (байхгүй бол ``None``)."""
    return await db.scalar(
        select(Shift).where(Shift.status == ShiftStatus.OPEN).order_by(Shift.opened_at.desc()).limit(1)
    )


async def require_open_shift(db: AsyncSession) -> Shift:
    shift = await get_open_shift(db)
    if shift is None:
        raise HTTPException(status_code=422, detail="Ээлж нээгээгүй байна")
    return shift


# =========================================================================== #
# 2. Насосны таталтын мэдээлэл (Redis)
# =========================================================================== #
async def read_authorization(authorization_id: uuid.UUID | str) -> AuthRecord | None:
    """``auth:{id}`` түлхүүрийг уншина. Байхгүй/Redis унтарсан бол ``None``."""
    # Redis-ийн клиентийг зөвхөн хэрэгтэй үед импортлоно (тестийг цэвэр байлгана).
    from app.redis_client import get_redis

    try:
        raw = await get_redis().get(f"auth:{authorization_id}")
    except Exception:  # noqa: BLE001 — Redis унтарсан бол гараар бүртгэнэ
        log.warning("Таталтын мэдээлэл унших боломжгүй: %s", authorization_id, exc_info=True)
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        log.warning("Таталтын мэдээлэл эвдэрсэн байна: %s", authorization_id)
        return None
    if not isinstance(data, dict):
        return None

    def _num(key: str) -> Decimal | None:
        # Драйвер тоог string болгож бичдэг; тоо ирсэн ч str()-ээр дамжуулж
        # Decimal болгоно (float арифметик хэзээ ч хийхгүй).
        value = data.get(key)
        return None if value is None else to_decimal(str(value))

    return AuthRecord(
        pump_id=_uuid(data.get("pump_id")),
        nozzle_id=_uuid(data.get("nozzle_id")),
        fuel_id=_uuid(data.get("fuel_id")),
        tank_id=_uuid(data.get("tank_id")),
        liters=q3(_num("liters") or ZERO_L),
        amount=q2(_num("amount")) if _num("amount") is not None else None,
        unit_price=q2(_num("unit_price")) if _num("unit_price") is not None else None,
    )


async def clear_authorization(authorization_id: uuid.UUID | str) -> None:
    """Борлуулалт үүссэний дараа таталтын түлхүүрийг устгана (давхар ашиглахаас сэргийлнэ)."""
    from app.redis_client import get_redis

    try:
        await get_redis().delete(f"auth:{authorization_id}")
    except Exception:  # noqa: BLE001
        log.warning("Таталтын түлхүүр устгаж чадсангүй: %s", authorization_id, exc_info=True)


# =========================================================================== #
# 3. Мөрүүдийг шийдвэрлэх
# =========================================================================== #
async def _resolve_fuel_line(db: AsyncSession, raw: Any, *, contract: Contract | None) -> ResolvedLine:
    qty = q3(to_decimal(_get(raw, "qty"), ZERO_L))
    fuel_id = _uuid(_get(raw, "fuel_id"))
    tank_id = _uuid(_get(raw, "tank_id"))
    pump_id = _uuid(_get(raw, "pump_id"))
    nozzle_id = _uuid(_get(raw, "nozzle_id"))
    auth_id = _uuid(_get(raw, "authorization_id"))

    record = await read_authorization(auth_id) if auth_id is not None else None
    if record is not None:
        if record.liters <= ZERO_L:
            raise HTTPException(status_code=422, detail="Насосны заалт хоосон байна")
        if qty > ZERO_L and not liters_match(qty, record.liters):
            raise HTTPException(
                status_code=422,
                detail="Оруулсан литр насосны заалттай тохирохгүй байна",
            )
        # Насосны заалт үнэн эх сурвалж.
        qty = record.liters
        fuel_id = record.fuel_id or fuel_id
        tank_id = record.tank_id or tank_id
        pump_id = record.pump_id or pump_id
        nozzle_id = record.nozzle_id or nozzle_id

    if qty <= ZERO_L:
        raise HTTPException(status_code=422, detail="Түлшний хэмжээ 0-ээс их байх ёстой")

    if nozzle_id is not None and (fuel_id is None or tank_id is None):
        nozzle = await db.scalar(select(PumpNozzle).where(PumpNozzle.id == nozzle_id))
        if nozzle is None:
            raise HTTPException(status_code=404, detail="Хошуу олдсонгүй")
        fuel_id = fuel_id or nozzle.fuel_id
        tank_id = tank_id or nozzle.tank_id
        pump_id = pump_id or nozzle.pump_id

    if fuel_id is None:
        raise HTTPException(status_code=422, detail="Түлшний төрөл заагаагүй байна")

    fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
    if fuel is None:
        raise HTTPException(status_code=404, detail="Түлш олдсонгүй")

    if tank_id is not None:
        tank = await db.scalar(select(Tank).where(Tank.id == tank_id).with_for_update())
        if tank is None:
            raise HTTPException(status_code=404, detail="Сав олдсонгүй")
        if tank.fuel_id != fuel.id:
            raise HTTPException(status_code=422, detail="Сав болон түлшний төрөл тохирохгүй байна")
    else:
        tank = await db.scalar(
            select(Tank)
            .where(Tank.fuel_id == fuel.id, Tank.is_active.is_(True))
            .order_by(Tank.current_l.desc())
            .limit(1)
            .with_for_update()
        )
        if tank is None:
            raise HTTPException(status_code=422, detail="Энэ түлшний идэвхтэй сав олдсонгүй")

    raw_price = _get(raw, "unit_price")
    if record is not None and record.unit_price is not None:
        base_price = record.unit_price
    elif raw_price is not None:
        base_price = q2(to_decimal(raw_price))
    else:
        # Савны салбарт өөр үнэ мөрдөж байвал түүнийг хэрэглэнэ.
        from app.services.pricing_service import effective_fuel_price

        base_price = await effective_fuel_price(db, fuel, getattr(tank, "branch_id", None))
    if base_price <= ZERO:
        raise HTTPException(status_code=422, detail="Түлшний үнэ тодорхойлогдоогүй байна")

    discount = q2(to_decimal(contract.price_discount_per_l)) if contract is not None else ZERO
    unit_price = discounted_price(base_price, discount)

    # Насосны дүн нь эрх мэдэлтэй: хөнгөлөлтгүй, үнэ өөрчлөгдөөгүй үед түүнийг барина.
    if record is not None and record.amount is not None and discount == ZERO and unit_price == base_price:
        amount = q2(record.amount)
    else:
        amount = line_amount(qty, unit_price)

        # Гараар бүртгэсэн (насосны бичлэггүй) мөрд касс мөнгөн дүнгээр оруулсан
        # бол түүнийг барина: литр 3 оронтой тул тооцоолсон дүн 1-2₮ зөрдөг.
        # Хэтрүүлж бичихээс сэргийлж 1 миллилитрийн үнээр л зөрүүг зөвшөөрнө.
        raw_amount = _get(raw, "amount")
        if record is None and raw_amount is not None:
            wanted = q2(to_decimal(raw_amount))
            tolerance = q2(unit_price * Decimal("0.001") + Decimal("0.01"))
            if abs(wanted - amount) > tolerance:
                raise HTTPException(
                    status_code=422,
                    detail="Мөрийн дүн тоо хэмжээ × нэгж үнэтэй тохирохгүй байна",
                )
            amount = wanted

    return ResolvedLine(
        item_type=str(ItemType.FUEL),
        name=fuel.name_mn,
        qty=qty,
        unit_price=unit_price,
        amount=amount,
        fuel_id=fuel.id,
        tank_id=tank.id,
        pump_id=pump_id,
        nozzle_id=nozzle_id,
        tank=tank,
    )


async def _resolve_product_line(
    db: AsyncSession, raw: Any, branch_id: uuid.UUID | None = None
) -> ResolvedLine:
    product_id = _uuid(_get(raw, "product_id"))
    if product_id is None:
        raise HTTPException(status_code=422, detail="Бараа заагаагүй байна")

    product = await db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if product is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    if not product.is_active:
        raise HTTPException(status_code=422, detail="Бараа идэвхгүй байна")

    qty = q3(to_decimal(_get(raw, "qty"), ZERO_L))
    if qty <= ZERO_L:
        raise HTTPException(status_code=422, detail="Барааны тоо хэмжээ 0-ээс их байх ёстой")

    raw_price = _get(raw, "unit_price")
    if raw_price is not None:
        unit_price = q2(to_decimal(raw_price))
    else:
        # Кассын салбарт өөр үнэ мөрдөж байвал түүнийг хэрэглэнэ.
        from app.services.pricing_service import effective_product_price

        unit_price = await effective_product_price(db, product, branch_id)
    if unit_price < ZERO:
        raise HTTPException(status_code=422, detail="Барааны үнэ сөрөг байж болохгүй")

    amount = line_amount(qty, unit_price)

    # Задлан (грамлаж) зарахад касс мөнгөн дүнгээр оруулдаг: тоо хэмжээ 3
    # оронтой тул `тоо × үнэ` нь 1-2₮ зөрдөг.  Түлштэй ижил дүрмээр — зөрүү
    # нь нэгжийн мянганы нэгээс хэтрэхгүй бол кассын дүнг барина.
    raw_amount = _get(raw, "amount")
    if raw_amount is not None:
        wanted = q2(to_decimal(raw_amount))
        tolerance = q2(unit_price * Decimal("0.001") + Decimal("0.01"))
        if abs(wanted - amount) > tolerance:
            raise HTTPException(
                status_code=422,
                detail="Мөрийн дүн тоо хэмжээ × нэгж үнэтэй тохирохгүй байна",
            )
        amount = wanted

    return ResolvedLine(
        item_type=str(ItemType.PRODUCT),
        name=product.name_mn,
        qty=qty,
        unit_price=unit_price,
        amount=amount,
        product_id=product.id,
        product=product,
    )


# =========================================================================== #
# 4. Гэрээ / төлбөрийн хэрэгсэл
# =========================================================================== #
async def _load_contract(db: AsyncSession, contract_id: uuid.UUID) -> Contract:
    contract = await db.scalar(select(Contract).where(Contract.id == contract_id).with_for_update())
    if contract is None:
        raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
    return contract


async def _resolve_payments(
    db: AsyncSession,
    payments_in: Sequence[Any],
    *,
    total: Decimal,
    sale_contract: Contract | None,
) -> list[ResolvedTender]:
    """Төлбөрүүдийг шалгаж, хэрэгслийг ачаална (өөрчлөлтийг ЭНД хийхгүй)."""
    amounts = [q2(to_decimal(_get(p, "amount"))) for p in payments_in]
    for amount in amounts:
        if amount <= ZERO:
            raise HTTPException(status_code=422, detail="Төлбөрийн дүн 0-ээс их байх ёстой")
    validate_payment_total(total, amounts)

    tenders: list[ResolvedTender] = []
    contract_cache: dict[uuid.UUID, Contract] = {}
    contract_used: dict[uuid.UUID, Decimal] = {}
    card_cache: dict[str, PrepaidCard] = {}
    card_used: dict[str, Decimal] = {}
    voucher_codes: set[str] = set()

    if sale_contract is not None:
        contract_cache[sale_contract.id] = sale_contract

    for raw, amount in zip(payments_in, amounts, strict=True):
        method = str(_get(raw, "method", PaymentMethod.CASH))
        if method not in PAYMENT_METHOD_MN:
            raise HTTPException(status_code=422, detail="Тодорхойгүй төлбөрийн хэрэгсэл")
        tender = ResolvedTender(method=method, amount=amount, ref_no=_clean(_get(raw, "ref_no")))

        if method == str(PaymentMethod.CASH):
            received = _get(raw, "received")
            if received is not None:
                tender.received = q2(to_decimal(received))
                tender.change = compute_change(amount, tender.received)

        elif method == str(PaymentMethod.CONTRACT):
            contract_id = _uuid(_get(raw, "contract_id")) or (
                sale_contract.id if sale_contract is not None else None
            )
            if contract_id is None:
                raise HTTPException(status_code=422, detail="Гэрээ сонгогдоогүй байна")
            contract = contract_cache.get(contract_id)
            if contract is None:
                contract = await _load_contract(db, contract_id)
                contract_cache[contract_id] = contract
            if str(contract.status) != str(ContractStatus.ACTIVE):
                raise HTTPException(status_code=422, detail="Гэрээ идэвхгүй байна")
            used = q2(contract_used.get(contract_id, ZERO) + amount)
            if not fits_credit_limit(contract.credit_limit, contract.balance, used):
                raise HTTPException(status_code=422, detail="Гэрээний зээлийн лимит хэтэрсэн байна")
            contract_used[contract_id] = used
            tender.contract = contract

        elif method == str(PaymentMethod.VOUCHER):
            code = (_clean(_get(raw, "voucher_code")) or "").upper()
            if not code:
                raise HTTPException(status_code=422, detail="Ваучерын код оруулаагүй байна")
            if code in voucher_codes:
                raise HTTPException(status_code=422, detail="Нэг ваучерыг давхардуулж ашиглах боломжгүй")
            voucher_codes.add(code)
            voucher = await db.scalar(select(Voucher).where(Voucher.code == code).with_for_update())
            if voucher is None:
                raise HTTPException(status_code=404, detail="Ваучер олдсонгүй")
            assert_voucher_usable(voucher)
            if amount != q2(to_decimal(voucher.face_value)):
                raise HTTPException(
                    status_code=422,
                    detail="Ваучерыг хэсэгчлэн ашиглах боломжгүй — нэрлэсэн дүнгээр нь ашиглана",
                )
            tender.voucher = voucher

        elif method == str(PaymentMethod.PREPAID):
            card_no = _clean(_get(raw, "card_no"))
            if not card_no:
                raise HTTPException(status_code=422, detail="Картын дугаар оруулаагүй байна")
            card = card_cache.get(card_no)
            if card is None:
                card = await db.scalar(
                    select(PrepaidCard).where(PrepaidCard.card_no == card_no).with_for_update()
                )
                if card is None:
                    raise HTTPException(status_code=404, detail="Карт олдсонгүй")
                card_cache[card_no] = card
            if str(card.status) != str(CardStatus.ACTIVE):
                raise HTTPException(status_code=422, detail="Карт идэвхгүй байна")
            used = q2(card_used.get(card_no, ZERO) + amount)
            if q2(to_decimal(card.balance)) < used:
                raise HTTPException(status_code=422, detail="Картын үлдэгдэл хүрэлцэхгүй")
            card_used[card_no] = used
            tender.card = card

        tenders.append(tender)

    return tenders


def assert_voucher_usable(voucher: Voucher, *, now: datetime | None = None) -> None:
    """Ваучер ашиглах боломжтой эсэх (422 монгол шалтгаантай)."""
    now = now or datetime.now(UTC)
    status = str(voucher.status)
    if status == str(VoucherStatus.REDEEMED):
        raise HTTPException(status_code=422, detail="Ваучер аль хэдийн ашиглагдсан байна")
    if status == str(VoucherStatus.VOID):
        raise HTTPException(status_code=422, detail="Ваучер хүчингүй болсон байна")
    if status == str(VoucherStatus.EXPIRED):
        raise HTTPException(status_code=422, detail="Ваучерын хугацаа дууссан байна")
    if status != str(VoucherStatus.ACTIVE):
        raise HTTPException(status_code=422, detail="Ваучер идэвхгүй байна")
    if voucher.expires_at is not None:
        expires = voucher.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < now:
            raise HTTPException(status_code=422, detail="Ваучерын хугацаа дууссан байна")


# =========================================================================== #
# 5. Нөөц хасалт
# =========================================================================== #
async def _consume_line(
    db: AsyncSession,
    line: ResolvedLine,
    sale_id: uuid.UUID,
    branch_id: uuid.UUID | None = None,
) -> tuple[Decimal, Decimal]:
    """``(unit_cost, cogs_amount)`` буцаана."""
    if line.item_type == str(ItemType.FUEL):
        if line.tank is None:  # pragma: no cover — дээр шалгагдсан
            raise HTTPException(status_code=422, detail="Түлшний сав тодорхойлогдоогүй байна")
        unit_cost = q6(to_decimal(line.tank.avg_cost))
        cogs = await consume_fuel(db, line.tank, line.qty, ref_type=str(SourceType.SALE), ref_id=sale_id)
        return unit_cost, q2(cogs)

    # Барааны нөөцийг WP7-ийн inventory_service эзэмшинэ.
    from app.services.inventory_service import consume_product

    if line.product is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    unit_cost = q6(to_decimal(line.product.avg_cost))
    cogs = await consume_product(
        db,
        line.product,
        line.qty,
        ref_type=str(SourceType.SALE),
        ref_id=sale_id,
        branch_id=branch_id,
    )
    return unit_cost, q2(cogs)


# =========================================================================== #
# Борлуулалт үүсгэх
# =========================================================================== #
async def create_sale(db: AsyncSession, user: User, payload: Any) -> Sale:
    """Борлуулалт бүртгэх бүрэн урсгал (CONTRACTS.md §1, §2, §5)."""
    # --- 1. Нээлттэй ээлж ---
    shift = await require_open_shift(db)

    items_in = list(_get(payload, "items", []) or [])
    if not items_in:
        raise HTTPException(status_code=422, detail="Борлуулалтын мөр хоосон байна")
    payments_in = list(_get(payload, "payments", []) or [])
    if not payments_in:
        raise HTTPException(status_code=422, detail="Төлбөрийн мэдээлэл хоосон байна")

    # --- Гэрээ / харилцагч ---
    contract: Contract | None = None
    contract_id = _uuid(_get(payload, "contract_id"))
    if contract_id is None:
        for raw in payments_in:
            if str(_get(raw, "method", "")) == str(PaymentMethod.CONTRACT):
                contract_id = _uuid(_get(raw, "contract_id"))
                if contract_id is not None:
                    break
    if contract_id is not None:
        contract = await _load_contract(db, contract_id)
        if str(contract.status) != str(ContractStatus.ACTIVE):
            raise HTTPException(status_code=422, detail="Гэрээ идэвхгүй байна")

    customer_id = _uuid(_get(payload, "customer_id"))
    if customer_id is None and contract is not None:
        customer_id = contract.customer_id
    if customer_id is not None:
        exists = await db.scalar(select(func.count()).select_from(Customer).where(Customer.id == customer_id))
        if not exists:
            raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй")

    # --- 2, 3. Мөрүүдийг шийдвэрлэх ---
    resolved: list[ResolvedLine] = []
    auth_ids: list[uuid.UUID] = []
    for raw in items_in:
        item_type = str(_get(raw, "item_type", ItemType.FUEL))
        if item_type == str(ItemType.FUEL):
            resolved.append(await _resolve_fuel_line(db, raw, contract=contract))
            auth_id = _uuid(_get(raw, "authorization_id"))
            if auth_id is not None:
                auth_ids.append(auth_id)
        elif item_type == str(ItemType.PRODUCT):
            resolved.append(
                await _resolve_product_line(db, raw, branch_id=getattr(shift, "branch_id", None))
            )
        else:
            raise HTTPException(status_code=422, detail="Мөрийн төрөл буруу байна")

    # --- 4. Нийт дүн ---
    subtotal, vat_amount, total = compute_totals([ln.amount for ln in resolved])
    if total <= ZERO:
        raise HTTPException(status_code=422, detail="Борлуулалтын нийт дүн 0-ээс их байх ёстой")

    # --- 5, 6. Төлбөр шалгах (өөрчлөлт хараахан хийхгүй) ---
    # Салбарт идэвхгүй болгосон хэрэгслээр төлөх боломжгүй.
    from app.services.branch_payment_service import assert_allowed

    await assert_allowed(
        db,
        getattr(shift, "branch_id", None),
        [str(_get(p, "method", "")) for p in payments_in],
    )
    tenders = await _resolve_payments(db, payments_in, total=total, sale_contract=contract)

    now = datetime.now(UTC)
    sale = Sale(
        # Ээлж нь салбартаа харьяалагдана — борлуулалт үүнийг өвлөнө.
        branch_id=getattr(shift, "branch_id", None),
        shift_id=shift.id,
        cashier_id=user.id,
        sale_type=resolve_sale_type([ln.item_type for ln in resolved]),
        status=str(SaleStatus.COMPLETED),
        subtotal=subtotal,
        vat_amount=vat_amount,
        total=total,
        cogs_total=ZERO,
        customer_id=customer_id,
        contract_id=contract.id if contract is not None else None,
        note=_clean(_get(payload, "note")),
        completed_at=now,
    )
    db.add(sale)
    await db.flush()

    # --- 7. Нөөц хасалт + мөрүүд ---
    cogs_total = ZERO
    sale_items: list[SaleItem] = []
    for line_no, line in enumerate(resolved, start=1):
        unit_cost, cogs = await _consume_line(db, line, sale.id, branch_id=sale.branch_id)
        cogs_total = q2(cogs_total + cogs)
        item = SaleItem(
            sale_id=sale.id,
            line_no=line_no,
            item_type=line.item_type,
            fuel_id=line.fuel_id,
            tank_id=line.tank_id,
            pump_id=line.pump_id,
            nozzle_id=line.nozzle_id,
            product_id=line.product_id,
            name_snapshot=line.name[:128],
            qty=line.qty,
            unit_price=line.unit_price,
            amount=line.amount,
            unit_cost=unit_cost,
            cogs_amount=cogs,
            refunded_qty=ZERO_L,
        )
        db.add(item)
        sale_items.append(item)
    sale.cogs_total = cogs_total

    # --- 6. Төлбөрийн хэрэгслийн үр дагавар + Payment мөрүүд ---
    sale_payments: list[Payment] = []
    for tender in tenders:
        payment = Payment(
            sale_id=sale.id,
            method=tender.method,
            amount=tender.amount,
            received=tender.received,
            change_given=tender.change,
            ref_no=tender.ref_no,
        )
        if tender.contract is not None:
            tender.contract.balance = q2(to_decimal(tender.contract.balance) + tender.amount)
            payment.contract_id = tender.contract.id
        if tender.voucher is not None:
            tender.voucher.status = str(VoucherStatus.REDEEMED)
            tender.voucher.redeemed_sale_id = sale.id
            tender.voucher.redeemed_at = now
            payment.voucher_id = tender.voucher.id
        if tender.card is not None:
            card = tender.card
            card.balance = q2(to_decimal(card.balance) - tender.amount)
            db.add(
                PrepaidCardTransaction(
                    card_id=card.id,
                    tx_type=str(CardTxType.REDEEM),
                    amount=tender.amount,
                    balance_after=q2(to_decimal(card.balance)),
                    sale_id=sale.id,
                )
            )
            payment.prepaid_card_id = card.id
        db.add(payment)
        sale_payments.append(payment)

    await db.flush()
    await _ensure_number(db, sale)

    # --- 9. Журналын бичилт ---
    try:
        await posting.post(
            db,
            event_type=str(EventType.SALE_POSTED),
            source_type=str(SourceType.SALE),
            source_id=sale.id,
            entry_date=now.date(),
            description=f"Борлуулалт №{sale.number}",
            lines=posting_rules.build_sale_lines(sale, sale_items, sale_payments),
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=f"Журналын бичилт тэнцэхгүй байна: {exc}") from exc

    # --- 10. И-баримтын дараалал (HTTP дуудлага энд хийхгүй) ---
    db.add(EbarimtQueue(sale_id=sale.id, status=str(EbarimtStatus.PENDING)))

    # --- 11. Outbox + audit ---
    await emit(
        db,
        aggregate_type="sale",
        aggregate_id=sale.id,
        event_type="SALE_COMPLETED",
        payload={
            "sale_id": str(sale.id),
            "number": int(sale.number),
            "shift_id": str(sale.shift_id),
            "cashier_id": str(sale.cashier_id),
            "sale_type": str(sale.sale_type),
            "subtotal": str(sale.subtotal),
            "vat_amount": str(sale.vat_amount),
            "total": str(sale.total),
            "cogs_total": str(sale.cogs_total),
            "customer_id": str(sale.customer_id) if sale.customer_id else None,
            "contract_id": str(sale.contract_id) if sale.contract_id else None,
            "completed_at": now.isoformat(),
            "items": [
                {
                    "line_no": item.line_no,
                    "item_type": str(item.item_type),
                    "name": item.name_snapshot,
                    "qty": str(item.qty),
                    "unit_price": str(item.unit_price),
                    "amount": str(item.amount),
                }
                for item in sale_items
            ],
            "payments": [
                {"method": str(p.method), "amount": str(p.amount)} for p in sale_payments
            ],
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="sale.create",
        entity_type="sale",
        entity_id=sale.id,
        after={
            "number": int(sale.number),
            "total": str(sale.total),
            "vat_amount": str(sale.vat_amount),
            "cogs_total": str(sale.cogs_total),
            "items": len(sale_items),
            "methods": ",".join(str(p.method) for p in sale_payments),
        },
    )

    await db.flush()
    # ``items``/``payments`` цуглуулгыг тодорхой ачаална — дараагийн уншилт
    # (баримт, хариу) async lazy-load хийж алдаа гаргахгүй.
    await db.refresh(sale)

    # Таталтын түлхүүрийг чөлөөлнө — нэг таталт зөвхөн нэг удаа зарагдана.
    for auth_id in auth_ids:
        await clear_authorization(auth_id)

    return sale


async def _ensure_number(db: AsyncSession, sale: Sale) -> None:
    """``number`` нь sequence-ээс сервер талд үүсдэг — ачаалагдаагүй бол уншина."""
    try:
        from sqlalchemy import inspect as sa_inspect

        if "number" in sa_inspect(sale).unloaded:
            await db.refresh(sale, ["number"])
    except Exception:  # noqa: BLE001 — дугаар нь зөвхөн тайлбарт хэрэглэгдэнэ
        log.warning("Борлуулалтын дугаар уншигдсангүй: %s", sale.id, exc_info=True)


# =========================================================================== #
# Баримтын өгөгдөл (80мм принтер)
# =========================================================================== #
async def receipt_payload(db: AsyncSession, sale: Sale) -> dict[str, Any]:
    """Хэвлэх баримтын бүрэн өгөгдөл."""
    conf = await settings_service.get_all(db)

    cashier_name = await db.scalar(select(User.full_name).where(User.id == sale.cashier_id))
    shift_number = await db.scalar(select(Shift.number).where(Shift.id == sale.shift_id))

    customer_name = None
    if sale.customer_id is not None:
        customer_name = await db.scalar(select(Customer.name).where(Customer.id == sale.customer_id))
    contract_no = None
    if sale.contract_id is not None:
        contract_no = await db.scalar(select(Contract.contract_no).where(Contract.id == sale.contract_id))

    items = list(sale.items)
    product_ids = [item.product_id for item in items if item.product_id is not None]
    units: dict[uuid.UUID, str] = {}
    if product_ids:
        rows = (await db.execute(select(Product.id, Product.unit).where(Product.id.in_(product_ids)))).all()
        units = {row[0]: row[1] for row in rows}

    receipt_items = [
        {
            "line_no": item.line_no,
            "name": item.name_snapshot,
            "unit": "л" if str(item.item_type) == str(ItemType.FUEL) else units.get(item.product_id, "ш"),
            "qty": q3(to_decimal(item.qty, ZERO_L)),
            "unit_price": q2(to_decimal(item.unit_price)),
            "amount": q2(to_decimal(item.amount)),
        }
        for item in items
    ]

    payments = list(sale.payments)
    change_total = q2(sum((to_decimal(p.change_given) for p in payments), ZERO))
    receipt_payments = [
        {
            "method": str(p.method),
            "method_name": method_label(p.method),
            "amount": q2(to_decimal(p.amount)),
            "received": q2(to_decimal(p.received)) if p.received is not None else None,
            "change": q2(to_decimal(p.change_given)) if p.change_given is not None else None,
        }
        for p in payments
    ]

    queued = await db.scalar(select(EbarimtQueue).where(EbarimtQueue.sale_id == sale.id))
    ebarimt = (
        {
            "status": str(queued.status),
            "status_name": EBARIMT_STATUS_MN.get(str(queued.status), str(queued.status)),
            "receipt_id": queued.receipt_id,
            "qr_data": queued.qr_data,
            "lottery_no": queued.lottery_no,
        }
        if queued is not None
        else None
    )

    try:
        printer_width = int(conf.get("printer_width_mm", 80) or 80)
    except (TypeError, ValueError):
        printer_width = 80

    return {
        "station": {
            "name": str(conf.get("station_name") or settings.station_name),
            "address": str(conf.get("station_address") or ""),
            "phone": str(conf.get("station_phone") or ""),
            "vat_payer_no": str(conf.get("vat_payer_no") or ""),
            "footer": str(conf.get("receipt_footer") or ""),
            "printer_width_mm": printer_width,
            "currency_symbol": str(conf.get("currency_symbol") or "₮"),
        },
        "sale_id": sale.id,
        "number": int(sale.number),
        "sold_at": sale.completed_at,
        "cashier_name": cashier_name,
        "shift_number": int(shift_number) if shift_number is not None else None,
        "customer_name": customer_name,
        "contract_no": contract_no,
        "note": sale.note,
        "items": receipt_items,
        "subtotal": q2(to_decimal(sale.subtotal)),
        "vat_amount": q2(to_decimal(sale.vat_amount)),
        "total": q2(to_decimal(sale.total)),
        "change_total": change_total,
        "payments": receipt_payments,
        "ebarimt": ebarimt,
    }


# =========================================================================== #
# Унших талын туслахууд (router-т хэрэглэнэ)
# =========================================================================== #
async def get_sale(db: AsyncSession, sale_id: uuid.UUID) -> Sale:
    sale = await db.scalar(select(Sale).where(Sale.id == sale_id))
    if sale is None:
        raise HTTPException(status_code=404, detail="Борлуулалт олдсонгүй")
    return sale


async def sale_detail(db: AsyncSession, sale: Sale) -> dict[str, Any]:
    """``SaleOut``-д тохирсон бүрэн dict."""
    cashier_name = await db.scalar(select(User.full_name).where(User.id == sale.cashier_id))
    shift_number = await db.scalar(select(Shift.number).where(Shift.id == sale.shift_id))
    customer_name = (
        await db.scalar(select(Customer.name).where(Customer.id == sale.customer_id))
        if sale.customer_id is not None
        else None
    )
    contract_no = (
        await db.scalar(select(Contract.contract_no).where(Contract.id == sale.contract_id))
        if sale.contract_id is not None
        else None
    )
    queued = await db.scalar(select(EbarimtQueue).where(EbarimtQueue.sale_id == sale.id))

    payments = list(sale.payments)
    return {
        "id": sale.id,
        "number": int(sale.number),
        "shift_id": sale.shift_id,
        "shift_number": int(shift_number) if shift_number is not None else None,
        "cashier_id": sale.cashier_id,
        "cashier_name": cashier_name,
        "sale_type": str(sale.sale_type),
        "status": str(sale.status),
        "status_name": SALE_STATUS_MN.get(str(sale.status), str(sale.status)),
        "subtotal": q2(to_decimal(sale.subtotal)),
        "vat_amount": q2(to_decimal(sale.vat_amount)),
        "total": q2(to_decimal(sale.total)),
        "cogs_total": q2(to_decimal(sale.cogs_total)),
        "change_total": q2(sum((to_decimal(p.change_given) for p in payments), ZERO)),
        "customer_id": sale.customer_id,
        "customer_name": customer_name,
        "contract_id": sale.contract_id,
        "contract_no": contract_no,
        "note": sale.note,
        "completed_at": sale.completed_at,
        "created_at": sale.created_at,
        "items": [
            {
                "id": item.id,
                "line_no": item.line_no,
                "item_type": str(item.item_type),
                "fuel_id": item.fuel_id,
                "tank_id": item.tank_id,
                "pump_id": item.pump_id,
                "nozzle_id": item.nozzle_id,
                "product_id": item.product_id,
                "name_snapshot": item.name_snapshot,
                "qty": q3(to_decimal(item.qty, ZERO_L)),
                "unit_price": q2(to_decimal(item.unit_price)),
                "amount": q2(to_decimal(item.amount)),
                "unit_cost": q6(to_decimal(item.unit_cost)),
                "cogs_amount": q2(to_decimal(item.cogs_amount)),
                "refunded_qty": q3(to_decimal(item.refunded_qty, ZERO_L)),
            }
            for item in sale.items
        ],
        "payments": [
            {
                "id": p.id,
                "method": str(p.method),
                "method_name": method_label(p.method),
                "amount": q2(to_decimal(p.amount)),
                "contract_id": p.contract_id,
                "voucher_id": p.voucher_id,
                "prepaid_card_id": p.prepaid_card_id,
                "received": q2(to_decimal(p.received)) if p.received is not None else None,
                "change_given": q2(to_decimal(p.change_given)) if p.change_given is not None else None,
                "ref_no": p.ref_no,
            }
            for p in payments
        ],
        "ebarimt": (
            {
                "status": str(queued.status),
                "status_name": EBARIMT_STATUS_MN.get(str(queued.status), str(queued.status)),
                "receipt_id": queued.receipt_id,
                "qr_data": queued.qr_data,
                "lottery_no": queued.lottery_no,
                "sent_at": queued.sent_at,
            }
            if queued is not None
            else None
        ),
    }


async def list_sales(
    db: AsyncSession,
    *,
    date_from: Any = None,
    date_to: Any = None,
    shift_id: uuid.UUID | None = None,
    method: str | None = None,
    customer_id: uuid.UUID | None = None,
    cashier_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Борлуулалтын жагсаалт (шүүлт + хуудаслалт)."""
    conditions: list[Any] = [Sale.status != str(SaleStatus.DRAFT)]
    if date_from is not None:
        conditions.append(Sale.completed_at >= day_start(date_from))
    if date_to is not None:
        conditions.append(Sale.completed_at <= day_end(date_to))
    if shift_id is not None:
        conditions.append(Sale.shift_id == shift_id)
    if customer_id is not None:
        conditions.append(Sale.customer_id == customer_id)
    if cashier_id is not None:
        conditions.append(Sale.cashier_id == cashier_id)
    if method:
        conditions.append(
            Sale.id.in_(select(Payment.sale_id).where(Payment.method == str(method)))
        )

    total = await db.scalar(select(func.count()).select_from(Sale).where(*conditions)) or 0
    rows = (
        await db.scalars(
            select(Sale)
            .where(*conditions)
            .order_by(Sale.number.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    cashier_ids = {row.cashier_id for row in rows}
    names: dict[uuid.UUID, str] = {}
    if cashier_ids:
        result = (await db.execute(select(User.id, User.full_name).where(User.id.in_(cashier_ids)))).all()
        names = {r[0]: r[1] for r in result}

    customer_ids = {row.customer_id for row in rows if row.customer_id is not None}
    customers: dict[uuid.UUID, str] = {}
    if customer_ids:
        result = (
            await db.execute(select(Customer.id, Customer.name).where(Customer.id.in_(customer_ids)))
        ).all()
        customers = {r[0]: r[1] for r in result}

    items: list[dict[str, Any]] = []
    for sale in rows:
        methods = [str(p.method) for p in sale.payments]
        items.append(
            {
                "id": sale.id,
                "number": int(sale.number),
                "shift_id": sale.shift_id,
                "cashier_id": sale.cashier_id,
                "cashier_name": names.get(sale.cashier_id),
                "sale_type": str(sale.sale_type),
                "status": str(sale.status),
                "status_name": SALE_STATUS_MN.get(str(sale.status), str(sale.status)),
                "total": q2(to_decimal(sale.total)),
                "vat_amount": q2(to_decimal(sale.vat_amount)),
                "customer_id": sale.customer_id,
                "customer_name": customers.get(sale.customer_id) if sale.customer_id else None,
                "methods": methods,
                "method_names": [method_label(m) for m in methods],
                "items_count": len(sale.items),
                "completed_at": sale.completed_at,
                "created_at": sale.created_at,
            }
        )

    return {"items": items, "total": int(total)}
