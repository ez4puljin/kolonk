"""Ачилт: олон нийлүүлэгч, бараа материал, хуваарилалтын төлөвлөгөө.

Нэг машин олон нийлүүлэгчээс өөр өөр түлш **ба бараа** авч, салбар бүрийн
өөр өөр саванд/агуулахад өөр хэмжээгээр буулгадаг болов:

* ``fuel_shipment_items.supplier_id`` — мөр бүрийн нийлүүлэгч (хоосон бол
  ачилтын толгойн «үндсэн» нийлүүлэгч, тээврийн зардал түүнд бичигдэнэ);
  бүртгэхэд нийлүүлэгч тус бүрд тусдаа өглөг нээгдэнэ;
* ``fuel_shipment_goods`` — ачилтын барааны мөрүүд;
* ``purchases.shipment_id`` — ачилтаас салбарт буусан бараа худалдан авалтын
  баримт болж (``fuel_receipts.shipment_id``-ийн адил) салбарын нөөцөд орно;
* ``fuel_shipments.plan`` — үүсгэх үедээ оруулсан хуваарилалт (сав/литр,
  салбар/тоо); бүртгэхэд автоматаар буулгагдана;
* 1304 «Замд яваа бараа» данс — бараа машин дээр байх хугацаанд.

Revision ID: c8d4f2a1b9e3
Revises: a91f4c72e8b5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "c8d4f2a1b9e3"
down_revision: str | None = "a91f4c72e8b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- мөр бүрийн нийлүүлэгч ---
    op.add_column(
        "fuel_shipment_items",
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
    )
    op.create_index("ix_fuel_shipment_items_supplier_id", "fuel_shipment_items", ["supplier_id"])

    # --- хуваарилалтын төлөвлөгөө (ноорог дээр хадгалагдана) ---
    op.add_column("fuel_shipments", sa.Column("plan", JSONB(), nullable=True))

    # --- барааны мөрүүд ---
    op.create_table(
        "fuel_shipment_goods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "shipment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("fuel_shipments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id")),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("landed_unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fuel_shipment_goods_shipment_id", "fuel_shipment_goods", ["shipment_id"])
    op.create_index("ix_fuel_shipment_goods_supplier_id", "fuel_shipment_goods", ["supplier_id"])

    # --- ачилтаас буусан бараа = худалдан авалтын баримт ---
    op.add_column(
        "purchases",
        sa.Column("shipment_id", UUID(as_uuid=True), sa.ForeignKey("fuel_shipments.id")),
    )
    op.create_index("ix_purchases_shipment_id", "purchases", ["shipment_id"])

    # --- 1304 данс ---
    op.execute(
        """
        INSERT INTO accounts (code, name_mn, account_type, is_postable, parent_code, sort_order)
        VALUES ('1304', 'Замд яваа бараа (ачилт)', 'asset', true, '1000', 1304)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_purchases_shipment_id", table_name="purchases")
    op.drop_column("purchases", "shipment_id")
    op.drop_index("ix_fuel_shipment_goods_supplier_id", table_name="fuel_shipment_goods")
    op.drop_index("ix_fuel_shipment_goods_shipment_id", table_name="fuel_shipment_goods")
    op.drop_table("fuel_shipment_goods")
    op.drop_column("fuel_shipments", "plan")
    op.drop_index("ix_fuel_shipment_items_supplier_id", table_name="fuel_shipment_items")
    op.drop_column("fuel_shipment_items", "supplier_id")
