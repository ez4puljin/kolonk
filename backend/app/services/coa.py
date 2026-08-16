"""Дансны төлөвлөгөө (Chart of Accounts).

CONTRACTS.md §4-д тогтоосон дансны кодууд. Бусад бүх модуль зөвхөн ``ACC``
тогтмолуудыг ашиглана — код руу шууд string бичихийг хориглоно.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AccountType, PaymentMethod
from app.models.accounting import Account


class ACC:
    """Дансны кодын тогтмолууд (CONTRACTS.md §4)."""

    # --- Хөрөнгө ---
    CASH = "1101"
    CARD_CLEARING = "1102"
    QR_CLEARING = "1103"
    BANK = "1110"
    AR_CONTRACT = "1201"
    #: Ажилтанд олгосон урьдчилгаа — цалингаас суутгаж хаагдана.
    AR_EMPLOYEE = "1205"
    INV_FUEL = "1301"
    INV_GOODS = "1302"
    VAT_INPUT = "1402"

    # --- Өр төлбөр ---
    AP_SUPPLIER = "2101"
    VAT_OUTPUT = "2201"
    VOUCHER_LIABILITY = "2301"
    PREPAID_LIABILITY = "2302"
    # --- Цалингийн өглөгүүд ---
    AP_SALARY = "2401"
    AP_PIT = "2402"
    AP_SOCIAL_INS = "2403"

    # --- Эздийн өмч ---
    OWNER_CAPITAL = "3101"
    RETAINED = "3201"

    # --- Орлого ---
    REV_FUEL = "4101"
    REV_GOODS = "4102"
    SALES_RETURNS = "4901"
    OTHER_INCOME = "4903"

    # --- Зардал: борлуулсан бүтээгдэхүүний өртөг ---
    COGS_FUEL = "5101"
    COGS_GOODS = "5102"

    # --- Зардал: үйл ажиллагааны (гараар бүртгэгддэг) ---
    EXP_SALARY = "5301"
    EXP_SOCIAL_INS = "5302"
    EXP_ELECTRICITY = "5311"
    EXP_WATER_HEAT = "5312"
    EXP_COMMUNICATION = "5313"
    EXP_RENT = "5321"
    EXP_REPAIR = "5331"
    EXP_TRANSPORT = "5341"
    EXP_SUPPLIES = "5351"
    EXP_ADVERTISING = "5361"
    EXP_BANK_FEE = "5371"
    EXP_TAX_FEE = "5381"
    EXP_SECURITY = "5391"
    EXP_DEPRECIATION = "5401"
    EXP_OTHER = "5901"

    # --- Зардал: автоматаар бичигддэг зөрүү ---
    FUEL_LOSS = "5201"
    CASH_SHORT = "5902"

    #: Гараар бүртгэх боломжтой үйл ажиллагааны зардлын данснууд.
    #: Зөвхөн эдгээрт зардлын баримт бичиж болно — өртөг (5101/5102) ба
    #: зөрүүний данснууд (5201/5902) нь системээс автоматаар бичигддэг тул
    #: гараар бүртгэхийг хориглоно.
    OPERATING_EXPENSES: tuple[str, ...] = (
        EXP_SALARY,
        EXP_SOCIAL_INS,
        EXP_ELECTRICITY,
        EXP_WATER_HEAT,
        EXP_COMMUNICATION,
        EXP_RENT,
        EXP_REPAIR,
        EXP_TRANSPORT,
        EXP_SUPPLIES,
        EXP_ADVERTISING,
        EXP_BANK_FEE,
        EXP_TAX_FEE,
        EXP_SECURITY,
        EXP_DEPRECIATION,
        EXP_OTHER,
    )

    # --- Толгой (postable биш) данснууд ---
    HDR_ASSET = "1000"
    HDR_LIABILITY = "2000"
    HDR_EQUITY = "3000"
    HDR_REVENUE = "4000"
    HDR_EXPENSE = "5000"

    #: Тайлант үеийн ашиг — балансад тооцоолж гаргадаг виртуал мөр (данс биш).
    CURRENT_EARNINGS = "3900"

    #: Төлбөрийн хэрэгсэл → дебит хийх данс (CONTRACTS.md §4).
    TENDER_ACCOUNTS: dict[str, str] = {
        PaymentMethod.CASH: CASH,
        PaymentMethod.CARD: CARD_CLEARING,
        PaymentMethod.QR: QR_CLEARING,
        PaymentMethod.CONTRACT: AR_CONTRACT,
        PaymentMethod.VOUCHER: VOUCHER_LIABILITY,
        PaymentMethod.PREPAID: PREPAID_LIABILITY,
    }

    #: Өртгийн данснууд (ашгийн тайланд борлуулсан бүтээгдэхүүний өртөг).
    COGS_ACCOUNTS: tuple[str, ...] = (COGS_FUEL, COGS_GOODS)

    @classmethod
    def tender_account(cls, method: str) -> str:
        """Төлбөрийн хэрэгслийн код → дебит хийх дансны код."""
        try:
            return cls.TENDER_ACCOUNTS[str(method)]
        except KeyError as exc:  # noqa: PERF203
            raise ValueError(f"Тодорхойгүй төлбөрийн хэрэгсэл: {method}") from exc


def _acc(
    code: str,
    name_mn: str,
    account_type: str,
    sort_order: int,
    *,
    parent_code: str | None = None,
    is_postable: bool = True,
) -> dict[str, Any]:
    return {
        "code": code,
        "name_mn": name_mn,
        "account_type": str(account_type),
        "is_postable": is_postable,
        "parent_code": parent_code,
        "sort_order": sort_order,
    }


COA_SEED: list[dict[str, Any]] = [
    # ---------------- 1000 Хөрөнгө ----------------
    _acc(ACC.HDR_ASSET, "Хөрөнгө", AccountType.ASSET, 1000, is_postable=False),
    _acc(ACC.CASH, "Касс — бэлэн мөнгө", AccountType.ASSET, 1101, parent_code=ACC.HDR_ASSET),
    _acc(ACC.CARD_CLEARING, "Картын гүйлгээний тооцоо", AccountType.ASSET, 1102, parent_code=ACC.HDR_ASSET),
    _acc(ACC.QR_CLEARING, "QR гүйлгээний тооцоо", AccountType.ASSET, 1103, parent_code=ACC.HDR_ASSET),
    _acc(ACC.BANK, "Харилцах данс", AccountType.ASSET, 1110, parent_code=ACC.HDR_ASSET),
    _acc(ACC.AR_CONTRACT, "Гэрээт худалдан авагчийн авлага", AccountType.ASSET, 1201, parent_code=ACC.HDR_ASSET),
    _acc(ACC.AR_EMPLOYEE, "Ажилтны урьдчилгаа", AccountType.ASSET, 1205, parent_code=ACC.HDR_ASSET),
    _acc(ACC.INV_FUEL, "Түлшний бараа материал", AccountType.ASSET, 1301, parent_code=ACC.HDR_ASSET),
    _acc(ACC.INV_GOODS, "Дэлгүүрийн бараа материал", AccountType.ASSET, 1302, parent_code=ACC.HDR_ASSET),
    _acc(ACC.VAT_INPUT, "Орох НӨАТ", AccountType.ASSET, 1402, parent_code=ACC.HDR_ASSET),
    # ---------------- 2000 Өр төлбөр ----------------
    _acc(ACC.HDR_LIABILITY, "Өр төлбөр", AccountType.LIABILITY, 2000, is_postable=False),
    _acc(ACC.AP_SUPPLIER, "Нийлүүлэгчийн өглөг", AccountType.LIABILITY, 2101, parent_code=ACC.HDR_LIABILITY),
    _acc(ACC.VAT_OUTPUT, "Гарах НӨАТ", AccountType.LIABILITY, 2201, parent_code=ACC.HDR_LIABILITY),
    _acc(ACC.VOUCHER_LIABILITY, "Ваучерын өр төлбөр", AccountType.LIABILITY, 2301, parent_code=ACC.HDR_LIABILITY),
    _acc(
        ACC.PREPAID_LIABILITY,
        "Урьдчилсан төлбөрт картын өр",
        AccountType.LIABILITY,
        2302,
        parent_code=ACC.HDR_LIABILITY,
    ),
    _acc(ACC.AP_SALARY, "Цалингийн өглөг", AccountType.LIABILITY, 2401, parent_code=ACC.HDR_LIABILITY),
    _acc(ACC.AP_PIT, "ХХОАТ-ын өглөг", AccountType.LIABILITY, 2402, parent_code=ACC.HDR_LIABILITY),
    _acc(ACC.AP_SOCIAL_INS, "НДШ-ийн өглөг", AccountType.LIABILITY, 2403, parent_code=ACC.HDR_LIABILITY),
    # ---------------- 3000 Эздийн өмч ----------------
    _acc(ACC.HDR_EQUITY, "Эздийн өмч", AccountType.EQUITY, 3000, is_postable=False),
    _acc(ACC.OWNER_CAPITAL, "Эзний оруулсан хөрөнгө", AccountType.EQUITY, 3101, parent_code=ACC.HDR_EQUITY),
    _acc(ACC.RETAINED, "Хуримтлагдсан ашиг", AccountType.EQUITY, 3201, parent_code=ACC.HDR_EQUITY),
    # ---------------- 4000 Орлого ----------------
    _acc(ACC.HDR_REVENUE, "Орлого", AccountType.REVENUE, 4000, is_postable=False),
    _acc(ACC.REV_FUEL, "Түлшний борлуулалтын орлого", AccountType.REVENUE, 4101, parent_code=ACC.HDR_REVENUE),
    _acc(ACC.REV_GOODS, "Барааны борлуулалтын орлого", AccountType.REVENUE, 4102, parent_code=ACC.HDR_REVENUE),
    _acc(ACC.SALES_RETURNS, "Борлуулалтын буцаалт", AccountType.REVENUE, 4901, parent_code=ACC.HDR_REVENUE),
    _acc(ACC.OTHER_INCOME, "Бусад орлого", AccountType.REVENUE, 4903, parent_code=ACC.HDR_REVENUE),
    # ---------------- 5000 Зардал ----------------
    _acc(ACC.HDR_EXPENSE, "Зардал", AccountType.EXPENSE, 5000, is_postable=False),
    _acc(ACC.COGS_FUEL, "Түлшний борлуулалтын өртөг", AccountType.EXPENSE, 5101, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.COGS_GOODS, "Барааны борлуулалтын өртөг", AccountType.EXPENSE, 5102, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.FUEL_LOSS, "Түлшний хорогдол, дутагдал", AccountType.EXPENSE, 5201, parent_code=ACC.HDR_EXPENSE),
    # --- Үйл ажиллагааны зардал (зардлын баримтаар гараар бүртгэнэ) ---
    _acc(ACC.EXP_SALARY, "Цалин хөлс", AccountType.EXPENSE, 5301, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_SOCIAL_INS, "Нийгмийн даатгалын шимтгэл", AccountType.EXPENSE, 5302, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_ELECTRICITY, "Цахилгааны зардал", AccountType.EXPENSE, 5311, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_WATER_HEAT, "Ус, дулааны зардал", AccountType.EXPENSE, 5312, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_COMMUNICATION, "Холбоо, интернэтийн зардал", AccountType.EXPENSE, 5313, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_RENT, "Түрээсийн зардал", AccountType.EXPENSE, 5321, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_REPAIR, "Засвар үйлчилгээний зардал", AccountType.EXPENSE, 5331, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_TRANSPORT, "Тээвэр, шатахууны зардал", AccountType.EXPENSE, 5341, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_SUPPLIES, "Бичиг хэрэг, аж ахуйн зардал", AccountType.EXPENSE, 5351, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_ADVERTISING, "Зар сурталчилгааны зардал", AccountType.EXPENSE, 5361, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_BANK_FEE, "Банкны шимтгэл", AccountType.EXPENSE, 5371, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_TAX_FEE, "Татвар, хураамж", AccountType.EXPENSE, 5381, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_SECURITY, "Хамгаалалт, цэвэрлэгээ", AccountType.EXPENSE, 5391, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_DEPRECIATION, "Элэгдэл, хорогдол", AccountType.EXPENSE, 5401, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.EXP_OTHER, "Бусад зардал", AccountType.EXPENSE, 5901, parent_code=ACC.HDR_EXPENSE),
    _acc(ACC.CASH_SHORT, "Кассын дутагдал", AccountType.EXPENSE, 5902, parent_code=ACC.HDR_EXPENSE),
]

#: Кодоор нь хайхад зориулсан индекс.
COA_BY_CODE: dict[str, dict[str, Any]] = {row["code"]: row for row in COA_SEED}


async def ensure_accounts(db: AsyncSession) -> None:
    """``COA_SEED``-ийг ``accounts`` хүснэгтэд идемпотентоор нийлүүлнэ.

    Дахин дуудахад давхардал үүсгэхгүй, зөвхөн нэр/төрөл/эрэмбийг шинэчилнэ.
    Commit хийхгүй — ``get_db`` эзэмшинэ.
    """
    existing = {a.code: a for a in (await db.scalars(select(Account))).all()}
    for spec in COA_SEED:
        row = existing.get(spec["code"])
        if row is None:
            db.add(Account(**spec))
            continue
        row.name_mn = spec["name_mn"]
        row.account_type = spec["account_type"]
        row.is_postable = spec["is_postable"]
        row.parent_code = spec["parent_code"]
        row.sort_order = spec["sort_order"]
    await db.flush()
