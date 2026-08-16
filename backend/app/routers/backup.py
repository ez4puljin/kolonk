"""Дата backup-ийн API — жагсаалт, үүсгэх, сэргээх, татах, устгах, хавтас (WP8)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine, get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.report import (
    BackupCreatedOut,
    BackupDirIn,
    BackupDirOut,
    BackupFileOut,
    BackupListOut,
    DeleteResultOut,
    RestoreConfirmIn,
    RestoreResultOut,
)
from app.services import backup_service, settings_service
from app.services.audit_service import audit

log = logging.getLogger("kolonk.backup")

router = APIRouter(prefix="/api", tags=["backup"])

CanManage = Depends(require_permission("backup.manage"))

#: Сэргээх үйлдлийг баталгаажуулах үг.
RESTORE_CONFIRM_WORD = "СЭРГЭЭХ"

DUMP_MEDIA_TYPE = "application/octet-stream"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _configured_dir(db: AsyncSession) -> str:
    """Тохиргоонд заасан хавтас (хоосон бол .env-ийн анхдагч)."""
    raw = await settings_service.get_setting(db, "backup_dir")
    return str(raw or "").strip()


# --------------------------------------------------------------------------- #
# Хадгалах хавтас
# --------------------------------------------------------------------------- #
@router.get("/backups/directory", response_model=BackupDirOut)
async def get_backup_directory(
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> BackupDirOut:
    configured = await _configured_dir(db)
    info = backup_service.check_directory(configured)
    return BackupDirOut(**info, is_default=configured == "")


@router.put("/backups/directory", response_model=BackupDirOut)
async def set_backup_directory(
    payload: BackupDirIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> BackupDirOut:
    """Хавтсыг солино. Бичих эрхтэй эсэхийг шалгаж байж хадгална."""
    wanted = (payload.directory or "").strip()
    info = backup_service.check_directory(wanted)

    old, _ = await settings_service.set_setting(db, "backup_dir", wanted)
    await audit(
        db,
        user_id=user.id,
        action="backup.set_directory",
        entity_type="setting",
        before={"backup_dir": old},
        after={"backup_dir": wanted, "resolved": info["directory"]},
        ip=_client_ip(request),
    )
    return BackupDirOut(**info, is_default=wanted == "")


@router.get("/backups", response_model=BackupListOut)
async def list_backups(
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> BackupListOut:
    items = backup_service.list_backups(await _configured_dir(db))
    return BackupListOut(
        items=[BackupFileOut(**item) for item in items],
        total=len(items),
    )


@router.post("/backups", response_model=BackupCreatedOut, status_code=201)
async def create_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> BackupCreatedOut:
    directory = await _configured_dir(db)
    filename = await backup_service.create_backup(directory=directory)
    info = backup_service.backup_info(filename, directory)

    await audit(
        db,
        user_id=user.id,
        action="backup.create",
        entity_type="backup",
        after={"filename": filename, "size_mb": info["size_mb"]},
        ip=_client_ip(request),
    )
    return BackupCreatedOut(**info, message="Нөөцлөлт амжилттай үүслээ")


@router.get("/backups/{filename}/download")
async def download_backup(
    filename: str,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> FileResponse:
    path = backup_service.resolve_backup(filename, await _configured_dir(db))
    return FileResponse(path=str(path), filename=path.name, media_type=DUMP_MEDIA_TYPE)


@router.post("/backups/{filename}/restore", response_model=RestoreResultOut)
async def restore_backup(
    filename: str,
    payload: RestoreConfirmIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> RestoreResultOut:
    """Сэргээх нь бүх өгөгдлийг дарж бичнэ — ``{"confirm": "СЭРГЭЭХ"}`` шаардана."""
    if (payload.confirm or "").strip().upper() != RESTORE_CONFIRM_WORD:
        raise HTTPException(
            status_code=422,
            detail=f"Сэргээхийг баталгаажуулахын тулд '{RESTORE_CONFIRM_WORD}' гэж бичнэ үү",
        )

    directory = await _configured_dir(db)
    path = backup_service.resolve_backup(filename, directory)
    log.warning("Өгөгдлийн сан сэргээж байна: %s (хэрэглэгч %s)", path.name, user.username)

    # pg_restore --clean нь хүснэгтүүдийг DROP хийх тул хүсэлтийн гүйлгээ
    # хаагдаагүй бол түгжээ мөргөлдөнө. Тиймээс эхлээд гүйлгээг сулласны дараа
    # сэргээж, дараа нь ШИНЭ session-д аудитаа бичнэ (хуучин session-ий
    # холболтын кэш хүчингүй болно).
    await db.rollback()

    restored = await backup_service.restore_backup(path.name, directory=directory)
    await engine.dispose()

    async with async_session_factory() as fresh:
        await audit(
            fresh,
            user_id=user.id,
            action="backup.restore",
            entity_type="backup",
            after={"filename": restored},
            ip=_client_ip(request),
        )
        await fresh.commit()

    return RestoreResultOut(
        filename=restored,
        message="Өгөгдлийн сан амжилттай сэргээгдлээ. Системд дахин нэвтэрнэ үү",
    )


@router.delete("/backups/{filename}", response_model=DeleteResultOut)
async def delete_backup(
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> DeleteResultOut:
    directory = await _configured_dir(db)
    info = backup_service.backup_info(filename, directory)
    removed = backup_service.delete_backup(filename, directory)

    await audit(
        db,
        user_id=user.id,
        action="backup.delete",
        entity_type="backup",
        before={"filename": removed, "size_mb": info["size_mb"]},
        ip=_client_ip(request),
    )
    return DeleteResultOut(filename=removed, message="Нөөцлөлтийн файл устгагдлаа")
