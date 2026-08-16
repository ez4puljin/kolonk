/** Ангилалын багана — хэвтээ (жагсаалт) эсвэл босоо (хугацаа) байрлалтай. */

import type { ReactElement } from "react";

import {
  ChartEmpty,
  chartColor,
  chartNumber,
  labelStep,
  niceDomain,
  useChartWidth,
  type ChartValue,
} from "./chartBase";

export interface BarDatum {
  key: string;
  label: string;
  value: ChartValue;
  /** Тухайн зүйлийн өөрийн өнгө (жишээ: түлшний `color_hex`). */
  color?: string | null;
  /** Бэлэн форматласан утга — `formatMNT`, `formatLiters` гэх мэт. */
  display?: string;
}

export interface BarChartProps {
  data: readonly BarDatum[];
  /** Дэлгэц уншигчид зориулсан гарчиг (`<title>`). */
  title: string;
  orientation?: "horizontal" | "vertical";
  /** Утгын шошго харуулах эсэх. */
  showValues?: boolean;
  /** Босоо байрлалын өндөр (хэвтээд мөрийн тооноос бодогдоно). */
  height?: number;
  /** Босоо байрлалд хамгийн ихдээ хэдэн х тэнхлэгийн шошго. */
  maxLabels?: number;
  emptyMessage?: string;
  className?: string;
}

const ROW_HEIGHT = 34;
const AXIS_HEIGHT = 22;

export function BarChart({
  data,
  title,
  orientation = "horizontal",
  showValues = true,
  height = 200,
  maxLabels = 8,
  emptyMessage,
  className = "",
}: BarChartProps) {
  const { ref, width } = useChartWidth(320);
  const values = data.map((item) => chartNumber(item.value));
  const usable = data.length > 0 && width > 40;

  const { lo, hi } = niceDomain(values);
  const span = hi - lo || 1;

  const horizontal = orientation === "horizontal";
  const chartHeight = horizontal ? Math.max(ROW_HEIGHT, data.length * ROW_HEIGHT + 6) : height;

  const body = (): ReactElement => {
    if (horizontal) {
      const labelW = Math.min(160, Math.max(70, Math.round(width * 0.3)));
      const valueW = showValues ? Math.min(150, Math.max(74, Math.round(width * 0.27))) : 0;
      const trackX = labelW + 8;
      const trackW = Math.max(12, width - trackX - valueW - 4);
      const zeroX = trackX + ((0 - lo) / span) * trackW;

      return (
        <svg role="img" aria-label={title} width={width} height={chartHeight}>
          <title>{title}</title>
          {data.map((item, index) => {
            const value = values[index];
            const valueX = trackX + ((value - lo) / span) * trackW;
            const barX = Math.min(zeroX, valueX);
            const barW = Math.max(2, Math.abs(valueX - zeroX));
            const rowY = index * ROW_HEIGHT + 3;
            const fill = chartColor(index, item.color);

            return (
              <g key={item.key}>
                <text
                  x={0}
                  y={rowY + ROW_HEIGHT / 2}
                  dominantBaseline="middle"
                  fontSize={13}
                  fill="#475569"
                >
                  {item.label.length > 18 ? `${item.label.slice(0, 17)}…` : item.label}
                </text>
                <rect
                  x={trackX}
                  y={rowY + 6}
                  width={trackW}
                  height={ROW_HEIGHT - 16}
                  rx={3}
                  fill="#F1F5F9"
                />
                <rect x={barX} y={rowY + 6} width={barW} height={ROW_HEIGHT - 16} rx={3} fill={fill}>
                  <title>{`${item.label}: ${item.display ?? String(item.value ?? "")}`}</title>
                </rect>
                {showValues ? (
                  <text
                    x={width}
                    y={rowY + ROW_HEIGHT / 2}
                    dominantBaseline="middle"
                    textAnchor="end"
                    fontSize={13}
                    fontWeight={600}
                    fill="#0F172A"
                    style={{ fontVariantNumeric: "tabular-nums" }}
                  >
                    {item.display ?? ""}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      );
    }

    const plotTop = 8;
    const plotH = Math.max(24, chartHeight - AXIS_HEIGHT - plotTop);
    const slot = width / data.length;
    const barW = Math.max(3, Math.min(30, slot * 0.66));
    const zeroY = plotTop + plotH - ((0 - lo) / span) * plotH;
    const step = labelStep(data.length, maxLabels);

    return (
      <svg role="img" aria-label={title} width={width} height={chartHeight}>
        <title>{title}</title>
        <line x1={0} y1={zeroY} x2={width} y2={zeroY} stroke="#CBD5E1" strokeWidth={1} />
        {data.map((item, index) => {
          const value = values[index];
          const valueY = plotTop + plotH - ((value - lo) / span) * plotH;
          const barY = Math.min(zeroY, valueY);
          const barH = Math.max(2, Math.abs(valueY - zeroY));
          const centerX = slot * index + slot / 2;
          const fill = chartColor(index, item.color);

          return (
            <g key={item.key}>
              <rect x={centerX - barW / 2} y={barY} width={barW} height={barH} rx={2} fill={fill}>
                <title>{`${item.label}: ${item.display ?? String(item.value ?? "")}`}</title>
              </rect>
              {index % step === 0 ? (
                <text
                  x={centerX}
                  y={chartHeight - 6}
                  textAnchor="middle"
                  fontSize={11}
                  fill="#94A3B8"
                  style={{ fontVariantNumeric: "tabular-nums" }}
                >
                  {item.label}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
    );
  };

  return (
    <div ref={ref} className={`w-full min-w-0 ${className}`}>
      {usable ? body() : <ChartEmpty height={horizontal ? 120 : height} message={emptyMessage} />}
    </div>
  );
}

export default BarChart;
