"""Ээлжийн хаалтын батламж.

Нягтлан салбар бүрийн түгээгчийн хаалтыг хянаж, кассын зөрүүг засаад
батална. Батлагдсан хаалт цаашид засагдахгүй.

Revision ID: d5b18c3e97a4
Revises: c3f74a20d918
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "d5b18c3e97a4"
down_revision: str | None = "c3f74a20d918"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shift_closings",
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "shift_closings",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("shift_closings", sa.Column("approval_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("shift_closings", "approval_note")
    op.drop_column("shift_closings", "approved_at")
    op.drop_column("shift_closings", "approved_by")
