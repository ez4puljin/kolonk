"""Борлуулалт, төлбөр, буцаалтын API схемүүд (WP6).

Мөнгө/литрийн бүх талбар ``Decimal`` — Pydantic v2 JSON руу **string**-ээр
гаргана. Хэрэглэгчид харагдах бүх текст монгол.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ItemType, PaymentMethod, RefundType, SaleType

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")


# --------------------------------------------------------------------------- #
# Оролт — борлуулалт
# --------------------------------------------------------------------------- #
class SaleItemIn(BaseModel):
    """Борлуулалтын нэг мөр.

    Түлшний мөрд ``authorization_id`` өгвөл насосны бодит заалт (Redis дэх
    ``auth:{id}``) үнэн эх сурвалж болно. Өгөөгүй бол гараар бүртгэсэн гэж үзнэ.
    """

    model_config = ConfigDict(extra="forbid")

    item_type: ItemType = ItemType.FUEL
    fuel_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    pump_id: uuid.UUID | None = None
    nozzle_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=0, description="Литр эсвэл ширхэг")
    unit_price: Decimal | None = Field(default=None, ge=0)
    #: Гараар бүртгэсэн түлшний мөрд кассын оруулсан яг мөнгөн дүн.
    #: Литр 3 оронтой тул `тоо × үнэ` нь бөөрөнхийлөлтөөр 1-2₮ зөрж болно —
    #: энэ талбар байвал (зөрүү нь 1 мл-ийн үнээс хэтрэхгүй бол) түүнийг барина.
    amount: Decimal | None = Field(default=None, ge=0)
    authorization_id: uuid.UUID | None = None


class PaymentIn(BaseModel):
    """Нэг төлбөрийн хэрэгсэл. Нэг борлуулалт олон хэрэгслээр төлөгдөж болно."""

    model_config = ConfigDict(extra="forbid")

    method: PaymentMethod = PaymentMethod.CASH
    amount: Decimal = Field(gt=0)
    contract_id: uuid.UUID | None = None
    received: Decimal | None = Field(default=None, ge=0, description="Бэлнээр авсан мөнгө")
    ref_no: str | None = Field(default=None, max_length=64)


class SaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_type: SaleType = SaleType.FUEL
    items: list[SaleItemIn] = Field(min_length=1)
    payments: list[PaymentIn] = Field(min_length=1)
    customer_id: uuid.UUID | None = None
    contract_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------- #
# Гаралт — борлуулалт
# --------------------------------------------------------------------------- #
class SaleItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    item_type: str
    fuel_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    pump_id: uuid.UUID | None = None
    nozzle_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    name_snapshot: str
    qty: Decimal
    unit_price: Decimal
    amount: Decimal
    unit_cost: Decimal = Decimal("0.000000")
    cogs_amount: Decimal = ZERO
    refunded_qty: Decimal = ZERO_L


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: str
    method_name: str = ""
    amount: Decimal
    contract_id: uuid.UUID | None = None
    received: Decimal | None = None
    change_given: Decimal | None = None
    ref_no: str | None = None


class EbarimtInfo(BaseModel):
    status: str
    status_name: str = ""
    receipt_id: str | None = None
    qr_data: str | None = None
    lottery_no: str | None = None
    sent_at: datetime | None = None


class SaleOut(BaseModel):
    id: uuid.UUID
    number: int
    shift_id: uuid.UUID
    shift_number: int | None = None
    cashier_id: uuid.UUID
    cashier_name: str | None = None
    sale_type: str
    status: str
    status_name: str = ""
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total: Decimal = ZERO
    cogs_total: Decimal = ZERO
    change_total: Decimal = ZERO
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    contract_id: uuid.UUID | None = None
    contract_no: str | None = None
    note: str | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    items: list[SaleItemOut] = Field(default_factory=list)
    payments: list[PaymentOut] = Field(default_factory=list)
    ebarimt: EbarimtInfo | None = None


class SaleRow(BaseModel):
    """Жагсаалтын хөнгөн мөр."""

    id: uuid.UUID
    number: int
    shift_id: uuid.UUID
    cashier_id: uuid.UUID
    cashier_name: str | None = None
    sale_type: str
    status: str
    status_name: str = ""
    total: Decimal = ZERO
    vat_amount: Decimal = ZERO
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    methods: list[str] = Field(default_factory=list)
    method_names: list[str] = Field(default_factory=list)
    items_count: int = 0
    completed_at: datetime | None = None
    created_at: datetime | None = None


class SaleListOut(BaseModel):
    items: list[SaleRow]
    total: int


# --------------------------------------------------------------------------- #
# Гаралт — 80мм баримт
# --------------------------------------------------------------------------- #
class ReceiptStation(BaseModel):
    name: str = ""
    address: str = ""
    phone: str = ""
    vat_payer_no: str = ""
    footer: str = ""
    printer_width_mm: int = 80
    currency_symbol: str = "₮"


class ReceiptItem(BaseModel):
    line_no: int
    name: str
    unit: str = "ш"
    qty: Decimal
    unit_price: Decimal
    amount: Decimal


class ReceiptPayment(BaseModel):
    method: str
    method_name: str
    amount: Decimal
    received: Decimal | None = None
    change: Decimal | None = None


class ReceiptEbarimt(BaseModel):
    status: str
    status_name: str = ""
    receipt_id: str | None = None
    qr_data: str | None = None
    lottery_no: str | None = None


class ReceiptOut(BaseModel):
    station: ReceiptStation
    sale_id: uuid.UUID
    number: int
    sold_at: datetime | None = None
    cashier_name: str | None = None
    shift_number: int | None = None
    customer_name: str | None = None
    contract_no: str | None = None
    note: str | None = None
    items: list[ReceiptItem] = Field(default_factory=list)
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total: Decimal = ZERO
    change_total: Decimal = ZERO
    payments: list[ReceiptPayment] = Field(default_factory=list)
    ebarimt: ReceiptEbarimt | None = None


class SaleCreatedOut(BaseModel):
    """``POST /api/sales``-ийн хариу — борлуулалт + хэвлэх баримт."""

    sale: SaleOut
    receipt: ReceiptOut


# --------------------------------------------------------------------------- #
# Буцаалт
# --------------------------------------------------------------------------- #
class RefundItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_item_id: uuid.UUID
    qty: Decimal = Field(gt=0)


class RefundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_id: uuid.UUID
    refund_type: RefundType = RefundType.FULL
    items: list[RefundItemIn] = Field(default_factory=list)
    amount: Decimal | None = Field(default=None, ge=0, description="Заавал биш — сервер тооцоолно")
    reason: str | None = Field(default=None, max_length=500)
    restock: bool = False
    refund_method: PaymentMethod | None = None


class RefundDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class RefundItemOut(BaseModel):
    id: uuid.UUID
    sale_item_id: uuid.UUID
    name: str = ""
    item_type: str = ""
    qty: Decimal
    amount: Decimal
    cogs_amount: Decimal = ZERO


class RefundOut(BaseModel):
    id: uuid.UUID
    sale_id: uuid.UUID
    sale_number: int | None = None
    refund_type: str
    amount: Decimal
    vat_amount: Decimal = ZERO
    cogs_amount: Decimal = ZERO
    reason: str | None = None
    restock: bool = False
    refund_method: str
    refund_method_name: str = ""
    status: str
    status_name: str = ""
    requested_by: uuid.UUID | None = None
    requested_by_name: str | None = None
    decided_by: uuid.UUID | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    shift_id: uuid.UUID | None = None
    items: list[RefundItemOut] = Field(default_factory=list)
    created_at: datetime | None = None


class RefundListOut(BaseModel):
    items: list[RefundOut]
    total: int


class RefundResultOut(BaseModel):
    refund: RefundOut
    sale_status: str | None = None
    journal_entry_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Туслах
# --------------------------------------------------------------------------- #
class OkOut(BaseModel):
    ok: bool = True
    message: str | None = None
    data: dict[str, Any] | None = None
