"""Насосны талбай дахь бодит байршил.

Салбарын тохиргоонд насосыг зурган дээр байрлуулж, ПОС мөн тэр дарааллаар
харуулна.  Хуучин бичлэгт дугаараар нь автоматаар байрлуулна (2 багана).

Revision ID: e7c30d5a1b42
Revises: d4a91c25b8e3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e7c30d5a1b42"
down_revision: str | None = "d4a91c25b8e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pumps", sa.Column("position_x", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pumps", sa.Column("position_y", sa.Integer(), nullable=False, server_default="0"))
    # Хуучин насосыг дугаараар нь 2 баганад эмхэлнэ (0-оос эхэлсэн индекс).
    op.execute(
        """
        UPDATE pumps SET
            position_x = (number - 1) % 2,
            position_y = (number - 1) / 2
        """
    )


def downgrade() -> None:
    op.drop_column("pumps", "position_y")
    op.drop_column("pumps", "position_x")
