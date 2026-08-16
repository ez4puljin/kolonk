import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ApprovalStatus, RefundType
from app.models.base import Liters, Money, TimestampMixin, UUIDPKMixin


class PriceChange(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "price_changes"

    target_type: Mapped[str] = mapped_column(String(16), nullable=False, default="fuel")
    #: Аль салбарт үйлчлэх вэ. NULL = бүх салбар (суурь үнэ солигдоно).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )
    fuel_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id"))
    old_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ApprovalStatus.PENDING, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    #: Аль өдрөөс хэрэгжих вэ (NULL = батламагц шууд). Тосны үнийн өөрчлөлтийг
    #: маргаашнаас эхлүүлэхэд ашиглана — өнөөдрийн борлуулалт хуучин үнээрээ явна.
    effective_date: Mapped[date | None] = mapped_column(Date)
    #: Үнэ бодитоор солигдсон мөч (хойшлуулсан өөрчлөлтөд worker бөглөнө).
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Refund(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "refunds"

    sale_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sales.id"), nullable=False, index=True)
    refund_type: Mapped[str] = mapped_column(String(16), nullable=False, default=RefundType.FULL)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    cogs_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    reason: Mapped[str | None] = mapped_column(Text)
    restock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    refund_method: Mapped[str] = mapped_column(String(16), nullable=False, default="cash")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ApprovalStatus.PENDING, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    #: Аль өдрөөс хэрэгжих вэ (NULL = батламагц шууд). Тосны үнийн өөрчлөлтийг
    #: маргаашнаас эхлүүлэхэд ашиглана — өнөөдрийн борлуулалт хуучин үнээрээ явна.
    effective_date: Mapped[date | None] = mapped_column(Date)
    #: Үнэ бодитоор солигдсон мөч (хойшлуулсан өөрчлөлтөд worker бөглөнө).
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shift_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("shifts.id"))

    items: Mapped[list["RefundItem"]] = relationship(
        back_populates="refund", cascade="all, delete-orphan", lazy="selectin"
    )


class RefundItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "refund_items"

    refund_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("refunds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sale_item_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sale_items.id"), nullable=False)
    #: Литр 3 оронтой (Numeric(12,3)) — борлуулалтын мөртэй ижил нарийвчлал.
    #: 2 орон байсан үед 31.034 л-ийн бүтэн буцаалт 31.03 болж дүн зөрдөг байв.
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cogs_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    refund: Mapped[Refund] = relationship(back_populates="items")
