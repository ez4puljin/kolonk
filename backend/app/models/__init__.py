"""All ORM models — imported here so Alembic sees the complete metadata."""

from app.models.accounting import (
    Account,
    ApInvoice,
    ApPayment,
    ArInvoice,
    ArPayment,
    JournalEntry,
    JournalLine,
)
from app.models.approval import PriceChange, Refund, RefundItem
from app.models.bank import (
    BankAccount,
    BankStatement,
    BankStatementConfig,
    BankTransaction,
)
from app.models.expense import Expense
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank, TankMovement, TotalizerReading
from app.models.partner import Contract, Customer, Supplier
from app.models.advance import EmployeeAdvance
from app.models.branch import Branch
from app.models.branch_payment import BranchPaymentMethod
from app.models.payroll import Employee, PayrollLine, PayrollPeriod
from app.models.procurement import FuelReceipt, Purchase, PurchaseItem
from app.models.pricing import BranchPrice
from app.models.product import (
    InventoryTransaction,
    Product,
    ProductBranchStock,
    ProductCategory,
)
from app.models.sale import Payment, Sale, SaleItem
from app.models.shift import (
    Shift,
    ShiftAttachment,
    ShiftClosing,
    ShiftPriceMark,
    ShiftTankLevel,
)
from app.models.system import EbarimtQueue, Setting, SyncOutbox
from app.models.user import AuditLog, Permission, Role, RolePermission, User

__all__ = [
    "Account",
    "BankAccount",
    "BankStatement",
    "BankStatementConfig",
    "BankTransaction",
    "ApInvoice",
    "ApPayment",
    "ArInvoice",
    "ArPayment",
    "AuditLog",
    "Branch",
    "BranchPaymentMethod",
    "BranchPrice",
    "Contract",
    "Customer",
    "EbarimtQueue",
    "Employee",
    "EmployeeAdvance",
    "Expense",
    "Fuel",
    "FuelReceipt",
    "InventoryTransaction",
    "JournalEntry",
    "JournalLine",
    "Payment",
    "PayrollLine",
    "PayrollPeriod",
    "Permission",
    "PriceChange",
    "Product",
    "ProductBranchStock",
    "ProductCategory",
    "Pump",
    "PumpNozzle",
    "Purchase",
    "PurchaseItem",
    "Refund",
    "RefundItem",
    "Role",
    "RolePermission",
    "Sale",
    "SaleItem",
    "Setting",
    "Shift",
    "ShiftAttachment",
    "ShiftClosing",
    "ShiftPriceMark",
    "ShiftTankLevel",
    "Supplier",
    "SyncOutbox",
    "Tank",
    "TankMovement",
    "TotalizerReading",
    "User",
]
