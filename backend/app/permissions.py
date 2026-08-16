"""Permission codes and role → permission mapping (seeded into the DB)."""

from app.enums import RoleCode

PERMISSIONS: dict[str, str] = {
    "sales.create": "Борлуулалт хийх",
    "sales.view": "Борлуулалт харах",
    "sales.view_all": "Бүх борлуулалт харах",
    "sales.refund.request": "Буцаалт хүсэх",
    "sales.refund.approve": "Буцаалт батлах",
    "shifts.open": "Ээлж нээх",
    "shifts.close": "Ээлж хаах",
    "shifts.view_all": "Бүх ээлж харах",
    "tanks.view": "Сав харах",
    "tanks.manage": "Сав удирдах",
    "pumps.view": "Насос харах",
    "pumps.manage": "Насос удирдах",
    "products.view": "Бараа харах",
    "products.manage": "Бараа удирдах",
    "inventory.manage": "Нөөц удирдах",
    "inventory.convert": "Задлан хөрвүүлэх",
    "prices.request": "Үнэ өөрчлөх хүсэх",
    "prices.approve": "Үнэ өөрчлөх батлах",
    "receipts.create": "Шатахуун таталт бүртгэх",
    "purchases.manage": "Худалдан авалт удирдах",
    "expenses.manage": "Зардал бүртгэх",
    "bank.manage": "Харилцах данс, банкны хуулга",
    "payroll.manage": "Цалин тооцох",
    "payroll.approve": "Цалин батлах, олгох",
    "suppliers.manage": "Нийлүүлэгч удирдах",
    "contracts.manage": "Гэрээ удирдах",
    "instruments.manage": "Ваучер/карт удирдах",
    "accounting.view": "НББ харах",
    "accounting.manage": "НББ бичилт хийх",
    "reports.view": "Тайлан харах",
    "dashboard.owner": "Эзний хяналт",
    "users.manage": "Хэрэглэгч удирдах",
    "settings.manage": "Тохиргоо удирдах",
    "backup.manage": "Нөөцлөлт удирдах",
    "audit.view": "Аудит лог харах",
    "ebarimt.manage": "И-баримт удирдах",
}

CASHIER_PERMS = [
    "sales.create",
    "sales.view",
    "sales.refund.request",
    "shifts.open",
    "shifts.close",
    "tanks.view",
    "pumps.view",
    "products.view",
    # Задлан зарах саванд шатахуун дуусахад түгээгч өөрөө шинийг задална.
    "inventory.convert",
]

MANAGER_PERMS = CASHIER_PERMS + [
    "sales.view_all",
    "shifts.view_all",
    "tanks.manage",
    "pumps.manage",
    "products.manage",
    "inventory.manage",
    "prices.request",
    "receipts.create",
    "purchases.manage",
    "expenses.manage",
    "bank.manage",
    "payroll.manage",
    "suppliers.manage",
    "contracts.manage",
    "instruments.manage",
    "accounting.view",
    "reports.view",
    "ebarimt.manage",
]

OWNER_PERMS = list(PERMISSIONS.keys())

ROLE_PERMISSIONS: dict[str, list[str]] = {
    RoleCode.CASHIER: CASHIER_PERMS,
    RoleCode.MANAGER: MANAGER_PERMS,
    RoleCode.OWNER: OWNER_PERMS,
}

ROLE_NAMES_MN: dict[str, str] = {
    RoleCode.CASHIER: "Түгээгч",
    RoleCode.MANAGER: "Менежер",
    RoleCode.OWNER: "Эзэн",
}
