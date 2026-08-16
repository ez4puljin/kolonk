"""Идемпотент seed — `python -m app.seed`.

Дахин ажиллуулахад давхардуулахгүй: бүх мөрийг байгалийн түлхүүрээр (code/sku/username)
хайж, байхгүй бол л үүсгэнэ.
"""

import asyncio
import logging
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.database import async_session_factory
from app.enums import (
    CardStatus,
    ContractStatus,
    CustomerType,
    DocStatus,
    ProductSaleMode,
    PumpStatus,
    RoleCode,
    VoucherStatus,
)
from app.models.fuel import Fuel, Pump, PumpNozzle, Tank
from app.models.instrument import PrepaidCard, Voucher
from app.models.partner import Contract, Customer, Supplier
from app.models.procurement import FuelReceipt
from app.models.product import Product, ProductCategory
from app.models.user import Permission, Role, RolePermission, User
from app.money import q2, q6
from app.permissions import PERMISSIONS, ROLE_NAMES_MN, ROLE_PERMISSIONS
from app.security import hash_pin

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed")

# Туршилтад хялбар байх үүднээс бүх хэрэглэгч нэг ПИН-тэй.
# АШИГЛАЛТАД ОРУУЛАХЫН ӨМНӨ хэрэглэгч бүрд өөр ПИН олгоно уу
# (Тохиргоо → Хэрэглэгч → ПИН сэргээх), эс бөгөөс аудит логоос
# хэн үйлдэл хийснийг ялгах боломжгүй.
DEMO_PIN = "000000"

DEMO_USERS = [
    ("bold", "Болд", RoleCode.OWNER, DEMO_PIN),
    ("saraa", "Сараа", RoleCode.MANAGER, DEMO_PIN),
    ("dorj", "Дорж", RoleCode.CASHIER, DEMO_PIN),
    ("tuya", "Туяа", RoleCode.CASHIER, DEMO_PIN),
]

FUELS = [
    ("AI92", "АИ-92", Decimal("2940.00"), "#10B981", 1),
    ("AI95", "АИ-95", Decimal("3180.00"), "#2563EB", 2),
    ("DT", "Дизель", Decimal("3050.00"), "#F59E0B", 3),
]

TANKS = [
    ("1-р сав (АИ-92)", "AI92", Decimal("20000"), Decimal("2000")),
    ("2-р сав (АИ-95)", "AI95", Decimal("15000"), Decimal("1500")),
    ("3-р сав (Дизель)", "DT", Decimal("20000"), Decimal("2000")),
]

# (насосны дугаар, нэр, [(nozzle дугаар, түлшний код)])
PUMPS = [
    (1, "1-р насос", [(1, "AI92"), (2, "AI95")]),
    (2, "2-р насос", [(1, "AI92"), (2, "DT")]),
    (3, "3-р насос", [(1, "AI95"), (2, "DT")]),
    (4, "4-р насос", [(1, "AI92")]),
]

CATEGORIES = [
    ("Тос, тосолгооны материал", "droplet", 1),
    ("Антифриз, ХШУ", "thermometer", 2),
    ("Аккумулятор, цахилгаан", "battery", 3),
    ("Ундаа, ус", "cup-soda", 4),
    ("Хүнс, амттан", "cookie", 5),
    ("Тамхи", "cigarette", 6),
    ("Автын хэрэгсэл", "wrench", 7),
    ("Угаалга, арчилгаа", "spray-can", 8),
]

# Задлан (грамлаж) зарах бүтээгдэхүүн — талбай дээр литр/дүнгээр зарагдана.
# Эхний үлдэгдэлгүй: ширхэг барааг задалж л нөөц үүснэ.
# (sku, нэр, ангиллын индекс, нэгж, 1 нэгжийн үнэ, эх бараа sku, 1 ширхэгээс гарах хэмжээ)
BULK_PRODUCTS = [
    ("BLK-001", "Мотор тос 5W-30 задлан", 0, "л", "21000", "OIL-001", "4"),
    ("BLK-002", "Мотор тос 10W-40 задлан", 0, "л", "19500", "OIL-002", "4"),
    ("BLK-003", "Антифриз ногоон задлан", 1, "л", "11500", "ANT-001", "4"),
]

# (sku, нэр, категорийн индекс, нэгж, зарах үнэ, өртөг, эхний үлдэгдэл)
PRODUCTS = [
    ("OIL-001", "Мотор тос 5W-30 4л", 0, "ш", "78000", "58000", "24"),
    ("OIL-002", "Мотор тос 10W-40 4л", 0, "ш", "72000", "53000", "30"),
    ("OIL-003", "Мотор тос 5W-40 1л", 0, "ш", "22000", "15500", "48"),
    ("OIL-004", "Хурдны хайрцгийн тос ATF 1л", 0, "ш", "26000", "18000", "20"),
    ("OIL-005", "Гидравлик тос 1л", 0, "ш", "19000", "13000", "18"),
    ("OIL-006", "Тормозны шингэн DOT-4", 0, "ш", "17000", "11000", "25"),
    ("ANT-001", "Антифриз ногоон 4л", 1, "ш", "42000", "29000", "22"),
    ("ANT-002", "Антифриз улаан 4л", 1, "ш", "45000", "31000", "16"),
    ("ANT-003", "Хөргөлтийн шингэн 1л", 1, "ш", "13000", "8500", "35"),
    ("ANT-004", "Шил угаагч -30°C 4л", 1, "ш", "16000", "10000", "40"),
    ("BAT-001", "Аккумулятор 60Ah", 2, "ш", "295000", "225000", "6"),
    ("BAT-002", "Аккумулятор 75Ah", 2, "ш", "365000", "280000", "4"),
    ("BAT-003", "Гал хамгаалагчийн иж бүрдэл", 2, "ш", "12000", "7000", "30"),
    ("BAT-004", "Гэрлийн чийдэн H4", 2, "ш", "18000", "11000", "24"),
    ("DRK-001", "Ус 0.5л", 3, "ш", "1500", "900", "120"),
    ("DRK-002", "Ус 1.5л", 3, "ш", "2500", "1600", "80"),
    ("DRK-003", "Кока-Кола 0.5л", 3, "ш", "3000", "2100", "96"),
    ("DRK-004", "Спрайт 0.5л", 3, "ш", "3000", "2100", "72"),
    ("DRK-005", "Эрчим хүчний ундаа", 3, "ш", "5500", "3800", "48"),
    ("DRK-006", "Хүйтэн цай 0.5л", 3, "ш", "3200", "2200", "60"),
    ("DRK-007", "Жүүс 1л", 3, "ш", "6500", "4500", "36"),
    ("FOD-001", "Шоколад", 4, "ш", "4500", "3000", "60"),
    ("FOD-002", "Жигнэмэг", 4, "ш", "3500", "2300", "50"),
    ("FOD-003", "Чипс", 4, "ш", "5000", "3400", "45"),
    ("FOD-004", "Самар 100гр", 4, "ш", "8000", "5500", "30"),
    ("FOD-005", "Бохь", 4, "ш", "2000", "1200", "80"),
    ("FOD-006", "Талх", 4, "ш", "3000", "2000", "20"),
    ("CIG-001", "Мальборо", 5, "ш", "9500", "8000", "50"),
    ("CIG-002", "Винстон", 5, "ш", "8500", "7100", "40"),
    ("CIG-003", "Кэмел", 5, "ш", "9000", "7500", "35"),
    ("TOL-001", "Шүүр (цас цэвэрлэгч)", 6, "ш", "25000", "16000", "15"),
    ("TOL-002", "Домкрат 2т", 6, "ш", "135000", "98000", "5"),
    ("TOL-003", "Чирэх татлага 5т", 6, "ш", "48000", "33000", "10"),
    ("TOL-004", "Насос (компрессор)", 6, "ш", "85000", "62000", "8"),
    ("TOL-005", "Гар чийдэн", 6, "ш", "22000", "14000", "12"),
    ("CLN-001", "Шил арчигч алчуур", 7, "ш", "6000", "3800", "40"),
    ("CLN-002", "Салфетка", 7, "ш", "4000", "2500", "60"),
    ("CLN-003", "Автын шампунь 1л", 7, "ш", "18000", "12000", "20"),
    ("CLN-004", "Гялалзуулагч полироль", 7, "ш", "27000", "18500", "14"),
    ("CLN-005", "Дугуйны хөө арилгагч", 7, "ш", "15000", "9800", "18"),
]

SUPPLIERS = [
    ("НИК ХХК", "2801234", "7000-1234", "5001234567"),
    ("Петровис ХХК", "2805678", "7000-5678", "5005678901"),
    ("Шунхлай ХХК", "2809012", "7000-9012", "5009012345"),
    ("Ундаа Дистрибьютер ХХК", "2811111", "9911-1111", "5011111111"),
]

CUSTOMERS = [
    ("Тээвэр Транс ХХК", "2812345", "9911-2233", "GR-001", Decimal("15000000")),
    ("Барилга Констракшн ХХК", "2823456", "9911-4455", "GR-002", Decimal("25000000")),
    ("Такси Сервис ХХК", "2834567", "9911-6677", "GR-003", Decimal("8000000")),
]


async def seed_permissions_and_roles(db) -> dict[str, Role]:
    existing_perms = {p.code: p for p in (await db.scalars(select(Permission))).all()}
    for code, name in PERMISSIONS.items():
        if code not in existing_perms:
            perm = Permission(code=code, name_mn=name)
            db.add(perm)
            existing_perms[code] = perm
    await db.flush()

    roles: dict[str, Role] = {r.code: r for r in (await db.scalars(select(Role))).all()}
    for code, perm_codes in ROLE_PERMISSIONS.items():
        role = roles.get(code)
        if role is None:
            role = Role(code=code, name_mn=ROLE_NAMES_MN[code])
            db.add(role)
            await db.flush()
            roles[code] = role
        elif role.name_mn != ROLE_NAMES_MN[code]:
            # Нэршил өөрчлөгдсөн бол (Кассчин → Түгээгч) байгаа мөрийг шинэчилнэ.
            role.name_mn = ROLE_NAMES_MN[code]
        current = {rp.permission_id for rp in (await db.scalars(select(RolePermission).where(RolePermission.role_id == role.id))).all()}
        for pc in perm_codes:
            perm = existing_perms[pc]
            if perm.id not in current:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db.flush()
    log.info("Эрх, дүрүүд бэлэн (%d эрх, %d дүр)", len(existing_perms), len(roles))
    return roles


async def seed_users(db, roles: dict[str, Role]) -> None:
    for username, full_name, role_code, pin in DEMO_USERS:
        user = await db.scalar(select(User).where(User.username == username))
        if user is None:
            db.add(
                User(
                    username=username,
                    full_name=full_name,
                    pin_hash=hash_pin(pin),
                    role_id=roles[role_code].id,
                    is_active=True,
                )
            )
    await db.flush()
    log.info("Хэрэглэгчид бэлэн (%d)", len(DEMO_USERS))


async def seed_fuels_and_tanks(db) -> tuple[dict[str, Fuel], dict[str, Tank]]:
    fuels: dict[str, Fuel] = {f.code: f for f in (await db.scalars(select(Fuel))).all()}
    for code, name, price, color, order in FUELS:
        if code not in fuels:
            fuel = Fuel(code=code, name_mn=name, price_per_liter=price, color_hex=color, sort_order=order)
            db.add(fuel)
            fuels[code] = fuel
    await db.flush()

    tanks: dict[str, Tank] = {t.name: t for t in (await db.scalars(select(Tank))).all()}
    for name, fuel_code, capacity, min_level in TANKS:
        if name not in tanks:
            tank = Tank(
                name=name,
                fuel_id=fuels[fuel_code].id,
                capacity_l=capacity,
                current_l=Decimal("0"),
                avg_cost=Decimal("0"),
                min_level_l=min_level,
            )
            db.add(tank)
            tanks[name] = tank
    await db.flush()
    log.info("Түлш, сав бэлэн (%d түлш, %d сав)", len(fuels), len(tanks))
    return fuels, tanks


async def seed_pumps(db, fuels: dict[str, Fuel], tanks: dict[str, Tank]) -> None:
    tank_by_fuel = {t.fuel_id: t for t in tanks.values()}
    for number, name, nozzles in PUMPS:
        pump = await db.scalar(select(Pump).where(Pump.number == number))
        if pump is None:
            pump = Pump(number=number, name=name, status=PumpStatus.IDLE, driver="simulated")
            db.add(pump)
            await db.flush()
        existing = {n.nozzle_number for n in (await db.scalars(select(PumpNozzle).where(PumpNozzle.pump_id == pump.id))).all()}
        for nz_number, fuel_code in nozzles:
            if nz_number not in existing:
                fuel = fuels[fuel_code]
                db.add(
                    PumpNozzle(
                        pump_id=pump.id,
                        nozzle_number=nz_number,
                        fuel_id=fuel.id,
                        tank_id=tank_by_fuel[fuel.id].id,
                        totalizer=Decimal(random.randint(80_000, 250_000)),
                    )
                )
    await db.flush()
    log.info("Насос бэлэн (%d)", len(PUMPS))


async def seed_catalog(db) -> None:
    cats: list[ProductCategory] = []
    for name, icon, order in CATEGORIES:
        cat = await db.scalar(select(ProductCategory).where(ProductCategory.name_mn == name))
        if cat is None:
            cat = ProductCategory(name_mn=name, icon=icon, sort_order=order)
            db.add(cat)
            await db.flush()
        cats.append(cat)

    # Нөөцийг ШУУД оруулахгүй — доор жинхэнэ худалдан авалтын баримтаар
    # оруулснаар өртөг, өглөг, журналын бичилт зөв үүснэ.
    for sku, name, cat_idx, unit, price, _cost, _stock in PRODUCTS:
        product = await db.scalar(select(Product).where(Product.sku == sku))
        if product is None:
            db.add(
                Product(
                    sku=sku,
                    name_mn=name,
                    category_id=cats[cat_idx].id,
                    unit=unit,
                    price=q2(Decimal(price)),
                    avg_cost=Decimal("0"),
                    stock_qty=Decimal("0"),
                    min_stock=Decimal("5"),
                )
            )
    await db.flush()

    # Задлан зарах бүтээгдэхүүн + ширхэг бараатай холбоос.
    for sku, name, cat_idx, unit, price, source_sku, factor in BULK_PRODUCTS:
        bulk = await db.scalar(select(Product).where(Product.sku == sku))
        if bulk is None:
            bulk = Product(
                sku=sku,
                name_mn=name,
                category_id=cats[cat_idx].id,
                unit=unit,
                price=q2(Decimal(price)),
                avg_cost=Decimal("0"),
                stock_qty=Decimal("0"),
                min_stock=Decimal("2"),
                sale_mode=str(ProductSaleMode.BULK),
            )
            db.add(bulk)
            await db.flush()
        source = await db.scalar(select(Product).where(Product.sku == source_sku))
        if source is not None and source.bulk_product_id is None:
            source.bulk_product_id = bulk.id
            source.bulk_factor = Decimal(factor)
    await db.flush()

    log.info(
        "Каталог бэлэн (%d ангилал, %d бараа, %d задлан)",
        len(CATEGORIES),
        len(PRODUCTS),
        len(BULK_PRODUCTS),
    )


async def seed_partners(db) -> None:
    for name, register, phone, account in SUPPLIERS:
        if await db.scalar(select(Supplier).where(Supplier.name == name)) is None:
            db.add(Supplier(name=name, register_no=register, phone=phone, bank_account=account))
    await db.flush()

    for name, register, phone, contract_no, limit in CUSTOMERS:
        customer = await db.scalar(select(Customer).where(Customer.name == name))
        if customer is None:
            customer = Customer(name=name, register_no=register, phone=phone, type=CustomerType.B2B)
            db.add(customer)
            await db.flush()
        if await db.scalar(select(Contract).where(Contract.contract_no == contract_no)) is None:
            db.add(
                Contract(
                    customer_id=customer.id,
                    contract_no=contract_no,
                    credit_limit=limit,
                    balance=Decimal("0"),
                    price_discount_per_l=Decimal("40.00"),
                    billing_day=1,
                    status=ContractStatus.ACTIVE,
                )
            )
    await db.flush()
    log.info("Харилцагч бэлэн (%d нийлүүлэгч, %d гэрээт)", len(SUPPLIERS), len(CUSTOMERS))


async def seed_instruments(db) -> None:
    count = await db.scalar(select(func.count()).select_from(Voucher))
    if not count:
        for i in range(1, 21):
            db.add(
                Voucher(
                    code=f"V{1000000000 + i}",
                    face_value=Decimal("50000.00") if i % 2 else Decimal("100000.00"),
                    status=VoucherStatus.ACTIVE,
                    expires_at=datetime.now(UTC) + timedelta(days=365),
                )
            )
    # Картыг тэг үлдэгдэлтэй үүсгээд доор жинхэнэ цэнэглэлтээр дүүргэнэ —
    # ингэснээр 2302 өр төлбөр журналд зөв бүртгэгдэнэ.
    card_count = await db.scalar(select(func.count()).select_from(PrepaidCard))
    if not card_count:
        for i in range(1, 6):
            db.add(
                PrepaidCard(
                    card_no=f"PC{100000 + i}",
                    holder_name=f"Картын эзэн {i}",
                    balance=Decimal("0"),
                    status=CardStatus.ACTIVE,
                )
            )
    await db.flush()
    log.info("Ваучер, урьдчилсан карт бэлэн")


async def seed_opening_fuel_stock(db, tanks: dict[str, Tank]) -> None:
    """Эхний үлдэгдлийг жинхэнэ таталтын баримтаар оруулна — ингэснээр
    avg_cost бодитой болж, НББ-ийн бичилт балансална."""
    from app.services.receipt_service import post_fuel_receipt

    if await db.scalar(select(func.count()).select_from(FuelReceipt)):
        log.info("Эхний таталт аль хэдийн бүртгэгдсэн")
        return

    supplier = await db.scalar(select(Supplier).where(Supplier.name == "НИК ХХК"))
    owner = await db.scalar(select(User).join(Role).where(Role.code == RoleCode.OWNER))
    opening = [
        ("1-р сав (АИ-92)", Decimal("14000"), Decimal("2450.000000"), Decimal("450000")),
        ("2-р сав (АИ-95)", Decimal("10500"), Decimal("2680.000000"), Decimal("380000")),
        ("3-р сав (Дизель)", Decimal("16000"), Decimal("2560.000000"), Decimal("520000")),
    ]
    for tank_name, liters, unit_cost, freight in opening:
        tank = tanks[tank_name]
        receipt = FuelReceipt(
            supplier_id=supplier.id,
            tank_id=tank.id,
            fuel_id=tank.fuel_id,
            receipt_date=date.today() - timedelta(days=3),
            invoice_no=f"NIC-{tank.name[:1]}-0001",
            liters=liters,
            unit_cost=unit_cost,
            freight_cost=freight,
            status=DocStatus.DRAFT,
        )
        db.add(receipt)
        await db.flush()
        await post_fuel_receipt(db, owner, receipt)
    log.info("Эхний шатахууны нөөц таталтаар бүртгэгдлээ")


async def seed_opening_goods_stock(db) -> None:
    """Барааны эхний үлдэгдлийг жинхэнэ худалдан авалтын баримтаар оруулна."""
    from app.models.procurement import Purchase, PurchaseItem
    from app.services.receipt_service import post_purchase

    if await db.scalar(select(func.count()).select_from(Purchase)):
        log.info("Барааны эхний худалдан авалт аль хэдийн бүртгэгдсэн")
        return

    supplier = await db.scalar(select(Supplier).where(Supplier.name == "Ундаа Дистрибьютер ХХК"))
    owner = await db.scalar(select(User).join(Role).where(Role.code == RoleCode.OWNER))

    purchase = Purchase(
        supplier_id=supplier.id,
        purchase_date=date.today() - timedelta(days=2),
        invoice_no="OPEN-0001",
        status=DocStatus.DRAFT,
        note="Эхний үлдэгдэл",
    )
    db.add(purchase)
    await db.flush()

    for sku, _name, _cat, _unit, _price, cost, stock in PRODUCTS:
        product = await db.scalar(select(Product).where(Product.sku == sku))
        qty, unit_cost = Decimal(stock), q6(Decimal(cost))
        db.add(
            PurchaseItem(
                purchase_id=purchase.id,
                product_id=product.id,
                qty=qty,
                unit_cost=unit_cost,
                amount=q2(qty * unit_cost),
            )
        )
    await db.flush()
    await db.refresh(purchase, ["items"])
    await post_purchase(db, owner, purchase)
    log.info("Барааны эхний нөөц худалдан авалтаар бүртгэгдлээ (%d нэр төрөл)", len(PRODUCTS))


async def seed_prepaid_topups(db) -> None:
    """Урьдчилсан картыг жинхэнэ цэнэглэлтээр дүүргэнэ (2302 өр үүснэ)."""
    from app.models.instrument import PrepaidCardTransaction
    from app.services.instrument_service import topup_card

    if await db.scalar(select(func.count()).select_from(PrepaidCardTransaction)):
        log.info("Картын цэнэглэлт аль хэдийн бүртгэгдсэн")
        return

    owner = await db.scalar(select(User).join(Role).where(Role.code == RoleCode.OWNER))
    for card in (await db.scalars(select(PrepaidCard))).all():
        await topup_card(db, owner, card, Decimal("200000.00"))
    log.info("Урьдчилсан картууд цэнэглэгдлээ")


# (банк, дансны дугаар, эзэмшигч, эхний үлдэгдэл, шимтгэлийн анхдагч)
BANK_ACCOUNTS = [
    ("Хаан банк", "5301234567", "Колонк ХХК", "25000000", True),
    ("Голомт банк", "1105001234", "Колонк ХХК", "8000000", False),
]


async def seed_bank_accounts(db) -> None:
    """Харилцах данс — банкны хуулга оруулахад дугаараар нь холбогдоно."""
    from app.models.bank import BankAccount
    from app.models.branch import Branch

    branch = await db.scalar(select(Branch).order_by(Branch.created_at).limit(1))
    for order, (bank, number, holder, opening, is_fee) in enumerate(BANK_ACCOUNTS):
        exists = await db.scalar(select(BankAccount).where(BankAccount.account_number == number))
        if exists is not None:
            continue
        db.add(
            BankAccount(
                branch_id=branch.id if branch is not None else None,
                bank_name=bank,
                account_number=number,
                holder_name=holder,
                currency="MNT",
                opening_balance=q2(Decimal(opening)),
                is_fee_default=is_fee,
                sort_order=order,
            )
        )
    await db.flush()
    log.info("Харилцах данс бэлэн (%d)", len(BANK_ACCOUNTS))


async def seed_expenses(db) -> None:
    """Жишээ үйл ажиллагааны зардал — орлого зардлын тайлан утгатай харагдана."""
    from app.models.expense import Expense
    from app.services.expense_service import create_expense

    if await db.scalar(select(func.count()).select_from(Expense)):
        log.info("Зардал аль хэдийн бүртгэгдсэн")
        return

    owner = await db.scalar(select(User).join(Role).where(Role.code == RoleCode.OWNER))
    # Анхаар: 5301 (цалин) ба 5302 (НДШ) энд БАЙХГҮЙ — тэдгээрийг цалингийн
    # модуль автоматаар бичдэг тул давхар тоологдох болно.
    demo = [
        ("5311", "480000", "cash", True, "Цахилгааны төлбөр"),
        ("5312", "180000", "cash", True, "Ус, дулаан"),
        ("5321", "1500000", "bank", True, "Талбайн түрээс"),
        ("5313", "90000", "cash", True, "Интернэт, утас"),
    ]
    for code, amount, method, vat, desc in demo:
        await create_expense(
            db,
            owner,
            account_code=code,
            amount=Decimal(amount),
            payment_method=method,
            has_vat=vat,
            description=desc,
        )
    log.info("Жишээ зардал бүртгэгдлээ (%d баримт)", len(demo))


async def seed_employees(db) -> None:
    """Жишээ ажилтнууд — цалингийн модулийг шууд туршихад бэлэн."""
    from app.models.payroll import Employee

    if await db.scalar(select(func.count()).select_from(Employee)):
        log.info("Ажилтан аль хэдийн бүртгэгдсэн")
        return

    staff = [
        ("Батбаяр", "Ахлах түгээгч", "1800000"),
        ("Оюунаа", "Түгээгч", "1500000"),
        ("Ганбат", "Түгээгч", "1350000"),
        ("Цэцэгмаа", "Нягтлан", "2200000"),
        ("Дэлгэрмаа", "Цэвэрлэгч", "900000"),
    ]
    for name, position, salary in staff:
        db.add(
            Employee(
                full_name=name,
                position=position,
                base_salary=Decimal(salary),
                is_active=True,
            )
        )
    await db.flush()
    log.info("Ажилтан бэлэн (%d)", len(staff))


async def seed_branches(db) -> None:
    """Үндсэн салбар. Олон салбар нэмэхэд тайлан, шүүлт өөрөө өргөжинө."""
    from app.models.branch import Branch

    existing = await db.scalar(select(Branch).where(Branch.code == "01"))
    if existing is None:
        existing = Branch(code="01", name="Төв салбар", sort_order=1, is_active=True)
        db.add(existing)
        await db.flush()
        log.info("Салбар үүслээ (%s)", existing.name)

    # Салбаргүй үлдсэн бичлэгүүдийг үндсэн салбарт харьяалуулна (нэг удаагийн нөхөлт).
    from sqlalchemy import update as sa_update

    from app.models.expense import Expense
    from app.models.fuel import Pump, Tank
    from app.models.payroll import Employee
    from app.models.sale import Sale
    from app.models.shift import Shift

    # Кассчдыг салбарт харьяалуулна — нэвтрэхэд салбар нь автоматаар сонгогдоно.
    # Менежер, эзэн салбаргүй: бүх салбарын мэдээллийг хардаг.
    from app.models.user import Role as _Role, User as _User

    cashier_role = await db.scalar(select(_Role).where(_Role.code == RoleCode.CASHIER))
    if cashier_role is not None:
        cashiers = (
            await db.scalars(
                select(_User).where(_User.role_id == cashier_role.id, _User.branch_id.is_(None))
            )
        ).all()
        for cashier in cashiers:
            cashier.branch_id = existing.id
        if cashiers:
            await db.flush()
            log.info("%d түгээгч '%s'-д харьяалагдлаа", len(cashiers), existing.name)

    from app.models.procurement import Purchase as _Purchase
    from app.models.product import InventoryTransaction as _InvTx

    filled = 0
    for model in (Tank, Pump, Shift, Sale, Employee, Expense, _Purchase, _InvTx):
        result = await db.execute(
            sa_update(model).where(model.branch_id.is_(None)).values(branch_id=existing.id)
        )
        filled += result.rowcount or 0
    if filled:
        log.info("Салбаргүй %d бичлэгийг '%s'-д харьяалуулав", filled, existing.name)


async def main() -> None:
    from app.services.coa import ensure_accounts
    from app.services.settings_service import ensure_settings

    async with async_session_factory() as db:
        await ensure_accounts(db)
        await ensure_settings(db)
        roles = await seed_permissions_and_roles(db)
        await seed_users(db, roles)
        await seed_branches(db)
        fuels, tanks = await seed_fuels_and_tanks(db)
        await seed_pumps(db, fuels, tanks)
        await seed_catalog(db)
        await seed_partners(db)
        await seed_instruments(db)
        await seed_opening_fuel_stock(db, tanks)
        await seed_opening_goods_stock(db)
        await seed_prepaid_topups(db)
        await seed_bank_accounts(db)
        await seed_expenses(db)
        await seed_employees(db)
        await seed_branches(db)
        await db.commit()

    log.info("=" * 52)
    log.info("Seed амжилттай дууслаа.")
    for username, full_name, role_code, pin in DEMO_USERS:
        log.info("  %-8s %-6s %-8s ПИН: %s", username, full_name, role_code, pin)
    log.info("=" * 52)


if __name__ == "__main__":
    asyncio.run(main())
