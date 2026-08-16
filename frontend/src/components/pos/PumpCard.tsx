import { AlertTriangle, Fuel, Gauge, PowerOff } from "lucide-react";

import type { Pump, PumpTelemetry } from "../../api/types";
import { t } from "../../i18n/mn";
import { PUMP_STATUS_META, colors, statusMeta } from "../../lib/constants";
import { formatLiters, formatMNT, formatNumber } from "../../lib/format";

/** Дэлгэц дээрх дөрвөн байдал — CONTRACTS-ийн 6 төлвийг эндээс буулгана. */
export type PumpVisual = "idle" | "active" | "busy" | "down";

export function pumpVisual(status: string): PumpVisual {
  if (status === "idle") return "idle";
  if (status === "authorized" || status === "fueling") return "active";
  if (status === "complete") return "busy";
  return "down";
}

const RING: Record<PumpVisual, string> = {
  idle: colors.success,
  active: colors.action,
  busy: colors.warning,
  down: colors.danger,
};

const SHELL: Record<PumpVisual, string> = {
  idle: "bg-white",
  active: "bg-action-soft",
  busy: "bg-warning-soft",
  down: "bg-surface-alt",
};

export interface PumpCardProps {
  pump: Pump;
  /** WebSocket-ийн шууд телеметр (байхгүй бол `pump.live`). */
  live: PumpTelemetry | null;
  onSelect: (pump: Pump) => void;
  /** Ээлж хаалттай / өөр таталт явж байгаа үед. */
  disabled?: boolean;
}

export function PumpCard({ pump, live, onSelect, disabled = false }: PumpCardProps) {
  const telemetry = live ?? pump.live;
  const status = telemetry?.status ?? pump.status;
  const visual = pumpVisual(status);
  const meta = statusMeta(PUMP_STATUS_META, status);
  const ring = RING[visual];
  const selectable = visual === "idle" && !disabled && pump.nozzles.length > 0;

  return (
    <button
      type="button"
      disabled={!selectable}
      onClick={() => onSelect(pump)}
      aria-label={`${t.pumps.pumpNo}${pump.number} — ${meta.label}`}
      className={[
        "relative flex min-h-56 flex-col overflow-hidden rounded-2xl border-4 px-4 py-4 text-left transition-transform",
        SHELL[visual],
        selectable ? "hover:-translate-y-0.5 active:translate-y-0" : "cursor-default",
        disabled && visual === "idle" ? "opacity-60" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ borderColor: ring }}
    >
      {/* Идэвхтэй таталтын цохилт */}
      {visual === "active" ? (
        <span
          className="pointer-events-none absolute inset-0 animate-pulse rounded-xl"
          style={{ boxShadow: `inset 0 0 0 6px ${ring}33` }}
          aria-hidden="true"
        />
      ) : null}

      {/* Толгой */}
      <div className="relative flex items-start gap-3">
        <span
          className="num flex h-16 w-16 shrink-0 items-center justify-center rounded-xl text-4xl font-black text-white"
          style={{ backgroundColor: ring }}
        >
          {pump.number}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-base font-bold text-ink">{pump.name}</span>
          <span className="mt-1 flex items-center gap-1.5 text-sm font-semibold" style={{ color: ring }}>
            {visual === "down" ? (
              status === "error" ? (
                <AlertTriangle className="h-4 w-4" />
              ) : (
                <PowerOff className="h-4 w-4" />
              )
            ) : visual === "active" ? (
              <Gauge className="h-4 w-4" />
            ) : (
              <Fuel className="h-4 w-4" />
            )}
            {meta.label}
          </span>
        </span>
      </div>

      {/* Шууд заалт эсвэл хошуунууд */}
      {visual === "active" || visual === "busy" ? (
        <div className="relative mt-4 flex flex-1 flex-col justify-center gap-1">
          <div className="num text-[44px] leading-none font-bold text-ink">
            {formatLiters(telemetry?.liters ?? "0.000", 2)}
          </div>
          <div className="num text-2xl leading-none font-bold" style={{ color: ring }}>
            {formatMNT(telemetry?.amount ?? "0.00")}
          </div>
          <div className="num mt-1 text-sm text-ink-soft">
            {t.pos.flow}: {formatNumber(telemetry?.flow_lpm ?? "0", 1)} {t.units.lpm}
          </div>
        </div>
      ) : (
        <div className="relative mt-4 flex flex-1 flex-col justify-end gap-1.5">
          {pump.nozzles.map((nozzle) => (
            <div key={nozzle.id} className="flex items-center gap-2 text-sm">
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: nozzle.color_hex }}
                aria-hidden="true"
              />
              <span className="min-w-0 flex-1 truncate font-semibold text-ink">{nozzle.fuel_name}</span>
              <span className="num shrink-0 font-bold text-ink-soft">
                {formatNumber(nozzle.price_per_liter, 0)} {t.units.perLiter}
              </span>
            </div>
          ))}
          {pump.nozzles.length === 0 ? (
            <div className="text-sm text-ink-faint">{t.common.none}</div>
          ) : null}
        </div>
      )}
    </button>
  );
}

export default PumpCard;
