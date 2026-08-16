"""Задлан (грамлаж) зарах бараа.

``sale_mode`` нь ``piece`` (ширхэг) эсвэл ``bulk`` (грам).  Ширхэг бараан дээр
``bulk_product_id`` + ``bulk_factor`` тохируулбал түүнийг задалж грам
бүтээгдэхүүн рүү хөрвүүлж болно (1 ширхэг → ``bulk_factor`` нэгж).

Revision ID: c9e2b47f0a15
Revises: b5d47e91a0c3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "c9e2b47f0a15"
down_revision: str | None = "b5d47e91a0c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("sale_mode", sa.String(8), nullable=False, server_default="piece"),
    )
    op.add_column("products", sa.Column("bulk_product_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "products",
        sa.Column("bulk_factor", sa.Numeric(12, 3), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_products_bulk_product_id",
        "products",
        "products",
        ["bulk_product_id"],
        ["id"],
    )
    op.create_index("ix_products_bulk_product_id", "products", ["bulk_product_id"])


def downgrade() -> None:
    op.drop_index("ix_products_bulk_product_id", table_name="products")
    op.drop_constraint("fk_products_bulk_product_id", "products", type_="foreignkey")
    op.drop_column("products", "bulk_factor")
    op.drop_column("products", "bulk_product_id")
    op.drop_column("products", "sale_mode")
