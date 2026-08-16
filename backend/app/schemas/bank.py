"""Банкны данс ба хуулгын схемүүд.

Мөнгө бүгд ``Decimal`` — JSON руу string-ээр гарна (CONTRACTS.md §2).
Хэрэглэгчид харагдах бүх текст монгол.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

ZERO = Decimal("0.00")

#: Хуулгын мөрөнд дутуу байгаа зүйлийн монгол нэр.
MISSING_NAMES_MN: dict[str, str] = {
    "target": "Харилцагч / ангилал",
    "desc": "Гүйлгээний утга",
}


# --------------------------------------------------------------------------- #
# Харилцах данс
# --------------------------------------------------------------------------- #
class BankAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank_name: str = Field(min_length=1, max_length=64)
    account_number: str = Field(min_length=1, max_length=32)
    holder_name: str = Field(default="", max_length=128)
    currency: str = Field(default="MNT", min_length=1, max_length=8)
    opening_balance: Decimal = Field(default=ZERO)
    branch_id: uuid.UUID | None = None
    is_fee_default: bool = False
    is_active: bool = True
    note: str | None = Field(default=None, max_length=500)
    sort_order: int = 0


class BankAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank_name: str | None = Field(default=None, min_length=1, max_length=64)
    account_number: str | None = Field(default=None, min_length=1, max_length=32)
    holder_name: str | None = Field(default=None, max_length=128)
    currency: str | None = Field(default=None, min_length=1, max_length=8)
    opening_balance: Decimal | None = None
    branch_id: uuid.UUID | None = None
    is_fee_default: bool | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)
    sort_order: int | None = None


class BankAccountOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None = None
    bank_name: str
    account_number: str
    holder_name: str = ""
    currency: str = "MNT"
    opening_balance: Decimal = ZERO
    #: Ерөнхий дэвтэр дэх цэвэр хөдөлгөөн (дебит − кредит).
    movement: Decimal = ZERO
    balance: Decimal = ZERO
    is_fee_default: bool = False
    is_active: bool = True
    note: str | None = None
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BankAccountListOut(BaseModel):
    items: list[BankAccountOut]
    total: int
    #: Аль ч данстай холбогдоогүй 1110 хөдөлгөөн.
    unassigned: Decimal = ZERO
    #: Дансны нийт үлдэгдэл + хуваарилаагүй = 1110 дансны үлдэгдэл.
    ledger_balance: Decimal = ZERO


# --------------------------------------------------------------------------- #
# Хуулга
# --------------------------------------------------------------------------- #
class StatementFeeOut(BaseModel):
    count: int = 0
    total: Decimal = ZERO
    posted: bool = False
    expense_number: int | None = None


class BankTransactionOut(BaseModel):
    id: uuid.UUID
    txn_date: datetime | None = None
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    bank_description: str = ""
    bank_counterpart: str = ""
    is_fee: bool = False
    description: str = ""
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    contract_id: uuid.UUID | None = None
    contract_no: str | None = None
    expense_account_code: str | None = None
    expense_account_name: str | None = None
    ar_payment_id: uuid.UUID | None = None
    expense_id: uuid.UUID | None = None
    posted_at: datetime | None = None
    is_income: bool = False
    #: ПОС-ын тооцоо (SETTLEMENT) мөр эсэх.
    is_settlement: bool = False
    missing: list[str] = []


class BankStatementOut(BaseModel):
    id: uuid.UUID
    account_number: str = ""
    currency: str = "MNT"
    date_from: date | None = None
    date_to: date | None = None
    filename: str = ""
    uploaded_at: datetime | None = None
    bank_account_id: uuid.UUID | None = None
    bank_name: str | None = None
    txn_count: int = 0
    total_credit: Decimal = ZERO
    total_debit: Decimal = ZERO
    posted_count: int = 0
    ready_count: int = 0
    missing: dict[str, int] = {}
    fee: StatementFeeOut = StatementFeeOut()


class BankStatementDetailOut(BankStatementOut):
    transactions: list[BankTransactionOut] = []


class BankStatementListOut(BaseModel):
    items: list[BankStatementOut]
    total: int


class StatementCalendarOut(BaseModel):
    year: int
    month: int
    days: dict[str, dict[str, int]] = {}


class TransactionUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=500)
    #: Орлогын мөр — аль гэрээний авлага хаагдах вэ (хоосон = цуцлах).
    contract_id: uuid.UUID | None = None
    #: Зарлагын мөр — зардлын дансны код (хоосон = цуцлах).
    expense_account_code: str | None = Field(default=None, max_length=16)


class StatementConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settlement_contract_id: uuid.UUID | None = None
    settlement_description: str | None = Field(default=None, max_length=500)
    fee_account_code: str | None = Field(default=None, max_length=16)
    fee_description: str | None = Field(default=None, max_length=500)


class StatementConfigOut(BaseModel):
    settlement_customer_id: uuid.UUID | None = None
    settlement_customer_name: str | None = None
    settlement_contract_id: uuid.UUID | None = None
    settlement_contract_no: str | None = None
    settlement_description: str = ""
    fee_account_code: str | None = None
    fee_account_name: str | None = None
    fee_description: str = ""


class SetBankAccountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bank_account_id: uuid.UUID | None = None


class PostFeesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Хоосон бол тохиргооны анхдагч ангиллыг ашиглана.
    expense_account_code: str | None = Field(default=None, max_length=16)


class PostAllOut(BaseModel):
    posted: int = 0
    skipped: list[dict[str, str]] = []
    statement: BankStatementDetailOut
