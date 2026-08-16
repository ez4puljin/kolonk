# CONTRACTS.md — Колонк ШТС POS/ERP дотоод гэрээ

Энэ бол зэрэгцээ ажиллаж буй бүх хэрэгжүүлэгчийн **заавал дагах** гэрээ. Энд заасан нэр, зам, төрлийг өөрчилж болохгүй.

## 0. Аль хэдийн бэлэн байгаа суурь (дахин бүү бич, зөвхөн импортло)

| Файл | Агуулга |
|---|---|
| `app/config.py` | `settings` (database_url, redis_url, jwt_*, vat_rate, ebarimt_mode, backup_dir, station_name) |
| `app/database.py` | `engine`, `async_session_factory`, `Base`, `get_db` (**commit-ийг get_db хийнэ**) |
| `app/money.py` | `q2`, `q3`, `q6`, `vat_from_gross`, `net_from_gross`, `split_remainder` |
| `app/enums.py` | Бүх StrEnum (RoleCode, PumpStatus, PaymentMethod, EventType, SourceType, ...) |
| `app/permissions.py` | `PERMISSIONS` dict, `ROLE_PERMISSIONS`, `ROLE_NAMES_MN` |
| `app/security.py` | `hash_pin`, `verify_pin`, `create_token`, `decode_token` |
| `app/deps.py` | `get_current_user`, `require_permission("code", ...)`, `user_permissions` |
| `app/redis_client.py` | `get_redis()`, `publish(channel, dict)`, `PUMP_CHANNEL` |
| `app/models/*` | Бүх ORM модель — **өөрчлөхгүй**, зөвхөн импортлоно |
| `app/services/outbox_service.py` | `emit(db, aggregate_type=, aggregate_id=, event_type=, payload=)` |
| `app/services/audit_service.py` | `audit(db, user_id=, action=, entity_type=, entity_id=, before=, after=, ip=)` |

## 1. Транзакцийн дүрэм (ЗӨРЧВӨЛ АЛДАА)

- Service функц **хэзээ ч `db.commit()` дуудахгүй**. `get_db` dependency нэг л commit хийнэ.
- Хэрэгтэй бол `await db.flush()` ашиглаж ID авна.
- Нэг бизнес үйлдэл = домэйн өөрчлөлт + журнал бичилт + outbox + audit — бүгд нэг transaction.

## 1a. Цаг хугацааны дүрэм (ЗӨРЧВӨЛ ТАЙЛАН БУРУУ ГАРНА)

- Бүх `timestamptz` баганыг **UTC**-ээр хадгална.
- Хэрэглэгчийн сонгодог **огноо** нь станцын орон нутгийн огноо (`TZ`, Улаанбаатар UTC+8).
- Огноо → хугацааны муж хөрвүүлэлтийг **зөвхөн** `app/stationtime.py`-аас хийнэ
  (`day_start`, `day_end`, `range_bounds`, `today_local`).
- `datetime.combine(..., tzinfo=UTC)` бичихийг **хориглоно**: орон нутгийн 08:00-аас
  өмнөх борлуулалт "өнөөдөр"-ийн шүүлтээс унана.

## 2. Мөнгөний дүрэм

- Python талд зөвхөн `Decimal`. `float()` хориотой.
- Бүх мөнгө `q2()`-оор дугуйлна, литр `q3()`, нэгж өртөг `q6()`.
- НӨАТ борлуулалтын үнэд **шингэсэн**: `vat_from_gross(gross)` = gross/11.
- Нийлүүлэгчийн баримт НӨАТ-**гүй** дүнгээр орж, НӨАТ нэмэгдэнэ (орох НӨАТ 1402).
- Pydantic response-д мөнгө `Decimal` → JSON руу **string**-ээр гарна (`model_config = ConfigDict(json_encoders=...)` хэрэггүй, FastAPI Decimal-ыг string болгоно). Frontend талд parseFloat **хориотой**.

## 3. PostingService интерфэйс (WP3 хэрэгжүүлнэ, бусад нь заавал энэ дагуу дуудна)

```python
# app/services/posting.py
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Dims:
    fuel_id: UUID | None = None
    tank_id: UUID | None = None
    customer_id: UUID | None = None
    supplier_id: UUID | None = None
    bank_account_id: UUID | None = None   # зөвхөн 1110 мөрд

@dataclass(frozen=True)
class LineSpec:
    account_code: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    memo: str | None = None
    dims: Dims = Dims()

class PostingService:
    async def post(self, db, *, event_type: str, source_type: str, source_id: UUID,
                   entry_date: date, description: str, lines: list[LineSpec],
                   posted_by: UUID | None = None) -> JournalEntry | None: ...

posting = PostingService()   # module-level singleton
```

Дүрэм: Σdebit == Σcredit эсэхийг шалгаж, зөрвөл `UnbalancedEntryError`. Тэг мөрүүд хасагдана. Идемпотент: `(source_type, source_id, event_type)` давхардвал байгаа бичилтээ буцаана.

## 4. Дансны код (`app/services/coa.py` → `ACC` тогтмол)

`ACC.CASH="1101"`, `ACC.CARD_CLEARING="1102"`, `ACC.QR_CLEARING="1103"`, `ACC.BANK="1110"`, `ACC.AR_CONTRACT="1201"`, `ACC.INV_FUEL="1301"`, `ACC.INV_GOODS="1302"`, `ACC.VAT_INPUT="1402"`, `ACC.AP_SUPPLIER="2101"`, `ACC.VAT_OUTPUT="2201"`, `ACC.VOUCHER_LIABILITY="2301"`, `ACC.PREPAID_LIABILITY="2302"`, `ACC.OWNER_CAPITAL="3101"`, `ACC.RETAINED="3201"`, `ACC.REV_FUEL="4101"`, `ACC.REV_GOODS="4102"`, `ACC.SALES_RETURNS="4901"`, `ACC.OTHER_INCOME="4903"`, `ACC.COGS_FUEL="5101"`, `ACC.COGS_GOODS="5102"`, `ACC.FUEL_LOSS="5201"`, `ACC.CASH_SHORT="5902"`.

Tender → дебит данс: cash→1101, card→1102, qr→1103, contract→1201, voucher→2301, prepaid→2302 (`ACC.tender_account(method)` функц WP3 гаргана).

## 5. Бичилтийн дүрэм (posting_rules.py)

| event_type | Дебит | Кредит |
|---|---|---|
| `SALE_POSTED` | төлбөр мөр тус бүр tender данс; 5101 = Σ түлш COGS (dim_fuel/tank), 5102 = Σ бараа COGS | 4101 = түлш net, 4102 = бараа net, 2201 = НӨАТ; 1301 = түлш COGS, 1302 = бараа COGS |
| `VOUCHER_SOLD` | tender данс | 2301 |
| `PREPAID_TOPUP` | tender данс | 2302 |
| `FUEL_RECEIPT_POSTED` | 1301 = liters·unit_cost + freight; 1402 = НӨАТ | 2101 = нийт (dim_supplier) |
| `PURCHASE_POSTED` | 1302 = subtotal; 1402 = НӨАТ | 2101 (dim_supplier) |
| `AP_PAYMENT` | 2101 (dim_supplier) | 1110 эсвэл 1101 |
| `AR_RECEIPT` | 1110 (dim_bank_account) эсвэл 1101 | 1201 (dim_customer) |
| `SHIFT_CASH_SHORT` | 5902 | 1101 |
| `SHIFT_CASH_OVER` | 1101 | 4903 |
| `FUEL_VARIANCE_LOSS` | 5201 (dim_tank/fuel) | 1301 |
| `FUEL_VARIANCE_GAIN` | 1301 | 4903 |
| `REFUND_POSTED` | 4901 = net, 2201 = НӨАТ (+restock бол 1302) | 1101 (+restock бол 5102) |
| `EXPENSE_POSTED` | зардлын данс (5301–5901) НӨАТ-гүй дүн, 1402 НӨАТ | 1101 (бэлэн) / 1110 (банк) / 2101 (өглөг) |
| `PAYROLL_POSTED` | 5301 нийт цалин, 5302 ажил олгогчийн НДШ | 2401 гарт олгох, 2402 ХХОАТ, 2403 НДШ, 1205 суутгасан урьдчилгаа |
| `PAYROLL_PAID` | 2401 / 2402 / 2403 | 1110 (банк) эсвэл 1101 (касс) |
| `ADVANCE_PAID` | 1205 Ажилтны урьдчилгаа | 1101 / 1110 |
| `CARD_SETTLEMENT` / `QR_SETTLEMENT` | 1110 | 1102 / 1103 |
| `MANUAL_ENTRY` | гараар | гараар |

### Үйл ажиллагааны зардал

Дансны төлөвлөгөөний `5000` бүлэг хоёр төрөлтэй:

| Хэсэг | Данс | Хэрхэн бичигдэх |
|---|---|---|
| Борлуулалтын өртөг | 5101, 5102 | борлуулалтаас **автоматаар** |
| Үйл ажиллагааны зардал | 5301–5901 | зардлын баримтаар **гараар** |
| Зөрүү | 5201, 5902 | ээлж хаахад **автоматаар** |

`ACC.OPERATING_EXPENSES` дотор байгаа данс руу л зардлын баримт бичиж болно —
өртөг ба зөрүүний данс руу гараар бичихийг `build_expense_lines` хориглоно.

Зардлын дүн нь **төлсөн нийт дүнгээр** орж, `has_vat=true` үед НӨАТ уг дүнд
шингэсэн гэж үзэж салгана (борлуулалттай ижил дүрэм).

Бэлнээр төлсөн зардал нь ээлжийн байвал зохих кассаас **автоматаар** хасагдана
— `_other_cash_movement` нь `1101` дансны хөдөлгөөнийг ерөнхий дэвтрээс уншдаг
тул нэмэлт код шаардахгүй.

### Цалингийн тооцоо

Ажилтан тус бүрийн тооцоо (`payroll_service.compute_line` — цэвэр функц, тесттэй):

```
ажилласан цалин = үндсэн цалин × ажилласан хоног / сарын хоног
нийт цалин      = ажилласан цалин + урамшуулал + бусад нэмэгдэл
НДШ (ажилтан)   = нийт цалин × ажилтны хувь          (дээд хязгаартай)
ХХОАТ суурь     = нийт цалин − НДШ (ажилтан)
ХХОАТ           = max(0, суурь × хувь − сарын хөнгөлөлт)
гарт олгох      = нийт цалин − НДШ − ХХОАТ − урьдчилгаа − бусад суутгал
НДШ (ажил олгогч) = нийт цалин × ажил олгогчийн хувь  → 5302 зардал
```

Хувь хэмжээ нь **тохиргоонд** (`payroll_si_employee_rate`, `payroll_si_employer_rate`,
`payroll_pit_rate`, `payroll_pit_credit`, `payroll_si_base_cap`) — хууль өөрчлөгдөхөд
код засах шаардлагагүй. Хугацаа үүсэх үед тухайн үеийн хувийг **хугацаанд хуулж
хадгална**, ингэснээр хуучин тооцоо анх батлагдсан дүрмээрээ хэвээр үлдэнэ.

Төлөв: `draft` (засаж болно) → `approved` (журналд бичигдсэн, засах боломжгүй)
→ `paid` (гурван өглөг бүрэн хаагдсан).

**Урьдчилгаа:** олгоход `1205` авлага үүснэ (`ADVANCE_PAID`), цалин бодоход
суутгагдаж хаагдана. Бэлнээр олгосон бол ээлжийн кассаас автоматаар хасагдана.

**Эрх:** `payroll.manage` (менежер, эзэн) — тооцоолох, засах, урьдчилгаа олгох;
`payroll.approve` (**зөвхөн эзэн**) — батлах ба төлөх.

### Ээлжийн хүлээгдэх кассын дүрэм

```
хүлээгдэх касс = эхний касс
               + бэлэн борлуулалт
               − бэлнээр буцаасан
               + бусад кассын хөдөлгөөн
```

**Бусад кассын хөдөлгөөн** нь ээлжийн хугацаанд `1101` дансанд хийгдсэн
бичилтийн (дебит − кредит) нийлбэр, гэхдээ `sale`, `refund`, `shift` эх
сурвалжтайг хасна. Ингэснээр ваучер бэлнээр зарах, урьдчилсан карт цэнэглэх,
кассаас нийлүүлэгчид төлөх зэрэг **борлуулалт биш** кассын хөдөлгөөн автоматаар
тооцогдоно. Кассд мөнгө оруулдаг шинэ үйл явдал нэмэгдэхэд `posting`-оор
`1101`-д бичигдсэн бол ямар ч нэмэлт кодгүйгээр зөв тооцогдоно.

## 6. Нөөцийн үйлчилгээ (WP7 хэрэгжүүлнэ, WP6 дуудна)

```python
# app/services/inventory_service.py
async def consume_product(db, product, qty: Decimal, *, ref_type: str, ref_id: UUID) -> Decimal
    """stock_qty-г хасаж, InventoryTransaction бичиж, COGS дүнг (qty*avg_cost) буцаана."""
async def restock_product(db, product, qty: Decimal, unit_cost: Decimal, *, ref_type, ref_id) -> None
async def receive_product(db, product, qty: Decimal, unit_cost: Decimal, *, ref_type, ref_id) -> None
    """Moving average: new_avg = (old_qty*old_avg + qty*unit_cost) / (old_qty+qty)"""
async def convert_to_bulk(db, source, target, qty: Decimal, out_qty: Decimal, *, branch_id, ...) -> tuple
    """Ширхэг барааг задалж грам бүтээгдэхүүн рүү (`sale_mode=bulk`) шилжүүлнэ.
    Өртөг бүрэн шилжинэ (qty*avg_cost) тул хоёулаа 1302-т байдаг — журналын
    бичилт ҮҮСГЭХГҮЙ. Нөөцийн дэвтэрт `convert_out` / `convert_in` мөр үлдэнэ."""

# app/services/tank_service.py  (WP4 хэрэгжүүлнэ)
async def consume_fuel(db, tank, liters: Decimal, *, ref_type: str, ref_id: UUID) -> Decimal   # COGS буцаана
async def receive_fuel(db, tank, liters: Decimal, landed_unit_cost: Decimal, *, ref_type, ref_id) -> None
async def adjust_fuel(db, tank, liters: Decimal, *, movement_type: str, ref_type, ref_id, note) -> None
```

## 6b. Банкны хуулга (bank_statement)

Банкнаас татсан Excel хуулгыг оруулж, мөр бүрийг манай бүртгэлд буулгана:

| Хуулгын мөр | Юу болох | Журналын бичилт |
|---|---|---|
| Кредит (орлого) | гэрээт харилцагчийн авлагын төлбөр | `AR_RECEIPT` — Дт 1110, Кт 1201 |
| Дебит (зарлага) | үйл ажиллагааны зардал | `EXPENSE_POSTED` — Дт 53xx, Кт 1110 |
| Шимтгэл (`is_fee`) | хуулга тус бүрд **нэг** нэгдсэн зардал | `EXPENSE_POSTED` (5371) |

Дүрмүүд:

* Төлбөр/зардлыг `contract_service.record_payment` ба
  `expense_service.create_expense` **өөрсдөө** үүсгэнэ — тусдаа журналын код
  бичихгүй.  Ингэснээр авлага, өглөг, дансны үлдэгдэл бүгд өөрөө зөв хөдөлнө.
* Мөр бүр `posted_at` + үүссэн баримтын `id`-г хадгална.  «Буцаах» нь баримт
  болон журналын бичилтийг **хамт** устгаж (`posting.reverse`) нөлөөг бүрэн
  сэргээнэ; хэн буцаасныг `audit_logs` хөтөлнө.
* Бүх харилцах данс ерөнхий дэвтэрт `1110`-д нэгтгэгдэнэ.  Данс тус бүрийн
  үлдэгдлийг `journal_lines.dim_bank_account_id` хэмжүүрээр гаргана:

      Σ(дансны хөдөлгөөн) + хуваарилаагүй == 1110 дансны үлдэгдэл

* Зардлын **ангилал** нь Колонкийн дансны төлөвлөгөө (`ACC.OPERATING_EXPENSES`,
  15 данс) — тусдаа хүснэгт байхгүй, ингэснээр бичилт үргэлж зөв данс руу орно.

## 6c. Түгээгчийн өдрийн ээлж (attendant)

``pos_sales_enabled=false`` үед ээлж миль (тоолуур) дээр суурилна:

* Нээлтэд заалт бүрд **үнийн snapshot** (`totalizer_readings.price_per_liter`)
  хадгалагдана — сегментийн эх үнэ.
* ``shift_price_marks`` — өдрийн дундуур үнэ өөрчлөгдөхөд аль мильд шинэ үнэ
  эхэлснийг тэмдэглэнэ; ``attendant_service.compute_dispensed`` хошуу бүрийг
  сегментчилж (литр × сегментийн үнэ) бодно.
* ``daily_close`` НЭГ transaction-д: зээлийн Sale-ууд (гэрээт төлбөрөөр) →
  нэгдсэн түлшний Sale (сегмент тус бүр нэг мөр; зээлийн литрийг сүүлийн
  сегментээс хасна; төлбөр = settlement карт + үлдэгдэл бэлэн) → тос/барааны
  Sale → авлагын төлбөрүүд → зардлууд → ердийн ``close_shift``.
  Бүгд ердийн үйлчилгээгээр үүсдэг тул журнал, нөөц, авлага өөрөө зөв.
* Зураг ``shift_attachments``-д (kind: open/close/settlement/price_mark),
  агуулгын байтаар JPG/PNG/WEBP/PDF гэж шалгана.
* Үнийн өөрчлөлтөд ``effective_date`` — ирээдүйн огноотой батлагдсан
  өөрчлөлт ``applied_at`` хоосон хүлээж, worker-ийн өдөр тутмын cron
  (``apply_due_price_changes``) хугацаа болмогц тавина.
* **Савны инвариант**: хошуу бүр савтайгаа холбоотой (`pump_nozzles.tank_id`);
  хаалтын Sale-ийн мөр бүр `tank_id`-тайгаа үүсдэг тул сав бүрийн зарлага
  яг Σ(тухайн савны хошуудын миль зөрүү) болно. Зээлийн литр
  `_SegmentSlots`-оор сегментүүдийн сүүлээс (tank_id, liters) хуваарилагдана.
* Тайлангийн ``daily`` хэсэгт хошуу бүрд `tank_name`, мөн `tanks` жагсаалт
  (сав тус бүрийн литр, дүн) ирнэ.
* ``GET /api/shifts/daily-closings?date_from&date_to`` — өдөр бүрийн
  тооцооны жагсаалт (ээлж №, огноо, түгээгч, эхний мөнгө, миль×үнэ, зээл,
  тос/бараа, settlement, тоолсон/байвал зохих бэлэн, зөрүү); эрх:
  `shifts.view_all | shifts.close`. FE: «Өдрийн тооцоо» цэс `/daily-closings`.
* ``GET /api/expense-categories`` эрх: `expenses.manage | shifts.close` —
  түгээгч өдрийн хаалтад зарлага бүртгэдэг.

## 7. Насосны абстракц (WP4)

```python
# app/hardware/pump_driver.py
@dataclass
class Preset: type: str  # PresetType; value: Decimal | None
@dataclass
class Telemetry: pump_id: UUID; nozzle_id: UUID|None; status: str; liters: Decimal; amount: Decimal; flow_lpm: Decimal; authorization_id: UUID|None
@dataclass
class FuelingComplete: pump_id: UUID; nozzle_id: UUID; authorization_id: UUID; liters: Decimal; amount: Decimal; unit_price: Decimal

class PumpDriver(Protocol):
    async def authorize(self, nozzle_id: UUID, preset: Preset, unit_price: Decimal) -> UUID
    async def halt(self) -> None
    def status(self) -> Telemetry

# app/hardware/pump_manager.py
class PumpManager:
    async def start(self) -> None          # DB-ээс насос ачаалж драйвер асаана (DB байхгүй бол чимээгүй өнгөрнө)
    async def stop(self) -> None
    async def authorize(self, pump_id: UUID, nozzle_id: UUID, preset: Preset) -> UUID
    async def halt(self, pump_id: UUID) -> None
    def snapshot(self) -> list[Telemetry]
```

Дууссан таталтыг Redis-д `auth:{authorization_id}` түлхүүрээр 1 цаг хадгална (JSON: pump_id, nozzle_id, liters, amount, unit_price, fuel_id, tank_id). `POST /api/sales` энэ утгыг уншиж түлшний мөрийг баталгаажуулна.

WebSocket мессежийн формат (`/ws/pumps`):
```json
{"type":"pump_status","pump_id":"...","nozzle_id":"...","status":"fueling","liters":"12.340","amount":"36285.00","flow_lpm":"38.5","authorization_id":"..."}
{"type":"fueling_complete","pump_id":"...","nozzle_id":"...","authorization_id":"...","liters":"20.000","amount":"58800.00"}
```

## 8. API хариултын ерөнхий хэлбэр

- Жагсаалт: `{"items": [...], "total": 123}` (paging: `?limit=&offset=`)
- Алдаа: FastAPI-н стандарт `{"detail": "Монгол текст"}`. Бизнес алдаанд **422**, эрхгүйд **403**, олдоогүйд **404**.
- Огноо ISO 8601, timezone-той.
- Бүх endpoint `/api` prefix-тэй. Router бүр `router = APIRouter(prefix="/api", tags=["..."])`.

## 9. Frontend гэрээ

- Бүх DTO төрөл `frontend/src/api/types.ts`-д. Мөнгө/литр `string` төрөлтэй.
- API дуудлага `frontend/src/api/client.ts`-ийн `api.get/post/patch/del` (JWT автоматаар).
- Текст зөвхөн `frontend/src/i18n/mn.ts`-ийн `t` объектоос.
- Формат `frontend/src/lib/format.ts`: `formatMNT("58800.00") → "58 800₮"`, `formatLiters("20.000") → "20.00 л"`, `formatDate`, `formatDateTime`.
- Товч `components/ui/Button.tsx` (`size="md"` = 48px, `size="lg"` = 64px). Тоо оруулах бүх талбар `NumPad`-аар (гараас бичихгүй).
- Сервер дата = TanStack Query, түр state = Zustand. Query key: `['домэйн', ...параметр]`.
- Өнгө: success `#10B981`, action `#2563EB`, warning `#F59E0B`, danger `#EF4444`, bg `#F8FAFC`.
