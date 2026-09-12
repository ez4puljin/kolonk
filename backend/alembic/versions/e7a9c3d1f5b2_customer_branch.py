"""Харилцагчийн салбар — ``customers.branch_id``.

Түгээгч өдрийн хаалтын үед шинэ харилцагч үүсгэхэд тухайн салбарт нь
харьяалуулна; Харилцагч цэснээс засаж болно. Хуучин харилцагчдыг анхны
борлуулалтын салбараар нөхнө (мэдээллийн талбар — зээлийн эрхэд нөлөөлөхгүй).

Revision ID: e7a9c3d1f5b2
Revises: d1e5a7c3b2f4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "e7a9c3d1f5b2"
down_revision: str | None = "d1e5a7c3b2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id")),
    )
    op.create_index("ix_customers_branch_id", "customers", ["branch_id"])
    op.execute(
        """
        UPDATE customers c
        SET branch_id = (
            SELECT s.branch_id FROM sales s
            WHERE s.customer_id = c.id AND s.branch_id IS NOT NULL
            ORDER BY s.completed_at NULLS LAST, s.created_at
            LIMIT 1
        )
        WHERE c.branch_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_customers_branch_id", table_name="customers")
    op.drop_column("customers", "branch_id")
