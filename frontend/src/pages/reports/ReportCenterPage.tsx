/**
 * Тайлангийн төв — тайлангийн төрөл сонгоод, олон утгатай шүүлтээр гаргана.
 *
 * Шүүлт бүр олон утга авна; юу ч сонгоогүй бол **"Бүгд"**.
 * Задаргааны мөр дээр **давхар товшиход** тухайн гүйлгээ рүү орно.
 */

import { useEffect, useMemo, useState } from "react";
import { FileSpreadsheet, Play, Printer, SlidersHorizontal } from "lucide-react";

import {
  downloadReportCenter,
  useReportCenterOptions,
  useReportCenterRun,
} from "../../api/queries/reportCenter";
import type { ReportCenterParams, ReportCenterRow } from "../../api/types";
import { ReportDrillRows } from "../../components/reports/ReportDrillRows";
import { TransactionDetailModal } from "../../components/reports/TransactionDetailModal";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { MultiSelect } from "../../components/ui/MultiSelect";
import { Spinner } from "../../components/ui/Spinner";
import { t } from "../../i18n/mn";
import { formatDate, formatMNT, formatNumber } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField } from "../catalog/_shared";

function monthStart(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function today(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const EMPTY: ReportCenterParams = {
  report: "turnover",
  date_from: monthStart(),
  date_to: today(),
  account_code: [],
  branch_id: [],
  fuel_id: [],
  category_id: [],
  employee_id: [],
  tx_type: [],
  group_by: [],
  include_details: false,
};

export function ReportCenterPage() {
  const [draft, setDraft] = useState<ReportCenterParams>(EMPTY);
  const [params, setParams] = useState<ReportCenterParams | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [detail, setDetail] = useState<{ type: string; id: string } | null>(null);
  //: Давхар товшиж дэлгэсэн бүлгийн замууд ("inbound/1301" гэх мэт).
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const optionsQuery = useReportCenterOptions();
  const runQuery = useReportCenterRun(params);
  const toastError = useUiStore((state) => state.toastError);

  const options = optionsQuery.data;
  const result = runQuery.data;

  const selectedReport = useMemo(
    () => options?.reports.find((r) => r.code === draft.report),
    [options, draft.report],
  );

  // Тайлангийн төрөл солиход түүний анхдагч бүлэглэлийг санал болгоно.
  useEffect(() => {
    if (selectedReport) {
      setDraft((d) => ({ ...d, group_by: selectedReport.default_group_by }));
    }
  }, [selectedReport?.code]);

  const set = <K extends keyof ReportCenterParams>(key: K, value: ReportCenterParams[K]): void =>
    setDraft((d) => ({ ...d, [key]: value }));

  const run = (): void => {
    setParams({ ...draft });
    setExpanded(new Set());
    setFilterOpen(false);
  };

  /** Мөр дээр давхар товшиход задаргааг нь дэлгэж/хаана. */
  const toggleRow = (path: string[]): void => {
    const key = path.join("/");
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const exportExcel = (): void => {
    if (!params || !result) return;
    downloadReportCenter(
      params,
      `${result.report_name}_${params.date_from}_${params.date_to}.xlsx`,
    ).catch((e: unknown) => toastError(e instanceof Error ? e.message : t.common.error));
  };

  const rowClass = (row: ReportCenterRow): string =>
    row.level === 0 ? "bg-surface-sunken font-bold" : row.level === 1 ? "font-semibold" : "";

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t.reportCenter.title}</h1>
          <p className="text-sm text-ink-soft">{t.reportCenter.subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="lg" icon={<SlidersHorizontal />} onClick={() => setFilterOpen(true)}>
            {t.reportCenter.openFilter}
          </Button>
          {result ? (
            <>
              <Button size="lg" variant="ghost" icon={<Printer />} onClick={() => window.print()}>
                {t.common.print}
              </Button>
              <Button size="lg" variant="ghost" icon={<FileSpreadsheet />} onClick={exportExcel}>
                {t.common.exportExcel}
              </Button>
            </>
          ) : null}
        </div>
      </header>

      {/* Тайлангийн төрлүүд — том плиткууд */}
      {!result ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 print:hidden">
          {(options?.reports ?? []).map((r) => (
            <button
              key={r.code}
              type="button"
              onClick={() => {
                setDraft((d) => ({ ...d, report: r.code }));
                setFilterOpen(true);
              }}
              className={`flex min-h-24 flex-col items-start justify-center gap-1 rounded-2xl border-2 px-5 py-4 text-left transition active:scale-[0.99] ${
                draft.report === r.code
                  ? "border-action bg-action-soft"
                  : "border-line bg-surface hover:bg-surface-sunken"
              }`}
            >
              <span className="text-base font-bold text-ink">{r.name}</span>
              <span className="text-sm text-ink-soft">{r.description}</span>
            </button>
          ))}
        </div>
      ) : null}

      {runQuery.isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : result ? (
        <div className="report-sheet rounded-2xl border border-line bg-surface p-6 print:border-0 print:p-0">
          <h2 className="mb-3 text-center text-xl font-bold text-ink">{result.report_name}</h2>
          <div className="mb-2 flex flex-wrap justify-between gap-3 text-sm">
            <span className="num">
              {formatDate(result.date_from)} — {formatDate(result.date_to)}
            </span>
            <span className="text-ink-soft">
              {t.reportCenter.grouping}: {result.group_by_labels.join(" → ")}
            </span>
          </div>
          <p className="mb-3 text-xs text-ink-soft">
            <b>{t.reportCenter.conditions}:</b> {result.filter_text}
          </p>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-sm">
              <thead>
                <tr className="bg-surface-sunken">
                  <th className="border border-line px-3 py-2 text-left">{t.reportCenter.name}</th>
                  <th className="border border-line px-3 py-2 text-right">{t.reportCenter.qty}</th>
                  <th className="border border-line px-3 py-2 text-right">{t.reportCenter.amount}</th>
                  <th className="border border-line px-3 py-2 text-right">{t.reportCenter.count}</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, index) => (
                  <>
                    <tr
                      key={`r${index}`}
                      onDoubleClick={() => toggleRow(row.path)}
                      title={t.reportCenter.doubleClickRow}
                      className={`cursor-pointer select-none hover:bg-action-soft ${rowClass(row)}`}
                    >
                      <td className="border border-line px-3 py-1.5">
                        <span style={{ paddingLeft: `${row.level * 1.25}rem` }}>
                          <span className="mr-1 inline-block w-3 text-ink-soft">
                            {expanded.has(row.path.join("/")) ? "▾" : "▸"}
                          </span>
                          {row.name}
                        </span>
                      </td>
                      <td className="num border border-line px-3 py-1.5 text-right">
                        {Number(row.qty) === 0 ? "" : formatNumber(row.qty, 2)}
                      </td>
                      <td className="num border border-line px-3 py-1.5 text-right">
                        {formatMNT(row.amount)}
                      </td>
                      <td className="num border border-line px-3 py-1.5 text-right">{row.count}</td>
                    </tr>
                    {expanded.has(row.path.join("/")) && params ? (
                      <ReportDrillRows
                        key={`x${index}`}
                        params={params}
                        path={row.path}
                        level={row.level}
                        onOpenTransaction={(type, id) => setDetail({ type, id })}
                      />
                    ) : null}
                    {row.details.map((det, di) => (
                      <tr
                        key={`d${index}-${di}`}
                        onDoubleClick={() =>
                          det.source_id && setDetail({ type: det.source_type, id: det.source_id })
                        }
                        title={t.reportCenter.doubleClickHint}
                        className="cursor-pointer text-xs text-ink-soft hover:bg-action-soft"
                      >
                        <td className="border border-line px-3 py-1">
                          <span style={{ paddingLeft: `${(row.level + 1) * 1.25}rem` }}>
                            {formatDate(det.date)} · {det.tx_type_name} {det.doc_no} — {det.item_name}
                            {det.employee_name && det.employee_name !== "—"
                              ? ` (${det.employee_name})`
                              : ""}
                          </span>
                        </td>
                        <td className="num border border-line px-3 py-1 text-right">
                          {Number(det.qty) === 0 ? "" : `${formatNumber(det.qty, 2)} ${det.unit}`}
                        </td>
                        <td className="num border border-line px-3 py-1 text-right">
                          {formatMNT(det.amount)}
                        </td>
                        <td className="border border-line px-3 py-1" />
                      </tr>
                    ))}
                  </>
                ))}
                <tr className="font-bold">
                  <td className="border border-line px-3 py-2 text-right">{t.reportCenter.total}</td>
                  <td className="num border border-line px-3 py-2 text-right">
                    {Number(result.totals.qty) === 0 ? "" : formatNumber(result.totals.qty, 2)}
                  </td>
                  <td className="num border border-line px-3 py-2 text-right">
                    {formatMNT(result.totals.amount)}
                  </td>
                  <td className="num border border-line px-3 py-2 text-right">
                    {result.totals.count}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {result.include_details ? (
            <p className="mt-3 text-xs text-ink-soft print:hidden">
              {t.reportCenter.doubleClickHint}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Шүүлтийн цонх */}
      <Modal
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        title={selectedReport?.name ?? t.reportCenter.openFilter}
        size="lg"
      >
        <div className="flex flex-col gap-4">
          <MultiSelect
            label={t.reportCenter.reportType}
            values={[draft.report]}
            onChange={(v) => v.length && set("report", v[v.length - 1])}
            options={(options?.reports ?? []).map((r) => ({ value: r.code, label: r.name }))}
            placeholder={t.reportCenter.reportType}
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <MultiSelect
              label={t.reportCenter.account}
              values={draft.account_code ?? []}
              onChange={(v) => set("account_code", v)}
              options={(options?.accounts ?? []).map((a) => ({
                value: a.code,
                label: `${a.code} — ${a.name}`,
              }))}
              searchable
            />
            <MultiSelect
              label={t.reportCenter.branch}
              values={draft.branch_id ?? []}
              onChange={(v) => set("branch_id", v)}
              options={(options?.branches ?? []).map((b) => ({ value: b.id as string, label: b.name }))}
            />
            <MultiSelect
              label={t.reportCenter.fuel}
              values={draft.fuel_id ?? []}
              onChange={(v) => set("fuel_id", v)}
              options={(options?.fuels ?? []).map((f) => ({
                value: f.id as string,
                label: `${f.code} — ${f.name}`,
              }))}
            />
            <MultiSelect
              label={t.reportCenter.category}
              values={draft.category_id ?? []}
              onChange={(v) => set("category_id", v)}
              options={(options?.categories ?? []).map((c) => ({ value: c.id as string, label: c.name }))}
            />
            <MultiSelect
              label={t.reportCenter.employee}
              values={draft.employee_id ?? []}
              onChange={(v) => set("employee_id", v)}
              options={(options?.employees ?? []).map((e) => ({ value: e.id as string, label: e.name }))}
            />
            <MultiSelect
              label={t.reportCenter.txType}
              values={draft.tx_type ?? []}
              onChange={(v) => set("tx_type", v)}
              options={(options?.tx_types ?? []).map((x) => ({ value: x.code, label: x.name }))}
            />
            <DateField
              label={t.reportCenter.dateFrom}
              value={draft.date_from}
              onChange={(v) => set("date_from", v)}
            />
            <DateField
              label={t.reportCenter.dateTo}
              value={draft.date_to}
              onChange={(v) => set("date_to", v)}
            />
          </div>

          <MultiSelect
            label={t.reportCenter.groupBy}
            values={draft.group_by ?? []}
            onChange={(v) => set("group_by", v)}
            options={(options?.group_fields ?? []).map((g) => ({ value: g.code, label: g.name }))}
            placeholder={t.reportCenter.groupByHint}
          />

          <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 border-line bg-surface px-4">
            <input
              type="checkbox"
              checked={draft.include_details ?? false}
              onChange={(e) => set("include_details", e.target.checked)}
              className="h-6 w-6 accent-action"
            />
            <span className="text-sm font-medium text-ink">{t.reportCenter.showDetails}</span>
          </label>

          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setFilterOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button size="lg" className="flex-1" icon={<Play />} onClick={run}>
              {t.reportCenter.run}
            </Button>
          </div>
        </div>
      </Modal>

      <TransactionDetailModal
        sourceType={detail?.type ?? null}
        sourceId={detail?.id ?? null}
        onClose={() => setDetail(null)}
      />
    </div>
  );
}

export default ReportCenterPage;
