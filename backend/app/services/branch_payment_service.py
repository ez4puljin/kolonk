"""Салбарын төлбөрийн хэлбэрийн үйлчилгээ.

Дүрэм: салбарт **тохиргооны мөр байхгүй бол бүх хэлбэр нээлттэй**.  Мөр
үүссэн үед зөвхөн ``is_enabled=True`` байгаа нь ашиглагдана.

Энэ модуль ``db.commit()`` дуудахгүй — ``get_db`` эзэмшинэ (CONTRACTS.md §1).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import PaymentMethod
from app.models.branch_payment import BranchPaymentMethod

#: Дэлгэцэнд харагдах дараалал — ПОС-ын товчнуудын байрлал.
DEFAULT_ORDER: tuple[str, ...] = (
    str(PaymentMethod.CASH),
    str(PaymentMethod.CARD),
    str(PaymentMethod.QR),
    str(PaymentMethod.TRANSFER),
    str(PaymentMethod.CONTRACT),
)

#: Бэлэн мөнгийг хааж болохгүй — хариулт өгөх, ээлжийн касс үүн дээр тулгуурладаг.
ALWAYS_ENABLED: frozenset[str] = frozenset({str(PaymentMethod.CASH)})


def _valid(method: str) -> str:
    value = str(method or "").strip()
    if value not in DEFAULT_ORDER:
        raise HTTPException(status_code=422, detail=f"Төлбөрийн хэлбэр буруу байна: {value}")
    return value


async def _rows(db: AsyncSession, branch_id: uuid.UUID) -> dict[str, BranchPaymentMethod]:
    rows = (
        await db.scalars(
            select(BranchPaymentMethod).where(BranchPaymentMethod.branch_id == branch_id)
        )
    ).all()
    return {str(row.method): row for row in rows}


async def enabled_methods(db: AsyncSession, branch_id: uuid.UUID | None) -> set[str]:
    """Тухайн салбарт ашиглаж болох хэлбэрүүд (тохиргоогүй бол бүгд)."""
    if branch_id is None:
        return set(DEFAULT_ORDER)
    rows = await _rows(db, branch_id)
    if not rows:
        return set(DEFAULT_ORDER)
    allowed = {method for method, row in rows.items() if row.is_enabled}
    # Тохиргоонд ороогүй хэлбэрийг нээлттэй гэж үзнэ (шинэ хэлбэр нэмэгдсэн үед).
    allowed |= {m for m in DEFAULT_ORDER if m not in rows}
    return allowed | set(ALWAYS_ENABLED)


async def list_methods(db: AsyncSession, branch_id: uuid.UUID) -> list[dict[str, Any]]:
    """Салбарын бүх хэлбэр + идэвхтэй эсэх (дэлгэцэд харуулах дараалалтай)."""
    from app.services.sale_service import method_label

    rows = await _rows(db, branch_id)
    out: list[dict[str, Any]] = []
    for index, method in enumerate(DEFAULT_ORDER):
        row = rows.get(method)
        out.append(
            {
                "method": method,
                "label": method_label(method),
                "is_enabled": bool(row.is_enabled) if row is not None else True,
                "sort_order": int(row.sort_order) if row is not None else index,
                "locked": method in ALWAYS_ENABLED,
            }
        )
    out.sort(key=lambda item: item["sort_order"])
    return out


async def set_methods(
    db: AsyncSession, branch_id: uuid.UUID, methods: list[Any]
) -> list[dict[str, Any]]:
    """Салбарын тохиргоог бүхэлд нь дарж бичнэ."""
    rows = await _rows(db, branch_id)

    for index, item in enumerate(methods or []):
        method = _valid(getattr(item, "method", None) or (item or {}).get("method"))
        raw_enabled = getattr(item, "is_enabled", None)
        if raw_enabled is None and isinstance(item, dict):
            raw_enabled = item.get("is_enabled")
        enabled = True if raw_enabled is None else bool(raw_enabled)

        # Бэлэн мөнгийг хаах боломжгүй — хариулт, ээлжийн касс үүнээс хамаарна.
        if method in ALWAYS_ENABLED:
            enabled = True

        row = rows.get(method)
        if row is None:
            db.add(
                BranchPaymentMethod(
                    branch_id=branch_id, method=method, is_enabled=enabled, sort_order=index
                )
            )
        else:
            row.is_enabled = enabled
            row.sort_order = index

    await db.flush()
    return await list_methods(db, branch_id)


async def assert_allowed(
    db: AsyncSession, branch_id: uuid.UUID | None, methods: list[str]
) -> None:
    """Борлуулалтад ашигласан хэлбэрүүд салбарт зөвшөөрөгдсөн эсэхийг шалгана."""
    if branch_id is None or not methods:
        return
    from app.services.sale_service import method_label

    allowed = await enabled_methods(db, branch_id)
    blocked = sorted({m for m in methods if m not in allowed})
    if blocked:
        names = ", ".join(method_label(m) for m in blocked)
        raise HTTPException(
            status_code=422,
            detail=f"Энэ салбарт дараах төлбөрийн хэлбэр идэвхгүй байна: {names}",
        )
