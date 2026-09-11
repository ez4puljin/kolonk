"""Салбар хоорондын тооцооны дэвтэр.

Толгой (Админ) нийлүүлэгчээс түлшийг бөөнд нь авч, машин салбар бүрд буулгана.
Түгээлт бүрд салбарын **өр** (charge) үүсэж, салбар толгойн данс руу мөнгө
шилжүүлэхэд **төлбөр** (payment) бүртгэгдэнэ.  Салбарын үлдэгдэл = Σcharge −
Σpayment.

Нэг хуулийн этгээдийн доторх тооцоо тул энэ дэвтэр өөрөө ерөнхий дэвтрийн
данс биш; харин төлбөрийн мөр нь мөнгөний бодит хөдөлгөөнийг (салбарын касс
→ толгойн харилцах) `BRANCH_SETTLEMENT_PAID` бичилтээр журналд тусгана.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.enums import SettlementEntryType
from app.models.base import Money, TimestampMixin, UUIDPKMixin


class BranchSettlement(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "branch_settlements"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(
        String(8), nullable=False, default=SettlementEntryType.CHARGE, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)

    #: Charge мөрийн эх баримт (fuel_receipt — түгээлт).
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)

    #: Payment мөр: мөнгө хаанаас гарсан — ``cash`` (салбарын касс) эсвэл ``bank``.
    paid_from: Mapped[str | None] = mapped_column(String(8))
    #: ``bank``-аас төлсөн бол аль данснаас.
    from_bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bank_accounts.id")
    )
    #: Мөнгө орсон толгойн харилцах данс.
    to_bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bank_accounts.id")
    )

    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
