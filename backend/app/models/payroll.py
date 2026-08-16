"""Ажилтан ба цалингийн тооцоо.

Урсгал: ажилтан бүртгэх → сарын хугацаа үүсгэж тооцоолох (ноорог) → батлах
(журналд бичигдэнэ) → цалин/ХХОАТ/НДШ-ийг тус тусад нь төлөх.

Тооцооны бүх хувь хэмжээ (НДШ, ХХОАТ) тохиргоонд байдаг тул хууль өөрчлөгдөхөд
код засах шаардлагагүй. Мөр бүрд тухайн үед хэрэглэсэн хувийг **хадгална** —
ингэснээр хуучин тооцоог дараа нь дахин үзэхэд яг тэр үеийн дүрмээр харагдана.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import PayrollStatus
from app.models.base import Money, TimestampMixin, UUIDPKMixin

#: Хувь хэмжээ — 0.115 гэх мэт (6 аравтын орон).
Rate = Numeric(8, 6)


class Employee(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "employees"

    #: Аль салбарынх вэ (олон салбарын тайлан, шүүлтэд ашиглана).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("branches.id"), index=True
    )

    full_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    #: Регистрийн дугаар (ХХОАТ-ын тайланд шаардлагатай).
    register_no: Mapped[str | None] = mapped_column(String(32))
    #: Нийгмийн даатгалын дэвтрийн дугаар.
    social_no: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    bank_account: Mapped[str | None] = mapped_column(String(64))

    #: Сарын үндсэн цалин.
    base_salary: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: НДШ бодох эсэх. False бол ажилтан ба ажил олгогчийн НДШ 0 болж,
    #: ХХОАТ нь нийт цалингаас шууд бодогдоно (тэтгэвэрт гарсан, гэрээт г.м.).
    si_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)

    hire_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, index=True)

    #: Системд нэвтэрдэг хэрэглэгчтэй холбоо (заавал биш).
    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)


class PayrollPeriod(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_periods"

    __table_args__ = (UniqueConstraint("year", "month", name="uq_payroll_period"),)

    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    #: True бол дахин тооцоолоход шинэ ажилтан автоматаар нэмэгдэнэ.
    #: Ажилтнаа гараар сонгож үүсгэсэн сард False — сонголт хэвээр үлдэнэ.
    auto_sync: Mapped[bool] = mapped_column(nullable=False, default=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PayrollStatus.DRAFT, index=True
    )

    #: Тооцоонд хэрэглэсэн хувь хэмжээ (тухайн үеийн тохиргооны хуулбар).
    si_employee_rate: Mapped[Decimal] = mapped_column(Rate, nullable=False, default=Decimal("0"))
    si_employer_rate: Mapped[Decimal] = mapped_column(Rate, nullable=False, default=Decimal("0"))
    pit_rate: Mapped[Decimal] = mapped_column(Rate, nullable=False, default=Decimal("0"))
    pit_credit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: Нийлбэр дүнгүүд (мөрүүдээс тооцоологдоно).
    gross_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    si_employee_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    si_employer_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    pit_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    net_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: Аль хэсэг нь төлөгдсөн бэ (2401/2402/2403 тус бүрээр).
    paid_salary: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    paid_pit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    paid_social: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    approved_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["PayrollLine"]] = relationship(
        back_populates="period", cascade="all, delete-orphan", lazy="selectin"
    )


class PayrollLine(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_lines"
    __table_args__ = (UniqueConstraint("period_id", "employee_id", name="uq_payroll_line"),)

    period_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )

    #: Ажилласан хоног / сарын нийт хоног — цалинг хувь тэнцүүлэн бодно.
    #: `month_days` нь тухайн сарын жинхэнэ хоног (28/29/30/31).
    worked_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    month_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))

    #: Тухайн сард ажилтны ажилласан бодит хугацаа.
    #: Сарын дундуур ажилд орсон/гарсан бол энэ нь бүтэн сар байхгүй —
    #: `worked_days`-ийн анхдагч утга эндээс тооцоологдоно.
    worked_from: Mapped[date | None] = mapped_column(Date)
    worked_to: Mapped[date | None] = mapped_column(Date)

    #: НДШ бодсон эсэх — тухайн сарын тооцоог хожим өөрчлөхгүйгээр хөлдөөнө.
    si_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)

    base_salary: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: Ажилласан хоногоор тооцсон үндсэн цалин.
    earned_salary: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    bonus: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    other_addition: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: Нийт цалин = earned + bonus + other_addition.
    gross: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    si_employee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    si_employer: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    #: ХХОАТ бодох суурь = gross − si_employee.
    taxable: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    pit: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: Урьдчилгаа, зээл, бусад суутгал.
    advance: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))
    other_deduction: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    #: Гарт олгох = gross − si_employee − pit − advance − other_deduction.
    net: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0"))

    note: Mapped[str | None] = mapped_column(Text)

    period: Mapped[PayrollPeriod] = relationship(back_populates="lines")
