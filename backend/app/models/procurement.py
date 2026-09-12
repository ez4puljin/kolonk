import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import DocStatus, ShipmentOutflowKind, ShipmentStatus
from app.models.base import Liters, Money, TimestampMixin, UnitCost, UUIDPKMixin

receipt_number_seq = Sequence("receipt_number_seq", start=1)
purchase_number_seq = Sequence("purchase_number_seq", start=1)
shipment_number_seq = Sequence("shipment_number_seq", start=1)


class FuelShipment(UUIDPKMixin, TimestampMixin, Base):
    """Нэг машины ачилт — нийлүүлэгчээс татсан түлшийг салбаруудад түгээнэ.

    Бүртгэгдэхэд нийт дүнгээр нийлүүлэгчийн өглөг нээгдэж, түлш нь «Замд яваа
    түлш» (1303) дансанд орно.  Машин салбар бүрд буулгах тутам түгээлтийн
    баримт (``FuelReceipt.shipment_id``) үүсэж 1303 → 1301 шилжинэ.  Үлдсэн
    литрийг машинаас шууд борлуулах эсвэл хорогдолд бичиж болно.  Бүх литр
    тэглэгдмэгц ачилт хаагдана.
    """

    __tablename__ = "fuel_shipments"

    number: Mapped[int] = mapped_column(
        Integer, shipment_number_seq, server_default=shipment_number_seq.next_value(), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    #: Машины улсын дугаар — салбарын худалдан авалтын түүхэнд харагдана.
    vehicle_no: Mapped[str] = mapped_column(String(32), nullable=False)
    driver_name: Mapped[str | None] = mapped_column(String(64))
    shipment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    #: Тээврийн зардал — нэгж өртөгт (landed cost) дүнгээр нь хуваарилагдана.
    freight_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total_gross: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ShipmentStatus.DRAFT, index=True)
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ap_invoices.id"))
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["FuelShipmentItem"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", lazy="selectin"
    )
    outflows: Mapped[list["FuelShipmentOutflow"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", lazy="selectin"
    )
    goods: Mapped[list["FuelShipmentGoods"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", lazy="selectin"
    )
    #: Үүсгэх үедээ оруулсан хуваарилалтын төлөвлөгөө — бүртгэхэд автоматаар
    #: буулгагдана. Хэлбэр: {"fuel": [{"fuel_id", "tank_id", "liters"}],
    #: "goods": [{"product_id", "branch_id", "qty"}]}.
    plan: Mapped[dict | None] = mapped_column(JSONB)


class FuelShipmentItem(UUIDPKMixin, TimestampMixin, Base):
    """Ачилтын нэг түлш: хэдэн литр, ямар нэгж үнээр, ХЭНЭЭС ачигдсан бэ."""

    __tablename__ = "fuel_shipment_items"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fuel_shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Мөрийн нийлүүлэгч — хоосон бол ачилтын толгойн (үндсэн) нийлүүлэгч.
    #: Нэг машин олон нийлүүлэгчээс ачдаг тул өглөг нийлүүлэгч тус бүрээр үүснэ.
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("suppliers.id"), index=True
    )
    fuel_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"), nullable=False)
    liters: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Тээвэр хуваарилсны дараах нэгж өртөг — сав руу энэ өртгөөр орно.
    landed_unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))

    shipment: Mapped[FuelShipment] = relationship(back_populates="items")
    fuel: Mapped["Fuel"] = relationship(lazy="selectin")  # noqa: F821


class FuelShipmentGoods(UUIDPKMixin, TimestampMixin, Base):
    """Ачилтын нэг бараа: хэдэн ширхэг, ямар нэгж өртгөөр, хэнээс.

    Бүртгэхэд «Замд яваа бараа» (1304) дансанд орж, салбарт буухад тухайн
    салбарын худалдан авалт (``Purchase.shipment_id``) болж 1302 руу шилжинэ.
    """

    __tablename__ = "fuel_shipment_goods"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fuel_shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("suppliers.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Тээвэр хуваарилсны дараах нэгж өртөг — салбарын нөөцөд энэ өртгөөр орно.
    landed_unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))

    shipment: Mapped[FuelShipment] = relationship(back_populates="goods")
    product: Mapped["Product"] = relationship(lazy="selectin")  # noqa: F821


class FuelShipmentOutflow(UUIDPKMixin, TimestampMixin, Base):
    """Машинаас шууд гарсан литр — борлуулалт эсвэл хорогдол.

    Саванд ороогүй тул нөөцөд нөлөөлөхгүй; 1303-аас шууд хасагдана.
    """

    __tablename__ = "fuel_shipment_outflows"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fuel_shipments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default=ShipmentOutflowKind.SALE)
    fuel_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"), nullable=False)
    #: Борлуулалтыг аль салбарын орлогод тооцох вэ (хоосон = толгойд).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True)
    outflow_date: Mapped[date] = mapped_column(Date, nullable=False)
    liters: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    #: Борлуулалтын нэгж үнэ (НӨАТ-тай); хорогдолд 0.
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Өртөг — литр × landed нэгж өртөг (1303-аас хасагдсан дүн).
    cost_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Төлбөр хаана орсон: ``cash`` эсвэл ``bank``.
    received_to: Mapped[str] = mapped_column(String(8), nullable=False, default="bank")
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bank_accounts.id")
    )
    customer_name: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))

    shipment: Mapped[FuelShipment] = relationship(back_populates="outflows")
    fuel: Mapped["Fuel"] = relationship(lazy="selectin")  # noqa: F821


class FuelReceipt(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fuel_receipts"

    number: Mapped[int] = mapped_column(
        Integer, receipt_number_seq, server_default=receipt_number_seq.next_value(), nullable=False, index=True
    )
    #: Ачилтаас буусан түгээлт бол эх ачилт нь; хоосон = шууд таталт.
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fuel_shipments.id"), index=True
    )
    #: Аль салбарын худалдан авалт вэ (савны салбараас хуулбарлана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    tank_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tanks.id"), nullable=False)
    fuel_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("fuels.id"), nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    liters: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False)
    freight_cost: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    density: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total_gross: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    landed_unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DocStatus.DRAFT, index=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ap_invoices.id"))
    note: Mapped[str | None] = mapped_column(Text)


class Purchase(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchases"

    number: Mapped[int] = mapped_column(
        Integer, purchase_number_seq, server_default=purchase_number_seq.next_value(), nullable=False, index=True
    )
    #: Ачилтаас буусан бараа бол эх ачилт нь (``FuelReceipt.shipment_id``-ийн
    #: адил); хоосон = шууд худалдан авалт. Ачилтын баримт өглөг, НӨАТ-гүй —
    #: тэдгээр нь ачилт дээрээ бүртгэгдсэн.
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fuel_shipments.id"), index=True
    )
    #: Бараа аль салбарын нөөцөд орох вэ (хоосон бол үндсэн салбар).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(64))
    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    total_gross: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DocStatus.DRAFT, index=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ap_invoice_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ap_invoices.id"))
    note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase", cascade="all, delete-orphan", lazy="selectin"
    )


class PurchaseItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_items"

    purchase_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Liters, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(UnitCost, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)

    purchase: Mapped[Purchase] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(lazy="selectin")  # noqa: F821
