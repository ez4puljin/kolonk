"""Бараа, ангилал, нөөц, үнийн өөрчлөлтийн схемүүд (WP7).

Мөнгө/тоо хэмжээ бүгд ``Decimal`` — JSON руу string-ээр гарна (CONTRACTS.md §2).
Хэрэглэгчид харагдах бүх текст монгол.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ApprovalStatus, InventoryTxType, ProductSaleMode

ZERO = Decimal("0.00")
ZERO_Q = Decimal("0.000")

#: Нөөцийн хөдөлгөөний төрлийн монгол нэр.
INVENTORY_TX_NAMES_MN: dict[str, str] = {
    InventoryTxType.PURCHASE: "Худалдан авалт",
    InventoryTxType.SALE: "Борлуулалт",
    InventoryTxType.REFUND: "Буцаалт",
    InventoryTxType.ADJUSTMENT: "Тохируулга",
    InventoryTxType.CONVERT_OUT: "Задлалт (гарсан)",
    InventoryTxType.CONVERT_IN: "Задлалт (орсон)",
    InventoryTxType.TRANSFER_OUT: "Шилжүүлэг (гарсан)",
    InventoryTxType.TRANSFER_IN: "Шилжүүлэг (орсон)",
}

#: Борлуулах хэлбэрийн монгол нэр.
SALE_MODE_NAMES_MN: dict[str, str] = {
    ProductSaleMode.PIECE: "Ширхэгээр",
    ProductSaleMode.BULK: "Задлан (грам)",
}

#: Батлах урсгалын төлвийн монгол нэр.
APPROVAL_STATUS_NAMES_MN: dict[str, str] = {
    ApprovalStatus.PENDING: "Хүлээгдэж буй",
    ApprovalStatus.APPROVED: "Батлагдсан",
    ApprovalStatus.REJECTED: "Татгалзсан",
}

#: Үнийн өөрчлөлтийн зорилтын монгол нэр.
PRICE_TARGET_NAMES_MN: dict[str, str] = {
    "fuel": "Түлш",
    "product": "Бараа",
}

PriceTarget = Literal["fuel", "product"]


# --------------------------------------------------------------------------- #
# Барааны ангилал
# --------------------------------------------------------------------------- #
class ProductCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_mn: str = Field(min_length=1, max_length=64)
    icon: str | None = Field(default=None, max_length=32)
    sort_order: int = 0


class ProductCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_mn: str | None = Field(default=None, min_length=1, max_length=64)
    icon: str | None = Field(default=None, max_length=32)
    sort_order: int | None = None


class ProductCategoryOut(BaseModel):
    id: uuid.UUID
    name_mn: str
    icon: str | None = None
    sort_order: int = 0
    product_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductCategoryListOut(BaseModel):
    items: list[ProductCategoryOut]
    total: int


# --------------------------------------------------------------------------- #
# Бараа
# --------------------------------------------------------------------------- #
class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=32)
    barcode: str | None = Field(default=None, max_length=64)
    name_mn: str = Field(min_length=1, max_length=128)
    category_id: uuid.UUID
    unit: str = Field(default="ш", min_length=1, max_length=8)
    price: Decimal = Field(default=ZERO, ge=0)
    opening_qty: Decimal = Field(default=ZERO_Q, ge=0, description="Эхний үлдэгдэл")
    opening_cost: Decimal = Field(default=ZERO, ge=0, description="Эхний үлдэгдлийн нэгж өртөг")
    min_stock: Decimal = Field(default=ZERO_Q, ge=0)
    is_active: bool = True
    sale_mode: ProductSaleMode = ProductSaleMode.PIECE
    #: Ширхэг барааг задлахад аль грам бүтээгдэхүүн рүү орох вэ.
    bulk_product_id: uuid.UUID | None = None
    #: 1 ширхэгээс гарах хэмжээ (жишээ нь 5.000 л).
    bulk_factor: Decimal = Field(default=ZERO_Q, ge=0)


class ProductUpdate(BaseModel):
    """``price`` зөвхөн татгалзах мессеж өгөхийн тулд байна — үнэ нь үнийн
    өөрчлөлтийн урсгалаар л (``/api/price-changes``) солигдоно.  ``stock_qty``,
    ``avg_cost`` энд огт байхгүй: тэдгээр нь зөвхөн нөөцийн дэвтрээр хөдөлнө."""

    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(default=None, min_length=1, max_length=32)
    barcode: str | None = Field(default=None, max_length=64)
    name_mn: str | None = Field(default=None, min_length=1, max_length=128)
    category_id: uuid.UUID | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=8)
    price: Decimal | None = None
    min_stock: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sale_mode: ProductSaleMode | None = None
    bulk_product_id: uuid.UUID | None = None
    bulk_factor: Decimal | None = Field(default=None, ge=0)


class ProductOut(BaseModel):
    id: uuid.UUID
    sku: str
    barcode: str | None = None
    name_mn: str
    category_id: uuid.UUID
    category_name: str | None = None
    unit: str = "ш"
    price: Decimal = ZERO
    avg_cost: Decimal = ZERO
    stock_qty: Decimal = ZERO_Q
    min_stock: Decimal = ZERO_Q
    stock_value: Decimal = ZERO
    is_low: bool = False
    is_active: bool = True
    sale_mode: str = str(ProductSaleMode.PIECE)
    sale_mode_name: str = ""
    bulk_product_id: uuid.UUID | None = None
    bulk_product_name: str | None = None
    bulk_product_unit: str | None = None
    bulk_factor: Decimal = ZERO_Q
    #: Задлан хөрвүүлэх боломжтой эсэх (ширхэг + зорилт + итгэлцүүр).
    is_convertible: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int


# --------------------------------------------------------------------------- #
# Нөөц
# --------------------------------------------------------------------------- #
class BranchQty(BaseModel):
    """Салбар дахь үлдэгдэл (нөөцийн задаргаа)."""

    branch_id: uuid.UUID
    branch_name: str = ""
    qty: Decimal = ZERO_Q


class InventoryRow(BaseModel):
    product_id: uuid.UUID
    sku: str
    name_mn: str
    category_id: uuid.UUID
    category_name: str | None = None
    unit: str = "ш"
    price: Decimal = ZERO
    stock_qty: Decimal = ZERO_Q
    avg_cost: Decimal = ZERO
    value: Decimal = ZERO
    min_stock: Decimal = ZERO_Q
    is_low: bool = False
    is_active: bool = True
    sale_mode: str = str(ProductSaleMode.PIECE)
    sale_mode_name: str = ""
    #: Салбар тус бүрийн үлдэгдэл (бүх салбарын горимд).
    branches: list[BranchQty] = []


class InventoryTotals(BaseModel):
    product_count: int = 0
    low_count: int = 0
    total_qty: Decimal = ZERO_Q
    total_value: Decimal = ZERO


class InventoryListOut(BaseModel):
    items: list[InventoryRow]
    total: int
    totals: InventoryTotals


class InventoryTxOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    sku: str | None = None
    unit: str | None = None
    tx_type: str
    tx_type_name: str = ""
    qty: Decimal = ZERO_Q
    unit_cost: Decimal = ZERO
    balance_after: Decimal = ZERO_Q
    amount: Decimal = ZERO
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    note: str | None = None
    created_at: datetime | None = None


class InventoryTxListOut(BaseModel):
    items: list[InventoryTxOut]
    total: int


class InventoryAdjustmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    qty: Decimal = Field(description="Тэмдэгтэй утга: + нэмэгдэл, − хорогдол")
    #: Аль салбарт тохируулах вэ (хоосон бол хэрэглэгчийн/үндсэн салбар).
    branch_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=255)


class InventoryAdjustmentOut(BaseModel):
    product: ProductOut
    transaction: InventoryTxOut


# --------------------------------------------------------------------------- #
# Салбар хоорондын шилжүүлэг
# --------------------------------------------------------------------------- #
class BranchTransferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID
    from_branch_id: uuid.UUID
    to_branch_id: uuid.UUID
    qty: Decimal = Field(gt=0, description="Шилжүүлэх тоо хэмжээ")
    note: str | None = Field(default=None, max_length=255)


class BranchTransferOut(BaseModel):
    product: ProductOut
    out_transaction: InventoryTxOut
    in_transaction: InventoryTxOut


# --------------------------------------------------------------------------- #
# Задлан хөрвүүлэлт (ширхэг → грам)
# --------------------------------------------------------------------------- #
class BulkConversionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Задлах ширхэг бараа (``sale_mode=piece``, ``bulk_product_id`` тохируулсан).
    product_id: uuid.UUID
    #: Хэдэн ширхэгийг задлах вэ.
    qty: Decimal = Field(gt=0, description="Задлах ширхэгийн тоо")
    #: Аль салбарт (хоосон бол хэрэглэгчийн/үндсэн салбар).
    branch_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=255)


class BulkConversionOut(BaseModel):
    source: ProductOut
    target: ProductOut
    #: Хэдэн ширхэг задалсан.
    qty: Decimal = ZERO_Q
    #: Грам бүтээгдэхүүн рүү орсон хэмжээ.
    out_qty: Decimal = ZERO_Q
    #: Шилжсэн өртөг.
    cost: Decimal = ZERO
    out_transaction: InventoryTxOut
    in_transaction: InventoryTxOut


# --------------------------------------------------------------------------- #
# Үнийн өөрчлөлтийн хүсэлт
# --------------------------------------------------------------------------- #
class PriceChangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: PriceTarget = "fuel"
    #: Аль салбарт үйлчлэх вэ. Хоосон = бүх салбар (суурь үнэ).
    branch_id: uuid.UUID | None = None
    fuel_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    new_price: Decimal = Field(ge=0)
    #: Аль өдрөөс хэрэгжих вэ (хоосон = батламагц шууд). Тосны үнийг
    #: маргаашнаас эхлүүлэхэд ашиглана.
    effective_date: date | None = None
    reason: str | None = Field(default=None, max_length=500)


class PriceChangeDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class PriceChangeOut(BaseModel):
    id: uuid.UUID
    target_type: str
    target_type_name: str = ""
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    fuel_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    target_id: uuid.UUID | None = None
    target_name: str | None = None
    target_code: str | None = None
    old_price: Decimal = ZERO
    new_price: Decimal = ZERO
    diff: Decimal = ZERO
    diff_pct: Decimal = ZERO
    reason: str | None = None
    status: str
    status_name: str = ""
    requested_by: uuid.UUID
    requested_by_name: str | None = None
    decided_by: uuid.UUID | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    effective_date: date | None = None
    applied_at: datetime | None = None
    created_at: datetime | None = None


class PriceChangeListOut(BaseModel):
    items: list[PriceChangeOut]
    total: int
