"""Харилцагч, гэрээ, авлага, ваучер, урьдчилсан төлбөрт картын схемүүд (WP6).

Мөнгөний бүх талбар ``Decimal`` — JSON руу string-ээр гарна.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ContractStatus, CustomerType, PaymentMethod

ZERO = Decimal("0.00")


# --------------------------------------------------------------------------- #
# Харилцагч
# --------------------------------------------------------------------------- #
class ContractBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_no: str
    credit_limit: Decimal = ZERO
    balance: Decimal = ZERO
    credit_available: Decimal = ZERO
    price_discount_per_l: Decimal = ZERO
    status: str
    status_name: str = ""


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_name: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    register_no: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    phone2: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    province: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    credit_limit: Decimal = Field(default=ZERO, ge=0)
    type: CustomerType = CustomerType.B2B
    is_active: bool = True


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_name: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    register_no: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    phone2: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=128)
    province: str | None = Field(default=None, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    credit_limit: Decimal | None = Field(default=None, ge=0)
    type: CustomerType | None = None
    is_active: bool | None = None


class CustomerOut(BaseModel):
    id: uuid.UUID
    last_name: str | None = None
    name: str
    #: "Овог Нэр" хэлбэрийн дэлгэцийн нэр.
    full_name: str = ""
    register_no: str | None = None
    phone: str | None = None
    phone2: str | None = None
    email: str | None = None
    province: str | None = None
    district: str | None = None
    credit_limit: Decimal = ZERO
    #: Сканнердсан гэрээ хавсаргасан эсэх.
    has_contract_file: bool = False
    type: str
    type_name: str = ""
    is_active: bool = True
    contracts: list[ContractBrief] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomerListOut(BaseModel):
    items: list[CustomerOut]
    total: int


# --------------------------------------------------------------------------- #
# Гэрээ
# --------------------------------------------------------------------------- #
class ContractCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID
    contract_no: str = Field(min_length=1, max_length=32)
    credit_limit: Decimal = Field(default=ZERO, ge=0)
    price_discount_per_l: Decimal = Field(default=ZERO, ge=0)
    billing_day: int = Field(default=1, ge=1, le=28)
    status: ContractStatus = ContractStatus.ACTIVE


class ContractUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_no: str | None = Field(default=None, min_length=1, max_length=32)
    credit_limit: Decimal | None = Field(default=None, ge=0)
    price_discount_per_l: Decimal | None = Field(default=None, ge=0)
    billing_day: int | None = Field(default=None, ge=1, le=28)
    status: ContractStatus | None = None


class ContractOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    contract_no: str
    credit_limit: Decimal = ZERO
    balance: Decimal = ZERO
    credit_available: Decimal = ZERO
    price_discount_per_l: Decimal = ZERO
    billing_day: int = 1
    status: str
    status_name: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContractListOut(BaseModel):
    items: list[ContractOut]
    total: int


# --------------------------------------------------------------------------- #
# Тооцоо нийлэх акт
# --------------------------------------------------------------------------- #
class StatementRow(BaseModel):
    date: datetime | None = None
    kind: str
    kind_name: str = ""
    ref: str | None = None
    description: str = ""
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    balance: Decimal = ZERO


class StatementOut(BaseModel):
    contract: ContractOut
    date_from: date | None = None
    date_to: date | None = None
    opening_balance: Decimal = ZERO
    sales_total: Decimal = ZERO
    payments_total: Decimal = ZERO
    closing_balance: Decimal = ZERO
    rows: list[StatementRow] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Авлагын нэхэмжлэх / төлбөр
# --------------------------------------------------------------------------- #
class InvoiceGenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date


class ArInvoiceOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    contract_id: uuid.UUID
    contract_no: str | None = None
    invoice_no: str
    period_start: date
    period_end: date
    issued_at: datetime | None = None
    amount: Decimal = ZERO
    amount_paid: Decimal = ZERO
    amount_due: Decimal = ZERO
    status: str
    status_name: str = ""
    lines: list[dict[str, Any]] = Field(default_factory=list)


class ArInvoiceListOut(BaseModel):
    items: list[ArInvoiceOut]
    total: int


class ArPaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    received_to: str = Field(default="bank", description="'bank' эсвэл 'cash'")
    payment_date: date | None = None
    ar_invoice_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class ArPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ar_invoice_id: uuid.UUID | None = None
    customer_id: uuid.UUID
    contract_id: uuid.UUID
    amount: Decimal
    received_to: str
    payment_date: date
    note: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None


class ArPaymentResultOut(BaseModel):
    payment: ArPaymentOut
    contract: ContractOut
    invoice: ArInvoiceOut | None = None
    journal_entry_id: uuid.UUID | None = None


# --------------------------------------------------------------------------- #
# Ваучер
# --------------------------------------------------------------------------- #
class VoucherOut(BaseModel):
    id: uuid.UUID
    code: str
    face_value: Decimal
    status: str
    status_name: str = ""
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    sold_sale_id: uuid.UUID | None = None
    redeemed_sale_id: uuid.UUID | None = None
    sold_at: datetime | None = None
    redeemed_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


class VoucherListOut(BaseModel):
    items: list[VoucherOut]
    total: int


class VoucherIssueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=1, le=500)
    face_value: Decimal = Field(gt=0)
    expires_at: datetime | None = None
    customer_id: uuid.UUID | None = None


class VoucherSellIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tender_method: PaymentMethod = PaymentMethod.CASH
    customer_id: uuid.UUID | None = None


class VoucherVoidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=255)


class VoucherValidateOut(BaseModel):
    valid: bool
    message: str
    voucher: VoucherOut | None = None


# --------------------------------------------------------------------------- #
# Урьдчилсан төлбөрт карт
# --------------------------------------------------------------------------- #
class PrepaidCardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_no: str = Field(min_length=1, max_length=32)
    holder_name: str | None = Field(default=None, max_length=128)
    customer_id: uuid.UUID | None = None
    initial_amount: Decimal = Field(default=ZERO, ge=0)
    tender_method: PaymentMethod = PaymentMethod.CASH


class PrepaidCardOut(BaseModel):
    id: uuid.UUID
    card_no: str
    holder_name: str | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    balance: Decimal = ZERO
    status: str
    status_name: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PrepaidCardListOut(BaseModel):
    items: list[PrepaidCardOut]
    total: int


class CardTopupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    tender_method: PaymentMethod = PaymentMethod.CASH


class CardBlockIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=255)


class CardTxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    tx_type: str
    tx_type_name: str = ""
    amount: Decimal
    balance_after: Decimal
    sale_id: uuid.UUID | None = None
    created_at: datetime | None = None


class CardTxListOut(BaseModel):
    items: list[CardTxOut]
    total: int


class CardOperationOut(BaseModel):
    card: PrepaidCardOut
    transaction: CardTxOut | None = None
    journal_entry_id: uuid.UUID | None = None
