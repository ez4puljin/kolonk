import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ItemType, PaymentMethod, SaleStatus, SaleType
from app.models.base import Liters, Money, TimestampMixin, UnitCost, UUIDPKMixin

sale_number_seq = Sequence("sale_number_seq", start=1)


class Sale(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales"

    #: Аль салбарынх вэ (олон салбарын тайлан, шүүлтэд ашиглана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    number: Mapped[int] = mapped_column(
        BigInteger, sale_number_seq, server_default=sale_number_seq.next_value(), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("shifts.id"), nullable=False, index=True
    )
    cashier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(16), nullable=False, default=SaleType.FUEL)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SaleStatus.COMPLETED, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    cogs_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("customers.id"))
    contract_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("contracts.id"))
    note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", lazy="selectin", order_by="SaleItem.line_no"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )


class SaleItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sale_items"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, default=ItemType.FUEL)
    fuel_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"))
    tank_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tanks.id"))
    pump_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("pumps.id"))
    nozzle_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("pump_nozzles.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id"))
    name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    cogs_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    refunded_qty: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))

    sale: Mapped[Sale] = relationship(back_populates="items")


class Payment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(16), nullable=False, default=PaymentMethod.CASH, index=True)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("contracts.id"))
    voucher_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("vouchers.id"))
    prepaid_card_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("prepaid_cards.id"))
    received: Mapped[Decimal | None] = mapped_column(Money)
    change_given: Mapped[Decimal | None] = mapped_column(Money)
    ref_no: Mapped[str | None] = mapped_column(String(64))

    sale: Mapped[Sale] = relationship(back_populates="payments")
