"""Бичилтийн дүрэм (CONTRACTS.md §5).

Энэ модулийн бүх функц **цэвэр** — DB, сүлжээ, цаг ашиглахгүй, зөвхөн
``LineSpec`` жагсаалт буцаана. Ингэснээр нэгжийн тестээр бүрэн шалгах боломжтой.

Тэмдгийн гэрээ:
* ``build_cash_variance_lines(diff)`` — ``diff = зарлагадсан − тооцоолсон``.
  ``diff > 0`` илүүдэл (SHIFT_CASH_OVER), ``diff < 0`` дутагдал (SHIFT_CASH_SHORT).
* ``build_fuel_variance_lines(amount, ...)`` — ``amount > 0`` илүүдэл
  (FUEL_VARIANCE_GAIN), ``amount < 0`` хорогдол (FUEL_VARIANCE_LOSS).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Iterable

from app.config import settings
from app.enums import EventType, ItemType, PaymentMethod
from app.money import q2, split_remainder, vat_from_gross
from app.services.coa import ACC
from app.services.posting import Dims, LineSpec

ZERO = Decimal("0")

VAT_RATE: Decimal = settings.vat_rate

PAYMENT_METHOD_MN: dict[str, str] = {
    PaymentMethod.CASH: "Бэлэн",
    PaymentMethod.CARD: "Карт",
    PaymentMethod.QR: "QR",
    PaymentMethod.TRANSFER: "Шилжүүлэг",
    # Гэрээт борлуулалтыг хэрэглэгчид «зээл» гэж нэрлэдэг — бүх дэлгэц,
    # тайлан, журналын тайлбарт ижил нэршил.
    PaymentMethod.CONTRACT: "Зээл",
}


# --------------------------------------------------------------------------- #
# Туслах функцууд
# --------------------------------------------------------------------------- #
def _d(value: Any) -> Decimal:
    """Ямар ч тоог Decimal болгоно (None → 0). float хэзээ ч ирэхгүй."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _m(value: Any) -> Decimal:
    return q2(_d(value))


def _cash_account(where: Any) -> str:
    """``bank``/``cash`` утгаас мөнгөн дансны кодыг тодорхойлно."""
    return ACC.CASH if str(where or "bank") == "cash" else ACC.BANK


def cash_variance_event(diff: Decimal) -> str:
    """Кассын зөрүүний тэмдгээс event_type-ыг тодорхойлно."""
    return str(EventType.SHIFT_CASH_OVER if _d(diff) > 0 else EventType.SHIFT_CASH_SHORT)


def fuel_variance_event(amount: Decimal) -> str:
    """Түлшний зөрүүний тэмдгээс event_type-ыг тодорхойлно."""
    return str(EventType.FUEL_VARIANCE_GAIN if _d(amount) > 0 else EventType.FUEL_VARIANCE_LOSS)


def settlement_event(method: str) -> str:
    """``card``/``qr`` → CARD_SETTLEMENT / QR_SETTLEMENT."""
    key = str(method).lower()
    if key == str(PaymentMethod.CARD):
        return str(EventType.CARD_SETTLEMENT)
    if key == str(PaymentMethod.QR):
        return str(EventType.QR_SETTLEMENT)
    raise ValueError(f"Тодорхойгүй тооцооны төрөл: {method}")


# --------------------------------------------------------------------------- #
# SALE_POSTED
# --------------------------------------------------------------------------- #
def build_sale_lines(sale: Any, items: Iterable[Any], payments: Iterable[Any]) -> list[LineSpec]:
    """Борлуулалтын бичилт.

    * Дебит — төлбөр бүр өөрийн tender данс руу.
    * Кредит — 4101 түлшний цэвэр орлого (түлш бүрээр, dim_fuel/tank),
      4102 барааны цэвэр орлого, 2201 НӨАТ.
    * Өртөг — 5101/1301 (түлш бүрээр), 5102/1302 (бараа).

    НӨАТ-ыг бүлэг тус бүрээр тооцож ``split_remainder``-ээр дугуйллын үлдэгдлийг
    хуваарилдаг тул хэсгүүдийн нийлбэр яг ``sale.vat_amount`` болно.
    """
    lines: list[LineSpec] = []
    items = list(items)
    payments = list(payments)

    # --- 1. Төлбөрийн дебит мөрүүд ---
    customer_id = getattr(sale, "customer_id", None)
    branch_id = getattr(sale, "branch_id", None)
    for pay in payments:
        method = str(getattr(pay, "method", PaymentMethod.CASH))
        amount = _m(getattr(pay, "amount", ZERO))
        if amount == 0:
            continue
        dims = (
            Dims(customer_id=customer_id, branch_id=branch_id)
            if method == str(PaymentMethod.CONTRACT)
            else Dims(branch_id=branch_id)
        )
        lines.append(
            LineSpec(
                account_code=ACC.tender_account(method),
                debit=amount,
                memo=f"Төлбөр — {PAYMENT_METHOD_MN.get(method, method)}",
                dims=dims,
            )
        )

    # --- 2. Мөрүүдийг бүлэглэх ---
    # Түлш: (fuel_id, tank_id) хослолоор; бараа: нэг бүлэг.
    fuel_groups: dict[tuple[Any, Any], dict[str, Decimal]] = {}
    goods_gross = ZERO
    goods_cogs = ZERO

    for item in items:
        item_type = str(getattr(item, "item_type", ItemType.FUEL))
        amount = _m(getattr(item, "amount", ZERO))
        cogs = _m(getattr(item, "cogs_amount", ZERO))
        if item_type == str(ItemType.FUEL):
            key = (getattr(item, "fuel_id", None), getattr(item, "tank_id", None))
            bucket = fuel_groups.setdefault(key, {"gross": ZERO, "cogs": ZERO})
            bucket["gross"] = q2(bucket["gross"] + amount)
            bucket["cogs"] = q2(bucket["cogs"] + cogs)
        else:
            goods_gross = q2(goods_gross + amount)
            goods_cogs = q2(goods_cogs + cogs)

    group_keys = list(fuel_groups.keys())

    # --- 3. НӨАТ-ыг бүлгүүдэд яг хуваарилах ---
    vat_total = _m(getattr(sale, "vat_amount", ZERO))
    raw_parts = [vat_from_gross(fuel_groups[k]["gross"], VAT_RATE) for k in group_keys]
    raw_parts.append(vat_from_gross(goods_gross, VAT_RATE))
    vat_parts = split_remainder(vat_total, raw_parts)

    # --- 4. Орлогын кредит мөрүүд ---
    for idx, key in enumerate(group_keys):
        fuel_id, tank_id = key
        net = q2(fuel_groups[key]["gross"] - vat_parts[idx])
        if net != 0:
            lines.append(
                LineSpec(
                    account_code=ACC.REV_FUEL,
                    credit=net,
                    memo="Түлшний борлуулалт",
                    dims=Dims(fuel_id=fuel_id, tank_id=tank_id, branch_id=branch_id),
                )
            )

    goods_net = q2(goods_gross - vat_parts[-1])
    if goods_net != 0:
        lines.append(
            LineSpec(
                account_code=ACC.REV_GOODS,
                credit=goods_net,
                memo="Барааны борлуулалт",
                dims=Dims(branch_id=branch_id),
            )
        )

    vat_booked = q2(sum(vat_parts, ZERO))
    if vat_booked != 0:
        lines.append(
            LineSpec(
                account_code=ACC.VAT_OUTPUT,
                credit=vat_booked,
                memo="Борлуулалтын НӨАТ",
                dims=Dims(branch_id=branch_id),
            )
        )

    # --- 5. Өртгийн мөрүүд ---
    for key in group_keys:
        fuel_id, tank_id = key
        cogs = fuel_groups[key]["cogs"]
        if cogs == 0:
            continue
        dims = Dims(fuel_id=fuel_id, tank_id=tank_id, branch_id=branch_id)
        lines.append(LineSpec(account_code=ACC.COGS_FUEL, debit=cogs, memo="Түлшний өртөг", dims=dims))
        lines.append(LineSpec(account_code=ACC.INV_FUEL, credit=cogs, memo="Түлшний нөөц хасалт", dims=dims))

    if goods_cogs != 0:
        goods_dims = Dims(branch_id=branch_id)
        lines.append(
            LineSpec(account_code=ACC.COGS_GOODS, debit=goods_cogs, memo="Барааны өртөг", dims=goods_dims)
        )
        lines.append(
            LineSpec(account_code=ACC.INV_GOODS, credit=goods_cogs, memo="Барааны нөөц хасалт", dims=goods_dims)
        )

    return lines


# --------------------------------------------------------------------------- #
# FUEL_RECEIPT_POSTED / PURCHASE_POSTED
# --------------------------------------------------------------------------- #
def build_fuel_receipt_lines(receipt: Any) -> list[LineSpec]:
    """Шатахуун таталт: 1301 = литр·нэгж өртөг + тээвэр, 1402 = НӨАТ, кредит 2101.

    Өглөгийн дүнг ``нөөц + НӨАТ``-аар гаргадаг тул бичилт үргэлж тэнцэнэ.
    """
    liters = _d(getattr(receipt, "liters", ZERO))
    unit_cost = _d(getattr(receipt, "unit_cost", ZERO))
    freight = _m(getattr(receipt, "freight_cost", ZERO))
    inventory = q2(q2(liters * unit_cost) + freight)
    vat = _m(getattr(receipt, "vat_amount", ZERO))
    gross = q2(inventory + vat)
    if gross == 0:
        return []

    supplier_id = getattr(receipt, "supplier_id", None)
    branch_id = getattr(receipt, "branch_id", None)
    number = getattr(receipt, "number", None)
    memo = f"Шатахуун таталт{f' №{number}' if number else ''}"

    lines = [
        LineSpec(
            account_code=ACC.INV_FUEL,
            debit=inventory,
            memo=memo,
            dims=Dims(
                fuel_id=getattr(receipt, "fuel_id", None),
                tank_id=getattr(receipt, "tank_id", None),
                supplier_id=supplier_id,
                branch_id=branch_id,
            ),
        )
    ]
    if vat != 0:
        lines.append(
            LineSpec(
                account_code=ACC.VAT_INPUT,
                debit=vat,
                memo="Орох НӨАТ",
                dims=Dims(supplier_id=supplier_id),
            )
        )
    lines.append(
        LineSpec(
            account_code=ACC.AP_SUPPLIER,
            credit=gross,
            memo=memo,
            dims=Dims(supplier_id=supplier_id),
        )
    )
    return lines


def build_purchase_lines(purchase: Any) -> list[LineSpec]:
    """Барааны худалдан авалт: 1302 = НӨАТ-гүй дүн, 1402 = НӨАТ, кредит 2101."""
    subtotal = _m(getattr(purchase, "subtotal", ZERO))
    vat = _m(getattr(purchase, "vat_amount", ZERO))
    gross = q2(subtotal + vat)
    if gross == 0:
        return []

    supplier_id = getattr(purchase, "supplier_id", None)
    branch_id = getattr(purchase, "branch_id", None)
    number = getattr(purchase, "number", None)
    memo = f"Худалдан авалт{f' №{number}' if number else ''}"

    lines = [
        LineSpec(
            account_code=ACC.INV_GOODS,
            debit=subtotal,
            memo=memo,
            dims=Dims(supplier_id=supplier_id, branch_id=branch_id),
        )
    ]
    if vat != 0:
        lines.append(
            LineSpec(
                account_code=ACC.VAT_INPUT,
                debit=vat,
                memo="Орох НӨАТ",
                dims=Dims(supplier_id=supplier_id),
            )
        )
    lines.append(
        LineSpec(
            account_code=ACC.AP_SUPPLIER,
            credit=gross,
            memo=memo,
            dims=Dims(supplier_id=supplier_id),
        )
    )
    return lines


# --------------------------------------------------------------------------- #
# EXPENSE_POSTED
# --------------------------------------------------------------------------- #
def build_expense_lines(expense: Any) -> list[LineSpec]:
    """Үйл ажиллагааны зардал.

    Дт: зардлын данс (НӨАТ-гүй дүн) + 1402 (орох НӨАТ, байвал)
    Кт: 1101 (бэлэн) / 1110 (банк) / 2101 (нийлүүлэгчийн өглөг)
    """
    subtotal = _m(getattr(expense, "subtotal", ZERO))
    vat = _m(getattr(expense, "vat_amount", ZERO))
    gross = q2(subtotal + vat)
    if gross == 0:
        return []

    account_code = getattr(expense, "account_code", None)
    if account_code not in ACC.OPERATING_EXPENSES:
        raise ValueError(f"Зардлын данс биш: {account_code}")

    supplier_id = getattr(expense, "supplier_id", None)
    branch_id = getattr(expense, "branch_id", None)
    number = getattr(expense, "number", None)
    memo = f"Зардал{f' №{number}' if number else ''}"

    method = str(getattr(expense, "payment_method", "cash"))
    if method == "credit":
        credit_account = ACC.AP_SUPPLIER
    elif method == "bank":
        credit_account = ACC.BANK
    else:
        credit_account = ACC.CASH

    lines = [
        LineSpec(
            account_code=account_code,
            debit=subtotal,
            memo=memo,
            dims=Dims(supplier_id=supplier_id, branch_id=branch_id),
        )
    ]
    if vat != 0:
        lines.append(
            LineSpec(
                account_code=ACC.VAT_INPUT,
                debit=vat,
                memo="Орох НӨАТ",
                dims=Dims(supplier_id=supplier_id, branch_id=branch_id),
            )
        )
    # Харилцахаас төлсөн бол аль данснаас гарсныг хэмжүүрээр тэмдэглэнэ —
    # ингэснээр данс тус бүрийн үлдэгдэл ерөнхий дэвтрээс гарна.
    bank_account_id = (
        getattr(expense, "bank_account_id", None) if credit_account == ACC.BANK else None
    )
    lines.append(
        LineSpec(
            account_code=credit_account,
            credit=gross,
            memo=memo,
            dims=Dims(supplier_id=supplier_id, bank_account_id=bank_account_id, branch_id=branch_id),
        )
    )
    return lines


# --------------------------------------------------------------------------- #
# PAYROLL_POSTED / PAYROLL_PAID
# --------------------------------------------------------------------------- #
def build_payroll_lines(period: Any) -> list[LineSpec]:
    """Сарын цалингийн тооцоог журналд бичих.

    Дт 5301 Цалин хөлс            = нийт цалин (gross)
    Дт 5302 НД шимтгэл            = ажил олгогчийн НДШ
       Кт 2401 Цалингийн өглөг    = гарт олгох цэвэр цалин
       Кт 2402 ХХОАТ-ын өглөг     = суутгасан ХХОАТ
       Кт 2403 НДШ-ийн өглөг      = ажилтны + ажил олгогчийн НДШ

    Урьдчилгаа/суутгал байвал нэмж:
       Кт 1205 Ажилтны урьдчилгаа = суутгасан дүн

    Учир нь урьдчилгаа нь **өмнө нь олгогдсон** мөнгө — түүнийг цалингаас
    суутгах нь шинэ өр үүсгэхгүй, харин авлагыг хаадаг.

    Тэнцэл: gross + si_employer == net + pit + (si_employee + si_employer) + суутгал,
    учир нь net = gross − si_employee − pit − суутгал.
    """
    gross = _m(getattr(period, "gross_total", ZERO))
    si_employee = _m(getattr(period, "si_employee_total", ZERO))
    si_employer = _m(getattr(period, "si_employer_total", ZERO))
    pit = _m(getattr(period, "pit_total", ZERO))
    net = _m(getattr(period, "net_total", ZERO))
    if gross == 0:
        return []

    year = getattr(period, "year", None)
    month = getattr(period, "month", None)
    memo = f"Цалин {year}.{month:02d}" if year and month else "Цалингийн тооцоо"

    # Урьдчилгаа/бусад суутгал — өмнө нь олгосон мөнгө тул авлагыг хаана.
    deductions = q2(gross - si_employee - pit - net)

    lines = [
        LineSpec(account_code=ACC.EXP_SALARY, debit=gross, memo=memo),
    ]
    if si_employer != 0:
        lines.append(
            LineSpec(account_code=ACC.EXP_SOCIAL_INS, debit=si_employer, memo=f"{memo} — ажил олгогчийн НДШ")
        )
    lines.append(LineSpec(account_code=ACC.AP_SALARY, credit=net, memo=f"{memo} — гарт олгох"))
    if pit != 0:
        lines.append(LineSpec(account_code=ACC.AP_PIT, credit=pit, memo=f"{memo} — ХХОАТ"))
    si_total = q2(si_employee + si_employer)
    if si_total != 0:
        lines.append(LineSpec(account_code=ACC.AP_SOCIAL_INS, credit=si_total, memo=f"{memo} — НДШ"))
    if deductions != 0:
        lines.append(
            LineSpec(
                account_code=ACC.AR_EMPLOYEE,
                credit=deductions,
                memo=f"{memo} — урьдчилгаа суутгал",
            )
        )
    return lines


def build_advance_lines(advance: Any) -> list[LineSpec]:
    """Ажилтанд урьдчилгаа олгох: Дт 1205 Ажилтны урьдчилгаа, Кт касс/банк.

    Цалин бодох үед энэ авлага суутгагдаж хаагдана.
    """
    amount = _m(getattr(advance, "amount", ZERO))
    if amount == 0:
        return []
    memo = getattr(advance, "memo", None) or "Ажилтанд урьдчилгаа"
    credit_account = _cash_account(getattr(advance, "paid_from", "cash"))
    return [
        LineSpec(account_code=ACC.AR_EMPLOYEE, debit=amount, memo=memo),
        LineSpec(account_code=credit_account, credit=amount, memo=memo),
    ]


def build_payroll_payment_lines(payment: Any) -> list[LineSpec]:
    """Цалин / ХХОАТ / НДШ-ийн өглөгийг төлөх: Дт өглөг, Кт касс эсвэл банк."""
    amount = _m(getattr(payment, "amount", ZERO))
    if amount == 0:
        return []

    target = str(getattr(payment, "target", "salary"))
    debit_account = {
        "salary": ACC.AP_SALARY,
        "pit": ACC.AP_PIT,
        "social": ACC.AP_SOCIAL_INS,
    }.get(target)
    if debit_account is None:
        raise ValueError(f"Тодорхойгүй цалингийн төлбөрийн зорилт: {target}")

    memo = getattr(payment, "memo", None) or "Цалингийн төлбөр"
    credit_account = _cash_account(getattr(payment, "paid_from", "bank"))
    return [
        LineSpec(account_code=debit_account, debit=amount, memo=memo),
        LineSpec(account_code=credit_account, credit=amount, memo=memo),
    ]


# --------------------------------------------------------------------------- #
# AP_PAYMENT / AR_RECEIPT
# --------------------------------------------------------------------------- #
def build_ap_payment_lines(payment: Any) -> list[LineSpec]:
    """Нийлүүлэгчид төлсөн: дебит 2101, кредит 1110 (эсвэл 1101)."""
    amount = _m(getattr(payment, "amount", ZERO))
    if amount == 0:
        return []
    supplier_id = getattr(payment, "supplier_id", None)
    account = _cash_account(getattr(payment, "paid_from", "bank"))
    memo = "Нийлүүлэгчид төлсөн"
    return [
        LineSpec(
            account_code=ACC.AP_SUPPLIER,
            debit=amount,
            memo=memo,
            dims=Dims(supplier_id=supplier_id),
        ),
        LineSpec(account_code=account, credit=amount, memo=memo, dims=Dims(supplier_id=supplier_id)),
    ]


def build_ar_receipt_lines(payment: Any) -> list[LineSpec]:
    """Гэрээт үйлчлүүлэгчээс төлбөр авсан: дебит 1110/1101, кредит 1201."""
    amount = _m(getattr(payment, "amount", ZERO))
    if amount == 0:
        return []
    customer_id = getattr(payment, "customer_id", None)
    account = _cash_account(getattr(payment, "received_to", "bank"))
    bank_account_id = getattr(payment, "bank_account_id", None) if account == ACC.BANK else None
    memo = "Гэрээт авлагын төлбөр"
    return [
        LineSpec(
            account_code=account,
            debit=amount,
            memo=memo,
            dims=Dims(customer_id=customer_id, bank_account_id=bank_account_id),
        ),
        LineSpec(
            account_code=ACC.AR_CONTRACT,
            credit=amount,
            memo=memo,
            dims=Dims(customer_id=customer_id),
        ),
    ]


# --------------------------------------------------------------------------- #
# Ээлжийн кассын зөрүү / түлшний зөрүү
# --------------------------------------------------------------------------- #
def build_cash_variance_lines(diff: Decimal) -> list[LineSpec]:
    """Кассын зөрүү. ``diff = зарлагадсан − тооцоолсон``.

    ``diff < 0`` → дутагдал: дебит 5902, кредит 1101.
    ``diff > 0`` → илүүдэл: дебит 1101, кредит 4903.
    """
    value = _m(diff)
    if value == 0:
        return []
    if value < 0:
        short = -value
        return [
            LineSpec(account_code=ACC.CASH_SHORT, debit=short, memo="Кассын дутагдал"),
            LineSpec(account_code=ACC.CASH, credit=short, memo="Кассын дутагдал"),
        ]
    return [
        LineSpec(account_code=ACC.CASH, debit=value, memo="Кассын илүүдэл"),
        LineSpec(account_code=ACC.OTHER_INCOME, credit=value, memo="Кассын илүүдэл"),
    ]


def build_fuel_variance_lines(
    amount: Decimal,
    tank_id: uuid.UUID | None = None,
    fuel_id: uuid.UUID | None = None,
) -> list[LineSpec]:
    """Түлшний зөрүү (мөнгөн дүнгээр).

    ``amount < 0`` → хорогдол: дебит 5201, кредит 1301.
    ``amount > 0`` → илүүдэл: дебит 1301, кредит 4903.
    """
    value = _m(amount)
    if value == 0:
        return []
    dims = Dims(fuel_id=fuel_id, tank_id=tank_id)
    if value < 0:
        loss = -value
        return [
            LineSpec(account_code=ACC.FUEL_LOSS, debit=loss, memo="Түлшний хорогдол", dims=dims),
            LineSpec(account_code=ACC.INV_FUEL, credit=loss, memo="Түлшний хорогдол", dims=dims),
        ]
    return [
        LineSpec(account_code=ACC.INV_FUEL, debit=value, memo="Түлшний илүүдэл", dims=dims),
        LineSpec(account_code=ACC.OTHER_INCOME, credit=value, memo="Түлшний илүүдэл", dims=dims),
    ]


# --------------------------------------------------------------------------- #
# REFUND_POSTED
# --------------------------------------------------------------------------- #
def build_refund_lines(
    amount: Decimal,
    vat: Decimal,
    cogs: Decimal = ZERO,
    restock: bool = False,
    method: str = PaymentMethod.CASH,
) -> list[LineSpec]:
    """Буцаалт: дебит 4901 (цэвэр) + 2201 (НӨАТ), кредит мөнгө.

    ``restock=True`` бол нөөц буцаана: дебит 1302, кредит 5102.
    """
    gross = _m(amount)
    vat_amount = _m(vat)
    cogs_amount = _m(cogs)
    lines: list[LineSpec] = []

    if gross != 0:
        net = q2(gross - vat_amount)
        if net != 0:
            lines.append(LineSpec(account_code=ACC.SALES_RETURNS, debit=net, memo="Борлуулалтын буцаалт"))
        if vat_amount != 0:
            lines.append(LineSpec(account_code=ACC.VAT_OUTPUT, debit=vat_amount, memo="Буцаалтын НӨАТ"))
        method = str(method)
        refund_account = ACC.CASH if method == str(PaymentMethod.CASH) else ACC.tender_account(method)
        lines.append(LineSpec(account_code=refund_account, credit=gross, memo="Буцаалтын төлбөр"))

    if restock and cogs_amount != 0:
        lines.append(LineSpec(account_code=ACC.INV_GOODS, debit=cogs_amount, memo="Буцаалтын нөөц сэргээлт"))
        lines.append(LineSpec(account_code=ACC.COGS_GOODS, credit=cogs_amount, memo="Буцаалтын өртөг сэргээлт"))

    return lines


# --------------------------------------------------------------------------- #
# CARD_SETTLEMENT / QR_SETTLEMENT
# --------------------------------------------------------------------------- #
def build_settlement_lines(method: str, amount: Decimal) -> list[LineSpec]:
    """Эквайрингийн тооцоо: дебит 1110, кредит 1102 (карт) эсвэл 1103 (QR)."""
    value = _m(amount)
    if value == 0:
        return []
    key = str(method).lower()
    if key == str(PaymentMethod.CARD):
        clearing, label = ACC.CARD_CLEARING, "Картын тооцоо"
    elif key == str(PaymentMethod.QR):
        clearing, label = ACC.QR_CLEARING, "QR тооцоо"
    else:
        raise ValueError(f"Тодорхойгүй тооцооны төрөл: {method}")
    return [
        LineSpec(account_code=ACC.BANK, debit=value, memo=label),
        LineSpec(account_code=clearing, credit=value, memo=label),
    ]


# --------------------------------------------------------------------------- #
# SHIPMENT_POSTED / SHIPMENT_DELIVERY / SHIPMENT_SALE / SHIPMENT_LOSS
# --------------------------------------------------------------------------- #
def build_shipment_lines(shipment: Any, totals: Iterable[Any]) -> list[LineSpec]:
    """Ачилтын бүртгэл: Дт 1303 (түлш бүрээр), Дт 1304 (бараа бүрээр) — тээвэртэй
    landed өртгөөр; дараа нь НИЙЛҮҮЛЭГЧ ТУС БҮРД Дт 1402, Кт 2101.

    Түлш машин дээр байгаа тул 1301 биш «Замд яваа түлш» (1303), бараа «Замд
    яваа бараа» (1304) дансанд орно.  Салбарт буулгах бүрд 1303 → 1301,
    1304 → 1302 шилжинэ.  ``totals`` — ``shipment_service.supplier_totals``:
    нийлүүлэгч бүрийн subtotal (үндсэнд тээвэртэй), vat_amount, total_gross;
    Σ subtotal == shipment.subtotal тул дебит, кредит яг тэнцэнэ.
    """
    main_supplier = getattr(shipment, "supplier_id", None)
    number = getattr(shipment, "number", None)
    vehicle = getattr(shipment, "vehicle_no", "") or ""
    memo = f"Ачилт{f' №{number}' if number else ''} — {vehicle}".strip(" —")

    def line_supplier(line: Any) -> Any:
        return getattr(line, "supplier_id", None) or main_supplier

    lines: list[LineSpec] = []
    landed_total = ZERO
    for item in getattr(shipment, "items", []) or []:
        amount = _m(_d(getattr(item, "liters", ZERO)) * _d(getattr(item, "landed_unit_cost", ZERO)))
        if amount == 0:
            continue
        landed_total = q2(landed_total + amount)
        lines.append(
            LineSpec(
                account_code=ACC.FUEL_IN_TRANSIT,
                debit=amount,
                memo=memo,
                dims=Dims(fuel_id=getattr(item, "fuel_id", None), supplier_id=line_supplier(item)),
            )
        )
    for goods in getattr(shipment, "goods", []) or []:
        amount = _m(_d(getattr(goods, "qty", ZERO)) * _d(getattr(goods, "landed_unit_cost", ZERO)))
        if amount == 0:
            continue
        landed_total = q2(landed_total + amount)
        lines.append(
            LineSpec(
                account_code=ACC.GOODS_IN_TRANSIT,
                debit=amount,
                memo=f"{memo} (бараа)",
                dims=Dims(supplier_id=line_supplier(goods)),
            )
        )
    if not lines:
        return []

    # Тээврийн хуваарилалтын дугуйллын зөрүүг эхний мөрөнд шингээнэ —
    # ингэснээр Σ дебит == subtotal (тоо·өртөг + тээвэр) яг тэнцэнэ.
    subtotal = _m(getattr(shipment, "subtotal", ZERO))
    drift = q2(subtotal - landed_total)
    if drift != 0:
        first = lines[0]
        lines[0] = LineSpec(
            account_code=first.account_code,
            debit=q2(first.debit + drift),
            memo=first.memo,
            dims=first.dims,
        )

    # Нийлүүлэгч бүрийн НӨАТ ба өглөг — машин олон нийлүүлэгчээс ачдаг.
    for bucket in totals:
        supplier_id = getattr(bucket, "supplier_id", None)
        vat = _m(getattr(bucket, "vat_amount", ZERO))
        gross = _m(getattr(bucket, "total_gross", ZERO))
        if gross == 0:
            continue
        if vat != 0:
            lines.append(
                LineSpec(
                    account_code=ACC.VAT_INPUT,
                    debit=vat,
                    memo="Орох НӨАТ",
                    dims=Dims(supplier_id=supplier_id),
                )
            )
        lines.append(
            LineSpec(
                account_code=ACC.AP_SUPPLIER,
                credit=gross,
                memo=memo,
                dims=Dims(supplier_id=supplier_id),
            )
        )
    return lines


def build_shipment_delivery_lines(receipt: Any) -> list[LineSpec]:
    """Ачилтаас салбарын саванд буулгах: Дт 1301 (салбар), Кт 1303.

    Өглөг, НӨАТ ачилт дээрээ аль хэдийн бүртгэгдсэн тул энд зөвхөн нөөц
    шилжинэ.  ``receipt.subtotal`` = литр × ачилтын landed нэгж өртөг.
    """
    amount = _m(getattr(receipt, "subtotal", ZERO))
    if amount == 0:
        return []
    number = getattr(receipt, "number", None)
    memo = f"Ачилтаас буулгалт{f' №{number}' if number else ''}"
    fuel_id = getattr(receipt, "fuel_id", None)
    return [
        LineSpec(
            account_code=ACC.INV_FUEL,
            debit=amount,
            memo=memo,
            dims=Dims(
                fuel_id=fuel_id,
                tank_id=getattr(receipt, "tank_id", None),
                branch_id=getattr(receipt, "branch_id", None),
            ),
        ),
        LineSpec(
            account_code=ACC.FUEL_IN_TRANSIT,
            credit=amount,
            memo=memo,
            dims=Dims(fuel_id=fuel_id),
        ),
    ]


def build_shipment_goods_delivery_lines(purchase: Any) -> list[LineSpec]:
    """Ачилтаас салбарт бараа буулгах: Дт 1302 (салбар), Кт 1304.

    Өглөг, НӨАТ ачилт дээрээ бүртгэгдсэн тул энд зөвхөн нөөц шилжинэ.
    ``purchase.subtotal`` = Σ тоо × ачилтын landed нэгж өртөг.
    """
    amount = _m(getattr(purchase, "subtotal", ZERO))
    if amount == 0:
        return []
    number = getattr(purchase, "number", None)
    memo = f"Ачилтаас бараа буулгалт{f' №{number}' if number else ''}"
    supplier_id = getattr(purchase, "supplier_id", None)
    return [
        LineSpec(
            account_code=ACC.INV_GOODS,
            debit=amount,
            memo=memo,
            dims=Dims(supplier_id=supplier_id, branch_id=getattr(purchase, "branch_id", None)),
        ),
        LineSpec(
            account_code=ACC.GOODS_IN_TRANSIT,
            credit=amount,
            memo=memo,
            dims=Dims(supplier_id=supplier_id),
        ),
    ]


def build_shipment_sale_lines(outflow: Any) -> list[LineSpec]:
    """Машинаас шууд борлуулалт: Дт мөнгө, Кт 4101 + 2201; Дт 5101, Кт 1303.

    ``outflow.amount`` — НӨАТ-тай нийт үнэ, ``outflow.cost_amount`` — өртөг.
    """
    gross = _m(getattr(outflow, "amount", ZERO))
    cost = _m(getattr(outflow, "cost_amount", ZERO))
    if gross == 0 and cost == 0:
        return []

    fuel_id = getattr(outflow, "fuel_id", None)
    branch_id = getattr(outflow, "branch_id", None)
    memo = "Машинаас шууд борлуулалт"
    dims = Dims(fuel_id=fuel_id, branch_id=branch_id)

    lines: list[LineSpec] = []
    if gross != 0:
        received = str(getattr(outflow, "received_to", "bank"))
        cash_account = _cash_account(received)
        bank_account_id = (
            getattr(outflow, "bank_account_id", None) if cash_account == ACC.BANK else None
        )
        vat = vat_from_gross(gross, VAT_RATE)
        net = q2(gross - vat)
        lines.append(
            LineSpec(
                account_code=cash_account,
                debit=gross,
                memo=memo,
                dims=Dims(fuel_id=fuel_id, branch_id=branch_id, bank_account_id=bank_account_id),
            )
        )
        lines.append(LineSpec(account_code=ACC.REV_FUEL, credit=net, memo=memo, dims=dims))
        if vat != 0:
            lines.append(
                LineSpec(account_code=ACC.VAT_OUTPUT, credit=vat, memo="Борлуулалтын НӨАТ", dims=dims)
            )
    if cost != 0:
        lines.append(LineSpec(account_code=ACC.COGS_FUEL, debit=cost, memo="Түлшний өртөг", dims=dims))
        lines.append(
            LineSpec(
                account_code=ACC.FUEL_IN_TRANSIT,
                credit=cost,
                memo="Машинаас хасалт",
                dims=Dims(fuel_id=fuel_id),
            )
        )
    return lines


def build_shipment_loss_lines(outflow: Any) -> list[LineSpec]:
    """Машин дээрх хорогдол: Дт 5201, Кт 1303 (өртгөөр)."""
    cost = _m(getattr(outflow, "cost_amount", ZERO))
    if cost == 0:
        return []
    fuel_id = getattr(outflow, "fuel_id", None)
    memo = "Ачилтын хорогдол"
    return [
        LineSpec(
            account_code=ACC.FUEL_LOSS,
            debit=cost,
            memo=memo,
            dims=Dims(fuel_id=fuel_id, branch_id=getattr(outflow, "branch_id", None)),
        ),
        LineSpec(
            account_code=ACC.FUEL_IN_TRANSIT,
            credit=cost,
            memo=memo,
            dims=Dims(fuel_id=fuel_id),
        ),
    ]


# --------------------------------------------------------------------------- #
# BRANCH_SETTLEMENT_PAID
# --------------------------------------------------------------------------- #
def build_branch_settlement_lines(payment: Any) -> list[LineSpec]:
    """Салбараас толгойн данс руу төлбөр: Дт 1110 (толгойн данс), Кт касс/банк.

    Салбарын кассад хуримтлагдсан борлуулалтын мөнгө толгойн харилцах руу
    шилжиж байгаа бодит хөдөлгөөн.  Кредит тал салбарын хэмжүүртэй тул
    салбарын кассын үлдэгдэл ерөнхий дэвтрээс зөв гарна.
    """
    amount = _m(getattr(payment, "amount", ZERO))
    if amount == 0:
        return []
    branch_id = getattr(payment, "branch_id", None)
    memo = "Салбарын тооцооны төлбөр"

    paid_from = str(getattr(payment, "paid_from", "cash"))
    credit_account = _cash_account(paid_from)
    from_bank = (
        getattr(payment, "from_bank_account_id", None) if credit_account == ACC.BANK else None
    )
    return [
        LineSpec(
            account_code=ACC.BANK,
            debit=amount,
            memo=memo,
            dims=Dims(bank_account_id=getattr(payment, "to_bank_account_id", None)),
        ),
        LineSpec(
            account_code=credit_account,
            credit=amount,
            memo=memo,
            dims=Dims(branch_id=branch_id, bank_account_id=from_bank),
        ),
    ]
