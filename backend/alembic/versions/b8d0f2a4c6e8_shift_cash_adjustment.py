"""Ээлжийн кассын зөрүүний админы гар засвар (системийн алдаа).

* ``shifts.cash_adjustment`` — байвал зохих бэлэн мөнгөнд нэмэх засвар;
* ``shifts.cash_adjustment_note`` / ``cash_adjusted_by`` / ``cash_adjusted_at``
  — шалтгаан, хэн, хэзээ.

Revision ID: b8d0f2a4c6e8
Revises: a7c9e1f3b5d7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b8d0f2a4c6e8"
down_revision = "a7c9e1f3b5d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shifts",
        sa.Column("cash_adjustment", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column("shifts", sa.Column("cash_adjustment_note", sa.Text(), nullable=True))
    op.add_column(
        "shifts",
        sa.Column(
            "cash_adjusted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column("shifts", sa.Column("cash_adjusted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shifts", "cash_adjusted_at")
    op.drop_column("shifts", "cash_adjusted_by")
    op.drop_column("shifts", "cash_adjustment_note")
    op.drop_column("shifts", "cash_adjustment")
