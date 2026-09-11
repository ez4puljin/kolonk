"""Түлшний ачилтын API — машинаар татсан түлшийг салбаруудад түгээх.

Урсгал: ноорог → бүртгэх (өглөг нээгдэнэ) → салбаруудад буулгах →
үлдэгдлийг шууд зарах/хорогдолд бичих → хаах.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import DocStatus, ShipmentStatus
from app.models.accounting import ApInvoice
from app.models.branch import Branch
from app.models.fuel import Fuel, Tank
from app.models.partner import Supplier
from app.models.procurement import FuelReceipt, FuelShipment, FuelShipmentItem
from app.models.user import User
from app.money import q2, q3
from app.schemas.shipment import (
    OUTFLOW_KIND_NAMES_MN,
    SHIPMENT_STATUS_NAMES_MN,
    FuelShipmentCreate,
    FuelShipmentDetailOut,
    FuelShipmentListOut,
    FuelShipmentOut,
    FuelShipmentUpdate,
    ShipmentDeliverIn,
    ShipmentDeliveryRow,
    ShipmentItemOut,
    ShipmentOutflowIn,
    ShipmentOutflowOut,
)
from app.services import shipment_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["fuel_shipments"])

ZERO = Decimal("0")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _number(shipment: FuelShipment) -> int | None:
    try:
        return shipment.number
    except Exception:  # noqa: BLE001
        return None


async def _load_shipment(db: AsyncSession, shipment_id: uuid.UUID) -> FuelShipment:
    shipment = await db.scalar(select(FuelShipment).where(FuelShipment.id == shipment_id))
    if shipment is None:
        raise HTTPException(status_code=404, detail="Ачилт олдсонгүй")
    return shipment


async def _fuel_map(db: AsyncSession) -> dict[uuid.UUID, Fuel]:
    return {f.id: f for f in (await db.scalars(select(Fuel))).all()}


async def _invoice_info(db: AsyncSession, shipment: FuelShipment) -> tuple[Decimal, str | None]:
    if shipment.ap_invoice_id is None:
        return ZERO, None
    invoice = await db.scalar(select(ApInvoice).where(ApInvoice.id == shipment.ap_invoice_id))
    if invoice is None:
        return ZERO, None
    return q2(invoice.amount_paid or ZERO), str(invoice.status)


async def _to_out(
    db: AsyncSession,
    shipment: FuelShipment,
    supplier_name: str | None = None,
    *,
    with_remaining: bool = True,
) -> FuelShipmentOut:
    fuels = await _fuel_map(db)
    remaining = (
        await shipment_service.remaining_by_fuel(db, shipment) if with_remaining else {}
    )

    # Түлш бүрийн буусан/гарсан литр (дэлгэрэнгүй мөрөнд).
    delivered: dict[uuid.UUID, Decimal] = {}
    if with_remaining:
        rows = (
            await db.execute(
                select(FuelReceipt.fuel_id, func.coalesce(func.sum(FuelReceipt.liters), 0))
                .where(
                    FuelReceipt.shipment_id == shipment.id,
                    FuelReceipt.status == str(DocStatus.POSTED),
                )
                .group_by(FuelReceipt.fuel_id)
            )
        ).all()
        delivered = {fuel_id: q3(liters) for fuel_id, liters in rows}

    # Шууд query — шинэхэн flush хийсэн объектын relationship async дээр
    # lazy-load хийж унадаг тул найдвартай замаар уншина.
    from app.models.procurement import FuelShipmentOutflow

    outflow_l: dict[uuid.UUID, Decimal] = {}
    outflow_rows = (
        await db.execute(
            select(FuelShipmentOutflow.fuel_id, FuelShipmentOutflow.liters).where(
                FuelShipmentOutflow.shipment_id == shipment.id
            )
        )
    ).all()
    for fuel_id, liters in outflow_rows:
        outflow_l[fuel_id] = q3(outflow_l.get(fuel_id, ZERO) + Decimal(liters))

    items = [
        ShipmentItemOut(
            id=item.id,
            fuel_id=item.fuel_id,
            fuel_name=fuels[item.fuel_id].name_mn if item.fuel_id in fuels else None,
            fuel_code=fuels[item.fuel_id].code if item.fuel_id in fuels else None,
            liters=q3(item.liters or ZERO),
            unit_cost=Decimal(item.unit_cost or ZERO),
            amount=q2(item.amount or ZERO),
            landed_unit_cost=Decimal(item.landed_unit_cost or ZERO),
            delivered_l=delivered.get(item.fuel_id, ZERO),
            outflow_l=outflow_l.get(item.fuel_id, ZERO),
            remaining_l=remaining.get(item.fuel_id, ZERO),
        )
        for item in shipment.items
    ]

    if supplier_name is None:
        supplier_name = await db.scalar(
            select(Supplier.name).where(Supplier.id == shipment.supplier_id)
        )

    amount_paid, invoice_status = await _invoice_info(db, shipment)
    total_liters = q3(sum((Decimal(i.liters or ZERO) for i in shipment.items), ZERO))
    remaining_liters = q3(sum(remaining.values(), ZERO)) if with_remaining else ZERO

    return FuelShipmentOut(
        id=shipment.id,
        number=_number(shipment),
        supplier_id=shipment.supplier_id,
        supplier_name=supplier_name,
        vehicle_no=shipment.vehicle_no,
        driver_name=shipment.driver_name,
        shipment_date=shipment.shipment_date,
        invoice_no=shipment.invoice_no,
        freight_cost=q2(shipment.freight_cost or ZERO),
        subtotal=q2(shipment.subtotal or ZERO),
        vat_amount=q2(shipment.vat_amount or ZERO),
        total_gross=q2(shipment.total_gross or ZERO),
        status=str(shipment.status),
        status_name=SHIPMENT_STATUS_NAMES_MN.get(str(shipment.status), str(shipment.status)),
        ap_invoice_id=shipment.ap_invoice_id,
        amount_paid=amount_paid,
        invoice_status=invoice_status,
        posted_at=shipment.posted_at,
        closed_at=shipment.closed_at,
        note=shipment.note,
        created_at=shipment.created_at,
        items=items,
        total_liters=total_liters,
        remaining_liters=remaining_liters,
    )


def _snapshot(shipment: FuelShipment) -> dict:
    return {
        "supplier_id": str(shipment.supplier_id),
        "vehicle_no": shipment.vehicle_no,
        "shipment_date": shipment.shipment_date.isoformat(),
        "freight_cost": str(shipment.freight_cost),
        "subtotal": str(shipment.subtotal),
        "total_gross": str(shipment.total_gross),
        "status": str(shipment.status),
        "items": [
            {"fuel_id": str(i.fuel_id), "liters": str(i.liters), "unit_cost": str(i.unit_cost)}
            for i in shipment.items
        ],
    }


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
@router.get("/fuel-shipments", response_model=FuelShipmentListOut)
async def list_shipments(
    status: ShipmentStatus | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("shipments.manage")),
) -> FuelShipmentListOut:
    conditions = []
    if status is not None:
        conditions.append(FuelShipment.status == str(status))
    if supplier_id is not None:
        conditions.append(FuelShipment.supplier_id == supplier_id)
    if date_from is not None:
        conditions.append(FuelShipment.shipment_date >= date_from)
    if date_to is not None:
        conditions.append(FuelShipment.shipment_date <= date_to)

    total = await db.scalar(select(func.count()).select_from(FuelShipment).where(*conditions)) or 0
    rows = (
        await db.execute(
            select(FuelShipment, Supplier.name)
            .join(Supplier, Supplier.id == FuelShipment.supplier_id)
            .where(*conditions)
            .order_by(FuelShipment.shipment_date.desc(), FuelShipment.number.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    items = [await _to_out(db, shipment, name) for shipment, name in rows]
    return FuelShipmentListOut(items=items, total=int(total))


@router.get("/fuel-shipments/{shipment_id}", response_model=FuelShipmentDetailOut)
async def get_shipment(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("shipments.manage")),
) -> FuelShipmentDetailOut:
    shipment = await _load_shipment(db, shipment_id)
    base = await _to_out(db, shipment)

    # Түгээлтүүд — салбар, савны нэртэй.
    delivery_rows = (
        await db.execute(
            select(FuelReceipt, Branch.name, Tank.name, Fuel.name_mn, Fuel.code)
            .join(Tank, Tank.id == FuelReceipt.tank_id)
            .join(Fuel, Fuel.id == FuelReceipt.fuel_id)
            .outerjoin(Branch, Branch.id == FuelReceipt.branch_id)
            .where(FuelReceipt.shipment_id == shipment.id)
            .order_by(FuelReceipt.receipt_date, FuelReceipt.created_at)
        )
    ).all()
    deliveries = [
        ShipmentDeliveryRow(
            id=receipt.id,
            number=receipt.number,
            receipt_date=receipt.receipt_date,
            branch_id=receipt.branch_id,
            branch_name=branch_name,
            tank_id=receipt.tank_id,
            tank_name=tank_name,
            fuel_name=fuel_name,
            fuel_code=fuel_code,
            liters=q3(receipt.liters or ZERO),
            unit_cost=Decimal(receipt.unit_cost or ZERO),
            subtotal=q2(receipt.subtotal or ZERO),
        )
        for receipt, branch_name, tank_name, fuel_name, fuel_code in delivery_rows
    ]

    fuels = await _fuel_map(db)
    branch_names = {
        b.id: b.name for b in (await db.scalars(select(Branch))).all()
    }
    outflows = [
        ShipmentOutflowOut(
            id=out.id,
            kind=str(out.kind),
            kind_name=OUTFLOW_KIND_NAMES_MN.get(str(out.kind), str(out.kind)),
            fuel_id=out.fuel_id,
            fuel_name=fuels[out.fuel_id].name_mn if out.fuel_id in fuels else None,
            branch_id=out.branch_id,
            branch_name=branch_names.get(out.branch_id) if out.branch_id else None,
            outflow_date=out.outflow_date,
            liters=q3(out.liters or ZERO),
            unit_price=q2(out.unit_price or ZERO),
            amount=q2(out.amount or ZERO),
            cost_amount=q2(out.cost_amount or ZERO),
            received_to=str(out.received_to),
            bank_account_id=out.bank_account_id,
            customer_name=out.customer_name,
            note=out.note,
        )
        for out in sorted(shipment.outflows, key=lambda o: (o.outflow_date, o.created_at))
    ]

    return FuelShipmentDetailOut(
        **base.model_dump(), deliveries=deliveries, outflows=outflows
    )


# --------------------------------------------------------------------------- #
# Бичих
# --------------------------------------------------------------------------- #
@router.post("/fuel-shipments", response_model=FuelShipmentOut, status_code=201)
async def create_shipment(
    payload: FuelShipmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> FuelShipmentOut:
    supplier = await db.scalar(select(Supplier).where(Supplier.id == payload.supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")

    fuels = await _fuel_map(db)
    seen: set[uuid.UUID] = set()
    for item in payload.items:
        if item.fuel_id not in fuels:
            raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
        if item.fuel_id in seen:
            raise HTTPException(status_code=422, detail="Нэг түлш давхардаж байна — мөрийг нэгтгэнэ үү")
        seen.add(item.fuel_id)

    shipment = FuelShipment(
        supplier_id=supplier.id,
        vehicle_no=payload.vehicle_no.strip(),
        driver_name=(payload.driver_name or "").strip() or None,
        shipment_date=payload.shipment_date or date.today(),
        invoice_no=(payload.invoice_no or "").strip() or None,
        freight_cost=q2(payload.freight_cost),
        status=str(ShipmentStatus.DRAFT),
        note=(payload.note or "").strip() or None,
    )
    shipment.items = [
        FuelShipmentItem(fuel_id=item.fuel_id, liters=q3(item.liters), unit_cost=item.unit_cost)
        for item in payload.items
    ]
    shipment_service.recalculate(shipment)
    db.add(shipment)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel_shipment.create",
        entity_type="fuel_shipment",
        entity_id=shipment.id,
        after=_snapshot(shipment),
        ip=_client_ip(request),
    )
    return await _to_out(db, shipment, supplier.name)


@router.patch("/fuel-shipments/{shipment_id}", response_model=FuelShipmentOut)
async def update_shipment(
    shipment_id: uuid.UUID,
    payload: FuelShipmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> FuelShipmentOut:
    shipment = await _load_shipment(db, shipment_id)
    if str(shipment.status) != str(ShipmentStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Бүртгэсэн ачилтыг засах боломжгүй")

    before = _snapshot(shipment)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("supplier_id") is not None:
        supplier = await db.scalar(select(Supplier).where(Supplier.id == changes["supplier_id"]))
        if supplier is None:
            raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")
        shipment.supplier_id = supplier.id
    if changes.get("vehicle_no") is not None:
        shipment.vehicle_no = changes["vehicle_no"].strip()
    if "driver_name" in changes:
        shipment.driver_name = (changes["driver_name"] or "").strip() or None
    if changes.get("shipment_date") is not None:
        shipment.shipment_date = changes["shipment_date"]
    if "invoice_no" in changes:
        shipment.invoice_no = (changes["invoice_no"] or "").strip() or None
    if changes.get("freight_cost") is not None:
        shipment.freight_cost = q2(changes["freight_cost"])
    if "note" in changes:
        shipment.note = (changes["note"] or "").strip() or None

    if payload.items is not None:
        if not payload.items:
            raise HTTPException(status_code=422, detail="Ачилтад дор хаяж нэг түлш хэрэгтэй")
        fuels = await _fuel_map(db)
        seen: set[uuid.UUID] = set()
        for item in payload.items:
            if item.fuel_id not in fuels:
                raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
            if item.fuel_id in seen:
                raise HTTPException(status_code=422, detail="Нэг түлш давхардаж байна — мөрийг нэгтгэнэ үү")
            seen.add(item.fuel_id)
        shipment.items = [
            FuelShipmentItem(fuel_id=item.fuel_id, liters=q3(item.liters), unit_cost=item.unit_cost)
            for item in payload.items
        ]

    shipment_service.recalculate(shipment)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel_shipment.update",
        entity_type="fuel_shipment",
        entity_id=shipment.id,
        before=before,
        after=_snapshot(shipment),
        ip=_client_ip(request),
    )
    return await _to_out(db, shipment)


@router.delete("/fuel-shipments/{shipment_id}", status_code=204, response_model=None)
async def delete_shipment(
    shipment_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> None:
    shipment = await _load_shipment(db, shipment_id)
    if str(shipment.status) != str(ShipmentStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Бүртгэсэн ачилтыг устгах боломжгүй")

    before = _snapshot(shipment)
    await db.delete(shipment)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel_shipment.delete",
        entity_type="fuel_shipment",
        entity_id=shipment_id,
        before=before,
        ip=_client_ip(request),
    )


# --------------------------------------------------------------------------- #
# Үйлдлүүд
# --------------------------------------------------------------------------- #
@router.post("/fuel-shipments/{shipment_id}/post", response_model=FuelShipmentOut)
async def post_shipment(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> FuelShipmentOut:
    """Ноорог ачилтыг бүртгэнэ: өглөг + 1303 бичилт."""
    shipment = await _load_shipment(db, shipment_id)
    await shipment_service.post_shipment(db, user, shipment)
    return await _to_out(db, shipment)


@router.post("/fuel-shipments/{shipment_id}/deliver", response_model=ShipmentDeliveryRow, status_code=201)
async def deliver(
    shipment_id: uuid.UUID,
    payload: ShipmentDeliverIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> ShipmentDeliveryRow:
    """Машинаас салбарын саванд буулгана."""
    shipment = await _load_shipment(db, shipment_id)
    receipt = await shipment_service.deliver(
        db,
        user,
        shipment,
        tank_id=payload.tank_id,
        liters=payload.liters,
        receipt_date=payload.receipt_date,
        note=payload.note,
    )
    row = (
        await db.execute(
            select(Branch.name, Tank.name, Fuel.name_mn, Fuel.code)
            .select_from(Tank)
            .join(Fuel, Fuel.id == Tank.fuel_id)
            .outerjoin(Branch, Branch.id == Tank.branch_id)
            .where(Tank.id == receipt.tank_id)
        )
    ).first()
    branch_name, tank_name, fuel_name, fuel_code = row if row else (None, None, None, None)
    return ShipmentDeliveryRow(
        id=receipt.id,
        number=_numberish(receipt),
        receipt_date=receipt.receipt_date,
        branch_id=receipt.branch_id,
        branch_name=branch_name,
        tank_id=receipt.tank_id,
        tank_name=tank_name,
        fuel_name=fuel_name,
        fuel_code=fuel_code,
        liters=q3(receipt.liters or ZERO),
        unit_cost=Decimal(receipt.unit_cost or ZERO),
        subtotal=q2(receipt.subtotal or ZERO),
    )


def _numberish(receipt: FuelReceipt) -> int | None:
    try:
        return receipt.number
    except Exception:  # noqa: BLE001
        return None


@router.post("/fuel-shipments/{shipment_id}/outflow", response_model=ShipmentOutflowOut, status_code=201)
async def add_outflow(
    shipment_id: uuid.UUID,
    payload: ShipmentOutflowIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> ShipmentOutflowOut:
    """Машинаас шууд борлуулалт эсвэл хорогдол бүртгэнэ."""
    shipment = await _load_shipment(db, shipment_id)
    outflow = await shipment_service.add_outflow(
        db,
        user,
        shipment,
        kind=str(payload.kind),
        fuel_id=payload.fuel_id,
        liters=payload.liters,
        unit_price=payload.unit_price,
        received_to=payload.received_to,
        bank_account_id=payload.bank_account_id,
        branch_id=payload.branch_id,
        outflow_date=payload.outflow_date,
        customer_name=payload.customer_name,
        note=payload.note,
    )
    fuel = await db.scalar(select(Fuel).where(Fuel.id == outflow.fuel_id))
    branch_name = None
    if outflow.branch_id is not None:
        branch_name = await db.scalar(select(Branch.name).where(Branch.id == outflow.branch_id))
    return ShipmentOutflowOut(
        id=outflow.id,
        kind=str(outflow.kind),
        kind_name=OUTFLOW_KIND_NAMES_MN.get(str(outflow.kind), str(outflow.kind)),
        fuel_id=outflow.fuel_id,
        fuel_name=fuel.name_mn if fuel else None,
        branch_id=outflow.branch_id,
        branch_name=branch_name,
        outflow_date=outflow.outflow_date,
        liters=q3(outflow.liters or ZERO),
        unit_price=q2(outflow.unit_price or ZERO),
        amount=q2(outflow.amount or ZERO),
        cost_amount=q2(outflow.cost_amount or ZERO),
        received_to=str(outflow.received_to),
        bank_account_id=outflow.bank_account_id,
        customer_name=outflow.customer_name,
        note=outflow.note,
    )


@router.post("/fuel-shipments/{shipment_id}/close", response_model=FuelShipmentOut)
async def close_shipment(
    shipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> FuelShipmentOut:
    """Бүх литр тэглэгдсэн ачилтыг хаана."""
    shipment = await _load_shipment(db, shipment_id)
    await shipment_service.close_shipment(db, user, shipment)
    return await _to_out(db, shipment)
