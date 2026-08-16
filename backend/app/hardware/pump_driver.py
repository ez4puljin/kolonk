"""Pump hardware abstraction (CONTRACTS.md §7).

A driver owns exactly one physical pump.  It is told to authorize a nozzle with
a preset and a unit price, it streams telemetry through an async callback while
fuel flows, and it announces a finished fueling with :class:`FuelingComplete`.

v1 ships :class:`~app.hardware.simulated_pump.SimulatedPumpDriver`.  A real
driver (Gilbarco/Wayne/IFSF over TCP) only has to satisfy :class:`PumpDriver`
and the rest of the system is unchanged.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Union, runtime_checkable

from app.enums import PresetType


@dataclass
class Preset:
    """What the cashier asked for: N liters, N ₮, or a full tank."""

    type: str = PresetType.FULL
    value: Decimal | None = None


@dataclass
class Telemetry:
    """A pump's live state.  Emitted on every state change and on every tick."""

    pump_id: uuid.UUID
    nozzle_id: uuid.UUID | None
    status: str
    liters: Decimal
    amount: Decimal
    flow_lpm: Decimal
    authorization_id: uuid.UUID | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Wire form — every Decimal/UUID becomes a string (never a float)."""
        return {
            "pump_id": str(self.pump_id),
            "nozzle_id": str(self.nozzle_id) if self.nozzle_id else None,
            "status": str(self.status),
            "liters": str(self.liters),
            "amount": str(self.amount),
            "flow_lpm": str(self.flow_lpm),
            "authorization_id": str(self.authorization_id) if self.authorization_id else None,
        }


@dataclass
class FuelingComplete:
    """A finished fueling — the POS turns this into a sale line."""

    pump_id: uuid.UUID
    nozzle_id: uuid.UUID
    authorization_id: uuid.UUID
    liters: Decimal
    amount: Decimal
    unit_price: Decimal

    def as_dict(self) -> dict[str, str]:
        return {
            "pump_id": str(self.pump_id),
            "nozzle_id": str(self.nozzle_id),
            "authorization_id": str(self.authorization_id),
            "liters": str(self.liters),
            "amount": str(self.amount),
            "unit_price": str(self.unit_price),
        }


PumpEvent = Union[Telemetry, FuelingComplete]
PumpCallback = Callable[[PumpEvent], Awaitable[None]]


@runtime_checkable
class PumpDriver(Protocol):
    """Every pump driver — simulated or real — implements exactly this."""

    async def authorize(self, nozzle_id: uuid.UUID, preset: Preset, unit_price: Decimal) -> uuid.UUID:
        """Arm the nozzle and return the authorization id.

        Raises ``ValueError`` (Mongolian message) if the pump is not free.
        """
        ...

    async def halt(self) -> None:
        """Stop the current fueling immediately at the liters dispensed so far."""
        ...

    def status(self) -> Telemetry:
        """Current state — never blocks, never touches the network."""
        ...
