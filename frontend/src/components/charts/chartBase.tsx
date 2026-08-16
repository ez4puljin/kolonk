/**
 * Графикийн нийтлэг суурь — өнгөний хуваарь, тэнхлэгийн туслах, хоосон төлөв.
 *
 * ДҮРЭМ: мөнгө/литр сервер талаас **string** ирнэ. Энд `chartNumber` зөвхөн
 * геометр (цэгийн байрлал, баганы өргөн) бодоход хөрвүүлнэ — харагдах утга
 * үргэлж `lib/format.ts`-ийн форматлагчаар дамжина.
 */

import { useEffect, useRef, useState, type RefObject } from "react";

import { t } from "../../i18n/mn";
import { colors } from "../../lib/constants";
import { dToNumber } from "../../lib/decimal";

export type ChartValue = string | number | null | undefined;

/** Бүх график нэг дараалалтай өнгө хэрэглэнэ. */
export const CHART_PALETTE: readonly string[] = [
  colors.action,
  colors.success,
  colors.warning,
  colors.danger,
  "#7C3AED",
  "#0891B2",
  "#DB2777",
  "#65A30D",
  "#EA580C",
  colors.neutral,
];

/** Индексээр өнгө сонгоно. `override` (жишээ нь түлшний өнгө) байвал түүнийг. */
export function chartColor(index: number, override?: string | null): string {
  if (typeof override === "string" && override.trim() !== "") return override;
  const size = CHART_PALETTE.length;
  return CHART_PALETTE[((index % size) + size) % size];
}

/** ЗӨВХӨН геометрт зориулсан хөрвүүлэлт (`parseFloat` биш, decimal.ts дамжина). */
export function chartNumber(value: ChartValue): number {
  const parsed = dToNumber(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Хамгийн ойрын "цэвэрхэн" дээд утга — 1, 2, 2.5, 5, 10 × 10^n. */
export function niceCeil(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const base = 10 ** exponent;
  const normalized = value / base;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return step * base;
}

/** Утгын мужийг тэгийг багтаасан "цэвэрхэн" хязгаар болгоно. */
export function niceDomain(values: readonly number[]): { lo: number; hi: number } {
  let min = 0;
  let max = 0;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  const lo = min < 0 ? -niceCeil(-min) : 0;
  const hi = max > 0 ? niceCeil(max) : 0;
  if (lo === 0 && hi === 0) return { lo: 0, hi: 1 };
  return { lo, hi };
}

/** Тэнхлэгийн тэмдэглэгээний утгууд. */
export function axisTicks(lo: number, hi: number, count = 4): number[] {
  if (!(hi > lo) || count < 1) return [lo];
  const step = (hi - lo) / count;
  const ticks: number[] = [];
  for (let index = 0; index <= count; index += 1) ticks.push(lo + step * index);
  return ticks;
}

function trimDecimal(value: number): string {
  const fixed = value >= 100 ? value.toFixed(0) : value.toFixed(1);
  return fixed.replace(/\.0$/, "");
}

/** Тэнхлэгийн богино тоо — "1.2 сая", "350 мян". */
export function compactNumber(value: number): string {
  if (!Number.isFinite(value)) return "0";
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${sign}${trimDecimal(abs / 1_000_000_000)} тэрбум`;
  if (abs >= 1_000_000) return `${sign}${trimDecimal(abs / 1_000_000)} сая`;
  if (abs >= 1_000) return `${sign}${trimDecimal(abs / 1_000)} мян`;
  return `${sign}${trimDecimal(abs)}`;
}

/** n элементээс хамгийн ихдээ `maxLabels` ширхэг шошго харуулах алхам. */
export function labelStep(count: number, maxLabels: number): number {
  if (count <= maxLabels || maxLabels < 1) return 1;
  return Math.ceil(count / maxLabels);
}

/**
 * Савны бодит өргөнийг хэмжинэ — SVG-г 1:1 пиксэлээр зурснаар текст
 * жижигрэхгүй, 375px дэлгэцэнд ч уншигдана.
 */
export function useChartWidth(fallback = 320): { ref: RefObject<HTMLDivElement>; width: number } {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    const measure = (): void => {
      const next = node.clientWidth;
      if (next > 0) setWidth(next);
    };

    measure();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }

    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}

export interface ChartEmptyProps {
  height?: number;
  message?: string;
  className?: string;
}

/** Өгөгдөлгүй үеийн эелдэг төлөв — график хэзээ ч хоосон дөрвөлжин болохгүй. */
export function ChartEmpty({ height = 120, message, className = "" }: ChartEmptyProps) {
  return (
    <div
      className={`flex items-center justify-center rounded-xl border border-dashed border-line-strong bg-surface-alt px-4 text-center text-sm font-medium text-ink-faint ${className}`}
      style={{ minHeight: height }}
    >
      {message ?? t.reports.noData}
    </div>
  );
}

export interface LegendItem {
  key: string;
  label: string;
  color: string;
  value?: string;
  hint?: string;
}

/** График доорх тайлбар жагсаалт. */
export function ChartLegend({ items, className = "" }: { items: readonly LegendItem[]; className?: string }) {
  if (items.length === 0) return null;
  return (
    <ul className={`flex flex-col gap-1.5 ${className}`}>
      {items.map((item) => (
        <li key={item.key} className="flex min-h-8 items-center gap-2.5 text-sm">
          <span
            className="h-3 w-3 shrink-0 rounded-sm"
            style={{ backgroundColor: item.color }}
            aria-hidden="true"
          />
          <span className="min-w-0 flex-1 truncate text-ink-soft">{item.label}</span>
          {item.value ? <span className="num shrink-0 font-semibold text-ink">{item.value}</span> : null}
          {item.hint ? <span className="num shrink-0 text-xs text-ink-faint">{item.hint}</span> : null}
        </li>
      ))}
    </ul>
  );
}
