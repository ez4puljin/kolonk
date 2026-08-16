import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Banknote,
  CreditCard,
  Database,
  Droplets,
  Fuel,
  Gauge,
  Package,
  TriangleAlert,
} from "lucide-react";

import { usePumps } from "../../api/queries/pumps";
import { useCurrentShift } from "../../api/queries/shifts";
import { useTanks } from "../../api/queries/tanks";
import type { Tank } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { pumpVisual } from "../../components/pos/PumpCard";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { PUMP_STATUS_META, colors, statusMeta } from "../../lib/constants";
import { D_ZERO, dAdd } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, formatMoneyExact, formatPct } from "../../lib/format";
import { usePumpsStore } from "../../stores/pumps";

const VISUAL_COLOR = {
  idle: colors.success,
  active: colors.action,
  busy: colors.warning,
  down: colors.danger,
} as const;

function fillPct(tank: Tank): number {
  const pct = Number(tank.fill_pct);
  return Number.isFinite(pct) ? pct : 0;
}

function minPct(tank: Tank): number | null {
  const capacity = Number(tank.capacity_l);
  const min = Number(tank.min_level_l);
  if (!Number.isFinite(capacity) || capacity <= 0 || !Number.isFinite(min)) return null;
  return (min / capacity) * 100;
}

export function CashierDashboard() {
  const navigate = useNavigate();

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const { data: tanksPage, isLoading: tanksLoading } = useTanks({ active_only: true });
  const { data: pumpsPage } = usePumps({ active_only: true });
  const telemetry = usePumpsStore((state) => state.telemetry);

  const shift = current?.shift ?? null;
  const tanks = useMemo(() => tanksPage?.items ?? [], [tanksPage]);
  const pumps = useMemo(() => pumpsPage?.items ?? [], [pumpsPage]);
  const lowTanks = tanks.filter((tank) => tank.is_low);

  const cashless = useMemo(() => {
    let sum = D_ZERO;
    for (const row of current?.sales.by_tender ?? []) {
      if (row.method === "card" || row.method === "qr") sum = dAdd(sum, row.amount);
    }
    return sum;
  }, [current]);

  if (shiftLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.dashboard.title}
        actions={
          <>
            <Button variant="secondary" size="md" icon={<Package />} onClick={() => navigate("/pos/store")}>
              {t.pos.store}
            </Button>
            <Button variant="primary" size="md" icon={<Fuel />} onClick={() => navigate("/pos")}>
              {t.pos.forecourt}
            </Button>
          </>
        }
      />

      {/* Ээлжийн байдал */}
      {shift ? (
        <section className="flex flex-wrap items-center gap-4 rounded-2xl bg-brand-900 px-5 py-4 text-ink-invert">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-success text-white">
            <Gauge className="h-7 w-7" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="num text-xl font-bold text-white">
              {t.shift.current} · {t.shift.number}
              {shift.number}
            </div>
            <div className="num text-sm text-slate-400">
              {t.shift.opened}: {formatDateTime(shift.opened_at)} · {shift.opened_by_name ?? ""}
            </div>
          </div>
          <Button variant="dark" size="md" onClick={() => navigate("/shift")}>
            {t.shift.close}
          </Button>
        </section>
      ) : (
        <section className="flex flex-wrap items-center gap-4 rounded-2xl border-2 border-warning bg-warning-soft px-5 py-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-warning text-white">
            <TriangleAlert className="h-7 w-7" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-xl font-bold text-ink">{t.shift.noOpen}</div>
            <div className="text-sm text-ink-soft">{t.pos.noOpenShift}</div>
          </div>
          <Button variant="warning" size="md" onClick={() => navigate("/shift")}>
            {t.pos.openShiftNow}
          </Button>
        </section>
      )}

      {/* Дөрвөн үзүүлэлт */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatBox
          label={t.dashboard.todaySales}
          value={formatMoneyExact(current?.sales.gross_total ?? "0", false)}
          unit={t.units.mnt}
          size="lg"
          tone="action"
          icon={<Banknote className="h-6 w-6" />}
          hint={`${current?.sales.count ?? 0} ${t.common.rows}`}
        />
        <StatBox
          label={t.dashboard.todayLiters}
          value={formatLiters(current?.sales.fuel_liters ?? "0", 2)}
          size="lg"
          tone="success"
          icon={<Droplets className="h-6 w-6" />}
          hint={formatMNT(current?.sales.fuel_amount ?? "0")}
        />
        <StatBox
          label={t.dashboard.cashInDrawer}
          value={formatMoneyExact(current?.cash.expected_cash ?? "0", false)}
          unit={t.units.mnt}
          size="lg"
          tone="warning"
          icon={<Banknote className="h-6 w-6" />}
          hint={`${t.shift.openingCash}: ${formatMNT(current?.cash.opening_cash ?? "0")}`}
        />
        <StatBox
          label={`${t.tender.card} + ${t.tender.qr}`}
          value={formatMoneyExact(cashless, false)}
          unit={t.units.mnt}
          size="lg"
          tone="neutral"
          icon={<CreditCard className="h-6 w-6" />}
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {/* Савны түвшин */}
        <Card
          title={t.tanks.title}
          subtitle={lowTanks.length > 0 ? `${t.dashboard.lowTanks}: ${lowTanks.length}` : undefined}
          actions={
            <Button variant="ghost" size="md" icon={<Database />} onClick={() => navigate("/tanks")}>
              {t.common.details}
            </Button>
          }
        >
          {tanksLoading ? (
            <div className="flex justify-center py-8 text-ink-soft">
              <Spinner label={t.common.loading} />
            </div>
          ) : tanks.length === 0 ? (
            <EmptyState compact title={t.common.empty} />
          ) : (
            <ul className="flex flex-col gap-4">
              {tanks.map((tank) => (
                <li key={tank.id} className="flex flex-col gap-1.5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{ backgroundColor: tank.fuel.color_hex }}
                        aria-hidden="true"
                      />
                      <span className="truncate text-[15px] font-bold text-ink">{tank.name}</span>
                      <span className="truncate text-sm text-ink-soft">{tank.fuel.name_mn}</span>
                      {tank.is_low ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-danger-soft px-2 py-0.5 text-xs font-bold text-danger-dark">
                          <TriangleAlert className="h-3.5 w-3.5" />
                          {t.tanks.low}
                        </span>
                      ) : null}
                    </span>
                    <span className="num shrink-0 text-sm font-semibold text-ink">
                      {formatLiters(tank.current_l, 0)} / {formatLiters(tank.capacity_l, 0)} ·{" "}
                      {formatPct(tank.fill_pct)}
                    </span>
                  </div>
                  <ProgressBar value={fillPct(tank)} autoTone size="md" markerPct={minPct(tank)} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Насосны төлөв */}
        <Card
          title={t.pumps.title}
          subtitle={`${t.dashboard.activePumps}: ${
            pumps.filter((pump) => {
              const status = telemetry[pump.id]?.status ?? pump.status;
              return pumpVisual(status) === "active";
            }).length
          }`}
          actions={
            <Button variant="ghost" size="md" icon={<Fuel />} onClick={() => navigate("/pos")}>
              {t.pos.forecourt}
            </Button>
          }
        >
          {pumps.length === 0 ? (
            <EmptyState compact title={t.common.empty} />
          ) : (
            <ul className="flex flex-wrap gap-2.5">
              {pumps.map((pump) => {
                const live = telemetry[pump.id] ?? pump.live;
                const status = live?.status ?? pump.status;
                const visual = pumpVisual(status);
                const meta = statusMeta(PUMP_STATUS_META, status);
                const accent = VISUAL_COLOR[visual];
                return (
                  <li
                    key={pump.id}
                    className="flex min-h-16 min-w-40 flex-1 items-center gap-3 rounded-xl border-2 bg-white px-3 py-2"
                    style={{ borderColor: accent }}
                  >
                    <span
                      className="num flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-xl font-black text-white"
                      style={{ backgroundColor: accent }}
                    >
                      {pump.number}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-bold" style={{ color: accent }}>
                        {meta.label}
                      </span>
                      <span className="num block truncate text-xs text-ink-soft">
                        {visual === "active" || visual === "busy"
                          ? `${formatLiters(live?.liters ?? "0", 2)} · ${formatMNT(live?.amount ?? "0")}`
                          : pump.name}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

export default CashierDashboard;
