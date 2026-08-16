"""Үйл ажиллагааны зардлын баримт.

Цалин, цахилгаан, түрээс, засвар зэрэг борлуулалттай шууд холбоогүй зардлыг
бүртгэнэ. Батлагдмагц ерөнхий дэвтэрт (`EXPENSE_POSTED`) бичигдэж, орлого
зардлын тайланд цэвэр ашгийг зөв гаргах боломж олгоно.

Бэлнээр төлсөн зардал нь ээлжийн байвал зохих кассын үлдэгдлээс автоматаар
хасагдана — `shift_service._other_cash_movement` нь `1101` дансны хөдөлгөөнийг
ерөнхий дэвтрээс уншдаг тул нэмэлт код шаардахгүй.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Sequence, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.enums import DocStatus
from app.models.base import Money, TimestampMixin, UUIDPKMixin

expense_number_seq = Sequence("expense_number_seq", start=1)


class Expense(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    #: Аль салбарынх вэ (олон салбарын тайлан, шүүлтэд ашиглана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    number: Mapped[int] = mapped_column(
        Integer,
        expense_number_seq,
        server_default=expense_number_seq.next_value(),
        nullable=False,
        index=True,
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    #: Зардлын данс (ACC.OPERATING_EXPENSES дотор байх ёстой).
    account_code: Mapped[str] = mapped_column(
        String(16), ForeignKey("accounts.code"), nullable=False, index=True
    )

    #: Төлсөн хэлбэр: `cash` (касс), `bank` (харилцах), `credit` (нийлүүлэгчийн өглөг).
    payment_method: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    #: НӨАТ-гүй дүн, НӨАТ, нийт төлсөн дүн.
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("suppliers.id")
    )
    #: `credit` төлбөрийн үед үүсэх өглөгийн нэхэмжлэх.
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ap_invoices.id")
    )
    #: Бэлнээр төлсөн бол аль ээлжийн кассаас гарсныг тэмдэглэнэ.
    shift_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("shifts.id"))
    #: `bank` төлбөрийн үед аль харилцах данснаас гарсан бэ.
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bank_accounts.id"), index=True
    )

    invoice_no: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DocStatus.DRAFT, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
