import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeftRight,
  ChevronLeft,
  CircleCheck,
  Landmark,
  Receipt,
  Settings2,
  Trash2,
  Undo2,
  Upload,
  Wand2,
} from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useBankAccounts,
  useBankStatement,
  useBankStatements,
  useDeleteStatementMutation,
  usePostAllMutation,
  useSetStatementAccountMutation,
  useStatementActionMutation,
  useStatementConfig,
  useTransactionActionMutation,
  useUpdateBankTransactionMutation,
  useUpdateStatementConfigMutation,
  useUploadStatementMutation,
} from "../../api/queries/bank";
import { useExpenseCategories } from "../../api/queries/expenses";
import { useCustomers } from "../../api/queries/partners";
import type { BankStatement, BankTransaction, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { formatDate, formatDateTime, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { PickerField, TextField } from "../catalog/_shared";

/** Гэрээт харилцагчийн сонголт — Колонкийн харилцагчийн бүртгэлээс. */
function useContractOptions() {
  const { data } = useCustomers({ q: "", active_only: true, limit: 200 });
  return useMemo(
    () =>
      (data?.items ?? []).flatMap((customer) =>
        customer.contracts
          .filter((contract) => contract.status === "active")
          .map((contract) => ({
            value: contract.id,
            label: `${customer.name} · ${contract.contract_no}`,
          })),
      ),
    [data],
  );
}

// --------------------------------------------------------------------------
// Тохиргооны цонх
// --------------------------------------------------------------------------
function ConfigModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const { data } = useStatementConfig();
  const categories = useExpenseCategories();
  const contracts = useContractOptions();
  const save = useUpdateStatementConfigMutation();

  const [contractId, setContractId] = useState("");
  const [settlementText, setSettlementText] = useState("");
  const [feeCode, setFeeCode] = useState("");
  const [feeText, setFeeText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !data) return;
    setContractId(data.settlement_contract_id ?? "");
    setSettlementText(data.settlement_description);
    setFeeCode(data.fee_account_code ?? "");
    setFeeText(data.fee_description);
    setError(null);
  }, [open, data]);

  const categoryOptions = useMemo(
    () => [
      { value: "", label: t.common.none },
      ...(categories.data ?? []).map((row) => ({ value: row.code, label: row.name_mn })),
    ],
    [categories.data],
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={t.bank.config}
      subtitle={t.bank.configHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            loading={save.isPending}
            onClick={() =>
              save.mutate(
                {
                  settlement_contract_id: contractId || null,
                  settlement_description: settlementText,
                  fee_account_code: feeCode || null,
                  fee_description: feeText,
                },
                {
                  onSuccess: () => {
                    toastSuccess(t.common.saved);
                    onClose();
                  },
                  onError: (cause) => setError(errorMessage(cause)),
                },
              )
            }
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField
          label={t.bank.settlementContract}
          value={contractId}
          options={[{ value: "", label: t.common.none }, ...contracts]}
          onChange={setContractId}
        />
        <TextField
          label={t.bank.settlementDescription}
          value={settlementText}
          onChange={setSettlementText}
        />
        <PickerField
          label={t.bank.feeCategory}
          value={feeCode}
          options={categoryOptions}
          onChange={setFeeCode}
        />
        <TextField label={t.bank.feeDescription} value={feeText} onChange={setFeeText} />
        {error ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Мөр засах цонх
// --------------------------------------------------------------------------
function TxnEditModal({
  statementId,
  txn,
  onClose,
}: {
  statementId: UUID;
  txn: BankTransaction | null;
  onClose: () => void;
}) {
  const categories = useExpenseCategories();
  const contracts = useContractOptions();
  const update = useUpdateBankTransactionMutation();

  const [description, setDescription] = useState("");
  const [contractId, setContractId] = useState("");
  const [accountCode, setAccountCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!txn) return;
    setDescription(txn.description);
    setContractId(txn.contract_id ?? "");
    setAccountCode(txn.expense_account_code ?? "");
    setError(null);
  }, [txn]);

  const categoryOptions = useMemo(
    () => [
      { value: "", label: t.common.none },
      ...(categories.data ?? []).map((row) => ({ value: row.code, label: row.name_mn })),
    ],
    [categories.data],
  );

  const income = txn?.is_income ?? false;

  return (
    <Modal
      open={txn !== null}
      onClose={onClose}
      size="md"
      title={t.common.edit}
      subtitle={txn ? `${formatMNT(income ? txn.credit : txn.debit)} · ${txn.bank_description}` : ""}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            loading={update.isPending}
            onClick={() => {
              if (!txn) return;
              update.mutate(
                {
                  statementId,
                  txnId: txn.id,
                  payload: income
                    ? { description, contract_id: contractId || null }
                    : { description, expense_account_code: accountCode || null },
                },
                { onSuccess: onClose, onError: (cause) => setError(errorMessage(cause)) },
              );
            }}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {income ? (
          <PickerField
            label={t.nav.customers}
            value={contractId}
            options={[{ value: "", label: t.common.none }, ...contracts]}
            onChange={setContractId}
          />
        ) : (
          <PickerField
            label={t.expenses.category}
            value={accountCode}
            options={categoryOptions}
            onChange={setAccountCode}
          />
        )}
        <TextField label={t.bank.ourDescription} value={description} onChange={setDescription} />
        {txn?.bank_counterpart ? (
          <p className="num text-sm text-ink-soft">
            {t.bank.counterpart}: {txn.bank_counterpart}
          </p>
        ) : null}
        {error ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------
// Хуулгын дэлгэрэнгүй
// --------------------------------------------------------------------------
function StatementDetail({ id, onBack }: { id: UUID; onBack: () => void }) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const { data: statement, isLoading } = useBankStatement(id);
  const accountsQuery = useBankAccounts({ active_only: true });
  const setAccount = useSetStatementAccountMutation();
  const fillDescriptions = useStatementActionMutation("fill-descriptions");
  const swapColumns = useStatementActionMutation("swap-debit-credit");
  const postFees = useStatementActionMutation("post-fees");
  const unpostFees = useStatementActionMutation("unpost-fees");
  const postAll = usePostAllMutation();
  const postRow = useTransactionActionMutation("post");
  const unpostRow = useTransactionActionMutation("unpost");

  const [editing, setEditing] = useState<BankTransaction | null>(null);

  const fail = (cause: unknown): void => {
    toastError(errorMessage(cause));
  };

  const accountOptions = useMemo(
    () => [
      { value: "", label: t.bank.selectAccount },
      ...(accountsQuery.data?.items ?? []).map((row) => ({
        value: row.id,
        label: `${row.bank_name} · ${row.account_number}`,
      })),
    ],
    [accountsQuery.data],
  );

  if (isLoading || !statement) {
    return (
      <div className="flex items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  const rows = statement.transactions.filter((row) => !row.is_fee);
  const locked = statement.posted_count > 0 || statement.fee.posted;

  const columns: Column<BankTransaction>[] = [
    {
      key: "date",
      header: t.common.date,
      numeric: true,
      render: (row) => (row.txn_date ? formatDate(row.txn_date) : "—"),
    },
    {
      key: "bank",
      header: t.bank.bankDescription,
      primary: true,
      render: (row) => (
        <span className="flex flex-col gap-0.5">
          <span className="line-clamp-2 text-[15px]">{row.bank_description || "—"}</span>
          {row.is_settlement ? (
            <StatusBadge size="sm" tone="action" label={t.bank.settlement} />
          ) : null}
        </span>
      ),
    },
    {
      key: "credit",
      header: t.bank.income,
      align: "right",
      numeric: true,
      render: (row) =>
        row.credit === "0.00" ? (
          "—"
        ) : (
          <span className="font-bold text-success-dark">{formatMNT(row.credit)}</span>
        ),
    },
    {
      key: "debit",
      header: t.bank.outcome,
      align: "right",
      numeric: true,
      render: (row) =>
        row.debit === "0.00" ? (
          "—"
        ) : (
          <span className="font-bold text-danger-dark">{formatMNT(row.debit)}</span>
        ),
    },
    {
      key: "target",
      header: t.bank.target,
      render: (row) => {
        const label = row.is_income
          ? (row.customer_name ?? null)
          : (row.expense_account_name ?? null);
        return label ? (
          <span className="text-[15px]">{label}</span>
        ) : (
          <StatusBadge size="sm" tone="warning" label={t.bank.notReady} />
        );
      },
    },
    {
      key: "desc",
      header: t.bank.ourDescription,
      hideOnMobile: true,
      render: (row) => <span className="line-clamp-2 text-sm">{row.description || "—"}</span>,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          {row.posted_at ? (
            <Button
              variant="ghost"
              size="md"
              icon={<Undo2 />}
              onClick={() =>
                unpostRow.mutate(
                  { statementId: id, txnId: row.id },
                  { onSuccess: () => toastSuccess(t.common.saved), onError: fail },
                )
              }
            >
              {t.bank.unpostRow}
            </Button>
          ) : (
            <>
              <Button variant="secondary" size="md" onClick={() => setEditing(row)}>
                {t.common.edit}
              </Button>
              <Button
                variant="primary"
                size="md"
                disabled={row.missing.length > 0}
                onClick={() =>
                  postRow.mutate(
                    { statementId: id, txnId: row.id },
                    { onSuccess: () => toastSuccess(t.common.saved), onError: fail },
                  )
                }
              >
                {t.bank.postRow}
              </Button>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" size="md" icon={<ChevronLeft />} onClick={onBack}>
          {t.common.back}
        </Button>
        <h1 className="min-w-0 flex-1 truncate text-2xl font-bold text-ink">
          {statement.filename || t.bank.statements}
        </h1>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatBox
          label={t.bank.period}
          value={
            statement.date_from
              ? `${formatDate(statement.date_from)} — ${formatDate(statement.date_to ?? statement.date_from)}`
              : "—"
          }
          tone="neutral"
        />
        <StatBox label={t.bank.totalCredit} value={formatMNT(statement.total_credit)} tone="success" />
        <StatBox label={t.bank.totalDebit} value={formatMNT(statement.total_debit)} tone="danger" />
        <StatBox
          label={t.bank.posted}
          value={`${statement.posted_count} / ${statement.txn_count}`}
          tone={statement.posted_count === statement.txn_count ? "success" : "warning"}
        />
      </div>

      {/* Данс + үйлдлүүд */}
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <PickerField
            label={t.bank.selectAccount}
            value={statement.bank_account_id ?? ""}
            options={accountOptions}
            disabled={locked}
            onChange={(value) =>
              setAccount.mutate(
                { id, bankAccountId: value || null },
                { onSuccess: () => toastSuccess(t.common.saved), onError: fail },
              )
            }
            className="min-w-[16rem]"
          />
          <Button
            variant="secondary"
            size="md"
            icon={<Wand2 />}
            onClick={() => fillDescriptions.mutate({ id }, { onError: fail })}
          >
            {t.bank.fillDescriptions}
          </Button>
          <Button
            variant="secondary"
            size="md"
            icon={<ArrowLeftRight />}
            disabled={locked}
            onClick={() => swapColumns.mutate({ id }, { onError: fail })}
          >
            {t.bank.swapColumns}
          </Button>
          <Button
            variant="success"
            size="md"
            icon={<CircleCheck />}
            disabled={statement.ready_count === 0}
            loading={postAll.isPending}
            onClick={() =>
              postAll.mutate(id, {
                onSuccess: (result) =>
                  toastSuccess(
                    `${result.posted} ${t.bank.postedCount}` +
                      (result.skipped.length
                        ? ` · ${result.skipped.length} ${t.bank.skippedCount}`
                        : ""),
                  ),
                onError: fail,
              })
            }
          >
            {t.bank.postAll} ({statement.ready_count})
          </Button>
        </div>
        {!statement.bank_account_id ? (
          <p className="mt-3 rounded-xl bg-warning-soft px-4 py-3 text-sm font-semibold text-warning-dark">
            {t.bank.accountRequired}
          </p>
        ) : null}
      </Card>

      {/* Шимтгэл */}
      {statement.fee.count > 0 ? (
        <Card title={t.bank.fee} subtitle={t.bank.feeHint}>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap items-baseline gap-4">
              <span className="num text-3xl font-black text-danger-dark">
                {formatMNT(statement.fee.total)}
              </span>
              <span className="text-sm text-ink-soft">
                {statement.fee.count} {t.bank.feeCount}
              </span>
              {statement.fee.posted && statement.fee.expense_number ? (
                <StatusBadge
                  size="sm"
                  tone="success"
                  label={`${t.bank.feePosted}${statement.fee.expense_number}`}
                />
              ) : null}
            </div>
            {statement.fee.posted ? (
              <Button
                variant="ghost"
                size="md"
                icon={<Undo2 />}
                onClick={() =>
                  unpostFees.mutate(
                    { id },
                    { onSuccess: () => toastSuccess(t.common.saved), onError: fail },
                  )
                }
              >
                {t.bank.unpostFees}
              </Button>
            ) : (
              <Button
                variant="primary"
                size="md"
                icon={<Receipt />}
                onClick={() =>
                  postFees.mutate(
                    { id },
                    { onSuccess: () => toastSuccess(t.common.saved), onError: fail },
                  )
                }
              >
                {t.bank.postFees}
              </Button>
            )}
          </div>
        </Card>
      ) : null}

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          rowClassName={(row) => (row.posted_at ? "bg-success-soft/30" : "")}
          empty={<EmptyState title={t.bank.noTransactions} hint={t.common.emptyHint} />}
        />
      </Card>

      <TxnEditModal statementId={id} txn={editing} onClose={() => setEditing(null)} />
    </div>
  );
}

// --------------------------------------------------------------------------
// Хуулгын жагсаалт
// --------------------------------------------------------------------------
export function BankStatementsPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [openId, setOpenId] = useState<UUID | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [deleting, setDeleting] = useState<BankStatement | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const statementsQuery = useBankStatements();
  const upload = useUploadStatementMutation();
  const remove = useDeleteStatementMutation();

  if (openId) return <StatementDetail id={openId} onBack={() => setOpenId(null)} />;

  const rows = statementsQuery.data?.items ?? [];

  const columns: Column<BankStatement>[] = [
    {
      key: "period",
      header: t.bank.period,
      primary: true,
      render: (row) => (
        <span className="flex flex-col gap-0.5">
          <span className="num font-semibold">
            {row.date_from
              ? `${formatDate(row.date_from)} — ${formatDate(row.date_to ?? row.date_from)}`
              : "—"}
          </span>
          <span className="truncate text-xs text-ink-soft">{row.filename}</span>
        </span>
      ),
    },
    {
      key: "account",
      header: t.bank.bankName,
      render: (row) =>
        row.bank_name ?? (
          <StatusBadge size="sm" tone="warning" label={t.bank.selectAccount} />
        ),
    },
    {
      key: "credit",
      header: t.bank.totalCredit,
      align: "right",
      numeric: true,
      render: (row) => <span className="text-success-dark">{formatMNT(row.total_credit)}</span>,
    },
    {
      key: "debit",
      header: t.bank.totalDebit,
      align: "right",
      numeric: true,
      render: (row) => <span className="text-danger-dark">{formatMNT(row.total_debit)}</span>,
    },
    {
      key: "posted",
      header: t.bank.posted,
      align: "right",
      numeric: true,
      render: (row) => (
        <span className={row.posted_count === row.txn_count ? "font-bold text-success-dark" : ""}>
          {row.posted_count} / {row.txn_count}
        </span>
      ),
    },
    {
      key: "uploaded",
      header: t.common.createdAt,
      numeric: true,
      hideOnMobile: true,
      render: (row) => (row.uploaded_at ? formatDateTime(row.uploaded_at) : "—"),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" size="md" onClick={() => setOpenId(row.id)}>
            {t.common.details}
          </Button>
          <Button variant="ghost" size="md" icon={<Trash2 />} onClick={() => setDeleting(row)}>
            {t.common.delete}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.bank.statements}
        subtitle={t.bank.statementsHint}
        actions={
          <>
            <Button
              variant="secondary"
              size="lg"
              icon={<Settings2 />}
              onClick={() => setConfigOpen(true)}
            >
              {t.bank.config}
            </Button>
            <Button
              variant="primary"
              size="lg"
              icon={<Upload />}
              loading={upload.isPending}
              onClick={() => fileRef.current?.click()}
            >
              {t.bank.upload}
            </Button>
          </>
        }
      />

      <input
        ref={fileRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          upload.mutate(file, {
            onSuccess: (statement) => {
              toastSuccess(`${statement.txn_count} ${t.common.rows}`);
              setOpenId(statement.id);
            },
            onError: (cause) => toastError(errorMessage(cause)),
          });
        }}
      />

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={statementsQuery.isLoading}
          empty={
            <EmptyState
              icon={<Landmark className="h-7 w-7" />}
              title={t.bank.noStatements}
              hint={t.bank.uploadHint}
              action={
                <Button variant="primary" size="md" icon={<Upload />} onClick={() => fileRef.current?.click()}>
                  {t.bank.upload}
                </Button>
              }
            />
          }
        />
      </Card>

      <ConfigModal open={configOpen} onClose={() => setConfigOpen(false)} />

      <ConfirmDialog
        open={deleting !== null}
        title={t.bank.deleteStatement}
        message={deleting ? `${deleting.filename} — ${t.bank.deleteConfirm}` : ""}
        variant="danger"
        confirmLabel={t.common.delete}
        loading={remove.isPending}
        onConfirm={() => {
          if (!deleting) return;
          remove.mutate(deleting.id, {
            onSuccess: () => {
              toastSuccess(t.common.saved);
              setDeleting(null);
            },
            onError: (cause) => {
              toastError(errorMessage(cause));
              setDeleting(null);
            },
          });
        }}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}

export default BankStatementsPage;
