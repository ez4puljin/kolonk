/**
 * Серверийн DTO төрлүүд (CONTRACTS.md §8-9).
 *
 * ДҮРЭМ: мөнгө, литр, өртөг, тоо ширхэг бүгд `string`. `parseFloat` хориотой —
 * тооцоололд `lib/decimal.ts`, харуулахад `lib/format.ts` ашиглана.
 */

// --------------------------------------------------------------------------
// Ерөнхий
// --------------------------------------------------------------------------

export type UUID = string;
/** Decimal → JSON string. Жишээ: "58800.00", "20.000", "1234.567890" */
export type MoneyStr = string;
export type LitersStr = string;
/** ISO 8601, timezone-той. */
export type IsoDateTime = string;
/** "YYYY-MM-DD" */
export type IsoDate = string;

export interface Paged<T> {
  items: T[];
  total: number;
}

export interface OkResponse {
  ok: boolean;
  message?: string | null;
}

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

// --------------------------------------------------------------------------
// Тоочилсон утгууд (backend app/enums.py-тай нэг мөр)
// --------------------------------------------------------------------------

export type RoleCode = "cashier" | "manager" | "owner";
export type PumpStatus = "offline" | "idle" | "authorized" | "fueling" | "complete" | "error";
export type ShiftStatus = "open" | "closed";
export type ShiftPhase = "open" | "close";
export type TankMovementType = "receipt" | "sale" | "adjustment" | "variance";
export type InventoryTxType =
  | "purchase"
  | "sale"
  | "refund"
  | "adjustment"
  | "convert_out"
  | "convert_in";
export type SaleType = "fuel" | "store" | "mixed";
export type SaleStatus = "draft" | "completed" | "refunded" | "partial_refund";
export type ItemType = "fuel" | "product";
export type PaymentMethod =
  | "cash"
  | "card"
  | "qr"
  | "transfer"
  | "contract"
  | "voucher"
  | "prepaid";
export type DocStatus = "draft" | "posted";
export type ApprovalStatus = "pending" | "approved" | "rejected";
export type RefundType = "full" | "partial";
export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";
export type InvoiceStatus = "open" | "partial" | "paid";
export type ContractStatus = "active" | "suspended" | "closed";
export type VoucherStatus = "active" | "redeemed" | "void" | "expired";
export type CardStatus = "active" | "blocked" | "closed";
export type CardTxType = "topup" | "redeem" | "refund";
export type CustomerType = "b2b" | "individual";
export type EbarimtStatus = "pending" | "sent" | "failed";
export type CashAccount = "bank" | "cash";
export type PresetType = "liters" | "amount" | "full";
export type PriceTargetType = "fuel" | "product";

// --------------------------------------------------------------------------
// Нэвтрэлт, хэрэглэгч
// --------------------------------------------------------------------------

export interface UserTile {
  id: UUID;
  full_name: string;
  username: string;
  role_code: string;
  role_name_mn: string;
  /** Түгээгчийн харьяа салбар (нэвтрэхэд автоматаар сонгогдоно). */
  branch: UserBranch | null;
  /** True бол бүх салбарыг харна (менежер, эзэн). */
  all_branches: boolean;
}

export interface LoginRequest {
  user_id: UUID;
  pin: string;
}

export interface LoginResponse {
  token: string;
  user: UserTile;
  permissions: string[];
}

export interface MeResponse {
  user: UserTile;
  permissions: string[];
  shift_open: boolean;
  shift_id: UUID | null;
  shift_number: number | null;
}

export interface User {
  id: UUID;
  username: string;
  full_name: string;
  role_id: UUID;
  role_code: string;
  role_name_mn: string;
  phone: string | null;
  is_active: boolean;
  last_login_at: IsoDateTime | null;
  created_at: IsoDateTime | null;
  branch_id: UUID | null;
  branch_name: string | null;
}

export interface UserCreate {
  username: string;
  full_name: string;
  pin: string;
  role_id: UUID;
  phone?: string | null;
  /** Түгээгчд заавал; менежер, эзэнд null. */
  branch_id?: UUID | null;
}

export interface UserUpdate {
  username?: string;
  full_name?: string;
  role_id?: UUID;
  phone?: string | null;
  is_active?: boolean;
  /** Түгээгчд заавал; менежер, эзэнд null. */
  branch_id?: UUID | null;
}

export interface Role {
  id: UUID;
  code: string;
  name_mn: string;
  permissions: string[];
  user_count: number;
}

export interface Permission {
  code: string;
  name_mn: string;
}

export interface PermissionGroup {
  key: string;
  name_mn: string;
  items: Permission[];
}

export interface PermissionGroupList {
  groups: PermissionGroup[];
  total: number;
}

// --------------------------------------------------------------------------
// Түлш, сав, насос
// --------------------------------------------------------------------------

export interface FuelBrief {
  id: UUID;
  code: string;
  name_mn: string;
  color_hex: string;
  price_per_liter: MoneyStr;
}

export interface Fuel {
  id: UUID;
  code: string;
  name_mn: string;
  price_per_liter: MoneyStr;
  color_hex: string;
  sort_order: number;
  is_active: boolean;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface FuelCreate {
  code: string;
  name_mn: string;
  price_per_liter?: MoneyStr;
  color_hex?: string;
  sort_order?: number;
  is_active?: boolean;
}

export interface FuelUpdate {
  code?: string;
  name_mn?: string;
  color_hex?: string;
  sort_order?: number;
  is_active?: boolean;
}

export interface Tank {
  id: UUID;
  name: string;
  branch_id: UUID | null;
  branch_name: string | null;
  fuel_id: UUID;
  fuel: FuelBrief;
  capacity_l: LitersStr;
  current_l: LitersStr;
  avg_cost: MoneyStr;
  min_level_l: LitersStr;
  is_active: boolean;
  fill_pct: string;
  is_low: boolean;
  stock_value: MoneyStr;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface TankCreate {
  branch_id?: UUID | null;
  name: string;
  fuel_id: UUID;
  capacity_l: LitersStr;
  current_l?: LitersStr;
  avg_cost?: MoneyStr;
  min_level_l?: LitersStr;
  is_active?: boolean;
}

export interface TankUpdate {
  name?: string;
  fuel_id?: UUID;
  capacity_l?: LitersStr;
  min_level_l?: LitersStr;
  is_active?: boolean;
}

export interface TankMovement {
  id: UUID;
  tank_id: UUID;
  movement_type: TankMovementType | string;
  liters: LitersStr;
  balance_after_l: LitersStr;
  unit_cost: MoneyStr;
  ref_type: string | null;
  ref_id: UUID | null;
  note: string | null;
  created_at: IsoDateTime;
}

export interface TankAdjustment {
  liters: LitersStr;
  note?: string | null;
}

export interface PumpNozzle {
  id: UUID;
  pump_id: UUID;
  nozzle_number: number;
  fuel_id: UUID;
  fuel_code: string;
  fuel_name: string;
  price_per_liter: MoneyStr;
  color_hex: string;
  tank_id: UUID;
  tank_name: string;
  tank_current_l: LitersStr;
  totalizer: LitersStr;
}

export interface PumpTelemetry {
  pump_id: UUID;
  nozzle_id: UUID | null;
  status: PumpStatus | string;
  liters: LitersStr;
  amount: MoneyStr;
  flow_lpm: string;
  authorization_id: UUID | null;
}

export interface Pump {
  id: UUID;
  number: number;
  name: string;
  branch_id: UUID | null;
  branch_name: string | null;
  /** Талбай дахь бодит байршил. */
  position_x: number;
  position_y: number;
  status: PumpStatus | string;
  driver: string;
  is_active: boolean;
  nozzles: PumpNozzle[];
  live: PumpTelemetry | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface NozzleCreate {
  nozzle_number: number;
  fuel_id: UUID;
  tank_id: UUID;
  totalizer?: LitersStr;
}

export interface NozzleUpdate {
  nozzle_number?: number;
  fuel_id?: UUID;
  tank_id?: UUID;
  totalizer?: LitersStr;
}

export interface PumpCreate {
  number: number;
  name: string;
  branch_id?: UUID | null;
  /** Талбай дахь бодит байршил (нүдний координат). */
  position_x?: number;
  position_y?: number;
  driver?: string;
  is_active?: boolean;
  nozzles?: NozzleCreate[];
}

export interface PumpUpdate {
  number?: number;
  name?: string;
  branch_id?: UUID | null;
  position_x?: number;
  position_y?: number;
  driver?: string;
  is_active?: boolean;
}

export interface AuthorizeRequest {
  nozzle_id: UUID;
  preset_type: PresetType;
  preset_value?: MoneyStr | null;
}

export interface AuthorizeResponse {
  authorization_id: UUID;
}

export interface PumpActionResponse {
  ok: boolean;
  pump_id: UUID;
  status: string;
}

/** `/ws/pumps`-ийн мессежүүд (CONTRACTS.md §7). */
export interface WsSnapshotMessage {
  type: "snapshot";
  pumps: PumpTelemetry[];
}

export interface WsPumpStatusMessage extends PumpTelemetry {
  type: "pump_status";
}

export interface WsFuelingCompleteMessage {
  type: "fueling_complete";
  pump_id: UUID;
  nozzle_id: UUID;
  authorization_id: UUID;
  liters: LitersStr;
  amount: MoneyStr;
  unit_price?: MoneyStr;
}

export interface WsPingMessage {
  type: "ping";
}

export interface WsErrorMessage {
  type: "error";
  message: string;
}

export type PumpSocketMessage =
  | WsSnapshotMessage
  | WsPumpStatusMessage
  | WsFuelingCompleteMessage
  | WsPingMessage
  | WsErrorMessage;

// --------------------------------------------------------------------------
// Ээлж
// --------------------------------------------------------------------------

export interface TankDipInput {
  tank_id: UUID;
  dip_liters: LitersStr;
}

export interface TotalizerReadingInput {
  nozzle_id: UUID;
  reading: LitersStr;
}

export interface ShiftOpenRequest {
  opening_cash: MoneyStr;
  tank_dips: TankDipInput[];
  totalizer_readings: TotalizerReadingInput[];
}

export interface ShiftCloseRequest {
  declared_cash: MoneyStr;
  tank_dips: TankDipInput[];
  totalizer_readings: TotalizerReadingInput[];
  note?: string | null;
}

export interface ShiftSummary {
  id: UUID;
  number: number;
  status: ShiftStatus | string;
  status_name: string;
  opened_at: IsoDateTime;
  closed_at: IsoDateTime | null;
  opened_by: UUID | null;
  opened_by_name: string | null;
  closed_by: UUID | null;
  closed_by_name: string | null;
  opening_cash: MoneyStr;
  declared_cash: MoneyStr | null;
  expected_cash: MoneyStr | null;
  cash_over_short: MoneyStr | null;
  note: string | null;
  sales_count: number;
  sales_total: MoneyStr;
}

/** Дан ээлжийн мөр — жагсаалт/түүхэнд. */
export type Shift = ShiftSummary;

export interface TenderRow {
  method: PaymentMethod | string;
  method_name: string;
  count: number;
  amount: MoneyStr;
}

export interface SalesSummary {
  count: number;
  gross_total: MoneyStr;
  vat_total: MoneyStr;
  net_total: MoneyStr;
  fuel_amount: MoneyStr;
  fuel_liters: LitersStr;
  store_amount: MoneyStr;
  by_tender: TenderRow[];
}

export interface ShiftFuelRow {
  fuel_id: UUID;
  code: string;
  name: string;
  liters: LitersStr;
  amount: MoneyStr;
}

export interface ShiftNozzleRow {
  pump_id: UUID;
  pump_number: number;
  pump_name: string;
  nozzle_id: UUID;
  nozzle_number: number;
  fuel_name: string;
  opening_reading: LitersStr | null;
  closing_reading: LitersStr | null;
  reading_delta_l: LitersStr | null;
  sold_liters: LitersStr;
  sold_amount: MoneyStr;
}

export interface ShiftTankRow {
  tank_id: UUID;
  tank_name: string;
  fuel_name: string;
  open_dip: LitersStr | null;
  close_dip: LitersStr | null;
  book_liters: LitersStr | null;
  variance_l: LitersStr | null;
  variance_value: MoneyStr;
}

export interface CashSection {
  opening_cash: MoneyStr;
  cash_sales: MoneyStr;
  refunds: MoneyStr;
  expected_cash: MoneyStr;
  declared_cash: MoneyStr | null;
  cash_over_short: MoneyStr | null;
}

export interface ShiftRefundRow {
  id: UUID;
  sale_number: number | null;
  amount: MoneyStr;
  refund_method: string;
  refund_method_name: string;
  status: ApprovalStatus | string;
  status_name: string;
  reason: string | null;
  decided_at: IsoDateTime | null;
}

export interface ProfitSection {
  revenue_net: MoneyStr;
  cogs_total: MoneyStr;
  gross_profit: MoneyStr;
  margin_pct: string;
}

export interface PostedEntryRow {
  entry_no: number | null;
  event_type: string;
  description: string;
  amount: MoneyStr;
}

export interface ShiftReport {
  shift: ShiftSummary;
  sales: SalesSummary;
  fuels: ShiftFuelRow[];
  nozzles: ShiftNozzleRow[];
  tanks: ShiftTankRow[];
  cash: CashSection;
  refunds: ShiftRefundRow[];
  profit: ProfitSection;
  posted_entries: PostedEntryRow[];
  /** Түгээгчийн өдрийн хаалт (байвал). */
  daily?: DailyClosing | null;
}

export interface CurrentShift {
  shift: ShiftSummary;
  sales: SalesSummary;
  fuels: ShiftFuelRow[];
  cash: CashSection;
}

// --------------------------------------------------------------------------
// Бараа, нөөц
// --------------------------------------------------------------------------

export interface ProductCategory {
  id: UUID;
  name_mn: string;
  icon: string | null;
  sort_order: number;
  product_count?: number;
}

export interface ProductCategoryCreate {
  name_mn: string;
  icon?: string | null;
  sort_order?: number;
}

export interface Product {
  id: UUID;
  sku: string;
  barcode: string | null;
  name_mn: string;
  category_id: UUID;
  category_name: string | null;
  unit: string;
  price: MoneyStr;
  avg_cost: MoneyStr;
  stock_qty: string;
  min_stock: string;
  is_active: boolean;
  is_low: boolean;
  stock_value: MoneyStr;
  /** Ширхэгээр (`piece`) эсвэл задлан/грамлаж (`bulk`) зарах уу. */
  sale_mode: ProductSaleMode;
  sale_mode_name: string;
  /** Ширхэг барааг задлахад аль грам бүтээгдэхүүн рүү орох вэ. */
  bulk_product_id: UUID | null;
  bulk_product_name: string | null;
  bulk_product_unit: string | null;
  /** 1 ширхэгээс гарах хэмжээ. */
  bulk_factor: string;
  /** Задлан хөрвүүлэлт хийх боломжтой эсэх. */
  is_convertible: boolean;
  created_at: IsoDateTime | null;
  updated_at: IsoDateTime | null;
}

/** Барааг хэрхэн борлуулах вэ. */
export type ProductSaleMode = "piece" | "bulk";

export interface ProductCreate {
  sku: string;
  barcode?: string | null;
  name_mn: string;
  category_id: UUID;
  unit?: string;
  price?: MoneyStr;
  min_stock?: string;
  is_active?: boolean;
  sale_mode?: ProductSaleMode;
  bulk_product_id?: UUID | null;
  bulk_factor?: string;
}

export interface ProductUpdate {
  sku?: string;
  barcode?: string | null;
  name_mn?: string;
  category_id?: UUID;
  unit?: string;
  min_stock?: string;
  is_active?: boolean;
  sale_mode?: ProductSaleMode;
  bulk_product_id?: UUID | null;
  bulk_factor?: string;
}

/** Нөөцийн жагсаалтын мөр. */
export interface InventoryRow {
  product_id: UUID;
  sku: string;
  name_mn: string;
  category_id: UUID | null;
  category_name: string | null;
  unit: string;
  stock_qty: string;
  min_stock: string;
  avg_cost: MoneyStr;
  price: MoneyStr;
  /** Нөөцийн үнэлгээ (тоо × дундаж өртөг). Backend талбарын нэр — `value`. */
  value: MoneyStr;
  is_active: boolean;
  is_low: boolean;
  sale_mode: ProductSaleMode;
  sale_mode_name: string;
  /** Салбар тус бүрийн үлдэгдэл. */
  branches: BranchQty[];
}

export interface BranchQty {
  branch_id: UUID;
  branch_name: string;
  qty: string;
}

export interface InventoryTransaction {
  id: UUID;
  product_id: UUID;
  product_name: string | null;
  tx_type: InventoryTxType | string;
  qty: string;
  unit_cost: MoneyStr;
  balance_after: string;
  ref_type: string | null;
  ref_id: UUID | null;
  note: string | null;
  created_at: IsoDateTime;
}

export interface InventoryAdjustment {
  product_id: UUID;
  qty: string;
  /** Аль салбарт тохируулах вэ (хоосон бол үндсэн салбар). */
  branch_id?: UUID | null;
  note?: string | null;
}

/** Задлан хөрвүүлэлт — ширхэг барааг грам бүтээгдэхүүн рүү. */
export interface BulkConversionInput {
  product_id: UUID;
  /** Хэдэн ширхэгийг задлах вэ. */
  qty: string;
  branch_id?: UUID | null;
  note?: string | null;
}

export interface BulkConversionResult {
  source: Product;
  target: Product;
  qty: string;
  out_qty: string;
  cost: MoneyStr;
  out_transaction: InventoryTransaction;
  in_transaction: InventoryTransaction;
}

// --------------------------------------------------------------------------
// Худалдан авалт
// --------------------------------------------------------------------------

/* ------------------------------------------------------------------ *
 * Үйл ажиллагааны зардал
 * ------------------------------------------------------------------ */

export interface ExpenseCategory {
  code: string;
  name_mn: string;
}

export interface ExpensePaymentMethod {
  code: string;
  name_mn: string;
}

export interface Expense {
  id: UUID;
  number: number;
  expense_date: string;
  account_code: string;
  account_name: string;
  payment_method: string;
  payment_method_name: string;
  subtotal: MoneyStr;
  vat_amount: MoneyStr;
  total: MoneyStr;
  supplier_id: UUID | null;
  supplier_name: string | null;
  bank_account_id: UUID | null;
  bank_account_name: string | null;
  invoice_no: string | null;
  description: string | null;
  status: string;
}

export interface ExpenseByAccount {
  account_code: string;
  account_name: string;
  amount: MoneyStr;
}

export interface ExpenseListResult {
  items: Expense[];
  total: number;
  total_amount: MoneyStr;
  by_account: ExpenseByAccount[];
}

export interface ExpenseCreate {
  account_code: string;
  /** Төлсөн нийт дүн (НӨАТ-тай бол түүнийг оруулаад). */
  amount: MoneyStr;
  payment_method: string;
  expense_date?: string;
  has_vat?: boolean;
  supplier_id?: UUID | null;
  /** `bank` төлбөрийн үед аль харилцах данснаас гарсан бэ. */
  bank_account_id?: UUID | null;
  invoice_no?: string | null;
  description?: string | null;
}

/* ------------------------------------------------------------------ *
 * Ажилтан ба цалин
 * ------------------------------------------------------------------ */

export interface Employee {
  id: UUID;
  full_name: string;
  base_salary: MoneyStr;
  branch_id: UUID | null;
  branch_name: string | null;
  /** НДШ бодох эсэх. False бол НДШ 0, ХХОАТ нийт цалингаас шууд бодогдоно. */
  si_enabled: boolean;
  position: string | null;
  register_no: string | null;
  social_no: string | null;
  phone: string | null;
  bank_account: string | null;
  hire_date: string | null;
  end_date: string | null;
  is_active: boolean;
  note: string | null;
  created_at: IsoDateTime | null;
}

export interface EmployeeCreate {
  full_name: string;
  base_salary: MoneyStr;
  branch_id?: UUID | null;
  si_enabled?: boolean;
  position?: string | null;
  register_no?: string | null;
  social_no?: string | null;
  phone?: string | null;
  bank_account?: string | null;
  hire_date?: string | null;
}

export interface EmployeeUpdate extends Partial<EmployeeCreate> {
  is_active?: boolean;
  end_date?: string | null;
}

export interface PayrollLine {
  id: UUID;
  employee_id: UUID;
  employee_name: string;
  position: string | null;
  /** Энэ мөрд НДШ бодсон эсэх. */
  si_enabled: boolean;
  base_salary: MoneyStr;
  worked_days: string;
  month_days: string;
  /** Тухайн сард ажилласан бодит хугацаа. */
  worked_from: string | null;
  worked_to: string | null;
  /** Бүтэн сар ажиллаагүй эсэх. */
  partial_month: boolean;
  earned_salary: MoneyStr;
  bonus: MoneyStr;
  other_addition: MoneyStr;
  gross: MoneyStr;
  si_employee: MoneyStr;
  si_employer: MoneyStr;
  taxable: MoneyStr;
  pit: MoneyStr;
  advance: MoneyStr;
  other_deduction: MoneyStr;
  net: MoneyStr;
  note: string | null;
}

export interface PayrollPeriod {
  id: UUID;
  year: number;
  month: number;
  label: string;
  status: string;
  si_employee_rate: string;
  si_employer_rate: string;
  pit_rate: string;
  pit_credit: MoneyStr;
  gross_total: MoneyStr;
  si_employee_total: MoneyStr;
  si_employer_total: MoneyStr;
  si_total: MoneyStr;
  pit_total: MoneyStr;
  net_total: MoneyStr;
  /** Ажил олгогчид тусах нийт зардал = нийт цалин + ажил олгогчийн НДШ. */
  employer_cost: MoneyStr;
  paid_salary: MoneyStr;
  paid_pit: MoneyStr;
  paid_social: MoneyStr;
  owed_salary: MoneyStr;
  owed_pit: MoneyStr;
  owed_social: MoneyStr;
  employee_count: number;
  lines: PayrollLine[];
}

export interface PayrollPeriodRow {
  id: UUID;
  year: number;
  month: number;
  label: string;
  status: string;
  gross_total: MoneyStr;
  net_total: MoneyStr;
  pit_total: MoneyStr;
  si_total: MoneyStr;
  employer_cost: MoneyStr;
}

export interface PayrollLineUpdate {
  /** Энэ мөрд НДШ бодох эсэх. */
  si_enabled?: boolean;
  worked_days?: string;
  bonus?: MoneyStr;
  other_addition?: MoneyStr;
  advance?: MoneyStr;
  other_deduction?: MoneyStr;
  base_salary?: MoneyStr;
  note?: string | null;
}

export interface PayrollPayRequest {
  /** `salary` | `pit` | `social` */
  target: string;
  amount?: MoneyStr | null;
  /** `bank` | `cash` */
  paid_from?: string;
  payment_date?: string | null;
}

export interface EmployeeAdvance {
  id: UUID;
  employee_id: UUID;
  employee_name: string;
  advance_date: string;
  amount: MoneyStr;
  paid_from: string;
  note: string | null;
}

export interface AdvanceCreate {
  employee_id: UUID;
  amount: MoneyStr;
  paid_from?: string;
  advance_date?: string | null;
  note?: string | null;
}

/* ------------------------------------------------------------------ *
 * Бараа материалын тайлан /өртгөөр/
 * ------------------------------------------------------------------ */

export interface InventoryReportDetail {
  date: string;
  movement_type: string;
  movement_name: string;
  note: string | null;
  in_qty: string | null;
  in_value: MoneyStr | null;
  out_qty: string | null;
  out_value: MoneyStr | null;
  balance_qty: string;
  unit_cost: MoneyStr;
}

export interface InventoryReportRow {
  /** 0 = данс, 1 = байршил, 2 = бараа (бүлэглэлээс хамаарна). */
  level: number;
  code: string;
  name: string;
  unit: string;
  opening_qty: string;
  opening_value: MoneyStr;
  in_qty: string;
  in_value: MoneyStr;
  out_qty: string;
  out_value: MoneyStr;
  closing_qty: string;
  closing_value: MoneyStr;
  unit_cost: MoneyStr;
  details: InventoryReportDetail[];
}

export interface InventoryReportTotals {
  opening_qty: string;
  opening_value: MoneyStr;
  in_qty: string;
  in_value: MoneyStr;
  out_qty: string;
  out_value: MoneyStr;
  closing_qty: string;
  closing_value: MoneyStr;
}

export interface InventoryReport {
  date_from: string;
  date_to: string;
  group_by: string;
  group_by_label: string;
  tx_type: string;
  include_details: boolean;
  filter_text: string;
  rows: InventoryReportRow[];
  totals: InventoryReportTotals;
}

export interface InventoryReportParams {
  date_from: string;
  date_to: string;
  account_code?: string | null;
  tank_id?: UUID | null;
  fuel_id?: UUID | null;
  product_id?: UUID | null;
  category_id?: UUID | null;
  group_by?: string;
  tx_type?: string;
  note_search?: string | null;
  include_details?: boolean;
  skip_empty?: boolean;
}

export interface InventoryFilterOptions {
  accounts: { code: string; name: string }[];
  locations: { id: UUID; code: string; name: string; account_code: string }[];
  fuels: { id: UUID; code: string; name: string }[];
  categories: { id: UUID; name: string }[];
  products: { id: UUID; code: string; name: string; category_id: UUID | null }[];
  group_by: { code: string; name: string }[];
  tx_types: { code: string; name: string }[];
}

/* ------------------------------------------------------------------ *
 * Тайлангийн төв
 * ------------------------------------------------------------------ */

export interface ReportDefinition {
  code: string;
  name: string;
  description: string;
  default_group_by: string[];
}

export interface CodeName {
  code: string;
  name: string;
}

export interface IdName {
  id: UUID;
  name: string;
  code?: string;
  position?: string | null;
}

export interface ReportCenterOptions {
  reports: ReportDefinition[];
  accounts: CodeName[];
  branches: IdName[];
  fuels: IdName[];
  categories: IdName[];
  employees: IdName[];
  staff: IdName[];
  tx_types: CodeName[];
  group_fields: CodeName[];
}

export interface ReportDetailRow {
  when: IsoDateTime;
  date: string;
  tx_type: string;
  tx_type_name: string;
  doc_no: string;
  item_name: string;
  employee_name: string;
  branch_name: string;
  qty: string;
  unit: string;
  amount: MoneyStr;
  note: string;
  /** Давхар товшиход гүйлгээ рүү орох түлхүүр. */
  source_type: string;
  source_id: string | null;
}

export interface ReportCenterRow {
  level: number;
  /** Дээд түвшнээс эхэлсэн бүрэн зам — задаргаа татахад ашиглана. */
  path: string[];
  code: string;
  name: string;
  qty: string;
  amount: MoneyStr;
  count: number;
  details: ReportDetailRow[];
}

export interface ReportCenterResult {
  report: string;
  report_name: string;
  date_from: string;
  date_to: string;
  group_by: string[];
  group_by_labels: string[];
  include_details: boolean;
  filter_text: string;
  rows: ReportCenterRow[];
  totals: { qty: string; amount: MoneyStr; count: number };
}

export interface ReportDrillResult {
  path: string[];
  total: number;
  truncated: boolean;
  items: ReportDetailRow[];
  totals: { qty: string; amount: MoneyStr; count: number };
}

export interface ReportCenterParams {
  report: string;
  date_from: string;
  date_to: string;
  account_code?: string[];
  branch_id?: string[];
  fuel_id?: string[];
  category_id?: string[];
  employee_id?: string[];
  tx_type?: string[];
  group_by?: string[];
  include_details?: boolean;
}

export interface TransactionLine {
  name: string;
  qty: string | null;
  unit: string;
  unit_price: MoneyStr | null;
  amount: MoneyStr;
  cogs: MoneyStr;
}

export interface TransactionPayment {
  method: string;
  method_name: string;
  amount: MoneyStr;
  received: MoneyStr | null;
  change_given: MoneyStr | null;
  ref_no: string | null;
}

export interface TransactionDetail {
  source_type: string;
  source_id: string;
  title: string;
  when: IsoDateTime;
  branch: string;
  person_label: string;
  person: string;
  customer?: string | null;
  supplier?: string | null;
  invoice_no?: string | null;
  status: string;
  note: string | null;
  lines: TransactionLine[];
  payments: TransactionPayment[];
  extra?: { label: string; value: string | number | null }[];
  subtotal: MoneyStr;
  vat_amount: MoneyStr;
  total: MoneyStr;
}

/* ------------------------------------------------------------------ *
 * Салбар
 * ------------------------------------------------------------------ */

export interface Branch {
  id: UUID;
  code: string;
  name: string;
  address: string | null;
  phone: string | null;
  is_active: boolean;
  sort_order: number;
  user_count: number;
  open_shifts: number;
}

/** Салбарт тухайн төлбөрийн хэрэгсэл идэвхтэй эсэх. */
export interface BranchPaymentMethod {
  method: PaymentMethod | string;
  label: string;
  is_enabled: boolean;
  sort_order: number;
  /** Бэлэн мөнгө — хаах боломжгүй. */
  locked: boolean;
}

export interface BranchCreate {
  code: string;
  name: string;
  address?: string | null;
  phone?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

export type BranchUpdate = Partial<BranchCreate>;

/** Нэвтэрсэн хэрэглэгчийн харьяа салбар. */
export interface UserBranch {
  id: UUID;
  code: string;
  name: string;
}

export interface Supplier {
  id: UUID;
  name: string;
  register_no: string | null;
  phone: string | null;
  bank_account: string | null;
  address: string | null;
  is_active: boolean;
  balance?: MoneyStr;
  created_at: IsoDateTime | null;
  updated_at: IsoDateTime | null;
}

export interface SupplierCreate {
  name: string;
  register_no?: string | null;
  phone?: string | null;
  bank_account?: string | null;
  address?: string | null;
  is_active?: boolean;
}

export type SupplierUpdate = Partial<SupplierCreate>;

export interface FuelReceipt {
  id: UUID;
  number: number;
  supplier_id: UUID;
  supplier_name: string | null;
  tank_id: UUID;
  tank_name: string | null;
  fuel_id: UUID;
  fuel_name: string | null;
  receipt_date: IsoDate;
  invoice_no: string | null;
  liters: LitersStr;
  unit_cost: MoneyStr;
  freight_cost: MoneyStr;
  density: string | null;
  temperature_c: string | null;
  subtotal: MoneyStr;
  vat_amount: MoneyStr;
  total_gross: MoneyStr;
  landed_unit_cost: MoneyStr;
  status: DocStatus | string;
  status_name: string;
  posted_by: UUID | null;
  posted_at: IsoDateTime | null;
  ap_invoice_id: UUID | null;
  note: string | null;
  created_at: IsoDateTime | null;
}

export interface FuelReceiptCreate {
  supplier_id: UUID;
  tank_id: UUID;
  fuel_id: UUID;
  receipt_date: IsoDate;
  invoice_no?: string | null;
  liters: LitersStr;
  unit_cost: MoneyStr;
  freight_cost?: MoneyStr;
  density?: string | null;
  temperature_c?: string | null;
  note?: string | null;
}

export interface PurchaseItem {
  id: UUID;
  product_id: UUID;
  product_name: string | null;
  sku: string | null;
  qty: string;
  unit_cost: MoneyStr;
  amount: MoneyStr;
}

export interface Purchase {
  id: UUID;
  number: number;
  supplier_id: UUID;
  supplier_name: string | null;
  branch_id: UUID | null;
  purchase_date: IsoDate;
  invoice_no: string | null;
  subtotal: MoneyStr;
  vat_amount: MoneyStr;
  total_gross: MoneyStr;
  status: DocStatus | string;
  status_name: string;
  posted_by: UUID | null;
  posted_at: IsoDateTime | null;
  ap_invoice_id: UUID | null;
  note: string | null;
  items: PurchaseItem[];
  created_at: IsoDateTime | null;
}

export interface PurchaseItemCreate {
  product_id: UUID;
  qty: string;
  unit_cost: MoneyStr;
}

export interface PurchaseCreate {
  supplier_id: UUID;
  /** Бараа аль салбарын нөөцөд орох вэ. */
  branch_id?: UUID | null;
  purchase_date: IsoDate;
  invoice_no?: string | null;
  items: PurchaseItemCreate[];
  note?: string | null;
}

// --------------------------------------------------------------------------
// Харилцагч, гэрээ, авлага
// --------------------------------------------------------------------------

export interface ContractBrief {
  id: UUID;
  contract_no: string;
  credit_limit: MoneyStr;
  balance: MoneyStr;
  credit_available: MoneyStr;
  price_discount_per_l: MoneyStr;
  status: ContractStatus | string;
  status_name: string;
}

export interface Customer {
  id: UUID;
  /** Овог (иргэнд). */
  last_name: string | null;
  name: string;
  /** "Овог Нэр" — дэлгэцийн нэр. */
  full_name: string;
  register_no: string | null;
  phone: string | null;
  phone2: string | null;
  email: string | null;
  /** Аймаг/хот. */
  province: string | null;
  /** Сум/дүүрэг. */
  district: string | null;
  /** Гэрээнд заасан зээлийн лимит. */
  credit_limit: MoneyStr;
  /** Сканнердсан гэрээний PDF хавсаргасан эсэх. */
  has_contract_file: boolean;
  type: CustomerType | string;
  type_name: string;
  is_active: boolean;
  contracts: ContractBrief[];
  created_at: IsoDateTime | null;
  updated_at: IsoDateTime | null;
}

export interface CustomerCreate {
  last_name?: string | null;
  name: string;
  register_no?: string | null;
  phone?: string | null;
  phone2?: string | null;
  email?: string | null;
  province?: string | null;
  district?: string | null;
  credit_limit?: MoneyStr;
  type?: CustomerType;
  is_active?: boolean;
}

export type CustomerUpdate = Partial<CustomerCreate>;

export interface Contract {
  id: UUID;
  customer_id: UUID;
  customer_name: string | null;
  contract_no: string;
  credit_limit: MoneyStr;
  balance: MoneyStr;
  credit_available: MoneyStr;
  price_discount_per_l: MoneyStr;
  billing_day: number;
  status: ContractStatus | string;
  status_name: string;
  created_at: IsoDateTime | null;
  updated_at: IsoDateTime | null;
}

export interface ContractCreate {
  customer_id: UUID;
  contract_no: string;
  credit_limit?: MoneyStr;
  price_discount_per_l?: MoneyStr;
  billing_day?: number;
  status?: ContractStatus;
}

export interface ContractUpdate {
  contract_no?: string;
  credit_limit?: MoneyStr;
  price_discount_per_l?: MoneyStr;
  billing_day?: number;
  status?: ContractStatus;
}

export interface StatementRow {
  date: IsoDateTime | null;
  kind: string;
  kind_name: string;
  ref: string | null;
  description: string;
  debit: MoneyStr;
  credit: MoneyStr;
  balance: MoneyStr;
}

export interface ContractStatement {
  contract: Contract;
  date_from: IsoDate | null;
  date_to: IsoDate | null;
  opening_balance: MoneyStr;
  sales_total: MoneyStr;
  payments_total: MoneyStr;
  closing_balance: MoneyStr;
  rows: StatementRow[];
}

export interface ArInvoice {
  id: UUID;
  customer_id: UUID;
  customer_name: string | null;
  contract_id: UUID;
  contract_no: string | null;
  invoice_no: string;
  period_start: IsoDate;
  period_end: IsoDate;
  issued_at: IsoDateTime | null;
  amount: MoneyStr;
  amount_paid: MoneyStr;
  amount_due: MoneyStr;
  status: InvoiceStatus | string;
  status_name: string;
  lines: Record<string, JsonValue>[];
}

export interface ArPaymentCreate {
  contract_id: UUID;
  amount: MoneyStr;
  received_to: CashAccount;
  payment_date?: IsoDate | null;
  ar_invoice_id?: UUID | null;
  note?: string | null;
}

export interface ArPayment {
  id: UUID;
  ar_invoice_id: UUID | null;
  customer_id: UUID;
  contract_id: UUID;
  amount: MoneyStr;
  received_to: string;
  payment_date: IsoDate;
  note: string | null;
  created_by: UUID | null;
  created_at: IsoDateTime | null;
}

export interface ArPaymentResult {
  payment: ArPayment;
  contract: Contract;
  invoice: ArInvoice | null;
  journal_entry_id: UUID | null;
}

// --------------------------------------------------------------------------
// Ваучер, урьдчилсан төлбөрт карт
// --------------------------------------------------------------------------

export interface Voucher {
  id: UUID;
  code: string;
  face_value: MoneyStr;
  status: VoucherStatus | string;
  status_name: string;
  customer_id: UUID | null;
  customer_name: string | null;
  sold_sale_id: UUID | null;
  redeemed_sale_id: UUID | null;
  sold_at: IsoDateTime | null;
  redeemed_at: IsoDateTime | null;
  expires_at: IsoDateTime | null;
  created_at: IsoDateTime | null;
}

export interface VoucherIssueRequest {
  count: number;
  face_value: MoneyStr;
  expires_at?: IsoDateTime | null;
  customer_id?: UUID | null;
}

export interface VoucherSellRequest {
  tender_method: PaymentMethod;
  customer_id?: UUID | null;
}

export interface VoucherVoidRequest {
  reason?: string | null;
}

export interface VoucherValidateResult {
  valid: boolean;
  message: string;
  voucher: Voucher | null;
}

export interface PrepaidCard {
  id: UUID;
  card_no: string;
  holder_name: string | null;
  customer_id: UUID | null;
  customer_name: string | null;
  balance: MoneyStr;
  status: CardStatus | string;
  status_name: string;
  created_at: IsoDateTime | null;
  updated_at: IsoDateTime | null;
}

export interface PrepaidCardCreate {
  card_no: string;
  holder_name?: string | null;
  customer_id?: UUID | null;
  initial_amount?: MoneyStr;
  tender_method?: PaymentMethod;
}

export interface CardTopupRequest {
  amount: MoneyStr;
  tender_method: PaymentMethod;
}

export interface CardBlockRequest {
  reason?: string | null;
}

export interface CardTransaction {
  id: UUID;
  card_id: UUID;
  tx_type: CardTxType | string;
  tx_type_name: string;
  amount: MoneyStr;
  balance_after: MoneyStr;
  sale_id: UUID | null;
  created_at: IsoDateTime | null;
}

export interface CardOperationResult {
  card: PrepaidCard;
  transaction: CardTransaction | null;
  journal_entry_id: UUID | null;
}

// --------------------------------------------------------------------------
// Борлуулалт
// --------------------------------------------------------------------------

export interface SaleItemInput {
  /** Гар бүртгэлийн түлшний мөрд кассын оруулсан яг мөнгөн дүн. */
  amount?: MoneyStr | null;
  item_type: ItemType;
  fuel_id?: UUID | null;
  tank_id?: UUID | null;
  pump_id?: UUID | null;
  nozzle_id?: UUID | null;
  product_id?: UUID | null;
  qty: string;
  unit_price?: MoneyStr | null;
  authorization_id?: UUID | null;
}

export interface PaymentInput {
  method: PaymentMethod;
  amount: MoneyStr;
  contract_id?: UUID | null;
  voucher_code?: string | null;
  card_no?: string | null;
  received?: MoneyStr | null;
  ref_no?: string | null;
}

export interface SaleCreate {
  sale_type: SaleType;
  items: SaleItemInput[];
  payments: PaymentInput[];
  customer_id?: UUID | null;
  contract_id?: UUID | null;
  note?: string | null;
}

export interface SaleItem {
  id: UUID;
  line_no: number;
  item_type: ItemType | string;
  fuel_id: UUID | null;
  tank_id: UUID | null;
  pump_id: UUID | null;
  nozzle_id: UUID | null;
  product_id: UUID | null;
  name_snapshot: string;
  qty: string;
  unit_price: MoneyStr;
  amount: MoneyStr;
  unit_cost: MoneyStr;
  cogs_amount: MoneyStr;
  refunded_qty: string;
}

export interface Payment {
  id: UUID;
  method: PaymentMethod | string;
  method_name: string;
  amount: MoneyStr;
  contract_id: UUID | null;
  voucher_id: UUID | null;
  prepaid_card_id: UUID | null;
  received: MoneyStr | null;
  change_given: MoneyStr | null;
  ref_no: string | null;
}

export interface EbarimtInfo {
  status: EbarimtStatus | string;
  status_name: string;
  receipt_id: string | null;
  qr_data: string | null;
  lottery_no: string | null;
  sent_at: IsoDateTime | null;
}

export interface Sale {
  id: UUID;
  number: number;
  shift_id: UUID;
  shift_number: number | null;
  cashier_id: UUID;
  cashier_name: string | null;
  sale_type: SaleType | string;
  status: SaleStatus | string;
  status_name: string;
  subtotal: MoneyStr;
  vat_amount: MoneyStr;
  total: MoneyStr;
  cogs_total: MoneyStr;
  change_total: MoneyStr;
  customer_id: UUID | null;
  customer_name: string | null;
  contract_id: UUID | null;
  contract_no: string | null;
  note: string | null;
  completed_at: IsoDateTime | null;
  created_at: IsoDateTime | null;
  items: SaleItem[];
  payments: Payment[];
  ebarimt: EbarimtInfo | null;
}

export interface SaleRow {
  id: UUID;
  number: number;
  shift_id: UUID;
  cashier_id: UUID;
  cashier_name: string | null;
  sale_type: SaleType | string;
  status: SaleStatus | string;
  status_name: string;
  total: MoneyStr;
  vat_amount: MoneyStr;
  customer_id: UUID | null;
  customer_name: string | null;
  methods: string[];
  method_names: string[];
  items_count: number;
  completed_at: IsoDateTime | null;
  created_at: IsoDateTime | null;
}

// --------------------------------------------------------------------------
// Баримт (80мм)
// --------------------------------------------------------------------------

export interface ReceiptStation {
  name: string;
  address: string;
  phone: string;
  vat_payer_no: string;
  footer: string;
  printer_width_mm: number;
  currency_symbol: string;
}

export interface ReceiptItem {
  line_no: number;
  name: string;
  unit: string;
  qty: string;
  unit_price: MoneyStr;
  amount: MoneyStr;
}

export interface ReceiptPayment {
  method: PaymentMethod | string;
  method_name: string;
  amount: MoneyStr;
  received: MoneyStr | null;
  change: MoneyStr | null;
}

export interface ReceiptEbarimt {
  status: EbarimtStatus | string;
  status_name: string;
  receipt_id: string | null;
  qr_data: string | null;
  lottery_no: string | null;
}

export interface ReceiptPayload {
  station: ReceiptStation;
  sale_id: UUID;
  number: number;
  sold_at: IsoDateTime | null;
  cashier_name: string | null;
  shift_number: number | null;
  customer_name: string | null;
  contract_no: string | null;
  note: string | null;
  items: ReceiptItem[];
  subtotal: MoneyStr;
  vat_amount: MoneyStr;
  total: MoneyStr;
  change_total: MoneyStr;
  payments: ReceiptPayment[];
  ebarimt: ReceiptEbarimt | null;
}

export interface SaleCreatedResponse {
  sale: Sale;
  receipt: ReceiptPayload;
}

// --------------------------------------------------------------------------
// Буцаалт, үнийн өөрчлөлт
// --------------------------------------------------------------------------

export interface RefundItemInput {
  sale_item_id: UUID;
  qty: string;
}

export interface RefundCreate {
  sale_id: UUID;
  refund_type: RefundType;
  items: RefundItemInput[];
  amount?: MoneyStr | null;
  reason?: string | null;
  restock: boolean;
  refund_method?: PaymentMethod | null;
}

export interface RefundDecision {
  note?: string | null;
}

export interface RefundItem {
  id: UUID;
  sale_item_id: UUID;
  name: string;
  item_type: string;
  qty: string;
  amount: MoneyStr;
  cogs_amount: MoneyStr;
}

export interface Refund {
  id: UUID;
  sale_id: UUID;
  sale_number: number | null;
  refund_type: RefundType | string;
  amount: MoneyStr;
  vat_amount: MoneyStr;
  cogs_amount: MoneyStr;
  reason: string | null;
  restock: boolean;
  refund_method: PaymentMethod | string;
  refund_method_name: string;
  status: ApprovalStatus | string;
  status_name: string;
  requested_by: UUID | null;
  requested_by_name: string | null;
  decided_by: UUID | null;
  decided_by_name: string | null;
  decided_at: IsoDateTime | null;
  decision_note: string | null;
  shift_id: UUID | null;
  items: RefundItem[];
  created_at: IsoDateTime | null;
}

export interface RefundResult {
  refund: Refund;
  sale_status: string | null;
  journal_entry_id: UUID | null;
}

export interface PriceChange {
  id: UUID;
  target_type: PriceTargetType | string;
  /** Аль салбарт үйлчлэх вэ (null = бүх салбар). */
  branch_id: UUID | null;
  branch_name: string | null;
  fuel_id: UUID | null;
  product_id: UUID | null;
  target_name: string | null;
  old_price: MoneyStr;
  new_price: MoneyStr;
  diff: MoneyStr;
  reason: string | null;
  status: ApprovalStatus | string;
  status_name: string;
  requested_by: UUID | null;
  requested_by_name: string | null;
  decided_by: UUID | null;
  decided_by_name: string | null;
  decided_at: IsoDateTime | null;
  decision_note: string | null;
  created_at: IsoDateTime | null;
}

export interface PriceChangeCreate {
  target_type: PriceTargetType;
  /** Хоосон = бүх салбар (суурь үнэ солигдоно). */
  branch_id?: UUID | null;
  fuel_id?: UUID | null;
  product_id?: UUID | null;
  new_price: MoneyStr;
  /** Аль өдрөөс хэрэгжих вэ (хоосон = батламагц шууд). */
  effective_date?: string | null;
  reason?: string | null;
}

export interface PriceChangeDecision {
  note?: string | null;
}

// --------------------------------------------------------------------------
// Нягтлан бодох бүртгэл
// --------------------------------------------------------------------------

export interface Account {
  id: UUID;
  code: string;
  name_mn: string;
  account_type: AccountType | string;
  is_postable: boolean;
  parent_code: string | null;
  sort_order: number;
}

export interface JournalLine {
  id: UUID;
  line_no: number;
  account_code: string;
  debit: MoneyStr;
  credit: MoneyStr;
  memo: string | null;
  dim_fuel_id: UUID | null;
  dim_tank_id: UUID | null;
  dim_customer_id: UUID | null;
  dim_supplier_id: UUID | null;
}

export interface JournalEntry {
  id: UUID;
  entry_no: number;
  entry_date: IsoDate;
  description: string;
  source_type: string;
  source_id: UUID;
  event_type: string;
  posted_by: UUID | null;
  created_at: IsoDateTime;
  lines: JournalLine[];
}

export interface ManualEntryLineInput {
  account_code: string;
  debit: MoneyStr;
  credit: MoneyStr;
  memo?: string | null;
}

export interface ManualEntryCreate {
  entry_date: IsoDate;
  description: string;
  lines: ManualEntryLineInput[];
}

export interface TrialBalanceRow {
  code: string;
  name_mn: string;
  account_type: AccountType | string;
  debit: MoneyStr;
  credit: MoneyStr;
  balance: MoneyStr;
}

export interface TrialBalance {
  as_of: IsoDate | null;
  accounts: TrialBalanceRow[];
  total_debit: MoneyStr;
  total_credit: MoneyStr;
  imbalance: MoneyStr;
}

export interface AccountingStatementRow {
  code: string;
  name_mn: string;
  amount: MoneyStr;
}

export interface FuelMargin {
  fuel_id: UUID;
  fuel_name_mn: string | null;
  revenue: MoneyStr;
  cogs: MoneyStr;
  margin: MoneyStr;
  margin_pct: string;
}

export interface IncomeStatement {
  date_from: IsoDate;
  date_to: IsoDate;
  revenue: AccountingStatementRow[];
  total_revenue: MoneyStr;
  cogs: AccountingStatementRow[];
  total_cogs: MoneyStr;
  expense: AccountingStatementRow[];
  total_expense: MoneyStr;
  gross_profit: MoneyStr;
  net_profit: MoneyStr;
  fuel_margins: FuelMargin[];
}

export interface BalanceSheetRow {
  code: string;
  name_mn: string;
  balance: MoneyStr;
}

export interface BalanceSheet {
  as_of: IsoDate | null;
  assets: BalanceSheetRow[];
  total_assets: MoneyStr;
  liabilities: BalanceSheetRow[];
  total_liabilities: MoneyStr;
  equity: BalanceSheetRow[];
  total_equity: MoneyStr;
  retained_earnings: MoneyStr;
  total_liabilities_equity: MoneyStr;
  is_balanced: boolean;
  difference: MoneyStr;
}

export interface CashFlowRow {
  event_type: string;
  inflow: MoneyStr;
  outflow: MoneyStr;
  net: MoneyStr;
}

export interface CashFlow {
  date_from: IsoDate;
  date_to: IsoDate;
  accounts: string[];
  opening_balance: MoneyStr;
  flows: CashFlowRow[];
  total_inflow: MoneyStr;
  total_outflow: MoneyStr;
  net_change: MoneyStr;
  closing_balance: MoneyStr;
}

export interface TankValuationRow {
  tank_id: UUID;
  tank_name: string;
  fuel_id: UUID | null;
  fuel_name_mn: string | null;
  qty: LitersStr;
  avg_cost: MoneyStr;
  value: MoneyStr;
}

export interface ProductValuationRow {
  product_id: UUID;
  sku: string;
  name_mn: string;
  qty: string;
  avg_cost: MoneyStr;
  value: MoneyStr;
}

export interface InventoryValuation {
  tanks: TankValuationRow[];
  products: ProductValuationRow[];
  fuel_value: MoneyStr;
  goods_value: MoneyStr;
  total_value: MoneyStr;
  ledger_fuel: MoneyStr;
  ledger_goods: MoneyStr;
  ledger_total: MoneyStr;
  fuel_delta: MoneyStr;
  goods_delta: MoneyStr;
  total_delta: MoneyStr;
}

export interface IntegrityCheck {
  name: string;
  ok: boolean;
  expected: MoneyStr;
  actual: MoneyStr;
  difference: MoneyStr;
}

export interface SettlementCreate {
  method: "card" | "qr";
  amount: MoneyStr;
  date: IsoDate;
}

export interface Settlement {
  journal_entry_id: UUID;
  entry_no: number;
  method: string;
  amount: MoneyStr;
  settlement_date: IsoDate;
}

export interface ApInvoice {
  id: UUID;
  supplier_id: UUID;
  supplier_name: string | null;
  invoice_no: string;
  invoice_date: IsoDate;
  due_date: IsoDate | null;
  source_type: string;
  source_id: UUID;
  amount_gross: MoneyStr;
  amount_paid: MoneyStr;
  amount_due: MoneyStr;
  status: InvoiceStatus | string;
}

export interface ApPaymentCreate {
  ap_invoice_id: UUID;
  amount: MoneyStr;
  paid_from: CashAccount;
  payment_date: IsoDate;
  note?: string | null;
}

export interface ApPayment {
  id: UUID;
  ap_invoice_id: UUID;
  supplier_id: UUID;
  amount: MoneyStr;
  paid_from: string;
  payment_date: IsoDate;
  note: string | null;
  created_by: UUID | null;
}

export interface ApPaymentResult {
  payment: ApPayment;
  invoice: ApInvoice;
  journal_entry_id: UUID | null;
}

// --------------------------------------------------------------------------
// Тайлан
// --------------------------------------------------------------------------

export interface SalesReportRow {
  key: string;
  label: string;
  count: number;
  liters: LitersStr;
  net: MoneyStr;
  vat: MoneyStr;
  gross: MoneyStr;
  cogs: MoneyStr;
  margin: MoneyStr;
  margin_pct: string;
}

export interface SalesReport {
  date_from: IsoDate;
  date_to: IsoDate;
  group_by: string;
  rows: SalesReportRow[];
  count: number;
  total_liters: LitersStr;
  total_net: MoneyStr;
  total_vat: MoneyStr;
  total_gross: MoneyStr;
  total_cogs: MoneyStr;
  total_margin: MoneyStr;
  avg_ticket: MoneyStr;
  by_tender: TenderRow[];
}

export interface FuelReportRow {
  fuel_id: UUID;
  code: string;
  name_mn: string;
  color_hex: string;
  liters_sold: LitersStr;
  liters_received: LitersStr;
  liters_variance: LitersStr;
  revenue: MoneyStr;
  cogs: MoneyStr;
  margin: MoneyStr;
  margin_pct: string;
  closing_liters: LitersStr;
}

export interface FuelReport {
  date_from: IsoDate;
  date_to: IsoDate;
  rows: FuelReportRow[];
  total_liters_sold: LitersStr;
  total_revenue: MoneyStr;
  total_cogs: MoneyStr;
  total_margin: MoneyStr;
}

// --------------------------------------------------------------------------
// Хяналтын самбар
// --------------------------------------------------------------------------

export interface DashboardAlert {
  kind: string;
  level: "info" | "warning" | "danger" | string;
  message: string;
  count?: number;
}

/** `GET /api/dashboards/cashier` — backend-ийн бодит хэлбэр. */
export interface CashierDashboard {
  date: string;
  shift: CashierDashboardShift | null;
  /** Нэвтэрсэн түгээгчийн өнөөдрийн үзүүлэлт. */
  today: CashierDashboardToday;
  /** Станцын нийт өнөөдрийн үзүүлэлт (бүх түгээгч). */
  station_today: CashierDashboardStation;
  tanks: Tank[];
  pumps: Pump[];
}

export interface CashierDashboardShift {
  id: UUID;
  number: number;
  status: string;
  opened_at: IsoDateTime;
  opened_by: UUID;
  opened_by_name: string | null;
  opening_cash: MoneyStr;
  sales_count: number;
  sales_total: MoneyStr;
}

export interface CashierDashboardToday {
  total: MoneyStr;
  sale_count: number;
  liters: LitersStr;
  by_tender: TenderRow[];
}

export interface CashierDashboardStation {
  total: MoneyStr;
  sale_count: number;
  liters: LitersStr;
  gross_profit: MoneyStr;
}

export interface TrendPoint {
  date: IsoDate;
  amount: MoneyStr;
  liters: LitersStr;
  count: number;
}

export interface TopCustomerRow {
  customer_id: UUID;
  customer_name: string;
  amount: MoneyStr;
  balance: MoneyStr;
}

export interface OwnerDashboard {
  date_from: IsoDate;
  date_to: IsoDate;
  revenue: MoneyStr;
  gross_profit: MoneyStr;
  margin_pct: string;
  sales_count: number;
  fuel_liters: LitersStr;
  cash_position: MoneyStr;
  bank_position: MoneyStr;
  receivables: MoneyStr;
  payables: MoneyStr;
  inventory_value: MoneyStr;
  trend: TrendPoint[];
  fuel_margins: FuelMargin[];
  top_customers: TopCustomerRow[];
  pending_price_changes: number;
  pending_refunds: number;
  ebarimt_failed: number;
  low_tanks: Tank[];
  low_products: InventoryRow[];
  alerts: DashboardAlert[];
}

// --------------------------------------------------------------------------
// Систем
// --------------------------------------------------------------------------

export interface EbarimtQueueRow {
  id: UUID;
  sale_id: UUID;
  sale_number: number | null;
  status: EbarimtStatus | string;
  status_name: string;
  attempt_count: number;
  last_error: string | null;
  receipt_id: string | null;
  qr_data: string | null;
  lottery_no: string | null;
  sent_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface AuditLog {
  id: UUID;
  user_id: UUID | null;
  user_full_name: string | null;
  action: string;
  entity_type: string | null;
  entity_id: UUID | null;
  before: Record<string, JsonValue> | null;
  after: Record<string, JsonValue> | null;
  ip: string | null;
  created_at: IsoDateTime;
}

export type SettingsMap = Record<string, JsonValue>;

export interface Setting {
  key: string;
  value: JsonValue;
  description: string | null;
}

/** Нөөцлөлт хадгалах хавтасны төлөв. */
export interface BackupDirectory {
  directory: string;
  writable: boolean;
  free_mb: number;
  /** True бол системийн анхдагч (тохиргоонд өөрчлөөгүй). */
  is_default: boolean;
}

export interface BackupFile {
  /** Backend талбарын нэр — `filename`. */
  filename: string;
  size_bytes: number;
  size_mb: number;
  created_at: IsoDateTime;
}

export interface BackupResult {
  ok: boolean;
  file: BackupFile | null;
  message?: string | null;
}

export interface RestoreRequest {
  confirm: string;
}

export interface HealthResponse {
  status: string;
  db: boolean;
  redis: boolean;
}

// --------------------------------------------------------------------------
// Харилцах данс, банкны хуулга
// --------------------------------------------------------------------------

export interface BankAccount {
  id: UUID;
  branch_id: UUID | null;
  bank_name: string;
  account_number: string;
  holder_name: string;
  currency: string;
  opening_balance: MoneyStr;
  /** Ерөнхий дэвтэр дэх цэвэр хөдөлгөөн (дебит − кредит). */
  movement: MoneyStr;
  balance: MoneyStr;
  /** Банкны шимтгэлийг анхдагчаар энэ данснаас хаана. */
  is_fee_default: boolean;
  is_active: boolean;
  note: string | null;
  sort_order: number;
  created_at: IsoDateTime | null;
  updated_at: IsoDateTime | null;
}

export interface BankAccountList {
  items: BankAccount[];
  total: number;
  /** Аль ч данстай холбогдоогүй 1110 хөдөлгөөн. */
  unassigned: MoneyStr;
  /** Σ(дансны үлдэгдэл) + хуваарилаагүй = 1110 дансны үлдэгдэл. */
  ledger_balance: MoneyStr;
}

export interface BankAccountCreate {
  bank_name: string;
  account_number: string;
  holder_name?: string;
  currency?: string;
  opening_balance?: MoneyStr;
  branch_id?: UUID | null;
  is_fee_default?: boolean;
  is_active?: boolean;
  note?: string | null;
  sort_order?: number;
}

export type BankAccountUpdate = Partial<BankAccountCreate>;

/** Хуулгын мөрөнд дутуу байгаа зүйл. */
export type BankTxnMissing = "target" | "desc";

export interface BankTransaction {
  id: UUID;
  txn_date: IsoDateTime | null;
  debit: MoneyStr;
  credit: MoneyStr;
  bank_description: string;
  bank_counterpart: string;
  is_fee: boolean;
  description: string;
  customer_id: UUID | null;
  customer_name: string | null;
  contract_id: UUID | null;
  contract_no: string | null;
  expense_account_code: string | null;
  expense_account_name: string | null;
  ar_payment_id: UUID | null;
  expense_id: UUID | null;
  posted_at: IsoDateTime | null;
  is_income: boolean;
  /** ПОС-ын тооцоо (SETTLEMENT) мөр эсэх. */
  is_settlement: boolean;
  missing: BankTxnMissing[];
}

export interface BankStatementFee {
  count: number;
  total: MoneyStr;
  posted: boolean;
  expense_number: number | null;
}

export interface BankStatement {
  id: UUID;
  account_number: string;
  currency: string;
  date_from: IsoDate | null;
  date_to: IsoDate | null;
  filename: string;
  uploaded_at: IsoDateTime | null;
  bank_account_id: UUID | null;
  bank_name: string | null;
  txn_count: number;
  total_credit: MoneyStr;
  total_debit: MoneyStr;
  posted_count: number;
  ready_count: number;
  missing: Record<string, number>;
  fee: BankStatementFee;
}

export interface BankStatementDetail extends BankStatement {
  transactions: BankTransaction[];
}

export interface BankStatementConfig {
  settlement_customer_id: UUID | null;
  settlement_customer_name: string | null;
  settlement_contract_id: UUID | null;
  settlement_contract_no: string | null;
  settlement_description: string;
  fee_account_code: string | null;
  fee_account_name: string | null;
  fee_description: string;
}

export interface BankStatementConfigInput {
  settlement_contract_id?: UUID | null;
  settlement_description?: string;
  fee_account_code?: string | null;
  fee_description?: string;
}

export interface BankTransactionUpdate {
  description?: string;
  contract_id?: UUID | null;
  expense_account_code?: string | null;
}

export interface PostAllResult {
  posted: number;
  skipped: { id: string; reason: string }[];
  statement: BankStatementDetail;
}

// --------------------------------------------------------------------------
// Түгээгчийн өдрийн ээлж
// --------------------------------------------------------------------------

export interface ShiftAttachment {
  id: UUID;
  kind: "open" | "close" | "settlement" | "price_mark" | string;
  ref_id: UUID | null;
  original_name: string;
  content_type: string;
  size_bytes: number;
  created_at: IsoDateTime | null;
}

export interface PriceMark {
  id: UUID;
  nozzle_id: UUID;
  nozzle_number: number | null;
  fuel_name: string;
  reading: LitersStr;
  old_price: MoneyStr;
  new_price: MoneyStr;
  note: string | null;
  created_at: IsoDateTime | null;
}

export interface PriceMarkInput {
  nozzle_id: UUID;
  reading: LitersStr;
  new_price: MoneyStr;
  note?: string | null;
}

export interface CreditItemInput {
  fuel_id?: UUID | null;
  product_id?: UUID | null;
  qty?: string | null;
  amount?: MoneyStr | null;
}

export interface CreditLineInput {
  contract_id: UUID;
  items: CreditItemInput[];
}

export interface OilLineInput {
  product_id: UUID;
  qty: string;
  unit_price?: MoneyStr | null;
}

export interface ArPaymentLineInput {
  contract_id: UUID;
  amount: MoneyStr;
  method: "cash" | "card" | "transfer";
  note?: string | null;
}

export interface ExpenseLineInput {
  account_code: string;
  amount: MoneyStr;
  payment_method: "cash" | "bank";
  description?: string | null;
}

export interface DailyCloseRequest {
  totalizer_readings: TotalizerReadingInput[];
  declared_cash: MoneyStr;
  settlement_vat: MoneyStr;
  settlement_novat: MoneyStr;
  /** Дансаар шилжүүлж тушаасан дүн. */
  transfer_total?: MoneyStr;
  oil_lines: OilLineInput[];
  credit_lines: CreditLineInput[];
  ar_payments: ArPaymentLineInput[];
  expenses: ExpenseLineInput[];
  tank_dips?: TankDipInput[];
  note?: string | null;
}

export interface DailySegment {
  liters: LitersStr;
  price: MoneyStr;
  amount: MoneyStr;
}

export interface DailyNozzleCalc {
  nozzle_id: UUID;
  pump_id: UUID;
  nozzle_number: number;
  fuel_id: UUID;
  tank_id?: UUID;
  pump_name?: string;
  fuel_name?: string;
  tank_name?: string;
  open_reading: LitersStr;
  close_reading: LitersStr;
  liters: LitersStr;
  amount: MoneyStr;
  segments: DailySegment[];
}

/** Сав тус бүрийн өдрийн зарлага — Σ хошууны милийн зөрүү. */
export interface DailyTankRow {
  tank_id: UUID;
  tank_name: string;
  liters: LitersStr;
  amount: MoneyStr;
}

export interface DailyPreview {
  nozzles: DailyNozzleCalc[];
  fuel_total: MoneyStr;
  fuel_liters: LitersStr;
  opening_cash: MoneyStr;
}

export interface DailyClosing {
  settlement_vat: MoneyStr;
  settlement_novat: MoneyStr;
  settlement_total: MoneyStr;
  /** Дансаар шилжүүлж тушаасан дүн. */
  transfer_total: MoneyStr;
  fuel_total: MoneyStr;
  credit_total: MoneyStr;
  oil_total: MoneyStr;
  note: string | null;
  nozzles: DailyNozzleCalc[];
  tanks?: DailyTankRow[];
}

/** Өдрийн тооцооны жагсаалтын мөр — нэг хаагдсан түгээгчийн ээлж. */
export interface DailyClosingRow {
  shift_id: UUID;
  shift_number: number;
  date: string;
  attendant: string;
  opening_cash: MoneyStr;
  fuel_total: MoneyStr;
  credit_total: MoneyStr;
  oil_total: MoneyStr;
  settlement_total: MoneyStr;
  transfer_total: MoneyStr;
  declared_cash: MoneyStr | null;
  expected_cash: MoneyStr | null;
  cash_over_short: MoneyStr | null;
}
