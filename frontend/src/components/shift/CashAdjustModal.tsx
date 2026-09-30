/**
 * Админы гар засвар — өмнөх системийн алдаанаас үүссэн кассын зөрүү.
 *
 * Нэг ээлжийн (CashAdjustModal) болон сонгосон олон ээлжийн (CashAdjustBulkModal)
 * жинхэнэ илүүдэл/дутагдлыг тогтооно. Засвар = системийн тооцоолсон зөрүү −
 * жинхэнэ зөрүү; кассын дутагдал/илүүдлээс тусдаа «4902 Борлуулалтын
 * залруулга» дансаар журналд бичигдэж, аудитад үлдэнэ. Зөвхөн «Admin» эрх.
 */

import { useState } from "react";
import { AlertTriangle, RotateCcw, Wrench } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useCashAdjustBulkMutation,
  useCashAdjustClearMutation,
  useCashAdjustment,
  useCashAdjustMutation,
} from "../../api/queries/shifts";
import type { DailyClosingRow, MoneyStr, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { dCmp, dIsZero, dNeg, dSub, toDisplay } from "../../lib/decimal";
import { formatDateTime, formatMoneyExact, formatSignedMNT } from "../../lib/format";
import { ChipGroup, NumberField, TextField } from "../../pages/catalog/_shared";
import { useUiStore } from "../../stores/ui";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";

const T = t.cashAdjust;

type TargetMode = "zero" | "client" | "custom";

function toneOf(value: MoneyStr | null | undefined): string {
  const cmp = dCmp(value ?? "0", "0");
  return cmp < 0 ? "text-danger-dark" : cmp > 0 ? "text-warning-dark" : "text-success-dark";
}

function Line({ label, value, strong, tone }: { label: string; value: string; strong?: boolean; tone?: string }) {
  return (
    <div className="num flex items-baseline justify-between gap-3 py-0.5 text-[15px]">
      <span className={strong ? "font-bold text-ink" : "text-ink-soft"}>{label}</span>
      <span className={`${strong ? "text-lg font-black" : "font-semibold"} ${tone ?? "text-ink"}`}>{value}</span>
    </div>
  );
}

// --------------------------------------------------------------------------
// Нэг ээлж
// --------------------------------------------------------------------------
export function CashAdjustModal({
  shiftId,
  open,
  onClose,
  subtitle,
}: {
  shiftId: UUID | null;
  open: boolean;
  onClose: () => void;
  subtitle?: string;
}) {
  const info = useCashAdjustment(shiftId, open);
  const save = useCashAdjustMutation();
  const clear = useCashAdjustClearMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [ready, setReady] = useState<string | null>(null);
  const [mode, setMode] = useState<TargetMode>("zero");
  const [sign, setSign] = useState<"short" | "over">("short");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const data = info.data;
  // Цонх нээгдэж өгөгдөл ирэх бүрд: түгээгчийн дэлгэцийн зөрүү хадгалагдсан бол түүгээр.
  const readyKey = open && data ? `${data.shift_id}` : null;
  if (readyKey !== ready) {
    setReady(readyKey);
    if (readyKey && data) {
      setMode(data.client_diff != null ? "client" : "zero");
      setSign("short");
      setAmount("");
      setNote(data.note ?? "");
      setError(null);
    }
  }

  const custom = sign === "short" ? dNeg(amount === "" ? "0" : amount) : toDisplay(amount === "" ? "0" : amount);
  const target: MoneyStr =
    mode === "zero" ? "0.00" : mode === "client" ? toDisplay(data?.client_diff ?? "0") : custom;
  const adjustment = data ? dSub(data.raw_over_short, target) : "0";
  const noteOk = note.trim().length >= 3;
  const busy = save.isPending || clear.isPending;

  const submit = (): void => {
    if (!shiftId || !data) return;
    setError(null);
    save.mutate(
      { shiftId, target_over_short: target, note: note.trim() },
      {
        onSuccess: () => {
          toastSuccess(T.saved);
          onClose();
        },
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  const remove = (): void => {
    if (!shiftId) return;
    setError(null);
    clear.mutate(
      { shiftId, note: note.trim() || null },
      {
        onSuccess: () => {
          toastSuccess(T.cleared);
          onClose();
        },
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  return (
    <Modal
      open={open && shiftId !== null}
      onClose={onClose}
      size="md"
      title={T.title}
      subtitle={subtitle ?? (data ? `${t.shift.number}${data.shift_number}` : undefined)}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose} disabled={busy}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Wrench />}
            loading={save.isPending}
            disabled={!data || data.approved || !noteOk}
            onClick={submit}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      {info.isLoading || !data ? (
        <div className="flex justify-center py-8 text-ink-soft">
          {info.isError ? <span className="text-sm text-danger-dark">{errorMessage(info.error)}</span> : <Spinner label={t.common.loading} />}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-soft">{T.hint}</p>

          <div className="rounded-xl border border-line bg-surface-alt px-4 py-3">
            <Line label={t.shift.declaredCash} value={formatMoneyExact(data.declared_cash)} />
            <Line label={T.systemExpected} value={formatMoneyExact(data.raw_expected)} />
            <Line label={T.systemDiff} value={formatSignedMNT(data.raw_over_short)} tone={toneOf(data.raw_over_short)} strong />
            <Line
              label={T.attendantSaw}
              value={data.client_diff != null ? formatSignedMNT(data.client_diff) : T.notSaved}
              tone={data.client_diff != null ? toneOf(data.client_diff) : "text-ink-faint"}
            />
          </div>

          {!dIsZero(data.adjustment) ? (
            <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-action/40 bg-action-soft/40 px-4 py-3 text-sm">
              <span className="min-w-0 flex-1">
                <span className="num block font-bold text-ink">
                  {T.current}: {formatSignedMNT(data.adjustment)} → {T.after}: {formatSignedMNT(data.cash_over_short)}
                </span>
                <span className="block text-ink-soft">
                  {[data.note, data.adjusted_by_name, data.adjusted_at ? formatDateTime(data.adjusted_at) : null]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
              <Button
                variant="secondary"
                size="sm"
                icon={<RotateCcw />}
                loading={clear.isPending}
                disabled={data.approved}
                onClick={remove}
              >
                {T.clear}
              </Button>
            </div>
          ) : null}

          <ChipGroup<TargetMode>
            label={T.targetLabel}
            value={mode}
            onChange={setMode}
            options={[
              { value: "zero", label: T.targetZero },
              ...(data.client_diff != null
                ? [{ value: "client" as const, label: `${T.targetClient} (${formatSignedMNT(data.client_diff)})` }]
                : []),
              { value: "custom", label: T.targetCustom },
            ]}
          />
          {mode === "custom" ? (
            <div className="flex flex-wrap items-end gap-3">
              <ChipGroup<"short" | "over">
                value={sign}
                onChange={setSign}
                options={[
                  { value: "short", label: T.short },
                  { value: "over", label: T.over },
                ]}
              />
              <NumberField
                name="cash-adjust-amount"
                label={T.amount}
                value={amount}
                onChange={setAmount}
                suffix={t.units.mnt}
                className="min-w-[10rem] flex-1"
              />
            </div>
          ) : null}

          <div className="rounded-xl border-2 border-line-strong px-4 py-3">
            <Line label={T.adjustment} value={formatSignedMNT(adjustment)} strong />
            <Line label={T.resultDiff} value={formatSignedMNT(target)} tone={toneOf(target)} />
          </div>

          <TextField label={T.reason} value={note} onChange={setNote} maxLength={1000} hint={T.reasonHint} />
          <p className="text-xs text-ink-soft">{T.journalHint}</p>

          {data.approved ? (
            <p className="flex gap-2 rounded-xl bg-warning-soft px-4 py-3 text-sm font-medium text-warning-dark">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              {T.approvedLocked}
            </p>
          ) : null}
          {error ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
          ) : null}
        </div>
      )}
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Сонгосон олон ээлж
// --------------------------------------------------------------------------
export function CashAdjustBulkModal({
  rows,
  open,
  onClose,
  onDone,
}: {
  rows: DailyClosingRow[];
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const bulk = useCashAdjustBulkMutation();
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const [mode, setMode] = useState<"zero" | "client">("zero");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const withClient = rows.filter((row) => row.client_diff != null).length;

  const submit = (): void => {
    setError(null);
    bulk.mutate(
      { shift_ids: rows.map((row) => row.shift_id), mode, note: note.trim() },
      {
        onSuccess: (result) => {
          toastSuccess(
            T.bulkDone
              .replace("{n}", String(result.adjusted.length))
              .replace("{m}", String(result.skipped.length)),
          );
          setNote("");
          onDone();
          onClose();
        },
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={T.bulkTitle.replace("{n}", String(rows.length))}
      subtitle={T.bulkHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose} disabled={bulk.isPending}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Wrench />}
            loading={bulk.isPending}
            disabled={rows.length === 0 || note.trim().length < 3}
            onClick={submit}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <ChipGroup<"zero" | "client">
          label={T.targetLabel}
          value={mode}
          onChange={setMode}
          options={[
            { value: "zero", label: T.targetZero },
            { value: "client", label: `${T.targetClient} (${withClient}/${rows.length})` },
          ]}
        />
        {mode === "client" && withClient < rows.length ? (
          <p className="text-xs text-ink-soft">{T.bulkClientSkip}</p>
        ) : null}
        <div className="flex max-h-[34vh] flex-col divide-y divide-line overflow-y-auto rounded-xl border border-line">
          {rows.map((row) => {
            const target = mode === "zero" ? "0" : row.client_diff;
            return (
              <div key={row.shift_id} className="num flex items-baseline justify-between gap-3 px-3 py-2 text-sm">
                <span className="min-w-0 truncate text-ink">
                  {row.date} · {row.attendant} · {t.shift.number}
                  {row.shift_number}
                </span>
                <span className="shrink-0">
                  <span className={toneOf(row.cash_over_short)}>{formatSignedMNT(row.cash_over_short ?? "0")}</span>
                  {" → "}
                  {target != null ? (
                    <span className={toneOf(target)}>{formatSignedMNT(target)}</span>
                  ) : (
                    <span className="text-ink-faint">{T.skip}</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
        <TextField label={T.reason} value={note} onChange={setNote} maxLength={1000} hint={T.reasonHint} />
        <p className="text-xs text-ink-soft">{T.journalHint}</p>
        {error ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
        ) : null}
      </div>
    </Modal>
  );
}

export default CashAdjustModal;
