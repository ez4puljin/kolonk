import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ContractStatus, CustomerType
from app.models.base import Money, TimestampMixin, UUIDPKMixin


class Supplier(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    register_no: Mapped[str | None] = mapped_column(String(32))
    phone: Mapped[str | None] = mapped_column(String(32))
    bank_account: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Customer(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    #: Аль салбарын харилцагч вэ (мэдээллийн — бүх салбарт зээлээр авч болно).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )
    #: Иргэний овог (байгууллагад хоосон).
    last_name: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    register_no: Mapped[str | None] = mapped_column(String(32))
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    phone2: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(128))
    #: Байршил: аймаг/хот ба сум/дүүрэг (жишээ: Хөвсгөл / Цагаан-Уул).
    province: Mapped[str | None] = mapped_column(String(64), index=True)
    district: Mapped[str | None] = mapped_column(String(64), index=True)
    #: Гэрээнд заасан зээлийн лимит (мэдээллийн — тооцооны лимит гэрээн дээрээ).
    credit_limit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Лимитгүй — энэ харилцагчийн бүх гэрээнд зээлийн лимит шалгагдахгүй.
    credit_unlimited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    #: Сканнердсан гэрээний PDF файлын нэр (uploads доторх).
    contract_file: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(16), nullable=False, default=CustomerType.B2B)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    contracts: Mapped[list["Contract"]] = relationship(back_populates="customer", lazy="selectin")


class Contract(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "contracts"

    customer_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    contract_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    credit_limit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    balance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    price_discount_per_l: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    billing_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ContractStatus.ACTIVE)
    #: Системд шилжихэд импортоор орж ирсэн авлагын эхний үлдэгдэл (балансад
    #: багтсан, тооцооны хуулгад «Эхний үлдэгдэл» мөрөөр гарна).
    opening_balance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    opening_date: Mapped[date | None] = mapped_column(Date)

    customer: Mapped[Customer] = relationship(back_populates="contracts", lazy="selectin")
