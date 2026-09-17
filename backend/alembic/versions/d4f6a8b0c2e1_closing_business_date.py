"""Хаалтын бизнес огноо — батлахдаа ээлжийн огноог засах.

* ``shift_closings.business_date`` — хаалт хожуу хийгдсэн (жишээ: 9/12-ны
  ээлжийг 9/16-нд хаасан) үед нягтлан батлахдаа зөв өдрийг зааж өгнө.
  Хоосон бол ээлж нээсэн огноо ашиглагдана.

Revision ID: d4f6a8b0c2e1
Revises: c9e1f3a5b7d2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4f6a8b0c2e1"
down_revision = "c9e1f3a5b7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shift_closings", sa.Column("business_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("shift_closings", "business_date")
