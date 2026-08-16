"""PumpManager — owns one driver per active pump and bridges hardware to the app.

It is created in ``main.lifespan`` and lives on ``app.state.pump_manager``.

Responsibilities
  * load active pumps + nozzles from the DB and spin up drivers (a dead DB must
    never stop the API from booting — the manager just stays empty);
  * republish every driver event to Redis ``PUMP_CHANNEL`` so ``/ws/pumps``
    clients see it;
  * persist the consequences of a finished fueling: nozzle totalizer, pump
    status and the ``auth:{authorization_id}`` handoff key the POS reads when
    the cashier turns the fueling into a sale.

Sessions opened here are **outside** a request, so this module commits its own
short-lived sessions — the "services never commit" rule covers request-scoped
work, which is not what happens on a hardware callback.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.enums import PumpStatus
from app.hardware.pump_driver import FuelingComplete, Preset, PumpEvent, Telemetry
from app.hardware.simulated_pump import SimulatedPumpDriver
from app.models.fuel import Fuel, Pump, PumpNozzle
from app.redis_client import PUMP_CHANNEL, get_redis, publish

log = logging.getLogger("kolonk.pump")

AUTH_KEY_TTL_SECONDS = 3600


def auth_key(authorization_id: uuid.UUID | str) -> str:
    return f"auth:{authorization_id}"


@dataclass(frozen=True)
class NozzleInfo:
    nozzle_id: uuid.UUID
    pump_id: uuid.UUID
    nozzle_number: int
    fuel_id: uuid.UUID
    tank_id: uuid.UUID


class PumpManager:
    def __init__(self) -> None:
        self._drivers: dict[uuid.UUID, SimulatedPumpDriver] = {}
        self._nozzles: dict[uuid.UUID, NozzleInfo] = {}
        self._db_status: dict[uuid.UUID, str] = {}
        self._started = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Load pumps from the DB and arm a driver for each one."""
        try:
            async with async_session_factory() as session:
                pumps = (
                    await session.scalars(
                        select(Pump)
                        .options(selectinload(Pump.nozzles))
                        .where(Pump.is_active.is_(True))
                        .order_by(Pump.number)
                    )
                ).all()

                for pump in pumps:
                    self._drivers[pump.id] = SimulatedPumpDriver(pump.id, callback=self._on_event)
                    self._db_status[pump.id] = PumpStatus.IDLE
                    for nozzle in pump.nozzles:
                        self._nozzles[nozzle.id] = NozzleInfo(
                            nozzle_id=nozzle.id,
                            pump_id=pump.id,
                            nozzle_number=nozzle.nozzle_number,
                            fuel_id=nozzle.fuel_id,
                            tank_id=nozzle.tank_id,
                        )

                if pumps:
                    await session.execute(
                        update(Pump)
                        .where(Pump.id.in_([p.id for p in pumps]))
                        .values(status=PumpStatus.IDLE)
                    )
                await session.commit()

            self._started = True
            log.info("Насосны менежер аслаа: %s насос, %s хошуу", len(self._drivers), len(self._nozzles))
        except Exception:  # noqa: BLE001 — never block application startup
            self._drivers.clear()
            self._nozzles.clear()
            self._db_status.clear()
            self._started = False
            log.warning("Насос ачаалж чадсангүй — менежер хоосон эхэллээ", exc_info=True)

    async def stop(self) -> None:
        for driver in list(self._drivers.values()):
            try:
                await driver.stop()
            except Exception:  # noqa: BLE001
                log.warning("Насос унтраахад алдаа гарлаа: %s", driver.pump_id, exc_info=True)
        self._drivers.clear()
        self._nozzles.clear()
        self._db_status.clear()
        self._started = False

    async def refresh(self) -> None:
        """Re-sync drivers with the DB after pump/nozzle CRUD.

        Busy pumps are left alone — a pump that is fueling is never torn down.
        """
        try:
            async with async_session_factory() as session:
                pumps = (
                    await session.scalars(
                        select(Pump)
                        .options(selectinload(Pump.nozzles))
                        .where(Pump.is_active.is_(True))
                        .order_by(Pump.number)
                    )
                ).all()
                active_ids = {p.id for p in pumps}

                nozzles: dict[uuid.UUID, NozzleInfo] = {}
                for pump in pumps:
                    if pump.id not in self._drivers:
                        self._drivers[pump.id] = SimulatedPumpDriver(pump.id, callback=self._on_event)
                        self._db_status[pump.id] = pump.status
                    for nozzle in pump.nozzles:
                        nozzles[nozzle.id] = NozzleInfo(
                            nozzle_id=nozzle.id,
                            pump_id=pump.id,
                            nozzle_number=nozzle.nozzle_number,
                            fuel_id=nozzle.fuel_id,
                            tank_id=nozzle.tank_id,
                        )
                self._nozzles = nozzles

            for pump_id in list(self._drivers):
                if pump_id in active_ids:
                    continue
                driver = self._drivers[pump_id]
                if driver.status().status in (PumpStatus.IDLE, PumpStatus.OFFLINE, PumpStatus.ERROR):
                    await driver.stop()
                    self._drivers.pop(pump_id, None)
                    self._db_status.pop(pump_id, None)
        except Exception:  # noqa: BLE001
            log.warning("Насосны жагсаалт шинэчлэхэд алдаа гарлаа", exc_info=True)

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #

    async def authorize(self, pump_id: uuid.UUID, nozzle_id: uuid.UUID, preset: Preset) -> uuid.UUID:
        driver = self._drivers.get(pump_id)
        if driver is None:
            raise ValueError("Насос холбогдоогүй байна")

        info = self._nozzles.get(nozzle_id)
        if info is None or info.pump_id != pump_id:
            raise ValueError("Хошуу олдсонгүй")

        if driver.status().status not in (PumpStatus.IDLE, PumpStatus.OFFLINE, PumpStatus.ERROR):
            raise ValueError("Насос завгүй байна")

        async with async_session_factory() as session:
            price = await session.scalar(select(Fuel.price_per_liter).where(Fuel.id == info.fuel_id))
            if price is None:
                raise ValueError("Түлш олдсонгүй")

            # Насосны салбарт өөр үнэ мөрдөж байвал түүгээр шатахуун түгээнэ.
            branch_id = await session.scalar(select(Pump.branch_id).where(Pump.id == pump_id))
            if branch_id is not None:
                from app.models.pricing import BranchPrice

                override = await session.scalar(
                    select(BranchPrice.price).where(
                        BranchPrice.branch_id == branch_id,
                        BranchPrice.fuel_id == info.fuel_id,
                    )
                )
                if override is not None:
                    price = override
            if Decimal(price) <= 0:
                raise ValueError("Түлшний үнэ тохируулаагүй байна")

            authorization_id = await driver.authorize(nozzle_id, preset, Decimal(price))

            await session.execute(
                update(Pump).where(Pump.id == pump_id).values(status=PumpStatus.AUTHORIZED)
            )
            await session.commit()

        self._db_status[pump_id] = PumpStatus.AUTHORIZED
        return authorization_id

    async def halt(self, pump_id: uuid.UUID) -> None:
        driver = self._drivers.get(pump_id)
        if driver is None:
            raise ValueError("Насос холбогдоогүй байна")
        await driver.halt()

    def snapshot(self) -> list[Telemetry]:
        return [driver.status() for driver in self._drivers.values()]

    def telemetry_for(self, pump_id: uuid.UUID) -> Telemetry | None:
        driver = self._drivers.get(pump_id)
        return driver.status() if driver is not None else None

    def has_pump(self, pump_id: uuid.UUID) -> bool:
        return pump_id in self._drivers

    @property
    def is_empty(self) -> bool:
        return not self._drivers

    # ------------------------------------------------------------------ #
    # Driver callback
    # ------------------------------------------------------------------ #

    async def _on_event(self, event: PumpEvent) -> None:
        try:
            if isinstance(event, FuelingComplete):
                await self._on_complete(event)
            else:
                await self._on_telemetry(event)
        except Exception:  # noqa: BLE001 — a callback must never break the pump
            log.exception("Насосны үйл явдал боловсруулахад алдаа гарлаа")

    async def _on_telemetry(self, telemetry: Telemetry) -> None:
        payload = {"type": "pump_status", **telemetry.as_dict()}
        await self._publish(payload)
        await self._sync_status(telemetry.pump_id, telemetry.status)

    async def _on_complete(self, event: FuelingComplete) -> None:
        await self._publish({"type": "fueling_complete", **event.as_dict()})

        info = self._nozzles.get(event.nozzle_id)

        # 1) Persist the mechanical counter and free the pump.
        try:
            async with async_session_factory() as session:
                await session.execute(
                    update(PumpNozzle)
                    .where(PumpNozzle.id == event.nozzle_id)
                    .values(totalizer=PumpNozzle.totalizer + event.liters)
                )
                await session.execute(
                    update(Pump).where(Pump.id == event.pump_id).values(status=PumpStatus.IDLE)
                )
                await session.commit()
            self._db_status[event.pump_id] = PumpStatus.IDLE
        except Exception:  # noqa: BLE001
            log.exception("Тоолуур/төлөв хадгалахад алдаа гарлаа: насос=%s", event.pump_id)

        # 2) Hand the fueling over to the POS (`POST /api/sales` reads this key).
        record = {
            "pump_id": str(event.pump_id),
            "nozzle_id": str(event.nozzle_id),
            "fuel_id": str(info.fuel_id) if info else None,
            "tank_id": str(info.tank_id) if info else None,
            "liters": str(event.liters),
            "amount": str(event.amount),
            "unit_price": str(event.unit_price),
        }
        try:
            await get_redis().setex(
                auth_key(event.authorization_id), AUTH_KEY_TTL_SECONDS, json.dumps(record)
            )
        except Exception:  # noqa: BLE001
            log.exception("Таталтын мэдээлэл Redis-д хадгалахад алдаа гарлаа: %s", event.authorization_id)

    async def _publish(self, payload: dict) -> None:
        try:
            await publish(PUMP_CHANNEL, payload)
        except Exception:  # noqa: BLE001 — Redis down must not stop fueling
            log.warning("Насосны мэдээлэл нийтлэхэд алдаа гарлаа", exc_info=True)

    async def _sync_status(self, pump_id: uuid.UUID, status: str) -> None:
        """Mirror the driver status into the DB, but only when it changed."""
        if self._db_status.get(pump_id) == status:
            return
        self._db_status[pump_id] = status
        try:
            async with async_session_factory() as session:
                await session.execute(update(Pump).where(Pump.id == pump_id).values(status=status))
                await session.commit()
        except Exception:  # noqa: BLE001
            self._db_status.pop(pump_id, None)
            log.warning("Насосны төлөв хадгалахад алдаа гарлаа: %s", pump_id, exc_info=True)
