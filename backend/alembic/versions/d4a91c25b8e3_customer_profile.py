"""Харилцагчийн дэлгэрэнгүй карт.

Овог, хоёр дахь утас, байршил (аймаг/сум), гэрээний зээлийн лимит,
сканнердсан гэрээний PDF файлын зам.

Revision ID: d4a91c25b8e3
Revises: c1f8a2d94e07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d4a91c25b8e3"
down_revision: str | None = "c1f8a2d94e07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("last_name", sa.String(64), nullable=True))
    op.add_column("customers", sa.Column("phone2", sa.String(32), nullable=True))
    op.add_column("customers", sa.Column("province", sa.String(64), nullable=True))
    op.add_column("customers", sa.Column("district", sa.String(64), nullable=True))
    op.add_column(
        "customers",
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column("customers", sa.Column("contract_file", sa.String(255), nullable=True))
    op.create_index("ix_customers_phone", "customers", ["phone"])
    op.create_index("ix_customers_province", "customers", ["province"])
    op.create_index("ix_customers_district", "customers", ["district"])


def downgrade() -> None:
    op.drop_index("ix_customers_district", table_name="customers")
    op.drop_index("ix_customers_province", table_name="customers")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_column("customers", "contract_file")
    op.drop_column("customers", "credit_limit")
    op.drop_column("customers", "district")
    op.drop_column("customers", "province")
    op.drop_column("customers", "phone2")
    op.drop_column("customers", "last_name")
