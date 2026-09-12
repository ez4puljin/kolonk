"""Түлшний ачилтын хөдөлгүүр — машинаар татсан түлш, барааг салбаруудад түгээх.

Урсгал:

1. **Ноорог** — Админ ачилтыг бүртгэнэ: машины дугаар, үндсэн нийлүүлэгч,
   мөр бүрд (түлш эсвэл бараа) нийлүүлэгч, тоо хэмжээ, нэгж үнэ, мөн хүсвэл
   хуваарилалтын төлөвлөгөө: аль салбарын саванд хэдэн литр, аль салбарт
   хэдэн ширхэг.
2. **Бүртгэх** — НИЙЛҮҮЛЭГЧ ТУС БҮРД тусдаа өглөг нээгдэнэ (тээврийн зардал
   үндсэн нийлүүлэгчийнхэд), түлш «Замд яваа түлш» (1303), бараа «Замд яваа
   бараа» (1304) дансанд орно.  Төлөвлөгөө байвал тэр дороо буулгагдана.
3. **Буулгах** — машин салбар бүрд зогсоход тухайн савны литрийг (нэг зогсолтод
   олон сав) оруулна: түгээлт бүр `FuelReceipt` (shipment_id-тай) болж,
   1303 → 1301 шилжиж, салбарын тооцооны дэвтэрт **өр** (charge) үүснэ.
   Бараа салбарт буухад `Purchase` (shipment_id-тай) үүсч 1304 → 1302
   шилжиж, мөн өр үүснэ.
4. **Шууд борлуулалт / хорогдол** — үлдсэн литрийг машинаас шууд зарах
   эсвэл хорогдолд бичих.
5. **Хаах** — бүх литр, ширхэг тэглэгдмэгц ачилт хаагдана.

Бүгд нэг transaction дотор; энэ модуль хэзээ ч ``db.commit()`` дуудахгүй.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import (
    DocStatus,
    EventType,
    InvoiceStatus,
    SettlementEntryType,
    ShipmentOutflowKind,
    ShipmentStatus,
    SourceType,
)
from app.models.accounting import ApInvoice
from app.models.bank import BankAccount
from app.models.branch import Branch
from app.models.fuel import Fuel, Tank
from app.models.partner import Supplier
from app.models.procurement import (
    FuelReceipt,
    FuelShipment,
    FuelShipmentGoods,
    FuelShipmentItem,
    FuelShipmentOutflow,
    Purchase,
    PurchaseItem,
)
from app.models.product import Product
from app.models.settlement import BranchSettlement
from app.models.user import User
from app.money import q2, q3, q6
from app.services import inventory_service, tank_service
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import posting
from app.services.posting_rules import (
    build_shipment_delivery_lines,
    build_shipment_goods_delivery_lines,
    build_shipment_lines,
    build_shipment_loss_lines,
    build_shipment_sale_lines,
)

ZERO = Decimal("0")

VAT_RATE: Decimal = settings.vat_rate

#: Нийлүүлэгчийн өглөгийн стандарт төлбөрийн хугацаа (хоног).
PAYMENT_TERM_DAYS = 30


def _d(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _user_id(user: User | None) -> uuid.UUID | None:
    return getattr(user, "id", None)


async def _shipment_number(db: AsyncSession, shipment: FuelShipment) -> int | None:
    try:
        return shipment.number
    except Exception:  # noqa: BLE001
        try:
            await db.refresh(shipment, ["number"])
            return shipment.number
        except Exception:  # noqa: BLE001
            return None


def effective_supplier(shipment: FuelShipment, line: Any) -> uuid.UUID:
    """Мөрийн нийлүүлэгч — заагаагүй бол ачилтын үндсэн нийлүүлэгч."""
    return getattr(line, "supplier_id", None) or shipment.supplier_id


# --------------------------------------------------------------------------- #
# Дүн, landed өртөг, нийлүүлэгч тус бүрийн өглөг
# --------------------------------------------------------------------------- #
class SupplierTotal:
    """Нэг нийлүүлэгчид төлөх дүн: мөрүүд (+ үндсэнд тээвэр), НӨАТ, нийт."""

    __slots__ = ("supplier_id", "is_main", "subtotal", "vat_amount", "total_gross")

    def __init__(self, supplier_id: uuid.UUID, is_main: bool) -> None:
        self.supplier_id = supplier_id
        self.is_main = is_main
        self.subtotal = ZERO
        self.vat_amount = ZERO
        self.total_gross = ZERO


def supplier_totals(shipment: FuelShipment) -> list[SupplierTotal]:
    """Нийлүүлэгч тус бүрийн НӨАТ-гүй дүн, НӨАТ, нийт — ``recalculate``-ийн дараа.

    Тээврийн зардал үндсэн нийлүүлэгчийн нэхэмжлэхэд орно: машиныг тэр
    гаргасан гэж үзнэ.  Өөр нийлүүлэгчийн мөр зөвхөн өөрийн дүнгээрээ.
    """
    totals: dict[uuid.UUID, SupplierTotal] = {}
    main = shipment.supplier_id
    totals[main] = SupplierTotal(main, True)
    for line in [*shipment.items, *shipment.goods]:
        sid = effective_supplier(shipment, line)
        bucket = totals.get(sid)
        if bucket is None:
            bucket = totals[sid] = SupplierTotal(sid, False)
        bucket.subtotal = q2(bucket.subtotal + q2(_d(line.amount)))
    totals[main].subtotal = q2(totals[main].subtotal + q2(_d(shipment.freight_cost)))
    for bucket in totals.values():
        bucket.vat_amount = q2(bucket.subtotal * VAT_RATE)
        bucket.total_gross = q2(bucket.subtotal + bucket.vat_amount)
    # Үндсэн нийлүүлэгч эхэнд, бусад нь дүнгээр буурахаар.
    return sorted(totals.values(), key=lambda b: (not b.is_main, -b.total_gross))


def recalculate(shipment: FuelShipment) -> None:
    """Дүн ба landed нэгж өртгийг шинэчилнэ (ноорог дээр ч ажиллана).

    Тээврийн зардлыг БҮХ мөрийн (түлш + бараа) дүнгээр пропорциональ
    хуваарилж, мөр бүрийн landed нэгж өртгийг гаргана — сав/нөөц рүү энэ
    өртгөөр орно.  НӨАТ, нийт дүн нийлүүлэгч тус бүрээр бодогдож нийлнэ —
    ингэснээр Σ(нэхэмжлэх) == ачилтын нийт дүн яг тэнцэнэ.
    """
    lines: list[Any] = [*shipment.items, *shipment.goods]
    subtotal_lines = ZERO
    for line in lines:
        qty = q3(_d(getattr(line, "liters", None) if hasattr(line, "liters") else line.qty))
        unit_cost = q6(_d(line.unit_cost))
        if hasattr(line, "liters"):
            line.liters = qty
        else:
            line.qty = qty
        line.unit_cost = unit_cost
        line.amount = q2(qty * unit_cost)
        subtotal_lines = q2(subtotal_lines + line.amount)

    freight = q2(_d(shipment.freight_cost))
    for line in lines:
        qty = _d(getattr(line, "liters", None) if hasattr(line, "liters") else line.qty)
        if qty <= ZERO:
            line.landed_unit_cost = ZERO
            continue
        share = q2(freight * line.amount / subtotal_lines) if subtotal_lines > ZERO else ZERO
        line.landed_unit_cost = q6((line.amount + share) / qty)

    shipment.subtotal = q2(subtotal_lines + freight)
    totals = supplier_totals(shipment)
    shipment.vat_amount = q2(sum((b.vat_amount for b in totals), ZERO))
    shipment.total_gross = q2(sum((b.total_gross for b in totals), ZERO))


async def remaining_by_fuel(db: AsyncSession, shipment: FuelShipment) -> dict[uuid.UUID, Decimal]:
    """Түлш бүрээр машин дээр үлдсэн литр = ачсан − буусан − зарсан − хорогдсон."""
    remaining: dict[uuid.UUID, Decimal] = {}
    for item in shipment.items:
        remaining[item.fuel_id] = q3(remaining.get(item.fuel_id, ZERO) + _d(item.liters))

    delivered = (
        await db.execute(
            select(FuelReceipt.fuel_id, FuelReceipt.liters).where(
                FuelReceipt.shipment_id == shipment.id,
                FuelReceipt.status == str(DocStatus.POSTED),
            )
        )
    ).all()
    for fuel_id, liters in delivered:
        remaining[fuel_id] = q3(remaining.get(fuel_id, ZERO) - _d(liters))

    # Шууд query — шинэхэн flush хийсэн объектын relationship async дээр
    # lazy-load хийж унадаг (MissingGreenlet) тул найдвартай замаар уншина.
    outflows = (
        await db.execute(
            select(FuelShipmentOutflow.fuel_id, FuelShipmentOutflow.liters).where(
                FuelShipmentOutflow.shipment_id == shipment.id
            )
        )
    ).all()
    for fuel_id, liters in outflows:
        remaining[fuel_id] = q3(remaining.get(fuel_id, ZERO) - _d(liters))

    return remaining


async def remaining_goods_by_product(
    db: AsyncSession, shipment: FuelShipment
) -> dict[uuid.UUID, Decimal]:
    """Бараа бүрээр машин дээр үлдсэн ширхэг = ачсан − салбарт буусан."""
    remaining: dict[uuid.UUID, Decimal] = {}
    for line in shipment.goods:
        remaining[line.product_id] = q3(remaining.get(line.product_id, ZERO) + _d(line.qty))
    delivered = (
        await db.execute(
            select(PurchaseItem.product_id, PurchaseItem.qty)
            .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
            .where(Purchase.shipment_id == shipment.id, Purchase.status == str(DocStatus.POSTED))
        )
    ).all()
    for product_id, qty in delivered:
        remaining[product_id] = q3(remaining.get(product_id, ZERO) - _d(qty))
    return remaining


def _fuel_line(shipment: FuelShipment, fuel_id: uuid.UUID) -> FuelShipmentItem:
    for item in shipment.items:
        if item.fuel_id == fuel_id:
            return item
    raise HTTPException(status_code=422, detail="Энэ түлш ачилтад байхгүй")


def _landed_cost(shipment: FuelShipment, fuel_id: uuid.UUID) -> Decimal:
    return q6(_d(_fuel_line(shipment, fuel_id).landed_unit_cost))


def _goods_line(shipment: FuelShipment, product_id: uuid.UUID) -> FuelShipmentGoods:
    for line in shipment.goods:
        if line.product_id == product_id:
            return line
    raise HTTPException(status_code=422, detail="Энэ бараа ачилтад байхгүй")


def _line_qty(line: Any) -> Decimal:
    return _d(getattr(line, "liters", None) if hasattr(line, "liters") else line.qty)


def posted_transit_amounts(shipment: FuelShipment) -> dict[uuid.UUID, Decimal]:
    """Мөр бүрийн 1303/1304-д ОРСОН дүн — ``build_shipment_lines``-ийн тольны хуулбар.

    Тэнд тоо × landed өртгийг мөр бүрээр центээр дугуйлж, тээврийн хуваарилалтын
    дугуйллын зөрүүг ЭХНИЙ мөрөнд шингээдэг.  Буулгалт бүр мөн тус тусдаа
    дугуйлагддаг тул Σ буулгалт энэ дүнгээс 1 центээр зөрж, ачилт хаагдсан ч
    1303/1304-д хэдэн цент үлдэж болно.  Мөрийн сүүлчийн хөдөлгөөн энэ
    дүнгээс үлдсэнийг яг авснаар замд яваа данс тэглэгдэнэ.
    """
    amounts: dict[uuid.UUID, Decimal] = {}
    total = ZERO
    first: uuid.UUID | None = None
    for line in [*shipment.items, *shipment.goods]:
        amount = q2(_line_qty(line) * q6(_d(line.landed_unit_cost)))
        if amount == ZERO:
            continue
        if first is None:
            first = line.id
        amounts[line.id] = amount
        total = q2(total + amount)
    drift = q2(q2(_d(shipment.subtotal)) - total)
    if drift != ZERO and first is not None:
        amounts[first] = q2(amounts[first] + drift)
    return amounts


async def _transit_left_amount(
    db: AsyncSession, shipment: FuelShipment, line: Any
) -> Decimal:
    """Тухайн мөрийн 1303/1304-д үлдсэн дүн = орсон − буусан − зарсан − хорогдсон."""
    posted = posted_transit_amounts(shipment).get(line.id, ZERO)
    if hasattr(line, "fuel_id"):
        out = await db.scalar(
            select(func.coalesce(func.sum(FuelReceipt.subtotal), 0)).where(
                FuelReceipt.shipment_id == shipment.id,
                FuelReceipt.fuel_id == line.fuel_id,
                FuelReceipt.status == str(DocStatus.POSTED),
            )
        )
        outflow = await db.scalar(
            select(func.coalesce(func.sum(FuelShipmentOutflow.cost_amount), 0)).where(
                FuelShipmentOutflow.shipment_id == shipment.id,
                FuelShipmentOutflow.fuel_id == line.fuel_id,
            )
        )
        return q2(posted - _d(out) - _d(outflow))
    out = await db.scalar(
        select(func.coalesce(func.sum(PurchaseItem.amount), 0))
        .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
        .where(
            Purchase.shipment_id == shipment.id,
            Purchase.status == str(DocStatus.POSTED),
            PurchaseItem.product_id == line.product_id,
        )
    )
    return q2(posted - _d(out))


# --------------------------------------------------------------------------- #
# Хуваарилалтын төлөвлөгөө (ноорог)
# --------------------------------------------------------------------------- #
def plan_from_payload(items: list[Any], goods: list[Any]) -> dict[str, list[dict[str, str]]]:
    """Оролтын мөрүүдийн ``allocations``-ыг JSONB-д хадгалах хэлбэрт хувиргана."""
    fuel = [
        {"fuel_id": str(item.fuel_id), "tank_id": str(a.tank_id), "liters": str(q3(_d(a.liters)))}
        for item in items
        for a in (item.allocations or [])
    ]
    goods_plan = [
        {"product_id": str(line.product_id), "branch_id": str(a.branch_id), "qty": str(q3(_d(a.qty)))}
        for line in goods
        for a in (line.allocations or [])
    ]
    return {"fuel": fuel, "goods": goods_plan}


async def validate_plan(db: AsyncSession, shipment: FuelShipment) -> None:
    """Төлөвлөгөө мөрүүдтэйгээ таарч байгааг шалгана — бүртгэхэд гэнэт унахгүй.

    * түлш: сав идэвхтэй, савны түлш мөрийнхтэй ижил, Σ литр ≤ мөрийн литр;
    * бараа: салбар идэвхтэй, Σ ширхэг ≤ мөрийн ширхэг.
    """
    plan = shipment.plan or {}
    fuel_plan = plan.get("fuel") or []
    goods_plan = plan.get("goods") or []
    if not fuel_plan and not goods_plan:
        return

    if fuel_plan:
        tank_ids = {uuid.UUID(a["tank_id"]) for a in fuel_plan}
        tanks = {t.id: t for t in (await db.scalars(select(Tank).where(Tank.id.in_(tank_ids)))).all()}
        per_fuel: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
        for a in fuel_plan:
            fuel_id = uuid.UUID(a["fuel_id"])
            tank = tanks.get(uuid.UUID(a["tank_id"]))
            if tank is None or not tank.is_active:
                raise HTTPException(status_code=422, detail="Хуваарилалтын сав олдсонгүй эсвэл идэвхгүй")
            if tank.fuel_id != fuel_id:
                raise HTTPException(
                    status_code=422, detail=f"«{tank.name}» сав өөр түлшнийх — хуваарилалт таарахгүй"
                )
            per_fuel[fuel_id] = q3(per_fuel[fuel_id] + _d(a["liters"]))
        for fuel_id, total in per_fuel.items():
            line = _fuel_line(shipment, fuel_id)
            if total > q3(_d(line.liters)):
                fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
                raise HTTPException(
                    status_code=422,
                    detail=f"{fuel.name_mn if fuel else 'Түлш'}: хуваарилалт ({total} л) ачсан литрээс ({line.liters} л) их байна",
                )

    if goods_plan:
        branch_ids = {uuid.UUID(a["branch_id"]) for a in goods_plan}
        branches = {
            b.id: b for b in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()
        }
        per_product: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
        for a in goods_plan:
            branch = branches.get(uuid.UUID(a["branch_id"]))
            if branch is None or not branch.is_active:
                raise HTTPException(status_code=422, detail="Хуваарилалтын салбар олдсонгүй эсвэл идэвхгүй")
            product_id = uuid.UUID(a["product_id"])
            per_product[product_id] = q3(per_product[product_id] + _d(a["qty"]))
        for product_id, total in per_product.items():
            line = _goods_line(shipment, product_id)
            if total > q3(_d(line.qty)):
                product = await db.scalar(select(Product).where(Product.id == product_id))
                raise HTTPException(
                    status_code=422,
                    detail=f"{product.name_mn if product else 'Бараа'}: хуваарилалт ({total}) ачсан тооноос ({line.qty}) их байна",
                )


async def execute_plan(db: AsyncSession, user: User | None, shipment: FuelShipment) -> None:
    """Бүртгэсний дараа төлөвлөгөөг буулгана: сав бүрд литр, салбар бүрд бараа."""
    plan = shipment.plan or {}
    for a in plan.get("fuel") or []:
        await deliver(
            db,
            user,
            shipment,
            tank_id=uuid.UUID(a["tank_id"]),
            liters=_d(a["liters"]),
            receipt_date=shipment.shipment_date,
            note="Ачилтын төлөвлөгөөгөөр",
        )
    by_branch: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal]]] = defaultdict(list)
    for a in plan.get("goods") or []:
        by_branch[uuid.UUID(a["branch_id"])].append((uuid.UUID(a["product_id"]), _d(a["qty"])))
    for branch_id, lines in by_branch.items():
        await deliver_goods(
            db,
            user,
            shipment,
            branch_id=branch_id,
            lines=lines,
            receipt_date=shipment.shipment_date,
            note="Ачилтын төлөвлөгөөгөөр",
        )


# --------------------------------------------------------------------------- #
# Бүртгэх
# --------------------------------------------------------------------------- #
async def post_shipment(db: AsyncSession, user: User | None, shipment: FuelShipment) -> FuelShipment:
    """Ноорог ачилтыг бүртгэнэ: нийлүүлэгч тус бүрд өглөг + 1303/1304 бичилт,
    дараа нь хуваарилалтын төлөвлөгөөг буулгана."""
    if str(shipment.status) != str(ShipmentStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Аль хэдийн бүртгэгдсэн")
    if not shipment.items and not shipment.goods:
        raise HTTPException(status_code=422, detail="Ачилтад түлш эсвэл бараа оруулаагүй байна")
    for line in [*shipment.items, *shipment.goods]:
        qty = _d(getattr(line, "liters", None) if hasattr(line, "liters") else line.qty)
        if q3(qty) <= ZERO:
            raise HTTPException(status_code=422, detail="Тоо хэмжээ 0-ээс их байх ёстой")
        if q6(_d(line.unit_cost)) < ZERO:
            raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")

    recalculate(shipment)
    totals = supplier_totals(shipment)
    supplier_ids = [b.supplier_id for b in totals]
    suppliers = {
        s.id: s for s in (await db.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))).all()
    }
    if len(suppliers) != len(supplier_ids):
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")
    await validate_plan(db, shipment)

    number = await _shipment_number(db, shipment)
    base_no = (shipment.invoice_no or "").strip() or f"SH-{number if number is not None else str(shipment.id)[:8]}"

    # 1. Нийлүүлэгч тус бүрд өглөг — машин олон нийлүүлэгчээс ачдаг тул
    #    нэхэмжлэх нэг биш, нийлүүлэгч бүрд өөрийнх.
    invoice_ids: dict[uuid.UUID, uuid.UUID] = {}
    for index, bucket in enumerate(totals):
        if bucket.total_gross <= ZERO:
            continue
        invoice = ApInvoice(
            supplier_id=bucket.supplier_id,
            invoice_no=base_no if bucket.is_main else f"{base_no}/{index + 1}",
            invoice_date=shipment.shipment_date,
            due_date=shipment.shipment_date + timedelta(days=PAYMENT_TERM_DAYS),
            source_type=str(SourceType.FUEL_SHIPMENT),
            source_id=shipment.id,
            amount_gross=bucket.total_gross,
            amount_paid=Decimal("0.00"),
            status=str(InvoiceStatus.OPEN),
        )
        db.add(invoice)
        await db.flush()
        invoice_ids[bucket.supplier_id] = invoice.id
    shipment.ap_invoice_id = invoice_ids.get(shipment.supplier_id)

    # 2. Журналын бичилт: 1303 (түлш), 1304 (бараа), 1402 / 2101 нийлүүлэгч бүрээр.
    main_name = suppliers[shipment.supplier_id].name
    extra = len(totals) - 1
    await posting.post(
        db,
        event_type=str(EventType.SHIPMENT_POSTED),
        source_type=str(SourceType.FUEL_SHIPMENT),
        source_id=shipment.id,
        entry_date=shipment.shipment_date,
        description=(
            f"Ачилт №{number} — {main_name}"
            + (f" +{extra} нийлүүлэгч" if extra > 0 else "")
            + f", {shipment.vehicle_no}"
        ),
        lines=build_shipment_lines(shipment, totals),
        posted_by=_user_id(user),
    )

    shipment.status = str(ShipmentStatus.POSTED)
    shipment.posted_by = _user_id(user)
    shipment.posted_at = datetime.now(UTC)
    await db.flush()

    await emit(
        db,
        aggregate_type="fuel_shipment",
        aggregate_id=shipment.id,
        event_type=str(EventType.SHIPMENT_POSTED),
        payload={
            "shipment_id": str(shipment.id),
            "number": number,
            "supplier_id": str(shipment.supplier_id),
            "supplier_count": len(totals),
            "vehicle_no": shipment.vehicle_no,
            "shipment_date": shipment.shipment_date.isoformat(),
            "subtotal": str(shipment.subtotal),
            "vat_amount": str(shipment.vat_amount),
            "total_gross": str(shipment.total_gross),
            "ap_invoice_ids": [str(i) for i in invoice_ids.values()],
        },
    )
    await audit(
        db,
        user_id=_user_id(user),
        action="fuel_shipment.post",
        entity_type="fuel_shipment",
        entity_id=shipment.id,
        before={"status": str(ShipmentStatus.DRAFT)},
        after={
            "status": str(ShipmentStatus.POSTED),
            "total_gross": str(shipment.total_gross),
            "suppliers": {str(k): str(v) for k, v in invoice_ids.items()},
        },
    )

    # 3. Төлөвлөгөө — үүсгэх үедээ заасан сав/салбар руу тэр дороо буулгана.
    await execute_plan(db, user, shipment)
    return shipment


# --------------------------------------------------------------------------- #
# Салбарт буулгах — түлш
# --------------------------------------------------------------------------- #
async def deliver(
    db: AsyncSession,
    user: User | None,
    shipment: FuelShipment,
    *,
    tank_id: uuid.UUID,
    liters: Decimal,
    receipt_date: date | None = None,
    note: str | None = None,
) -> FuelReceipt:
    """Машинаас салбарын саванд буулгана.

    * `FuelReceipt` (shipment_id-тай, мөрийн нийлүүлэгчтэй) үүсч шууд бүртгэгдэнэ;
    * сав ачилтын landed өртгөөр дүүрнэ;
    * 1303 → 1301 журналын бичилт;
    * салбарын тооцоонд өр (charge) = литр × landed × (1 + НӨАТ).
    """
    if str(shipment.status) != str(ShipmentStatus.POSTED):
        raise HTTPException(status_code=422, detail="Зөвхөн бүртгэсэн ачилтаас буулгана")

    liters = q3(_d(liters))
    if liters <= ZERO:
        raise HTTPException(status_code=422, detail="Литр 0-ээс их байх ёстой")

    tank = await db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Сав олдсонгүй")

    line = _fuel_line(shipment, tank.fuel_id)
    landed = q6(_d(line.landed_unit_cost))

    remaining = await remaining_by_fuel(db, shipment)
    left = remaining.get(tank.fuel_id, ZERO)
    if liters > left:
        fuel = await db.scalar(select(Fuel).where(Fuel.id == tank.fuel_id))
        name = fuel.name_mn if fuel else "түлш"
        raise HTTPException(
            status_code=422,
            detail=f"Машин дээр {name} {left} л үлдсэн — {liters} л буулгах боломжгүй",
        )

    capacity = q3(_d(tank.capacity_l))
    if capacity > ZERO and q3(_d(tank.current_l) + liters) > capacity:
        raise HTTPException(status_code=422, detail=f"{tank.name}: савны багтаамжаас хэтэрч байна")

    when = receipt_date or shipment.shipment_date
    subtotal = q2(liters * landed)
    # Мөрийн сүүлчийн литр: 1303-д үлдсэн дүнг яг авна — буулгалт бүрийн
    # дугуйллын зөрүү хуримтлагдаж замд яваа дансанд цент үлдэхгүй.
    if liters == left:
        subtotal = await _transit_left_amount(db, shipment, line)

    receipt = FuelReceipt(
        shipment_id=shipment.id,
        branch_id=tank.branch_id,
        supplier_id=effective_supplier(shipment, line),
        tank_id=tank.id,
        fuel_id=tank.fuel_id,
        receipt_date=when,
        invoice_no=shipment.invoice_no,
        liters=liters,
        unit_cost=landed,
        freight_cost=ZERO,
        subtotal=subtotal,
        # НӨАТ ачилт дээрээ бүртгэгдсэн — түгээлт дээр давхардуулахгүй.
        vat_amount=ZERO,
        total_gross=subtotal,
        landed_unit_cost=landed,
        status=str(DocStatus.POSTED),
        posted_by=_user_id(user),
        posted_at=datetime.now(UTC),
        note=(note or "").strip() or None,
    )
    db.add(receipt)
    await db.flush()

    # 1. Сав дүүрнэ — хөдлөх дундаж өртгөөр.
    await tank_service.receive_fuel(
        db,
        tank,
        liters,
        landed,
        ref_type=str(SourceType.FUEL_RECEIPT),
        ref_id=receipt.id,
    )

    # 2. Журналын бичилт: 1301 (салбар) / 1303.
    number = None
    try:
        await db.refresh(receipt, ["number"])
        number = receipt.number
    except Exception:  # noqa: BLE001
        pass
    await posting.post(
        db,
        event_type=str(EventType.SHIPMENT_DELIVERY),
        source_type=str(SourceType.FUEL_RECEIPT),
        source_id=receipt.id,
        entry_date=when,
        description=f"Ачилт №{await _shipment_number(db, shipment)} → {tank.name}",
        lines=build_shipment_delivery_lines(receipt),
        posted_by=_user_id(user),
    )

    # 3. Салбарын тооцооны өр — салбартай сав л тооцоонд орно.
    if tank.branch_id is not None:
        await _charge_branch(
            db,
            user,
            branch_id=tank.branch_id,
            when=when,
            subtotal=subtotal,
            ref_type=str(SourceType.FUEL_RECEIPT),
            ref_id=receipt.id,
            note=f"Ачилт №{await _shipment_number(db, shipment)} — {liters} л",
        )

    await audit(
        db,
        user_id=_user_id(user),
        action="fuel_shipment.deliver",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        after={
            "shipment_id": str(shipment.id),
            "tank_id": str(tank.id),
            "branch_id": str(tank.branch_id) if tank.branch_id else None,
            "liters": str(liters),
            "landed_unit_cost": str(landed),
            "subtotal": str(subtotal),
            "number": number,
        },
    )
    return receipt


async def deliver_many(
    db: AsyncSession,
    user: User | None,
    shipment: FuelShipment,
    *,
    allocations: list[tuple[uuid.UUID, Decimal]],
    receipt_date: date | None = None,
    note: str | None = None,
) -> list[FuelReceipt]:
    """Нэг зогсолтоор олон саванд буулгах — салбар бүрийн саванд өөр хэмжээгээр.

    Нэг transaction: аль нэг сав багтаамж/үлдэгдлээс хэтэрвэл бүгд буцна.
    """
    receipts: list[FuelReceipt] = []
    for tank_id, liters in allocations:
        receipts.append(
            await deliver(
                db, user, shipment, tank_id=tank_id, liters=liters, receipt_date=receipt_date, note=note
            )
        )
    return receipts


async def _charge_branch(
    db: AsyncSession,
    user: User | None,
    *,
    branch_id: uuid.UUID,
    when: date,
    subtotal: Decimal,
    ref_type: str,
    ref_id: uuid.UUID,
    note: str,
) -> None:
    """Салбарын тооцооны дэвтэрт өр — толгойгоос салбарт очсон түлш/бараа (НӨАТ-тай)."""
    charge = q2(subtotal * (Decimal("1") + VAT_RATE))
    db.add(
        BranchSettlement(
            branch_id=branch_id,
            entry_type=str(SettlementEntryType.CHARGE),
            entry_date=when,
            amount=charge,
            ref_type=ref_type,
            ref_id=ref_id,
            note=note,
            created_by=_user_id(user),
        )
    )
    await db.flush()


# --------------------------------------------------------------------------- #
# Салбарт буулгах — бараа
# --------------------------------------------------------------------------- #
async def deliver_goods(
    db: AsyncSession,
    user: User | None,
    shipment: FuelShipment,
    *,
    branch_id: uuid.UUID,
    lines: list[tuple[uuid.UUID, Decimal]],
    receipt_date: date | None = None,
    note: str | None = None,
) -> list[Purchase]:
    """Машинаас нэг салбарт бараа буулгана.

    Нийлүүлэгч тус бүрд нэг `Purchase` (shipment_id-тай) үүсч шууд бүртгэгдэнэ:
    бараа салбарын нөөцөд landed өртгөөр орж (1302 салбар), 1304-өөс хасагдана;
    өглөг, НӨАТ ачилт дээрээ бүртгэгдсэн тул энд давхардахгүй; салбарын
    тооцоонд өр үүснэ.
    """
    if str(shipment.status) != str(ShipmentStatus.POSTED):
        raise HTTPException(status_code=422, detail="Зөвхөн бүртгэсэн ачилтаас буулгана")
    if not lines:
        raise HTTPException(status_code=422, detail="Буулгах бараа сонгоогүй байна")

    branch = await db.scalar(select(Branch).where(Branch.id == branch_id))
    if branch is None or not branch.is_active:
        raise HTTPException(status_code=404, detail="Салбар олдсонгүй эсвэл идэвхгүй")

    # Нэг бараа хоёр мөрөнд орсон бол нэгтгэнэ.
    merged: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for product_id, qty in lines:
        qty = q3(_d(qty))
        if qty <= ZERO:
            raise HTTPException(status_code=422, detail="Тоо хэмжээ 0-ээс их байх ёстой")
        merged[product_id] = q3(merged[product_id] + qty)

    remaining = await remaining_goods_by_product(db, shipment)
    products = {
        p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(merged)))).all()
    }
    for product_id, qty in merged.items():
        line = _goods_line(shipment, product_id)  # ачилтад байгаа эсэх
        left = remaining.get(product_id, ZERO)
        product = products.get(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
        if qty > left:
            raise HTTPException(
                status_code=422,
                detail=f"Машин дээр {product.name_mn} {left} {product.unit} үлдсэн — {qty} буулгах боломжгүй",
            )
        del line

    when = receipt_date or shipment.shipment_date
    number = await _shipment_number(db, shipment)

    # Нийлүүлэгч бүрд тусдаа баримт — худалдан авалтын түүх нийлүүлэгчээр шүүгддэг.
    by_supplier: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal]]] = defaultdict(list)
    for product_id, qty in merged.items():
        by_supplier[effective_supplier(shipment, _goods_line(shipment, product_id))].append((product_id, qty))

    purchases: list[Purchase] = []
    for supplier_id, group in by_supplier.items():
        purchase = Purchase(
            shipment_id=shipment.id,
            branch_id=branch.id,
            supplier_id=supplier_id,
            purchase_date=when,
            invoice_no=shipment.invoice_no,
            status=str(DocStatus.POSTED),
            posted_by=_user_id(user),
            posted_at=datetime.now(UTC),
            note=(note or "").strip() or None,
        )
        subtotal = ZERO
        purchase.items = []
        for product_id, qty in group:
            goods_line = _goods_line(shipment, product_id)
            landed = q6(_d(goods_line.landed_unit_cost))
            amount = q2(qty * landed)
            # Барааны сүүлчийн ширхэг: 1304-д үлдсэн дүнг яг авна (дугуйллын зөрүү).
            if qty == remaining.get(product_id, ZERO):
                amount = await _transit_left_amount(db, shipment, goods_line)
            subtotal = q2(subtotal + amount)
            purchase.items.append(
                PurchaseItem(product_id=product_id, qty=qty, unit_cost=landed, amount=amount)
            )
        purchase.subtotal = subtotal
        # НӨАТ ачилт дээрээ бүртгэгдсэн.
        purchase.vat_amount = ZERO
        purchase.total_gross = subtotal
        db.add(purchase)
        await db.flush()

        # 1. Салбарын нөөц — хөдлөх дундаж өртгөөр.
        for item in purchase.items:
            await inventory_service.receive_product(
                db,
                products[item.product_id],
                item.qty,
                item.unit_cost,
                ref_type=str(SourceType.PURCHASE),
                ref_id=purchase.id,
                branch_id=branch.id,
            )

        # 2. Журнал: 1302 (салбар) / 1304.
        await posting.post(
            db,
            event_type=str(EventType.SHIPMENT_GOODS_DELIVERY),
            source_type=str(SourceType.PURCHASE),
            source_id=purchase.id,
            entry_date=when,
            description=f"Ачилт №{number} → {branch.name} (бараа)",
            lines=build_shipment_goods_delivery_lines(purchase),
            posted_by=_user_id(user),
        )

        # 3. Салбарын тооцооны өр.
        await _charge_branch(
            db,
            user,
            branch_id=branch.id,
            when=when,
            subtotal=subtotal,
            ref_type=str(SourceType.PURCHASE),
            ref_id=purchase.id,
            note=f"Ачилт №{number} — бараа {len(purchase.items)} нэр төрөл",
        )

        await audit(
            db,
            user_id=_user_id(user),
            action="fuel_shipment.deliver_goods",
            entity_type="purchase",
            entity_id=purchase.id,
            after={
                "shipment_id": str(shipment.id),
                "branch_id": str(branch.id),
                "supplier_id": str(supplier_id),
                "subtotal": str(subtotal),
                "items": [{"product_id": str(i.product_id), "qty": str(i.qty)} for i in purchase.items],
            },
        )
        purchases.append(purchase)
    return purchases


# --------------------------------------------------------------------------- #
# Машинаас шууд борлуулах / хорогдол
# --------------------------------------------------------------------------- #
async def add_outflow(
    db: AsyncSession,
    user: User | None,
    shipment: FuelShipment,
    *,
    kind: str,
    fuel_id: uuid.UUID,
    liters: Decimal,
    unit_price: Decimal = ZERO,
    received_to: str = "bank",
    bank_account_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
    outflow_date: date | None = None,
    customer_name: str | None = None,
    note: str | None = None,
) -> FuelShipmentOutflow:
    """Үлдсэн литрийг машинаас шууд борлуулах (`sale`) эсвэл хорогдолд (`loss`) бичнэ."""
    if str(shipment.status) != str(ShipmentStatus.POSTED):
        raise HTTPException(status_code=422, detail="Зөвхөн бүртгэсэн ачилт дээр боломжтой")

    kind = str(kind)
    if kind not in (str(ShipmentOutflowKind.SALE), str(ShipmentOutflowKind.LOSS)):
        raise HTTPException(status_code=422, detail="Төрөл буруу: sale эсвэл loss")

    liters = q3(_d(liters))
    if liters <= ZERO:
        raise HTTPException(status_code=422, detail="Литр 0-ээс их байх ёстой")

    landed = _landed_cost(shipment, fuel_id)
    remaining = await remaining_by_fuel(db, shipment)
    left = remaining.get(fuel_id, ZERO)
    if liters > left:
        raise HTTPException(
            status_code=422, detail=f"Машин дээр {left} л үлдсэн — {liters} л гаргах боломжгүй"
        )

    unit_price = q2(_d(unit_price))
    if kind == str(ShipmentOutflowKind.SALE):
        if unit_price <= ZERO:
            raise HTTPException(status_code=422, detail="Борлуулалтын нэгж үнэ 0-ээс их байх ёстой")
        if received_to not in ("cash", "bank"):
            raise HTTPException(status_code=422, detail="Төлбөр cash эсвэл bank байна")
        if received_to == "bank" and bank_account_id is not None:
            account = await db.scalar(select(BankAccount).where(BankAccount.id == bank_account_id))
            if account is None:
                raise HTTPException(status_code=404, detail="Харилцах данс олдсонгүй")
    else:
        unit_price = ZERO

    amount = q2(liters * unit_price)
    cost_amount = q2(liters * landed)
    # Түлшний сүүлчийн литр машинаас гарахад 1303-д үлдсэн дүнг яг авна.
    if liters == left:
        cost_amount = await _transit_left_amount(db, shipment, _fuel_line(shipment, fuel_id))
    when = outflow_date or datetime.now(UTC).date()

    outflow = FuelShipmentOutflow(
        shipment_id=shipment.id,
        kind=kind,
        fuel_id=fuel_id,
        branch_id=branch_id,
        outflow_date=when,
        liters=liters,
        unit_price=unit_price,
        amount=amount,
        cost_amount=cost_amount,
        received_to=received_to,
        bank_account_id=bank_account_id if received_to == "bank" else None,
        customer_name=(customer_name or "").strip() or None,
        note=(note or "").strip() or None,
        created_by=_user_id(user),
    )
    db.add(outflow)
    await db.flush()

    if kind == str(ShipmentOutflowKind.SALE):
        event, lines = EventType.SHIPMENT_SALE, build_shipment_sale_lines(outflow)
        description = f"Машинаас шууд борлуулалт — {liters} л"
    else:
        event, lines = EventType.SHIPMENT_LOSS, build_shipment_loss_lines(outflow)
        description = f"Ачилтын хорогдол — {liters} л"

    await posting.post(
        db,
        event_type=str(event),
        source_type=str(SourceType.SHIPMENT_OUTFLOW),
        source_id=outflow.id,
        entry_date=when,
        description=description,
        lines=lines,
        posted_by=_user_id(user),
    )

    await audit(
        db,
        user_id=_user_id(user),
        action=f"fuel_shipment.{kind}",
        entity_type="fuel_shipment_outflow",
        entity_id=outflow.id,
        after={
            "shipment_id": str(shipment.id),
            "fuel_id": str(fuel_id),
            "liters": str(liters),
            "unit_price": str(unit_price),
            "amount": str(amount),
            "cost_amount": str(cost_amount),
        },
    )
    return outflow


# --------------------------------------------------------------------------- #
# Хаах
# --------------------------------------------------------------------------- #
async def close_shipment(db: AsyncSession, user: User | None, shipment: FuelShipment) -> FuelShipment:
    """Бүх литр, ширхэг тэглэгдсэн ачилтыг хаана."""
    if str(shipment.status) != str(ShipmentStatus.POSTED):
        raise HTTPException(status_code=422, detail="Зөвхөн бүртгэсэн ачилтыг хаана")

    remaining = await remaining_by_fuel(db, shipment)
    leftovers = {fid: liters for fid, liters in remaining.items() if liters != ZERO}
    parts: list[str] = []
    if leftovers:
        fuels = {
            f.id: f.name_mn
            for f in (await db.scalars(select(Fuel).where(Fuel.id.in_(leftovers)))).all()
        }
        parts.extend(f"{fuels.get(fid, '?')}: {liters} л" for fid, liters in leftovers.items())

    goods_left = {
        pid: qty for pid, qty in (await remaining_goods_by_product(db, shipment)).items() if qty != ZERO
    }
    if goods_left:
        products = {
            p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(goods_left)))).all()
        }
        parts.extend(
            f"{products[pid].name_mn if pid in products else '?'}: {qty} {products[pid].unit if pid in products else ''}".strip()
            for pid, qty in goods_left.items()
        )
    if parts:
        raise HTTPException(
            status_code=422,
            detail=f"Машин дээр үлдэгдэлтэй байна ({', '.join(parts)}) — буулгах, зарах эсвэл хорогдолд бичнэ үү",
        )

    shipment.status = str(ShipmentStatus.CLOSED)
    shipment.closed_at = datetime.now(UTC)
    await db.flush()

    await audit(
        db,
        user_id=_user_id(user),
        action="fuel_shipment.close",
        entity_type="fuel_shipment",
        entity_id=shipment.id,
        after={"status": str(ShipmentStatus.CLOSED)},
    )
    return shipment
