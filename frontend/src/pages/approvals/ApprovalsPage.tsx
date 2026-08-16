import { useMemo, useState } from "react";
import { ArrowRight, Check, ClipboardCheck, X } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useApprovePriceChangeMutation,
  useApproveRefundMutation,
  usePriceChanges,
  useRefunds,
  useRejectPriceChangeMutation,
  useRejectRefundMutation,
} from "../../api/queries/approvals";
import type { PriceChange, Refund } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar } from "../../components/ui/TabBar";
import { useCan } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { PAGE_SIZE } from "../../lib/constants";
import { dIsNegative, dToNumber } from "../../lib/decimal";
import { formatDateTime, formatMNT, formatPct, formatQty } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { Pager } from "../catalog/_shared";

type Tab = "prices" | "refunds";
type Decision = { kind: "approve" | "reject"; tab: Tab; id: string; label: string };

export function ApprovalsPage() {
  const canApprovePrices = useCan("prices.approve");
  const canApproveRefunds = useCan("sales.refund.approve");
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [tab, setTab] = useState<Tab>("prices");
  const [priceOffset, setPriceOffset] = useState(0);
  const [refundOffset, setRefundOffset] = useState(0);
  const [decision, setDecision] = useState<Decision | null>(null);

  const priceQuery = usePriceChanges({ status: "pending", limit: PAGE_SIZE, offset: priceOffset });
  const refundQuery = useRefunds({ status: "pending", limit: PAGE_SIZE, offset: refundOffset });

  const approvePrice = useApprovePriceChangeMutation();
  const rejectPrice = useRejectPriceChangeMutation();
  const approveRefund = useApproveRefundMutation();
  const rejectRefund = useRejectRefundMutation();

  const priceRows = useMemo(() => priceQuery.data?.items ?? [], [priceQuery.data]);
  const refundRows = useMemo(() => refundQuery.data?.items ?? [], [refundQuery.data]);
  const priceTotal = priceQuery.data?.total ?? 0;
  const refundTotal = refundQuery.data?.total ?? 0;

  const pending = priceTotal + refundTotal;
  const busy =
    approvePrice.isPending || rejectPrice.isPending || approveRefund.isPending || rejectRefund.isPending;

  const confirmDecision = (): void => {
    if (!decision) return;
    const options = {
      onSuccess: () => {
        toastSuccess(t.common.saved);
        setDecision(null);
      },
      onError: (error: unknown) => {
        toastError(errorMessage(error));
        setDecision(null);
      },
    };

    if (decision.tab === "prices") {
      if (decision.kind === "approve") approvePrice.mutate({ id: decision.id }, options);
      else rejectPrice.mutate({ id: decision.id }, options);
      return;
    }
    if (decision.kind === "approve") approveRefund.mutate({ id: decision.id }, options);
    else rejectRefund.mutate({ id: decision.id }, options);
  };

  const decisionButtons = (kind: Tab, id: string, label: string, allowed: boolean) =>
    allowed ? (
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button
          variant="success"
          size="md"
          icon={<Check />}
          onClick={() => setDecision({ kind: "approve", tab: kind, id, label })}
        >
          {t.refunds.approve}
        </Button>
        <Button
          variant="danger"
          size="md"
          icon={<X />}
          onClick={() => setDecision({ kind: "reject", tab: kind, id, label })}
        >
          {t.refunds.reject}
        </Button>
      </div>
    ) : (
      <StatusBadge size="sm" tone="warning" label={t.approvals.pending} />
    );

  const priceColumns: Column<PriceChange>[] = [
    {
      key: "target",
      header: t.prices.target,
      primary: true,
      render: (row) => (
        <span className="flex flex-col">
          <span className="text-base font-bold text-ink">{row.target_name ?? "—"}</span>
          <span className="text-xs text-ink-soft">
            {row.target_type === "fuel" ? t.prices.targetFuel : t.prices.targetProduct} ·{" "}
            {row.requested_by_name ?? "—"}
          </span>
        </span>
      ),
    },
    {
      key: "created_at",
      header: t.common.date,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "prices",
      header: `${t.prices.oldPrice} → ${t.prices.newPrice}`,
      align: "right",
      numeric: true,
      render: (row) => {
        const oldPrice = dToNumber(row.old_price);
        const pct = oldPrice > 0 ? (dToNumber(row.diff) / oldPrice) * 100 : null;
        const negative = dIsNegative(row.diff);
        return (
          <span className="flex flex-col items-end">
            <span className="inline-flex items-center gap-2">
              <span className="text-ink-soft line-through">{formatMNT(row.old_price)}</span>
              <ArrowRight className="h-4 w-4 text-ink-faint" />
              <span className="text-xl font-bold text-ink">{formatMNT(row.new_price)}</span>
            </span>
            <span className={`text-sm font-semibold ${negative ? "text-success-dark" : "text-danger-dark"}`}>
              {negative ? "" : "+"}
              {formatMNT(row.diff)}
              {pct !== null ? ` (${negative ? "" : "+"}${formatPct(pct)})` : ""}
            </span>
          </span>
        );
      },
    },
    {
      key: "reason",
      header: t.common.reason,
      hideOnMobile: true,
      render: (row) => <span className="text-ink-soft">{row.reason ?? "—"}</span>,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        decisionButtons("prices", row.id, `${row.target_name ?? ""} → ${formatMNT(row.new_price)}`, canApprovePrices),
    },
  ];

  const refundColumns: Column<Refund>[] = [
    {
      key: "sale",
      header: t.sales.saleNo,
      primary: true,
      render: (row) => (
        <span className="flex flex-col">
          <span className="text-base font-bold text-ink">№{row.sale_number ?? "—"}</span>
          <span className="text-xs text-ink-soft">
            {row.requested_by_name ?? "—"} · {row.refund_type === "full" ? t.refunds.full : t.refunds.partial}
          </span>
        </span>
      ),
    },
    {
      key: "created_at",
      header: t.common.date,
      numeric: true,
      render: (row) => formatDateTime(row.created_at),
    },
    {
      key: "items",
      header: t.sales.items,
      render: (row) => (
        <span className="flex flex-col gap-0.5">
          {row.items.slice(0, 3).map((item) => (
            <span key={item.id} className="num text-sm text-ink-soft">
              {item.name} · {formatQty(item.qty)}
            </span>
          ))}
          {row.items.length > 3 ? (
            <span className="text-xs text-ink-faint">+{row.items.length - 3}</span>
          ) : null}
        </span>
      ),
    },
    {
      key: "amount",
      header: t.refunds.refundAmount,
      align: "right",
      numeric: true,
      render: (row) => (
        <span className="flex flex-col items-end">
          <span className="text-xl font-bold text-danger-dark">{formatMNT(row.amount)}</span>
          <span className="text-xs text-ink-soft">
            {row.refund_method_name} · {row.restock ? t.refunds.restock : t.common.no}
          </span>
        </span>
      ),
    },
    {
      key: "reason",
      header: t.common.reason,
      hideOnMobile: true,
      render: (row) => <span className="text-ink-soft">{row.reason ?? "—"}</span>,
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        decisionButtons("refunds", row.id, `№${row.sale_number ?? ""} · ${formatMNT(row.amount)}`, canApproveRefunds),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.approvals.title}
        subtitle={`${t.prices.pendingCount}: ${pending}`}
      >
        <TabBar<Tab>
          variant="underline"
          value={tab}
          onChange={setTab}
          items={[
            { value: "prices", label: t.approvals.priceChanges, badge: priceTotal || null },
            { value: "refunds", label: t.approvals.refunds, badge: refundTotal || null },
          ]}
        />
      </PageHeader>

      {tab === "prices" ? (
        <Card flush>
          <DataTable
            columns={priceColumns}
            rows={priceRows}
            rowKey={(row) => row.id}
            loading={priceQuery.isLoading}
            empty={
              <EmptyState
                icon={<ClipboardCheck className="h-7 w-7" />}
                title={t.approvals.nothingPending}
                hint={t.common.emptyHint}
              />
            }
            footer={
              <Pager offset={priceOffset} limit={PAGE_SIZE} total={priceTotal} onChange={setPriceOffset} />
            }
          />
        </Card>
      ) : (
        <Card flush>
          <DataTable
            columns={refundColumns}
            rows={refundRows}
            rowKey={(row) => row.id}
            loading={refundQuery.isLoading}
            empty={
              <EmptyState
                icon={<ClipboardCheck className="h-7 w-7" />}
                title={t.approvals.nothingPending}
                hint={t.common.emptyHint}
              />
            }
            footer={
              <Pager offset={refundOffset} limit={PAGE_SIZE} total={refundTotal} onChange={setRefundOffset} />
            }
          />
        </Card>
      )}

      <ConfirmDialog
        open={decision !== null}
        title={decision?.kind === "approve" ? t.refunds.approve : t.refunds.reject}
        variant={decision?.kind === "approve" ? "success" : "danger"}
        confirmLabel={decision?.kind === "approve" ? t.refunds.approve : t.refunds.reject}
        loading={busy}
        onConfirm={confirmDecision}
        onCancel={() => setDecision(null)}
        message={
          decision ? (
            <div className="space-y-2">
              <p>
                {decision.tab === "prices"
                  ? decision.kind === "approve"
                    ? t.prices.approveConfirm
                    : t.common.deleteConfirm
                  : decision.kind === "approve"
                    ? t.refunds.approveConfirm
                    : t.refunds.rejectConfirm}
              </p>
              <p className="num font-bold text-ink">{decision.label}</p>
            </div>
          ) : null
        }
      />
    </div>
  );
}

export default ApprovalsPage;
