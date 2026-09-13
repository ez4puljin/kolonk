"""Google Drive руу нөөцлөлт байршуулах / татах (service account).

Тохиргоо ``settings`` хүснэгтэд (Админ панел → Дата backup → Google Drive):

* ``gdrive_service_account`` — Google Cloud service account-ын түлхүүр (JSON текст).
* ``gdrive_folder_id`` — Drive дээрх хавтасны ID (хавтсыг service account-ын
  и-мэйлтэй «Editor» эрхээр хуваалцсан байх ёстой).
* ``gdrive_enabled`` — цаг тутмын автомат байршуулалт асаалттай эсэх.
* ``gdrive_last_upload_at`` / ``gdrive_last_error`` — сүүлийн байршуулалтын төлөв.

Drive дээр ҮРГЭЛЖ ганц файл (``kolonk-latest.dump``) байна — байгаа файлыг
дарж (``files.update``) бичдэг тул хогийн сав, зай дүүрэхгүй.

Google-ийн номын сангууд синхрон тул бүх дуудлагыг ``asyncio.to_thread``-ээр
хийнэ (Windows дээр uvicorn-ы SelectorEventLoop дэд процесс дэмждэггүйтэй
адил шалтгаанаар thread аюулгүй).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import settings_service

log = logging.getLogger("kolonk.gdrive")

#: Drive дээрх ганц нөөцлөлтийн файлын нэр (локал ``backup_service.LATEST_NAME``-тэй ижил).
REMOTE_NAME = "kolonk-latest.dump"

SCOPES = ["https://www.googleapis.com/auth/drive"]
CHUNK = 8 * 1024 * 1024
MB = 1024 * 1024

#: Автомат байршуулалтын хамгаалалт: локал dump Drive дээрхээс энэ хувиас
#: бага бол (шинэ/хоосон сан) дарж бичихгүй — гараар «Одоо байршуулах» л дарна.
SHRINK_GUARD_RATIO = 0.5
SHRINK_GUARD_MIN_BYTES = 1 * MB


# --------------------------------------------------------------------------- #
# Тохиргоо
# --------------------------------------------------------------------------- #
class GdriveConfig:
    def __init__(self, service_account: str, folder_id: str, enabled: bool) -> None:
        self.service_account = (service_account or "").strip()
        self.folder_id = (folder_id or "").strip()
        self.enabled = bool(enabled)

    @property
    def configured(self) -> bool:
        return bool(self.service_account and self.folder_id)

    @property
    def client_email(self) -> str | None:
        try:
            return str(json.loads(self.service_account).get("client_email") or "") or None
        except (ValueError, AttributeError):
            return None


async def load_config(db: AsyncSession) -> GdriveConfig:
    return GdriveConfig(
        service_account=str(await settings_service.get_setting(db, "gdrive_service_account") or ""),
        folder_id=str(await settings_service.get_setting(db, "gdrive_folder_id") or ""),
        enabled=await settings_service.get_bool(db, "gdrive_enabled"),
    )


def validate_service_account(raw: str) -> dict[str, Any]:
    """JSON түлхүүрийг шалгаад dict буцаана (422 — буруу бол)."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Service account JSON уншигдсангүй") from exc
    if not isinstance(data, dict) or data.get("type") != "service_account":
        raise HTTPException(status_code=422, detail='JSON нь "type": "service_account" байх ёстой')
    for key in ("client_email", "private_key", "token_uri"):
        if not data.get(key):
            raise HTTPException(status_code=422, detail=f"Service account JSON-д «{key}» алга")
    return data


# --------------------------------------------------------------------------- #
# Drive клиент (синхрон — thread дотор)
# --------------------------------------------------------------------------- #
def _drive(service_account: str):  # noqa: ANN202 — googleapiclient Resource
    try:
        from google.oauth2 import service_account as sa  # noqa: PLC0415
        from googleapiclient.discovery import build  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover — requirements суугаагүй
        raise HTTPException(
            status_code=422, detail="Google Drive номын сан суугаагүй (google-api-python-client)"
        ) from exc
    info = validate_service_account(service_account)
    try:
        creds = sa.Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception as exc:  # noqa: BLE001 — private_key гэмтэлтэй бол ValueError
        raise HTTPException(
            status_code=422, detail="Service account түлхүүр буруу байна (private_key уншигдсангүй)"
        ) from exc
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _http_detail(exc: Exception) -> str:
    """Google-ийн алдааг хүнд ойлгомжтой богино мөр болгоно."""
    text = str(exc)
    if "404" in text:
        return "Drive хавтас олдсонгүй — Folder ID буруу эсвэл service account-д хуваалцаагүй"
    if "403" in text:
        return "Drive хавтсанд бичих эрхгүй — хавтсыг service account-ын и-мэйлд Editor эрхээр хуваалцна уу"
    if "invalid_grant" in text or "JWT" in text:
        return "Service account түлхүүр хүчингүй (invalid_grant) — шинэ JSON түлхүүр үүсгэнэ үү"
    return " ".join(text.split())[:300]


def _find_remote(drive, folder_id: str, name: str) -> dict[str, Any] | None:  # noqa: ANN001
    safe = name.replace("'", "\\'")
    resp = (
        drive.files()
        .list(
            q=f"name = '{safe}' and '{folder_id}' in parents and trashed = false",
            fields="files(id, name, size, modifiedTime)",
            pageSize=5,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = resp.get("files") or []
    if not files:
        return None
    row = files[0]
    return {
        "id": row["id"],
        "name": row.get("name"),
        "size_bytes": int(row.get("size") or 0),
        "modified_at": row.get("modifiedTime"),
    }


def _check_sync(service_account: str, folder_id: str) -> dict[str, Any]:
    drive = _drive(service_account)
    try:
        folder = (
            drive.files()
            .get(fileId=folder_id, fields="id, name, mimeType", supportsAllDrives=True)
            .execute()
        )
        if folder.get("mimeType") != "application/vnd.google-apps.folder":
            raise HTTPException(status_code=422, detail="Folder ID нь хавтас биш файл заажээ")
        remote = _find_remote(drive, folder_id, REMOTE_NAME)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_http_detail(exc)) from exc
    return {"folder_name": folder.get("name"), "remote": remote}


def _upload_sync(service_account: str, folder_id: str, path: Path, *, force: bool) -> dict[str, Any]:
    from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

    drive = _drive(service_account)
    local_size = path.stat().st_size
    try:
        existing = _find_remote(drive, folder_id, REMOTE_NAME)
        if (
            existing
            and not force
            and existing["size_bytes"] >= SHRINK_GUARD_MIN_BYTES
            and local_size < existing["size_bytes"] * SHRINK_GUARD_RATIO
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Автомат байршуулалт зогсоов: локал нөөцлөлт ({local_size // 1024} КБ) Drive дээрхээс "
                    f"({existing['size_bytes'] // 1024} КБ) хэт бага — шинэ/хоосон сан байж магадгүй. "
                    "Зөв бол «Одоо байршуулах» товчоор гараар дарж бичнэ."
                ),
            )
        media = MediaFileUpload(str(path), mimetype="application/octet-stream", chunksize=CHUNK, resumable=True)
        if existing:
            request = drive.files().update(
                fileId=existing["id"], media_body=media, fields="id, size, modifiedTime", supportsAllDrives=True
            )
        else:
            request = drive.files().create(
                body={"name": REMOTE_NAME, "parents": [folder_id]},
                media_body=media,
                fields="id, size, modifiedTime",
                supportsAllDrives=True,
            )
        response = None
        while response is None:
            _status, response = request.next_chunk()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_http_detail(exc)) from exc
    return {
        "id": response["id"],
        "name": REMOTE_NAME,
        "size_bytes": int(response.get("size") or local_size),
        "modified_at": response.get("modifiedTime"),
    }


def _download_sync(service_account: str, folder_id: str, dest: Path) -> dict[str, Any]:
    from googleapiclient.http import MediaIoBaseDownload  # noqa: PLC0415

    drive = _drive(service_account)
    try:
        remote = _find_remote(drive, folder_id, REMOTE_NAME)
        if remote is None:
            raise HTTPException(status_code=404, detail=f"Drive хавтсанд {REMOTE_NAME} файл алга")
        part = dest.with_suffix(dest.suffix + ".part")
        with part.open("wb") as handle:
            downloader = MediaIoBaseDownload(
                handle, drive.files().get_media(fileId=remote["id"], supportsAllDrives=True), chunksize=CHUNK
            )
            done = False
            while not done:
                _status, done = downloader.next_chunk()
        os.replace(part, dest)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=_http_detail(exc)) from exc
    return remote


# --------------------------------------------------------------------------- #
# Async API
# --------------------------------------------------------------------------- #
async def check(config: GdriveConfig) -> dict[str, Any]:
    """Хавтас, эрхийг шалгаад Drive дээрх файлын мэдээллийг буцаана."""
    if not config.configured:
        raise HTTPException(status_code=422, detail="Google Drive тохируулаагүй байна")
    return await asyncio.to_thread(_check_sync, config.service_account, config.folder_id)


async def upload(config: GdriveConfig, path: Path, *, force: bool = False) -> dict[str, Any]:
    if not config.configured:
        raise HTTPException(status_code=422, detail="Google Drive тохируулаагүй байна")
    return await asyncio.to_thread(_upload_sync, config.service_account, config.folder_id, path, force=force)


async def download(config: GdriveConfig, dest: Path) -> dict[str, Any]:
    if not config.configured:
        raise HTTPException(status_code=422, detail="Google Drive тохируулаагүй байна")
    return await asyncio.to_thread(_download_sync, config.service_account, config.folder_id, dest)


async def record_result(db: AsyncSession, *, error: str | None) -> None:
    """Сүүлийн байршуулалтын төлөвийг тохиргоонд бичнэ (амжилт → цаг, алдаа → мессеж)."""
    if error is None:
        await settings_service.set_setting(db, "gdrive_last_upload_at", datetime.now(UTC).isoformat())
        await settings_service.set_setting(db, "gdrive_last_error", "")
    else:
        await settings_service.set_setting(db, "gdrive_last_error", error[:500])


def masked_status(config: GdriveConfig) -> dict[str, Any]:
    return {
        "configured": config.configured,
        "enabled": config.enabled,
        "folder_id": config.folder_id,
        "client_email": config.client_email,
    }


__all__ = [
    "REMOTE_NAME",
    "GdriveConfig",
    "check",
    "download",
    "load_config",
    "masked_status",
    "record_result",
    "upload",
    "validate_service_account",
]

# io импортыг MediaIoBaseDownload-ын төрлийн лавлагаанд үлдээв.
_ = io
