"""Өдрийн хаалтын цонхны хуулбар — түгээгч юу бөглөж, ямар тулгалт харсан бэ.

* ``shift_closings.close_input`` (JSONB) — илгээсэн өгөгдөл + түгээгчийн
  дэлгэц дээрх тулгалт (тушаах ёстой / тушаасан / зөрүү, бүх мөр). Ээлжийн
  тайланд «Өдрийн хаалтын цонх» хэсэгт серверийн бүртгэлтэй харьцуулна.

Revision ID: e5a7c9d1f3b2
Revises: d4f6a8b0c2e1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5a7c9d1f3b2"
down_revision = "d4f6a8b0c2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shift_closings", sa.Column("close_input", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("shift_closings", "close_input")
