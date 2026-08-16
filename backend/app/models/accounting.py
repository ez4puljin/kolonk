import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Sequence,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import AccountType, InvoiceStatus
from app.models.base import Money, TimestampMixin, UUIDPKMixin

entry_number_seq = Sequence("journal_entry_no_seq", start=1)


class Account(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name_mn: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False, default=AccountType.ASSET)
    is_postable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class JournalEntry(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "event_type", name="uq_journal_source_event"),
    )

    entry_no: Mapped[int] = mapped_column(
        Integer, entry_number_seq, server_default=entry_number_seq.next_value(), nullable=False, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin", order_by="JournalLine.line_no"
    )


class JournalLine(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit = 0 OR credit = 0", name="ck_journal_line_single_side"),
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_line_non_negative"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    account_code: Mapped[str] = mapped_column(String(16), ForeignKey("accounts.code"), nullable=False, index=True)
    debit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    memo: Mapped[str | None] = mapped_column(String(255))
    dim_fuel_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    dim_tank_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    dim_customer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    dim_supplier_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    #: 1110 мөрийг аль харилцах данстай холбох вэ.  Σ(данс) == 1110 үлдэгдэл.
    dim_bank_account_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")


class ApInvoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ap_invoices"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    invoice_no: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    amount_gross: Mapped[Decimal] = mapped_column(Money, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=InvoiceStatus.OPEN, index=True)

    supplier: Mapped["Supplier"] = relationship(lazy="selectin")  # noqa: F821


class ApPayment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ap_payments"

    ap_invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ap_invoices.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    paid_from: Mapped[str] = mapped_column(String(16), nullable=False, default="bank")
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))


class ArInvoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ar_invoices"
    __table_args__ = (UniqueConstraint("contract_id", "period_start", name="uq_ar_contract_period"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    invoice_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=InvoiceStatus.OPEN, index=True)
    lines: Mapped[list | None] = mapped_column(JSONB)

    customer: Mapped["Customer"] = relationship(lazy="selectin")  # noqa: F821


class ArPayment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ar_payments"

    ar_invoice_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ar_invoices.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    received_to: Mapped[str] = mapped_column(String(16), nullable=False, default="bank")
    #: `bank` руу хүлээн авсан бол аль харилцах данс вэ.
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bank_accounts.id"), index=True
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
