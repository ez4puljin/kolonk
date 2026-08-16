"""Буцаалтын тоо хэмжээг литрийн нарийвчлалд оруулах.

``refund_items.qty`` нь Numeric(18,2) байсан тул 3 оронтой түлшний мөрийг
бүтнээр нь буцаах боломжгүй байв: 31.034 л → 31.03 болж хуваарилсан дүн
борлуулалтынхаас зөрч «Буцаалтын дүн тооцоолсон дүнтэй тохирохгүй байна»
гэж унадаг байсан.  Одоо борлуулалтын мөртэй ижил Numeric(12,3).

Revision ID: a83f6c204e11
Revises: f2b81e4c7d95
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a83f6c204e11"
down_revision: str | None = "f2b81e4c7d95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "refund_items",
        "qty",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(12, 3),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "refund_items",
        "qty",
        existing_type=sa.Numeric(12, 3),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
