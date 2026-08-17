import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import InventoryTxType, ProductSaleMode
from app.models.base import Liters, Money, TimestampMixin, UnitCost, UUIDPKMixin


class ProductCategory(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_categories"

    name_mn: Mapped[str] = mapped_column(String(64), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    name_mn: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(8), nullable=False, default="ш")
    price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    avg_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    stock_qty: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))
    min_stock: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    #: Ширхэгээр эсвэл задлан (грамлаж) зарах уу.
    sale_mode: Mapped[str] = mapped_column(
        String(8), nullable=False, default=str(ProductSaleMode.PIECE), server_default="piece"
    )
    #: Ширхэг барааг задлахад аль грам бүтээгдэхүүн рүү орох вэ (зөвхөн ``piece``).
    bulk_product_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id"), index=True
    )
    #: 1 ширхэгээс гарах грам бүтээгдэхүүний хэмжээ (жишээ нь 5.000 л).
    bulk_factor: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))

    # Задлалтын зорилтыг ORM холбоосоор биш, нэр хэрэгтэй газартаа тусдаа
    # асуулгаар авна — өөрийг нь заасан FK дээр eager loading нь давхар
    # (recursive) асуулга үүсгэх эрсдэлтэй.
    category: Mapped[ProductCategory] = relationship(back_populates="products", lazy="selectin")


class ProductBranchStock(UUIDPKMixin, TimestampMixin, Base):
    """Салбар тус бүрийн барааны үлдэгдэл ба өртөг.

    ``Product.stock_qty`` нь БҮХ салбарын нийлбэр хэвээр (журнал 1302 үүнтэй
    тулдаг), харин энэ хүснэгт салбар бүрийн задаргааг хөтөлнө.
    Инвариант: Σ(qty) == product.stock_qty.

    ``avg_cost`` нь тухайн салбарын хөдлөх дундаж өртөг — салбар бүр өөр
    үнээр татсан бол борлуулалтын өртөг (COGS) тухайн салбарынхаараа
    бодогдоно. ``Product.avg_cost`` нь эдгээрийн жигнэсэн дундаж:
    Σ(qty × avg_cost) / Σ(qty).
    """

    __tablename__ = "product_branch_stocks"
    __table_args__ = (UniqueConstraint("product_id", "branch_id", name="uq_product_branch"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), nullable=False, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False, default=Decimal("0"))
    avg_cost: Mapped[Decimal] = mapped_column(
        UnitCost, nullable=False, default=Decimal("0"), server_default="0"
    )


class InventoryTransaction(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transactions"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    #: Аль салбарт гарсан хөдөлгөөн вэ.
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )
    tx_type: Mapped[str] = mapped_column(String(24), nullable=False, default=InventoryTxType.SALE)
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    balance_after: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(String(255))

    product: Mapped[Product] = relationship(lazy="selectin")
