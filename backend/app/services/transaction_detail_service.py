"""Гүйлгээний дэлгэрэнгүй — тайлангийн задаргаанаас давхар товшиход нээгдэнэ.

Эх сурвалж бүрд өөрийн бүтэц:
  * `sale`          — юу юу авсан, хэн зарсан, хэзээ, төлбөрийн хэлбэр, нийт дүн
  * `fuel_receipt`  — нийлүүлэгч, сав, литр, нэгж өртөг, тээвэр, НӨАТ
  * `purchase`      — нийлүүлэгч, барааны мөрүүд
  * `expense`       — зардлын данс, төлбөрийн хэлбэр, тайлбар
  * `tank_movement` / `inventory_tx` — залруулгын мөр
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.expense import Expense
from app.models.fuel import Fuel, Pump, Tank, TankMovement
from app.models.partner import Customer, Supplier
from app.models.payroll import Employee
from app.models.procurement import FuelReceipt, Purchase, PurchaseItem
from app.models.product import InventoryTransaction, Product
from app.models.sale import Payment, Sale, SaleItem
from app.models.user import User
from app.money import q2, q3

ZERO = Decimal("0.00")

TENDER_NAMES = {
    "cash": "Бэлэн",
    "card": "Карт",
    "qr": "QR",
    "transfer": "Шилжүүлэг",
    "contract": "Зээл",
    "voucher": "Ваучер",
    "prepaid": "Урьдчилсан карт",
}


def _d(value: Any, default: Decimal = ZERO) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


async def _person_name(db: AsyncSession, user_id: uuid.UUID | None) -> str:
    if user_id is None:
        return "—"
    employee = await db.scalar(select(Employee).where(Employee.user_id == user_id))
    if employee:
        return employee.full_name
    user = await db.get(User, user_id)
    return user.full_name if user else "—"


async def _branch_name(db: AsyncSession, branch_id: uuid.UUID | None) -> str:
    if branch_id is None:
        return "—"
    branch = await db.get(Branch, branch_id)
    return branch.name if branch else "—"


async def transaction_detail(
    db: AsyncSession, source_type: str, source_id: uuid.UUID
) -> dict[str, Any]:
    """Тайлангийн задаргааны мөрөөс гүйлгээний бүрэн мэдээлэл рүү."""
    if source_type == "sale":
        return await _sale_detail(db, source_id)
    if source_type == "fuel_receipt":
        return await _fuel_receipt_detail(db, source_id)
    if source_type == "purchase":
        return await _purchase_detail(db, source_id)
    if source_type == "expense":
        return await _expense_detail(db, source_id)
    if source_type == "tank_movement":
        return await _tank_movement_detail(db, source_id)
    if source_type == "inventory_tx":
        return await _inventory_tx_detail(db, source_id)
    raise HTTPException(status_code=404, detail="Гүйлгээний төрөл тодорхойгүй")


async def _sale_detail(db: AsyncSession, sale_id: uuid.UUID) -> dict[str, Any]:
    sale = await db.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Борлуулалт олдсонгүй")

    items = (await db.scalars(select(SaleItem).where(SaleItem.sale_id == sale.id))).all()
    payments = (await db.scalars(select(Payment).where(Payment.sale_id == sale.id))).all()

    fuels = {f.id: f for f in (await db.scalars(select(Fuel))).all()}
    products = {p.id: p for p in (await db.scalars(select(Product))).all()}
    pumps = {p.id: p for p in (await db.scalars(select(Pump))).all()}

    customer_name = None
    if sale.customer_id:
        customer = await db.get(Customer, sale.customer_id)
        customer_name = customer.name if customer else None

    lines = []
    for item in sorted(items, key=lambda i: i.line_no or 0):
        if item.fuel_id:
            fuel = fuels.get(item.fuel_id)
            pump = pumps.get(item.pump_id) if item.pump_id else None
            name = fuel.name_mn if fuel else "—"
            extra = f" · {pump.name}" if pump else ""
        else:
            product = products.get(item.product_id)
            name = product.name_mn if product else "—"
            extra = f" · {product.sku}" if product else ""
        lines.append(
            {
                "name": f"{name}{extra}",
                "qty": q3(_d(item.qty)),
                "unit": "л" if item.fuel_id else "ш",
                "unit_price": q2(_d(item.unit_price)),
                "amount": q2(_d(item.amount)),
                "cogs": q2(_d(item.cogs_amount)),
            }
        )

    return {
        "source_type": "sale",
        "source_id": str(sale.id),
        "title": f"Борлуулалт №{sale.number}",
        "when": sale.completed_at,
        "branch": await _branch_name(db, sale.branch_id),
        "person_label": "Борлуулсан",
        "person": await _person_name(db, sale.cashier_id),
        "customer": customer_name,
        "status": sale.status,
        "note": sale.note,
        "lines": lines,
        "payments": [
            {
                "method": p.method,
                "method_name": TENDER_NAMES.get(str(p.method), str(p.method)),
                "amount": q2(_d(p.amount)),
                "received": q2(_d(p.received)) if p.received is not None else None,
                "change_given": q2(_d(p.change_given)) if p.change_given is not None else None,
                "ref_no": p.ref_no,
            }
            for p in payments
        ],
        "subtotal": q2(_d(sale.subtotal)),
        "vat_amount": q2(_d(sale.vat_amount)),
        "total": q2(_d(sale.total)),
    }


async def _fuel_receipt_detail(db: AsyncSession, receipt_id: uuid.UUID) -> dict[str, Any]:
    receipt = await db.get(FuelReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Таталтын баримт олдсонгүй")

    supplier = await db.get(Supplier, receipt.supplier_id)
    tank = await db.get(Tank, receipt.tank_id)
    fuel = await db.get(Fuel, receipt.fuel_id)

    return {
        "source_type": "fuel_receipt",
        "source_id": str(receipt.id),
        "title": f"Шатахуун таталт №{receipt.number}",
        "when": receipt.posted_at or receipt.created_at,
        "branch": await _branch_name(db, tank.branch_id if tank else None),
        "person_label": "Бүртгэсэн",
        "person": await _person_name(db, receipt.posted_by),
        "supplier": supplier.name if supplier else None,
        "invoice_no": receipt.invoice_no,
        "status": receipt.status,
        "note": receipt.note,
        "lines": [
            {
                "name": f"{fuel.name_mn if fuel else '—'} → {tank.name if tank else '—'}",
                "qty": q3(_d(receipt.liters)),
                "unit": "л",
                "unit_price": q2(_d(receipt.unit_cost)),
                "amount": q2(_d(receipt.subtotal)),
                "cogs": ZERO,
            }
        ],
        "extra": [
            {"label": "Тээврийн зардал", "value": q2(_d(receipt.freight_cost))},
            {"label": "Нэгж өртөг (тээвэртэй)", "value": q2(_d(receipt.landed_unit_cost))},
            {"label": "Нягтрал", "value": receipt.density},
            {"label": "Температур °C", "value": receipt.temperature_c},
        ],
        "payments": [],
        "subtotal": q2(_d(receipt.subtotal)),
        "vat_amount": q2(_d(receipt.vat_amount)),
        "total": q2(_d(receipt.total_gross)),
    }


async def _purchase_detail(db: AsyncSession, purchase_id: uuid.UUID) -> dict[str, Any]:
    purchase = await db.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="Худалдан авалт олдсонгүй")

    supplier = await db.get(Supplier, purchase.supplier_id)
    items = (await db.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == purchase.id))).all()
    products = {p.id: p for p in (await db.scalars(select(Product))).all()}

    return {
        "source_type": "purchase",
        "source_id": str(purchase.id),
        "title": f"Худалдан авалт №{purchase.number}",
        "when": purchase.posted_at or purchase.created_at,
        "branch": "—",
        "person_label": "Бүртгэсэн",
        "person": await _person_name(db, purchase.posted_by),
        "supplier": supplier.name if supplier else None,
        "invoice_no": purchase.invoice_no,
        "status": purchase.status,
        "note": purchase.note,
        "lines": [
            {
                "name": (products.get(i.product_id).name_mn if products.get(i.product_id) else "—"),
                "qty": q3(_d(i.qty)),
                "unit": (products.get(i.product_id).unit if products.get(i.product_id) else "ш") or "ш",
                "unit_price": q2(_d(i.unit_cost)),
                "amount": q2(_d(i.amount)),
                "cogs": ZERO,
            }
            for i in items
        ],
        "payments": [],
        "subtotal": q2(_d(purchase.subtotal)),
        "vat_amount": q2(_d(purchase.vat_amount)),
        "total": q2(_d(purchase.total_gross)),
    }


async def _expense_detail(db: AsyncSession, expense_id: uuid.UUID) -> dict[str, Any]:
    expense = await db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Зардал олдсонгүй")

    supplier = None
    if expense.supplier_id:
        row = await db.get(Supplier, expense.supplier_id)
        supplier = row.name if row else None

    from app.services.expense_service import PAYMENT_METHODS

    return {
        "source_type": "expense",
        "source_id": str(expense.id),
        "title": f"Зардал №{expense.number}",
        "when": expense.posted_at or expense.created_at,
        "branch": await _branch_name(db, expense.branch_id),
        "person_label": "Бүртгэсэн",
        "person": await _person_name(db, expense.created_by),
        "supplier": supplier,
        "invoice_no": expense.invoice_no,
        "status": expense.status,
        "note": expense.description,
        "lines": [
            {
                "name": expense.description or expense.account_code,
                "qty": None,
                "unit": "",
                "unit_price": None,
                "amount": q2(_d(expense.subtotal)),
                "cogs": ZERO,
            }
        ],
        "extra": [
            {"label": "Данс", "value": expense.account_code},
            {
                "label": "Төлбөрийн хэлбэр",
                "value": PAYMENT_METHODS.get(expense.payment_method, expense.payment_method),
            },
        ],
        "payments": [],
        "subtotal": q2(_d(expense.subtotal)),
        "vat_amount": q2(_d(expense.vat_amount)),
        "total": q2(_d(expense.total)),
    }


async def _tank_movement_detail(db: AsyncSession, movement_id: uuid.UUID) -> dict[str, Any]:
    mv = await db.get(TankMovement, movement_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="Савны хөдөлгөөн олдсонгүй")
    tank = await db.get(Tank, mv.tank_id)
    fuel = await db.get(Fuel, tank.fuel_id) if tank else None

    return {
        "source_type": "tank_movement",
        "source_id": str(mv.id),
        "title": "Савны залруулга",
        "when": mv.created_at,
        "branch": await _branch_name(db, tank.branch_id if tank else None),
        "person_label": "—",
        "person": "—",
        "status": mv.movement_type,
        "note": mv.note,
        "lines": [
            {
                "name": f"{fuel.name_mn if fuel else '—'} · {tank.name if tank else '—'}",
                "qty": q3(_d(mv.liters)),
                "unit": "л",
                "unit_price": q2(_d(mv.unit_cost)),
                "amount": q2(_d(mv.liters) * _d(mv.unit_cost)),
                "cogs": ZERO,
            }
        ],
        "extra": [{"label": "Дараах үлдэгдэл", "value": q3(_d(mv.balance_after_l))}],
        "payments": [],
        "subtotal": q2(_d(mv.liters) * _d(mv.unit_cost)),
        "vat_amount": ZERO,
        "total": q2(_d(mv.liters) * _d(mv.unit_cost)),
    }


async def _inventory_tx_detail(db: AsyncSession, tx_id: uuid.UUID) -> dict[str, Any]:
    tx = await db.get(InventoryTransaction, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Нөөцийн хөдөлгөөн олдсонгүй")
    product = await db.get(Product, tx.product_id)

    return {
        "source_type": "inventory_tx",
        "source_id": str(tx.id),
        "title": "Нөөцийн хөдөлгөөн",
        "when": tx.created_at,
        "branch": "—",
        "person_label": "—",
        "person": "—",
        "status": tx.tx_type,
        "note": tx.note,
        "lines": [
            {
                "name": product.name_mn if product else "—",
                "qty": q3(_d(tx.qty)),
                "unit": (product.unit if product else "ш") or "ш",
                "unit_price": q2(_d(tx.unit_cost)),
                "amount": q2(_d(tx.qty) * _d(tx.unit_cost)),
                "cogs": ZERO,
            }
        ],
        "extra": [{"label": "Дараах үлдэгдэл", "value": q3(_d(tx.balance_after))}],
        "payments": [],
        "subtotal": q2(_d(tx.qty) * _d(tx.unit_cost)),
        "vat_amount": ZERO,
        "total": q2(_d(tx.qty) * _d(tx.unit_cost)),
    }
