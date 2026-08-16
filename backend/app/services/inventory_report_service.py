"""Бараа материалын тайлан /өртгөөр/ — Erkhet маягийн хөдөлгөөний тайлан.

Мөр бүрд: **эхний үлдэгдэл → орлого → зарлага → эцсийн үлдэгдэл** (тоо ба дүн),
нэгж өртөг. Шаталсан бүлэглэлтэй (данс → байршил → бараа) бөгөөд задаргаа
асаавал гүйлгээ тус бүр гүйлгээний дараах үлдэгдэлтэйгээ харагдана.

Өгөгдлийн эх сурвалж:
  * түлш   — `tank_movements`  (байршил = сав)
  * бараа  — `inventory_transactions` (байршил = дэлгүүр)

Дүн нь `тоо × нэгж өртөг` — хөдлөх дундаж өртгийн арга тул эдгээрийн нийлбэр
нь нөөцийн дансны (1301/1302) үлдэгдэлтэй тэнцэнэ (`/accounting/integrity`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import InventoryTxType, TankMovementType
from app.models.fuel import Fuel, Tank, TankMovement
from app.models.product import InventoryTransaction, Product, ProductCategory
from app.money import q2, q3, q6
from app.services.coa import ACC
from app.stationtime import day_end, day_start

ZERO = Decimal("0.00")
ZERO_Q = Decimal("0.000")

#: Нөөцийн данснууд — тайлангийн дээд түвшний бүлэг.
ACCOUNT_NAMES: dict[str, str] = {
    ACC.INV_FUEL: "Түлшний бараа материал",
    ACC.INV_GOODS: "Дэлгүүрийн бараа материал",
}

#: Барааны нэг байршил (олон салбар болоход энэ нь агуулах болж өргөжинө).
GOODS_LOCATION_CODE = "01"
GOODS_LOCATION_NAME = "Дэлгүүр"

#: Гүйлгээний төрлийн монгол нэр — задаргааны мөрд харагдана.
MOVEMENT_NAMES: dict[str, str] = {
    str(TankMovementType.RECEIPT): "Шатахуун таталт",
    str(TankMovementType.SALE): "Борлуулалт",
    str(TankMovementType.ADJUSTMENT): "Тохируулга",
    str(TankMovementType.VARIANCE): "Ээлжийн зөрүү",
    str(InventoryTxType.PURCHASE): "Худалдан авалт",
    str(InventoryTxType.SALE): "Борлуулалт",
    str(InventoryTxType.REFUND): "Буцаалт",
    str(InventoryTxType.ADJUSTMENT): "Тохируулга",
    str(InventoryTxType.CONVERT_OUT): "Задлалт (гарсан)",
    str(InventoryTxType.CONVERT_IN): "Задлалт (орсон)",
}

GROUP_BY_LABELS: dict[str, str] = {
    "account_location_item": "Данс-Байршил",
    "account_item": "Данс-Бараа",
    "location_item": "Байршил-Бараа",
    "item": "Бараа",
}

TX_TYPE_LABELS: dict[str, str] = {
    "all": "Бүгд",
    "in": "Зөвхөн орлого",
    "out": "Зөвхөн зарлага",
}


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass
class Bucket:
    """Нэг бүлгийн хуримтлагдсан дүн."""

    code: str
    name: str
    level: int
    unit: str = ""
    opening_qty: Decimal = ZERO_Q
    opening_value: Decimal = ZERO
    in_qty: Decimal = ZERO_Q
    in_value: Decimal = ZERO
    out_qty: Decimal = ZERO_Q
    out_value: Decimal = ZERO
    details: list[dict[str, Any]] = field(default_factory=list)
    children: dict[str, "Bucket"] = field(default_factory=dict)

    def add_opening(self, qty: Decimal, value: Decimal) -> None:
        self.opening_qty = q3(self.opening_qty + qty)
        self.opening_value = q2(self.opening_value + value)

    def add_movement(self, qty: Decimal, value: Decimal) -> None:
        if qty >= 0:
            self.in_qty = q3(self.in_qty + qty)
            self.in_value = q2(self.in_value + value)
        else:
            self.out_qty = q3(self.out_qty - qty)
            self.out_value = q2(self.out_value - value)

    @property
    def closing_qty(self) -> Decimal:
        return q3(self.opening_qty + self.in_qty - self.out_qty)

    @property
    def closing_value(self) -> Decimal:
        return q2(self.opening_value + self.in_value - self.out_value)

    @property
    def is_empty(self) -> bool:
        return (
            self.opening_qty == 0
            and self.in_qty == 0
            and self.out_qty == 0
            and self.closing_qty == 0
        )


@dataclass
class Movement:
    """Түлш ба барааны хөдөлгөөнийг нэгтгэсэн дотоод дүрслэл."""

    when: Any
    account_code: str
    location_code: str
    location_name: str
    item_code: str
    item_name: str
    unit: str
    qty: Decimal            # тэмдэгтэй: + орлого, − зарлага
    unit_cost: Decimal
    value: Decimal          # тэмдэгтэй
    balance_after: Decimal
    movement_type: str
    note: str | None
    category_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Өгөгдөл татах
# --------------------------------------------------------------------------- #
def _fuel_stmt(
    *,
    tank_id: uuid.UUID | None,
    fuel_id: uuid.UUID | None,
) -> Select:
    stmt = (
        select(TankMovement, Tank, Fuel)
        .join(Tank, TankMovement.tank_id == Tank.id)
        .join(Fuel, Tank.fuel_id == Fuel.id)
    )
    if tank_id is not None:
        stmt = stmt.where(TankMovement.tank_id == tank_id)
    if fuel_id is not None:
        stmt = stmt.where(Tank.fuel_id == fuel_id)
    return stmt


def _goods_stmt(
    *,
    product_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
) -> Select:
    stmt = (
        select(InventoryTransaction, Product, ProductCategory)
        .join(Product, InventoryTransaction.product_id == Product.id)
        .outerjoin(ProductCategory, Product.category_id == ProductCategory.id)
    )
    if product_id is not None:
        stmt = stmt.where(InventoryTransaction.product_id == product_id)
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    return stmt


async def _load_movements(
    db: AsyncSession,
    *,
    account_code: str | None,
    tank_id: uuid.UUID | None,
    fuel_id: uuid.UUID | None,
    product_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    until: Any,
    since: Any | None,
) -> list[Movement]:
    """`since` (байвал) ба `until` хоорондох хөдөлгөөнүүд. `since=None` бол эхнээс."""
    out: list[Movement] = []

    want_fuel = account_code in (None, "", ACC.INV_FUEL)
    want_goods = account_code in (None, "", ACC.INV_GOODS)
    # Барааны шүүлт тавьсан бол түлш хамаарахгүй, эсрэгээр нь ч мөн адил.
    if product_id is not None or category_id is not None:
        want_fuel = False
    if tank_id is not None or fuel_id is not None:
        want_goods = False

    if want_fuel:
        stmt = _fuel_stmt(tank_id=tank_id, fuel_id=fuel_id).where(TankMovement.created_at < until)
        if since is not None:
            stmt = stmt.where(TankMovement.created_at >= since)
        for mv, tank, fuel in (await db.execute(stmt.order_by(TankMovement.created_at))).all():
            qty = q3(_d(mv.liters, ZERO_Q))
            cost = q6(_d(mv.unit_cost))
            out.append(
                Movement(
                    when=mv.created_at,
                    account_code=ACC.INV_FUEL,
                    location_code=f"{tank.name}",
                    location_name=tank.name,
                    item_code=fuel.code,
                    item_name=fuel.name_mn,
                    unit="л",
                    qty=qty,
                    unit_cost=cost,
                    value=q2(qty * cost),
                    balance_after=q3(_d(mv.balance_after_l, ZERO_Q)),
                    movement_type=str(mv.movement_type),
                    note=mv.note,
                    item_id=fuel.id,
                    location_id=tank.id,
                )
            )

    if want_goods:
        stmt = _goods_stmt(product_id=product_id, category_id=category_id).where(
            InventoryTransaction.created_at < until
        )
        if since is not None:
            stmt = stmt.where(InventoryTransaction.created_at >= since)
        rows = (await db.execute(stmt.order_by(InventoryTransaction.created_at))).all()
        for tx, product, category in rows:
            qty = q3(_d(tx.qty, ZERO_Q))
            cost = q6(_d(tx.unit_cost))
            out.append(
                Movement(
                    when=tx.created_at,
                    account_code=ACC.INV_GOODS,
                    location_code=GOODS_LOCATION_CODE,
                    location_name=category.name_mn if category else GOODS_LOCATION_NAME,
                    item_code=product.sku,
                    item_name=product.name_mn,
                    unit=product.unit or "ш",
                    qty=qty,
                    unit_cost=cost,
                    value=q2(qty * cost),
                    balance_after=q3(_d(tx.balance_after, ZERO_Q)),
                    movement_type=str(tx.tx_type),
                    note=tx.note,
                    category_id=product.category_id,
                    item_id=product.id,
                )
            )

    out.sort(key=lambda m: m.when)
    return out


# --------------------------------------------------------------------------- #
# Бүлэглэл
# --------------------------------------------------------------------------- #
def _keys_for(movement: Movement, group_by: str) -> list[tuple[str, str]]:
    """(код, нэр) хосуудын жагсаалт — гүнээс гүн рүү."""
    account = (movement.account_code, ACCOUNT_NAMES.get(movement.account_code, movement.account_code))
    location = (movement.location_code, movement.location_name)
    item = (movement.item_code, movement.item_name)

    if group_by == "account_item":
        return [account, item]
    if group_by == "location_item":
        return [location, item]
    if group_by == "item":
        return [item]
    return [account, location, item]  # account_location_item (анхдагч)


def _walk(bucket: Bucket, keys: list[tuple[str, str]], unit: str) -> list[Bucket]:
    """Түлхүүрийн замаар бүх түвшний bucket-ыг үүсгэж, замын bucket-уудыг буцаана."""
    path: list[Bucket] = []
    node = bucket
    for level, (code, name) in enumerate(keys):
        child = node.children.get(code)
        if child is None:
            child = Bucket(code=code, name=name, level=level, unit=unit if level == len(keys) - 1 else "")
            node.children[code] = child
        path.append(child)
        node = child
    return path


def _flatten(bucket: Bucket, *, skip_empty: bool, out: list[dict[str, Any]]) -> None:
    for child in bucket.children.values():
        if skip_empty and child.is_empty:
            continue
        out.append(
            {
                "level": child.level,
                "code": child.code,
                "name": child.name,
                "unit": child.unit,
                "opening_qty": child.opening_qty,
                "opening_value": child.opening_value,
                "in_qty": child.in_qty,
                "in_value": child.in_value,
                "out_qty": child.out_qty,
                "out_value": child.out_value,
                "closing_qty": child.closing_qty,
                "closing_value": child.closing_value,
                "unit_cost": (
                    q2(child.closing_value / child.closing_qty) if child.closing_qty else ZERO
                ),
                "details": child.details,
            }
        )
        _flatten(child, skip_empty=skip_empty, out=out)


def _filter_text(parts: list[str]) -> str:
    return ", ".join(p for p in parts if p)


# --------------------------------------------------------------------------- #
# Гол функц
# --------------------------------------------------------------------------- #
async def inventory_movement_report(
    db: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    account_code: str | None = None,
    tank_id: uuid.UUID | None = None,
    fuel_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    group_by: str = "account_location_item",
    tx_type: str = "all",
    note_search: str | None = None,
    include_details: bool = False,
    skip_empty: bool = True,
) -> dict[str, Any]:
    """Бараа материалын хөдөлгөөний тайлан /өртгөөр/."""
    start = day_start(date_from)
    end = day_end(date_to)

    common = {
        "account_code": account_code,
        "tank_id": tank_id,
        "fuel_id": fuel_id,
        "product_id": product_id,
        "category_id": category_id,
    }

    opening = await _load_movements(db, until=start, since=None, **common)
    period = await _load_movements(db, until=end, since=start, **common)

    if note_search:
        needle = note_search.strip().lower()
        period = [m for m in period if needle in (m.note or "").lower()]

    root = Bucket(code="", name="", level=-1)

    # Эхний үлдэгдэл — тайлант үеэс өмнөх бүх хөдөлгөөний нийлбэр.
    for mv in opening:
        for node in _walk(root, _keys_for(mv, group_by), mv.unit):
            node.add_opening(mv.qty, mv.value)

    # Тайлант үеийн хөдөлгөөн.
    for mv in period:
        if tx_type == "in" and mv.qty < 0:
            continue
        if tx_type == "out" and mv.qty >= 0:
            continue
        path = _walk(root, _keys_for(mv, group_by), mv.unit)
        for node in path:
            node.add_movement(mv.qty, mv.value)
        if include_details and path:
            leaf = path[-1]
            leaf.details.append(
                {
                    "date": mv.when.date() if hasattr(mv.when, "date") else mv.when,
                    "movement_type": mv.movement_type,
                    "movement_name": MOVEMENT_NAMES.get(mv.movement_type, mv.movement_type),
                    "note": mv.note,
                    "in_qty": mv.qty if mv.qty >= 0 else None,
                    "in_value": mv.value if mv.qty >= 0 else None,
                    "out_qty": -mv.qty if mv.qty < 0 else None,
                    "out_value": -mv.value if mv.qty < 0 else None,
                    "balance_qty": mv.balance_after,
                    "unit_cost": mv.unit_cost,
                }
            )

    rows: list[dict[str, Any]] = []
    _flatten(root, skip_empty=skip_empty, out=rows)

    # Нийт дүн — зөвхөн дээд түвшний бүлгүүдийн нийлбэр (давхар тоолохгүй).
    totals = {
        "opening_qty": ZERO_Q,
        "opening_value": ZERO,
        "in_qty": ZERO_Q,
        "in_value": ZERO,
        "out_qty": ZERO_Q,
        "out_value": ZERO,
    }
    for top in root.children.values():
        totals["opening_qty"] = q3(totals["opening_qty"] + top.opening_qty)
        totals["opening_value"] = q2(totals["opening_value"] + top.opening_value)
        totals["in_qty"] = q3(totals["in_qty"] + top.in_qty)
        totals["in_value"] = q2(totals["in_value"] + top.in_value)
        totals["out_qty"] = q3(totals["out_qty"] + top.out_qty)
        totals["out_value"] = q2(totals["out_value"] + top.out_value)
    totals["closing_qty"] = q3(totals["opening_qty"] + totals["in_qty"] - totals["out_qty"])
    totals["closing_value"] = q2(totals["opening_value"] + totals["in_value"] - totals["out_value"])

    # Шүүлтийн нөхцлийг эх хэлээр бичих (тайлангийн толгойд гарна).
    conditions: list[str] = []
    if account_code:
        conditions.append(f"Данс: {account_code} - {ACCOUNT_NAMES.get(account_code, '')}")
    if tank_id is not None:
        tank = await db.get(Tank, tank_id)
        if tank:
            conditions.append(f"Байршил: {tank.name}")
    if fuel_id is not None:
        fuel = await db.get(Fuel, fuel_id)
        if fuel:
            conditions.append(f"Түлш: {fuel.code} - {fuel.name_mn}")
    if category_id is not None:
        cat = await db.get(ProductCategory, category_id)
        if cat:
            conditions.append(f"Ангилал: {cat.name_mn}")
    if product_id is not None:
        product = await db.get(Product, product_id)
        if product:
            conditions.append(f"Бараа: {product.sku} - {product.name_mn}")
    if tx_type != "all":
        conditions.append(f"Гүйлгээний төрөл: {TX_TYPE_LABELS.get(tx_type, tx_type)}")
    if note_search:
        conditions.append(f"Гүйлгээний утга: {note_search}")

    return {
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "group_by_label": GROUP_BY_LABELS.get(group_by, group_by),
        "tx_type": tx_type,
        "include_details": include_details,
        "filter_text": _filter_text(conditions),
        "rows": rows,
        "totals": totals,
    }
