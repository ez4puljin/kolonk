"""Эхний үлдэгдэл: салбарын нэг удаагийн нээлт, гэрээний авлагын эхний үлдэгдэл.

* ``branches.opening_done_at/by`` — Админ панел → Салбарын тохиргоо → «Эхний
  үлдэгдэл»-ээр савны эхний үлдэгдэл, хошууны одоогийн милийг НЭГ УДАА
  оруулсныг тэмдэглэнэ; дахин оруулах боломжгүй.
* ``contracts.opening_balance/opening_date`` — Excel импортоор (нэр, утас,
  авлага, огноо) орж ирсэн авлагын эхний үлдэгдэл; тооцооны хуулгад эхний
  үлдэгдлээр харагдана, журналд Дт 1201 / Кт 3101.

Revision ID: a4c7e9b2d6f1
Revises: f3b8d2c7a1e4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a4c7e9b2d6f1"
down_revision = "f3b8d2c7a1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("opening_done_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "branches",
        sa.Column("opening_done_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column("contracts", sa.Column("opening_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("contracts", "opening_date")
    op.drop_column("contracts", "opening_balance")
    op.drop_column("branches", "opening_done_by")
    op.drop_column("branches", "opening_done_at")
