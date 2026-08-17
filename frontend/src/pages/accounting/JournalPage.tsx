/**
 * Ерөнхий журнал (WP12) — бичилтийн жагсаалт, мөрийн задаргаа, гар бичилт.
 *
 * Сервер: `/api/accounting/journal`, `/api/accounting/manual-entries`.
 */

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, Trash2, X } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  accountingKeys,
  useAccounts,
  useCreateManualEntryMutation,
  useJournal,
} from "../../api/queries/accounting";
import { useCustomers } from "../../api/queries/partners";
import { useFuels } from "../../api/queries/fuels";
import { useSuppliers } from "../../api/queries/procurement";
import { useTanks } from "../../api/queries/tanks";
import type { JournalEntry, JournalLine, ManualEntryLineInput, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, rangeFor, type DateRange } from "../../components/ui/DateRangePicker";
import { Modal } from "../../components/ui/Modal";
import { NumPad } from "../../components/ui/NumPad";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar, type TabItem } from "../../components/ui/TabBar";
import { usePermission } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import type { Tone } from "../../lib/constants";
import { PAGE_SIZE } from "../../lib/constants";
import { dIsZero, dSub, dSum, toDisplay } from "../../lib/decimal";
import { formatDate, formatDateTime, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";

type SourceFilter = "all" | string;

const SOURCE_TYPE_MN: Record<string, string> = {
  sale: t.sales.sale,
  fuel_receipt: t.procurement.fuelReceipt,
  purchase: t.procurement.purchase,
  ap_payment: t.procurement.apPayment,
  ar_payment: t.partners.arPayment,
  shift: t.shift.title,
  refund: t.refunds.refund,
  manual: t.accounting.manualEntry,
  settlement: t.accounting.settlement,
};

const SOURCE_TONE: Record<string, Tone> = {
  sale: "success",
  fuel_receipt: "action",
  purchase: "action",
  ap_payment: "warning",
  ar_payment: "warning",
  shift: "neutral",
  refund: "danger",
  manual: "brand",
  settlement: "action",
};

const SOURCE_TABS: readonly TabItem<SourceFilter>[] = [
  { value: "all", label: t.common.all },
  ...Object.keys(SOURCE_TYPE_MN).map((key) => ({ value: key, label: SOURCE_TYPE_MN[key] })),
];

function sourceName(code: string): string {
  return SOURCE_TYPE_MN[code] ?? code;
}

function entryTotal(entry: JournalEntry): string {
  return dSum(entry.lines.map((line) => line.debit));
}

// --------------------------------------------------------------------------
// NumPad-аар дүн оруулах жижиг талбар (гараас бичихгүй)
// --------------------------------------------------------------------------

function MoneyField({
  label,
  value,
  onChange,
  tone = "action",
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  tone?: "action" | "warning";
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");

  const start = (): void => {
    setDraft(dIsZero(value) ? "" : value);
    setOpen(true);
  };

  const commit = (): void => {
    onChange(toDisplay(draft === "" ? "0" : draft));
    setOpen(false);
  };

  return (
    <>
      <button
        type="button"
        onClick={start}
        aria-label={label}
        className={[
          "num h-12 w-full rounded-xl border px-3 text-right text-[15px] font-semibold transition-colors",
          dIsZero(value)
            ? "border-line-strong bg-white text-ink-faint"
            : tone === "warning"
              ? "border-warning bg-warning-soft text-warning-dark"
              : "border-action bg-action-soft text-action-dark",
        ].join(" ")}
      >
        {formatMoneyExact(value, false)}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={label} size="sm">
        <NumPad
          value={draft}
          onChange={setDraft}
          onSubmit={commit}
          onCancel={() => setOpen(false)}
          suffix={t.units.mnt}
          label={label}
        />
      </Modal>
    </>
  );
}

// --------------------------------------------------------------------------
// Гар бичилтийн цонх
// --------------------------------------------------------------------------

interface DraftLine {
  id: string;
  account_code: string;
  debit: string;
  credit: string;
  memo: string;
}

let lineSeq = 0;

function newLine(): DraftLine {
  lineSeq += 1;
  return { id: `line-${lineSeq}`, account_code: "", debit: "0.00", credit: "0.00", memo: "" };
}

function ManualEntryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const accountsQuery = useAccounts(true);
  const mutation = useCreateManualEntryMutation();

  const [entryDate, setEntryDate] = useState(todayInput);
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<DraftLine[]>(() => [newLine(), newLine()]);

  const totalDebit = dSum(lines.map((line) => line.debit));
  const totalCredit = dSum(lines.map((line) => line.credit));
  const difference = dSub(totalDebit, totalCredit);
  const balanced = dIsZero(difference);

  const filled = lines.filter((line) => line.account_code !== "" && !(dIsZero(line.debit) && dIsZero(line.credit)));
  const bothSides = lines.some((line) => !dIsZero(line.debit) && !dIsZero(line.credit));
  const canSubmit =
    balanced &&
    !bothSides &&
    filled.length >= 2 &&
    description.trim() !== "" &&
    !dIsZero(totalDebit) &&
    !mutation.isPending;

  const update = (id: string, patch: Partial<DraftLine>): void => {
    setLines((current) => current.map((line) => (line.id === id ? { ...line, ...patch } : line)));
  };

  const reset = (): void => {
    setEntryDate(todayInput());
    setDescription("");
    setLines([newLine(), newLine()]);
  };

  const submit = (): void => {
    const payload: ManualEntryLineInput[] = filled.map((line) => ({
      account_code: line.account_code,
      debit: line.debit,
      credit: line.credit,
      memo: line.memo.trim() === "" ? null : line.memo.trim(),
    }));

    mutation.mutate(
      { entry_date: entryDate, description: description.trim(), lines: payload },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          void queryClient.invalidateQueries({ queryKey: accountingKeys.all });
          reset();
          onClose();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  const inputClass =
    "h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none";

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title={t.accounting.newManualEntry}
      subtitle={t.accounting.manualEntry}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="success"
            size="lg"
            onClick={submit}
            disabled={!canSubmit}
            loading={mutation.isPending}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[12rem_1fr]">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
              {t.accounting.entryDate}
            </span>
            <input
              type="date"
              value={entryDate}
              onChange={(event) => setEntryDate(event.target.value)}
              className={`num ${inputClass}`}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
              {t.accounting.description}
            </span>
            <input
              type="text"
              value={description}
              maxLength={255}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t.accounting.description}
              className={inputClass}
            />
          </label>
        </div>

        {/* Мөрүүд */}
        <div className="flex flex-col gap-3">
          {lines.map((line, index) => (
            <div
              key={line.id}
              className="grid grid-cols-1 gap-2 rounded-xl border border-line bg-surface-alt p-3 sm:grid-cols-[1fr_9rem_9rem_2.5rem]"
            >
              <div className="flex flex-col gap-2">
                <select
                  value={line.account_code}
                  onChange={(event) => update(line.id, { account_code: event.target.value })}
                  aria-label={t.accounting.account}
                  className={inputClass}
                >
                  <option value="">{`${t.common.select} — ${t.accounting.account}`}</option>
                  {(accountsQuery.data ?? []).map((account) => (
                    <option key={account.id} value={account.code}>
                      {`${account.code} · ${account.name_mn}`}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={line.memo}
                  maxLength={255}
                  onChange={(event) => update(line.id, { memo: event.target.value })}
                  placeholder={t.accounting.memo}
                  className={inputClass}
                />
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
                  {t.accounting.debit}
                </span>
                <MoneyField
                  label={`${t.accounting.debit} ${index + 1}`}
                  value={line.debit}
                  onChange={(next) => update(line.id, { debit: next, credit: "0.00" })}
                />
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
                  {t.accounting.credit}
                </span>
                <MoneyField
                  label={`${t.accounting.credit} ${index + 1}`}
                  value={line.credit}
                  tone="warning"
                  onChange={(next) => update(line.id, { credit: next, debit: "0.00" })}
                />
              </div>

              <button
                type="button"
                onClick={() => setLines((current) => (current.length <= 2 ? current : current.filter((item) => item.id !== line.id)))}
                disabled={lines.length <= 2}
                aria-label={t.common.delete}
                className="flex h-12 w-full items-center justify-center rounded-xl border border-line-strong bg-white text-danger-dark disabled:opacity-40 sm:mt-5 sm:w-12"
              >
                <Trash2 className="h-5 w-5" />
              </button>
            </div>
          ))}

          <Button
            variant="secondary"
            size="md"
            block
            icon={<Plus className="h-5 w-5" />}
            onClick={() => setLines((current) => [...current, newLine()])}
          >
            {t.procurement.addLine}
          </Button>
        </div>

        {/* Шууд харагдах Дт/Кт зөрүү */}
        <div
          className={[
            "grid grid-cols-3 gap-3 rounded-xl border px-4 py-3",
            balanced && !dIsZero(totalDebit)
              ? "border-success/40 bg-success-soft"
              : "border-danger/40 bg-danger-soft",
          ].join(" ")}
        >
          <div>
            <div className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
              {t.accounting.totalDebit}
            </div>
            <div className="num text-xl font-bold text-ink">{formatMoneyExact(totalDebit)}</div>
          </div>
          <div>
            <div className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
              {t.accounting.totalCredit}
            </div>
            <div className="num text-xl font-bold text-ink">{formatMoneyExact(totalCredit)}</div>
          </div>
          <div>
            <div className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
              {t.accounting.imbalance}
            </div>
            <div
              className={`num text-xl font-bold ${balanced ? "text-success-dark" : "text-danger-dark"}`}
            >
              {formatMoneyExact(difference)}
            </div>
          </div>
        </div>

        {bothSides ? (
          <p className="text-sm font-semibold text-danger-dark">
            Нэг мөрөнд дебит ба кредит зэрэг дүнтэй байж болохгүй
          </p>
        ) : null}
        {!balanced ? <p className="text-sm font-semibold text-danger-dark">{t.accounting.unbalanced}</p> : null}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------

export function JournalPage() {
  const { can } = usePermission();

  const [range, setRange] = useState<DateRange>(() => rangeFor("month"));
  const [source, setSource] = useState<SourceFilter>("all");
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<UUID | null>(null);
  const [manualOpen, setManualOpen] = useState(false);

  const params = {
    date_from: range.from,
    date_to: range.to,
    source_type: source === "all" ? undefined : source,
    limit: PAGE_SIZE,
    offset,
  };

  const journalQuery = useJournal(params);
  const accountsQuery = useAccounts(false);
  const fuelsQuery = useFuels();
  const tanksQuery = useTanks();
  const suppliersQuery = useSuppliers({ limit: 200 });
  const customersQuery = useCustomers({ limit: 200 });

  const accountNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const account of accountsQuery.data ?? []) map.set(account.code, account.name_mn);
    return map;
  }, [accountsQuery.data]);

  const dimNames = useMemo(() => {
    const fuel = new Map<string, string>();
    const tank = new Map<string, string>();
    const supplier = new Map<string, string>();
    const customer = new Map<string, string>();
    for (const item of fuelsQuery.data?.items ?? []) fuel.set(item.id, item.name_mn);
    for (const item of tanksQuery.data?.items ?? []) tank.set(item.id, item.name);
    for (const item of suppliersQuery.data?.items ?? []) supplier.set(item.id, item.name);
    for (const item of customersQuery.data?.items ?? []) customer.set(item.id, item.name);
    return { fuel, tank, supplier, customer };
  }, [fuelsQuery.data, tanksQuery.data, suppliersQuery.data, customersQuery.data]);

  const entries = journalQuery.data?.items ?? [];
  const total = journalQuery.data?.total ?? 0;
  const expanded = entries.find((entry) => entry.id === expandedId) ?? null;

  const dimTags = (line: JournalLine): string[] => {
    const tags: string[] = [];
    if (line.dim_fuel_id) tags.push(dimNames.fuel.get(line.dim_fuel_id) ?? t.sales.fuel);
    if (line.dim_tank_id) tags.push(dimNames.tank.get(line.dim_tank_id) ?? t.tanks.tank);
    if (line.dim_supplier_id) tags.push(dimNames.supplier.get(line.dim_supplier_id) ?? t.procurement.supplier);
    if (line.dim_customer_id) tags.push(dimNames.customer.get(line.dim_customer_id) ?? t.partners.customer);
    return tags;
  };

  const columns: Column<JournalEntry>[] = [
    {
      key: "entry_no",
      header: t.accounting.entryNo,
      primary: true,
      numeric: true,
      render: (row) => <span className="num font-bold">{`№${row.entry_no}`}</span>,
    },
    {
      key: "date",
      header: t.accounting.entryDate,
      numeric: true,
      render: (row) => formatDate(row.entry_date),
    },
    {
      key: "description",
      header: t.accounting.description,
      render: (row) => <span className="text-ink">{row.description}</span>,
    },
    {
      key: "source",
      header: t.accounting.sourceType,
      render: (row) => (
        <StatusBadge
          size="sm"
          tone={SOURCE_TONE[row.source_type] ?? "neutral"}
          label={sourceName(row.source_type)}
        />
      ),
    },
    {
      key: "lines",
      header: t.accounting.lines,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => String(row.lines.length),
    },
    {
      key: "total",
      header: t.common.total,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(entryTotal(row))}</span>,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.accounting.generalJournal}
        subtitle={`${formatDate(range.from)} — ${formatDate(range.to)} · ${total} ${t.common.rows}`}
        actions={
          can("accounting.manage") ? (
            <Button
              variant="primary"
              size="md"
              icon={<Plus className="h-5 w-5" />}
              onClick={() => setManualOpen(true)}
            >
              {t.accounting.manualEntry}
            </Button>
          ) : null
        }
      >
        <div className="flex flex-col gap-3">
          <DateRangePicker
            value={range}
            onChange={(next) => {
              setRange(next);
              setOffset(0);
              setExpandedId(null);
            }}
          />
          <TabBar
            value={source}
            onChange={(next) => {
              setSource(next);
              setOffset(0);
              setExpandedId(null);
            }}
            items={SOURCE_TABS}
          />
        </div>
      </PageHeader>

      <Card title={t.accounting.generalJournal} flush>
        <DataTable
          columns={columns}
          rows={entries}
          rowKey={(row) => row.id}
          loading={journalQuery.isLoading}
          emptyTitle={t.reports.noData}
          onRowClick={(row) => setExpandedId((current) => (current === row.id ? null : row.id))}
          rowClassName={(row) => (row.id === expandedId ? "bg-action-soft" : "")}
          footer={
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="num text-sm text-ink-soft">
                {`${total === 0 ? 0 : offset + 1}–${Math.min(offset + PAGE_SIZE, total)} / ${total}`}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="md"
                  icon={<ChevronLeft className="h-5 w-5" />}
                  disabled={offset === 0}
                  onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                >
                  {t.common.prev}
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  iconRight={<ChevronRight className="h-5 w-5" />}
                  disabled={offset + PAGE_SIZE >= total}
                  onClick={() => setOffset((current) => current + PAGE_SIZE)}
                >
                  {t.common.next}
                </Button>
              </div>
            </div>
          }
        />
      </Card>

      {expanded ? (
        <Card
          title={`${t.accounting.entryNo}${expanded.entry_no} · ${expanded.description}`}
          subtitle={`${formatDateTime(expanded.created_at)} · ${sourceName(expanded.source_type)} · ${expanded.event_type}`}
          actions={
            <button
              type="button"
              onClick={() => setExpandedId(null)}
              aria-label={t.common.close}
              className="flex h-12 w-12 items-center justify-center rounded-xl text-ink-soft hover:bg-surface-alt active:bg-surface-sunken"
            >
              <X className="h-5 w-5" />
            </button>
          }
        >
          <ul className="flex flex-col divide-y divide-line">
            {expanded.lines.map((line) => {
              const tags = dimTags(line);
              return (
                <li key={line.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5">
                  <span className="num w-8 shrink-0 text-sm text-ink-faint">{line.line_no}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold text-ink">
                      <span className="num mr-2">{line.account_code}</span>
                      {accountNames.get(line.account_code) ?? ""}
                    </span>
                    {line.memo ? <span className="block text-sm text-ink-soft">{line.memo}</span> : null}
                    {tags.length > 0 ? (
                      <span className="mt-1 flex flex-wrap gap-1.5">
                        {tags.map((tag) => (
                          <StatusBadge key={tag} size="sm" tone="neutral" label={tag} />
                        ))}
                      </span>
                    ) : null}
                  </span>
                  <span className="num w-32 shrink-0 text-right text-[15px] font-semibold text-action-dark">
                    {dIsZero(line.debit) ? "" : formatMoneyExact(line.debit, false)}
                  </span>
                  <span className="num w-32 shrink-0 text-right text-[15px] font-semibold text-warning-dark">
                    {dIsZero(line.credit) ? "" : formatMoneyExact(line.credit, false)}
                  </span>
                </li>
              );
            })}
          </ul>

          <div className="mt-3 flex flex-wrap items-center justify-end gap-4 border-t-2 border-line-strong pt-3">
            <span className="text-sm font-bold text-ink-soft">{t.common.total}</span>
            <span className="num w-32 text-right text-lg font-bold text-action-dark">
              {formatMoneyExact(dSum(expanded.lines.map((line) => line.debit)), false)}
            </span>
            <span className="num w-32 text-right text-lg font-bold text-warning-dark">
              {formatMoneyExact(dSum(expanded.lines.map((line) => line.credit)), false)}
            </span>
          </div>
        </Card>
      ) : null}

      {can("accounting.manage") ? (
        <ManualEntryModal open={manualOpen} onClose={() => setManualOpen(false)} />
      ) : null}
    </div>
  );
}

export default JournalPage;
