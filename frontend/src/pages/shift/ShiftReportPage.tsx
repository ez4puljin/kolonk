import { Fragment, useState } from "react";
import { useParams } from "react-router-dom";
import { AlertTriangle, Check, Download, Droplets, Pencil, Printer } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  downloadShiftReport,
  useRecalculateCashMutation,
  useCorrectOpeningCashMutation,
  useCorrectOpeningReadingMutation,
  useShiftReport,
} from "../../api/queries/shifts";
import { useSettings } from "../../api/queries/system";
import type {
  MoneyStr,
  ShiftFuelRow,
  ShiftNozzleRow,
  ShiftTankRow,
  TenderRow,
} from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { AttendantRecord } from "../../components/shift/AttendantRecord";
import { ShiftReportTemplate } from "../../components/receipt/ShiftReportTemplate";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { usePermission } from "../../hooks/usePermission";
import { usePrint } from "../../hooks/usePrint";
import { t } from "../../i18n/mn";
import { dToNumber } from "../../lib/decimal";
import { SHIFT_STATUS_META, statusMeta } from "../../lib/constants";
import { dCmp, dIsPositive, dIsZero, dSub } from "../../lib/decimal";
import { formatDateTime, formatLiters, formatMNT, formatMoneyExact, formatNumber, formatPct } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { NumberField, TextField } from "../catalog/_shared";
import { PriceMarkModal } from "./AttendantShiftPage";

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

// --------------------------------------------------------------------------
// Нээлтийн миль засах цонх (админ, зөвхөн нээлттэй ээлж)
// --------------------------------------------------------------------------
function OpeningFixModal({
  shiftId,
  row,
  onClose,
}: {
  shiftId: string;
  row: ShiftNozzleRow | null;
  onClose: () => void;
}) {
  const fix = useCorrectOpeningReadingMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const [reading, setReading] = useState("");
  const [note, setNote] = useState("");
  const [ready, setReady] = useState<string | null>(null);

  // Цонх нээгдэх бүрд одоогийн мильээр урьдчилан бөглөнө.
  if (row && ready !== row.nozzle_id) {
    setReady(row.nozzle_id);
    setReading(row.opening_reading ?? "");
    setNote("");
  }

  const prev = row?.prev_close_reading ?? null;
  const nextGap = prev !== null && reading.trim() !== "" ? dSub(reading, prev) : null;

  return (
    <Modal
      open={row !== null}
      onClose={onClose}
      size="md"
      title={t.shift.fixOpeningTitle}
      subtitle={row ? `${row.pump_number} · ${row.pump_name} — ${row.nozzle_number} · ${row.fuel_name}` : undefined}
      dismissible={!fix.isPending}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Check />}
            loading={fix.isPending}
            disabled={reading.trim() === ""}
            onClick={() => {
              if (!row) return;
              fix.mutate(
                { shiftId, nozzleId: row.nozzle_id, reading: reading.trim(), note },
                {
                  onSuccess: () => {
                    toastSuccess(t.shift.fixOpeningToast);
                    setReady(null);
                    onClose();
                  },
                  onError: (cause) => toastError(errorMessage(cause)),
                },
              );
            }}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{t.shift.fixOpeningHint}</p>

        <div className="num grid grid-cols-2 gap-3 rounded-xl border border-line bg-surface-alt px-4 py-3 text-sm">
          <span className="text-ink-soft">{t.attendant.prevClose}</span>
          <span className="text-right font-semibold text-ink">{formatLiters(prev, 3)}</span>
          <span className="text-ink-soft">{t.shift.fixOpeningCurrent}</span>
          <span className="text-right font-semibold text-ink">{formatLiters(row?.opening_reading ?? null, 3)}</span>
        </div>

        <NumberField
          name="fix-opening-reading"
          label={t.shift.fixOpeningNew}
          value={reading}
          onChange={setReading}
          suffix={t.units.liter}
          maxDecimals={3}
        />

        <div className="num flex items-baseline justify-between rounded-xl border border-line-strong px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.attendant.mileGap}</span>
          <span
            className={`text-xl font-black ${nextGap === null || dIsZero(nextGap) ? "text-success-dark" : "text-warning-dark"}`}
          >
            {nextGap === null ? "—" : `${dIsPositive(nextGap) ? "+" : ""}${formatLiters(nextGap, 3)}`}
          </span>
        </div>

        <TextField label={t.shift.fixOpeningNote} value={note} onChange={setNote} />
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Эхний бэлэн мөнгө засах цонх (админ; нээлттэй ба батлагдаагүй хаагдсан ээлж)
// --------------------------------------------------------------------------
function OpeningCashModal({
  shiftId,
  open,
  current,
  expected,
  declared,
  onClose,
}: {
  shiftId: string;
  open: boolean;
  current: MoneyStr;
  expected: MoneyStr | null;
  declared: MoneyStr | null;
  onClose: () => void;
}) {
  const fix = useCorrectOpeningCashMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const [value, setValue] = useState("");
  const [note, setNote] = useState("");
  const [ready, setReady] = useState(false);

  if (open && !ready) {
    setReady(true);
    setValue(current);
    setNote("");
  }
  if (!open && ready) setReady(false);

  // Хаагдсан ээлжид: шинэ байвал зохих = хуучин + (шинэ эхний − хуучин эхний).
  const delta = value.trim() === "" ? "0" : dSub(value, current);
  const nextExpected = expected !== null ? dSub(expected, dSub("0", delta)) : null;
  const nextDiff = nextExpected !== null && declared !== null ? dSub(declared, nextExpected) : null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={t.shift.fixOpeningCashTitle}
      dismissible={!fix.isPending}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Check />}
            loading={fix.isPending}
            disabled={value.trim() === ""}
            onClick={() =>
              fix.mutate(
                { shiftId, openingCash: value.trim(), note },
                {
                  onSuccess: () => {
                    toastSuccess(t.shift.fixOpeningCashToast);
                    onClose();
                  },
                  onError: (cause) => toastError(errorMessage(cause)),
                },
              )
            }
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{t.shift.fixOpeningCashHint}</p>
        <div className="num flex items-baseline justify-between rounded-xl border border-line bg-surface-alt px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.shift.fixOpeningCurrent}</span>
          <span className="text-lg font-bold text-ink">{formatMNT(current)}</span>
        </div>
        <NumberField name="fix-opening-cash" label={t.shift.fixOpeningCashNew} value={value} onChange={setValue} suffix={t.units.mnt} />
        {nextExpected !== null ? (
          <div className="num grid grid-cols-2 gap-2 rounded-xl border border-line-strong px-4 py-3 text-sm">
            <span className="text-ink-soft">{t.shift.expectedCash}</span>
            <span className="text-right font-bold text-ink">{formatMNT(nextExpected)}</span>
            {nextDiff !== null ? (
              <>
                <span className="text-ink-soft">{t.shift.overShort}</span>
                <span
                  className={`text-right text-lg font-black ${dCmp(nextDiff, "0") < 0 ? "text-danger-dark" : dIsPositive(nextDiff) ? "text-warning-dark" : "text-success-dark"}`}
                >
                  {formatMNT(nextDiff)}
                </span>
              </>
            ) : null}
          </div>
        ) : null}
        <TextField label={t.shift.fixOpeningNote} value={note} onChange={setNote} />
      </div>
    </Modal>
  );
}

export function ShiftReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data: report, isLoading, isError, error } = useShiftReport(id ?? null);
  const { data: settings } = useSettings();
  const { print, portal } = usePrint();
  const { can } = usePermission();
  const toastError = useUiStore((state) => state.toastError);
  const [downloading, setDownloading] = useState(false);
  const [fixRow, setFixRow] = useState<ShiftNozzleRow | null>(null);
  const [cashFixOpen, setCashFixOpen] = useState(false);
  const [markOpen, setMarkOpen] = useState(false);
  const recalc = useRecalculateCashMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

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
  // Нээлтийн мильийг зөвхөн НЭЭЛТТЭЙ ээлжид, хаалт засах эрхтэй хүн засна.
  const canFixOpening = shift.status === "open" && can("shifts.approve");
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
      key: "prev",
      header: t.attendant.prevClose,
      render: (row) => formatLiters(row.prev_close_reading, 3),
      align: "right",
      numeric: true,
      hideOnMobile: true,
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
      // Миль бол хуримтлагдсан заалт — өмнөх хаалттай ЯГ тэнцүү байх ёстой.
      key: "gap",
      header: t.attendant.mileGap,
      render: (row) => {
        if (row.mile_gap_l === null) return "—";
        if (dIsZero(row.mile_gap_l)) return <span className="text-success-dark">0.000</span>;
        return (
          <span className="font-bold text-warning-dark">
            {dIsPositive(row.mile_gap_l) ? "+" : ""}
            {formatLiters(row.mile_gap_l, 3)}
          </span>
        );
      },
      align: "right",
      numeric: true,
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
    ...(canFixOpening
      ? [
          {
            // "actions" — утасны картад тусдаа мөрөнд бүтэн өргөнөөр гарна.
            key: "actions",
            header: t.common.actions,
            align: "right" as const,
            render: (row: ShiftNozzleRow) =>
              row.opening_reading !== null ? (
                <Button variant="secondary" size="sm" icon={<Pencil />} onClick={() => setFixRow(row)}>
                  {t.shift.fixOpening}
                </Button>
              ) : null,
          } satisfies Column<ShiftNozzleRow>,
        ]
      : []),
  ];

  // Милийн залгамж зөрчигдсөн хошуунууд — тайлангийн дээд талд сануулна.
  const gapRows = nozzles.filter(
    (row) => row.mile_gap_l !== null && !dIsZero(row.mile_gap_l),
  );

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
            {shift.status === "open" && can("shifts.view_all") ? (
              <Button variant="warning" size="md" icon={<Droplets />} onClick={() => setMarkOpen(true)}>
                {t.attendant.priceMark}
              </Button>
            ) : null}
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

      {/* Милийн залгамжийн зөрчил — мөнгөний алдагдал байж болзошгүй тул
          тайланг нээмэгц хамгийн түрүүнд харагдана. */}
      {gapRows.length > 0 ? (
        <div className="rounded-2xl border border-warning bg-warning-soft/50 px-4 py-3.5">
          <p className="flex items-center gap-2 text-[15px] font-bold text-warning-dark">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {t.attendant.mileGapTitle} · {t.attendant.mileGapNozzles.replace("{n}", String(gapRows.length))}
          </p>
          <p className="mt-1 text-sm text-ink-soft">{t.attendant.mileGapHint}</p>
          <ul className="num mt-2 flex flex-col gap-1 text-sm font-semibold text-ink">
            {gapRows.map((row) => (
              <li key={row.nozzle_id}>
                {row.pump_name} · №{row.nozzle_number} {row.fuel_name} —{" "}
                <span className="text-warning-dark">
                  {dIsPositive(row.mile_gap_l ?? "0") ? "+" : ""}
                  {formatLiters(row.mile_gap_l, 3)}
                </span>{" "}
                <span className="font-normal text-ink-soft">
                  {t.attendant.mileGapRow
                    .replace("{prev}", formatLiters(row.prev_close_reading, 3))
                    .replace("{now}", formatLiters(row.opening_reading, 3))}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

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
            <CashRow label={t.attendant.settlementTotal} value={daily.settlement_total} strong />
            <CashRow label={t.attendant.transferTotal} value={daily.transfer_total ?? "0"} />
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
                      <Fragment key={row.nozzle_id}>
                        <tr className="border-t border-line">
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
                        {/* Ээлжийн дундуур үнэ өөрчлөгдсөн бол дүн нь нэг үнээр
                            биш, сегмент тус бүрээр бодогдоно. Нягтлан гараар
                            шалгах боломжтой байхын тулд задаргааг нь харуулна. */}
                        {row.segments.length > 1
                          ? row.segments.map((segment, index) => (
                              <tr key={`${row.nozzle_id}-${index}`} className="bg-surface-alt/60 text-xs">
                                <td className="px-3 py-1.5 pl-8 text-ink-soft" colSpan={2}>
                                  {t.attendant.segments} {index + 1} · {formatMNT(segment.price)}/
                                  {t.units.liter}
                                </td>
                                <td className="px-3 py-1.5" colSpan={2} />
                                <td className="px-3 py-1.5 text-right text-ink-soft">
                                  {formatLiters(segment.liters, 3)}
                                </td>
                                <td className="px-3 py-1.5 text-right font-semibold text-ink-soft">
                                  {formatMNT(segment.amount)}
                                </td>
                              </tr>
                            ))
                          : null}
                      </Fragment>
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

        <Card
          title={t.dashboard.cashInDrawer}
          actions={
            can("shifts.approve") ? (
              <Button variant="secondary" size="sm" icon={<Pencil />} onClick={() => setCashFixOpen(true)}>
                {t.shift.fixOpeningCash}
              </Button>
            ) : undefined
          }
        >
          <CashRow label={t.shift.openingCash} value={cash.opening_cash} />
          <CashRow label={t.tender.cash} value={cash.cash_sales} />
          <CashRow label={t.refunds.title} value={cash.refunds} />
          {cash.other_cash && !dIsZero(cash.other_cash) ? (
            <CashRow label={t.shift.otherCash} value={cash.other_cash} />
          ) : null}
          <CashRow label={t.shift.expectedCash} value={cash.expected_cash} strong />
          {cash.recalc_expected ? (
            // Хуучин дүрмээр хаагдсан: ээлжийн бус хүний кассын гүйлгээ орсон байна.
            <div className="my-2 flex flex-col gap-2 rounded-xl border-2 border-warning bg-warning-soft px-3 py-2.5 text-sm text-warning-dark">
              <span className="font-bold">{t.shift.recalcTitle}</span>
              <span className="text-ink-soft">
                {t.shift.recalcHint
                  .replace("{expected}", formatMoneyExact(cash.recalc_expected))
                  .replace("{diff}", formatMoneyExact(dSub(cash.declared_cash ?? "0", cash.recalc_expected)))}
              </span>
              {can("shifts.approve") ? (
                <Button
                  variant="warning"
                  size="md"
                  loading={recalc.isPending}
                  onClick={() =>
                    recalc.mutate(shift.id, {
                      onSuccess: () => toastSuccess(t.shift.recalcToast),
                      onError: (cause) => toastError(errorMessage(cause)),
                    })
                  }
                >
                  {t.shift.recalcAction}
                </Button>
              ) : null}
            </div>
          ) : null}
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

      <Card title={t.shift.byTender} flush className="max-w-4xl">
        <DataTable columns={tenderColumns} rows={sales.by_tender} rowKey={(row) => row.method} />
      </Card>

      <Card title={t.shift.byFuel} flush className="max-w-4xl">
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
      {shift.status === "open" && can("shifts.view_all") ? (
        <PriceMarkModal shiftId={shift.id} open={markOpen} onClose={() => setMarkOpen(false)} />
      ) : null}
      {canFixOpening ? <OpeningFixModal shiftId={shift.id} row={fixRow} onClose={() => setFixRow(null)} /> : null}
      {can("shifts.approve") ? (
        <OpeningCashModal
          shiftId={shift.id}
          open={cashFixOpen}
          current={cash.opening_cash}
          expected={shift.status === "open" ? null : cash.expected_cash}
          declared={cash.declared_cash}
          onClose={() => setCashFixOpen(false)}
        />
      ) : null}

      {/* Түгээгчийн оруулсан тоо + дарсан зураг — баримтын хэсэг. */}
      {id ? <AttendantRecord shiftId={id} report={report} /> : null}

      {portal}
    </div>
  );
}

export default ShiftReportPage;
