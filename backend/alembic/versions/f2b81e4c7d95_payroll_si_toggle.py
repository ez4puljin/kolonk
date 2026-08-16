"""НДШ бодох эсэх сонголт.

Ажилтан бүрд НДШ бодох эсэхийг тохируулна.  Унтраасан үед ажилтан ба
ажил олгогчийн НДШ 0 болж, ХХОАТ нийт цалингаас шууд бодогдоно.
``payroll_lines``-д мөн хуулж хадгална — хуучин сарын тооцоо хожим
өөрчлөгдөхгүй.

Revision ID: f2b81e4c7d95
Revises: e7c30d5a1b42
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f2b81e4c7d95"
down_revision: str | None = "e7c30d5a1b42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("si_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "payroll_lines",
        sa.Column("si_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "payroll_periods",
        sa.Column("auto_sync", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("payroll_periods", "auto_sync")
    op.drop_column("payroll_lines", "si_enabled")
    op.drop_column("employees", "si_enabled")
