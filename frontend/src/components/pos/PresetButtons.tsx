import { Infinity as InfinityIcon, Keyboard } from "lucide-react";

import type { MoneyStr, PresetType } from "../../api/types";
import { t } from "../../i18n/mn";
import { PRESET_AMOUNTS, PRESET_LITERS } from "../../lib/constants";
import { dCmp } from "../../lib/decimal";
import { formatNumber } from "../../lib/format";
import type { EntryMode } from "./AmountLiterToggle";

export interface PresetButtonsProps {
  mode: EntryMode;
  presetType: PresetType;
  presetValue: MoneyStr | null;
  onPreset: (type: PresetType, value: MoneyStr | null) => void;
  /** Гараар оруулах — NumPad нээнэ. */
  onCustom: () => void;
}

function isActive(
  presetType: PresetType,
  presetValue: MoneyStr | null,
  type: PresetType,
  value: string,
): boolean {
  if (presetType !== type) return false;
  if (presetValue === null) return false;
  return dCmp(presetValue, value) === 0;
}

const TILE =
  "flex min-h-20 flex-col items-center justify-center gap-0.5 rounded-2xl border-2 text-center transition-colors";

/** 10Л / 20Л / 30Л / 50Л + Дүүргэх + Гараар. */
export function PresetButtons({ mode, presetType, presetValue, onPreset, onCustom }: PresetButtonsProps) {
  const values = mode === "liters" ? PRESET_LITERS : PRESET_AMOUNTS;
  const type: PresetType = mode === "liters" ? "liters" : "amount";
  const unit = mode === "liters" ? t.units.liter : t.units.mnt;

  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm font-semibold tracking-wide text-ink-soft uppercase">{t.pos.preset}</div>

      <div className="grid grid-cols-3 gap-3">
        {values.map((raw) => {
          const value = String(raw);
          const active = isActive(presetType, presetValue, type, value);
          return (
            <button
              key={value}
              type="button"
              onClick={() => onPreset(type, value)}
              aria-pressed={active}
              className={[
                TILE,
                active
                  ? "border-action bg-action text-white"
                  : "border-line-strong bg-white text-ink hover:bg-surface-alt active:bg-surface-sunken",
              ].join(" ")}
            >
              <span className="num text-3xl leading-none font-black">{formatNumber(raw, 0)}</span>
              <span className={`text-sm font-semibold ${active ? "text-white/80" : "text-ink-soft"}`}>
                {unit}
              </span>
            </button>
          );
        })}

        <button
          type="button"
          onClick={() => onPreset("full", null)}
          aria-pressed={presetType === "full"}
          className={[
            TILE,
            presetType === "full"
              ? "border-success bg-success text-white"
              : "border-success/40 bg-success-soft text-success-dark active:bg-success/20",
          ].join(" ")}
        >
          <InfinityIcon className="h-7 w-7" />
          <span className="text-base font-bold">{t.pos.presetFull}</span>
        </button>

        <button
          type="button"
          onClick={onCustom}
          className={[TILE, "border-line-strong bg-white text-ink active:bg-surface-sunken"].join(" ")}
        >
          <Keyboard className="h-7 w-7 text-ink-soft" />
          <span className="text-base font-bold">{t.pos.presetCustom}</span>
        </button>
      </div>
    </div>
  );
}

export default PresetButtons;
