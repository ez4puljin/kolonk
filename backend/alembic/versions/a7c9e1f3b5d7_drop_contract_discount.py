"""Гэрээний литр тутмын үнийн хөнгөлөлтийг устгав.

Гэрээт харилцагч түлшийг колонкийн (жагсаалтын) үнээр авна — хөнгөлөлтийн
ойлголт системээс бүрмөсөн хасагдсан (``contracts.price_discount_per_l``).

Revision ID: a7c9e1f3b5d7
Revises: e5a7c9d1f3b2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7c9e1f3b5d7"
down_revision = "e5a7c9d1f3b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("contracts", "price_discount_per_l")


def downgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("price_discount_per_l", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
