"""Түлшний ачилтын API — машинаар татсан түлш, барааг салбаруудад түгээх.

Урсгал: ноорог (олон нийлүүлэгч, түлш + бараа, хуваарилалтын төлөвлөгөө)
→ бүртгэх (нийлүүлэгч бүрд өглөг, төлөвлөгөө буулгагдана) → үлдэгдлийг
салбаруудад буулгах → шууд зарах/хорогдолд бичих → хаах.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import DocStatus, InvoiceStatus, ShipmentStatus
from app.models.accounting import ApInvoice
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
from app.models.user import User
from app.money import q2, q3, q6
from app.schemas.shipment import (
    OUTFLOW_KIND_NAMES_MN,
    SHIPMENT_STATUS_NAMES_MN,
    FuelAllocationOut,
    FuelShipmentCreate,
    FuelShipmentDetailOut,
    FuelShipmentListOut,
    FuelShipmentOut,
    FuelShipmentUpdate,
    GoodsAllocationOut,
    ShipmentDeliverGoodsIn,
    ShipmentDeliverIn,
    ShipmentDeliverManyIn,
    ShipmentDeliveryRow,
    ShipmentGoodsDeliveryRow,
    ShipmentGoodsIn,
    ShipmentGoodsOut,
    ShipmentItemIn,
    ShipmentItemOut,
    ShipmentOutflowIn,
    ShipmentOutflowOut,
    ShipmentSupplierOut,
)
from app.services import shipment_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["fuel_shipments"])

ZERO = Decimal("0")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _number(doc: FuelShipment | FuelReceipt | Purchase) -> int | None:
    try:
        return doc.number
    except Exception:  # noqa: BLE001
        return None


async def _load_shipment(db: AsyncSession, shipment_id: uuid.UUID) -> FuelShipment:
    shipment = await db.scalar(select(FuelShipment).where(FuelShipment.id == shipment_id))
    if shipment is None:
        raise HTTPException(status_code=404, detail="Ачилт олдсонгүй")
    return shipment


async def _fuel_map(db: AsyncSession) -> dict[uuid.UUID, Fuel]:
    return {f.id: f for f in (await db.scalars(select(Fuel))).all()}


async def _supplier_names(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict((await db.execute(select(Supplier.id, Supplier.name).where(Supplier.id.in_(ids)))).all())


async def _branch_names(db: AsyncSession) -> dict[uuid.UUID, str]:
    return dict((await db.execute(select(Branch.id, Branch.name))).all())


# --------------------------------------------------------------------------- #
# Гаралт
# --------------------------------------------------------------------------- #
async def _supplier_rows(db: AsyncSession, shipment: FuelShipment) -> list[ShipmentSupplierOut]:
    """Нийлүүлэгч тус бүрийн дүн + (бүртгэсэн бол) нэхэмжлэхийн төлөв."""
    totals = shipment_service.supplier_totals(shipment)
    names = await _supplier_names(db, {b.supplier_id for b in totals})
    invoices: dict[uuid.UUID, ApInvoice] = {}
    if str(shipment.status) != str(ShipmentStatus.DRAFT):
        rows = (
            await db.scalars(
                select(ApInvoice).where(
                    ApInvoice.source_type == "fuel_shipment", ApInvoice.source_id == shipment.id
                )
            )
        ).all()
        invoices = {inv.supplier_id: inv for inv in rows}
    out: list[ShipmentSupplierOut] = []
    for bucket in totals:
        inv = invoices.get(bucket.supplier_id)
        out.append(
            ShipmentSupplierOut(
                supplier_id=bucket.supplier_id,
                supplier_name=names.get(bucket.supplier_id),
                is_main=bucket.is_main,
                subtotal=bucket.subtotal,
                vat_amount=bucket.vat_amount,
                total_gross=bucket.total_gross,
                ap_invoice_id=inv.id if inv else None,
                amount_paid=q2(inv.amount_paid or ZERO) if inv else ZERO,
                invoice_status=str(inv.status) if inv else None,
            )
        )
    return out


def _aggregate_invoice_status(rows: list[ShipmentSupplierOut]) -> tuple[Decimal, str | None]:
    """Бүх нийлүүлэгчийн төлсөн нийт ба нэгдсэн төлөв: paid / partial / open."""
    with_invoice = [r for r in rows if r.invoice_status is not None]
    if not with_invoice:
        return ZERO, None
    paid = q2(sum((r.amount_paid for r in with_invoice), ZERO))
    statuses = {r.invoice_status for r in with_invoice}
    if statuses == {str(InvoiceStatus.PAID)}:
        status = str(InvoiceStatus.PAID)
    elif paid > ZERO or str(InvoiceStatus.PARTIAL) in statuses:
        status = str(InvoiceStatus.PARTIAL)
    else:
        status = str(InvoiceStatus.OPEN)
    return paid, status


async def _plan_out(
    db: AsyncSession, shipment: FuelShipment
) -> tuple[dict[uuid.UUID, list[FuelAllocationOut]], dict[uuid.UUID, list[GoodsAllocationOut]]]:
    """Ноорог дээрх хуваарилалтын төлөвлөгөө — мөр бүрээр, нэртэй."""
    plan = shipment.plan or {}
    fuel_plan = plan.get("fuel") or []
    goods_plan = plan.get("goods") or []
    fuel_alloc: dict[uuid.UUID, list[FuelAllocationOut]] = defaultdict(list)
    goods_alloc: dict[uuid.UUID, list[GoodsAllocationOut]] = defaultdict(list)
    if not fuel_plan and not goods_plan:
        return fuel_alloc, goods_alloc
    branches = await _branch_names(db)
    if fuel_plan:
        tank_ids = {uuid.UUID(a["tank_id"]) for a in fuel_plan}
        tanks = {t.id: t for t in (await db.scalars(select(Tank).where(Tank.id.in_(tank_ids)))).all()}
        for a in fuel_plan:
            tank = tanks.get(uuid.UUID(a["tank_id"]))
            fuel_alloc[uuid.UUID(a["fuel_id"])].append(
                FuelAllocationOut(
                    tank_id=uuid.UUID(a["tank_id"]),
                    tank_name=tank.name if tank else None,
                    branch_id=tank.branch_id if tank else None,
                    branch_name=branches.get(tank.branch_id) if tank and tank.branch_id else None,
                    liters=q3(Decimal(a["liters"])),
                )
            )
    for a in goods_plan:
        goods_alloc[uuid.UUID(a["product_id"])].append(
            GoodsAllocationOut(
                branch_id=uuid.UUID(a["branch_id"]),
                branch_name=branches.get(uuid.UUID(a["branch_id"])),
                qty=q3(Decimal(a["qty"])),
            )
        )
    return fuel_alloc, goods_alloc


async def _to_out(
    db: AsyncSession,
    shipment: FuelShipment,
    supplier_name: str | None = None,
    *,
    with_remaining: bool = True,
) -> FuelShipmentOut:
    fuels = await _fuel_map(db)
    remaining = await shipment_service.remaining_by_fuel(db, shipment) if with_remaining else {}
    remaining_goods = (
        await shipment_service.remaining_goods_by_product(db, shipment) if with_remaining else {}
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

    line_suppliers = {shipment.supplier_id} | {
        s for s in (l.supplier_id for l in [*shipment.items, *shipment.goods]) if s is not None
    }
    supplier_names = await _supplier_names(db, line_suppliers)
    fuel_alloc, goods_alloc = await _plan_out(db, shipment)

    items = [
        ShipmentItemOut(
            id=item.id,
            fuel_id=item.fuel_id,
            fuel_name=fuels[item.fuel_id].name_mn if item.fuel_id in fuels else None,
            fuel_code=fuels[item.fuel_id].code if item.fuel_id in fuels else None,
            supplier_id=shipment_service.effective_supplier(shipment, item),
            supplier_name=supplier_names.get(shipment_service.effective_supplier(shipment, item)),
            liters=q3(item.liters or ZERO),
            unit_cost=Decimal(item.unit_cost or ZERO),
            amount=q2(item.amount or ZERO),
            landed_unit_cost=Decimal(item.landed_unit_cost or ZERO),
            delivered_l=delivered.get(item.fuel_id, ZERO),
            outflow_l=outflow_l.get(item.fuel_id, ZERO),
            remaining_l=remaining.get(item.fuel_id, ZERO),
            allocations=fuel_alloc.get(item.fuel_id, []),
        )
        for item in shipment.items
    ]

    goods_out: list[ShipmentGoodsOut] = []
    if shipment.goods:
        products = {
            p.id: p
            for p in (
                await db.scalars(select(Product).where(Product.id.in_({g.product_id for g in shipment.goods})))
            ).all()
        }
        for line in shipment.goods:
            product = products.get(line.product_id)
            qty = q3(line.qty or ZERO)
            left = remaining_goods.get(line.product_id, qty if not with_remaining else ZERO)
            goods_out.append(
                ShipmentGoodsOut(
                    id=line.id,
                    product_id=line.product_id,
                    product_name=product.name_mn if product else None,
                    product_sku=product.sku if product else None,
                    unit=product.unit if product else None,
                    supplier_id=shipment_service.effective_supplier(shipment, line),
                    supplier_name=supplier_names.get(shipment_service.effective_supplier(shipment, line)),
                    qty=qty,
                    unit_cost=Decimal(line.unit_cost or ZERO),
                    amount=q2(line.amount or ZERO),
                    landed_unit_cost=Decimal(line.landed_unit_cost or ZERO),
                    delivered_qty=q3(qty - left) if with_remaining else ZERO,
                    remaining_qty=left if with_remaining else qty,
                    allocations=goods_alloc.get(line.product_id, []),
                )
            )

    if supplier_name is None:
        supplier_name = supplier_names.get(shipment.supplier_id)

    suppliers = await _supplier_rows(db, shipment)
    amount_paid, invoice_status = _aggregate_invoice_status(suppliers)
    total_liters = q3(sum((Decimal(i.liters or ZERO) for i in shipment.items), ZERO))
    remaining_liters = q3(sum(remaining.values(), ZERO)) if with_remaining else ZERO
    total_goods = q3(sum((Decimal(g.qty or ZERO) for g in shipment.goods), ZERO))
    remaining_goods_qty = q3(sum(remaining_goods.values(), ZERO)) if with_remaining else ZERO

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
        goods=goods_out,
        suppliers=suppliers,
        supplier_count=len(suppliers),
        total_liters=total_liters,
        remaining_liters=remaining_liters,
        total_goods_qty=total_goods,
        remaining_goods_qty=remaining_goods_qty,
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
            {
                "fuel_id": str(i.fuel_id),
                "supplier_id": str(i.supplier_id) if i.supplier_id else None,
                "liters": str(i.liters),
                "unit_cost": str(i.unit_cost),
            }
            for i in shipment.items
        ],
        "goods": [
            {
                "product_id": str(g.product_id),
                "supplier_id": str(g.supplier_id) if g.supplier_id else None,
                "qty": str(g.qty),
                "unit_cost": str(g.unit_cost),
            }
            for g in shipment.goods
        ],
        "plan": shipment.plan,
    }


# --------------------------------------------------------------------------- #
# Оролт шалгах
# --------------------------------------------------------------------------- #
async def _validate_lines(
    db: AsyncSession, items: list[ShipmentItemIn], goods: list[ShipmentGoodsIn]
) -> tuple[list[FuelShipmentItem], list[FuelShipmentGoods]]:
    if not items and not goods:
        raise HTTPException(status_code=422, detail="Ачилтад дор хаяж нэг түлш эсвэл бараа хэрэгтэй")

    supplier_ids = {s for s in (l.supplier_id for l in [*items, *goods]) if s is not None}
    if supplier_ids:
        found = set((await db.scalars(select(Supplier.id).where(Supplier.id.in_(supplier_ids)))).all())
        if found != supplier_ids:
            raise HTTPException(status_code=404, detail="Мөрийн нийлүүлэгч олдсонгүй")

    fuels = await _fuel_map(db)
    seen_fuel: set[uuid.UUID] = set()
    for item in items:
        if item.fuel_id not in fuels:
            raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
        if item.fuel_id in seen_fuel:
            raise HTTPException(status_code=422, detail="Нэг түлш давхардаж байна — мөрийг нэгтгэнэ үү")
        seen_fuel.add(item.fuel_id)
        if sum((q3(a.liters) for a in item.allocations), ZERO) > q3(item.liters):
            raise HTTPException(
                status_code=422,
                detail=f"{fuels[item.fuel_id].name_mn}: хуваарилалт ачсан литрээс их байна",
            )

    if goods:
        product_ids = {g.product_id for g in goods}
        products = {
            p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
        }
        if len(products) != len(product_ids):
            raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
        seen_product: set[uuid.UUID] = set()
        for line in goods:
            if line.product_id in seen_product:
                raise HTTPException(status_code=422, detail="Нэг бараа давхардаж байна — мөрийг нэгтгэнэ үү")
            seen_product.add(line.product_id)
            if sum((q3(a.qty) for a in line.allocations), ZERO) > q3(line.qty):
                raise HTTPException(
                    status_code=422,
                    detail=f"{products[line.product_id].name_mn}: хуваарилалт ачсан тооноос их байна",
                )

    return (
        [
            FuelShipmentItem(
                fuel_id=item.fuel_id,
                supplier_id=item.supplier_id,
                liters=q3(item.liters),
                unit_cost=q6(item.unit_cost),
            )
            for item in items
        ],
        [
            FuelShipmentGoods(
                product_id=line.product_id,
                supplier_id=line.supplier_id,
                qty=q3(line.qty),
                unit_cost=q6(line.unit_cost),
            )
            for line in goods
        ],
    )


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
        # Үндсэн эсвэл аль нэг мөрийн нийлүүлэгч.
        item_match = select(FuelShipmentItem.shipment_id).where(FuelShipmentItem.supplier_id == supplier_id)
        goods_match = select(FuelShipmentGoods.shipment_id).where(FuelShipmentGoods.supplier_id == supplier_id)
        conditions.append(
            (FuelShipment.supplier_id == supplier_id)
            | FuelShipment.id.in_(item_match)
            | FuelShipment.id.in_(goods_match)
        )
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

    # Түлшний түгээлтүүд — салбар, савны нэртэй.
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
    deliveries = [_delivery_row(receipt, branch_name, tank_name, fuel_name, fuel_code) for receipt, branch_name, tank_name, fuel_name, fuel_code in delivery_rows]

    # Барааны түгээлтүүд — худалдан авалтын мөр бүрээр.
    goods_rows = (
        await db.execute(
            select(PurchaseItem, Purchase, Branch.name, Product.name_mn, Product.unit)
            .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
            .join(Product, Product.id == PurchaseItem.product_id)
            .outerjoin(Branch, Branch.id == Purchase.branch_id)
            .where(Purchase.shipment_id == shipment.id, Purchase.status == str(DocStatus.POSTED))
            .order_by(Purchase.purchase_date, Purchase.created_at, PurchaseItem.created_at)
        )
    ).all()
    goods_deliveries = [
        ShipmentGoodsDeliveryRow(
            id=item.id,
            purchase_id=purchase.id,
            number=_number(purchase),
            receipt_date=purchase.purchase_date,
            branch_id=purchase.branch_id,
            branch_name=branch_name,
            product_id=item.product_id,
            product_name=product_name,
            unit=unit,
            qty=q3(item.qty or ZERO),
            unit_cost=Decimal(item.unit_cost or ZERO),
            amount=q2(item.amount or ZERO),
        )
        for item, purchase, branch_name, product_name, unit in goods_rows
    ]

    fuels = await _fuel_map(db)
    branch_names = await _branch_names(db)
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
        **base.model_dump(), deliveries=deliveries, goods_deliveries=goods_deliveries, outflows=outflows
    )


def _delivery_row(
    receipt: FuelReceipt,
    branch_name: str | None,
    tank_name: str | None,
    fuel_name: str | None,
    fuel_code: str | None,
) -> ShipmentDeliveryRow:
    return ShipmentDeliveryRow(
        id=receipt.id,
        number=_number(receipt),
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


async def _delivery_row_for(db: AsyncSession, receipt: FuelReceipt) -> ShipmentDeliveryRow:
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
    return _delivery_row(receipt, branch_name, tank_name, fuel_name, fuel_code)


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

    items, goods = await _validate_lines(db, payload.items, payload.goods)

    shipment = FuelShipment(
        supplier_id=supplier.id,
        vehicle_no=payload.vehicle_no.strip(),
        driver_name=(payload.driver_name or "").strip() or None,
        shipment_date=payload.shipment_date or date.today(),
        invoice_no=(payload.invoice_no or "").strip() or None,
        freight_cost=q2(payload.freight_cost),
        status=str(ShipmentStatus.DRAFT),
        note=(payload.note or "").strip() or None,
        plan=shipment_service.plan_from_payload(payload.items, payload.goods),
    )
    shipment.items = items
    shipment.goods = goods
    shipment_service.recalculate(shipment)
    db.add(shipment)
    await db.flush()
    # Төлөвлөгөө сав/салбартай таарч байгааг үүсгэх үедээ шалгана — бүртгэхэд
    # биш, оруулж байгаа хүнд тэр дороо мэдэгдэнэ.
    await shipment_service.validate_plan(db, shipment)

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

    if payload.items is not None or payload.goods is not None:
        new_items = payload.items if payload.items is not None else [
            ShipmentItemIn(fuel_id=i.fuel_id, supplier_id=i.supplier_id, liters=i.liters, unit_cost=i.unit_cost)
            for i in shipment.items
        ]
        new_goods = payload.goods if payload.goods is not None else [
            ShipmentGoodsIn(product_id=g.product_id, supplier_id=g.supplier_id, qty=g.qty, unit_cost=g.unit_cost)
            for g in shipment.goods
        ]
        items, goods = await _validate_lines(db, new_items, new_goods)
        shipment.items = items
        shipment.goods = goods
        shipment.plan = shipment_service.plan_from_payload(new_items, new_goods)

    shipment_service.recalculate(shipment)
    await db.flush()
    await shipment_service.validate_plan(db, shipment)

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
    """Ноорог ачилтыг бүртгэнэ: нийлүүлэгч бүрд өглөг + 1303/1304 бичилт,
    хуваарилалтын төлөвлөгөө буулгагдана."""
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
    """Машинаас нэг саванд буулгана."""
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
    return await _delivery_row_for(db, receipt)


@router.post(
    "/fuel-shipments/{shipment_id}/deliver-many",
    response_model=list[ShipmentDeliveryRow],
    status_code=201,
)
async def deliver_many(
    shipment_id: uuid.UUID,
    payload: ShipmentDeliverManyIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> list[ShipmentDeliveryRow]:
    """Нэг зогсолтоор олон саванд буулгана — салбар бүрийн саванд өөр хэмжээгээр."""
    shipment = await _load_shipment(db, shipment_id)
    receipts = await shipment_service.deliver_many(
        db,
        user,
        shipment,
        allocations=[(a.tank_id, a.liters) for a in payload.allocations],
        receipt_date=payload.receipt_date,
        note=payload.note,
    )
    return [await _delivery_row_for(db, r) for r in receipts]


@router.post(
    "/fuel-shipments/{shipment_id}/deliver-goods",
    response_model=list[ShipmentGoodsDeliveryRow],
    status_code=201,
)
async def deliver_goods(
    shipment_id: uuid.UUID,
    payload: ShipmentDeliverGoodsIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("shipments.manage")),
) -> list[ShipmentGoodsDeliveryRow]:
    """Машинаас нэг салбарт бараа буулгана — салбарын нөөцөд орж, тооцоонд өр үүснэ."""
    shipment = await _load_shipment(db, shipment_id)
    purchases = await shipment_service.deliver_goods(
        db,
        user,
        shipment,
        branch_id=payload.branch_id,
        lines=[(l.product_id, l.qty) for l in payload.lines],
        receipt_date=payload.receipt_date,
        note=payload.note,
    )
    branch_name = await db.scalar(select(Branch.name).where(Branch.id == payload.branch_id))
    product_ids = {i.product_id for p in purchases for i in p.items}
    products = {
        p.id: p for p in (await db.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
    }
    rows: list[ShipmentGoodsDeliveryRow] = []
    for purchase in purchases:
        for item in purchase.items:
            product = products.get(item.product_id)
            rows.append(
                ShipmentGoodsDeliveryRow(
                    id=item.id,
                    purchase_id=purchase.id,
                    number=_number(purchase),
                    receipt_date=purchase.purchase_date,
                    branch_id=purchase.branch_id,
                    branch_name=branch_name,
                    product_id=item.product_id,
                    product_name=product.name_mn if product else None,
                    unit=product.unit if product else None,
                    qty=q3(item.qty or ZERO),
                    unit_cost=Decimal(item.unit_cost or ZERO),
                    amount=q2(item.amount or ZERO),
                )
            )
    return rows


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
    """Бүх литр, ширхэг тэглэгдсэн ачилтыг хаана."""
    shipment = await _load_shipment(db, shipment_id)
    await shipment_service.close_shipment(db, user, shipment)
    return await _to_out(db, shipment)
