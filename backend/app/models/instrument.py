import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import CardStatus, CardTxType, VoucherStatus
from app.models.base import Money, TimestampMixin, UUIDPKMixin


class Voucher(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "vouchers"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    face_value: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=VoucherStatus.ACTIVE, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("customers.id"))
    sold_sale_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    redeemed_sale_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PrepaidCard(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "prepaid_cards"

    card_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    holder_name: Mapped[str | None] = mapped_column(String(128))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("customers.id"))
    balance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CardStatus.ACTIVE)

    transactions: Mapped[list["PrepaidCardTransaction"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class PrepaidCardTransaction(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "prepaid_card_transactions"

    card_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("prepaid_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tx_type: Mapped[str] = mapped_column(String(16), nullable=False, default=CardTxType.REDEEM)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Money, nullable=False)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    card: Mapped[PrepaidCard] = relationship(back_populates="transactions")
