"""Pydantic v2 schemas for fuels, tanks, tank movements and pumps (WP4).

Money/liters are ``Decimal`` everywhere — pydantic serialises them to JSON
strings, never floats.  All user facing validation messages are in Mongolian.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import PresetType

# --------------------------------------------------------------------------- #
# Fuels
# --------------------------------------------------------------------------- #


class FuelBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_mn: str
    color_hex: str
    price_per_liter: Decimal


class FuelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_mn: str
    price_per_liter: Decimal
    color_hex: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FuelCreate(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name_mn: str = Field(min_length=1, max_length=64)
    price_per_liter: Decimal = Decimal("0")
    color_hex: str = Field(default="#2563EB", max_length=9)
    sort_order: int = 0
    is_active: bool = True


class FuelUpdate(BaseModel):
    """``price_per_liter`` is accepted only so the API can reject it with a
    clear message — prices move exclusively through the price-change flow."""

    code: str | None = Field(default=None, min_length=1, max_length=16)
    name_mn: str | None = Field(default=None, min_length=1, max_length=64)
    price_per_liter: Decimal | None = None
    color_hex: str | None = Field(default=None, max_length=9)
    sort_order: int | None = None
    is_active: bool | None = None


class FuelListOut(BaseModel):
    items: list[FuelOut]
    total: int


# --------------------------------------------------------------------------- #
# Tanks
# --------------------------------------------------------------------------- #


class TankOut(BaseModel):
    id: uuid.UUID
    name: str
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    fuel_id: uuid.UUID
    fuel: FuelBrief
    capacity_l: Decimal
    current_l: Decimal
    avg_cost: Decimal
    min_level_l: Decimal
    is_active: bool
    fill_pct: Decimal
    is_low: bool
    stock_value: Decimal
    created_at: datetime
    updated_at: datetime


class TankCreate(BaseModel):
    branch_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=64)
    fuel_id: uuid.UUID
    capacity_l: Decimal
    current_l: Decimal = Decimal("0")
    avg_cost: Decimal = Decimal("0")
    min_level_l: Decimal = Decimal("0")
    is_active: bool = True


class TankUpdate(BaseModel):
    """Balance and average cost are deliberately absent — they only change via
    receipts, sales and adjustments so the fuel ledger stays auditable."""

    name: str | None = Field(default=None, min_length=1, max_length=64)
    fuel_id: uuid.UUID | None = None
    capacity_l: Decimal | None = None
    min_level_l: Decimal | None = None
    is_active: bool | None = None


class TankListOut(BaseModel):
    items: list[TankOut]
    total: int


class TankMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tank_id: uuid.UUID
    movement_type: str
    liters: Decimal
    balance_after_l: Decimal
    unit_cost: Decimal
    ref_type: str | None
    ref_id: uuid.UUID | None
    note: str | None
    created_at: datetime


class TankMovementListOut(BaseModel):
    items: list[TankMovementOut]
    total: int


class TankAdjustmentIn(BaseModel):
    liters: Decimal = Field(description="Тэмдэгтэй утга: + нэмэгдэл, − хорогдол")
    note: str | None = Field(default=None, max_length=255)


# --------------------------------------------------------------------------- #
# Pumps
# --------------------------------------------------------------------------- #


class NozzleOut(BaseModel):
    id: uuid.UUID
    pump_id: uuid.UUID
    nozzle_number: int
    fuel_id: uuid.UUID
    fuel_code: str
    fuel_name: str
    price_per_liter: Decimal
    color_hex: str
    tank_id: uuid.UUID
    tank_name: str
    tank_current_l: Decimal
    totalizer: Decimal


class NozzleCreate(BaseModel):
    nozzle_number: int = Field(ge=1, le=99)
    fuel_id: uuid.UUID
    tank_id: uuid.UUID
    totalizer: Decimal = Decimal("0")


class NozzleUpdate(BaseModel):
    nozzle_number: int | None = Field(default=None, ge=1, le=99)
    fuel_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    totalizer: Decimal | None = None


class TelemetryOut(BaseModel):
    pump_id: uuid.UUID
    nozzle_id: uuid.UUID | None
    status: str
    liters: Decimal
    amount: Decimal
    flow_lpm: Decimal
    authorization_id: uuid.UUID | None


class PumpOut(BaseModel):
    id: uuid.UUID
    number: int
    name: str
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    position_x: int = 0
    position_y: int = 0
    status: str
    driver: str
    is_active: bool
    nozzles: list[NozzleOut]
    live: TelemetryOut | None = None
    created_at: datetime
    updated_at: datetime


class PumpCreate(BaseModel):
    branch_id: uuid.UUID | None = None
    position_x: int = Field(default=0, ge=0, le=20)
    position_y: int = Field(default=0, ge=0, le=20)
    number: int = Field(ge=1, le=999)
    name: str = Field(min_length=1, max_length=64)
    driver: str = Field(default="simulated", max_length=32)
    is_active: bool = True
    nozzles: list[NozzleCreate] = Field(default_factory=list)


class PumpUpdate(BaseModel):
    branch_id: uuid.UUID | None = None
    position_x: int | None = Field(default=None, ge=0, le=20)
    position_y: int | None = Field(default=None, ge=0, le=20)
    number: int | None = Field(default=None, ge=1, le=999)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    driver: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class PumpListOut(BaseModel):
    items: list[PumpOut]
    total: int


class AuthorizeIn(BaseModel):
    nozzle_id: uuid.UUID
    preset_type: PresetType = PresetType.FULL
    preset_value: Decimal | None = None


class AuthorizeOut(BaseModel):
    authorization_id: uuid.UUID


class PumpActionOut(BaseModel):
    ok: bool = True
    pump_id: uuid.UUID
    status: str
