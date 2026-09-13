"""Салбарын журам: милийн зургийг зөвхөн камераар авах эсэх.

Түгээгч галерейгээс хуучин (өмнөх өдрийн) милийн зураг оруулж болдог байв.
Асаалттай үед милийн зураг аппын камераар л авагдаж, зураг дээр огноо/цаг,
салбар, түгээгчийн нэр тамгалагдана; settlement, үнийн тэмдэглэл, бэлэн
мөнгөний зургийг галерейгээс сонгож болно. Анхдагч утга `true`.

Revision ID: f3b8d2c7a1e4
Revises: e7a9c3d1f5b2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3b8d2c7a1e4"
down_revision = "e7a9c3d1f5b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "mile_photo_camera_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "mile_photo_camera_only")
