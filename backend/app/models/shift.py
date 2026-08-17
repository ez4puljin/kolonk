import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ShiftStatus
from app.models.base import Liters, Money, TimestampMixin, UUIDPKMixin


class Shift(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    #: Аль салбарынх вэ (олон салбарын тайлан, шүүлтэд ашиглана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ShiftStatus.OPEN, index=True)
    opened_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_cash: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    declared_cash: Mapped[Decimal | None] = mapped_column(Money)
    expected_cash: Mapped[Decimal | None] = mapped_column(Money)
    cash_over_short: Mapped[Decimal | None] = mapped_column(Money)
    note: Mapped[str | None] = mapped_column(Text)

    tank_levels: Mapped[list["ShiftTankLevel"]] = relationship(
        back_populates="shift", cascade="all, delete-orphan", lazy="selectin"
    )


class ShiftAttachment(UUIDPKMixin, TimestampMixin, Base):
    """Ээлжид хавсаргасан зураг (нээлт/хаалтын миль, settlement-ийн баримт).

    Түгээгчийн горимд миль, кассын тоолол, settlement-ийг заавал зургаар
    баталгаажуулдаг — маргаан гарахад нотолгоо болно.
    """

    __tablename__ = "shift_attachments"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Юуны зураг вэ: open / close / settlement / price_mark.
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    #: Тодорхой бичлэгт (жишээ нь үнийн тэмдэглэлд) хамаарвал түүний id.
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    #: Диск дээрх файлын нэр (uploads/shift_photos/{shift_id}/ доторх).
    file_name: Mapped[str] = mapped_column(String(128), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))


class ShiftPriceMark(UUIDPKMixin, TimestampMixin, Base):
    """Өдрийн дундуур үнэ өөрчлөгдөхөд аль мильд шинэ үнэ эхэлснийг тэмдэглэнэ.

    Хаалтын тооцоо хошуу бүрийг сегментчилнэ:
    ``нээлтийн миль → тэмдэглэлийн миль`` хуучин үнээр,
    ``тэмдэглэлийн миль → хаалтын миль`` шинэ үнээр.
    """

    __tablename__ = "shift_price_marks"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nozzle_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pump_nozzles.id"), nullable=False, index=True
    )
    #: Шинэ үнэ энэ мильээс эхэлж үйлчилнэ.
    reading: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    old_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    new_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))


class ShiftClosing(UUIDPKMixin, TimestampMixin, Base):
    """Түгээгчийн өдрийн хаалтын баримт.

    Settlement (банкны терминалын тооцоо) болон хаалтад үүссэн нэгдсэн
    борлуулалтуудын холбоосыг хадгална — тайлан, тулгалтад ашиглагдана.
    """

    __tablename__ = "shift_closings"

    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    #: Терминалын тооцоо — НӨАТ-тэй / НӨАТ-гүй борлуулалтын дүн.
    settlement_vat: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    settlement_novat: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Харилцагчид дансаар шилжүүлсэн дүн — банкинд шууд орсон.
    transfer_total: Mapped[Decimal] = mapped_column(
        Money, nullable=False, default=Decimal("0"), server_default="0"
    )
    #: Миль×үнэ-ээр бодогдсон түлшний нийт түгээлт.
    fuel_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Зээлээр (гэрээт) өгсөн нийт дүн.
    credit_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Тос, барааны борлуулалтын нийт дүн.
    oil_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Хаалтад үүссэн нэгдсэн түлшний борлуулалт.
    fuel_sale_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sales.id"))
    #: Хаалтад үүссэн тос/барааны борлуулалт.
    oil_sale_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sales.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    #: Нягтлан хянаж баталсан мөч — батлагдсан хаалтыг засах боломжгүй.
    approved_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(Text)


class ShiftTankLevel(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "shift_tank_levels"
    __table_args__ = (UniqueConstraint("shift_id", "tank_id", "phase", name="uq_shift_tank_phase"),)

    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    tank_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tanks.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(8), nullable=False)
    dip_liters: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    book_liters: Mapped[Decimal | None] = mapped_column(Liters)
    variance_l: Mapped[Decimal | None] = mapped_column(Liters)

    shift: Mapped[Shift] = relationship(back_populates="tank_levels")
