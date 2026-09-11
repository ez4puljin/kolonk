"""Түлшний ачилт, салбарын тооцоо, журналын салбарын хэмжүүр.

* ``fuel_shipments`` + ``fuel_shipment_items`` — машины ачилт (нийлүүлэгчээс
  бөөнөөр татаж салбаруудад түгээх), «Замд яваа түлш» (1303) данс нэмэгдэнэ;
* ``fuel_shipment_outflows`` — машинаас шууд борлуулалт / хорогдол;
* ``branch_settlements`` — салбарын өр/төлбөрийн тооцооны дэвтэр;
* ``fuel_receipts.shipment_id`` + ``branch_id`` — түгээлтийг ачилттай холбож,
  салбарын худалдан авалтын түүхийг шүүх;
* ``journal_lines.dim_branch_id`` — салбар бүрийн орлого зарлага, ашгийн тайлан.

Revision ID: a91f4c72e8b5
Revises: c4a81f6b23de
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "a91f4c72e8b5"
down_revision: str | None = "c4a81f6b23de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------- журналын хэмжүүр
    op.add_column("journal_lines", sa.Column("dim_branch_id", UUID(as_uuid=True)))
    op.create_index("ix_journal_lines_dim_branch_id", "journal_lines", ["dim_branch_id"])

    # ---------------------------------------------------------------- ачилт
    op.execute("CREATE SEQUENCE IF NOT EXISTS shipment_number_seq START 1")
    op.create_table(
        "fuel_shipments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("nextval('shipment_number_seq')"),
        ),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("vehicle_no", sa.String(32), nullable=False),
        sa.Column("driver_name", sa.String(64)),
        sa.Column("shipment_date", sa.Date(), nullable=False),
        sa.Column("invoice_no", sa.String(64)),
        sa.Column("freight_cost", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_gross", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("ap_invoice_id", UUID(as_uuid=True), sa.ForeignKey("ap_invoices.id")),
        sa.Column("posted_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fuel_shipments_number", "fuel_shipments", ["number"])
    op.create_index("ix_fuel_shipments_status", "fuel_shipments", ["status"])
    op.create_index("ix_fuel_shipments_shipment_date", "fuel_shipments", ["shipment_date"])

    op.create_table(
        "fuel_shipment_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "shipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fuel_shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fuel_id", UUID(as_uuid=True), sa.ForeignKey("fuels.id"), nullable=False),
        sa.Column("liters", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("landed_unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fuel_shipment_items_shipment_id", "fuel_shipment_items", ["shipment_id"])

    op.create_table(
        "fuel_shipment_outflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "shipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fuel_shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(8), nullable=False, server_default="sale"),
        sa.Column("fuel_id", UUID(as_uuid=True), sa.ForeignKey("fuels.id"), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("outflow_date", sa.Date(), nullable=False),
        sa.Column("liters", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cost_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("received_to", sa.String(8), nullable=False, server_default="bank"),
        sa.Column("bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id")),
        sa.Column("customer_name", sa.String(128)),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fuel_shipment_outflows_shipment_id", "fuel_shipment_outflows", ["shipment_id"])
    op.create_index("ix_fuel_shipment_outflows_branch_id", "fuel_shipment_outflows", ["branch_id"])

    # ------------------------------------------------------ таталтын холбоос
    op.add_column(
        "fuel_receipts",
        sa.Column("shipment_id", UUID(as_uuid=True), sa.ForeignKey("fuel_shipments.id")),
    )
    op.add_column(
        "fuel_receipts",
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id")),
    )
    op.create_index("ix_fuel_receipts_shipment_id", "fuel_receipts", ["shipment_id"])
    op.create_index("ix_fuel_receipts_branch_id", "fuel_receipts", ["branch_id"])
    # Хуучин баримтуудад савны салбарыг нөхөж бичнэ.
    op.execute(
        """
        UPDATE fuel_receipts fr
        SET branch_id = t.branch_id
        FROM tanks t
        WHERE fr.tank_id = t.id AND fr.branch_id IS NULL AND t.branch_id IS NOT NULL
        """
    )

    # ------------------------------------------------------ салбарын тооцоо
    op.create_table(
        "branch_settlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("entry_type", sa.String(8), nullable=False, server_default="charge"),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("ref_type", sa.String(32)),
        sa.Column("ref_id", UUID(as_uuid=True)),
        sa.Column("paid_from", sa.String(8)),
        sa.Column("from_bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id")),
        sa.Column("to_bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id")),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_branch_settlements_branch_id", "branch_settlements", ["branch_id"])
    op.create_index("ix_branch_settlements_entry_type", "branch_settlements", ["entry_type"])
    op.create_index("ix_branch_settlements_entry_date", "branch_settlements", ["entry_date"])
    op.create_index("ix_branch_settlements_ref_id", "branch_settlements", ["ref_id"])

    # ------------------------------------------------------------- 1303 данс
    op.execute(
        """
        INSERT INTO accounts (code, name_mn, account_type, is_postable, parent_code, sort_order)
        VALUES ('1303', 'Замд яваа түлш (ачилт)', 'asset', true, '1000', 1303)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_branch_settlements_ref_id", table_name="branch_settlements")
    op.drop_index("ix_branch_settlements_entry_date", table_name="branch_settlements")
    op.drop_index("ix_branch_settlements_entry_type", table_name="branch_settlements")
    op.drop_index("ix_branch_settlements_branch_id", table_name="branch_settlements")
    op.drop_table("branch_settlements")

    op.drop_index("ix_fuel_receipts_branch_id", table_name="fuel_receipts")
    op.drop_index("ix_fuel_receipts_shipment_id", table_name="fuel_receipts")
    op.drop_column("fuel_receipts", "branch_id")
    op.drop_column("fuel_receipts", "shipment_id")

    op.drop_index("ix_fuel_shipment_outflows_branch_id", table_name="fuel_shipment_outflows")
    op.drop_index("ix_fuel_shipment_outflows_shipment_id", table_name="fuel_shipment_outflows")
    op.drop_table("fuel_shipment_outflows")
    op.drop_index("ix_fuel_shipment_items_shipment_id", table_name="fuel_shipment_items")
    op.drop_table("fuel_shipment_items")
    op.drop_index("ix_fuel_shipments_shipment_date", table_name="fuel_shipments")
    op.drop_index("ix_fuel_shipments_status", table_name="fuel_shipments")
    op.drop_index("ix_fuel_shipments_number", table_name="fuel_shipments")
    op.drop_table("fuel_shipments")
    op.execute("DROP SEQUENCE IF EXISTS shipment_number_seq")

    op.drop_index("ix_journal_lines_dim_branch_id", table_name="journal_lines")
    op.drop_column("journal_lines", "dim_branch_id")
