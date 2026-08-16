"""Өгөгдлийн сангийн нөөцлөлт, сэргээлт (WP8).

``pg_dump -Fc`` / ``pg_restore --clean --if-exists`` командыг дэд процессоор
ажиллуулна. Холболтын мэдээллийг ``settings.database_url`` -аас задлан авч,
нууц үгийг ``PGPASSWORD`` орчны хувьсагчаар дамжуулна (командын мөрөнд
нууц үг гарахгүй).

Файлын нэр: ``kolonk_YYYYMMDD_HHMMSS.dump``. Хадгалах хавтсыг эзэн
тохиргооноос (``backup_dir``) солино — тохируулаагүй бол ``.env``-ийн утга.
Замын халдлагаас (``../``) хамгаалахын тулд зөвхөн үндсэн нэрийг зөвшөөрнө.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.config import settings

BACKUP_PREFIX = "kolonk_"
BACKUP_SUFFIX = ".dump"
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

PG_DUMP = "pg_dump"
PG_RESTORE = "pg_restore"

#: Нэг үйлдэлд зөвшөөрөх дээд хугацаа (секунд).
DEFAULT_TIMEOUT = 600.0

MB = 1024 * 1024


# --------------------------------------------------------------------------- #
# Холболтын мэдээлэл
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PgTarget:
    """``pg_dump``/``pg_restore`` -д дамжуулах холболтын параметрүүд."""

    host: str
    port: str
    user: str
    password: str
    database: str

    def args(self) -> list[str]:
        return ["-h", self.host, "-p", self.port, "-U", self.user, "-d", self.database]

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.password:
            env["PGPASSWORD"] = self.password
        return env


def parse_database_url(url: str | None = None) -> PgTarget:
    """``postgresql+asyncpg://user:pass@host:5432/db`` → холболтын хэсгүүд."""
    raw = url or settings.database_url
    parts = urlsplit(raw)
    database = unquote(parts.path or "").lstrip("/")
    if not database:
        raise HTTPException(status_code=422, detail="Өгөгдлийн сангийн хаяг буруу байна")
    return PgTarget(
        host=parts.hostname or "localhost",
        port=str(parts.port or 5432),
        user=unquote(parts.username or ""),
        password=unquote(parts.password or ""),
        database=database,
    )


# --------------------------------------------------------------------------- #
# Хавтас, файлын нэр
# --------------------------------------------------------------------------- #
def backup_dir(directory: str | Path | None = None) -> Path:
    """Нөөцлөлтийн хавтас (байхгүй бол үүсгэнэ).

    ``directory`` өгөгдвөл түүнийг, эс бөгөөс ``.env``-ийн утгыг ашиглана.
    """
    raw = str(directory).strip() if directory not in (None, "") else settings.backup_dir
    path = Path(raw).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=422, detail=f"Нөөцлөлтийн хавтас үүсгэх боломжгүй: {exc}"
        ) from exc
    return path


def check_directory(directory: str) -> dict[str, Any]:
    """Хавтсыг үүсгэж, бичих эрхтэй эсэхийг шалгана (тохиргоо хадгалахын өмнө)."""
    path = backup_dir(directory)
    probe = path / ".kolonk_write_test"
    try:
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        raise HTTPException(
            status_code=422, detail=f"Хавтсанд бичих боломжгүй: {exc}"
        ) from exc
    usage = shutil.disk_usage(path)
    return {
        "directory": str(path.resolve()),
        "writable": True,
        "free_mb": round(usage.free / MB, 2),
    }


def _local_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.tz))
    except Exception:  # noqa: BLE001
        return datetime.now(UTC)


def new_backup_name() -> str:
    return f"{BACKUP_PREFIX}{_local_now().strftime('%Y%m%d_%H%M%S')}{BACKUP_SUFFIX}"


def safe_name(filename: str) -> str:
    """Зөвхөн үндсэн нэр (``../`` болон замын тусгаарлагчгүй)."""
    candidate = os.path.basename((filename or "").strip())
    if candidate != (filename or "").strip() or not FILENAME_PATTERN.match(candidate):
        raise HTTPException(status_code=422, detail="Файлын нэр буруу байна")
    if not candidate.endswith(BACKUP_SUFFIX):
        raise HTTPException(status_code=422, detail="Зөвхөн .dump өргөтгөлтэй файл зөвшөөрнө")
    return candidate


def resolve_backup(filename: str, directory: str | Path | None = None) -> Path:
    """Нэрийг шалгаад хавтас доторх бодит замыг буцаана."""
    name = safe_name(filename)
    directory = backup_dir(directory)
    path = directory / name
    try:
        resolved = path.resolve()
        root = directory.resolve()
    except OSError as exc:  # pragma: no cover — файлын систем гэмтэлтэй
        raise HTTPException(status_code=422, detail=f"Файлын зам буруу байна: {exc}") from exc
    if resolved.parent != root:
        raise HTTPException(status_code=422, detail="Файлын нэр буруу байна")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Нөөцлөлтийн файл олдсонгүй")
    return resolved


# --------------------------------------------------------------------------- #
# Дэд процесс
# --------------------------------------------------------------------------- #
def _run_blocking(command: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
    """``subprocess.run`` — тусдаа thread-д ажиллана."""
    try:
        done = subprocess.run(  # noqa: S603 — команд нь дотоод, хэрэглэгчийн оролт биш
            command,
            env=env,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"'{command[0]}' програм олдсонгүй. PostgreSQL client суулгасан эсэхийг шалгана уу",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=422, detail=f"Үйлдэл {int(timeout)} секундэд багтаж дуусаагүй тул зогсоов"
        ) from exc
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"Команд ажиллуулах боломжгүй: {exc}") from exc

    message = (done.stderr or b"").decode("utf-8", errors="replace").strip()
    return int(done.returncode or 0), message


async def _run(command: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
    """Командыг ажиллуулж ``(гарах код, stderr)`` буцаана.

    ``asyncio.create_subprocess_exec`` ашиглахгүй: uvicorn Windows дээр
    SelectorEventLoop сонгодог бөгөөд тэр нь дэд процесс дэмждэггүй
    (``NotImplementedError``). Тиймээс блоклодог хувилбарыг thread-д хийнэ —
    ямар ч платформ, ямар ч event loop дээр ажиллана.
    """
    return await asyncio.to_thread(_run_blocking, command, env, timeout)


def _tail(message: str, limit: int = 400) -> str:
    text = " ".join(message.split())
    return text if len(text) <= limit else "…" + text[-limit:]


# --------------------------------------------------------------------------- #
# Нийтийн API
# --------------------------------------------------------------------------- #
def list_backups(directory: str | Path | None = None) -> list[dict[str, Any]]:
    """Хавтас дахь нөөцлөлтүүд — шинэ нь эхэнд."""
    directory = backup_dir(directory)
    rows: list[dict[str, Any]] = []
    for path in directory.glob(f"*{BACKUP_SUFFIX}"):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "filename": path.name,
                "size_bytes": int(stat.st_size),
                "size_mb": round(stat.st_size / MB, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            }
        )
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return rows


def backup_info(filename: str, directory: str | Path | None = None) -> dict[str, Any]:
    """Нэг файлын мэдээлэл (байхгүй бол 404)."""
    path = resolve_backup(filename, directory)
    stat = path.stat()
    return {
        "filename": path.name,
        "size_bytes": int(stat.st_size),
        "size_mb": round(stat.st_size / MB, 2),
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    }


async def create_backup(
    *, directory: str | Path | None = None, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """``pg_dump -Fc`` ажиллуулж шинэ нөөцлөлт үүсгээд файлын нэрийг буцаана."""
    target = parse_database_url()
    directory = backup_dir(directory)
    filename = new_backup_name()
    path = directory / filename

    command = [
        PG_DUMP,
        *target.args(),
        "-Fc",
        "--no-owner",
        "--no-privileges",
        "-f",
        str(path),
    ]
    code, message = await _run(command, target.env(), timeout)
    if code != 0:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422, detail=f"Нөөцлөлт амжилтгүй боллоо: {_tail(message) or 'тодорхойгүй алдаа'}"
        )
    if not path.is_file() or path.stat().st_size == 0:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Нөөцлөлтийн файл хоосон үүслээ")
    return filename


async def restore_backup(
    filename: str, *, directory: str | Path | None = None, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """``pg_restore --clean --if-exists`` -ээр өгөгдлийн санг сэргээнэ."""
    path = resolve_backup(filename, directory)
    target = parse_database_url()

    command = [
        PG_RESTORE,
        *target.args(),
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        str(path),
    ]
    code, message = await _run(command, target.env(), timeout)
    if code != 0:
        raise HTTPException(
            status_code=422, detail=f"Сэргээлт амжилтгүй боллоо: {_tail(message) or 'тодорхойгүй алдаа'}"
        )
    return path.name


def delete_backup(filename: str, directory: str | Path | None = None) -> str:
    """Нөөцлөлтийн файлыг устгана (зөвхөн хавтас доторх бодит файл)."""
    path = resolve_backup(filename, directory)
    try:
        path.unlink()
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"Файл устгах боломжгүй: {exc}") from exc
    return path.name
