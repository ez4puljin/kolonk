"""Системийн тохиргооны үйлчилгээ.

Тохиргоо нь `settings` хүснэгтэд `key` → JSONB `value` хэлбэрээр хадгалагдана.
JSONB багана нь dict төрөлтэй тул утгыг `{"value": <утга>}` хэлбэрээр боож
хадгалаад унших үедээ задална. Гуравдагч кодоос шууд бичсэн энгийн утгыг
мөн зөв уншина (`_unwrap` хоёр хэлбэрийг хоёуланг нь дэмжинэ).

ЧУХАЛ: энэ модуль хэзээ ч `db.commit()` дуудахгүй — `get_db` нэг л commit хийнэ.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.models.system import Setting

# ---------------------------------------------------------------------------
# Анхдагч утгууд
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: dict[str, Any] = {
    "station_name": app_settings.station_name,
    "station_address": "",
    "station_phone": "",
    "vat_payer_no": "",
    "vat_rate": str(app_settings.vat_rate),
    "receipt_footer": "Та бүхэнд баярлалаа. Дахин уулзая!",
    "printer_width_mm": 80,
    "ebarimt_enabled": True,
    "ebarimt_pos_id": app_settings.ebarimt_pos_id,
    "auto_print_receipt": True,
    "currency_symbol": "₮",
    # --- Ээлж ---
    # Механик тоолуургүй станцад үүнийг унтраавал ээлж зөвхөн бэлэн мөнгө,
    # савны хэмжилтээр нээгдэж хаагдана.
    "shift_totalizer_enabled": True,
    # ПОС борлуулалт (Талбай/Дэлгүүр/Төлбөр) ашиглах эсэх. Унтраавал түгээгч
    # ээлжээ бэлэн мөнгө + милийн зурагтай нээж, орой өдрийн хаалтаар бүх
    # борлуулалт, зээл, зарлагаа нэг дор бүртгэнэ.
    "pos_sales_enabled": True,
    # --- Дата backup ---
    # Хоосон бол .env-ийн BACKUP_DIR ашиглагдана.
    "backup_dir": "",
    # --- Цалингийн тооцоо ---
    # Хувь хэмжээг НЯГТЛАНТАЙГАА тулгаж баталгаажуулна уу. Хууль өөрчлөгдвөл
    # энэ тохиргоог солиход л хангалттай — код өөрчлөх шаардлагагүй.
    "payroll_si_employee_rate": "0.115",
    "payroll_si_employer_rate": "0.125",
    "payroll_pit_rate": "0.10",
    "payroll_pit_credit": "20000",
    "payroll_si_base_cap": "0",
}

SETTING_DESCRIPTIONS: dict[str, str] = {
    "station_name": "ШТС-ийн нэр",
    "station_address": "ШТС-ийн хаяг",
    "station_phone": "Холбоо барих утас",
    "vat_payer_no": "НӨАТ төлөгчийн дугаар",
    "vat_rate": "НӨАТ-ын хувь (0.10 = 10%)",
    "receipt_footer": "Баримтын хөлийн текст",
    "printer_width_mm": "Принтерийн цаасны өргөн (мм)",
    "ebarimt_enabled": "И-баримт илгээх эсэх",
    "ebarimt_pos_id": "И-баримтын ПОС дугаар",
    "auto_print_receipt": "Баримтыг автоматаар хэвлэх",
    "currency_symbol": "Мөнгөн тэмдэгт",
    "shift_totalizer_enabled": "Ээлжид тоолуурын заалт бүртгэх эсэх",
    "pos_sales_enabled": "ПОС борлуулалт ашиглах эсэх (унтраавал түгээгчийн өдрийн горим)",
    "backup_dir": "Нөөцлөлт хадгалах хавтас",
    "payroll_si_employee_rate": "НДШ — ажилтны хувь (0.115 = 11.5%)",
    "payroll_si_employer_rate": "НДШ — ажил олгогчийн хувь (0.125 = 12.5%)",
    "payroll_pit_rate": "ХХОАТ-ын хувь (0.10 = 10%)",
    "payroll_pit_credit": "ХХОАТ-ын сарын хөнгөлөлт (₮)",
    "payroll_si_base_cap": "НДШ бодох дээд хязгаар (0 = хязгааргүй)",
}


# ---------------------------------------------------------------------------
# Дотоод туслахууд
# ---------------------------------------------------------------------------


def _wrap(value: Any) -> dict[str, Any]:
    return {"value": value}


def _unwrap(stored: Any) -> Any:
    if isinstance(stored, dict) and set(stored.keys()) == {"value"}:
        return stored["value"]
    return stored


# ---------------------------------------------------------------------------
# Нийтийн API
# ---------------------------------------------------------------------------


async def ensure_settings(db: AsyncSession) -> None:
    """Дутуу байгаа анхдагч тохиргоог нэмнэ. Идемпотент — байгаа утгыг дарж бичихгүй."""
    existing = set(await db.scalars(select(Setting.key)))
    missing = [key for key in DEFAULT_SETTINGS if key not in existing]
    if not missing:
        return
    rows = [
        {
            "key": key,
            "value": _wrap(DEFAULT_SETTINGS[key]),
            "description": SETTING_DESCRIPTIONS.get(key),
        }
        for key in missing
    ]
    stmt = pg_insert(Setting).values(rows).on_conflict_do_nothing(index_elements=["key"])
    await db.execute(stmt)


async def get_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Нэг тохиргооны утгыг буцаана. Байхгүй бол `default`, тэр нь өгөгдөөгүй бол
    анхдагч утга (DEFAULT_SETTINGS)-ыг буцаана."""
    row = await db.scalar(select(Setting).where(Setting.key == key))
    if row is not None:
        return _unwrap(row.value)
    if default is not None:
        return default
    return DEFAULT_SETTINGS.get(key)


async def get_all(db: AsyncSession) -> dict[str, Any]:
    """Бүх тохиргоог `{key: value}` толь болгон буцаана (анхдагч утгууд дээр давхарлана)."""
    result: dict[str, Any] = dict(DEFAULT_SETTINGS)
    rows = await db.scalars(select(Setting))
    for row in rows:
        result[row.key] = _unwrap(row.value)
    return result


async def set_setting(
    db: AsyncSession,
    key: str,
    value: Any,
    *,
    description: str | None = None,
) -> tuple[Any, Setting]:
    """Тохиргоог шинэчилнэ (байхгүй бол үүсгэнэ). `(хуучин утга, мөр)` буцаана."""
    row = await db.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        old_value = DEFAULT_SETTINGS.get(key)
        row = Setting(
            key=key,
            value=_wrap(value),
            description=description or SETTING_DESCRIPTIONS.get(key),
        )
        db.add(row)
        await db.flush()
    else:
        old_value = _unwrap(row.value)
        row.value = _wrap(value)
        if description is not None:
            row.description = description
        await db.flush()
    return old_value, row


async def get_bool(db: AsyncSession, key: str) -> bool:
    """Тохиргоог boolean болгож уншина.

    Утга нь JSONB-д ``true`` байж болох ч тохиргооны дэлгэцээс ``"true"`` /
    ``"1"`` гэсэн мөр хэлбэрээр ирж болзошгүй тул хоёуланг нь зөв тайлбарлана.
    """
    raw = await get_setting(db, key)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "1", "yes", "on", "тийм")
    if isinstance(raw, (int, float)):
        return bool(raw)
    return bool(DEFAULT_SETTINGS.get(key, False))
