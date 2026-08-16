"""И-баримтын дараалалын API — жагсаалт, дахин илгээх (WP8)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import require_permission
from app.enums import EbarimtStatus
from app.jobs.ebarimt_jobs import EbarimtSubmitError, submit_ebarimt
from app.models.sale import Sale
from app.models.system import EbarimtQueue
from app.models.user import User
from app.money import q2
from app.schemas.report import EbarimtQueueList, EbarimtQueueRow, EbarimtRetryOut
from app.services.audit_service import audit

log = logging.getLogger("kolonk.ebarimt")

router = APIRouter(prefix="/api", tags=["ebarimt"])

CanManage = Depends(require_permission("ebarimt.manage"))

STATUS_NAMES_MN: dict[str, str] = {
    EbarimtStatus.PENDING: "Хүлээгдэж буй",
    EbarimtStatus.SENT: "Илгээгдсэн",
    EbarimtStatus.FAILED: "Амжилтгүй",
}

#: Redis холбогдох оролдлогод зарцуулах дээд хугацаа (секунд).
REDIS_TIMEOUT = 3.0

JOB_NAME = "submit_ebarimt"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _row_out(row: EbarimtQueue, sale: Sale | None) -> EbarimtQueueRow:
    return EbarimtQueueRow(
        id=row.id,
        sale_id=row.sale_id,
        sale_number=int(sale.number) if sale is not None and sale.number is not None else None,
        sale_total=q2(sale.total) if sale is not None else None,
        sale_completed_at=sale.completed_at if sale is not None else None,
        status=str(row.status),
        status_name=STATUS_NAMES_MN.get(row.status, str(row.status)),
        attempt_count=int(row.attempt_count or 0),
        last_error=row.last_error,
        receipt_id=row.receipt_id,
        qr_data=row.qr_data,
        lottery_no=row.lottery_no,
        sent_at=row.sent_at,
        created_at=row.created_at,
    )


async def _load_sale(db: AsyncSession, sale_id: uuid.UUID) -> Sale | None:
    return await db.scalar(select(Sale).where(Sale.id == sale_id))


async def _enqueue(queue_id: uuid.UUID) -> str | None:
    """ARQ дараалалд ажлыг оруулна. Redis ажиллахгүй бол алдаа шиднэ."""
    from arq import create_pool  # noqa: PLC0415 — зөвхөн шаардлагатай үед
    from arq.connections import RedisSettings  # noqa: PLC0415

    pool = await asyncio.wait_for(
        create_pool(RedisSettings.from_dsn(settings.redis_url)), timeout=REDIS_TIMEOUT
    )
    try:
        job = await pool.enqueue_job(JOB_NAME, str(queue_id))
    finally:
        with contextlib.suppress(Exception):
            await pool.aclose()
    return getattr(job, "job_id", None) if job is not None else None


# --------------------------------------------------------------------------- #
# Дараалал
# --------------------------------------------------------------------------- #
@router.get("/ebarimt/queue", response_model=EbarimtQueueList)
async def list_queue(
    status: str | None = Query(default=None, description="pending | sent | failed"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> EbarimtQueueList:
    conditions = []
    if status:
        normalized = status.strip().lower()
        if normalized not in {str(s) for s in EbarimtStatus}:
            raise HTTPException(status_code=422, detail="Төлөв зөвхөн pending, sent, failed байна")
        conditions.append(EbarimtQueue.status == normalized)

    total = await db.scalar(select(func.count(EbarimtQueue.id)).where(*conditions)) or 0
    rows = (
        await db.execute(
            select(EbarimtQueue, Sale)
            .outerjoin(Sale, EbarimtQueue.sale_id == Sale.id)
            .where(*conditions)
            .order_by(EbarimtQueue.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return EbarimtQueueList(
        items=[_row_out(row, sale) for row, sale in rows],
        total=int(total),
    )


@router.get("/ebarimt/queue/{queue_id}", response_model=EbarimtQueueRow)
async def get_queue_item(
    queue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> EbarimtQueueRow:
    row = await db.scalar(select(EbarimtQueue).where(EbarimtQueue.id == queue_id))
    if row is None:
        raise HTTPException(status_code=404, detail="И-баримтын дараалалын бичлэг олдсонгүй")
    return _row_out(row, await _load_sale(db, row.sale_id))


@router.post("/ebarimt/queue/{queue_id}/retry", response_model=EbarimtRetryOut)
async def retry_queue_item(
    queue_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = CanManage,
) -> EbarimtRetryOut:
    """Амжилтгүй болсон баримтыг дахин илгээнэ.

    Эхлээд ARQ дараалалд оруулахыг оролдоно. Redis ажиллахгүй байвал шууд
    (inline) илгээнэ — тэр нь ч бүтэхгүй бол 503 буцаана.
    """
    row = await db.scalar(select(EbarimtQueue).where(EbarimtQueue.id == queue_id))
    if row is None:
        raise HTTPException(status_code=404, detail="И-баримтын дараалалын бичлэг олдсонгүй")
    if str(row.status) == str(EbarimtStatus.SENT):
        raise HTTPException(status_code=422, detail="Энэ баримт аль хэдийн илгээгдсэн байна")

    await audit(
        db,
        user_id=user.id,
        action="ebarimt.retry",
        entity_type="ebarimt_queue",
        entity_id=row.id,
        before={"status": str(row.status), "attempt_count": int(row.attempt_count or 0)},
        ip=_client_ip(request),
    )

    try:
        job_id = await _enqueue(row.id)
    except Exception as exc:  # noqa: BLE001 — Redis унтарсан бол шууд илгээнэ
        log.warning("ARQ дараалал ашиглах боломжгүй (%s) — шууд илгээж байна", exc)
        try:
            # Ажил өөрийн session-тэй тул хүсэлтийн гүйлгээг хөндөхгүй.
            await submit_ebarimt({}, str(row.id))
        except EbarimtSubmitError as inline_exc:
            raise HTTPException(
                status_code=503,
                detail=f"И-баримт илгээх боломжгүй байна: {inline_exc}",
            ) from inline_exc
        except Exception as inline_exc:  # noqa: BLE001
            raise HTTPException(
                status_code=503,
                detail="И-баримтын үйлчилгээ болон дараалал хоёулаа ажиллахгүй байна",
            ) from inline_exc

        await db.refresh(row)
        return EbarimtRetryOut(
            queued=False,
            inline=True,
            job_id=None,
            item=_row_out(row, await _load_sale(db, row.sale_id)),
            message="Дараалал ажиллахгүй байсан тул баримтыг шууд илгээлээ",
        )

    return EbarimtRetryOut(
        queued=True,
        inline=False,
        job_id=job_id,
        item=_row_out(row, await _load_sale(db, row.sale_id)),
        message="Баримтыг дахин илгээхээр дараалалд оруулав",
    )
