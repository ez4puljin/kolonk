"""Түлшний ачилтын хөдөлгүүр — машинаар татсан түлшийг салбаруудад түгээх.

Урсгал:

1. **Ноорог** — Админ ачилтыг бүртгэнэ: машины дугаар, нийлүүлэгч, түлш
   бүрийн литр ба нэгж үнэ.
2. **Бүртгэх** — нийт дүнгээр нийлүүлэгчийн өглөг нээгдэж (нэг нэхэмжлэх),
   түлш «Замд яваа түлш» (1303) дансанд орно.  Төлбөрийг Админ бүртгэлтэй
   данснаас `/ap-payments`-ээр төлнө.
3. **Буулгах** — машин салбар бүрд зогсоход тухайн савны литрийг оруулна.
   Түгээлт бүр `FuelReceipt` (shipment_id-тай) болж, 1303 → 1301 шилжиж,
   салбарын тооцооны дэвтэрт **өр** (charge) үүснэ.
4. **Шууд борлуулалт / хорогдол** — үлдсэн литрийг машинаас шууд зарах
   эсвэл хорогдолд бичих.
5. **Хаах** — бүх литр тэглэгдмэгц ачилт хаагдана.

Бүгд нэг transaction дотор; энэ модуль хэзээ ч ``db.commit()`` дуудахгүй.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
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
from app.models.fuel import Fuel, Tank
from app.models.partner import Supplier
from app.models.procurement import (
    FuelReceipt,
    FuelShipment,
    FuelShipmentItem,
    FuelShipmentOutflow,
)
from app.models.settlement import BranchSettlement
from app.models.user import User
from app.money import q2, q3, q6
from app.services import tank_service
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import posting
from app.services.posting_rules import (
    build_shipment_delivery_lines,
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


def recalculate(shipment: FuelShipment) -> None:
    """Дүн ба landed нэгж өртгийг шинэчилнэ (ноорог дээр ч ажиллана).

    Тээврийн зардлыг мөрийн дүнгээр (пропорциональ) хуваарилж, түлш бүрийн
    landed нэгж өртгийг гаргана — сав руу энэ өртгөөр орно.
    """
    subtotal_items = ZERO
    for item in shipment.items:
        liters = q3(_d(item.liters))
        unit_cost = q6(_d(item.unit_cost))
        item.liters = liters
        item.unit_cost = unit_cost
        item.amount = q2(liters * unit_cost)
        subtotal_items = q2(subtotal_items + item.amount)

    freight = q2(_d(shipment.freight_cost))
    for item in shipment.items:
        liters = _d(item.liters)
        if liters <= ZERO:
            item.landed_unit_cost = ZERO
            continue
        share = (
            q2(freight * item.amount / subtotal_items) if subtotal_items > ZERO else ZERO
        )
        item.landed_unit_cost = q6((item.amount + share) / liters)

    shipment.subtotal = q2(subtotal_items + freight)
    shipment.vat_amount = q2(shipment.subtotal * VAT_RATE)
    shipment.total_gross = q2(shipment.subtotal + shipment.vat_amount)


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


def _landed_cost(shipment: FuelShipment, fuel_id: uuid.UUID) -> Decimal:
    for item in shipment.items:
        if item.fuel_id == fuel_id:
            return q6(_d(item.landed_unit_cost))
    raise HTTPException(status_code=422, detail="Энэ түлш ачилтад байхгүй")


# --------------------------------------------------------------------------- #
# Бүртгэх
# --------------------------------------------------------------------------- #
async def post_shipment(db: AsyncSession, user: User | None, shipment: FuelShipment) -> FuelShipment:
    """Ноорог ачилтыг бүртгэнэ: өглөг + 1303 журналын бичилт."""
    if str(shipment.status) != str(ShipmentStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Аль хэдийн бүртгэгдсэн")
    if not shipment.items:
        raise HTTPException(status_code=422, detail="Ачилтад түлш оруулаагүй байна")
    for item in shipment.items:
        if q3(_d(item.liters)) <= ZERO:
            raise HTTPException(status_code=422, detail="Литр 0-ээс их байх ёстой")
        if q6(_d(item.unit_cost)) < ZERO:
            raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")

    supplier = await db.scalar(select(Supplier).where(Supplier.id == shipment.supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")

    recalculate(shipment)
    number = await _shipment_number(db, shipment)

    # 1. Нийлүүлэгчийн өглөг — машины НИЙТ дүнгээр нэг нэхэмжлэх.
    invoice = ApInvoice(
        supplier_id=shipment.supplier_id,
        invoice_no=((shipment.invoice_no or "").strip() or f"SH-{number if number is not None else str(shipment.id)[:8]}"),
        invoice_date=shipment.shipment_date,
        due_date=shipment.shipment_date + timedelta(days=PAYMENT_TERM_DAYS),
        source_type=str(SourceType.FUEL_SHIPMENT),
        source_id=shipment.id,
        amount_gross=shipment.total_gross,
        amount_paid=Decimal("0.00"),
        status=str(InvoiceStatus.OPEN),
    )
    db.add(invoice)
    await db.flush()
    shipment.ap_invoice_id = invoice.id

    # 2. Журналын бичилт: 1303 + 1402 / 2101.
    await posting.post(
        db,
        event_type=str(EventType.SHIPMENT_POSTED),
        source_type=str(SourceType.FUEL_SHIPMENT),
        source_id=shipment.id,
        entry_date=shipment.shipment_date,
        description=f"Ачилт №{number} — {supplier.name}, {shipment.vehicle_no}",
        lines=build_shipment_lines(shipment, shipment.items),
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
            "vehicle_no": shipment.vehicle_no,
            "shipment_date": shipment.shipment_date.isoformat(),
            "subtotal": str(shipment.subtotal),
            "vat_amount": str(shipment.vat_amount),
            "total_gross": str(shipment.total_gross),
            "ap_invoice_id": str(invoice.id),
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
            "ap_invoice_id": str(invoice.id),
        },
    )
    return shipment


# --------------------------------------------------------------------------- #
# Салбарт буулгах
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

    * `FuelReceipt` (shipment_id-тай) үүсч шууд бүртгэгдэнэ;
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

    landed = _landed_cost(shipment, tank.fuel_id)

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
        raise HTTPException(status_code=422, detail="Савны багтаамжаас хэтэрч байна")

    when = receipt_date or shipment.shipment_date
    subtotal = q2(liters * landed)

    receipt = FuelReceipt(
        shipment_id=shipment.id,
        branch_id=tank.branch_id,
        supplier_id=shipment.supplier_id,
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
        charge = q2(subtotal * (Decimal("1") + VAT_RATE))
        db.add(
            BranchSettlement(
                branch_id=tank.branch_id,
                entry_type=str(SettlementEntryType.CHARGE),
                entry_date=when,
                amount=charge,
                ref_type=str(SourceType.FUEL_RECEIPT),
                ref_id=receipt.id,
                note=f"Ачилт №{await _shipment_number(db, shipment)} — {liters} л",
                created_by=_user_id(user),
            )
        )
        await db.flush()

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
    """Бүх литр тэглэгдсэн ачилтыг хаана."""
    if str(shipment.status) != str(ShipmentStatus.POSTED):
        raise HTTPException(status_code=422, detail="Зөвхөн бүртгэсэн ачилтыг хаана")

    remaining = await remaining_by_fuel(db, shipment)
    leftovers = {fid: liters for fid, liters in remaining.items() if liters != ZERO}
    if leftovers:
        fuels = {
            f.id: f.name_mn
            for f in (await db.scalars(select(Fuel).where(Fuel.id.in_(leftovers)))).all()
        }
        detail = ", ".join(f"{fuels.get(fid, '?')}: {liters} л" for fid, liters in leftovers.items())
        raise HTTPException(
            status_code=422,
            detail=f"Машин дээр үлдэгдэлтэй байна ({detail}) — буулгах, зарах эсвэл хорогдолд бичнэ үү",
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
