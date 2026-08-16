"""Салбарын нөөц ба салбарын үнэ.

* ``product_branch_stocks`` — салбар тус бүрийн барааны үлдэгдэл
  (``products.stock_qty`` нийлбэр хэвээр).
* ``inventory_transactions.branch_id`` — хөдөлгөөн аль салбарт гарсан.
* ``purchases.branch_id`` — худалдан авалт аль салбарын нөөцөд орсон.
* ``branch_prices`` — салбарын зарах үнийн override.
* ``price_changes.branch_id`` — үнийн өөрчлөлт аль салбарт (NULL = бүгд).

Backfill: одоо байгаа бүх үлдэгдэл, түүх үндсэн (эхний) салбарт очно.

Revision ID: c1f8a2d94e07
Revises: 2b3fd0c957b0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "c1f8a2d94e07"
down_revision: str | None = "2b3fd0c957b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_branch_stocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("product_id", "branch_id", name="uq_product_branch"),
    )
    op.create_index("ix_product_branch_stocks_product_id", "product_branch_stocks", ["product_id"])
    op.create_index("ix_product_branch_stocks_branch_id", "product_branch_stocks", ["branch_id"])

    op.create_table(
        "branch_prices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("fuel_id", UUID(as_uuid=True), sa.ForeignKey("fuels.id"), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("branch_id", "fuel_id", name="uq_branch_fuel_price"),
        sa.UniqueConstraint("branch_id", "product_id", name="uq_branch_product_price"),
    )
    op.create_index("ix_branch_prices_branch_id", "branch_prices", ["branch_id"])
    op.create_index("ix_branch_prices_fuel_id", "branch_prices", ["fuel_id"])
    op.create_index("ix_branch_prices_product_id", "branch_prices", ["product_id"])

    op.add_column("inventory_transactions", sa.Column("branch_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_inventory_tx_branch", "inventory_transactions", "branches", ["branch_id"], ["id"]
    )
    op.create_index("ix_inventory_transactions_branch_id", "inventory_transactions", ["branch_id"])

    op.add_column("purchases", sa.Column("branch_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_purchases_branch", "purchases", "branches", ["branch_id"], ["id"])
    op.create_index("ix_purchases_branch_id", "purchases", ["branch_id"])

    op.add_column("price_changes", sa.Column("branch_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_price_changes_branch", "price_changes", "branches", ["branch_id"], ["id"])
    op.create_index("ix_price_changes_branch_id", "price_changes", ["branch_id"])

    # ------- Backfill: бүх түүх үндсэн салбарт ------- #
    op.execute(
        """
        WITH main AS (
            SELECT id FROM branches WHERE is_active
            ORDER BY created_at LIMIT 1
        )
        INSERT INTO product_branch_stocks (product_id, branch_id, qty)
        SELECT p.id, main.id, p.stock_qty FROM products p, main
        WHERE p.stock_qty <> 0
        """
    )
    op.execute(
        """
        WITH main AS (
            SELECT id FROM branches WHERE is_active
            ORDER BY created_at LIMIT 1
        )
        UPDATE inventory_transactions SET branch_id = (SELECT id FROM main)
        WHERE branch_id IS NULL
        """
    )
    op.execute(
        """
        WITH main AS (
            SELECT id FROM branches WHERE is_active
            ORDER BY created_at LIMIT 1
        )
        UPDATE purchases SET branch_id = (SELECT id FROM main)
        WHERE branch_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_price_changes_branch_id", table_name="price_changes")
    op.drop_constraint("fk_price_changes_branch", "price_changes", type_="foreignkey")
    op.drop_column("price_changes", "branch_id")

    op.drop_index("ix_purchases_branch_id", table_name="purchases")
    op.drop_constraint("fk_purchases_branch", "purchases", type_="foreignkey")
    op.drop_column("purchases", "branch_id")

    op.drop_index("ix_inventory_transactions_branch_id", table_name="inventory_transactions")
    op.drop_constraint("fk_inventory_tx_branch", "inventory_transactions", type_="foreignkey")
    op.drop_column("inventory_transactions", "branch_id")

    op.drop_table("branch_prices")
    op.drop_table("product_branch_stocks")
