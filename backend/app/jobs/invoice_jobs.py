"""Гэрээт харилцагчийн сарын нэхэмжлэхийн ARQ ажил (WP8).

Сар бүрийн 1-нд 02:00 цагт ажиллаж **өмнөх сарын** гэрээт борлуулалтаар
нэхэмжлэх үүсгэнэ. ``contract_service`` -ийг функц дотор нь оройтуулж
импортлоно — ингэснээр дугуй импорт (worker → jobs → services → routers)
үүсэхгүй.
"""

from __future__ import annotations

import inspect
import logging
from datetime import date, timedelta
from typing import Any

from app.database import async_session_factory
from app.services.report_service import today_local

log = logging.getLogger("kolonk.invoices")

#: Хугацааны параметрийн нэрсийн боломжит хувилбарууд.
START_NAMES = ("period_start", "date_from", "start", "start_date", "from_date")
END_NAMES = ("period_end", "date_to", "end", "end_date", "to_date")


def previous_month(today: date | None = None) -> tuple[date, date]:
    """Өмнөх сарын эхний ба сүүлийн өдөр."""
    anchor = today or today_local()
    first_of_this_month = anchor.replace(day=1)
    period_end = first_of_this_month - timedelta(days=1)
    period_start = period_end.replace(day=1)
    return period_start, period_end


def _build_kwargs(fn: Any, period_start: date, period_end: date) -> dict[str, Any] | None:
    """Функцийн гарын үсгээс хамааруулж нэрлэсэн аргументуудыг барина."""
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):  # pragma: no cover
        return None

    parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]
    if not parameters:
        return None

    kwargs: dict[str, Any] = {}
    for parameter in parameters[1:]:  # эхнийх нь db session
        name = parameter.name
        if name in START_NAMES:
            kwargs[name] = period_start
        elif name in END_NAMES:
            kwargs[name] = period_end
        elif name == "year":
            kwargs[name] = period_start.year
        elif name == "month":
            kwargs[name] = period_start.month
        elif name in ("as_of", "today", "reference_date"):
            kwargs[name] = period_end
        elif parameter.default is inspect.Parameter.empty:
            return None  # танихгүй заавал шаардлагатай параметр — fallback ашиглана
    return kwargs


async def generate_monthly_invoices(ctx: dict[str, Any]) -> dict[str, Any]:
    """Өмнөх сарын гэрээт нэхэмжлэхүүдийг үүсгэнэ."""
    from app.services import contract_service  # noqa: PLC0415 — дугуй импортоос сэргийлж оройтуулав

    generate = getattr(contract_service, "generate_invoices", None)
    if generate is None:  # pragma: no cover — WP6 хараахан бэлэн биш үед
        log.error("contract_service.generate_invoices олдсонгүй — нэхэмжлэх үүсгэсэнгүй")
        return {"status": "unavailable", "created": 0}

    period_start, period_end = previous_month()
    log.info("Сарын нэхэмжлэх үүсгэж байна: %s — %s", period_start, period_end)

    async with async_session_factory() as db:
        kwargs = _build_kwargs(generate, period_start, period_end)
        try:
            if kwargs is not None:
                result = await generate(db, **kwargs)
            else:
                result = await generate(db, period_start, period_end)
        except TypeError:
            log.warning("generate_invoices-ийн гарын үсэг тохирсонгүй — өөр хэлбэрээр дуудаж байна")
            result = await generate(db)
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            log.exception("Сарын нэхэмжлэх үүсгэхэд алдаа гарлаа")
            raise RuntimeError(f"Сарын нэхэмжлэх үүсгэхэд алдаа гарлаа: {exc}") from exc

        await db.commit()

    created = len(result) if isinstance(result, (list, tuple)) else result
    log.info("Сарын нэхэмжлэх дууслаа: %s", created)
    return {
        "status": "ok",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "created": created if isinstance(created, int) else None,
    }
