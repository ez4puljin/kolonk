import type { Tone } from "../../lib/constants";

export interface ProgressBarProps {
  /** 0-100 хооронд. Хязгаараас гарсан утгыг таслана. */
  value: number;
  tone?: Tone;
  /** Дүүргэлтийн хувиас хамаарч ногоон/шар/улаан болгоно (савны түвшин). */
  autoTone?: boolean;
  size?: "sm" | "md" | "lg";
  label?: string;
  /** Баруун талд харагдах утга ("18 400 л"). */
  valueLabel?: string;
  /** Доод хязгаарын тэмдэглэгээ (0-100). */
  markerPct?: number | null;
  className?: string;
}

const FILL: Record<Tone, string> = {
  success: "bg-success",
  action: "bg-action",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-ink-faint",
  brand: "bg-brand-600",
};

const HEIGHT: Record<NonNullable<ProgressBarProps["size"]>, string> = {
  sm: "h-2",
  md: "h-3.5",
  lg: "h-6",
};

function toneForPct(pct: number): Tone {
  if (pct <= 15) return "danger";
  if (pct <= 30) return "warning";
  return "success";
}

export function ProgressBar({
  value,
  tone = "action",
  autoTone = false,
  size = "md",
  label,
  valueLabel,
  markerPct = null,
  className = "",
}: ProgressBarProps) {
  const pct = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
  const resolved: Tone = autoTone ? toneForPct(pct) : tone;

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {(label || valueLabel) && (
        <div className="flex items-baseline justify-between gap-3 text-sm">
          {label ? <span className="truncate font-medium text-ink-soft">{label}</span> : <span />}
          {valueLabel ? <span className="num shrink-0 font-semibold text-ink">{valueLabel}</span> : null}
        </div>
      )}

      <div
        className={`relative w-full overflow-hidden rounded-full bg-surface-sunken ${HEIGHT[size]}`}
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-300 ease-out ${FILL[resolved]}`}
          style={{ width: `${pct}%` }}
        />
        {markerPct !== null && markerPct > 0 && markerPct < 100 ? (
          <span
            className="absolute inset-y-0 w-0.5 bg-brand-800/60"
            style={{ left: `${Math.min(100, Math.max(0, markerPct))}%` }}
            aria-hidden="true"
          />
        ) : null}
      </div>
    </div>
  );
}

export default ProgressBar;
