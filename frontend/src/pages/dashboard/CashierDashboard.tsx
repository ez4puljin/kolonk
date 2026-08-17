/**
 * Хяналтын самбар — салбар төвтэй харагдац.
 *
 * Түгээгчийн горимд борлуулалт зөвхөн өдрийн хаалтаар бүртгэгддэг тул
 * бодит явцыг ХОШУУНЫ МИЛЬ (тоолуурын заалт) дээр тулгуурлан харуулна:
 *   · салбар бүрийн нээлттэй ээлж — түгээгч, эхний бэлэн, милийн явц;
 *   · сүүлийн 7 хоногийн түлшний зарлага — өдөр бүр түлшээр өнгө ялган;
 *   · савны түвшин — салбараар бүлэглэсэн.
 */

import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Banknote, Database, Droplets, Fuel, Gauge, Package, TriangleAlert } from "lucide-react";

import { useBranches } from "../../api/queries/branches";
import { useBranchShifts, useFuelTrend } from "../../api/queries/dashboards";
import { useCurrentShift } from "../../api/queries/shifts";
import { useTanks } from "../../api/queries/tanks";
import type { FuelTrend, FuelTrendBranch, Tank } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { dToNumber } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, formatMoneyExact, formatPct } from "../../lib/format";

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

/** `2026-08-17` → `08/17` — баганын доорх богино шошго. */
function shortDay(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : iso;
}

// --------------------------------------------------------------------------
// Түлшээр өнгө ялгасан өдрийн багана — хошууны милээр
// --------------------------------------------------------------------------

/** Хамгийн өндөр баганын эзлэх хувь — дээрх үлдсэн зайд өдрийн литр бичигдэнэ. */
const BAR_MAX_PCT = 84;

function FuelTrendChart({ branch, fuels }: { branch: FuelTrendBranch; fuels: FuelTrend["fuels"] }) {
  const fuelById = useMemo(() => new Map(fuels.map((f) => [f.id, f])), [fuels]);
  const peak = useMemo(
    () => Math.max(...branch.rows.map((row) => dToNumber(row.liters)), 0),
    [branch.rows],
  );

  if (peak <= 0) {
    return <EmptyState compact title={t.dashboard.noMileData} hint={t.dashboard.noMileHint} />;
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Багана бүр 100% өндөртэй; хамгийн өндөр нь BAR_MAX_PCT — үлдсэн зайд утга бичигдэнэ. */}
      <div className="flex gap-1.5 sm:gap-2.5" style={{ height: 176 }}>
        {branch.rows.map((row) => {
          const dayLiters = dToNumber(row.liters);
          const barPct = peak > 0 && dayLiters > 0 ? Math.max((dayLiters / peak) * BAR_MAX_PCT, 3) : 0;
          return (
            <div key={row.date} className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
              <div className="relative flex w-full flex-1 items-end">
                {dayLiters > 0 ? (
                  <span
                    className="num absolute inset-x-0 text-center text-[11px] font-semibold text-ink-soft"
                    style={{ bottom: `calc(${barPct}% + 3px)` }}
                  >
                    {formatLiters(row.liters, 0).replace(" л", "")}
                  </span>
                ) : null}
                <div
                  className="flex w-full flex-col-reverse overflow-hidden rounded-t-lg bg-surface-alt"
                  style={{ height: `${barPct}%` }}
                  title={`${row.date}: ${formatLiters(row.liters)} · ${formatMNT(row.amount)}`}
                >
                  {row.by_fuel.map((slice) => {
                    const share = dayLiters > 0 ? (dToNumber(slice.liters) / dayLiters) * 100 : 0;
                    const fuel = fuelById.get(slice.fuel_id);
                    return (
                      <div
                        key={slice.fuel_id}
                        style={{
                          height: `${share}%`,
                          backgroundColor: fuel?.color_hex ?? "#94A3B8",
                        }}
                        title={`${fuel?.name_mn ?? ""}: ${formatLiters(slice.liters)}`}
                      />
                    );
                  })}
                </div>
              </div>
              <span className="num text-[11px] text-ink-faint">{shortDay(row.date)}</span>
            </div>
          );
        })}
      </div>

      {/* Долоо хоногийн задаргаа — түлш тус бүрээр */}
      <ul className="flex flex-wrap gap-x-4 gap-y-1.5 border-t border-line pt-2.5">
        {branch.by_fuel.map((item) => {
          const fuel = fuelById.get(item.fuel_id);
          return (
            <li key={item.fuel_id} className="flex items-center gap-1.5 text-sm">
              <span
                className="h-3 w-3 shrink-0 rounded-sm"
                style={{ backgroundColor: fuel?.color_hex ?? "#94A3B8" }}
                aria-hidden="true"
              />
              <span className="text-ink-soft">{fuel?.name_mn ?? ""}</span>
              <span className="num font-bold text-ink">{formatLiters(item.liters, 0)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------------------
export function CashierDashboard() {
  const navigate = useNavigate();

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const { data: tanksPage, isLoading: tanksLoading } = useTanks({ active_only: true });
  const branchesQuery = useBranches();

  const branchShifts = useBranchShifts();
  const trendQuery = useFuelTrend(7);

  const shift = current?.shift ?? null;
  const tanks = useMemo(() => tanksPage?.items ?? [], [tanksPage]);
  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  const lowTanks = tanks.filter((tank) => tank.is_low);
  const multiBranch = branches.length > 1;

  /** Сав → салбараар бүлэглэсэн (нэг салбартай бол ганц бүлэг). */
  const tankGroups = useMemo(() => {
    if (!multiBranch) return [{ id: "", name: "", tanks }];
    const map = new Map<string, { id: string; name: string; tanks: Tank[] }>();
    for (const tank of tanks) {
      const key = tank.branch_id ?? "";
      const hit = map.get(key);
      if (hit) hit.tanks.push(tank);
      else map.set(key, { id: key, name: tank.branch_name ?? t.branches.noBranch, tanks: [tank] });
    }
    const order = new Map(branches.map((branch, index) => [branch.id, index]));
    return [...map.values()].sort((a, b) => (order.get(a.id) ?? 999) - (order.get(b.id) ?? 999));
  }, [tanks, branches, multiBranch]);

  if (shiftLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  const trend = trendQuery.data;

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

      {/* Өөрийн ээлжийн үндсэн үзүүлэлт */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
      </div>

      {/* Салбар бүрийн түгээгчийн ээлж */}
      <Card
        title={t.dashboard.branchShifts}
        subtitle={t.dashboard.branchShiftsHint}
        actions={
          <Button variant="ghost" size="md" icon={<Gauge />} onClick={() => navigate("/shift")}>
            {t.nav.shift}
          </Button>
        }
      >
        {branchShifts.isLoading ? (
          <div className="flex justify-center py-8 text-ink-soft">
            <Spinner label={t.common.loading} />
          </div>
        ) : (branchShifts.data ?? []).length === 0 ? (
          <EmptyState compact title={t.common.empty} />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {(branchShifts.data ?? []).map((row) => (
              <section
                key={row.branch_id}
                className={[
                  "flex flex-col gap-2.5 rounded-xl border px-4 py-3",
                  row.shift ? "border-success/40 bg-success-soft/25" : "border-line bg-surface-alt",
                ].join(" ")}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-[15px] font-bold text-ink">{row.branch_name}</h3>
                  {row.shift ? (
                    <span className="num text-xs font-semibold text-success-dark">
                      {t.shift.number}
                      {row.shift.number} · {formatDateTime(row.shift.opened_at)}
                    </span>
                  ) : (
                    <span className="text-xs font-semibold text-ink-faint">{t.shift.noOpen}</span>
                  )}
                </div>

                {row.shift ? (
                  <>
                    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm">
                      <span className="font-semibold text-ink">{row.shift.attendant}</span>
                      <span className="num text-ink-soft">
                        {t.shift.openingCash}: {formatMNT(row.shift.opening_cash)}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between gap-3 border-t border-line pt-2">
                      <span className="text-sm text-ink-soft">{t.dashboard.mileProgress}</span>
                      <span className="num text-lg font-bold text-ink">
                        {formatLiters(row.liters, 1)}
                        <span className="ml-2 text-sm font-semibold text-ink-soft">
                          ≈ {formatMNT(row.amount)}
                        </span>
                      </span>
                    </div>

                    {row.fuels.length > 0 ? (
                      <ul className="flex flex-wrap gap-x-4 gap-y-1">
                        {row.fuels.map((fuel) => (
                          <li key={fuel.fuel_id} className="flex items-center gap-1.5 text-sm">
                            <span
                              className="h-2.5 w-2.5 shrink-0 rounded-full"
                              style={{ backgroundColor: fuel.color_hex }}
                              aria-hidden="true"
                            />
                            <span className="text-ink-soft">{fuel.fuel_name}</span>
                            <span className="num font-semibold text-ink">
                              {formatLiters(fuel.liters, 1)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-ink-soft">{t.pos.noOpenShift}</p>
                )}
              </section>
            ))}
          </div>
        )}
      </Card>

      {/* 7 хоногийн түлшний зарлага — салбар тус бүрээр */}
      <Card title={t.dashboard.weekTrend} subtitle={t.dashboard.weekTrendHint}>
        {trendQuery.isLoading ? (
          <div className="flex justify-center py-8 text-ink-soft">
            <Spinner label={t.common.loading} />
          </div>
        ) : !trend || trend.branches.length === 0 ? (
          <EmptyState compact title={t.common.empty} />
        ) : (
          <div className="flex flex-col gap-6">
            {trend.branches.map((branch) => (
              <section key={branch.branch_id} className="flex flex-col gap-2.5">
                <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
                  <h3 className="text-[15px] font-bold text-ink">{branch.branch_name}</h3>
                  <span className="num text-sm text-ink-soft">
                    {formatLiters(branch.total_liters, 0)} · ≈ {formatMNT(branch.total_amount)}
                  </span>
                </header>
                <FuelTrendChart branch={branch} fuels={trend.fuels} />
              </section>
            ))}
          </div>
        )}
      </Card>

      {/* Савны түвшин — салбараар */}
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
          <div className="flex flex-col gap-5">
            {tankGroups.map((group) => (
              <section key={group.id || "single"} className="flex flex-col gap-3">
                {multiBranch ? (
                  <h3 className="border-b border-line pb-1.5 text-sm font-bold tracking-wide text-ink-soft uppercase">
                    {group.name}
                  </h3>
                ) : null}
                <ul className="flex flex-col gap-4">
                  {group.tanks.map((tank) => (
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
              </section>
            ))}
          </div>
        )}
      </Card>

      {/* Өөрийн ээлж нээгээгүй үед сануулга */}
      {!shift ? (
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
      ) : null}
    </div>
  );
}

export default CashierDashboard;
