"""Ээлжийн API схемүүд (WP5).

Мөнгө/литрийн бүх талбар `Decimal` — Pydantic v2 JSON руу string-ээр гаргана.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    #: Батлахдаа зассан ажилласан огноо (өдрийн хаалттай бол).
    business_date: date | None = None
    #: Нягтлан баталсан эсэх.
    approved: bool = False
    #: Өдрийн хаалтын банкны терминал, шилжүүлгийн дүн (тулгалтын нийт дүнд).
    settlement_total: Decimal = ZERO
    transfer_total: Decimal = ZERO
    sales_total: Decimal = ZERO
    #: Хадгалсан «байвал зохих» дүн хуучин дүрмээр бодогдсон — дахин бодох шаардлагатай.
    needs_recalc: bool = False
    expected_recalc: Decimal | None = None
    #: Админы гар засвар (системийн алдаа).
    cash_adjustment: Decimal = ZERO


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
    #: Өмнөх ээлжийн хаалтын миль — нээх мөчид хөлдөөсөн.
    prev_close_reading: Decimal | None = None
    #: Нээлт − өмнөх хаалт. 0-ээс өөр бол мэдэгдэлгүй түгээлт эсвэл буруу бичилт.
    mile_gap_l: Decimal | None = None
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
    #: Хаагдсан ээлжийн хадгалсан дүн одоогийн (зөв) дүрмээс өөр бол шинэ дүн.
    recalc_expected: Decimal | None = None
    #: Админы гар засвар — системийн алдаанаас үүссэн зөрүүний залруулга.
    adjustment: Decimal = ZERO
    adjustment_note: str | None = None
    adjusted_by_name: str | None = None
    adjusted_at: datetime | None = None


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


class PriceAlertOut(BaseModel):
    """Нээлттэй ээлжид үнэ батлагдсан ч тэмдэглэл ороогүй хошуу."""

    nozzle_id: uuid.UUID
    nozzle_number: int
    pump_name: str
    fuel_id: uuid.UUID
    fuel_name: str
    #: Систем одоо энэ хошуунд бодож буй үнэ (нээлтийн эсвэл сүүлийн тэмдэглэлийн).
    used_price: Decimal
    #: Батлагдаж мөрдөгдөж буй үнэ.
    current_price: Decimal
    approved_at: datetime | None = None
    #: Тэмдэглэл оруулсан ч үнэ нь буруу бол True.
    has_mark: bool = False
    #: Сүүлийн тэмдэглэлээс (эсвэл ээлж нээснээс) хойш үнэ батлагдсан ч
    #: тэмдэглэгдээгүй — өдрийн хаалт хийгдэхгүй. False бол зөвхөн анхааруулга
    #: (тэмдэглэлийн үнэ батлагдаагүй / хүсэлт хүлээгдэж буй гэх мэт).
    blocking: bool = False


class OpenShiftPriceAlertOut(BaseModel):
    """Үнийн тэмдэглэл дутуу нээлттэй ээлж (админд)."""

    shift_id: uuid.UUID
    shift_number: int
    branch_id: uuid.UUID | None = None
    branch_name: str = ""
    attendant: str = ""
    opened_at: datetime
    alerts: list[PriceAlertOut]


class CreditItemIn(BaseModel):
    """Зээлийн борлуулалтын нэг мөр — түлш (литр эсвэл дүнгээр) эсвэл бараа.

    ``amount`` — түлшний КОЛОНКИЙН (бүтэн үнийн) дүн; гэрээний хөнгөлөлтийг
    сервер хасаж нэхэмжилнэ. ``unit_price`` — ээлжийн дундуур үнэ өөрчлөгдсөн
    бол аль үнээр авсан (түлш: сегментийн үнэ, бараа: ээлжид мөрдсөн үнэ).
    """

    model_config = ConfigDict(extra="forbid")

    fuel_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    qty: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)


class NewCreditCustomerIn(BaseModel):
    """Хаалтын үед шинээр үүсгэх харилцагч — гэрээ автоматаар нээгдэнэ.

    Утас нь бүртгэлтэй харилцагчтай таарвал шинээр үүсгэхгүй, түүний идэвхтэй
    гэрээг ашиглана (давхар бүртгэлээс сэргийлнэ).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    last_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    register_no: str | None = Field(default=None, max_length=32)
    #: Зээлийн хязгаар — хоосон/0 бол энэ хаалтын зээлийн дүнгээр тогтооно.
    credit_limit: Decimal = Field(default=ZERO, ge=0)


class CreditLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Гурвын аль нэг нь заавал: байгаа гэрээ / гэрээгүй бүртгэлтэй харилцагч
    #: (гэрээ автоматаар нээгдэнэ) / шинэ харилцагч.
    contract_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    new_customer: NewCreditCustomerIn | None = None
    items: list[CreditItemIn] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_target(self) -> "CreditLineIn":
        given = sum(x is not None for x in (self.contract_id, self.customer_id, self.new_customer))
        if given != 1:
            raise ValueError("Гэрээ, харилцагч эсвэл шинэ харилцагч — аль нэгийг нь")
        return self


class OilLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


class ArPaymentLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Байгаа гэрээ — эсвэл энэ хаалтын «Зээл» алхамд шинээр нэмсэн харилцагч
    #: (``new_customer`` — нэр/утас нь зээлийн мөртэй ижил бол нэг гэрээ).
    contract_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    new_customer: NewCreditCustomerIn | None = None
    amount: Decimal = Field(gt=0)
    #: cash | card | transfer — карт/шилжүүлэг банк руу орно.
    method: str = "cash"
    note: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _one_target(self) -> "ArPaymentLineIn":
        given = sum(x is not None for x in (self.contract_id, self.customer_id, self.new_customer))
        if given != 1:
            raise ValueError("Гэрээ, харилцагч эсвэл шинэ харилцагч — аль нэгийг нь")
        return self


class ExpenseLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_code: str
    amount: Decimal = Field(gt=0)
    #: cash | card (банкны терминал) | transfer | bank — терминал/шилжүүлэг
    #: харилцахаас (bank) гарна, хэлбэр нь зардлын тайлбарт бичигдэнэ.
    payment_method: str = "cash"
    description: str | None = Field(default=None, max_length=255)


class DailyCloseIn(BaseModel):
    """Өдрийн хаалт — бүх бүртгэл нэг дор."""

    model_config = ConfigDict(extra="forbid")

    totalizer_readings: list[TotalizerReadingIn] = Field(min_length=1)
    declared_cash: Decimal = Field(ge=0)
    settlement_vat: Decimal = Field(default=ZERO, ge=0)
    settlement_novat: Decimal = Field(default=ZERO, ge=0)
    #: Банкны терминалын нийт дүн (НӨАТ-тэй/гүй хуваахгүй). Өгвөл vat/novat-ыг
    #: орлоно: settlement_vat = total, settlement_novat = 0.
    settlement_total: Decimal | None = Field(default=None, ge=0)
    #: Дансаар шилжүүлсэн орлого — картын тооцооны адил бэлэн мөнгийг бууруулна.
    transfer_total: Decimal = Field(default=ZERO, ge=0)
    #: Шилжүүлэг аль банкны дансанд орсон бэ (хоосон бол салбарын данс, эсвэл
    #: шимтгэлийн анхдагч данс) — банкны данс бүрийн үлдэгдэл зөв гарахад.
    transfer_bank_account_id: uuid.UUID | None = None
    oil_lines: list[OilLineIn] = Field(default_factory=list)
    credit_lines: list[CreditLineIn] = Field(default_factory=list)
    ar_payments: list[ArPaymentLineIn] = Field(default_factory=list)
    expenses: list[ExpenseLineIn] = Field(default_factory=list)
    tank_dips: list[TankDipIn] = Field(default_factory=list)
    note: str | None = None
    #: Түгээгчийн дэлгэц дээрх тулгалт, мөрүүд — тайланд харьцуулахад хадгална.
    client_snapshot: dict[str, Any] | None = None
    #: «Шалгах» алхамд түгээгчийн харсан серверийн тооцоо — хаах мөчид өөр бол 409
    #: (тулгалтыг шинэчилж дахин харуулна).
    preview_fuel_total: Decimal | None = None
    preview_opening_cash: Decimal | None = None
    preview_refunds_cash: Decimal | None = None
    preview_other_cash: Decimal | None = None
    preview_day_cash_sales: Decimal | None = None


class CloseDraftIn(BaseModel):
    """Хаалтын ноорог — frontend-ийн мөрүүд (тос/бараа, зээл, өглөг төлөлт, зарлага)."""

    model_config = ConfigDict(extra="forbid")

    draft: dict[str, Any]


class CloseDraftOut(BaseModel):
    draft: dict[str, Any] | None = None
    updated_at: datetime | None = None


class ClosingCorrectIn(BaseModel):
    """Нягтлангийн засвар — тоолсон бэлэн мөнгө."""

    model_config = ConfigDict(extra="forbid")

    declared_cash: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class OpeningReadingFixIn(BaseModel):
    """Админы засвар — нээлттэй ээлжийн нээлтийн миль (буруу бичсэн үед)."""

    model_config = ConfigDict(extra="forbid")

    nozzle_id: uuid.UUID
    reading: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class OpeningReadingFixOut(BaseModel):
    shift_id: uuid.UUID
    nozzle_id: uuid.UUID
    #: Өмнөх ээлжийн хаалтын миль (нээх мөчид хөлдөөсөн).
    prev_reading: Decimal | None
    old_reading: Decimal
    reading: Decimal
    #: Шинэ нээлт − өмнөх хаалт.
    mile_gap_l: Decimal | None


class ClosingTendersIn(BaseModel):
    """Хаалтын засвар — тоолсон бэлэн, банкны терминал, шилжүүлэг."""

    model_config = ConfigDict(extra="forbid")

    declared_cash: Decimal = Field(ge=0)
    settlement_total: Decimal = Field(ge=0)
    transfer_total: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class ClosingTargetMixin(BaseModel):
    """Байгаа гэрээ / гэрээгүй харилцагч / шинэ харилцагч — аль нэг нь."""

    contract_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    new_customer: "NewCreditCustomerIn | None" = None

    @model_validator(mode="after")
    def _one_target(self) -> "ClosingTargetMixin":
        given = sum(x is not None for x in (self.contract_id, self.customer_id, self.new_customer))
        if given != 1:
            raise ValueError("Гэрээ, харилцагч эсвэл шинэ харилцагч — аль нэгийг нь")
        return self


class ClosingCreditIn(ClosingTargetMixin):
    """Хаалтын засвар — нэгдсэн борлуулалтаас харилцагчийн зээл рүү шилжүүлэх.

    ``amount`` — колонкийн (бүтэн үнийн) дүн; ``unit_price`` — ээлжид олон үнэ
    байвал аль үнээр авсан.
    """

    model_config = ConfigDict(extra="forbid")

    fuel_id: uuid.UUID
    qty: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)


class AdminCreditItemIn(BaseModel):
    """Админы зээлийн мөр — түлш эсвэл бараа.

    Түлш: ``amount`` (колонкийн дүн) эсвэл ``qty`` (литр); хоёуланг нь өгвөл
    өөрчлөгдөөгүй мөр гэж танина. ``unit_price`` — ээлжид олон үнэ байвал аль
    үнээр авсан. Бараа: ``qty`` ба ``unit_price`` (хоосон бол ээлжийн үеийн үнэ).
    """

    model_config = ConfigDict(extra="forbid")

    fuel_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    qty: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)


class AdminCreditIn(BaseModel):
    """Админ — зээлийн борлуулалт нэмэх/засах: харилцагч солих ба/эсвэл мөрүүд."""

    model_config = ConfigDict(extra="forbid")

    contract_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    new_customer: NewCreditCustomerIn | None = None
    #: Хоосон (None) бол мөрүүд хэвээр — зөвхөн харилцагч солино.
    items: list[AdminCreditItemIn] | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _at_most_one_target(self) -> "AdminCreditIn":
        given = sum(x is not None for x in (self.contract_id, self.customer_id, self.new_customer))
        if given > 1:
            raise ValueError("Гэрээ, харилцагч эсвэл шинэ харилцагч — аль нэгийг нь")
        return self

    @property
    def has_target(self) -> bool:
        return any(x is not None for x in (self.contract_id, self.customer_id, self.new_customer))


class AdminOilLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    #: Хоосон бол ээлжийн үеийн үнэ.
    unit_price: Decimal | None = Field(default=None, ge=0)


class AdminOilLinesIn(BaseModel):
    """Админ — тос, барааны борлуулалтын мөрүүдийг бүрэн солих (хоосон бол устгана)."""

    model_config = ConfigDict(extra="forbid")

    lines: list[AdminOilLineIn] = Field(default_factory=list, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class AdminPriceMarkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nozzle_id: uuid.UUID
    #: Шинэ үнэ эхэлсэн миль (нээлт ба хаалтын хооронд).
    reading: Decimal = Field(ge=0)
    new_price: Decimal = Field(gt=0)


class AdminCreditPriceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    unit_price: Decimal = Field(gt=0)


class AdminFuelIn(BaseModel):
    """Админ — хаалтын миль ба үнийн тэмдэглэл.

    ``readings`` — өөрчлөх хаалтын милүүд; ``marks`` — ээлжийн бүх тэмдэглэл
    (None бол хэвээр); ``credit_prices`` — зээлийн түлшний мөрийн шинэ үнэ.
    """

    model_config = ConfigDict(extra="forbid")

    readings: list[TotalizerReadingIn] = Field(default_factory=list, max_length=200)
    marks: list[AdminPriceMarkIn] | None = Field(default=None, max_length=200)
    credit_prices: list[AdminCreditPriceIn] = Field(default_factory=list, max_length=500)
    note: str | None = Field(default=None, max_length=500)


class ClosingArIn(ClosingTargetMixin):
    """Хаалтын засвар — өглөг төлөлт нэмэх."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0)
    method: str = "cash"


class ClosingExpenseIn(BaseModel):
    """Хаалтын засвар — зарлага нэмэх."""

    model_config = ConfigDict(extra="forbid")

    account_code: str
    amount: Decimal = Field(gt=0)
    method: str = "cash"
    description: str | None = Field(default=None, max_length=200)


class CashRecalcOut(BaseModel):
    shift_id: uuid.UUID
    expected_cash: Decimal
    cash_over_short: Decimal


class CashAdjustIn(BaseModel):
    """Админы гар засвар — энэ ээлжийн ЖИНХЭНЭ илүүдэл/дутагдал ба шалтгаан."""

    model_config = ConfigDict(extra="forbid")

    target_over_short: Decimal = ZERO
    note: str = Field(min_length=3, max_length=1000)


class CashAdjustClearIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=1000)


class CashAdjustOut(BaseModel):
    shift_id: uuid.UUID
    shift_number: int
    declared_cash: Decimal
    #: Засваргүй — одоогийн дүрмээр бодсон байвал зохих ба зөрүү.
    raw_expected: Decimal
    raw_over_short: Decimal
    adjustment: Decimal = ZERO
    expected_cash: Decimal
    cash_over_short: Decimal
    note: str | None = None
    adjusted_by_name: str | None = None
    adjusted_at: datetime | None = None
    #: Түгээгч хаалт хийхдээ дэлгэц дээрээ харсан зөрүү (хадгалагдсан бол).
    client_diff: Decimal | None = None
    approved: bool = False


class CashAdjustBulkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shift_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    #: zero — жинхэнэ зөрүүг 0; client — түгээгчийн дэлгэц дээрх зөрүүгээр.
    mode: Literal["zero", "client"] = "zero"
    note: str = Field(min_length=3, max_length=1000)


class CashAdjustBulkRow(BaseModel):
    shift_id: uuid.UUID
    number: int
    adjustment: Decimal | None = None
    cash_over_short: Decimal | None = None
    reason: str | None = None


class CashAdjustBulkOut(BaseModel):
    adjusted: list[CashAdjustBulkRow]
    skipped: list[CashAdjustBulkRow]


class CashRecalcBulkIn(BaseModel):
    """Хуучин дүрмээр бодогдсон ээлжүүдийг бөөнөөр дахин бодох."""

    model_config = ConfigDict(extra="forbid")

    shift_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class CashRecalcBulkRow(BaseModel):
    shift_id: uuid.UUID
    number: int
    expected_cash: Decimal | None = None
    cash_over_short: Decimal | None = None
    reason: str | None = None


class CashRecalcBulkOut(BaseModel):
    recalculated: list[CashRecalcBulkRow]
    skipped: list[CashRecalcBulkRow]


class OpeningCashFixIn(BaseModel):
    """Админы засвар — ээлжийн эхний бэлэн мөнгө (буруу бичсэн үед)."""

    model_config = ConfigDict(extra="forbid")

    opening_cash: Decimal = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class OpeningCashFixOut(BaseModel):
    shift_id: uuid.UUID
    old_opening_cash: Decimal
    opening_cash: Decimal
    #: Хаагдсан ээлжид — дахин бодогдсон байвал зохих мөнгө, зөрүү.
    expected_cash: Decimal | None
    cash_over_short: Decimal | None


class ClosingApprovalIn(BaseModel):
    """Хаалт батлах / батламж буцаах."""

    model_config = ConfigDict(extra="forbid")

    approved: bool = True
    note: str | None = Field(default=None, max_length=500)
    #: Батлахдаа ээлжийн огноог засна (хаалтыг хожуу хийсэн үед) — тайланд энэ огноо гарна.
    business_date: date | None = None


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
