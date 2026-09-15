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
import hashlib
import os
import re
import subprocess
import zipfile
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
#: Цаг тутмын «сүүлийн» нөөцлөлт — үргэлж энэ нэг файлыг дарж бичнэ
#: (хард дүүрэхгүй); Google Drive дээр ч ижил нэртэй ганц файл байна.
LATEST_NAME = "kolonk-latest.dump"
#: Хавсралтын архив (ээлжийн зураг, гэрээний PDF) — мөн үргэлж нэг файл.
UPLOADS_ARCHIVE = "kolonk-uploads.zip"
#: Хавсралтын хавтас — routers (shift_photos, customer_contracts)-тай ижил харьцангуй зам.
UPLOADS_DIR = Path("uploads")
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
#: Windows: Docker-гүй станцад worker далд (консолгүй) процессоор ажилладаг тул
#: pg_dump/pg_restore дэд процесс ШИНЭ консол цонх нээж, цаг тутмын нөөцлөлт
#: бүрд хар терминал гялсхийдэг байв. CREATE_NO_WINDOW үүнийг болиулна.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _run_blocking(command: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
    """``subprocess.run`` — тусдаа thread-д ажиллана."""
    try:
        done = subprocess.run(  # noqa: S603 — команд нь дотоод, хэрэглэгчийн оролт биш
            command,
            env=env,
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=_NO_WINDOW,
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
    *,
    directory: str | Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    filename: str | None = None,
) -> str:
    """``pg_dump -Fc`` ажиллуулж нөөцлөлт үүсгээд файлын нэрийг буцаана.

    ``filename`` өгвөл (жишээ нь ``LATEST_NAME``) тэр файлыг ДАРЖ бичнэ —
    эхлээд ``.part`` түр файлд буулгаад амжилттай бол ``os.replace``-ээр
    сольдог тул dump дундаа тасарсан ч өмнөх бүтэн хуулбар үлдэнэ.
    """
    target = parse_database_url()
    directory = backup_dir(directory)
    filename = safe_name(filename) if filename else new_backup_name()
    path = directory / filename
    part = directory / f"{filename}.part"

    command = [
        PG_DUMP,
        *target.args(),
        "-Fc",
        "--no-owner",
        "--no-privileges",
        "-f",
        str(part),
    ]
    code, message = await _run(command, target.env(), timeout)
    if code != 0:
        part.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422, detail=f"Нөөцлөлт амжилтгүй боллоо: {_tail(message) or 'тодорхойгүй алдаа'}"
        )
    if not part.is_file() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Нөөцлөлтийн файл хоосон үүслээ")
    os.replace(part, path)
    return filename


def prune_dated_backups(keep_days: int, directory: str | Path | None = None) -> list[str]:
    """``kolonk_YYYYMMDD_HHMMSS.dump`` файлуудаас ``keep_days``-ээс хуучныг устгана.

    ``LATEST_NAME`` болон бусад нэртэй (before-reset-… гэх мэт) файлд хүрэхгүй.
    ``keep_days`` ≤ 0 бол юу ч устгахгүй.
    """
    if keep_days <= 0:
        return []
    directory = backup_dir(directory)
    cutoff = datetime.now(UTC).timestamp() - keep_days * 86400
    removed: list[str] = []
    for path in directory.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        if not path.is_file() or path.name == LATEST_NAME:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path.name)
        except OSError:  # pragma: no cover — зэрэг устгагдсан
            continue
    return removed


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


# --------------------------------------------------------------------------- #
# Хавсралтын архив (ээлжийн зураг, гэрээний PDF)
# --------------------------------------------------------------------------- #
def uploads_fingerprint(root: Path | None = None) -> tuple[str, int]:
    """Хавсралтын хавтасны (зам, хэмжээ, mtime) хурууны хээ ба файлын тоо.

    Өөрчлөлт байхгүй бол архивыг дахин үүсгэх, Drive руу дахин байршуулах
    шаардлагагүй — цаг тутам хэдэн зуун МБ илгээхээс сэргийлнэ.
    """
    root = root or UPLOADS_DIR
    digest = hashlib.sha256()
    count = 0
    if root.is_dir():
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            stat = path.stat()
            digest.update(f"{path.relative_to(root).as_posix()}|{stat.st_size}|{int(stat.st_mtime)}\n".encode())
            count += 1
    return digest.hexdigest(), count


def uploads_archive_info(directory: str | Path | None = None) -> dict[str, Any] | None:
    path = backup_dir(directory) / UPLOADS_ARCHIVE
    if not path.is_file():
        return None
    stat = path.stat()
    return {
        "filename": path.name,
        "size_bytes": int(stat.st_size),
        "size_mb": round(stat.st_size / MB, 2),
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    }


def _build_uploads_archive(root: Path, dest: Path) -> int:
    part = dest.with_suffix(dest.suffix + ".part")
    count = 0
    # Зураг (JPEG) аль хэдийн шахагдсан тул ZIP_STORED — хурдан, CPU бага.
    with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(root).as_posix())
            count += 1
    os.replace(part, dest)
    return count


async def create_uploads_archive(
    *, directory: str | Path | None = None, force: bool = False
) -> dict[str, Any] | None:
    """``uploads/``-ыг ``kolonk-uploads.zip`` болгоно (хавтас хоосон бол None).

    Хурууны хээ өмнөх архивынхтай ижил бол дахин үүсгэхгүй (``changed=False``).
    """
    root = UPLOADS_DIR
    fingerprint, count = await asyncio.to_thread(uploads_fingerprint, root)
    if count == 0:
        return None
    directory = backup_dir(directory)
    dest = directory / UPLOADS_ARCHIVE
    marker = directory / f"{UPLOADS_ARCHIVE}.fp"
    previous = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    changed = force or previous != fingerprint or not dest.is_file()
    if changed:
        await asyncio.to_thread(_build_uploads_archive, root, dest)
        marker.write_text(fingerprint, encoding="utf-8")
    info = uploads_archive_info(directory) or {}
    return {**info, "files": count, "fingerprint": fingerprint, "changed": changed}


def _extract_uploads_archive(archive: Path, root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    root_resolved = root.resolve()
    count = 0
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = (root / member.filename).resolve()
            if root_resolved not in target.parents:  # zip-slip хамгаалалт
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


async def restore_uploads_archive(directory: str | Path | None = None) -> int:
    """``kolonk-uploads.zip``-ийг ``uploads/`` руу задална (байгаа файлыг дарж, бусдыг үлдээнэ)."""
    archive = backup_dir(directory) / UPLOADS_ARCHIVE
    if not archive.is_file():
        raise HTTPException(status_code=404, detail=f"{UPLOADS_ARCHIVE} олдсонгүй — эхлээд Drive-аас татна уу")
    try:
        return await asyncio.to_thread(_extract_uploads_archive, archive, UPLOADS_DIR)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="Архив гэмтэлтэй байна") from exc
