"""Нөөцлөлтийн ARQ ажлууд (WP8).

``run_backup`` шөнө бүр 03:00 цагт cron-оор ажиллана (``app.worker``).
``run_restore`` нь зөвхөн гараар дуудагдана.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services import backup_service

log = logging.getLogger("kolonk.backup")

#: ARQ-ийн job_timeout (300 сек) дотор багтахаар бага зэрэг богино хугацаа.
JOB_TIMEOUT = 280.0


async def run_backup(ctx: dict[str, Any]) -> dict[str, Any]:
    """Өгөгдлийн сангийн бүтэн нөөцлөлт үүсгэнэ."""
    try:
        filename = await backup_service.create_backup(timeout=JOB_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — ARQ дахин оролдоно
        log.exception("Нөөцлөлт амжилтгүй боллоо")
        raise RuntimeError(f"Нөөцлөлт амжилтгүй боллоо: {exc}") from exc

    info = backup_service.backup_info(filename)
    log.info("Нөөцлөлт үүслээ: %s (%s МБ)", filename, info["size_mb"])
    return {"filename": filename, "size_mb": info["size_mb"]}


async def run_restore(ctx: dict[str, Any], filename: str) -> dict[str, Any]:
    """Заасан нөөцлөлтөөс өгөгдлийн санг сэргээнэ."""
    try:
        restored = await backup_service.restore_backup(filename, timeout=JOB_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        log.exception("Сэргээлт амжилтгүй боллоо: %s", filename)
        raise RuntimeError(f"Сэргээлт амжилтгүй боллоо: {exc}") from exc

    log.info("Өгөгдлийн сан сэргээгдлээ: %s", restored)
    return {"filename": restored, "status": "restored"}
