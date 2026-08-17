"""Санхүүгийн тайлангийн үйлчилгээ — журналаас шууд тооцоолно.

Бүх функц энгийн ``dict`` буцаана (мөнгө нь ``Decimal``). Тайлан бүр журналын
мөрүүдийг эх сурвалж болгодог тул домэйн хүснэгттэй зөрөх боломжийг
``integrity_check`` илрүүлнэ.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AccountType
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.fuel import Fuel, Tank
from app.models.partner import Contract
from app.models.product import Product
from app.money import q2
from app.services.coa import ACC

ZERO = Decimal("0")

#: Дебит талдаа хэвийн үлдэгдэлтэй дансны төрлүүд.
DEBIT_NORMAL: frozenset[str] = frozenset({str(AccountType.ASSET), str(AccountType.EXPENSE)})

#: Мөнгөн гүйлгээний тайланд хамаарах данснууд (шууд арга).
CASH_ACCOUNTS: tuple[str, ...] = (ACC.CASH, ACC.BANK)


# --------------------------------------------------------------------------- #
# Дотоод туслахууд
# --------------------------------------------------------------------------- #
def _natural(account_type: str, debit: Decimal, credit: Decimal) -> Decimal:
    """Дансны төрлөөс хамаарсан хэвийн үлдэгдэл."""
    if str(account_type) in DEBIT_NORMAL:
        return q2(debit - credit)
    return q2(credit - debit)


def _apply_period(stmt: Select, date_from: date | None, date_to: date | None) -> Select:
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    return stmt


async def _totals_by_account(
    db: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, tuple[Decimal, Decimal]]:
    """``{дансны код: (Σдебит, Σкредит)}``."""
    stmt = (
        select(
            JournalLine.account_code,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .group_by(JournalLine.account_code)
    )
    stmt = _apply_period(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()
    return {row.account_code: (q2(row.debit), q2(row.credit)) for row in rows}


async def _account_map(db: AsyncSession) -> list[Account]:
    return list((await db.scalars(select(Account).order_by(Account.sort_order, Account.code))).all())


async def _account_balance(
    db: AsyncSession,
    code: str,
    *,
    as_of: date | None = None,
) -> Decimal:
    """Нэг дансны дебит − кредит үлдэгдэл."""
    stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0) - func.coalesce(func.sum(JournalLine.credit), 0)
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.account_code == code)
    )
    stmt = _apply_period(stmt, None, as_of)
    return q2(await db.scalar(stmt) or 0)


async def _tank_rows(db: AsyncSession) -> list[dict[str, Any]]:
    tanks = list((await db.scalars(select(Tank).order_by(Tank.name))).all())
    rows: list[dict[str, Any]] = []
    for tank in tanks:
        qty = Decimal(tank.current_l or 0)
        avg = Decimal(tank.avg_cost or 0)
        rows.append(
            {
                "tank_id": tank.id,
                "tank_name": tank.name,
                "fuel_id": tank.fuel_id,
                "fuel_name_mn": tank.fuel.name_mn if tank.fuel is not None else None,
                "qty": qty,
                "avg_cost": avg,
                "value": q2(qty * avg),
            }
        )
    return rows


async def _product_rows(db: AsyncSession) -> list[dict[str, Any]]:
    products = list((await db.scalars(select(Product).order_by(Product.name_mn))).all())
    rows: list[dict[str, Any]] = []
    for product in products:
        qty = Decimal(product.stock_qty or 0)
        avg = Decimal(product.avg_cost or 0)
        rows.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name_mn": product.name_mn,
                "qty": qty,
                "avg_cost": avg,
                "value": q2(qty * avg),
            }
        )
    return rows


def _sum_values(rows: list[dict[str, Any]]) -> Decimal:
    return q2(sum((row["value"] for row in rows), ZERO))


# --------------------------------------------------------------------------- #
# Гүйлгээний баланс
# --------------------------------------------------------------------------- #
async def trial_balance(db: AsyncSession, as_of: date | None = None) -> dict[str, Any]:
    """Гүйлгээний баланс — хөдөлгөөнтэй данс бүрийн дебит/кредит/үлдэгдэл."""
    totals = await _totals_by_account(db, date_to=as_of)
    accounts = await _account_map(db)

    rows: list[dict[str, Any]] = []
    total_debit = ZERO
    total_credit = ZERO
    for account in accounts:
        debit, credit = totals.get(account.code, (ZERO, ZERO))
        if debit == 0 and credit == 0:
            continue
        total_debit = q2(total_debit + debit)
        total_credit = q2(total_credit + credit)
        rows.append(
            {
                "code": account.code,
                "name_mn": account.name_mn,
                "account_type": account.account_type,
                "debit": debit,
                "credit": credit,
                "balance": _natural(account.account_type, debit, credit),
            }
        )

    return {
        "as_of": as_of,
        "accounts": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "imbalance": q2(total_debit - total_credit),
    }


# --------------------------------------------------------------------------- #
# Орлого үр дүнгийн тайлан
# --------------------------------------------------------------------------- #
async def income_statement(db: AsyncSession, date_from: date, date_to: date) -> dict[str, Any]:
    """Орлого, өртөг, зардлын тайлан + түлш тус бүрийн ашгийн задаргаа."""
    totals = await _totals_by_account(db, date_from=date_from, date_to=date_to)
    accounts = await _account_map(db)

    revenue: list[dict[str, Any]] = []
    cogs: list[dict[str, Any]] = []
    expense: list[dict[str, Any]] = []
    total_revenue = ZERO
    total_cogs = ZERO
    total_expense = ZERO

    for account in accounts:
        debit, credit = totals.get(account.code, (ZERO, ZERO))
        if debit == 0 and credit == 0:
            continue
        acc_type = str(account.account_type)
        row = {"code": account.code, "name_mn": account.name_mn, "amount": ZERO}
        if acc_type == str(AccountType.REVENUE):
            row["amount"] = q2(credit - debit)
            total_revenue = q2(total_revenue + row["amount"])
            revenue.append(row)
        elif acc_type == str(AccountType.EXPENSE):
            row["amount"] = q2(debit - credit)
            if account.code in ACC.COGS_ACCOUNTS:
                total_cogs = q2(total_cogs + row["amount"])
                cogs.append(row)
            else:
                total_expense = q2(total_expense + row["amount"])
                expense.append(row)

    gross_profit = q2(total_revenue - total_cogs)
    net_profit = q2(gross_profit - total_expense)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "revenue": revenue,
        "total_revenue": total_revenue,
        "cogs": cogs,
        "total_cogs": total_cogs,
        "expense": expense,
        "total_expense": total_expense,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "fuel_margins": await _fuel_margins(db, date_from, date_to),
    }


async def _fuel_margins(db: AsyncSession, date_from: date, date_to: date) -> list[dict[str, Any]]:
    """Түлш тус бүрийн орлого/өртөг/ашиг (4101 ба 5101 мөрийн dim_fuel_id-аар)."""
    stmt = (
        select(
            JournalLine.dim_fuel_id,
            JournalLine.account_code,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.account_code.in_([ACC.REV_FUEL, ACC.COGS_FUEL]),
            JournalLine.dim_fuel_id.is_not(None),
        )
        .group_by(JournalLine.dim_fuel_id, JournalLine.account_code)
    )
    stmt = _apply_period(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()

    buckets: dict[uuid.UUID, dict[str, Decimal]] = {}
    for row in rows:
        bucket = buckets.setdefault(row.dim_fuel_id, {"revenue": ZERO, "cogs": ZERO})
        if row.account_code == ACC.REV_FUEL:
            bucket["revenue"] = q2(bucket["revenue"] + q2(row.credit) - q2(row.debit))
        else:
            bucket["cogs"] = q2(bucket["cogs"] + q2(row.debit) - q2(row.credit))

    names: dict[uuid.UUID, str] = {}
    if buckets:
        fuels = (await db.scalars(select(Fuel).where(Fuel.id.in_(list(buckets.keys()))))).all()
        names = {fuel.id: fuel.name_mn for fuel in fuels}

    result: list[dict[str, Any]] = []
    for fuel_id, bucket in buckets.items():
        revenue = bucket["revenue"]
        cogs = bucket["cogs"]
        margin = q2(revenue - cogs)
        margin_pct = q2(margin * Decimal(100) / revenue) if revenue != 0 else ZERO
        result.append(
            {
                "fuel_id": fuel_id,
                "fuel_name_mn": names.get(fuel_id),
                "revenue": revenue,
                "cogs": cogs,
                "margin": margin,
                "margin_pct": margin_pct,
            }
        )
    result.sort(key=lambda item: item["revenue"], reverse=True)
    return result


# --------------------------------------------------------------------------- #
# Баланс
# --------------------------------------------------------------------------- #
async def balance_sheet(db: AsyncSession, as_of: date | None = None) -> dict[str, Any]:
    """Санхүүгийн байдлын тайлан. Тайлант үеийн ашгийг эздийн өмчид оруулна."""
    totals = await _totals_by_account(db, date_to=as_of)
    accounts = await _account_map(db)

    assets: list[dict[str, Any]] = []
    liabilities: list[dict[str, Any]] = []
    equity: list[dict[str, Any]] = []
    total_assets = ZERO
    total_liabilities = ZERO
    total_equity = ZERO
    period_revenue = ZERO
    period_expense = ZERO

    for account in accounts:
        debit, credit = totals.get(account.code, (ZERO, ZERO))
        if debit == 0 and credit == 0:
            continue
        acc_type = str(account.account_type)
        balance = _natural(acc_type, debit, credit)
        row = {"code": account.code, "name_mn": account.name_mn, "balance": balance}
        if acc_type == str(AccountType.ASSET):
            total_assets = q2(total_assets + balance)
            assets.append(row)
        elif acc_type == str(AccountType.LIABILITY):
            total_liabilities = q2(total_liabilities + balance)
            liabilities.append(row)
        elif acc_type == str(AccountType.EQUITY):
            total_equity = q2(total_equity + balance)
            equity.append(row)
        elif acc_type == str(AccountType.REVENUE):
            period_revenue = q2(period_revenue + balance)
        elif acc_type == str(AccountType.EXPENSE):
            period_expense = q2(period_expense + balance)

    retained_earnings = q2(period_revenue - period_expense)
    equity.append(
        {
            "code": ACC.CURRENT_EARNINGS,
            "name_mn": "Тайлант үеийн ашиг (алдагдал)",
            "balance": retained_earnings,
        }
    )
    total_equity = q2(total_equity + retained_earnings)

    difference = q2(total_assets - q2(total_liabilities + total_equity))
    return {
        "as_of": as_of,
        "assets": assets,
        "total_assets": total_assets,
        "liabilities": liabilities,
        "total_liabilities": total_liabilities,
        "equity": equity,
        "total_equity": total_equity,
        "retained_earnings": retained_earnings,
        "total_liabilities_equity": q2(total_liabilities + total_equity),
        "is_balanced": difference == 0,
        "difference": difference,
    }


# --------------------------------------------------------------------------- #
# Мөнгөн гүйлгээ (шууд арга)
# --------------------------------------------------------------------------- #
async def cash_flow(db: AsyncSession, date_from: date, date_to: date) -> dict[str, Any]:
    """1101 ба 1110 дансны хөдөлгөөнийг үйл явдлын төрлөөр задалсан тайлан."""
    opening_stmt = (
        select(
            func.coalesce(func.sum(JournalLine.debit), 0) - func.coalesce(func.sum(JournalLine.credit), 0)
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.account_code.in_(list(CASH_ACCOUNTS)),
            JournalEntry.entry_date < date_from,
        )
    )
    opening = q2(await db.scalar(opening_stmt) or 0)

    flow_stmt = (
        select(
            JournalEntry.event_type,
            func.coalesce(func.sum(JournalLine.debit), 0).label("inflow"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("outflow"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(JournalLine.account_code.in_(list(CASH_ACCOUNTS)))
        .group_by(JournalEntry.event_type)
        .order_by(JournalEntry.event_type)
    )
    flow_stmt = _apply_period(flow_stmt, date_from, date_to)
    rows = (await db.execute(flow_stmt)).all()

    flows: list[dict[str, Any]] = []
    total_inflow = ZERO
    total_outflow = ZERO
    for row in rows:
        inflow = q2(row.inflow)
        outflow = q2(row.outflow)
        total_inflow = q2(total_inflow + inflow)
        total_outflow = q2(total_outflow + outflow)
        flows.append(
            {
                "event_type": row.event_type,
                "inflow": inflow,
                "outflow": outflow,
                "net": q2(inflow - outflow),
            }
        )

    net_change = q2(total_inflow - total_outflow)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "accounts": list(CASH_ACCOUNTS),
        "opening_balance": opening,
        "flows": flows,
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
        "net_change": net_change,
        "closing_balance": q2(opening + net_change),
    }


# --------------------------------------------------------------------------- #
# Нөөцийн үнэлгээ
# --------------------------------------------------------------------------- #
async def inventory_valuation(db: AsyncSession) -> dict[str, Any]:
    """Сав ба барааны бодит үнэлгээг журналын үлдэгдэлтэй тулгана."""
    tanks = await _tank_rows(db)
    products = await _product_rows(db)
    fuel_value = _sum_values(tanks)
    goods_value = _sum_values(products)

    ledger_fuel = await _account_balance(db, ACC.INV_FUEL)
    ledger_goods = await _account_balance(db, ACC.INV_GOODS)

    return {
        "tanks": tanks,
        "products": products,
        "fuel_value": fuel_value,
        "goods_value": goods_value,
        "total_value": q2(fuel_value + goods_value),
        "ledger_fuel": ledger_fuel,
        "ledger_goods": ledger_goods,
        "ledger_total": q2(ledger_fuel + ledger_goods),
        "fuel_delta": q2(ledger_fuel - fuel_value),
        "goods_delta": q2(ledger_goods - goods_value),
        "total_delta": q2(q2(ledger_fuel + ledger_goods) - q2(fuel_value + goods_value)),
    }


# --------------------------------------------------------------------------- #
# Бүрэн бүтэн байдлын шалгалт
# --------------------------------------------------------------------------- #
#: Нөөцийн тулгалтад зөвшөөрөх бөөрөнхийлөлтийн хязгаар.
#: Жигнэсэн дундаж өртөг 6 оронтой, харин бичилт бүр 2 орон хүртэл
#: бөөрөнхийлөгддөг тул гүйлгээ бүрт ≤0.005₮ зөрүү үүсэж хуримтлагдана.
#: Хуримтлал гүйлгээний тоотой шугаман өсдөг тул тогтмол жижиг хязгаар тавина.
ROUNDING_TOLERANCE = Decimal("1.00")


def _check(
    name: str,
    expected: Decimal,
    actual: Decimal,
    tolerance: Decimal = Decimal("0"),
) -> dict[str, Any]:
    expected = q2(expected)
    actual = q2(actual)
    difference = q2(actual - expected)
    return {
        "name": name,
        "ok": abs(difference) <= tolerance,
        "expected": expected,
        "actual": actual,
        "difference": difference,
        "tolerance": q2(tolerance),
        "is_rounding": difference != 0 and abs(difference) <= tolerance,
    }


async def integrity_check(db: AsyncSession) -> list[dict[str, Any]]:
    """Ерөнхий дэвтэр ба туслах бүртгэлийн тулгалт."""
    checks: list[dict[str, Any]] = []

    # 1. Журналын тэнцэл
    totals_stmt = select(
        func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
        func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
    )
    totals_row = (await db.execute(totals_stmt)).one()
    checks.append(_check("Журналын дебит/кредит тэнцэл", q2(totals_row.debit), q2(totals_row.credit)))

    # 2. Гэрээт авлага 1201 ↔ contracts.balance
    contract_total = q2(await db.scalar(select(func.coalesce(func.sum(Contract.balance), 0))) or 0)
    checks.append(_check("Гэрээт авлага (1201)", contract_total, await _account_balance(db, ACC.AR_CONTRACT)))

    # Нөөцийн үнэлгээ
    tanks = await _tank_rows(db)
    products = await _product_rows(db)
    checks.append(
        _check(
            "Түлшний нөөц (1301)",
            _sum_values(tanks),
            await _account_balance(db, ACC.INV_FUEL),
            tolerance=ROUNDING_TOLERANCE,
        )
    )
    checks.append(
        _check(
            "Барааны нөөц (1302)",
            _sum_values(products),
            await _account_balance(db, ACC.INV_GOODS),
            tolerance=ROUNDING_TOLERANCE,
        )
    )

    return checks
