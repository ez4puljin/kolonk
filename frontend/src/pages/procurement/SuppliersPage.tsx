import { useMemo, useState } from "react";
import { Building2, Pencil, Plus, Wallet } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useApInvoices, useCreateApPaymentMutation } from "../../api/queries/accounting";
import {
  useCreateSupplierMutation,
  useSuppliers,
  useUpdateSupplierMutation,
} from "../../api/queries/procurement";
import type { ApInvoice, CashAccount, Supplier } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { INVOICE_STATUS_META, PAGE_SIZE, statusMeta } from "../../lib/constants";
import { dCmp, dSum, dToNumber } from "../../lib/decimal";
import { formatDate, formatMNT, todayInput } from "../../lib/format";
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
  ToggleField,
} from "../catalog/_shared";

interface SupplierForm {
  name: string;
  register_no: string;
  phone: string;
  bank_account: string;
  address: string;
  is_active: boolean;
}

const EMPTY_FORM: SupplierForm = {
  name: "",
  register_no: "",
  phone: "",
  bank_account: "",
  address: "",
  is_active: true,
};

export function SuppliersPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Supplier | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [form, setForm] = useState<SupplierForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const [payOpen, setPayOpen] = useState(false);
  const [payInvoiceId, setPayInvoiceId] = useState("");
  const [payAmount, setPayAmount] = useState("");
  const [payFrom, setPayFrom] = useState<CashAccount>("bank");
  const [payDate, setPayDate] = useState(todayInput());
  const [payError, setPayError] = useState<string | null>(null);

  const suppliersQuery = useSuppliers({ limit: 500 });
  const ledgerQuery = useApInvoices({ supplier_id: selected?.id, limit: 200 });
  const createMutation = useCreateSupplierMutation();
  const updateMutation = useUpdateSupplierMutation();
  const payMutation = useCreateApPaymentMutation();

  const allSuppliers = useMemo(() => suppliersQuery.data?.items ?? [], [suppliersQuery.data]);

  // Сервер талын хайлт `search` параметрээр явдаг тул (query hook `q` илгээдэг)
  // жагсаалтыг клиент талд шүүж, хуудаслалтыг өөрсдөө хийнэ.
  const filtered = useMemo(
    () => allSuppliers.filter((supplier) => matchesQuery([supplier.name, supplier.register_no, supplier.phone], query)),
    [allSuppliers, query],
  );
  const rows = useMemo(() => filtered.slice(offset, offset + PAGE_SIZE), [filtered, offset]);

  const totalBalance = useMemo(
    () => dSum(allSuppliers.map((supplier) => supplier.balance ?? "0")),
    [allSuppliers],
  );

  const invoices = useMemo(
    () => (selected ? (ledgerQuery.data?.items ?? []) : []),
    [ledgerQuery.data, selected],
  );
  const openInvoices = useMemo(
    () => invoices.filter((invoice) => dCmp(invoice.amount_due, "0") > 0),
    [invoices],
  );

  const openForm = (supplier: Supplier | null): void => {
    setEditing(supplier);
    setFormError(null);
    setForm(
      supplier
        ? {
            name: supplier.name,
            register_no: supplier.register_no ?? "",
            phone: supplier.phone ?? "",
            bank_account: supplier.bank_account ?? "",
            address: supplier.address ?? "",
            is_active: supplier.is_active,
          }
        : EMPTY_FORM,
    );
    setFormOpen(true);
  };

  const submitForm = (): void => {
    setFormError(null);
    const payload = {
      name: form.name.trim(),
      register_no: form.register_no.trim() || null,
      phone: form.phone.trim() || null,
      bank_account: form.bank_account.trim() || null,
      address: form.address.trim() || null,
      is_active: form.is_active,
    };
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setFormOpen(false);
    };
    const onError = (error: unknown): void => setFormError(errorMessage(error));

    if (editing) {
      updateMutation.mutate({ id: editing.id, payload }, { onSuccess, onError });
    } else {
      createMutation.mutate(payload, { onSuccess, onError });
    }
  };

  const openPayment = (invoice: ApInvoice | null): void => {
    setPayInvoiceId(invoice?.id ?? openInvoices[0]?.id ?? "");
    setPayAmount(invoice?.amount_due ?? openInvoices[0]?.amount_due ?? "");
    setPayFrom("bank");
    setPayDate(todayInput());
    setPayError(null);
    setPayOpen(true);
  };

  const submitPayment = (): void => {
    if (payInvoiceId === "" || dToNumber(payAmount) <= 0) return;
    setPayError(null);
    payMutation.mutate(
      {
        ap_invoice_id: payInvoiceId,
        amount: payAmount,
        paid_from: payFrom,
        payment_date: payDate,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setPayOpen(false);
        },
        onError: (error) => setPayError(errorMessage(error)),
      },
    );
  };

  const columns: Column<Supplier>[] = [
    { key: "name", header: t.common.name, primary: true, render: (row) => <span className="font-semibold">{row.name}</span> },
    {
      key: "register_no",
      header: t.common.registerNo,
      numeric: true,
      render: (row) => row.register_no ?? "—",
    },
    { key: "phone", header: t.common.phone, numeric: true, render: (row) => row.phone ?? "—" },
    {
      key: "bank_account",
      header: t.procurement.bankAccount,
      numeric: true,
      hideOnMobile: true,
      render: (row) => row.bank_account ?? "—",
    },
    {
      key: "balance",
      header: t.procurement.amountDue,
      align: "right",
      numeric: true,
      render: (row) => (
        <span className={dCmp(row.balance ?? "0", "0") > 0 ? "font-bold text-danger-dark" : "text-ink-soft"}>
          {formatMNT(row.balance ?? "0")}
        </span>
      ),
    },
    {
      key: "is_active",
      header: t.common.status,
      render: (row) => (
        <StatusBadge size="sm" tone={row.is_active ? "success" : "neutral"} label={row.is_active ? t.common.active : t.common.inactive} />
      ),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      hideOnMobile: true,
      render: (row) => (
        <Button
          variant="secondary"
          size="md"
          icon={<Pencil />}
          onClick={(event) => {
            event.stopPropagation();
            openForm(row);
          }}
        >
          {t.common.edit}
        </Button>
      ),
    },
  ];

  const invoiceColumns: Column<ApInvoice>[] = [
    { key: "invoice_no", header: t.procurement.invoiceNo, primary: true, render: (row) => row.invoice_no },
    {
      key: "invoice_date",
      header: t.common.date,
      numeric: true,
      render: (row) => formatDate(row.invoice_date),
    },
    {
      key: "due_date",
      header: t.procurement.dueDate,
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatDate(row.due_date),
    },
    {
      key: "amount_gross",
      header: t.common.gross,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.amount_gross),
    },
    {
      key: "amount_paid",
      header: t.partners.paymentsTotal,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.amount_paid),
    },
    {
      key: "amount_due",
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
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        dCmp(row.amount_due, "0") > 0 ? (
          <Button variant="primary" size="md" icon={<Wallet />} onClick={() => openPayment(row)}>
            {t.procurement.apPayment}
          </Button>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.procurement.suppliers}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => openForm(null)}>
            {t.procurement.newSupplier}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.procurement.suppliers} value={allSuppliers.length} tone="neutral" />
        <StatBox
          label={t.procurement.apInvoices}
          value={formatMNT(totalBalance)}
          tone={dCmp(totalBalance, "0") > 0 ? "warning" : "neutral"}
        />
        <StatBox
          label={t.common.active}
          value={allSuppliers.filter((supplier) => supplier.is_active).length}
          tone="success"
        />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={setSelected}
          loading={suppliersQuery.isLoading}
          empty={
            <EmptyState
              icon={<Building2 className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => openForm(null)}>
                  {t.procurement.newSupplier}
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={filtered.length} onChange={setOffset} />}
        />
      </Card>

      {selected ? (
        <Card
          title={selected.name}
          subtitle={t.procurement.apInvoices}
          actions={
            <>
              <Button
                variant="primary"
                size="md"
                icon={<Wallet />}
                disabled={openInvoices.length === 0}
                onClick={() => openPayment(null)}
              >
                {t.procurement.apPayment}
              </Button>
              <Button variant="ghost" size="md" onClick={() => setSelected(null)}>
                {t.common.close}
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue label={t.common.registerNo} value={selected.register_no ?? "—"} numeric />
              <KeyValue label={t.common.phone} value={selected.phone ?? "—"} numeric />
              <KeyValue label={t.procurement.bankAccount} value={selected.bank_account ?? "—"} numeric />
              <KeyValue label={t.common.address} value={selected.address ?? "—"} />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <StatBox
                label={t.common.gross}
                value={formatMNT(dSum(invoices.map((invoice) => invoice.amount_gross)))}
                tone="neutral"
              />
              <StatBox
                label={t.partners.paymentsTotal}
                value={formatMNT(dSum(invoices.map((invoice) => invoice.amount_paid)))}
                tone="success"
              />
              <StatBox
                label={t.common.balance}
                value={formatMNT(dSum(invoices.map((invoice) => invoice.amount_due)))}
                tone="warning"
              />
            </div>

            <DataTable
              columns={invoiceColumns}
              rows={invoices}
              rowKey={(row) => row.id}
              loading={ledgerQuery.isLoading}
              empty={<EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />}
            />
          </div>
        </Card>
      ) : null}

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editing ? t.common.edit : t.procurement.newSupplier}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={form.name.trim() === ""}
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submitForm}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField label={t.common.name} value={form.name} onChange={(value) => setForm({ ...form, name: value })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label={t.common.registerNo}
              value={form.register_no}
              onChange={(value) => setForm({ ...form, register_no: value })}
            />
            <TextField
              label={t.common.phone}
              value={form.phone}
              onChange={(value) => setForm({ ...form, phone: value })}
            />
          </div>
          <TextField
            label={t.procurement.bankAccount}
            value={form.bank_account}
            onChange={(value) => setForm({ ...form, bank_account: value })}
          />
          <TextField
            label={t.common.address}
            value={form.address}
            onChange={(value) => setForm({ ...form, address: value })}
          />
          <ToggleField
            label={t.common.active}
            value={form.is_active}
            onChange={(value) => setForm({ ...form, is_active: value })}
          />
          {formError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {formError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={payOpen}
        onClose={() => setPayOpen(false)}
        size="md"
        title={t.procurement.apPayment}
        subtitle={selected?.name}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setPayOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={payInvoiceId === "" || dToNumber(payAmount) <= 0}
              loading={payMutation.isPending}
              onClick={submitPayment}
            >
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <PickerField
            label={t.procurement.invoiceNo}
            value={payInvoiceId}
            options={openInvoices.map((invoice) => ({
              value: invoice.id,
              label: invoice.invoice_no,
              hint: `${formatDate(invoice.invoice_date)} · ${formatMNT(invoice.amount_due)}`,
            }))}
            onChange={(value) => {
              setPayInvoiceId(value);
              const invoice = openInvoices.find((item) => item.id === value);
              if (invoice) setPayAmount(invoice.amount_due);
            }}
          />
          <NumberField
            name="ap-payment-amount"
            label={t.common.amount}
            value={payAmount}
            onChange={setPayAmount}
            suffix={t.units.mnt}
          />
          <ChipGroup<CashAccount>
            label={t.procurement.payFrom}
            value={payFrom}
            onChange={setPayFrom}
            options={[
              { value: "bank", label: t.procurement.bank },
              { value: "cash", label: t.procurement.cash },
            ]}
          />
          <DateField label={t.common.date} value={payDate} onChange={setPayDate} />
          {payError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {payError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default SuppliersPage;
