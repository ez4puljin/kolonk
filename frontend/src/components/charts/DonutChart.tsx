/** Бөгж график — төлбөрийн хэрэгсэл/ангилалын эзлэх хувь, төвдөө нийт дүн. */

import { ChartEmpty, ChartLegend, chartColor, chartNumber, type ChartValue, type LegendItem } from "./chartBase";

export interface DonutSlice {
  key: string;
  label: string;
  value: ChartValue;
  color?: string | null;
  /** Бэлэн форматласан утга (`formatMNT`). */
  display?: string;
  /** Хувийн бэлэн текст ("42.1%"). */
  share?: string;
}

export interface DonutChartProps {
  data: readonly DonutSlice[];
  /** Дэлгэц уншигчид зориулсан гарчиг (`<title>`). */
  title: string;
  /** Төвийн жижиг шошго. */
  centerLabel?: string;
  /** Төвийн том утга — бэлэн форматласан. */
  centerValue?: string;
  size?: number;
  thickness?: number;
  legend?: boolean;
  emptyMessage?: string;
  className?: string;
}

const VIEW = 220;

function polar(radius: number, angleDeg: number): { x: number; y: number } {
  const radians = ((angleDeg - 90) * Math.PI) / 180;
  return { x: VIEW / 2 + radius * Math.cos(radians), y: VIEW / 2 + radius * Math.sin(radians) };
}

function arcPath(outer: number, inner: number, startAngle: number, endAngle: number): string {
  const large = endAngle - startAngle > 180 ? 1 : 0;
  const a = polar(outer, startAngle);
  const b = polar(outer, endAngle);
  const c = polar(inner, endAngle);
  const d = polar(inner, startAngle);
  return [
    `M ${a.x.toFixed(2)} ${a.y.toFixed(2)}`,
    `A ${outer} ${outer} 0 ${large} 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`,
    `L ${c.x.toFixed(2)} ${c.y.toFixed(2)}`,
    `A ${inner} ${inner} 0 ${large} 0 ${d.x.toFixed(2)} ${d.y.toFixed(2)}`,
    "Z",
  ].join(" ");
}

export function DonutChart({
  data,
  title,
  centerLabel,
  centerValue,
  size = 200,
  thickness = 30,
  legend = true,
  emptyMessage,
  className = "",
}: DonutChartProps) {
  const slices = data
    .map((slice, index) => ({ slice, index, amount: Math.max(0, chartNumber(slice.value)) }))
    .filter((entry) => entry.amount > 0);

  const total = slices.reduce((sum, entry) => sum + entry.amount, 0);

  if (total <= 0) {
    return <ChartEmpty height={size} message={emptyMessage} className={className} />;
  }

  const outer = VIEW / 2 - 6;
  const inner = Math.max(12, outer - thickness);

  let cursor = 0;
  const arcs = slices.map((entry) => {
    const sweep = (entry.amount / total) * 360;
    const start = cursor;
    cursor += sweep;
    return {
      key: entry.slice.key,
      color: chartColor(entry.index, entry.slice.color),
      label: entry.slice.label,
      display: entry.slice.display,
      path: sweep >= 359.99 ? null : arcPath(outer, inner, start, Math.min(360, start + sweep)),
    };
  });

  const legendItems: LegendItem[] = slices.map((entry) => ({
    key: entry.slice.key,
    label: entry.slice.label,
    color: chartColor(entry.index, entry.slice.color),
    value: entry.slice.display,
    hint: entry.slice.share ?? `${((entry.amount / total) * 100).toFixed(1)}%`,
  }));

  return (
    <div className={`flex flex-col items-center gap-4 sm:flex-row sm:items-center ${className}`}>
      <svg
        role="img"
        aria-label={title}
        viewBox={`0 0 ${VIEW} ${VIEW}`}
        width={size}
        height={size}
        className="max-w-full shrink-0"
      >
        <title>{title}</title>
        {arcs.map((arc) =>
          arc.path === null ? (
            <circle
              key={arc.key}
              cx={VIEW / 2}
              cy={VIEW / 2}
              r={(outer + inner) / 2}
              fill="none"
              stroke={arc.color}
              strokeWidth={outer - inner}
            >
              <title>{`${arc.label}: ${arc.display ?? ""}`}</title>
            </circle>
          ) : (
            <path key={arc.key} d={arc.path} fill={arc.color}>
              <title>{`${arc.label}: ${arc.display ?? ""}`}</title>
            </path>
          ),
        )}

        {centerValue ? (
          <text
            x={VIEW / 2}
            y={centerLabel ? VIEW / 2 + 2 : VIEW / 2 + 6}
            textAnchor="middle"
            fontSize={centerValue.length > 11 ? 17 : 21}
            fontWeight={700}
            fill="#0F172A"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {centerValue}
          </text>
        ) : null}
        {centerLabel ? (
          <text x={VIEW / 2} y={VIEW / 2 + 22} textAnchor="middle" fontSize={12} fill="#94A3B8">
            {centerLabel}
          </text>
        ) : null}
      </svg>

      {legend ? <ChartLegend items={legendItems} className="w-full min-w-0 flex-1" /> : null}
    </div>
  );
}

export default DonutChart;
