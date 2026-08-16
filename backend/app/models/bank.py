"""Банкны данс ба банкны хуулга.

Хуулгын гүйлгээг манай бүртгэлд шууд буулгана:

* **орлого (кредит)** → гэрээт харилцагчийн авлагын төлбөр (``AR_RECEIPT``);
* **зарлага (дебит)** → үйл ажиллагааны зардал (``EXPENSE_POSTED``).

Журналын бичилтийг тухайн модулиудын үйлчилгээ хийдэг тул дансны үлдэгдэл,
харилцагчийн өр, авлагын дэвтэр бүгд өөрөө зөв хөдөлнө.  Энэ модуль зөвхөн
хуулгын мөрийг үүссэн баримттай холбоно.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import Money, TimestampMixin, UUIDPKMixin


class BankAccount(UUIDPKMixin, TimestampMixin, Base):
    """Байгууллагын харилцах данс.

    Ерөнхий дэвтэрт бүх данс ``1110 Банк``-т нэгтгэгдэнэ; данс тус бүрийн
    үлдэгдлийг ``journal_lines.dim_bank_account_id`` хэмжүүрээр гаргана.
    Ингэснээр Σ(дансны үлдэгдэл) == 1110 үлдэгдэл гэсэн инвариант хадгалагдана.
    """

    __tablename__ = "bank_accounts"
    __table_args__ = (UniqueConstraint("account_number", name="uq_bank_account_number"),)

    #: Аль салбарынх вэ (хоосон бол бүх салбарын нийтийн данс).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    bank_name: Mapped[str] = mapped_column(String(64), nullable=False)
    account_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    holder_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="MNT")

    #: Систем ашиглаж эхлэхийн өмнөх үлдэгдэл — ерөнхий дэвтэрт байхгүй.
    opening_balance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: Банкны шимтгэлийг анхдагчаар энэ данснаас хаах эсэх.
    is_fee_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(Text)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BankStatement(UUIDPKMixin, TimestampMixin, Base):
    """Банкнаас татсан нэг Excel хуулга."""

    __tablename__ = "bank_statements"

    #: Файлын нэрнээс ялгаж авсан дансны дугаар (манай данстай тулгахад).
    account_number: Mapped[str] = mapped_column(String(32), nullable=False, default="", index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="MNT")
    date_from: Mapped[date | None] = mapped_column(Date, index=True)
    date_to: Mapped[date | None] = mapped_column(Date)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )

    #: Дансны дугаараар автоматаар холбогдоно; олдохгүй бол гараар сонгоно.
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bank_accounts.id"), index=True
    )

    #: Шимтгэлийн мөрүүдийг нэгтгэж үүсгэсэн ганц зардал.  Шимтгэл олон удаа
    #: бага дүнгээр суудаг тул мөр бүрээр нь биш, нийлбэрээр нь хаана.
    fee_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id"), unique=True
    )

    transactions: Mapped[list["BankTransaction"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan", lazy="selectin"
    )


class BankTransaction(UUIDPKMixin, TimestampMixin, Base):
    """Хуулгын нэг мөр."""

    __tablename__ = "bank_transactions"

    statement_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bank_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    statement: Mapped[BankStatement] = relationship(back_populates="transactions")

    # --- Банкнаас ирсэн өгөгдөл (өөрчлөгдөхгүй) ---
    txn_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    debit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    bank_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    bank_counterpart: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_fee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Хэрэглэгчийн бөглөх хэсэг ---
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: Орлогын мөр — аль харилцагчийн (гэрээний) авлага хаагдах вэ.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id"), index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("contracts.id"), index=True
    )

    #: Зарлагын мөр — аль зардлын ангилалд (данс) бүртгэгдэх вэ.
    expense_account_code: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("accounts.code")
    )

    # --- Бүртгэсний дараах холбоос (буцаахад цэвэрлэгдэнэ) ---
    ar_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ar_payments.id"), unique=True
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id"), unique=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BankStatementConfig(UUIDPKMixin, TimestampMixin, Base):
    """Хуулга оруулахад мөрүүдийг урьдчилж бөглөх тохиргоо (нэг мөр)."""

    __tablename__ = "bank_statement_config"

    #: ПОС-ын тооцоо (SETTLEMENT) ямар харилцагчийн төлбөр болох вэ.
    settlement_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id")
    )
    settlement_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("contracts.id")
    )
    settlement_description: Mapped[str] = mapped_column(
        Text, nullable=False, default="ПОС орлого"
    )

    #: Банкны шимтгэл ямар зардлын ангилалд бүртгэгдэх вэ.
    fee_account_code: Mapped[str | None] = mapped_column(String(16), ForeignKey("accounts.code"))
    fee_description: Mapped[str] = mapped_column(Text, nullable=False, default="Банкны шимтгэл")
