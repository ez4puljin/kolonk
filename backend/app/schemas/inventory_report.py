"""Бараа материалын тайлан /өртгөөр/ — схемүүд."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

ZERO = Decimal("0.00")
ZERO_Q = Decimal("0.000")


class MovementDetail(BaseModel):
    """Задаргааны нэг мөр — гүйлгээ ба түүний дараах үлдэгдэл."""

    date: date
    movement_type: str
    movement_name: str
    note: str | None = None
    in_qty: Decimal | None = None
    in_value: Decimal | None = None
    out_qty: Decimal | None = None
    out_value: Decimal | None = None
    balance_qty: Decimal = ZERO_Q
    unit_cost: Decimal = ZERO


class InventoryReportRow(BaseModel):
    """Шаталсан мөр: 0 = данс, 1 = байршил, 2 = бараа (бүлэглэлээс хамаарна)."""

    level: int
    code: str
    name: str
    unit: str = ""
    opening_qty: Decimal = ZERO_Q
    opening_value: Decimal = ZERO
    in_qty: Decimal = ZERO_Q
    in_value: Decimal = ZERO
    out_qty: Decimal = ZERO_Q
    out_value: Decimal = ZERO
    closing_qty: Decimal = ZERO_Q
    closing_value: Decimal = ZERO
    unit_cost: Decimal = ZERO
    details: list[MovementDetail] = []


class InventoryReportTotals(BaseModel):
    opening_qty: Decimal = ZERO_Q
    opening_value: Decimal = ZERO
    in_qty: Decimal = ZERO_Q
    in_value: Decimal = ZERO
    out_qty: Decimal = ZERO_Q
    out_value: Decimal = ZERO
    closing_qty: Decimal = ZERO_Q
    closing_value: Decimal = ZERO


class InventoryReportOut(BaseModel):
    date_from: date
    date_to: date
    group_by: str
    group_by_label: str
    tx_type: str
    include_details: bool = False
    #: Тайлангийн толгойд гарах "Шүүлтийн нөхцөл" мөр.
    filter_text: str = ""
    rows: list[InventoryReportRow] = []
    totals: InventoryReportTotals


class InventoryFilterOptions(BaseModel):
    """Шүүлтийн цонхны сонголтууд."""

    accounts: list[dict] = []
    locations: list[dict] = []
    fuels: list[dict] = []
    categories: list[dict] = []
    products: list[dict] = []
    group_by: list[dict] = []
    tx_types: list[dict] = []
