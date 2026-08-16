"""Хойшлуулсан үнийн өөрчлөлтийг хэрэгжүүлэх ажил.

«Тосны үнийн өөрчлөлт маргаашнаас» — батлагдсан ч ``effective_date`` нь
ирээгүй өөрчлөлт үнэд нөлөөлөхгүй хүлээдэг.  Энэ ажил өдөр бүр өглөө станцын
цагаар шалгаж, хугацаа нь болсныг нь бодитоор тавьдаг.
"""

from __future__ import annotations

import logging
from typing import Any

from app.database import async_session_factory
from app.services.price_change_service import apply_due_changes

log = logging.getLogger("kolonk.jobs.price")


async def apply_due_price_changes(ctx: dict[str, Any]) -> int:
    """Хугацаа нь болсон үнийн өөрчлөлтүүдийг хэрэгжүүлнэ (өдөр бүр)."""
    async with async_session_factory() as db:
        applied = await apply_due_changes(db)
        await db.commit()
    if applied:
        log.info("Хойшлуулсан %d үнийн өөрчлөлт хэрэгжлээ", applied)
    return applied
