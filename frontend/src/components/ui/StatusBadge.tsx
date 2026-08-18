import type { ReactNode } from "react";

import type { StatusMeta, Tone } from "../../lib/constants";

export interface StatusBadgeProps {
  label?: string;
  meta?: StatusMeta;
  tone?: Tone;
  icon?: ReactNode;
  /** Зүүн талд өнгөт цэг харуулах. */
  dot?: boolean;
  size?: "sm" | "md";
  className?: string;
}

const CHIP: Record<Tone, string> = {
  violet: "bg-violet-100 text-violet-700 border-violet-300",
  success: "bg-success-soft text-success-dark border-success/30",
  action: "bg-action-soft text-action-dark border-action/30",
  warning: "bg-warning-soft text-warning-dark border-warning/30",
  danger: "bg-danger-soft text-danger-dark border-danger/30",
  neutral: "bg-surface-sunken text-ink-soft border-line-strong",
  brand: "bg-brand-800 text-ink-invert border-brand-700",
};

const DOT: Record<Tone, string> = {
  violet: "bg-violet-500",
  success: "bg-success",
  action: "bg-action",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-ink-faint",
  brand: "bg-ink-faint",
};

export function StatusBadge({
  label,
  meta,
  tone,
  icon,
  dot = false,
  size = "md",
  className = "",
}: StatusBadgeProps) {
  const resolvedTone: Tone = tone ?? meta?.tone ?? "neutral";
  const text = label ?? meta?.label ?? "";
  const sizing = size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm";

  return (
    <span
      className={[
        "inline-flex shrink-0 items-center gap-2 rounded-full border font-semibold whitespace-nowrap",
        sizing,
        CHIP[resolvedTone],
        className,
      ].join(" ")}
    >
      {dot ? <span className={`h-2 w-2 rounded-full ${DOT[resolvedTone]}`} /> : null}
      {icon}
      {text}
    </span>
  );
}

export default StatusBadge;
