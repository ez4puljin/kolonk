/**
 * Дэлгэцэнд харуулах формат.
 *
 * ЧУХАЛ: мөнгө сервер талаас **string**-ээр ирнэ. Энд зөвхөн харуулахын тулд
 * `Number()`-ыг форматлагчийн дотор ашиглана. Мөнгөн **арифметик** хийхийг
 * хориглоно — түүнийг `lib/decimal.ts`-ийн string/BigInt функцууд гүйцэтгэнэ.
 */

import { t } from "../i18n/mn";

export type Numeric = string | number | null | undefined;

const CURRENCY = t.units.mnt;
const GROUP_SEP = " "; // тасрахгүй зай — "58 800₮" мөр дундуур тасрахгүй
const EMPTY = "—";

const LOCALE = "mn-MN";

/** `null`, хоосон, тоо биш утгыг ялгана. */
function toNumber(value: Numeric): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const raw = value.trim();
  if (raw === "") return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Тухайн локалиар бүхэл/аравтын хэсгийг нь ялгаж, "-1234.56" хэлбэрт хөрвүүлнэ.
 * `Intl` байхгүй/алдаа өгвөл `toFixed`-руу шилжинэ.
 */
function plainFixed(value: number, digits: number): string {
  let raw: string;
  try {
    raw = new Intl.NumberFormat(LOCALE, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      useGrouping: false,
    }).format(value);
  } catch {
    raw = value.toFixed(digits);
  }
  // Локалиас хамаарч зай/таслал орж ирж болно — нэг хэлбэрт оруулна.
  raw = raw.replace(/[\s   ']/g, "").replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(raw)) raw = value.toFixed(digits);
  return raw;
}

/** Мянгатыг зайгаар тусгаарлана: "58800.00" → "58 800.00" */
function group(fixed: string): string {
  const negative = fixed.startsWith("-");
  const body = negative ? fixed.slice(1) : fixed;
  const [intPart, fracPart] = body.split(".");
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, GROUP_SEP);
  const out = fracPart ? `${grouped}.${fracPart}` : grouped;
  return negative ? `-${out}` : out;
}

/** Ерөнхий тоон формат — өгөгдсөн аравтын оронтой, мянгат тусгаарлагчтай. */
export function formatNumber(value: Numeric, digits = 0): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  return group(plainFixed(n, digits));
}

/**
 * Мөнгө — "58 800₮".
 * Аравтын орон харуулахгүй. Зөвхөн 1000-аас бага бөгөөд бутархайтай үед 2 орон.
 */
export function formatMNT(value: Numeric): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  const fractional = Math.abs(n - Math.trunc(n)) > 1e-9;
  const digits = Math.abs(n) < 1000 && fractional ? 2 : 0;
  return `${group(plainFixed(n, digits))}${CURRENCY}`;
}

/** Мөнгө — үргэлж 2 аравтын оронтой (журнал, тооцоо нийлэх акт). */
export function formatMoneyExact(value: Numeric, withSymbol = true): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  const body = group(plainFixed(n, 2));
  return withSymbol ? `${body}${CURRENCY}` : body;
}

/** Литр — "20.00 л". */
export function formatLiters(value: Numeric, digits = 2): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  return `${group(plainFixed(n, digits))} ${t.units.liter}`;
}

/** Тоо ширхэг — хэрэггүй тэгийг таслана ("2", "2.5", "0.750"→"0.75"). */
export function formatQty(value: Numeric, unit?: string | null): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  let body = plainFixed(n, 3);
  if (body.includes(".")) body = body.replace(/\.?0+$/, "");
  const out = group(body);
  return unit ? `${out} ${unit}` : out;
}

/** Хувь — "12.5%". `asRatio` үнэн бол 0.125 → "12.5%". */
export function formatPct(value: Numeric, digits = 1, asRatio = false): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  const scaled = asRatio ? n * 100 : n;
  return `${group(plainFixed(scaled, digits))}${t.units.percent}`;
}

/** Тэмдэгтэй дүн — "+1 200₮" / "−1 200₮". */
export function formatSignedMNT(value: Numeric): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  if (n === 0) return formatMNT(0);
  const sign = n > 0 ? "+" : "−";
  return `${sign}${formatMNT(Math.abs(n))}`;
}

// --------------------------------------------------------------------------
// Огноо, цаг
// --------------------------------------------------------------------------

function toDate(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** "2026.08.06" */
export function formatDate(value: string | number | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return EMPTY;
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`;
}

/** "14:35" */
export function formatTime(value: string | number | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return EMPTY;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** "2026.08.06 14:35" */
export function formatDateTime(value: string | number | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return EMPTY;
  return `${formatDate(d)} ${formatTime(d)}`;
}

/** "14:35:09" — шууд цагийн заагчид. */
export function formatClock(value: string | number | Date | null | undefined): string {
  const d = toDate(value);
  if (!d) return EMPTY;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/** `<input type="date">`-д тохирох "YYYY-MM-DD". */
export function toDateInput(value: Date | string | number | null | undefined): string {
  const d = toDate(value) ?? new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Өнөөдрийн "YYYY-MM-DD". */
export function todayInput(): string {
  return toDateInput(new Date());
}

/** Өнөөдрөөс N хоногийн өмнөх "YYYY-MM-DD". */
export function daysAgoInput(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return toDateInput(d);
}

/** Файлын хэмжээ — "12.4 МБ". */
export function formatBytes(value: Numeric): string {
  const n = toNumber(value);
  if (n === null) return EMPTY;
  const mb = n / (1024 * 1024);
  if (mb < 0.1) return `${group(plainFixed(n / 1024, 1))} КБ`;
  return `${group(plainFixed(mb, 1))} ${t.units.mb}`;
}

export const EMPTY_VALUE = EMPTY;
