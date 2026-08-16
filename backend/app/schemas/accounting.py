"""НББ модулийн Pydantic v2 схемүүд.

Мөнгө бүх талбарт ``Decimal`` — FastAPI JSON руу string болгож гаргана.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Данс
# --------------------------------------------------------------------------- #
class AccountOut(BaseModel):
    model_config = ORM

    id: uuid.UUID
    code: str
    name_mn: str
    account_type: str
    is_postable: bool
    parent_code: str | None = None
    sort_order: int


# --------------------------------------------------------------------------- #
# Журнал
# --------------------------------------------------------------------------- #
class JournalLineOut(BaseModel):
    model_config = ORM

    id: uuid.UUID
    line_no: int
    account_code: str
    debit: Decimal
    credit: Decimal
    memo: str | None = None
    dim_fuel_id: uuid.UUID | None = None
    dim_tank_id: uuid.UUID | None = None
    dim_customer_id: uuid.UUID | None = None
    dim_supplier_id: uuid.UUID | None = None


class JournalEntryOut(BaseModel):
    model_config = ORM

    id: uuid.UUID
    entry_no: int
    entry_date: date
    description: str
    source_type: str
    source_id: uuid.UUID
    event_type: str
    posted_by: uuid.UUID | None = None
    created_at: datetime
    lines: list[JournalLineOut] = Field(default_factory=list)


class JournalEntryList(BaseModel):
    items: list[JournalEntryOut]
    total: int


# --------------------------------------------------------------------------- #
# Гар бичилт
# --------------------------------------------------------------------------- #
class ManualEntryLineIn(BaseModel):
    account_code: str = Field(min_length=1, max_length=16)
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    memo: str | None = Field(default=None, max_length=255)


class ManualEntryIn(BaseModel):
    entry_date: date
    description: str = Field(min_length=1, max_length=255)
    lines: list[ManualEntryLineIn] = Field(min_length=2)


# --------------------------------------------------------------------------- #
# Гүйлгээний баланс
# --------------------------------------------------------------------------- #
class TrialBalanceRow(BaseModel):
    code: str
    name_mn: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class TrialBalanceOut(BaseModel):
    as_of: date | None = None
    accounts: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    imbalance: Decimal


# --------------------------------------------------------------------------- #
# Орлого үр дүн
# --------------------------------------------------------------------------- #
class StatementRow(BaseModel):
    code: str
    name_mn: str
    amount: Decimal


class FuelMarginOut(BaseModel):
    fuel_id: uuid.UUID
    fuel_name_mn: str | None = None
    revenue: Decimal
    cogs: Decimal
    margin: Decimal
    margin_pct: Decimal


class IncomeStatementOut(BaseModel):
    date_from: date
    date_to: date
    revenue: list[StatementRow]
    total_revenue: Decimal
    cogs: list[StatementRow]
    total_cogs: Decimal
    expense: list[StatementRow]
    total_expense: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    fuel_margins: list[FuelMarginOut]


# --------------------------------------------------------------------------- #
# Баланс
# --------------------------------------------------------------------------- #
class BalanceSheetRow(BaseModel):
    code: str
    name_mn: str
    balance: Decimal


class BalanceSheetOut(BaseModel):
    as_of: date | None = None
    assets: list[BalanceSheetRow]
    total_assets: Decimal
    liabilities: list[BalanceSheetRow]
    total_liabilities: Decimal
    equity: list[BalanceSheetRow]
    total_equity: Decimal
    retained_earnings: Decimal
    total_liabilities_equity: Decimal
    is_balanced: bool
    difference: Decimal


# --------------------------------------------------------------------------- #
# Мөнгөн гүйлгээ
# --------------------------------------------------------------------------- #
class CashFlowRow(BaseModel):
    event_type: str
    inflow: Decimal
    outflow: Decimal
    net: Decimal


class CashFlowOut(BaseModel):
    date_from: date
    date_to: date
    accounts: list[str]
    opening_balance: Decimal
    flows: list[CashFlowRow]
    total_inflow: Decimal
    total_outflow: Decimal
    net_change: Decimal
    closing_balance: Decimal


# --------------------------------------------------------------------------- #
# Нөөцийн үнэлгээ
# --------------------------------------------------------------------------- #
class TankValuationRow(BaseModel):
    tank_id: uuid.UUID
    tank_name: str
    fuel_id: uuid.UUID | None = None
    fuel_name_mn: str | None = None
    qty: Decimal
    avg_cost: Decimal
    value: Decimal


class ProductValuationRow(BaseModel):
    product_id: uuid.UUID
    sku: str
    name_mn: str
    qty: Decimal
    avg_cost: Decimal
    value: Decimal


class InventoryValuationOut(BaseModel):
    tanks: list[TankValuationRow]
    products: list[ProductValuationRow]
    fuel_value: Decimal
    goods_value: Decimal
    total_value: Decimal
    ledger_fuel: Decimal
    ledger_goods: Decimal
    ledger_total: Decimal
    fuel_delta: Decimal
    goods_delta: Decimal
    total_delta: Decimal


# --------------------------------------------------------------------------- #
# Бүрэн бүтэн байдал
# --------------------------------------------------------------------------- #
class IntegrityCheckOut(BaseModel):
    name: str
    ok: bool
    expected: Decimal
    actual: Decimal
    difference: Decimal


# --------------------------------------------------------------------------- #
# Эквайрингийн тооцоо
# --------------------------------------------------------------------------- #
class SettlementIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    method: str = Field(description="card эсвэл qr")
    amount: Decimal = Field(gt=0)
    settlement_date: date = Field(alias="date")


class SettlementOut(BaseModel):
    journal_entry_id: uuid.UUID
    entry_no: int
    method: str
    amount: Decimal
    settlement_date: date


# --------------------------------------------------------------------------- #
# Нийлүүлэгчийн өглөг
# --------------------------------------------------------------------------- #
class ApInvoiceOut(BaseModel):
    model_config = ORM

    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    invoice_no: str
    invoice_date: date
    due_date: date | None = None
    source_type: str
    source_id: uuid.UUID
    amount_gross: Decimal
    amount_paid: Decimal
    amount_due: Decimal
    status: str


class ApInvoiceList(BaseModel):
    items: list[ApInvoiceOut]
    total: int


class ApPaymentIn(BaseModel):
    ap_invoice_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    paid_from: str = Field(default="bank", description="bank эсвэл cash")
    payment_date: date
    note: str | None = None


class ApPaymentOut(BaseModel):
    model_config = ORM

    id: uuid.UUID
    ap_invoice_id: uuid.UUID
    supplier_id: uuid.UUID
    amount: Decimal
    paid_from: str
    payment_date: date
    note: str | None = None
    created_by: uuid.UUID | None = None


class ApPaymentResultOut(BaseModel):
    payment: ApPaymentOut
    invoice: ApInvoiceOut
    journal_entry_id: uuid.UUID | None = None
