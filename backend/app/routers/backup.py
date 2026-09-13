"""Дата backup-ийн API — жагсаалт, үүсгэх, сэргээх, татах, устгах, хавтас (WP8)."""

from __future__ import annotations

import logging
from datetime import datetime

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
    GdriveConfigIn,
    GdriveDownloadOut,
    GdriveRemoteFileOut,
    GdriveStatusOut,
    GdriveUploadOut,
    RestoreConfirmIn,
    RestoreResultOut,
    UploadsArchiveOut,
    UploadsRestoreOut,
)
from app.jobs.backup_jobs import hourly_backup_and_upload
from app.services import backup_service, gdrive_service, settings_service
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


# --------------------------------------------------------------------------- #
# Google Drive
# --------------------------------------------------------------------------- #
def _parse_dt(raw: object) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _remote_out(remote: dict | None) -> GdriveRemoteFileOut | None:
    if not remote:
        return None
    return GdriveRemoteFileOut(
        name=remote["name"], size_bytes=remote["size_bytes"], modified_at=_parse_dt(remote.get("modified_at"))
    )


async def _gdrive_status(db: AsyncSession, *, probe: bool) -> GdriveStatusOut:
    config = await gdrive_service.load_config(db)
    out = GdriveStatusOut(
        **gdrive_service.masked_status(config),
        last_upload_at=_parse_dt(await settings_service.get_setting(db, "gdrive_last_upload_at")),
        last_error=str(await settings_service.get_setting(db, "gdrive_last_error") or "") or None,
    )
    if probe and config.configured:
        try:
            info = await gdrive_service.check(config)
            out.folder_name = info.get("folder_name")
            out.remote = _remote_out(info.get("remote"))
            out.remote_uploads = _remote_out(info.get("remote_uploads"))
        except HTTPException as exc:
            out.check_error = str(exc.detail)
    return out


@router.get("/backups/gdrive", response_model=GdriveStatusOut)
async def get_gdrive_status(
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> GdriveStatusOut:
    """Тохиргоо + Drive дээрх файлын төлөв (холбогдож шалгана)."""
    return await _gdrive_status(db, probe=True)


@router.put("/backups/gdrive", response_model=GdriveStatusOut)
async def set_gdrive_config(
    payload: GdriveConfigIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> GdriveStatusOut:
    """Түлхүүр, хавтсыг хадгална — өмнө нь Drive-д хүрч чадахыг шалгана."""
    current = await gdrive_service.load_config(db)
    service_account = current.service_account
    if payload.service_account_json is not None:
        service_account = payload.service_account_json.strip()
        if service_account:
            gdrive_service.validate_service_account(service_account)
    folder_id = payload.folder_id.strip()

    config = gdrive_service.GdriveConfig(service_account, folder_id, payload.enabled)
    if config.configured:
        await gdrive_service.check(config)  # 422 — хавтас олдохгүй/эрхгүй бол
    elif payload.enabled:
        raise HTTPException(
            status_code=422, detail="Автомат байршуулалт асаахын тулд түлхүүр, хавтас хоёулаа хэрэгтэй"
        )

    await settings_service.set_setting(db, "gdrive_service_account", service_account)
    await settings_service.set_setting(db, "gdrive_folder_id", folder_id)
    await settings_service.set_setting(db, "gdrive_enabled", bool(payload.enabled))
    await settings_service.set_setting(db, "gdrive_last_error", "")
    await audit(
        db,
        user_id=user.id,
        action="backup.gdrive_config",
        entity_type="setting",
        before={"folder_id": current.folder_id, "enabled": current.enabled, "client_email": current.client_email},
        after={"folder_id": folder_id, "enabled": payload.enabled, "client_email": config.client_email},
        ip=_client_ip(request),
    )
    return await _gdrive_status(db, probe=True)


@router.post("/backups/gdrive/upload", response_model=GdriveUploadOut)
async def gdrive_upload_now(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> GdriveUploadOut:
    """Одоо kolonk-latest.dump үүсгээд Drive руу дарж бичнэ (гар үйлдэл — хэмжээний хамгаалалтгүй)."""
    config = await gdrive_service.load_config(db)
    if not config.configured:
        raise HTTPException(status_code=422, detail="Google Drive тохируулаагүй байна")
    result = await hourly_backup_and_upload(force_upload=True)
    await audit(
        db,
        user_id=user.id,
        action="backup.gdrive_upload",
        entity_type="backup",
        after={"filename": result["filename"], "uploaded": result["uploaded"], "error": result["error"]},
        ip=_client_ip(request),
    )
    if result["error"]:
        raise HTTPException(status_code=422, detail=result["error"])
    return GdriveUploadOut(
        filename=result["filename"],
        size_mb=result["size_mb"],
        uploaded=True,
        remote=_remote_out(result.get("remote")),
        remote_uploads=_remote_out(result.get("remote_uploads")),
        message="Google Drive руу байршууллаа",
    )


@router.post("/backups/gdrive/download", response_model=GdriveDownloadOut)
async def gdrive_download_latest(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> GdriveDownloadOut:
    """Drive дээрх kolonk-latest.dump (+ kolonk-uploads.zip байвал)-ыг локал хавтас руу татна.

    Дараа нь жагсаалтаас «Сэргээх», зургийг «Зургуудыг сэргээх» товчоор.
    """
    config = await gdrive_service.load_config(db)
    directory = await _configured_dir(db)
    root = backup_service.backup_dir(directory)
    await gdrive_service.download(config, root / backup_service.LATEST_NAME)
    info = backup_service.backup_info(backup_service.LATEST_NAME, directory)
    uploads = await gdrive_service.download(
        config, root / backup_service.UPLOADS_ARCHIVE, name=gdrive_service.REMOTE_UPLOADS_NAME, optional=True
    )
    uploads_info = backup_service.uploads_archive_info(directory) if uploads else None
    await audit(
        db,
        user_id=user.id,
        action="backup.gdrive_download",
        entity_type="backup",
        after={"filename": info["filename"], "size_mb": info["size_mb"], "uploads": bool(uploads_info)},
        ip=_client_ip(request),
    )
    return GdriveDownloadOut(
        dump=BackupFileOut(**info),
        uploads=BackupFileOut(**uploads_info) if uploads_info else None,
        message="Drive-аас татлаа — жагсаалтаас сэргээнэ үү",
    )


# --------------------------------------------------------------------------- #
# Хавсралтын архив (ээлжийн зураг)
# --------------------------------------------------------------------------- #
@router.get("/backups/uploads", response_model=UploadsArchiveOut)
async def get_uploads_archive(
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> UploadsArchiveOut:
    directory = await _configured_dir(db)
    info = backup_service.uploads_archive_info(directory)
    _fp, count = backup_service.uploads_fingerprint()
    if info is None:
        return UploadsArchiveOut(exists=False, files=count)
    return UploadsArchiveOut(
        filename=info["filename"], exists=True, size_bytes=info["size_bytes"], created_at=info["created_at"], files=count
    )


@router.post("/backups/uploads/extract", response_model=UploadsRestoreOut)
async def restore_uploads(
    payload: RestoreConfirmIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> UploadsRestoreOut:
    """kolonk-uploads.zip → uploads/ (байгаа файл дарагдана, бусад нь үлдэнэ).

    Зам нь ``/backups/{filename}/restore``-той мөргөлдөхгүйн тулд «extract».
    """
    if (payload.confirm or "").strip().upper() != RESTORE_CONFIRM_WORD:
        raise HTTPException(
            status_code=422,
            detail=f"Сэргээхийг баталгаажуулахын тулд '{RESTORE_CONFIRM_WORD}' гэж бичнэ үү",
        )
    directory = await _configured_dir(db)
    count = await backup_service.restore_uploads_archive(directory)
    await audit(
        db,
        user_id=user.id,
        action="backup.uploads_restore",
        entity_type="backup",
        after={"files": count},
        ip=_client_ip(request),
    )
    return UploadsRestoreOut(files=count, message=f"{count} файл сэргэлээ")
