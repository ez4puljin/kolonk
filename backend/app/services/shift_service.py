"""Ээлжийн хөдөлгүүр — нээх, хаах, тооцоо нийлүүлэх, тайлагнах (WP5).

Санхүүгийн хамгийн эмзэг урсгал: ээлж хаахад
  * кассын байвал зохих үлдэгдлийг тооцож илүүдэл/дутагдлыг журналд бичнэ,
  * сав бүрийн хэмжилтээр дэвтрийн үлдэгдлийг залруулж, зөрүүг өртгөөр нь бичнэ,
  * хошуу бүрийн механик тоолуурын заалтыг тогтооно.

Дүрэм: энэ модуль **хэзээ ч** `db.commit()` дуудахгүй — `get_db` нэг л commit хийнэ.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.enums import (
    ApprovalStatus,
    EventType,
    ItemType,
    PaymentMethod,
    ReadingType,
    SaleStatus,
    ShiftPhase,
    ShiftStatus,
    SourceType,
    TankMovementType,
)
from app.models.accounting import JournalEntry, JournalLine
from app.models.approval import Refund
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank, TotalizerReading
from app.models.sale import Payment, Sale, SaleItem
from app.models.shift import Shift, ShiftTankLevel
from app.models.user import User
from app.money import q2, q3
from app.stationtime import day_end, day_start
from app.services import tank_service
from app.services.audit_service import audit
from app.services.coa import ACC
from app.services.outbox_service import emit
from app.services.posting import Dims, LineSpec, posting

try:  # posting_rules-ийг WP3 эзэмшинэ; байхгүй/өөр гарын үсэгтэй бол доорх дүрмээр өөрсдөө барина.
    from app.services import posting_rules as _rules
except Exception:  # noqa: BLE001  # pragma: no cover
    _rules = None  # type: ignore[assignment]

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")

TENDER_ORDER: list[str] = [
    PaymentMethod.CASH,
    PaymentMethod.CARD,
    PaymentMethod.QR,
    PaymentMethod.TRANSFER,
    PaymentMethod.CONTRACT,
    PaymentMethod.VOUCHER,
    PaymentMethod.PREPAID,
]

TENDER_NAMES_MN: dict[str, str] = {
    PaymentMethod.CASH: "Бэлэн",
    PaymentMethod.CARD: "Карт",
    PaymentMethod.QR: "QR",
    PaymentMethod.TRANSFER: "Шилжүүлэг",
    PaymentMethod.CONTRACT: "Зээл",
    PaymentMethod.VOUCHER: "Ваучер",
    PaymentMethod.PREPAID: "Урьдчилсан карт",
}

STATUS_NAMES_MN: dict[str, str] = {
    ShiftStatus.OPEN: "Нээлттэй",
    ShiftStatus.CLOSED: "Хаагдсан",
}

REFUND_STATUS_MN: dict[str, str] = {
    ApprovalStatus.PENDING: "Хүлээгдэж буй",
    ApprovalStatus.APPROVED: "Батлагдсан",
    ApprovalStatus.REJECTED: "Татгалзсан",
}


# --------------------------------------------------------------------------- #
# Туслах
# --------------------------------------------------------------------------- #
def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _field(item: Any, key: str) -> Any:
    """Оролт нь dict эсвэл Pydantic объект аль нь ч байж болно."""
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def _rule_lines(name: str, **kwargs: Any) -> list[LineSpec] | None:
    """WP3-ийн `posting_rules` туслахыг боломжтой бол ашиглана, үгүй бол None."""
    fn = getattr(_rules, name, None) if _rules is not None else None
    if fn is None:
        return None
    try:
        built = fn(**kwargs)
    except TypeError:  # өөр гарын үсэгтэй — доорх дүрмээр өөрсдөө барина
        return None
    if not built:
        return None
    lines = list(built)
    if not all(hasattr(line, "account_code") for line in lines):
        return None
    return lines


def _truncate(text: str, limit: int = 255) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def _user_names(db: AsyncSession, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = (await db.execute(select(User.id, User.full_name).where(User.id.in_(list(wanted))))).all()
    return {row[0]: row[1] for row in rows}


def _sale_scope(shift: Shift) -> tuple[Any, ...]:
    """Ээлжид харьяалагдах, ноорог биш борлуулалтууд."""
    return (Sale.shift_id == shift.id, Sale.status != SaleStatus.DRAFT)


async def _cash_flows(db: AsyncSession, shift: Shift) -> tuple[Decimal, Decimal]:
    """(бэлнээр авсан төлбөр, бэлнээр буцаасан дүн) — SQL агрегатаар."""
    cash_sales = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), ZERO))
        .select_from(Payment)
        .join(Sale, Payment.sale_id == Sale.id)
        .where(*_sale_scope(shift), Payment.method == PaymentMethod.CASH)
    )
    refunds_cash = await db.scalar(
        select(func.coalesce(func.sum(Refund.amount), ZERO))
        .select_from(Refund)
        .where(
            Refund.shift_id == shift.id,
            Refund.status == ApprovalStatus.APPROVED,
            Refund.refund_method == PaymentMethod.CASH,
        )
    )
    return q2(_dec(cash_sales)), q2(_dec(refunds_cash))


async def _other_cash_movement(db: AsyncSession, shift: Shift) -> Decimal:
    """Борлуулалт/буцаалтаас гадуурх кассын хөдөлгөөн (цэвэр дүн).

    Ваучер бэлнээр зарах, урьдчилсан карт бэлнээр цэнэглэх, нийлүүлэгчид
    кассаас төлөх, авлагыг кассаар авах зэрэг нь бүгд бодит бэлэн мөнгийг
    касст оруулж/гаргадаг ч ``Sale``-тай холбоогүй тул дээрх агрегатад ордоггүй.

    Тэдгээрийг ерөнхий дэвтрээс шууд уншина: ээлжийн хугацаанд ``1101`` дансанд
    хийгдсэн бичилтийн (дебит − кредит) нийлбэр. Ингэснээр ирээдүйд нэмэгдэх
    кассын аливаа үйл явдал автоматаар тооцогдоно.

    Хасагдах зүйлс:
      * ``source_type='shift'`` — ээлжийн зөрүүний бичилт өөрөө (дугуй хамаарал);
      * ``SALE``/``REFUND`` — эдгээрийг аль хэдийн ``_cash_flows`` тоолсон.
    """
    window_end = shift.closed_at or datetime.now(UTC)
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), ZERO)
            - func.coalesce(func.sum(JournalLine.credit), ZERO)
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(
            JournalLine.account_code == ACC.CASH,
            JournalEntry.created_at >= shift.opened_at,
            JournalEntry.created_at < window_end,
            JournalEntry.source_type.notin_(
                [str(SourceType.SHIFT), str(SourceType.SALE), str(SourceType.REFUND)]
            ),
        )
    )
    return q2(_dec(await db.scalar(stmt)))


async def _load_tanks(
    db: AsyncSession, tank_ids: Sequence[uuid.UUID], *, lock: bool = False
) -> dict[uuid.UUID, Tank]:
    if not tank_ids:
        return {}
    stmt = select(Tank).where(Tank.id.in_(list(tank_ids)))
    if lock:
        stmt = stmt.with_for_update()
    rows = (await db.scalars(stmt)).all()
    return {tank.id: tank for tank in rows}


async def _load_nozzles(db: AsyncSession, nozzle_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, PumpNozzle]:
    if not nozzle_ids:
        return {}
    rows = (await db.scalars(select(PumpNozzle).where(PumpNozzle.id.in_(list(nozzle_ids))))).all()
    return {nozzle.id: nozzle for nozzle in rows}


async def attendant_mode(db: AsyncSession) -> bool:
    """ПОС унтраалттай = түгээгчийн өдрийн горим.

    Энэ горимд ээлж бэлэн мөнгө + милийн заалтаар нээгдэж, бүх борлуулалт
    өдрийн хаалтаар нэг дор бүртгэгддэг тул тоолуур ЗААВАЛ бүртгэгдэнэ.
    """
    from app.services.settings_service import get_bool

    return not await get_bool(db, "pos_sales_enabled")


async def totalizer_enabled(db: AsyncSession) -> bool:
    """Ээлжид тоолуурын заалт бүртгэх эсэх (эзэн тохиргооноос асаана/унтраана).

    Түгээгчийн горимд тохиргооноос үл хамааран үргэлж идэвхтэй — миль байхгүй
    бол өдрийн тооцоо хийх боломжгүй.
    """
    from app.services.settings_service import get_bool

    if await attendant_mode(db):
        return True
    return await get_bool(db, "shift_totalizer_enabled")


async def _required_nozzles(db: AsyncSession, branch_id: uuid.UUID | None) -> list[PumpNozzle]:
    """Заалт нь заавал бүртгэгдэх ёстой хошуунууд — идэвхтэй насосныхаас.

    Ээлж салбартай бол тухайн салбарын насос л хамаарна; салбаргүй (нэг
    салбартай станц) үед бүх идэвхтэй насос.
    """
    from app.models.fuel import Pump

    stmt = (
        select(PumpNozzle)
        .join(Pump, Pump.id == PumpNozzle.pump_id)
        .where(Pump.is_active.is_(True))
    )
    if branch_id is not None:
        stmt = stmt.where(Pump.branch_id == branch_id)
    return list((await db.scalars(stmt.order_by(PumpNozzle.nozzle_number))).all())


async def _check_all_readings(
    db: AsyncSession, branch_id: uuid.UUID | None, readings: Sequence[tuple[uuid.UUID, Decimal]]
) -> None:
    """Идэвхтэй хошуу бүрд заалт өгсөн эсэхийг шалгана."""
    required = await _required_nozzles(db, branch_id)
    given = {nozzle_id for nozzle_id, _ in readings}
    missing = [n for n in required if n.id not in given]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"{len(missing)} хошууны тоолуурын заалт дутуу байна",
        )


def _normalize_dips(tank_dips: Sequence[Any]) -> list[tuple[uuid.UUID, Decimal]]:
    seen: set[uuid.UUID] = set()
    out: list[tuple[uuid.UUID, Decimal]] = []
    for item in tank_dips or []:
        raw_id = _field(item, "tank_id")
        if raw_id is None:
            raise HTTPException(status_code=422, detail="Савны дугаар заагаагүй байна")
        tank_id = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
        if tank_id in seen:
            raise HTTPException(status_code=422, detail="Нэг сав давхардаж бүртгэгдсэн байна")
        seen.add(tank_id)
        liters = q3(_dec(_field(item, "dip_liters"), ZERO_L))
        if liters < 0:
            raise HTTPException(status_code=422, detail="Савны хэмжилт сөрөг байж болохгүй")
        out.append((tank_id, liters))
    return out


def _normalize_readings(totalizer_readings: Sequence[Any]) -> list[tuple[uuid.UUID, Decimal]]:
    seen: set[uuid.UUID] = set()
    out: list[tuple[uuid.UUID, Decimal]] = []
    for item in totalizer_readings or []:
        raw_id = _field(item, "nozzle_id")
        if raw_id is None:
            raise HTTPException(status_code=422, detail="Хошууны дугаар заагаагүй байна")
        nozzle_id = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
        if nozzle_id in seen:
            raise HTTPException(status_code=422, detail="Нэг хошуу давхардаж бүртгэгдсэн байна")
        seen.add(nozzle_id)
        reading = q3(_dec(_field(item, "reading"), ZERO_L))
        if reading < 0:
            raise HTTPException(status_code=422, detail="Тоолуурын заалт сөрөг байж болохгүй")
        out.append((nozzle_id, reading))
    return out


# --------------------------------------------------------------------------- #
# Ээлж нээх / хаах
# --------------------------------------------------------------------------- #
async def get_open_shift(db: AsyncSession) -> Shift | None:
    """Одоо нээлттэй байгаа ээлж (байхгүй бол None)."""
    return await db.scalar(
        select(Shift).where(Shift.status == ShiftStatus.OPEN).order_by(Shift.opened_at.desc()).limit(1)
    )


async def get_shift(db: AsyncSession, shift_id: uuid.UUID) -> Shift:
    shift = await db.scalar(select(Shift).where(Shift.id == shift_id))
    if shift is None:
        raise HTTPException(status_code=404, detail="Ээлж олдсонгүй")
    return shift


async def _branch_for_shift(db: AsyncSession, user: User | None):
    """Ээлжийн салбар.

    1. Түгээгч салбартаа харьяалагддаг — түүнийг шууд авна (нэвтрэхэд
       автоматаар сонгогдсон салбар).
    2. Харьяалалгүй (менежер, эзэн) бөгөөд идэвхтэй салбар ганц бол түүнийг.
    3. Олон салбартай үед харьяалалгүй хүн ээлж нээхэд салбар тодорхойгүй тул
       алдаа буцаана — буруу салбарт бичигдэхээс сэргийлнэ.
    """
    from app.models.branch import Branch

    if user is not None and getattr(user, "branch_id", None):
        return user.branch_id

    rows = (await db.scalars(select(Branch).where(Branch.is_active.is_(True)))).all()
    if len(rows) == 1:
        return rows[0].id
    if not rows:
        return None
    raise HTTPException(
        status_code=422,
        detail="Олон салбартай тул ээлж нээхэд салбартай хэрэглэгчээр нэвтэрнэ үү",
    )


async def open_shift(
    db: AsyncSession,
    user: User,
    *,
    opening_cash: Decimal,
    tank_dips: Sequence[Any],
    totalizer_readings: Sequence[Any],
) -> Shift:
    """Шинэ ээлж нээнэ. Савны хэмжилт, хошууны тоолуурын заалтыг эхлэлийн цэг болгож бүртгэнэ."""
    if await get_open_shift(db) is not None:
        raise HTTPException(status_code=422, detail="Өмнөх ээлж хаагдаагүй байна")

    dips = _normalize_dips(tank_dips)
    # Тоолуур унтраалттай үед заалтыг огт бүртгэхгүй (илгээсэн ч үл хэрэгснэ).
    use_totalizer = await totalizer_enabled(db)
    readings = _normalize_readings(totalizer_readings) if use_totalizer else []

    tanks = await _load_tanks(db, [tank_id for tank_id, _ in dips])
    for tank_id, _ in dips:
        if tank_id not in tanks:
            raise HTTPException(status_code=422, detail="Бүртгэлгүй сав заасан байна")
    nozzles = await _load_nozzles(db, [nozzle_id for nozzle_id, _ in readings])
    for nozzle_id, _ in readings:
        if nozzle_id not in nozzles:
            raise HTTPException(status_code=422, detail="Бүртгэлгүй хошуу заасан байна")

    branch_id = await _branch_for_shift(db, user)
    if use_totalizer:
        await _check_all_readings(db, branch_id, readings)

    now = datetime.now(UTC)
    max_number = await db.scalar(select(func.max(Shift.number)))
    shift = Shift(
        # Нэг салбартай үед автоматаар түүнд харьяалагдана.
        branch_id=branch_id,
        number=int(max_number or 0) + 1,
        status=ShiftStatus.OPEN,
        opened_by=user.id,
        opened_at=now,
        opening_cash=q2(_dec(opening_cash)),
    )
    db.add(shift)
    await db.flush()

    for tank_id, liters in dips:
        tank = tanks[tank_id]
        db.add(
            ShiftTankLevel(
                shift_id=shift.id,
                tank_id=tank.id,
                phase=ShiftPhase.OPEN,
                dip_liters=liters,
                book_liters=q3(_dec(tank.current_l, ZERO_L)),
            )
        )

    # Нээлтийн үеийн литрийн үнийг хошуу бүрд нь хөлдөөнө — өдрийн дундуур үнэ
    # өөрчлөгдвөл сегментийн эх үнэ болно (түгээгчийн миль×үнэ тооцоонд).
    from app.services.pricing_service import effective_fuel_price

    fuel_ids = {nozzles[nid].fuel_id for nid, _ in readings}
    fuels = {
        f.id: f
        for f in (await db.scalars(select(Fuel).where(Fuel.id.in_(fuel_ids)))).all()
    } if fuel_ids else {}
    price_cache: dict[uuid.UUID, Decimal] = {}
    for fuel_id, fuel in fuels.items():
        price_cache[fuel_id] = await effective_fuel_price(db, fuel, branch_id)

    for nozzle_id, reading in readings:
        nozzle = nozzles[nozzle_id]
        db.add(
            TotalizerReading(
                nozzle_id=nozzle.id,
                shift_id=shift.id,
                reading=reading,
                reading_type=ReadingType.SHIFT_OPEN,
                price_per_liter=price_cache.get(nozzle.fuel_id),
                recorded_by=user.id,
                recorded_at=now,
            )
        )
        # Механик тоолуур бол үнэн — ээлж нээхэд хошууны заалтыг оруулсан утгаар тогтооно.
        nozzle.totalizer = reading

    await db.flush()

    await emit(
        db,
        aggregate_type="shift",
        aggregate_id=shift.id,
        event_type="SHIFT_OPENED",
        payload={
            "shift_id": str(shift.id),
            "number": shift.number,
            "opened_at": now.isoformat(),
            "opened_by": str(user.id),
            "opening_cash": str(shift.opening_cash),
            "tank_dips": [{"tank_id": str(t), "dip_liters": str(v)} for t, v in dips],
            "totalizer_readings": [{"nozzle_id": str(n), "reading": str(v)} for n, v in readings],
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="shift.open",
        entity_type="shift",
        entity_id=shift.id,
        after={
            "number": shift.number,
            "opening_cash": shift.opening_cash,
            "tanks": len(dips),
            "nozzles": len(readings),
        },
    )
    return shift


async def close_shift(
    db: AsyncSession,
    user: User,
    *,
    shift: Shift,
    declared_cash: Decimal,
    tank_dips: Sequence[Any],
    totalizer_readings: Sequence[Any],
    note: str | None = None,
) -> dict[str, Any]:
    """Ээлж хааж, кассын болон савны зөрүүг журналд бичээд бүрэн тайланг буцаана."""
    if shift.status != ShiftStatus.OPEN:
        raise HTTPException(status_code=422, detail="Энэ ээлж аль хэдийн хаагдсан байна")

    dips = _normalize_dips(tank_dips)
    # Тоолуур унтраалттай үед заалтыг огт бүртгэхгүй (илгээсэн ч үл хэрэгснэ).
    use_totalizer = await totalizer_enabled(db)
    readings = _normalize_readings(totalizer_readings) if use_totalizer else []

    tanks = await _load_tanks(db, [tank_id for tank_id, _ in dips], lock=True)
    for tank_id, _ in dips:
        if tank_id not in tanks:
            raise HTTPException(status_code=422, detail="Бүртгэлгүй сав заасан байна")
    nozzles = await _load_nozzles(db, [nozzle_id for nozzle_id, _ in readings])
    for nozzle_id, _ in readings:
        if nozzle_id not in nozzles:
            raise HTTPException(status_code=422, detail="Бүртгэлгүй хошуу заасан байна")

    # Нээх үед заалт бүртгэсэн бол хаахад ч бүрэн бүртгэнэ.
    if use_totalizer:
        await _check_all_readings(db, shift.branch_id, readings)

    # Бичлэг хийхээс ӨМНӨ бүх заалтыг шалгана — залруулга хийсний дараа унахаас сэргийлнэ.
    open_readings = await _shift_readings(db, shift, ReadingType.SHIFT_OPEN)
    for nozzle_id, reading in readings:
        opened_at_reading = open_readings.get(nozzle_id)
        if opened_at_reading is not None and reading < opened_at_reading:
            raise HTTPException(
                status_code=422,
                detail="Хаалтын тоолуурын заалт нээлтийн заалтаас бага байж болохгүй",
            )

    now = datetime.now(UTC)
    entry_date = now.date()
    declared = q2(_dec(declared_cash))

    # ---------------- Касс ----------------
    cash_sales, refunds_cash = await _cash_flows(db, shift)
    other_cash = await _other_cash_movement(db, shift)
    opening_cash = q2(_dec(shift.opening_cash))
    expected = q2(opening_cash + cash_sales - refunds_cash + other_cash)
    over_short = q2(declared - expected)

    # ---------------- Сав: хэмжилт vs дэвтрийн үлдэгдэл ----------------
    loss_rows: list[tuple[Tank, Decimal, Decimal]] = []  # (tank, variance_l, value)
    gain_rows: list[tuple[Tank, Decimal, Decimal]] = []
    for tank_id, dip_liters in dips:
        tank = tanks[tank_id]
        # Дэвтрийн үлдэгдэл = залруулга хийхээс ӨМНӨХ current_l
        book = q3(_dec(tank.current_l, ZERO_L))
        variance = q3(dip_liters - book)
        db.add(
            ShiftTankLevel(
                shift_id=shift.id,
                tank_id=tank.id,
                phase=ShiftPhase.CLOSE,
                dip_liters=dip_liters,
                book_liters=book,
                variance_l=variance,
            )
        )
        if variance == 0:
            continue
        value = q2(abs(variance) * _dec(tank.avg_cost))
        # Хэмжилтээр нь бодит үлдэгдэлд хүргэнэ
        await tank_service.adjust_fuel(
            db,
            tank,
            variance,
            movement_type=TankMovementType.VARIANCE,
            ref_type=SourceType.SHIFT,
            ref_id=shift.id,
            note=f"Ээлж №{shift.number} хаалтын зөрүү",
        )
        if value <= 0:
            continue
        if variance < 0:
            loss_rows.append((tank, variance, value))
        else:
            gain_rows.append((tank, variance, value))

    # ---------------- Хошууны тоолуур ----------------
    for nozzle_id, reading in readings:
        nozzle = nozzles[nozzle_id]
        db.add(
            TotalizerReading(
                nozzle_id=nozzle.id,
                shift_id=shift.id,
                reading=reading,
                reading_type=ReadingType.SHIFT_CLOSE,
                recorded_by=user.id,
                recorded_at=now,
            )
        )
        nozzle.totalizer = reading

    # ---------------- Журналын бичилт ----------------
    posted: list[dict[str, Any]] = []
    posted.extend(
        await _post_cash_difference(db, user, shift=shift, entry_date=entry_date, over_short=over_short)
    )
    posted.extend(
        await _post_fuel_variance(
            db, user, shift=shift, entry_date=entry_date, loss_rows=loss_rows, gain_rows=gain_rows
        )
    )

    # ---------------- Ээлжийг хаах ----------------
    shift.status = ShiftStatus.CLOSED
    shift.closed_at = now
    shift.closed_by = user.id
    shift.declared_cash = declared
    shift.expected_cash = expected
    shift.cash_over_short = over_short
    if note:
        shift.note = note
    await db.flush()

    await emit(
        db,
        aggregate_type="shift",
        aggregate_id=shift.id,
        event_type="SHIFT_CLOSED",
        payload={
            "shift_id": str(shift.id),
            "number": shift.number,
            "closed_at": now.isoformat(),
            "closed_by": str(user.id),
            "opening_cash": str(opening_cash),
            "cash_sales": str(cash_sales),
            "cash_refunds": str(refunds_cash),
            "expected_cash": str(expected),
            "declared_cash": str(declared),
            "cash_over_short": str(over_short),
            "tank_variances": [
                {"tank_id": str(tank.id), "variance_l": str(var), "value": str(val)}
                for tank, var, val in (*loss_rows, *gain_rows)
            ],
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="shift.close",
        entity_type="shift",
        entity_id=shift.id,
        before={"status": str(ShiftStatus.OPEN), "opening_cash": opening_cash},
        after={
            "status": str(ShiftStatus.CLOSED),
            "declared_cash": declared,
            "expected_cash": expected,
            "cash_over_short": over_short,
            "note": note,
        },
    )

    return await shift_report(db, shift, posted_entries=posted)


async def _shift_readings(
    db: AsyncSession, shift: Shift, reading_type: str
) -> dict[uuid.UUID, Decimal]:
    rows = (
        await db.execute(
            select(TotalizerReading.nozzle_id, TotalizerReading.reading)
            .where(TotalizerReading.shift_id == shift.id, TotalizerReading.reading_type == reading_type)
            .order_by(TotalizerReading.created_at)
        )
    ).all()
    return {row[0]: q3(_dec(row[1], ZERO_L)) for row in rows}


# --------------------------------------------------------------------------- #
# Журналын бичилтүүд
# --------------------------------------------------------------------------- #
async def _post_cash_difference(
    db: AsyncSession,
    user: User,
    *,
    shift: Shift,
    entry_date: Any,
    over_short: Decimal,
) -> list[dict[str, Any]]:
    """Кассын илүүдэл/дутагдал. Тэг бол бичилт хийхгүй."""
    if over_short == 0:
        return []

    amount = q2(abs(over_short))
    if over_short < 0:
        event_type = EventType.SHIFT_CASH_SHORT
        description = _truncate(f"Ээлж №{shift.number} — кассын дутагдал")
        lines = _rule_lines("build_shift_cash_lines", amount=amount, is_short=True) or [
            LineSpec(account_code=ACC.CASH_SHORT, debit=amount, memo=description),
            LineSpec(account_code=ACC.CASH, credit=amount, memo=description),
        ]
    else:
        event_type = EventType.SHIFT_CASH_OVER
        description = _truncate(f"Ээлж №{shift.number} — кассын илүүдэл")
        lines = _rule_lines("build_shift_cash_lines", amount=amount, is_short=False) or [
            LineSpec(account_code=ACC.CASH, debit=amount, memo=description),
            LineSpec(account_code=ACC.OTHER_INCOME, credit=amount, memo=description),
        ]

    entry = await posting.post(
        db,
        event_type=event_type,
        source_type=SourceType.SHIFT,
        source_id=shift.id,
        entry_date=entry_date,
        description=description,
        lines=lines,
        posted_by=user.id,
    )
    await db.flush()
    return [
        {
            "entry_no": getattr(entry, "entry_no", None) if entry is not None else None,
            "event_type": str(event_type),
            "description": description,
            "amount": amount,
        }
    ]


async def repost_cash_difference(
    db: AsyncSession,
    user: User,
    *,
    shift: Shift,
    over_short: Decimal,
) -> list[dict[str, Any]]:
    """Кассын зөрүүний бичилтийг дахин бодож бичнэ (нягтлан засварлахад).

    Хуучин илүүдэл/дутагдлын хоёр бичилтийг хоёуланг нь цуцалж (аль нь ч
    байж болно), шинэ зөрүүгээр дахин бичнэ. Ингэснээр ерөнхий дэвтэр
    засварласан дүнтэй үргэлж таарна.
    """
    for event_type in (EventType.SHIFT_CASH_SHORT, EventType.SHIFT_CASH_OVER):
        await posting.reverse(
            db,
            event_type=str(event_type),
            source_type=str(SourceType.SHIFT),
            source_id=shift.id,
        )
    entry_date = (shift.closed_at or datetime.now(UTC)).date()
    return await _post_cash_difference(
        db, user, shift=shift, entry_date=entry_date, over_short=over_short
    )


async def _post_fuel_variance(
    db: AsyncSession,
    user: User,
    *,
    shift: Shift,
    entry_date: Any,
    loss_rows: list[tuple[Tank, Decimal, Decimal]],
    gain_rows: list[tuple[Tank, Decimal, Decimal]],
) -> list[dict[str, Any]]:
    """Савны зөрүү. `(source_type, source_id, event_type)` давхардахгүй тул сав бүрийг
    НЭГ бичилтэд нэгтгэж, сав тус бүр нэг мөр + нэгдсэн эсрэг мөртэй болгоно."""
    posted: list[dict[str, Any]] = []

    if loss_rows:
        total = q2(sum((value for _, _, value in loss_rows), ZERO))
        names = ", ".join(tank.name for tank, _, _ in loss_rows)
        description = _truncate(f"Ээлж №{shift.number} — түлшний дутагдал: {names}")
        lines = [
            LineSpec(
                account_code=ACC.FUEL_LOSS,
                debit=value,
                memo=_truncate(f"{tank.name}: {variance} л дутагдал", 255),
                dims=Dims(fuel_id=tank.fuel_id, tank_id=tank.id),
            )
            for tank, variance, value in loss_rows
        ]
        lines.append(LineSpec(account_code=ACC.INV_FUEL, credit=total, memo=description))
        entry = await posting.post(
            db,
            event_type=EventType.FUEL_VARIANCE_LOSS,
            source_type=SourceType.SHIFT,
            source_id=shift.id,
            entry_date=entry_date,
            description=description,
            lines=lines,
            posted_by=user.id,
        )
        await db.flush()
        posted.append(
            {
                "entry_no": getattr(entry, "entry_no", None) if entry is not None else None,
                "event_type": str(EventType.FUEL_VARIANCE_LOSS),
                "description": description,
                "amount": total,
            }
        )

    if gain_rows:
        total = q2(sum((value for _, _, value in gain_rows), ZERO))
        names = ", ".join(tank.name for tank, _, _ in gain_rows)
        description = _truncate(f"Ээлж №{shift.number} — түлшний илүүдэл: {names}")
        lines = [
            LineSpec(
                account_code=ACC.INV_FUEL,
                debit=value,
                memo=_truncate(f"{tank.name}: {variance} л илүүдэл", 255),
                dims=Dims(fuel_id=tank.fuel_id, tank_id=tank.id),
            )
            for tank, variance, value in gain_rows
        ]
        lines.append(LineSpec(account_code=ACC.OTHER_INCOME, credit=total, memo=description))
        entry = await posting.post(
            db,
            event_type=EventType.FUEL_VARIANCE_GAIN,
            source_type=SourceType.SHIFT,
            source_id=shift.id,
            entry_date=entry_date,
            description=description,
            lines=lines,
            posted_by=user.id,
        )
        await db.flush()
        posted.append(
            {
                "entry_no": getattr(entry, "entry_no", None) if entry is not None else None,
                "event_type": str(EventType.FUEL_VARIANCE_GAIN),
                "description": description,
                "amount": total,
            }
        )

    return posted


# --------------------------------------------------------------------------- #
# Тайлан
# --------------------------------------------------------------------------- #
async def _sales_section(db: AsyncSession, shift: Shift) -> dict[str, Any]:
    scope = _sale_scope(shift)

    totals = (
        await db.execute(
            select(
                func.count(Sale.id),
                func.coalesce(func.sum(Sale.total), ZERO),
                func.coalesce(func.sum(Sale.vat_amount), ZERO),
                func.coalesce(func.sum(Sale.subtotal), ZERO),
                func.coalesce(func.sum(Sale.cogs_total), ZERO),
            ).where(*scope)
        )
    ).one()

    tender_rows = (
        await db.execute(
            select(
                Payment.method,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount), ZERO),
            )
            .select_from(Payment)
            .join(Sale, Payment.sale_id == Sale.id)
            .where(*scope)
            .group_by(Payment.method)
        )
    ).all()
    tender_map = {row[0]: (int(row[1] or 0), q2(_dec(row[2]))) for row in tender_rows}
    by_tender: list[dict[str, Any]] = []
    for method in TENDER_ORDER:
        count, amount = tender_map.pop(method, (0, ZERO))
        if count == 0 and method != PaymentMethod.CASH:
            continue
        by_tender.append(
            {
                "method": str(method),
                "method_name": TENDER_NAMES_MN.get(method, str(method)),
                "count": count,
                "amount": amount,
            }
        )
    for method, (count, amount) in tender_map.items():  # гэнэтийн шинэ хэлбэр гарвал
        by_tender.append(
            {
                "method": str(method),
                "method_name": TENDER_NAMES_MN.get(method, str(method)),
                "count": count,
                "amount": amount,
            }
        )

    item_rows = (
        await db.execute(
            select(
                SaleItem.item_type,
                func.coalesce(func.sum(SaleItem.amount), ZERO),
                func.coalesce(func.sum(SaleItem.qty), ZERO_L),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(*scope)
            .group_by(SaleItem.item_type)
        )
    ).all()
    fuel_amount, fuel_liters, store_amount = ZERO, ZERO_L, ZERO
    for item_type, amount, qty in item_rows:
        if item_type == ItemType.FUEL:
            fuel_amount = q2(_dec(amount))
            fuel_liters = q3(_dec(qty, ZERO_L))
        else:
            store_amount = q2(store_amount + q2(_dec(amount)))

    return {
        "count": int(totals[0] or 0),
        "gross_total": q2(_dec(totals[1])),
        "vat_total": q2(_dec(totals[2])),
        "net_total": q2(_dec(totals[3])),
        "cogs_total": q2(_dec(totals[4])),
        "fuel_amount": fuel_amount,
        "fuel_liters": fuel_liters,
        "store_amount": store_amount,
        "by_tender": by_tender,
    }


async def _fuel_section(db: AsyncSession, shift: Shift) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                Fuel.id,
                Fuel.code,
                Fuel.name_mn,
                func.coalesce(func.sum(SaleItem.qty), ZERO_L),
                func.coalesce(func.sum(SaleItem.amount), ZERO),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Fuel, SaleItem.fuel_id == Fuel.id)
            .where(*_sale_scope(shift), SaleItem.item_type == ItemType.FUEL)
            .group_by(Fuel.id, Fuel.code, Fuel.name_mn, Fuel.sort_order)
            .order_by(Fuel.sort_order, Fuel.code)
        )
    ).all()
    return [
        {
            "fuel_id": row[0],
            "code": row[1],
            "name": row[2],
            "liters": q3(_dec(row[3], ZERO_L)),
            "amount": q2(_dec(row[4])),
        }
        for row in rows
    ]


async def _nozzle_section(db: AsyncSession, shift: Shift) -> list[dict[str, Any]]:
    sales_rows = (
        await db.execute(
            select(
                SaleItem.nozzle_id,
                func.coalesce(func.sum(SaleItem.qty), ZERO_L),
                func.coalesce(func.sum(SaleItem.amount), ZERO),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(*_sale_scope(shift), SaleItem.nozzle_id.is_not(None))
            .group_by(SaleItem.nozzle_id)
        )
    ).all()
    sold = {row[0]: (q3(_dec(row[1], ZERO_L)), q2(_dec(row[2]))) for row in sales_rows}

    opens = await _shift_readings(db, shift, ReadingType.SHIFT_OPEN)
    closes = await _shift_readings(db, shift, ReadingType.SHIFT_CLOSE)

    pairs = (
        await db.execute(
            select(PumpNozzle, Pump)
            .select_from(PumpNozzle)
            .join(Pump, PumpNozzle.pump_id == Pump.id)
            .order_by(Pump.number, PumpNozzle.nozzle_number)
        )
    ).all()

    out: list[dict[str, Any]] = []
    for nozzle, pump in pairs:
        opening = opens.get(nozzle.id)
        closing = closes.get(nozzle.id)
        sold_l, sold_amount = sold.get(nozzle.id, (ZERO_L, ZERO))
        if opening is None and closing is None and sold_l == 0 and sold_amount == 0:
            continue
        delta = q3(closing - opening) if (opening is not None and closing is not None) else None
        out.append(
            {
                "pump_id": pump.id,
                "pump_number": pump.number,
                "pump_name": pump.name,
                "nozzle_id": nozzle.id,
                "nozzle_number": nozzle.nozzle_number,
                "fuel_name": nozzle.fuel.name_mn if nozzle.fuel is not None else "",
                "opening_reading": opening,
                "closing_reading": closing,
                "reading_delta_l": delta,
                "sold_liters": sold_l,
                "sold_amount": sold_amount,
            }
        )
    return out


async def _tank_section(db: AsyncSession, shift: Shift) -> list[dict[str, Any]]:
    levels = (
        await db.scalars(select(ShiftTankLevel).where(ShiftTankLevel.shift_id == shift.id))
    ).all()
    if not levels:
        return []

    tanks = await _load_tanks(db, [level.tank_id for level in levels])
    opens: dict[uuid.UUID, ShiftTankLevel] = {}
    closes: dict[uuid.UUID, ShiftTankLevel] = {}
    for level in levels:
        if level.phase == ShiftPhase.OPEN:
            opens[level.tank_id] = level
        else:
            closes[level.tank_id] = level

    out: list[dict[str, Any]] = []
    for tank_id in {level.tank_id for level in levels}:
        tank = tanks.get(tank_id)
        open_level = opens.get(tank_id)
        close_level = closes.get(tank_id)
        variance = close_level.variance_l if close_level is not None else None
        avg_cost = _dec(tank.avg_cost) if tank is not None else ZERO
        value = q2(abs(_dec(variance, ZERO_L)) * avg_cost) if variance is not None else ZERO
        out.append(
            {
                "tank_id": tank_id,
                "tank_name": tank.name if tank is not None else "—",
                "fuel_name": tank.fuel.name_mn if tank is not None and tank.fuel is not None else "",
                "open_dip": q3(_dec(open_level.dip_liters, ZERO_L)) if open_level is not None else None,
                "close_dip": q3(_dec(close_level.dip_liters, ZERO_L)) if close_level is not None else None,
                "book_liters": q3(_dec(close_level.book_liters, ZERO_L))
                if close_level is not None and close_level.book_liters is not None
                else None,
                "variance_l": q3(_dec(variance, ZERO_L)) if variance is not None else None,
                "variance_value": value,
            }
        )
    out.sort(key=lambda row: str(row["tank_name"]))
    return out


async def _refund_section(db: AsyncSession, shift: Shift) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                Refund.id,
                Sale.number,
                Refund.amount,
                Refund.refund_method,
                Refund.status,
                Refund.reason,
                Refund.decided_at,
            )
            .select_from(Refund)
            .join(Sale, Refund.sale_id == Sale.id)
            .where(Refund.shift_id == shift.id)
            .order_by(Refund.created_at)
        )
    ).all()
    return [
        {
            "id": row[0],
            "sale_number": int(row[1]) if row[1] is not None else None,
            "amount": q2(_dec(row[2])),
            "refund_method": str(row[3]),
            "refund_method_name": TENDER_NAMES_MN.get(row[3], str(row[3])),
            "status": str(row[4]),
            "status_name": REFUND_STATUS_MN.get(row[4], str(row[4])),
            "reason": row[5],
            "decided_at": row[6],
        }
        for row in rows
    ]


async def shift_meta(db: AsyncSession, shift: Shift, *, sales: Mapping[str, Any] | None = None) -> dict[str, Any]:
    names = await _user_names(db, [shift.opened_by, shift.closed_by])
    return {
        "id": shift.id,
        "number": shift.number,
        "status": str(shift.status),
        "status_name": STATUS_NAMES_MN.get(shift.status, str(shift.status)),
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "opened_by": shift.opened_by,
        "opened_by_name": names.get(shift.opened_by),
        "closed_by": shift.closed_by,
        "closed_by_name": names.get(shift.closed_by) if shift.closed_by else None,
        "opening_cash": q2(_dec(shift.opening_cash)),
        "declared_cash": q2(_dec(shift.declared_cash)) if shift.declared_cash is not None else None,
        "expected_cash": q2(_dec(shift.expected_cash)) if shift.expected_cash is not None else None,
        "cash_over_short": q2(_dec(shift.cash_over_short)) if shift.cash_over_short is not None else None,
        "note": shift.note,
        "sales_count": int(sales["count"]) if sales else 0,
        "sales_total": sales["gross_total"] if sales else ZERO,
    }


async def shift_report(
    db: AsyncSession, shift: Shift, *, posted_entries: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Ээлжийн бүрэн тайлан — борлуулалт, түлш, хошуу, сав, касс, буцаалт, ашиг."""
    await db.flush()

    sales = await _sales_section(db, shift)
    fuels = await _fuel_section(db, shift)
    nozzles = await _nozzle_section(db, shift)
    tanks = await _tank_section(db, shift)
    refunds = await _refund_section(db, shift)
    cash_sales, refunds_cash = await _cash_flows(db, shift)
    other_cash = await _other_cash_movement(db, shift)
    meta = await shift_meta(db, shift, sales=sales)

    opening_cash = q2(_dec(shift.opening_cash))
    expected = (
        q2(_dec(shift.expected_cash))
        if shift.expected_cash is not None
        else q2(opening_cash + cash_sales - refunds_cash + other_cash)
    )

    revenue_net = sales["net_total"]
    cogs_total = sales["cogs_total"]
    gross_profit = q2(revenue_net - cogs_total)
    margin = q2(gross_profit / revenue_net * Decimal("100")) if revenue_net > 0 else ZERO

    return {
        "shift": meta,
        "sales": {
            "count": sales["count"],
            "gross_total": sales["gross_total"],
            "vat_total": sales["vat_total"],
            "net_total": sales["net_total"],
            "fuel_amount": sales["fuel_amount"],
            "fuel_liters": sales["fuel_liters"],
            "store_amount": sales["store_amount"],
            "by_tender": sales["by_tender"],
        },
        "fuels": fuels,
        "nozzles": nozzles,
        "tanks": tanks,
        "cash": {
            "opening_cash": opening_cash,
            "cash_sales": cash_sales,
            "refunds": refunds_cash,
            "other_cash": other_cash,
            "expected_cash": expected,
            "declared_cash": q2(_dec(shift.declared_cash)) if shift.declared_cash is not None else None,
            "cash_over_short": q2(_dec(shift.cash_over_short)) if shift.cash_over_short is not None else None,
        },
        "refunds": refunds,
        "profit": {
            "revenue_net": revenue_net,
            "cogs_total": cogs_total,
            "gross_profit": gross_profit,
            "margin_pct": margin,
        },
        "posted_entries": posted_entries or [],
    }


async def current_shift_summary(db: AsyncSession, shift: Shift) -> dict[str, Any]:
    """Нээлттэй ээлжийн шууд хураангуй — төлбөрийн хэлбэрээр, түлшний төрлөөр."""
    sales = await _sales_section(db, shift)
    fuels = await _fuel_section(db, shift)
    cash_sales, refunds_cash = await _cash_flows(db, shift)
    other_cash = await _other_cash_movement(db, shift)
    meta = await shift_meta(db, shift, sales=sales)
    opening_cash = q2(_dec(shift.opening_cash))
    return {
        "shift": meta,
        "sales": {
            "count": sales["count"],
            "gross_total": sales["gross_total"],
            "vat_total": sales["vat_total"],
            "net_total": sales["net_total"],
            "fuel_amount": sales["fuel_amount"],
            "fuel_liters": sales["fuel_liters"],
            "store_amount": sales["store_amount"],
            "by_tender": sales["by_tender"],
        },
        "fuels": fuels,
        "cash": {
            "opening_cash": opening_cash,
            "cash_sales": cash_sales,
            "refunds": refunds_cash,
            "other_cash": other_cash,
            "expected_cash": q2(opening_cash + cash_sales - refunds_cash + other_cash),
            "declared_cash": None,
            "cash_over_short": None,
        },
    }


async def list_shifts(
    db: AsyncSession,
    *,
    date_from: Any = None,
    date_to: Any = None,
    status: str | None = None,
    branch_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Ээлжийн жагсаалт (шүүлт + хуудаслалт)."""
    filters: list[Any] = []
    if date_from is not None:
        filters.append(Shift.opened_at >= day_start(date_from))
    if date_to is not None:
        end = day_end(date_to)
        filters.append(Shift.opened_at <= end)
    if status:
        filters.append(Shift.status == status)
    if branch_id is not None:
        filters.append(Shift.branch_id == branch_id)

    total = await db.scalar(select(func.count(Shift.id)).where(*filters)) or 0

    sales_agg = (
        select(
            Sale.shift_id.label("shift_id"),
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), ZERO).label("sales_total"),
        )
        .where(Sale.status != SaleStatus.DRAFT)
        .group_by(Sale.shift_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(Shift, sales_agg.c.sales_count, sales_agg.c.sales_total)
            .options(noload(Shift.tank_levels))
            .outerjoin(sales_agg, sales_agg.c.shift_id == Shift.id)
            .where(*filters)
            .order_by(Shift.number.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    shifts = [row[0] for row in rows]
    names = await _user_names(db, [s.opened_by for s in shifts] + [s.closed_by for s in shifts])

    items: list[dict[str, Any]] = []
    for shift, sales_count, sales_total in rows:
        items.append(
            {
                "id": shift.id,
                "number": shift.number,
                "status": str(shift.status),
                "status_name": STATUS_NAMES_MN.get(shift.status, str(shift.status)),
                "opened_at": shift.opened_at,
                "closed_at": shift.closed_at,
                "opened_by": shift.opened_by,
                "opened_by_name": names.get(shift.opened_by),
                "closed_by": shift.closed_by,
                "closed_by_name": names.get(shift.closed_by) if shift.closed_by else None,
                "opening_cash": q2(_dec(shift.opening_cash)),
                "declared_cash": q2(_dec(shift.declared_cash)) if shift.declared_cash is not None else None,
                "expected_cash": q2(_dec(shift.expected_cash)) if shift.expected_cash is not None else None,
                "cash_over_short": q2(_dec(shift.cash_over_short))
                if shift.cash_over_short is not None
                else None,
                "note": shift.note,
                "sales_count": int(sales_count or 0),
                "sales_total": q2(_dec(sales_total)),
            }
        )

    return {"items": items, "total": int(total)}
