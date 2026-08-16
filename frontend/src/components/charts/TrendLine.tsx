/** Олон цувааны чиг хандлага — тэнхлэгийн тэмдэглэгээ, тор, тайлбартай. */

import {
  ChartEmpty,
  ChartLegend,
  axisTicks,
  chartColor,
  chartNumber,
  compactNumber,
  labelStep,
  niceDomain,
  useChartWidth,
  type ChartValue,
  type LegendItem,
} from "./chartBase";

export interface TrendSeries {
  key: string;
  name: string;
  color?: string | null;
  values: readonly ChartValue[];
  /** Тайлбарт харагдах бэлэн нийт дүн. */
  total?: string;
}

export interface TrendLineProps {
  labels: readonly string[];
  series: readonly TrendSeries[];
  /** Дэлгэц уншигчид зориулсан гарчиг (`<title>`). */
  title: string;
  height?: number;
  /** Y тэнхлэгийн тэмдэглэгээний формат (анхдагч — богино тоо). */
  formatTick?: (value: number) => string;
  maxLabels?: number;
  emptyMessage?: string;
  className?: string;
}

export function TrendLine({
  labels,
  series,
  title,
  height = 240,
  formatTick = compactNumber,
  maxLabels = 7,
  emptyMessage,
  className = "",
}: TrendLineProps) {
  const { ref, width } = useChartWidth(320);

  const numeric = series.map((line) => line.values.map((value) => chartNumber(value)));
  const flat = numeric.flat();
  const usable = labels.length >= 2 && flat.length > 0 && width > 80;

  const { lo, hi } = niceDomain(flat);
  const span = hi - lo || 1;

  const gutterLeft = 58;
  const gutterBottom = 26;
  const padTop = 10;
  const padRight = 10;
  const plotW = Math.max(20, width - gutterLeft - padRight);
  const plotH = Math.max(30, height - padTop - gutterBottom);

  const xAt = (index: number): number =>
    gutterLeft + (labels.length > 1 ? (plotW * index) / (labels.length - 1) : plotW / 2);
  const yAt = (value: number): number => padTop + plotH - ((value - lo) / span) * plotH;

  const ticks = axisTicks(lo, hi, 4);
  const step = labelStep(labels.length, maxLabels);
  const showDots = labels.length <= 24;

  const legendItems: LegendItem[] = series.map((line, index) => ({
    key: line.key,
    label: line.name,
    color: chartColor(index, line.color),
    value: line.total,
  }));

  return (
    <div ref={ref} className={`w-full min-w-0 ${className}`}>
      {usable ? (
        <svg role="img" aria-label={title} width={width} height={height}>
          <title>{title}</title>

          {ticks.map((tick) => {
            const y = yAt(tick);
            return (
              <g key={`tick-${tick}`}>
                <line
                  x1={gutterLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  stroke={tick === 0 ? "#CBD5E1" : "#E2E8F0"}
                  strokeWidth={1}
                />
                <text
                  x={gutterLeft - 8}
                  y={y}
                  textAnchor="end"
                  dominantBaseline="middle"
                  fontSize={11}
                  fill="#94A3B8"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {formatTick(tick)}
                </text>
              </g>
            );
          })}

          {labels.map((label, index) =>
            index % step === 0 ? (
              <text
                key={`label-${label}-${index}`}
                x={xAt(index)}
                y={height - 8}
                textAnchor={index === 0 ? "start" : index === labels.length - 1 ? "end" : "middle"}
                fontSize={11}
                fill="#94A3B8"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {label}
              </text>
            ) : null,
          )}

          {series.map((line, lineIndex) => {
            const color = chartColor(lineIndex, line.color);
            const points = numeric[lineIndex];
            const path = labels
              .map((_, index) => {
                const value = points[index] ?? 0;
                return `${index === 0 ? "M" : "L"} ${xAt(index).toFixed(2)} ${yAt(value).toFixed(2)}`;
              })
              .join(" ");

            return (
              <g key={line.key}>
                <path
                  d={path}
                  fill="none"
                  stroke={color}
                  strokeWidth={2.5}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {showDots
                  ? labels.map((label, index) => (
                      <circle
                        key={`${line.key}-${label}-${index}`}
                        cx={xAt(index)}
                        cy={yAt(points[index] ?? 0)}
                        r={3}
                        fill={color}
                      />
                    ))
                  : null}
              </g>
            );
          })}
        </svg>
      ) : (
        <ChartEmpty height={height} message={emptyMessage} />
      )}

      {usable && series.length > 0 ? (
        <ChartLegend items={legendItems} className="mt-3 sm:flex-row sm:flex-wrap sm:gap-x-6" />
      ) : null}
    </div>
  );
}

export default TrendLine;
