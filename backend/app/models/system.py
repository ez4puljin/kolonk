import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.enums import EbarimtStatus
from app.models.base import TimestampMixin, UUIDPKMixin


class EbarimtQueue(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "ebarimt_queue"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sales.id"), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=EbarimtStatus.PENDING, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    receipt_id: Mapped[str | None] = mapped_column(String(64))
    qr_data: Mapped[str | None] = mapped_column(Text)
    lottery_no: Mapped[str | None] = mapped_column(String(32))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))


class SyncOutbox(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sync_outbox"

    aggregate_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
