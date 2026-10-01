"""Өдрийн хаалтын бүрэн засвар — зөвхөн Admin (``shifts.adjust``).

Нягтлангийн засвараас (тушаалт, түлшний зээл нэмэх/устгах, өглөг төлөлт,
зарлага — ``closing_edit_service``) гадна админ хаалтад оруулсан АЛИВАА
утгыг засна:

* зээлийн борлуулалт — харилцагч солих, мөрүүдийг (түлш, литр/дүн, үнэ,
  бараа) бүрэн солих, бараатай зээл нэмэх, устгах;
* тос, барааны борлуулалт — бараа, тоо, үнийг солих, мөр нэмэх/хасах;
* хаалтын миль ба үнийн тэмдэглэл — үнэ өөрчлөгдсөн ч тэмдэглэлгүй хаасан
  ээлжид шинэ үнэ эхэлсэн милийг нөхөж оруулна. Түлшний нэгдсэн (бэлэн)
  борлуулалт ба зээлийн литрийн хуваарилалт сегментээс дахин бодогдоно.

Нөөцийн зарчим:

* Бараа — өөрчлөгдсөн мөрийн анхны зарлагыг ЦУЦАЛНА: анх зарлагадсан
  өртгөөрөө буцааж (``ref_type='closing_edit'``, ``ref_id`` = цуцалсан SALE
  мөр), шинэ мөрийг одоогийн өртгөөр зарлагадна. Нөөцийн үнэлгээ ба 1302
  данс яг таарна; эхний үлдэгдлийн засвар энэ хосыг таньж дахин тоглуулна.
* Түлш — литр зээл ↔ нэгдсэн борлуулалтын хооронд л шилжинэ (сав
  хөдлөхгүй). Хаалтын милийг зассан бол зөрүү литр савнаас зарлагадна
  эсвэл буцаж орно.

Засвар бүрийн дараа төлбөрийн хуваарилалт, журнал, гэрээний үлдэгдэл,
байвал зохих бэлэн мөнгө, кассын зөрүү дахин бодогдоно. Энэ модуль
``db.commit()`` дуудахгүй.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ApprovalStatus,
    ContractStatus,
    EventType,
    InventoryTxType,
    ItemType,
    PaymentMethod,
    ReadingType,
    SaleStatus,
    SaleType,
    ShiftPhase,
    ShiftStatus,
    SourceType,
    TankMovementType,
)
from app.models.accounting import ArInvoice, JournalEntry
from app.models.approval import PriceChange, Refund
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank, TotalizerReading
from app.models.partner import Contract, Customer
from app.models.product import InventoryTransaction, Product
from app.models.sale import Payment, Sale, SaleItem
from app.models.shift import Shift, ShiftClosing, ShiftPriceMark, ShiftTankLevel
from app.models.user import User
from app.money import q2, q3, q6
from app.services import closing_edit_service as ce
from app.services import inventory_service, tank_service
from app.services.audit_service import audit
from app.services.posting import posting
from app.services.sale_service import compute_totals

ZERO = Decimal("0.00")
ZERO_L = Decimal("0.000")
MIN_L = Decimal("0.001")
#: ``opening_fix_service.CLOSING_EDIT_REF``-тэй ижил.
CLOSING_EDIT_REF = "closing_edit"
ADMIN_NOTE = f"{ce.CLOSE_NOTE} — {ce.EDIT_NOTE}"

_d = ce._d
_fmt = ce._fmt


def _liters(value: Decimal) -> str:
    return f"{q3(value):,.3f}"


# --------------------------------------------------------------------------- #
# Хамгаалалт
# --------------------------------------------------------------------------- #
async def _refund_block(db: AsyncSession, sale: Sale) -> None:
    """Буцаалттай борлуулалтын мөрийг солихгүй — буцаалт мөрөө заадаг."""
    exists = await db.scalar(
        select(Refund.id)
        .where(Refund.sale_id == sale.id, Refund.status != str(ApprovalStatus.REJECTED))
        .limit(1)
    )
    if exists:
        raise HTTPException(
            status_code=422,
            detail=f"Борлуулалт №{sale.number}-д буцаалт бүртгэгдсэн — мөрийг нь засах боломжгүй",
        )


async def _invoice_block(db: AsyncSession, sale: Sale) -> None:
    """Нэхэмжлэхэд орсон зээлийн харилцагч, дүнг өөрчлөхгүй (нэхэмжлэх хуучирна)."""
    invoice_no = await db.scalar(
        select(ArInvoice.invoice_no).where(ArInvoice.lines.contains([{"sale_id": str(sale.id)}])).limit(1)
    )
    if invoice_no:
        raise HTTPException(
            status_code=422,
            detail=f"Зээлийн борлуулалт №{sale.number} нэхэмжлэх {invoice_no}-д орсон — засах боломжгүй",
        )


def _is_closing_credit(sale: Sale, closing: ShiftClosing) -> bool:
    """Өдрийн хаалтаар (эсвэл хаалтын засвараар) үүссэн зээл — ПОС-ын биш.

    Хаалтын transaction-ий бүх мөр ижил ``created_at``-тэй; засвараар
    үүссэнийх «Өдрийн хаалт …» тэмдэглэлтэй.
    """
    return sale.created_at == closing.created_at or (sale.note or "").startswith(ce.CLOSE_NOTE)


def _closing_time(closing: ShiftClosing, shift: Shift) -> datetime:
    return closing.created_at or shift.closed_at or datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Борлуулалтын туслахууд
# --------------------------------------------------------------------------- #
async def _new_sale(db: AsyncSession, shift: Shift, closing: ShiftClosing, sale_type: str, note: str) -> Sale:
    sale = Sale(
        branch_id=shift.branch_id,
        shift_id=shift.id,
        cashier_id=shift.opened_by,
        sale_type=sale_type,
        status=str(SaleStatus.COMPLETED),
        subtotal=ZERO,
        vat_amount=ZERO,
        total=ZERO,
        cogs_total=ZERO,
        note=note,
        completed_at=_closing_time(closing, shift),
    )
    db.add(sale)
    await db.flush()
    await db.refresh(sale, ["number", "created_at"])
    return sale


async def _retotal(db: AsyncSession, sale: Sale) -> list[SaleItem]:
    """Мөрүүдээс нийт дүн, НӨАТ, өртөг, төрлийг дахин бодно."""
    await db.flush()
    items = list(
        (await db.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id).order_by(SaleItem.line_no))).all()
    )
    sale.subtotal, sale.vat_amount, sale.total = compute_totals([q2(_d(i.amount)) for i in items])
    sale.cogs_total = q2(sum((q2(_d(i.cogs_amount)) for i in items), ZERO))
    kinds = {str(i.item_type) for i in items}
    if len(kinds) > 1:
        sale.sale_type = str(SaleType.MIXED)
    elif kinds == {str(ItemType.FUEL)}:
        sale.sale_type = str(SaleType.FUEL)
    elif kinds:
        sale.sale_type = str(SaleType.STORE)
    return items


async def _drop_sale(db: AsyncSession, closing: ShiftClosing, sale: Sale) -> None:
    """Хоосон болсон нэгдсэн/тосны борлуулалтыг устгана."""
    from app.models.system import EbarimtQueue  # noqa: PLC0415

    if closing.fuel_sale_id == sale.id:
        closing.fuel_sale_id = None
    if closing.oil_sale_id == sale.id:
        closing.oil_sale_id = None
    await db.flush()
    await posting.reverse(db, event_type=str(EventType.SALE_POSTED), source_type=str(SourceType.SALE), source_id=sale.id)
    # И-баримтын дараалал, мөр, төлбөрийг шууд устгана — борлуулалтаас ӨМНӨ
    # (FK), энэ хүсэлтэд аль хэдийн устгасан мөрүүд каскадад дахин орохгүй.
    await db.execute(delete(EbarimtQueue).where(EbarimtQueue.sale_id == sale.id))
    await db.execute(delete(Payment).where(Payment.sale_id == sale.id))
    await db.execute(delete(SaleItem).where(SaleItem.sale_id == sale.id))
    db.expire(sale, ["items", "payments"])
    await db.delete(sale)
    await db.flush()


async def _backdate_sale_entry(db: AsyncSession, sale: Sale, shift: Shift) -> None:
    entry = await db.scalar(
        select(JournalEntry).where(
            JournalEntry.source_type == str(SourceType.SALE),
            JournalEntry.source_id == sale.id,
            JournalEntry.event_type == str(EventType.SALE_POSTED),
        )
    )
    if entry is not None:
        entry.created_at = ce._inside(shift)


async def _settle(db: AsyncSession, user: User, shift: Shift, closing: ShiftClosing) -> None:
    """Төлбөрийн хуваарилалт (карт/шилжүүлэг → бэлэн), журнал, касс."""
    await db.flush()
    await ce._resplit(
        db,
        shift,
        closing,
        q2(_d(closing.settlement_vat) + _d(closing.settlement_novat)),
        q2(_d(closing.transfer_total)),
    )
    await ce._recalc(db, user, shift)


# --------------------------------------------------------------------------- #
# Үнэ — ээлжийн үеийнх
# --------------------------------------------------------------------------- #
async def _price_at(
    db: AsyncSession,
    shift: Shift,
    *,
    product: Product | None = None,
    fuel: Fuel | None = None,
) -> Decimal:
    """Ээлж хаагдах мөчид мөрдөж байсан үнэ (батлагдсан үнийн өөрчлөлтийн түүхээс).

    Салбарын тусгай үнийн өөрчлөлт байвал түүгээр, үгүй бол суурь үнийн
    өөрчлөлтөөр; түүх огт үгүй бол одоогийн үнэ.
    """
    from app.services.pricing_service import effective_fuel_price, effective_product_price  # noqa: PLC0415

    at = shift.closed_at or datetime.now(UTC)
    cond = PriceChange.product_id == product.id if product is not None else PriceChange.fuel_id == fuel.id
    branch_cond = (
        or_(PriceChange.branch_id == shift.branch_id, PriceChange.branch_id.is_(None))
        if shift.branch_id is not None
        else PriceChange.branch_id.is_(None)
    )
    rows = (
        await db.scalars(
            select(PriceChange)
            .where(
                cond,
                branch_cond,
                PriceChange.status == str(ApprovalStatus.APPROVED),
                PriceChange.applied_at.is_not(None),
            )
            .order_by(PriceChange.applied_at)
        )
    ).all()
    branch_rows = [r for r in rows if r.branch_id is not None]
    use = branch_rows or list(rows)
    before = [r for r in use if r.applied_at <= at]
    if before:
        return q2(_d(before[-1].new_price))
    after = [r for r in use if r.applied_at > at]
    if after:
        return q2(_d(after[0].old_price))
    if product is not None:
        return await effective_product_price(db, product, shift.branch_id)
    return await effective_fuel_price(db, fuel, shift.branch_id)


async def product_price(db: AsyncSession, shift_id: uuid.UUID, product_id: uuid.UUID) -> dict[str, Any]:
    """Барааны мөр нэмэхэд — ээлжийн үеийн үнэ ба одоогийн үнэ."""
    from app.services.pricing_service import effective_product_price  # noqa: PLC0415

    shift, _closing = await ce._load(db, shift_id)
    product = await db.scalar(select(Product).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    return {
        "product_id": product.id,
        "price": await _price_at(db, shift, product=product),
        "current": await effective_product_price(db, product, shift.branch_id),
    }


# --------------------------------------------------------------------------- #
# Барааны нөөц — зарлагадах / цуцлах
# --------------------------------------------------------------------------- #
async def _consume_goods(db: AsyncSession, sale: Sale, product: Product, qty: Decimal) -> tuple[Decimal, Decimal]:
    """Шинэ барааны мөрийг одоогийн (салбарын) өртгөөр зарлагадна."""
    product = await db.scalar(select(Product).where(Product.id == product.id).with_for_update()) or product
    stock = q3(_d(product.stock_qty, ZERO_L))
    if q3(qty) > stock:
        raise HTTPException(
            status_code=422,
            detail=f"{product.name_mn}: үлдэгдэл хүрэлцэхгүй (одоо {_liters(stock)}, хэрэгтэй {_liters(qty)})",
        )
    unit_cost = await inventory_service.branch_unit_cost(db, product, sale.branch_id)
    cogs = await inventory_service.consume_product(
        db, product, q3(qty), ref_type=str(SourceType.SALE), ref_id=sale.id, branch_id=sale.branch_id
    )
    return q6(unit_cost), q2(cogs)


async def _unconsume_goods(db: AsyncSession, sale: Sale, item: SaleItem) -> None:
    """Барааны мөрийн анхны зарлагыг цуцална — анх зарлагадсан өртгөөрөө буцна.

    ``receive_product`` (дундаж хөдөлнө) ашигладаг тул нөөцийн үнэлгээ мөрийн
    өртгөөр яг нэмэгдэж, журналаас хасагдах өртөгтэй тэнцүү.
    """
    cancelled = select(InventoryTransaction.ref_id).where(
        InventoryTransaction.tx_type == str(InventoryTxType.REFUND),
        InventoryTransaction.ref_type == CLOSING_EDIT_REF,
        InventoryTransaction.ref_id.is_not(None),
    )
    tx = await db.scalar(
        select(InventoryTransaction)
        .where(
            InventoryTransaction.tx_type == str(InventoryTxType.SALE),
            InventoryTransaction.ref_id == sale.id,
            InventoryTransaction.product_id == item.product_id,
            InventoryTransaction.qty == -q3(_d(item.qty, ZERO_L)),
            InventoryTransaction.id.not_in(cancelled),
        )
        .order_by(InventoryTransaction.created_at.desc())
        .limit(1)
    )
    if tx is None:
        raise HTTPException(
            status_code=422,
            detail=f"Борлуулалт №{sale.number}: «{item.name_snapshot}» мөрийн нөөцийн бичлэг олдсонгүй — засах боломжгүй",
        )
    product = await db.scalar(select(Product).where(Product.id == item.product_id).with_for_update())
    if product is None:
        raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
    await inventory_service.receive_product(
        db,
        product,
        q3(_d(item.qty, ZERO_L)),
        q6(_d(tx.unit_cost)),
        ref_type=CLOSING_EDIT_REF,
        ref_id=tx.id,
        branch_id=tx.branch_id,
        tx_type=InventoryTxType.REFUND,
    )


def _goods_item(sale: Sale, product: Product, qty: Decimal, price: Decimal, unit_cost: Decimal, cogs: Decimal) -> SaleItem:
    return SaleItem(
        sale_id=sale.id,
        line_no=0,
        item_type=str(ItemType.PRODUCT),
        product_id=product.id,
        name_snapshot=(product.name_mn or "")[:128],
        qty=q3(qty),
        unit_price=q2(price),
        amount=q2(q3(qty) * q2(price)),
        unit_cost=q6(unit_cost),
        cogs_amount=q2(cogs),
        refunded_qty=ZERO_L,
    )


# --------------------------------------------------------------------------- #
# Түлшний сан — нэгдсэн (бэлэн) борлуулалтын мөрүүд
# --------------------------------------------------------------------------- #
@dataclass
class _Piece:
    fuel_id: uuid.UUID | None
    tank_id: uuid.UUID | None
    pump_id: uuid.UUID | None
    nozzle_id: uuid.UUID | None
    name: str
    price: Decimal
    liters: Decimal
    amount: Decimal
    unit_cost: Decimal
    cogs: Decimal


class _Pool:
    """Зээлийн литр энэ сангаас авагдаж, буцахдаа энд нийлнэ (сав хөдлөхгүй)."""

    def __init__(self, db: AsyncSession, shift: Shift, closing: ShiftClosing, sale: Sale | None, items: list[SaleItem]):
        self.db = db
        self.shift = shift
        self.closing = closing
        self.sale = sale
        self.items = items
        self.changed = False

    @classmethod
    async def load(cls, db: AsyncSession, shift: Shift, closing: ShiftClosing) -> _Pool:
        sale = await ce._sale(db, closing.fuel_sale_id)
        items = (await ce._sale_rows(db, sale))[0] if sale is not None else []
        if sale is not None:
            await _refund_block(db, sale)
        return cls(db, shift, closing, sale, items)

    def prices(self, fuel_id: uuid.UUID) -> list[Decimal]:
        out: list[Decimal] = []
        for item in self.items:
            price = q2(_d(item.unit_price))
            if item.fuel_id == fuel_id and q3(_d(item.qty, ZERO_L)) > ZERO_L and price not in out:
                out.append(price)
        return out

    def available(self, fuel_id: uuid.UUID, price: Decimal) -> tuple[Decimal, Decimal]:
        liters = ZERO_L
        amount = ZERO
        for item in self.items:
            if item.fuel_id == fuel_id and q2(_d(item.unit_price)) == price:
                liters = q3(liters + _d(item.qty, ZERO_L))
                amount = q2(amount + _d(item.amount))
        return liters, amount

    def _cut(self, item: SaleItem, take: Decimal, gross: Decimal, cogs: Decimal) -> _Piece:
        item.qty = q3(_d(item.qty, ZERO_L) - take)
        item.amount = q2(_d(item.amount) - gross)
        item.cogs_amount = q2(_d(item.cogs_amount) - cogs)
        self.changed = True
        return _Piece(
            fuel_id=item.fuel_id,
            tank_id=item.tank_id,
            pump_id=item.pump_id,
            nozzle_id=item.nozzle_id,
            name=item.name_snapshot,
            price=q2(_d(item.unit_price)),
            liters=take,
            amount=gross,
            unit_cost=q6(_d(item.unit_cost)),
            cogs=cogs,
        )

    def take(
        self,
        fuel_id: uuid.UUID,
        price: Decimal,
        *,
        liters: Decimal | None = None,
        amount: Decimal | None = None,
        label: str = "Түлш",
    ) -> list[_Piece]:
        """Литр (эсвэл колонкийн дүн)-г ``price`` үнийн мөрүүдээс авна — сүүлээс нь."""
        cands = [
            i
            for i in reversed(self.items)
            if i.fuel_id == fuel_id and q2(_d(i.unit_price)) == price and q3(_d(i.qty, ZERO_L)) > ZERO_L
        ]
        pieces: list[_Piece] = []
        if amount is not None:
            left = q2(amount)
            for item in cands:
                if left <= ZERO:
                    break
                item_qty = q3(_d(item.qty, ZERO_L))
                capacity = q2(_d(item.amount))
                if left >= capacity:
                    take, gross = item_qty, capacity
                else:
                    take = min(max(q3(left / price), MIN_L), item_qty)
                    gross = capacity if take >= item_qty else left
                full = take >= item_qty
                cogs = q2(_d(item.cogs_amount)) if full else q2(take * q6(_d(item.unit_cost)))
                pieces.append(self._cut(item, take, gross, cogs))
                left = q2(left - gross)
            short = left > ZERO
        else:
            need = q3(_d(liters, ZERO_L))
            for item in cands:
                if need <= ZERO_L:
                    break
                item_qty = q3(_d(item.qty, ZERO_L))
                take = min(item_qty, need)
                full = take >= item_qty
                gross = q2(_d(item.amount)) if full else q2(take * price)
                cogs = q2(_d(item.cogs_amount)) if full else q2(take * q6(_d(item.unit_cost)))
                pieces.append(self._cut(item, take, gross, cogs))
                need = q3(need - take)
            short = need > ZERO_L
        if short:
            # Аль хэдийн хассаныг буцааж, ойлгомжтой алдаа өгнө.
            for piece in pieces:
                self._restore(piece)
            have_l, have_a = self.available(fuel_id, price)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{label}: {_fmt(price)}₮ үнээр нэгдсэн (бэлэн) борлуулалтад {_liters(have_l)} л "
                    f"({_fmt(have_a)}₮) л үлдсэн — зээлд хүрэлцэхгүй"
                ),
            )
        return pieces

    def _restore(self, piece: _Piece) -> None:
        target = next(
            (
                i
                for i in self.items
                if i.fuel_id == piece.fuel_id
                and i.tank_id == piece.tank_id
                and i.nozzle_id == piece.nozzle_id
                and q2(_d(i.unit_price)) == piece.price
            ),
            None,
        )
        if target is not None:
            target.qty = q3(_d(target.qty, ZERO_L) + piece.liters)
            target.amount = q2(_d(target.amount) + piece.amount)
            target.cogs_amount = q2(_d(target.cogs_amount) + piece.cogs)

    async def give(self, item: SaleItem) -> None:
        """Зээлийн түлшний мөрийг нэгдсэн борлуулалт руу ЯГ буцаана."""
        price = q2(_d(item.unit_price))
        same = [i for i in self.items if i.fuel_id == item.fuel_id and i.tank_id == item.tank_id and q2(_d(i.unit_price)) == price]
        target = next((i for i in same if i.nozzle_id == item.nozzle_id), None) or (same[0] if same else None)
        self.changed = True
        if target is not None:
            target.qty = q3(_d(target.qty, ZERO_L) + _d(item.qty, ZERO_L))
            target.amount = q2(_d(target.amount) + _d(item.amount))
            target.cogs_amount = q2(_d(target.cogs_amount) + _d(item.cogs_amount))
            return
        if self.sale is None:
            self.sale = await _new_sale(self.db, self.shift, self.closing, str(SaleType.FUEL), ce.CLOSE_NOTE)
            self.closing.fuel_sale_id = self.sale.id
        row = SaleItem(
            sale_id=self.sale.id,
            line_no=max((i.line_no for i in self.items), default=0) + 1,
            item_type=str(ItemType.FUEL),
            fuel_id=item.fuel_id,
            tank_id=item.tank_id,
            pump_id=item.pump_id,
            nozzle_id=item.nozzle_id,
            name_snapshot=item.name_snapshot,
            qty=q3(_d(item.qty, ZERO_L)),
            unit_price=price,
            amount=q2(_d(item.amount)),
            unit_cost=q6(_d(item.unit_cost)),
            cogs_amount=q2(_d(item.cogs_amount)),
            refunded_qty=ZERO_L,
        )
        self.db.add(row)
        self.items.append(row)

    async def finish(self) -> None:
        """Хоосон мөрүүдийг устгаж, нийт дүнг дахин бодно (хоосон бол борлуулалтыг)."""
        if not self.changed or self.sale is None:
            return
        for item in list(self.items):
            if q3(_d(item.qty, ZERO_L)) <= ZERO_L:
                self.items.remove(item)
                if sa_inspect(item).pending:
                    self.db.expunge(item)
                else:
                    await self.db.delete(item)
        for n, item in enumerate(sorted(self.items, key=lambda i: i.line_no), start=1):
            item.line_no = n
        remaining = await _retotal(self.db, self.sale)
        if not remaining:
            await _drop_sale(self.db, self.closing, self.sale)
            self.sale = None


def _merge_pieces(pieces: list[_Piece]) -> list[_Piece]:
    """Нэг сав, хошуу, үнийн хэсгүүдийг нэг мөр болгоно."""
    merged: dict[tuple[Any, Any, Decimal], _Piece] = {}
    for piece in pieces:
        key = (piece.tank_id, piece.nozzle_id, piece.price)
        row = merged.get(key)
        if row is None:
            merged[key] = _Piece(**piece.__dict__)
        else:
            row.liters = q3(row.liters + piece.liters)
            row.amount = q2(row.amount + piece.amount)
            row.cogs = q2(row.cogs + piece.cogs)
    return list(merged.values())


def _fuel_item(sale: Sale, piece: _Piece) -> SaleItem:
    return SaleItem(
        sale_id=sale.id,
        line_no=0,
        item_type=str(ItemType.FUEL),
        fuel_id=piece.fuel_id,
        tank_id=piece.tank_id,
        pump_id=piece.pump_id,
        nozzle_id=piece.nozzle_id,
        name_snapshot=piece.name,
        qty=q3(piece.liters),
        unit_price=q2(piece.price),
        amount=q2(piece.amount),
        unit_cost=q6(piece.unit_cost),
        cogs_amount=q2(piece.cogs),
        refunded_qty=ZERO_L,
    )


# --------------------------------------------------------------------------- #
# Зээлийн борлуулалт — нэмэх, засах, устгах
# --------------------------------------------------------------------------- #
def _item_out(item: SaleItem) -> dict[str, Any]:
    return {
        "name": item.name_snapshot,
        "qty": str(q3(_d(item.qty, ZERO_L))),
        "unit_price": str(q2(_d(item.unit_price))),
        "amount": str(q2(_d(item.amount))),
    }


async def _credit_snapshot(db: AsyncSession, sale: Sale) -> dict[str, Any]:
    items, _ = await ce._sale_rows(db, sale)
    contract = await db.scalar(select(Contract).where(Contract.id == sale.contract_id)) if sale.contract_id else None
    customer = await db.scalar(select(Customer).where(Customer.id == sale.customer_id)) if sale.customer_id else None
    return {
        "sale_id": str(sale.id),
        "number": sale.number,
        "customer": customer.name if customer else "",
        "contract_no": contract.contract_no if contract else "",
        "amount": str(q2(_d(sale.total))),
        "items": [_item_out(i) for i in items],
    }


async def _fuel_name(db: AsyncSession, fuel_id: uuid.UUID) -> str:
    fuel = await db.scalar(select(Fuel).where(Fuel.id == fuel_id))
    return fuel.name_mn if fuel else "Түлш"


async def _rewrite_credit_items(
    db: AsyncSession,
    shift: Shift,
    closing: ShiftClosing,
    credit: Sale,
    specs: list[Any],
    old_items: list[SaleItem],
) -> None:
    """Зээлийн мөрүүдийг ``specs``-ээр бүрэн солино.

    Өөрчлөгдөөгүй мөр (түлш: үнэ+литр+дүн, бараа: бараа+тоо) хэвээр үлдэнэ;
    бусад нь буцаж (түлш — нэгдсэн борлуулалт руу, бараа — нөөцөд цуцлалтаар),
    шинэ мөрүүд авагдана.
    """
    pool = await _Pool.load(db, shift, closing)

    # Үнэ: заасан эсвэл (түлшинд) сангийн ганц үнэ.
    def fuel_price(spec: Any, prices: list[Decimal], label: str) -> Decimal:
        if spec.unit_price is not None:
            return q2(_d(spec.unit_price))
        if len(prices) == 1:
            return prices[0]
        if not prices:
            raise HTTPException(status_code=422, detail=f"{label}: нэгдсэн (бэлэн) борлуулалтад энэ түлш алга")
        listed = " / ".join(f"{_fmt(p)}₮" for p in prices)
        raise HTTPException(status_code=422, detail=f"{label}: энэ ээлжид үнэ өөрчлөгдсөн ({listed}) — аль үнээр авсныг сонгоно уу")

    # 1. Өөрчлөгдөөгүй мөрүүдийг тааруулна.
    kept: dict[int, SaleItem] = {}
    rest = list(old_items)
    for idx, spec in enumerate(specs):
        match: SaleItem | None = None
        for item in rest:
            if spec.product_id is not None:
                if item.product_id == spec.product_id and spec.qty is not None and q3(_d(item.qty, ZERO_L)) == q3(_d(spec.qty)):
                    match = item
            elif (
                spec.fuel_id is not None
                and str(item.item_type) == str(ItemType.FUEL)
                and item.fuel_id == spec.fuel_id
                and spec.qty is not None
                and spec.amount is not None
                and q3(_d(item.qty, ZERO_L)) == q3(_d(spec.qty))
                and q2(_d(item.amount)) == q2(_d(spec.amount))
                and (spec.unit_price is None or q2(_d(spec.unit_price)) == q2(_d(item.unit_price)))
            ):
                match = item
            if match is not None:
                break
        if match is not None:
            kept[idx] = match
            rest.remove(match)

    # 2. Өөрчлөгдсөн хуучин мөрүүдийг буцаана.
    for item in rest:
        if str(item.item_type) == str(ItemType.FUEL):
            await pool.give(item)
        else:
            await _unconsume_goods(db, credit, item)
        await db.delete(item)

    # 3. Шинэ мөрүүд.
    rows: list[SaleItem] = []
    for idx, spec in enumerate(specs):
        if idx in kept:
            item = kept[idx]
            if spec.product_id is not None and spec.unit_price is not None:
                item.unit_price = q2(_d(spec.unit_price))
                item.amount = q2(q3(_d(item.qty, ZERO_L)) * item.unit_price)
            rows.append(item)
            continue
        if spec.fuel_id is not None:
            label = await _fuel_name(db, spec.fuel_id)
            price = fuel_price(spec, pool.prices(spec.fuel_id), label)
            if spec.amount is not None:
                pieces = pool.take(spec.fuel_id, price, amount=q2(_d(spec.amount)), label=label)
            else:
                pieces = pool.take(spec.fuel_id, price, liters=q3(_d(spec.qty)), label=label)
            for piece in _merge_pieces(pieces):
                row = _fuel_item(credit, piece)
                db.add(row)
                rows.append(row)
        else:
            product = await db.scalar(select(Product).where(Product.id == spec.product_id))
            if product is None:
                raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
            qty = q3(_d(spec.qty))
            price = q2(_d(spec.unit_price)) if spec.unit_price is not None else await _price_at(db, shift, product=product)
            unit_cost, cogs = await _consume_goods(db, credit, product, qty)
            row = _goods_item(credit, product, qty, price, unit_cost, cogs)
            db.add(row)
            rows.append(row)
    for n, row in enumerate(rows, start=1):
        row.line_no = n
    await pool.finish()


def _validate_specs(specs: list[Any]) -> None:
    if not specs:
        raise HTTPException(status_code=422, detail="Зээлийн мөр оруулна уу")
    for spec in specs:
        if (spec.fuel_id is None) == (spec.product_id is None):
            raise HTTPException(status_code=422, detail="Мөр бүр түлш эсвэл бараа байна")
        if spec.product_id is not None and (spec.qty is None or _d(spec.qty) <= ZERO):
            raise HTTPException(status_code=422, detail="Барааны тоо 0-ээс их байх ёстой")
        if spec.fuel_id is not None and (spec.qty is None or _d(spec.qty) <= ZERO) and (spec.amount is None or _d(spec.amount) <= ZERO):
            raise HTTPException(status_code=422, detail="Түлшний литр эсвэл дүнг оруулна уу")


async def save_credit(
    db: AsyncSession,
    user: User,
    *,
    shift_id: uuid.UUID,
    sale_id: uuid.UUID | None,
    target: Any | None,
    items: list[Any] | None,
    note: str | None = None,
) -> dict[str, Any]:
    """Зээлийн борлуулалт нэмэх (``sale_id`` хоосон) эсвэл засах.

    ``target`` — харилцагч солих; ``items`` — мөрүүдийг бүрэн солих (түлш,
    бараа холимог байж болно). Аль нэгийг нь л өгч болно.
    """
    shift, closing = await ce._editable(db, shift_id)
    credit: Sale | None = None
    if sale_id is not None:
        credit = next((s for s in await ce._credit_sales(db, shift, closing) if s.id == sale_id), None)
        if credit is None:
            raise HTTPException(status_code=404, detail="Энэ ээлжийн зээлийн борлуулалт олдсонгүй")
        await _refund_block(db, credit)
        await _invoice_block(db, credit)
    if items is not None:
        _validate_specs(items)
    if credit is None and items is None:
        raise HTTPException(status_code=422, detail="Зээлийн мөр оруулна уу")
    if credit is None and target is None:
        raise HTTPException(status_code=422, detail="Харилцагч сонгоно уу")
    if target is None and items is None:
        raise HTTPException(status_code=422, detail="Өөрчлөх зүйлгүй байна")

    old_items: list[SaleItem] = (await ce._sale_rows(db, credit))[0] if credit is not None else []
    if credit is not None and items is not None and not _is_closing_credit(credit, closing):
        raise HTTPException(
            status_code=422,
            detail="Өдрийн турш кассаар бүртгэсэн зээлийн мөрийг энд засахгүй — зөвхөн харилцагчийг нь солино",
        )

    old_contract = (
        await db.scalar(select(Contract).where(Contract.id == credit.contract_id))
        if credit is not None and credit.contract_id
        else None
    )
    contract = await ce._resolve_contract(db, user, shift, target) if target is not None else old_contract
    if contract is None:
        raise HTTPException(status_code=422, detail="Гэрээ олдсонгүй")
    if target is not None and str(contract.status) != str(ContractStatus.ACTIVE):
        raise HTTPException(status_code=422, detail="Гэрээ идэвхгүй байна")

    before = await _credit_snapshot(db, credit) if credit is not None else None
    old_total = q2(_d(credit.total)) if credit is not None else ZERO
    created = credit is None
    if credit is None:
        credit = await _new_sale(db, shift, closing, str(SaleType.FUEL), ADMIN_NOTE)
    elif items is not None and not (credit.note or "").endswith(ce.EDIT_NOTE):
        # Засварласан зээлийг цонхонд «засвар» гэж ялгана.
        credit.note = ADMIN_NOTE if not credit.note else f"{credit.note} · {ce.EDIT_NOTE}"[:500]

    if items is not None:
        await _rewrite_credit_items(db, shift, closing, credit, items, old_items)
    rows = await _retotal(db, credit)
    if not rows:
        raise HTTPException(status_code=422, detail="Зээлийн мөр хоосон болж байна — устгах бол «Устгах»-ыг ашиглана уу")
    new_total = q2(_d(credit.total))

    # Гэрээ, төлбөр.
    if old_contract is not None:
        old_contract.balance = q2(_d(old_contract.balance) - old_total)
    contract.balance = q2(_d(contract.balance) + new_total)
    customer = await db.scalar(select(Customer).where(Customer.id == contract.customer_id))
    if not (customer is not None and customer.credit_unlimited) and q2(_d(contract.credit_limit)) < q2(_d(contract.balance)):
        contract.credit_limit = q2(_d(contract.balance))
    credit.contract_id = contract.id
    credit.customer_id = contract.customer_id
    pays = list((await db.scalars(select(Payment).where(Payment.sale_id == credit.id))).all())
    pay = next((p for p in pays if str(p.method) == str(PaymentMethod.CONTRACT)), None)
    for other in pays:
        if other is not pay:
            await db.delete(other)
    if pay is None:
        db.add(Payment(sale_id=credit.id, method=str(PaymentMethod.CONTRACT), amount=new_total, contract_id=contract.id))
    else:
        pay.amount = new_total
        pay.contract_id = contract.id
    await db.flush()

    await ce._repost_sale(db, credit)
    if created:
        await _backdate_sale_entry(db, credit, shift)
    closing.credit_total = q2(_d(closing.credit_total) + new_total - old_total)
    await _settle(db, user, shift, closing)

    after = await _credit_snapshot(db, credit)
    after["note"] = (note or "").strip() or None
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_credit_added" if created else "shift.closing_credit_edited",
        entity_type="shift",
        entity_id=shift.id,
        before=before,
        after=after,
    )
    return await ce.closing_view(db, shift_id)


async def delete_credit(db: AsyncSession, user: User, *, shift_id: uuid.UUID, sale_id: uuid.UUID) -> dict[str, Any]:
    """Зээлийн борлуулалтыг (бараатай ч) устгана: түлш нэгдсэн борлуулалт руу,
    бараа нөөцөд (цуцлалтаар) буцна."""
    from app.models.system import EbarimtQueue  # noqa: PLC0415

    shift, closing = await ce._editable(db, shift_id)
    credit = next((s for s in await ce._credit_sales(db, shift, closing) if s.id == sale_id), None)
    if credit is None:
        raise HTTPException(status_code=404, detail="Энэ ээлжийн зээлийн борлуулалт олдсонгүй")
    await _refund_block(db, credit)
    await _invoice_block(db, credit)
    items, _ = await ce._sale_rows(db, credit)
    if any(str(i.item_type) == str(ItemType.FUEL) for i in items) and not _is_closing_credit(credit, closing):
        raise HTTPException(status_code=422, detail="Өдрийн турш кассаар бүртгэсэн зээлийн борлуулалтыг энд устгахгүй")
    before = await _credit_snapshot(db, credit)

    pool = await _Pool.load(db, shift, closing)
    for item in items:
        if str(item.item_type) == str(ItemType.FUEL):
            await pool.give(item)
        else:
            await _unconsume_goods(db, credit, item)
    await pool.finish()

    contract = await db.scalar(select(Contract).where(Contract.id == credit.contract_id)) if credit.contract_id else None
    total = q2(_d(credit.total))
    if contract is not None:
        contract.balance = q2(_d(contract.balance) - total)
    await posting.reverse(db, event_type=str(EventType.SALE_POSTED), source_type=str(SourceType.SALE), source_id=credit.id)
    await db.flush()
    await db.execute(delete(EbarimtQueue).where(EbarimtQueue.sale_id == credit.id))
    await db.execute(delete(Payment).where(Payment.sale_id == credit.id))
    await db.execute(delete(SaleItem).where(SaleItem.sale_id == credit.id))
    db.expire(credit, ["items", "payments"])
    await db.delete(credit)
    await db.flush()
    closing.credit_total = q2(_d(closing.credit_total) - total)
    await _settle(db, user, shift, closing)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_credit_removed",
        entity_type="shift",
        entity_id=shift.id,
        before=before,
    )
    return await ce.closing_view(db, shift_id)


# --------------------------------------------------------------------------- #
# Тос, барааны борлуулалт
# --------------------------------------------------------------------------- #
async def set_oil_lines(
    db: AsyncSession, user: User, *, shift_id: uuid.UUID, lines: list[Any], note: str | None = None
) -> dict[str, Any]:
    """Тос, барааны борлуулалтын мөрүүдийг бүрэн солино (хоосон бол устгана)."""
    shift, closing = await ce._editable(db, shift_id)
    oil = await ce._sale(db, closing.oil_sale_id)
    if oil is not None:
        await _refund_block(db, oil)
    old_items = (await ce._sale_rows(db, oil))[0] if oil is not None else []
    before = {"amount": str(q2(_d(closing.oil_total))), "items": [_item_out(i) for i in old_items]}

    specs: list[tuple[Product, Decimal, Decimal]] = []
    for line in lines:
        product = await db.scalar(select(Product).where(Product.id == line.product_id))
        if product is None:
            raise HTTPException(status_code=404, detail="Бараа олдсонгүй")
        qty = q3(_d(line.qty))
        if qty <= ZERO_L:
            raise HTTPException(status_code=422, detail="Барааны тоо 0-ээс их байх ёстой")
        price = q2(_d(line.unit_price)) if line.unit_price is not None else await _price_at(db, shift, product=product)
        specs.append((product, qty, price))

    kept: dict[int, SaleItem] = {}
    rest = list(old_items)
    for idx, (product, qty, _price) in enumerate(specs):
        match = next((i for i in rest if i.product_id == product.id and q3(_d(i.qty, ZERO_L)) == qty), None)
        if match is not None:
            kept[idx] = match
            rest.remove(match)

    if specs and oil is None:
        oil = await _new_sale(db, shift, closing, str(SaleType.STORE), ADMIN_NOTE)
        closing.oil_sale_id = oil.id
    for item in rest:
        await _unconsume_goods(db, oil, item)
        await db.delete(item)
    rows: list[SaleItem] = []
    for idx, (product, qty, price) in enumerate(specs):
        if idx in kept:
            item = kept[idx]
            item.unit_price = price
            item.amount = q2(qty * price)
            rows.append(item)
            continue
        unit_cost, cogs = await _consume_goods(db, oil, product, qty)
        item = _goods_item(oil, product, qty, price, unit_cost, cogs)
        db.add(item)
        rows.append(item)
    for n, item in enumerate(rows, start=1):
        item.line_no = n

    if oil is not None:
        remaining = await _retotal(db, oil)
        if not remaining:
            await _drop_sale(db, closing, oil)
            oil = None
    closing.oil_total = q2(_d(oil.total)) if oil is not None else ZERO
    await _settle(db, user, shift, closing)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_oil_edited",
        entity_type="shift",
        entity_id=shift.id,
        before=before,
        after={
            "amount": str(closing.oil_total),
            "items": [_item_out(i) for i in rows],
            "note": (note or "").strip() or None,
        },
    )
    return await ce.closing_view(db, shift_id)


# --------------------------------------------------------------------------- #
# Үнийн өөрчлөлтийн сануулга — тэмдэглэлгүй хаасан ээлж
# --------------------------------------------------------------------------- #
async def price_hint_map(db: AsyncSession, shifts: list[Shift]) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Ээлжийн хугацаанд түлшний үнэ батлагдсан ч зарим хошуунд тэмдэглэл алга.

    Тэмдэглэлгүй бол шинэ үнээр түгээсэн литр хуучин үнээр бодогдож, зөрүү нь
    кассын дутагдал/илүүдэл болж харагддаг. Хошуу бүрийн мөрдсөн үнүүд
    (нээлтийн үнэ + тэмдэглэлүүд)-д өөрчлөлтийн шинэ үнэ алга бол сануулна.
    """
    closed = [s for s in shifts if s.closed_at is not None]
    if not closed:
        return {}
    ids = [s.id for s in closed]
    readings = (
        await db.execute(
            select(
                TotalizerReading.shift_id,
                TotalizerReading.nozzle_id,
                TotalizerReading.price_per_liter,
                TotalizerReading.reading,
                TotalizerReading.reading_type,
            ).where(
                TotalizerReading.shift_id.in_(ids),
                TotalizerReading.reading_type.in_([str(ReadingType.SHIFT_OPEN), str(ReadingType.SHIFT_CLOSE)]),
            )
        )
    ).all()
    closes = {(r[0], r[1]): q3(_d(r[3], ZERO_L)) for r in readings if str(r[4]) == str(ReadingType.SHIFT_CLOSE)}
    # Ээлжид огт түгээгээгүй хошуу (нээлт = хаалт) — үнийн тэмдэглэл хэрэггүй.
    opens = [
        (r[0], r[1], r[2])
        for r in readings
        if str(r[4]) == str(ReadingType.SHIFT_OPEN) and closes.get((r[0], r[1])) != q3(_d(r[3], ZERO_L))
    ]
    if not opens:
        return {}
    marks = (await db.scalars(select(ShiftPriceMark).where(ShiftPriceMark.shift_id.in_(ids)))).all()
    nozzle_ids = {row[1] for row in opens}
    nozzles = {n.id: n for n in (await db.scalars(select(PumpNozzle).where(PumpNozzle.id.in_(nozzle_ids)))).all()}
    pumps = {
        p.id: p
        for p in (await db.scalars(select(Pump).where(Pump.id.in_({n.pump_id for n in nozzles.values()})))).all()
    } if nozzles else {}
    fuel_ids = {n.fuel_id for n in nozzles.values()}
    fuels = {f.id: f for f in (await db.scalars(select(Fuel).where(Fuel.id.in_(fuel_ids)))).all()} if fuel_ids else {}
    start = min(s.opened_at for s in closed)
    end = max(s.closed_at for s in closed)
    changes = (
        await db.scalars(
            select(PriceChange)
            .where(
                PriceChange.fuel_id.in_(fuel_ids),
                PriceChange.status == str(ApprovalStatus.APPROVED),
                PriceChange.applied_at.is_not(None),
                PriceChange.applied_at > start,
                PriceChange.applied_at <= end,
            )
            .order_by(PriceChange.applied_at)
        )
    ).all() if fuel_ids else []
    if not changes:
        return {}

    used: dict[tuple[uuid.UUID, uuid.UUID], set[Decimal]] = {}
    by_fuel: dict[uuid.UUID, dict[uuid.UUID, list[uuid.UUID]]] = {}
    for shift_id, nozzle_id, price in opens:
        nozzle = nozzles.get(nozzle_id)
        if nozzle is None:
            continue
        used.setdefault((shift_id, nozzle_id), set()).add(q2(_d(price)))
        by_fuel.setdefault(shift_id, {}).setdefault(nozzle.fuel_id, []).append(nozzle_id)
    for mark in marks:
        used.setdefault((mark.shift_id, mark.nozzle_id), set()).add(q2(_d(mark.new_price)))

    out: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for shift in closed:
        fuels_here = by_fuel.get(shift.id, {})
        hints: list[dict[str, Any]] = []
        for change in changes:
            group = fuels_here.get(change.fuel_id)
            if not group or not (shift.opened_at < change.applied_at <= shift.closed_at):
                continue
            if change.branch_id is not None and change.branch_id != shift.branch_id:
                continue
            seen = set().union(*(used.get((shift.id, n), set()) for n in group))
            if change.branch_id is None and shift.branch_id is not None and q2(_d(change.old_price)) not in seen:
                # Салбар тусгай үнээр явж байсан — суурь үнийн өөрчлөлт хамаарахгүй.
                continue
            new_price = q2(_d(change.new_price))
            missing = [n for n in group if new_price not in used.get((shift.id, n), set())]
            if not missing:
                continue
            fuel = fuels.get(change.fuel_id)
            hints.append(
                {
                    "fuel_id": change.fuel_id,
                    "fuel_name": fuel.name_mn if fuel else "",
                    "old_price": q2(_d(change.old_price)),
                    "new_price": new_price,
                    "applied_at": change.applied_at,
                    "nozzles": [
                        {
                            "nozzle_id": n,
                            "label": f"{pumps[nozzles[n].pump_id].name if nozzles[n].pump_id in pumps else ''} · "
                            f"хошуу {nozzles[n].nozzle_number}",
                        }
                        for n in missing
                    ],
                }
            )
        if hints:
            out[shift.id] = hints
    return out


# --------------------------------------------------------------------------- #
# Хаалтын миль ба үнийн тэмдэглэл
# --------------------------------------------------------------------------- #
@dataclass
class _MarkIn:
    nozzle_id: uuid.UUID
    reading: Decimal
    new_price: Decimal
    old_price: Decimal = ZERO


@dataclass
class _Alloc:
    sale: Sale
    item: SaleItem
    old_price: Decimal
    price: Decimal
    liters: Decimal
    amount: Decimal
    pieces: list[_Piece] = field(default_factory=list)


@dataclass
class _FuelPlan:
    shift: Shift
    closing: ShiftClosing
    fuel_sale: Sale | None
    closes: dict[uuid.UUID, TotalizerReading]
    old_close: dict[uuid.UUID, Decimal]
    new_close: dict[uuid.UUID, Decimal]
    marks: list[_MarkIn]
    calcs_old: list[Any]
    calcs_new: list[Any]
    nozzles: dict[uuid.UUID, PumpNozzle]
    labels: dict[uuid.UUID, str]
    allocs: list[_Alloc]
    fuel_rows: list[_Piece]
    tank_delta: dict[uuid.UUID, Decimal]
    tank_cogs_delta: dict[uuid.UUID, Decimal]
    errors: list[str]
    credit_names: dict[uuid.UUID, str]

    @property
    def mile_total(self) -> Decimal:
        return q2(sum((c.amount for c in self.calcs_new), ZERO))

    @property
    def fuel_sale_total(self) -> Decimal:
        return q2(sum((r.amount for r in self.fuel_rows), ZERO))


async def _nozzle_labels(db: AsyncSession, nozzle_ids: set[uuid.UUID]) -> tuple[dict[uuid.UUID, PumpNozzle], dict[uuid.UUID, str]]:
    nozzles = (
        {n.id: n for n in (await db.scalars(select(PumpNozzle).where(PumpNozzle.id.in_(nozzle_ids)))).all()}
        if nozzle_ids
        else {}
    )
    pumps = (
        {p.id: p for p in (await db.scalars(select(Pump).where(Pump.id.in_({n.pump_id for n in nozzles.values()})))).all()}
        if nozzles
        else {}
    )
    labels = {
        n.id: f"{pumps[n.pump_id].name if n.pump_id in pumps else ''} · хошуу {n.nozzle_number}".strip(" ·")
        for n in nozzles.values()
    }
    return nozzles, labels


def _take_exact(slots: Any, fuel_id: uuid.UUID, price: Decimal, liters: Decimal, amount: Decimal) -> list[_Piece] | None:
    """Зээлийн мөрийн ЯГ литр, дүнг ``price`` үнийн сегментүүдээс авна (сүүлээс нь).

    Хүрэлцэхгүй бол ``None`` (сегментүүд хөндөгдөхгүй).
    """
    cands = [
        slot
        for slot in reversed(slots.slots)
        if slot["calc"].nozzle.fuel_id == fuel_id and slot["seg"].price == price and slot["remaining"] > ZERO_L
    ]
    need = q3(liters)
    parts: list[tuple[dict[str, Any], Decimal]] = []
    for slot in cands:
        if need <= ZERO_L:
            break
        take = min(slot["remaining"], need)
        parts.append((slot, take))
        need = q3(need - take)
    if need > ZERO_L:
        return None
    pieces: list[_Piece] = []
    acc = ZERO
    for i, (slot, take) in enumerate(parts):
        last = i == len(parts) - 1
        full = take >= slot["remaining"]
        piece_amount = q2(amount - acc) if last else (slot["remaining_amount"] if full else q2(take * price))
        acc = q2(acc + piece_amount)
        slot["remaining"] = q3(slot["remaining"] - take)
        slot["remaining_amount"] = q2(slot["remaining_amount"] - piece_amount)
        nozzle = slot["calc"].nozzle
        pieces.append(
            _Piece(
                fuel_id=nozzle.fuel_id,
                tank_id=nozzle.tank_id,
                pump_id=nozzle.pump_id,
                nozzle_id=nozzle.id,
                name=nozzle.fuel.name_mn if nozzle.fuel is not None else "Түлш",
                price=price,
                liters=take,
                amount=piece_amount,
                unit_cost=ZERO,
                cogs=ZERO,
            )
        )
    return pieces


def _alloc_unchanged(alloc: _Alloc) -> bool:
    """Зээлийн мөр шинэ хуваарилалтаар ч яг хэвээр (сав, үнэ, литр, дүн, өртөг)."""
    item = alloc.item
    return (
        bool(alloc.pieces)
        and {p.tank_id for p in alloc.pieces} == {item.tank_id}
        and alloc.price == q2(_d(item.unit_price))
        and q3(sum((p.liters for p in alloc.pieces), ZERO_L)) == q3(_d(item.qty, ZERO_L))
        and q2(sum((p.amount for p in alloc.pieces), ZERO)) == q2(_d(item.amount))
        and q2(sum((p.cogs for p in alloc.pieces), ZERO)) == q2(_d(item.cogs_amount))
    )


def _merge_by_tank(pieces: list[_Piece]) -> list[_Piece]:
    """Зээлийн мөр — нэг сав, нэг үнэ нэг мөр (өдрийн хаалтын дүрэмтэй ижил)."""
    merged: dict[tuple[Any, Decimal], _Piece] = {}
    for piece in pieces:
        key = (piece.tank_id, piece.price)
        row = merged.get(key)
        if row is None:
            merged[key] = _Piece(**piece.__dict__)
            continue
        row.liters = q3(row.liters + piece.liters)
        row.amount = q2(row.amount + piece.amount)
        row.cogs = q2(row.cogs + piece.cogs)
        if row.nozzle_id != piece.nozzle_id:
            row.nozzle_id = None
        if row.pump_id != piece.pump_id:
            row.pump_id = None
    for row in merged.values():
        row.unit_cost = q6(row.cogs / row.liters) if row.liters > ZERO_L else row.unit_cost
    return list(merged.values())


def _available(slots: Any, fuel_id: uuid.UUID, price: Decimal) -> Decimal:
    return q3(
        sum(
            (s["remaining"] for s in slots.slots if s["calc"].nozzle.fuel_id == fuel_id and s["seg"].price == price),
            ZERO_L,
        )
    )


async def _fuel_plan(
    db: AsyncSession,
    shift: Shift,
    closing: ShiftClosing,
    *,
    readings: list[Any] | None,
    marks: list[Any] | None,
    credit_prices: dict[uuid.UUID, Decimal] | None,
) -> _FuelPlan:
    from app.services import attendant_service  # noqa: PLC0415

    open_rows = {
        r.nozzle_id: r
        for r in (
            await db.scalars(
                select(TotalizerReading).where(
                    TotalizerReading.shift_id == shift.id,
                    TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
                )
            )
        ).all()
    }
    closes = {
        r.nozzle_id: r
        for r in (
            await db.scalars(
                select(TotalizerReading).where(
                    TotalizerReading.shift_id == shift.id,
                    TotalizerReading.reading_type == str(ReadingType.SHIFT_CLOSE),
                )
            )
        ).all()
    }
    if not closes or not open_rows:
        raise HTTPException(status_code=422, detail="Энэ хаалтад хошууны миль бүртгэгдээгүй байна")
    nozzles, labels = await _nozzle_labels(db, set(open_rows) | set(closes))
    old_close = {n: q3(_d(r.reading, ZERO_L)) for n, r in closes.items()}
    new_close = dict(old_close)
    for row in readings or []:
        if row.nozzle_id not in closes:
            raise HTTPException(status_code=422, detail="Энэ ээлжид хаалтын миль бүртгэгдээгүй хошуу байна")
        new_close[row.nozzle_id] = q3(_d(row.reading, ZERO_L))

    # Үнийн тэмдэглэлүүд — өгөөгүй бол одоогийнх.
    if marks is None:
        mark_list = [
            _MarkIn(m.nozzle_id, q3(_d(m.reading, ZERO_L)), q2(_d(m.new_price)), q2(_d(m.old_price)))
            for m in (await db.scalars(select(ShiftPriceMark).where(ShiftPriceMark.shift_id == shift.id))).all()
        ]
    else:
        mark_list = [_MarkIn(m.nozzle_id, q3(_d(m.reading, ZERO_L)), q2(_d(m.new_price))) for m in marks]
    seen: set[tuple[uuid.UUID, Decimal]] = set()
    for mark in mark_list:
        label = labels.get(mark.nozzle_id, "Хошуу")
        opened = open_rows.get(mark.nozzle_id)
        if opened is None or mark.nozzle_id not in new_close:
            raise HTTPException(status_code=422, detail=f"{label}: энэ ээлжид нээлтийн миль алга")
        low = q3(_d(opened.reading, ZERO_L))
        high = new_close[mark.nozzle_id]
        if not (low <= mark.reading <= high):
            raise HTTPException(
                status_code=422,
                detail=f"{label}: үнийн тэмдэглэлийн миль {_liters(mark.reading)} нь нээлт {_liters(low)} – хаалт {_liters(high)} хооронд байх ёстой",
            )
        if mark.new_price <= ZERO:
            raise HTTPException(status_code=422, detail=f"{label}: шинэ үнэ 0-ээс их байх ёстой")
        key = (mark.nozzle_id, mark.reading)
        if key in seen:
            raise HTTPException(status_code=422, detail=f"{label}: нэг миль дээр хоёр тэмдэглэл байна")
        seen.add(key)
    # Хуучин үнэ — хошуу бүрд нээлтийн үнэ → өмнөх тэмдэглэлийн шинэ үнэ.
    for nozzle_id in {m.nozzle_id for m in mark_list}:
        opened = open_rows[nozzle_id]
        prev = q2(_d(opened.price_per_liter))
        if prev <= ZERO:
            nozzle = nozzles.get(nozzle_id)
            fuel = nozzle.fuel if nozzle is not None else None
            prev = await _price_at(db, shift, fuel=fuel) if fuel is not None else ZERO
        for mark in sorted((m for m in mark_list if m.nozzle_id == nozzle_id), key=lambda m: m.reading):
            mark.old_price = prev
            prev = mark.new_price

    calcs_old = await attendant_service.compute_dispensed(db, shift, old_close)
    calcs_new = await attendant_service.compute_dispensed(db, shift, new_close, marks=mark_list)

    # Хаалтын милийн өөрчлөлт → савны зөрүү литр.
    tank_delta: dict[uuid.UUID, Decimal] = {}
    for nozzle_id, value in new_close.items():
        delta = q3(value - old_close[nozzle_id])
        if delta == ZERO_L:
            continue
        nozzle = nozzles.get(nozzle_id)
        if nozzle is None:
            continue
        tank_delta[nozzle.tank_id] = q3(tank_delta.get(nozzle.tank_id, ZERO_L) + delta)
    tank_delta = {k: v for k, v in tank_delta.items() if v != ZERO_L}
    if tank_delta:
        dipped = (
            await db.scalars(
                select(ShiftTankLevel.tank_id).where(
                    ShiftTankLevel.shift_id == shift.id,
                    ShiftTankLevel.phase == str(ShiftPhase.CLOSE),
                    ShiftTankLevel.tank_id.in_(list(tank_delta)),
                )
            )
        ).all()
        if dipped:
            raise HTTPException(
                status_code=422,
                detail="Хаалтад савны хэмжилт хийсэн савны хошууны милийг засах боломжгүй (савны зөрүү дахин бодогдохгүй)",
            )

    # Зээлийн литрийг шинэ сегментүүдээс хуваарилна.
    fuel_names = {c.nozzle.fuel_id: c.nozzle.fuel.name_mn for c in calcs_new if c.nozzle.fuel is not None}
    slots = attendant_service._SegmentSlots(calcs_new, fuel_names)
    credit_prices = credit_prices or {}
    allocs: list[_Alloc] = []
    errors: list[str] = []
    credit_names: dict[uuid.UUID, str] = {}
    for sale in await ce._credit_sales(db, shift, closing):
        if not _is_closing_credit(sale, closing):
            continue
        customer = await db.scalar(select(Customer).where(Customer.id == sale.customer_id)) if sale.customer_id else None
        credit_names[sale.id] = customer.name if customer else ""
        items, _ = await ce._sale_rows(db, sale)
        for item in items:
            if str(item.item_type) != str(ItemType.FUEL) or item.fuel_id is None:
                continue
            old_price = q2(_d(item.unit_price))
            price = q2(_d(credit_prices.get(item.id, old_price)))
            liters = q3(_d(item.qty, ZERO_L))
            amount = q2(_d(item.amount)) if price == old_price else q2(liters * price)
            pieces = _take_exact(slots, item.fuel_id, price, liters, amount)
            if pieces is None:
                have = _available(slots, item.fuel_id, price)
                errors.append(
                    f"Зээл №{sale.number} ({credit_names[sale.id]}): {fuel_names.get(item.fuel_id, 'Түлш')} "
                    f"{_liters(liters)} л {_fmt(price)}₮ үнээр — тэр үнээр түгээсэн литр хүрэлцэхгүй "
                    f"({_liters(have)} л үлдсэн). Тэмдэглэлийн миль эсвэл энэ зээлийн үнийг шалгана уу."
                )
                pieces = []
            allocs.append(_Alloc(sale, item, old_price, price, liters, amount, pieces))

    # Үлдсэн сегментүүд → нэгдсэн (бэлэн) борлуулалт. Литргүй болсон сегментийн
    # дугуйлалтын үлдэгдлийг ижил үнийн өөр сегментэд шилжүүлнэ.
    for slot in slots.slots:
        if slot["remaining"] <= ZERO_L and slot["remaining_amount"] != ZERO:
            fuel_id = slot["calc"].nozzle.fuel_id
            price = slot["seg"].price
            peer = next(
                (
                    s
                    for s in reversed(slots.slots)
                    if s["calc"].nozzle.fuel_id == fuel_id and s["seg"].price == price and s["remaining"] > ZERO_L
                ),
                None,
            )
            if peer is not None:
                peer["remaining_amount"] = q2(peer["remaining_amount"] + slot["remaining_amount"])
            slot["remaining_amount"] = ZERO
    fuel_rows: list[_Piece] = []
    for slot in slots.slots:
        if slot["remaining"] <= ZERO_L:
            continue
        nozzle = slot["calc"].nozzle
        fuel_rows.append(
            _Piece(
                fuel_id=nozzle.fuel_id,
                tank_id=nozzle.tank_id,
                pump_id=nozzle.pump_id,
                nozzle_id=nozzle.id,
                name=nozzle.fuel.name_mn if nozzle.fuel is not None else "Түлш",
                price=slot["seg"].price,
                liters=slot["remaining"],
                amount=q2(slot["remaining_amount"]),
                unit_cost=ZERO,
                cogs=ZERO,
            )
        )

    # Өртөг — сав бүрийн нийт өртөг хадгалагдана (милийн өөрчлөлтийн зөрүүтэй).
    fuel_sale = await ce._sale(db, closing.fuel_sale_id)
    tank_cogs: dict[uuid.UUID, Decimal] = {}
    tank_liters: dict[uuid.UUID, Decimal] = {}
    current = list((await ce._sale_rows(db, fuel_sale))[0]) if fuel_sale is not None else []
    current += [a.item for a in allocs]
    for item in current:
        if str(item.item_type) != str(ItemType.FUEL) or item.tank_id is None:
            continue
        tank_cogs[item.tank_id] = q2(tank_cogs.get(item.tank_id, ZERO) + _d(item.cogs_amount))
        tank_liters[item.tank_id] = q3(tank_liters.get(item.tank_id, ZERO_L) + _d(item.qty, ZERO_L))
    tanks = (
        {t.id: t for t in (await db.scalars(select(Tank).where(Tank.id.in_(set(tank_cogs) | set(tank_delta))))).all()}
        if (tank_cogs or tank_delta)
        else {}
    )
    unit_cost: dict[uuid.UUID, Decimal] = {}
    for tank_id in set(tank_cogs) | set(tank_delta):
        liters = tank_liters.get(tank_id, ZERO_L)
        tank = tanks.get(tank_id)
        unit_cost[tank_id] = (
            q6(tank_cogs[tank_id] / liters) if liters > ZERO_L else q6(_d(tank.avg_cost if tank else ZERO))
        )
    tank_cogs_delta: dict[uuid.UUID, Decimal] = {}
    for tank_id, delta in tank_delta.items():
        tank = tanks.get(tank_id)
        if delta > ZERO_L:
            tank_cogs_delta[tank_id] = q2(delta * q6(_d(tank.avg_cost if tank else ZERO)))
        else:
            tank_cogs_delta[tank_id] = -q2(-delta * unit_cost[tank_id])
    new_cogs = {t: q2(tank_cogs.get(t, ZERO) + tank_cogs_delta.get(t, ZERO)) for t in set(tank_cogs) | set(tank_delta)}

    # Зээлийн хэсэг — сав, литр нь өөрчлөгдөөгүй бол хуучин өртгөө хадгална.
    credit_cogs: dict[uuid.UUID, Decimal] = {}
    for alloc in allocs:
        item_liters = q3(_d(alloc.item.qty, ZERO_L))
        keep = (
            bool(alloc.pieces)
            and all(p.tank_id == alloc.item.tank_id for p in alloc.pieces)
            and q3(sum((p.liters for p in alloc.pieces), ZERO_L)) == item_liters
        )
        item_cogs = q2(_d(alloc.item.cogs_amount))
        acc = ZERO
        for i, piece in enumerate(alloc.pieces):
            if keep:
                piece.unit_cost = q6(_d(alloc.item.unit_cost))
                last = i == len(alloc.pieces) - 1
                piece.cogs = q2(item_cogs - acc) if last else q2(item_cogs * piece.liters / item_liters)
                acc = q2(acc + piece.cogs)
            else:
                piece.unit_cost = unit_cost.get(piece.tank_id, ZERO)
                piece.cogs = q2(piece.liters * piece.unit_cost)
            credit_cogs[piece.tank_id] = q2(credit_cogs.get(piece.tank_id, ZERO) + piece.cogs)
    # Нэгдсэн борлуулалт — савны үлдсэн өртгийг литрээр нь хуваана (сүүлийнх үлдэгдлийг авна).
    for tank_id in {r.tank_id for r in fuel_rows}:
        rows = [r for r in fuel_rows if r.tank_id == tank_id]
        share = q2(new_cogs.get(tank_id, ZERO) - credit_cogs.get(tank_id, ZERO))
        total_l = q3(sum((r.liters for r in rows), ZERO_L))
        acc = ZERO
        for i, row in enumerate(rows):
            if i == len(rows) - 1:
                row.cogs = q2(share - acc)
            else:
                row.cogs = q2(share * row.liters / total_l) if total_l > ZERO_L else ZERO
            acc = q2(acc + row.cogs)
            row.unit_cost = q6(row.cogs / row.liters) if row.liters > ZERO_L else ZERO
    # Нэгдсэн борлуулалтгүй сав — үлдэгдлийг тухайн савны сүүлийн зээлийн хэсэгт.
    for tank_id in set(new_cogs) - {r.tank_id for r in fuel_rows}:
        rest = q2(new_cogs[tank_id] - credit_cogs.get(tank_id, ZERO))
        if rest == ZERO:
            continue
        holder = next((p for a in reversed(allocs) for p in reversed(a.pieces) if p.tank_id == tank_id), None)
        if holder is not None:
            holder.cogs = q2(holder.cogs + rest)

    return _FuelPlan(
        shift=shift,
        closing=closing,
        fuel_sale=fuel_sale,
        closes=closes,
        old_close=old_close,
        new_close=new_close,
        marks=mark_list,
        calcs_old=calcs_old,
        calcs_new=calcs_new,
        nozzles=nozzles,
        labels=labels,
        allocs=allocs,
        fuel_rows=fuel_rows,
        tank_delta=tank_delta,
        tank_cogs_delta=tank_cogs_delta,
        errors=errors,
        credit_names=credit_names,
    )


def _segments(calc: Any) -> list[dict[str, Any]]:
    return [{"liters": s.liters, "price": s.price, "amount": s.amount} for s in calc.segments]


async def fuel_preview(
    db: AsyncSession,
    *,
    shift_id: uuid.UUID,
    readings: list[Any] | None,
    marks: list[Any] | None,
    credit_prices: dict[uuid.UUID, Decimal] | None,
) -> dict[str, Any]:
    """Миль/үнийн тэмдэглэлийн засварын урьдчилсан тооцоо (юу ч бичихгүй)."""
    shift, closing = await ce._load(db, shift_id)
    plan = await _fuel_plan(db, shift, closing, readings=readings, marks=marks, credit_prices=credit_prices)
    view = await ce.closing_view(db, shift_id)
    old_fuel_sale = q2(_d(plan.fuel_sale.total)) if plan.fuel_sale is not None else ZERO
    delta = q2(plan.fuel_sale_total - old_fuel_sale)
    old_by = {c.nozzle.id: c for c in plan.calcs_old}
    nozzle_rows = []
    for calc in plan.calcs_new:
        old = old_by.get(calc.nozzle.id)
        nozzle_rows.append(
            {
                "nozzle_id": calc.nozzle.id,
                "label": plan.labels.get(calc.nozzle.id, ""),
                "fuel_name": calc.nozzle.fuel.name_mn if calc.nozzle.fuel is not None else "",
                "open_reading": calc.open_reading,
                "old_close": plan.old_close.get(calc.nozzle.id),
                "close_reading": calc.close_reading,
                "old_amount": old.amount if old is not None else ZERO,
                "amount": calc.amount,
                "segments": _segments(calc),
            }
        )
    prices_by_fuel: dict[uuid.UUID, list[Decimal]] = {}
    for calc in plan.calcs_new:
        for seg in calc.segments:
            row = prices_by_fuel.setdefault(calc.nozzle.fuel_id, [])
            if seg.liters > ZERO_L and seg.price not in row:
                row.append(seg.price)
    credit_items = [
        {
            "item_id": a.item.id,
            "sale_id": a.sale.id,
            "number": a.sale.number,
            "customer": plan.credit_names.get(a.sale.id, ""),
            "fuel_id": a.item.fuel_id,
            "fuel_name": a.item.name_snapshot,
            "liters": a.liters,
            "old_price": a.old_price,
            "price": a.price,
            "old_amount": q2(_d(a.item.amount)),
            "amount": a.amount,
            "prices": prices_by_fuel.get(a.item.fuel_id, []),
            "ok": bool(a.pieces) or a.liters <= ZERO_L,
        }
        for a in plan.allocs
    ]
    tank_names = {
        t.id: t.name
        for t in (await db.scalars(select(Tank).where(Tank.id.in_(list(plan.tank_delta))))).all()
    } if plan.tank_delta else {}
    return {
        "fuel_total": {"old": q2(_d(closing.fuel_total)), "new": plan.mile_total},
        "fuel_sale_total": {"old": old_fuel_sale, "new": plan.fuel_sale_total},
        "credit_total": {
            "old": q2(_d(closing.credit_total)),
            "new": q2(_d(closing.credit_total) + sum((a.amount - q2(_d(a.item.amount)) for a in plan.allocs), ZERO)),
        },
        "must": {"old": view["must"], "new": q2(view["must"] + delta)},
        "diff": {"old": view["diff"], "new": q2(view["diff"] - delta)},
        "nozzles": nozzle_rows,
        "credit_items": credit_items,
        "tanks": [
            {"tank_id": t, "name": tank_names.get(t, ""), "liters": v} for t, v in plan.tank_delta.items()
        ],
        "errors": plan.errors,
    }


async def _apply_readings(db: AsyncSession, plan: _FuelPlan) -> None:
    """Хаалтын милийг шинэчилнэ — хошууны одоогийн заалт, дараагийн ээлжийн
    «өмнөх хаалт» (миль залгамж) ч хамт."""
    for nozzle_id, value in plan.new_close.items():
        old = plan.old_close[nozzle_id]
        if value == old:
            continue
        row = plan.closes[nozzle_id]
        row.reading = value
        later = (
            await db.scalars(
                select(TotalizerReading)
                .where(TotalizerReading.nozzle_id == nozzle_id, TotalizerReading.created_at > row.created_at)
                .order_by(TotalizerReading.created_at)
            )
        ).all()
        nxt = next((r for r in later if str(r.reading_type) == str(ReadingType.SHIFT_OPEN)), None)
        if nxt is not None and nxt.prev_reading is not None and q3(_d(nxt.prev_reading, ZERO_L)) == old:
            nxt.prev_reading = value
        if not later:
            nozzle = plan.nozzles.get(nozzle_id)
            if nozzle is not None:
                nozzle.totalizer = value


async def _apply_tanks(db: AsyncSession, plan: _FuelPlan, ref_id: uuid.UUID | None) -> None:
    """Милийн өөрчлөлтийн литрийг савнаас зарлагадах / буцаана."""
    for tank_id, delta in plan.tank_delta.items():
        tank = await db.scalar(select(Tank).where(Tank.id == tank_id).with_for_update())
        if tank is None:
            continue
        if delta > ZERO_L:
            await tank_service.consume_fuel(db, tank, delta, ref_type=str(SourceType.SALE), ref_id=ref_id)
            continue
        liters = q3(-delta)
        value = q2(-plan.tank_cogs_delta.get(tank_id, ZERO))
        unit_cost = q6(value / liters) if liters > ZERO_L else q6(_d(tank.avg_cost))
        old_l = q3(_d(tank.current_l, ZERO_L))
        old_avg = q6(_d(tank.avg_cost))
        denominator = q3(old_l + liters)
        tank.avg_cost = q6((old_l * old_avg + liters * unit_cost) / denominator) if denominator > ZERO_L else unit_cost
        tank.current_l = denominator
        tank_service._record(
            db,
            tank,
            movement_type=TankMovementType.SALE,
            liters=liters,
            balance_after_l=denominator,
            unit_cost=unit_cost,
            ref_type=str(SourceType.SALE),
            ref_id=ref_id,
            note="Хаалтын засвар — миль",
        )


async def set_fuel(
    db: AsyncSession,
    user: User,
    *,
    shift_id: uuid.UUID,
    readings: list[Any] | None,
    marks: list[Any] | None,
    credit_prices: dict[uuid.UUID, Decimal] | None,
    note: str | None = None,
) -> dict[str, Any]:
    """Хаалтын миль / үнийн тэмдэглэлийг засаж, түлшний борлуулалтыг дахин бодно."""
    shift, closing = await ce._editable(db, shift_id)
    plan = await _fuel_plan(db, shift, closing, readings=readings, marks=marks, credit_prices=credit_prices)
    if plan.errors:
        raise HTTPException(status_code=422, detail=" ".join(plan.errors))
    if plan.fuel_sale is not None:
        await _refund_block(db, plan.fuel_sale)

    old_marks = (await db.scalars(select(ShiftPriceMark).where(ShiftPriceMark.shift_id == shift.id))).all()
    before = {
        "fuel_total": str(q2(_d(closing.fuel_total))),
        "marks": [
            {"nozzle": plan.labels.get(m.nozzle_id, ""), "reading": str(q3(_d(m.reading, ZERO_L))), "new_price": str(q2(_d(m.new_price)))}
            for m in sorted(old_marks, key=lambda m: (plan.labels.get(m.nozzle_id, ""), m.reading))
        ],
        "readings": [
            {"nozzle": plan.labels.get(n, ""), "reading": str(v)}
            for n, v in plan.old_close.items()
            if plan.new_close[n] != v
        ],
    }

    # 1. Үнийн тэмдэглэлүүд.
    await db.execute(delete(ShiftPriceMark).where(ShiftPriceMark.shift_id == shift.id))
    for mark in plan.marks:
        db.add(
            ShiftPriceMark(
                shift_id=shift.id,
                nozzle_id=mark.nozzle_id,
                reading=mark.reading,
                old_price=mark.old_price,
                new_price=mark.new_price,
                note=ADMIN_NOTE,
                created_by=user.id,
            )
        )

    # 2. Хаалтын миль, савны зөрүү литр.
    await _apply_readings(db, plan)
    await _apply_tanks(db, plan, plan.fuel_sale.id if plan.fuel_sale is not None else None)

    # 3. Зээлийн түлшний мөрүүд.
    credit_delta = ZERO
    by_sale: dict[uuid.UUID, list[_Alloc]] = {}
    for alloc in plan.allocs:
        by_sale.setdefault(alloc.sale.id, []).append(alloc)
    for allocs in by_sale.values():
        sale = allocs[0].sale
        if all(_alloc_unchanged(a) for a in allocs):
            continue
        await _refund_block(db, sale)
        old_total = q2(_d(sale.total))
        if any(a.amount != q2(_d(a.item.amount)) for a in allocs):
            await _invoice_block(db, sale)
        items, _ = await ce._sale_rows(db, sale)
        replaced = {a.item.id: a for a in allocs}
        rows: list[SaleItem] = []
        for item in items:
            alloc = replaced.get(item.id)
            if alloc is None or _alloc_unchanged(alloc):
                rows.append(item)
                continue
            for piece in _merge_by_tank(alloc.pieces):
                row = _fuel_item(sale, piece)
                db.add(row)
                rows.append(row)
            await db.delete(item)
        for n, row in enumerate(rows, start=1):
            row.line_no = n
        await _retotal(db, sale)
        new_total = q2(_d(sale.total))
        if new_total != old_total:
            contract = await db.scalar(select(Contract).where(Contract.id == sale.contract_id)) if sale.contract_id else None
            if contract is not None:
                contract.balance = q2(_d(contract.balance) + new_total - old_total)
            pay = await db.scalar(
                select(Payment).where(Payment.sale_id == sale.id, Payment.method == str(PaymentMethod.CONTRACT))
            )
            if pay is not None:
                pay.amount = new_total
            credit_delta = q2(credit_delta + new_total - old_total)
        await db.flush()
        await ce._repost_sale(db, sale)

    # 4. Түлшний нэгдсэн (бэлэн) борлуулалт — үлдсэн сегментүүдээс.
    fuel_sale = plan.fuel_sale
    if plan.fuel_rows:
        if fuel_sale is None:
            fuel_sale = await _new_sale(db, shift, closing, str(SaleType.FUEL), ce.CLOSE_NOTE)
            closing.fuel_sale_id = fuel_sale.id
        await db.execute(delete(SaleItem).where(SaleItem.sale_id == fuel_sale.id))
        for n, piece in enumerate(plan.fuel_rows, start=1):
            row = _fuel_item(fuel_sale, piece)
            row.line_no = n
            db.add(row)
        await db.flush()
        db.expire(fuel_sale, ["items"])
        await _retotal(db, fuel_sale)
    elif fuel_sale is not None:
        await _drop_sale(db, closing, fuel_sale)

    closing.fuel_total = plan.mile_total
    closing.credit_total = q2(_d(closing.credit_total) + credit_delta)
    await _settle(db, user, shift, closing)
    await audit(
        db,
        user_id=user.id,
        action="shift.closing_fuel_edited",
        entity_type="shift",
        entity_id=shift.id,
        before=before,
        after={
            "fuel_total": str(plan.mile_total),
            "marks": [
                {"nozzle": plan.labels.get(m.nozzle_id, ""), "reading": str(m.reading), "new_price": str(m.new_price)}
                for m in sorted(plan.marks, key=lambda m: (plan.labels.get(m.nozzle_id, ""), m.reading))
            ],
            "readings": [
                {"nozzle": plan.labels.get(n, ""), "reading": str(v)}
                for n, v in plan.new_close.items()
                if plan.old_close[n] != v
            ],
            "note": (note or "").strip() or None,
        },
    )
    return await ce.closing_view(db, shift_id)


async def fuel_editor(db: AsyncSession, shift_id: uuid.UUID) -> dict[str, Any]:
    """Миль, үнийн тэмдэглэлийн засварын цонхны өгөгдөл."""
    from app.services import attendant_service  # noqa: PLC0415

    shift, closing = await ce._load(db, shift_id)
    opens = {
        r.nozzle_id: r
        for r in (
            await db.scalars(
                select(TotalizerReading).where(
                    TotalizerReading.shift_id == shift.id,
                    TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
                )
            )
        ).all()
    }
    closes = {
        r.nozzle_id: r
        for r in (
            await db.scalars(
                select(TotalizerReading).where(
                    TotalizerReading.shift_id == shift.id,
                    TotalizerReading.reading_type == str(ReadingType.SHIFT_CLOSE),
                )
            )
        ).all()
    }
    nozzles, labels = await _nozzle_labels(db, set(opens) | set(closes))
    marks = (
        await db.scalars(
            select(ShiftPriceMark).where(ShiftPriceMark.shift_id == shift.id).order_by(ShiftPriceMark.reading)
        )
    ).all()
    calcs = (
        await attendant_service.compute_dispensed(db, shift, {n: q3(_d(r.reading, ZERO_L)) for n, r in closes.items()})
        if closes and opens
        else []
    )
    dipped = set(
        (
            await db.scalars(
                select(ShiftTankLevel.tank_id).where(
                    ShiftTankLevel.shift_id == shift.id, ShiftTankLevel.phase == str(ShiftPhase.CLOSE)
                )
            )
        ).all()
    )
    tank_ids = {n.tank_id for n in nozzles.values()}
    tanks = {t.id: t for t in (await db.scalars(select(Tank).where(Tank.id.in_(tank_ids)))).all()} if tank_ids else {}
    rows = []
    for calc in calcs:
        nozzle = calc.nozzle
        close_row = closes.get(nozzle.id)
        nxt = None
        if close_row is not None:
            nxt = await db.scalar(
                select(TotalizerReading)
                .where(
                    TotalizerReading.nozzle_id == nozzle.id,
                    TotalizerReading.reading_type == str(ReadingType.SHIFT_OPEN),
                    TotalizerReading.created_at > close_row.created_at,
                )
                .order_by(TotalizerReading.created_at)
                .limit(1)
            )
        opened = opens.get(nozzle.id)
        rows.append(
            {
                "nozzle_id": nozzle.id,
                "label": labels.get(nozzle.id, ""),
                "fuel_id": nozzle.fuel_id,
                "fuel_name": nozzle.fuel.name_mn if nozzle.fuel is not None else "",
                "tank_id": nozzle.tank_id,
                "tank_name": tanks[nozzle.tank_id].name if nozzle.tank_id in tanks else "",
                "open_reading": calc.open_reading,
                "close_reading": calc.close_reading,
                "open_price": q2(_d(opened.price_per_liter)) if opened is not None else ZERO,
                "liters": calc.liters,
                "amount": calc.amount,
                "segments": _segments(calc),
                "marks": [
                    {"reading": q3(_d(m.reading, ZERO_L)), "old_price": q2(_d(m.old_price)), "new_price": q2(_d(m.new_price))}
                    for m in marks
                    if m.nozzle_id == nozzle.id
                ],
                "next_open": q3(_d(nxt.reading, ZERO_L)) if nxt is not None else None,
                "locked": nozzle.tank_id in dipped,
            }
        )
    rows.sort(key=lambda r: r["label"])
    hints = (await price_hint_map(db, [shift])).get(shift.id, [])
    return {
        "shift_id": shift.id,
        "editable": closing.approved_at is None and shift.status != str(ShiftStatus.OPEN),
        "fuel_total": q2(_d(closing.fuel_total)),
        "nozzles": rows,
        "hints": hints,
    }
