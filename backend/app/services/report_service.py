"""Тайлан ба хяналтын самбарын үйлчилгээ (WP8).

Бүх тооцоолол SQL агрегатаар хийгдэнэ — хүснэгтийг бүтнээр нь Python руу
хэзээ ч ачаалахгүй. Мөнгө бүгд ``Decimal``, литр ``q3``, мөнгө ``q2``.

Огнооны бүлэглэлт нь ШТС-ийн цагийн бүсээр (``settings.tz``) хийгдэнэ:
``date_trunc(<granularity>, sales.completed_at AT TIME ZONE 'Asia/Ulaanbaatar')``.

ЧУХАЛ: энэ модуль ``db.commit()`` дуудахгүй — зөвхөн уншина.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Text, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import (
    ApprovalStatus,
    InvoiceStatus,
    ItemType,
    PaymentMethod,
    SaleStatus,
    ShiftStatus,
    TankMovementType,
)
from app.models.accounting import ApInvoice, ArInvoice
from app.models.approval import PriceChange, Refund
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank, TankMovement
from app.models.partner import Customer
from app.models.product import Product
from app.models.sale import Payment, Sale, SaleItem
from app.models.shift import Shift
from app.models.user import User
from app.money import q2, q3, vat_from_gross
from app.services import expense_service

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")
HUNDRED = Decimal("100")

#: Төлбөрийн хэрэгслийн дараалал (тайлан бүрт ижил дараалалтай гарна).
TENDER_ORDER: tuple[str, ...] = (
    PaymentMethod.CASH,
    PaymentMethod.CARD,
    PaymentMethod.QR,
    PaymentMethod.TRANSFER,
    PaymentMethod.CONTRACT,
)

TENDER_NAMES_MN: dict[str, str] = {
    PaymentMethod.CASH: "Бэлэн",
    PaymentMethod.CARD: "Карт",
    PaymentMethod.QR: "QR",
    PaymentMethod.TRANSFER: "Шилжүүлэг",
    PaymentMethod.CONTRACT: "Зээл",
}

GRANULARITIES: dict[str, str] = {"day": "day", "month": "month", "year": "year"}

GRANULARITY_NAMES_MN: dict[str, str] = {"day": "Өдрөөр", "month": "Сараар", "year": "Жилээр"}

SALE_TYPE_NAMES_MN: dict[str, str] = {"fuel": "Түлш", "store": "Дэлгүүр", "mixed": "Холимог"}

SALE_STATUS_NAMES_MN: dict[str, str] = {
    SaleStatus.DRAFT: "Ноорог",
    SaleStatus.COMPLETED: "Дууссан",
    SaleStatus.REFUNDED: "Буцаагдсан",
    SaleStatus.PARTIAL_REFUND: "Хэсэгчлэн буцаагдсан",
}

OPEN_INVOICE_STATUSES: tuple[str, ...] = (str(InvoiceStatus.OPEN), str(InvoiceStatus.PARTIAL))


# --------------------------------------------------------------------------- #
# Цаг хугацаа / хөрвүүлэлтийн туслахууд
# --------------------------------------------------------------------------- #
def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.tz)
    except Exception:  # noqa: BLE001 — тохиргоо буруу бол UTC-ээр ажиллана
        return ZoneInfo("UTC")


TZ = _zone()

#: ``timezone('Asia/Ulaanbaatar', ts)`` дуудлагад тодорхой ``text`` төрөл өгнө —
#: ингэснээр PostgreSQL функцийн overload сонголт хоёрдмол утгагүй болно.
_TZ_SQL = cast(literal(settings.tz), Text)


def _local(column: Any) -> Any:
    """timestamptz → ШТС-ийн бүсийн орон нутгийн timestamp."""
    return func.timezone(_TZ_SQL, column)


def _period_expr(granularity: str, column: Any) -> Any:
    return func.date_trunc(cast(literal(granularity), Text), _local(column))


def today_local() -> date:
    return datetime.now(TZ).date()


def _range_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Орон нутгийн огнооны мужийг timezone-той datetime хязгаар болгоно."""
    start = datetime.combine(date_from, time.min, tzinfo=TZ)
    end = datetime.combine(date_to, time.max, tzinfo=TZ)
    return start, end


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _year_start(day: date) -> date:
    return day.replace(month=1, day=1)


def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _m(value: Any) -> Decimal:
    return q2(_dec(value))


def _l(value: Any) -> Decimal:
    return q3(_dec(value, ZERO_L))


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return ZERO
    return q2(part * HUNDRED / whole)


def _vat(gross: Decimal) -> Decimal:
    return vat_from_gross(gross, settings.vat_rate)


def _granularity(value: str | None) -> str:
    key = (value or "day").strip().lower()
    if key not in GRANULARITIES:
        raise HTTPException(status_code=422, detail="Бүлэглэлт зөвхөн day, month, year байна")
    return GRANULARITIES[key]


def _check_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Дуусах огноо эхлэх огнооноос өмнө байж болохгүй")


def _period_label(granularity: str, moment: Any) -> str:
    if moment is None:
        return "—"
    if isinstance(moment, datetime):
        value = moment.date()
    elif isinstance(moment, date):
        value = moment
    else:  # pragma: no cover — драйвер өөр төрөл буцаавал
        return str(moment)
    if granularity == "year":
        return f"{value.year:04d}"
    if granularity == "month":
        return f"{value.year:04d}-{value.month:02d}"
    return value.isoformat()


def _period_date(moment: Any) -> date | None:
    if isinstance(moment, datetime):
        return moment.date()
    if isinstance(moment, date):
        return moment
    return None


def _sale_scope(
    start: datetime, end: datetime, branch_id: uuid.UUID | None = None
) -> tuple[Any, ...]:
    """Тайланд орох борлуулалт: ноорог биш, дуусгасан огноотой, мужид багтсан.

    ``branch_id`` өгвөл зөвхөн тэр салбарын борлуулалт."""
    conditions: tuple[Any, ...] = (
        Sale.status != SaleStatus.DRAFT,
        Sale.completed_at.is_not(None),
        Sale.completed_at >= start,
        Sale.completed_at <= end,
    )
    if branch_id is not None:
        conditions += (Sale.branch_id == branch_id,)
    return conditions


# --------------------------------------------------------------------------- #
# Борлуулалтын хураангуй
# --------------------------------------------------------------------------- #
async def sales_summary(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    granularity: str = "day",
    branch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Хугацааны борлуулалтын хураангуй — өдөр/сар/жилээр бүлэглэсэн."""
    gran = _granularity(granularity)
    _check_range(date_from, date_to)
    start, end = _range_bounds(date_from, date_to)
    scope = _sale_scope(start, end, branch_id)

    period = _period_expr(gran, Sale.completed_at).label("period")
    head_rows = (
        await db.execute(
            select(
                period,
                func.count(Sale.id).label("sale_count"),
                func.coalesce(func.sum(Sale.total), 0).label("total"),
                func.coalesce(func.sum(Sale.vat_amount), 0).label("vat"),
                func.coalesce(func.sum(Sale.cogs_total), 0).label("cogs"),
            )
            .where(*scope)
            .group_by(period)
            .order_by(period)
        )
    ).all()

    item_period = _period_expr(gran, Sale.completed_at).label("period")
    is_fuel = SaleItem.item_type == ItemType.FUEL
    item_rows = (
        await db.execute(
            select(
                item_period,
                func.coalesce(func.sum(case((is_fuel, SaleItem.amount), else_=0)), 0).label("fuel_total"),
                func.coalesce(func.sum(case((is_fuel, 0), else_=SaleItem.amount)), 0).label("store_total"),
                func.coalesce(func.sum(case((is_fuel, SaleItem.qty), else_=0)), 0).label("liters"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(*scope)
            .group_by(item_period)
        )
    ).all()
    items_by_period = {row.period: row for row in item_rows}

    rows: list[dict[str, Any]] = []
    totals = {
        "sale_count": 0,
        "total": ZERO,
        "vat": ZERO,
        "fuel_total": ZERO,
        "store_total": ZERO,
        "liters": ZERO_L,
        "cogs": ZERO,
        "gross_profit": ZERO,
    }

    for row in head_rows:
        detail = items_by_period.get(row.period)
        total = _m(row.total)
        vat = _m(row.vat)
        cogs = _m(row.cogs)
        fuel_total = _m(detail.fuel_total) if detail is not None else ZERO
        store_total = _m(detail.store_total) if detail is not None else ZERO
        liters = _l(detail.liters) if detail is not None else ZERO_L
        gross_profit = q2(total - vat - cogs)

        rows.append(
            {
                "period": _period_label(gran, row.period),
                "period_start": _period_date(row.period),
                "sale_count": int(row.sale_count or 0),
                "total": total,
                "vat": vat,
                "fuel_total": fuel_total,
                "store_total": store_total,
                "liters": liters,
                "cogs": cogs,
                "gross_profit": gross_profit,
            }
        )
        totals["sale_count"] += int(row.sale_count or 0)
        totals["total"] = q2(totals["total"] + total)
        totals["vat"] = q2(totals["vat"] + vat)
        totals["fuel_total"] = q2(totals["fuel_total"] + fuel_total)
        totals["store_total"] = q2(totals["store_total"] + store_total)
        totals["liters"] = q3(totals["liters"] + liters)
        totals["cogs"] = q2(totals["cogs"] + cogs)
        totals["gross_profit"] = q2(totals["gross_profit"] + gross_profit)

    totals["margin_pct"] = _pct(totals["gross_profit"], q2(totals["total"] - totals["vat"]))
    totals["avg_check"] = (
        q2(totals["total"] / Decimal(totals["sale_count"])) if totals["sale_count"] else ZERO
    )

    return {
        "granularity": gran,
        "granularity_name": GRANULARITY_NAMES_MN.get(gran, gran),
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "totals": totals,
    }


# --------------------------------------------------------------------------- #
# Өдрийн дэлгэрэнгүй
# --------------------------------------------------------------------------- #
async def sales_detail(
    db: AsyncSession, day: date, branch_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Нэг өдрийн борлуулалт бүрийн жагсаалт — түгээгч, төлбөрийн задаргаатай."""
    start, end = _range_bounds(day, day)
    scope = _sale_scope(start, end, branch_id)

    sale_rows = (
        await db.execute(
            select(
                Sale.id,
                Sale.number,
                Sale.completed_at,
                Sale.sale_type,
                Sale.status,
                Sale.subtotal,
                Sale.vat_amount,
                Sale.total,
                Sale.cogs_total,
                Sale.cashier_id,
                User.full_name.label("cashier_name"),
                Sale.customer_id,
                Customer.name.label("customer_name"),
            )
            .select_from(Sale)
            .join(User, Sale.cashier_id == User.id)
            .outerjoin(Customer, Sale.customer_id == Customer.id)
            .where(*scope)
            .order_by(Sale.completed_at, Sale.number)
        )
    ).all()

    payment_rows = (
        await db.execute(
            select(
                Payment.sale_id,
                Payment.method,
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0).label("amount"),
            )
            .select_from(Payment)
            .join(Sale, Payment.sale_id == Sale.id)
            .where(*scope)
            .group_by(Payment.sale_id, Payment.method)
        )
    ).all()

    liter_rows = (
        await db.execute(
            select(
                SaleItem.sale_id,
                func.coalesce(func.sum(SaleItem.qty), 0).label("liters"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(*scope, SaleItem.item_type == ItemType.FUEL)
            .group_by(SaleItem.sale_id)
        )
    ).all()
    liters_by_sale = {row.sale_id: _l(row.liters) for row in liter_rows}

    payments_by_sale: dict[uuid.UUID, list[dict[str, Any]]] = {}
    tender_totals: dict[str, dict[str, Any]] = {}
    for row in payment_rows:
        method = str(row.method)
        amount = _m(row.amount)
        payments_by_sale.setdefault(row.sale_id, []).append(
            {
                "method": method,
                "method_name": TENDER_NAMES_MN.get(method, method),
                "amount": amount,
            }
        )
        bucket = tender_totals.setdefault(method, {"count": 0, "amount": ZERO})
        bucket["count"] += int(row.count or 0)
        bucket["amount"] = q2(bucket["amount"] + amount)

    items: list[dict[str, Any]] = []
    totals = {
        "sale_count": 0,
        "total": ZERO,
        "vat": ZERO,
        "subtotal": ZERO,
        "cogs": ZERO,
        "liters": ZERO_L,
        "gross_profit": ZERO,
    }
    for row in sale_rows:
        total = _m(row.total)
        vat = _m(row.vat_amount)
        subtotal = _m(row.subtotal)
        cogs = _m(row.cogs_total)
        liters = liters_by_sale.get(row.id, ZERO_L)
        payments = sorted(
            payments_by_sale.get(row.id, []),
            key=lambda p: TENDER_ORDER.index(p["method"]) if p["method"] in TENDER_ORDER else 99,
        )
        items.append(
            {
                "id": row.id,
                "number": int(row.number or 0),
                "completed_at": row.completed_at,
                "sale_type": str(row.sale_type),
                "sale_type_name": SALE_TYPE_NAMES_MN.get(str(row.sale_type), str(row.sale_type)),
                "status": str(row.status),
                "status_name": SALE_STATUS_NAMES_MN.get(str(row.status), str(row.status)),
                "cashier_id": row.cashier_id,
                "cashier_name": row.cashier_name,
                "customer_id": row.customer_id,
                "customer_name": row.customer_name,
                "liters": liters,
                "subtotal": subtotal,
                "vat": vat,
                "total": total,
                "cogs": cogs,
                "gross_profit": q2(subtotal - cogs),
                "payments": payments,
            }
        )
        totals["sale_count"] += 1
        totals["total"] = q2(totals["total"] + total)
        totals["vat"] = q2(totals["vat"] + vat)
        totals["subtotal"] = q2(totals["subtotal"] + subtotal)
        totals["cogs"] = q2(totals["cogs"] + cogs)
        totals["liters"] = q3(totals["liters"] + liters)
        totals["gross_profit"] = q2(totals["gross_profit"] + q2(subtotal - cogs))

    by_tender: list[dict[str, Any]] = []
    grand = totals["total"]
    for method in TENDER_ORDER:
        bucket = tender_totals.get(method)
        if bucket is None:
            continue
        by_tender.append(
            {
                "method": str(method),
                "label_mn": TENDER_NAMES_MN.get(method, str(method)),
                "count": bucket["count"],
                "amount": bucket["amount"],
                "pct": _pct(bucket["amount"], grand),
            }
        )

    return {"date": day, "items": items, "totals": totals, "by_tender": by_tender}


# --------------------------------------------------------------------------- #
# Түлшний тайлан
# --------------------------------------------------------------------------- #
async def fuel_report(
    db: AsyncSession, date_from: date, date_to: date, branch_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Түлшний төрөл болон насос/хошуу тус бүрийн борлуулалт, ашиг."""
    _check_range(date_from, date_to)
    start, end = _range_bounds(date_from, date_to)
    scope = _sale_scope(start, end, branch_id)

    grade_rows = (
        await db.execute(
            select(
                Fuel.id,
                Fuel.code,
                Fuel.name_mn,
                func.coalesce(func.sum(SaleItem.qty), 0).label("liters"),
                func.coalesce(func.sum(SaleItem.amount), 0).label("revenue"),
                func.coalesce(func.sum(SaleItem.cogs_amount), 0).label("cogs"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Fuel, SaleItem.fuel_id == Fuel.id)
            .where(*scope, SaleItem.item_type == ItemType.FUEL)
            .group_by(Fuel.id, Fuel.code, Fuel.name_mn, Fuel.sort_order)
            .order_by(Fuel.sort_order, Fuel.code)
        )
    ).all()

    grades: list[dict[str, Any]] = []
    grade_totals = {
        "liters": ZERO_L,
        "revenue": ZERO,
        "revenue_net": ZERO,
        "cogs": ZERO,
        "margin": ZERO,
    }
    for row in grade_rows:
        liters = _l(row.liters)
        revenue = _m(row.revenue)
        revenue_net = q2(revenue - _vat(revenue))
        cogs = _m(row.cogs)
        margin = q2(revenue_net - cogs)
        grades.append(
            {
                "fuel_id": row.id,
                "code": row.code,
                "name": row.name_mn,
                "liters": liters,
                "revenue": revenue,
                "revenue_net": revenue_net,
                "cogs": cogs,
                "margin": margin,
                "margin_pct": _pct(margin, revenue_net),
                "avg_price": q2(revenue / liters) if liters > 0 else ZERO,
            }
        )
        grade_totals["liters"] = q3(grade_totals["liters"] + liters)
        grade_totals["revenue"] = q2(grade_totals["revenue"] + revenue)
        grade_totals["revenue_net"] = q2(grade_totals["revenue_net"] + revenue_net)
        grade_totals["cogs"] = q2(grade_totals["cogs"] + cogs)
        grade_totals["margin"] = q2(grade_totals["margin"] + margin)
    grade_totals["margin_pct"] = _pct(grade_totals["margin"], grade_totals["revenue_net"])

    nozzle_rows = (
        await db.execute(
            select(
                Pump.id.label("pump_id"),
                Pump.number.label("pump_number"),
                Pump.name.label("pump_name"),
                PumpNozzle.nozzle_number,
                func.coalesce(func.sum(SaleItem.qty), 0).label("liters"),
                func.coalesce(func.sum(SaleItem.amount), 0).label("amount"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Pump, SaleItem.pump_id == Pump.id)
            .outerjoin(PumpNozzle, SaleItem.nozzle_id == PumpNozzle.id)
            .where(*scope, SaleItem.item_type == ItemType.FUEL)
            .group_by(Pump.id, Pump.number, Pump.name, PumpNozzle.nozzle_number)
            .order_by(Pump.number, PumpNozzle.nozzle_number)
        )
    ).all()

    pumps: list[dict[str, Any]] = []
    pump_totals = {"liters": ZERO_L, "amount": ZERO}
    for row in nozzle_rows:
        liters = _l(row.liters)
        amount = _m(row.amount)
        pumps.append(
            {
                "pump_id": row.pump_id,
                "pump_number": int(row.pump_number or 0),
                "pump_name": row.pump_name,
                "nozzle_number": int(row.nozzle_number) if row.nozzle_number is not None else None,
                "liters": liters,
                "amount": amount,
            }
        )
        pump_totals["liters"] = q3(pump_totals["liters"] + liters)
        pump_totals["amount"] = q2(pump_totals["amount"] + amount)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "grades": grades,
        "grade_totals": grade_totals,
        "pumps": pumps,
        "pump_totals": pump_totals,
    }


# --------------------------------------------------------------------------- #
# Төлбөрийн хэлбэрийн задаргаа
# --------------------------------------------------------------------------- #
async def tender_breakdown(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Төлбөрийн хэрэгсэл тус бүрийн тоо, дүн, эзлэх хувь."""
    _check_range(date_from, date_to)
    start, end = _range_bounds(date_from, date_to)
    scope = _sale_scope(start, end, branch_id)

    rows = (
        await db.execute(
            select(
                Payment.method,
                func.count(Payment.id).label("count"),
                func.coalesce(func.sum(Payment.amount), 0).label("amount"),
            )
            .select_from(Payment)
            .join(Sale, Payment.sale_id == Sale.id)
            .where(*scope)
            .group_by(Payment.method)
        )
    ).all()

    by_method = {str(row.method): (int(row.count or 0), _m(row.amount)) for row in rows}
    total = q2(sum((amount for _, amount in by_method.values()), ZERO))
    total_count = sum(count for count, _ in by_method.values())

    ordered = list(TENDER_ORDER) + [m for m in by_method if m not in TENDER_ORDER]
    items: list[dict[str, Any]] = []
    for method in ordered:
        count, amount = by_method.get(str(method), (0, ZERO))
        if count == 0 and amount == 0:
            continue
        items.append(
            {
                "method": str(method),
                "label_mn": TENDER_NAMES_MN.get(method, str(method)),
                "count": count,
                "amount": amount,
                "pct": _pct(amount, total),
            }
        )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "items": items,
        "total": total,
        "total_count": total_count,
    }


async def _tender_map(
    db: AsyncSession, start: datetime, end: datetime, branch_id: uuid.UUID | None = None
) -> dict[str, Decimal]:
    """``{арга: дүн}`` — бүх аргыг (0 утгатайг ч) агуулсан толь."""
    rows = (
        await db.execute(
            select(
                Payment.method,
                func.coalesce(func.sum(Payment.amount), 0).label("amount"),
            )
            .select_from(Payment)
            .join(Sale, Payment.sale_id == Sale.id)
            .where(*_sale_scope(start, end, branch_id))
            .group_by(Payment.method)
        )
    ).all()
    found = {str(row.method): _m(row.amount) for row in rows}
    return {str(method): found.get(str(method), ZERO) for method in TENDER_ORDER}


# --------------------------------------------------------------------------- #
# Шилдэг жагсаалтууд
# --------------------------------------------------------------------------- #
async def top_products(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    limit: int = 10,
    branch_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Хамгийн их борлуулалттай бараа."""
    _check_range(date_from, date_to)
    start, end = _range_bounds(date_from, date_to)

    rows = (
        await db.execute(
            select(
                Product.id,
                Product.sku,
                Product.name_mn,
                Product.unit,
                func.coalesce(func.sum(SaleItem.qty), 0).label("qty"),
                func.coalesce(func.sum(SaleItem.amount), 0).label("amount"),
                func.coalesce(func.sum(SaleItem.cogs_amount), 0).label("cogs"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .join(Product, SaleItem.product_id == Product.id)
            .where(*_sale_scope(start, end, branch_id), SaleItem.item_type == ItemType.PRODUCT)
            .group_by(Product.id, Product.sku, Product.name_mn, Product.unit)
            .order_by(func.coalesce(func.sum(SaleItem.amount), 0).desc())
            .limit(limit)
        )
    ).all()

    result: list[dict[str, Any]] = []
    for row in rows:
        amount = _m(row.amount)
        cogs = _m(row.cogs)
        net = q2(amount - _vat(amount))
        margin = q2(net - cogs)
        result.append(
            {
                "product_id": row.id,
                "sku": row.sku,
                "name": row.name_mn,
                "unit": row.unit,
                "qty": _l(row.qty),
                "amount": amount,
                "cogs": cogs,
                "margin": margin,
                "margin_pct": _pct(margin, net),
            }
        )
    return result


async def top_customers(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    limit: int = 10,
    branch_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Хамгийн их худалдан авалттай харилцагч."""
    _check_range(date_from, date_to)
    start, end = _range_bounds(date_from, date_to)
    scope = _sale_scope(start, end, branch_id)

    rows = (
        await db.execute(
            select(
                Customer.id,
                Customer.name,
                Customer.type,
                func.count(Sale.id).label("sale_count"),
                func.coalesce(func.sum(Sale.total), 0).label("total"),
            )
            .select_from(Sale)
            .join(Customer, Sale.customer_id == Customer.id)
            .where(*scope)
            .group_by(Customer.id, Customer.name, Customer.type)
            .order_by(func.coalesce(func.sum(Sale.total), 0).desc())
            .limit(limit)
        )
    ).all()
    if not rows:
        return []

    customer_ids = [row.id for row in rows]
    liter_rows = (
        await db.execute(
            select(
                Sale.customer_id,
                func.coalesce(func.sum(SaleItem.qty), 0).label("liters"),
            )
            .select_from(SaleItem)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(
                *scope,
                SaleItem.item_type == ItemType.FUEL,
                Sale.customer_id.in_(customer_ids),
            )  # scope нь салбарын шүүлтийг агуулна
            .group_by(Sale.customer_id)
        )
    ).all()
    liters_by_customer = {row.customer_id: _l(row.liters) for row in liter_rows}

    return [
        {
            "customer_id": row.id,
            "name": row.name,
            "type": str(row.type),
            "sale_count": int(row.sale_count or 0),
            "total": _m(row.total),
            "liters": liters_by_customer.get(row.id, ZERO_L),
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# Савны хорогдол
# --------------------------------------------------------------------------- #
async def tank_loss_report(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Сав тус бүрийн хэмжилтийн зөрүү (дутагдал/илүүдэл) литр ба өртгөөр."""
    _check_range(date_from, date_to)
    start, end = _range_bounds(date_from, date_to)

    branch_scope = (Tank.branch_id == branch_id,) if branch_id is not None else ()
    is_loss = TankMovement.liters < 0
    rows = (
        await db.execute(
            select(
                Tank.id,
                Tank.name,
                Fuel.code.label("fuel_code"),
                Fuel.name_mn.label("fuel_name"),
                func.coalesce(func.sum(TankMovement.liters), 0).label("liters"),
                func.coalesce(func.sum(TankMovement.liters * TankMovement.unit_cost), 0).label("value"),
                func.coalesce(func.sum(case((is_loss, TankMovement.liters), else_=0)), 0).label("loss_liters"),
                func.coalesce(func.sum(case((is_loss, 0), else_=TankMovement.liters)), 0).label("gain_liters"),
                func.count(TankMovement.id).label("movement_count"),
            )
            .select_from(TankMovement)
            .join(Tank, TankMovement.tank_id == Tank.id)
            .join(Fuel, Tank.fuel_id == Fuel.id)
            .where(
                TankMovement.movement_type == TankMovementType.VARIANCE,
                TankMovement.created_at >= start,
                TankMovement.created_at <= end,
                *branch_scope,
            )
            .group_by(Tank.id, Tank.name, Fuel.code, Fuel.name_mn)
            .order_by(Tank.name)
        )
    ).all()

    items: list[dict[str, Any]] = []
    totals = {
        "liters": ZERO_L,
        "value": ZERO,
        "loss_liters": ZERO_L,
        "gain_liters": ZERO_L,
        "movement_count": 0,
    }
    for row in rows:
        liters = _l(row.liters)
        value = _m(row.value)
        loss_liters = _l(row.loss_liters)
        gain_liters = _l(row.gain_liters)
        items.append(
            {
                "tank_id": row.id,
                "tank_name": row.name,
                "fuel_code": row.fuel_code,
                "fuel_name": row.fuel_name,
                "liters": liters,
                "value": value,
                "loss_liters": loss_liters,
                "gain_liters": gain_liters,
                "movement_count": int(row.movement_count or 0),
            }
        )
        totals["liters"] = q3(totals["liters"] + liters)
        totals["value"] = q2(totals["value"] + value)
        totals["loss_liters"] = q3(totals["loss_liters"] + loss_liters)
        totals["gain_liters"] = q3(totals["gain_liters"] + gain_liters)
        totals["movement_count"] += int(row.movement_count or 0)

    return {"date_from": date_from, "date_to": date_to, "items": items, "totals": totals}


# --------------------------------------------------------------------------- #
# Хяналтын самбарын туслахууд
# --------------------------------------------------------------------------- #
async def _sales_totals(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    *,
    cashier_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Мужийн нийт борлуулалт (тоо, дүн, НӨАТ, өртөг, ашиг) + литр."""
    scope: list[Any] = list(_sale_scope(start, end))
    if cashier_id is not None:
        scope.append(Sale.cashier_id == cashier_id)
    if branch_id is not None:
        scope.append(Sale.branch_id == branch_id)

    head = (
        await db.execute(
            select(
                func.count(Sale.id).label("sale_count"),
                func.coalesce(func.sum(Sale.total), 0).label("total"),
                func.coalesce(func.sum(Sale.vat_amount), 0).label("vat"),
                func.coalesce(func.sum(Sale.cogs_total), 0).label("cogs"),
            ).where(*scope)
        )
    ).one()

    liters = await db.scalar(
        select(func.coalesce(func.sum(SaleItem.qty), 0))
        .select_from(SaleItem)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(*scope, SaleItem.item_type == ItemType.FUEL)
    )

    total = _m(head.total)
    vat = _m(head.vat)
    cogs = _m(head.cogs)
    return {
        "sale_count": int(head.sale_count or 0),
        "sales_total": total,
        "total": total,
        "vat": vat,
        "cogs": cogs,
        "liters": _l(liters),
        "gross_profit": q2(total - vat - cogs),
    }


async def _tank_levels(
    db: AsyncSession, branch_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    conditions = [Tank.is_active.is_(True)]
    if branch_id is not None:
        conditions.append(Tank.branch_id == branch_id)
    rows = (
        await db.execute(
            select(
                Tank.id,
                Tank.name,
                Tank.capacity_l,
                Tank.current_l,
                Tank.min_level_l,
                Tank.avg_cost,
                Fuel.code.label("fuel_code"),
                Fuel.name_mn.label("fuel_name"),
            )
            .select_from(Tank)
            .join(Fuel, Tank.fuel_id == Fuel.id)
            .where(*conditions)
            .order_by(Tank.name)
        )
    ).all()

    tanks: list[dict[str, Any]] = []
    for row in rows:
        capacity = _l(row.capacity_l)
        current = _l(row.current_l)
        minimum = _l(row.min_level_l)
        tanks.append(
            {
                "tank_id": row.id,
                "name": row.name,
                "fuel_code": row.fuel_code,
                "fuel_name": row.fuel_name,
                "current_l": current,
                "capacity_l": capacity,
                "min_level_l": minimum,
                "fill_pct": _pct(current, capacity),
                "is_low": bool(minimum > 0 and current <= minimum),
                "value": q2(current * _dec(row.avg_cost)),
            }
        )
    return tanks


async def _pump_states(
    db: AsyncSession, branch_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    conditions = [Pump.is_active.is_(True)]
    if branch_id is not None:
        conditions.append(Pump.branch_id == branch_id)
    rows = (
        await db.execute(
            select(Pump.id, Pump.number, Pump.name, Pump.status)
            .where(*conditions)
            .order_by(Pump.number)
        )
    ).all()
    return [
        {
            "pump_id": row.id,
            "number": int(row.number or 0),
            "name": row.name,
            "status": str(row.status),
        }
        for row in rows
    ]


async def _open_shift_meta(db: AsyncSession) -> dict[str, Any] | None:
    shift = await db.scalar(
        select(Shift)
        .where(Shift.status == ShiftStatus.OPEN)
        .order_by(Shift.opened_at.desc())
        .limit(1)
    )
    if shift is None:
        return None
    opener = await db.scalar(select(User.full_name).where(User.id == shift.opened_by))
    sales = await _sales_totals(
        db,
        shift.opened_at,
        datetime.now(TZ),
    )
    return {
        "id": shift.id,
        "number": shift.number,
        "status": str(shift.status),
        "opened_at": shift.opened_at,
        "opened_by": shift.opened_by,
        "opened_by_name": opener,
        "opening_cash": _m(shift.opening_cash),
        "sales_count": sales["sale_count"],
        "sales_total": sales["sales_total"],
    }


# --------------------------------------------------------------------------- #
# Түгээгчийн хяналтын самбар
# --------------------------------------------------------------------------- #
async def cashier_dashboard(db: AsyncSession, user: User) -> dict[str, Any]:
    """Түгээгчийн нүүр самбар — нээлттэй ээлж, өнөөдрийн дүн, сав, насос.

    ``today`` нь тухайн түгээгчийн өнөөдрийн борлуулалт, ``station_today`` нь
    ШТС-ийн нийт дүн.
    """
    day = today_local()
    start, end = _range_bounds(day, day)

    # Түгээгч зөвхөн өөрийн салбарын дүнг харна; салбаргүй (менежер, эзэн) бол бүгд.
    branch_id = getattr(user, "branch_id", None)

    mine = await _sales_totals(db, start, end, cashier_id=user.id)
    station = await _sales_totals(db, start, end, branch_id=branch_id)
    tender = await _tender_map(db, start, end, branch_id)

    return {
        "date": day,
        "shift": await _open_shift_meta(db),
        "today": {
            "total": mine["total"],
            "sale_count": mine["sale_count"],
            "liters": mine["liters"],
            "by_tender": tender,
        },
        "station_today": {
            "total": station["total"],
            "sale_count": station["sale_count"],
            "liters": station["liters"],
            "gross_profit": station["gross_profit"],
        },
        "tanks": await _tank_levels(db, branch_id),
        "pumps": await _pump_states(db, branch_id),
    }


# --------------------------------------------------------------------------- #
# Эзний хяналтын самбар
# --------------------------------------------------------------------------- #
async def _branch_breakdown(
    db: AsyncSession, day_start: datetime, day_end: datetime,
    month_start: datetime, month_end: datetime,
) -> list[dict[str, Any]]:
    """Салбар тус бүрийн өнөөдөр/сарын дүн — эзний харьцуулалтад."""
    from app.models.branch import Branch

    branches = (
        await db.scalars(
            select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.sort_order, Branch.name)
        )
    ).all()

    out: list[dict[str, Any]] = []
    for branch in branches:
        today = await _sales_totals(db, day_start, day_end, branch_id=branch.id)
        month = await _sales_totals(db, month_start, month_end, branch_id=branch.id)
        out.append(
            {
                "branch_id": branch.id,
                "name": branch.name,
                "today_total": today["sales_total"],
                "today_liters": today["liters"],
                "today_sale_count": today["sale_count"],
                "month_total": month["sales_total"],
                "month_liters": month["liters"],
                "month_gross_profit": month["gross_profit"],
            }
        )
    return out


async def owner_dashboard(
    db: AsyncSession, branch_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Эзний хяналтын самбар — өнөөдөр/сар/жилийн дүн, сав, хорогдол, авлага өглөг.

    ``branch_id`` өгвөл зөвхөн тэр салбарын дүн; эс бөгөөс бүх салбарын нийлбэр
    дээр нэмж салбар тус бүрийн задаргаа.
    """
    day = today_local()
    day_start, day_end = _range_bounds(day, day)
    month_from = _month_start(day)
    month_start, month_end = _range_bounds(month_from, day)
    year_from = _year_start(day)
    year_start, year_end = _range_bounds(year_from, day)

    today = await _sales_totals(db, day_start, day_end, branch_id=branch_id)
    month = await _sales_totals(db, month_start, month_end, branch_id=branch_id)
    year = await _sales_totals(db, year_start, year_end, branch_id=branch_id)

    loss = await tank_loss_report(db, month_from, day, branch_id)
    tender_today = await tender_breakdown(db, day, day, branch_id)

    # Батлах хүсэлтүүд: үнийн өөрчлөлтийн branch_id=NULL нь БҮХ салбарт
    # үйлчилдэг тул салбарын горимд түүнийг ч хамруулна.
    price_scope = (
        [or_(PriceChange.branch_id == branch_id, PriceChange.branch_id.is_(None))]
        if branch_id is not None
        else []
    )
    pending_prices = await db.scalar(
        select(func.count(PriceChange.id)).where(
            PriceChange.status == ApprovalStatus.PENDING, *price_scope
        )
    )
    refund_stmt = select(func.count(Refund.id)).where(Refund.status == ApprovalStatus.PENDING)
    if branch_id is not None:
        # Буцаалт нь ээлжээрээ салбартай холбогдоно.
        refund_stmt = refund_stmt.join(Shift, Refund.shift_id == Shift.id).where(
            Shift.branch_id == branch_id
        )
    pending_refunds = await db.scalar(refund_stmt)

    ar_open = await db.scalar(
        select(func.coalesce(func.sum(ArInvoice.amount - ArInvoice.amount_paid), 0)).where(
            ArInvoice.status.in_(OPEN_INVOICE_STATUSES)
        )
    )
    ar_overdue = await db.scalar(
        select(func.coalesce(func.sum(ArInvoice.amount - ArInvoice.amount_paid), 0)).where(
            ArInvoice.status.in_(OPEN_INVOICE_STATUSES),
            ArInvoice.period_end < day,
        )
    )
    ap_open = await db.scalar(
        select(func.coalesce(func.sum(ApInvoice.amount_gross - ApInvoice.amount_paid), 0)).where(
            ApInvoice.status.in_(OPEN_INVOICE_STATUSES)
        )
    )

    # Үйл ажиллагааны зардал — бохир ашгаас хасаж цэвэр ашгийг гаргана.
    expense_today = await expense_service.expense_total(db, day, day, branch_id)
    expense_month = await expense_service.expense_total(db, month_from, day, branch_id)

    return {
        "date": day,
        "today": {
            "sales_total": today["sales_total"],
            "liters": today["liters"],
            "sale_count": today["sale_count"],
            "gross_profit": today["gross_profit"],
            "expense_total": expense_today,
            "net_profit": q2(today["gross_profit"] - expense_today),
        },
        "month": {
            "sales_total": month["sales_total"],
            "liters": month["liters"],
            "gross_profit": month["gross_profit"],
            "expense_total": expense_month,
            "net_profit": q2(month["gross_profit"] - expense_month),
        },
        "year": {"sales_total": year["sales_total"]},
        "tanks": await _tank_levels(db, branch_id),
        "branches": (
            []
            if branch_id is not None
            else await _branch_breakdown(db, day_start, day_end, month_start, month_end)
        ),
        "tank_loss_mtd": {
            "liters": loss["totals"]["liters"],
            "value": loss["totals"]["value"],
        },
        "tender_breakdown_today": tender_today["items"],
        "top_products": await top_products(db, month_from, day, 5, branch_id),
        "pending": {
            "price_changes": int(pending_prices or 0),
            "refunds": int(pending_refunds or 0),
        },
        "ar": {"open_total": _m(ar_open), "overdue_total": _m(ar_overdue)},
        "ap": {"open_total": _m(ap_open)},
    }
