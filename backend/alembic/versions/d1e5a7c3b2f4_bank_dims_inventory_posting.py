"""Санхүүгийн бүрэн бүтэн байдал: банкны хэмжүүр, нөөцийн бичилт, салбарын нөхөлт.

Санхүүгийн аудитаар олдсон дутагдлууд:

* Нийлүүлэгчийн төлбөр (``ap_payments``) ба борлуулалтын шилжүүлэг
  (``payments``) АЛЬ банкны данснаас/руу явсныг тэмдэглэдэггүй байв — 1110
  дансны мөр ``dim_bank_account_id``-гүй үлдэж, банкны данс бүрийн үлдэгдэл
  буруу гардаг. Хоёуланд нь ``bank_account_id`` багана нэмэв.
* Салбарын хэмжүүр (``journal_lines.dim_branch_id``) нэвтрүүлэхээс өмнөх
  борлуулалтын бичилтүүд салбаргүй үлдсэн — ээлжийн салбараас нөхөж бичнэ,
  ингэснээр салбар бүрийн орлого зарлагын тайлан бүрэн болно.

Нөөцийн залруулга, салбар хоорондын шилжүүлэг, банкны эхний үлдэгдлийн
журналын бичилтүүд кодоор нэмэгдэв (хүснэгтийн өөрчлөлт шаардахгүй).

Revision ID: d1e5a7c3b2f4
Revises: c8d4f2a1b9e3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "d1e5a7c3b2f4"
down_revision: str | None = "c8d4f2a1b9e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ap_payments",
        sa.Column("bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id")),
    )
    op.create_index("ix_ap_payments_bank_account_id", "ap_payments", ["bank_account_id"])

    op.add_column(
        "payments",
        sa.Column("bank_account_id", UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id")),
    )
    op.create_index("ix_payments_bank_account_id", "payments", ["bank_account_id"])

    # Хуучин борлуулалтын бичилтүүдэд ээлжийн салбарыг нөхнө (нөөцийн 1301/1302
    # мөрүүд аль хэдийн сав/салбартай тул зөвхөн хоосон мөрүүд).
    op.execute(
        """
        UPDATE journal_lines jl
        SET dim_branch_id = sh.branch_id
        FROM journal_entries je
        JOIN sales sa ON sa.id = je.source_id
        JOIN shifts sh ON sh.id = sa.shift_id
        WHERE jl.entry_id = je.id
          AND je.source_type = 'sale'
          AND jl.dim_branch_id IS NULL
          AND sh.branch_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_payments_bank_account_id", table_name="payments")
    op.drop_column("payments", "bank_account_id")
    op.drop_index("ix_ap_payments_bank_account_id", table_name="ap_payments")
    op.drop_column("ap_payments", "bank_account_id")
