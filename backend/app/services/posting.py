"""Журналын бичилтийн үйлчилгээ (CONTRACTS.md §3).

Домэйн үйлчилгээ бүр ``posting.post(...)``-оор дамжуулан давхар бичилт хийнэ.
Энэ модуль **хэзээ ч commit хийхгүй** — ``get_db`` л commit хийнэ.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import JournalEntry, JournalLine
from app.money import q2

ZERO = Decimal("0")


class UnbalancedEntryError(Exception):
    """Дебит ба кредит тэнцээгүй, эсвэл бичилт хүчингүй үед."""


@dataclass(frozen=True)
class Dims:
    """Журналын мөрийн аналитик хэмжигдэхүүн."""

    fuel_id: uuid.UUID | None = None
    tank_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    #: 1110 дансны мөрийг аль харилцах данстай холбох вэ.
    bank_account_id: uuid.UUID | None = None


NO_DIMS = Dims()


@dataclass(frozen=True)
class LineSpec:
    """Нэг журналын мөрийн тодорхойлолт (DB-ээс хамааралгүй)."""

    account_code: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    memo: str | None = None
    dims: Dims = field(default=NO_DIMS)


def normalize_lines(lines: list[LineSpec]) -> list[LineSpec]:
    """Мөрүүдийг цэвэрлэж, тэнцлийг шалгана (цэвэр функц — DB хэрэггүй).

    * бүх дүнг ``q2``-оор дугуйлна;
    * сөрөг дүнг эсрэг тал руу нь хөрвүүлнэ;
    * дебит=0 ба кредит=0 мөрийг хасна;
    * үлдсэн мөр байхгүй бол хоосон жагсаалт буцаана (бичих зүйлгүй);
    * үлдсэн мөр 2-оос цөөн буюу Σдебит ≠ Σкредит бол ``UnbalancedEntryError``.
    """
    cleaned: list[LineSpec] = []
    for line in lines:
        debit = q2(line.debit or ZERO)
        credit = q2(line.credit or ZERO)

        # Сөрөг дүнг эсрэг тал руу шилжүүлнэ (DB-д debit/credit >= 0 байх ёстой).
        if debit < 0:
            credit += -debit
            debit = ZERO
        if credit < 0:
            debit += -credit
            credit = ZERO
        debit, credit = q2(debit), q2(credit)

        # Хоёр тал зэрэг дүнтэй бол цэвэр үлдэгдэл рүү нь хураана.
        if debit > 0 and credit > 0:
            net = q2(debit - credit)
            debit, credit = (net, ZERO) if net >= 0 else (ZERO, -net)

        if debit == 0 and credit == 0:
            continue
        cleaned.append(replace(line, debit=debit, credit=credit, dims=line.dims or NO_DIMS))

    if not cleaned:
        return []

    if len(cleaned) < 2:
        raise UnbalancedEntryError("Журналын бичилт хамгийн багадаа 2 мөртэй байх ёстой")

    total_debit = q2(sum((ln.debit for ln in cleaned), ZERO))
    total_credit = q2(sum((ln.credit for ln in cleaned), ZERO))
    if total_debit != total_credit:
        raise UnbalancedEntryError(
            f"Журналын бичилт тэнцэхгүй байна: дебит {total_debit} ≠ кредит {total_credit}"
        )
    return cleaned


class PostingService:
    """Идемпотент давхар бичилтийн үйлчилгээ."""

    async def post(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        source_type: str,
        source_id: uuid.UUID,
        entry_date: date,
        description: str,
        lines: list[LineSpec],
        posted_by: uuid.UUID | None = None,
    ) -> JournalEntry | None:
        """Журналын бичилт үүсгэнэ.

        Бичих мөр байхгүй (бүгд тэг) бол ``None`` буцаана.
        ``(source_type, source_id, event_type)`` давхардвал байгаа бичилтийг
        өөрчлөхгүйгээр буцаана.
        """
        normalized = normalize_lines(lines)
        if not normalized:
            return None

        existing = await db.scalar(
            select(JournalEntry).where(
                JournalEntry.source_type == str(source_type),
                JournalEntry.source_id == source_id,
                JournalEntry.event_type == str(event_type),
            )
        )
        if existing is not None:
            return existing

        entry = JournalEntry(
            entry_date=entry_date,
            description=(description or "")[:255],
            source_type=str(source_type),
            source_id=source_id,
            event_type=str(event_type),
            posted_by=posted_by,
        )
        for line_no, spec in enumerate(normalized, start=1):
            dims = spec.dims or NO_DIMS
            entry.lines.append(
                JournalLine(
                    line_no=line_no,
                    account_code=spec.account_code,
                    debit=spec.debit,
                    credit=spec.credit,
                    memo=(spec.memo[:255] if spec.memo else None),
                    dim_fuel_id=dims.fuel_id,
                    dim_tank_id=dims.tank_id,
                    dim_customer_id=dims.customer_id,
                    dim_supplier_id=dims.supplier_id,
                    dim_bank_account_id=dims.bank_account_id,
                )
            )

        db.add(entry)
        await db.flush()
        return entry

    async def reverse(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        source_type: str,
        source_id: uuid.UUID,
    ) -> bool:
        """Бичилтийг бүрмөсөн цуцална (мөрүүд нь cascade-аар устана).

        **Зөвхөн буруу бүртгэлийг буцаахад** — жишээ нь банкны хуулгын мөрийг
        андуу харилцагч/ангиллаар хаачихсан үед.  Баримт нь өөрөө хамт
        устдаг тул ерөнхий дэвтэр ба туслах бүртгэл хоёулаа зэрэг цэвэрлэгдэж,
        тулгалт хэвээр таарна.  Хэн юуг буцаасныг ``audit_logs`` хөтөлнө.

        Бичилт олдоогүй бол ``False``.
        """
        entry = await db.scalar(
            select(JournalEntry).where(
                JournalEntry.source_type == str(source_type),
                JournalEntry.source_id == source_id,
                JournalEntry.event_type == str(event_type),
            )
        )
        if entry is None:
            return False
        await db.delete(entry)
        await db.flush()
        return True

    async def find(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        source_type: str,
        source_id: uuid.UUID,
    ) -> JournalEntry | None:
        """Эх сурвалжаар нь журналын бичилтийг хайна (идемпотент шалгалтад)."""
        return await db.scalar(
            select(JournalEntry).where(
                JournalEntry.source_type == str(source_type),
                JournalEntry.source_id == source_id,
                JournalEntry.event_type == str(event_type),
            )
        )


#: Модуль түвшний ганц instance — бүх модуль үүнийг импортлоно.
posting = PostingService()
