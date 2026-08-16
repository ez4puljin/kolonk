import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, FileText, Pencil, Plus, Wallet } from "lucide-react";

import { api, errorMessage } from "../../api/client";
import {
  useArInvoices,
  useContracts,
  useContractStatement,
  useCreateArPaymentMutation,
  useCreateContractMutation,
  useCustomers,
  useUpdateContractMutation,
} from "../../api/queries/partners";
import type {
  ArInvoice,
  CashAccount,
  Contract,
  ContractStatus,
  Paged,
  StatementRow,
} from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { DateRangePicker, type DateRange } from "../../components/ui/DateRangePicker";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { CONTRACT_STATUS_META, PAGE_SIZE, statusMeta } from "../../lib/constants";
import { dCmp, dSum, dToNumber } from "../../lib/decimal";
import { formatDate, formatMNT, toDateInput, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  DateField,
  KeyValue,
  matchesQuery,
  NumberField,
  Pager,
  PickerField,
  SearchInput,
  TextField,
} from "../catalog/_shared";

type StatusFilter = "all" | ContractStatus;

interface ContractForm {
  customer_id: string;
  contract_no: string;
  credit_limit: string;
  price_discount_per_l: string;
  billing_day: string;
  status: ContractStatus;
}

const EMPTY_FORM: ContractForm = {
  customer_id: "",
  contract_no: "",
  credit_limit: "",
  price_discount_per_l: "",
  billing_day: "1",
  status: "active",
};

function monthStart(): string {
  const now = new Date();
  return toDateInput(new Date(now.getFullYear(), now.getMonth(), 1));
}

export function ContractsPage() {
  const queryClient = useQueryClient();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [offset, setOffset] = useState(0);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Contract | null>(null);
  const [form, setForm] = useState<ContractForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const [statementFor, setStatementFor] = useState<Contract | null>(null);
  const [statementRange, setStatementRange] = useState<DateRange>({ from: monthStart(), to: todayInput() });

  const [invoiceFor, setInvoiceFor] = useState<Contract | null>(null);
  const [periodStart, setPeriodStart] = useState(monthStart());
  const [periodEnd, setPeriodEnd] = useState(todayInput());
  const [invoiceError, setInvoiceError] = useState<string | null>(null);

  const [payFor, setPayFor] = useState<Contract | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [payAccount, setPayAccount] = useState<CashAccount>("bank");
  const [payInvoiceId, setPayInvoiceId] = useState("");
  const [payDate, setPayDate] = useState(todayInput());
  const [payError, setPayError] = useState<string | null>(null);

  const contractsQuery = useContracts({
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 200,
  });
  const customersQuery = useCustomers({ active_only: true, limit: 200 });
  const statementQuery = useContractStatement(
    statementFor?.id,
    statementRange.from,
    statementRange.to,
  );
  const payInvoicesQuery = useArInvoices({ contract_id: payFor?.id, limit: 100 });

  const createMutation = useCreateContractMutation();
  const updateMutation = useUpdateContractMutation();
  const payMutation = useCreateArPaymentMutation();

  /**
   * Нэхэмжлэх үүсгэх — сервер дээрх зам `/invoices/generate` (queries/partners.ts-ийн
   * туслах `/invoices` рүү ханддаг тул энд шууд клиентээр дуудаж байна).
   */
  const generateMutation = useMutation({
    mutationFn: ({ contractId, from, to }: { contractId: string; from: string; to: string }) =>
      api.post<Paged<ArInvoice>>(`/api/contracts/${contractId}/invoices/generate`, {
        period_start: from,
        period_end: to,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ar-invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["contracts"] });
    },
  });

  const allContracts = useMemo(() => contractsQuery.data?.items ?? [], [contractsQuery.data]);
  const filtered = useMemo(
    () => allContracts.filter((contract) => matchesQuery([contract.contract_no, contract.customer_name], query)),
    [allContracts, query],
  );
  const rows = useMemo(() => filtered.slice(offset, offset + PAGE_SIZE), [filtered, offset]);

  const totals = useMemo(
    () => ({
      limit: dSum(filtered.map((contract) => contract.credit_limit)),
      balance: dSum(filtered.map((contract) => contract.balance)),
      available: dSum(filtered.map((contract) => contract.credit_available)),
    }),
    [filtered],
  );

  const customerOptions = useMemo(
    () =>
      (customersQuery.data?.items ?? []).map((customer) => ({
        value: customer.id,
        label: customer.name,
        hint: customer.register_no ?? undefined,
      })),
    [customersQuery.data],
  );

  const openInvoices = useMemo(
    () => (payInvoicesQuery.data?.items ?? []).filter((invoice) => dCmp(invoice.amount_due, "0") > 0),
    [payInvoicesQuery.data],
  );

  const openForm = (contract: Contract | null): void => {
    setEditing(contract);
    setFormError(null);
    setForm(
      contract
        ? {
            customer_id: contract.customer_id,
            contract_no: contract.contract_no,
            credit_limit: contract.credit_limit,
            price_discount_per_l: contract.price_discount_per_l,
            billing_day: String(contract.billing_day),
            status: (contract.status as ContractStatus) ?? "active",
          }
        : EMPTY_FORM,
    );
    setFormOpen(true);
  };

  const submitForm = (): void => {
    setFormError(null);
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setFormOpen(false);
    };
    const onError = (error: unknown): void => setFormError(errorMessage(error));
    const billingDay = Math.min(28, Math.max(1, Math.round(dToNumber(form.billing_day)) || 1));

    if (editing) {
      updateMutation.mutate(
        {
          id: editing.id,
          payload: {
            contract_no: form.contract_no.trim(),
            credit_limit: form.credit_limit === "" ? "0" : form.credit_limit,
            price_discount_per_l:
              form.price_discount_per_l === "" ? "0" : form.price_discount_per_l,
            billing_day: billingDay,
            status: form.status,
          },
        },
        { onSuccess, onError },
      );
    } else {
      createMutation.mutate(
        {
          customer_id: form.customer_id,
          contract_no: form.contract_no.trim(),
          credit_limit: form.credit_limit === "" ? "0" : form.credit_limit,
          price_discount_per_l: form.price_discount_per_l === "" ? "0" : form.price_discount_per_l,
          billing_day: billingDay,
          status: form.status,
        },
        { onSuccess, onError },
      );
    }
  };

  const submitInvoice = (): void => {
    if (!invoiceFor) return;
    setInvoiceError(null);
    generateMutation.mutate(
      { contractId: invoiceFor.id, from: periodStart, to: periodEnd },
      {
        onSuccess: (result) => {
          toastSuccess(`${t.partners.generateInvoice}: ${result.total}`);
          setInvoiceFor(null);
        },
        onError: (error) => setInvoiceError(errorMessage(error)),
      },
    );
  };

  const submitPayment = (): void => {
    if (!payFor || dToNumber(payAmount) <= 0) return;
    setPayError(null);
    payMutation.mutate(
      {
        contract_id: payFor.id,
        amount: payAmount,
        received_to: payAccount,
        payment_date: payDate,
        ar_invoice_id: payInvoiceId || null,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setPayFor(null);
        },
        onError: (error) => setPayError(errorMessage(error)),
      },
    );
  };

  const columns: Column<Contract>[] = [
    {
      key: "contract_no",
      header: t.partners.contractNo,
      primary: true,
      numeric: true,
      render: (row) => <span className="font-bold">{row.contract_no}</span>,
    },
    { key: "customer", header: t.partners.customer, render: (row) => row.customer_name ?? "—" },
    {
      key: "usage",
      header: t.partners.creditLimit,
      width: "16rem",
      render: (row) => {
        const limit = dToNumber(row.credit_limit);
        const used = dToNumber(row.balance);
        const pct = limit > 0 ? (used / limit) * 100 : 0;
        return (
          <ProgressBar
            value={pct}
            tone={pct >= 90 ? "danger" : pct >= 70 ? "warning" : "success"}
            size="sm"
            valueLabel={`${formatMNT(row.balance)} / ${formatMNT(row.credit_limit)}`}
          />
        );
      },
    },
    {
      key: "available",
      header: t.partners.creditAvailable,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.credit_available)}</span>,
    },
    {
      key: "discount",
      header: t.partners.discountPerL,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.price_discount_per_l),
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(CONTRACT_STATUS_META, row.status, row.status_name)} />,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" size="md" icon={<FileText />} onClick={() => setStatementFor(row)}>
            {t.partners.statement}
          </Button>
          <Button
            variant="secondary"
            size="md"
            icon={<FilePlus2 />}
            onClick={() => {
              setInvoiceFor(row);
              setInvoiceError(null);
            }}
          >
            {t.partners.generateInvoice}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Wallet />}
            onClick={() => {
              setPayFor(row);
              setPayAmount(row.balance);
              setPayInvoiceId("");
              setPayAccount("bank");
              setPayDate(todayInput());
              setPayError(null);
            }}
          >
            {t.partners.arPayment}
          </Button>
          <Button variant="ghost" size="md" icon={<Pencil />} onClick={() => openForm(row)}>
            {t.common.edit}
          </Button>
        </div>
      ),
    },
  ];

  const statementColumns: Column<StatementRow>[] = [
    {
      key: "date",
      header: t.common.date,
      primary: true,
      numeric: true,
      render: (row) => formatDate(row.date),
    },
    { key: "kind", header: t.common.status, render: (row) => row.kind_name || row.kind },
    { key: "ref", header: "№", numeric: true, hideOnMobile: true, render: (row) => row.ref ?? "—" },
    { key: "description", header: t.accounting.description, render: (row) => row.description },
    {
      key: "debit",
      header: t.accounting.debit,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.debit),
    },
    {
      key: "credit",
      header: t.accounting.credit,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.credit),
    },
    {
      key: "balance",
      header: t.common.balance,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.balance)}</span>,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.partners.contracts}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => openForm(null)}>
            {t.partners.newContract}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.partners.creditLimit} value={formatMNT(totals.limit)} tone="neutral" />
        <StatBox label={t.dashboard.receivables} value={formatMNT(totals.balance)} tone="warning" size="lg" />
        <StatBox label={t.partners.creditAvailable} value={formatMNT(totals.available)} tone="success" />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
        />
        <ChipGroup<StatusFilter>
          value={statusFilter}
          onChange={(next) => {
            setStatusFilter(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "active", label: t.status.active },
            { value: "suspended", label: t.status.suspended },
            { value: "closed", label: t.status.closed },
          ]}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={contractsQuery.isLoading}
          empty={
            <EmptyState
              icon={<FileText className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => openForm(null)}>
                  {t.partners.newContract}
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={filtered.length} onChange={setOffset} />}
        />
      </Card>

      {/* Тооцоо нийлэх акт */}
      <Modal
        open={statementFor !== null}
        onClose={() => setStatementFor(null)}
        size="xl"
        title={t.partners.statement}
        subtitle={statementFor ? `${statementFor.contract_no} · ${statementFor.customer_name ?? ""}` : ""}
      >
        <div className="flex flex-col gap-4">
          <DateRangePicker value={statementRange} onChange={setStatementRange} />

          <div className="grid gap-4 sm:grid-cols-4">
            <StatBox
              label={t.partners.openingBalance}
              value={formatMNT(statementQuery.data?.opening_balance ?? "0")}
              tone="neutral"
            />
            <StatBox
              label={t.partners.salesTotal}
              value={formatMNT(statementQuery.data?.sales_total ?? "0")}
              tone="action"
            />
            <StatBox
              label={t.partners.paymentsTotal}
              value={formatMNT(statementQuery.data?.payments_total ?? "0")}
              tone="success"
            />
            <StatBox
              label={t.partners.closingBalance}
              value={formatMNT(statementQuery.data?.closing_balance ?? "0")}
              tone="warning"
            />
          </div>

          <DataTable
            columns={statementColumns}
            rows={statementQuery.data?.rows ?? []}
            rowKey={(row) => `${row.date ?? ""}-${row.kind}-${row.ref ?? ""}-${row.balance}`}
            loading={statementQuery.isLoading}
            empty={<EmptyState compact title={t.reports.noData} hint={t.common.emptyHint} />}
          />
        </div>
      </Modal>

      {/* Нэхэмжлэх үүсгэх */}
      <Modal
        open={invoiceFor !== null}
        onClose={() => setInvoiceFor(null)}
        size="md"
        title={t.partners.generateInvoice}
        subtitle={invoiceFor?.contract_no}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setInvoiceFor(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              loading={generateMutation.isPending}
              onClick={submitInvoice}
            >
              {t.common.create}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <DateField label={t.common.from} value={periodStart} onChange={setPeriodStart} max={periodEnd} />
            <DateField label={t.common.to} value={periodEnd} onChange={setPeriodEnd} min={periodStart} />
          </div>
          <p className="text-sm text-ink-soft">{t.partners.arInvoices}</p>
          {invoiceError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {invoiceError}
            </p>
          ) : null}
        </div>
      </Modal>

      {/* Төлбөр бүртгэх */}
      <Modal
        open={payFor !== null}
        onClose={() => setPayFor(null)}
        size="md"
        title={t.partners.arPayment}
        subtitle={payFor ? `${payFor.contract_no} · ${formatMNT(payFor.balance)}` : ""}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setPayFor(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={dToNumber(payAmount) <= 0}
              loading={payMutation.isPending}
              onClick={submitPayment}
            >
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <NumberField
            name="ar-payment-amount"
            label={t.common.amount}
            value={payAmount}
            onChange={setPayAmount}
            suffix={t.units.mnt}
          />
          <ChipGroup<CashAccount>
            label={t.partners.receivedTo}
            value={payAccount}
            onChange={setPayAccount}
            options={[
              { value: "bank", label: t.procurement.bank },
              { value: "cash", label: t.procurement.cash },
            ]}
          />
          <PickerField
            label={t.partners.arInvoices}
            value={payInvoiceId}
            options={[
              { value: "", label: t.common.none },
              ...openInvoices.map((invoice) => ({
                value: invoice.id,
                label: invoice.invoice_no,
                hint: `${formatDate(invoice.period_end)} · ${formatMNT(invoice.amount_due)}`,
              })),
            ]}
            onChange={(value) => {
              setPayInvoiceId(value);
              const invoice = openInvoices.find((item) => item.id === value);
              if (invoice) setPayAmount(invoice.amount_due);
            }}
          />
          <DateField label={t.common.date} value={payDate} onChange={setPayDate} />
          {payError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {payError}
            </p>
          ) : null}
        </div>
      </Modal>

      {/* Гэрээ үүсгэх / засах */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editing ? t.common.edit : t.partners.newContract}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={form.contract_no.trim() === "" || (!editing && form.customer_id === "")}
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submitForm}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {editing ? (
            <KeyValue label={t.partners.customer} value={editing.customer_name ?? "—"} />
          ) : (
            <PickerField
              label={t.partners.customer}
              value={form.customer_id}
              options={customerOptions}
              onChange={(value) => setForm({ ...form, customer_id: value })}
            />
          )}
          <TextField
            label={t.partners.contractNo}
            value={form.contract_no}
            onChange={(value) => setForm({ ...form, contract_no: value })}
          />
          <NumberField
            name="contract-form-limit"
            label={t.partners.creditLimit}
            value={form.credit_limit}
            onChange={(value) => setForm({ ...form, credit_limit: value })}
            suffix={t.units.mnt}
          />
          <NumberField
            name="contract-form-discount"
            label={t.partners.discountPerL}
            value={form.price_discount_per_l}
            onChange={(value) => setForm({ ...form, price_discount_per_l: value })}
            suffix={t.units.perLiter}
          />
          <NumberField
            name="contract-form-billing-day"
            label={t.partners.billingDay}
            value={form.billing_day}
            onChange={(value) => setForm({ ...form, billing_day: value })}
            allowDecimal={false}
          />
          <ChipGroup<ContractStatus>
            label={t.common.status}
            value={form.status}
            onChange={(value) => setForm({ ...form, status: value })}
            options={[
              { value: "active", label: t.status.active },
              { value: "suspended", label: t.status.suspended },
              { value: "closed", label: t.status.closed },
            ]}
          />
          {formError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {formError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default ContractsPage;
