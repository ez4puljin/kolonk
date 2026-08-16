"""Ажилтан ба цалингийн схемүүд."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.enums import PayrollStatus

ZERO = Decimal("0.00")

PAYROLL_STATUS_NAMES_MN: dict[str, str] = {
    PayrollStatus.DRAFT: "Ноорог",
    PayrollStatus.APPROVED: "Батлагдсан",
    PayrollStatus.PAID: "Олгосон",
}


# --------------------------------------------------------------------------- #
# Ажилтан
# --------------------------------------------------------------------------- #
class EmployeeCreate(BaseModel):
    full_name: str
    base_salary: Decimal = ZERO
    #: Аль салбарт ажилладаг вэ.
    branch_id: uuid.UUID | None = None
    si_enabled: bool = True
    position: str | None = None
    register_no: str | None = None
    social_no: str | None = None
    phone: str | None = None
    bank_account: str | None = None
    #: Ажилд орсон/гарсан огноо — сарын дундуур ажилласан цалинг хоногоор нь
    #: автоматаар хуваарилахад ашиглагдана.
    hire_date: date | None = None
    end_date: date | None = None
    user_id: uuid.UUID | None = None
    note: str | None = None


class EmployeeUpdate(BaseModel):
    full_name: str | None = None
    base_salary: Decimal | None = None
    branch_id: uuid.UUID | None = None
    si_enabled: bool | None = None
    position: str | None = None
    register_no: str | None = None
    social_no: str | None = None
    phone: str | None = None
    bank_account: str | None = None
    hire_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    note: str | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    base_salary: Decimal = ZERO
    branch_id: uuid.UUID | None = None
    branch_name: str | None = None
    #: НДШ бодох эсэх.
    si_enabled: bool = True
    position: str | None = None
    register_no: str | None = None
    social_no: str | None = None
    phone: str | None = None
    bank_account: str | None = None
    hire_date: date | None = None
    end_date: date | None = None
    is_active: bool = True
    note: str | None = None
    created_at: datetime | None = None


class EmployeeListOut(BaseModel):
    items: list[EmployeeOut]
    total: int


# --------------------------------------------------------------------------- #
# Цалингийн хугацаа
# --------------------------------------------------------------------------- #
class PayrollPeriodCreate(BaseModel):
    year: int
    month: int
    #: Хоосон бол тухайн сард ажилласан бүх ажилтан орно.
    employee_ids: list[uuid.UUID] | None = None


class PayrollLineUpdate(BaseModel):
    #: Энэ мөрд НДШ бодох эсэх (ажилтны анхдагчийг тухайн сард дарна).
    si_enabled: bool | None = None
    worked_days: Decimal | None = None
    bonus: Decimal | None = None
    other_addition: Decimal | None = None
    advance: Decimal | None = None
    other_deduction: Decimal | None = None
    base_salary: Decimal | None = None
    note: str | None = None


class PayrollLineOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    position: str | None = None
    #: Энэ мөрд НДШ бодох эсэх.
    si_enabled: bool = True
    base_salary: Decimal = ZERO
    worked_days: Decimal = ZERO
    month_days: Decimal = ZERO
    #: Тухайн сард ажилласан бодит хугацаа (сарын дундуур орсон/гарсан бол богино).
    worked_from: date | None = None
    worked_to: date | None = None
    partial_month: bool = False
    earned_salary: Decimal = ZERO
    bonus: Decimal = ZERO
    other_addition: Decimal = ZERO
    gross: Decimal = ZERO
    si_employee: Decimal = ZERO
    si_employer: Decimal = ZERO
    taxable: Decimal = ZERO
    pit: Decimal = ZERO
    advance: Decimal = ZERO
    other_deduction: Decimal = ZERO
    net: Decimal = ZERO
    note: str | None = None


class PayrollPeriodOut(BaseModel):
    id: uuid.UUID
    year: int
    month: int
    label: str
    status: str
    si_employee_rate: Decimal = ZERO
    si_employer_rate: Decimal = ZERO
    pit_rate: Decimal = ZERO
    pit_credit: Decimal = ZERO
    gross_total: Decimal = ZERO
    si_employee_total: Decimal = ZERO
    si_employer_total: Decimal = ZERO
    si_total: Decimal = ZERO
    pit_total: Decimal = ZERO
    net_total: Decimal = ZERO
    #: Ажил олгогчид тусах нийт зардал = нийт цалин + ажил олгогчийн НДШ.
    employer_cost: Decimal = ZERO
    paid_salary: Decimal = ZERO
    paid_pit: Decimal = ZERO
    paid_social: Decimal = ZERO
    owed_salary: Decimal = ZERO
    owed_pit: Decimal = ZERO
    owed_social: Decimal = ZERO
    employee_count: int = 0
    lines: list[PayrollLineOut] = []


class PayrollPeriodRow(BaseModel):
    id: uuid.UUID
    year: int
    month: int
    label: str
    status: str
    gross_total: Decimal = ZERO
    net_total: Decimal = ZERO
    pit_total: Decimal = ZERO
    si_total: Decimal = ZERO
    employer_cost: Decimal = ZERO


class PayrollPeriodListOut(BaseModel):
    items: list[PayrollPeriodRow]
    total: int


class PayrollPayRequest(BaseModel):
    #: `salary` | `pit` | `social`
    target: str
    #: Хоосон бол үлдэгдэл бүтнээр төлөгдөнө.
    amount: Decimal | None = None
    #: `bank` эсвэл `cash`
    paid_from: str = "bank"
    payment_date: date | None = None


class AdvanceCreate(BaseModel):
    employee_id: uuid.UUID
    amount: Decimal
    #: `cash` эсвэл `bank`
    paid_from: str = "cash"
    advance_date: date | None = None
    note: str | None = None


class AdvanceOut(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    advance_date: date
    amount: Decimal = ZERO
    paid_from: str
    note: str | None = None


class AdvanceListOut(BaseModel):
    items: list[AdvanceOut]
    total: int
