/**
 * Бараа материалын тайлан /өртгөөр/ — Erkhet маягийн хөдөлгөөний тайлан.
 *
 * "Тайлан авах" цонхоор шүүлт хийж, шаталсан мөр бүхий тайлан гаргана:
 * эхний үлдэгдэл → орлого → зарлага → эцсийн үлдэгдэл (тоо ба дүн).
 * Задаргаа асаавал гүйлгээ тус бүр үлдэгдэлтэйгээ харагдана.
 *
 * Тайлан ерөнхий дэвтрийн 1301/1302 дансны үлдэгдэлтэй яг тэнцэнэ.
 */

import { useMemo, useState } from "react";
import { FileSpreadsheet, Printer, SlidersHorizontal } from "lucide-react";

import {
  downloadInventoryReport,
  useInventoryReport,
  useInventoryReportOptions,
} from "../../api/queries/inventoryReport";
import { useSettings } from "../../api/queries/system";
import type { InventoryReportParams, InventoryReportRow } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { TouchSelect } from "../../components/ui/TouchSelect";
import { t } from "../../i18n/mn";
import { formatDate, formatMNT, formatNumber } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, TextField } from "../catalog/_shared";

const ANY = "__any__";

function monthStart(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function today(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Тоо — хоосон бол зураас (Erkhet тайлангийн зан). */
function qty(value: string | null | undefined): string {
  if (value === null || value === undefined) return "";
  return Number(value) === 0 ? "" : formatNumber(value, 2);
}

function money(value: string | null | undefined): string {
  if (value === null || value === undefined) return "";
  return Number(value) === 0 ? "" : formatMNT(value);
}

export function InventoryReportPage() {
  const [filterOpen, setFilterOpen] = useState(false);
  const [params, setParams] = useState<InventoryReportParams | null>({
    date_from: monthStart(),
    date_to: today(),
    group_by: "account_location_item",
    tx_type: "all",
    include_details: false,
    skip_empty: true,
  });

  // Цонхны түр төлөв — "Тайлан авах" дархад л params руу шилжинэ.
  const [draft, setDraft] = useState<InventoryReportParams>({
    date_from: monthStart(),
    date_to: today(),
    group_by: "account_location_item",
    tx_type: "all",
    include_details: false,
    skip_empty: true,
  });

  const optionsQuery = useInventoryReportOptions();
  const reportQuery = useInventoryReport(params);
  const settingsQuery = useSettings();
  const toastError = useUiStore((state) => state.toastError);

  const options = optionsQuery.data;
  const report = reportQuery.data;

  const stationName = useMemo(() => {
    const rows = settingsQuery.data ?? [];
    const found = Array.isArray(rows)
      ? rows.find((r: { key: string }) => r.key === "station_name")
      : null;
    return (found as { value?: string } | null)?.value ?? "";
  }, [settingsQuery.data]);

  const apply = (): void => {
    setParams({ ...draft });
    setFilterOpen(false);
  };

  const exportExcel = (): void => {
    if (!params) return;
    downloadInventoryReport(params).catch((e: unknown) =>
      toastError(e instanceof Error ? e.message : t.common.error),
    );
  };

  const rowClass = (row: InventoryReportRow): string => {
    if (row.level === 0) return "bg-surface-sunken font-bold";
    if (row.level === 1) return "font-semibold";
    return "";
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Хэвлэхэд хэрэггүй удирдлагууд */}
      <header className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t.inventoryReport.title}</h1>
          <p className="text-sm text-ink-soft">{t.inventoryReport.subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="lg"
            variant="secondary"
            icon={<SlidersHorizontal />}
            onClick={() => setFilterOpen(true)}
          >
            {t.inventoryReport.filter}
          </Button>
          <Button size="lg" variant="ghost" icon={<Printer />} onClick={() => window.print()}>
            {t.common.print}
          </Button>
          <Button size="lg" variant="ghost" icon={<FileSpreadsheet />} onClick={exportExcel}>
            {t.common.exportExcel}
          </Button>
        </div>
      </header>

      {reportQuery.isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : report ? (
        <div className="report-sheet rounded-2xl border border-line bg-surface p-6 print:border-0 print:p-0">
          {/* Тайлангийн толгой */}
          <h2 className="mb-4 text-center text-xl font-bold text-ink">
            {t.inventoryReport.reportTitle}
          </h2>
          <div className="mb-2 flex flex-wrap items-start justify-between gap-4 text-sm">
            <div>
              <div className="border-b border-ink px-6 pb-0.5 text-center font-semibold">
                {stationName || " "}
              </div>
              <div className="text-center text-xs text-ink-soft">
                {t.inventoryReport.orgName}
              </div>
            </div>
            <div className="text-right">
              <div className="num">
                {formatDate(report.date_from)} - {formatDate(report.date_to)}
              </div>
              <div className="text-xs text-ink-soft">({t.inventoryReport.inMnt})</div>
            </div>
          </div>
          {report.filter_text ? (
            <p className="mb-3 text-xs text-ink-soft">
              <b>{t.inventoryReport.conditions}:</b> {report.filter_text}
            </p>
          ) : null}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead>
                <tr>
                  <th rowSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.code}</th>
                  <th rowSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.name}</th>
                  <th colSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.opening}</th>
                  <th colSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.inbound}</th>
                  <th colSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.outbound}</th>
                  <th colSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.closing}</th>
                  <th rowSpan={2} className="border border-line px-3 py-2">{t.inventoryReport.unitCost}</th>
                </tr>
                <tr>
                  {[0, 1, 2, 3].map((i) => (
                    <>
                      <th key={`q${i}`} className="border border-line px-3 py-1 text-xs font-medium">
                        {t.inventoryReport.qty}
                      </th>
                      <th key={`v${i}`} className="border border-line px-3 py-1 text-xs font-medium">
                        {t.inventoryReport.amount}
                      </th>
                    </>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.rows.map((row, index) => (
                  <>
                    <tr key={`${row.level}-${row.code}-${index}`} className={rowClass(row)}>
                      <td className="border border-line px-3 py-1.5">{row.code}</td>
                      <td className="border border-line px-3 py-1.5">
                        <span style={{ paddingLeft: `${row.level * 1.25}rem` }}>{row.name}</span>
                      </td>
                      <td className="num border border-line px-3 py-1.5 text-right">{qty(row.opening_qty)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{money(row.opening_value)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{qty(row.in_qty)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{money(row.in_value)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{qty(row.out_qty)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{money(row.out_value)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{qty(row.closing_qty)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{money(row.closing_value)}</td>
                      <td className="num border border-line px-3 py-1.5 text-right">{money(row.unit_cost)}</td>
                    </tr>
                    {row.details.map((det, di) => (
                      <tr key={`${index}-d${di}`} className="text-xs italic text-ink-soft">
                        <td className="border border-line px-3 py-1" />
                        <td className="border border-line px-3 py-1">
                          <span style={{ paddingLeft: `${(row.level + 1) * 1.25}rem` }}>
                            {formatDate(det.date)} - {det.movement_name}
                            {det.note ? ` (${det.note})` : ""}
                          </span>
                        </td>
                        <td className="border border-line px-3 py-1" />
                        <td className="border border-line px-3 py-1" />
                        <td className="num border border-line px-3 py-1 text-right">{qty(det.in_qty)}</td>
                        <td className="num border border-line px-3 py-1 text-right">{money(det.in_value)}</td>
                        <td className="num border border-line px-3 py-1 text-right">{qty(det.out_qty)}</td>
                        <td className="num border border-line px-3 py-1 text-right">{money(det.out_value)}</td>
                        <td className="num border border-line px-3 py-1 text-right">{qty(det.balance_qty)}</td>
                        <td className="border border-line px-3 py-1" />
                        <td className="border border-line px-3 py-1" />
                      </tr>
                    ))}
                  </>
                ))}
                <tr className="font-bold">
                  <td className="border border-line px-3 py-2" />
                  <td className="border border-line px-3 py-2 text-right">{t.inventoryReport.total}</td>
                  <td className="num border border-line px-3 py-2 text-right">{qty(report.totals.opening_qty)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{money(report.totals.opening_value)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{qty(report.totals.in_qty)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{money(report.totals.in_value)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{qty(report.totals.out_qty)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{money(report.totals.out_value)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{qty(report.totals.closing_qty)}</td>
                  <td className="num border border-line px-3 py-2 text-right">{money(report.totals.closing_value)}</td>
                  <td className="border border-line px-3 py-2" />
                </tr>
              </tbody>
            </table>
          </div>

          {/* Гарын үсэг */}
          <div className="mt-8 flex flex-col gap-2 text-sm text-ink-soft">
            <div>{t.inventoryReport.preparedBy}: ................................. /............................/</div>
            <div>{t.inventoryReport.checkedBy}: ................................. /............................/</div>
          </div>
        </div>
      ) : null}

      {/* Шүүлтийн цонх */}
      <Modal
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        title={t.inventoryReport.filter}
        size="lg"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <TouchSelect
            label={t.inventoryReport.account}
            value={draft.account_code ?? ANY}
            onChange={(v) => setDraft((d) => ({ ...d, account_code: v === ANY ? null : v }))}
            options={[
              { value: ANY, label: t.common.all },
              ...(options?.accounts ?? []).map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` })),
            ]}
            columns={1}
          />

          <TouchSelect
            label={t.inventoryReport.location}
            value={(draft.tank_id as string) ?? ANY}
            onChange={(v) => setDraft((d) => ({ ...d, tank_id: v === ANY ? null : (v as never) }))}
            options={[
              { value: ANY, label: t.common.all },
              ...(options?.locations ?? []).map((l) => ({ value: l.id as string, label: l.name })),
            ]}
            columns={1}
          />

          <TouchSelect
            label={t.inventoryReport.fuel}
            value={(draft.fuel_id as string) ?? ANY}
            onChange={(v) => setDraft((d) => ({ ...d, fuel_id: v === ANY ? null : (v as never) }))}
            options={[
              { value: ANY, label: t.common.all },
              ...(options?.fuels ?? []).map((f) => ({ value: f.id as string, label: `${f.code} — ${f.name}` })),
            ]}
            columns={2}
          />

          <TouchSelect
            label={t.inventoryReport.category}
            value={(draft.category_id as string) ?? ANY}
            onChange={(v) => setDraft((d) => ({ ...d, category_id: v === ANY ? null : (v as never) }))}
            options={[
              { value: ANY, label: t.common.all },
              ...(options?.categories ?? []).map((c) => ({ value: c.id as string, label: c.name })),
            ]}
            columns={1}
          />

          <TouchSelect
            label={t.inventoryReport.groupBy}
            value={draft.group_by ?? "account_location_item"}
            onChange={(v) => setDraft((d) => ({ ...d, group_by: v }))}
            options={(options?.group_by ?? []).map((g) => ({ value: g.code, label: g.name }))}
            columns={2}
          />

          <TouchSelect
            label={t.inventoryReport.txType}
            value={draft.tx_type ?? "all"}
            onChange={(v) => setDraft((d) => ({ ...d, tx_type: v }))}
            options={(options?.tx_types ?? []).map((x) => ({ value: x.code, label: x.name }))}
            columns={3}
          />

          <DateField
            label={t.inventoryReport.dateFrom}
            value={draft.date_from}
            onChange={(v) => setDraft((d) => ({ ...d, date_from: v }))}
          />
          <DateField
            label={t.inventoryReport.dateTo}
            value={draft.date_to}
            onChange={(v) => setDraft((d) => ({ ...d, date_to: v }))}
          />

          <div className="md:col-span-2">
            <TextField
              label={t.inventoryReport.noteSearch}
              value={draft.note_search ?? ""}
              onChange={(v) => setDraft((d) => ({ ...d, note_search: v || null }))}
              placeholder="—"
            />
          </div>

          <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 border-line bg-surface px-4">
            <input
              type="checkbox"
              checked={draft.include_details ?? false}
              onChange={(e) => setDraft((d) => ({ ...d, include_details: e.target.checked }))}
              className="h-6 w-6 accent-action"
            />
            <span className="text-sm font-medium text-ink">{t.inventoryReport.showDetails}</span>
          </label>

          <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 border-line bg-surface px-4">
            <input
              type="checkbox"
              checked={!(draft.skip_empty ?? true)}
              onChange={(e) => setDraft((d) => ({ ...d, skip_empty: !e.target.checked }))}
              className="h-6 w-6 accent-action"
            />
            <span className="text-sm font-medium text-ink">{t.inventoryReport.keepEmpty}</span>
          </label>

          <div className="flex gap-3 md:col-span-2">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setFilterOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button size="lg" className="flex-1" onClick={apply}>
              {t.inventoryReport.run}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default InventoryReportPage;
