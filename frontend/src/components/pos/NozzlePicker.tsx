import { Check, Droplets } from "lucide-react";

import type { PumpNozzle, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { formatLiters, formatNumber } from "../../lib/format";

export interface NozzlePickerProps {
  nozzles: readonly PumpNozzle[];
  value: UUID | null;
  onChange: (nozzle: PumpNozzle) => void;
}

/** Хошуу тус бүрд нэг том плитка — түлшний нэр, ₮/л, савны үлдэгдэл. */
export function NozzlePicker({ nozzles, value, onChange }: NozzlePickerProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm font-semibold tracking-wide text-ink-soft uppercase">{t.pos.selectNozzle}</div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {nozzles.map((nozzle) => {
          const selected = nozzle.id === value;
          const dry = Number(nozzle.tank_current_l) <= 0;
          return (
            <button
              key={nozzle.id}
              type="button"
              disabled={dry}
              onClick={() => onChange(nozzle)}
              aria-pressed={selected}
              className={[
                "relative flex min-h-28 items-center gap-4 overflow-hidden rounded-2xl border-2 px-5 py-4 text-left transition-colors",
                selected
                  ? "border-action bg-action-soft ring-2 ring-action"
                  : "border-line-strong bg-white hover:bg-surface-alt active:bg-surface-sunken",
                dry ? "pointer-events-none opacity-45" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span
                className="absolute inset-y-0 left-0 w-2"
                style={{ backgroundColor: nozzle.color_hex }}
                aria-hidden="true"
              />

              <span
                className="ml-1 flex h-14 w-14 shrink-0 items-center justify-center rounded-xl text-white"
                style={{ backgroundColor: nozzle.color_hex }}
              >
                <Droplets className="h-7 w-7" />
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-xl font-bold text-ink">{nozzle.fuel_name}</span>
                <span className="num mt-0.5 block text-2xl font-black text-ink">
                  {formatNumber(nozzle.price_per_liter, 0)}
                  <span className="ml-1 text-base font-semibold text-ink-soft">{t.units.perLiter}</span>
                </span>
                <span className="num mt-0.5 block truncate text-xs text-ink-faint">
                  {t.pumps.nozzleNo}
                  {nozzle.nozzle_number} · {nozzle.tank_name} · {formatLiters(nozzle.tank_current_l, 0)}
                </span>
              </span>

              {selected ? <Check className="h-7 w-7 shrink-0 text-action" aria-hidden="true" /> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default NozzlePicker;
