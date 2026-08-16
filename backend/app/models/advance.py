"""Ажилтанд олгосон урьдчилгаа (цалингаас суутгагдана)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import Money, TimestampMixin, UUIDPKMixin


class EmployeeAdvance(UUIDPKMixin, TimestampMixin, Base):
    """Урьдчилгаа олгосон баримт — 1205 дансанд авлага үүснэ."""

    __tablename__ = "employee_advances"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True
    )
    advance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: `cash` эсвэл `bank`
    paid_from: Mapped[str] = mapped_column(String(16), nullable=False, default="cash")
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
