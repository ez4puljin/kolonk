"""Ээлжийн хаалтын ноорог — өдрийн турш бөглөсөн тос/бараа, зээл, өглөг төлөлт, зарлага.

* ``shifts.close_draft`` (JSONB) — түгээгч ээлжийн явцад бүртгэсэн мөрүүд;
  орой хаалтын wizard эндээс бөглөгдөнө. Хаалт хийгдэхэд цэвэрлэгдэнэ.
* ``shifts.close_draft_at`` — сүүлд хадгалсан цаг.

Revision ID: c9e1f3a5b7d2
Revises: b8d2f4a6c1e3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c9e1f3a5b7d2"
down_revision = "b8d2f4a6c1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shifts", sa.Column("close_draft", JSONB(), nullable=True))
    op.add_column("shifts", sa.Column("close_draft_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shifts", "close_draft_at")
    op.drop_column("shifts", "close_draft")
