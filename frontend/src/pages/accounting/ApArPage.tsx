/**
 * Өглөг, авлага (WP12) — насжилтын бүлэг, үлдэгдэл, төлөлт/хүлээн авалт,
 * гэрээний тооцоо нийлэх акт.
 *
 * Сервер: `/api/ap-invoices`, `/api/ap-payments`, `/api/ar-invoices`,
 * `/api/ar-payments`, `/api/contracts/{id}/statement`.
 */

import { useMemo, useState } from "react";
import { FileText, Wallet } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useApInvoices, useCreateApPaymentMutation } from "../../api/queries/accounting";
import { useArInvoices, useContractStatement, useCreateArPaymentMutation } from "../../api/queries/partners";
import type { ApInvoice, ArInvoice, CashAccount, StatementRow, UUID } from "../../api/types";
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

  const [amount, setAmount] = useState("0.00");
  const [paidFrom, setPaidFrom] = useState<CashAccount>("bank");
  const [paymentDate, setPaymentDate] = useState(todayInput);
  const [note, setNote] = useState("");

  const due = invoice?.amount_due ?? "0";
  const valid = !dIsZero(amount) && dCmp(amount, due) <= 0 && dCmp(amount, "0") > 0;

  const submit = (): void => {
    if (!invoice) return;
    mutation.mutate(
      {
        ap_invoice_id: invoice.id,
        amount,
        paid_from: paidFrom,
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

function ArPaymentModal({ invoice, onClose }: { invoice: ArInvoice | null; onClose: () => void }) {
  const toastError = useUiStore((state) => state.toastError);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const mutation = useCreateArPaymentMutation();

  const [amount, setAmount] = useState("0.00");
  const [receivedTo, setReceivedTo] = useState<CashAccount>("bank");
  const [paymentDate, setPaymentDate] = useState(todayInput);
  const [note, setNote] = useState("");

  const due = invoice?.amount_due ?? "0";
  const valid = dCmp(amount, "0") > 0;

  const submit = (): void => {
    if (!invoice) return;
    mutation.mutate(
      {
        contract_id: invoice.contract_id,
        ar_invoice_id: invoice.id,
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
      open={invoice !== null}
      onClose={onClose}
      size="md"
      title={t.partners.arPayment}
      subtitle={invoice ? `${invoice.customer_name ?? ""} · ${invoice.invoice_no}` : undefined}
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
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
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
  const [arTarget, setArTarget] = useState<ArInvoice | null>(null);
  const [statementContract, setStatementContract] = useState<UUID | null>(null);

  const apQuery = useApInvoices({ limit: 200 });
  const arQuery = useArInvoices({ limit: 200 });

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
              onClick={() => setArTarget(row)}
            >
              {t.partners.arPayment}
            </Button>
          ) : null}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.accounting.apar}
        subtitle={`${t.common.total}: ${formatMNT(outstanding)}`}
        actions={
          <Button variant={openOnly ? "primary" : "secondary"} size="md" onClick={() => setOpenOnly((v) => !v)}>
            {openOnly ? t.status.unpaid : t.common.all}
          </Button>
        }
      >
        <TabBar variant="underline" value={tab} onChange={setTab} items={TABS} />
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
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
        <Card title={t.procurement.apInvoices} subtitle={`${apRows.length} ${t.common.rows}`} flush>
          <DataTable
            columns={apColumns}
            rows={apRows}
            rowKey={(row) => row.id}
            loading={apQuery.isLoading}
            emptyTitle={t.reports.noData}
          />
        </Card>
      ) : (
        <Card title={t.partners.arInvoices} subtitle={`${arRows.length} ${t.common.rows}`} flush>
          <DataTable
            columns={arColumns}
            rows={arRows}
            rowKey={(row) => row.id}
            loading={arQuery.isLoading}
            emptyTitle={t.reports.noData}
          />
        </Card>
      )}

      <ApPaymentModal invoice={apTarget} onClose={() => setApTarget(null)} />
      <ArPaymentModal invoice={arTarget} onClose={() => setArTarget(null)} />
      <StatementModal contractId={statementContract} onClose={() => setStatementContract(null)} />
    </div>
  );
}

export default ApArPage;
