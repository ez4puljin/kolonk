"""Тайлангийн төв — нэг хөдөлгүүр, олон төрлийн тайлан.

Загвар: бүх эх сурвалжийг нэг **гүйлгээний баримт** (`Fact`) болгон хөрвүүлж,
дараа нь сонгосон бүлэглэлээр (данс, салбар, ажилтан, түлш, ангилал) шаталсан
дүнг гаргана.

Шүүлт бүр **олон утга** авна — юу ч сонгоогүй бол "Бүгд".

Гүйлгээний төрөл:
    sale        Борлуулалт
    inbound     Орлого (шатахуун таталт, худалдан авалт)
    outbound    Зарлага (зардал, цалин, өглөг төлөлт)
    refund      Буцаалт
    adjustment  Залруулга (тохируулга, ээлжийн зөрүү)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import DocStatus, InventoryTxType, SaleStatus, TankMovementType
from app.models.branch import Branch
from app.models.expense import Expense
from app.models.fuel import Fuel, Tank, TankMovement
from app.models.payroll import Employee
from app.models.procurement import FuelReceipt, Purchase, PurchaseItem
from app.models.product import InventoryTransaction, Product, ProductCategory
from app.models.sale import Payment, Sale, SaleItem
from app.models.user import User
from app.money import q2, q3
from app.services.coa import ACC
from app.stationtime import day_end, day_start

ZERO = Decimal("0.00")
ZERO_Q = Decimal("0.000")

# --------------------------------------------------------------------------- #
# Тогтмолууд
# --------------------------------------------------------------------------- #
TX_TYPES: list[dict[str, str]] = [
    {"code": "sale", "name": "Борлуулалт"},
    {"code": "inbound", "name": "Орлого"},
    {"code": "outbound", "name": "Зарлага"},
    {"code": "refund", "name": "Буцаалт"},
    {"code": "adjustment", "name": "Залруулга"},
]
TX_TYPE_NAMES = {t["code"]: t["name"] for t in TX_TYPES}

GROUP_FIELDS: list[dict[str, str]] = [
    {"code": "account", "name": "Данс"},
    {"code": "branch", "name": "Салбар"},
    {"code": "employee", "name": "Ажилтан"},
    {"code": "fuel", "name": "Түлш"},
    {"code": "category", "name": "Барааны ангилал"},
    {"code": "item", "name": "Бараа"},
    {"code": "tx_type", "name": "Гүйлгээний төрөл"},
    {"code": "day", "name": "Өдрөөр"},
]

REPORTS: list[dict[str, Any]] = [
    {
        "code": "turnover",
        "name": "Гүйлгээний тайлан",
        "description": "Бүх төрлийн гүйлгээг сонгосон бүлэглэлээр нэгтгэнэ",
        "default_group_by": ["tx_type", "account"],
    },
    {
        "code": "inventory",
        "name": "Бараа материалын тайлан /өртгөөр/",
        "description": "Эхний үлдэгдэл, орлого, зарлага, эцсийн үлдэгдэл",
        "default_group_by": ["account", "item"],
    },
    {
        "code": "sales",
        "name": "Борлуулалтын тайлан",
        "description": "Зөвхөн борлуулалт — ажилтан, түлш, ангиллаар",
        "default_group_by": ["employee", "item"],
    },
    {
        "code": "expense",
        "name": "Зардлын тайлан",
        "description": "Үйл ажиллагааны зардал дансаар",
        "default_group_by": ["account"],
    },
]
REPORT_CODES = {r["code"] for r in REPORTS}


@dataclass
class Fact:
    """Тайлангийн нэг мөр — бүх хэмжигдэхүүн ба хэмжээст."""

    when: Any
    tx_type: str
    account_code: str
    account_name: str
    branch_id: uuid.UUID | None
    branch_name: str
    employee_id: uuid.UUID | None
    employee_name: str
    fuel_id: uuid.UUID | None
    fuel_name: str
    category_id: uuid.UUID | None
    category_name: str
    item_code: str
    item_name: str
    unit: str
    qty: Decimal
    amount: Decimal
    #: Задаргаанаас гүйлгээ рүү орох түлхүүр.
    source_type: str
    source_id: uuid.UUID | None
    doc_no: str
    note: str


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _in(value: Any, allowed: Iterable[Any] | None) -> bool:
    """Шүүлт хоосон бол бүгд тэнцэнэ."""
    if not allowed:
        return True
    return value in set(allowed)


# --------------------------------------------------------------------------- #
# Гүйлгээ цуглуулах
# --------------------------------------------------------------------------- #
async def _collect(
    db: AsyncSession,
    *,
    start: Any,
    end: Any,
) -> list[Fact]:
    """Хугацааны бүх гүйлгээг нэг жагсаалт болгож хөрвүүлнэ."""
    from app.models.accounting import Account

    branches = {b.id: b.name for b in (await db.scalars(select(Branch))).all()}
    accounts = {a.code: a.name_mn for a in (await db.scalars(select(Account))).all()}
    users = {u.id: u.full_name for u in (await db.scalars(select(User))).all()}
    employees = {e.user_id: e.full_name for e in (await db.scalars(select(Employee))).all() if e.user_id}
    facts: list[Fact] = []

    def branch_name(bid: uuid.UUID | None) -> str:
        return branches.get(bid, "—") if bid else "—"

    def person(uid: uuid.UUID | None) -> tuple[uuid.UUID | None, str]:
        if uid is None:
            return None, "—"
        return uid, employees.get(uid) or users.get(uid) or "—"

    # ---- Борлуулалт (мөр тус бүрээр) -------------------------------------- #
    rows = (
        await db.execute(
            select(SaleItem, Sale)
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(
                Sale.completed_at >= start,
                Sale.completed_at <= end,
                Sale.status != SaleStatus.DRAFT,
            )
        )
    ).all()
    fuels = {f.id: f for f in (await db.scalars(select(Fuel))).all()}
    products = {p.id: p for p in (await db.scalars(select(Product))).all()}
    categories = {c.id: c.name_mn for c in (await db.scalars(select(ProductCategory))).all()}

    for item, sale in rows:
        emp_id, emp_name = person(sale.cashier_id)
        if item.fuel_id:
            fuel = fuels.get(item.fuel_id)
            facts.append(
                Fact(
                    when=sale.completed_at,
                    tx_type="sale",
                    account_code=ACC.REV_FUEL,
                    account_name="Шатахууны борлуулалтын орлого",
                    branch_id=sale.branch_id,
                    branch_name=branch_name(sale.branch_id),
                    employee_id=emp_id,
                    employee_name=emp_name,
                    fuel_id=item.fuel_id,
                    fuel_name=fuel.name_mn if fuel else "—",
                    category_id=None,
                    category_name="Шатахуун",
                    item_code=fuel.code if fuel else "—",
                    item_name=fuel.name_mn if fuel else "—",
                    unit="л",
                    qty=q3(_d(item.qty, ZERO_Q)),
                    amount=q2(_d(item.amount)),
                    source_type="sale",
                    source_id=sale.id,
                    doc_no=f"№{sale.number}",
                    note=f"Борлуулалт №{sale.number}",
                )
            )
        elif item.product_id:
            product = products.get(item.product_id)
            facts.append(
                Fact(
                    when=sale.completed_at,
                    tx_type="sale",
                    account_code=ACC.REV_GOODS,
                    account_name="Барааны борлуулалтын орлого",
                    branch_id=sale.branch_id,
                    branch_name=branch_name(sale.branch_id),
                    employee_id=emp_id,
                    employee_name=emp_name,
                    fuel_id=None,
                    fuel_name="—",
                    category_id=product.category_id if product else None,
                    category_name=categories.get(product.category_id, "—") if product else "—",
                    item_code=product.sku if product else "—",
                    item_name=product.name_mn if product else "—",
                    unit=(product.unit if product else "ш") or "ш",
                    qty=q3(_d(item.qty, ZERO_Q)),
                    amount=q2(_d(item.amount)),
                    source_type="sale",
                    source_id=sale.id,
                    doc_no=f"№{sale.number}",
                    note=f"Борлуулалт №{sale.number}",
                )
            )

    # ---- Шатахууны таталт (орлого) ---------------------------------------- #
    receipts = (
        await db.execute(
            select(FuelReceipt, Tank, Fuel)
            .join(Tank, FuelReceipt.tank_id == Tank.id)
            .join(Fuel, FuelReceipt.fuel_id == Fuel.id)
            .where(
                FuelReceipt.status == str(DocStatus.POSTED),
                FuelReceipt.receipt_date >= start.date(),
                FuelReceipt.receipt_date <= end.date(),
            )
        )
    ).all()
    for receipt, tank, fuel in receipts:
        emp_id, emp_name = person(receipt.posted_by)
        facts.append(
            Fact(
                when=receipt.posted_at or receipt.created_at,
                tx_type="inbound",
                account_code=ACC.INV_FUEL,
                account_name="Түлшний бараа материал",
                branch_id=tank.branch_id,
                branch_name=branch_name(tank.branch_id),
                employee_id=emp_id,
                employee_name=emp_name,
                fuel_id=fuel.id,
                fuel_name=fuel.name_mn,
                category_id=None,
                category_name="Шатахуун",
                item_code=fuel.code,
                item_name=fuel.name_mn,
                unit="л",
                qty=q3(_d(receipt.liters, ZERO_Q)),
                amount=q2(_d(receipt.total_gross)),
                source_type="fuel_receipt",
                source_id=receipt.id,
                doc_no=f"№{receipt.number}",
                note=f"Шатахуун таталт №{receipt.number}",
            )
        )

    # ---- Барааны худалдан авалт (орлого) ---------------------------------- #
    purchases = (
        await db.execute(
            select(PurchaseItem, Purchase)
            .join(Purchase, PurchaseItem.purchase_id == Purchase.id)
            .where(
                Purchase.status == str(DocStatus.POSTED),
                Purchase.purchase_date >= start.date(),
                Purchase.purchase_date <= end.date(),
            )
        )
    ).all()
    for item, purchase in purchases:
        product = products.get(item.product_id)
        emp_id, emp_name = person(purchase.posted_by)
        facts.append(
            Fact(
                when=purchase.posted_at or purchase.created_at,
                tx_type="inbound",
                account_code=ACC.INV_GOODS,
                account_name="Дэлгүүрийн бараа материал",
                branch_id=None,
                branch_name="—",
                employee_id=emp_id,
                employee_name=emp_name,
                fuel_id=None,
                fuel_name="—",
                category_id=product.category_id if product else None,
                category_name=categories.get(product.category_id, "—") if product else "—",
                item_code=product.sku if product else "—",
                item_name=product.name_mn if product else "—",
                unit=(product.unit if product else "ш") or "ш",
                qty=q3(_d(item.qty, ZERO_Q)),
                amount=q2(_d(item.amount)),
                source_type="purchase",
                source_id=purchase.id,
                doc_no=f"№{purchase.number}",
                note=f"Худалдан авалт №{purchase.number}",
            )
        )

    # ---- Зардал (зарлага) -------------------------------------------------- #
    expenses = (
        await db.scalars(
            select(Expense).where(
                Expense.status == str(DocStatus.POSTED),
                Expense.expense_date >= start.date(),
                Expense.expense_date <= end.date(),
            )
        )
    ).all()
    for expense in expenses:
        emp_id, emp_name = person(expense.created_by)
        facts.append(
            Fact(
                when=expense.posted_at or expense.created_at,
                tx_type="outbound",
                account_code=expense.account_code,
                account_name=accounts.get(expense.account_code, expense.account_code),
                branch_id=expense.branch_id,
                branch_name=branch_name(expense.branch_id),
                employee_id=emp_id,
                employee_name=emp_name,
                fuel_id=None,
                fuel_name="—",
                category_id=None,
                category_name="Зардал",
                item_code=expense.account_code,
                item_name=expense.description or "Зардал",
                unit="",
                qty=ZERO_Q,
                amount=q2(_d(expense.total)),
                source_type="expense",
                source_id=expense.id,
                doc_no=f"№{expense.number}",
                note=expense.description or "Зардал",
            )
        )

    # ---- Залруулга ба зөрүү ------------------------------------------------ #
    adjustments = (
        await db.execute(
            select(TankMovement, Tank, Fuel)
            .join(Tank, TankMovement.tank_id == Tank.id)
            .join(Fuel, Tank.fuel_id == Fuel.id)
            .where(
                TankMovement.created_at >= start,
                TankMovement.created_at <= end,
                TankMovement.movement_type.in_(
                    [str(TankMovementType.ADJUSTMENT), str(TankMovementType.VARIANCE)]
                ),
            )
        )
    ).all()
    for mv, tank, fuel in adjustments:
        facts.append(
            Fact(
                when=mv.created_at,
                tx_type="adjustment",
                account_code=ACC.INV_FUEL,
                account_name="Түлшний бараа материал",
                branch_id=tank.branch_id,
                branch_name=branch_name(tank.branch_id),
                employee_id=None,
                employee_name="—",
                fuel_id=fuel.id,
                fuel_name=fuel.name_mn,
                category_id=None,
                category_name="Шатахуун",
                item_code=fuel.code,
                item_name=fuel.name_mn,
                unit="л",
                qty=q3(_d(mv.liters, ZERO_Q)),
                amount=q2(_d(mv.liters, ZERO_Q) * _d(mv.unit_cost)),
                source_type="tank_movement",
                source_id=mv.id,
                doc_no=tank.name,
                note=mv.note or "Залруулга",
            )
        )

    goods_adj = (
        await db.execute(
            select(InventoryTransaction, Product)
            .join(Product, InventoryTransaction.product_id == Product.id)
            .where(
                InventoryTransaction.created_at >= start,
                InventoryTransaction.created_at <= end,
                InventoryTransaction.tx_type.in_(
                    [str(InventoryTxType.ADJUSTMENT), str(InventoryTxType.REFUND)]
                ),
            )
        )
    ).all()
    for tx, product in goods_adj:
        is_refund = str(tx.tx_type) == str(InventoryTxType.REFUND)
        facts.append(
            Fact(
                when=tx.created_at,
                tx_type="refund" if is_refund else "adjustment",
                account_code=ACC.INV_GOODS,
                account_name="Дэлгүүрийн бараа материал",
                branch_id=None,
                branch_name="—",
                employee_id=None,
                employee_name="—",
                fuel_id=None,
                fuel_name="—",
                category_id=product.category_id,
                category_name=categories.get(product.category_id, "—"),
                item_code=product.sku,
                item_name=product.name_mn,
                unit=product.unit or "ш",
                qty=q3(_d(tx.qty, ZERO_Q)),
                amount=q2(_d(tx.qty, ZERO_Q) * _d(tx.unit_cost)),
                source_type="inventory_tx",
                source_id=tx.id,
                doc_no="—",
                note=tx.note or ("Буцаалт" if is_refund else "Залруулга"),
            )
        )

    # ---- Буцаагдсан борлуулалт --------------------------------------------- #
    refunded = (
        await db.scalars(
            select(Sale).where(
                Sale.completed_at >= start,
                Sale.completed_at <= end,
                Sale.status.in_([SaleStatus.REFUNDED, SaleStatus.PARTIAL_REFUND]),
            )
        )
    ).all()
    for sale in refunded:
        emp_id, emp_name = person(sale.cashier_id)
        facts.append(
            Fact(
                when=sale.completed_at,
                tx_type="refund",
                account_code=ACC.SALES_RETURNS,
                account_name="Борлуулалтын буцаалт",
                branch_id=sale.branch_id,
                branch_name=branch_name(sale.branch_id),
                employee_id=emp_id,
                employee_name=emp_name,
                fuel_id=None,
                fuel_name="—",
                category_id=None,
                category_name="—",
                item_code="—",
                item_name=f"Борлуулалт №{sale.number}",
                unit="",
                qty=ZERO_Q,
                amount=q2(_d(sale.total)),
                source_type="sale",
                source_id=sale.id,
                doc_no=f"№{sale.number}",
                note=f"Буцаалт — борлуулалт №{sale.number}",
            )
        )

    facts.sort(key=lambda f: (f.when is None, f.when))
    return facts


# --------------------------------------------------------------------------- #
# Бүлэглэл
# --------------------------------------------------------------------------- #
def _dimension(fact: Fact, field_code: str) -> tuple[str, str]:
    if field_code == "account":
        return fact.account_code, fact.account_name
    if field_code == "branch":
        return (str(fact.branch_id) if fact.branch_id else "—"), fact.branch_name
    if field_code == "employee":
        return (str(fact.employee_id) if fact.employee_id else "—"), fact.employee_name
    if field_code == "fuel":
        return (str(fact.fuel_id) if fact.fuel_id else "—"), fact.fuel_name
    if field_code == "category":
        return (str(fact.category_id) if fact.category_id else "—"), fact.category_name
    if field_code == "tx_type":
        return fact.tx_type, TX_TYPE_NAMES.get(fact.tx_type, fact.tx_type)
    if field_code == "day":
        d = fact.when.date() if hasattr(fact.when, "date") else fact.when
        return str(d), str(d)
    return fact.item_code, fact.item_name  # item


@dataclass
class Node:
    code: str
    name: str
    level: int
    #: Дээд түвшнээс эхэлсэн бүрэн зам — задаргаа татахад ашиглана.
    path: list[str] = field(default_factory=list)
    qty: Decimal = ZERO_Q
    amount: Decimal = ZERO
    count: int = 0
    children: dict[str, "Node"] = field(default_factory=dict)
    details: list[dict[str, Any]] = field(default_factory=list)


def _flatten(node: Node, out: list[dict[str, Any]]) -> None:
    for child in node.children.values():
        out.append(
            {
                "level": child.level,
                "code": child.code,
                "name": child.name,
                "path": child.path,
                "qty": child.qty,
                "amount": child.amount,
                "count": child.count,
                "details": child.details,
            }
        )
        _flatten(child, out)


# --------------------------------------------------------------------------- #
# Гол функц
# --------------------------------------------------------------------------- #
async def run_report(
    db: AsyncSession,
    *,
    report: str = "turnover",
    date_from: date,
    date_to: date,
    account_codes: list[str] | None = None,
    branch_ids: list[uuid.UUID] | None = None,
    fuel_ids: list[uuid.UUID] | None = None,
    category_ids: list[uuid.UUID] | None = None,
    employee_ids: list[uuid.UUID] | None = None,
    tx_types: list[str] | None = None,
    group_by: list[str] | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    """Сонгосон тайланг олон утгатай шүүлтээр гаргана."""
    start = day_start(date_from)
    end = day_end(date_to)

    facts = await _collect(db, start=start, end=end)

    # Тайлангийн төрлөөс хамаарсан урьдчилсан хязгаарлалт.
    if report == "sales":
        facts = [f for f in facts if f.tx_type == "sale"]
    elif report == "expense":
        facts = [f for f in facts if f.tx_type == "outbound"]
    elif report == "inventory":
        facts = [f for f in facts if f.account_code in (ACC.INV_FUEL, ACC.INV_GOODS)]

    # Хэрэглэгчийн шүүлт — хоосон бол "Бүгд".
    filtered = [
        f
        for f in facts
        if _in(f.account_code, account_codes)
        and _in(f.branch_id, branch_ids)
        and _in(f.fuel_id, fuel_ids)
        and _in(f.category_id, category_ids)
        and _in(f.employee_id, employee_ids)
        and _in(f.tx_type, tx_types)
    ]

    levels = group_by or next(
        (r["default_group_by"] for r in REPORTS if r["code"] == report), ["account"]
    )
    levels = [g for g in levels if g in {f["code"] for f in GROUP_FIELDS}] or ["account"]

    root = Node(code="", name="", level=-1)
    for fact in filtered:
        node = root
        path: list[Node] = []
        path_codes: list[str] = []
        for level, field_code in enumerate(levels):
            code, name = _dimension(fact, field_code)
            child = node.children.get(code)
            if child is None:
                child = Node(code=code, name=name, level=level, path=[*path_codes, code])
                node.children[code] = child
            path.append(child)
            path_codes.append(code)
            node = child
        for n in path:
            n.qty = q3(n.qty + fact.qty)
            n.amount = q2(n.amount + fact.amount)
            n.count += 1
        if include_details and path:
            path[-1].details.append(
                {
                    "when": fact.when,
                    "date": fact.when.date() if hasattr(fact.when, "date") else fact.when,
                    "tx_type": fact.tx_type,
                    "tx_type_name": TX_TYPE_NAMES.get(fact.tx_type, fact.tx_type),
                    "doc_no": fact.doc_no,
                    "item_name": fact.item_name,
                    "employee_name": fact.employee_name,
                    "branch_name": fact.branch_name,
                    "qty": fact.qty,
                    "unit": fact.unit,
                    "amount": fact.amount,
                    "note": fact.note,
                    # Давхар товшиход гүйлгээ рүү орох түлхүүр
                    "source_type": fact.source_type,
                    "source_id": str(fact.source_id) if fact.source_id else None,
                }
            )

    rows: list[dict[str, Any]] = []
    _flatten(root, rows)

    totals = {
        "qty": q3(sum((n.qty for n in root.children.values()), ZERO_Q)),
        "amount": q2(sum((n.amount for n in root.children.values()), ZERO)),
        "count": sum(n.count for n in root.children.values()),
    }

    report_meta = next((r for r in REPORTS if r["code"] == report), REPORTS[0])
    return {
        "report": report,
        "report_name": report_meta["name"],
        "date_from": date_from,
        "date_to": date_to,
        "group_by": levels,
        "group_by_labels": [
            next((g["name"] for g in GROUP_FIELDS if g["code"] == code), code) for code in levels
        ],
        "include_details": include_details,
        "filter_text": await _filter_text(
            db,
            account_codes=account_codes,
            branch_ids=branch_ids,
            fuel_ids=fuel_ids,
            category_ids=category_ids,
            employee_ids=employee_ids,
            tx_types=tx_types,
        ),
        "rows": rows,
        "totals": totals,
    }


async def drill_group(
    db: AsyncSession,
    *,
    path: list[str],
    report: str = "turnover",
    date_from: date,
    date_to: date,
    account_codes: list[str] | None = None,
    branch_ids: list[uuid.UUID] | None = None,
    fuel_ids: list[uuid.UUID] | None = None,
    category_ids: list[uuid.UUID] | None = None,
    employee_ids: list[uuid.UUID] | None = None,
    tx_types: list[str] | None = None,
    group_by: list[str] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Тухайн бүлгийн задаргаа — тайлангийн мөр дээр давхар товшиход дуудагдана.

    `path` нь тайлангийн мөрийн бүрэн зам (дээд түвшнээс). Уг замын угсаатай
    таарах гүйлгээнүүдийг л буцаана — бүлэг дундах түвшин ч байж болно.
    """
    start = day_start(date_from)
    end = day_end(date_to)

    facts = await _collect(db, start=start, end=end)

    if report == "sales":
        facts = [f for f in facts if f.tx_type == "sale"]
    elif report == "expense":
        facts = [f for f in facts if f.tx_type == "outbound"]
    elif report == "inventory":
        facts = [f for f in facts if f.account_code in (ACC.INV_FUEL, ACC.INV_GOODS)]

    facts = [
        f
        for f in facts
        if _in(f.account_code, account_codes)
        and _in(f.branch_id, branch_ids)
        and _in(f.fuel_id, fuel_ids)
        and _in(f.category_id, category_ids)
        and _in(f.employee_id, employee_ids)
        and _in(f.tx_type, tx_types)
    ]

    levels = group_by or next(
        (r["default_group_by"] for r in REPORTS if r["code"] == report), ["account"]
    )
    levels = [g for g in levels if g in {f["code"] for f in GROUP_FIELDS}] or ["account"]

    # Замын угсаагаар шүүнэ: path[i] нь levels[i]-ийн утгатай тэнцэх ёстой.
    matched: list[Fact] = []
    for fact in facts:
        ok = True
        for i, wanted in enumerate(path):
            if i >= len(levels):
                break
            code, _ = _dimension(fact, levels[i])
            if code != wanted:
                ok = False
                break
        if ok:
            matched.append(fact)

    matched.sort(key=lambda f: (f.when is None, f.when))
    total_count = len(matched)

    return {
        "path": path,
        "total": total_count,
        "truncated": total_count > limit,
        "items": [
            {
                "when": f.when,
                "date": f.when.date() if hasattr(f.when, "date") else f.when,
                "tx_type": f.tx_type,
                "tx_type_name": TX_TYPE_NAMES.get(f.tx_type, f.tx_type),
                "doc_no": f.doc_no,
                "item_name": f.item_name,
                "employee_name": f.employee_name,
                "branch_name": f.branch_name,
                "qty": f.qty,
                "unit": f.unit,
                "amount": f.amount,
                "note": f.note,
                "source_type": f.source_type,
                "source_id": str(f.source_id) if f.source_id else None,
            }
            for f in matched[:limit]
        ],
        "totals": {
            "qty": q3(sum((f.qty for f in matched), ZERO_Q)),
            "amount": q2(sum((f.amount for f in matched), ZERO)),
            "count": total_count,
        },
    }


async def _filter_text(
    db: AsyncSession,
    *,
    account_codes: list[str] | None,
    branch_ids: list[uuid.UUID] | None,
    fuel_ids: list[uuid.UUID] | None,
    category_ids: list[uuid.UUID] | None,
    employee_ids: list[uuid.UUID] | None,
    tx_types: list[str] | None,
) -> str:
    """Тайлангийн толгойд гарах "Шүүлтийн нөхцөл" мөрийг эх хэлээр бүрдүүлнэ."""
    parts: list[str] = []
    if account_codes:
        parts.append(f"Данс: {', '.join(account_codes)}")
    if branch_ids:
        names = [
            b.name for b in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()
        ]
        parts.append(f"Салбар: {', '.join(names)}")
    if fuel_ids:
        names = [f.name_mn for f in (await db.scalars(select(Fuel).where(Fuel.id.in_(fuel_ids)))).all()]
        parts.append(f"Түлш: {', '.join(names)}")
    if category_ids:
        names = [
            c.name_mn
            for c in (
                await db.scalars(select(ProductCategory).where(ProductCategory.id.in_(category_ids)))
            ).all()
        ]
        parts.append(f"Барааны ангилал: {', '.join(names)}")
    if employee_ids:
        names = [
            u.full_name for u in (await db.scalars(select(User).where(User.id.in_(employee_ids)))).all()
        ]
        parts.append(f"Ажилтан: {', '.join(names)}")
    if tx_types:
        parts.append(
            f"Гүйлгээний төрөл: {', '.join(TX_TYPE_NAMES.get(t, t) for t in tx_types)}"
        )
    return ", ".join(parts) if parts else "Бүгд"


# --------------------------------------------------------------------------- #
# Шүүлтийн сонголтууд
# --------------------------------------------------------------------------- #
async def filter_options(db: AsyncSession) -> dict[str, Any]:
    branches = (await db.scalars(select(Branch).order_by(Branch.sort_order))).all()
    fuels = (await db.scalars(select(Fuel).order_by(Fuel.sort_order))).all()
    categories = (await db.scalars(select(ProductCategory).order_by(ProductCategory.sort_order))).all()
    users = (await db.scalars(select(User).order_by(User.full_name))).all()
    employees = (await db.scalars(select(Employee).order_by(Employee.full_name))).all()

    from app.services.coa import COA_SEED

    return {
        "reports": REPORTS,
        "accounts": [
            {"code": a["code"], "name": a["name_mn"]} for a in COA_SEED if a["is_postable"]
        ],
        "branches": [{"id": str(b.id), "code": b.code, "name": b.name} for b in branches],
        "fuels": [{"id": str(f.id), "code": f.code, "name": f.name_mn} for f in fuels],
        "categories": [{"id": str(c.id), "name": c.name_mn} for c in categories],
        # Гүйлгээ хийдэг хүн = системийн хэрэглэгч. Ажилтны бүртгэлтэй бол
        # нэрийг нь тэндээс авна.
        "employees": [
            {"id": str(u.id), "name": u.full_name, "role": u.role_id and ""} for u in users
        ],
        "staff": [{"id": str(e.id), "name": e.full_name, "position": e.position} for e in employees],
        "tx_types": TX_TYPES,
        "group_fields": GROUP_FIELDS,
    }
