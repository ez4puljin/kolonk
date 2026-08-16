import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { RotateCcw } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useCreateRefundMutation } from "../../api/queries/approvals";
import { useSale } from "../../api/queries/sales";
import type { PaymentMethod, RefundItemInput } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { StatBox } from "../../components/ui/StatBox";
import { t } from "../../i18n/mn";
import { TENDER_METHODS } from "../../lib/constants";
import { dCmp, dMul, dSub, dSum, dToQty } from "../../lib/decimal";
import { formatMNT, formatQty } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { ChipGroup, NumberField, TextAreaField, ToggleField } from "../catalog/_shared";

export function RefundPage() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const saleQuery = useSale(id);
  const refundMutation = useCreateRefundMutation();

  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [restock, setRestock] = useState(true);
  const [reason, setReason] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sale = saleQuery.data ?? null;

  const lines = useMemo(() => {
    if (!sale) return [];
    return sale.items.map((item) => {
      // Буцаагаагүй мөрд анхны тоог бүтнээр нь үлдээнэ (3 орны нарийвчлал хадгалагдана).
      const available = dCmp(item.refunded_qty, "0") === 0 ? item.qty : dSub(item.qty, item.refunded_qty);
      const selectedQty = quantities[item.id] ?? "";
      return {
        item,
        available,
        selectedQty,
        amount: dMul(item.unit_price, dToQty(selectedQty)),
        overflow: dToQty(selectedQty) > dToQty(available) + 1e-9,
      };
    });
  }, [sale, quantities]);

  const refundTotal = dSum(lines.map((line) => line.amount));
  const hasSelection = lines.some((line) => dToQty(line.selectedQty) > 0);
  const hasOverflow = lines.some((line) => line.overflow);
  const isFull =
    lines.length > 0 &&
    lines.every((line) => dToQty(line.selectedQty) >= dToQty(line.available) - 1e-9) &&
    lines.every((line) => dToQty(line.available) > 0 || dToQty(line.selectedQty) === 0);

  const selectAll = (): void => {
    const next: Record<string, string> = {};
    for (const line of lines) {
      if (dToQty(line.available) > 0) next[line.item.id] = line.available;
    }
    setQuantities(next);
  };

  const submit = (): void => {
    if (!sale || !hasSelection || hasOverflow) return;
    setError(null);

    const items: RefundItemInput[] = lines
      .filter((line) => dToQty(line.selectedQty) > 0)
      .map((line) => ({ sale_item_id: line.item.id, qty: line.selectedQty }));

    refundMutation.mutate(
      {
        sale_id: sale.id,
        refund_type: isFull ? "full" : "partial",
        items,
        reason: reason.trim() || null,
        restock,
        refund_method: method,
      },
      {
        onSuccess: () => {
          toastSuccess(t.refunds.requested);
          navigate(`/sales/${sale.id}`);
        },
        onError: (mutationError) => {
          setConfirmOpen(false);
          setError(errorMessage(mutationError));
        },
      },
    );
  };

  if (saleQuery.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-24 text-ink-soft">
        <Spinner size="lg" label={t.common.loading} />
      </div>
    );
  }

  if (!sale) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.refunds.newRefund} back="/sales" />
        <EmptyState title={t.errors.notFound} hint={t.errors.notFoundHint} />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.refunds.newRefund}
        subtitle={`${t.sales.saleNo} ${sale.number} · ${formatMNT(sale.total)}`}
        back={`/sales/${sale.id}`}
        actions={
          <Button variant="secondary" size="md" onClick={selectAll}>
            {t.refunds.full}
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Card title={t.sales.items} flush>
          <div className="flex flex-col">
            {lines.map((line) => {
              const exhausted = dToQty(line.available) <= 0;
              return (
                <div
                  key={line.item.id}
                  className={`flex flex-col gap-3 border-b border-line px-5 py-4 last:border-b-0 sm:flex-row sm:items-end ${exhausted ? "opacity-50" : ""}`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[15px] font-bold text-ink">{line.item.name_snapshot}</div>
                    <div className="num text-sm text-ink-soft">
                      {formatQty(line.item.qty)} × {formatMNT(line.item.unit_price)} ={" "}
                      {formatMNT(line.item.amount)}
                    </div>
                    <div className="text-xs text-ink-soft">
                      {exhausted
                        ? t.refunds.alreadyRefunded
                        : `${t.refunds.refundQty}: ${formatQty(line.available)}`}
                    </div>
                  </div>

                  <NumberField
                    name={`refund-qty-${line.item.id}`}
                    label={t.refunds.refundQty}
                    value={line.selectedQty}
                    disabled={exhausted}
                    maxDecimals={3}
                    onChange={(value) => setQuantities((current) => ({ ...current, [line.item.id]: value }))}
                    className="w-full sm:w-48"
                    hint={line.overflow ? t.errors.validation : undefined}
                  />

                  <div className="num w-full text-right text-xl font-bold text-ink sm:w-40">
                    {formatMNT(line.amount)}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          <StatBox label={t.refunds.refundAmount} value={formatMNT(refundTotal)} tone="danger" size="lg" />

          <Card title={t.refunds.refund}>
            <div className="flex flex-col gap-4">
              <ChipGroup<PaymentMethod>
                label={t.refunds.refundMethod}
                value={method}
                onChange={setMethod}
                options={TENDER_METHODS.filter((tender) =>
                  ["cash", "card", "qr"].includes(tender.value),
                ).map((tender) => ({ value: tender.value, label: tender.label }))}
              />
              <ToggleField
                label={t.refunds.restock}
                value={restock}
                onChange={setRestock}
                hint={t.inventory.refund}
              />
              <TextAreaField label={t.common.reason} value={reason} onChange={setReason} />
            </div>
          </Card>

          {hasOverflow ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {t.errors.validation}
            </p>
          ) : null}
          {error ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
          ) : null}

          <Button
            variant="danger"
            size="lg"
            block
            icon={<RotateCcw />}
            disabled={!hasSelection || hasOverflow}
            onClick={() => setConfirmOpen(true)}
          >
            {t.refunds.request}
          </Button>
          <Button variant="secondary" size="md" block onClick={() => navigate(`/sales/${sale.id}`)}>
            {t.common.cancel}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={t.refunds.newRefund}
        variant="danger"
        confirmLabel={t.refunds.request}
        loading={refundMutation.isPending}
        onConfirm={submit}
        onCancel={() => setConfirmOpen(false)}
        message={
          <div className="space-y-2">
            <p>{isFull ? t.refunds.full : t.refunds.partial}</p>
            <p className="num text-lg font-bold text-ink">{formatMNT(refundTotal)}</p>
            <p className="text-ink-soft">{t.refunds.approveConfirm}</p>
          </div>
        }
      />
    </div>
  );
}

export default RefundPage;
