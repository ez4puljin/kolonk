"""Насосны дугаар салбар дотроо давхардахгүй.

Олон салбартай станцад салбар бүр өөрийн «1-р насос»-той байх ёстой.
Өмнө нь ``pumps.number`` бүх системд unique байсан тул 2-р салбарт
насос үүсгэх боломжгүй байв.

Revision ID: f19d3c85b7e2
Revises: e8c41d7b6a92
"""

from __future__ import annotations

from alembic import op

revision: str = "f19d3c85b7e2"
down_revision: str | None = "e8c41d7b6a92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Баганын түвшний unique нэр нь тавтологиар `pumps_number_key`.
    op.execute("ALTER TABLE pumps DROP CONSTRAINT IF EXISTS pumps_number_key")
    op.create_unique_constraint("uq_pump_branch_number", "pumps", ["branch_id", "number"])


def downgrade() -> None:
    op.drop_constraint("uq_pump_branch_number", "pumps", type_="unique")
    op.create_unique_constraint("pumps_number_key", "pumps", ["number"])
