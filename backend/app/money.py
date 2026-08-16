from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MILLI = Decimal("0.001")
MICRO = Decimal("0.000001")


def q2(value: Decimal | int | str) -> Decimal:
    """Quantize to money precision (2dp, half-up)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def q3(value: Decimal | int | str) -> Decimal:
    """Quantize to liter/qty precision (3dp)."""
    return Decimal(value).quantize(MILLI, rounding=ROUND_HALF_UP)


def q6(value: Decimal | int | str) -> Decimal:
    """Quantize to unit-cost precision (6dp)."""
    return Decimal(value).quantize(MICRO, rounding=ROUND_HALF_UP)


def vat_from_gross(gross: Decimal, rate: Decimal = Decimal("0.10")) -> Decimal:
    """VAT included in a gross price: 10% → gross / 11."""
    return q2(Decimal(gross) * rate / (Decimal(1) + rate))


def net_from_gross(gross: Decimal, rate: Decimal = Decimal("0.10")) -> Decimal:
    return q2(Decimal(gross) - vat_from_gross(gross, rate))


def split_remainder(total: Decimal, parts: list[Decimal]) -> list[Decimal]:
    """Assign any rounding remainder to the last non-zero part so Σparts == total."""
    quantized = [q2(p) for p in parts]
    diff = q2(total) - sum(quantized, Decimal("0"))
    if diff != 0:
        for i in range(len(quantized) - 1, -1, -1):
            if quantized[i] != 0:
                quantized[i] = q2(quantized[i] + diff)
                break
        else:
            if quantized:
                quantized[-1] = q2(quantized[-1] + diff)
    return quantized
