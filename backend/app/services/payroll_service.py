"""Цалингийн тооцоо — ажилтан, сарын хугацаа, ХХОАТ/НДШ, журналын бичилт.

Тооцооны дараалал (ажилтан тус бүрд):

    ажилласан цалин = үндсэн цалин × ажилласан хоног / сарын хоног
    нийт цалин      = ажилласан цалин + урамшуулал + бусад нэмэгдэл
    НДШ (ажилтан)   = нийт цалин × ажилтны хувь        (дээд хязгаартай)
    ХХОАТ суурь     = нийт цалин − НДШ (ажилтан)
    ХХОАТ           = max(0, суурь × хувь − сарын хөнгөлөлт)
    гарт олгох      = нийт цалин − НДШ − ХХОАТ − урьдчилгаа − бусад суутгал
    НДШ (ажил олгогч) = нийт цалин × ажил олгогчийн хувь   (зардал болно)

Хувь хэмжээ бүр тохиргооноос ирнэ (`payroll_*`). Хугацаа үүсгэх үед тухайн
үеийн хувийг хугацаанд ХУУЛЖ хадгална — хууль өөрчлөгдсөн ч хуучин тооцоо
хэвээр үлдэнэ.

Дүрэм: энэ модуль **хэзээ ч** `db.commit()` дуудахгүй.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventType, PayrollPayTarget, PayrollStatus, SourceType
from app.models.advance import EmployeeAdvance
from app.models.payroll import Employee, PayrollLine, PayrollPeriod
from app.models.user import User
from app.money import q2
from app.stationtime import today_local
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import posting
from app.services.posting_rules import (
    build_advance_lines,
    build_payroll_lines,
    build_payroll_payment_lines,
)
from app.services.settings_service import get_setting

ZERO = Decimal("0.00")


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _user_id(user: User | None) -> uuid.UUID | None:
    return getattr(user, "id", None) if user else None


def _period_label(period: PayrollPeriod) -> str:
    return f"{period.year}.{period.month:02d}"


def _period_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


async def _rates(db: AsyncSession) -> dict[str, Decimal]:
    """Тохиргооноос цалингийн хувь хэмжээг уншина."""
    async def num(key: str, default: str) -> Decimal:
        raw = await get_setting(db, key)
        try:
            return Decimal(str(raw)) if raw not in (None, "") else Decimal(default)
        except Exception:  # noqa: BLE001 — буруу утга тохируулсан бол анхдагчийг авна
            return Decimal(default)

    return {
        "si_employee": await num("payroll_si_employee_rate", "0.115"),
        "si_employer": await num("payroll_si_employer_rate", "0.125"),
        "pit": await num("payroll_pit_rate", "0.10"),
        "pit_credit": await num("payroll_pit_credit", "20000"),
        "si_cap": await num("payroll_si_base_cap", "0"),
    }


# --------------------------------------------------------------------------- #
# Ажилтан
# --------------------------------------------------------------------------- #
async def list_employees(
    db: AsyncSession,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
    search: str | None = None,
    branch_id: uuid.UUID | None = None,
    hired_from: date | None = None,
    hired_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> dict[str, Any]:
    from sqlalchemy import or_

    from app.models.branch import Branch
    from app.stationtime import day_end, day_start

    filters = []
    if active_only:
        filters.append(Employee.is_active.is_(True))
    if is_active is not None:
        filters.append(Employee.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip()}%"
        # Бүх мэдээллээр хайна — нэр, албан тушаал, регистр, НД, утас, данс.
        filters.append(
            or_(
                Employee.full_name.ilike(pattern),
                Employee.position.ilike(pattern),
                Employee.register_no.ilike(pattern),
                Employee.social_no.ilike(pattern),
                Employee.phone.ilike(pattern),
                Employee.bank_account.ilike(pattern),
            )
        )
    if branch_id is not None:
        filters.append(Employee.branch_id == branch_id)
    if hired_from is not None:
        filters.append(Employee.hire_date >= hired_from)
    if hired_to is not None:
        filters.append(Employee.hire_date <= hired_to)
    # Бүртгэсэн огноог станцын цагийн бүсээр (CONTRACTS.md §1a).
    if created_from is not None:
        filters.append(Employee.created_at >= day_start(created_from))
    if created_to is not None:
        filters.append(Employee.created_at <= day_end(created_to))

    total = await db.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
    rows = (
        await db.scalars(select(Employee).where(*filters).order_by(Employee.full_name))
    ).all()

    # Салбарын нэрийг хавсаргана (EmployeeOut.branch_name).
    branch_names = dict((await db.execute(select(Branch.id, Branch.name))).all())
    for row in rows:
        row.branch_name = branch_names.get(row.branch_id)
    return {"items": rows, "total": total}


async def create_employee(db: AsyncSession, user: User | None, **data: Any) -> Employee:
    employee = Employee(**data)
    db.add(employee)
    await db.flush()
    await audit(
        db,
        user_id=_user_id(user),
        action="employee.create",
        entity_type="employee",
        entity_id=employee.id,
        after={"full_name": employee.full_name, "base_salary": str(employee.base_salary)},
    )
    return employee


async def update_employee(
    db: AsyncSession, user: User | None, employee: Employee, **data: Any
) -> Employee:
    before = {"full_name": employee.full_name, "base_salary": str(employee.base_salary)}
    for key, value in data.items():
        if value is not None:
            setattr(employee, key, value)
    await db.flush()
    await audit(
        db,
        user_id=_user_id(user),
        action="employee.update",
        entity_type="employee",
        entity_id=employee.id,
        before=before,
        after={"full_name": employee.full_name, "base_salary": str(employee.base_salary)},
    )
    return employee


# --------------------------------------------------------------------------- #
# Тооцоолол
# --------------------------------------------------------------------------- #
def compute_line(
    *,
    base_salary: Decimal,
    worked_days: Decimal,
    month_days: Decimal,
    bonus: Decimal,
    other_addition: Decimal,
    advance: Decimal,
    other_deduction: Decimal,
    rates: dict[str, Decimal],
    si_enabled: bool = True,
) -> dict[str, Decimal]:
    """Нэг ажилтны цалингийн бүрэн тооцоо — цэвэр функц (тесттэй).

    ``si_enabled=False`` үед татварын тооцоо огт хийгдэхгүй: НДШ (ажилтан ба
    ажил олгогч) болон ХХОАТ бүгд 0.  Гарт олгох дүн нь нийт цалингаас зөвхөн
    урьдчилгаа, бусад суутгалыг хассан дүн болно.
    """
    base_salary = q2(base_salary)
    month_days = _d(month_days)
    worked_days = _d(worked_days)

    if month_days <= 0:
        earned = base_salary
    else:
        ratio = min(worked_days / month_days, Decimal("1"))
        earned = q2(base_salary * ratio)

    gross = q2(earned + q2(bonus) + q2(other_addition))

    if si_enabled:
        si_base = gross
        cap = rates["si_cap"]
        if cap > 0:
            si_base = min(gross, q2(cap))
        si_employee = q2(si_base * rates["si_employee"])
        si_employer = q2(si_base * rates["si_employer"])

        taxable = q2(gross - si_employee)
        pit = q2(taxable * rates["pit"] - rates["pit_credit"])
        if pit < 0:
            pit = ZERO
    else:
        # Татварын тооцоонд ороогүй ажилтан — НДШ ч, ХХОАТ ч бодогдохгүй.
        si_employee = ZERO
        si_employer = ZERO
        taxable = ZERO
        pit = ZERO

    net = q2(gross - si_employee - pit - q2(advance) - q2(other_deduction))

    return {
        "earned_salary": earned,
        "gross": gross,
        "si_employee": si_employee,
        "si_employer": si_employer,
        "taxable": taxable,
        "pit": pit,
        "net": net,
    }


def employment_window(
    employee: Any, year: int, month: int
) -> tuple[date, date, Decimal] | None:
    """Ажилтны тухайн сард ажилласан хугацаа ба хоногийн тоо.

    Ажилд орсон/гарсан огноог сарын хүрээтэй огтолцуулна:

        эхлэл = max(сарын эхлэл, ажилд орсон огноо)
        төгсгөл = min(сарын төгсгөл, ажлаас гарсан огноо)

    Огтолцохгүй бол `None` — тухайн сард энэ ажилтан ажиллаагүй тул
    цалингийн жагсаалтад ер нь орохгүй.

    Хоногийн тоог **хоёр талыг нь оруулж** тоолно: 07-15-аас 07-31 бол 17 хоног.
    """
    month_start = date(year, month, 1)
    month_end = _period_end(year, month)

    hire = getattr(employee, "hire_date", None)
    end = getattr(employee, "end_date", None)

    start = max(month_start, hire) if hire else month_start
    finish = min(month_end, end) if end else month_end

    if start > finish:
        return None
    return start, finish, Decimal((finish - start).days + 1)



# --------------------------------------------------------------------------- #
# Хугацаа
# --------------------------------------------------------------------------- #
async def get_or_create_period(
    db: AsyncSession,
    user: User | None,
    year: int,
    month: int,
    employee_ids: list[uuid.UUID] | None = None,
) -> PayrollPeriod:
    """Тухайн сарын хугацааг үүсгэж, ажилтан бүрд мөр нээнэ.

    ``employee_ids`` өгвөл зөвхөн тэдгээр ажилтныг оруулж, сарыг «гараар
    сонгосон» гэж тэмдэглэнэ — дахин тооцоолоход бусад ажилтан нэмэгдэхгүй.
    """
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="Сар 1–12 хооронд байх ёстой")

    period = await db.scalar(
        select(PayrollPeriod).where(PayrollPeriod.year == year, PayrollPeriod.month == month)
    )
    if period is not None:
        return period

    picked = set(employee_ids or [])
    rates = await _rates(db)
    period = PayrollPeriod(
        year=year,
        month=month,
        auto_sync=not picked,
        status=str(PayrollStatus.DRAFT),
        si_employee_rate=rates["si_employee"],
        si_employer_rate=rates["si_employer"],
        pit_rate=rates["pit"],
        pit_credit=rates["pit_credit"],
    )
    db.add(period)
    await db.flush()

    month_days = Decimal(calendar.monthrange(year, month)[1])

    # Идэвхтэй ажилтан төдийгүй ТУХАЙН САРД ажиллаж байсан хүн бүрийг авна.
    # Ажлаас гарсан хүн идэвхгүй болсон ч сүүлийн цалингаа авах ёстой.
    employees = (await db.scalars(select(Employee).order_by(Employee.full_name))).all()

    added = 0
    for employee in employees:
        if picked and employee.id not in picked:
            continue  # сонгогдоогүй ажилтан
        window = employment_window(employee, year, month)
        if window is None:
            continue  # энэ сард ажиллаагүй
        start, finish, days = window
        db.add(
            PayrollLine(
                period_id=period.id,
                employee_id=employee.id,
                base_salary=q2(_d(employee.base_salary)),
                si_enabled=bool(getattr(employee, "si_enabled", True)),
                worked_days=days,
                month_days=month_days,
                worked_from=start,
                worked_to=finish,
            )
        )
        added += 1
    await db.flush()
    await recalculate(db, period)
    return period


async def delete_draft(db: AsyncSession, user: User | None, period: PayrollPeriod) -> None:
    """Ноорог тооцоог бүрэн устгана — мөрүүд нь cascade-аар хамт устана.

    Ноорогт журналын бичилт хийгдээгүй тул НББ-д ул мөр үлдэхгүй. Батлагдсан
    буюу олгогдсон тооцоог устгахыг хориглоно — тэдгээрийг залруулга хийж
    буцаах ёстой.
    """
    if str(period.status) != str(PayrollStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Зөвхөн ноорог тооцоог цуцална")

    label = _period_label(period)
    await audit(
        db,
        user_id=_user_id(user),
        action="payroll.cancel_draft",
        entity_type="payroll_period",
        entity_id=period.id,
        before={
            "period": label,
            "status": str(period.status),
            "gross_total": str(period.gross_total),
            "employee_count": str(len(period.lines)),
        },
    )
    await db.delete(period)
    await db.flush()


async def _sync_lines(db: AsyncSession, period: PayrollPeriod) -> None:
    """Ноорог хугацааны мөрүүдийг ажилтны бүртгэлтэй тааруулна.

    * Тухайн сард ажилласан ч мөргүй байгаа ажилтанд мөр нээнэ
      (тооцоо хийсний ДАРАА ажилд орсон хүн).
    * Ажилд орсон/гарсан огноо нь өөрчлөгдөж, тухайн сард огт ажиллаагүй
      болсон ажилтны мөрийг хасна.
    * Ажилласан хугацааг дахин тооцоолж, `worked_days`-ийг шинэчилнэ —
      гэхдээ гараар засаж багасгасан утгыг хэвээр үлдээнэ.
    """
    existing = {
        line.employee_id: line
        for line in (
            await db.scalars(select(PayrollLine).where(PayrollLine.period_id == period.id))
        ).all()
    }
    employees = (await db.scalars(select(Employee).order_by(Employee.full_name))).all()
    month_days = Decimal(calendar.monthrange(period.year, period.month)[1])

    for employee in employees:
        window = employment_window(employee, period.year, period.month)
        line = existing.get(employee.id)

        if window is None:
            # Энэ сард ажиллаагүй — мөр байвал хасна.
            if line is not None:
                await db.delete(line)
            continue

        start, finish, days = window
        if line is None:
            # Ажилтнаа гараар сонгосон сард сонголтыг хүндэтгэж, шинээр нэмэхгүй.
            if not period.auto_sync:
                continue
            db.add(
                PayrollLine(
                    period_id=period.id,
                    employee_id=employee.id,
                    base_salary=q2(_d(employee.base_salary)),
                    si_enabled=bool(getattr(employee, "si_enabled", True)),
                    worked_days=days,
                    month_days=month_days,
                    worked_from=start,
                    worked_to=finish,
                )
            )
            continue

        # Хугацааны хил өөрчлөгдсөн бол шинэчилнэ. Хэрэглэгч гараар багасгасан
        # (жишээ нь чөлөө авсан) бол түүнийг нь дарж бичихгүй.
        line.month_days = month_days
        line.worked_from = start
        line.worked_to = finish
        if _d(line.worked_days) > days:
            line.worked_days = days

    await db.flush()


async def recalculate(db: AsyncSession, period: PayrollPeriod) -> PayrollPeriod:
    """Мөр бүрийг дахин тооцоолж, хугацааны нийлбэрийг шинэчилнэ."""
    if str(period.status) != str(PayrollStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Зөвхөн ноорог хугацааг дахин тооцоолно")

    # Хувь хэмжээг ХУГАЦААНААС авна — тохиргоо дараа өөрчлөгдсөн ч энэ сарын
    # тооцоо анх батлагдсан дүрмээрээ хэвээр үлдэнэ.
    # Зөвхөн НДШ-ийн дээд хязгаар нь хугацаанд хадгалагддаггүй тул тохиргооноос.
    rates = {
        "si_employee": _d(period.si_employee_rate),
        "si_employer": _d(period.si_employer_rate),
        "pit": _d(period.pit_rate),
        "pit_credit": _d(period.pit_credit),
        "si_cap": (await _rates(db))["si_cap"],
    }

    totals = {"gross": ZERO, "si_employee": ZERO, "si_employer": ZERO, "pit": ZERO, "net": ZERO}

    await _sync_lines(db, period)

    lines = (await db.scalars(select(PayrollLine).where(PayrollLine.period_id == period.id))).all()
    for line in lines:
        # Ажилласан хоног сарын хоногоос хэтэрсэн бол засна (хуучин өгөгдлийг
        # эдгээх). Тооцоо аль хэдийн 1-ээр таслагддаг ч дэлгэцэнд "52/30" гэж
        # утгагүй харагдахаас сэргийлнэ.
        month_days = _d(line.month_days)
        if month_days > 0 and _d(line.worked_days) > month_days:
            line.worked_days = month_days

        result = compute_line(
            base_salary=_d(line.base_salary),
            worked_days=_d(line.worked_days),
            month_days=_d(line.month_days),
            bonus=_d(line.bonus),
            other_addition=_d(line.other_addition),
            advance=_d(line.advance),
            other_deduction=_d(line.other_deduction),
            rates=rates,
            si_enabled=bool(line.si_enabled),
        )
        line.earned_salary = result["earned_salary"]
        line.gross = result["gross"]
        line.si_employee = result["si_employee"]
        line.si_employer = result["si_employer"]
        line.taxable = result["taxable"]
        line.pit = result["pit"]
        line.net = result["net"]

        totals["gross"] = q2(totals["gross"] + result["gross"])
        totals["si_employee"] = q2(totals["si_employee"] + result["si_employee"])
        totals["si_employer"] = q2(totals["si_employer"] + result["si_employer"])
        totals["pit"] = q2(totals["pit"] + result["pit"])
        totals["net"] = q2(totals["net"] + result["net"])

    period.gross_total = totals["gross"]
    period.si_employee_total = totals["si_employee"]
    period.si_employer_total = totals["si_employer"]
    period.pit_total = totals["pit"]
    period.net_total = totals["net"]
    await db.flush()
    return period


async def update_line(
    db: AsyncSession, period: PayrollPeriod, line: PayrollLine, **data: Any
) -> PayrollPeriod:
    """Мөрийн оролтыг засаад бүх тооцоог дахин гүйцэтгэнэ."""
    if str(period.status) != str(PayrollStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Батлагдсан цалинг засах боломжгүй")

    for key, value in data.items():
        if value is None:
            continue
        if key == "note":
            line.note = value
            continue
        if key == "si_enabled":
            # Мөнгө биш логик тэмдэг — зөвхөн энэ мөрд үйлчилнэ.
            line.si_enabled = bool(value)
            continue
        amount = q2(_d(value))
        if amount < 0:
            raise HTTPException(status_code=422, detail="Сөрөг утга оруулах боломжгүй")
        if key == "worked_days":
            # Ажилласан хоног сарын хоногоос хэтэрч болохгүй — эс бөгөөс
            # тайланд "52 / 30" гэх мэт утгагүй харагдана.
            month_days = _d(line.month_days)
            if month_days > 0 and amount > month_days:
                raise HTTPException(
                    status_code=422,
                    detail=f"Ажилласан хоног {month_days:.0f}-аас их байж болохгүй",
                )
        setattr(line, key, amount)
    await db.flush()
    return await recalculate(db, period)


async def approve(db: AsyncSession, user: User | None, period: PayrollPeriod) -> PayrollPeriod:
    """Цалинг батлаж журналд бичнэ (2401/2402/2403 өглөг үүснэ)."""
    if str(period.status) != str(PayrollStatus.DRAFT):
        raise HTTPException(status_code=422, detail="Аль хэдийн батлагдсан")
    if _d(period.gross_total) <= 0:
        raise HTTPException(status_code=422, detail="Тооцоолсон цалин байхгүй байна")

    entry_date = _period_end(period.year, period.month)
    await posting.post(
        db,
        event_type=str(EventType.PAYROLL_POSTED),
        source_type=str(SourceType.PAYROLL),
        source_id=period.id,
        entry_date=entry_date,
        description=f"Цалингийн тооцоо {_period_label(period)}",
        lines=build_payroll_lines(period),
        posted_by=_user_id(user),
    )

    period.status = str(PayrollStatus.APPROVED)
    period.approved_by = _user_id(user)
    period.approved_at = datetime.now(UTC)
    await db.flush()

    await emit(
        db,
        aggregate_type="payroll",
        aggregate_id=period.id,
        event_type=str(EventType.PAYROLL_POSTED),
        payload={
            "period": _period_label(period),
            "gross_total": str(period.gross_total),
            "net_total": str(period.net_total),
            "pit_total": str(period.pit_total),
        },
    )
    await audit(
        db,
        user_id=_user_id(user),
        action="payroll.approve",
        entity_type="payroll_period",
        entity_id=period.id,
        after={"period": _period_label(period), "gross_total": str(period.gross_total)},
    )
    return period


async def pay(
    db: AsyncSession,
    user: User | None,
    period: PayrollPeriod,
    *,
    target: str,
    amount: Decimal | str | None = None,
    paid_from: str = "bank",
    payment_date: date | None = None,
) -> PayrollPeriod:
    """Цалин / ХХОАТ / НДШ-ийн өглөгийг төлнө."""
    if str(period.status) not in (str(PayrollStatus.APPROVED), str(PayrollStatus.PAID)):
        raise HTTPException(status_code=422, detail="Эхлээд цалинг батлана уу")

    target = str(target)
    owed_map = {
        str(PayrollPayTarget.SALARY): (_d(period.net_total), _d(period.paid_salary)),
        str(PayrollPayTarget.PIT): (_d(period.pit_total), _d(period.paid_pit)),
        str(PayrollPayTarget.SOCIAL): (
            q2(_d(period.si_employee_total) + _d(period.si_employer_total)),
            _d(period.paid_social),
        ),
    }
    if target not in owed_map:
        raise HTTPException(status_code=422, detail="Төлбөрийн зорилт буруу байна")

    total_owed, already_paid = owed_map[target]
    remaining = q2(total_owed - already_paid)
    if remaining <= 0:
        raise HTTPException(status_code=422, detail="Энэ хэсэг бүрэн төлөгдсөн байна")

    value = remaining if amount in (None, "") else q2(_d(amount))
    if value <= 0:
        raise HTTPException(status_code=422, detail="Төлбөрийн дүн 0-ээс их байх ёстой")
    if value > remaining:
        raise HTTPException(
            status_code=422, detail=f"Төлбөрийн дүн үлдэгдлээс ({remaining}) их байна"
        )

    label = {
        str(PayrollPayTarget.SALARY): "цалин",
        str(PayrollPayTarget.PIT): "ХХОАТ",
        str(PayrollPayTarget.SOCIAL): "НДШ",
    }[target]
    memo = f"Цалин {_period_label(period)} — {label} төлөв"

    payment = type(
        "PayrollPayment",
        (),
        {"amount": value, "target": target, "paid_from": paid_from, "memo": memo},
    )()

    await posting.post(
        db,
        event_type=str(EventType.PAYROLL_PAID),
        source_type=str(SourceType.PAYROLL),
        # Нэг хугацаанд гурван төрлийн төлбөр бичигдэх тул source_id-г
        # зорилтоор нь салгаж идемпотентийг хадгална.
        source_id=uuid.uuid5(period.id, target),
        entry_date=payment_date or _period_end(period.year, period.month),
        description=memo,
        lines=build_payroll_payment_lines(payment),
        posted_by=_user_id(user),
    )

    if target == str(PayrollPayTarget.SALARY):
        period.paid_salary = q2(already_paid + value)
    elif target == str(PayrollPayTarget.PIT):
        period.paid_pit = q2(already_paid + value)
    else:
        period.paid_social = q2(already_paid + value)

    fully_paid = (
        _d(period.paid_salary) >= _d(period.net_total)
        and _d(period.paid_pit) >= _d(period.pit_total)
        and _d(period.paid_social) >= q2(_d(period.si_employee_total) + _d(period.si_employer_total))
    )
    if fully_paid:
        period.status = str(PayrollStatus.PAID)
    await db.flush()

    await audit(
        db,
        user_id=_user_id(user),
        action="payroll.pay",
        entity_type="payroll_period",
        entity_id=period.id,
        after={"target": target, "amount": str(value), "paid_from": paid_from},
    )
    return period


# --------------------------------------------------------------------------- #
# Унших
# --------------------------------------------------------------------------- #
async def period_detail(db: AsyncSession, period: PayrollPeriod) -> dict[str, Any]:
    lines = (
        await db.scalars(select(PayrollLine).where(PayrollLine.period_id == period.id))
    ).all()
    employee_ids = {line.employee_id for line in lines}
    employees: dict[uuid.UUID, Employee] = {}
    if employee_ids:
        employees = {
            e.id: e
            for e in (await db.scalars(select(Employee).where(Employee.id.in_(employee_ids)))).all()
        }

    si_total = q2(_d(period.si_employee_total) + _d(period.si_employer_total))
    return {
        "id": period.id,
        "year": period.year,
        "month": period.month,
        "label": _period_label(period),
        "status": period.status,
        "si_employee_rate": _d(period.si_employee_rate),
        "si_employer_rate": _d(period.si_employer_rate),
        "pit_rate": _d(period.pit_rate),
        "pit_credit": _d(period.pit_credit),
        "gross_total": _d(period.gross_total),
        "si_employee_total": _d(period.si_employee_total),
        "si_employer_total": _d(period.si_employer_total),
        "si_total": si_total,
        "pit_total": _d(period.pit_total),
        "net_total": _d(period.net_total),
        "employer_cost": q2(_d(period.gross_total) + _d(period.si_employer_total)),
        "paid_salary": _d(period.paid_salary),
        "paid_pit": _d(period.paid_pit),
        "paid_social": _d(period.paid_social),
        "owed_salary": q2(_d(period.net_total) - _d(period.paid_salary)),
        "owed_pit": q2(_d(period.pit_total) - _d(period.paid_pit)),
        "owed_social": q2(si_total - _d(period.paid_social)),
        "employee_count": len(lines),
        "lines": [
            {
                "id": line.id,
                "employee_id": line.employee_id,
                "employee_name": employees[line.employee_id].full_name
                if line.employee_id in employees
                else "—",
                "position": employees[line.employee_id].position
                if line.employee_id in employees
                else None,
                "si_enabled": bool(line.si_enabled),
                "base_salary": _d(line.base_salary),
                "worked_days": _d(line.worked_days),
                "month_days": _d(line.month_days),
                "worked_from": line.worked_from,
                "worked_to": line.worked_to,
                #: Бүтэн сар ажиллаагүй бол дэлгэцэнд онцолж харуулна.
                "partial_month": bool(
                    line.worked_from
                    and line.worked_to
                    and _d(line.worked_days) < _d(line.month_days)
                ),
                "earned_salary": _d(line.earned_salary),
                "bonus": _d(line.bonus),
                "other_addition": _d(line.other_addition),
                "gross": _d(line.gross),
                "si_employee": _d(line.si_employee),
                "si_employer": _d(line.si_employer),
                "taxable": _d(line.taxable),
                "pit": _d(line.pit),
                "advance": _d(line.advance),
                "other_deduction": _d(line.other_deduction),
                "net": _d(line.net),
                "note": line.note,
            }
            for line in sorted(lines, key=lambda x: employees.get(x.employee_id).full_name if x.employee_id in employees else "")
        ],
    }


async def list_periods(db: AsyncSession, *, limit: int = 24) -> dict[str, Any]:
    rows = (
        await db.scalars(
            select(PayrollPeriod)
            .order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())
            .limit(limit)
        )
    ).all()
    return {
        "items": [
            {
                "id": p.id,
                "year": p.year,
                "month": p.month,
                "label": _period_label(p),
                "status": p.status,
                "gross_total": _d(p.gross_total),
                "net_total": _d(p.net_total),
                "pit_total": _d(p.pit_total),
                "si_total": q2(_d(p.si_employee_total) + _d(p.si_employer_total)),
                "employer_cost": q2(_d(p.gross_total) + _d(p.si_employer_total)),
            }
            for p in rows
        ],
        "total": len(rows),
    }


# --------------------------------------------------------------------------- #
# Урьдчилгаа
# --------------------------------------------------------------------------- #
async def give_advance(
    db: AsyncSession,
    user: User | None,
    *,
    employee_id: uuid.UUID,
    amount: Decimal | str,
    paid_from: str = "cash",
    advance_date: date | None = None,
    note: str | None = None,
) -> EmployeeAdvance:
    """Ажилтанд урьдчилгаа олгож 1205 дансанд авлага үүсгэнэ.

    Бэлнээр олгосон бол ээлжийн байвал зохих кассаас автоматаар хасагдана
    (`shift_service._other_cash_movement` нь 1101-ийн хөдөлгөөнийг уншдаг).
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Ажилтан олдсонгүй")

    value = q2(_d(amount))
    if value <= 0:
        raise HTTPException(status_code=422, detail="Урьдчилгааны дүн 0-ээс их байх ёстой")
    if paid_from not in ("cash", "bank"):
        raise HTTPException(status_code=422, detail="Эх үүсвэр буруу байна")

    row = EmployeeAdvance(
        employee_id=employee_id,
        advance_date=advance_date or today_local(),
        amount=value,
        paid_from=paid_from,
        note=(note or "").strip() or None,
        created_by=_user_id(user),
    )
    db.add(row)
    await db.flush()

    memo = f"Урьдчилгаа — {employee.full_name}"
    payload = type("Adv", (), {"amount": value, "paid_from": paid_from, "memo": memo})()
    await posting.post(
        db,
        event_type=str(EventType.ADVANCE_PAID),
        source_type=str(SourceType.PAYROLL),
        source_id=row.id,
        entry_date=row.advance_date,
        description=memo,
        lines=build_advance_lines(payload),
        posted_by=_user_id(user),
    )
    await audit(
        db,
        user_id=_user_id(user),
        action="payroll.advance",
        entity_type="employee_advance",
        entity_id=row.id,
        after={"employee": employee.full_name, "amount": str(value), "paid_from": paid_from},
    )
    return row


async def list_advances(db: AsyncSession, *, employee_id: uuid.UUID | None = None) -> dict[str, Any]:
    filters = []
    if employee_id is not None:
        filters.append(EmployeeAdvance.employee_id == employee_id)
    rows = (
        await db.scalars(
            select(EmployeeAdvance).where(*filters).order_by(EmployeeAdvance.advance_date.desc())
        )
    ).all()
    names = {
        e.id: e.full_name
        for e in (await db.scalars(select(Employee))).all()
    }
    return {
        "items": [
            {
                "id": r.id,
                "employee_id": r.employee_id,
                "employee_name": names.get(r.employee_id, "—"),
                "advance_date": r.advance_date,
                "amount": _d(r.amount),
                "paid_from": r.paid_from,
                "note": r.note,
            }
            for r in rows
        ],
        "total": len(rows),
    }
