"""Simulated fuel pump — the v1 hardware.

State machine::

    idle ──authorize()──▶ authorized ──1.5s──▶ fueling ──target/halt──▶ complete ──3s──▶ idle

While fueling the driver ticks every 0.5 s and dispenses at 35–45 L/min with a
±5 % per-tick jitter.  All randomness is generated as ``Decimal`` (integer RNG
scaled down) so no float ever touches liters or money.

The run loop never raises: any unexpected error is logged and the pump drops to
``error`` status, which the manager republishes to the POS.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import uuid
from decimal import Decimal

from app.enums import PresetType, PumpStatus
from app.hardware.pump_driver import FuelingComplete, Preset, PumpCallback, PumpEvent, Telemetry
from app.money import q2, q3

log = logging.getLogger("kolonk.pump")

ZERO_L = Decimal("0.000")
ZERO_M = Decimal("0.00")
ZERO_F = Decimal("0.00")

BUSY_STATUSES = (PumpStatus.AUTHORIZED, PumpStatus.FUELING, PumpStatus.COMPLETE)


def rand_decimal(low: Decimal, high: Decimal, places: int = 3) -> Decimal:
    """Uniform ``Decimal`` in [low, high] without ever creating a float."""
    scale = Decimal(10) ** places
    low_i = int((low * scale).to_integral_value())
    high_i = int((high * scale).to_integral_value())
    if high_i <= low_i:
        return low
    return Decimal(random.randint(low_i, high_i)) / scale


def rand_chance(percent: int) -> bool:
    """True with ``percent`` probability."""
    return random.randint(1, 100) <= percent


class SimulatedPumpDriver:
    """In-process pump simulator implementing :class:`PumpDriver`."""

    # Timings (seconds) — overridable in tests to make the machine instant.
    AUTHORIZE_SECONDS: float = 1.5
    TICK_SECONDS: float = 0.5
    COMPLETE_SECONDS: float = 3.0

    # Flow model
    MIN_FLOW_LPM = Decimal("35")
    MAX_FLOW_LPM = Decimal("45")
    JITTER_LOW = Decimal("0.95")
    JITTER_HIGH = Decimal("1.05")

    # "Full tank" model
    FULL_MIN_L = Decimal("20")
    FULL_MAX_L = Decimal("60")
    NOZZLE_CLICK_PERCENT = 5  # % of full fills that stop early
    CLICK_LOW = Decimal("0.40")
    CLICK_HIGH = Decimal("0.80")

    def __init__(self, pump_id: uuid.UUID, callback: PumpCallback | None = None) -> None:
        self.pump_id = pump_id
        self._callback = callback
        self._lock = asyncio.Lock()
        self._halt = asyncio.Event()
        self._task: asyncio.Task | None = None

        self._status: str = PumpStatus.IDLE
        self._nozzle_id: uuid.UUID | None = None
        self._authorization_id: uuid.UUID | None = None
        self._unit_price: Decimal = ZERO_M
        self._liters: Decimal = ZERO_L
        self._amount: Decimal = ZERO_M
        #: Дүнгээр таталтад зогсох ЯГ дүн (эс бөгөөс None).
        self._target_amount: Decimal | None = None
        self._flow: Decimal = ZERO_F
        self._rate: Decimal = ZERO_F
        self._stop_at: Decimal = ZERO_L

    # ------------------------------------------------------------------ #
    # PumpDriver protocol
    # ------------------------------------------------------------------ #

    def set_callback(self, callback: PumpCallback | None) -> None:
        self._callback = callback

    def status(self) -> Telemetry:
        return Telemetry(
            pump_id=self.pump_id,
            nozzle_id=self._nozzle_id,
            status=self._status,
            liters=self._liters,
            amount=self._amount,
            flow_lpm=self._flow,
            authorization_id=self._authorization_id,
        )

    async def authorize(self, nozzle_id: uuid.UUID, preset: Preset, unit_price: Decimal) -> uuid.UUID:
        async with self._lock:
            if self._status in BUSY_STATUSES or (self._task is not None and not self._task.done()):
                raise ValueError("Насос завгүй байна")

            unit_price = q2(unit_price)
            if unit_price <= 0:
                raise ValueError("Түлшний үнэ тохируулаагүй байна")

            target, stop_at, target_amount = self._plan(preset, unit_price)

            self._halt = asyncio.Event()
            self._nozzle_id = nozzle_id
            self._authorization_id = uuid.uuid4()
            self._unit_price = unit_price
            self._liters = ZERO_L
            self._amount = ZERO_M
            self._target_amount = target_amount
            self._flow = ZERO_F
            self._rate = rand_decimal(self.MIN_FLOW_LPM, self.MAX_FLOW_LPM, 2)
            self._stop_at = stop_at
            self._status = PumpStatus.AUTHORIZED

            log.info(
                "Насос %s зөвшөөрөгдлөө: хошуу=%s зорилт=%s л (зогсох=%s л) үнэ=%s",
                self.pump_id,
                nozzle_id,
                target,
                stop_at,
                unit_price,
            )
            self._task = asyncio.create_task(self._run(), name=f"pump-{self.pump_id}")
            return self._authorization_id

    async def halt(self) -> None:
        """Finish the current fueling right now at the liters already dispensed."""
        self._halt.set()

    async def stop(self) -> None:
        """Shut the driver down (app shutdown) — cancels the running session."""
        self._halt.set()
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._status = PumpStatus.OFFLINE
        self._flow = ZERO_F

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _plan(
        self, preset: Preset, unit_price: Decimal
    ) -> tuple[Decimal, Decimal, Decimal | None]:
        """Return (target liters, stop-at liters, exact target amount or None).

        Гурав дахь утга нь зөвхөн ДҮНГЭЭР таталтад утгатай — тухайн дүн дээр
        яг зогсоохын тулд ашиглагдана.
        """
        preset_type = str(preset.type or PresetType.FULL)

        if preset_type == PresetType.LITERS:
            if preset.value is None or q3(preset.value) <= 0:
                raise ValueError("Урьдчилсан литр 0-ээс их байх ёстой")
            target = q3(preset.value)
            return target, target, None

        if preset_type == PresetType.AMOUNT:
            if preset.value is None or q2(preset.value) <= 0:
                raise ValueError("Урьдчилсан дүн 0-ээс их байх ёстой")
            amount = q2(preset.value)
            target = q3(Decimal(preset.value) / unit_price)
            if target <= 0:
                raise ValueError("Урьдчилсан дүн хэтэрхий бага байна")
            return target, target, amount

        if preset_type != PresetType.FULL:
            raise ValueError("Урьдчилсан тохиргооны төрөл буруу байна")

        target = rand_decimal(self.FULL_MIN_L, self.FULL_MAX_L, 3)
        stop_at = target
        if rand_chance(self.NOZZLE_CLICK_PERCENT):
            # Nozzle clicked off early — the tank was smaller than expected.
            stop_at = q3(target * rand_decimal(self.CLICK_LOW, self.CLICK_HIGH, 4))
            if stop_at <= 0:
                stop_at = target
        return target, stop_at, None

    async def _sleep_or_halt(self, seconds: float) -> bool:
        """Sleep, returning True if halt() was requested during the wait."""
        try:
            await asyncio.wait_for(self._halt.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False

    async def _run(self) -> None:
        try:
            await self._emit(self.status())

            if await self._sleep_or_halt(self.AUTHORIZE_SECONDS):
                await self._go_idle()
                return

            self._status = PumpStatus.FUELING
            self._flow = q2(self._rate)
            await self._emit(self.status())

            tick_minutes = Decimal(str(self.TICK_SECONDS)) / Decimal("60")

            while self._liters < self._stop_at:
                if await self._sleep_or_halt(self.TICK_SECONDS):
                    break

                tick_rate = self._rate * rand_decimal(self.JITTER_LOW, self.JITTER_HIGH, 4)
                delta = q3(tick_rate * tick_minutes)
                if delta <= 0:
                    delta = Decimal("0.001")

                liters = q3(self._liters + delta)
                if liters >= self._stop_at:
                    liters = self._stop_at

                self._liters = liters
                self._amount = q2(liters * self._unit_price)
                self._flow = q2(tick_rate)
                await self._emit(self.status())

            # Дүнгээр таталт: жинхэнэ насос мөнгөний тоолуур дээрээ зогсдог тул
            # эцсийн дүн нь заасан дүнтэй ЯГ тэнцүү байх ёстой. Литрийг 3 орон
            # хүртэл дугуйлснаас үүсэх ±0.01₮ зөрүүг эндээ арилгана.
            if self._target_amount is not None and self._liters >= self._stop_at:
                self._amount = self._target_amount

            if self._liters <= 0:
                # Cancelled before a single drop — no sale to hand to the POS.
                await self._go_idle()
                return

            self._flow = ZERO_F
            self._status = PumpStatus.COMPLETE
            await self._emit(self.status())
            await self._emit(
                FuelingComplete(
                    pump_id=self.pump_id,
                    nozzle_id=self._nozzle_id,
                    authorization_id=self._authorization_id,
                    liters=self._liters,
                    amount=self._amount,
                    unit_price=self._unit_price,
                )
            )

            await asyncio.sleep(self.COMPLETE_SECONDS)
            await self._go_idle()

        except asyncio.CancelledError:  # app shutdown — stay quiet
            raise
        except Exception:  # noqa: BLE001 — the loop must never bubble up
            log.exception("Насос %s ажиллахад алдаа гарлаа", self.pump_id)
            self._status = PumpStatus.ERROR
            self._flow = ZERO_F
            await self._emit(self.status())

    async def _go_idle(self) -> None:
        self._status = PumpStatus.IDLE
        self._flow = ZERO_F
        self._liters = ZERO_L
        self._amount = ZERO_M
        self._nozzle_id = None
        self._authorization_id = None
        self._unit_price = ZERO_M
        self._stop_at = ZERO_L
        await self._emit(self.status())

    async def _emit(self, event: PumpEvent) -> None:
        callback = self._callback
        if callback is None:
            return
        try:
            await callback(event)
        except Exception:  # noqa: BLE001 — a broken sink must not stop fuel flow
            log.exception("Насос %s: телеметр илгээхэд алдаа гарлаа", self.pump_id)
