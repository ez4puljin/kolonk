/**
 * Үйл ажиллагааны зардал — цалин, цахилгаан, түрээс, засвар г.м.
 *
 * Энэ дэлгэц нь орлого зардлын тайланд цэвэр ашгийг үнэн зөв гаргах цорын
 * ганц зам: борлуулалттай холбоогүй зардлыг НББ мэдлэггүй хүн ч бүртгэж
 * чадахаар том плитка, NumPad-аар зохион байгуулсан.
 *
 * Бэлнээр төлсөн зардал ээлжийн байвал зохих кассаас автоматаар хасагдана.
 */

import { useMemo, useState } from "react";
import { Plus, Receipt, Wallet } from "lucide-react";

import { useExpenseCategories, useExpenses, useCreateExpenseMutation } from "../../api/queries/expenses";
import { useBankAccounts } from "../../api/queries/bank";
import { useBranches } from "../../api/queries/branches";
import { useSuppliers } from "../../api/queries/procurement";
import type { Expense, ExpenseCategory } from "../../api/types";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Column, DataTable } from "../../components/ui/DataTable";
import { DateRangePicker } from "../../components/ui/DateRangePicker";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { TouchSelect } from "../../components/ui/TouchSelect";
import { t } from "../../i18n/mn";
import { formatDate, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, TextAreaField, TextField } from "../catalog/_shared";

const PAD_AMOUNT = "expense.amount";

/** Хамгийн түгээмэл зардлууд — дээр нь товч байдлаар харуулна. */
const QUICK_CODES = ["5301", "5311", "5312", "5321", "5331", "5341"];

function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function monthStartIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`;
}

const METHODS = [
  { value: "cash", label: t.expenses.methodCash },
  { value: "bank", label: t.expenses.methodBank },
  { value: "credit", label: t.expenses.methodCredit },
] as const;

export function ExpensesPage() {
  const [dateFrom, setDateFrom] = useState(monthStartIso);
  const [dateTo, setDateTo] = useState(todayIso);
  const [formOpen, setFormOpen] = useState(false);
  //  Салбарын шүүлт (жагсаалт) ба маягтын салбар — олон салбартай үед л.
  const [filterBranchId, setFilterBranchId] = useState("");

  const categoriesQuery = useExpenseCategories();
  const suppliersQuery = useSuppliers({ limit: 200 });
  const bankAccountsQuery = useBankAccounts({ active_only: true });
  const branchesQuery = useBranches();
  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );
  const listQuery = useExpenses({
    date_from: dateFrom,
    date_to: dateTo,
    branch_id: filterBranchId || undefined,
    limit: 200,
  });
  const createMutation = useCreateExpenseMutation();

  const openNumPad = useUiStore((state) => state.openNumPad);
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  // ---- маягтын төлөв ----
  const [accountCode, setAccountCode] = useState<string | null>(null);
  const [amount, setAmount] = useState("0.00");
  const [method, setMethod] = useState<string>("cash");
  const [hasVat, setHasVat] = useState(false);
  const [supplierId, setSupplierId] = useState<string | null>(null);
  /** Харилцахаас төлөх үед аль данснаас гарахыг заана. */
  const [bankAccountId, setBankAccountId] = useState<string | null>(null);
  const [expenseDate, setExpenseDate] = useState(todayIso);
  const [invoiceNo, setInvoiceNo] = useState("");
  const [description, setDescription] = useState("");

  const categories = useMemo<ExpenseCategory[]>(
    () => categoriesQuery.data ?? [],
    [categoriesQuery.data],
  );
  const suppliers = useMemo(() => suppliersQuery.data?.items ?? [], [suppliersQuery.data]);
  const bankAccounts = useMemo(
    () => bankAccountsQuery.data?.items ?? [],
    [bankAccountsQuery.data],
  );
  const result = listQuery.data;
  const rows = result?.items ?? [];

  const quick = useMemo(
    () => categories.filter((c) => QUICK_CODES.includes(c.code)),
    [categories],
  );

  const resetForm = (): void => {
    setAccountCode(null);
    setAmount("0.00");
    setMethod("cash");
    setHasVat(false);
    setSupplierId(null);
    setBankAccountId(null);
    setExpenseDate(todayIso());
    setInvoiceNo("");
    setDescription("");
  };

  const openForm = (code?: string): void => {
    resetForm();
    if (code) setAccountCode(code);
    setFormOpen(true);
  };

  const canSubmit =
    Boolean(accountCode) &&
    Number(amount) > 0 &&
    (method !== "credit" || Boolean(supplierId)) &&
    !createMutation.isPending;

  const submit = (): void => {
    if (!accountCode) return;
    createMutation.mutate(
      {
        account_code: accountCode,
        amount,
        payment_method: method,
        expense_date: expenseDate,
        has_vat: hasVat,
        supplier_id: supplierId,
        bank_account_id: method === "bank" ? bankAccountId : null,
        invoice_no: invoiceNo.trim() || null,
        description: description.trim() || null,
        // Шүүлтэд сонгосон салбарт бичнэ; сонгоогүй бол сервер хэрэглэгчийн
        // (эсвэл үндсэн) салбарыг өөрөө ононо.
        branch_id: filterBranchId || null,
      },
      {
        onSuccess: (created) => {
          toastSuccess(`${t.expenses.saved}: ${formatMNT(created.total)}`);
          setFormOpen(false);
          resetForm();
        },
        onError: (error: unknown) => {
          toastError(error instanceof Error ? error.message : t.common.error);
        },
      },
    );
  };

  const columns: Column<Expense>[] = [
    {
      key: "number",
      header: "№",
      render: (row) => <span className="num">{row.number}</span>,
      width: "5rem",
    },
    {
      key: "date",
      header: t.expenses.date,
      render: (row) => formatDate(row.expense_date),
      width: "8rem",
    },
    {
      key: "account",
      header: t.expenses.category,
      render: (row) => row.account_name,
      primary: true,
    },
    {
      key: "description",
      header: t.expenses.description,
      render: (row) => row.description ?? "—",
      hideOnMobile: true,
    },
    {
      key: "method",
      header: t.expenses.paymentMethod,
      render: (row) => row.payment_method_name,
      hideOnMobile: true,
    },
    {
      key: "supplier",
      header: t.expenses.supplier,
      render: (row) => row.supplier_name ?? "—",
      hideOnMobile: true,
    },
    {
      key: "vat",
      header: t.expenses.vat,
      render: (row) => formatMNT(row.vat_amount),
      align: "right",
      numeric: true,
      hideOnMobile: true,
    },
    {
      key: "total",
      header: t.expenses.total,
      render: (row) => <span className="font-bold">{formatMNT(row.total)}</span>,
      align: "right",
      numeric: true,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">{t.expenses.title}</h1>
          <p className="text-sm text-ink-soft">{t.expenses.subtitle}</p>
        </div>
        <Button size="lg" icon={<Plus />} onClick={() => openForm()}>
          {t.expenses.add}
        </Button>
      </header>

      {/* Түгээмэл зардлууд — нэг товшилтоор маягт нээнэ */}
      {quick.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {quick.map((c) => (
            <button
              key={c.code}
              type="button"
              onClick={() => openForm(c.code)}
              className="flex min-h-20 flex-col items-start justify-center gap-1 rounded-2xl border-2 border-line bg-surface px-4 py-3 text-left transition active:scale-[0.98] active:bg-surface-sunken"
            >
              <span className="num text-xs text-ink-soft">{c.code}</span>
              <span className="text-sm font-semibold text-ink">{c.name_mn}</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatBox
          label={t.expenses.periodTotal}
          value={formatMNT(result?.total_amount ?? "0")}
          icon={<Wallet />}
          tone="warning"
          size="lg"
        />
        <StatBox
          label={t.expenses.count}
          value={result?.total ?? 0}
          icon={<Receipt />}
        />
        <Card className="p-4">
          <div className="flex flex-col gap-3">
            <DateRangePicker
              value={{ from: dateFrom, to: dateTo }}
              onChange={(range) => {
                setDateFrom(range.from);
                setDateTo(range.to);
              }}
            />
            {branches.length > 1 ? (
              <TouchSelect
                label={t.branches.title}
                value={filterBranchId}
                onChange={setFilterBranchId}
                options={[
                  { value: "", label: t.branches.allBranches },
                  ...branches.map((branch) => ({ value: branch.id, label: branch.name })),
                ]}
                columns={1}
              />
            ) : null}
          </div>
        </Card>
      </div>

      {/* Дансаар нь задаргаа */}
      {result && result.by_account.length > 0 ? (
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-soft">
            {t.expenses.byCategory}
          </h2>
          <div className="flex flex-col gap-2">
            {result.by_account.map((row) => (
              <div key={row.account_code} className="flex items-center justify-between gap-4">
                <span className="text-sm text-ink">{row.account_name}</span>
                <span className="num text-sm font-bold text-ink">{formatMNT(row.amount)}</span>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        loading={listQuery.isLoading}
        emptyTitle={t.expenses.empty}
      />

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={t.expenses.add}
        size="lg"
      >
        <div className="flex flex-col gap-4">
          <TouchSelect
            label={t.expenses.category}
            value={accountCode}
            onChange={setAccountCode}
            options={categories.map((c) => ({ value: c.code, label: c.name_mn }))}
            columns={2}
          />

          <div>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-soft">
              {t.expenses.amount}
            </div>
            <button
              type="button"
              onClick={() =>
                openNumPad({
                  target: PAD_AMOUNT,
                  title: t.expenses.amount,
                  value: amount,
                  allowDecimal: true,
                  suffix: t.units.mnt,
                })
              }
              className="flex min-h-20 w-full items-center justify-between rounded-2xl border-2 border-line-strong bg-surface-alt px-6"
            >
              <span className="text-sm text-ink-soft">{t.expenses.totalPaid}</span>
              <span className="num text-3xl font-bold text-ink">{formatMNT(amount)}</span>
            </button>
          </div>

          <TouchSelect
            label={t.expenses.paymentMethod}
            value={method}
            onChange={(v) => {
              setMethod(v);
              if (v !== "credit") setSupplierId(null);
            }}
            options={METHODS.map((m) => ({ value: m.value, label: m.label }))}
            columns={3}
          />

          <label className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 border-line bg-surface px-4">
            <input
              type="checkbox"
              checked={hasVat}
              onChange={(e) => setHasVat(e.target.checked)}
              className="h-6 w-6 accent-action"
            />
            <span className="text-sm font-medium text-ink">{t.expenses.hasVat}</span>
          </label>

          {/* Харилцахаас төлөх бол аль данснаас гарахыг заана — дансны
              үлдэгдэл ерөнхий дэвтрээс данс тус бүрээр гарна. */}
          {method === "bank" && bankAccounts.length > 0 ? (
            <TouchSelect
              label={t.expenses.bankAccount}
              value={bankAccountId}
              onChange={setBankAccountId}
              options={bankAccounts.map((account) => ({
                value: account.id,
                label: `${account.bank_name} · ${account.account_number}`,
              }))}
              columns={2}
            />
          ) : null}

          {method === "credit" || suppliers.length > 0 ? (
            <TouchSelect
              label={
                method === "credit" ? t.expenses.supplierRequired : t.expenses.supplierOptional
              }
              value={supplierId}
              onChange={setSupplierId}
              options={suppliers.map((s) => ({ value: s.id, label: s.name }))}
              columns={2}
            />
          ) : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <DateField label={t.expenses.date} value={expenseDate} onChange={setExpenseDate} />
            <TextField
              label={t.expenses.invoiceNo}
              value={invoiceNo}
              onChange={setInvoiceNo}
              placeholder="—"
            />
          </div>

          <TextAreaField
            label={t.expenses.description}
            value={description}
            onChange={setDescription}
            rows={2}
          />

          <div className="flex gap-3">
            <Button variant="ghost" size="lg" className="flex-1" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              size="lg"
              className="flex-1"
              disabled={!canSubmit}
              loading={createMutation.isPending}
              onClick={submit}
            >
              {t.common.save}
            </Button>
          </div>
        </div>
      </Modal>

      <NumPadModal
        onSubmit={(target, value) => {
          if (target === PAD_AMOUNT) setAmount(value || "0");
        }}
      />
    </div>
  );
}

export default ExpensesPage;
