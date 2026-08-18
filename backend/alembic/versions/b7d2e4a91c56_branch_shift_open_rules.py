"""Салбар бүрд ээлж нээх шаардлагыг тохируулах хоёр тохиргоо.

Станц бүр өөр өөр журамтай: зарим салбарт хошууны миль, зураг хоёуланг нь
заавал бүртгүүлдэг бол зарим нь зөвхөн мильтэй, эсвэл зургийг заавал
шаарддаггүй. Өмнө нь хоёулаа кодод хатуу шаардлага байсан.

Анхдагч утга нь `true` — өнөөг хүртэлх зан төлөв хэвээр үлдэнэ, тохиргоог
гараар сулласан салбарт л өөрчлөгдөнө.

Revision ID: b7d2e4a91c56
Revises: a2f96e1c47d3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7d2e4a91c56"
down_revision = "a2f96e1c47d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "branches",
        sa.Column(
            "require_open_mile",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "branches",
        sa.Column(
            "require_open_photo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("branches", "require_open_photo")
    op.drop_column("branches", "require_open_mile")
