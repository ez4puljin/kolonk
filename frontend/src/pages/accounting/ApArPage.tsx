/**
 * Өглөг, авлага (WP12) — насжилтын бүлэг, үлдэгдэл, төлөлт/хүлээн авалт,
 * гэрээний тооцоо нийлэх акт.
 *
 * Сервер: `/api/ap-invoices`, `/api/ap-payments`, `/api/ar-invoices`,
 * `/api/ar-payments`, `/api/contracts/{id}/statement`.
 */

import { useMemo, useState } from "react";
import { FileText, Pencil, Plus, ShoppingBag, Wallet } from "lucide-react";

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
  useCustomerPurchases,
  useCreateArChargeMutation,
  useCreateArPaymentMutation,
  useCustomers,
} from "../../api/queries/partners";
import { useSuppliers } from "../../api/queries/procurement";
import type {
  ApInvoice,
  ArInvoice,
  CashAccount,
  Contract,
  Customer,
  CustomerPurchaseRow,
  StatementRow,
  UUID,
} from "../../api/types";
import { DateField, PickerField } from "../catalog/_shared";
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
import { dAdd, dCmp, dIsZero, dSub, dSum, toDisplay } from "../../lib/decimal";
import { formatDate, formatDateTime, formatLiters, formatMNT, formatMoneyExact, todayInput } from "../../lib/format";
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

/** Авлага үүсгэх сонголтын утга: гэрээтэй бол гэрээний id, гэрээгүй харилцагч бол `u:<customerId>`. */
interface ArChargeTarget {
  contractId?: UUID;
  customerId?: UUID;
}

function targetValue(target: ArChargeTarget | null): string {
  if (!target) return "";
  return target.contractId ?? (target.customerId ? `u:${target.customerId}` : "");
}

function ArChargeModal({
  open,
  target,
  onClose,
}: {
  open: boolean;
  /** Мөрөөс дарж нээхэд урьдчилан сонгогдох харилцагч/гэрээ. */
  target: ArChargeTarget | null;
  onClose: () => void;
}) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateArChargeMutation();
  const customersQuery = useCustomers({ active_only: true, limit: 500 });

  const [picked, setPicked] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [negative, setNegative] = useState(false);
  const [kind, setKind] = useState<"opening" | "income">("opening");
  const [chargeDate, setChargeDate] = useState(todayInput);
  const [note, setNote] = useState("");
  const value = picked !== "" ? picked : targetValue(target);

  /** Бүх идэвхтэй харилцагч — гэрээтэй бол гэрээ бүрээр, гэрээгүй бол харилцагчаар (гэрээ автоматаар нээгдэнэ). */
  const options = useMemo(() => {
    const items = customersQuery.data?.items ?? [];
    const rows: { value: string; label: string; hint: string; balance: string }[] = [];
    for (const customer of items) {
      const active = customer.contracts.filter((c) => c.status === "active");
      if (active.length === 0) {
        rows.push({
          value: `u:${customer.id}`,
          label: `${customer.full_name} · ${t.partners.noContractAuto}`,
          hint: customer.phone ?? "",
          balance: "0.00",
        });
        continue;
      }
      for (const contract of active) {
        rows.push({
          value: contract.id,
          label: `${customer.full_name} · ${contract.contract_no}`,
          hint: `${t.partners.currentBalance}: ${formatMNT(contract.balance)}`,
          balance: contract.balance,
        });
      }
    }
    return rows.sort((a, b) => a.label.localeCompare(b.label));
  }, [customersQuery.data]);
  const selected = options.find((o) => o.value === value) ?? null;
  const valid = value !== "" && dCmp(amount, "0") > 0;

  const close = (): void => {
    setPicked("");
    onClose();
  };

  const submit = (): void => {
    if (!valid) return;
    const ids = value.startsWith("u:") ? { customerId: value.slice(2) } : { contractId: value };
    mutation.mutate(
      {
        ...ids,
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
          close();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={close}
      size="md"
      title={t.partners.arCharge}
      subtitle={t.partners.arChargeHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={close}>
            {t.common.cancel}
          </Button>
          <Button variant="success" size="lg" onClick={submit} disabled={!valid} loading={mutation.isPending}>
            {t.common.confirm}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField label={t.partners.customer} value={value} options={options} onChange={setPicked} searchable />
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

/** Авлагын хүснэгтийн мөр — нэг харилцагч, түүний идэвхтэй гэрээнүүд. */
interface CustomerArRow {
  customer: Customer;
  contracts: Contract[];
  /** Хуулга/төлбөрт ашиглах гэрээ (үлдэгдэл хамгийн их нь). */
  primary: Contract | null;
  opening: string;
  limit: string;
  balance: string;
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

// --------------------------------------------------------------------------
// Харилцагчийн худалдан авалтын түүх
// --------------------------------------------------------------------------

const purchaseColumns: Column<CustomerPurchaseRow>[] = [
  { key: "date", header: t.common.date, primary: true, numeric: true, render: (row) => formatDateTime(row.date) },
  { key: "no", header: t.common.code, hideOnMobile: true, render: (row) => (row.sale_number != null ? `№${row.sale_number}` : "—") },
  { key: "name", header: t.partners.purchaseItem, render: (row) => <span className="font-semibold">{row.name}</span> },
  { key: "qty", header: t.partners.purchaseQty, align: "right", numeric: true, render: (row) => (row.item_type === "fuel" ? formatLiters(row.qty, 3) : toDisplay(row.qty)) },
  { key: "price", header: t.partners.purchaseUnitPrice, align: "right", numeric: true, hideOnMobile: true, render: (row) => formatMNT(row.unit_price) },
  { key: "amount", header: t.common.amount, align: "right", numeric: true, render: (row) => <span className="font-bold">{formatMNT(row.amount)}</span> },
  { key: "methods", header: t.partners.paymentMethods, hideOnMobile: true, render: (row) => row.methods || "—" },
  { key: "contract", header: t.partners.contractNo, hideOnMobile: true, render: (row) => row.contract_no ?? "—" },
];

function PurchasesModal({ customer, onClose }: { customer: Customer | null; onClose: () => void }) {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const query = useCustomerPurchases(customer?.id, dateFrom, dateTo);
  const data = query.data;

  return (
    <Modal
      open={customer !== null}
      onClose={onClose}
      size="xl"
      title={t.partners.purchases}
      subtitle={customer ? `${customer.full_name} · ${t.partners.purchasesHint}` : undefined}
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <DateField label={t.partners.purchaseFrom} value={dateFrom} onChange={setDateFrom} />
          <DateField label={t.partners.purchaseTo} value={dateTo} onChange={setDateTo} />
        </div>
        {query.isLoading ? (
          <div className="flex justify-center py-16 text-ink-soft">
            <Spinner size="lg" label={t.common.loading} />
          </div>
        ) : data ? (
          <>
            <div className="grid grid-cols-1 gap-3 min-[520px]:grid-cols-3">
              <StatBox label={t.partners.purchasesCount} value={data.sales_count} />
              <StatBox label={t.partners.purchasesLiters} value={formatLiters(data.fuel_liters, 1)} tone="action" />
              <StatBox label={t.partners.purchasesTotal} value={formatMNT(data.total)} tone="success" />
            </div>
            <DataTable
              columns={purchaseColumns}
              rows={data.rows}
              rowKey={(row) => `${row.sale_number ?? ""}-${row.name}-${row.amount}-${row.date ?? ""}`}
              emptyTitle={t.reports.noData}
            />
          </>
        ) : (
          <p className="py-8 text-center text-ink-soft">{t.reports.noData}</p>
        )}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Эхний үлдэгдэл засах — зөв дүнг оруулахад зөрүүг залруулга болгож бичнэ
// --------------------------------------------------------------------------

function OpeningFixModal({
  target,
  onClose,
}: {
  target: { customer: Customer; contract: Contract | null } | null;
  onClose: () => void;
}) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateArChargeMutation();
  const [value, setValue] = useState("0.00");
  const [openingDate, setOpeningDate] = useState("");
  const [touched, setTouched] = useState(false);

  const current = target?.contract?.opening_balance ?? "0";
  const balance = target?.contract?.balance ?? "0";
  const shown = touched ? value : toDisplay(current);
  const delta = dSub(shown === "" ? "0" : shown, current);
  const wouldGoNegative = dCmp(dAdd(balance, delta), "0") < 0;
  const valid = target !== null && !dIsZero(delta) && !wouldGoNegative;

  const close = (): void => {
    setTouched(false);
    setValue("0.00");
    setOpeningDate("");
    onClose();
  };

  const submit = (): void => {
    if (!target || !valid) return;
    mutation.mutate(
      {
        ...(target.contract ? { contractId: target.contract.id } : { customerId: target.customer.id }),
        amount: delta,
        kind: "opening",
        charge_date: openingDate || target.contract?.opening_date || null,
        opening_date: openingDate || null,
        note: t.partners.openingFix,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          close();
        },
        onError: (error: unknown) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open={target !== null}
      onClose={close}
      size="md"
      title={t.partners.openingFix}
      subtitle={target ? `${target.customer.full_name}${target.contract ? ` · ${target.contract.contract_no}` : ""}` : undefined}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={close}>
            {t.common.cancel}
          </Button>
          <Button variant="success" size="lg" onClick={submit} disabled={!valid} loading={mutation.isPending}>
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-soft">{t.partners.openingFixHint}</p>
        <div className="grid grid-cols-2 gap-3 rounded-xl bg-surface-alt px-4 py-3">
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-ink-soft">{t.partners.openingCurrent}</span>
            <span className="num text-xl font-bold text-ink">{formatMNT(current)}</span>
            {target?.contract?.opening_date ? (
              <span className="num text-xs text-ink-soft">{formatDate(target.contract.opening_date)}</span>
            ) : null}
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-ink-soft">{t.partners.currentBalance}</span>
            <span className="num text-xl font-bold text-ink">{formatMNT(balance)}</span>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.partners.openingNew}</span>
          <MoneyField
            label={t.partners.openingNew}
            value={shown}
            onChange={(next) => {
              setTouched(true);
              setValue(next);
            }}
          />
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">{t.partners.openingDate}</span>
          <input
            type="date"
            value={openingDate}
            onChange={(event) => setOpeningDate(event.target.value)}
            className="num h-12 w-full rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink focus:border-action focus:outline-none"
          />
        </label>
        <div className="num flex items-center justify-between rounded-xl border border-line px-4 py-3">
          <span className="text-sm font-semibold text-ink-soft">{t.partners.openingDelta}</span>
          <span className={`text-xl font-bold ${dCmp(delta, "0") < 0 ? "text-danger-dark" : "text-ink"}`}>
            {dIsZero(delta) ? t.partners.openingNoChange : `${dCmp(delta, "0") > 0 ? "+" : ""}${formatMNT(delta)}`}
          </span>
        </div>
        {wouldGoNegative ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{t.partners.openingBelowZero}</p>
        ) : null}
      </div>
    </Modal>
  );
}

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
  const [arChargeTarget, setArChargeTarget] = useState<ArChargeTarget | null>(null);
  const [purchasesCustomer, setPurchasesCustomer] = useState<Customer | null>(null);
  const [openingFix, setOpeningFix] = useState<{ customer: Customer; contract: Contract | null } | null>(null);
  const [apCreateOpen, setApCreateOpen] = useState(false);

  const apQuery = useApInvoices({ limit: 200 });
  const arQuery = useArInvoices({ limit: 200 });
  const contractsQuery = useContracts({ limit: 500 });
  const customersQuery = useCustomers({ active_only: true, limit: 500 });

  /** Харилцагч бүр нэг мөр — гэрээгүй (гараар үүсгэсэн) харилцагч ч энд харагдана. */
  const customerRows = useMemo(() => {
    const contracts = (contractsQuery.data?.items ?? []).filter((c) => c.status === "active");
    const byCustomer = new Map<UUID, Contract[]>();
    for (const contract of contracts) {
      const list = byCustomer.get(contract.customer_id) ?? [];
      list.push(contract);
      byCustomer.set(contract.customer_id, list);
    }
    const rows: CustomerArRow[] = (customersQuery.data?.items ?? []).map((customer) => {
      const own = byCustomer.get(customer.id) ?? [];
      const primary = [...own].sort((a, b) => dCmp(b.balance, a.balance))[0] ?? null;
      return {
        customer,
        contracts: own,
        primary,
        opening: dSum(own.map((c) => c.opening_balance ?? "0")),
        limit: own.length > 0 ? dSum(own.map((c) => c.credit_limit)) : customer.credit_limit,
        balance: dSum(own.map((c) => c.balance)),
      };
    });
    // Бүх харилцагч (үлдэгдэлгүй, гэрээгүй ч) харагдана — «Төлөгдөөгүй» шүүлт зөвхөн нэхэмжлэхэд.
    return rows.sort((a, b) => {
      const byBalance = dCmp(b.balance, a.balance);
      return byBalance !== 0 ? byBalance : a.customer.full_name.localeCompare(b.customer.full_name);
    });
  }, [contractsQuery.data, customersQuery.data]);
  const arBalanceTotal = useMemo(() => dSum(customerRows.map((r) => r.balance)), [customerRows]);

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

  const customerColumns: Column<CustomerArRow>[] = [
    {
      key: "customer",
      header: t.partners.customer,
      primary: true,
      render: (row) => (
        <span className="flex flex-col">
          <span className="font-bold">{row.customer.full_name}</span>
          {row.customer.phone ? <span className="num text-xs text-ink-soft">{row.customer.phone}</span> : null}
        </span>
      ),
    },
    {
      key: "contract",
      header: t.partners.contractNo,
      hideOnMobile: true,
      render: (row) =>
        row.contracts.length > 0 ? (
          row.contracts.map((c) => c.contract_no).join(", ")
        ) : (
          <span className="text-ink-soft">{t.partners.noContract}</span>
        ),
    },
    {
      key: "opening",
      header: t.partners.openingBalance,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.opening),
    },
    {
      key: "limit",
      header: t.partners.creditLimit,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.customer.credit_unlimited ? t.partners.creditUnlimited : formatMNT(row.limit)),
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
      render: (row) => {
        const primary = row.primary;
        return (
          <span className="flex flex-wrap justify-end gap-2">
            {primary ? (
              <Button
                variant="secondary"
                size="md"
                icon={<FileText className="h-5 w-5" />}
                onClick={() => setStatementContract(primary.id)}
              >
                {t.partners.statement}
              </Button>
            ) : null}
            <Button
              variant="secondary"
              size="md"
              icon={<ShoppingBag className="h-5 w-5" />}
              onClick={() => setPurchasesCustomer(row.customer)}
            >
              {t.partners.purchases}
            </Button>
            <Button
              variant="secondary"
              size="md"
              icon={<Plus className="h-5 w-5" />}
              onClick={() => setArChargeTarget(primary ? { contractId: primary.id } : { customerId: row.customer.id })}
            >
              {t.partners.arCharge}
            </Button>
            <Button
              variant="ghost"
              size="md"
              icon={<Pencil className="h-5 w-5" />}
              onClick={() => setOpeningFix({ customer: row.customer, contract: primary })}
            >
              {t.partners.openingFix}
            </Button>
            {primary && dCmp(primary.balance, "0") > 0 ? (
              <Button
                variant="primary"
                size="md"
                icon={<Wallet className="h-5 w-5" />}
                onClick={() =>
                  setArTarget({
                    contract_id: primary.id,
                    invoice_id: null,
                    label: `${row.customer.full_name} · ${primary.contract_no}`,
                    due: primary.balance,
                  })
                }
              >
                {t.partners.arPayment}
              </Button>
            ) : null}
          </span>
        );
      },
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
              columns={customerColumns}
              rows={customerRows}
              rowKey={(row) => row.customer.id}
              loading={contractsQuery.isLoading || customersQuery.isLoading}
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
      <ArChargeModal
        open={arChargeOpen || arChargeTarget !== null}
        target={arChargeTarget}
        onClose={() => {
          setArChargeOpen(false);
          setArChargeTarget(null);
        }}
      />
      <ApInvoiceModal open={apCreateOpen} onClose={() => setApCreateOpen(false)} />
      <StatementModal contractId={statementContract} onClose={() => setStatementContract(null)} />
      <PurchasesModal customer={purchasesCustomer} onClose={() => setPurchasesCustomer(null)} />
      <OpeningFixModal target={openingFix} onClose={() => setOpeningFix(null)} />
    </div>
  );
}

export default ApArPage;
