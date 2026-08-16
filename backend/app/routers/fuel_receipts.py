"""Шатахууны таталтын баримт (WP7).

Урсгал: ноорог үүсгэх → шалгаж засах → **бүртгэх**.  Бүртгэсэн үед сав дүүрч,
нийлүүлэгчийн өглөг нээгдэж, НББ-ийн бичилт хийгдэнэ (``receipt_service``).
Бүртгэсэн баримт хэзээ ч засагдахгүй, устгагдахгүй.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import require_permission
from app.enums import DocStatus
from app.models.fuel import Fuel, Tank
from app.models.partner import Supplier
from app.models.procurement import FuelReceipt
from app.models.user import User
from app.money import q2, q3, q6
from app.schemas.procurement import (
    DOC_STATUS_NAMES_MN,
    FuelReceiptCreate,
    FuelReceiptListOut,
    FuelReceiptOut,
    FuelReceiptUpdate,
)
from app.services import receipt_service
from app.services.audit_service import audit

router = APIRouter(prefix="/api", tags=["fuel_receipts"])

ZERO = Decimal("0")

VAT_RATE: Decimal = settings.vat_rate


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _number(receipt: FuelReceipt) -> int | None:
    """Дарааллаас олгогдсон дугаар (ачаагдаагүй байвал ``None``)."""
    try:
        return receipt.number
    except Exception:  # noqa: BLE001
        return None


async def _ensure_number(db: AsyncSession, receipt: FuelReceipt) -> None:
    """Шинээр үүсгэсэн баримтын дугаарыг DB-ээс баталгаатай уншина."""
    if _number(receipt) is None:
        try:
            await db.refresh(receipt, ["number"])
        except Exception:  # noqa: BLE001
            pass


def _to_out(
    receipt: FuelReceipt,
    supplier_name: str | None = None,
    tank_name: str | None = None,
    fuel_name: str | None = None,
    fuel_code: str | None = None,
) -> FuelReceiptOut:
    return FuelReceiptOut(
        id=receipt.id,
        number=_number(receipt),
        supplier_id=receipt.supplier_id,
        supplier_name=supplier_name,
        tank_id=receipt.tank_id,
        tank_name=tank_name,
        fuel_id=receipt.fuel_id,
        fuel_name=fuel_name,
        fuel_code=fuel_code,
        receipt_date=receipt.receipt_date,
        invoice_no=receipt.invoice_no,
        liters=q3(receipt.liters or ZERO),
        unit_cost=Decimal(receipt.unit_cost or ZERO),
        freight_cost=q2(receipt.freight_cost or ZERO),
        density=receipt.density,
        temperature_c=receipt.temperature_c,
        subtotal=q2(receipt.subtotal or ZERO),
        vat_amount=q2(receipt.vat_amount or ZERO),
        total_gross=q2(receipt.total_gross or ZERO),
        landed_unit_cost=Decimal(receipt.landed_unit_cost or ZERO),
        status=receipt.status,
        status_name=DOC_STATUS_NAMES_MN.get(str(receipt.status), str(receipt.status)),
        posted_by=receipt.posted_by,
        posted_at=receipt.posted_at,
        ap_invoice_id=receipt.ap_invoice_id,
        note=receipt.note,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
    )


def _row_to_out(row: Row) -> FuelReceiptOut:
    receipt, supplier_name, tank_name, fuel_name, fuel_code = row
    return _to_out(receipt, supplier_name, tank_name, fuel_name, fuel_code)


def _snapshot(receipt: FuelReceipt) -> dict:
    return {
        "supplier_id": str(receipt.supplier_id),
        "tank_id": str(receipt.tank_id),
        "fuel_id": str(receipt.fuel_id),
        "receipt_date": receipt.receipt_date.isoformat(),
        "invoice_no": receipt.invoice_no,
        "liters": str(receipt.liters),
        "unit_cost": str(receipt.unit_cost),
        "freight_cost": str(receipt.freight_cost),
        "subtotal": str(receipt.subtotal),
        "vat_amount": str(receipt.vat_amount),
        "total_gross": str(receipt.total_gross),
        "status": str(receipt.status),
    }


def _recalculate(receipt: FuelReceipt) -> None:
    """Ноорог дээр ч дүнг тооцоолж хадгална — кассч/менежер бүртгэхээсээ өмнө
    нийт дүнгээ хараад баримттай тулгах боломжтой байх ёстой."""
    liters = q3(receipt.liters or ZERO)
    unit_cost = q6(receipt.unit_cost or ZERO)
    freight = q2(receipt.freight_cost or ZERO)

    subtotal = q2(q2(liters * unit_cost) + freight)
    receipt.subtotal = subtotal
    receipt.vat_amount = q2(subtotal * VAT_RATE)
    receipt.total_gross = q2(subtotal + receipt.vat_amount)
    receipt.landed_unit_cost = q6(subtotal / liters) if liters > 0 else Decimal("0")


def _base_query():
    return (
        select(FuelReceipt, Supplier.name, Tank.name, Fuel.name_mn, Fuel.code)
        .join(Supplier, Supplier.id == FuelReceipt.supplier_id)
        .join(Tank, Tank.id == FuelReceipt.tank_id)
        .join(Fuel, Fuel.id == FuelReceipt.fuel_id)
    )


async def _load_row(db: AsyncSession, receipt_id: uuid.UUID) -> Row:
    row = (await db.execute(_base_query().where(FuelReceipt.id == receipt_id))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Таталтын баримт олдсонгүй")
    return row


async def _resolve_targets(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    tank_id: uuid.UUID,
    fuel_id: uuid.UUID | None,
) -> tuple[Supplier, Tank, Fuel]:
    supplier = await db.scalar(select(Supplier).where(Supplier.id == supplier_id))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Нийлүүлэгч олдсонгүй")

    tank = await db.scalar(select(Tank).where(Tank.id == tank_id))
    if tank is None:
        raise HTTPException(status_code=404, detail="Сав олдсонгүй")

    if fuel_id is not None and fuel_id != tank.fuel_id:
        raise HTTPException(status_code=422, detail="Савны түлш баримтын түлштэй таарахгүй байна")

    fuel = await db.scalar(select(Fuel).where(Fuel.id == tank.fuel_id))
    if fuel is None:
        raise HTTPException(status_code=404, detail="Түлш олдсонгүй")
    return supplier, tank, fuel


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
@router.get("/fuel-receipts", response_model=FuelReceiptListOut)
async def list_receipts(
    status: DocStatus | None = Query(default=None),
    supplier_id: uuid.UUID | None = Query(default=None),
    tank_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("receipts.create")),
) -> FuelReceiptListOut:
    conditions = []
    if status is not None:
        conditions.append(FuelReceipt.status == str(status))
    if supplier_id is not None:
        conditions.append(FuelReceipt.supplier_id == supplier_id)
    if tank_id is not None:
        conditions.append(FuelReceipt.tank_id == tank_id)
    if date_from is not None:
        conditions.append(FuelReceipt.receipt_date >= date_from)
    if date_to is not None:
        conditions.append(FuelReceipt.receipt_date <= date_to)

    total = await db.scalar(select(func.count()).select_from(FuelReceipt).where(*conditions)) or 0
    rows = (
        await db.execute(
            _base_query()
            .where(*conditions)
            .order_by(FuelReceipt.receipt_date.desc(), FuelReceipt.number.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return FuelReceiptListOut(items=[_row_to_out(r) for r in rows], total=int(total))


@router.get("/fuel-receipts/{receipt_id}", response_model=FuelReceiptOut)
async def get_receipt(
    receipt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("receipts.create")),
) -> FuelReceiptOut:
    return _row_to_out(await _load_row(db, receipt_id))


# --------------------------------------------------------------------------- #
# Бичих
# --------------------------------------------------------------------------- #
@router.post("/fuel-receipts", response_model=FuelReceiptOut, status_code=201)
async def create_receipt(
    payload: FuelReceiptCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("receipts.create")),
) -> FuelReceiptOut:
    supplier, tank, fuel = await _resolve_targets(
        db, payload.supplier_id, payload.tank_id, payload.fuel_id
    )

    liters = q3(payload.liters)
    if liters <= 0:
        raise HTTPException(status_code=422, detail="Татсан литр 0-ээс их байх ёстой")

    capacity = q3(tank.capacity_l or ZERO)
    if capacity > 0 and q3(Decimal(tank.current_l or ZERO) + liters) > capacity:
        raise HTTPException(status_code=422, detail="Савны багтаамжаас хэтэрч байна")

    receipt = FuelReceipt(
        supplier_id=supplier.id,
        tank_id=tank.id,
        fuel_id=fuel.id,
        receipt_date=payload.receipt_date or date.today(),
        invoice_no=(payload.invoice_no or "").strip() or None,
        liters=liters,
        unit_cost=q6(payload.unit_cost),
        freight_cost=q2(payload.freight_cost),
        density=payload.density,
        temperature_c=payload.temperature_c,
        status=str(DocStatus.DRAFT),
        note=(payload.note or "").strip() or None,
    )
    _recalculate(receipt)
    db.add(receipt)
    await db.flush()
    await _ensure_number(db, receipt)

    await audit(
        db,
        user_id=user.id,
        action="fuel_receipt.create",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        after=_snapshot(receipt),
        ip=_client_ip(request),
    )
    return _to_out(receipt, supplier.name, tank.name, fuel.name_mn, fuel.code)


@router.patch("/fuel-receipts/{receipt_id}", response_model=FuelReceiptOut)
async def update_receipt(
    receipt_id: uuid.UUID,
    payload: FuelReceiptUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("receipts.create")),
) -> FuelReceiptOut:
    row = await _load_row(db, receipt_id)
    receipt: FuelReceipt = row[0]
    if str(receipt.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Бүртгэсэн баримтыг засах боломжгүй")

    changes = payload.model_dump(exclude_unset=True)
    before = _snapshot(receipt)

    supplier_id = changes.get("supplier_id") or receipt.supplier_id
    tank_id = changes.get("tank_id") or receipt.tank_id
    fuel_id = changes.get("fuel_id")
    supplier, tank, fuel = await _resolve_targets(db, supplier_id, tank_id, fuel_id)

    receipt.supplier_id = supplier.id
    receipt.tank_id = tank.id
    receipt.fuel_id = fuel.id

    if changes.get("receipt_date") is not None:
        receipt.receipt_date = changes["receipt_date"]
    if "invoice_no" in changes:
        receipt.invoice_no = (changes["invoice_no"] or "").strip() or None
    if changes.get("liters") is not None:
        receipt.liters = q3(changes["liters"])
    if changes.get("unit_cost") is not None:
        receipt.unit_cost = q6(changes["unit_cost"])
    if changes.get("freight_cost") is not None:
        receipt.freight_cost = q2(changes["freight_cost"])
    if "density" in changes:
        receipt.density = changes["density"]
    if "temperature_c" in changes:
        receipt.temperature_c = changes["temperature_c"]
    if "note" in changes:
        receipt.note = (changes["note"] or "").strip() or None

    liters = q3(receipt.liters or ZERO)
    if liters <= 0:
        raise HTTPException(status_code=422, detail="Татсан литр 0-ээс их байх ёстой")

    capacity = q3(tank.capacity_l or ZERO)
    if capacity > 0 and q3(Decimal(tank.current_l or ZERO) + liters) > capacity:
        raise HTTPException(status_code=422, detail="Савны багтаамжаас хэтэрч байна")

    _recalculate(receipt)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel_receipt.update",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        before=before,
        after=_snapshot(receipt),
        ip=_client_ip(request),
    )
    return _to_out(receipt, supplier.name, tank.name, fuel.name_mn, fuel.code)


@router.post("/fuel-receipts/{receipt_id}/post", response_model=FuelReceiptOut)
async def post_receipt(
    receipt_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("receipts.create")),
) -> FuelReceiptOut:
    """Ноорог баримтыг бүртгэнэ: сав + өглөг + журналын бичилт."""
    row = await _load_row(db, receipt_id)
    receipt: FuelReceipt = row[0]

    await receipt_service.post_fuel_receipt(db, user, receipt)

    await audit(
        db,
        user_id=user.id,
        action="fuel_receipt.post_request",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        after={"status": str(receipt.status)},
        ip=_client_ip(request),
    )
    return _to_out(receipt, row[1], row[2], row[3], row[4])


@router.delete("/fuel-receipts/{receipt_id}", status_code=204, response_model=None)
async def delete_receipt(
    receipt_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("receipts.create")),
) -> None:
    """Зөвхөн ноорог устгагдана — бүртгэсэн баримт НББ-д бичигдсэн байна."""
    row = await _load_row(db, receipt_id)
    receipt: FuelReceipt = row[0]
    if str(receipt.status) != str(DocStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Бүртгэсэн баримтыг устгах боломжгүй")

    before = _snapshot(receipt)
    await db.delete(receipt)
    await db.flush()

    await audit(
        db,
        user_id=user.id,
        action="fuel_receipt.delete",
        entity_type="fuel_receipt",
        entity_id=receipt_id,
        before=before,
        ip=_client_ip(request),
    )
