import { Banknote, Droplet } from "lucide-react";

import { t } from "../../i18n/mn";

/** Гараар оруулах горим — дүнгээр (₮) эсвэл литрээр (л). */
export type EntryMode = "amount" | "liters";

export interface AmountLiterToggleProps {
  value: EntryMode;
  onChange: (mode: EntryMode) => void;
  className?: string;
}

const OPTIONS: readonly { mode: EntryMode; label: string; unit: string }[] = [
  { mode: "amount", label: t.pos.presetAmount, unit: t.units.mnt },
  { mode: "liters", label: t.pos.presetLiters, unit: t.units.liter },
];

export function AmountLiterToggle({ value, onChange, className = "" }: AmountLiterToggleProps) {
  return (
    <div
      role="tablist"
      aria-label={t.pos.presetCustom}
      className={`grid grid-cols-2 gap-2 rounded-2xl border border-line-strong bg-surface-alt p-2 ${className}`}
    >
      {OPTIONS.map((option) => {
        const active = option.mode === value;
        return (
          <button
            key={option.mode}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(option.mode)}
            className={[
              "flex min-h-14 items-center justify-center gap-2.5 rounded-xl text-lg font-bold transition-colors",
              active ? "bg-action text-white shadow-sm" : "bg-white text-ink-soft active:bg-surface-sunken",
            ].join(" ")}
          >
            {option.mode === "amount" ? (
              <Banknote className="h-6 w-6" />
            ) : (
              <Droplet className="h-6 w-6" />
            )}
            {option.label}
            <span className={active ? "text-white/80" : "text-ink-faint"}>{option.unit}</span>
          </button>
        );
      })}
    </div>
  );
}

export default AmountLiterToggle;
