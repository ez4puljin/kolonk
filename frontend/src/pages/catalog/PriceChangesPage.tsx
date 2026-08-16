import { useMemo, useState } from "react";
import { ArrowRight, Check, Plus, TrendingUp, X } from "lucide-react";

import { errorMessage } from "../../api/client";
import {
  useApprovePriceChangeMutation,
  useCreatePriceChangeMutation,
  usePriceChanges,
  useRejectPriceChangeMutation,
} from "../../api/queries/approvals";
import { useBranches } from "../../api/queries/branches";
import { useFuels } from "../../api/queries/fuels";
import { useProducts } from "../../api/queries/products";
import type { ApprovalStatus, PriceChange, PriceTargetType } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { TabBar } from "../../components/ui/TabBar";
import { useCan } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { APPROVAL_STATUS_META, PAGE_SIZE, statusMeta } from "../../lib/constants";
import { dIsNegative, dToNumber } from "../../lib/decimal";
import { formatDateTime, formatMNT, formatPct } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, DateField, NumberField, Pager, PickerField, TextAreaField } from "./_shared";

type Decision = { row: PriceChange; kind: "approve" | "reject" };

/** Хувийн өөрчлөлт — зөвхөн харуулах зорилготой тооцоо. */
function diffPct(row: PriceChange): number | null {
  const oldPrice = dToNumber(row.old_price);
  if (oldPrice <= 0) return null;
  return (dToNumber(row.diff) / oldPrice) * 100;
}

export function PriceChangesPage() {
  const canApprove = useCan("prices.approve");
  const canRequest = useCan("prices.request");
  const toastSuccess = useUiStore((state) => state.toastSuccess);
  const toastError = useUiStore((state) => state.toastError);

  const [tab, setTab] = useState<ApprovalStatus>("pending");
  const [offset, setOffset] = useState(0);
  const [decision, setDecision] = useState<Decision | null>(null);

  const [requestOpen, setRequestOpen] = useState(false);
  const [targetType, setTargetType] = useState<PriceTargetType>("fuel");
  const [branchId, setBranchId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [newPrice, setNewPrice] = useState("");
  /** Хэрэгжих огноо — хоосон бол батламагц шууд. Тосны үнийг маргаашнаас. */
  const [effectiveDate, setEffectiveDate] = useState("");
  const [reason, setReason] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);

  const listQuery = usePriceChanges({ status: tab, limit: PAGE_SIZE, offset });
  const pendingQuery = usePriceChanges({ status: "pending", limit: 1 });
  const fuelsQuery = useFuels({ active_only: true });
  const productsQuery = useProducts({ limit: 500 });
  const branchesQuery = useBranches();

  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );

  const createMutation = useCreatePriceChangeMutation();
  const approveMutation = useApprovePriceChangeMutation();
  const rejectMutation = useRejectPriceChangeMutation();

  const rows = useMemo(() => listQuery.data?.items ?? [], [listQuery.data]);
  const total = listQuery.data?.total ?? 0;
  const pendingCount = pendingQuery.data?.total ?? 0;

  const targetOptions = useMemo(() => {
    if (targetType === "fuel") {
      return (fuelsQuery.data?.items ?? []).map((fuel) => ({
        value: fuel.id,
        label: fuel.name_mn,
        hint: `${fuel.code} · ${formatMNT(fuel.price_per_liter)}`,
      }));
    }
    return (productsQuery.data?.items ?? [])
      .filter((product) => product.is_active)
      .map((product) => ({
        value: product.id,
        label: product.name_mn,
        hint: `${product.sku} · ${formatMNT(product.price)}`,
      }));
  }, [targetType, fuelsQuery.data, productsQuery.data]);

  const currentPrice = useMemo(() => {
    if (targetType === "fuel") {
      return (fuelsQuery.data?.items ?? []).find((fuel) => fuel.id === targetId)?.price_per_liter ?? "0";
    }
    return (productsQuery.data?.items ?? []).find((product) => product.id === targetId)?.price ?? "0";
  }, [targetType, targetId, fuelsQuery.data, productsQuery.data]);

  const submitRequest = (): void => {
    if (targetId === "" || dToNumber(newPrice) <= 0) return;
    setRequestError(null);
    createMutation.mutate(
      {
        target_type: targetType,
        branch_id: branchId || null,
        fuel_id: targetType === "fuel" ? targetId : null,
        product_id: targetType === "product" ? targetId : null,
        new_price: newPrice,
        effective_date: effectiveDate || null,
        reason: reason.trim() || null,
      },
      {
        onSuccess: () => {
          toastSuccess(t.refunds.requested);
          setRequestOpen(false);
          setTargetId("");
          setNewPrice("");
          setReason("");
        },
        onError: (error) => setRequestError(errorMessage(error)),
      },
    );
  };

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
    if (decision.kind === "approve") {
      approveMutation.mutate({ id: decision.row.id }, options);
    } else {
      rejectMutation.mutate({ id: decision.row.id }, options);
    }
  };

  const columns: Column<PriceChange>[] = [
    {
      key: "target",
      header: t.prices.target,
      primary: true,
      render: (row) => (
        <span className="flex flex-col">
          <span className="font-semibold text-ink">{row.target_name ?? "—"}</span>
          <span className="text-xs text-ink-soft">
            {row.target_type === "fuel" ? t.prices.targetFuel : t.prices.targetProduct}
            {" · "}
            {row.branch_name ?? t.branches.allBranches}
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
      render: (row) => (
        <span className="inline-flex items-center gap-2">
          <span className="text-ink-soft line-through">{formatMNT(row.old_price)}</span>
          <ArrowRight className="h-4 w-4 text-ink-faint" />
          <span className="text-lg font-bold text-ink">{formatMNT(row.new_price)}</span>
        </span>
      ),
    },
    {
      key: "diff",
      header: t.prices.diff,
      align: "right",
      numeric: true,
      render: (row) => {
        const pct = diffPct(row);
        const negative = dIsNegative(row.diff);
        return (
          <span className={`font-bold ${negative ? "text-success-dark" : "text-danger-dark"}`}>
            {negative ? "" : "+"}
            {formatMNT(row.diff)}
            {pct !== null ? (
              <span className="ml-2 text-sm font-semibold">
                ({negative ? "" : "+"}
                {formatPct(pct)})
              </span>
            ) : null}
          </span>
        );
      },
    },
    {
      key: "requested_by",
      header: t.refunds.requestedBy,
      hideOnMobile: true,
      render: (row) => row.requested_by_name ?? "—",
    },
    {
      key: "reason",
      header: t.common.reason,
      hideOnMobile: true,
      render: (row) => <span className="text-ink-soft">{row.reason ?? "—"}</span>,
    },
    {
      key: "status",
      header: t.common.status,
      render: (row) => (
        <span className="flex flex-col gap-1">
          <StatusBadge size="sm" meta={statusMeta(APPROVAL_STATUS_META, row.status, row.status_name)} />
          {row.decided_by_name ? (
            <span className="text-xs text-ink-soft">{row.decided_by_name}</span>
          ) : null}
        </span>
      ),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) =>
        canApprove && row.status === "pending" ? (
          <div className="flex justify-end gap-2">
            <Button
              variant="success"
              size="md"
              icon={<Check />}
              onClick={() => setDecision({ row, kind: "approve" })}
            >
              {t.prices.approve}
            </Button>
            <Button
              variant="danger"
              size="md"
              icon={<X />}
              onClick={() => setDecision({ row, kind: "reject" })}
            >
              {t.prices.reject}
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.prices.title}
        subtitle={t.products.priceChangeOnly}
        actions={
          canRequest ? (
            <Button variant="primary" size="lg" icon={<Plus />} onClick={() => setRequestOpen(true)}>
              {t.prices.request}
            </Button>
          ) : null
        }
      >
        <TabBar<ApprovalStatus>
          variant="underline"
          value={tab}
          onChange={(next) => {
            setTab(next);
            setOffset(0);
          }}
          items={[
            { value: "pending", label: t.approvals.pending, badge: pendingCount || null },
            { value: "approved", label: t.approvals.approved },
            { value: "rejected", label: t.approvals.rejected },
          ]}
        />
      </PageHeader>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={listQuery.isLoading}
          empty={
            <EmptyState
              icon={<TrendingUp className="h-7 w-7" />}
              title={t.approvals.nothingPending}
              hint={t.common.emptyHint}
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />}
        />
      </Card>

      <Modal
        open={requestOpen}
        onClose={() => setRequestOpen(false)}
        size="md"
        title={t.prices.request}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setRequestOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={targetId === "" || dToNumber(newPrice) <= 0}
              loading={createMutation.isPending}
              onClick={submitRequest}
            >
              {t.refunds.request}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <ChipGroup<PriceTargetType>
            label={t.prices.target}
            value={targetType}
            onChange={(next) => {
              setTargetType(next);
              setTargetId("");
            }}
            options={[
              { value: "fuel", label: t.prices.targetFuel },
              { value: "product", label: t.prices.targetProduct },
            ]}
          />
          {branches.length > 1 ? (
            <PickerField
              label={t.branches.title}
              value={branchId}
              options={[
                { value: "", label: t.branches.allBranches },
                ...branches.map((branch) => ({ value: branch.id, label: branch.name })),
              ]}
              onChange={setBranchId}
            />
          ) : null}
          <PickerField
            label={t.common.name}
            value={targetId}
            options={targetOptions}
            onChange={(value) => {
              setTargetId(value);
              const fuel = (fuelsQuery.data?.items ?? []).find((item) => item.id === value);
              const product = (productsQuery.data?.items ?? []).find((item) => item.id === value);
              setNewPrice(fuel?.price_per_liter ?? product?.price ?? "");
            }}
          />
          <div className="rounded-xl border border-line bg-surface-alt px-4 py-3">
            <div className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
              {t.prices.oldPrice}
            </div>
            <div className="num text-2xl font-bold text-ink">{formatMNT(currentPrice)}</div>
          </div>
          <NumberField
            name="price-change-new"
            label={t.prices.newPrice}
            value={newPrice}
            onChange={setNewPrice}
            suffix={t.units.mnt}
          />
          <DateField
            label={t.prices.effectiveDate}
            value={effectiveDate}
            onChange={setEffectiveDate}
          />
          <p className="text-sm text-ink-soft">{t.prices.effectiveHint}</p>
          <TextAreaField label={t.common.reason} value={reason} onChange={setReason} />
          {requestError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {requestError}
            </p>
          ) : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={decision !== null}
        title={decision?.kind === "approve" ? t.prices.approve : t.prices.reject}
        variant={decision?.kind === "approve" ? "success" : "danger"}
        confirmLabel={decision?.kind === "approve" ? t.prices.approve : t.prices.reject}
        loading={approveMutation.isPending || rejectMutation.isPending}
        onConfirm={confirmDecision}
        onCancel={() => setDecision(null)}
        message={
          decision ? (
            <div className="space-y-2">
              <p>{decision.kind === "approve" ? t.prices.approveConfirm : t.common.deleteConfirm}</p>
              <p className="num font-bold text-ink">
                {decision.row.target_name} · {decision.row.branch_name ?? t.branches.allBranches} ·{" "}
                {formatMNT(decision.row.old_price)} → {formatMNT(decision.row.new_price)}
              </p>
            </div>
          ) : null
        }
      />
    </div>
  );
}

export default PriceChangesPage;
