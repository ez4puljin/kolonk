import { useMemo, useState } from "react";
import { HandCoins, Landmark, Scale } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBankAccounts } from "../../api/queries/bank";
import {
  useSettlementBalances,
  useSettlementEntries,
  useSettlementPaymentMutation,
} from "../../api/queries/shipments";
import type { SettlementBalance, SettlementEntry } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { PAGE_SIZE } from "../../lib/constants";
import { dSum } from "../../lib/decimal";
import { formatDate, formatMNT, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, DateField, NumberField, Pager, PickerField, TextField } from "../catalog/_shared";

type TypeFilter = "all" | "charge" | "payment";

/** Төлбөр бүртгэх цонх. */
function PaymentModal({
  balances,
  defaultBranchId,
  onClose,
}: {
  balances: SettlementBalance[];
  defaultBranchId: string;
  onClose: () => void;
}) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);
  const paymentMutation = useSettlementPaymentMutation();
  const bankAccountsQuery = useBankAccounts({ active_only: true });

  const [branchId, setBranchId] = useState(defaultBranchId);
  const [amount, setAmount] = useState("");
  const [when, setWhen] = useState(todayInput());
  const [paidFrom, setPaidFrom] = useState<"cash" | "bank">("cash");
  const [fromAccountId, setFromAccountId] = useState("");
  const [toAccountId, setToAccountId] = useState("");
  const [note, setNote] = useState("");

  const branchOptions = balances.map((row) => ({
    value: row.branch_id,
    label: row.branch_name,
    hint: `Үлдэгдэл: ${formatMNT(row.balance)}`,
  }));
  const accountOptions = (bankAccountsQuery.data?.items ?? []).map((account) => ({
    value: account.id,
    label: `${account.bank_name} ${account.account_number}`,
    hint: account.holder_name || undefined,
  }));

  const selected = balances.find((row) => row.branch_id === branchId) ?? null;
  const canSubmit = Boolean(branchId) && Number(amount) > 0 && Boolean(toAccountId);

  const submit = (): void => {
    if (!canSubmit) return;
    paymentMutation.mutate(
      {
        branch_id: branchId,
        amount,
        entry_date: when || null,
        paid_from: paidFrom,
        from_bank_account_id: paidFrom === "bank" ? fromAccountId || null : null,
        to_bank_account_id: toAccountId,
        note: note.trim() || null,
      },
      {
        onSuccess: () => {
          toastSuccess("Төлбөр бүртгэгдлээ");
          onClose();
        },
        onError: (error) => toastError(errorMessage(error)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Салбарын төлбөр бүртгэх"
      subtitle="Салбараас толгойн данс руу шилжүүлсэн мөнгө"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="lg" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="lg"
            icon={<HandCoins />}
            disabled={!canSubmit}
            loading={paymentMutation.isPending}
            onClick={submit}
          >
            Бүртгэх
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <PickerField label={t.nav.branches} value={branchId} options={branchOptions} onChange={setBranchId} />
        <NumberField
          name="settlement-amount"
          label="Дүн"
          value={amount}
          onChange={setAmount}
          suffix="₮"
          maxDecimals={2}
          hint={selected ? `Тооцооны үлдэгдэл: ${formatMNT(selected.balance)}` : undefined}
          quick={selected && Number(selected.balance) > 0 ? [Number(selected.balance)] : undefined}
        />
        <ChipGroup<"cash" | "bank">
          value={paidFrom}
          onChange={setPaidFrom}
          options={[
            { value: "cash", label: "Салбарын кассаас" },
            { value: "bank", label: "Данснаас" },
          ]}
        />
        {paidFrom === "bank" ? (
          <PickerField
            label="Төлсөн данс"
            value={fromAccountId}
            options={accountOptions}
            onChange={setFromAccountId}
          />
        ) : null}
        <PickerField
          label="Мөнгө орсон данс (толгой)"
          value={toAccountId}
          options={accountOptions}
          onChange={setToAccountId}
        />
        <DateField label="Огноо" value={when} onChange={setWhen} max={todayInput()} />
        <TextField label={t.common.note} value={note} onChange={setNote} maxLength={255} />
      </div>
    </Modal>
  );
}

export function BranchSettlementsPage() {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [branchFilter, setBranchFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [paying, setPaying] = useState<string | null>(null);

  const balancesQuery = useSettlementBalances();
  const entriesQuery = useSettlementEntries({
    branch_id: branchFilter || undefined,
    entry_type: typeFilter === "all" ? undefined : typeFilter,
    limit: PAGE_SIZE,
    offset,
  });

  const balances = useMemo(() => balancesQuery.data ?? [], [balancesQuery.data]);
  const entries = useMemo(() => entriesQuery.data?.items ?? [], [entriesQuery.data]);
  const total = entriesQuery.data?.total ?? 0;

  const totalBalance = dSum(balances.map((row) => row.balance));

  const branchOptions = useMemo(
    () => [
      { value: "", label: t.common.all },
      ...balances.map((row) => ({ value: row.branch_id, label: row.branch_name })),
    ],
    [balances],
  );

  const entryColumns: Column<SettlementEntry>[] = [
    {
      key: "date",
      header: "Огноо",
      numeric: true,
      render: (row) => formatDate(row.entry_date),
    },
    {
      key: "branch",
      header: t.nav.branches,
      primary: true,
      render: (row) => <span className="font-bold">{row.branch_name ?? "—"}</span>,
    },
    {
      key: "type",
      header: "Төрөл",
      render: (row) => (
        <span
          className={
            row.entry_type === "charge"
              ? "font-semibold text-warning-dark"
              : "font-semibold text-success-dark"
          }
        >
          {row.entry_type_name ?? row.entry_type}
        </span>
      ),
    },
    {
      key: "amount",
      header: "Дүн",
      align: "right",
      numeric: true,
      render: (row) => (
        <span className={`num font-bold ${row.entry_type === "payment" ? "text-success-dark" : ""}`}>
          {row.entry_type === "payment" ? "−" : "+"}
          {formatMNT(row.amount)}
        </span>
      ),
    },
    {
      key: "account",
      header: "Данс",
      hideOnMobile: true,
      render: (row) => row.to_bank_account_name ?? "—",
    },
    {
      key: "note",
      header: t.common.note,
      hideOnMobile: true,
      render: (row) => <span className="text-ink-soft">{row.note ?? "—"}</span>,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.nav.branchSettlements}
        subtitle="Түгээсэн түлшний өр ба салбарын төлбөрийн тооцоо"
        actions={
          <Button variant="primary" size="lg" icon={<HandCoins />} onClick={() => setPaying("")}>
            Төлбөр бүртгэх
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox
          label="Нийт авах тооцоо"
          value={formatMNT(totalBalance)}
          tone={Number(totalBalance) > 0 ? "warning" : "success"}
        />
        {balances.slice(0, 3).map((row) => (
          <StatBox
            key={row.branch_id}
            label={row.branch_name}
            value={formatMNT(row.balance)}
            tone={Number(row.balance) > 0 ? "neutral" : "success"}
          />
        ))}
      </div>

      <Card title="Салбар бүрийн үлдэгдэл" flush>
        <DataTable
          columns={[
            {
              key: "branch",
              header: t.nav.branches,
              primary: true,
              render: (row: SettlementBalance) => (
                <span className="font-bold">
                  {row.branch_name} <span className="text-ink-soft">({row.branch_code})</span>
                </span>
              ),
            },
            {
              key: "charged",
              header: "Түгээсэн (өр)",
              align: "right",
              numeric: true,
              render: (row: SettlementBalance) => formatMNT(row.charged),
            },
            {
              key: "paid",
              header: "Төлсөн",
              align: "right",
              numeric: true,
              render: (row: SettlementBalance) => formatMNT(row.paid),
            },
            {
              key: "balance",
              header: "Үлдэгдэл",
              align: "right",
              numeric: true,
              render: (row: SettlementBalance) => (
                <span className={`num font-bold ${Number(row.balance) > 0 ? "text-warning-dark" : "text-success-dark"}`}>
                  {formatMNT(row.balance)}
                </span>
              ),
            },
            {
              key: "actions",
              header: t.common.actions,
              align: "right",
              render: (row: SettlementBalance) => (
                <Button variant="secondary" size="md" icon={<Landmark />} onClick={() => setPaying(row.branch_id)}>
                  Төлбөр
                </Button>
              ),
            },
          ]}
          rows={balances}
          rowKey={(row) => row.branch_id}
          loading={balancesQuery.isLoading}
          empty={
            <EmptyState
              icon={<Scale className="h-7 w-7" />}
              title={t.common.empty}
              hint="Ачилтаас салбарт түлш буулгахад тооцоо энд үүснэ"
            />
          }
        />
      </Card>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <ChipGroup<TypeFilter>
          value={typeFilter}
          onChange={(value) => {
            setTypeFilter(value);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "charge", label: "Өр" },
            { value: "payment", label: "Төлбөр" },
          ]}
        />
        <PickerField
          label={t.nav.branches}
          value={branchFilter}
          options={branchOptions}
          onChange={(value) => {
            setBranchFilter(value);
            setOffset(0);
          }}
          className="min-w-[14rem]"
        />
      </div>

      <Card title="Тооцооны түүх" flush>
        <DataTable
          columns={entryColumns}
          rows={entries}
          rowKey={(row) => row.id}
          loading={entriesQuery.isLoading}
          empty={<div className="px-4 py-10 text-center text-ink-soft">{t.common.empty}</div>}
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>

      {paying !== null ? (
        <PaymentModal balances={balances} defaultBranchId={paying} onClose={() => setPaying(null)} />
      ) : null}
    </div>
  );
}

export default BranchSettlementsPage;
