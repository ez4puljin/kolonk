"""Ээлжийн API схемүүд (WP5).

Мөнгө/литрийн бүх талбар `Decimal` — Pydantic v2 JSON руу string-ээр гаргана.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

ZERO = Decimal("0.00")


# --------------------------------------------------------------------------- #
# Оролт
# --------------------------------------------------------------------------- #
class TankDipIn(BaseModel):
    """Савны шингэний хэмжилт (уулзуур)."""

    model_config = ConfigDict(extra="forbid")

    tank_id: uuid.UUID
    dip_liters: Decimal = Field(ge=0)


class TotalizerReadingIn(BaseModel):
    """Хошууны механик тоолуурын заалт."""

    model_config = ConfigDict(extra="forbid")

    nozzle_id: uuid.UUID
    reading: Decimal = Field(ge=0)


class ShiftOpenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_cash: Decimal = Field(default=ZERO, ge=0)
    tank_dips: list[TankDipIn] = Field(default_factory=list)
    totalizer_readings: list[TotalizerReadingIn] = Field(default_factory=list)


class ShiftCloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declared_cash: Decimal = Field(ge=0)
    tank_dips: list[TankDipIn] = Field(default_factory=list)
    totalizer_readings: list[TotalizerReadingIn] = Field(default_factory=list)
    note: str | None = None


# --------------------------------------------------------------------------- #
# Гаралт
# --------------------------------------------------------------------------- #
class ShiftSummary(BaseModel):
    id: uuid.UUID
    number: int
    status: str
    status_name: str
    opened_at: datetime
    closed_at: datetime | None = None
    opened_by: uuid.UUID | None = None
    opened_by_name: str | None = None
    closed_by: uuid.UUID | None = None
    closed_by_name: str | None = None
    opening_cash: Decimal = ZERO
    declared_cash: Decimal | None = None
    expected_cash: Decimal | None = None
    cash_over_short: Decimal | None = None
    note: str | None = None
    sales_count: int = 0
    sales_total: Decimal = ZERO


class ShiftListOut(BaseModel):
    items: list[ShiftSummary]
    total: int


class TenderRow(BaseModel):
    method: str
    method_name: str
    count: int
    amount: Decimal


class SalesSummaryOut(BaseModel):
    count: int = 0
    gross_total: Decimal = ZERO
    vat_total: Decimal = ZERO
    net_total: Decimal = ZERO
    fuel_amount: Decimal = ZERO
    fuel_liters: Decimal = Decimal("0.000")
    store_amount: Decimal = ZERO
    by_tender: list[TenderRow] = Field(default_factory=list)


class FuelRow(BaseModel):
    fuel_id: uuid.UUID
    code: str
    name: str
    liters: Decimal
    amount: Decimal


class NozzleRow(BaseModel):
    pump_id: uuid.UUID
    pump_number: int
    pump_name: str
    nozzle_id: uuid.UUID
    nozzle_number: int
    fuel_name: str
    opening_reading: Decimal | None = None
    closing_reading: Decimal | None = None
    reading_delta_l: Decimal | None = None
    sold_liters: Decimal = Decimal("0.000")
    sold_amount: Decimal = ZERO


class TankRow(BaseModel):
    tank_id: uuid.UUID
    tank_name: str
    fuel_name: str
    open_dip: Decimal | None = None
    close_dip: Decimal | None = None
    book_liters: Decimal | None = None
    variance_l: Decimal | None = None
    variance_value: Decimal = ZERO


class CashSection(BaseModel):
    opening_cash: Decimal = ZERO
    cash_sales: Decimal = ZERO
    refunds: Decimal = ZERO
    #: Борлуулалтаас гадуурх кассын цэвэр хөдөлгөөн — ваучер бэлнээр зарах,
    #: карт цэнэглэх, кассаас нийлүүлэгчид төлөх г.м.
    other_cash: Decimal = ZERO
    expected_cash: Decimal = ZERO
    declared_cash: Decimal | None = None
    cash_over_short: Decimal | None = None


class RefundRow(BaseModel):
    id: uuid.UUID
    sale_number: int | None = None
    amount: Decimal
    refund_method: str
    refund_method_name: str
    status: str
    status_name: str
    reason: str | None = None
    decided_at: datetime | None = None


class ProfitSection(BaseModel):
    revenue_net: Decimal = ZERO
    cogs_total: Decimal = ZERO
    gross_profit: Decimal = ZERO
    margin_pct: Decimal = ZERO


class PostedEntryRow(BaseModel):
    entry_no: int | None = None
    event_type: str
    description: str
    amount: Decimal = ZERO


class ShiftReportOut(BaseModel):
    shift: ShiftSummary
    sales: SalesSummaryOut
    fuels: list[FuelRow] = Field(default_factory=list)
    nozzles: list[NozzleRow] = Field(default_factory=list)
    tanks: list[TankRow] = Field(default_factory=list)
    cash: CashSection
    refunds: list[RefundRow] = Field(default_factory=list)
    profit: ProfitSection
    posted_entries: list[PostedEntryRow] = Field(default_factory=list)
    #: Түгээгчийн өдрийн хаалтын баримт (байвал) — миль тооцоо, settlement.
    daily: dict | None = None


class CurrentShiftOut(BaseModel):
    """Нээлттэй ээлжийн шууд (running) хураангуй."""

    shift: ShiftSummary
    sales: SalesSummaryOut
    fuels: list[FuelRow] = Field(default_factory=list)
    cash: CashSection


# --------------------------------------------------------------------------- #
# Түгээгчийн өдрийн ээлж
# --------------------------------------------------------------------------- #
class PriceMarkIn(BaseModel):
    """Өдрийн дундуур үнэ өөрчлөгдөхөд аль мильд шинэ үнэ эхэлснийг тэмдэглэнэ."""

    model_config = ConfigDict(extra="forbid")

    nozzle_id: uuid.UUID
    reading: Decimal = Field(ge=0)
    new_price: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class PriceMarkOut(BaseModel):
    id: uuid.UUID
    nozzle_id: uuid.UUID
    nozzle_number: int | None = None
    fuel_name: str = ""
    reading: Decimal = ZERO
    old_price: Decimal = ZERO
    new_price: Decimal = ZERO
    note: str | None = None
    created_at: datetime | None = None


class CreditItemIn(BaseModel):
    """Зээлийн борлуулалтын нэг мөр — түлш (литр эсвэл дүнгээр) эсвэл бараа."""

    model_config = ConfigDict(extra="forbid")

    fuel_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    qty: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0)


class CreditLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: uuid.UUID
    items: list[CreditItemIn] = Field(min_length=1)


class OilLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


class ArPaymentLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    #: cash | card | transfer — карт/шилжүүлэг банк руу орно.
    method: str = "cash"
    note: str | None = Field(default=None, max_length=255)


class ExpenseLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_code: str
    amount: Decimal = Field(gt=0)
    payment_method: str = "cash"
    description: str | None = Field(default=None, max_length=255)


class DailyCloseIn(BaseModel):
    """Өдрийн хаалт — бүх бүртгэл нэг дор."""

    model_config = ConfigDict(extra="forbid")

    totalizer_readings: list[TotalizerReadingIn] = Field(min_length=1)
    declared_cash: Decimal = Field(ge=0)
    settlement_vat: Decimal = Field(default=ZERO, ge=0)
    settlement_novat: Decimal = Field(default=ZERO, ge=0)
    #: Дансаар шилжүүлсэн орлого — картын тооцооны адил бэлэн мөнгийг бууруулна.
    transfer_total: Decimal = Field(default=ZERO, ge=0)
    oil_lines: list[OilLineIn] = Field(default_factory=list)
    credit_lines: list[CreditLineIn] = Field(default_factory=list)
    ar_payments: list[ArPaymentLineIn] = Field(default_factory=list)
    expenses: list[ExpenseLineIn] = Field(default_factory=list)
    tank_dips: list[TankDipIn] = Field(default_factory=list)
    note: str | None = None


class DailyPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totalizer_readings: list[TotalizerReadingIn] = Field(min_length=1)


class ShiftAttachmentOut(BaseModel):
    id: uuid.UUID
    kind: str = "open"
    ref_id: uuid.UUID | None = None
    original_name: str = ""
    content_type: str = ""
    size_bytes: int = 0
    created_at: datetime | None = None
