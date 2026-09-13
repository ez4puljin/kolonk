"""Харилцагч: «Лимитгүй» — зээлийн лимит шалгахгүй.

* ``customers.credit_unlimited`` — True бол энэ харилцагчийн бүх гэрээнд
  зээлийн лимит шалгагдахгүй (ПОС-ын гэрээт төлбөр, өдрийн хаалтын зээл,
  гар авлага). Нягтлан/админ Харилцагч цэснээс тохируулна.

Revision ID: b8d2f4a6c1e3
Revises: a4c7e9b2d6f1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8d2f4a6c1e3"
down_revision = "a4c7e9b2d6f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("credit_unlimited", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("customers", "credit_unlimited")
