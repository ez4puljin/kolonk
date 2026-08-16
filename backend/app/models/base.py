import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

# Shared column types — money/liters are Decimal everywhere, never float.
Money = Numeric(18, 2)
UnitCost = Numeric(18, 6)
Liters = Numeric(12, 3)
Totalizer = Numeric(14, 3)

ZERO = Decimal("0.00")


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
