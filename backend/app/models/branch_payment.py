"""Салбарын төлбөрийн хэлбэрийн тохиргоо.

Салбар бүр өөрийн боломжтой төлбөрийн хэрэгслийг тохируулна (жишээ нь алслагдсан
цэгт QR, гэрээт байхгүй байж болно).  **Мөр байхгүй бол бүх хэлбэр нээлттэй** —
шинэ салбар ямар ч тохиргоогүйгээр ажиллана.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class BranchPaymentMethod(UUIDPKMixin, TimestampMixin, Base):
    """Нэг салбарт нэг төлбөрийн хэрэгсэл идэвхтэй эсэх."""

    __tablename__ = "branch_payment_methods"
    __table_args__ = (
        UniqueConstraint("branch_id", "method", name="uq_branch_payment_method"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: ``PaymentMethod`` утга — cash / card / qr / contract / voucher / prepaid.
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
