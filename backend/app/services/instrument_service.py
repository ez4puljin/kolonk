"""Ваучер ба урьдчилсан төлбөрт картын үйлчилгээ (WP6).

Хоёулаа **өр төлбөр** үүсгэдэг хэрэгсэл:
  * ваучер зарах → дебит tender данс, кредит ``2301``;
  * карт цэнэглэх → дебит tender данс, кредит ``2302``;
  * борлуулалтад ашиглах үед л орлого хүлээн зөвшөөрөгдөнө (``sale_service``).

Энэ модуль хэзээ ч ``db.commit()`` дуудахгүй — ``get_db`` нэг л commit хийнэ.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CardStatus, CardTxType, EventType, PaymentMethod, SourceType, VoucherStatus
from app.models.instrument import PrepaidCard, PrepaidCardTransaction, Voucher
from app.models.partner import Customer
from app.models.user import User
from app.money import q2
from app.services import posting_rules
from app.services.audit_service import audit
from app.services.outbox_service import emit
from app.services.posting import UnbalancedEntryError, posting

ZERO = Decimal("0.00")

#: Ваучерын кодын формат: "V" + 10 цифр.
VOUCHER_CODE_DIGITS = 10
MAX_CODE_ATTEMPTS = 50

VOUCHER_STATUS_MN: dict[str, str] = {
    VoucherStatus.ACTIVE: "Идэвхтэй",
    VoucherStatus.REDEEMED: "Ашиглагдсан",
    VoucherStatus.VOID: "Хүчингүй",
    VoucherStatus.EXPIRED: "Хугацаа дууссан",
}

CARD_STATUS_MN: dict[str, str] = {
    CardStatus.ACTIVE: "Идэвхтэй",
    CardStatus.BLOCKED: "Хаагдсан",
    CardStatus.CLOSED: "Цуцлагдсан",
}

CARD_TX_MN: dict[str, str] = {
    CardTxType.TOPUP: "Цэнэглэлт",
    CardTxType.REDEEM: "Зарцуулалт",
    CardTxType.REFUND: "Буцаалт",
}


def _dec(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _tender(method: Any) -> str:
    value = str(method or PaymentMethod.CASH)
    if value not in {str(m) for m in PaymentMethod}:
        raise HTTPException(status_code=422, detail="Тодорхойгүй төлбөрийн хэрэгсэл")
    if value in (str(PaymentMethod.VOUCHER), str(PaymentMethod.PREPAID)):
        raise HTTPException(status_code=422, detail="Ваучер/картаар төлөх боломжгүй")
    return value


# --------------------------------------------------------------------------- #
# Гаралтын хэлбэр
# --------------------------------------------------------------------------- #
def voucher_out(voucher: Voucher, *, customer_name: str | None = None) -> dict[str, Any]:
    return {
        "id": voucher.id,
        "code": voucher.code,
        "face_value": q2(_dec(voucher.face_value)),
        "status": str(voucher.status),
        "status_name": VOUCHER_STATUS_MN.get(str(voucher.status), str(voucher.status)),
        "customer_id": voucher.customer_id,
        "customer_name": customer_name,
        "sold_sale_id": voucher.sold_sale_id,
        "redeemed_sale_id": voucher.redeemed_sale_id,
        "sold_at": voucher.sold_at,
        "redeemed_at": voucher.redeemed_at,
        "expires_at": voucher.expires_at,
        "created_at": voucher.created_at,
    }


def card_out(card: PrepaidCard, *, customer_name: str | None = None) -> dict[str, Any]:
    return {
        "id": card.id,
        "card_no": card.card_no,
        "holder_name": card.holder_name,
        "customer_id": card.customer_id,
        "customer_name": customer_name,
        "balance": q2(_dec(card.balance)),
        "status": str(card.status),
        "status_name": CARD_STATUS_MN.get(str(card.status), str(card.status)),
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


def card_tx_out(tx: PrepaidCardTransaction) -> dict[str, Any]:
    return {
        "id": tx.id,
        "card_id": tx.card_id,
        "tx_type": str(tx.tx_type),
        "tx_type_name": CARD_TX_MN.get(str(tx.tx_type), str(tx.tx_type)),
        "amount": q2(_dec(tx.amount)),
        "balance_after": q2(_dec(tx.balance_after)),
        "sale_id": tx.sale_id,
        "created_at": tx.created_at,
    }


async def customer_name(db: AsyncSession, customer_id: uuid.UUID | None) -> str | None:
    """Харилцагчийн нэр (ID байхгүй бол ``None``)."""
    if customer_id is None:
        return None
    return await db.scalar(select(Customer.name).where(Customer.id == customer_id))


# --------------------------------------------------------------------------- #
# Ваучер
# --------------------------------------------------------------------------- #
def generate_code() -> str:
    """``V`` + 10 санамсаргүй цифр."""
    digits = "".join(str(secrets.randbelow(10)) for _ in range(VOUCHER_CODE_DIGITS))
    return f"V{digits}"


async def _unique_code(db: AsyncSession, taken: set[str]) -> str:
    for _ in range(MAX_CODE_ATTEMPTS):
        code = generate_code()
        if code in taken:
            continue
        exists = await db.scalar(select(func.count()).select_from(Voucher).where(Voucher.code == code))
        if not exists:
            taken.add(code)
            return code
    raise HTTPException(status_code=422, detail="Ваучерын код үүсгэж чадсангүй, дахин оролдоно уу")


async def issue_vouchers(
    db: AsyncSession,
    user: User,
    *,
    count: int,
    face_value: Decimal,
    expires_at: datetime | None = None,
    customer_id: uuid.UUID | None = None,
) -> list[Voucher]:
    """Багцаар ваучер хэвлэх — давхардахгүй код үүсгэнэ."""
    if count < 1 or count > 500:
        raise HTTPException(status_code=422, detail="Ваучерын тоо 1-500 хооронд байна")
    value = q2(_dec(face_value))
    if value <= ZERO:
        raise HTTPException(status_code=422, detail="Ваучерын үнэ 0-ээс их байх ёстой")
    expiry = _aware(expires_at)
    if expiry is not None and expiry <= _now():
        raise HTTPException(status_code=422, detail="Дуусах хугацаа өнгөрсөн байна")
    if customer_id is not None:
        exists = await db.scalar(select(func.count()).select_from(Customer).where(Customer.id == customer_id))
        if not exists:
            raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй")

    taken: set[str] = set()
    vouchers: list[Voucher] = []
    for _ in range(count):
        voucher = Voucher(
            code=await _unique_code(db, taken),
            face_value=value,
            status=str(VoucherStatus.ACTIVE),
            customer_id=customer_id,
            expires_at=expiry,
        )
        db.add(voucher)
        vouchers.append(voucher)
    await db.flush()

    await emit(
        db,
        aggregate_type="voucher_batch",
        aggregate_id=vouchers[0].id,
        event_type="VOUCHER_ISSUED",
        payload={
            "count": count,
            "face_value": str(value),
            "expires_at": expiry.isoformat() if expiry else None,
            "codes": [v.code for v in vouchers],
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="voucher.issue_batch",
        entity_type="voucher",
        entity_id=vouchers[0].id,
        after={"count": count, "face_value": str(value), "codes": ",".join(v.code for v in vouchers)},
    )
    return vouchers


async def get_voucher(db: AsyncSession, voucher_id: uuid.UUID, *, lock: bool = False) -> Voucher:
    stmt = select(Voucher).where(Voucher.id == voucher_id)
    if lock:
        stmt = stmt.with_for_update()
    voucher = await db.scalar(stmt)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Ваучер олдсонгүй")
    return voucher


async def validate_voucher(db: AsyncSession, code: str) -> Voucher:
    """Кодоор ваучер шалгах. Олдохгүй бол 404, ашиглах боломжгүй бол 422."""
    cleaned = (code or "").strip().upper()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Ваучерын код оруулаагүй байна")

    voucher = await db.scalar(select(Voucher).where(Voucher.code == cleaned))
    if voucher is None:
        raise HTTPException(status_code=404, detail="Ваучер олдсонгүй")

    status = str(voucher.status)
    if status == str(VoucherStatus.REDEEMED):
        raise HTTPException(status_code=422, detail="Ваучер аль хэдийн ашиглагдсан байна")
    if status == str(VoucherStatus.VOID):
        raise HTTPException(status_code=422, detail="Ваучер хүчингүй болсон байна")
    if status == str(VoucherStatus.EXPIRED):
        raise HTTPException(status_code=422, detail="Ваучерын хугацаа дууссан байна")
    if status != str(VoucherStatus.ACTIVE):
        raise HTTPException(status_code=422, detail="Ваучер идэвхгүй байна")

    expires = _aware(voucher.expires_at)
    if expires is not None and expires < _now():
        voucher.status = str(VoucherStatus.EXPIRED)
        await db.flush()
        raise HTTPException(status_code=422, detail="Ваучерын хугацаа дууссан байна")

    return voucher


async def sell_voucher(
    db: AsyncSession,
    user: User,
    voucher_id: uuid.UUID,
    tender_method: str = PaymentMethod.CASH,
    *,
    customer_id: uuid.UUID | None = None,
) -> tuple[Voucher, uuid.UUID | None]:
    """Ваучер зарах — өр төлбөр (2301) үүсгэж, мөнгө хүлээн авна."""
    method = _tender(tender_method)
    voucher = await get_voucher(db, voucher_id, lock=True)

    if str(voucher.status) != str(VoucherStatus.ACTIVE):
        raise HTTPException(status_code=422, detail="Зөвхөн идэвхтэй ваучер зарагдана")
    if voucher.sold_at is not None:
        raise HTTPException(status_code=422, detail="Ваучер аль хэдийн зарагдсан байна")

    expires = _aware(voucher.expires_at)
    if expires is not None and expires < _now():
        raise HTTPException(status_code=422, detail="Ваучерын хугацаа дууссан байна")

    if customer_id is not None:
        exists = await db.scalar(select(func.count()).select_from(Customer).where(Customer.id == customer_id))
        if not exists:
            raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй")
        voucher.customer_id = customer_id

    now = _now()
    voucher.sold_at = now
    await db.flush()

    try:
        entry = await posting.post(
            db,
            event_type=str(EventType.VOUCHER_SOLD),
            source_type=str(SourceType.VOUCHER),
            source_id=voucher.id,
            entry_date=now.date(),
            description=f"Ваучер зарсан — {voucher.code}",
            lines=posting_rules.build_voucher_sold_lines(voucher, method),
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=f"Журналын бичилт тэнцэхгүй байна: {exc}") from exc

    await emit(
        db,
        aggregate_type="voucher",
        aggregate_id=voucher.id,
        event_type=str(EventType.VOUCHER_SOLD),
        payload={
            "voucher_id": str(voucher.id),
            "code": voucher.code,
            "face_value": str(q2(_dec(voucher.face_value))),
            "method": method,
            "sold_at": now.isoformat(),
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="voucher.sell",
        entity_type="voucher",
        entity_id=voucher.id,
        after={"code": voucher.code, "face_value": str(q2(_dec(voucher.face_value))), "method": method},
    )
    await db.flush()
    return voucher, (entry.id if entry is not None else None)


async def void_voucher(
    db: AsyncSession, user: User, voucher_id: uuid.UUID, *, reason: str | None = None
) -> Voucher:
    """Ваучерыг хүчингүй болгох (ашиглагдсаныг буцаах боломжгүй)."""
    voucher = await get_voucher(db, voucher_id, lock=True)
    if str(voucher.status) == str(VoucherStatus.REDEEMED):
        raise HTTPException(status_code=422, detail="Ашиглагдсан ваучерыг хүчингүй болгох боломжгүй")
    if str(voucher.status) == str(VoucherStatus.VOID):
        raise HTTPException(status_code=422, detail="Ваучер аль хэдийн хүчингүй болсон байна")

    before = {"status": str(voucher.status)}
    voucher.status = str(VoucherStatus.VOID)
    await db.flush()

    await emit(
        db,
        aggregate_type="voucher",
        aggregate_id=voucher.id,
        event_type="VOUCHER_VOIDED",
        payload={"voucher_id": str(voucher.id), "code": voucher.code, "reason": reason},
    )
    await audit(
        db,
        user_id=user.id,
        action="voucher.void",
        entity_type="voucher",
        entity_id=voucher.id,
        before=before,
        after={"status": voucher.status, "reason": reason},
    )
    return voucher


# --------------------------------------------------------------------------- #
# Урьдчилсан төлбөрт карт
# --------------------------------------------------------------------------- #
async def get_card(db: AsyncSession, card_id: uuid.UUID, *, lock: bool = False) -> PrepaidCard:
    stmt = select(PrepaidCard).where(PrepaidCard.id == card_id)
    if lock:
        stmt = stmt.with_for_update()
    card = await db.scalar(stmt)
    if card is None:
        raise HTTPException(status_code=404, detail="Карт олдсонгүй")
    return card


async def lookup_card(db: AsyncSession, card_no: str, *, lock: bool = False) -> PrepaidCard:
    """Дугаараар карт хайх (ПОС дэлгэц)."""
    cleaned = (card_no or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Картын дугаар оруулаагүй байна")
    stmt = select(PrepaidCard).where(PrepaidCard.card_no == cleaned)
    if lock:
        stmt = stmt.with_for_update()
    card = await db.scalar(stmt)
    if card is None:
        raise HTTPException(status_code=404, detail="Карт олдсонгүй")
    return card


async def create_card(
    db: AsyncSession,
    user: User,
    *,
    card_no: str,
    holder_name: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> PrepaidCard:
    """Шинэ карт нээх — үлдэгдэл 0-ээс эхэлнэ (цэнэглэлт тусдаа гүйлгээ)."""
    cleaned = (card_no or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Картын дугаар оруулаагүй байна")

    exists = await db.scalar(
        select(func.count()).select_from(PrepaidCard).where(PrepaidCard.card_no == cleaned)
    )
    if exists:
        raise HTTPException(status_code=422, detail="Ийм дугаартай карт бүртгэгдсэн байна")

    if customer_id is not None:
        found = await db.scalar(select(func.count()).select_from(Customer).where(Customer.id == customer_id))
        if not found:
            raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй")

    card = PrepaidCard(
        card_no=cleaned,
        holder_name=(holder_name or "").strip() or None,
        customer_id=customer_id,
        balance=ZERO,
        status=str(CardStatus.ACTIVE),
    )
    db.add(card)
    await db.flush()

    await emit(
        db,
        aggregate_type="prepaid_card",
        aggregate_id=card.id,
        event_type="PREPAID_CARD_CREATED",
        payload={"card_id": str(card.id), "card_no": card.card_no, "holder_name": card.holder_name},
    )
    await audit(
        db,
        user_id=user.id,
        action="prepaid_card.create",
        entity_type="prepaid_card",
        entity_id=card.id,
        after={"card_no": card.card_no, "holder_name": card.holder_name},
    )
    return card


async def topup_card(
    db: AsyncSession,
    user: User,
    card: PrepaidCard,
    amount: Decimal,
    tender_method: str = PaymentMethod.CASH,
) -> tuple[PrepaidCardTransaction, uuid.UUID | None]:
    """Карт цэнэглэх — үлдэгдэл нэмэгдэж, ``2302`` өр төлбөр үүснэ."""
    method = _tender(tender_method)
    value = q2(_dec(amount))
    if value <= ZERO:
        raise HTTPException(status_code=422, detail="Цэнэглэх дүн 0-ээс их байх ёстой")
    if str(card.status) != str(CardStatus.ACTIVE):
        raise HTTPException(status_code=422, detail="Карт идэвхгүй байна")

    before = {"balance": str(q2(_dec(card.balance)))}
    card.balance = q2(_dec(card.balance) + value)
    tx = PrepaidCardTransaction(
        card_id=card.id,
        tx_type=str(CardTxType.TOPUP),
        amount=value,
        balance_after=q2(_dec(card.balance)),
        sale_id=None,
    )
    db.add(tx)
    await db.flush()

    now = _now()
    try:
        entry = await posting.post(
            db,
            event_type=str(EventType.PREPAID_TOPUP),
            source_type=str(SourceType.PREPAID),
            source_id=tx.id,
            entry_date=now.date(),
            description=f"Карт цэнэглэлт — {card.card_no}",
            lines=posting_rules.build_prepaid_topup_lines(card, value, method),
            posted_by=user.id,
        )
    except UnbalancedEntryError as exc:
        raise HTTPException(status_code=422, detail=f"Журналын бичилт тэнцэхгүй байна: {exc}") from exc

    await emit(
        db,
        aggregate_type="prepaid_card",
        aggregate_id=card.id,
        event_type=str(EventType.PREPAID_TOPUP),
        payload={
            "card_id": str(card.id),
            "card_no": card.card_no,
            "transaction_id": str(tx.id),
            "amount": str(value),
            "balance_after": str(q2(_dec(card.balance))),
            "method": method,
        },
    )
    await audit(
        db,
        user_id=user.id,
        action="prepaid_card.topup",
        entity_type="prepaid_card",
        entity_id=card.id,
        before=before,
        after={"balance": str(q2(_dec(card.balance))), "amount": str(value), "method": method},
    )
    await db.flush()
    return tx, (entry.id if entry is not None else None)


async def block_card(
    db: AsyncSession, user: User, card: PrepaidCard, *, reason: str | None = None
) -> PrepaidCard:
    """Картыг хаах — цаашид төлбөрт ашиглагдахгүй."""
    if str(card.status) == str(CardStatus.BLOCKED):
        raise HTTPException(status_code=422, detail="Карт аль хэдийн хаагдсан байна")
    if str(card.status) == str(CardStatus.CLOSED):
        raise HTTPException(status_code=422, detail="Карт цуцлагдсан байна")

    before = {"status": str(card.status)}
    card.status = str(CardStatus.BLOCKED)
    await db.flush()

    await emit(
        db,
        aggregate_type="prepaid_card",
        aggregate_id=card.id,
        event_type="PREPAID_CARD_BLOCKED",
        payload={"card_id": str(card.id), "card_no": card.card_no, "reason": reason},
    )
    await audit(
        db,
        user_id=user.id,
        action="prepaid_card.block",
        entity_type="prepaid_card",
        entity_id=card.id,
        before=before,
        after={"status": card.status, "reason": reason},
    )
    return card


async def card_transactions(
    db: AsyncSession, card_id: uuid.UUID, *, limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    total = (
        await db.scalar(
            select(func.count())
            .select_from(PrepaidCardTransaction)
            .where(PrepaidCardTransaction.card_id == card_id)
        )
        or 0
    )
    rows = (
        await db.scalars(
            select(PrepaidCardTransaction)
            .where(PrepaidCardTransaction.card_id == card_id)
            .order_by(PrepaidCardTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {"items": [card_tx_out(tx) for tx in rows], "total": int(total)}
