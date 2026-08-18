"""Нийлүүлэгч, шатахууны таталт, барааны худалдан авалтын схемүүд (WP7).

Нийлүүлэгчийн баримт **НӨАТ-гүй** дүнгээр ирж, НӨАТ нь дээрээс нэмэгддэг
(CONTRACTS.md §2).  Тиймээс ``subtotal`` нь цэвэр дүн, ``total_gross`` нь
өглөгт бүртгэгдэх нийт дүн.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import DocStatus, InvoiceStatus

ZERO = Decimal("0.00")
ZERO_Q = Decimal("0.000")
ZERO_C = Decimal("0.000000")

#: Баримтын төлвийн монгол нэр.
DOC_STATUS_NAMES_MN: dict[str, str] = {
    DocStatus.DRAFT: "Ноорог",
    DocStatus.POSTED: "Бүртгэсэн",
}

#: Нэхэмжлэхийн төлвийн монгол нэр.
INVOICE_STATUS_NAMES_MN: dict[str, str] = {
    InvoiceStatus.OPEN: "Нээлттэй",
    InvoiceStatus.PARTIAL: "Хэсэгчлэн төлсөн",
    InvoiceStatus.PAID: "Төлсөн",
}


# --------------------------------------------------------------------------- #
# Нийлүүлэгч
# --------------------------------------------------------------------------- #
class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    register_no: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    bank_account: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    register_no: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    bank_account: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class SupplierOut(BaseModel):
    id: uuid.UUID
    name: str
    register_no: str | None = None
    phone: str | None = None
    bank_account: str | None = None
    address: str | None = None
    is_active: bool = True
    balance: Decimal = ZERO
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierListOut(BaseModel):
    items: list[SupplierOut]
    total: int


class ApInvoiceRow(BaseModel):
    id: uuid.UUID
    invoice_no: str
    invoice_date: date
    due_date: date | None = None
    source_type: str
    source_id: uuid.UUID
    amount_gross: Decimal = ZERO
    amount_paid: Decimal = ZERO
    amount_due: Decimal = ZERO
    status: str
    status_name: str = ""
    is_overdue: bool = False
    created_at: datetime | None = None


class ApPaymentRow(BaseModel):
    id: uuid.UUID
    ap_invoice_id: uuid.UUID
    invoice_no: str | None = None
    amount: Decimal = ZERO
    paid_from: str = "bank"
    payment_date: date
    note: str | None = None
    created_at: datetime | None = None


class SupplierLedgerOut(BaseModel):
    supplier: SupplierOut
    invoices: list[ApInvoiceRow]
    payments: list[ApPaymentRow]
    invoiced_total: Decimal = ZERO
    paid_total: Decimal = ZERO
    balance: Decimal = ZERO


# --------------------------------------------------------------------------- #
# Шатахууны таталт
# --------------------------------------------------------------------------- #
class FuelReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID
    tank_id: uuid.UUID
    fuel_id: uuid.UUID | None = Field(default=None, description="Хоосон бол савны түлшийг авна")
    receipt_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    liters: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0, description="НӨАТ-гүй нэгж өртөг")
    freight_cost: Decimal = Field(default=ZERO, ge=0)
    density: Decimal | None = Field(default=None, ge=0)
    temperature_c: Decimal | None = None
    note: str | None = Field(default=None, max_length=500)


class FuelReceiptUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    fuel_id: uuid.UUID | None = None
    receipt_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    liters: Decimal | None = Field(default=None, gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    freight_cost: Decimal | None = Field(default=None, ge=0)
    density: Decimal | None = Field(default=None, ge=0)
    temperature_c: Decimal | None = None
    note: str | None = Field(default=None, max_length=500)


class FuelReceiptOut(BaseModel):
    id: uuid.UUID
    number: int | None = None
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    tank_id: uuid.UUID
    tank_name: str | None = None
    fuel_id: uuid.UUID
    fuel_name: str | None = None
    fuel_code: str | None = None
    receipt_date: date
    invoice_no: str | None = None
    liters: Decimal = ZERO_Q
    unit_cost: Decimal = ZERO_C
    freight_cost: Decimal = ZERO
    density: Decimal | None = None
    temperature_c: Decimal | None = None
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total_gross: Decimal = ZERO
    landed_unit_cost: Decimal = ZERO_C
    status: str
    status_name: str = ""
    posted_by: uuid.UUID | None = None
    posted_at: datetime | None = None
    ap_invoice_id: uuid.UUID | None = None
    note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FuelReceiptListOut(BaseModel):
    items: list[FuelReceiptOut]
    total: int


# --------------------------------------------------------------------------- #
# Барааны худалдан авалт
# --------------------------------------------------------------------------- #
class PurchaseItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0, description="НӨАТ-гүй нэгж өртөг")


class PurchaseItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku: str | None = None
    unit: str | None = None
    qty: Decimal = ZERO_Q
    unit_cost: Decimal = ZERO_C
    amount: Decimal = ZERO


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID
    #: Бараа аль салбарын нөөцөд орох вэ (хоосон бол үндсэн салбар).
    branch_id: uuid.UUID | None = None
    purchase_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    items: list[PurchaseItemIn] = Field(min_length=1)


class PurchaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = None
    purchase_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    items: list[PurchaseItemIn] | None = Field(default=None, min_length=1)


class PurchaseOut(BaseModel):
    id: uuid.UUID
    number: int | None = None
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    purchase_date: date
    invoice_no: str | None = None
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total_gross: Decimal = ZERO
    status: str
    status_name: str = ""
    posted_by: uuid.UUID | None = None
    posted_at: datetime | None = None
    ap_invoice_id: uuid.UUID | None = None
    note: str | None = None
    items: list[PurchaseItemOut] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PurchaseListOut(BaseModel):
    items: list[PurchaseOut]
    total: int


# --------------------------------------------------------------------------- #
# Нэгдсэн орлого — шатахуун + бараа нэг баримтаар
# --------------------------------------------------------------------------- #
class ReceiveFuelLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tank_id: uuid.UUID
    fuel_id: uuid.UUID | None = None
    liters: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0, description="НӨАТ-гүй нэгж өртөг")
    freight_cost: Decimal = Field(default=ZERO, ge=0)
    density: Decimal | None = Field(default=None, ge=0)
    temperature_c: Decimal | None = None


class ReceiveIn(BaseModel):
    """Нэг нийлүүлэгчээс нэг өдөр авсан шатахуун ба барааг цуг бүртгэнэ."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID
    receipt_date: date | None = None
    invoice_no: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)
    #: Бараа аль салбарын нөөцөд орох вэ.
    branch_id: uuid.UUID | None = None
    fuels: list[ReceiveFuelLine] = Field(default_factory=list)
    items: list[PurchaseItemIn] = Field(default_factory=list)


class ReceiveOut(BaseModel):
    fuel_receipt_ids: list[uuid.UUID] = Field(default_factory=list)
    purchase_id: uuid.UUID | None = None
    fuel_total: Decimal = ZERO
    goods_total: Decimal = ZERO
    total_gross: Decimal = ZERO
