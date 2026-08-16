"""Үйл ажиллагааны зардлын схемүүд.

Зардал нь **төлсөн нийт дүнгээр** бүртгэгдэнэ. `has_vat=True` үед НӨАТ уг
дүнд шингэсэн гэж үзэж салгана (борлуулалттай ижил дүрэм, CONTRACTS.md §2).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

ZERO = Decimal("0.00")


class ExpenseCategoryOut(BaseModel):
    code: str
    name_mn: str


class ExpenseCreate(BaseModel):
    account_code: str
    #: Төлсөн нийт дүн (НӨАТ-тай бол түүнийг оруулаад).
    amount: Decimal
    payment_method: str = "cash"
    expense_date: date | None = None
    has_vat: bool = False
    supplier_id: uuid.UUID | None = None
    #: `bank` төлбөрийн үед аль харилцах данснаас гарсан бэ.
    bank_account_id: uuid.UUID | None = None
    invoice_no: str | None = None
    description: str | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: int
    expense_date: date
    account_code: str
    account_name: str
    payment_method: str
    payment_method_name: str
    subtotal: Decimal = ZERO
    vat_amount: Decimal = ZERO
    total: Decimal = ZERO
    supplier_id: uuid.UUID | None = None
    supplier_name: str | None = None
    bank_account_id: uuid.UUID | None = None
    bank_account_name: str | None = None
    invoice_no: str | None = None
    description: str | None = None
    status: str


class ExpenseByAccount(BaseModel):
    account_code: str
    account_name: str
    amount: Decimal = ZERO


class ExpenseListOut(BaseModel):
    items: list[ExpenseOut]
    total: int
    #: Шүүлтэд тохирсон бүртгэгдсэн зардлын нийт дүн.
    total_amount: Decimal = ZERO
    by_account: list[ExpenseByAccount] = []
