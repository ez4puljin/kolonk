import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuditLog


def _jsonable(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    return {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v) for k, v in data.items()}


async def audit(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=_jsonable(before),
        after=_jsonable(after),
        ip=ip,
    )
    db.add(row)
    return row
