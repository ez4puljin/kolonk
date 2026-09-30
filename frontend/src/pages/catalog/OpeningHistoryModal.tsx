/**
 * Эхний үлдэгдлийн түүх, засвар — /inventory.
 *
 * Өмнө оруулсан эхний үлдэгдлийн тоо хэмжээ, нэгж өртгийг засна. Засвар нь
 * тэр мөчөөс хойших нөөцийн дэвтрийг дахин тоглуулж дундаж өртөг,
 * борлуулалтын өртөг, ашиг, журналыг бүгдийг дахин боддог тул эхлээд нөлөөг
 * нь урьдчилан харуулж, дараа нь л хадгална.
 */

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ChevronLeft, Pencil, Scale } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import {
  useOpeningFixMutation,
  useOpeningFixPreviewMutation,
  useOpeningRecords,
} from "../../api/queries/inventory";
import type { OpeningFixResult, OpeningRecord } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { dIsZero, dNeg, dToQty, toDisplay } from "../../lib/decimal";
import { formatDate, formatDateTime, formatMNT, formatQty, formatSignedMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { NumberField, PickerField, TextField } from "./_shared";

const T = t.inventory;

export function OpeningHistoryModal({
  open,
  onClose,
  branchId: initialBranchId = "",
}: {
  open: boolean;
  onClose: () => void;
  branchId?: string;
}) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [branchId, setBranchId] = useState(initialBranchId);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<OpeningRecord | null>(null);
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const [note, setNote] = useState("");
  const [impact, setImpact] = useState<OpeningFixResult | null>(null);
  const [impactKey, setImpactKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const branchesQuery = useBranches();
  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  const recordsQuery = useOpeningRecords(
    { branch_id: branchId || undefined, search: search.trim() || undefined },
    open,
  );
  const records = recordsQuery.data ?? [];
  const previewMutation = useOpeningFixPreviewMutation();
  const applyMutation = useOpeningFixMutation();

  useEffect(() => {
    if (!open) return;
    setBranchId(initialBranchId);
    setEditing(null);
    setImpact(null);
    setError(null);
  }, [open, initialBranchId]);

  const startEdit = (row: OpeningRecord): void => {
    setEditing(row);
    setQty(String(dToQty(row.qty)));
    setCost(toDisplay(row.unit_cost));
    setNote("");
    setImpact(null);
    setImpactKey(null);
    setError(null);
  };
  const backToList = (): void => {
    setEditing(null);
    setImpact(null);
    setError(null);
  };

  // Урьдчилан харсан нөлөө одоогийн утгуудынх эсэх — өөрчилсөн бол дахин тооцуулна.
  const inputKey = `${qty}|${cost}`;
  const stale = impact !== null && impactKey !== inputKey;
  const payload = { qty: qty === "" ? "0" : qty, unit_cost: cost === "" ? "0" : cost };

  const runPreview = (): void => {
    if (!editing) return;
    setError(null);
    previewMutation.mutate(
      { txId: editing.id, payload },
      {
        onSuccess: (data) => {
          setImpact(data);
          setImpactKey(inputKey);
        },
        onError: (cause) => {
          setImpact(null);
          setError(errorMessage(cause));
        },
      },
    );
  };

  const runApply = (): void => {
    if (!editing || !impact || stale) return;
    setError(null);
    applyMutation.mutate(
      { txId: editing.id, payload: { ...payload, note: note.trim() || null } },
      {
        onSuccess: () => {
          toastSuccess(T.openingApplied);
          backToList();
        },
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  const footer = editing ? (
    <>
      <Button variant="secondary" size="md" icon={<ChevronLeft />} onClick={backToList}>
        {T.openingBack}
      </Button>
      <Button
        variant="secondary"
        size="md"
        icon={<Scale />}
        loading={previewMutation.isPending}
        onClick={runPreview}
      >
        {T.openingPreview}
      </Button>
      <Button
        variant="primary"
        size="md"
        disabled={!impact || stale}
        loading={applyMutation.isPending}
        onClick={runApply}
      >
        {T.openingApply}
      </Button>
    </>
  ) : (
    <Button variant="secondary" size="md" onClick={onClose}>
      {t.common.close}
    </Button>
  );

  return (
    <Modal open={open} onClose={onClose} size="lg" title={T.openingFixTitle} subtitle={T.openingFixHint} footer={footer}>
      {editing ? (
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-line px-4 py-3">
            <span className="block text-base font-bold text-ink">{editing.product_name}</span>
            <span className="num block text-xs text-ink-soft">
              {[
                editing.branch_name,
                `${T.openingAsOf}: ${formatDate(editing.as_of)}`,
                formatDateTime(editing.entered_at),
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
            <span className="num mt-1 block text-sm text-ink">
              {T.openingCurrent}: {formatQty(editing.qty, editing.unit)} × {formatMNT(editing.unit_cost)} ={" "}
              <b>{formatMNT(editing.value)}</b>
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <NumberField
              name="opening-fix-qty"
              label={T.openingNewQty}
              value={qty}
              onChange={setQty}
              maxDecimals={3}
              suffix={editing.unit ?? undefined}
            />
            <NumberField
              name="opening-fix-cost"
              label={T.openingNewCost}
              value={cost}
              onChange={setCost}
              maxDecimals={2}
              suffix={t.units.mnt}
            />
          </div>
          <TextField label={T.openingNote} value={note} onChange={setNote} />

          {impact ? <Impact data={impact} /> : <p className="text-sm text-ink-soft">{T.openingPreviewFirst}</p>}
          {stale ? (
            <p className="rounded-xl bg-warning-soft px-4 py-2.5 text-sm font-medium text-warning-dark">
              {T.openingPreviewStale}
            </p>
          ) : null}
          {error ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
          ) : null}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {branches.length > 1 ? (
              <PickerField
                label={t.branches.title}
                value={branchId}
                onChange={setBranchId}
                options={[
                  { value: "", label: t.branches.allBranches },
                  ...branches.map((branch) => ({ value: branch.id, label: branch.name })),
                ]}
              />
            ) : null}
            <TextField label={t.common.search} value={search} onChange={setSearch} />
          </div>

          {recordsQuery.isLoading ? (
            <div className="flex justify-center py-10 text-ink-soft">
              <Spinner label={t.common.loading} />
            </div>
          ) : records.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-soft">{T.openingFixEmpty}</p>
          ) : (
            <div className="flex max-h-[52vh] flex-col divide-y divide-line overflow-y-auto rounded-xl border border-line">
              {records.map((row) => (
                <div key={row.id} className="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center sm:gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="text-[15px] font-semibold text-ink">{row.product_name}</span>
                      {row.source === "product" ? (
                        <StatusBadge size="sm" tone="neutral" label={T.openingFromProduct} />
                      ) : null}
                      {row.corrections > 0 ? (
                        <StatusBadge
                          size="sm"
                          tone="warning"
                          label={T.openingCorrected.replace("{n}", String(row.corrections))}
                        />
                      ) : null}
                    </span>
                    <span className="num block text-xs text-ink-soft">
                      {[
                        row.sku,
                        row.branch_name,
                        `${T.openingAsOf}: ${formatDate(row.as_of)}`,
                        row.entered_by ? `${T.openingEnteredBy}: ${row.entered_by}` : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                  <span className="num shrink-0 text-left sm:text-right">
                    <span className="block text-[15px] font-semibold text-ink">
                      {formatQty(row.qty, row.unit)} × {formatMNT(row.unit_cost)}
                    </span>
                    <span className="block text-xs text-ink-soft">{formatMNT(row.value)}</span>
                  </span>
                  {row.editable ? (
                    <Button variant="secondary" size="md" icon={<Pencil />} onClick={() => startEdit(row)}>
                      {T.openingEdit}
                    </Button>
                  ) : (
                    <span className="text-xs text-ink-faint">{T.openingNotEditable}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function ImpactRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-t border-line pt-2 first:border-t-0 first:pt-0 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
      <span className="text-sm text-ink-soft">{label}</span>
      <span className="num text-sm font-semibold text-ink sm:text-right">{children}</span>
    </div>
  );
}

/** Засварын нөлөө — юу хэрхэн өөрчлөгдөхийг нэг дор. */
function Impact({ data }: { data: OpeningFixResult }) {
  const nothing =
    dIsZero(data.value_change) &&
    data.stock.length === 0 &&
    data.avg_cost.length === 0 &&
    data.sales_count === 0 &&
    data.journal_entries === 0;
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-alt px-4 py-3">
      <span className="text-xs font-bold tracking-wide text-ink-soft uppercase">{T.impactTitle}</span>
      {nothing ? <p className="text-sm text-ink-soft">{T.impactNone}</p> : null}
      <ImpactRow label={T.impactValue}>
        {formatMNT(data.old_value)} → {formatMNT(data.new_value)} ({formatSignedMNT(data.value_change)})
      </ImpactRow>
      {data.stock.length > 0 ? (
        <ImpactRow label={T.impactStock}>
          {data.stock.map((row) => (
            <span key={`${row.product_id}-${row.branch_id ?? "all"}`} className="block">
              {row.product_name}
              {row.branch_name ? ` · ${row.branch_name}` : ""}: {formatQty(row.before, row.unit)} →{" "}
              {formatQty(row.after, row.unit)}
            </span>
          ))}
        </ImpactRow>
      ) : null}
      {data.avg_cost.length > 0 ? (
        <ImpactRow label={T.impactAvg}>
          {data.avg_cost.map((row) => (
            <span key={row.product_id} className="block">
              {row.product_name}: {formatMNT(row.before)} → {formatMNT(row.after)}
            </span>
          ))}
        </ImpactRow>
      ) : null}
      {data.sales_count > 0 ? (
        <ImpactRow label={T.impactSales}>
          {T.impactSalesRow
            .replace("{n}", String(data.sales_count))
            .replace("{cogs}", formatSignedMNT(data.cogs_change))
            .replace("{profit}", formatSignedMNT(dNeg(data.cogs_change)))}
        </ImpactRow>
      ) : null}
      {data.refunds_count > 0 ? (
        <ImpactRow label={T.impactRefunds}>
          {T.impactCount.replace("{n}", String(data.refunds_count))} · {formatSignedMNT(data.refund_cogs_change)}
        </ImpactRow>
      ) : null}
      {data.adjustments_count > 0 ? (
        <ImpactRow label={T.impactAdjustments}>
          {T.impactCount.replace("{n}", String(data.adjustments_count))} ·{" "}
          {formatSignedMNT(data.adjustment_value_change)}
        </ImpactRow>
      ) : null}
      {data.transfers_count > 0 ? (
        <ImpactRow label={T.impactTransfers}>{T.impactCount.replace("{n}", String(data.transfers_count))}</ImpactRow>
      ) : null}
      {data.conversions_count > 0 ? (
        <ImpactRow label={T.impactConversions}>
          {T.impactCount.replace("{n}", String(data.conversions_count))}
        </ImpactRow>
      ) : null}
      {data.journal_entries > 0 ? (
        <ImpactRow label={T.impactJournal}>{T.impactCount.replace("{n}", String(data.journal_entries))}</ImpactRow>
      ) : null}
      {data.shift_count > 0 ? (
        <ImpactRow label={T.impactShifts}>
          {T.impactShiftsRow
            .replace("{n}", String(data.shift_count))
            .replace("{closed}", String(data.shifts_closed))
            .replace("{approved}", String(data.shifts_approved))}
          <span className="block text-xs font-normal text-ink-soft">
            {data.shift_numbers.map((n) => `№${n}`).join(", ")}
          </span>
        </ImpactRow>
      ) : null}
      {data.date_from ? (
        <ImpactRow label={T.impactPeriod}>
          {formatDate(data.date_from)}
          {data.date_to && data.date_to !== data.date_from ? ` – ${formatDate(data.date_to)}` : ""}
        </ImpactRow>
      ) : null}
      {data.warnings.map((warning) => (
        <p
          key={warning}
          className="flex gap-2 rounded-lg bg-warning-soft px-3 py-2 text-sm font-medium text-warning-dark"
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {warning}
        </p>
      ))}
    </div>
  );
}

export default OpeningHistoryModal;
