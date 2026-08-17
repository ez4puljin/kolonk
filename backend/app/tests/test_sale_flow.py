"""Борлуулалтын математикийн нэгжийн тест (WP6).

DB, Redis, сүлжээ **огт хэрэглэхгүй** — зөвхөн ``sale_service``-ийн цэвэр
функцууд болон ``contract_service``-ийн зээлийн шалгуурыг шалгана.

Ажиллуулах:  ``pytest app/tests/test_sale_flow.py``
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.enums import ContractStatus, ItemType, PaymentMethod
from app.money import q2
from app.services import contract_service
from app.services.sale_service import (
    compute_change,
    compute_totals,
    credit_available,
    discounted_price,
    fits_credit_limit,
    line_amount,
    liters_match,
    method_label,
    payments_total,
    resolve_sale_type,
    validate_payment_total,
)

D = Decimal


def _contract(*, credit_limit: str, balance: str, status: str = ContractStatus.ACTIVE) -> SimpleNamespace:
    return SimpleNamespace(
        credit_limit=D(credit_limit),
        balance=D(balance),
        status=str(status),
    )


# --------------------------------------------------------------------------- #
# Мөрийн дүн
# --------------------------------------------------------------------------- #
class TestLineAmount:
    def test_liters_times_price(self) -> None:
        # 20 л × 2 940₮ = 58 800₮
        assert line_amount(D("20.000"), D("2940.00")) == D("58800.00")

    def test_rounds_half_up_to_two_places(self) -> None:
        # 12.345 л × 2 940.00 = 36 294.30
        assert line_amount(D("12.345"), D("2940.00")) == D("36294.30")
        # 0.005 нь дээш дугуйлагдана
        assert line_amount(D("1.000"), D("0.005")) == D("0.01")

    def test_zero_qty_gives_zero(self) -> None:
        assert line_amount(D("0"), D("2940.00")) == D("0.00")

    def test_never_returns_float(self) -> None:
        assert isinstance(line_amount(D("1.5"), D("100")), Decimal)


# --------------------------------------------------------------------------- #
# Гэрээний хөнгөлөлт
# --------------------------------------------------------------------------- #
class TestDiscountedPrice:
    def test_discount_applied_per_liter(self) -> None:
        assert discounted_price(D("2940.00"), D("40.00")) == D("2900.00")

    def test_no_discount_keeps_price(self) -> None:
        assert discounted_price(D("2940.00"), D("0")) == D("2940.00")

    def test_never_goes_negative(self) -> None:
        assert discounted_price(D("100.00"), D("500.00")) == D("0.00")


# --------------------------------------------------------------------------- #
# НӨАТ — үнэд шингэсэн (нийт/11)
# --------------------------------------------------------------------------- #
class TestVatExtraction:
    def test_vat_is_extracted_from_gross(self) -> None:
        subtotal, vat, total = compute_totals([D("58800.00")])
        assert total == D("58800.00")
        assert vat == D("5345.45")  # 58800 / 11
        assert subtotal == D("53454.55")

    def test_parts_always_reconstruct_the_total(self) -> None:
        for gross in ("1.00", "0.05", "12345.67", "99999.99", "58800.00", "3.33"):
            subtotal, vat, total = compute_totals([D(gross)])
            assert q2(subtotal + vat) == total, gross

    def test_sums_multiple_lines_before_vat(self) -> None:
        subtotal, vat, total = compute_totals([D("58800.00"), D("4500.00"), D("2500.50")])
        assert total == D("65800.50")
        assert vat == q2(D("65800.50") / D("11"))
        assert subtotal == q2(total - vat)

    def test_empty_sale_is_zero(self) -> None:
        assert compute_totals([]) == (D("0.00"), D("0.00"), D("0.00"))

    def test_custom_rate(self) -> None:
        _subtotal, vat, total = compute_totals([D("100.00")], D("0"))
        assert total == D("100.00")
        assert vat == D("0.00")


# --------------------------------------------------------------------------- #
# Төлбөрийн нийлбэрийн шалгуур
# --------------------------------------------------------------------------- #
class TestPaymentValidation:
    def test_exact_single_payment_passes(self) -> None:
        assert validate_payment_total(D("58800.00"), [D("58800.00")]) == D("58800.00")

    def test_split_payment_passes(self) -> None:
        paid = validate_payment_total(D("58800.00"), [D("30000.00"), D("28800.00")])
        assert paid == D("58800.00")

    def test_three_way_split_passes(self) -> None:
        amounts = [D("20000.00"), D("18800.00"), D("20000.00")]
        assert payments_total(amounts) == D("58800.00")
        validate_payment_total(D("58800.00"), amounts)

    def test_underpayment_is_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_payment_total(D("58800.00"), [D("58799.99")])
        assert exc.value.status_code == 422
        assert exc.value.detail == "Төлбөрийн дүн нийт дүнтэй тохирохгүй байна"

    def test_overpayment_is_rejected(self) -> None:
        # Илүү төлсөн дүн бол "хариулт" — төлбөрийн мөрөнд орж болохгүй.
        with pytest.raises(HTTPException) as exc:
            validate_payment_total(D("58800.00"), [D("60000.00")])
        assert exc.value.status_code == 422

    def test_no_payment_is_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            validate_payment_total(D("58800.00"), [])
        assert exc.value.status_code == 422


# --------------------------------------------------------------------------- #
# Бэлэн мөнгөний хариулт
# --------------------------------------------------------------------------- #
class TestChange:
    def test_change_from_larger_note(self) -> None:
        assert compute_change(D("58800.00"), D("60000.00")) == D("1200.00")

    def test_exact_cash_gives_no_change(self) -> None:
        assert compute_change(D("58800.00"), D("58800.00")) == D("0.00")

    def test_missing_received_gives_no_change(self) -> None:
        assert compute_change(D("58800.00"), None) == D("0.00")

    def test_short_cash_is_rejected(self) -> None:
        with pytest.raises(HTTPException) as exc:
            compute_change(D("58800.00"), D("50000.00"))
        assert exc.value.status_code == 422
        assert "бага" in exc.value.detail


# --------------------------------------------------------------------------- #
# Гэрээний зээлийн лимит
# --------------------------------------------------------------------------- #
class TestCreditLimit:
    def test_available_is_limit_minus_balance(self) -> None:
        assert credit_available(D("1000000.00"), D("250000.00")) == D("750000.00")

    def test_overdrawn_contract_reports_negative(self) -> None:
        assert credit_available(D("100000.00"), D("150000.00")) == D("-50000.00")

    def test_fits_when_below_limit(self) -> None:
        assert fits_credit_limit(D("1000000.00"), D("250000.00"), D("58800.00")) is True

    def test_fits_exactly_at_limit(self) -> None:
        assert fits_credit_limit(D("100000.00"), D("41200.00"), D("58800.00")) is True

    def test_does_not_fit_above_limit(self) -> None:
        assert fits_credit_limit(D("100000.00"), D("41200.01"), D("58800.00")) is False

    def test_assert_credit_passes_within_limit(self) -> None:
        contract = _contract(credit_limit="1000000.00", balance="250000.00")
        contract_service.assert_credit(contract, D("58800.00"))  # алдаа гарах ёсгүй

    def test_assert_credit_rejects_over_limit(self) -> None:
        contract = _contract(credit_limit="100000.00", balance="90000.00")
        with pytest.raises(HTTPException) as exc:
            contract_service.assert_credit(contract, D("58800.00"))
        assert exc.value.status_code == 422
        assert exc.value.detail == "Гэрээний зээлийн лимит хэтэрсэн байна"

    def test_assert_credit_rejects_inactive_contract(self) -> None:
        contract = _contract(credit_limit="1000000.00", balance="0.00", status=ContractStatus.SUSPENDED)
        with pytest.raises(HTTPException) as exc:
            contract_service.assert_credit(contract, D("100.00"))
        assert exc.value.status_code == 422
        assert exc.value.detail == "Гэрээ идэвхгүй байна"

    def test_credit_available_helper_matches_service(self) -> None:
        contract = _contract(credit_limit="500000.00", balance="120000.00")
        assert contract_service.credit_available(contract) == credit_available(
            contract.credit_limit, contract.balance
        )


# --------------------------------------------------------------------------- #
# Насосны заалттай тулгах
# --------------------------------------------------------------------------- #
class TestLitersMatch:
    def test_identical_readings_match(self) -> None:
        assert liters_match(D("20.000"), D("20.000")) is True

    def test_within_tolerance_matches(self) -> None:
        assert liters_match(D("20.000"), D("20.010")) is True

    def test_beyond_tolerance_does_not_match(self) -> None:
        assert liters_match(D("20.000"), D("20.020")) is False
        assert liters_match(D("20.000"), D("19.500")) is False


# --------------------------------------------------------------------------- #
# Борлуулалтын төрөл ба төлбөрийн нэршил
# --------------------------------------------------------------------------- #
class TestClassification:
    def test_fuel_only_sale(self) -> None:
        assert resolve_sale_type([ItemType.FUEL, ItemType.FUEL]) == "fuel"

    def test_store_only_sale(self) -> None:
        assert resolve_sale_type([ItemType.PRODUCT]) == "store"

    def test_mixed_sale(self) -> None:
        assert resolve_sale_type([ItemType.FUEL, ItemType.PRODUCT]) == "mixed"

    def test_payment_labels_are_mongolian(self) -> None:
        assert method_label(PaymentMethod.CASH) == "Бэлэн"
        # Гэрээт борлуулалт бүх дэлгэц, тайланд «Зээл» гэж нэрлэгдэнэ.
        assert method_label(PaymentMethod.CONTRACT) == "Зээл"
        assert method_label(PaymentMethod.TRANSFER) == "Шилжүүлэг"
        assert method_label(PaymentMethod.CARD) == "Карт"


# --------------------------------------------------------------------------- #
# Бүтэн урсгалын математик
# --------------------------------------------------------------------------- #
class TestWholeSaleMath:
    def test_fuel_plus_store_split_tender(self) -> None:
        fuel = line_amount(D("20.000"), D("2940.00"))  # 58 800.00
        water = line_amount(D("2.000"), D("1500.00"))  # 3 000.00
        subtotal, vat, total = compute_totals([fuel, water])

        assert total == D("61800.00")
        assert vat == D("5618.18")
        assert subtotal == D("56181.82")
        assert q2(subtotal + vat) == total

        payments = [D("40000.00"), D("21800.00")]
        validate_payment_total(total, payments)
        assert compute_change(payments[0], D("50000.00")) == D("10000.00")

    def test_contract_sale_uses_discounted_price(self) -> None:
        price = discounted_price(D("2940.00"), D("40.00"))
        amount = line_amount(D("50.000"), price)
        _subtotal, _vat, total = compute_totals([amount])
        assert total == D("145000.00")

        contract = _contract(credit_limit="200000.00", balance="60000.00")
        with pytest.raises(HTTPException):
            contract_service.assert_credit(contract, total)

        contract.credit_limit = D("500000.00")
        contract_service.assert_credit(contract, total)
        validate_payment_total(total, [total])
