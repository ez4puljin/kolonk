"""ARQ ажилчин (worker) тохиргоо — WP8.

Ажиллуулах:

.. code-block:: shell

    arq app.worker.WorkerSettings

Cron:

* шөнө бүр **03:00** — өгөгдлийн сангийн нөөцлөлт,
* сар бүрийн **1-ний 02:00** — өмнөх сарын гэрээт нэхэмжлэх.

Дараалалын ажил амжилтгүй болвол ARQ ``max_tries`` (5) удаа дахин оролдоно.
"""

from __future__ import annotations

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.jobs.backup_jobs import run_backup, run_restore
from app.jobs.ebarimt_jobs import submit_ebarimt
from app.jobs.invoice_jobs import generate_monthly_invoices
from app.jobs.price_jobs import apply_due_price_changes

log = logging.getLogger("kolonk.worker")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def redis_settings() -> RedisSettings:
    """``settings.redis_url`` -аас ARQ-ийн Redis тохиргоо."""
    return RedisSettings.from_dsn(settings.redis_url)


async def startup(ctx: dict[str, Any]) -> None:
    log.info("Колонк ажилчин асаалаа (%s)", settings.station_name)


async def shutdown(ctx: dict[str, Any]) -> None:
    from app.database import engine  # noqa: PLC0415 — унтраахдаа л хэрэгтэй

    await engine.dispose()
    log.info("Колонк ажилчин унтарлаа")


class WorkerSettings:
    """ARQ-ийн тохиргоо (``arq app.worker.WorkerSettings``)."""

    functions = [
        submit_ebarimt,
        run_backup,
        run_restore,
        generate_monthly_invoices,
        apply_due_price_changes,
    ]

    cron_jobs = [
        # Шөнө бүр 03:00 — бүтэн нөөцлөлт.
        cron(run_backup, hour=3, minute=0, run_at_startup=False),
        # Сар бүрийн 1-ний 02:00 — өмнөх сарын нэхэмжлэх.
        cron(generate_monthly_invoices, day=1, hour=2, minute=0, run_at_startup=False),
        # Өдөр бүр 16:05 UTC = станцын 00:05 — хугацаа болсон үнийн
        # өөрчлөлтийг хэрэгжүүлнэ («маргаашнаас» гэсэн нь шөнө дунд эхэлнэ).
        # Асаалттай үед мөн нэг удаа ажиллана — worker унтарч байсан ч
        # хоцорсон өөрчлөлт нөхөн хэрэгжинэ.
        cron(apply_due_price_changes, hour=16, minute=5, run_at_startup=True),
    ]

    redis_settings = redis_settings()

    max_tries = 5
    job_timeout = 300
    keep_result = 3600
    max_jobs = 10
    retry_jobs = True

    on_startup = startup
    on_shutdown = shutdown
