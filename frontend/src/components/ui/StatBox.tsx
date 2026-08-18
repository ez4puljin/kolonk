import type { ReactNode } from "react";

import type { Tone } from "../../lib/constants";

export interface StatBoxProps {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  /** Өөрчлөлт — "+12.4%" гэх мэт. */
  delta?: ReactNode;
  deltaTone?: Tone;
  icon?: ReactNode;
  tone?: Tone;
  size?: "md" | "lg" | "xl";
  onClick?: () => void;
  className?: string;
}

const TEXT_TONE: Record<Tone, string> = {
  success: "text-success-dark",
  action: "text-action-dark",
  warning: "text-warning-dark",
  danger: "text-danger-dark",
  neutral: "text-ink",
  brand: "text-ink-invert",
};

const ACCENT: Record<Tone, string> = {
  success: "bg-success",
  action: "bg-action",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-line-strong",
  brand: "bg-brand-600",
};

const SHELL: Record<Tone, string> = {
  success: "bg-white border-line",
  action: "bg-white border-line",
  warning: "bg-white border-line",
  danger: "bg-white border-line",
  neutral: "bg-white border-line",
  brand: "bg-panel border-brand-700",
};

const VALUE_SIZE: Record<NonNullable<StatBoxProps["size"]>, string> = {
  md: "text-3xl",
  lg: "text-[40px] leading-none",
  xl: "text-[56px] leading-none",
};

export function StatBox({
  label,
  value,
  unit,
  hint,
  delta,
  deltaTone = "neutral",
  icon,
  tone = "neutral",
  size = "md",
  onClick,
  className = "",
}: StatBoxProps) {
  const interactive = typeof onClick === "function";
  const labelTone = tone === "brand" ? "text-ink-faint" : "text-ink-soft";

  const content = (
    <>
      <span className={`absolute inset-y-0 left-0 w-1.5 ${ACCENT[tone]}`} aria-hidden="true" />
      <div className="flex items-start justify-between gap-3">
        <span className={`text-sm font-medium ${labelTone}`}>{label}</span>
        {icon ? <span className={`shrink-0 ${TEXT_TONE[tone]}`}>{icon}</span> : null}
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className={`num font-bold tracking-tight ${VALUE_SIZE[size]} ${TEXT_TONE[tone]}`}>
          {value}
        </span>
        {unit ? <span className={`text-lg font-semibold ${labelTone}`}>{unit}</span> : null}
      </div>

      {(delta || hint) && (
        <div className="mt-2 flex items-center gap-2 text-sm">
          {delta ? <span className={`font-semibold ${TEXT_TONE[deltaTone]}`}>{delta}</span> : null}
          {hint ? <span className={labelTone}>{hint}</span> : null}
        </div>
      )}
    </>
  );

  // Утсанд хэвтээ зайг хураана: 152px өргөнтэй хайрцагт 44px зай нь
  // 9 оронтой төгрөгийн дүнг таслахад хүргэж байв.
  const shell = `relative overflow-hidden rounded-xl border pl-4 pr-3 py-4 sm:pl-6 sm:pr-5 ${SHELL[tone]} ${className}`;

  if (interactive) {
    return (
      <button type="button" onClick={onClick} className={`${shell} touch-target text-left transition-colors hover:bg-surface-alt`}>
        {content}
      </button>
    );
  }

  return <div className={shell}>{content}</div>;
}

export default StatBox;
