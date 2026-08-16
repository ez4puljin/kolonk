"""WP3 — бичилтийн дүрмийн нэгжийн тест.

Бүх тест **DB-гүй**: ``posting_rules`` цэвэр функцууд ба ``normalize_lines``
шалгалтыг л шинжилнэ. Fake объектууд ``SimpleNamespace``-ээр үүснэ.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.enums import EventType, ItemType, PaymentMethod, SourceType
from app.money import q2, vat_from_gross
from app.services.coa import ACC, COA_BY_CODE, COA_SEED
from app.services.posting import (
    Dims,
    LineSpec,
    UnbalancedEntryError,
    normalize_lines,
    posting,
)
from app.services import posting_rules as rules

D = Decimal
ZERO = D("0")

FUEL_A = uuid4()
FUEL_B = uuid4()
TANK_A = uuid4()
TANK_B = uuid4()
SUPPLIER = uuid4()
CUSTOMER = uuid4()


# --------------------------------------------------------------------------- #
# Туслахууд
# --------------------------------------------------------------------------- #
def totals(lines: list[LineSpec]) -> tuple[Decimal, Decimal]:
    debit = q2(sum((ln.debit for ln in lines), ZERO))
    credit = q2(sum((ln.credit for ln in lines), ZERO))
    return debit, credit


def assert_balanced(lines: list[LineSpec]) -> None:
    assert lines, "мөр үүсээгүй байна"
    debit, credit = totals(lines)
    assert debit == credit, f"тэнцэхгүй: дебит {debit} ≠ кредит {credit}"
    assert debit > 0
    # normalize_lines алдаа өгөхгүй байх ёстой
    normalize_lines(lines)


def account_sum(lines: list[LineSpec], code: str, side: str) -> Decimal:
    return q2(sum((getattr(ln, side) for ln in lines if ln.account_code == code), ZERO))


def fuel_item(fuel_id, tank_id, amount: str, cogs: str) -> SimpleNamespace:
    return SimpleNamespace(
        item_type=ItemType.FUEL,
        fuel_id=fuel_id,
        tank_id=tank_id,
        product_id=None,
        amount=D(amount),
        cogs_amount=D(cogs),
    )


def product_item(amount: str, cogs: str) -> SimpleNamespace:
    return SimpleNamespace(
        item_type=ItemType.PRODUCT,
        fuel_id=None,
        tank_id=None,
        product_id=uuid4(),
        amount=D(amount),
        cogs_amount=D(cogs),
    )


def payment(method, amount: str) -> SimpleNamespace:
    return SimpleNamespace(method=method, amount=D(amount))


def make_sale(items, payments, customer_id=None) -> SimpleNamespace:
    gross = q2(sum((i.amount for i in items), ZERO))
    return SimpleNamespace(
        id=uuid4(),
        customer_id=customer_id,
        subtotal=q2(gross - vat_from_gross(gross)),
        vat_amount=vat_from_gross(gross),
        total=gross,
        cogs_total=q2(sum((i.cogs_amount for i in items), ZERO)),
    )


# --------------------------------------------------------------------------- #
# Дансны төлөвлөгөө
# --------------------------------------------------------------------------- #
def test_tender_account_mapping() -> None:
    assert ACC.tender_account(PaymentMethod.CASH) == ACC.CASH == "1101"
    assert ACC.tender_account(PaymentMethod.CARD) == ACC.CARD_CLEARING == "1102"
    assert ACC.tender_account(PaymentMethod.QR) == ACC.QR_CLEARING == "1103"
    assert ACC.tender_account(PaymentMethod.CONTRACT) == ACC.AR_CONTRACT == "1201"
    assert ACC.tender_account(PaymentMethod.VOUCHER) == ACC.VOUCHER_LIABILITY == "2301"
    assert ACC.tender_account(PaymentMethod.PREPAID) == ACC.PREPAID_LIABILITY == "2302"
    # мөр (str) хэлбэрээр ч ажиллана
    assert ACC.tender_account("cash") == "1101"


def test_tender_account_unknown_raises() -> None:
    with pytest.raises(ValueError):
        ACC.tender_account("bitcoin")


def test_coa_seed_covers_every_constant() -> None:
    codes = {row["code"] for row in COA_SEED}
    required = {
        ACC.CASH, ACC.CARD_CLEARING, ACC.QR_CLEARING, ACC.BANK, ACC.AR_CONTRACT,
        ACC.INV_FUEL, ACC.INV_GOODS, ACC.VAT_INPUT, ACC.AP_SUPPLIER, ACC.VAT_OUTPUT,
        ACC.VOUCHER_LIABILITY, ACC.PREPAID_LIABILITY, ACC.OWNER_CAPITAL, ACC.RETAINED,
        ACC.REV_FUEL, ACC.REV_GOODS, ACC.SALES_RETURNS, ACC.OTHER_INCOME,
        ACC.COGS_FUEL, ACC.COGS_GOODS, ACC.FUEL_LOSS, ACC.CASH_SHORT,
    }
    assert required <= codes
    assert len(codes) == len(COA_SEED), "давхардсан дансны код байна"
    for header in (ACC.HDR_ASSET, ACC.HDR_LIABILITY, ACC.HDR_EQUITY, ACC.HDR_REVENUE, ACC.HDR_EXPENSE):
        assert COA_BY_CODE[header]["is_postable"] is False
    for code in required:
        assert COA_BY_CODE[code]["is_postable"] is True
        assert COA_BY_CODE[code]["parent_code"] in {
            ACC.HDR_ASSET, ACC.HDR_LIABILITY, ACC.HDR_EQUITY, ACC.HDR_REVENUE, ACC.HDR_EXPENSE
        }
        assert COA_BY_CODE[code]["name_mn"].strip(), "монгол нэр хоосон байна"


# --------------------------------------------------------------------------- #
# normalize_lines
# --------------------------------------------------------------------------- #
def test_normalize_drops_zero_lines() -> None:
    lines = [
        LineSpec(ACC.CASH, debit=D("100.00")),
        LineSpec(ACC.OTHER_INCOME, credit=D("100.00")),
        LineSpec(ACC.BANK),
        LineSpec(ACC.INV_GOODS, debit=ZERO, credit=ZERO),
    ]
    result = normalize_lines(lines)
    assert len(result) == 2
    assert {ln.account_code for ln in result} == {ACC.CASH, ACC.OTHER_INCOME}


def test_normalize_quantizes_to_two_places() -> None:
    lines = [
        LineSpec(ACC.CASH, debit=D("100.005")),
        LineSpec(ACC.OTHER_INCOME, credit=D("100.005")),
    ]
    result = normalize_lines(lines)
    assert result[0].debit == D("100.01")
    assert result[1].credit == D("100.01")


def test_normalize_flips_negative_amounts() -> None:
    lines = [
        LineSpec(ACC.CASH, debit=D("-50.00")),
        LineSpec(ACC.OTHER_INCOME, credit=D("-50.00")),
    ]
    result = normalize_lines(lines)
    assert result[0].debit == ZERO and result[0].credit == D("50.00")
    assert result[1].credit == ZERO and result[1].debit == D("50.00")


def test_normalize_empty_returns_empty() -> None:
    assert normalize_lines([]) == []
    assert normalize_lines([LineSpec(ACC.CASH), LineSpec(ACC.BANK)]) == []


def test_normalize_unbalanced_raises() -> None:
    lines = [
        LineSpec(ACC.CASH, debit=D("100.00")),
        LineSpec(ACC.OTHER_INCOME, credit=D("99.99")),
    ]
    with pytest.raises(UnbalancedEntryError) as exc:
        normalize_lines(lines)
    assert "тэнцэхгүй" in str(exc.value)


def test_normalize_single_line_raises() -> None:
    with pytest.raises(UnbalancedEntryError) as exc:
        normalize_lines([LineSpec(ACC.CASH, debit=D("10.00")), LineSpec(ACC.BANK)])
    assert "2 мөр" in str(exc.value)


def test_post_rejects_unbalanced_before_touching_db() -> None:
    """db=None дамжуулсан ч тэнцлийн шалгалт эхэлж ажиллана."""
    lines = [
        LineSpec(ACC.CASH, debit=D("10.00")),
        LineSpec(ACC.OTHER_INCOME, credit=D("11.00")),
    ]
    with pytest.raises(UnbalancedEntryError):
        asyncio.run(
            posting.post(
                None,  # type: ignore[arg-type]
                event_type=EventType.MANUAL_ENTRY,
                source_type=SourceType.MANUAL,
                source_id=uuid4(),
                entry_date=None,
                description="тест",
                lines=lines,
            )
        )


def test_post_returns_none_when_nothing_to_post() -> None:
    result = asyncio.run(
        posting.post(
            None,  # type: ignore[arg-type]
            event_type=EventType.FUEL_VARIANCE_LOSS,
            source_type=SourceType.SHIFT,
            source_id=uuid4(),
            entry_date=None,
            description="тэг зөрүү",
            lines=rules.build_fuel_variance_lines(ZERO, TANK_A, FUEL_A),
        )
    )
    assert result is None


# --------------------------------------------------------------------------- #
# build_sale_lines
# --------------------------------------------------------------------------- #
def test_sale_lines_balanced_and_split_exact() -> None:
    items = [
        fuel_item(FUEL_A, TANK_A, "58800.00", "45000.00"),
        fuel_item(FUEL_B, TANK_B, "33333.33", "25000.00"),
        product_item("5500.00", "3300.00"),
    ]
    payments = [payment(PaymentMethod.CASH, "50000.00"), payment(PaymentMethod.CARD, "47633.33")]
    sale = make_sale(items, payments)

    lines = rules.build_sale_lines(sale, items, payments)
    assert_balanced(lines)

    # НӨАТ яг sale.vat_amount
    assert account_sum(lines, ACC.VAT_OUTPUT, "credit") == sale.vat_amount

    # Орлого + НӨАТ = барааны нийт дүн
    revenue = account_sum(lines, ACC.REV_FUEL, "credit") + account_sum(lines, ACC.REV_GOODS, "credit")
    assert q2(revenue + sale.vat_amount) == sale.total

    # Төлбөр бүр өөрийн дансаараа дебит
    assert account_sum(lines, ACC.CASH, "debit") == D("50000.00")
    assert account_sum(lines, ACC.CARD_CLEARING, "debit") == D("47633.33")

    # Өртөг
    assert account_sum(lines, ACC.COGS_FUEL, "debit") == D("70000.00")
    assert account_sum(lines, ACC.INV_FUEL, "credit") == D("70000.00")
    assert account_sum(lines, ACC.COGS_GOODS, "debit") == D("3300.00")
    assert account_sum(lines, ACC.INV_GOODS, "credit") == D("3300.00")


def test_sale_revenue_and_cogs_carry_fuel_dimensions() -> None:
    items = [
        fuel_item(FUEL_A, TANK_A, "58800.00", "45000.00"),
        fuel_item(FUEL_A, TANK_A, "11760.00", "9000.00"),
        fuel_item(FUEL_B, TANK_B, "33333.33", "25000.00"),
    ]
    payments = [payment(PaymentMethod.CASH, "103893.33")]
    sale = make_sale(items, payments)
    lines = rules.build_sale_lines(sale, items, payments)
    assert_balanced(lines)

    rev_lines = [ln for ln in lines if ln.account_code == ACC.REV_FUEL]
    assert len(rev_lines) == 2, "түлш тус бүрд нэг орлогын мөр"
    assert {ln.dims.fuel_id for ln in rev_lines} == {FUEL_A, FUEL_B}
    assert {ln.dims.tank_id for ln in rev_lines} == {TANK_A, TANK_B}

    cogs_lines = [ln for ln in lines if ln.account_code == ACC.COGS_FUEL]
    assert len(cogs_lines) == 2
    by_fuel = {ln.dims.fuel_id: ln.debit for ln in cogs_lines}
    assert by_fuel[FUEL_A] == D("54000.00")
    assert by_fuel[FUEL_B] == D("25000.00")


@pytest.mark.parametrize(
    "fuel_amounts,goods_amount",
    [
        (["0.01"], "0.01"),
        (["33333.33", "33333.33", "33333.34"], "0.00"),
        (["7.77", "13.13"], "9.99"),
        (["100000.00"], "0.00"),
        (["0.00"], "12345.67"),
        (["1234.56", "2345.67", "3456.78", "4567.89"], "5678.90"),
    ],
)
def test_sale_vat_split_remainder_is_exact(fuel_amounts: list[str], goods_amount: str) -> None:
    items = [
        fuel_item(uuid4(), uuid4(), amount, "0.00")
        for amount in fuel_amounts
        if D(amount) != 0
    ]
    if D(goods_amount) != 0:
        items.append(product_item(goods_amount, "0.00"))
    gross = q2(sum((i.amount for i in items), ZERO))
    payments = [payment(PaymentMethod.CASH, str(gross))]
    sale = make_sale(items, payments)

    lines = rules.build_sale_lines(sale, items, payments)
    assert_balanced(lines)

    vat_booked = account_sum(lines, ACC.VAT_OUTPUT, "credit")
    assert vat_booked == sale.vat_amount, "НӨАТ-ын хэсгүүд яг нийлбэртэй тэнцэх ёстой"

    revenue = account_sum(lines, ACC.REV_FUEL, "credit") + account_sum(lines, ACC.REV_GOODS, "credit")
    assert q2(revenue + vat_booked) == gross


def test_sale_contract_payment_carries_customer_dim() -> None:
    items = [fuel_item(FUEL_A, TANK_A, "11000.00", "8000.00")]
    payments = [payment(PaymentMethod.CONTRACT, "11000.00")]
    sale = make_sale(items, payments, customer_id=CUSTOMER)
    lines = rules.build_sale_lines(sale, items, payments)
    assert_balanced(lines)

    ar = [ln for ln in lines if ln.account_code == ACC.AR_CONTRACT]
    assert len(ar) == 1
    assert ar[0].debit == D("11000.00")
    assert ar[0].dims.customer_id == CUSTOMER


def test_sale_with_voucher_and_prepaid_tenders() -> None:
    items = [product_item("22000.00", "14000.00")]
    payments = [
        payment(PaymentMethod.VOUCHER, "10000.00"),
        payment(PaymentMethod.PREPAID, "7000.00"),
        payment(PaymentMethod.QR, "5000.00"),
    ]
    sale = make_sale(items, payments)
    lines = rules.build_sale_lines(sale, items, payments)
    assert_balanced(lines)
    assert account_sum(lines, ACC.VOUCHER_LIABILITY, "debit") == D("10000.00")
    assert account_sum(lines, ACC.PREPAID_LIABILITY, "debit") == D("7000.00")
    assert account_sum(lines, ACC.QR_CLEARING, "debit") == D("5000.00")


def test_sale_builder_is_pure() -> None:
    items = [fuel_item(FUEL_A, TANK_A, "58800.00", "45000.00"), product_item("5500.00", "3300.00")]
    payments = [payment(PaymentMethod.CASH, "64300.00")]
    sale = make_sale(items, payments)
    snapshot = [(i.amount, i.cogs_amount) for i in items]

    first = rules.build_sale_lines(sale, items, payments)
    second = rules.build_sale_lines(sale, items, payments)

    assert first == second, "цэвэр функц давтан дуудахад ижил үр дүн өгөх ёстой"
    assert [(i.amount, i.cogs_amount) for i in items] == snapshot, "оролтыг өөрчилсөн байна"
    assert sale.vat_amount == make_sale(items, payments).vat_amount


# --------------------------------------------------------------------------- #
# Ваучер / урьдчилсан карт
# --------------------------------------------------------------------------- #
def test_voucher_sold_lines() -> None:
    voucher = SimpleNamespace(id=uuid4(), code="V-0001", face_value=D("50000.00"), customer_id=CUSTOMER)
    lines = rules.build_voucher_sold_lines(voucher, PaymentMethod.CASH)
    assert_balanced(lines)
    assert account_sum(lines, ACC.CASH, "debit") == D("50000.00")
    assert account_sum(lines, ACC.VOUCHER_LIABILITY, "credit") == D("50000.00")
    assert lines[1].dims.customer_id == CUSTOMER
    assert rules.build_voucher_sold_lines(SimpleNamespace(face_value=ZERO, customer_id=None)) == []


def test_prepaid_topup_lines() -> None:
    card = SimpleNamespace(id=uuid4(), card_no="P-77", customer_id=CUSTOMER, balance=ZERO)
    lines = rules.build_prepaid_topup_lines(card, D("120000.00"), PaymentMethod.CARD)
    assert_balanced(lines)
    assert account_sum(lines, ACC.CARD_CLEARING, "debit") == D("120000.00")
    assert account_sum(lines, ACC.PREPAID_LIABILITY, "credit") == D("120000.00")
    assert rules.build_prepaid_topup_lines(card, ZERO) == []


# --------------------------------------------------------------------------- #
# Худалдан авалт / таталт
# --------------------------------------------------------------------------- #
def test_fuel_receipt_lines() -> None:
    receipt = SimpleNamespace(
        id=uuid4(),
        number=12,
        supplier_id=SUPPLIER,
        tank_id=TANK_A,
        fuel_id=FUEL_A,
        liters=D("8000.000"),
        unit_cost=D("2450.500000"),
        freight_cost=D("150000.00"),
        vat_amount=D("1976400.00"),
        total_gross=D("21740400.00"),
    )
    lines = rules.build_fuel_receipt_lines(receipt)
    assert_balanced(lines)

    expected_inventory = q2(D("8000.000") * D("2450.500000") + D("150000.00"))
    assert account_sum(lines, ACC.INV_FUEL, "debit") == expected_inventory
    assert account_sum(lines, ACC.VAT_INPUT, "debit") == D("1976400.00")
    assert account_sum(lines, ACC.AP_SUPPLIER, "credit") == q2(expected_inventory + D("1976400.00"))

    inv_line = next(ln for ln in lines if ln.account_code == ACC.INV_FUEL)
    assert inv_line.dims.tank_id == TANK_A
    assert inv_line.dims.fuel_id == FUEL_A
    ap_line = next(ln for ln in lines if ln.account_code == ACC.AP_SUPPLIER)
    assert ap_line.dims.supplier_id == SUPPLIER


def test_fuel_receipt_without_vat_still_balances() -> None:
    receipt = SimpleNamespace(
        number=1,
        supplier_id=SUPPLIER,
        tank_id=TANK_A,
        fuel_id=FUEL_A,
        liters=D("1000.000"),
        unit_cost=D("2000.000000"),
        freight_cost=ZERO,
        vat_amount=ZERO,
        total_gross=D("2000000.00"),
    )
    lines = rules.build_fuel_receipt_lines(receipt)
    assert_balanced(lines)
    assert len(lines) == 2
    assert account_sum(lines, ACC.AP_SUPPLIER, "credit") == D("2000000.00")


def test_purchase_lines() -> None:
    purchase = SimpleNamespace(
        id=uuid4(),
        number=5,
        supplier_id=SUPPLIER,
        subtotal=D("450000.00"),
        vat_amount=D("45000.00"),
        total_gross=D("495000.00"),
    )
    lines = rules.build_purchase_lines(purchase)
    assert_balanced(lines)
    assert account_sum(lines, ACC.INV_GOODS, "debit") == D("450000.00")
    assert account_sum(lines, ACC.VAT_INPUT, "debit") == D("45000.00")
    assert account_sum(lines, ACC.AP_SUPPLIER, "credit") == D("495000.00")


def test_empty_documents_produce_no_lines() -> None:
    empty_receipt = SimpleNamespace(
        supplier_id=SUPPLIER, tank_id=TANK_A, fuel_id=FUEL_A,
        liters=ZERO, unit_cost=ZERO, freight_cost=ZERO, vat_amount=ZERO, total_gross=ZERO, number=None,
    )
    assert rules.build_fuel_receipt_lines(empty_receipt) == []
    assert rules.build_purchase_lines(
        SimpleNamespace(supplier_id=SUPPLIER, subtotal=ZERO, vat_amount=ZERO, total_gross=ZERO, number=None)
    ) == []


# --------------------------------------------------------------------------- #
# Өглөг / авлагын төлбөр
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("paid_from,expected", [("bank", ACC.BANK), ("cash", ACC.CASH)])
def test_ap_payment_lines(paid_from: str, expected: str) -> None:
    pay = SimpleNamespace(id=uuid4(), supplier_id=SUPPLIER, amount=D("1500000.00"), paid_from=paid_from)
    lines = rules.build_ap_payment_lines(pay)
    assert_balanced(lines)
    assert account_sum(lines, ACC.AP_SUPPLIER, "debit") == D("1500000.00")
    assert account_sum(lines, expected, "credit") == D("1500000.00")
    assert lines[0].dims.supplier_id == SUPPLIER


@pytest.mark.parametrize("received_to,expected", [("bank", ACC.BANK), ("cash", ACC.CASH)])
def test_ar_receipt_lines(received_to: str, expected: str) -> None:
    pay = SimpleNamespace(id=uuid4(), customer_id=CUSTOMER, amount=D("880000.00"), received_to=received_to)
    lines = rules.build_ar_receipt_lines(pay)
    assert_balanced(lines)
    assert account_sum(lines, expected, "debit") == D("880000.00")
    assert account_sum(lines, ACC.AR_CONTRACT, "credit") == D("880000.00")
    assert lines[1].dims.customer_id == CUSTOMER


def test_zero_payments_produce_no_lines() -> None:
    assert rules.build_ap_payment_lines(SimpleNamespace(supplier_id=SUPPLIER, amount=ZERO, paid_from="bank")) == []
    assert rules.build_ar_receipt_lines(SimpleNamespace(customer_id=CUSTOMER, amount=ZERO, received_to="bank")) == []


# --------------------------------------------------------------------------- #
# Кассын / түлшний зөрүү
# --------------------------------------------------------------------------- #
def test_cash_variance_short() -> None:
    lines = rules.build_cash_variance_lines(D("-12500.00"))
    assert_balanced(lines)
    assert account_sum(lines, ACC.CASH_SHORT, "debit") == D("12500.00")
    assert account_sum(lines, ACC.CASH, "credit") == D("12500.00")
    assert rules.cash_variance_event(D("-12500.00")) == EventType.SHIFT_CASH_SHORT


def test_cash_variance_over() -> None:
    lines = rules.build_cash_variance_lines(D("3200.00"))
    assert_balanced(lines)
    assert account_sum(lines, ACC.CASH, "debit") == D("3200.00")
    assert account_sum(lines, ACC.OTHER_INCOME, "credit") == D("3200.00")
    assert rules.cash_variance_event(D("3200.00")) == EventType.SHIFT_CASH_OVER


def test_cash_variance_zero() -> None:
    assert rules.build_cash_variance_lines(ZERO) == []


def test_fuel_variance_loss() -> None:
    lines = rules.build_fuel_variance_lines(D("-98000.00"), TANK_A, FUEL_A)
    assert_balanced(lines)
    assert account_sum(lines, ACC.FUEL_LOSS, "debit") == D("98000.00")
    assert account_sum(lines, ACC.INV_FUEL, "credit") == D("98000.00")
    assert all(ln.dims == Dims(fuel_id=FUEL_A, tank_id=TANK_A) for ln in lines)
    assert rules.fuel_variance_event(D("-98000.00")) == EventType.FUEL_VARIANCE_LOSS


def test_fuel_variance_gain() -> None:
    lines = rules.build_fuel_variance_lines(D("4500.00"), TANK_B, FUEL_B)
    assert_balanced(lines)
    assert account_sum(lines, ACC.INV_FUEL, "debit") == D("4500.00")
    assert account_sum(lines, ACC.OTHER_INCOME, "credit") == D("4500.00")
    assert rules.fuel_variance_event(D("4500.00")) == EventType.FUEL_VARIANCE_GAIN


def test_fuel_variance_zero() -> None:
    assert rules.build_fuel_variance_lines(ZERO, TANK_A, FUEL_A) == []


# --------------------------------------------------------------------------- #
# Буцаалт
# --------------------------------------------------------------------------- #
def test_refund_lines_without_restock() -> None:
    lines = rules.build_refund_lines(D("22000.00"), D("2000.00"))
    assert_balanced(lines)
    assert account_sum(lines, ACC.SALES_RETURNS, "debit") == D("20000.00")
    assert account_sum(lines, ACC.VAT_OUTPUT, "debit") == D("2000.00")
    assert account_sum(lines, ACC.CASH, "credit") == D("22000.00")
    assert account_sum(lines, ACC.INV_GOODS, "debit") == ZERO


def test_refund_lines_with_restock() -> None:
    lines = rules.build_refund_lines(D("22000.00"), D("2000.00"), D("13500.00"), True)
    assert_balanced(lines)
    assert account_sum(lines, ACC.INV_GOODS, "debit") == D("13500.00")
    assert account_sum(lines, ACC.COGS_GOODS, "credit") == D("13500.00")


def test_refund_lines_by_card() -> None:
    lines = rules.build_refund_lines(D("11000.00"), D("1000.00"), ZERO, False, PaymentMethod.CARD)
    assert_balanced(lines)
    assert account_sum(lines, ACC.CARD_CLEARING, "credit") == D("11000.00")


def test_refund_zero_produces_no_lines() -> None:
    assert rules.build_refund_lines(ZERO, ZERO) == []


# --------------------------------------------------------------------------- #
# Эквайрингийн тооцоо
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "method,clearing,event",
    [
        ("card", ACC.CARD_CLEARING, EventType.CARD_SETTLEMENT),
        ("qr", ACC.QR_CLEARING, EventType.QR_SETTLEMENT),
    ],
)
def test_settlement_lines(method: str, clearing: str, event: str) -> None:
    lines = rules.build_settlement_lines(method, D("2450000.00"))
    assert_balanced(lines)
    assert account_sum(lines, ACC.BANK, "debit") == D("2450000.00")
    assert account_sum(lines, clearing, "credit") == D("2450000.00")
    assert rules.settlement_event(method) == event


def test_settlement_unknown_method_raises() -> None:
    with pytest.raises(ValueError):
        rules.build_settlement_lines("cash", D("100.00"))
    with pytest.raises(ValueError):
        rules.settlement_event("cash")


def test_settlement_zero_produces_no_lines() -> None:
    assert rules.build_settlement_lines("card", ZERO) == []


# --------------------------------------------------------------------------- #
# Бүх builder тэнцүү байх нэгдсэн шалгалт
# --------------------------------------------------------------------------- #
def test_every_builder_returns_balanced_lines() -> None:
    items = [
        fuel_item(FUEL_A, TANK_A, "58800.00", "45000.00"),
        fuel_item(FUEL_B, TANK_B, "9999.99", "7777.77"),
        product_item("1234.56", "800.00"),
    ]
    payments = [payment(PaymentMethod.CASH, "70034.55")]
    sale = make_sale(items, payments)

    receipt = SimpleNamespace(
        number=1, supplier_id=SUPPLIER, tank_id=TANK_A, fuel_id=FUEL_A,
        liters=D("5000.000"), unit_cost=D("2333.333333"), freight_cost=D("99.99"),
        vat_amount=D("1166676.66"), total_gross=ZERO,
    )
    purchase = SimpleNamespace(
        number=2, supplier_id=SUPPLIER, subtotal=D("77777.77"),
        vat_amount=D("7777.78"), total_gross=D("85555.55"),
    )

    batches = [
        rules.build_sale_lines(sale, items, payments),
        rules.build_voucher_sold_lines(SimpleNamespace(code="V1", face_value=D("20000.00"), customer_id=None)),
        rules.build_prepaid_topup_lines(SimpleNamespace(card_no="C1", customer_id=None), D("33333.33")),
        rules.build_fuel_receipt_lines(receipt),
        rules.build_purchase_lines(purchase),
        rules.build_ap_payment_lines(SimpleNamespace(supplier_id=SUPPLIER, amount=D("11.11"), paid_from="cash")),
        rules.build_ar_receipt_lines(SimpleNamespace(customer_id=CUSTOMER, amount=D("22.22"), received_to="bank")),
        rules.build_cash_variance_lines(D("-0.01")),
        rules.build_cash_variance_lines(D("0.01")),
        rules.build_fuel_variance_lines(D("-1234.56"), TANK_A, FUEL_A),
        rules.build_fuel_variance_lines(D("1234.56"), TANK_A, FUEL_A),
        rules.build_refund_lines(D("999.99"), D("90.91"), D("500.00"), True),
        rules.build_settlement_lines("card", D("0.01")),
        rules.build_settlement_lines("qr", D("123456.78")),
    ]
    for batch in batches:
        assert_balanced(batch)
        for line in batch:
            assert line.debit >= 0 and line.credit >= 0
            assert not (line.debit > 0 and line.credit > 0), "нэг мөрөнд хоёр тал зэрэг байж болохгүй"
            assert line.account_code in COA_BY_CODE, f"тодорхойгүй данс: {line.account_code}"
            assert COA_BY_CODE[line.account_code]["is_postable"] is True


# --------------------------------------------------------------------------- #
# Үйл ажиллагааны зардал
# --------------------------------------------------------------------------- #
def make_expense(account_code, subtotal, vat, method, supplier_id=None):
    return SimpleNamespace(
        number=7,
        account_code=account_code,
        subtotal=D(subtotal),
        vat_amount=D(vat),
        payment_method=method,
        supplier_id=supplier_id,
    )


@pytest.mark.parametrize(
    ("method", "credit_account"),
    [
        ("cash", ACC.CASH),
        ("bank", ACC.BANK),
        ("credit", ACC.AP_SUPPLIER),
    ],
)
def test_expense_lines_credit_the_right_source(method, credit_account) -> None:
    """Төлбөрийн хэлбэр бүр зөв дансыг кредитлэнэ."""
    expense = make_expense(ACC.EXP_ELECTRICITY, "409090.91", "40909.09", method)
    lines = rules.build_expense_lines(expense)

    assert_balanced(lines)
    assert account_sum(lines, ACC.EXP_ELECTRICITY, "debit") == D("409090.91")
    assert account_sum(lines, ACC.VAT_INPUT, "debit") == D("40909.09")
    assert account_sum(lines, credit_account, "credit") == D("450000.00")


def test_expense_lines_without_vat_have_no_vat_line() -> None:
    expense = make_expense(ACC.EXP_SALARY, "2800000.00", "0.00", "bank")
    lines = rules.build_expense_lines(expense)

    assert_balanced(lines)
    assert account_sum(lines, ACC.VAT_INPUT, "debit") == D("0.00")
    assert account_sum(lines, ACC.EXP_SALARY, "debit") == D("2800000.00")
    assert account_sum(lines, ACC.BANK, "credit") == D("2800000.00")


def test_expense_rejects_non_operating_account() -> None:
    """Өртөг (5101) ба зөрүүний данс руу гараар зардал бичихийг хориглоно."""
    for bad in (ACC.COGS_FUEL, ACC.COGS_GOODS, ACC.FUEL_LOSS, ACC.CASH_SHORT, ACC.CASH):
        expense = make_expense(bad, "1000.00", "0.00", "cash")
        with pytest.raises(ValueError):
            rules.build_expense_lines(expense)


def test_expense_zero_amount_posts_nothing() -> None:
    expense = make_expense(ACC.EXP_OTHER, "0.00", "0.00", "cash")
    assert rules.build_expense_lines(expense) == []


def test_every_operating_expense_account_is_seeded() -> None:
    """OPERATING_EXPENSES дахь код бүр COA-д бодитоор байх ёстой."""
    for code in ACC.OPERATING_EXPENSES:
        assert code in COA_BY_CODE, f"COA-д алга: {code}"
        assert COA_BY_CODE[code]["is_postable"] is True


# --------------------------------------------------------------------------- #
# Цалин
# --------------------------------------------------------------------------- #
RATES = {
    "si_employee": D("0.115"),
    "si_employer": D("0.125"),
    "pit": D("0.10"),
    "pit_credit": D("20000"),
    "si_cap": D("0"),
}


def test_payroll_compute_matches_hand_calculation() -> None:
    """1,800,000₮ цалин: НДШ 207,000 → ХХОАТ суурь 1,593,000 → татвар 139,300."""
    from app.services.payroll_service import compute_line

    r = compute_line(
        base_salary=D("1800000"), worked_days=D("30"), month_days=D("30"),
        bonus=D("0"), other_addition=D("0"), advance=D("0"), other_deduction=D("0"),
        rates=RATES,
    )
    assert r["gross"] == D("1800000.00")
    assert r["si_employee"] == D("207000.00")
    assert r["si_employer"] == D("225000.00")
    assert r["taxable"] == D("1593000.00")
    assert r["pit"] == D("139300.00")
    assert r["net"] == D("1453700.00")


def test_payroll_prorates_by_worked_days() -> None:
    from app.services.payroll_service import compute_line

    r = compute_line(
        base_salary=D("1800000"), worked_days=D("15"), month_days=D("30"),
        bonus=D("200000"), other_addition=D("0"), advance=D("300000"), other_deduction=D("0"),
        rates=RATES,
    )
    assert r["earned_salary"] == D("900000.00")
    assert r["gross"] == D("1100000.00")
    # гарт олгох = нийт − НДШ − ХХОАТ − урьдчилгаа
    assert r["net"] == q2(r["gross"] - r["si_employee"] - r["pit"] - D("300000"))


def test_payroll_pit_never_negative() -> None:
    """Бага цалин дээр хөнгөлөлт татвараас их бол ХХОАТ 0 болно (сөрөг биш)."""
    from app.services.payroll_service import compute_line

    r = compute_line(
        base_salary=D("150000"), worked_days=D("30"), month_days=D("30"),
        bonus=D("0"), other_addition=D("0"), advance=D("0"), other_deduction=D("0"),
        rates=RATES,
    )
    assert r["pit"] == D("0.00")


def test_payroll_si_cap_limits_contribution_base() -> None:
    from app.services.payroll_service import compute_line

    capped = dict(RATES, si_cap=D("1000000"))
    r = compute_line(
        base_salary=D("5000000"), worked_days=D("30"), month_days=D("30"),
        bonus=D("0"), other_addition=D("0"), advance=D("0"), other_deduction=D("0"),
        rates=capped,
    )
    assert r["si_employee"] == D("115000.00")   # 1,000,000 × 11.5%
    assert r["si_employer"] == D("125000.00")


def make_period(gross, si_emp, si_empr, pit, net):
    return SimpleNamespace(
        year=2026, month=8,
        gross_total=D(gross), si_employee_total=D(si_emp),
        si_employer_total=D(si_empr), pit_total=D(pit), net_total=D(net),
    )


def test_payroll_entry_balances_without_deductions() -> None:
    period = make_period("6850000.00", "787750.00", "856250.00", "526225.00", "5536025.00")
    lines = rules.build_payroll_lines(period)

    assert_balanced(lines)
    assert account_sum(lines, ACC.EXP_SALARY, "debit") == D("6850000.00")
    assert account_sum(lines, ACC.EXP_SOCIAL_INS, "debit") == D("856250.00")
    assert account_sum(lines, ACC.AP_SALARY, "credit") == D("5536025.00")
    assert account_sum(lines, ACC.AP_PIT, "credit") == D("526225.00")
    assert account_sum(lines, ACC.AP_SOCIAL_INS, "credit") == D("1644000.00")
    assert account_sum(lines, ACC.AR_EMPLOYEE, "credit") == D("0.00")


def test_payroll_entry_balances_with_advance_deduction() -> None:
    """Урьдчилгаа суутгасан үед 1205 авлага хаагдаж, бичилт тэнцэнэ."""
    # net нь 300,000-аар бага — тэр нь урьдчилгаа
    period = make_period("6850000.00", "787750.00", "856250.00", "526225.00", "5236025.00")
    lines = rules.build_payroll_lines(period)

    assert_balanced(lines)
    assert account_sum(lines, ACC.AR_EMPLOYEE, "credit") == D("300000.00")


def test_advance_payment_lines() -> None:
    adv = SimpleNamespace(amount=D("250000.00"), paid_from="cash", memo="Урьдчилгаа")
    lines = rules.build_advance_lines(adv)

    assert_balanced(lines)
    assert account_sum(lines, ACC.AR_EMPLOYEE, "debit") == D("250000.00")
    assert account_sum(lines, ACC.CASH, "credit") == D("250000.00")


@pytest.mark.parametrize(
    ("target", "account"),
    [("salary", ACC.AP_SALARY), ("pit", ACC.AP_PIT), ("social", ACC.AP_SOCIAL_INS)],
)
def test_payroll_payment_debits_the_right_liability(target, account) -> None:
    pay = SimpleNamespace(amount=D("100000.00"), target=target, paid_from="bank", memo="төлөв")
    lines = rules.build_payroll_payment_lines(pay)

    assert_balanced(lines)
    assert account_sum(lines, account, "debit") == D("100000.00")
    assert account_sum(lines, ACC.BANK, "credit") == D("100000.00")


def test_payroll_payment_rejects_unknown_target() -> None:
    pay = SimpleNamespace(amount=D("1000.00"), target="bonus", paid_from="bank")
    with pytest.raises(ValueError):
        rules.build_payroll_payment_lines(pay)


def test_payroll_accounts_are_seeded() -> None:
    for code in (ACC.AP_SALARY, ACC.AP_PIT, ACC.AP_SOCIAL_INS, ACC.AR_EMPLOYEE):
        assert code in COA_BY_CODE, f"COA-д алга: {code}"
        assert COA_BY_CODE[code]["is_postable"] is True


# --------------------------------------------------------------------------- #
# Сарын хоног ба сарын дундуур ажилласан хугацаа
# --------------------------------------------------------------------------- #
def _emp(hire=None, end=None):
    from datetime import date as _date

    return SimpleNamespace(
        hire_date=_date.fromisoformat(hire) if hire else None,
        end_date=_date.fromisoformat(end) if end else None,
    )


@pytest.mark.parametrize(
    ("year", "month", "days"),
    [(2026, 1, 31), (2026, 2, 28), (2024, 2, 29), (2026, 4, 30), (2026, 7, 31)],
)
def test_month_days_follow_the_calendar(year, month, days) -> None:
    """2 сар 28/29, 4 сар 30, 7 сар 31 — календарийн жинхэнэ хоног."""
    from app.services.payroll_service import employment_window

    window = employment_window(_emp(), year, month)
    assert window is not None
    _, _, worked = window
    assert worked == D(str(days))


def test_hired_mid_month_counts_from_hire_date() -> None:
    """7-р сарын 15-нд ажилд орсон → 7-р сард 17 хоног (15–31, хоёр талыг оруулж)."""
    from app.services.payroll_service import employment_window

    start, finish, days = employment_window(_emp(hire="2026-07-15"), 2026, 7)
    assert (start.isoformat(), finish.isoformat()) == ("2026-07-15", "2026-07-31")
    assert days == D("17")


def test_left_mid_month_counts_until_end_date() -> None:
    """8-р сарын 20-нд ажлаас гарсан → 8-р сард 20 хоног (1–20)."""
    from app.services.payroll_service import employment_window

    start, finish, days = employment_window(_emp(end="2026-08-20"), 2026, 8)
    assert (start.isoformat(), finish.isoformat()) == ("2026-08-01", "2026-08-20")
    assert days == D("20")


def test_full_month_between_hire_and_end() -> None:
    """7-15-аас 8-20 хүртэл ажилласан хүн 8-р сард бүтэн биш, 7-р сард ч бүтэн биш."""
    from app.services.payroll_service import employment_window

    emp = _emp(hire="2026-07-15", end="2026-08-20")
    assert employment_window(emp, 2026, 7)[2] == D("17")   # 07-15 … 07-31
    assert employment_window(emp, 2026, 8)[2] == D("20")   # 08-01 … 08-20
    assert employment_window(emp, 2026, 9) is None          # 9-р сард ажиллаагүй
    assert employment_window(emp, 2026, 6) is None          # 6-р сард хараахан ороогүй


def test_salary_is_prorated_by_actual_days() -> None:
    """3,100,000₮ цалин, 31 хоногт 17 хоног ажилласан → 1,700,000₮."""
    from app.services.payroll_service import compute_line

    r = compute_line(
        base_salary=D("3100000"), worked_days=D("17"), month_days=D("31"),
        bonus=D("0"), other_addition=D("0"), advance=D("0"), other_deduction=D("0"),
        rates=RATES,
    )
    assert r["earned_salary"] == D("1700000.00")


def test_february_prorate_uses_28_days() -> None:
    """2-р сард 14 хоног ажилласан → яг хагас цалин (28 хоногийн 14)."""
    from app.services.payroll_service import compute_line

    r = compute_line(
        base_salary=D("2800000"), worked_days=D("14"), month_days=D("28"),
        bonus=D("0"), other_addition=D("0"), advance=D("0"), other_deduction=D("0"),
        rates=RATES,
    )
    assert r["earned_salary"] == D("1400000.00")
