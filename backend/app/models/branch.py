"""Салбар — олон цэгт өргөжих суурь.

v1-д нэг салбар ("Төв салбар") seed-ээр үүсэж, бүх бичлэг түүнд харьяалагдана.
Шинэ салбар нэмэхэд тайлан, шүүлт нь ямар ч кодын өөрчлөлтгүйгээр ажиллана.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class Branch(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "branches"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(32))
    #: Тухайн салбарын менежер (заавал биш).
    manager_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- Ээлж нээх журам (салбар бүр өөр байж болно) ---
    #: Хошуу бүрийн миль заавал бүртгэгдсэн байх ёстой эсэх.
    require_open_mile: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    #: Миль, бэлэн мөнгөнд зураг заавал хавсаргах эсэх.
    require_open_photo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
