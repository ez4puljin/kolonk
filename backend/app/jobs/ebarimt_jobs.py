"""И-баримт илгээх ARQ ажил (WP8).

``submit_ebarimt`` нь ``ebarimt_queue`` хүснэгтийн нэг мөрийг боловсруулна:
амжилттай бол ``SENT`` төлөвт баримтын дугаар/QR/сугалааны дугаарыг хадгална,
амжилтгүй бол ``attempt_count`` -ыг нэмж, ``last_error`` -ыг бичээд алдааг
дахин шидэж ARQ-д дахин оролдох (max_tries=5) боломж өгнө.

Ажил нь хүсэлтийн гадна ажилладаг тул өөрийн session нээж, өөрөө commit хийнэ.
Хүсэлтийн дотор (Redis унтарсан үед) ``process_queue_row`` -ыг шууд дуудаж
болно — тэр функц commit хийхгүй.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.enums import EbarimtStatus
from app.models.sale import Sale
from app.models.system import EbarimtQueue
from app.services import settings_service
from app.services.ebarimt_client import build_ebarimt_payload, get_ebarimt_client

log = logging.getLogger("kolonk.ebarimt")

#: Хэдэн удаа амжилтгүй болвол мөрийг эцсийн байдлаар FAILED болгох вэ.
MAX_ATTEMPTS = 5

ERROR_LIMIT = 2000


class EbarimtSubmitError(RuntimeError):
    """И-баримт илгээх явцад гарсан алдаа (ARQ дахин оролдоно)."""


def _record_failure(row: EbarimtQueue, message: str) -> None:
    row.attempt_count = int(row.attempt_count or 0) + 1
    row.last_error = (message or "Тодорхойгүй алдаа")[:ERROR_LIMIT]
    row.status = (
        str(EbarimtStatus.FAILED)
        if row.attempt_count >= MAX_ATTEMPTS
        else str(EbarimtStatus.PENDING)
    )


async def process_queue_row(db: AsyncSession, row: EbarimtQueue) -> EbarimtQueue:
    """Дараалалын нэг мөрийг илгээнэ. **commit хийхгүй.**

    Амжилтгүй бол мөрийн алдааны мэдээллийг бичээд ``EbarimtSubmitError``
    шиднэ — дуудагч нь (ажил эсвэл router) хэрхэн хариу өгөхөө шийднэ.
    """
    if str(row.status) == str(EbarimtStatus.SENT):
        return row

    sale = await db.scalar(select(Sale).where(Sale.id == row.sale_id))
    if sale is None:
        _record_failure(row, "Холбогдох борлуулалт олдсонгүй")
        await db.flush()
        raise EbarimtSubmitError("Холбогдох борлуулалт олдсонгүй")

    try:
        config = await settings_service.get_all(db)
        payload = build_ebarimt_payload(sale, sale.items, config)
        client = get_ebarimt_client()
        result: dict[str, Any] = await client.send(payload)
    except Exception as exc:  # noqa: BLE001 — бүх алдааг мөрөнд тэмдэглэнэ
        _record_failure(row, str(exc))
        await db.flush()
        raise EbarimtSubmitError(str(exc)) from exc

    if not result.get("success"):
        message = str(result.get("message") or "И-баримтын сервер алдаа буцаалаа")
        _record_failure(row, message)
        await db.flush()
        raise EbarimtSubmitError(message)

    row.status = str(EbarimtStatus.SENT)
    row.receipt_id = str(result.get("receipt_id") or "")[:64] or None
    row.qr_data = result.get("qr_data")
    lottery = result.get("lottery_no")
    row.lottery_no = str(lottery)[:32] if lottery else None
    row.last_error = None
    row.sent_at = datetime.now(UTC)
    await db.flush()
    return row


async def submit_ebarimt(ctx: dict[str, Any], queue_id: str) -> dict[str, Any]:
    """ARQ ажил — дараалалын мөрийг илгээнэ (өөрийн session, өөрөө commit)."""
    try:
        row_id = uuid.UUID(str(queue_id))
    except (ValueError, AttributeError, TypeError) as exc:
        log.error("И-баримтын дараалалын ID буруу: %s", queue_id)
        raise EbarimtSubmitError(f"Дараалалын ID буруу: {queue_id}") from exc

    async with async_session_factory() as db:
        row = await db.scalar(select(EbarimtQueue).where(EbarimtQueue.id == row_id))
        if row is None:
            log.warning("И-баримтын дараалалын мөр олдсонгүй: %s", row_id)
            return {"queue_id": str(row_id), "status": "missing"}

        try:
            await process_queue_row(db, row)
        except Exception:
            # Алдааны тоолуур, мессежийг хадгалаад дараа нь дахин шиднэ.
            try:
                await db.commit()
            except Exception:  # noqa: BLE001 — commit бүтэхгүй бол rollback
                await db.rollback()
            raise

        await db.commit()
        log.info("И-баримт илгээгдлээ: queue=%s receipt=%s", row_id, row.receipt_id)
        return {
            "queue_id": str(row_id),
            "status": str(row.status),
            "receipt_id": row.receipt_id,
            "lottery_no": row.lottery_no,
        }
