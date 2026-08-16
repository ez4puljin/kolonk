import { useMemo, useState } from "react";
import { Landmark, Pencil, Plus, Power } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useBankAccounts,
  useCreateBankAccountMutation,
  useDeactivateBankAccountMutation,
  useUpdateBankAccountMutation,
} from "../../api/queries/bank";
import { useBranches } from "../../api/queries/branches";
import type { BankAccount } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useCan } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { dSum } from "../../lib/decimal";
import { formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  NumberField,
  PickerField,
  TextAreaField,
  TextField,
  ToggleField,
} from "../catalog/_shared";

interface AccountForm {
  bank_name: string;
  account_number: string;
  holder_name: string;
  currency: string;
  opening_balance: string;
  branch_id: string;
  is_fee_default: boolean;
  is_active: boolean;
  note: string;
}

const EMPTY_FORM: AccountForm = {
  bank_name: "",
  account_number: "",
  holder_name: "",
  currency: "MNT",
  opening_balance: "",
  branch_id: "",
  is_fee_default: false,
  is_active: true,
  note: "",
};

/**
 * Харилцах данс — банкны хуулга оруулахад дансны дугаараар нь холбогдоно.
 *
 * Ерөнхий дэвтэрт бүх данс `1110 Банк`-т нэгтгэгддэг; данс тус бүрийн
 * үлдэгдлийг журналын мөрийн хэмжүүрээр гаргадаг тул Σ(данс) + хуваарилаагүй
 * нь 1110-тэй үргэлж таарна.
 */
export function BankAccountsPage() {
  const canManage = useCan("bank.manage");
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [filter, setFilter] = useState<"all" | "active">("active");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<BankAccount | null>(null);
  const [form, setForm] = useState<AccountForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [deactivating, setDeactivating] = useState<BankAccount | null>(null);

  const accountsQuery = useBankAccounts();
  const branchesQuery = useBranches();
  const createMutation = useCreateBankAccountMutation();
  const updateMutation = useUpdateBankAccountMutation();
  const deactivateMutation = useDeactivateBankAccountMutation();

  const data = accountsQuery.data;
  const rows = useMemo(
    () => (data?.items ?? []).filter((row) => (filter === "active" ? row.is_active : true)),
    [data, filter],
  );
  const totalBalance = useMemo(() => dSum(rows.map((row) => row.balance)), [rows]);

  const branchOptions = useMemo(
    () => [
      { value: "", label: t.branches.allBranches },
      ...(branchesQuery.data ?? []).map((branch) => ({ value: branch.id, label: branch.name })),
    ],
    [branchesQuery.data],
  );

  const openForm = (account: BankAccount | null): void => {
    setEditing(account);
    setFormError(null);
    setForm(
      account
        ? {
            bank_name: account.bank_name,
            account_number: account.account_number,
            holder_name: account.holder_name,
            currency: account.currency,
            opening_balance: account.opening_balance,
            branch_id: account.branch_id ?? "",
            is_fee_default: account.is_fee_default,
            is_active: account.is_active,
            note: account.note ?? "",
          }
        : EMPTY_FORM,
    );
    setFormOpen(true);
  };

  const submit = (): void => {
    setFormError(null);
    const payload = {
      bank_name: form.bank_name.trim(),
      account_number: form.account_number.trim(),
      holder_name: form.holder_name.trim(),
      currency: form.currency.trim() || "MNT",
      opening_balance: form.opening_balance === "" ? "0" : form.opening_balance,
      branch_id: form.branch_id || null,
      is_fee_default: form.is_fee_default,
      is_active: form.is_active,
      note: form.note.trim() || null,
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

  const columns: Column<BankAccount>[] = [
    {
      key: "bank",
      header: t.bank.bankName,
      primary: true,
      render: (row) => (
        <span className="flex flex-col gap-0.5">
          <span className="flex items-center gap-2 font-semibold">
            {row.bank_name}
            {row.is_fee_default ? (
              <StatusBadge size="sm" tone="warning" label={t.bank.feeDefault} />
            ) : null}
          </span>
          <span className="num text-xs text-ink-soft">{row.holder_name || "—"}</span>
        </span>
      ),
    },
    {
      key: "number",
      header: t.bank.accountNumber,
      numeric: true,
      render: (row) => row.account_number,
    },
    {
      key: "currency",
      header: t.bank.currency,
      hideOnMobile: true,
      render: (row) => row.currency,
    },
    {
      key: "opening",
      header: t.bank.openingBalance,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.opening_balance),
    },
    {
      key: "movement",
      header: t.bank.movement,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.movement),
    },
    {
      key: "balance",
      header: t.bank.balance,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.balance)}</span>,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        canManage ? (
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" size="md" icon={<Pencil />} onClick={() => openForm(row)}>
              {t.common.edit}
            </Button>
            {row.is_active ? (
              <Button variant="ghost" size="md" icon={<Power />} onClick={() => setDeactivating(row)}>
                {t.admin.deactivate}
              </Button>
            ) : null}
          </div>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.bank.accounts}
        subtitle={t.bank.accountsHint}
        actions={
          canManage ? (
            <Button variant="primary" size="lg" icon={<Plus />} onClick={() => openForm(null)}>
              {t.bank.newAccount}
            </Button>
          ) : null
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.bank.balance} value={formatMNT(totalBalance)} tone="success" size="lg" />
        <StatBox
          label={t.bank.unassigned}
          value={formatMNT(data?.unassigned ?? "0")}
          tone={data && data.unassigned !== "0.00" ? "warning" : "neutral"}
        />
        <StatBox
          label={t.bank.ledgerBalance}
          value={formatMNT(data?.ledger_balance ?? "0")}
          tone="neutral"
        />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <ChipGroup<"all" | "active">
          value={filter}
          onChange={setFilter}
          options={[
            { value: "active", label: t.common.active },
            { value: "all", label: t.common.all },
          ]}
        />
        <p className="text-sm text-ink-soft">{t.bank.unassignedHint}</p>
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={accountsQuery.isLoading}
          rowClassName={(row) => (row.is_active ? "" : "opacity-60")}
          empty={
            <EmptyState
              icon={<Landmark className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.bank.accountsHint}
              action={
                canManage ? (
                  <Button variant="primary" size="md" onClick={() => openForm(null)}>
                    {t.bank.newAccount}
                  </Button>
                ) : undefined
              }
            />
          }
        />
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editing ? t.common.edit : t.bank.newAccount}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={form.bank_name.trim() === "" || form.account_number.trim() === ""}
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submit}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label={t.bank.bankName}
              value={form.bank_name}
              onChange={(value) => setForm({ ...form, bank_name: value })}
            />
            <TextField
              label={t.bank.accountNumber}
              value={form.account_number}
              onChange={(value) => setForm({ ...form, account_number: value })}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label={t.bank.holderName}
              value={form.holder_name}
              onChange={(value) => setForm({ ...form, holder_name: value })}
            />
            <TextField
              label={t.bank.currency}
              value={form.currency}
              onChange={(value) => setForm({ ...form, currency: value })}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              name="bank-opening"
              label={t.bank.openingBalance}
              value={form.opening_balance}
              onChange={(value) => setForm({ ...form, opening_balance: value })}
              suffix={t.units.mnt}
            />
            <PickerField
              label={t.branches.title}
              value={form.branch_id}
              options={branchOptions}
              onChange={(value) => setForm({ ...form, branch_id: value })}
            />
          </div>
          <ToggleField
            label={t.bank.feeDefault}
            hint={t.bank.feeDefaultHint}
            value={form.is_fee_default}
            onChange={(value) => setForm({ ...form, is_fee_default: value })}
          />
          <ToggleField
            label={t.common.active}
            value={form.is_active}
            onChange={(value) => setForm({ ...form, is_active: value })}
          />
          <TextAreaField
            label={t.common.note}
            value={form.note}
            onChange={(value) => setForm({ ...form, note: value })}
          />
          {formError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {formError}
            </p>
          ) : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title={t.admin.deactivate}
        message={deactivating ? `${deactivating.bank_name} · ${deactivating.account_number}` : ""}
        variant="danger"
        confirmLabel={t.admin.deactivate}
        loading={deactivateMutation.isPending}
        onConfirm={() => {
          if (!deactivating) return;
          deactivateMutation.mutate(deactivating.id, {
            onSuccess: () => {
              toastSuccess(t.common.saved);
              setDeactivating(null);
            },
            onError: () => setDeactivating(null),
          });
        }}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}

export default BankAccountsPage;
