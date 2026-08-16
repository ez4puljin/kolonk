"""Тайлан, хяналтын самбар, И-баримт, нөөцлөлтийн Pydantic v2 схемүүд (WP8).

Мөнгө/литр бүх талбарт ``Decimal`` — FastAPI JSON руу string болгож гаргана
(frontend талд ``parseFloat`` хориотой).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Борлуулалтын хураангуй
# --------------------------------------------------------------------------- #
class SalesSummaryRow(BaseModel):
    period: str
    period_start: date | None = None
    sale_count: int
    total: Decimal
    vat: Decimal
    fuel_total: Decimal
    store_total: Decimal
    liters: Decimal
    cogs: Decimal
    gross_profit: Decimal


class SalesSummaryTotals(BaseModel):
    sale_count: int
    total: Decimal
    vat: Decimal
    fuel_total: Decimal
    store_total: Decimal
    liters: Decimal
    cogs: Decimal
    gross_profit: Decimal
    margin_pct: Decimal
    avg_check: Decimal


class SalesReportOut(BaseModel):
    """Борлуулалтын хураангуй тайлан (ээлжийн ``SalesSummaryOut`` -оос ялгаатай)."""

    granularity: str
    granularity_name: str
    date_from: date
    date_to: date
    rows: list[SalesSummaryRow]
    totals: SalesSummaryTotals


# --------------------------------------------------------------------------- #
# Төлбөрийн задаргаа
# --------------------------------------------------------------------------- #
class TenderShareRow(BaseModel):
    method: str
    label_mn: str
    count: int
    amount: Decimal
    pct: Decimal


class TenderBreakdownOut(BaseModel):
    date_from: date
    date_to: date
    items: list[TenderShareRow]
    total: Decimal
    total_count: int


# --------------------------------------------------------------------------- #
# Өдрийн дэлгэрэнгүй
# --------------------------------------------------------------------------- #
class SalePaymentRow(BaseModel):
    method: str
    method_name: str
    amount: Decimal


class SaleDetailRow(BaseModel):
    id: uuid.UUID
    number: int
    completed_at: datetime | None = None
    sale_type: str
    sale_type_name: str
    status: str
    status_name: str
    cashier_id: uuid.UUID
    cashier_name: str | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    liters: Decimal
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    cogs: Decimal
    gross_profit: Decimal
    payments: list[SalePaymentRow] = Field(default_factory=list)


class SalesDetailTotals(BaseModel):
    sale_count: int
    total: Decimal
    vat: Decimal
    subtotal: Decimal
    cogs: Decimal
    liters: Decimal
    gross_profit: Decimal


class SalesDetailOut(BaseModel):
    date: date
    items: list[SaleDetailRow]
    totals: SalesDetailTotals
    by_tender: list[TenderShareRow]


# --------------------------------------------------------------------------- #
# Түлшний тайлан
# --------------------------------------------------------------------------- #
class FuelGradeRow(BaseModel):
    fuel_id: uuid.UUID
    code: str
    name: str
    liters: Decimal
    revenue: Decimal
    revenue_net: Decimal
    cogs: Decimal
    margin: Decimal
    margin_pct: Decimal
    avg_price: Decimal


class FuelGradeTotals(BaseModel):
    liters: Decimal
    revenue: Decimal
    revenue_net: Decimal
    cogs: Decimal
    margin: Decimal
    margin_pct: Decimal


class FuelPumpRow(BaseModel):
    pump_id: uuid.UUID
    pump_number: int
    pump_name: str
    nozzle_number: int | None = None
    liters: Decimal
    amount: Decimal


class FuelPumpTotals(BaseModel):
    liters: Decimal
    amount: Decimal


class FuelReportOut(BaseModel):
    date_from: date
    date_to: date
    grades: list[FuelGradeRow]
    grade_totals: FuelGradeTotals
    pumps: list[FuelPumpRow]
    pump_totals: FuelPumpTotals


# --------------------------------------------------------------------------- #
# Савны хорогдол
# --------------------------------------------------------------------------- #
class TankLossRow(BaseModel):
    tank_id: uuid.UUID
    tank_name: str
    fuel_code: str | None = None
    fuel_name: str | None = None
    liters: Decimal
    value: Decimal
    loss_liters: Decimal
    gain_liters: Decimal
    movement_count: int


class TankLossTotals(BaseModel):
    liters: Decimal
    value: Decimal
    loss_liters: Decimal
    gain_liters: Decimal
    movement_count: int


class TankLossOut(BaseModel):
    date_from: date
    date_to: date
    items: list[TankLossRow]
    totals: TankLossTotals


# --------------------------------------------------------------------------- #
# Шилдэг жагсаалтууд
# --------------------------------------------------------------------------- #
class TopProductRow(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    unit: str | None = None
    qty: Decimal
    amount: Decimal
    cogs: Decimal
    margin: Decimal
    margin_pct: Decimal


class TopCustomerRow(BaseModel):
    customer_id: uuid.UUID
    name: str
    type: str
    sale_count: int
    total: Decimal
    liters: Decimal


# --------------------------------------------------------------------------- #
# Хяналтын самбар
# --------------------------------------------------------------------------- #
class BranchDashboardRow(BaseModel):
    """Салбар тус бүрийн товч үзүүлэлт (эзний харьцуулалт)."""

    branch_id: uuid.UUID
    name: str
    today_total: Decimal = Decimal("0")
    today_liters: Decimal = Decimal("0")
    today_sale_count: int = 0
    month_total: Decimal = Decimal("0")
    month_liters: Decimal = Decimal("0")
    month_gross_profit: Decimal = Decimal("0")


class TankLevelOut(BaseModel):
    tank_id: uuid.UUID
    name: str
    fuel_code: str | None = None
    fuel_name: str | None = None
    current_l: Decimal
    capacity_l: Decimal
    min_level_l: Decimal
    fill_pct: Decimal
    is_low: bool
    value: Decimal


class PumpStateOut(BaseModel):
    pump_id: uuid.UUID
    number: int
    name: str
    status: str


class DashboardShiftOut(BaseModel):
    id: uuid.UUID
    number: int
    status: str
    opened_at: datetime
    opened_by: uuid.UUID
    opened_by_name: str | None = None
    opening_cash: Decimal
    sales_count: int
    sales_total: Decimal


class CashierTodayOut(BaseModel):
    total: Decimal
    sale_count: int
    liters: Decimal
    by_tender: dict[str, Decimal]


class StationTodayOut(BaseModel):
    total: Decimal
    sale_count: int
    liters: Decimal
    gross_profit: Decimal


class CashierDashboardOut(BaseModel):
    date: date
    shift: DashboardShiftOut | None = None
    today: CashierTodayOut
    station_today: StationTodayOut
    tanks: list[TankLevelOut]
    pumps: list[PumpStateOut]


class OwnerTodayOut(BaseModel):
    sales_total: Decimal
    liters: Decimal
    sale_count: int
    gross_profit: Decimal
    #: Үйл ажиллагааны зардал ба түүнийг хассан цэвэр ашиг.
    expense_total: Decimal = Decimal("0.00")
    net_profit: Decimal = Decimal("0.00")


class OwnerMonthOut(BaseModel):
    sales_total: Decimal
    liters: Decimal
    gross_profit: Decimal
    expense_total: Decimal = Decimal("0.00")
    net_profit: Decimal = Decimal("0.00")


class OwnerYearOut(BaseModel):
    sales_total: Decimal


class TankLossSummaryOut(BaseModel):
    liters: Decimal
    value: Decimal


class PendingCountsOut(BaseModel):
    price_changes: int
    refunds: int


class ArSummaryOut(BaseModel):
    open_total: Decimal
    overdue_total: Decimal


class ApSummaryOut(BaseModel):
    open_total: Decimal


class OwnerDashboardOut(BaseModel):
    date: date
    today: OwnerTodayOut
    month: OwnerMonthOut
    year: OwnerYearOut
    tanks: list[TankLevelOut]
    branches: list[BranchDashboardRow] = []
    tank_loss_mtd: TankLossSummaryOut
    tender_breakdown_today: list[TenderShareRow]
    top_products: list[TopProductRow]
    pending: PendingCountsOut
    ar: ArSummaryOut
    ap: ApSummaryOut


# --------------------------------------------------------------------------- #
# И-баримтын дараалал
# --------------------------------------------------------------------------- #
class EbarimtQueueRow(BaseModel):
    id: uuid.UUID
    sale_id: uuid.UUID
    sale_number: int | None = None
    sale_total: Decimal | None = None
    sale_completed_at: datetime | None = None
    status: str
    status_name: str
    attempt_count: int
    last_error: str | None = None
    receipt_id: str | None = None
    qr_data: str | None = None
    lottery_no: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


class EbarimtQueueList(BaseModel):
    items: list[EbarimtQueueRow]
    total: int


class EbarimtRetryOut(BaseModel):
    queued: bool
    inline: bool = False
    job_id: str | None = None
    item: EbarimtQueueRow
    message: str


# --------------------------------------------------------------------------- #
# Нөөцлөлт
# --------------------------------------------------------------------------- #
class BackupFileOut(BaseModel):
    filename: str
    size_bytes: int
    size_mb: float
    created_at: datetime


class BackupDirOut(BaseModel):
    """Нөөцлөлт хадгалах хавтасны төлөв."""

    directory: str
    writable: bool = True
    free_mb: float = 0.0
    #: True бол ``.env``-ийн анхдагч (тохиргоонд өөрчлөөгүй).
    is_default: bool = True


class BackupDirIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Хоосон бол анхдагч (.env) хавтас руу буцаана.
    directory: str = Field(default="", max_length=255)


class BackupListOut(BaseModel):
    items: list[BackupFileOut]
    total: int


class BackupCreatedOut(BaseModel):
    filename: str
    size_bytes: int
    size_mb: float
    created_at: datetime
    message: str


class RestoreConfirmIn(BaseModel):
    confirm: str = Field(description="Баталгаажуулах үг: СЭРГЭЭХ")


class RestoreResultOut(BaseModel):
    filename: str
    message: str


class DeleteResultOut(BaseModel):
    filename: str
    message: str
