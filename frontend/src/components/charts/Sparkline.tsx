/** Нэг цувааны богино чиг хандлага — гарын үсэг шиг жижиг график. */

import { ChartEmpty, chartColor, chartNumber, useChartWidth, type ChartValue } from "./chartBase";

export interface SparklinePoint {
  key: string;
  label: string;
  value: ChartValue;
}

export interface SparklineProps {
  points: readonly SparklinePoint[];
  /** Дэлгэц уншигчид зориулсан гарчиг (`<title>`). */
  title: string;
  color?: string | null;
  height?: number;
  /** Графикийн дээр харагдах бэлэн форматласан утга. */
  caption?: string;
  emptyMessage?: string;
  className?: string;
}

export function Sparkline({
  points,
  title,
  color,
  height = 64,
  caption,
  emptyMessage,
  className = "",
}: SparklineProps) {
  const { ref, width } = useChartWidth(280);
  const stroke = chartColor(0, color);

  const values = points.map((point) => chartNumber(point.value));
  const usable = values.length >= 2 && width > 16;

  let linePath = "";
  let areaPath = "";
  let lastX = 0;
  let lastY = 0;

  if (usable) {
    const padY = 5;
    const padX = 2;
    const plotW = Math.max(1, width - padX * 2);
    const plotH = Math.max(1, height - padY * 2);

    let min = Math.min(...values);
    let max = Math.max(...values);
    if (max === min) {
      max = min + 1;
      min -= 1;
    }
    const span = max - min;

    const coords = values.map((value, index) => {
      const x = padX + (plotW * index) / (values.length - 1);
      const y = padY + plotH - ((value - min) / span) * plotH;
      return { x, y };
    });

    linePath = coords
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
      .join(" ");

    const first = coords[0];
    const last = coords[coords.length - 1];
    lastX = last.x;
    lastY = last.y;
    areaPath = `${linePath} L ${last.x.toFixed(2)} ${(height - padY).toFixed(2)} L ${first.x.toFixed(2)} ${(height - padY).toFixed(2)} Z`;
  }

  return (
    <div ref={ref} className={`w-full min-w-0 ${className}`}>
      {caption ? <div className="num mb-1 text-sm font-semibold text-ink">{caption}</div> : null}

      {usable ? (
        <svg role="img" aria-label={title} width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          <title>{title}</title>
          <path d={areaPath} fill={stroke} opacity={0.14} />
          <path
            d={linePath}
            fill="none"
            stroke={stroke}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx={lastX} cy={lastY} r={3.5} fill={stroke} />
        </svg>
      ) : (
        <ChartEmpty height={height} message={emptyMessage} />
      )}
    </div>
  );
}

export default Sparkline;
