import { useState } from "react";
import { useParams } from "react-router-dom";
import { Download, Printer } from "lucide-react";

import { errorMessage } from "../../api/client";
import { downloadShiftReport, useShiftReport } from "../../api/queries/shifts";
import { useSettings } from "../../api/queries/system";
import type {
  MoneyStr,
  ShiftFuelRow,
  ShiftNozzleRow,
  ShiftTankRow,
  TenderRow,
} from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { ShiftReportTemplate } from "../../components/receipt/ShiftReportTemplate";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { usePrint } from "../../hooks/usePrint";
import { t } from "../../i18n/mn";
import { dToNumber } from "../../lib/decimal";
import { SHIFT_STATUS_META, statusMeta } from "../../lib/constants";
import { dCmp, dIsZero } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, formatMoneyExact, formatNumber, formatPct } from "../../lib/format";
import { useUiStore } from "../../stores/ui";

function CashRow({ label, value, strong }: { label: string; value: MoneyStr | null; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2.5 last:border-b-0">
      <span className={`text-[15px] ${strong ? "font-bold text-ink" : "text-ink-soft"}`}>{label}</span>
      <span className={`num text-lg ${strong ? "font-black text-ink" : "font-semibold text-ink"}`}>
        {formatMoneyExact(value)}
      </span>
    </div>
  );
}

export function ShiftReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data: report, isLoading, isError, error } = useShiftReport(id ?? null);
  const { data: settings } = useSettings();
  const { print, portal } = usePrint();
  const toastError = useUiStore((state) => state.toastError);
  const [downloading, setDownloading] = useState(false);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (isError || !report) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.shift.report} back />
        <EmptyState title={t.errors.loadFailed} hint={isError ? errorMessage(error) : t.common.emptyHint} />
      </div>
    );
  }

  const { shift, sales, cash, profit, tanks, nozzles, fuels, daily } = report;

  /** Тоолуурын заалт унтраалттай ээлжид энэ хэсэг утгагүй тул нуухыг шийднэ. */
  const hasReadings = nozzles.some(
    (row) => dToNumber(row.opening_reading) > 0 || dToNumber(row.closing_reading) > 0,
  );
  const overShort = cash.cash_over_short;
  const balanced = overShort === null || dIsZero(overShort);
  const short = overShort !== null && dCmp(overShort, "0") < 0;
  const stationName = typeof settings?.station_name === "string" ? settings.station_name : undefined;

  const handleDownload = (): void => {
    setDownloading(true);
    void downloadShiftReport(shift.id, shift.number)
      .catch((cause: unknown) => toastError(errorMessage(cause)))
      .finally(() => setDownloading(false));
  };

  const tenderColumns: Column<TenderRow>[] = [
    { key: "method", header: t.tender.title, render: (row) => row.method_name, primary: true },
    { key: "count", header: t.reports.transactions, render: (row) => row.count, align: "right", numeric: true },
    {
      key: "amount",
      header: t.common.amount,
      render: (row) => formatMoneyExact(row.amount),
      align: "right",
      numeric: true,
    },
  ];

  const fuelColumns: Column<ShiftFuelRow>[] = [
    { key: "name", header: t.tanks.fuelType, render: (row) => row.name, primary: true },
    { key: "code", header: t.common.code, render: (row) => row.code, hideOnMobile: true },
    {
      key: "liters",
      header: t.pos.liters,
      render: (row) => formatLiters(row.liters, 3),
      align: "right",
      numeric: true,
    },
    {
      key: "amount",
      header: t.common.amount,
      render: (row) => formatMoneyExact(row.amount),
      align: "right",
      numeric: true,
    },
  ];

  const tankColumns: Column<ShiftTankRow>[] = [
    { key: "tank", header: t.tanks.tank, render: (row) => row.tank_name, primary: true },
    { key: "fuel", header: t.tanks.fuelType, render: (row) => row.fuel_name, hideOnMobile: true },
    {
      key: "open",
      header: t.shift.openDip,
      render: (row) => formatLiters(row.open_dip, 3),
      align: "right",
      numeric: true,
    },
    {
      key: "close",
      header: t.shift.closeDip,
      render: (row) => formatLiters(row.close_dip, 3),
      align: "right",
      numeric: true,
    },
    {
      key: "book",
      header: t.shift.bookLiters,
      render: (row) => formatLiters(row.book_liters, 3),
      align: "right",
      numeric: true,
    },
    {
      key: "variance",
      header: t.shift.variance,
      render: (row) => (
        <span
          className={
            row.variance_l === null || dIsZero(row.variance_l)
              ? "text-ink"
              : dCmp(row.variance_l, "0") < 0
                ? "font-bold text-danger-dark"
                : "font-bold text-success-dark"
          }
        >
          {formatLiters(row.variance_l, 3)}
        </span>
      ),
      align: "right",
      numeric: true,
    },
    {
      key: "value",
      header: t.shift.varianceValue,
      render: (row) => formatMoneyExact(row.variance_value),
      align: "right",
      numeric: true,
    },
  ];

  const nozzleColumns: Column<ShiftNozzleRow>[] = [
    {
      key: "pump",
      header: t.pumps.pump,
      render: (row) => `${row.pump_number} · ${row.pump_name}`,
      primary: true,
    },
    {
      key: "nozzle",
      header: t.pumps.nozzleNo,
      render: (row) => `${row.nozzle_number} · ${row.fuel_name}`,
    },
    {
      key: "open",
      header: t.shift.openingReading,
      render: (row) => formatLiters(row.opening_reading, 3),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "close",
      header: t.shift.closingReading,
      render: (row) => formatLiters(row.closing_reading, 3),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "delta",
      header: t.shift.readingDelta,
      render: (row) => formatLiters(row.reading_delta_l, 3),
      align: "right",
      numeric: true,
    },
    {
      key: "sold",
      header: t.shift.soldLiters,
      render: (row) => formatLiters(row.sold_liters, 3),
      align: "right",
      numeric: true,
    },
    {
      key: "amount",
      header: t.shift.soldAmount,
      render: (row) => formatMoneyExact(row.sold_amount),
      align: "right",
      numeric: true,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={`${t.shift.reportOf}${shift.number}`}
        back="/shift"
        subtitle={
          <span className="num">
            {formatDateTime(shift.opened_at)} — {formatDateTime(shift.closed_at)} ·{" "}
            {shift.closed_by_name ?? shift.opened_by_name ?? ""}
          </span>
        }
        actions={
          <>
            <StatusBadge meta={statusMeta(SHIFT_STATUS_META, shift.status, shift.status_name)} dot />
            <Button
              variant="secondary"
              size="md"
              icon={<Printer />}
              onClick={() => print(<ShiftReportTemplate report={report} stationName={stationName} />)}
            >
              {t.common.print}
            </Button>
            <Button
              variant="primary"
              size="md"
              icon={<Download />}
              loading={downloading}
              onClick={handleDownload}
            >
              {t.common.exportExcel}
            </Button>
          </>
        }
      />

      {/* Гол үзүүлэлт */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatBox
          label={t.shift.salesSummary}
          value={formatMoneyExact(sales.gross_total, false)}
          unit={t.units.mnt}
          hint={`${sales.count} ${t.common.rows}`}
          tone="action"
        />
        <StatBox
          label={t.reports.litersSold}
          value={formatLiters(sales.fuel_liters, 2)}
          tone="success"
          hint={formatMoneyExact(sales.fuel_amount)}
        />
        <StatBox
          label={t.shift.grossProfit}
          value={formatMoneyExact(profit.gross_profit, false)}
          unit={t.units.mnt}
          hint={`${t.shift.marginPct}: ${formatPct(profit.margin_pct)}`}
          tone="success"
        />
        <StatBox
          label={t.shift.overShort}
          value={formatMoneyExact(overShort, false)}
          unit={t.units.mnt}
          tone={balanced ? "neutral" : short ? "danger" : "success"}
          hint={balanced ? t.accounting.balanced : short ? t.shift.short : t.shift.over}
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {/* Касс */}
        {daily ? (
          <Card title={t.attendant.reconciliation} subtitle={t.attendant.title}>
            <CashRow label={t.attendant.fuelByMile} value={daily.fuel_total} strong />
            <CashRow label={t.attendant.settlementVat} value={daily.settlement_vat} />
            <CashRow label={t.attendant.settlementNovat} value={daily.settlement_novat} />
            <CashRow label={t.attendant.settlementTotal} value={daily.settlement_total} strong />
            <CashRow label={t.attendant.creditSales} value={daily.credit_total} />
            <CashRow label={t.attendant.oilSales} value={daily.oil_total} />
            {daily.nozzles.length > 0 ? (
              <div className="mt-3 overflow-x-auto rounded-xl border border-line">
                <table className="num w-full text-sm">
                  <thead className="bg-surface-alt text-left text-xs font-bold text-ink-soft uppercase">
                    <tr>
                      <th className="px-3 py-2">{t.pumps.title}</th>
                      <th className="px-3 py-2">{t.attendant.tank}</th>
                      <th className="px-3 py-2 text-right">{t.attendant.openMile}</th>
                      <th className="px-3 py-2 text-right">{t.attendant.closeMile}</th>
                      <th className="px-3 py-2 text-right">{t.pos.liters}</th>
                      <th className="px-3 py-2 text-right">{t.common.amount}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {daily.nozzles.map((row) => (
                      <tr key={row.nozzle_id} className="border-t border-line">
                        <td className="px-3 py-2">
                          {row.pump_name} №{row.nozzle_number} {row.fuel_name}
                          {row.segments.length > 1 ? (
                            <span className="ml-2 text-xs text-warning-dark">
                              {row.segments.length} {t.attendant.segments}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-ink-soft">{row.tank_name ?? "—"}</td>
                        <td className="px-3 py-2 text-right">{formatNumber(row.open_reading, 1)}</td>
                        <td className="px-3 py-2 text-right">{formatNumber(row.close_reading, 1)}</td>
                        <td className="px-3 py-2 text-right">{formatLiters(row.liters, 1)}</td>
                        <td className="px-3 py-2 text-right font-bold">{formatMNT(row.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {daily.tanks && daily.tanks.length > 0 ? (
              <div className="mt-3 overflow-x-auto rounded-xl border border-line">
                <table className="num w-full text-sm">
                  <thead className="bg-surface-alt text-left text-xs font-bold text-ink-soft uppercase">
                    <tr>
                      <th className="px-3 py-2">{t.attendant.tankUsage}</th>
                      <th className="px-3 py-2 text-right">{t.pos.liters}</th>
                      <th className="px-3 py-2 text-right">{t.common.amount}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {daily.tanks.map((row) => (
                      <tr key={row.tank_id} className="border-t border-line">
                        <td className="px-3 py-2">{row.tank_name}</td>
                        <td className="px-3 py-2 text-right">{formatLiters(row.liters, 1)}</td>
                        <td className="px-3 py-2 text-right font-bold">{formatMNT(row.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </Card>
        ) : null}

        <Card title={t.dashboard.cashInDrawer}>
          <CashRow label={t.shift.openingCash} value={cash.opening_cash} />
          <CashRow label={t.tender.cash} value={cash.cash_sales} />
          <CashRow label={t.refunds.title} value={cash.refunds} />
          <CashRow label={t.shift.expectedCash} value={cash.expected_cash} strong />
          <CashRow label={t.shift.declaredCash} value={cash.declared_cash} strong />
          <div
            className={`mt-3 flex items-center justify-between gap-4 rounded-xl border-2 px-4 py-3 ${
              balanced
                ? "border-line-strong bg-surface-alt"
                : short
                  ? "border-danger bg-danger-soft"
                  : "border-success bg-success-soft"
            }`}
          >
            <span className="text-[15px] font-bold text-ink">{t.shift.overShort}</span>
            <span
              className={`num text-2xl font-black ${
                balanced ? "text-ink" : short ? "text-danger-dark" : "text-success-dark"
              }`}
            >
              {formatMoneyExact(overShort)}
            </span>
          </div>
        </Card>

        {/* Ашиг */}
        <Card title={t.shift.profit}>
          <CashRow label={t.shift.revenueNet} value={profit.revenue_net} />
          <CashRow label={t.shift.cogs} value={profit.cogs_total} />
          <CashRow label={t.shift.grossProfit} value={profit.gross_profit} strong />
          <div className="mt-3 flex items-center justify-between gap-4 rounded-xl bg-surface-alt px-4 py-3">
            <span className="text-[15px] font-bold text-ink">{t.shift.marginPct}</span>
            <span className="num text-2xl font-black text-success-dark">{formatPct(profit.margin_pct)}</span>
          </div>
          <div className="mt-3">
            <CashRow label={t.common.vat} value={sales.vat_total} />
            <CashRow label={t.sales.store} value={sales.store_amount} />
          </div>
        </Card>
      </div>

      <Card title={t.shift.byTender} flush>
        <DataTable columns={tenderColumns} rows={sales.by_tender} rowKey={(row) => row.method} />
      </Card>

      <Card title={t.shift.byFuel} flush>
        <DataTable columns={fuelColumns} rows={fuels} rowKey={(row) => row.fuel_id} />
      </Card>

      <Card title={t.shift.tankDips} flush>
        <DataTable columns={tankColumns} rows={tanks} rowKey={(row) => row.tank_id} />
      </Card>

      {hasReadings ? (
        <Card title={t.shift.totalizers} flush>
          <DataTable columns={nozzleColumns} rows={nozzles} rowKey={(row) => row.nozzle_id} />
        </Card>
      ) : null}

      {portal}
    </div>
  );
}

export default ShiftReportPage;
