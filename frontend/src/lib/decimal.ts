/**
 * Мөнгөний арифметик — BigInt дээр 10^2 масштабтай.
 *
 * Сервер мөнгийг **string**-ээр өгдөг (CONTRACTS.md §2, §9). `parseFloat`-аар
 * тооцоолвол 0.1 + 0.2 ≠ 0.3 маягийн алдаа гарна. Тиймээс энэ модулийн бүх
 * функц string авч string буцаана — хуваан төлөх, хариулт бодох логик бүхэлдээ
 * эндүүр явна.
 */

export type Money = string | number | null | undefined;

const SCALE = 2;
const FACTOR = 100n;
/** dMul-д ашиглах итгэлцүүрийн нарийвчлал (10^6). */
const MUL_SCALE = 1_000_000n;

const ZERO = "0.00";

/** "-1234.567" → -123457n (хагасыг дээш нь). Буруу утга → 0n. */
function toScaled(value: Money): bigint {
  if (value === null || value === undefined) return 0n;

  let raw = typeof value === "number" ? numberToRaw(value) : value.trim();
  if (raw === "") return 0n;

  // Экспоненциал бичлэг (1e-7) — тоогоор дамжуулж хэвийн болгоно.
  if (/e/i.test(raw)) {
    const n = Number(raw);
    if (!Number.isFinite(n)) return 0n;
    raw = numberToRaw(n);
  }

  const match = /^([+-]?)(\d*)(?:\.(\d*))?$/.exec(raw);
  if (!match) return 0n;

  const sign = match[1] === "-" ? -1n : 1n;
  const intPart = match[2] === "" ? "0" : match[2];
  const fracRaw = match[3] ?? "";

  const fracKept = fracRaw.slice(0, SCALE).padEnd(SCALE, "0");
  const nextDigit = fracRaw.charCodeAt(SCALE); // NaN бол дугуйлахгүй

  let scaled = BigInt(intPart) * FACTOR + BigInt(fracKept);
  if (nextDigit >= 53 /* '5' */) scaled += 1n; // хагасыг дээш (тэгээс хол)

  return sign * scaled;
}

function numberToRaw(value: number): string {
  if (!Number.isFinite(value)) return "0";
  // 20 орон — double-ийн бүх мэдээллийг барихад хангалттай, экспонентгүй.
  return value.toFixed(Math.min(20, Math.max(SCALE + 6, 8)));
}

/** -123456n → "-1234.56" */
function fromScaled(scaled: bigint): string {
  const negative = scaled < 0n;
  const abs = negative ? -scaled : scaled;
  const int = abs / FACTOR;
  const frac = abs % FACTOR;
  const body = `${int}.${frac.toString().padStart(SCALE, "0")}`;
  return negative && body !== "0.00" ? `-${body}` : body;
}

// --------------------------------------------------------------------------
// Нийтийн API
// --------------------------------------------------------------------------

/** Дурын оролтыг "1234.56" хэлбэрт хөрвүүлнэ. */
export function toDisplay(value: Money): string {
  return fromScaled(toScaled(value));
}

/** Хоёр дүнг нэмнэ. */
export function dAdd(a: Money, b: Money): string {
  return fromScaled(toScaled(a) + toScaled(b));
}

/** a − b */
export function dSub(a: Money, b: Money): string {
  return fromScaled(toScaled(a) - toScaled(b));
}

/**
 * Дүнг тоон итгэлцүүрээр үржүүлнэ (тоо ширхэг, литр, хувь).
 * Итгэлцүүрийг 10^6 нарийвчлалаар барьж, үр дүнг 2 орон руу дугуйлна.
 */
export function dMul(value: Money, factor: number): string {
  if (!Number.isFinite(factor)) return ZERO;

  const scaledValue = toScaled(value);
  const scaledFactor = BigInt(Math.round(factor * Number(MUL_SCALE)));
  const product = scaledValue * scaledFactor; // 10^(2+6) масштаб

  const negative = product < 0n;
  const abs = negative ? -product : product;
  let result = abs / MUL_SCALE;
  if ((abs % MUL_SCALE) * 2n >= MUL_SCALE) result += 1n;

  return fromScaled(negative ? -result : result);
}

/**
 * Хуваалт — `a / b`, `decimals` орны нарийвчлалтай мөр буцаана.
 *
 * Түлшний ПОС-д "мөнгөн дүн ÷ литрийн үнэ = литр" гэж бодоход хэрэглэнэ.
 * Хуваарь 0 бол "0" (тэгд хуваахгүй).
 */
export function dDiv(a: Money, b: Money, decimals = 2): string {
  const divisor = toScaled(b);
  if (divisor === 0n) return decimals > 0 ? `0.${"0".repeat(decimals)}` : "0";

  const power = 10n ** BigInt(decimals);
  const dividend = toScaled(a) * power;

  const negative = dividend < 0n !== divisor < 0n;
  const absDividend = dividend < 0n ? -dividend : dividend;
  const absDivisor = divisor < 0n ? -divisor : divisor;

  let result = absDividend / absDivisor;
  if ((absDividend % absDivisor) * 2n >= absDivisor) result += 1n; // хагасыг дээш

  const text = result.toString().padStart(decimals + 1, "0");
  const whole = text.slice(0, text.length - decimals) || "0";
  const frac = decimals > 0 ? `.${text.slice(text.length - decimals)}` : "";
  return `${negative ? "-" : ""}${whole}${frac}`;
}

/** Жагсаалтын нийлбэр. */
export function dSum(values: readonly Money[]): string {
  let acc = 0n;
  for (const v of values) acc += toScaled(v);
  return fromScaled(acc);
}

/** −1 (a < b), 0 (тэнцүү), 1 (a > b) */
export function dCmp(a: Money, b: Money): -1 | 0 | 1 {
  const x = toScaled(a);
  const y = toScaled(b);
  if (x < y) return -1;
  if (x > y) return 1;
  return 0;
}

export function dIsZero(value: Money): boolean {
  return toScaled(value) === 0n;
}

export function dIsNegative(value: Money): boolean {
  return toScaled(value) < 0n;
}

export function dIsPositive(value: Money): boolean {
  return toScaled(value) > 0n;
}

/** Тэмдгийг эсрэгээр. */
export function dNeg(value: Money): string {
  return fromScaled(-toScaled(value));
}

/** Үнэмлэхүй утга. */
export function dAbs(value: Money): string {
  const scaled = toScaled(value);
  return fromScaled(scaled < 0n ? -scaled : scaled);
}

/** Тэгээс бага бол тэг болгоно (үлдэгдэл төлбөр бодоход). */
export function dClampMin(value: Money, min: Money = ZERO): string {
  return dCmp(value, min) < 0 ? toDisplay(min) : toDisplay(value);
}

/** Хоёрын бага нь. */
export function dMin(a: Money, b: Money): string {
  return dCmp(a, b) <= 0 ? toDisplay(a) : toDisplay(b);
}

/** Хоёрын их нь. */
export function dMax(a: Money, b: Money): string {
  return dCmp(a, b) >= 0 ? toDisplay(a) : toDisplay(b);
}

/**
 * Зөвхөн хязгаар шалгах/дэвсгэр өргөнд зориулсан тоон хөрвүүлэлт.
 * Мөнгөн үр дүн бодоход **хэрэглэхгүй**.
 *
 * АНХААР: энэ нь мөнгөний 2 орон руу дугуйлдаг тул литр, кг зэрэг 3 оронтой
 * тоо хэмжээнд хэрэглэж БОЛОХГҮЙ (2.609 л → 2.61 болно). Тэдгээрт `dToQty`.
 */
export function dToNumber(value: Money): number {
  return Number(toDisplay(value));
}

/**
 * Тоо хэмжээний (литр, кг, ширхэг) тоон утга — 3 орны нарийвчлалтай.
 *
 * Сервер тоо хэмжээг `Numeric(12,3)` гэж хадгалдаг тул ПОС-оос явуулах
 * литр, задлан барааны хэмжээг энэ функцээр хөрвүүлнэ. Мөнгө биш учир
 * float ашиглах нь аюулгүй — 3 орон нь давхар нарийвчлалд яг багтана.
 */
export function dToQty(value: Money): number {
  const raw = typeof value === "number" ? value : Number((value ?? "").toString().trim());
  if (!Number.isFinite(raw)) return 0;
  return Math.round(raw * 1000) / 1000;
}

export const D_ZERO = ZERO;
