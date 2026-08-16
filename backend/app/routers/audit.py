"""Аудит лог харах."""

import uuid
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.deps import require_permission
from app.models.user import AuditLog, User
from app.schemas.system import AuditLogListResponse, AuditLogOut

router = APIRouter(prefix="/api", tags=["audit"])

try:
    STATION_TZ: tzinfo = ZoneInfo(app_settings.tz)
except Exception:  # noqa: BLE001 — цагийн бүсийн сан байхгүй бол UTC-д шилжинэ
    STATION_TZ = timezone.utc


def _parse_bound(raw: str | None, *, end_of_day: bool) -> datetime | None:
    """`2026-08-06` эсвэл бүрэн ISO огноо-цагийг цагийн бүстэй datetime болгоно."""
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        if len(value) == 10:
            day = date.fromisoformat(value)
            if end_of_day:
                return datetime.combine(day + timedelta(days=1), time.min, tzinfo=STATION_TZ)
            return datetime.combine(day, time.min, tzinfo=STATION_TZ)
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Огнооны формат буруу байна (ЖИШЭЭ: 2026-08-06)",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=STATION_TZ)
    return parsed


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    user_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current: User = Depends(require_permission("audit.view")),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    conditions = []
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action.ilike(f"{action.strip()}%"))
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type.strip())

    dt_from = _parse_bound(date_from, end_of_day=False)
    dt_to = _parse_bound(date_to, end_of_day=True)
    if dt_from is not None:
        conditions.append(AuditLog.created_at >= dt_from)
    if dt_to is not None:
        conditions.append(AuditLog.created_at < dt_to)

    total_stmt = select(func.count()).select_from(AuditLog)
    if conditions:
        total_stmt = total_stmt.where(*conditions)
    total = int((await db.scalar(total_stmt)) or 0)

    stmt = select(AuditLog)
    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    rows = (await db.scalars(stmt)).all()

    items = [
        AuditLogOut(
            id=row.id,
            user_id=row.user_id,
            user_full_name=row.user.full_name if row.user else None,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            before=row.before,
            after=row.after,
            ip=row.ip,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return AuditLogListResponse(items=items, total=total)
