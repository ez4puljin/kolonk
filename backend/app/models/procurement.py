import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, Sequence, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import DocStatus
from app.models.base import Liters, Money, TimestampMixin, UnitCost, UUIDPKMixin

receipt_number_seq = Sequence("receipt_number_seq", start=1)
purchase_number_seq = Sequence("purchase_number_seq", start=1)


class FuelReceipt(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fuel_receipts"

    number: Mapped[int] = mapped_column(
        Integer, receipt_number_seq, server_default=receipt_number_seq.next_value(), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    tank_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tanks.id"), nullable=False)
    fuel_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    liters: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False)
    freight_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    density: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total_gross: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    landed_unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DocStatus.DRAFT, index=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ap_invoices.id"))
    note: Mapped[str | None] = mapped_column(Text)


class Purchase(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchases"

    number: Mapped[int] = mapped_column(
        Integer, purchase_number_seq, server_default=purchase_number_seq.next_value(), nullable=False, index=True
    )
    #: Бараа аль салбарын нөөцөд орох вэ (хоосон бол үндсэн салбар).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total_gross: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DocStatus.DRAFT, index=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ap_invoices.id"))
    note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_items"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)

    purchase: Mapped[Purchase] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="selectin")  # noqa: F821
