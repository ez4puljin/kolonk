"""Ваучер, урьдчилсан картыг өгөгдлийн сангаас бүрмөсөн устгах.

Функц нь кодоос аль хэдийн хасагдсан. Энэ миграц үлдсэн МӨРҮҮДИЙГ цэвэрлэнэ:

  * ``voucher`` / ``prepaid`` эх сурвалжтай журналын бичилтүүд — бичилт
    БҮТНЭЭР устдаг тул дебит/кредит тэнцвэр хэвээр (демо картын цэнэглэлт
    1 000 000₮ — касс тэр хэмжээгээр буурна, 2302 өр цэвэрлэгдэнэ);
  * 2301, 2302 дансууд (цаашид хөдөлгөөнгүй);
  * ``payments.voucher_id`` / ``prepaid_card_id`` багана (бүгд NULL);
  * ``prepaid_card_transactions``, ``prepaid_cards``, ``vouchers`` хүснэгт;
  * харгалзах sync_outbox болон audit_log мөрүүд.

Буцаах боломжгүй (өгөгдөл устдаг) — downgrade зөвхөн хоосон хүснэгтүүдийг
сэргээнэ.

Revision ID: a2f96e1c47d3
Revises: f19d3c85b7e2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "a2f96e1c47d3"
down_revision: str | None = "f19d3c85b7e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Журналын бичилтүүд — мөрүүд нь cascade-аар устана.
    op.execute("DELETE FROM journal_entries WHERE source_type IN ('voucher', 'prepaid')")

    # 2. Дансны төлөвлөгөөнөөс ваучер/картын өр төлбөрийн данс.
    op.execute("DELETE FROM accounts WHERE code IN ('2301', '2302')")

    # 3. Борлуулалтын төлбөрийн холбоос (бүгд NULL — ашиглагдаж байгаагүй).
    op.drop_column("payments", "voucher_id")
    op.drop_column("payments", "prepaid_card_id")

    # 4. Хүснэгтүүд.
    op.drop_table("prepaid_card_transactions")
    op.drop_table("prepaid_cards")
    op.drop_table("vouchers")

    # 5. Үйл явдал, аудитын үлдэгдэл.
    op.execute("DELETE FROM sync_outbox WHERE event_type IN ('VOUCHER_SOLD', 'PREPAID_TOPUP')")
    op.execute("DELETE FROM audit_logs WHERE entity_type IN ('voucher', 'prepaid_card')")


def downgrade() -> None:
    """Зөвхөн бүтцийг сэргээнэ — устсан өгөгдөл эргэж ирэхгүй."""
    op.create_table(
        "vouchers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("face_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("sold_sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id")),
        sa.Column("redeemed_sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id")),
        sa.Column("sold_at", sa.DateTime(timezone=True)),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "prepaid_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("card_no", sa.String(32), nullable=False, unique=True),
        sa.Column("holder_name", sa.String(128)),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "prepaid_card_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "card_id",
            UUID(as_uuid=True),
            sa.ForeignKey("prepaid_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tx_type", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("payments", sa.Column("voucher_id", UUID(as_uuid=True), sa.ForeignKey("vouchers.id")))
    op.add_column(
        "payments", sa.Column("prepaid_card_id", UUID(as_uuid=True), sa.ForeignKey("prepaid_cards.id"))
    )
