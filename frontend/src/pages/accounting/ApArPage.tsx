/**
 * Өглөг, авлага (WP12) — насжилтын бүлэг, үлдэгдэл, төлөлт/хүлээн авалт,
 * гэрээний тооцоо нийлэх акт.
 *
 * Сервер: `/api/ap-invoices`, `/api/ap-payments`, `/api/ar-invoices`,
 * `/api/ar-payments`, `/api/contracts/{id}/statement`.
 */

import { useMemo, useState } from "react";
import { FileText, Plus, Wallet } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useApInvoices,
  useCreateApInvoiceMutation,
  useCreateApPaymentMutation,
} from "../../api/queries/accounting";
import { useBankAccounts } from "../../api/queries/bank";
import { useExpenseCategories } from "../../api/queries/expenses";
import {
  useArInvoices,
  useContracts,
  useContractStatement,
  useCreateArChargeMutation,
  useCreateArPaymentMutation,
} from "../../api/queries/partners";
import { useSuppliers } from "../../api/queries/procurement";
import type { ApInvoice, ArInvoice, CashAccount, Contract, StatementRow, UUID } from "../../api/types";
import { PickerField } from "../catalog/_shared";
import { BarChart, type BarDatum } from "../../components/charts/BarChart";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { Modal } from "../../components/ui/Modal";
import { NumPad } from "../../components/ui/NumPad";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar, type TabItem } from "../../components/ui/TabBar";
import { TouchSelect } from "../../components/ui/TouchSelect";
import { t } from "../../i18n/mn";
import { INVOICE_STATUS_META, statusMeta } from "../../lib/constants";
import { dAdd, dCmp, dIsZero, dSum, toDisplay } from "../../lib/decimal";
import { formatDate, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";

type AparTab = "ap" | "ar";

const TABS: readonly TabItem<AparTab>[] = [
  { value: "ap", label: t.dashboard.payables },
  { value: "ar", label: t.dashboard.receivables },
];

const BUCKET_LABELS: readonly string[] = ["0–30 хоног", "31–60 хоног", "61–90 хоног", "90+ хоног"];
const BUCKET_COLORS: readonly string[] = ["#10B981", "#F59E0B", "#EA580C", "#EF4444"];

const DAY_MS = 24 * 60 * 60 * 1000;

function daysPast(dueIso: string | null): number {
  if (!dueIso) return 0;
  const due = new Date(`${dueIso}T00:00:00`).getTime();
  if (Number.isNaN(due)) return 0;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.floor((today.getTime() - due) / DAY_MS));
}

function bucketIndex(days: number): number {
  if (days <= 30) return 0;
  if (days <= 60) return 1;
  if (days <= 90) return 2;
  return 3;
}

/** Насжилтын 4 бүлгийн үлдэгдлийг тооцно (мөнгө — string арифметик). */
function agingTotals(rows: readonly { due: string | null; amount: string }[]): string[] {
  const buckets = ["0.00", "0.00", "0.00", "0.00"];
  for (const row of rows) {
    if (dCmp(row.amount, "0") <= 0) continue;
    const index = bucketIndex(daysPast(row.due));
    buckets[index] = dAdd(buckets[index], row.amount);
  }
  return buckets;
}

// --------------------------------------------------------------------------
// NumPad-аар дүн оруулах талбар
// --------------------------------------------------------------------------

function MoneyField({
  label,
  value,
  onChange,
  max,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  max?: string;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setDraft(dIsZero(value) ? "" : value);
          setOpen(true);
        }}
        aria-label={label}
        className="num h-16 w-full rounded-xl border border-action bg-action-soft px-4 text-right text-2xl font-bold text-action-dark"
      >
        {formatMoneyExact(value, false)}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={label} size="sm">
        <NumPad
          value={draft}
          onChange={setDraft}
          onSubmit={() => {
            const next = toDisplay(draft === "" ? "0" : draft);
            onChange(max !== undefined && dCmp(next, max) > 0 ? toDisplay(max) : next);
            setOpen(false);
          }}
          onCancel={() => setOpen(false)}
          suffix={t.units.mnt}
          label={label}
        />
      </Modal>
    </>
  );
}

const CASH_OPTIONS = [
  { value: "bank" as CashAccount, label: t.procurement.bank },
  { value: "cash" as CashAccount, label: t.procurement.cash },
];

// --------------------------------------------------------------------------
// Өглөг төлөх цонх
// --------------------------------------------------------------------------

function ApPaymentModal({ invoice, onClose }: { invoice: ApInvoice | null; onClose: () => void }) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateApPaymentMutation();

  const bankAccounts = useBankAccounts({ active_only: true });

  const [amount, setAmount] = useState("0.00");
  const [paidFrom, setPaidFrom] = useState<CashAccount>("bank");
  const [bankAccountId, setBankAccountId] = useState<UUID | "">("");
  const [paymentDate, setPaymentDate] = useState(todayInput);
  const [note, setNote] = useState("");

  const accountOptions = useMemo(
    () =>
      (bankAccounts.data?.items ?? []).map((account) => ({
        value: account.id,
        label: `${account.bank_name} · ${account.account_number}`,
      })),
    [bankAccounts.data],
  );
  // Анхдагч: шимтгэлийн үндсэн данс, байхгүй бол эхний данс.
  const defaultAccountId = useMemo(() => {
    const items = bankAccounts.data?.items ?? [];
    return items.find((account) => account.is_fee_default)?.id ?? items[0]?.id ?? "";
  }, [bankAccounts.data]);
  const effectiveAccountId = bankAccountId === "" ? defaultAccountId : bankAccountId;

  const due = invoice?.amount_due ?? "0";
  const valid = !dIsZero(amount) && dCmp(amount, due) <= 0 && dCmp(amount, "0") > 0;

  const submit = (): void => {
    if (!invoice) return;
    mutation.mutate(
      {
        ap_invoice_id: invoice.id,
        amount,
        paid_from: paidFrom,
        bank_account_id: paidFrom === "bank" && effectiveAccountId !== "" ? effectiveAccountId : null,
        payment_date: paymentDate,
        note: note.trim() === "" ? null : note.trim(),
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setAmount("0.00");
          setNote("");
          onClose();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open={invoice !== null}
      onClose={onClose}
      size="md"
      title={t.procurement.apPayment}
      subtitle={invoice ? `${invoice.supplier_name ?? ""} · ${invoice.invoice_no}` : undefined}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="success"
            size="lg"
            onClick={submit}
            disabled={!valid}
            loading={mutation.isPending}
          >
            {t.common.confirm}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-xl bg-surface-alt px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.procurement.amountDue}</span>
          <span className="num text-2xl font-bold text-ink">{formatMNT(due)}</span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.amount}
          </span>
          <MoneyField label={t.common.amount} value={amount} onChange={setAmount} max={due} />
          <Button variant="secondary" size="md" block onClick={() => setAmount(toDisplay(due))}>
            {t.procurement.amountDue}
          </Button>
        </div>

        <TouchSelect
          label={t.procurement.payFrom}
          value={paidFrom}
          onChange={setPaidFrom}
          options={CASH_OPTIONS}
          columns={2}
        />

        {paidFrom === "bank" && accountOptions.length > 0 && (
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
              {t.bank.accounts}
            </span>
            <select
              value={effectiveAccountId}
              onChange={(event) => setBankAccountId(event.target.value as UUID)}
              className="h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
            >
              {accountOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.date}
          </span>
          <input
            type="date"
            value={paymentDate}
            onChange={(event) => setPaymentDate(event.target.value)}
            className="num h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.note}
          </span>
          <input
            type="text"
            value={note}
            maxLength={255}
            onChange={(event) => setNote(event.target.value)}
            className="h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Авлага хүлээн авах цонх
// --------------------------------------------------------------------------

/** Авлагын төлбөрийн зорилт — нэхэмжлэхтэй эсвэл гэрээний үлдэгдлээс шууд. */
interface ArPayTarget {
  contract_id: UUID;
  invoice_id?: UUID | null;
  label: string;
  due: string;
}

function ArPaymentModal({ target, onClose }: { target: ArPayTarget | null; onClose: () => void }) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateArPaymentMutation();

  const [amount, setAmount] = useState("0.00");
  const [receivedTo, setReceivedTo] = useState<CashAccount>("bank");
  const [paymentDate, setPaymentDate] = useState(todayInput);
  const [note, setNote] = useState("");

  const due = target?.due ?? "0";
  const valid = dCmp(amount, "0") > 0;

  const submit = (): void => {
    if (!target) return;
    mutation.mutate(
      {
        contract_id: target.contract_id,
        ar_invoice_id: target.invoice_id ?? null,
        amount,
        received_to: receivedTo,
        payment_date: paymentDate,
        note: note.trim() === "" ? null : note.trim(),
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setAmount("0.00");
          setNote("");
          onClose();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open={target !== null}
      onClose={onClose}
      size="md"
      title={t.partners.arPayment}
      subtitle={target?.label}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="success"
            size="lg"
            onClick={submit}
            disabled={!valid}
            loading={mutation.isPending}
          >
            {t.common.confirm}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-xl bg-surface-alt px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.procurement.amountDue}</span>
          <span className="num text-2xl font-bold text-ink">{formatMNT(due)}</span>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.amount}
          </span>
          <MoneyField label={t.common.amount} value={amount} onChange={setAmount} />
          <Button variant="secondary" size="md" block onClick={() => setAmount(toDisplay(due))}>
            {t.procurement.amountDue}
          </Button>
        </div>

        <TouchSelect
          label={t.partners.receivedTo}
          value={receivedTo}
          onChange={setReceivedTo}
          options={CASH_OPTIONS}
          columns={2}
        />

        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.date}
          </span>
          <input
            type="date"
            value={paymentDate}
            onChange={(event) => setPaymentDate(event.target.value)}
            className="num h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            {t.common.note}
          </span>
          <input
            type="text"
            value={note}
            maxLength={255}
            onChange={(event) => setNote(event.target.value)}
            className="h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Авлага гараар үүсгэх (гэрээнд нэмэх / хасах)
// --------------------------------------------------------------------------

function ArChargeModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateArChargeMutation();
  const contractsQuery = useContracts({ limit: 500 });

  const [contractId, setContractId] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [negative, setNegative] = useState(false);
  const [kind, setKind] = useState<"opening" | "income">("opening");
  const [chargeDate, setChargeDate] = useState(todayInput);
  const [note, setNote] = useState("");

  const options = useMemo(
    () =>
      (contractsQuery.data?.items ?? [])
        .filter((contract) => contract.status === "active")
        .map((contract) => ({
          value: contract.id,
          label: `${contract.customer_name ?? "—"} · ${contract.contract_no}`,
          hint: `${t.partners.currentBalance}: ${formatMNT(contract.balance)}`,
        })),
    [contractsQuery.data],
  );
  const selected = (contractsQuery.data?.items ?? []).find((c) => c.id === contractId) ?? null;
  const valid = contractId !== "" && dCmp(amount, "0") > 0;

  const submit = (): void => {
    if (!valid) return;
    mutation.mutate(
      {
        contractId,
        amount: negative ? `-${amount}` : amount,
        charge_date: chargeDate,
        kind,
        note: note.trim() === "" ? null : note.trim(),
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setAmount("0.00");
          setNote("");
          onClose();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={t.partners.arCharge}
      subtitle={t.partners.arChargeHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button variant="success" size="lg" onClick={submit} disabled={!valid} loading={mutation.isPending}>
            {t.common.confirm}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField label={t.partners.contract} value={contractId} options={options} onChange={setContractId} searchable />
        {selected ? (
          <div className="flex items-center justify-between rounded-xl bg-surface-alt px-4 py-3">
            <span className="text-sm font-semibold text-ink-soft">{t.partners.currentBalance}</span>
            <span className="num text-2xl font-bold text-ink">{formatMNT(selected.balance)}</span>
          </div>
        ) : null}
        <TouchSelect<"add" | "sub">
          label={t.common.type}
          value={negative ? "sub" : "add"}
          onChange={(value) => setNegative(value === "sub")}
          options={[
            { value: "add", label: `+ ${t.partners.arCharge}` },
            { value: "sub", label: `− ${t.partners.arChargeAmountHint}` },
          ]}
          columns={2}
        />
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.amount}</span>
          <MoneyField label={t.common.amount} value={amount} onChange={setAmount} />
        </div>
        <TouchSelect<"opening" | "income">
          label={t.partners.arChargeKind}
          value={kind}
          onChange={setKind}
          options={[
            { value: "opening", label: t.partners.arChargeOpening },
            { value: "income", label: t.partners.arChargeIncome },
          ]}
          columns={2}
        />
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.date}</span>
          <input
            type="date"
            value={chargeDate}
            onChange={(event) => setChargeDate(event.target.value)}
            className="num h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.note}</span>
          <input
            type="text"
            value={note}
            maxLength={255}
            onChange={(event) => setNote(event.target.value)}
            className="h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Өглөг гараар үүсгэх (нийлүүлэгчийн нэхэмжлэх)
// --------------------------------------------------------------------------

function ApInvoiceModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateApInvoiceMutation();
  const suppliersQuery = useSuppliers({ limit: 200, active_only: true });
  const categoriesQuery = useExpenseCategories();

  const [supplierId, setSupplierId] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [kind, setKind] = useState<"opening" | "expense">("opening");
  const [accountCode, setAccountCode] = useState("");
  const [invoiceDate, setInvoiceDate] = useState(todayInput);
  const [dueDate, setDueDate] = useState("");
  const [invoiceNo, setInvoiceNo] = useState("");
  const [note, setNote] = useState("");

  const supplierOptions = useMemo(
    () =>
      (suppliersQuery.data?.items ?? []).map((supplier) => ({
        value: supplier.id,
        label: supplier.name,
        hint: supplier.phone ?? undefined,
      })),
    [suppliersQuery.data],
  );
  const accountOptions = useMemo(
    () => (categoriesQuery.data ?? []).map((row) => ({ value: row.code, label: `${row.code} · ${row.name_mn}` })),
    [categoriesQuery.data],
  );
  const valid = supplierId !== "" && dCmp(amount, "0") > 0 && (kind === "opening" || accountCode !== "");

  const submit = (): void => {
    if (!valid) return;
    mutation.mutate(
      {
        supplier_id: supplierId,
        amount,
        invoice_date: invoiceDate,
        due_date: dueDate === "" ? null : dueDate,
        invoice_no: invoiceNo.trim() === "" ? null : invoiceNo.trim(),
        kind,
        expense_account_code: kind === "expense" ? accountCode : null,
        note: note.trim() === "" ? null : note.trim(),
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setAmount("0.00");
          setInvoiceNo("");
          setNote("");
          onClose();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={t.procurement.apCreate}
      subtitle={t.procurement.apCreateHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button variant="success" size="lg" onClick={submit} disabled={!valid} loading={mutation.isPending}>
            {t.common.confirm}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField label={t.procurement.supplier} value={supplierId} options={supplierOptions} onChange={setSupplierId} searchable />
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.amount}</span>
          <MoneyField label={t.common.amount} value={amount} onChange={setAmount} />
        </div>
        <TouchSelect<"opening" | "expense">
          label={t.procurement.apKind}
          value={kind}
          onChange={setKind}
          options={[
            { value: "opening", label: t.procurement.apKindOpening },
            { value: "expense", label: t.procurement.apKindExpense },
          ]}
          columns={2}
        />
        {kind === "expense" ? (
          <PickerField label={t.procurement.apKindExpense} value={accountCode} options={accountOptions} onChange={setAccountCode} searchable />
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.date}</span>
            <input
              type="date"
              value={invoiceDate}
              onChange={(event) => setInvoiceDate(event.target.value)}
              className="num h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.procurement.dueDate}</span>
            <input
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="num h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
            />
          </label>
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.procurement.invoiceNo}</span>
          <input
            type="text"
            value={invoiceNo}
            maxLength={64}
            onChange={(event) => setInvoiceNo(event.target.value)}
            className="h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.common.note}</span>
          <input
            type="text"
            value={note}
            maxLength={255}
            onChange={(event) => setNote(event.target.value)}
            className="h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Тооцоо нийлэх акт
// --------------------------------------------------------------------------

const statementColumns: Column<StatementRow>[] = [
  {
    key: "date",
    header: t.common.date,
    primary: true,
    numeric: true,
    render: (row) => <span className="num font-semibold">{formatDate(row.date)}</span>,
  },
  { key: "kind", header: t.common.status, render: (row) => row.kind_name || row.kind },
  { key: "ref", header: t.common.code, hideOnMobile: true, render: (row) => row.ref ?? "—" },
  { key: "description", header: t.accounting.description, render: (row) => row.description },
  {
    key: "debit",
    header: t.accounting.debit,
    align: "right",
    numeric: true,
    render: (row) => (dIsZero(row.debit) ? "" : formatMoneyExact(row.debit, false)),
  },
  {
    key: "credit",
    header: t.accounting.credit,
    align: "right",
    numeric: true,
    render: (row) => (dIsZero(row.credit) ? "" : formatMoneyExact(row.credit, false)),
  },
  {
    key: "balance",
    header: t.common.balance,
    align: "right",
    numeric: true,
    render: (row) => <span className="font-bold">{formatMNT(row.balance)}</span>,
  },
];

function StatementModal({ contractId, onClose }: { contractId: UUID | null; onClose: () => void }) {
  const statementQuery = useContractStatement(contractId);
  const data = statementQuery.data;

  return (
    <Modal
      open={contractId !== null}
      onClose={onClose}
      size="xl"
      title={t.partners.statement}
      subtitle={data ? `${data.contract.customer_name ?? ""} · ${data.contract.contract_no}` : undefined}
    >
      {statementQuery.isLoading ? (
        <div className="flex justify-center py-16 text-ink-soft">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : data ? (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 min-[520px]:grid-cols-2 xl:grid-cols-4">
            <StatBox label={t.partners.openingBalance} value={formatMNT(data.opening_balance)} />
            <StatBox label={t.partners.salesTotal} value={formatMNT(data.sales_total)} tone="action" />
            <StatBox label={t.partners.paymentsTotal} value={formatMNT(data.payments_total)} tone="success" />
            <StatBox label={t.partners.closingBalance} value={formatMNT(data.closing_balance)} tone="warning" />
          </div>
          <DataTable
            columns={statementColumns}
            rows={data.rows}
            rowKey={(row) => `${row.date ?? ""}-${row.kind}-${row.ref ?? ""}-${row.balance}`}
            emptyTitle={t.reports.noData}
          />
        </div>
      ) : (
        <p className="py-8 text-center text-ink-soft">{t.reports.noData}</p>
      )}
    </Modal>
  );
}

// --------------------------------------------------------------------------

export function ApArPage() {
  const [tab, setTab] = useState<AparTab>("ap");
  const [openOnly, setOpenOnly] = useState(true);
  const [apTarget, setApTarget] = useState<ApInvoice | null>(null);
  const [arTarget, setArTarget] = useState<ArPayTarget | null>(null);
  const [statementContract, setStatementContract] = useState<UUID | null>(null);
  const [arChargeOpen, setArChargeOpen] = useState(false);
  const [apCreateOpen, setApCreateOpen] = useState(false);

  const apQuery = useApInvoices({ limit: 200 });
  const arQuery = useArInvoices({ limit: 200 });
  const contractsQuery = useContracts({ limit: 500 });

  /** Гэрээ бүрийн одоогийн үлдэгдэл — нэхэмжлэхгүй авлага ч энд харагдана. */
  const contractRows = useMemo(() => {
    const items = (contractsQuery.data?.items ?? []).filter((c) => c.status === "active");
    const rows = openOnly ? items.filter((c) => dCmp(c.balance, "0") > 0) : items;
    return [...rows].sort((a, b) => dCmp(b.balance, a.balance));
  }, [contractsQuery.data, openOnly]);
  const arBalanceTotal = useMemo(() => dSum(contractRows.map((c) => c.balance)), [contractRows]);

  /** Нийлүүлэгч бүрийн төлөгдөөгүй нэхэмжлэх. */
  const supplierRows = useMemo(() => {
    const map = new Map<string, { supplier_id: UUID; name: string; count: number; due: string }>();
    for (const invoice of apQuery.data?.items ?? []) {
      if (dCmp(invoice.amount_due, "0") <= 0) continue;
      const entry = map.get(invoice.supplier_id) ?? {
        supplier_id: invoice.supplier_id,
        name: invoice.supplier_name ?? "—",
        count: 0,
        due: "0",
      };
      entry.count += 1;
      entry.due = dAdd(entry.due, invoice.amount_due);
      map.set(invoice.supplier_id, entry);
    }
    return [...map.values()].sort((a, b) => dCmp(b.due, a.due));
  }, [apQuery.data]);

  const apRows = useMemo(() => {
    const items = apQuery.data?.items ?? [];
    return openOnly ? items.filter((invoice) => dCmp(invoice.amount_due, "0") > 0) : items;
  }, [apQuery.data, openOnly]);

  const arRows = useMemo(() => {
    const items = arQuery.data?.items ?? [];
    return openOnly ? items.filter((invoice) => dCmp(invoice.amount_due, "0") > 0) : items;
  }, [arQuery.data, openOnly]);

  const apAging = useMemo(
    () =>
      agingTotals(
        (apQuery.data?.items ?? []).map((invoice) => ({
          due: invoice.due_date ?? invoice.invoice_date,
          amount: invoice.amount_due,
        })),
      ),
    [apQuery.data],
  );

  const arAging = useMemo(
    () =>
      agingTotals(
        (arQuery.data?.items ?? []).map((invoice) => ({
          due: invoice.period_end,
          amount: invoice.amount_due,
        })),
      ),
    [arQuery.data],
  );

  const aging = tab === "ap" ? apAging : arAging;
  const outstanding = dSum(aging);

  const agingBars: BarDatum[] = aging.map((amount, index) => ({
    key: BUCKET_LABELS[index],
    label: BUCKET_LABELS[index],
    value: amount,
    color: BUCKET_COLORS[index],
    display: formatMNT(amount),
  }));

  const apColumns: Column<ApInvoice>[] = [
    {
      key: "supplier",
      header: t.procurement.supplier,
      primary: true,
      render: (row) => <span className="font-bold">{row.supplier_name ?? "—"}</span>,
    },
    { key: "invoice", header: t.procurement.invoiceNo, render: (row) => row.invoice_no },
    {
      key: "date",
      header: t.common.date,
      numeric: true,
      render: (row) => formatDate(row.invoice_date),
    },
    {
      key: "due",
      header: t.procurement.dueDate,
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.due_date ? formatDate(row.due_date) : "—"),
    },
    {
      key: "aging",
      header: t.common.period,
      render: (row) => {
        const index = bucketIndex(daysPast(row.due_date ?? row.invoice_date));
        return (
          <StatusBadge
            size="sm"
            tone={index === 0 ? "success" : index === 3 ? "danger" : "warning"}
            label={BUCKET_LABELS[index]}
          />
        );
      },
    },
    {
      key: "gross",
      header: t.common.gross,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.amount_gross),
    },
    {
      key: "due_amount",
      header: t.procurement.amountDue,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.amount_due)}</span>,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(INVOICE_STATUS_META, row.status)} />,
    },
    {
      key: "action",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        dCmp(row.amount_due, "0") > 0 ? (
          <Button
            variant="primary"
            size="md"
            icon={<Wallet className="h-5 w-5" />}
            onClick={() => setApTarget(row)}
          >
            {t.procurement.apPayment}
          </Button>
        ) : null,
    },
  ];

  const arColumns: Column<ArInvoice>[] = [
    {
      key: "customer",
      header: t.partners.customer,
      primary: true,
      render: (row) => <span className="font-bold">{row.customer_name ?? "—"}</span>,
    },
    { key: "invoice", header: t.procurement.invoiceNo, render: (row) => row.invoice_no },
    {
      key: "contract",
      header: t.partners.contractNo,
      hideOnMobile: true,
      render: (row) => row.contract_no ?? "—",
    },
    {
      key: "period",
      header: t.common.period,
      numeric: true,
      render: (row) => `${formatDate(row.period_start)} — ${formatDate(row.period_end)}`,
    },
    {
      key: "aging",
      header: t.common.status,
      render: (row) => {
        const index = bucketIndex(daysPast(row.period_end));
        return (
          <StatusBadge
            size="sm"
            tone={index === 0 ? "success" : index === 3 ? "danger" : "warning"}
            label={BUCKET_LABELS[index]}
          />
        );
      },
    },
    {
      key: "amount",
      header: t.common.amount,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.amount),
    },
    {
      key: "due_amount",
      header: t.procurement.amountDue,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.amount_due)}</span>,
    },
    {
      key: "action",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <span className="flex flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            size="md"
            icon={<FileText className="h-5 w-5" />}
            onClick={() => setStatementContract(row.contract_id)}
          >
            {t.partners.statement}
          </Button>
          {dCmp(row.amount_due, "0") > 0 ? (
            <Button
              variant="primary"
              size="md"
              icon={<Wallet className="h-5 w-5" />}
              onClick={() =>
                setArTarget({
                  contract_id: row.contract_id,
                  invoice_id: row.id,
                  label: `${row.customer_name ?? ""} · ${row.invoice_no}`,
                  due: row.amount_due,
                })
              }
            >
              {t.partners.arPayment}
            </Button>
          ) : null}
        </span>
      ),
    },
  ];

  const contractColumns: Column<Contract>[] = [
    {
      key: "customer",
      header: t.partners.customer,
      primary: true,
      render: (row) => <span className="font-bold">{row.customer_name ?? "—"}</span>,
    },
    { key: "contract", header: t.partners.contractNo, hideOnMobile: true, render: (row) => row.contract_no },
    {
      key: "opening",
      header: t.partners.openingBalance,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.opening_balance),
    },
    {
      key: "limit",
      header: t.partners.creditLimit,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.credit_limit),
    },
    {
      key: "balance",
      header: t.partners.currentBalance,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.balance)}</span>,
    },
    {
      key: "action",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <span className="flex flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            size="md"
            icon={<FileText className="h-5 w-5" />}
            onClick={() => setStatementContract(row.id)}
          >
            {t.partners.statement}
          </Button>
          {dCmp(row.balance, "0") > 0 ? (
            <Button
              variant="primary"
              size="md"
              icon={<Wallet className="h-5 w-5" />}
              onClick={() =>
                setArTarget({
                  contract_id: row.id,
                  invoice_id: null,
                  label: `${row.customer_name ?? ""} · ${row.contract_no}`,
                  due: row.balance,
                })
              }
            >
              {t.partners.arPayment}
            </Button>
          ) : null}
        </span>
      ),
    },
  ];

  const supplierColumns: Column<(typeof supplierRows)[number]>[] = [
    { key: "supplier", header: t.procurement.supplier, primary: true, render: (row) => <span className="font-bold">{row.name}</span> },
    { key: "count", header: t.procurement.invoiceCount, align: "right", numeric: true, render: (row) => row.count },
    {
      key: "due",
      header: t.procurement.amountDue,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.due)}</span>,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.accounting.apar}
        subtitle={`${t.common.total}: ${formatMNT(tab === "ar" ? arBalanceTotal : outstanding)}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant={openOnly ? "primary" : "secondary"} size="md" onClick={() => setOpenOnly((v) => !v)}>
              {openOnly ? t.status.unpaid : t.common.all}
            </Button>
            {tab === "ap" ? (
              <Button variant="success" size="md" icon={<Plus />} onClick={() => setApCreateOpen(true)}>
                {t.procurement.apCreate}
              </Button>
            ) : (
              <Button variant="success" size="md" icon={<Plus />} onClick={() => setArChargeOpen(true)}>
                {t.partners.arCharge}
              </Button>
            )}
          </div>
        }
      >
        <TabBar variant="underline" value={tab} onChange={setTab} items={TABS} />
      </PageHeader>

      <div className="grid grid-cols-1 gap-3 min-[520px]:grid-cols-2 xl:grid-cols-4">
        {BUCKET_LABELS.map((label, index) => (
          <StatBox
            key={label}
            label={label}
            value={formatMNT(aging[index])}
            tone={index === 0 ? "success" : index === 3 ? "danger" : "warning"}
          />
        ))}
      </div>

      <Card title={t.common.period} subtitle={tab === "ap" ? t.dashboard.payables : t.dashboard.receivables}>
        <BarChart data={agingBars} title={t.common.period} orientation="horizontal" />
      </Card>

      {tab === "ap" ? (
        <>
          <Card title={t.procurement.apBySupplier} subtitle={t.procurement.apBySupplierHint} flush>
            <DataTable
              columns={supplierColumns}
              rows={supplierRows}
              rowKey={(row) => row.supplier_id}
              loading={apQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
          <Card title={t.procurement.apInvoices} subtitle={`${apRows.length} ${t.common.rows}`} flush>
            <DataTable
              columns={apColumns}
              rows={apRows}
              rowKey={(row) => row.id}
              loading={apQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
        </>
      ) : (
        <>
          <Card
            title={t.partners.arByCustomer}
            subtitle={`${t.partners.arByCustomerHint} · ${t.common.total}: ${formatMNT(arBalanceTotal)}`}
            flush
          >
            <DataTable
              columns={contractColumns}
              rows={contractRows}
              rowKey={(row) => row.id}
              loading={contractsQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
          <Card title={t.partners.arInvoices} subtitle={`${arRows.length} ${t.common.rows}`} flush>
            <DataTable
              columns={arColumns}
              rows={arRows}
              rowKey={(row) => row.id}
              loading={arQuery.isLoading}
              emptyTitle={t.reports.noData}
            />
          </Card>
        </>
      )}

      <ApPaymentModal invoice={apTarget} onClose={() => setApTarget(null)} />
      <ArPaymentModal target={arTarget} onClose={() => setArTarget(null)} />
      <ArChargeModal open={arChargeOpen} onClose={() => setArChargeOpen(false)} />
      <ApInvoiceModal open={apCreateOpen} onClose={() => setApCreateOpen(false)} />
      <StatementModal contractId={statementContract} onClose={() => setStatementContract(null)} />
    </div>
  );
}

export default ApArPage;
