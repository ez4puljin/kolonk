import { useMemo, useState } from "react";
import { Ban, CreditCard, Plus, Wallet } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useBlockCardMutation,
  useCardTransactions,
  useCreateCardMutation,
  usePrepaidCards,
  useTopupCardMutation,
} from "../../api/queries/instruments";
import { useCustomers } from "../../api/queries/partners";
import type { CardStatus, CardTransaction, PaymentMethod, PrepaidCard } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { t } from "../../i18n/mn";
import { CARD_STATUS_META, PAGE_SIZE, QUICK_CASH, statusMeta } from "../../lib/constants";
import { dSum, dToNumber } from "../../lib/decimal";
import { formatDateTime, formatMNT } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import {
  ChipGroup,
  matchesQuery,
  NumberField,
  Pager,
  PickerField,
  SearchInput,
  TextAreaField,
  TextField,
} from "../catalog/_shared";

type StatusFilter = "all" | CardStatus;

const TENDERS: readonly { value: PaymentMethod; label: string }[] = [
  { value: "cash", label: t.tender.cash },
  { value: "card", label: t.tender.card },
  { value: "qr", label: t.tender.qr },
];

export function PrepaidCardsPage() {
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<PrepaidCard | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [cardNo, setCardNo] = useState("");
  const [holder, setHolder] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [initialAmount, setInitialAmount] = useState("");
  const [createTender, setCreateTender] = useState<PaymentMethod>("cash");
  const [createError, setCreateError] = useState<string | null>(null);

  const [topupCard, setTopupCard] = useState<PrepaidCard | null>(null);
  const [topupAmount, setTopupAmount] = useState("");
  const [topupTender, setTopupTender] = useState<PaymentMethod>("cash");
  const [topupError, setTopupError] = useState<string | null>(null);

  const [blocking, setBlocking] = useState<PrepaidCard | null>(null);
  const [blockReason, setBlockReason] = useState("");
  const [blockError, setBlockError] = useState<string | null>(null);

  const cardsQuery = usePrepaidCards({
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 200,
  });
  const customersQuery = useCustomers({ active_only: true, limit: 200 });
  const transactionsQuery = useCardTransactions(selected?.id);

  const createMutation = useCreateCardMutation();
  const topupMutation = useTopupCardMutation();
  const blockMutation = useBlockCardMutation();

  const allCards = useMemo(() => cardsQuery.data?.items ?? [], [cardsQuery.data]);
  const filtered = useMemo(
    () => allCards.filter((card) => matchesQuery([card.card_no, card.holder_name, card.customer_name], query)),
    [allCards, query],
  );
  const rows = useMemo(() => filtered.slice(offset, offset + PAGE_SIZE), [filtered, offset]);

  const totals = useMemo(
    () => ({
      count: filtered.length,
      active: filtered.filter((card) => card.status === "active").length,
      balance: dSum(filtered.map((card) => card.balance)),
    }),
    [filtered],
  );

  const customerOptions = useMemo(
    () => [
      { value: "", label: t.common.none },
      ...(customersQuery.data?.items ?? []).map((customer) => ({
        value: customer.id,
        label: customer.name,
      })),
    ],
    [customersQuery.data],
  );

  const submitCreate = (): void => {
    if (cardNo.trim() === "") return;
    setCreateError(null);
    createMutation.mutate(
      {
        card_no: cardNo.trim(),
        holder_name: holder.trim() || null,
        customer_id: customerId || null,
        initial_amount: initialAmount === "" ? "0" : initialAmount,
        tender_method: createTender,
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setCreateOpen(false);
          setCardNo("");
          setHolder("");
          setCustomerId("");
          setInitialAmount("");
        },
        onError: (error) => setCreateError(errorMessage(error)),
      },
    );
  };

  const submitTopup = (): void => {
    if (!topupCard || dToNumber(topupAmount) <= 0) return;
    setTopupError(null);
    topupMutation.mutate(
      { id: topupCard.id, payload: { amount: topupAmount, tender_method: topupTender } },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setTopupCard(null);
          setTopupAmount("");
        },
        onError: (error) => setTopupError(errorMessage(error)),
      },
    );
  };

  const submitBlock = (): void => {
    if (!blocking) return;
    setBlockError(null);
    blockMutation.mutate(
      { id: blocking.id, payload: { reason: blockReason.trim() || null } },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          setBlocking(null);
          setBlockReason("");
        },
        onError: (error) => setBlockError(errorMessage(error)),
      },
    );
  };

  const columns: Column<PrepaidCard>[] = [
    {
      key: "card_no",
      header: t.partners.cardNo,
      primary: true,
      numeric: true,
      render: (row) => <span className="font-bold tracking-wider">{row.card_no}</span>,
    },
    { key: "holder", header: t.partners.holderName, render: (row) => row.holder_name ?? "—" },
    { key: "customer", header: t.partners.customer, hideOnMobile: true, render: (row) => row.customer_name ?? "—" },
    {
      key: "balance",
      header: t.common.balance,
      align: "right",
      numeric: true,
      render: (row) => <span className="text-lg font-bold">{formatMNT(row.balance)}</span>,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => <StatusBadge size="sm" meta={statusMeta(CARD_STATUS_META, row.status, row.status_name)} />,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      hideOnMobile: true,
      render: (row) => (
        <div className="flex justify-end gap-2">
          {row.status === "active" ? (
            <>
              <Button
                variant="primary"
                size="md"
                icon={<Wallet />}
                onClick={(event) => {
                  event.stopPropagation();
                  setTopupCard(row);
                  setTopupAmount("");
                  setTopupTender("cash");
                  setTopupError(null);
                }}
              >
                {t.partners.topup}
              </Button>
              <Button
                variant="danger"
                size="md"
                icon={<Ban />}
                onClick={(event) => {
                  event.stopPropagation();
                  setBlocking(row);
                  setBlockReason("");
                  setBlockError(null);
                }}
              >
                {t.partners.blockCard}
              </Button>
            </>
          ) : null}
        </div>
      ),
    },
  ];

  const transactionColumns: Column<CardTransaction>[] = [
    {
      key: "created_at",
      header: t.common.dateTime,
      primary: true,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "tx_type",
      header: t.inventory.txType,
      render: (row) => (
        <StatusBadge
          size="sm"
          tone={row.tx_type === "topup" ? "success" : row.tx_type === "refund" ? "warning" : "action"}
          label={row.tx_type_name || row.tx_type}
        />
      ),
    },
    {
      key: "amount",
      header: t.common.amount,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.amount)}</span>,
    },
    {
      key: "balance_after",
      header: t.tanks.balanceAfter,
      align: "right",
      numeric: true,
      render: (row) => formatMNT(row.balance_after),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.partners.prepaidCards}
        actions={
          <Button variant="primary" size="lg" icon={<Plus />} onClick={() => setCreateOpen(true)}>
            {t.partners.newCard}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.partners.prepaidCards} value={totals.count} tone="neutral" />
        <StatBox label={t.status.active} value={totals.active} tone="success" />
        <StatBox label={t.common.balance} value={formatMNT(totals.balance)} tone="warning" size="lg" />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
          placeholder={t.tender.scanCard}
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
            { value: "blocked", label: t.status.blocked },
            { value: "closed", label: t.status.closed },
          ]}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          onRowClick={setSelected}
          loading={cardsQuery.isLoading}
          empty={
            <EmptyState
              icon={<CreditCard className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                <Button variant="primary" size="md" onClick={() => setCreateOpen(true)}>
                  {t.partners.newCard}
                </Button>
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={filtered.length} onChange={setOffset} />}
        />
      </Card>

      {/* Картын гүйлгээ */}
      <Modal
        open={selected !== null}
        onClose={() => setSelected(null)}
        size="lg"
        title={t.partners.cardTransactions}
        subtitle={selected ? `${selected.card_no} · ${formatMNT(selected.balance)}` : ""}
      >
        <div className="flex flex-col gap-4">
          {selected && selected.status === "active" ? (
            <div className="flex flex-wrap gap-2.5">
              <Button
                variant="primary"
                size="md"
                icon={<Wallet />}
                onClick={() => {
                  setTopupCard(selected);
                  setTopupAmount("");
                  setTopupTender("cash");
                  setTopupError(null);
                }}
              >
                {t.partners.topup}
              </Button>
              <Button
                variant="danger"
                size="md"
                icon={<Ban />}
                onClick={() => {
                  setBlocking(selected);
                  setBlockReason("");
                  setBlockError(null);
                }}
              >
                {t.partners.blockCard}
              </Button>
            </div>
          ) : null}

          <DataTable
            columns={transactionColumns}
            rows={transactionsQuery.data?.items ?? []}
            rowKey={(row) => row.id}
            loading={transactionsQuery.isLoading}
            empty={<EmptyState compact title={t.common.empty} hint={t.common.emptyHint} />}
          />
        </div>
      </Modal>

      {/* Шинэ карт */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        size="md"
        title={t.partners.newCard}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setCreateOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={cardNo.trim() === ""}
              loading={createMutation.isPending}
              onClick={submitCreate}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField label={t.partners.cardNo} value={cardNo} onChange={setCardNo} />
          <TextField label={t.partners.holderName} value={holder} onChange={setHolder} />
          <PickerField
            label={t.partners.customer}
            value={customerId}
            options={customerOptions}
            onChange={setCustomerId}
          />
          <NumberField
            name="card-initial-amount"
            label={t.partners.initialAmount}
            value={initialAmount}
            onChange={setInitialAmount}
            suffix={t.units.mnt}
            quick={QUICK_CASH.slice(0, 3)}
          />
          <ChipGroup<PaymentMethod>
            label={t.tender.title}
            value={createTender}
            onChange={setCreateTender}
            options={TENDERS.map((tender) => ({ value: tender.value, label: tender.label }))}
          />
          {createError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {createError}
            </p>
          ) : null}
        </div>
      </Modal>

      {/* Цэнэглэх */}
      <Modal
        open={topupCard !== null}
        onClose={() => setTopupCard(null)}
        size="md"
        title={t.partners.topup}
        subtitle={topupCard ? `${topupCard.card_no} · ${formatMNT(topupCard.balance)}` : ""}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setTopupCard(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={dToNumber(topupAmount) <= 0}
              loading={topupMutation.isPending}
              onClick={submitTopup}
            >
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <NumberField
            name="card-topup-amount"
            label={t.partners.topupAmount}
            value={topupAmount}
            onChange={setTopupAmount}
            suffix={t.units.mnt}
            quick={QUICK_CASH.slice(0, 3)}
          />
          <ChipGroup<PaymentMethod>
            label={t.tender.title}
            value={topupTender}
            onChange={setTopupTender}
            options={TENDERS.map((tender) => ({ value: tender.value, label: tender.label }))}
          />
          {topupCard ? (
            <div className="flex items-baseline justify-between gap-3 rounded-xl border border-line bg-surface-alt px-4 py-3">
              <span className="text-sm text-ink-soft">{t.tanks.balanceAfter}</span>
              <span className="num text-2xl font-bold text-ink">
                {formatMNT(dSum([topupCard.balance, topupAmount]))}
              </span>
            </div>
          ) : null}
          {topupError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {topupError}
            </p>
          ) : null}
        </div>
      </Modal>

      {/* Карт хаах */}
      <Modal
        open={blocking !== null}
        onClose={() => setBlocking(null)}
        size="sm"
        title={t.partners.blockCard}
        subtitle={blocking?.card_no}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setBlocking(null)}>
              {t.common.cancel}
            </Button>
            <Button variant="danger" size="md" loading={blockMutation.isPending} onClick={submitBlock}>
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <p className="text-[15px] text-ink">{t.common.deleteConfirm}</p>
          <TextAreaField label={t.common.reason} value={blockReason} onChange={setBlockReason} />
          {blockError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {blockError}
            </p>
          ) : null}
        </div>
      </Modal>
    </div>
  );
}

export default PrepaidCardsPage;
