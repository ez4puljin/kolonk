import type { ReactNode } from "react";
import { Check } from "lucide-react";

export interface TouchSelectOption<V> {
  value: V;
  label: string;
  hint?: string;
  /** Плиткийн өнгөт зурвас (жишээ: түлшний өнгө). */
  color?: string;
  icon?: ReactNode;
  disabled?: boolean;
  badge?: ReactNode;
}

export interface TouchSelectProps<V> {
  value: V | null;
  onChange: (value: V) => void;
  options: readonly TouchSelectOption<V>[];
  label?: string;
  /** Багананы тоо (анхдагч 2, ≥640px). */
  columns?: 1 | 2 | 3 | 4;
  size?: "md" | "lg";
  className?: string;
}

const COLUMNS: Record<1 | 2 | 3 | 4, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-2 sm:grid-cols-3",
  4: "grid-cols-2 sm:grid-cols-4",
};

/** Уугуул `<select>`-ийн оронд том плитка — бээлийтэй хуруунд ээлтэй. */
export function TouchSelect<V extends string | number>({
  value,
  onChange,
  options,
  label,
  columns = 2,
  size = "md",
  className = "",
}: TouchSelectProps<V>) {
  const height = size === "lg" ? "min-h-20" : "min-h-16";

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {label ? <span className="text-sm font-medium text-ink-soft">{label}</span> : null}
      <div className={`grid gap-3 ${COLUMNS[columns]}`} role="listbox" aria-label={label}>
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <button
              key={String(option.value)}
              type="button"
              role="option"
              aria-selected={selected}
              disabled={option.disabled}
              onClick={() => onChange(option.value)}
              className={[
                "relative flex items-center gap-3 overflow-hidden rounded-xl border px-4 py-3 text-left transition-colors",
                height,
                selected
                  ? "border-action bg-action-soft ring-2 ring-action"
                  : "border-line-strong bg-white hover:bg-surface-alt active:bg-surface-sunken",
                option.disabled ? "pointer-events-none opacity-40" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {option.color ? (
                <span
                  className="absolute inset-y-0 left-0 w-1.5"
                  style={{ backgroundColor: option.color }}
                  aria-hidden="true"
                />
              ) : null}

              {option.icon ? (
                <span className="ml-1 shrink-0 text-ink-soft [&_svg]:h-6 [&_svg]:w-6">{option.icon}</span>
              ) : null}

              <span className="min-w-0 flex-1">
                <span className="block truncate text-base font-bold text-ink">{option.label}</span>
                {option.hint ? (
                  <span className="num block truncate text-sm text-ink-soft">{option.hint}</span>
                ) : null}
              </span>

              {option.badge}

              {selected ? (
                <Check className="h-6 w-6 shrink-0 text-action" aria-hidden="true" />
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default TouchSelect;
