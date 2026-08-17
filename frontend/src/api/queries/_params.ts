/**
 * Жагсаалтын параметрийн нэрийг backend-ийн хүлээж буй нэр рүү хөрвүүлнэ.
 *
 * Frontend-ийн hook-ууд түүхэн шалтгаанаар `q` / `active_only` гэсэн нэр
 * ашигладаг ч router бүр өөр нэр хүлээж авдаг (`search`, `is_active`).
 * Хөрвүүлэлтийг энд төвлөрүүлснээр дэлгэцүүдийн код өөрчлөгдөхгүйгээр
 * шүүлт сервер талд зөв ажиллана.
 */

import type { QueryParams, QueryValue } from "../client";

/**
 * Дурын hook-ийн параметрийн объект.
 *
 * `object` гэж зарлаж байгаа нь санаатай: `Record<string, unknown>` гэвэл
 * индекс гарын үсэггүй энгийн `interface`-ууд (ProductListParams г.м.)
 * TypeScript-д тохирохгүй болдог.
 */
type AnyParams = object | undefined;

function isQueryValue(value: unknown): value is QueryValue | QueryValue[] {
  if (Array.isArray(value)) return value.every(isQueryValue);
  return (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  );
}

function rename(params: AnyParams, map: Record<string, string>): QueryParams {
  const out: QueryParams = {};
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (!isQueryValue(value)) continue;
    out[map[key] ?? key] = value;
  }
  return out;
}

/** `search` + `is_active` хүлээж авдаг router-ууд: products, inventory, suppliers. */
export function searchIsActive(params: AnyParams): QueryParams {
  return rename(params, { q: "search", active_only: "is_active" });
}

/** `search` + `active_only` хүлээж авдаг router: customers. */
export function searchActiveOnly(params: AnyParams): QueryParams {
  return rename(params, { q: "search" });
}

/** Зөвхөн `q` → `search` (contracts). */
export function searchOnly(params: AnyParams): QueryParams {
  return rename(params, { q: "search" });
}

/** Нэр солих шаардлагагүй — зөвхөн хоосон утгыг цэвэрлэнэ. */
export function clean(params: AnyParams): QueryParams {
  return rename(params, {});
}
