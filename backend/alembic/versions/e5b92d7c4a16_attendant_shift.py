"""Түгээгчийн өдрийн ээлж.

ПОС-гүй горим: түгээгч өглөө бэлэн мөнгө + насос бүрийн миль (тоолуур) зурагтай
бүртгэж нээгээд, орой нэг дор хаадаг.  Хаалтад миль×үнэ (үнийн өөрчлөлтийн
тэмдэглэлээр сегментчилсэн) нийт түгээлт бодогдож, settlement/зээл/бэлэн
хуваарилалттай тулгагдана.

* ``shift_attachments`` — нээлт/хаалт/settlement/үнийн тэмдэглэлийн зураг;
* ``shift_price_marks`` — өдрийн дундуур үнэ өөрчлөгдөхөд аль мильд шинэ үнэ
  эхэлснийг тэмдэглэнэ;
* ``shift_closings`` — хаалтын баримт (settlement НӨАТ-тэй/гүй, үүссэн
  борлуулалтын холбоос);
* ``totalizer_readings.price_per_liter`` — нээлтийн үеийн үнийн snapshot;
* ``price_changes.effective_date`` — тосны үнийн өөрчлөлт маргаашнаас
  хэрэгжих боломж (worker өдөр бүр хугацаа болсныг нь хэрэгжүүлнэ).

Revision ID: e5b92d7c4a16
Revises: d1a37c5b8e04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "e5b92d7c4a16"
down_revision: str | None = "d1a37c5b8e04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shift_attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "shift_id", UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", sa.String(24), nullable=False, server_default="open"),
        sa.Column("ref_id", UUID(as_uuid=True), nullable=True),
        sa.Column("file_name", sa.String(128), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_shift_attachments_shift_id", "shift_attachments", ["shift_id"])

    op.create_table(
        "shift_price_marks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "shift_id", UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("nozzle_id", UUID(as_uuid=True), sa.ForeignKey("pump_nozzles.id"), nullable=False),
        sa.Column("reading", sa.Numeric(14, 3), nullable=False),
        sa.Column("old_price", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("new_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.String(255)),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_shift_price_marks_shift_id", "shift_price_marks", ["shift_id"])
    op.create_index("ix_shift_price_marks_nozzle_id", "shift_price_marks", ["nozzle_id"])

    op.create_table(
        "shift_closings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "shift_id", UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, unique=True,
        ),
        sa.Column("settlement_vat", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("settlement_novat", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("fuel_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("oil_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("fuel_sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id")),
        sa.Column("oil_sale_id", UUID(as_uuid=True), sa.ForeignKey("sales.id")),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Нээлтийн заалттай хамт үнийн snapshot — сегментийн эхний үнэ болно.
    op.add_column(
        "totalizer_readings",
        sa.Column("price_per_liter", sa.Numeric(18, 2), nullable=True),
    )

    # Тосны үнийн өөрчлөлт маргаашнаас хэрэгжих боломж.
    op.add_column("price_changes", sa.Column("effective_date", sa.Date(), nullable=True))
    op.add_column("price_changes", sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True))
    # Хуучин батлагдсан өөрчлөлтүүд шийдвэрийн мөчид хэрэгжсэн.
    op.execute("UPDATE price_changes SET applied_at = decided_at WHERE status = 'approved'")


def downgrade() -> None:
    op.drop_column("price_changes", "applied_at")
    op.drop_column("price_changes", "effective_date")
    op.drop_column("totalizer_readings", "price_per_liter")
    op.drop_table("shift_closings")
    op.drop_table("shift_price_marks")
    op.drop_table("shift_attachments")
