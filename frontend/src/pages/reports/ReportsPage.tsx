/**
 * Тайлангийн дэлгэц (WP12).
 *
 * Сервер: `/api/reports/sales`, `/api/reports/sales/detail`, `/api/reports/fuel`,
 * `/api/reports/tender`, `/api/reports/tank-loss` ба `.xlsx` экспортууд.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, X } from "lucide-react";

import { api, errorMessage } from "../../api/client";
import type { IsoDate, IsoDateTime, LitersStr, MoneyStr, UUID } from "../../api/types";
import { BarChart, type BarDatum } from "../../components/charts/BarChart";
import { DonutChart, type DonutSlice } from "../../components/charts/DonutChart";
import { TrendLine } from "../../components/charts/TrendLine";
import { compactNumber } from "../../components/charts/chartBase";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, rangeFor, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatBox } from "../../components/ui/StatBox";
import { TabBar, type TabItem } from "../../components/ui/TabBar";
import { t } from "../../i18n/mn";
import { useUiStore } from "../../stores/ui";
import { formatDate, formatLiters, formatMNT, formatNumber, formatTime, toDateInput } from "../../lib/format";

// --------------------------------------------------------------------------
// Серверийн хэлбэр (app/schemas/report.py)
// --------------------------------------------------------------------------

type Granularity = "day" | "month" | "year";

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

interface SalesSummaryTotals {
  sale_count: number;
  total: MoneyStr;
  vat: MoneyStr;
  fuel_total: MoneyStr;
  store_total: MoneyStr;
  liters: LitersStr;
  cogs: MoneyStr;
  gross_profit: MoneyStr;
  margin_pct: string;
  avg_check: MoneyStr;
}

interface SalesSummaryReport {
  granularity: string;
  granularity_name: string;
  date_from: IsoDate;
  date_to: IsoDate;
  rows: SalesSummaryRow[];
  totals: SalesSummaryTotals;
}

interface TenderShareRow {
  method: string;
  label_mn: string;
  count: number;
  amount: MoneyStr;
  pct: string;
}

interface SalePaymentRow {
  method: string;
  method_name: string;
  amount: MoneyStr;
}

interface SaleDetailRow {
  id: UUID;
  number: number;
  completed_at: IsoDateTime | null;
  sale_type: string;
  sale_type_name: string;
  status: string;
  status_name: string;
  cashier_id: UUID;
  cashier_name: string | null;
  customer_id: UUID | null;
  customer_name: string | null;
  liters: LitersStr;
  subtotal: MoneyStr;
  vat: MoneyStr;
  total: MoneyStr;
  cogs: MoneyStr;
  gross_profit: MoneyStr;
  payments: SalePaymentRow[];
}

interface SalesDetailReport {
  date: IsoDate;
  items: SaleDetailRow[];
  totals: {
    sale_count: number;
    total: MoneyStr;
    vat: MoneyStr;
    subtotal: MoneyStr;
    cogs: MoneyStr;
    liters: LitersStr;
    gross_profit: MoneyStr;
  };
  by_tender: TenderShareRow[];
}

interface FuelGradeRow {
  fuel_id: UUID;
  code: string;
  name: string;
  liters: LitersStr;
  revenue: MoneyStr;
  revenue_net: MoneyStr;
  cogs: MoneyStr;
  margin: MoneyStr;
  margin_pct: string;
  avg_price: MoneyStr;
}

interface FuelPumpRow {
  pump_id: UUID;
  pump_number: number;
  pump_name: string;
  nozzle_number: number | null;
  liters: LitersStr;
  amount: MoneyStr;
}

interface FuelReportData {
  date_from: IsoDate;
  date_to: IsoDate;
  grades: FuelGradeRow[];
  grade_totals: {
    liters: LitersStr;
    revenue: MoneyStr;
    revenue_net: MoneyStr;
    cogs: MoneyStr;
    margin: MoneyStr;
    margin_pct: string;
  };
  pumps: FuelPumpRow[];
  pump_totals: { liters: LitersStr; amount: MoneyStr };
}

interface TenderBreakdown {
  date_from: IsoDate;
  date_to: IsoDate;
  items: TenderShareRow[];
  total: MoneyStr;
  total_count: number;
}

interface TankLossRow {
  tank_id: UUID;
  tank_name: string;
  fuel_code: string | null;
  fuel_name: string | null;
  liters: LitersStr;
  value: MoneyStr;
  loss_liters: LitersStr;
  gain_liters: LitersStr;
  movement_count: number;
}

interface TankLossReport {
  date_from: IsoDate;
  date_to: IsoDate;
  items: TankLossRow[];
  totals: {
    liters: LitersStr;
    value: MoneyStr;
    loss_liters: LitersStr;
    gain_liters: LitersStr;
    movement_count: number;
  };
}

// --------------------------------------------------------------------------
// Туслах
// --------------------------------------------------------------------------

type ReportTab = "sales" | "fuel" | "tender" | "tankloss";

const TOTALS_KEY = "__totals__";

const GRANULARITY_TABS: readonly TabItem<Granularity>[] = [
  { value: "day", label: "Өдөр" },
  { value: "month", label: t.common.month },
  { value: "year", label: t.common.year },
];

const TABS: readonly TabItem<ReportTab>[] = [
  { value: "sales", label: t.reports.sales },
  { value: "fuel", label: t.reports.fuel },
  { value: "tender", label: t.reports.byTender },
  { value: "tankloss", label: "Савны хорогдол" },
];

/** Хугацааны шошгыг богиносгоно: "2026-08-06" → "08.06". */
function periodLabel(granularity: Granularity, period: string): string {
  if (granularity === "day") {
    const parts = period.split("-");
    return parts.length === 3 ? `${parts[1]}.${parts[2]}` : period;
  }
  return period;
}

function clampDate(value: string, min: string, max: string): string {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function monthBounds(start: string): DateRange {
  const parsed = new Date(`${start}T00:00:00`);
  return {
    from: toDateInput(new Date(parsed.getFullYear(), parsed.getMonth(), 1)),
    to: toDateInput(new Date(parsed.getFullYear(), parsed.getMonth() + 1, 0)),
  };
}

function yearBounds(start: string): DateRange {
  const parsed = new Date(`${start}T00:00:00`);
  return {
    from: toDateInput(new Date(parsed.getFullYear(), 0, 1)),
    to: toDateInput(new Date(parsed.getFullYear(), 11, 31)),
  };
}

interface Drill {
  kind: "detail" | "summary";
  label: string;
  /** `detail` үед — тухайн өдөр. */
  date?: string;
  /** `summary` үед — дэд мужийн хязгаар ба нарийвчлал. */
  from?: string;
  to?: string;
  granularity?: Granularity;
}

/** Нийлбэр мөрийг хүснэгтэд синтетик мөрөөр нэмнэ (DataTable-д tfoot байхгүй). */
function withTotalsRow(rows: readonly SalesSummaryRow[], totals: SalesSummaryTotals): SalesSummaryRow[] {
  if (rows.length === 0) return [];
  return [
    ...rows,
    {
      period: TOTALS_KEY,
      period_start: null,
      sale_count: totals.sale_count,
      total: totals.total,
      vat: totals.vat,
      fuel_total: totals.fuel_total,
      store_total: totals.store_total,
      liters: totals.liters,
      cogs: totals.cogs,
      gross_profit: totals.gross_profit,
    },
  ];
}

// --------------------------------------------------------------------------

export function ReportsPage() {
  const toastError = useUiStore((state) => state.toastError);

  const [tab, setTab] = useState<ReportTab>("sales");
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [range, setRange] = useState<DateRange>(() => rangeFor("month"));
  const [drill, setDrill] = useState<Drill | null>(null);
  const [downloading, setDownloading] = useState(false);

  const params = { date_from: range.from, date_to: range.to };

  const salesQuery = useQuery({
    queryKey: ["reports", "sales-summary", { granularity, ...params }],
    queryFn: () =>
      api.get<SalesSummaryReport>("/api/reports/sales", { params: { granularity, ...params } }),
    enabled: tab === "sales" && Boolean(range.from && range.to),
  });

  const fuelQuery = useQuery({
    queryKey: ["reports", "fuel", params],
    queryFn: () => api.get<FuelReportData>("/api/reports/fuel", { params }),
    enabled: tab === "fuel" && Boolean(range.from && range.to),
  });

  const tenderQuery = useQuery({
    queryKey: ["reports", "tender", params],
    queryFn: () => api.get<TenderBreakdown>("/api/reports/tender", { params }),
    enabled: tab === "tender" && Boolean(range.from && range.to),
  });

  const tankLossQuery = useQuery({
    queryKey: ["reports", "tank-loss", params],
    queryFn: () => api.get<TankLossReport>("/api/reports/tank-loss", { params }),
    enabled: tab === "tankloss" && Boolean(range.from && range.to),
  });

  const detailQuery = useQuery({
    queryKey: ["reports", "sales-detail", drill?.date ?? ""],
    queryFn: () =>
      api.get<SalesDetailReport>("/api/reports/sales/detail", { params: { date: drill?.date } }),
    enabled: drill?.kind === "detail" && Boolean(drill.date),
  });

  const subSummaryQuery = useQuery({
    queryKey: [
      "reports",
      "sales-summary",
      { granularity: drill?.granularity ?? "day", date_from: drill?.from ?? "", date_to: drill?.to ?? "" },
    ],
    queryFn: () =>
      api.get<SalesSummaryReport>("/api/reports/sales", {
        params: { granularity: drill?.granularity, date_from: drill?.from, date_to: drill?.to },
      }),
    enabled: drill?.kind === "summary" && Boolean(drill.from && drill.to),
  });

  // ---- Excel ----
  const download = (path: string, query: Record<string, string>, filename: string): void => {
    setDownloading(true);
    api
      .download(path, query, filename)
      .catch((error: unknown) => toastError(errorMessage(error)))
      .finally(() => setDownloading(false));
  };

  const exportCurrent = (): void => {
    if (tab === "fuel" || tab === "tankloss") {
      // Савны хорогдолд тусдаа .xlsx байхгүй — түлшний тайлангийн файлыг татна.
      download("/api/reports/fuel.xlsx", params, `Түлш_${range.from}_${range.to}.xlsx`);
      return;
    }
    download(
      "/api/reports/sales.xlsx",
      { granularity: tab === "sales" ? granularity : "day", ...params },
      `Борлуулалт_${range.from}_${range.to}.xlsx`,
    );
  };

  // ---- Мөр дээр дарахад задлах ----
  const openDrill = (row: SalesSummaryRow, level: Granularity): void => {
    if (row.period === TOTALS_KEY) return;
    const start = row.period_start ?? row.period;

    if (level === "day") {
      setDrill({ kind: "detail", label: row.period, date: start });
      return;
    }
    if (level === "month") {
      const bounds = monthBounds(start);
      setDrill({
        kind: "summary",
        label: row.period,
        granularity: "day",
        from: clampDate(bounds.from, range.from, range.to),
        to: clampDate(bounds.to, range.from, range.to),
      });
      return;
    }
    const bounds = yearBounds(start);
    setDrill({
      kind: "summary",
      label: row.period,
      granularity: "month",
      from: clampDate(bounds.from, range.from, range.to),
      to: clampDate(bounds.to, range.from, range.to),
    });
  };

  // ---- Багана ----
  const summaryColumns = (level: Granularity): Column<SalesSummaryRow>[] => [
    {
      key: "period",
      header: t.common.period,
      primary: true,
      render: (row) => (
        <span className={row.period === TOTALS_KEY ? "font-bold" : "font-semibold"}>
          {row.period === TOTALS_KEY ? t.common.total : row.period}
        </span>
      ),
    },
    {
      key: "count",
      header: t.common.qty,
      align: "right",
      numeric: true,
      render: (row) => formatNumber(row.sale_count, 0),
    },
    {
      key: "total",
      header: t.sales.title,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-semibold">{formatMNT(row.total)}</span>,
    },
    {
      key: "vat",
      header: t.common.vat,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.vat),
    },
    {
      key: "fuel",
      header: t.sales.fuel,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.fuel_total),
    },
    {
      key: "store",
      header: t.products.product,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.store_total),
    },
    {
      key: "liters",
      header: t.pos.liters,
      align: "right",
      numeric: true,
      render: (row) => formatLiters(row.liters),
    },
    {
      key: "cogs",
      header: t.common.cost,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.cogs),
    },
    {
      key: "margin",
      header: t.accounting.grossProfit,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-semibold text-success-dark">{formatMNT(row.gross_profit)}</span>,
    },
    {
      key: "drill",
      header: "",
      align: "right",
      width: "1%",
      hideOnMobile: true,
      render: (row) =>
        row.period === TOTALS_KEY ? null : (
          <span className="text-xs font-semibold text-action-dark">
            {level === "day" ? t.common.details : t.common.more}
          </span>
        ),
    },
  ];

  const detailColumns: Column<SaleDetailRow>[] = [
    {
      key: "number",
      header: t.sales.saleNo,
      primary: true,
      render: (row) => <span className="num font-bold">{`№${row.number}`}</span>,
    },
    {
      key: "time",
      header: t.common.time,
      numeric: true,
      render: (row) => formatTime(row.completed_at),
    },
    { key: "cashier", header: t.sales.cashier, render: (row) => row.cashier_name ?? "—" },
    { key: "type", header: t.sales.saleType, hideOnMobile: true, render: (row) => row.sale_type_name },
    {
      key: "liters",
      header: t.pos.liters,
      align: "right",
      numeric: true,
      render: (row) => formatLiters(row.liters),
    },
    {
      key: "payments",
      header: t.sales.payments,
      hideOnMobile: true,
      render: (row) => row.payments.map((payment) => payment.method_name).join(", ") || "—",
    },
    {
      key: "total",
      header: t.common.total,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.total)}</span>,
    },
    {
      key: "profit",
      header: t.accounting.grossProfit,
      align: "right",
      numeric: true,
      render: (row) => <span className="text-success-dark">{formatMNT(row.gross_profit)}</span>,
    },
  ];

  // ---- График ----
  const trendLabels = useMemo(
    () => (salesQuery.data?.rows ?? []).map((row) => periodLabel(granularity, row.period)),
    [salesQuery.data, granularity],
  );

  const gradeBars: BarDatum[] = useMemo(
    () =>
      (fuelQuery.data?.grades ?? []).map((grade) => ({
        key: grade.fuel_id,
        label: grade.name,
        value: grade.revenue,
        display: formatMNT(grade.revenue),
      })),
    [fuelQuery.data],
  );

  const tenderSlices: DonutSlice[] = useMemo(
    () =>
      (tenderQuery.data?.items ?? []).map((item) => ({
        key: item.method,
        label: item.label_mn,
        value: item.amount,
        display: formatMNT(item.amount),
        share: `${formatNumber(item.pct, 1)}${t.units.percent}`,
      })),
    [tenderQuery.data],
  );

  const summary = salesQuery.data;

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.reports.title}
        subtitle={`${formatDate(range.from)} — ${formatDate(range.to)}`}
        actions={
          <Button
            variant="secondary"
            size="md"
            icon={<Download className="h-5 w-5" />}
            loading={downloading}
            onClick={exportCurrent}
          >
            {t.common.exportExcel}
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          <TabBar
            variant="underline"
            value={tab}
            onChange={(next) => {
              setTab(next);
              setDrill(null);
            }}
            items={TABS}
          />
          <DateRangePicker value={range} onChange={(next) => { setRange(next); setDrill(null); }} />
        </div>
      </PageHeader>

      {/* ---------------- Борлуулалт ---------------- */}
      {tab === "sales" ? (
        <div className="flex flex-col gap-4">
          <TabBar
            value={granularity}
            onChange={(next) => {
              setGranularity(next);
              setDrill(null);
            }}
            items={GRANULARITY_TABS}
            className="max-w-md"
          />

          {summary ? (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <StatBox label={t.sales.title} value={formatMNT(summary.totals.total)} tone="action" />
              <StatBox label={t.accounting.grossProfit} value={formatMNT(summary.totals.gross_profit)} tone="success" />
              <StatBox label={t.reports.litersSold} value={formatLiters(summary.totals.liters)} />
              <StatBox label={t.reports.avgTicket} value={formatMNT(summary.totals.avg_check)} />
            </div>
          ) : null}

          <Card title={t.dashboard.salesTrend} subtitle={summary?.granularity_name}>
            <TrendLine
              labels={trendLabels}
              title={t.dashboard.salesTrend}
              formatTick={(value) => `${compactNumber(value)}${t.units.mnt}`}
              series={[
                {
                  key: "total",
                  name: t.sales.title,
                  values: (summary?.rows ?? []).map((row) => row.total),
                  total: summary ? formatMNT(summary.totals.total) : undefined,
                },
                {
                  key: "margin",
                  name: t.accounting.grossProfit,
                  values: (summary?.rows ?? []).map((row) => row.gross_profit),
                  total: summary ? formatMNT(summary.totals.gross_profit) : undefined,
                },
              ]}
              height={240}
            />
          </Card>

          <Card title={t.reports.sales} flush>
            <DataTable
              columns={summaryColumns(granularity)}
              rows={withTotalsRow(summary?.rows ?? [], summary?.totals ?? emptyTotals())}
              rowKey={(row) => row.period}
              loading={salesQuery.isLoading}
              emptyTitle={t.reports.noData}
              onRowClick={(row) => openDrill(row, granularity)}
              rowClassName={(row) =>
                row.period === TOTALS_KEY
                  ? "bg-surface-alt font-bold"
                  : drill && drill.label === row.period
                    ? "bg-action-soft"
                    : ""
              }
            />
          </Card>

          {drill ? (
            <Card
              title={drill.label}
              subtitle={drill.kind === "detail" ? t.sales.title : t.common.period}
              flush
              actions={
                <button
                  type="button"
                  onClick={() => setDrill(null)}
                  aria-label={t.common.close}
                  className="flex h-12 w-12 items-center justify-center rounded-xl text-ink-soft hover:bg-surface-alt active:bg-surface-sunken"
                >
                  <X className="h-5 w-5" />
                </button>
              }
            >
              {drill.kind === "detail" ? (
                <DataTable
                  columns={detailColumns}
                  rows={detailQuery.data?.items ?? []}
                  rowKey={(row) => row.id}
                  loading={detailQuery.isLoading}
                  emptyTitle={t.sales.noSales}
                  footer={
                    detailQuery.data ? (
                      <div className="num flex flex-wrap items-center justify-between gap-3 text-sm font-semibold text-ink">
                        <span>{`${t.common.qty}: ${formatNumber(detailQuery.data.totals.sale_count, 0)}`}</span>
                        <span>{`${t.pos.liters}: ${formatLiters(detailQuery.data.totals.liters)}`}</span>
                        <span>{`${t.common.vat}: ${formatMNT(detailQuery.data.totals.vat)}`}</span>
                        <span>{`${t.common.total}: ${formatMNT(detailQuery.data.totals.total)}`}</span>
                      </div>
                    ) : null
                  }
                />
              ) : (
                <DataTable
                  columns={summaryColumns(drill.granularity ?? "day")}
                  rows={withTotalsRow(subSummaryQuery.data?.rows ?? [], subSummaryQuery.data?.totals ?? emptyTotals())}
                  rowKey={(row) => `${drill.label}-${row.period}`}
                  loading={subSummaryQuery.isLoading}
                  emptyTitle={t.reports.noData}
                  onRowClick={(row) => openDrill(row, drill.granularity ?? "day")}
                  rowClassName={(row) => (row.period === TOTALS_KEY ? "bg-surface-alt font-bold" : "")}
                />
              )}
            </Card>
          ) : null}
        </div>
      ) : null}

      {/* ---------------- Түлшний тайлан ---------------- */}
      {tab === "fuel" ? (
        <div className="flex flex-col gap-4">
          {fuelQuery.data ? (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <StatBox label={t.reports.litersSold} value={formatLiters(fuelQuery.data.grade_totals.liters)} />
              <StatBox label={t.reports.revenue} value={formatMNT(fuelQuery.data.grade_totals.revenue)} tone="action" />
              <StatBox label={t.common.cost} value={formatMNT(fuelQuery.data.grade_totals.cogs)} />
              <StatBox
                label={t.reports.margin}
                value={formatMNT(fuelQuery.data.grade_totals.margin)}
                tone="success"
                hint={`${formatNumber(fuelQuery.data.grade_totals.margin_pct, 1)}${t.units.percent}`}
              />
            </div>
          ) : null}

          <Card title={t.reports.revenue} subtitle={t.reports.byFuel}>
            <BarChart data={gradeBars} title={t.reports.byFuel} orientation="horizontal" />
          </Card>

          <Card title={t.reports.byFuel} flush>
            <DataTable
              columns={fuelGradeColumns}
              rows={fuelQuery.data?.grades ?? []}
              rowKey={(row) => row.fuel_id}
              loading={fuelQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>

          <Card title={t.pumps.title} flush>
            <DataTable
              columns={fuelPumpColumns}
              rows={fuelQuery.data?.pumps ?? []}
              rowKey={(row) => `${row.pump_id}-${row.nozzle_number ?? 0}`}
              loading={fuelQuery.isLoading}
              emptyTitle={t.reports.noData}
              footer={
                fuelQuery.data ? (
                  <div className="num flex flex-wrap items-center justify-between gap-3 text-sm font-semibold text-ink">
                    <span>{`${t.pos.liters}: ${formatLiters(fuelQuery.data.pump_totals.liters)}`}</span>
                    <span>{`${t.common.total}: ${formatMNT(fuelQuery.data.pump_totals.amount)}`}</span>
                  </div>
                ) : null
              }
            />
          </Card>
        </div>
      ) : null}

      {/* ---------------- Төлбөрийн хэлбэр ---------------- */}
      {tab === "tender" ? (
        <div className="flex flex-col gap-4">
          <Card title={t.reports.byTender}>
            <DonutChart
              data={tenderSlices}
              title={t.reports.byTender}
              centerLabel={t.common.total}
              centerValue={formatMNT(tenderQuery.data?.total ?? "0")}
              size={200}
            />
          </Card>

          <Card title={t.tender.title} flush>
            <DataTable
              columns={tenderColumns}
              rows={tenderQuery.data?.items ?? []}
              rowKey={(row) => row.method}
              loading={tenderQuery.isLoading}
              emptyTitle={t.reports.noData}
              footer={
                tenderQuery.data ? (
                  <div className="num flex flex-wrap items-center justify-between gap-3 text-sm font-semibold text-ink">
                    <span>{`${t.common.qty}: ${formatNumber(tenderQuery.data.total_count, 0)}`}</span>
                    <span>{`${t.common.total}: ${formatMNT(tenderQuery.data.total)}`}</span>
                  </div>
                ) : null
              }
            />
          </Card>
        </div>
      ) : null}

      {/* ---------------- Савны хорогдол ---------------- */}
      {tab === "tankloss" ? (
        <div className="flex flex-col gap-4">
          {tankLossQuery.data ? (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <StatBox
                label={t.shift.variance}
                value={formatLiters(tankLossQuery.data.totals.liters)}
                tone={tankLossQuery.data.totals.liters.startsWith("-") ? "danger" : "success"}
              />
              <StatBox label={t.shift.varianceValue} value={formatMNT(tankLossQuery.data.totals.value)} />
              <StatBox label={t.shift.short} value={formatLiters(tankLossQuery.data.totals.loss_liters)} tone="danger" />
              <StatBox label={t.shift.over} value={formatLiters(tankLossQuery.data.totals.gain_liters)} tone="success" />
            </div>
          ) : null}

          <Card title="Савны хорогдол" flush>
            <DataTable
              columns={tankLossColumns}
              rows={tankLossQuery.data?.items ?? []}
              rowKey={(row) => row.tank_id}
              loading={tankLossQuery.isLoading}
              empty={<EmptyState title={t.reports.noData} hint={t.tanks.adjustHint} />}
            />
          </Card>
        </div>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Тогтмол багана
// --------------------------------------------------------------------------

function emptyTotals(): SalesSummaryTotals {
  return {
    sale_count: 0,
    total: "0",
    vat: "0",
    fuel_total: "0",
    store_total: "0",
    liters: "0",
    cogs: "0",
    gross_profit: "0",
    margin_pct: "0",
    avg_check: "0",
  };
}

const fuelGradeColumns: Column<FuelGradeRow>[] = [
  {
    key: "name",
    header: t.tanks.fuelType,
    primary: true,
    render: (row) => <span className="font-semibold">{`${row.code} · ${row.name}`}</span>,
  },
  {
    key: "liters",
    header: t.pos.liters,
    align: "right",
    numeric: true,
    render: (row) => formatLiters(row.liters),
  },
  {
    key: "avg",
    header: t.common.unitPrice,
    align: "right",
    numeric: true,
    hideOnMobile: true,
    render: (row) => formatMNT(row.avg_price),
  },
  {
    key: "revenue",
    header: t.reports.revenue,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.revenue)}</span>,
  },
  {
    key: "net",
    header: t.common.net,
    align: "right",
    numeric: true,
    hideOnMobile: true,
    render: (row) => formatMNT(row.revenue_net),
  },
  {
    key: "cogs",
    header: t.common.cost,
    align: "right",
    numeric: true,
    render: (row) => formatMNT(row.cogs),
  },
  {
    key: "margin",
    header: t.reports.margin,
    align: "right",
    numeric: true,
    render: (row) => (
      <span className="font-semibold text-success-dark">
        {formatMNT(row.margin)}
        <span className="ml-1 text-xs font-normal text-ink-soft">
          {formatNumber(row.margin_pct, 1)}
          {t.units.percent}
        </span>
      </span>
    ),
  },
];

const fuelPumpColumns: Column<FuelPumpRow>[] = [
  {
    key: "pump",
    header: t.pumps.pump,
    primary: true,
    render: (row) => (
      <span className="font-semibold">
        {`${t.pumps.pumpNo}${row.pump_number} · ${row.pump_name}`}
      </span>
    ),
  },
  {
    key: "nozzle",
    header: t.pumps.nozzleNo,
    align: "right",
    numeric: true,
    render: (row) => (row.nozzle_number === null ? "—" : formatNumber(row.nozzle_number, 0)),
  },
  {
    key: "liters",
    header: t.pos.liters,
    align: "right",
    numeric: true,
    render: (row) => formatLiters(row.liters),
  },
  {
    key: "amount",
    header: t.common.amount,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.amount)}</span>,
  },
];

const tenderColumns: Column<TenderShareRow>[] = [
  { key: "method", header: t.tender.title, primary: true, render: (row) => row.label_mn },
  {
    key: "count",
    header: t.common.qty,
    align: "right",
    numeric: true,
    render: (row) => formatNumber(row.count, 0),
  },
  {
    key: "amount",
    header: t.common.amount,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatMNT(row.amount)}</span>,
  },
  {
    key: "pct",
    header: t.units.percent,
    align: "right",
    numeric: true,
    render: (row) => `${formatNumber(row.pct, 1)}${t.units.percent}`,
  },
];

const tankLossColumns: Column<TankLossRow>[] = [
  {
    key: "tank",
    header: t.tanks.tank,
    primary: true,
    render: (row) => (
      <span className="font-semibold">{`${row.tank_name} · ${row.fuel_name ?? row.fuel_code ?? ""}`}</span>
    ),
  },
  {
    key: "loss",
    header: t.shift.short,
    align: "right",
    numeric: true,
    render: (row) => <span className="text-danger-dark">{formatLiters(row.loss_liters)}</span>,
  },
  {
    key: "gain",
    header: t.shift.over,
    align: "right",
    numeric: true,
    render: (row) => <span className="text-success-dark">{formatLiters(row.gain_liters)}</span>,
  },
  {
    key: "net",
    header: t.shift.variance,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-semibold">{formatLiters(row.liters)}</span>,
  },
  {
    key: "value",
    header: t.shift.varianceValue,
    align: "right",
    numeric: true,
    render: (row) => formatMNT(row.value),
  },
  {
    key: "count",
    header: t.tanks.movements,
    align: "right",
    numeric: true,
    hideOnMobile: true,
    render: (row) => formatNumber(row.movement_count, 0),
  },
];

export default ReportsPage;
