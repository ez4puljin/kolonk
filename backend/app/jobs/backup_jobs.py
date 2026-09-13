"""Нөөцлөлтийн ARQ ажлууд (WP8).

* ``run_hourly_backup`` — цаг тутам :05: ``kolonk-latest.dump``-ыг дарж бичээд
  Google Drive тохируулсан бол тийш байршуулна (Drive дээр ч ганц файл).
* ``run_backup`` — шөнө бүр 03:00: огноотой ``kolonk_YYYYMMDD_HHMMSS.dump``,
  дараа нь ``backup_keep_days``-ээс хуучныг устгана.
* ``run_restore`` — зөвхөн гараар дуудагдана.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.database import async_session_factory
from app.services import backup_service, gdrive_service, settings_service

log = logging.getLogger("kolonk.backup")

#: ARQ-ийн job_timeout (300 сек) дотор багтахаар бага зэрэг богино хугацаа.
JOB_TIMEOUT = 280.0


async def _configured_dir() -> tuple[str, int]:
    async with async_session_factory() as db:
        directory = str(await settings_service.get_setting(db, "backup_dir") or "").strip()
        raw_days = await settings_service.get_setting(db, "backup_keep_days")
        try:
            keep_days = int(raw_days if raw_days not in (None, "") else 14)
        except (TypeError, ValueError):
            keep_days = 14
    return directory, keep_days


async def run_backup(ctx: dict[str, Any]) -> dict[str, Any]:
    """Өгөгдлийн сангийн огноотой бүтэн нөөцлөлт үүсгэж, хуучныг цэвэрлэнэ."""
    directory, keep_days = await _configured_dir()
    try:
        filename = await backup_service.create_backup(directory=directory, timeout=JOB_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — ARQ дахин оролдоно
        log.exception("Нөөцлөлт амжилтгүй боллоо")
        raise RuntimeError(f"Нөөцлөлт амжилтгүй боллоо: {exc}") from exc

    info = backup_service.backup_info(filename, directory)
    removed = backup_service.prune_dated_backups(keep_days, directory)
    log.info("Нөөцлөлт үүслээ: %s (%s МБ); хуучин %d файл устгав", filename, info["size_mb"], len(removed))
    return {"filename": filename, "size_mb": info["size_mb"], "pruned": removed}


async def hourly_backup_and_upload(*, force_upload: bool = False) -> dict[str, Any]:
    """``kolonk-latest.dump``-ыг дарж бичээд Google Drive руу байршуулна.

    Router («Одоо байршуулах») ба cron хоёулаа үүнийг дууддаг. Drive-ын алдаа
    нөөцлөлтийг унагахгүй — төлөвийг тохиргоонд бичээд буцаана.
    """
    directory, _ = await _configured_dir()
    filename = await backup_service.create_backup(
        directory=directory, timeout=JOB_TIMEOUT, filename=backup_service.LATEST_NAME
    )
    info = backup_service.backup_info(filename, directory)
    result: dict[str, Any] = {"filename": filename, "size_mb": info["size_mb"], "uploaded": False, "error": None}

    async with async_session_factory() as db:
        config = await gdrive_service.load_config(db)
        if not config.configured or not (config.enabled or force_upload):
            return result
        path = backup_service.resolve_backup(filename, directory)
        try:
            remote = await gdrive_service.upload(config, path, force=force_upload)
            await gdrive_service.record_result(db, error=None)
            result.update(uploaded=True, remote=remote)
            log.info("Google Drive руу байршууллаа: %s (%s байт)", remote["name"], remote["size_bytes"])
        except HTTPException as exc:
            await gdrive_service.record_result(db, error=str(exc.detail))
            result["error"] = str(exc.detail)
            log.warning("Google Drive байршуулалт амжилтгүй: %s", exc.detail)
        except Exception as exc:  # noqa: BLE001
            await gdrive_service.record_result(db, error=str(exc))
            result["error"] = str(exc)
            log.exception("Google Drive байршуулалт амжилтгүй")
        await db.commit()
    return result


async def run_hourly_backup(ctx: dict[str, Any]) -> dict[str, Any]:
    """Цаг тутмын ажил — latest dump + Drive."""
    try:
        return await hourly_backup_and_upload()
    except Exception as exc:  # noqa: BLE001
        log.exception("Цаг тутмын нөөцлөлт амжилтгүй боллоо")
        raise RuntimeError(f"Цаг тутмын нөөцлөлт амжилтгүй боллоо: {exc}") from exc


async def run_restore(ctx: dict[str, Any], filename: str) -> dict[str, Any]:
    """Заасан нөөцлөлтөөс өгөгдлийн санг сэргээнэ."""
    try:
        restored = await backup_service.restore_backup(filename, timeout=JOB_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        log.exception("Сэргээлт амжилтгүй боллоо: %s", filename)
        raise RuntimeError(f"Сэргээлт амжилтгүй боллоо: {exc}") from exc

    log.info("Өгөгдлийн сан сэргээгдлээ: %s", restored)
    return {"filename": restored, "status": "restored"}
