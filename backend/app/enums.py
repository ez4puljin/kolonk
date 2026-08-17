from enum import StrEnum


class RoleCode(StrEnum):
    CASHIER = "cashier"
    MANAGER = "manager"
    OWNER = "owner"


class PumpStatus(StrEnum):
    OFFLINE = "offline"
    IDLE = "idle"
    AUTHORIZED = "authorized"
    FUELING = "fueling"
    COMPLETE = "complete"
    ERROR = "error"


class ShiftStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ShiftPhase(StrEnum):
    OPEN = "open"
    CLOSE = "close"


class ReadingType(StrEnum):
    SHIFT_OPEN = "shift_open"
    SHIFT_CLOSE = "shift_close"
    MANUAL = "manual"


class TankMovementType(StrEnum):
    RECEIPT = "receipt"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    VARIANCE = "variance"


class InventoryTxType(StrEnum):
    PURCHASE = "purchase"
    SALE = "sale"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    #: Задлан хөрвүүлэлт — ширхэг бараанаас гарсан зарлага.
    CONVERT_OUT = "convert_out"
    #: Задлан хөрвүүлэлт — грам бүтээгдэхүүн рүү орсон орлого.
    CONVERT_IN = "convert_in"
    #: Салбар хоорондын шилжүүлэг — өгсөн салбарын зарлага.
    TRANSFER_OUT = "transfer_out"
    #: Салбар хоорондын шилжүүлэг — авсан салбарын орлого.
    TRANSFER_IN = "transfer_in"


class ProductSaleMode(StrEnum):
    """Барааг хэрхэн борлуулах вэ."""

    #: Ширхэгээр — дэлгүүрийн сагсанд бүхэл тоогоор нэмэгдэнэ.
    PIECE = "piece"
    #: Задлан (грамлаж) — талбай дээр литр/дүнгээр, яг түлш шиг зарагдана.
    BULK = "bulk"


class SaleType(StrEnum):
    FUEL = "fuel"
    STORE = "store"
    MIXED = "mixed"


class SaleStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"
    REFUNDED = "refunded"
    PARTIAL_REFUND = "partial_refund"


class ItemType(StrEnum):
    FUEL = "fuel"
    PRODUCT = "product"


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    QR = "qr"
    #: Харилцагч дансаар шилжүүлсэн — банкинд шууд орно (1110).
    TRANSFER = "transfer"
    CONTRACT = "contract"


class DocStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RefundType(StrEnum):
    FULL = "full"
    PARTIAL = "partial"


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class InvoiceStatus(StrEnum):
    OPEN = "open"
    PARTIAL = "partial"
    PAID = "paid"


class ContractStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class CustomerType(StrEnum):
    B2B = "b2b"
    INDIVIDUAL = "individual"


class EbarimtStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class CashAccount(StrEnum):
    BANK = "bank"
    CASH = "cash"


class SourceType(StrEnum):
    SALE = "sale"
    FUEL_RECEIPT = "fuel_receipt"
    PURCHASE = "purchase"
    AP_PAYMENT = "ap_payment"
    AR_PAYMENT = "ar_payment"
    SHIFT = "shift"
    REFUND = "refund"
    MANUAL = "manual"
    SETTLEMENT = "settlement"
    EXPENSE = "expense"
    PAYROLL = "payroll"


class EventType(StrEnum):
    SALE_POSTED = "SALE_POSTED"
    FUEL_RECEIPT_POSTED = "FUEL_RECEIPT_POSTED"
    PURCHASE_POSTED = "PURCHASE_POSTED"
    AP_PAYMENT = "AP_PAYMENT"
    AR_RECEIPT = "AR_RECEIPT"
    SHIFT_CASH_SHORT = "SHIFT_CASH_SHORT"
    SHIFT_CASH_OVER = "SHIFT_CASH_OVER"
    FUEL_VARIANCE_LOSS = "FUEL_VARIANCE_LOSS"
    FUEL_VARIANCE_GAIN = "FUEL_VARIANCE_GAIN"
    REFUND_POSTED = "REFUND_POSTED"
    CARD_SETTLEMENT = "CARD_SETTLEMENT"
    QR_SETTLEMENT = "QR_SETTLEMENT"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    EXPENSE_POSTED = "EXPENSE_POSTED"
    PAYROLL_POSTED = "PAYROLL_POSTED"
    PAYROLL_PAID = "PAYROLL_PAID"
    ADVANCE_PAID = "ADVANCE_PAID"


class PresetType(StrEnum):
    LITERS = "liters"
    AMOUNT = "amount"
    FULL = "full"


class PayrollStatus(StrEnum):
    """Цалингийн хугацааны төлөв."""

    DRAFT = "draft"          # тооцоолсон, засаж болно
    APPROVED = "approved"    # батлагдаж журналд бичигдсэн
    PAID = "paid"            # цалин олгогдсон


class PayrollPayTarget(StrEnum):
    """Цалингийн өглөгийн ямар хэсгийг төлж байгаа вэ."""

    SALARY = "salary"        # ажилтнуудын гарт олгох цэвэр цалин (2401)
    PIT = "pit"              # ХХОАТ татварын албанд (2402)
    SOCIAL = "social"        # НДШ даатгалын байгууллагад (2403)
