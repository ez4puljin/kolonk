"""И-баримт (ebarimt 3.0) клиент (WP8).

``settings.ebarimt_mode`` -оор хэрэгжилт сонгоно:

* ``stub`` — бодит холболтгүй, борлуулалтын ID-аас гаргасан **тогтвортой**
  (детерминистик) хуурамч баримт буцаана. Тест ба демод ашиглана.
* ``live`` — бодит холболт. Татварын албаны итгэмжлэл шаардлагатай тул энэ
  хувилбарт хэрэгжээгүй.

Клиент нь ORM-ээс хамааралгүй: ``build_ebarimt_payload`` борлуулалтыг
энгийн ``dict`` болгож хувиргана.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from app.config import settings
from app.enums import ItemType, PaymentMethod
from app.money import q2, q3, vat_from_gross

#: И-баримтын сугалааны дугаарт ашиглах тэмдэгтүүд (андуурч уншихаас сэргийлж
#: O, I, 0, 1-г хассан).
LOTTERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

RECEIPT_ID_LENGTH = 20
LOTTERY_LENGTH = 8

TAX_TYPE_VAT_ABLE = "VAT_ABLE"

RECEIPT_TYPE_B2C = "B2C_RECEIPT"
RECEIPT_TYPE_B2B = "B2B_RECEIPT"

#: Төлбөрийн хэрэгсэл → И-баримтын төлбөрийн код.
EBARIMT_PAYMENT_CODES: dict[str, str] = {
    PaymentMethod.CASH: "CASH",
    PaymentMethod.CARD: "PAYMENT_CARD",
    PaymentMethod.QR: "QR",
    PaymentMethod.TRANSFER: "BANK_TRANSFER",
    PaymentMethod.CONTRACT: "BANK_TRANSFER",
}

ZERO = Decimal("0.00")


# --------------------------------------------------------------------------- #
# Протокол
# --------------------------------------------------------------------------- #
@runtime_checkable
class EbarimtClient(Protocol):
    """И-баримтын клиентийн гэрээ."""

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Баримтыг илгээж ``{receipt_id, qr_data, lottery_no, success}`` буцаана."""
        ...


# --------------------------------------------------------------------------- #
# Туслахууд
# --------------------------------------------------------------------------- #
def _get(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _seed_int(seed: str) -> int:
    """Дурын текстээс тогтвортой бүхэл тоо (UUID бол шууд, эсбол SHA-256)."""
    try:
        return uuid.UUID(str(seed)).int
    except (ValueError, AttributeError, TypeError):
        return int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest(), 16)


def build_receipt_id(seed: Any) -> str:
    """Борлуулалтын ID-аас гаргасан 20 оронтой баримтын дугаар."""
    value = _seed_int(str(seed)) % (10**RECEIPT_ID_LENGTH)
    return str(value).zfill(RECEIPT_ID_LENGTH)


def build_lottery_no(seed: Any) -> str:
    """Борлуулалтын ID-аас гаргасан 8 тэмдэгт сугалааны дугаар."""
    value = _seed_int(f"lottery:{seed}")
    base = len(LOTTERY_ALPHABET)
    chars: list[str] = []
    for _ in range(LOTTERY_LENGTH):
        value, index = divmod(value, base)
        chars.append(LOTTERY_ALPHABET[index])
    return "".join(chars)


def _money_str(value: Any) -> str:
    if value is None:
        return "0.00"
    return str(q2(Decimal(str(value))))


def _qty_str(value: Any) -> str:
    if value is None:
        return "0.000"
    return str(q3(Decimal(str(value))))


def _dec(value: Any) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


# --------------------------------------------------------------------------- #
# Payload бүтээгч
# --------------------------------------------------------------------------- #
def build_ebarimt_payload(
    sale: Any,
    items: Iterable[Any],
    settings_dict: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Борлуулалтыг И-баримт 3.0 хэлбэрийн ``dict`` болгоно.

    ``settings_dict`` нь ``settings_service.get_all`` -ийн үр дүн (ШТС-ийн нэр,
    НӨАТ төлөгчийн дугаар, ПОС дугаар г.м.).
    """
    conf: Mapping[str, Any] = settings_dict or {}

    merchant_tin = str(conf.get("vat_payer_no") or conf.get("merchant_tin") or "")
    pos_no = str(conf.get("ebarimt_pos_id") or settings.ebarimt_pos_id or "")
    branch_no = str(conf.get("ebarimt_branch_no") or "001")
    district_code = str(conf.get("ebarimt_district_code") or "")
    customer_tin = str(conf.get("customer_tin") or "")

    receipt_items: list[dict[str, Any]] = []
    items_total = ZERO
    items_vat = ZERO
    for item in items or []:
        amount = q2(_dec(_get(item, "amount")))
        qty = q3(_dec(_get(item, "qty")))
        unit_price = q2(_dec(_get(item, "unit_price")))
        vat = vat_from_gross(amount, settings.vat_rate)
        items_total = q2(items_total + amount)
        items_vat = q2(items_vat + vat)
        is_fuel = str(_get(item, "item_type") or "") == str(ItemType.FUEL)
        receipt_items.append(
            {
                "name": str(_get(item, "name_snapshot") or ""),
                "barCode": str(_get(item, "barcode") or ""),
                "barCodeType": "UNDEFINED",
                "classificationCode": str(conf.get("ebarimt_classification_code") or ""),
                "measureUnit": "л" if is_fuel else str(_get(item, "unit") or "ш"),
                "qty": _qty_str(qty),
                "unitPrice": _money_str(unit_price),
                "totalAmount": _money_str(amount),
                "totalVAT": _money_str(vat),
                "totalCityTax": "0.00",
                "taxType": TAX_TYPE_VAT_ABLE,
            }
        )

    raw_total = _get(sale, "total")
    raw_vat = _get(sale, "vat_amount")
    total_amount = q2(_dec(raw_total)) if raw_total is not None else items_total
    total_vat = q2(_dec(raw_vat)) if raw_vat is not None else items_vat

    payments: list[dict[str, Any]] = []
    for payment in _get(sale, "payments") or []:
        method = str(_get(payment, "method") or PaymentMethod.CASH)
        payments.append(
            {
                "code": EBARIMT_PAYMENT_CODES.get(method, "CASH"),
                "method": method,
                "status": "PAID",
                "paidAmount": _money_str(_get(payment, "amount")),
            }
        )
    if not payments:
        payments.append(
            {
                "code": "CASH",
                "method": str(PaymentMethod.CASH),
                "status": "PAID",
                "paidAmount": _money_str(total_amount),
            }
        )

    completed_at = _get(sale, "completed_at")
    if isinstance(completed_at, datetime):
        completed_text = completed_at.isoformat()
    else:
        completed_text = str(completed_at or "")

    return {
        # --- дотоод холбоос (stub энэ утгаас баримтын дугаар гаргана) ---
        "sale_id": str(_get(sale, "id") or ""),
        "sale_number": _get(sale, "number"),
        "date": completed_text,
        # --- И-баримт 3.0 их бие ---
        "totalAmount": _money_str(total_amount),
        "totalVAT": _money_str(total_vat),
        "totalCityTax": "0.00",
        "branchNo": branch_no,
        "districtCode": district_code,
        "merchantTin": merchant_tin,
        "posNo": pos_no,
        "customerTin": customer_tin,
        "type": RECEIPT_TYPE_B2B if customer_tin else RECEIPT_TYPE_B2C,
        "receipts": [
            {
                "totalAmount": _money_str(total_amount),
                "totalVAT": _money_str(total_vat),
                "totalCityTax": "0.00",
                "taxType": TAX_TYPE_VAT_ABLE,
                "merchantTin": merchant_tin,
                "items": receipt_items,
            }
        ],
        "payments": payments,
    }


# --------------------------------------------------------------------------- #
# Хэрэгжилтүүд
# --------------------------------------------------------------------------- #
class StubEbarimtClient:
    """Бодит холболтгүй, детерминистик хариу буцаадаг клиент."""

    #: Сүлжээний саатлыг дуурайх хугацаа (секунд).
    delay: float = 0.05

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(self.delay)
        seed = str(
            payload.get("sale_id")
            or payload.get("billId")
            or payload.get("id")
            or payload.get("sale_number")
            or ""
        )
        receipt_id = build_receipt_id(seed)
        return {
            "success": True,
            "receipt_id": receipt_id,
            "qr_data": f"https://ebarimt.mn/receipt/{receipt_id}",
            "lottery_no": build_lottery_no(seed),
            "message": "И-баримт амжилттай илгээгдлээ (туршилтын горим)",
        }


def get_ebarimt_client(mode: str | None = None) -> EbarimtClient:
    """``settings.ebarimt_mode`` -оос хамаарсан клиент буцаана."""
    selected = (mode or settings.ebarimt_mode or "stub").strip().lower()
    if selected == "stub":
        return StubEbarimtClient()
    if selected == "live":
        raise NotImplementedError(
            "И-баримтын бодит холболт хэрэгжээгүй байна — татварын албаны "
            "итгэмжлэл (POS дугаар, нууц түлхүүр) шаардлагатай"
        )
    raise NotImplementedError(
        f"И-баримтын '{selected}' горим байхгүй. Зөвшөөрөгдөх утга: stub, live"
    )
