"""Салбарын үнийн давхарга.

Түлш болон барааны СУУРЬ үнэ ``fuels.price_per_liter`` / ``products.price``
хэвээр.  Тухайн салбарт өөр үнэ мөрдөх бол энд override мөр үүснэ — байхгүй
бол суурь үнэ үйлчилнэ.  Мөр зөвхөн үнийн өөрчлөлтийн батлах урсгалаар
(``price_change_service``) бичигдэнэ.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import Money, TimestampMixin, UUIDPKMixin


class BranchPrice(UUIDPKMixin, TimestampMixin, Base):
    """Нэг салбарт үйлчлэх түлш/барааны зарах үнэ (суурь үнийг дарна)."""

    __tablename__ = "branch_prices"
    __table_args__ = (
        UniqueConstraint("branch_id", "fuel_id", name="uq_branch_fuel_price"),
        UniqueConstraint("branch_id", "product_id", name="uq_branch_product_price"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    fuel_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fuels.id"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
