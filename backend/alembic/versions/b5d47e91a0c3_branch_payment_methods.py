"""Салбарын төлбөрийн хэлбэрийн тохиргоо.

Мөр байхгүй салбарт бүх хэлбэр нээлттэй тул хуучин өгөгдлийг backfill хийхгүй.

Revision ID: b5d47e91a0c3
Revises: a83f6c204e11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "b5d47e91a0c3"
down_revision: str | None = "a83f6c204e11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "branch_payment_methods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "branch_id", UUID(as_uuid=True),
            sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("branch_id", "method", name="uq_branch_payment_method"),
    )
    op.create_index(
        "ix_branch_payment_methods_branch_id", "branch_payment_methods", ["branch_id"]
    )


def downgrade() -> None:
    op.drop_table("branch_payment_methods")
