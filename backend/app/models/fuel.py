import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import PumpStatus, ReadingType, TankMovementType
from app.models.base import Liters, Money, TimestampMixin, Totalizer, UnitCost, UUIDPKMixin


class Fuel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fuels"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name_mn: Mapped[str] = mapped_column(String(64), nullable=False)
    price_per_liter: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    color_hex: Mapped[str] = mapped_column(String(9), default="#2563EB", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tanks: Mapped[list["Tank"]] = relationship(back_populates="fuel")


class Tank(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tanks"

    #: Аль салбарынх вэ (олон салбарын тайлан, шүүлтэд ашиглана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    fuel_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"), nullable=False)
    capacity_l: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    current_l: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))
    avg_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    min_level_l: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    fuel: Mapped[Fuel] = relationship(back_populates="tanks", lazy="selectin")


class TankMovement(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "tank_movements"

    tank_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tanks.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False, default=TankMovementType.SALE)
    liters: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    balance_after_l: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(String(255))

    tank: Mapped[Tank] = relationship(lazy="selectin")


class Pump(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "pumps"
    #: Дугаар САЛБАР ДОТРОО давхардахгүй — салбар бүр «1-р насос»-той байна.
    __table_args__ = (UniqueConstraint("branch_id", "number", name="uq_pump_branch_number"),)

    #: Аль салбарынх вэ (олон салбарын тайлан, шүүлтэд ашиглана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Талбай дахь бодит байршил — тохиргооны зураглал ба ПОС-ын дараалалд.
    position_x: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    position_y: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=PumpStatus.IDLE)
    driver: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    nozzles: Mapped[list["PumpNozzle"]] = relationship(
        back_populates="pump", cascade="all, delete-orphan", lazy="selectin"
    )


class PumpNozzle(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "pump_nozzles"
    __table_args__ = (UniqueConstraint("pump_id", "nozzle_number", name="uq_pump_nozzle"),)

    pump_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pumps.id", ondelete="CASCADE"), nullable=False
    )
    nozzle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fuel_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"), nullable=False)
    tank_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tanks.id"), nullable=False)
    totalizer: Mapped[Decimal] = mapped_column(Totalizer, nullable=False, default=Decimal("0"))

    pump: Mapped[Pump] = relationship(back_populates="nozzles")
    fuel: Mapped[Fuel] = relationship(lazy="selectin")
    tank: Mapped[Tank] = relationship(lazy="selectin")


class TotalizerReading(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "totalizer_readings"

    nozzle_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pump_nozzles.id"), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("shifts.id"), index=True)
    reading: Mapped[Decimal] = mapped_column(Totalizer, nullable=False)
    reading_type: Mapped[str] = mapped_column(String(24), nullable=False, default=ReadingType.MANUAL)
    #: Заалт бүртгэх үеийн литрийн үнэ (түгээгчийн горимд сегментийн эх үнэ).
    price_per_liter: Mapped[Decimal | None] = mapped_column(Money)
    #: Нээлтийн заалт дээр — тухайн мөчид хошуун дээр байсан өмнөх хаалтын миль.
    #: Хоёрын зөрүү нь мэдэгдэлгүй түгээлт эсвэл буруу бичсэн хаалтыг илтгэнэ.
    prev_reading: Mapped[Decimal | None] = mapped_column(Totalizer)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    nozzle: Mapped[PumpNozzle] = relationship(lazy="selectin")
