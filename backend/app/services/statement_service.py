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

from app.config import settings
from app.enums import (
    AccountType,
    ApprovalStatus,
    DocStatus,
    SaleStatus,
    ShiftStatus,
    ShipmentOutflowKind,
    ShipmentStatus,
    SourceType,
)
from app.models.accounting import Account, ApInvoice, JournalEntry, JournalLine
from app.models.approval import Refund
from app.models.expense import Expense
from app.models.fuel import Fuel, Tank
from app.models.partner import Contract
from app.models.procurement import FuelReceipt, FuelShipment, FuelShipmentOutflow, Purchase
from app.models.product import Product
from app.models.sale import Sale
from app.models.shift import Shift
from app.money import q2, vat_from_gross
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
    branch_id: uuid.UUID | None = None,
) -> dict[str, tuple[Decimal, Decimal]]:
    """``{дансны код: (Σдебит, Σкредит)}``.

    ``branch_id`` өгвөл зөвхөн тухайн салбарын хэмжүүртэй мөрүүдийг тоолно.
    """
    stmt = (
        select(
            JournalLine.account_code,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .group_by(JournalLine.account_code)
    )
    if branch_id is not None:
        stmt = stmt.where(JournalLine.dim_branch_id == branch_id)
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
async def income_statement(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Орлого, өртөг, зардлын тайлан + түлш тус бүрийн ашгийн задаргаа.

    ``branch_id`` өгвөл зөвхөн тухайн салбарын хэмжүүртэй бичилтүүдээс гаргана.
    """
    totals = await _totals_by_account(
        db, date_from=date_from, date_to=date_to, branch_id=branch_id
    )
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
        "fuel_margins": await _fuel_margins(db, date_from, date_to, branch_id=branch_id),
    }


async def _fuel_margins(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    branch_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
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
    if branch_id is not None:
        stmt = stmt.where(JournalLine.dim_branch_id == branch_id)
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
# Салбарын харьцуулалт
# --------------------------------------------------------------------------- #
async def branch_summary(db: AsyncSession, date_from: date, date_to: date) -> dict[str, Any]:
    """Салбар бүрийн орлого / өртөг / зардал / ашиг — нэг хүснэгтэд.

    Журналын мөрүүдийг ``dim_branch_id``-аар бүлэглэнэ.  Салбарын хэмжүүргүй
    (толгойн, хуваарилагдаагүй) мөрүүд «Хуваарилагдаагүй» мөрөнд нэгдэнэ.
    """
    from app.models.branch import Branch

    stmt = (
        select(
            JournalLine.dim_branch_id,
            Account.account_type,
            Account.code,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debit"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .join(Account, Account.code == JournalLine.account_code)
        .where(
            Account.account_type.in_([str(AccountType.REVENUE), str(AccountType.EXPENSE)])
        )
        .group_by(JournalLine.dim_branch_id, Account.account_type, Account.code)
    )
    stmt = _apply_period(stmt, date_from, date_to)
    rows = (await db.execute(stmt)).all()

    buckets: dict[uuid.UUID | None, dict[str, Decimal]] = {}
    for row in rows:
        bucket = buckets.setdefault(
            row.dim_branch_id, {"revenue": ZERO, "cogs": ZERO, "expense": ZERO}
        )
        if str(row.account_type) == str(AccountType.REVENUE):
            bucket["revenue"] = q2(bucket["revenue"] + q2(row.credit) - q2(row.debit))
        elif row.code in ACC.COGS_ACCOUNTS:
            bucket["cogs"] = q2(bucket["cogs"] + q2(row.debit) - q2(row.credit))
        else:
            bucket["expense"] = q2(bucket["expense"] + q2(row.debit) - q2(row.credit))

    branches = {b.id: b for b in (await db.scalars(select(Branch))).all()}

    items: list[dict[str, Any]] = []
    totals = {"revenue": ZERO, "cogs": ZERO, "expense": ZERO}
    for branch_key, bucket in buckets.items():
        branch = branches.get(branch_key) if branch_key is not None else None
        gross = q2(bucket["revenue"] - bucket["cogs"])
        net = q2(gross - bucket["expense"])
        items.append(
            {
                "branch_id": branch_key,
                "branch_name": branch.name if branch else "Хуваарилагдаагүй",
                "branch_code": branch.code if branch else None,
                "revenue": bucket["revenue"],
                "cogs": bucket["cogs"],
                "gross_profit": gross,
                "expense": bucket["expense"],
                "net_profit": net,
            }
        )
        for key in totals:
            totals[key] = q2(totals[key] + bucket[key])

    # Гүйлгээгүй ч идэвхтэй салбаруудыг 0 дүнтэй харуулна — жагсаалт бүрэн байг.
    for branch in branches.values():
        if branch.is_active and branch.id not in buckets:
            items.append(
                {
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "branch_code": branch.code,
                    "revenue": ZERO,
                    "cogs": ZERO,
                    "gross_profit": ZERO,
                    "expense": ZERO,
                    "net_profit": ZERO,
                }
            )

    # Нэртэй салбарууд эхэндээ, «Хуваарилагдаагүй» хамгийн сүүлд.
    items.sort(key=lambda r: (r["branch_id"] is None, str(r["branch_name"])))

    total_gross = q2(totals["revenue"] - totals["cogs"])
    total_net = q2(total_gross - totals["expense"])
    return {
        "date_from": date_from,
        "date_to": date_to,
        "items": items,
        "total_revenue": totals["revenue"],
        "total_cogs": totals["cogs"],
        "total_gross_profit": total_gross,
        "total_expense": totals["expense"],
        "total_net_profit": total_net,
    }


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

    # 5. Нийлүүлэгчийн өглөг 2101 ↔ нэхэмжлэхийн үлдэгдэл (кредит хэвийн)
    ap_open = q2(
        await db.scalar(
            select(func.coalesce(func.sum(ApInvoice.amount_gross - ApInvoice.amount_paid), 0))
        )
        or 0
    )
    checks.append(_check("Нийлүүлэгчийн өглөг (2101)", ap_open, -await _account_balance(db, ACC.AP_SUPPLIER)))

    # Борлуулалтын баримтууд: ноороггүй бүх борлуулалт + машинаас шууд борлуулалт − буцаалт
    live_sales = Sale.status != str(SaleStatus.DRAFT)
    sales_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(Sale.subtotal), 0).label("subtotal"),
                func.coalesce(func.sum(Sale.vat_amount), 0).label("vat"),
                func.coalesce(func.sum(Sale.cogs_total), 0).label("cogs"),
            ).where(live_sales)
        )
    ).one()
    refund_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(Refund.vat_amount), 0).label("vat"),
                func.coalesce(func.sum(Refund.cogs_amount), 0).label("cogs"),
            ).where(Refund.status == str(ApprovalStatus.APPROVED), Refund.restock.is_(True))
        )
    ).one()
    refund_vat = q2(
        await db.scalar(
            select(func.coalesce(func.sum(Refund.vat_amount), 0)).where(
                Refund.status == str(ApprovalStatus.APPROVED)
            )
        )
        or 0
    )
    outflows = (
        await db.execute(
            select(FuelShipmentOutflow.amount, FuelShipmentOutflow.cost_amount).where(
                FuelShipmentOutflow.kind == str(ShipmentOutflowKind.SALE)
            )
        )
    ).all()
    ship_vat = ZERO
    ship_net = ZERO
    ship_cost = ZERO
    for gross, cost in outflows:
        gross = q2(Decimal(gross or 0))
        vat = vat_from_gross(gross, settings.vat_rate)
        ship_vat = q2(ship_vat + vat)
        ship_net = q2(ship_net + (gross - vat))
        ship_cost = q2(ship_cost + Decimal(cost or 0))

    # 6. Гарах НӨАТ 2201 ↔ борлуулалтын НӨАТ − буцаалтын НӨАТ
    checks.append(
        _check(
            "Гарах НӨАТ (2201) ↔ борлуулалт",
            q2(q2(sales_row.vat) - refund_vat + ship_vat),
            -await _account_balance(db, ACC.VAT_OUTPUT),
        )
    )

    # 7. Борлуулалтын орлого 4101+4102 ↔ борлуулалтын цэвэр дүн
    revenue = q2(
        -await _account_balance(db, ACC.REV_FUEL) - await _account_balance(db, ACC.REV_GOODS)
    )
    checks.append(
        _check("Борлуулалтын орлого (4101+4102)", q2(q2(sales_row.subtotal) + ship_net), revenue)
    )

    # 8. Борлуулалтын өртөг 5101+5102 ↔ борлуулалтын өртөг − сэргээсэн буцаалт
    cogs = q2(await _account_balance(db, ACC.COGS_FUEL) + await _account_balance(db, ACC.COGS_GOODS))
    checks.append(
        _check(
            "Борлуулалтын өртөг (5101+5102)",
            q2(q2(sales_row.cogs) - q2(refund_row.cogs) + ship_cost),
            cogs,
        )
    )

    # 9. Орох НӨАТ 1402 ↔ бүртгэсэн худалдан авалт, ачилт, зардлын НӨАТ
    #    (ачилтын НӨАТ ачилт бүртгэхэд нэг удаа бичигддэг; түгээлтийн баримтууд НӨАТ-гүй)
    posted = str(DocStatus.POSTED)
    input_vat = ZERO
    for model, live in (
        (FuelReceipt, FuelReceipt.status == posted),
        (Purchase, Purchase.status == posted),
        (Expense, Expense.status == posted),
        (
            FuelShipment,
            FuelShipment.status.in_([str(ShipmentStatus.POSTED), str(ShipmentStatus.CLOSED)]),
        ),
    ):
        value = await db.scalar(select(func.coalesce(func.sum(model.vat_amount), 0)).where(live))
        input_vat = q2(input_vat + Decimal(value or 0))
    checks.append(_check("Орох НӨАТ (1402)", input_vat, await _account_balance(db, ACC.VAT_INPUT)))

    # 10. Кассын дутагдал 5902 ↔ хаагдсан ээлжийн сөрөг зөрүү
    short = await db.scalar(
        select(func.coalesce(func.sum(-Shift.cash_over_short), 0)).where(
            Shift.status == str(ShiftStatus.CLOSED), Shift.cash_over_short < 0
        )
    )
    checks.append(
        _check("Кассын дутагдал (5902)", q2(Decimal(short or 0)), await _account_balance(db, ACC.CASH_SHORT))
    )

    # 11. Бүртгэсэн баримт бүр журналд байгаа эсэх (тоо = 0 байх ёстой)
    missing = 0
    for model, source_type in (
        (FuelReceipt, SourceType.FUEL_RECEIPT),
        (Purchase, SourceType.PURCHASE),
        (Expense, SourceType.EXPENSE),
    ):
        posted_ids = select(model.id).where(model.status == posted)
        entry_ids = select(JournalEntry.source_id).where(JournalEntry.source_type == str(source_type))
        count = await db.scalar(
            select(func.count()).select_from(posted_ids.where(model.id.not_in(entry_ids)).subquery())
        )
        missing += int(count or 0)
    sales_missing = await db.scalar(
        select(func.count())
        .select_from(Sale)
        .where(
            live_sales,
            Sale.id.not_in(select(JournalEntry.source_id).where(JournalEntry.source_type == str(SourceType.SALE))),
        )
    )
    missing += int(sales_missing or 0)
    checks.append(_check("Журналгүй бүртгэсэн баримт (тоо)", ZERO, Decimal(missing)))

    # 12. Давхардсан бичилт (нэг баримт, нэг үйл явдал хоёр удаа) — 0 байх ёстой
    dup_stmt = (
        select(func.count())
        .select_from(JournalEntry)
        .group_by(JournalEntry.source_type, JournalEntry.source_id, JournalEntry.event_type)
        .having(func.count() > 1)
    )
    duplicates = len((await db.execute(dup_stmt)).all())
    checks.append(_check("Давхардсан журналын бичилт (тоо)", ZERO, Decimal(duplicates)))

    # 13. Харилцах данс 1110-ийн данс заагаагүй мөр — 0 байх ёстой (данс бүрийн үлдэгдэл)
    unassigned_bank = await db.scalar(
        select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).where(
            JournalLine.account_code == ACC.BANK, JournalLine.dim_bank_account_id.is_(None)
        )
    )
    checks.append(_check("Данс заагаагүй банкны хөдөлгөөн (1110)", ZERO, q2(Decimal(unassigned_bank or 0))))

    # 14. Салбар заагаагүй орлогын мөр — 0 байх ёстой (салбарын харьцуулалт)
    no_branch = await db.scalar(
        select(func.count())
        .select_from(JournalLine)
        .where(
            JournalLine.account_code.in_([ACC.REV_FUEL, ACC.REV_GOODS]),
            JournalLine.dim_branch_id.is_(None),
        )
    )
    checks.append(_check("Салбар заагаагүй орлогын мөр (тоо)", ZERO, Decimal(int(no_branch or 0))))

    return checks
