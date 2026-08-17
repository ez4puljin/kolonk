/**
 * Эзний хяналтын самбар (WP12) — гар утсанд эхэлж зохиосон.
 *
 * 375px: нэг багана · ≥768px: хоёр · ≥1280px: гурав.
 * Сервер: `GET /api/dashboards/owner`, `GET /api/reports/sales`, `GET /api/shifts`.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  BadgeDollarSign,
  ChevronRight,
  Coins,
  Droplets,
  Fuel,
  Gauge,
  Package,
  Scale,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import type { IsoDate, LitersStr, MoneyStr, Paged, ShiftSummary, UUID } from "../../api/types";
import { BarChart, type BarDatum } from "../../components/charts/BarChart";
import { DonutChart, type DonutSlice } from "../../components/charts/DonutChart";
import { PageHeader } from "../../components/layout/PageHeader";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { dSum, dToNumber, dIsNegative } from "../../lib/decimal";
import { daysAgoInput, formatDate, formatLiters, formatMNT, formatNumber, toDateInput, todayInput } from "../../lib/format";

// --------------------------------------------------------------------------
// Серверийн хэлбэр (app/schemas/report.py → OwnerDashboardOut)
// --------------------------------------------------------------------------

interface OwnerTotals {
  sales_total: MoneyStr;
  liters: LitersStr;
  sale_count: number;
  gross_profit: MoneyStr;
  /** Үйл ажиллагааны зардал ба түүнийг хассан цэвэр ашиг. */
  expense_total: MoneyStr;
  net_profit: MoneyStr;
}

interface OwnerMonthTotals {
  sales_total: MoneyStr;
  liters: LitersStr;
  gross_profit: MoneyStr;
  expense_total: MoneyStr;
  net_profit: MoneyStr;
}

interface TankLevel {
  tank_id: UUID;
  name: string;
  fuel_code: string | null;
  fuel_name: string | null;
  current_l: LitersStr;
  capacity_l: LitersStr;
  min_level_l: LitersStr;
  fill_pct: string;
  is_low: boolean;
  value: MoneyStr;
}

interface TenderShare {
  method: string;
  label_mn: string;
  count: number;
  amount: MoneyStr;
  pct: string;
}

interface TopProduct {
  product_id: UUID;
  sku: string;
  name: string;
  unit: string | null;
  qty: string;
  amount: MoneyStr;
  cogs: MoneyStr;
  margin: MoneyStr;
  margin_pct: string;
}


/** Салбар тус бүрийн товч үзүүлэлт. */
interface BranchRow {
  branch_id: UUID;
  name: string;
  today_total: MoneyStr;
  today_liters: LitersStr;
  today_sale_count: number;
  month_total: MoneyStr;
  month_liters: LitersStr;
  month_gross_profit: MoneyStr;
}

interface OwnerOverview {
  date: IsoDate;
  today: OwnerTotals;
  month: OwnerMonthTotals;
  year: { sales_total: MoneyStr };
  tanks: TankLevel[];
  branches: BranchRow[];
  tank_loss_mtd: { liters: LitersStr; value: MoneyStr };
  tender_breakdown_today: TenderShare[];
  top_products: TopProduct[];
  pending: { price_changes: number; refunds: number };
  ar: { open_total: MoneyStr; overdue_total: MoneyStr };
  ap: { open_total: MoneyStr };
}

interface SalesSummaryRow {
  period: string;
  period_start: IsoDate | null;
  sale_count: number;
  total: MoneyStr;
  vat: MoneyStr;
  fuel_total: MoneyStr;
  store_total: MoneyStr;
  liters: LitersStr;
  cogs: MoneyStr;
  gross_profit: MoneyStr;
}

interface SalesSummaryReport {
  granularity: string;
  granularity_name: string;
  date_from: IsoDate;
  date_to: IsoDate;
  rows: SalesSummaryRow[];
}

// --------------------------------------------------------------------------

function monthStartInput(): string {
  const now = new Date();
  return toDateInput(new Date(now.getFullYear(), now.getMonth(), 1));
}

/** "2026-08-06" → "08.06" — 30 хоногийн баганын шошго. */
function shortDay(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[1]}.${parts[2]}` : iso;
}

export function OwnerDashboard() {
  const navigate = useNavigate();
  const { can } = usePermission();

  const rangeFrom = daysAgoInput(29);
  const rangeTo = todayInput();
  const monthFrom = monthStartInput();

  // Бүх салбар (хоосон) эсвэл нэг салбарын хүрээнд харна.
  const [branchId, setBranchId] = useState("");
  const branchesQuery = useBranches();
  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );

  const overviewQuery = useQuery({
    queryKey: ["dashboards", "owner", branchId],
    queryFn: () =>
      api.get<OwnerOverview>("/api/dashboards/owner", {
        params: branchId ? { branch_id: branchId } : undefined,
      }),
    refetchInterval: 60_000,
  });

  const trendQuery = useQuery({
    queryKey: [
      "reports",
      "sales-summary",
      { granularity: "day", from: rangeFrom, to: rangeTo, branchId },
    ],
    queryFn: () =>
      api.get<SalesSummaryReport>("/api/reports/sales", {
        params: {
          granularity: "day",
          date_from: rangeFrom,
          date_to: rangeTo,
          ...(branchId ? { branch_id: branchId } : {}),
        },
      }),
    enabled: can("reports.view"),
    staleTime: 120_000,
  });

  // Кассын зөрүү — сонгосон салбарын хаагдсан ээлжүүдээр.
  const shiftsQuery = useQuery({
    queryKey: ["shifts", "list", { from: monthFrom, to: rangeTo, status: "closed", branchId }],
    queryFn: () =>
      api.get<Paged<ShiftSummary>>("/api/shifts", {
        params: {
          date_from: monthFrom,
          date_to: rangeTo,
          status: "closed",
          limit: 200,
          ...(branchId ? { branch_id: branchId } : {}),
        },
      }),
    enabled: can("shifts.view_all"),
    staleTime: 120_000,
  });

  const data = overviewQuery.data;

  const cashVariance = useMemo(
    () => dSum((shiftsQuery.data?.items ?? []).map((shift) => shift.cash_over_short ?? "0")),
    [shiftsQuery.data],
  );

  const trendBars: BarDatum[] = useMemo(
    () =>
      (trendQuery.data?.rows ?? []).map((row) => ({
        key: row.period,
        label: shortDay(row.period),
        value: row.total,
        display: formatMNT(row.total),
      })),
    [trendQuery.data],
  );

  const tenderSlices: DonutSlice[] = useMemo(
    () =>
      (data?.tender_breakdown_today ?? []).map((item) => ({
        key: item.method,
        label: item.label_mn,
        value: item.amount,
        display: formatMNT(item.amount),
        share: `${formatNumber(item.pct, 1)}${t.units.percent}`,
      })),
    [data],
  );

  const pendingCount = (data?.pending.price_changes ?? 0) + (data?.pending.refunds ?? 0);

  if (overviewQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.dashboard.ownerTitle} />
        <EmptyState title={t.errors.loadFailed} hint={t.common.retry} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.dashboard.ownerTitle}
        subtitle={`${formatDate(data.date)} · ${t.common.year}: ${formatMNT(data.year.sales_total)}`}
      />

      {/* Салбарын сонголт — олон салбартай үед */}
      {branches.length > 1 ? (
        <div className="flex flex-wrap gap-2">
          {[{ id: "", name: t.branches.allBranches }, ...branches].map((branch) => {
            const active = branchId === branch.id;
            return (
              <button
                key={branch.id || "all"}
                type="button"
                onClick={() => setBranchId(branch.id)}
                className={[
                  "flex h-12 items-center rounded-xl border px-4 text-[15px] font-semibold transition-colors",
                  active
                    ? "border-action bg-action text-white"
                    : "border-line-strong bg-white text-ink-soft hover:bg-surface-alt",
                ].join(" ")}
              >
                {branch.name}
              </button>
            );
          })}
        </div>
      ) : null}

      {/* KPI — сарын эхнээс өссөн дүнтэй харьцуулав */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatBox
          label={t.dashboard.todaySales}
          value={formatMNT(data.today.sales_total)}
          size="lg"
          tone="action"
          icon={<Coins className="h-6 w-6" />}
          delta={formatMNT(data.month.sales_total)}
          deltaTone="action"
          hint={t.common.month}
        />
        <StatBox
          label={t.dashboard.todayLiters}
          value={formatLiters(data.today.liters)}
          size="lg"
          tone="neutral"
          icon={<Droplets className="h-6 w-6" />}
          delta={formatLiters(data.month.liters)}
          hint={t.common.month}
        />
        <StatBox
          label={t.accounting.grossProfit}
          value={formatMNT(data.today.gross_profit)}
          size="lg"
          tone="success"
          icon={<TrendingUp className="h-6 w-6" />}
          delta={formatMNT(data.month.gross_profit)}
          deltaTone="success"
          hint={t.common.month}
        />
        <StatBox
          label={t.accounting.netProfit}
          value={formatMNT(data.today.net_profit)}
          size="lg"
          tone={dIsNegative(data.today.net_profit) ? "danger" : "success"}
          icon={<Wallet className="h-6 w-6" />}
          delta={formatMNT(data.month.net_profit)}
          deltaTone={dIsNegative(data.month.net_profit) ? "danger" : "success"}
          hint={`${t.common.month} · ${t.expenses.title}: ${formatMNT(data.month.expense_total)}`}
        />
        <StatBox
          label={t.shift.overShort}
          value={formatMNT(cashVariance)}
          size="lg"
          tone={dIsNegative(cashVariance) ? "danger" : "success"}
          icon={<Scale className="h-6 w-6" />}
          hint={can("shifts.view_all") ? `${t.common.month} · ${shiftsQuery.data?.items.length ?? 0} ${t.shift.title.toLowerCase()}` : t.auth.forbidden}
        />
      </div>

      {/* Хүлээгдэж буй зөвшөөрөл — хамгийн том хүрэх талбай */}
      <button
        type="button"
        onClick={() => navigate("/approvals")}
        className={[
          "flex min-h-[84px] w-full items-center gap-4 rounded-xl border px-5 py-4 text-left transition-colors",
          pendingCount > 0
            ? "border-warning/40 bg-warning-soft hover:bg-warning/20 active:bg-warning/25"
            : "border-line bg-white hover:bg-surface-alt active:bg-surface-sunken",
        ].join(" ")}
      >
        <span
          className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${
            pendingCount > 0 ? "bg-warning text-brand-900" : "bg-surface-sunken text-ink-faint"
          }`}
        >
          <AlertTriangle className="h-7 w-7" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-base font-bold text-ink">{t.dashboard.pendingApprovals}</span>
          <span className="block truncate text-sm text-ink-soft">
            {`${t.prices.title}: ${data.pending.price_changes} · ${t.refunds.title}: ${data.pending.refunds}`}
          </span>
        </span>
        <span
          className={`num flex h-12 min-w-12 shrink-0 items-center justify-center rounded-full px-3 text-2xl font-bold ${
            pendingCount > 0 ? "bg-danger text-white" : "bg-surface-sunken text-ink-faint"
          }`}
        >
          {pendingCount}
        </span>
        <ChevronRight className="h-6 w-6 shrink-0 text-ink-faint" aria-hidden="true" />
      </button>

      {/* Үндсэн сүлжээ */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {/* Савны түвшин */}
        <Card
          title={t.tanks.title}
          subtitle={t.tanks.fillPct}
          className="md:col-span-2 xl:col-span-1"
          actions={
            <button
              type="button"
              onClick={() => navigate("/tanks")}
              aria-label={t.tanks.title}
              className="flex h-12 w-12 items-center justify-center rounded-xl text-ink-soft hover:bg-surface-alt active:bg-surface-sunken"
            >
              <ArrowRight className="h-5 w-5" />
            </button>
          }
        >
          {data.tanks.length === 0 ? (
            <EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />
          ) : (
            <ul className="flex flex-col gap-4">
              {data.tanks.map((tank) => {
                const capacity = dToNumber(tank.capacity_l);
                const marker = capacity > 0 ? (dToNumber(tank.min_level_l) / capacity) * 100 : null;
                return (
                  <li key={tank.tank_id} className="flex flex-col gap-1">
                    <ProgressBar
                      size="lg"
                      autoTone
                      value={dToNumber(tank.fill_pct)}
                      markerPct={marker}
                      label={`${tank.name} · ${tank.fuel_name ?? tank.fuel_code ?? ""}`}
                      valueLabel={`${formatLiters(tank.current_l, 0)} / ${formatLiters(tank.capacity_l, 0)}`}
                    />
                    <div className="flex items-center justify-between gap-2 text-xs text-ink-soft">
                      <span className="num">{formatNumber(tank.fill_pct, 1)}{t.units.percent}</span>
                      {tank.is_low ? <StatusBadge size="sm" tone="danger" label={t.tanks.low} dot /> : null}
                      <span className="num">{formatMNT(tank.value)}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Өнөөдрийн төлбөрийн бүтэц */}
        <Card title={t.reports.byTender} subtitle={t.common.today}>
          <DonutChart
            data={tenderSlices}
            title={t.reports.byTender}
            centerLabel={t.common.total}
            centerValue={formatMNT(data.today.sales_total)}
            size={180}
          />
        </Card>

        {/* Авлага, өглөг */}
        <Card title={t.accounting.apar} subtitle={t.common.month}>
          <dl className="flex flex-col divide-y divide-line">
            <div className="flex min-h-12 items-center justify-between gap-3 py-2">
              <dt className="text-sm font-medium text-ink-soft">{t.dashboard.receivables}</dt>
              <dd className="num text-xl font-bold text-ink">{formatMNT(data.ar.open_total)}</dd>
            </div>
            <div className="flex min-h-12 items-center justify-between gap-3 py-2">
              <dt className="text-sm font-medium text-ink-soft">Хугацаа хэтэрсэн авлага</dt>
              <dd
                className={`num text-xl font-bold ${
                  dToNumber(data.ar.overdue_total) > 0 ? "text-danger-dark" : "text-ink"
                }`}
              >
                {formatMNT(data.ar.overdue_total)}
              </dd>
            </div>
            <div className="flex min-h-12 items-center justify-between gap-3 py-2">
              <dt className="text-sm font-medium text-ink-soft">{t.dashboard.payables}</dt>
              <dd className="num text-xl font-bold text-ink">{formatMNT(data.ap.open_total)}</dd>
            </div>
            <div className="flex min-h-12 items-center justify-between gap-3 py-2">
              <dt className="text-sm font-medium text-ink-soft">{t.tanks.varianceMovement}</dt>
              <dd className="num text-right text-base font-semibold text-ink">
                {formatLiters(data.tank_loss_mtd.liters)}
                <span className="block text-xs font-normal text-ink-soft">
                  {formatMNT(data.tank_loss_mtd.value)}
                </span>
              </dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={() => navigate("/accounting/apar")}
            className="touch-target mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-line-strong bg-white text-[15px] font-semibold text-ink-soft active:bg-surface-sunken"
          >
            {t.common.details}
            <ChevronRight className="h-5 w-5" />
          </button>
        </Card>

        {/* Сүүлийн 30 хоногийн борлуулалт */}
        <Card
          title={t.dashboard.salesTrend}
          subtitle={`${formatDate(rangeFrom)} — ${formatDate(rangeTo)}`}
          className="md:col-span-2 xl:col-span-3"
        >
          {trendQuery.isLoading ? (
            <div className="flex justify-center py-10 text-ink-soft">
              <Spinner label={t.common.loading} />
            </div>
          ) : (
            <BarChart
              data={trendBars}
              title={t.dashboard.salesTrend}
              orientation="vertical"
              height={220}
              maxLabels={6}
            />
          )}
        </Card>

        {/* Салбарын харьцуулалт — зөвхөн "бүх салбар" горимд */}
        {data.branches.length > 1 ? (
          <Card title={t.branches.title} subtitle={t.common.today} className="xl:col-span-1">
            <ol className="flex flex-col divide-y divide-line">
              {data.branches.map((branch) => (
                <li key={branch.branch_id} className="flex min-h-14 items-center gap-3 py-2">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] font-semibold text-ink">
                      {branch.name}
                    </span>
                    <span className="num block truncate text-xs text-ink-soft">
                      {`${formatLiters(branch.today_liters)} · ${branch.today_sale_count} ${t.common.rows}`}
                    </span>
                  </span>
                  <span className="num shrink-0 text-right">
                    <span className="block font-bold text-ink">{formatMNT(branch.today_total)}</span>
                    <span className="block text-xs text-ink-soft">
                      {t.common.month}: {formatMNT(branch.month_total)}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </Card>
        ) : null}

        {/* Шилдэг бараа */}
        <Card title="Шилдэг 5 бараа" subtitle={t.common.month} className="xl:col-span-1">
          {data.top_products.length === 0 ? (
            <EmptyState compact title={t.reports.noData} hint="" />
          ) : (
            <ol className="flex flex-col divide-y divide-line">
              {data.top_products.map((product, index) => (
                <li key={product.product_id} className="flex min-h-14 items-center gap-3 py-2">
                  <span className="num flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-sm font-bold text-ink-soft">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] font-semibold text-ink">{product.name}</span>
                    <span className="num block truncate text-xs text-ink-soft">
                      {`${product.sku} · ${formatNumber(product.qty, 0)} ${product.unit ?? t.units.piece}`}
                    </span>
                  </span>
                  <span className="num shrink-0 text-right">
                    <span className="block font-bold text-ink">{formatMNT(product.amount)}</span>
                    <span className="block text-xs text-success-dark">{formatMNT(product.margin)}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Card>

        {/* Богино холбоос */}
        <Card title={t.nav.reports} className="xl:col-span-1">
          <div className="grid grid-cols-1 gap-3">
            {[
              { to: "/reports", label: t.reports.sales, icon: <Gauge className="h-5 w-5" /> },
              { to: "/reports/financial", label: t.reports.financial, icon: <Scale className="h-5 w-5" /> },
              { to: "/accounting/journal", label: t.accounting.generalJournal, icon: <BadgeDollarSign className="h-5 w-5" /> },
              { to: "/tanks", label: t.tanks.title, icon: <Fuel className="h-5 w-5" /> },
              { to: "/inventory", label: t.inventory.title, icon: <Package className="h-5 w-5" /> },
            ].map((link) => (
              <button
                key={link.to}
                type="button"
                onClick={() => navigate(link.to)}
                className="touch-target-lg flex items-center gap-3 rounded-xl border border-line-strong bg-white px-4 text-left text-[15px] font-semibold text-ink transition-colors hover:bg-surface-alt active:bg-surface-sunken"
              >
                <span className="text-ink-soft">{link.icon}</span>
                <span className="min-w-0 flex-1 truncate">{link.label}</span>
                <ChevronRight className="h-5 w-5 shrink-0 text-ink-faint" />
              </button>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default OwnerDashboard;
