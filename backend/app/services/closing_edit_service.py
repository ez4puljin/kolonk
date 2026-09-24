"""Өдрийн хаалтын цонх — харах, нягтлан/админ засах.

Ээлжийн тайланд түгээгчийн өдрийн хаалтыг «цонх» хэлбэрээр (тушаалт, тос,
зээл, өглөг төлөлт, зарлага, тулгалт) серверт БҮРТГЭГДСЭН байдлаар нь
харуулж, түгээгчийн дэлгэц дээр харсан тулгалттай (``close_input``)
харьцуулна.

Засвар нь хаалтыг бүхэлд нь дахин хийхгүй — дараагийн ээлж энэ ээлжийн
хаалтын милээс эхэлсэн байж болох тул миль, сав хөдлөхгүй. Зөвхөн
тулгалтад нөлөөлөх хэсгүүдийг засна:

* тоолсон бэлэн / банкны терминал / шилжүүлэг — түлш, тосны борлуулалтын
  төлбөрийн хуваарилалт дахин хийгдэнэ;
* зээл нэмэх — түлшний нэгдсэн (бэлэн) борлуулалтаас литрийг харилцагчийн
  зээлийн борлуулалт руу шилжүүлнэ (сав хөдлөхгүй, литр л шилжинэ);
* зээл устгах — эсрэгээр нь нэгдсэн борлуулалт руу буцаана;
* өглөг төлөлт, зарлага нэмэх/устгах.

Засвар бүрийн дараа байвал зохих бэлэн мөнгө, кассын зөрүү, журнал дахин
бодогдоно. Батлагдсан хаалтыг засахаас өмнө батламжийг буцаана.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import EventType, ItemType, PaymentMethod, SaleStatus, SaleType, ShiftStatus, SourceType
from app.models.accounting import Account, ArPayment, JournalEntry
from app.models.expense import Expense
from app.models.fuel import Fuel
from app.models.partner import Contract, Customer
from app.models.sale import Payment, Sale, SaleItem
from app.models.shift import Shift, ShiftClosing
from app.models.user import User
from app.money import q2, q3
from app.services import posting_rules
from app.services.audit_service import audit
from app.services.posting import posting
from app.services.sale_service import compute_totals

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")
CLOSE_NOTE = "Өдрийн хаалт"
EDIT_NOTE = "засвар"

METHOD_MN = {"cash": "бэлэн", "card": "карт", "transfer": "шилжүүлэг"}


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


# --------------------------------------------------------------------------- #
# Ачаалах
# --------------------------------------------------------------------------- #
async def _load(db: AsyncSession, shift_id: uuid.UUID) -> tuple[Shift, ShiftClosing]:
    shift = await db.scalar(select(Shift).where(Shift.id == shift_id))
    if shift is None:
        raise HTTPException(status_code=404, detail="Ээлж олдсонгүй")
    closing = await db.scalar(select(ShiftClosing).where(ShiftClosing.shift_id == shift.id))
    if closing is None:
        raise HTTPException(status_code=404, detail="Энэ ээлжид өдрийн хаалт хийгдээгүй")
    return shift, closing


async def _editable(db: AsyncSession, shift_id: uuid.UUID) -> tuple[Shift, ShiftClosing]:
    shift, closing = await _load(db, shift_id)
    if shift.status == str(ShiftStatus.OPEN) or shift.closed_at is None:
        raise HTTPException(status_code=422, detail="Ээлж хаагдаагүй байна")
    if closing.approved_at is not None:
        raise HTTPException(status_code=422, detail="Батлагдсан хаалт — эхлээд батламжийг буцаана уу")
    return shift, closing


def _people(shift: Shift) -> list[uuid.UUID]:
    from app.services.shift_service import _shift_people  # noqa: PLC0415

    return _shift_people(shift)


def _window_end(shift: Shift):
    return shift.closed_at


def _inside(shift: Shift):
    """Засварын бичилтийг ээлжийн хугацаанд (хаалтаас 1 микросекундын өмнө)
    байршуулна — ингэснээр ээлжийн кассын тооцоонд орно."""
    return max(shift.opened_at, shift.closed_at - timedelta(microseconds=1))


async def _sale(db: AsyncSession, sale_id: uuid.UUID | None) -> Sale | None:
    if sale_id is None:
        return None
    return await db.scalar(select(Sale).where(Sale.id == sale_id))


async def _sale_rows(db: AsyncSession, sale: Sale) -> tuple[list[SaleItem], list[Payment]]:
    items = list((await db.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id).order_by(SaleItem.line_no))).all())
    pays = list((await db.scalars(select(Payment).where(Payment.sale_id == sale.id))).all())
    return items, pays


async def _credit_sales(db: AsyncSession, shift: Shift, closing: ShiftClosing) -> list[Sale]:
    skip = {closing.fuel_sale_id, closing.oil_sale_id}
    sales = (
        await db.scalars(
            select(Sale)
            .where(Sale.shift_id == shift.id, Sale.status != str(SaleStatus.DRAFT))
            .order_by(Sale.created_at)
        )
    ).all()
    out: list[Sale] = []
    for sale in sales:
        if sale.id in skip:
            continue
        pays = (await db.scalars(select(Payment).where(Payment.sale_id == sale.id))).all()
        if pays and all(str(p.method) == str(PaymentMethod.CONTRACT) for p in pays):
            out.append(sale)
    return out


async def _closing_ar(db: AsyncSession, shift: Shift) -> list[ArPayment]:
    return list(
        (
            await db.scalars(
                select(ArPayment)
                .where(
                    ArPayment.created_by.in_(_people(shift)),
                    ArPayment.created_at >= shift.opened_at,
                    ArPayment.created_at <= _window_end(shift),
                    ArPayment.note.ilike(f"{CLOSE_NOTE}%"),
                )
                .order_by(ArPayment.created_at)
            )
        ).all()
    )


async def _closing_expenses(db: AsyncSession, shift: Shift) -> list[Expense]:
    stmt = (
        select(Expense)
        .where(
            Expense.created_by.in_(_people(shift)),
            Expense.created_at >= shift.opened_at,
            Expense.created_at <= _window_end(shift),
        )
        .order_by(Expense.created_at)
    )
    if shift.branch_id is not None:
        stmt = stmt.where(Expense.branch_id == shift.branch_id)
    return list((await db.scalars(stmt)).all())


def _ar_method(pay: ArPayment) -> str:
    if str(pay.received_to) == "cash":
        return "cash"
    return "transfer" if "шилжүүлэг" in (pay.note or "") else "card"


def _expense_method(exp: Expense) -> str:
    if str(exp.payment_method) == "cash":
        return "cash"
    return "transfer" if "шилжүүлэг" in (exp.description or "") else "card"


async def _repost_sale(db: AsyncSession, sale: Sale) -> None:
    """Борлуулалтын журналыг мөрүүд/төлбөрийн одоогийн байдлаар дахин бичнэ."""
    old = await db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == str(SourceType.SALE),
            JournalEntry.source_id == sale.id,
            JournalEntry.event_type == str(EventType.SALE_POSTED),
        )
    )
    entry_date = old.entry_date if old is not None else (sale.completed_at or sale.created_at).date()
    posted_by = old.posted_by if old is not None else sale.cashier_id
    created_at = old.created_at if old is not None else None
    if old is not None:
        await db.delete(old)
        await db.flush()
    items, pays = await _sale_rows(db, sale)
    if not items:
        return
    entry = await posting.post(
        db,
        event_type=str(EventType.SALE_POSTED),
        source_type=str(SourceType.SALE),
        source_id=sale.id,
        entry_date=entry_date,
        description=f"Борлуулалт №{sale.number}",
        lines=posting_rules.build_sale_lines(sale, items, pays),
        posted_by=posted_by,
    )
    if entry is not None and created_at is not None:
        entry.created_at = created_at


async def _backdate_entry(db: AsyncSession, *, event_type: str, source_type: str, source_id: uuid.UUID, when) -> None:
    entry = await db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == source_type,
            JournalEntry.source_id == source_id,
            JournalEntry.event_type == event_type,
        )
    )
    if entry is not None:
        entry.created_at = when


async def _recalc(db: AsyncSession, user: User, shift: Shift) -> None:
    from app.services.shift_service import recalculate_cash  # noqa: PLC0415

    await db.flush()
    await recalculate_cash(db, user, shift_id=shift.id)


async def _attendant(db: AsyncSession, shift: Shift) -> User:
    attendant = await db.scalar(select(User).where(User.id == shift.opened_by))
    if attendant is None:
        raise HTTPException(status_code=404, detail="Ээлжийн түгээгч олдсонгүй")
    return attendant


async def _resolve_contract(db: AsyncSession, user: User, shift: Shift, target: Any) -> Contract:
    from app.services import attendant_service  # noqa: PLC0415

    if getattr(target, "new_customer", None) is not None:
        return await attendant_service._contract_for_new_customer(
            db, user, target.new_customer, {}, branch_id=shift.branch_id
        )
    if getattr(target, "customer_id", None) is not None:
        return await attendant_service._contract_for_customer(db, user, target.customer_id)
    if getattr(target, "contract_id", None) is not None:
        contract = await db.scalar(select(Contract).where(Contract.id == target.contract_id))
        if contract is None:
            raise HTTPException(status_code=404, detail="Гэрээ олдсонгүй")
        return contract
    raise HTTPException(status_code=422, detail="Харилцагч сонгоно уу")


# --------------------------------------------------------------------------- #
# Харах
# --------------------------------------------------------------------------- #
async def closing_view(db: AsyncSession, shift_id: uuid.UUID) -> dict[str, Any]:
    shift, closing = await _load(db, shift_id)
    fuel_sale = await _sale(db, closing.fuel_sale_id)
    oil_sale = await _sale(db, closing.oil_sale_id)

    def pay_sum(pays: list[Payment], method: PaymentMethod) -> Decimal:
        return q2(sum((_d(p.amount) for p in pays if str(p.method) == str(method)), ZERO))

    tender_sales: list[dict[str, Any]] = []
    oil_lines: list[dict[str, Any]] = []
    for label, sale in (("fuel", fuel_sale), ("oil", oil_sale)):
        if sale is None:
            continue
        items, pays = await _sale_rows(db, sale)
        tender_sales.append(
            {
                "kind": label,
                "sale_id": sale.id,
                "number": sale.number,
                "total": q2(_d(sale.total)),
                "cash": pay_sum(pays, PaymentMethod.CASH),
                "card": pay_sum(pays, PaymentMethod.CARD),
                "transfer": pay_sum(pays, PaymentMethod.TRANSFER),
            }
        )
        if label == "oil":
            oil_lines = [
                {"name": i.name_snapshot, "qty": q3(_d(i.qty, ZERO_L)), "unit_price": q2(_d(i.unit_price)), "amount": q2(_d(i.amount))}
                for i in items
            ]

    customers: dict[uuid.UUID, str] = {}

    async def customer_name(customer_id: uuid.UUID | None) -> str:
        if customer_id is None:
            return ""
        if customer_id not in customers:
            c = await db.scalar(select(Customer).where(Customer.id == customer_id))
            customers[customer_id] = (c.name if c else "") or ""
        return customers[customer_id]

    credit_lines: list[dict[str, Any]] = []
    credit_fuel = ZERO
    credit_goods = ZERO
    for sale in await _credit_sales(db, shift, closing):
        items, _pays = await _sale_rows(db, sale)
        contract = await db.scalar(select(Contract).where(Contract.id == sale.contract_id)) if sale.contract_id else None
        fuel_amt = q2(sum((_d(i.amount) for i in items if str(i.item_type) == str(ItemType.FUEL)), ZERO))
        credit_fuel = q2(credit_fuel + fuel_amt)
        credit_goods = q2(credit_goods + q2(_d(sale.total) - fuel_amt))
        credit_lines.append(
            {
                "sale_id": sale.id,
                "number": sale.number,
                "customer": await customer_name(sale.customer_id),
                "contract_no": contract.contract_no if contract else "",
                "total": q2(_d(sale.total)),
                "fuel_only": all(str(i.item_type) == str(ItemType.FUEL) for i in items),
                "edited": (sale.note or "").endswith(EDIT_NOTE),
                "items": [
                    {"name": i.name_snapshot, "qty": q3(_d(i.qty, ZERO_L)), "unit_price": q2(_d(i.unit_price)), "amount": q2(_d(i.amount))}
                    for i in items
                ],
            }
        )

    ar_rows: list[dict[str, Any]] = []
    ar_by = {"cash": ZERO, "card": ZERO, "transfer": ZERO}
    for pay in await _closing_ar(db, shift):
        method = _ar_method(pay)
        ar_by[method] = q2(ar_by[method] + _d(pay.amount))
        ar_rows.append(
            {
                "id": pay.id,
                "customer": await customer_name(pay.customer_id),
                "amount": q2(_d(pay.amount)),
                "method": method,
                "edited": EDIT_NOTE in (pay.note or ""),
            }
        )

    exp_rows: list[dict[str, Any]] = []
    exp_by = {"cash": ZERO, "card": ZERO, "transfer": ZERO}
    for exp in await _closing_expenses(db, shift):
        method = _expense_method(exp)
        exp_by[method] = q2(exp_by[method] + _d(exp.total))
        acc = await db.scalar(select(Account).where(Account.code == exp.account_code))
        exp_rows.append(
            {
                "id": exp.id,
                "account_code": exp.account_code,
                "account_name": acc.name_mn if acc else exp.account_code,
                "description": exp.description or "",
                "amount": q2(_d(exp.total)),
                "method": method,
            }
        )

    settlement = q2(_d(closing.settlement_vat) + _d(closing.settlement_novat))
    transfer = q2(_d(closing.transfer_total))
    declared = q2(_d(shift.declared_cash))
    opening = q2(_d(shift.opening_cash))
    fuel_total = q2(_d(closing.fuel_total))
    oil_total = q2(_d(closing.oil_total))
    ar_total = q2(sum(ar_by.values(), ZERO))
    credit_total = q2(credit_fuel + credit_goods)

    # Түгээгчийн тулгалтын томьёо (серверийн бүртгэлээр).
    must = q2(opening + fuel_total + oil_total + credit_goods + ar_total - credit_total - exp_by["cash"])
    handed = q2(declared + settlement + transfer)
    expected = q2(_d(shift.expected_cash))
    over_short = q2(_d(shift.cash_over_short))

    client = (closing.close_input or {}).get("client") if closing.close_input else None
    return {
        "shift_id": shift.id,
        "editable": closing.approved_at is None and shift.status != str(ShiftStatus.OPEN),
        "opening_cash": opening,
        "declared_cash": declared,
        "settlement_total": settlement,
        "transfer_total": transfer,
        "fuel_total": fuel_total,
        "oil_total": oil_total,
        "oil_lines": oil_lines,
        "credit_total": credit_total,
        "credit_fuel": credit_fuel,
        "credit_goods": credit_goods,
        "credit_lines": credit_lines,
        "ar_total": ar_total,
        "ar_by_method": ar_by,
        "ar_payments": ar_rows,
        "expense_by_method": exp_by,
        "expenses": exp_rows,
        "tender_sales": tender_sales,
        "must": must,
        "handed": handed,
        "diff": q2(handed - must),
        "expected_cash": expected,
        "cash_over_short": over_short,
        #: Серверийн тулгалтын зөрүү ба кассын зөрүү ижил байх ёстой — өөр бол
        #: ээлжийн бус кассын гүйлгээ эсвэл хуучин дүрмийн тооцоо орсон.
        "consistent": q2(handed - must) == over_short,
        "client": client,
    }


# --------------------------------------------------------------------------- #
# Засвар — тушаалт (бэлэн / терминал / шилжүүлэг)
# --------------------------------------------------------------------------- #
async def _resplit(db: AsyncSession, shift: Shift, closing: ShiftClosing, settlement: Decimal, transfer: Decimal) -> None:
    """Терминал/шилжүүлгийн дүнг түлш → тосны борлуулалтад дахин хуваарилна."""
    from app.services.attendant_service import _default_transfer_account, _noncash_payments  # noqa: PLC0415

    ar_card = ZERO
    ar_transfer = ZERO
    for pay in await _closing_ar(db, shift):
        method = _ar_method(pay)
        if method == "card":
            ar_card = q2(ar_card + _d(pay.amount))
        elif method == "transfer":
            ar_transfer = q2(ar_transfer + _d(pay.amount))
    if ar_card > settlement:
        raise HTTPException(status_code=422, detail="Өглөг төлөлтийн картын дүн терминалын дүнгээс их байна")
    if ar_transfer > transfer:
        raise HTTPException(status_code=422, detail="Өглөг төлөлтийн шилжүүлэг нийт шилжүүлгээс их байна")
    card_left = q2(settlement - ar_card)
    transfer_left = q2(transfer - ar_transfer)

    bank_account_id = None
    for sale_id in (closing.fuel_sale_id, closing.oil_sale_id):
        sale = await _sale(db, sale_id)
        if sale is None:
            continue
        _items, pays = await _sale_rows(db, sale)
        for p in pays:
            if str(p.method) == str(PaymentMethod.TRANSFER) and p.bank_account_id is not None:
                bank_account_id = p.bank_account_id
    if bank_account_id is None:
        bank_account_id = await _default_transfer_account(db, shift.branch_id)

    for sale_id in (closing.fuel_sale_id, closing.oil_sale_id):
        sale = await _sale(db, sale_id)
        if sale is None:
            continue
        _items, pays = await _sale_rows(db, sale)
        contract_paid = q2(sum((_d(p.amount) for p in pays if str(p.method) == str(PaymentMethod.CONTRACT)), ZERO))
        for p in pays:
            if str(p.method) != str(PaymentMethod.CONTRACT):
                await db.delete(p)
        await db.flush()
        payable = q2(_d(sale.total) - contract_paid)
        new_pays, used_card, used_transfer = _noncash_payments(payable, card_left, transfer_left, bank_account_id)
        for tender in new_pays:
            db.add(
                Payment(
                    sale_id=sale.id,
                    method=str(tender.method),
                    amount=tender.amount,
                    received=getattr(tender, "received", None),
                    ref_no=getattr(tender, "ref_no", None),
                    bank_account_id=getattr(tender, "bank_account_id", None),
                )
            )
        card_left = q2(card_left - used_card)
        transfer_left = q2(transfer_left - used_transfer)
        await db.flush()
        await _repost_sale(db, sale)

    if card_left > ZERO or transfer_left > ZERO:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Терминал + шилжүүлгийн дүн өдрийн бэлэн бус борлуулалтаас {q2(card_left + transfer_left):,.0f}₮-өөр их байна. "
                "Дүнгээ шалгана уу (өглөг төлөлтийн карт/шилжүүлэг хасагдсан)."
            ),
        )
    closing.settlement_vat = settlement
    closing.settlement_novat = ZERO
    closing.transfer_total = transfer


async def set_tenders(
    db: AsyncSession,
    user: User,
    *,
    shift_id: uuid.UUID,
    declared_cash: Decimal,
    settlement_total: Decimal,
    transfer_total: Decimal,
    note: str | None = None,
) -> dict[str, Any]:
    shift, closing = await _editable(db, shift_id)
    before = {
        "declared_cash": str(_d(shift.declared_cash)),
        "settlement_total": str(q2(_d(closing.settlement_vat) + _d(closing.settlement_novat))),
        "transfer_total": str(_d(closing.transfer_total)),
    }
    declared = q2(_d(declared_cash))
    settlement = q2(_d(settlement_total))
    transfer = q2(_d(transfer_total))
    if declared < ZERO or settlement < ZERO or transfer < ZERO:
        raise HTTPException(status_code=422, detail="Дүн сөрөг байж болохгүй")
    await _resplit(db, shift, closing, settlement, transfer)
    shift.declared_cash = declared
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_tenders_edited",
        entity_type="shift",
        entity_id=shift.id,
        before=before,
        after={"declared_cash": str(declared), "settlement_total": str(settlement), "transfer_total": str(transfer), "note": note},
    )
    return await closing_view(db, shift_id)


# --------------------------------------------------------------------------- #
# Засвар — зээл
# --------------------------------------------------------------------------- #
async def add_credit(db: AsyncSession, user: User, *, shift_id: uuid.UUID, target: Any, fuel_id: uuid.UUID, qty: Decimal | None, amount: Decimal | None) -> dict[str, Any]:
    """Нэгдсэн (бэлэн) түлшний борлуулалтаас литрийг харилцагчийн зээл рүү шилжүүлнэ."""
    shift, closing = await _editable(db, shift_id)
    fuel_sale = await _sale(db, closing.fuel_sale_id)
    if fuel_sale is None:
        raise HTTPException(status_code=422, detail="Түлшний нэгдсэн борлуулалт олдсонгүй")
    contract = await _resolve_contract(db, user, shift, target)
    discount = q2(_d(contract.price_discount_per_l))

    items, pays = await _sale_rows(db, fuel_sale)
    fuel_items = [i for i in reversed(items) if i.fuel_id == fuel_id and _d(i.qty, ZERO_L) > ZERO_L]
    if not fuel_items:
        raise HTTPException(status_code=422, detail="Энэ түлш нэгдсэн борлуулалтад алга")

    pieces: list[tuple[SaleItem, Decimal, Decimal, Decimal, Decimal]] = []  # item, take, gross, credit, cogs
    if amount is not None and _d(amount) > ZERO:
        left = q2(_d(amount))
        for item in fuel_items:
            if left <= ZERO:
                break
            item_qty = q3(_d(item.qty, ZERO_L))
            unit = q2(_d(item.unit_price) - discount)
            if unit <= ZERO:
                raise HTTPException(status_code=422, detail="Гэрээний хөнгөлөлт түлшний үнээс их байна")
            capacity = q2(item_qty * unit)
            if left < capacity:
                take = min(q3(left / unit), item_qty)
                credit = left
                gross = q2(left + take * discount)
            else:
                take, credit, gross = item_qty, capacity, q2(_d(item.amount))
            full = take >= item_qty
            cogs = q2(_d(item.cogs_amount)) if full else q2(take * _d(item.unit_cost))
            pieces.append((item, take, gross if not full else q2(_d(item.amount)), credit, cogs))
            left = q2(left - credit)
        if left > ZERO:
            raise HTTPException(status_code=422, detail="Зээлийн дүн нэгдсэн борлуулалтын энэ түлшний дүнгээс их байна")
    elif qty is not None and _d(qty, ZERO_L) > ZERO_L:
        need = q3(_d(qty, ZERO_L))
        for item in fuel_items:
            if need <= ZERO_L:
                break
            item_qty = q3(_d(item.qty, ZERO_L))
            take = min(item_qty, need)
            unit = q2(_d(item.unit_price) - discount)
            if unit <= ZERO:
                raise HTTPException(status_code=422, detail="Гэрээний хөнгөлөлт түлшний үнээс их байна")
            full = take >= item_qty
            gross = q2(_d(item.amount)) if full else q2(take * _d(item.unit_price))
            cogs = q2(_d(item.cogs_amount)) if full else q2(take * _d(item.unit_cost))
            pieces.append((item, take, gross, q2(take * unit), cogs))
            need = q3(need - take)
        if need > ZERO_L:
            raise HTTPException(status_code=422, detail="Зээлийн литр нэгдсэн борлуулалтын энэ түлшний литрээс их байна")
    else:
        raise HTTPException(status_code=422, detail="Литр эсвэл дүнг оруулна уу")

    gross_total = q2(sum((p[2] for p in pieces), ZERO))
    cash_pay = next((p for p in pays if str(p.method) == str(PaymentMethod.CASH)), None)
    if cash_pay is None or _d(cash_pay.amount) < gross_total:
        raise HTTPException(
            status_code=422,
            detail="Нэгдсэн борлуулалтын бэлэн төлбөр хүрэлцэхгүй — эхлээд терминал/шилжүүлгийн дүнг засна уу",
        )

    # Нэгдсэн борлуулалтаас хасна (сав хөдлөхгүй — литр л шилжинэ).
    cogs_moved = ZERO
    for item, take, gross, _credit, cogs in pieces:
        item.qty = q3(_d(item.qty, ZERO_L) - take)
        item.amount = q2(_d(item.amount) - gross)
        item.cogs_amount = q2(_d(item.cogs_amount) - cogs)
        cogs_moved = q2(cogs_moved + cogs)
        if item.qty <= ZERO_L:
            await db.delete(item)
    await db.flush()
    remaining, _ = await _sale_rows(db, fuel_sale)
    fuel_sale.subtotal, fuel_sale.vat_amount, fuel_sale.total = compute_totals([_d(i.amount) for i in remaining])
    fuel_sale.cogs_total = q2(_d(fuel_sale.cogs_total) - cogs_moved)
    cash_pay.amount = q2(_d(cash_pay.amount) - gross_total)
    cash_pay.received = cash_pay.amount
    if cash_pay.amount <= ZERO:
        await db.delete(cash_pay)

    # Харилцагчийн зээлийн борлуулалт.
    credit_items = [
        SaleItem(
            line_no=n,
            item_type=str(ItemType.FUEL),
            fuel_id=item.fuel_id,
            tank_id=item.tank_id,
            pump_id=item.pump_id,
            nozzle_id=item.nozzle_id,
            name_snapshot=item.name_snapshot,
            qty=take,
            unit_price=q2(_d(item.unit_price) - discount),
            amount=credit,
            unit_cost=item.unit_cost,
            cogs_amount=cogs,
            refunded_qty=ZERO_L,
        )
        for n, (item, take, _gross, credit, cogs) in enumerate(pieces, start=1)
    ]
    subtotal, vat, total = compute_totals([ci.amount for ci in credit_items])
    sale = Sale(
        branch_id=fuel_sale.branch_id,
        shift_id=shift.id,
        cashier_id=shift.opened_by,
        sale_type=str(SaleType.FUEL),
        status=str(SaleStatus.COMPLETED),
        subtotal=subtotal,
        vat_amount=vat,
        total=total,
        cogs_total=q2(sum((ci.cogs_amount for ci in credit_items), ZERO)),
        customer_id=contract.customer_id,
        contract_id=contract.id,
        note=f"{CLOSE_NOTE} — {EDIT_NOTE}",
        completed_at=fuel_sale.completed_at,
    )
    db.add(sale)
    await db.flush()
    for ci in credit_items:
        ci.sale_id = sale.id
        db.add(ci)
    db.add(Payment(sale_id=sale.id, method=str(PaymentMethod.CONTRACT), amount=total, contract_id=contract.id))
    contract.balance = q2(_d(contract.balance) + total)
    customer = await db.scalar(select(Customer).where(Customer.id == contract.customer_id))
    if not (customer is not None and customer.credit_unlimited) and q2(_d(contract.credit_limit)) < q2(_d(contract.balance)):
        contract.credit_limit = q2(_d(contract.balance))
    await db.flush()
    await db.refresh(sale, ["number"])

    old = await db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == str(SourceType.SALE),
            JournalEntry.source_id == fuel_sale.id,
            JournalEntry.event_type == str(EventType.SALE_POSTED),
        )
    )
    await _repost_sale(db, fuel_sale)
    items_new, pays_new = await _sale_rows(db, sale)
    entry = await posting.post(
        db,
        event_type=str(EventType.SALE_POSTED),
        source_type=str(SourceType.SALE),
        source_id=sale.id,
        entry_date=old.entry_date if old is not None else _inside(shift).date(),
        description=f"Борлуулалт №{sale.number} (хаалтын засвар)",
        lines=posting_rules.build_sale_lines(sale, items_new, pays_new),
        posted_by=shift.opened_by,
    )
    if entry is not None:
        entry.created_at = _inside(shift)
    closing.credit_total = q2(_d(closing.credit_total) + total)
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_credit_added",
        entity_type="shift",
        entity_id=shift.id,
        after={"sale_id": str(sale.id), "contract_id": str(contract.id), "amount": str(total), "liters": str(sum((p[1] for p in pieces), ZERO_L))},
    )
    return await closing_view(db, shift_id)


async def remove_credit(db: AsyncSession, user: User, *, shift_id: uuid.UUID, sale_id: uuid.UUID) -> dict[str, Any]:
    """Зээлийн борлуулалтыг нэгдсэн (бэлэн) борлуулалт руу буцаана."""
    from app.models.approval import Refund  # noqa: PLC0415
    from app.models.system import EbarimtQueue  # noqa: PLC0415

    shift, closing = await _editable(db, shift_id)
    credit = next((s for s in await _credit_sales(db, shift, closing) if s.id == sale_id), None)
    if credit is None:
        raise HTTPException(status_code=404, detail="Энэ ээлжийн зээлийн борлуулалт олдсонгүй")
    fuel_sale = await _sale(db, closing.fuel_sale_id)
    if fuel_sale is None:
        raise HTTPException(status_code=422, detail="Түлшний нэгдсэн борлуулалт олдсонгүй")
    if await db.scalar(select(Refund.id).where(Refund.sale_id == credit.id).limit(1)):
        raise HTTPException(status_code=422, detail="Буцаалттай борлуулалтыг устгах боломжгүй")
    items, pays = await _sale_rows(db, credit)
    if any(str(i.item_type) != str(ItemType.FUEL) for i in items):
        raise HTTPException(status_code=422, detail="Бараатай зээлийн мөрийг устгах боломжгүй — зөвхөн түлшний зээл")
    contract = await db.scalar(select(Contract).where(Contract.id == credit.contract_id)) if credit.contract_id else None
    discount = q2(_d(contract.price_discount_per_l)) if contract is not None else ZERO

    fuel_items, fuel_pays = await _sale_rows(db, fuel_sale)
    next_line = max((i.line_no for i in fuel_items), default=0)
    gross_total = ZERO
    for ci in items:
        base = q2(_d(ci.unit_price) + discount)
        # Нэгдсэн борлуулалтаас хасахдаа авсан дүнг ЯГ буцаана (литр × үнээр дахин
        # бодвол дүнгээр оруулсан зээлийн дугуйлалтаас 1-2₮ зөрдөг).
        gross = q2(_d(ci.amount) + _d(ci.qty, ZERO_L) * discount)
        gross_total = q2(gross_total + gross)
        target = next(
            (i for i in fuel_items if i.nozzle_id == ci.nozzle_id and i.tank_id == ci.tank_id and q2(_d(i.unit_price)) == base),
            None,
        )
        if target is not None:
            target.qty = q3(_d(target.qty, ZERO_L) + _d(ci.qty, ZERO_L))
            target.amount = q2(_d(target.amount) + gross)
            target.cogs_amount = q2(_d(target.cogs_amount) + _d(ci.cogs_amount))
        else:
            next_line += 1
            db.add(
                SaleItem(
                    sale_id=fuel_sale.id,
                    line_no=next_line,
                    item_type=str(ItemType.FUEL),
                    fuel_id=ci.fuel_id,
                    tank_id=ci.tank_id,
                    pump_id=ci.pump_id,
                    nozzle_id=ci.nozzle_id,
                    name_snapshot=ci.name_snapshot,
                    qty=ci.qty,
                    unit_price=base,
                    amount=gross,
                    unit_cost=ci.unit_cost,
                    cogs_amount=ci.cogs_amount,
                    refunded_qty=ZERO_L,
                )
            )
    await db.flush()
    fuel_items, fuel_pays = await _sale_rows(db, fuel_sale)
    fuel_sale.subtotal, fuel_sale.vat_amount, fuel_sale.total = compute_totals([_d(i.amount) for i in fuel_items])
    fuel_sale.cogs_total = q2(_d(fuel_sale.cogs_total) + _d(credit.cogs_total))
    cash_pay = next((p for p in fuel_pays if str(p.method) == str(PaymentMethod.CASH)), None)
    if cash_pay is None:
        db.add(Payment(sale_id=fuel_sale.id, method=str(PaymentMethod.CASH), amount=gross_total, received=gross_total))
    else:
        cash_pay.amount = q2(_d(cash_pay.amount) + gross_total)
        cash_pay.received = cash_pay.amount

    if contract is not None:
        contract.balance = q2(_d(contract.balance) - _d(credit.total))
    await posting.reverse(db, event_type=str(EventType.SALE_POSTED), source_type=str(SourceType.SALE), source_id=credit.id)
    for q in (await db.scalars(select(EbarimtQueue).where(EbarimtQueue.sale_id == credit.id))).all():
        await db.delete(q)
    total = q2(_d(credit.total))
    await db.delete(credit)
    await db.flush()
    await _repost_sale(db, fuel_sale)
    closing.credit_total = q2(_d(closing.credit_total) - total)
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_credit_removed",
        entity_type="shift",
        entity_id=shift.id,
        before={"sale_id": str(sale_id), "amount": str(total), "contract_id": str(contract.id) if contract else None},
    )
    return await closing_view(db, shift_id)


# --------------------------------------------------------------------------- #
# Засвар — өглөг төлөлт
# --------------------------------------------------------------------------- #
async def add_ar_payment(db: AsyncSession, user: User, *, shift_id: uuid.UUID, target: Any, amount: Decimal, method: str) -> dict[str, Any]:
    from app.services import contract_service  # noqa: PLC0415

    shift, closing = await _editable(db, shift_id)
    method = str(method or "cash")
    if method not in METHOD_MN:
        raise HTTPException(status_code=422, detail="Төлбөрийн хэлбэр буруу")
    value = q2(_d(amount))
    if value <= ZERO:
        raise HTTPException(status_code=422, detail="Дүн 0-ээс их байх ёстой")
    contract = await _resolve_contract(db, user, shift, target)
    attendant = await _attendant(db, shift)
    when = _inside(shift)
    payment, _contract, _inv, _entry = await contract_service.record_payment(
        db,
        attendant,
        contract_id=contract.id,
        amount=value,
        received_to="cash" if method == "cash" else "bank",
        payment_date=when.date(),
        note=f"{CLOSE_NOTE} — {METHOD_MN[method]} · {EDIT_NOTE}",
    )
    payment.created_at = when
    await _backdate_entry(db, event_type=str(EventType.AR_RECEIPT), source_type=str(SourceType.AR_PAYMENT), source_id=payment.id, when=when)
    await db.flush()
    if method != "cash":
        await _resplit(db, shift, closing, q2(_d(closing.settlement_vat) + _d(closing.settlement_novat)), q2(_d(closing.transfer_total)))
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_ar_added",
        entity_type="shift",
        entity_id=shift.id,
        after={"ar_payment_id": str(payment.id), "amount": str(value), "method": method, "contract_id": str(contract.id)},
    )
    return await closing_view(db, shift_id)


async def remove_ar_payment(db: AsyncSession, user: User, *, shift_id: uuid.UUID, payment_id: uuid.UUID) -> dict[str, Any]:
    from app.models.bank import BankTransaction  # noqa: PLC0415

    shift, closing = await _editable(db, shift_id)
    payment = next((p for p in await _closing_ar(db, shift) if p.id == payment_id), None)
    if payment is None:
        raise HTTPException(status_code=404, detail="Энэ хаалтын өглөг төлөлт олдсонгүй")
    if payment.ar_invoice_id is not None:
        raise HTTPException(status_code=422, detail="Нэхэмжлэхэд холбогдсон төлбөрийг устгах боломжгүй")
    if await db.scalar(select(BankTransaction.id).where(BankTransaction.ar_payment_id == payment.id).limit(1)):
        raise HTTPException(status_code=422, detail="Банкны хуулгатай тулгагдсан төлбөрийг устгах боломжгүй")
    method = _ar_method(payment)
    contract = await db.scalar(select(Contract).where(Contract.id == payment.contract_id))
    if contract is not None:
        contract.balance = q2(_d(contract.balance) + _d(payment.amount))
    await posting.reverse(db, event_type=str(EventType.AR_RECEIPT), source_type=str(SourceType.AR_PAYMENT), source_id=payment.id)
    amount = q2(_d(payment.amount))
    await db.delete(payment)
    await db.flush()
    if method != "cash":
        await _resplit(db, shift, closing, q2(_d(closing.settlement_vat) + _d(closing.settlement_novat)), q2(_d(closing.transfer_total)))
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_ar_removed",
        entity_type="shift",
        entity_id=shift.id,
        before={"ar_payment_id": str(payment_id), "amount": str(amount), "method": method},
    )
    return await closing_view(db, shift_id)


# --------------------------------------------------------------------------- #
# Засвар — зарлага
# --------------------------------------------------------------------------- #
async def add_expense(db: AsyncSession, user: User, *, shift_id: uuid.UUID, account_code: str, amount: Decimal, method: str, description: str | None = None) -> dict[str, Any]:
    from app.services import expense_service  # noqa: PLC0415

    shift, _closing = await _editable(db, shift_id)
    method = str(method or "cash")
    if method not in METHOD_MN:
        raise HTTPException(status_code=422, detail="Төлбөрийн хэлбэр буруу")
    attendant = await _attendant(db, shift)
    when = _inside(shift)
    text = (description or "").strip() or CLOSE_NOTE
    if method != "cash":
        text = f"{text} · {'банкны терминал' if method == 'card' else 'шилжүүлэг'}"
    expense = await expense_service.create_expense(
        db,
        attendant,
        account_code=account_code,
        amount=amount,
        payment_method="cash" if method == "cash" else "bank",
        expense_date=when.date(),
        description=f"{text} · {EDIT_NOTE}"[:255],
        branch_id=shift.branch_id,
    )
    expense.shift_id = shift.id if method == "cash" else None
    expense.created_at = when
    await _backdate_entry(db, event_type=str(EventType.EXPENSE_POSTED), source_type=str(SourceType.EXPENSE), source_id=expense.id, when=when)
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_expense_added",
        entity_type="shift",
        entity_id=shift.id,
        after={"expense_id": str(expense.id), "amount": str(expense.total), "method": method, "account_code": account_code},
    )
    return await closing_view(db, shift_id)


async def remove_expense(db: AsyncSession, user: User, *, shift_id: uuid.UUID, expense_id: uuid.UUID) -> dict[str, Any]:
    from app.models.bank import BankStatement, BankTransaction  # noqa: PLC0415

    shift, _closing = await _editable(db, shift_id)
    expense = next((e for e in await _closing_expenses(db, shift) if e.id == expense_id), None)
    if expense is None:
        raise HTTPException(status_code=404, detail="Энэ хаалтын зарлага олдсонгүй")
    if expense.ap_invoice_id is not None:
        raise HTTPException(status_code=422, detail="Өглөгтэй зарлагыг устгах боломжгүй")
    if await db.scalar(select(BankTransaction.id).where(BankTransaction.expense_id == expense.id).limit(1)) or await db.scalar(
        select(BankStatement.id).where(BankStatement.fee_expense_id == expense.id).limit(1)
    ):
        raise HTTPException(status_code=422, detail="Банкны хуулгатай тулгагдсан зарлагыг устгах боломжгүй")
    await posting.reverse(db, event_type=str(EventType.EXPENSE_POSTED), source_type=str(SourceType.EXPENSE), source_id=expense.id)
    amount = q2(_d(expense.total))
    method = _expense_method(expense)
    await db.delete(expense)
    await db.flush()
    await _recalc(db, user, shift)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_expense_removed",
        entity_type="shift",
        entity_id=shift.id,
        before={"expense_id": str(expense_id), "amount": str(amount), "method": method},
    )
    return await closing_view(db, shift_id)


async def fuel_options(db: AsyncSession, shift_id: uuid.UUID) -> list[dict[str, Any]]:
    """Зээл нэмэхэд сонгох түлш — нэгдсэн борлуулалтад байгаа литртэй нь."""
    _shift, closing = await _load(db, shift_id)
    fuel_sale = await _sale(db, closing.fuel_sale_id)
    if fuel_sale is None:
        return []
    items, _ = await _sale_rows(db, fuel_sale)
    agg: dict[uuid.UUID, dict[str, Any]] = {}
    for i in items:
        if i.fuel_id is None:
            continue
        row = agg.setdefault(i.fuel_id, {"fuel_id": i.fuel_id, "name": "", "liters": ZERO_L, "amount": ZERO})
        row["liters"] = q3(row["liters"] + _d(i.qty, ZERO_L))
        row["amount"] = q2(row["amount"] + _d(i.amount))
    for fid, row in agg.items():
        fuel = await db.scalar(select(Fuel).where(Fuel.id == fid))
        row["name"] = fuel.name_mn if fuel else ""
    return list(agg.values())
