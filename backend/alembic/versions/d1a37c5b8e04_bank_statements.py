"""Банкны данс ба банкны хуулга.

Хуулгын орлого → гэрээт авлагын төлбөр, зарлага → үйл ажиллагааны зардал.
Данс тус бүрийн үлдэгдлийг ерөнхий дэвтрээс гаргахын тулд журналын мөрд
``dim_bank_account_id`` хэмжүүр нэмэв — 1110 нь хяналтын данс хэвээр үлдэнэ.

Revision ID: d1a37c5b8e04
Revises: c9e2b47f0a15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "d1a37c5b8e04"
down_revision: str | None = "c9e2b47f0a15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ данс
    op.create_table(
        "bank_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id")),
        sa.Column("bank_name", sa.String(64), nullable=False),
        sa.Column("account_number", sa.String(32), nullable=False),
        sa.Column("holder_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("currency", sa.String(8), nullable=False, server_default="MNT"),
        sa.Column("opening_balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("is_fee_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("account_number", name="uq_bank_account_number"),
    )
    op.create_index("ix_bank_accounts_branch_id", "bank_accounts", ["branch_id"])
    op.create_index("ix_bank_accounts_account_number", "bank_accounts", ["account_number"])

    # ----------------------------------------------------------------- хуулга
    op.create_table(
        "bank_statements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_number", sa.String(32), nullable=False, server_default=""),
        sa.Column("currency", sa.String(8), nullable=False, server_default="MNT"),
        sa.Column("date_from", sa.Date()),
        sa.Column("date_to", sa.Date()),
        sa.Column("filename", sa.String(255), nullable=False, server_default=""),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id")),
        sa.Column("fee_expense_id", UUID(as_uuid=True), sa.ForeignKey("expenses.id"), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_bank_statements_account_number", "bank_statements", ["account_number"])
    op.create_index("ix_bank_statements_date_from", "bank_statements", ["date_from"])
    op.create_index("ix_bank_statements_bank_account_id", "bank_statements", ["bank_account_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "statement_id", UUID(as_uuid=True),
            sa.ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("txn_date", sa.DateTime(timezone=True)),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("bank_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("bank_counterpart", sa.String(64), nullable=False, server_default=""),
        sa.Column("is_fee", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id")),
        sa.Column("expense_account_code", sa.String(16), sa.ForeignKey("accounts.code")),
        sa.Column("ar_payment_id", UUID(as_uuid=True), sa.ForeignKey("ar_payments.id"), unique=True),
        sa.Column("expense_id", UUID(as_uuid=True), sa.ForeignKey("expenses.id"), unique=True),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_bank_transactions_statement_id", "bank_transactions", ["statement_id"])
    op.create_index("ix_bank_transactions_txn_date", "bank_transactions", ["txn_date"])
    op.create_index("ix_bank_transactions_customer_id", "bank_transactions", ["customer_id"])
    op.create_index("ix_bank_transactions_contract_id", "bank_transactions", ["contract_id"])

    op.create_table(
        "bank_statement_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("settlement_customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("settlement_contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id")),
        sa.Column("settlement_description", sa.Text(), nullable=False, server_default="ПОС орлого"),
        sa.Column("fee_account_code", sa.String(16), sa.ForeignKey("accounts.code")),
        sa.Column("fee_description", sa.Text(), nullable=False, server_default="Банкны шимтгэл"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --------------------------------------------------- холбогдох талбарууд
    op.add_column("expenses", sa.Column("bank_account_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_expenses_bank_account_id", "expenses", "bank_accounts", ["bank_account_id"], ["id"]
    )
    op.create_index("ix_expenses_bank_account_id", "expenses", ["bank_account_id"])

    op.add_column("ar_payments", sa.Column("bank_account_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_ar_payments_bank_account_id", "ar_payments", "bank_accounts", ["bank_account_id"], ["id"]
    )
    op.create_index("ix_ar_payments_bank_account_id", "ar_payments", ["bank_account_id"])

    op.add_column("journal_lines", sa.Column("dim_bank_account_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_journal_lines_dim_bank_account_id", "journal_lines", ["dim_bank_account_id"])


def downgrade() -> None:
    op.drop_index("ix_journal_lines_dim_bank_account_id", table_name="journal_lines")
    op.drop_column("journal_lines", "dim_bank_account_id")

    op.drop_index("ix_ar_payments_bank_account_id", table_name="ar_payments")
    op.drop_constraint("fk_ar_payments_bank_account_id", "ar_payments", type_="foreignkey")
    op.drop_column("ar_payments", "bank_account_id")

    op.drop_index("ix_expenses_bank_account_id", table_name="expenses")
    op.drop_constraint("fk_expenses_bank_account_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "bank_account_id")

    op.drop_table("bank_statement_config")
    op.drop_table("bank_transactions")
    op.drop_table("bank_statements")
    op.drop_table("bank_accounts")
