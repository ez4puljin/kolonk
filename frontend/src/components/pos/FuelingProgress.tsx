import { Gauge, OctagonX } from "lucide-react";

import type { LitersStr, MoneyStr, PresetType } from "../../api/types";
import { t } from "../../i18n/mn";
import { formatLiters, formatMNT, formatNumber } from "../../lib/format";
import { Button } from "../ui/Button";
import { ProgressBar } from "../ui/ProgressBar";

export interface FuelingProgressProps {
  pumpNumber: number | null;
  nozzleNumber: number | null;
  fuelName: string | null;
  fuelColor: string | null;
  unitPrice: MoneyStr | null;
  liters: LitersStr;
  amount: MoneyStr;
  flow: string;
  presetType: PresetType;
  presetValue: MoneyStr | null;
  /** Зөвшөөрөл өгсөн ч түгээлт эхлээгүй байгаа үе. */
  waiting: boolean;
  onHalt: () => void;
  halting?: boolean;
}

/** Хязгаараас хамаарсан явцын хувь. `full` бол хязгааргүй. */
function progressPct(
  presetType: PresetType,
  presetValue: MoneyStr | null,
  liters: LitersStr,
  amount: MoneyStr,
): number | null {
  if (presetValue === null) return null;
  const target = Number(presetValue);
  if (!Number.isFinite(target) || target <= 0) return null;
  const done = presetType === "liters" ? Number(liters) : Number(amount);
  if (!Number.isFinite(done)) return 0;
  return Math.min(100, (done / target) * 100);
}

export function FuelingProgress({
  pumpNumber,
  nozzleNumber,
  fuelName,
  fuelColor,
  unitPrice,
  liters,
  amount,
  flow,
  presetType,
  presetValue,
  waiting,
  onHalt,
  halting = false,
}: FuelingProgressProps) {
  const accent = fuelColor ?? "#2563EB";
  const pct = progressPct(presetType, presetValue, liters, amount);
  const targetLabel =
    presetValue === null
      ? t.pos.presetFull
      : presetType === "liters"
        ? formatLiters(presetValue, 0)
        : formatMNT(presetValue);

  return (
    <section className="dark-scroll flex min-h-[70vh] flex-1 flex-col overflow-hidden rounded-2xl bg-brand-900 p-5 text-ink-invert sm:p-8">
      {/* Толгой */}
      <header className="flex flex-wrap items-center gap-4">
        <span
          className="num flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-4xl font-black text-white"
          style={{ backgroundColor: accent }}
        >
          {pumpNumber ?? "?"}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-2xl font-bold text-white">{fuelName ?? t.sales.fuel}</div>
          <div className="num mt-0.5 text-sm text-slate-400">
            {t.pumps.nozzleNo}
            {nozzleNumber ?? "—"} · {formatNumber(unitPrice, 0)} {t.units.perLiter} · {t.pos.preset}:{" "}
            {targetLabel}
          </div>
        </div>
        <span
          className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-bold ${
            waiting
              ? "border-warning/50 bg-warning/15 text-warning"
              : "border-success/50 bg-success/15 text-success"
          }`}
        >
          <Gauge className="h-4 w-4" />
          {waiting ? t.pos.authorizing : t.pos.fueling}
        </span>
      </header>

      {/* Шууд заалт */}
      <div className="flex flex-1 flex-col items-center justify-center gap-2 py-8">
        <div className="text-sm font-semibold tracking-widest text-slate-400 uppercase">{t.pos.liters}</div>
        <div className="num text-[clamp(56px,14vw,132px)] leading-none font-black text-white">
          {formatNumber(liters, 2)}
        </div>
        <div className="text-lg font-semibold text-slate-400">{t.units.litersLong}</div>

        <div className="mt-6 text-sm font-semibold tracking-widest text-slate-400 uppercase">
          {t.pos.amountMnt}
        </div>
        <div
          className="num text-[clamp(40px,10vw,88px)] leading-none font-black"
          style={{ color: accent }}
        >
          {formatMNT(amount)}
        </div>
      </div>

      {/* Явц */}
      <div className="flex flex-col gap-4">
        {pct === null ? (
          <div className="h-6 w-full overflow-hidden rounded-full bg-brand-800">
            <div className="h-full w-1/3 animate-pulse rounded-full bg-action" />
          </div>
        ) : (
          <ProgressBar value={pct} size="lg" tone="action" valueLabel={`${Math.round(pct)}${t.units.percent}`} />
        )}

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="num text-lg font-semibold text-slate-300">
            {t.pos.flow}: {formatNumber(flow, 1)} {t.units.lpm}
          </div>

          <Button
            variant="danger"
            size="lg"
            icon={<OctagonX />}
            loading={halting}
            onClick={onHalt}
            className="min-w-48"
          >
            {t.pos.stop}
          </Button>
        </div>
      </div>
    </section>
  );
}

export default FuelingProgress;
