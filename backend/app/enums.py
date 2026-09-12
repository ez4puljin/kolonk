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
    #: Системд шилжих үеийн эхний үлдэгдэл (борлуулалт, худалдан авалт биш).
    OPENING = "opening"


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


class ShipmentStatus(StrEnum):
    """Түлшний ачилтын төлөв."""

    #: Ноорог — засаж, устгаж болно.
    DRAFT = "draft"
    #: Бүртгэсэн — өглөг нээгдэж, машин түгээлтэд гарсан.
    POSTED = "posted"
    #: Хаагдсан — бүх литр саванд орсон/зарагдсан/хорогдсон.
    CLOSED = "closed"


class ShipmentOutflowKind(StrEnum):
    """Машинаас шууд гарсан литрийн төрөл."""

    #: Саванд оруулалгүй шууд борлуулсан.
    SALE = "sale"
    #: Хорогдол, асгаралт — зардалд бичигдэнэ.
    LOSS = "loss"


class SettlementEntryType(StrEnum):
    """Салбарын тооцооны дэвтрийн мөрийн төрөл."""

    #: Толгой компаниас салбарт очсон түлшний өр (түгээлт бүрд үүснэ).
    CHARGE = "charge"
    #: Салбараас толгойн данс руу төлсөн төлбөр.
    PAYMENT = "payment"


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
    OPENING_BALANCE = "opening_balance"
    FUEL_SHIPMENT = "fuel_shipment"
    SHIPMENT_OUTFLOW = "shipment_outflow"
    BRANCH_SETTLEMENT = "branch_settlement"
    #: Нөөцийн залруулга, салбар хоорондын шилжүүлэг (inventory_transactions).
    INVENTORY_TX = "inventory_tx"
    #: Банкны дансны эхний үлдэгдэл.
    BANK_ACCOUNT = "bank_account"


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
    OPENING_BALANCE_POSTED = "OPENING_BALANCE_POSTED"
    SHIPMENT_POSTED = "SHIPMENT_POSTED"
    SHIPMENT_DELIVERY = "SHIPMENT_DELIVERY"
    SHIPMENT_SALE = "SHIPMENT_SALE"
    SHIPMENT_LOSS = "SHIPMENT_LOSS"
    #: Ачилтаас салбарт буусан бараа: Дт 1302 (салбар), Кт 1304.
    SHIPMENT_GOODS_DELIVERY = "SHIPMENT_GOODS_DELIVERY"
    BRANCH_SETTLEMENT_PAID = "BRANCH_SETTLEMENT_PAID"
    #: Тооллогын зөрүү / хорогдол: Дт 5901 (эсвэл Кт 4903) ↔ 1302 (салбар).
    INVENTORY_ADJUSTED = "INVENTORY_ADJUSTED"
    #: Салбар хоорондын барааны шилжүүлэг: Дт 1302 (авсан) / Кт 1302 (өгсөн).
    INVENTORY_TRANSFERRED = "INVENTORY_TRANSFERRED"
    #: Банкны дансны эхний үлдэгдэл: Дт 1110 (данс) / Кт 3101.
    BANK_OPENING_POSTED = "BANK_OPENING_POSTED"


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
