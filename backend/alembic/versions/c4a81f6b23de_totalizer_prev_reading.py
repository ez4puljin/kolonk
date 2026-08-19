"""Нээлтийн заалт дээр өмнөх хаалтын мильийг хөлдөөж хадгална.

Миль бол хошуунаас гарсан хуримтлагдсан хэмжээ тул өчигдрийн хаалт,
өнөөдрийн нээлт хоёр ЯГ тэнцүү байх ёстой. Зөрвөл хоёрын нэг нь болсон:
хаалтын миль буруу бичигдсэн, эсвэл ээлж хаагдсаны дараа мэдэгдэлгүй
шатахуун түгээгдсэн. Хоёулаа мөнгөний алдагдал.

Зөрүүг дараа нь тооцоолж олох боломжтой ч найдваргүй: өмнөх ээлжийн
хаалтыг нягтлан засвал зөрүү нь хойшоо алга болно. Иймд нээх мөчид
харсан утгыг тэр чигт нь хадгална.

Revision ID: c4a81f6b23de
Revises: b7d2e4a91c56
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4a81f6b23de"
down_revision = "b7d2e4a91c56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "totalizer_readings",
        sa.Column("prev_reading", sa.Numeric(14, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("totalizer_readings", "prev_reading")
