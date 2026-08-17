"""Салбар тус бүрийн дундаж өртөг.

Салбар бүр өөр үнээр татсан бол борлуулалтын өртөг (COGS), нөөцийн
үнэлгээ тухайн салбарынхаараа бодогдоно. Хуучин мөрүүдэд барааны глобал
дундаж өртгийг хуулна — ингэснээр миграцын мөчид нийт үнэлгээ яг хэвээр:
Σ(qty_салбар × cost) = Σ(qty_салбар) × cost = stock_qty × avg_cost.

Revision ID: e8c41d7b6a92
Revises: d5b18c3e97a4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e8c41d7b6a92"
down_revision: str | None = "d5b18c3e97a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_branch_stocks",
        sa.Column("avg_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
    )
    op.execute(
        """
        UPDATE product_branch_stocks AS pbs
        SET avg_cost = p.avg_cost
        FROM products AS p
        WHERE p.id = pbs.product_id
        """
    )


def downgrade() -> None:
    op.drop_column("product_branch_stocks", "avg_cost")
