"""Өдрийн хаалтад шилжүүлгийн дүн.

Түгээгч өдрийн орлогоо бэлэн мөнгө, Settlement (карт), шилжүүлэг гэсэн
3 сувгаар тушаадаг. Хуучин хаалтуудад шилжүүлэг байгаагүй тул 0-ээр бөглөнө.

Revision ID: c3f74a20d918
Revises: e5b92d7c4a16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c3f74a20d918"
down_revision: str | None = "e5b92d7c4a16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shift_closings",
        sa.Column("transfer_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("shift_closings", "transfer_total")
