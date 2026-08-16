import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import SyncOutbox


async def emit(
    db: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> SyncOutbox:
    """Record a domain event in the same transaction as the business change.
    v2 edge-sync consumes this feed; nothing reads it in v1."""
    row = SyncOutbox(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(row)
    return row
