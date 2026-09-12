"""Түлшний ачилт ба салбарын тооцооны схемүүд."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import SettlementEntryType, ShipmentOutflowKind, ShipmentStatus

ZERO = Decimal("0.00")

#: Ачилтын төлвийн монгол нэр.
SHIPMENT_STATUS_NAMES_MN: dict[str, str] = {
    ShipmentStatus.DRAFT: "Ноорог",
    ShipmentStatus.POSTED: "Түгээлтэд",
    ShipmentStatus.CLOSED: "Хаагдсан",
}

OUTFLOW_KIND_NAMES_MN: dict[str, str] = {
    ShipmentOutflowKind.SALE: "Шууд борлуулалт",
    ShipmentOutflowKind.LOSS: "Хорогдол",
}

SETTLEMENT_TYPE_NAMES_MN: dict[str, str] = {
    SettlementEntryType.CHARGE: "Түлшний өр",
    SettlementEntryType.PAYMENT: "Төлбөр",
}


# --------------------------------------------------------------------------- #
# Ачилт — оролт
# --------------------------------------------------------------------------- #
class FuelAllocationIn(BaseModel):
    """Түлшний мөрийн хуваарилалт: аль саванд хэдэн литр буулгах вэ."""

    model_config = ConfigDict(extra="forbid")

    tank_id: uuid.UUID
    liters: Decimal = Field(gt=0)


class GoodsAllocationIn(BaseModel):
    """Барааны мөрийн хуваарилалт: аль салбарт хэдэн ширхэг буулгах вэ."""

    model_config = ConfigDict(extra="forbid")

    branch_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class ShipmentItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fuel_id: uuid.UUID
    #: Мөрийн нийлүүлэгч; хоосон бол ачилтын үндсэн нийлүүлэгч.
    supplier_id: uuid.UUID | None = None
    liters: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    #: Салбар бүрийн саванд буулгах төлөвлөгөө (Σ ≤ liters). Бүртгэхэд
    #: автоматаар буулгагдана; үлдэгдлийг дараа нь гараар.
    allocations: list[FuelAllocationIn] = Field(default_factory=list)


class ShipmentGoodsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    allocations: list[GoodsAllocationIn] = Field(default_factory=list)


class FuelShipmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Үндсэн нийлүүлэгч — тээврийн зардал болон нийлүүлэгч заагаагүй мөрүүд
    #: түүний өглөгт бичигдэнэ.
    supplier_id: uuid.UUID
    vehicle_no: str = Field(min_length=1, max_length=32)
    driver_name: str | None = Field(default=None, max_length=64)
    shipment_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    freight_cost: Decimal = Field(default=ZERO, ge=0)
    note: str | None = None
    items: list[ShipmentItemIn] = Field(default_factory=list)
    goods: list[ShipmentGoodsIn] = Field(default_factory=list)


class FuelShipmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = None
    vehicle_no: str | None = Field(default=None, min_length=1, max_length=32)
    driver_name: str | None = Field(default=None, max_length=64)
    shipment_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    freight_cost: Decimal | None = Field(default=None, ge=0)
    note: str | None = None
    #: Өгвөл мөрүүдийг (хуваарилалттай нь) бүхэлд нь сольж бичнэ.
    items: list[ShipmentItemIn] | None = None
    goods: list[ShipmentGoodsIn] | None = None


class ShipmentDeliverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tank_id: uuid.UUID
    liters: Decimal = Field(gt=0)
    receipt_date: date | None = None
    note: str | None = None


class ShipmentDeliverManyIn(BaseModel):
    """Нэг зогсолтоор олон саванд буулгах — салбар бүрийн саванд өөр хэмжээгээр."""

    model_config = ConfigDict(extra="forbid")

    allocations: list[FuelAllocationIn] = Field(min_length=1)
    receipt_date: date | None = None
    note: str | None = None


class GoodsDeliverLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class ShipmentDeliverGoodsIn(BaseModel):
    """Машинаас нэг салбарт бараа буулгах."""

    model_config = ConfigDict(extra="forbid")

    branch_id: uuid.UUID
    lines: list[GoodsDeliverLineIn] = Field(min_length=1)
    receipt_date: date | None = None
    note: str | None = None


class ShipmentOutflowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ShipmentOutflowKind = ShipmentOutflowKind.SALE
    fuel_id: uuid.UUID
    liters: Decimal = Field(gt=0)
    #: НӨАТ-тай нэгж үнэ (борлуулалтад заавал).
    unit_price: Decimal = Field(default=ZERO, ge=0)
    received_to: str = "bank"
    bank_account_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    outflow_date: date | None = None
    customer_name: str | None = Field(default=None, max_length=128)
    note: str | None = None


# --------------------------------------------------------------------------- #
# Ачилт — гаралт
# --------------------------------------------------------------------------- #
class FuelAllocationOut(BaseModel):
    tank_id: uuid.UUID
    tank_name: str | None = None
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    liters: Decimal = ZERO


class GoodsAllocationOut(BaseModel):
    branch_id: uuid.UUID
    branch_name: str | None = None
    qty: Decimal = ZERO


class ShipmentItemOut(BaseModel):
    id: uuid.UUID
    fuel_id: uuid.UUID
    fuel_name: str | None = None
    fuel_code: str | None = None
    #: Мөрийн жинхэнэ нийлүүлэгч (хоосон байсан бол үндсэн нийлүүлэгч).
    supplier_id: uuid.UUID | None = None
    supplier_name: str | None = None
    liters: Decimal = ZERO
    unit_cost: Decimal = ZERO
    amount: Decimal = ZERO
    landed_unit_cost: Decimal = ZERO
    #: Түгээгдсэн/зарагдсан/хорогдсон/үлдсэн литр (дэлгэрэнгүйд).
    delivered_l: Decimal = ZERO
    outflow_l: Decimal = ZERO
    remaining_l: Decimal = ZERO
    #: Ноорог дээрх хуваарилалтын төлөвлөгөө.
    allocations: list[FuelAllocationOut] = []


class ShipmentGoodsOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    product_sku: str | None = None
    unit: str | None = None
    supplier_id: uuid.UUID | None = None
    supplier_name: str | None = None
    qty: Decimal = ZERO
    unit_cost: Decimal = ZERO
    amount: Decimal = ZERO
    landed_unit_cost: Decimal = ZERO
    delivered_qty: Decimal = ZERO
    remaining_qty: Decimal = ZERO
    allocations: list[GoodsAllocationOut] = []


class ShipmentSupplierOut(BaseModel):
    """Нийлүүлэгч тус бүрийн өглөг — ачилт олон нийлүүлэгчтэй."""

    supplier_id: uuid.UUID
    supplier_name: str | None = None
    #: Үндсэн нийлүүлэгч эсэх (тээврийн зардал түүнд).
    is_main: bool = False
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total_gross: Decimal = ZERO
    ap_invoice_id: uuid.UUID | None = None
    amount_paid: Decimal = ZERO
    invoice_status: str | None = None


class ShipmentDeliveryRow(BaseModel):
    id: uuid.UUID
    number: int | None = None
    receipt_date: date
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    tank_id: uuid.UUID
    tank_name: str | None = None
    fuel_name: str | None = None
    fuel_code: str | None = None
    liters: Decimal = ZERO
    unit_cost: Decimal = ZERO
    subtotal: Decimal = ZERO


class ShipmentGoodsDeliveryRow(BaseModel):
    """Ачилтаас салбарт буусан бараа — худалдан авалтын баримтын нэг мөр."""

    id: uuid.UUID
    purchase_id: uuid.UUID
    number: int | None = None
    receipt_date: date
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    product_id: uuid.UUID
    product_name: str | None = None
    unit: str | None = None
    qty: Decimal = ZERO
    unit_cost: Decimal = ZERO
    amount: Decimal = ZERO


class ShipmentOutflowOut(BaseModel):
    id: uuid.UUID
    kind: str
    kind_name: str | None = None
    fuel_id: uuid.UUID
    fuel_name: str | None = None
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    outflow_date: date
    liters: Decimal = ZERO
    unit_price: Decimal = ZERO
    amount: Decimal = ZERO
    cost_amount: Decimal = ZERO
    received_to: str = "bank"
    bank_account_id: uuid.UUID | None = None
    customer_name: str | None = None
    note: str | None = None


class FuelShipmentOut(BaseModel):
    id: uuid.UUID
    number: int | None = None
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    vehicle_no: str
    driver_name: str | None = None
    shipment_date: date
    invoice_no: str | None = None
    freight_cost: Decimal = ZERO
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total_gross: Decimal = ZERO
    status: str
    status_name: str | None = None
    ap_invoice_id: uuid.UUID | None = None
    #: Бүх нийлүүлэгчид төлсөн нийт дүн ба нэгдсэн төлөв (paid/partial/open).
    amount_paid: Decimal = ZERO
    invoice_status: str | None = None
    posted_at: datetime | None = None
    closed_at: datetime | None = None
    note: str | None = None
    created_at: datetime | None = None
    items: list[ShipmentItemOut] = []
    goods: list[ShipmentGoodsOut] = []
    #: Нийлүүлэгч тус бүрийн өглөг (жагсаалт, дэлгэрэнгүйд).
    suppliers: list[ShipmentSupplierOut] = []
    supplier_count: int = 1
    #: Нийт үлдсэн литр / ширхэг (жагсаалтад товч харуулна).
    total_liters: Decimal = ZERO
    remaining_liters: Decimal = ZERO
    total_goods_qty: Decimal = ZERO
    remaining_goods_qty: Decimal = ZERO


class FuelShipmentDetailOut(FuelShipmentOut):
    deliveries: list[ShipmentDeliveryRow] = []
    goods_deliveries: list[ShipmentGoodsDeliveryRow] = []
    outflows: list[ShipmentOutflowOut] = []


class FuelShipmentListOut(BaseModel):
    items: list[FuelShipmentOut]
    total: int


# --------------------------------------------------------------------------- #
# Салбарын тооцоо
# --------------------------------------------------------------------------- #
class SettlementBalanceRow(BaseModel):
    branch_id: uuid.UUID
    branch_name: str
    branch_code: str
    charged: Decimal = ZERO
    paid: Decimal = ZERO
    balance: Decimal = ZERO


class SettlementEntryOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    branch_name: str | None = None
    entry_type: str
    entry_type_name: str | None = None
    entry_date: date
    amount: Decimal = ZERO
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    #: Өрийн мөрийн эх баримтын тайлбар (ачилт, литр).
    paid_from: str | None = None
    to_bank_account_id: uuid.UUID | None = None
    to_bank_account_name: str | None = None
    note: str | None = None
    created_at: datetime | None = None


class SettlementEntryListOut(BaseModel):
    items: list[SettlementEntryOut]
    total: int


class SettlementPaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    entry_date: date | None = None
    paid_from: str = "cash"
    from_bank_account_id: uuid.UUID | None = None
    to_bank_account_id: uuid.UUID
    note: str | None = None
