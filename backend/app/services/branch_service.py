"""Салбар шийдвэрлэх туслахууд.

Нөөц, худалдан авалт зэрэг салбартай холбоотой бичлэгт салбар заагдаагүй
үед ҮНДСЭН салбар (sort_order-оор эхний идэвхтэй) үйлчилнэ — ингэснээр
Σ(салбарын үлдэгдэл) == нийт үлдэгдэл инвариант хэзээ ч алдагдахгүй.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.user import User


def effective_branch_id(user: User | None) -> uuid.UUID | None:
    """Хэрэглэгчийн АЖЛЫН салбар.

    1. Түгээгч салбартаа харьяалагддаг (``user.branch_id``) — үргэлж түүнийг.
    2. Салбаргүй хэрэглэгч (нягтлан, админ) нэвтрэхдээ салбар сонгосон бол
       тэр салбар — токены ``bid`` claim-аас ``deps.get_current_user``
       ``active_branch_id`` шинжид тавьдаг.
    3. Аль нь ч байхгүй бол ``None`` — дуудагч үндсэн салбар руу унана эсвэл
       бүх салбарыг хардаг.
    """
    if user is None:
        return None
    own = getattr(user, "branch_id", None)
    if own is not None:
        return own
    return getattr(user, "active_branch_id", None)


async def main_branch_id(db: AsyncSession) -> uuid.UUID | None:
    """Үндсэн салбарын id — хамгийн анх үүсгэсэн идэвхтэй салбар.

    ``sort_order`` нь зөвхөн харагдах дараалал бөгөөд шинэ салбар 0-тэй үүсдэг
    тул түүгээр эрэмбэлбэл "үндсэн" салбар гэнэт солигдоно.  Үүсгэсэн огноо
    хэзээ ч өөрчлөгддөггүй — тогтвортой.
    """
    return await db.scalar(
        select(Branch.id)
        .where(Branch.is_active.is_(True))
        .order_by(Branch.created_at)
        .limit(1)
    )


async def resolve_branch_id(
    db: AsyncSession, user: User | None = None, branch_id: uuid.UUID | None = None
) -> uuid.UUID | None:
    """Салбарыг дарааллаар шийднэ: заасан салбар → хэрэглэгчийн ажлын салбар → үндсэн."""
    if branch_id is not None:
        return branch_id
    working = effective_branch_id(user)
    if working is not None:
        return working
    return await main_branch_id(db)
