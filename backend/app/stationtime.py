"""ШТС-ийн орон нутгийн цагийн бүстэй ажиллах нэгдсэн туслахууд.

Бүх `timestamptz` баганыг UTC-ээр хадгалдаг ч хэрэглэгчийн сонгодог **огноо**
нь орон нутгийн огноо байдаг. Улаанбаатар UTC+8 тул орон нутгийн 08-06-ны
06:51 нь UTC-ээр 08-05 22:51 болно — огнооны шүүлтийг UTC-ээр хийвэл өглөөний
борлуулалт "өнөөдөр"-ийн жагсаалтад ОРОХГҮЙ.

Тиймээс огноо → хугацааны муж хөрвүүлэлтийг зөвхөн эндээс хийнэ.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def _zone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(settings.tz)
    except Exception:  # noqa: BLE001 — tzdata суулгаагүй орчинд
        return timezone(timedelta(hours=8))


#: Станцын цагийн бүс (тохиргооны `TZ`).
STATION_TZ = _zone()


def today_local() -> date:
    """Станцын орон нутгийн өнөөдрийн огноо."""
    return datetime.now(STATION_TZ).date()


def now_local() -> datetime:
    return datetime.now(STATION_TZ)


def day_start(day: date) -> datetime:
    """Орон нутгийн тухайн өдрийн 00:00:00 (timezone-той)."""
    return datetime.combine(day, time.min, tzinfo=STATION_TZ)


def day_end(day: date) -> datetime:
    """Орон нутгийн тухайн өдрийн 23:59:59.999999 (timezone-той)."""
    return datetime.combine(day, time.max, tzinfo=STATION_TZ)


def next_day_start(day: date) -> datetime:
    """Орон нутгийн дараагийн өдрийн эхлэл — хагас нээлттэй мужид тохиромжтой."""
    return day_start(day + timedelta(days=1))


def range_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Орон нутгийн огнооны мужийг [эхлэл, төгсгөл] хязгаар болгоно."""
    return day_start(date_from), day_end(date_to)
