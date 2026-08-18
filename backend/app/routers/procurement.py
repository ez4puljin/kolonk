"""Нэгдсэн худалдан авалт — шатахуун ба барааг нэг үйлдлээр орлогод авна.

Өмнө нь шатахуун (`/fuel-receipts`) ба бараа (`/purchases`) хоёр тусдаа
цэс, тусдаа маягттай байсан. Бодит амьдрал дээр нийлүүлэгч нэг өдөр
хоёуланг нь авчирдаг тул хоёр газар давхар бүртгэх шаардлагатай байв.

Баримтууд нь ТУСДАА хэвээр үлдэнэ (шатахуун савны хөдөлгөөн, бараа
нөөцийн хөдөлгөөн үүсгэдэг, нягтлан бодох бүртгэлийн заалт нь өөр), гэвч
хоёулаа **нэг транзакцад** бүртгэгдэж бүртгэгдэнэ: аль нэг нь унавал
бүгд буцна, хагас бүртгэгдсэн баримт үлдэхгүй.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_permission
from app.enums import DocStatus
from app.models.fuel import Fuel, Tank
from app.models.partner import Supplier
from app.models.procurement import FuelReceipt, Purchase, PurchaseItem
from app.models.product import Product
from app.models.user import User
from app.money import q2, q3, q6
from app.schemas.procurement import ReceiveIn, ReceiveOut
from app.services import receipt_service
from app.services.audit_service import audit

ZERO = Decimal("0")

router = APIRouter(prefix="/api", tags=["procurement"])


def _client_ip(request: Request) -> str | None:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()[:64]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


@router.post("/procurement/receive", response_model=ReceiveOut, status_code=201)
async def receive(
    payload: ReceiveIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("purchases.manage", "receipts.create")),
) -> ReceiveOut:
    """Шатахуун ба барааг нэг дор орлогод авч, шууд бүртгэнэ."""
    if not payload.fuels and not payload.items:
        raise HTTPException(status_code=422, detail="Орлогод авах зүйл сонгоогүй байна")

    supplier = await db.scalar(select(Supplier).where(Supplier.id == payload.supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")

    when = payload.receipt_date or date.today()
    invoice = (payload.invoice_no or "").strip() or None
    note = (payload.note or "").strip() or None

    fuel_ids: list[uuid.UUID] = []
    fuel_total: Decimal = ZERO

    # --- Шатахуун: сав тус бүрд нэг таталтын баримт ---
    for line in payload.fuels:
        tank = await db.scalar(select(Tank).where(Tank.id == line.tank_id))
        if tank is None:
            raise HTTPException(status_code=404, detail="Сав олдсонгүй")

        fuel_id = line.fuel_id or tank.fuel_id
        fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
        if fuel is None:
            raise HTTPException(status_code=404, detail="Түлш олдсонгүй")

        liters = q3(line.liters)
        capacity = q3(tank.capacity_l or ZERO)
        if capacity > ZERO and q3(Decimal(tank.current_l or ZERO) + liters) > capacity:
            raise HTTPException(
                status_code=422, detail=f"{tank.name}: савны багтаамжаас хэтэрч байна"
            )

        receipt = FuelReceipt(
            supplier_id=supplier.id,
            tank_id=tank.id,
            fuel_id=fuel.id,
            receipt_date=when,
            invoice_no=invoice,
            liters=liters,
            unit_cost=q6(line.unit_cost),
            freight_cost=q2(line.freight_cost),
            density=line.density,
            temperature_c=line.temperature_c,
            status=str(DocStatus.DRAFT),
            note=note,
        )
        db.add(receipt)
        await db.flush()
        await receipt_service.post_fuel_receipt(db, user, receipt)
        fuel_ids.append(receipt.id)
        fuel_total = q2(fuel_total + q2(receipt.total_gross))

    # --- Бараа: бүх мөрийг нэг худалдан авалтын баримтад ---
    purchase_id: uuid.UUID | None = None
    goods_total: Decimal = ZERO
    if payload.items:
        product_ids = {item.product_id for item in payload.items}
        products = {
            p.id: p
            for p in (await db.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
        }
        if len(products) != len(product_ids):
            raise HTTPException(status_code=404, detail="Бараа олдсонгүй")

        purchase = Purchase(
            supplier_id=supplier.id,
            branch_id=payload.branch_id,
            purchase_date=when,
            invoice_no=invoice,
            status=str(DocStatus.DRAFT),
            note=note,
        )
        purchase.items = [
            PurchaseItem(
                product_id=item.product_id,
                qty=q3(item.qty),
                unit_cost=q6(item.unit_cost),
                amount=q2(q3(item.qty) * q6(item.unit_cost)),
            )
            for item in payload.items
        ]
        db.add(purchase)
        await db.flush()
        await receipt_service.post_purchase(db, user, purchase)
        purchase_id = purchase.id
        goods_total = q2(purchase.total_gross)

    await audit(
        db,
        user_id=user.id,
        action="procurement.receive",
        entity_type="supplier",
        entity_id=supplier.id,
        after={
            "date": when.isoformat(),
            "invoice_no": invoice,
            "fuel_receipts": len(fuel_ids),
            "purchase_items": len(payload.items),
            "total_gross": str(q2(fuel_total + goods_total)),
        },
        ip=_client_ip(request),
    )

    return ReceiveOut(
        fuel_receipt_ids=fuel_ids,
        purchase_id=purchase_id,
        fuel_total=fuel_total,
        goods_total=goods_total,
        total_gross=q2(fuel_total + goods_total),
    )
