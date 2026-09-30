"""Барааны эхний үлдэгдлийн засвар — бүрэн хувилбар.

Өмнө оруулсан эхний үлдэгдлийн мөрийн тоо хэмжээ, нэгж өртгийг засахад тэр
мөчөөс хойших нөөцийн дэвтрийг ДАХИН ТОГЛУУЛНА:

* хөдлөх дундаж өртөг (салбар бүрээр), үлдэгдэл, дэвтрийн мөр бүрийн өртөг;
* борлуулалтын өртөг (COGS) — борлуулалтын мөр, баримтын нийт өртөг,
  журналын 5102/1302 мөр (ашиг, ээлжийн тайлан ч хамт засагдана);
* буцаалтын сэргээлт, тооллогын тохируулга, салбар хоорондын шилжүүлэг,
  задлан хөрвүүлэлт (грам бүтээгдэхүүний өртөг, борлуулалт ч хамт);
* эхний үлдэгдлийн үнэлгээний өөрчлөлт анхны огноогоор нь 1302/3101
  засварын бичилтээр.

Дахин тоглуулалтыг засваргүй (baseline) ба засвартай хоёр удаа хийж, зөвхөн
ЗӨРҮҮГ хадгалсан утгууд дээр нэмнэ. Ингэснээр засварт хамааралгүй түүх
(жишээ нь нэг transaction доторх мөрүүдийн дараалал) огт хөндөгдөхгүй —
өөрчлөлтгүй засвар ямар ч бичлэг өөрчлөхгүй.

Энэ модуль ``db.commit()`` дуудахгүй — ``get_db`` эзэмшинэ.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalStatus, EventType, InventoryTxType, ItemType, ShiftStatus, SourceType
from app.models.accounting import JournalEntry, JournalLine
from app.models.approval import Refund, RefundItem
from app.models.branch import Branch
from app.models.product import InventoryTransaction, Product, ProductBranchStock
from app.models.sale import Sale, SaleItem
from app.models.shift import Shift, ShiftClosing
from app.models.user import AuditLog, User
from app.money import q2, q3, q6
from app.services.audit_service import audit
from app.services.coa import ACC
from app.services.posting import NO_DIMS, Dims, LineSpec, normalize_lines, posting
from app.services.posting_rules import (
    build_inventory_adjustment_lines,
    build_inventory_transfer_lines,
)
from app.stationtime import STATION_TZ

ZERO = Decimal("0")
OPENING_REF = str(SourceType.OPENING_BALANCE)
CORRECTED_ACTION = "inventory.opening_corrected"

T_PURCHASE = str(InventoryTxType.PURCHASE)
T_SALE = str(InventoryTxType.SALE)
T_REFUND = str(InventoryTxType.REFUND)
T_ADJUSTMENT = str(InventoryTxType.ADJUSTMENT)
T_CONVERT_OUT = str(InventoryTxType.CONVERT_OUT)
T_CONVERT_IN = str(InventoryTxType.CONVERT_IN)
T_TRANSFER_OUT = str(InventoryTxType.TRANSFER_OUT)
T_TRANSFER_IN = str(InventoryTxType.TRANSFER_IN)
T_OPENING = str(InventoryTxType.OPENING)


def _d(value: Any) -> Decimal:
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _local_date(moment: datetime | None) -> date:
    return (moment or datetime.now(STATION_TZ)).astimezone(STATION_TZ).date()


def is_opening(tx: InventoryTransaction) -> bool:
    """Эхний үлдэгдлийн мөр: «Эхний үлдэгдэл» цонх эсвэл бараа үүсгэхэд оруулсан."""
    kind = str(tx.tx_type)
    return kind == T_OPENING or (kind == T_PURCHASE and str(tx.ref_type or "") == OPENING_REF)


def _opening_filter() -> Any:
    return or_(
        InventoryTransaction.tx_type == T_OPENING,
        and_(
            InventoryTransaction.tx_type == T_PURCHASE,
            InventoryTransaction.ref_type == OPENING_REF,
        ),
    )


# =========================================================================== #
# Дахин тоглуулах хөдөлгүүр — inventory_service-ийн томьёог яг давтана
# =========================================================================== #
@dataclass
class _BranchState:
    qty: Decimal = ZERO
    avg: Decimal = ZERO


@dataclass
class _State:
    """Нэг барааны үлдэгдэл, дундаж өртөг (нийт ба салбар бүрээр)."""

    qty: Decimal = ZERO
    avg: Decimal = ZERO
    branches: dict[uuid.UUID, _BranchState] = field(default_factory=dict)

    def cost(self, branch_id: uuid.UUID | None) -> Decimal:
        """``inventory_service.branch_unit_cost``."""
        if branch_id is None:
            return q6(self.avg)
        row = self.branches.get(branch_id)
        cost = q6(row.avg) if row is not None else ZERO
        return cost if cost > ZERO else q6(self.avg)

    def move(self, branch_id: uuid.UUID | None, delta: Decimal, in_cost: Decimal | None = None) -> Decimal | None:
        """``inventory_service._move_branch_stock`` — салбарын шинэ үлдэгдлийг буцаана."""
        if branch_id is None:
            return None
        row = self.branches.setdefault(branch_id, _BranchState())
        old_qty = q3(row.qty)
        balance = q3(old_qty + delta)
        if in_cost is not None and delta > ZERO:
            row.avg = (
                q6((old_qty * q6(row.avg) + delta * q6(in_cost)) / balance)
                if balance > ZERO
                else q6(in_cost)
            )
        row.qty = balance
        return balance

    def sync(self) -> None:
        """``inventory_service.sync_product_cost``."""
        if not self.branches:
            return
        total_qty = ZERO
        total_value = ZERO
        for row in self.branches.values():
            qty = q3(row.qty)
            total_qty += qty
            total_value += qty * q6(row.avg)
        if total_qty > ZERO:
            self.avg = q6(total_value / total_qty)


@dataclass
class _Run:
    cost: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    balance: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    cogs: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    negative: set[uuid.UUID] = field(default_factory=set)
    states: dict[uuid.UUID, _State] = field(default_factory=lambda: defaultdict(_State))


_PRIORITY = {T_TRANSFER_OUT: 0, T_CONVERT_OUT: 0, T_TRANSFER_IN: 2, T_CONVERT_IN: 2}


def _sort_key(tx: InventoryTransaction) -> tuple[Any, ...]:
    # Нэг transaction-д үүссэн мөрүүд ижил created_at-тэй: шилжүүлэг/задлалтын
    # «гарсан» мөр «орсон»-оосоо өмнө (өртөг нь дамжина).
    return (tx.created_at, _PRIORITY.get(str(tx.tx_type), 1), str(tx.id))


def _replay(
    rows: list[InventoryTransaction],
    *,
    edit_id: uuid.UUID,
    edit_qty: Decimal,
    edit_cost: Decimal,
    refund_source: dict[uuid.UUID, uuid.UUID],
    conv_external: dict[tuple[Any, Any], Decimal],
) -> _Run:
    run = _Run()
    conv_totals: dict[tuple[Any, Any], Decimal] = {}
    transfer_costs: dict[tuple[Any, Any, Decimal], Decimal] = {}

    for tx in rows:
        st = run.states[tx.product_id]
        kind = str(tx.tx_type)
        branch = tx.branch_id
        edited = tx.id == edit_id
        qty = q3(edit_qty) if edited else q3(_d(tx.qty))
        negative = False

        if kind == T_CONVERT_IN:
            key = (tx.created_at, tx.ref_id)
            total = conv_totals.pop(key, None)
            if total is None:
                total = conv_external.get(key, qty * q6(_d(tx.unit_cost)))
            cost = q6(total / qty) if qty > ZERO else q6(_d(tx.unit_cost))
            if qty > ZERO:
                old_qty = q3(st.qty)
                denominator = old_qty + qty
                st.avg = q6((old_qty * q6(st.avg) + total) / denominator) if denominator > ZERO else cost
                st.qty = q3(denominator)
                st.move(branch, qty, in_cost=cost)
                st.sync()
            balance = st.qty
        elif kind == T_CONVERT_OUT:
            cost = st.cost(branch)
            conv_totals[(tx.created_at, tx.ref_id or tx.product_id)] = abs(qty) * cost
            st.qty = q3(st.qty + qty)
            branch_qty = st.move(branch, qty)
            negative = st.qty < ZERO or (branch_qty is not None and branch_qty < ZERO)
            st.sync()
            balance = st.qty
        elif kind == T_TRANSFER_OUT:
            cost = st.cost(branch)
            transfer_costs[(tx.created_at, tx.product_id, abs(qty))] = cost
            branch_qty = st.move(branch, qty)
            negative = branch_qty is not None and branch_qty < ZERO
            balance = branch_qty if branch_qty is not None else st.qty
        elif kind == T_TRANSFER_IN:
            cost = transfer_costs.pop((tx.created_at, tx.product_id, abs(qty)), q6(_d(tx.unit_cost)))
            branch_qty = st.move(branch, qty, in_cost=cost)
            st.sync()
            balance = branch_qty if branch_qty is not None else st.qty
        elif kind in (T_PURCHASE, T_OPENING) and (qty > ZERO or edited):
            # Орлого — хөдлөх дундаж (``receive_product``).
            cost = q6(edit_cost) if edited else q6(_d(tx.unit_cost))
            if qty > ZERO:
                old_qty = q3(st.qty)
                denominator = old_qty + qty
                st.avg = q6((old_qty * q6(st.avg) + qty * cost) / denominator) if denominator > ZERO else cost
                st.qty = q3(denominator)
                st.move(branch, qty, in_cost=cost)
                st.sync()
            balance = st.qty
        elif kind == T_REFUND:
            # Буцаалт — анх зарагдсан өртгөөрөө, дундаж хөдлөхгүй.
            source = refund_source.get(tx.id)
            cost = run.cost.get(source, q6(_d(tx.unit_cost))) if source is not None else q6(_d(tx.unit_cost))
            st.qty = q3(st.qty + qty)
            st.move(branch, qty)
            st.sync()
            balance = st.qty
        else:
            # Зарлага (борлуулалт, тохируулга, эхний үлдэгдлийн бууралт) —
            # тухайн салбарын өртгөөр, дундаж хөдлөхгүй.
            cost = st.cost(branch)
            st.qty = q3(st.qty + qty)
            branch_qty = st.move(branch, qty)
            negative = st.qty < ZERO or (branch_qty is not None and branch_qty < ZERO)
            st.sync()
            balance = st.qty
            if kind == T_SALE:
                run.cogs[tx.id] = q2(abs(qty) * cost)

        run.cost[tx.id] = q6(cost)
        run.balance[tx.id] = q3(balance)
        if negative:
            run.negative.add(tx.id)
    return run


# =========================================================================== #
# Төлөвлөгөө — юу хэрхэн өөрчлөгдөхийг бүрэн бодно (DB-д бичихгүй)
# =========================================================================== #
@dataclass
class _Plan:
    edit: InventoryTransaction
    product: Product
    new_qty: Decimal
    new_cost: Decimal
    products: dict[uuid.UUID, Product]
    branches: dict[uuid.UUID, str]
    rows: list[InventoryTransaction]
    tx_updates: dict[uuid.UUID, tuple[Decimal, Decimal]] = field(default_factory=dict)  # tx → (cost, balance)
    sale_items: dict[uuid.UUID, tuple[SaleItem, Decimal, Decimal]] = field(default_factory=dict)
    sales: dict[uuid.UUID, Sale] = field(default_factory=dict)
    sale_cogs_delta: dict[uuid.UUID, Decimal] = field(default_factory=dict)
    refund_items: dict[uuid.UUID, tuple[RefundItem, Decimal]] = field(default_factory=dict)
    refunds: dict[uuid.UUID, Refund] = field(default_factory=dict)
    adjustments: list[InventoryTransaction] = field(default_factory=list)
    transfers: list[tuple[InventoryTransaction, InventoryTransaction]] = field(default_factory=list)
    conversions: int = 0
    #: (эхний үлдэгдлийн мөр, үнэлгээний зөрүү) — засварын журнал.
    opening_deltas: list[tuple[InventoryTransaction, Decimal]] = field(default_factory=list)
    opening_entries: dict[uuid.UUID, JournalEntry | None] = field(default_factory=dict)
    #: (бараа, салбар|None) → (өмнө, дараа) үлдэгдэл; бараа → (өмнө, дараа) дундаж.
    stock: dict[tuple[uuid.UUID, uuid.UUID | None], tuple[Decimal, Decimal]] = field(default_factory=dict)
    avg: dict[uuid.UUID, tuple[Decimal, Decimal]] = field(default_factory=dict)
    branch_avg: dict[tuple[uuid.UUID, uuid.UUID], tuple[Decimal, Decimal]] = field(default_factory=dict)
    later_openings: int = 0

    def opening_groups(self) -> dict[tuple[date, str], Decimal]:
        """Эхний үлдэгдлийн засварын журнал — (огноо, бараа) бүрд нэг бичилт."""
        grouped: dict[tuple[date, str], Decimal] = defaultdict(lambda: ZERO)
        for tx, delta in self.opening_deltas:
            entry = self.opening_entries.get(tx.id)
            entry_date = entry.entry_date if entry is not None else _local_date(tx.created_at)
            grouped[(entry_date, self.products[tx.product_id].name_mn)] += delta
        return {key: q2(value) for key, value in grouped.items() if q2(value) != ZERO}


async def _load_edit(db: AsyncSession, tx_id: uuid.UUID) -> InventoryTransaction:
    tx = await db.scalar(select(InventoryTransaction).where(InventoryTransaction.id == tx_id))
    if tx is None:
        raise HTTPException(status_code=404, detail="Эхний үлдэгдлийн бичлэг олдсонгүй")
    if not is_opening(tx):
        raise HTTPException(status_code=422, detail="Энэ бичлэг эхний үлдэгдэл биш байна")
    if q3(_d(tx.qty)) <= ZERO and not await _was_corrected(db, tx.id):
        raise HTTPException(
            status_code=422,
            detail="Үлдэгдэл бууруулсан (дахин оруулсан) мөрийг засахгүй — анхны эхний үлдэгдлийг засна уу",
        )
    return tx


async def _was_corrected(db: AsyncSession, tx_id: uuid.UUID) -> bool:
    count = await db.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == CORRECTED_ACTION, AuditLog.entity_id == tx_id)
    )
    return bool(count)


async def _scope(db: AsyncSession, product_id: uuid.UUID) -> set[uuid.UUID]:
    """Засварт хамаарах бараанууд — задлан хөрвүүлэлтээр өртөг нь дамжих грам бүтээгдэхүүн ч."""
    scope = {product_id}
    frontier = [product_id]
    while frontier:
        source = frontier.pop()
        targets = (
            await db.scalars(
                select(InventoryTransaction.product_id)
                .where(
                    InventoryTransaction.tx_type == T_CONVERT_IN,
                    InventoryTransaction.ref_id == source,
                )
                .distinct()
            )
        ).all()
        for target in targets:
            if target not in scope:
                scope.add(target)
                frontier.append(target)
    return scope


async def _plan(
    db: AsyncSession,
    tx_id: uuid.UUID,
    new_qty: Decimal,
    new_cost: Decimal,
    *,
    lock: bool = False,
) -> _Plan:
    edit = await _load_edit(db, tx_id)
    new_qty = q3(_d(new_qty))
    new_cost = q6(_d(new_cost))
    if new_qty < ZERO:
        raise HTTPException(status_code=422, detail="Тоо хэмжээ сөрөг байж болохгүй")
    if new_cost < ZERO:
        raise HTTPException(status_code=422, detail="Нэгж өртөг сөрөг байж болохгүй")

    scope = await _scope(db, edit.product_id)
    product_stmt = select(Product).where(Product.id.in_(scope))
    if lock:
        product_stmt = product_stmt.with_for_update()
    products = {p.id: p for p in (await db.scalars(product_stmt)).all()}
    product = products[edit.product_id]

    rows = sorted(
        (
            await db.scalars(
                select(InventoryTransaction).where(InventoryTransaction.product_id.in_(scope))
            )
        ).all(),
        key=_sort_key,
    )

    # --- Задлалтын гадаад эх үүсвэр (эх бараа нь хамрах хүрээнд ороогүй) ---
    conv_external: dict[tuple[Any, Any], Decimal] = {}
    foreign_sources = {
        tx.ref_id for tx in rows if str(tx.tx_type) == T_CONVERT_IN and tx.ref_id is not None and tx.ref_id not in scope
    }
    if foreign_sources:
        for out in (
            await db.scalars(
                select(InventoryTransaction).where(
                    InventoryTransaction.tx_type == T_CONVERT_OUT,
                    InventoryTransaction.product_id.in_(foreign_sources),
                )
            )
        ).all():
            conv_external[(out.created_at, out.ref_id or out.product_id)] = abs(q3(_d(out.qty))) * q6(_d(out.unit_cost))

    # --- Борлуулалтын мөрүүдтэй холбох ---
    sale_ids = {tx.ref_id for tx in rows if str(tx.tx_type) == T_SALE and tx.ref_id is not None}
    sales = (
        {s.id: s for s in (await db.scalars(select(Sale).where(Sale.id.in_(sale_ids)))).all()}
        if sale_ids
        else {}
    )
    items_by_sale: dict[tuple[uuid.UUID, uuid.UUID], list[SaleItem]] = defaultdict(list)
    if sale_ids:
        for item in (
            await db.scalars(
                select(SaleItem)
                .where(SaleItem.sale_id.in_(sale_ids), SaleItem.product_id.in_(scope))
                .order_by(SaleItem.sale_id, SaleItem.line_no)
            )
        ).all():
            items_by_sale[(item.sale_id, item.product_id)].append(item)
    tx_item: dict[uuid.UUID, SaleItem] = {}
    for tx in rows:
        if str(tx.tx_type) != T_SALE or tx.ref_id is None:
            continue
        pool = items_by_sale.get((tx.ref_id, tx.product_id), [])
        match = next((item for item in pool if q3(_d(item.qty)) == abs(q3(_d(tx.qty)))), None)
        if match is None:
            sale = sales.get(tx.ref_id)
            raise HTTPException(
                status_code=422,
                detail=f"Борлуулалт №{getattr(sale, 'number', '?')}-ийн мөр нөөцийн дэвтэртэй таарахгүй байна — засвар хийх боломжгүй",
            )
        pool.remove(match)
        tx_item[tx.id] = match
    item_tx = {item.id: tx_id_ for tx_id_, item in tx_item.items()}

    # --- Буцаалтын сэргээлтийг эх борлуулалтын мөртэй холбох ---
    refund_ids = {tx.ref_id for tx in rows if str(tx.tx_type) == T_REFUND and tx.ref_id is not None}
    refund_source: dict[uuid.UUID, uuid.UUID] = {}
    if refund_ids:
        refund_lines = (
            await db.scalars(select(RefundItem).where(RefundItem.refund_id.in_(refund_ids)))
        ).all()
        line_item = {
            item.id: item
            for item in (
                await db.scalars(
                    select(SaleItem).where(SaleItem.id.in_({ri.sale_item_id for ri in refund_lines}))
                )
            ).all()
        } if refund_lines else {}
        pools: dict[tuple[uuid.UUID, uuid.UUID], list[RefundItem]] = defaultdict(list)
        for ri in refund_lines:
            item = line_item.get(ri.sale_item_id)
            if item is not None and item.product_id is not None:
                pools[(ri.refund_id, item.product_id)].append(ri)
        for tx in rows:
            if str(tx.tx_type) != T_REFUND or tx.ref_id is None:
                continue
            pool = pools.get((tx.ref_id, tx.product_id), [])
            match = next((ri for ri in pool if q3(_d(ri.qty)) == q3(_d(tx.qty))), None)
            if match is None:
                continue
            pool.remove(match)
            source_tx = item_tx.get(match.sale_item_id)
            if source_tx is not None:
                refund_source[tx.id] = source_tx

    # --- Хоёр удаа дахин тоглуулна: засваргүй ба засвартай ---
    base = _replay(
        rows,
        edit_id=edit.id,
        edit_qty=q3(_d(edit.qty)),
        edit_cost=q6(_d(edit.unit_cost)),
        refund_source=refund_source,
        conv_external=conv_external,
    )
    fixed = _replay(
        rows,
        edit_id=edit.id,
        edit_qty=new_qty,
        edit_cost=new_cost,
        refund_source=refund_source,
        conv_external=conv_external,
    )

    branch_ids = {tx.branch_id for tx in rows if tx.branch_id is not None}
    branches = (
        {b.id: b.name for b in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()}
        if branch_ids
        else {}
    )
    plan = _Plan(
        edit=edit,
        product=product,
        new_qty=new_qty,
        new_cost=new_cost,
        products=products,
        branches=branches,
        rows=rows,
        sales=sales,
    )

    # --- Засвараар шинээр үүсэх сөрөг үлдэгдэл ---
    for tx in rows:
        if tx.id in fixed.negative and tx.id not in base.negative:
            name = products[tx.product_id].name_mn
            when = _local_date(tx.created_at).isoformat()
            doc = ""
            if str(tx.tx_type) == T_SALE and tx.ref_id in sales:
                doc = f" (борлуулалт №{sales[tx.ref_id].number})"
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Энэ засвараар {when}-ний хөдөлгөөнд{doc} «{name}»-ийн үлдэгдэл хасах болж байна. "
                    "Тэр үед зарагдсан/гарсан тоо хэмжээнээс бага эхний үлдэгдэл оруулах боломжгүй — "
                    "дутуу бүртгэгдсэн орлого (худалдан авалт) байгаа эсэхийг шалгана уу."
                ),
            )

    # --- Дэвтрийн мөр бүрийн зөрүү ---
    for tx in rows:
        d_cost = fixed.cost[tx.id] - base.cost[tx.id]
        d_balance = fixed.balance[tx.id] - base.balance[tx.id]
        if tx.id == edit.id:
            plan.tx_updates[tx.id] = (new_cost, q3(_d(tx.balance_after) + d_balance))
            continue
        if d_cost == ZERO and d_balance == ZERO:
            continue
        plan.tx_updates[tx.id] = (
            max(ZERO, q6(_d(tx.unit_cost) + d_cost)),
            q3(_d(tx.balance_after) + d_balance),
        )
        kind = str(tx.tx_type)
        if d_cost != ZERO and kind == T_ADJUSTMENT:
            plan.adjustments.append(tx)
        if d_cost != ZERO and kind in (T_CONVERT_OUT, T_CONVERT_IN):
            plan.conversions += 1
        if d_cost != ZERO and kind == T_OPENING and q3(_d(tx.qty)) < ZERO:
            new_value = q2(q3(_d(tx.qty)) * plan.tx_updates[tx.id][0])
            old_value = q2(q3(_d(tx.qty)) * q6(_d(tx.unit_cost)))
            if new_value != old_value:
                plan.opening_deltas.append((tx, q2(new_value - old_value)))

    # Засаж буй мөрийн үнэлгээний өөрчлөлт.
    old_value = q2(q3(_d(edit.qty)) * q6(_d(edit.unit_cost)))
    new_value = q2(new_qty * new_cost)
    if new_value != old_value:
        plan.opening_deltas.insert(0, (edit, q2(new_value - old_value)))

    # Шилжүүлэг — гарсан мөрийн өртөг өөрчлөгдвөл журнал нь ч.
    pending_out: dict[tuple[Any, Any, Decimal], InventoryTransaction] = {}
    for tx in rows:
        kind = str(tx.tx_type)
        key = (tx.created_at, tx.product_id, abs(q3(_d(tx.qty))))
        if kind == T_TRANSFER_OUT:
            pending_out[key] = tx
        elif kind == T_TRANSFER_IN:
            out = pending_out.pop(key, None)
            if out is not None and out.id in plan.tx_updates and fixed.cost[out.id] != base.cost[out.id]:
                plan.transfers.append((out, tx))

    # --- Борлуулалтын өртөг ---
    for tx_id_, item in tx_item.items():
        d_cogs = fixed.cogs.get(tx_id_, ZERO) - base.cogs.get(tx_id_, ZERO)
        d_cost = fixed.cost[tx_id_] - base.cost[tx_id_]
        if d_cogs == ZERO and d_cost == ZERO:
            continue
        plan.sale_items[item.id] = (
            item,
            max(ZERO, q6(_d(item.unit_cost) + d_cost)),
            max(ZERO, q2(_d(item.cogs_amount) + d_cogs)),
        )
        if d_cogs != ZERO:
            plan.sale_cogs_delta[item.sale_id] = q2(plan.sale_cogs_delta.get(item.sale_id, ZERO) + d_cogs)

    # --- Өртөг нь өөрчлөгдсөн борлуулалтын мөрийн буцаалтууд (бүх төлөв) ---
    changed_items = {item_id: new_cogs for item_id, (_i, _c, new_cogs) in plan.sale_items.items()}
    if changed_items:
        from app.services.refund_service import line_share  # noqa: PLC0415

        lines = (
            await db.scalars(select(RefundItem).where(RefundItem.sale_item_id.in_(list(changed_items))))
        ).all()
        for ri in lines:
            item = plan.sale_items[ri.sale_item_id][0]
            new_cogs = line_share(changed_items[ri.sale_item_id], _d(ri.qty), _d(item.qty))
            if new_cogs != q2(_d(ri.cogs_amount)):
                plan.refund_items[ri.id] = (ri, new_cogs)
        refund_ids_changed = {ri.refund_id for ri, _ in plan.refund_items.values()}
        if refund_ids_changed:
            plan.refunds = {
                r.id: r for r in (await db.scalars(select(Refund).where(Refund.id.in_(refund_ids_changed)))).all()
            }

    # --- Эцсийн үлдэгдэл, дундаж өртөг (засвартай − засваргүй зөрүүгээр) ---
    branch_deltas: dict[tuple[uuid.UUID, uuid.UUID], tuple[Decimal, Decimal]] = {}
    for pid in scope:
        b_state = base.states.get(pid) or _State()
        f_state = fixed.states.get(pid) or _State()
        current = products[pid]
        d_qty = q3(f_state.qty - b_state.qty)
        d_avg = q6(f_state.avg - b_state.avg)
        if d_qty != ZERO:
            plan.stock[(pid, None)] = (q3(_d(current.stock_qty)), q3(_d(current.stock_qty) + d_qty))
        if d_avg != ZERO:
            plan.avg[pid] = (q6(_d(current.avg_cost)), max(ZERO, q6(_d(current.avg_cost) + d_avg)))
        for bid in set(b_state.branches) | set(f_state.branches):
            bb = b_state.branches.get(bid) or _BranchState()
            fb = f_state.branches.get(bid) or _BranchState()
            delta = (q3(fb.qty - bb.qty), q6(fb.avg - bb.avg))
            if delta != (ZERO, ZERO):
                branch_deltas[(pid, bid)] = delta

    if branch_deltas:
        current_rows = {
            (r.product_id, r.branch_id): r
            for r in (
                await db.scalars(select(ProductBranchStock).where(ProductBranchStock.product_id.in_(scope)))
            ).all()
        }
        for key, (d_qty, d_avg) in branch_deltas.items():
            row = current_rows.get(key)
            cur_qty = q3(_d(row.qty)) if row is not None else ZERO
            cur_avg = q6(_d(row.avg_cost)) if row is not None else ZERO
            if q3(cur_qty + d_qty) < ZERO:
                raise HTTPException(
                    status_code=422,
                    detail=f"Засварын дараа «{products[key[0]].name_mn}»-ийн салбарын үлдэгдэл сөрөг болж байна",
                )
            if d_qty != ZERO:
                plan.stock[key] = (cur_qty, q3(cur_qty + d_qty))
            if d_avg != ZERO:
                plan.branch_avg[key] = (cur_avg, max(ZERO, q6(cur_avg + d_avg)))
    for (pid, bid), (_before, after) in plan.stock.items():
        if bid is None and after < ZERO:
            raise HTTPException(
                status_code=422,
                detail=f"Засварын дараа «{products[pid].name_mn}»-ийн үлдэгдэл сөрөг болж байна",
            )

    # Эхний үлдэгдлийн анхны журналууд — засварын бичилтийг тэдгээрийн огноогоор.
    for tx, _delta in plan.opening_deltas:
        plan.opening_entries[tx.id] = await _opening_entry(db, tx)

    # Энэ бараа, салбарт дараа нь дахин оруулсан эхний үлдэгдэл — давхардлын анхааруулга.
    plan.later_openings = sum(
        1
        for tx in rows
        if tx.id != edit.id
        and tx.product_id == edit.product_id
        and tx.branch_id == edit.branch_id
        and is_opening(tx)
        and _sort_key(tx) > _sort_key(edit)
    )
    return plan


# =========================================================================== #
# Дүгнэлт (preview ба apply хоёулаа буцаана)
# =========================================================================== #
async def _summary(db: AsyncSession, plan: _Plan) -> dict[str, Any]:
    edit = plan.edit
    old_qty = q3(_d(edit.qty))
    old_cost = q6(_d(edit.unit_cost))

    stock_rows = []
    for (pid, bid), (before, after) in sorted(
        plan.stock.items(), key=lambda kv: (plan.products[kv[0][0]].name_mn, "" if kv[0][1] is None else plan.branches.get(kv[0][1], ""))
    ):
        product = plan.products[pid]
        stock_rows.append(
            {
                "product_id": pid,
                "product_name": product.name_mn,
                "unit": product.unit,
                "branch_id": bid,
                "branch_name": plan.branches.get(bid, "") if bid is not None else "",
                "before": before,
                "after": after,
            }
        )
    avg_rows = [
        {
            "product_id": pid,
            "product_name": plan.products[pid].name_mn,
            "before": before,
            "after": after,
        }
        for pid, (before, after) in plan.avg.items()
    ]

    cogs_change = q2(sum(plan.sale_cogs_delta.values(), ZERO))
    refund_change = q2(
        sum((new - q2(_d(ri.cogs_amount)) for ri, new in plan.refund_items.values()), ZERO)
    )
    adjustment_change = ZERO
    for tx in plan.adjustments:
        new_cost = plan.tx_updates[tx.id][0]
        adjustment_change = q2(
            adjustment_change + q2(q3(_d(tx.qty)) * new_cost) - q2(q3(_d(tx.qty)) * q6(_d(tx.unit_cost)))
        )

    # Нөлөөлөх ээлжүүд — өртөг нь өөрчлөгдөх борлуулалтын ээлж.
    shift_ids = {plan.sales[sid].shift_id for sid in plan.sale_cogs_delta if sid in plan.sales and plan.sales[sid].shift_id}
    shift_numbers: list[int] = []
    approved = 0
    closed = 0
    if shift_ids:
        rows = (
            await db.execute(
                select(Shift.number, Shift.status, ShiftClosing.approved_at)
                .outerjoin(ShiftClosing, ShiftClosing.shift_id == Shift.id)
                .where(Shift.id.in_(shift_ids))
                .order_by(Shift.number)
            )
        ).all()
        for number, status, approved_at in rows:
            shift_numbers.append(int(number))
            if str(status) != str(ShiftStatus.OPEN):
                closed += 1
            if approved_at is not None:
                approved += 1

    dates = [
        _local_date(plan.sales[sid].completed_at or plan.sales[sid].created_at)
        for sid in plan.sale_cogs_delta
        if sid in plan.sales
    ]
    journal = (
        len(plan.sale_cogs_delta)
        + len({ri.refund_id for ri, _ in plan.refund_items.values()})
        + len(plan.adjustments)
        + len(plan.transfers)
        + len(plan.opening_groups())
    )

    warnings: list[str] = []
    if plan.later_openings:
        warnings.append(
            f"Энэ бараа, салбарт дараа нь {plan.later_openings} удаа дахин эхний үлдэгдэл оруулсан байна — "
            "тэр нь алдааг засах гэж оруулсан бол давхардахгүйн тулд тэдгээрийг мөн засна уу."
        )
    if approved:
        warnings.append(
            f"{approved} батлагдсан ээлжийн тайлангийн өртөг, ашиг өөрчлөгдөнө."
        )

    branch_name = plan.branches.get(edit.branch_id, "") if edit.branch_id is not None else ""
    if edit.branch_id is not None and not branch_name:
        branch = await db.scalar(select(Branch).where(Branch.id == edit.branch_id))
        branch_name = branch.name if branch else ""
    return {
        "tx_id": edit.id,
        "product_id": plan.product.id,
        "product_name": plan.product.name_mn,
        "unit": plan.product.unit,
        "branch_id": edit.branch_id,
        "branch_name": branch_name,
        "old_qty": old_qty,
        "old_unit_cost": old_cost,
        "old_value": q2(old_qty * old_cost),
        "new_qty": plan.new_qty,
        "new_unit_cost": plan.new_cost,
        "new_value": q2(plan.new_qty * plan.new_cost),
        "value_change": q2(q2(plan.new_qty * plan.new_cost) - q2(old_qty * old_cost)),
        "stock": stock_rows,
        "avg_cost": avg_rows,
        "sales_count": len(plan.sale_cogs_delta),
        "cogs_change": cogs_change,
        "refunds_count": len(plan.refunds),
        "refund_cogs_change": refund_change,
        "adjustments_count": len(plan.adjustments),
        "adjustment_value_change": adjustment_change,
        "transfers_count": len(plan.transfers),
        "conversions_count": plan.conversions,
        "journal_entries": journal,
        "shift_count": len(shift_numbers),
        "shifts_closed": closed,
        "shifts_approved": approved,
        "shift_numbers": shift_numbers[:30],
        "date_from": min(dates) if dates else None,
        "date_to": max(dates) if dates else None,
        "warnings": warnings,
    }


async def preview(db: AsyncSession, tx_id: uuid.UUID, qty: Decimal, unit_cost: Decimal) -> dict[str, Any]:
    plan = await _plan(db, tx_id, qty, unit_cost)
    return await _summary(db, plan)


# =========================================================================== #
# Хэрэгжүүлэх
# =========================================================================== #
def _line(entry_id: uuid.UUID, line_no: int, spec: LineSpec) -> JournalLine:
    dims = spec.dims or NO_DIMS
    return JournalLine(
        entry_id=entry_id,
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
        dim_branch_id=dims.branch_id,
    )


async def _replace_lines(db: AsyncSession, entry: JournalEntry, specs: list[LineSpec]) -> None:
    """Бичилтийн мөрүүдийг бүрэн солино (дугаар, огноо, эх сурвалж хэвээр)."""
    normalized = normalize_lines(specs)
    for line in list(entry.lines):
        await db.delete(line)
    await db.flush()
    for line_no, spec in enumerate(normalized, start=1):
        db.add(_line(entry.id, line_no, spec))
    await db.flush()
    await db.refresh(entry, ["lines"])


async def _set_pair(
    db: AsyncSession,
    entry: JournalEntry,
    *,
    debit_account: str,
    credit_account: str,
    amount: Decimal,
    dims: Dims,
    memo_debit: str,
    memo_credit: str,
) -> None:
    """Бичилтийн өртгийн хос мөрийг (Дт/Кт) шинэ дүнгээр — бусад мөр хөндөгдөхгүй."""
    amount = q2(amount)
    debit_line = next(
        (ln for ln in entry.lines if ln.account_code == debit_account and _d(ln.debit) > ZERO), None
    )
    credit_line = next(
        (ln for ln in entry.lines if ln.account_code == credit_account and _d(ln.credit) > ZERO), None
    )
    if amount > ZERO:
        next_no = max((ln.line_no for ln in entry.lines), default=0)
        if debit_line is None:
            next_no += 1
            db.add(_line(entry.id, next_no, LineSpec(account_code=debit_account, debit=amount, memo=memo_debit, dims=dims)))
        else:
            debit_line.debit = amount
        if credit_line is None:
            next_no += 1
            db.add(_line(entry.id, next_no, LineSpec(account_code=credit_account, credit=amount, memo=memo_credit, dims=dims)))
        else:
            credit_line.credit = amount
    else:
        for line in (debit_line, credit_line):
            if line is not None:
                await db.delete(line)
    await db.flush()
    await db.refresh(entry, ["lines"])


async def _opening_entry(db: AsyncSession, tx: InventoryTransaction) -> JournalEntry | None:
    """Эхний үлдэгдлийн мөрийн анхны журнал — нэг transaction-д үүссэн тул created_at ижил."""
    entries = (
        await db.scalars(
            select(JournalEntry).where(
                JournalEntry.source_type == OPENING_REF,
                JournalEntry.created_at == tx.created_at,
            )
        )
    ).all()
    if not entries:
        return None
    return next((e for e in entries if e.source_id == tx.product_id), entries[0])


async def apply(
    db: AsyncSession,
    user: User,
    tx_id: uuid.UUID,
    qty: Decimal,
    unit_cost: Decimal,
    note: str | None = None,
) -> dict[str, Any]:
    plan = await _plan(db, tx_id, qty, unit_cost, lock=True)
    summary = await _summary(db, plan)
    edit = plan.edit
    before = {"qty": str(q3(_d(edit.qty))), "unit_cost": str(q6(_d(edit.unit_cost)))}

    # --- 1. Нөөцийн дэвтэр ---
    by_id = {tx.id: tx for tx in plan.rows}
    for tx_id_, (cost, balance) in plan.tx_updates.items():
        tx = by_id[tx_id_]
        if tx_id_ == edit.id:
            tx.qty = plan.new_qty
        tx.unit_cost = cost
        tx.balance_after = balance

    # --- 2. Үлдэгдэл, дундаж өртөг ---
    for (pid, bid), (_before, after) in plan.stock.items():
        if bid is None:
            plan.products[pid].stock_qty = after
    for pid, (_before, after) in plan.avg.items():
        plan.products[pid].avg_cost = after
    branch_keys = [key for key in set(plan.stock) | set(plan.branch_avg) if key[1] is not None]
    if branch_keys:
        rows = {
            (r.product_id, r.branch_id): r
            for r in (
                await db.scalars(
                    select(ProductBranchStock)
                    .where(ProductBranchStock.product_id.in_({k[0] for k in branch_keys}))
                    .with_for_update()
                )
            ).all()
        }
        for key in branch_keys:
            row = rows.get(key)
            if row is None:
                row = ProductBranchStock(product_id=key[0], branch_id=key[1], qty=ZERO, avg_cost=ZERO)
                db.add(row)
            if key in plan.stock:
                row.qty = plan.stock[key][1]
            if key in plan.branch_avg:
                row.avg_cost = plan.branch_avg[key][1]

    # --- 3. Борлуулалтын өртөг + журнал (5102/1302) ---
    for item, unit_cost_new, cogs_new in plan.sale_items.values():
        item.unit_cost = unit_cost_new
        item.cogs_amount = cogs_new
    await db.flush()
    for sale_id, delta in plan.sale_cogs_delta.items():
        sale = plan.sales.get(sale_id)
        if sale is None:
            continue
        items = (await db.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id))).all()
        # Нийт өртгийг зөрүүгээр — баримтын бусад (түлшний) өртөг хөндөгдөхгүй.
        sale.cogs_total = q2(_d(sale.cogs_total) + delta)
        goods_cogs = q2(
            sum((q2(_d(i.cogs_amount)) for i in items if str(i.item_type) != str(ItemType.FUEL)), ZERO)
        )
        entry = await posting.find(
            db, event_type=str(EventType.SALE_POSTED), source_type=str(SourceType.SALE), source_id=sale.id
        )
        if entry is not None:
            await _set_pair(
                db,
                entry,
                debit_account=ACC.COGS_GOODS,
                credit_account=ACC.INV_GOODS,
                amount=goods_cogs,
                dims=Dims(branch_id=sale.branch_id),
                memo_debit="Барааны өртөг",
                memo_credit="Барааны нөөц хасалт",
            )

    # --- 4. Буцаалт (сэргээлтийн өртөг) ---
    refund_delta: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for ri, new_cogs in plan.refund_items.values():
        refund_delta[ri.refund_id] += q2(new_cogs - q2(_d(ri.cogs_amount)))
        ri.cogs_amount = new_cogs
    await db.flush()
    for refund in plan.refunds.values():
        refund.cogs_amount = q2(_d(refund.cogs_amount) + refund_delta.get(refund.id, ZERO))
        if not refund.restock or str(refund.status) != str(ApprovalStatus.APPROVED):
            continue
        lines = (await db.scalars(select(RefundItem).where(RefundItem.refund_id == refund.id))).all()
        line_items = {
            i.id: i
            for i in (
                await db.scalars(select(SaleItem).where(SaleItem.id.in_({ln.sale_item_id for ln in lines})))
            ).all()
        }
        restock_cogs = q2(
            sum(
                (
                    q2(_d(ln.cogs_amount))
                    for ln in lines
                    if line_items.get(ln.sale_item_id) is not None
                    and str(line_items[ln.sale_item_id].item_type) == str(ItemType.PRODUCT)
                ),
                ZERO,
            )
        )
        entry = await posting.find(
            db, event_type=str(EventType.REFUND_POSTED), source_type=str(SourceType.REFUND), source_id=refund.id
        )
        if entry is not None:
            await _set_pair(
                db,
                entry,
                debit_account=ACC.INV_GOODS,
                credit_account=ACC.COGS_GOODS,
                amount=restock_cogs,
                dims=NO_DIMS,
                memo_debit="Буцаалтын нөөц сэргээлт",
                memo_credit="Буцаалтын өртөг сэргээлт",
            )

    # --- 5. Тохируулга, шилжүүлгийн журнал ---
    for tx in plan.adjustments:
        specs = build_inventory_adjustment_lines(tx)
        entry = await posting.find(
            db, event_type=str(EventType.INVENTORY_ADJUSTED), source_type=str(SourceType.INVENTORY_TX), source_id=tx.id
        )
        if entry is not None and specs:
            await _replace_lines(db, entry, specs)
        elif entry is not None:
            await db.delete(entry)
            await db.flush()
        elif specs:
            created = await posting.post(
                db,
                event_type=str(EventType.INVENTORY_ADJUSTED),
                source_type=str(SourceType.INVENTORY_TX),
                source_id=tx.id,
                entry_date=_local_date(tx.created_at),
                description=f"Нөөцийн залруулга — {plan.products[tx.product_id].name_mn} ({q3(_d(tx.qty))})",
                lines=specs,
                posted_by=user.id,
            )
            if created is not None:
                created.created_at = tx.created_at
    for tx_out, tx_in in plan.transfers:
        specs = build_inventory_transfer_lines(tx_out, tx_in)
        entry = await posting.find(
            db,
            event_type=str(EventType.INVENTORY_TRANSFERRED),
            source_type=str(SourceType.INVENTORY_TX),
            source_id=tx_out.id,
        )
        if entry is not None and specs:
            await _replace_lines(db, entry, specs)

    # --- 6. Эхний үлдэгдлийн үнэлгээний засвар — анхны огноогоор (1302 ↔ 3101) ---
    for (entry_date, name), delta in plan.opening_groups().items():
        memo = f"Эхний үлдэгдлийн засвар — {name}"
        await posting.post(
            db,
            event_type=str(EventType.OPENING_BALANCE_POSTED),
            source_type=OPENING_REF,
            source_id=uuid.uuid4(),
            entry_date=entry_date,
            description=memo,
            lines=[
                LineSpec(
                    account_code=ACC.INV_GOODS,
                    debit=delta if delta > ZERO else ZERO,
                    credit=-delta if delta < ZERO else ZERO,
                    memo=memo,
                ),
                LineSpec(
                    account_code=ACC.OWNER_CAPITAL,
                    credit=delta if delta > ZERO else ZERO,
                    debit=-delta if delta < ZERO else ZERO,
                    memo=memo,
                ),
            ],
            posted_by=user.id,
        )

    await db.flush()
    await audit(
        db,
        user_id=user.id,
        action=CORRECTED_ACTION,
        entity_type="inventory_tx",
        entity_id=edit.id,
        before=before,
        after={
            "qty": str(plan.new_qty),
            "unit_cost": str(plan.new_cost),
            "note": (note or "").strip() or None,
            "product": plan.product.name_mn,
            "sales": summary["sales_count"],
            "cogs_change": str(summary["cogs_change"]),
            "value_change": str(summary["value_change"]),
            "shifts_approved": summary["shifts_approved"],
        },
    )
    summary["applied"] = True
    return summary


# =========================================================================== #
# Жагсаалт — эхний үлдэгдлийн түүх
# =========================================================================== #
async def list_openings(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    stmt = (
        select(InventoryTransaction, Product)
        .join(Product, Product.id == InventoryTransaction.product_id)
        .where(_opening_filter())
        .order_by(InventoryTransaction.created_at.desc(), Product.name_mn)
        .limit(limit)
    )
    if branch_id is not None:
        stmt = stmt.where(InventoryTransaction.branch_id == branch_id)
    if product_id is not None:
        stmt = stmt.where(InventoryTransaction.product_id == product_id)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Product.name_mn.ilike(pattern), Product.sku.ilike(pattern)))
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    times = {tx.created_at for tx, _ in rows}
    entries: dict[Any, list[JournalEntry]] = defaultdict(list)
    for entry in (
        await db.scalars(
            select(JournalEntry).where(
                JournalEntry.source_type == OPENING_REF,
                JournalEntry.created_at.in_(times),
            )
        )
    ).all():
        entries[entry.created_at].append(entry)
    user_ids = {e.posted_by for group in entries.values() for e in group if e.posted_by}
    users = (
        {u.id: (u.full_name or u.username) for u in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()}
        if user_ids
        else {}
    )
    branch_ids = {tx.branch_id for tx, _ in rows if tx.branch_id is not None}
    branches = (
        {b.id: b.name for b in (await db.scalars(select(Branch).where(Branch.id.in_(branch_ids)))).all()}
        if branch_ids
        else {}
    )
    corrected = dict(
        (
            await db.execute(
                select(AuditLog.entity_id, func.count())
                .where(
                    AuditLog.action == CORRECTED_ACTION,
                    AuditLog.entity_id.in_([tx.id for tx, _ in rows]),
                )
                .group_by(AuditLog.entity_id)
            )
        ).all()
    )

    out: list[dict[str, Any]] = []
    for tx, product in rows:
        group = entries.get(tx.created_at, [])
        entry = next((e for e in group if e.source_id == product.id), group[0] if group else None)
        qty = q3(_d(tx.qty))
        cost = q6(_d(tx.unit_cost))
        out.append(
            {
                "id": tx.id,
                "product_id": product.id,
                "product_name": product.name_mn,
                "sku": product.sku,
                "unit": product.unit,
                "branch_id": tx.branch_id,
                "branch_name": branches.get(tx.branch_id, "") if tx.branch_id else "",
                "qty": qty,
                "unit_cost": cost,
                "value": q2(qty * cost),
                "as_of": entry.entry_date if entry is not None else _local_date(tx.created_at),
                "entered_at": tx.created_at,
                "entered_by": users.get(entry.posted_by, "") if entry is not None and entry.posted_by else "",
                "source": "product" if str(tx.tx_type) == T_PURCHASE else "opening",
                "note": tx.note,
                "editable": qty > ZERO or int(corrected.get(tx.id, 0)) > 0,
                "corrections": int(corrected.get(tx.id, 0)),
            }
        )
    return out
