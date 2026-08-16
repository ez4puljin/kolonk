import { useEffect, useMemo, useState } from "react";
import { Scissors } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useConvertToBulkMutation } from "../../api/queries/inventory";
import { useProducts } from "../../api/queries/products";
import type { Product, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { dMul, dToQty } from "../../lib/decimal";
import { formatMNT, formatQty } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { Modal } from "../ui/Modal";

export interface BulkConvertDialogProps {
  open: boolean;
  onClose: () => void;
  /**
   * Аль грам бүтээгдэхүүн рүү задлах вэ.  Өгвөл зөвхөн түүн рүү задардаг
   * ширхэг бараанууд харагдана; өгөөгүй бол задлах боломжтой бүх бараа.
   */
  targetProductId?: UUID | null;
  /** Задлах ширхэг барааг шууд заасан үе (нөөцийн жагсаалтаас). */
  sourceProductId?: UUID | null;
  /** Аль салбарт (хоосон бол хэрэглэгчийн үндсэн салбар). */
  branchId?: UUID | null;
  onDone?: () => void;
}

/**
 * Задлан хөрвүүлэлт — ширхэг барааг задалж грам бүтээгдэхүүн рүү шилжүүлнэ.
 *
 * Жишээ: «Мотор тос 5W-30 4л» савнаас 1 ширхэг задлахад «5W-30 задлан»
 * бүртгэлд 4.000 л нэмэгдэж, талбай дээр литрээр зарагдана.  Өртөг бүрэн
 * шилжинэ — ерөнхий дэвтэр хөдлөхгүй.
 */
export function BulkConvertDialog({
  open,
  onClose,
  targetProductId = null,
  sourceProductId = null,
  branchId = null,
  onDone,
}: BulkConvertDialogProps) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const { data, isLoading } = useProducts({
    convertible: true,
    branch_id: branchId ?? undefined,
    limit: 200,
  });
  const convert = useConvertToBulkMutation();

  const [pickedId, setPickedId] = useState<UUID | "">("");
  const [qty, setQty] = useState("1");
  const [error, setError] = useState<string | null>(null);

  const sources = useMemo(() => {
    const all = (data?.items ?? []).filter((product) => product.is_active);
    if (sourceProductId) return all.filter((product) => product.id === sourceProductId);
    if (targetProductId) return all.filter((product) => product.bulk_product_id === targetProductId);
    return all;
  }, [data, targetProductId, sourceProductId]);

  // Цонх нээгдэх бүрд эхний боломжит барааг сонгож өгнө.
  useEffect(() => {
    if (!open) return;
    setQty("1");
    setError(null);
    setPickedId(sources[0]?.id ?? "");
  }, [open, sources]);

  const picked: Product | null = sources.find((product) => product.id === pickedId) ?? null;
  const pieces = dToQty(qty);
  const outQty = picked ? dMul(picked.bulk_factor, pieces) : "0";
  const cost = picked ? dMul(picked.avg_cost, pieces) : "0";
  const stock = picked ? dToQty(picked.stock_qty) : 0;
  const canSubmit = picked !== null && pieces > 0 && pieces <= stock;

  const submit = (): void => {
    if (!picked || !canSubmit) return;
    setError(null);
    convert.mutate(
      { product_id: picked.id, qty, branch_id: branchId ?? null },
      {
        onSuccess: (result) => {
          toastSuccess(
            `${t.inventory.converted} · ${formatQty(result.out_qty, result.target.unit)}`,
          );
          onDone?.();
          onClose();
        },
        onError: (cause) => setError(errorMessage(cause)),
      },
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="md"
      title={t.inventory.convertTitle}
      subtitle={t.inventory.convertHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<Scissors />}
            disabled={!canSubmit}
            loading={convert.isPending}
            onClick={submit}
          >
            {t.inventory.convert}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {isLoading ? (
          <p className="text-ink-soft">{t.common.loading}</p>
        ) : sources.length === 0 ? (
          <EmptyState compact title={t.inventory.noConvertible} hint={t.common.emptyHint} />
        ) : (
          <>
            {/* Задлах бараа */}
            <ul className="flex max-h-64 flex-col gap-2 overflow-y-auto">
              {sources.map((product) => {
                const active = product.id === pickedId;
                const empty = dToQty(product.stock_qty) <= 0;
                return (
                  <li key={product.id}>
                    <button
                      type="button"
                      disabled={empty}
                      onClick={() => setPickedId(product.id)}
                      className={[
                        "flex min-h-16 w-full flex-wrap items-center gap-3 rounded-xl border-2 px-4 py-2.5 text-left",
                        empty ? "border-line opacity-50" : "",
                        active ? "border-action bg-action-soft/40" : "border-line-strong bg-white",
                      ].join(" ")}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[15px] font-bold text-ink">
                          {product.name_mn}
                        </span>
                        <span className="num block truncate text-sm text-ink-soft">
                          {product.bulk_product_name} · 1{product.unit} →{" "}
                          {formatQty(product.bulk_factor, product.bulk_product_unit)}
                        </span>
                      </span>
                      <span className="num text-right text-sm font-semibold text-ink-soft">
                        {formatQty(product.stock_qty, product.unit)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            {/* Хэдэн ширхэг */}
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
                {t.inventory.convertQty}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setQty(String(Math.max(1, Math.round(pieces - 1))))}
                  className="h-14 w-14 shrink-0 rounded-xl border border-line-strong bg-white text-2xl font-bold text-ink active:bg-surface-sunken"
                >
                  −
                </button>
                <input
                  inputMode="decimal"
                  value={qty}
                  onChange={(event) => setQty(event.target.value.replace(/[^\d.]/g, ""))}
                  className="num h-14 min-w-0 flex-1 rounded-xl border border-line-strong bg-white px-4 text-center text-2xl font-bold text-ink outline-none focus:border-action"
                />
                <button
                  type="button"
                  onClick={() => setQty(String(Math.round(pieces + 1)))}
                  className="h-14 w-14 shrink-0 rounded-xl border border-line-strong bg-white text-2xl font-bold text-ink active:bg-surface-sunken"
                >
                  +
                </button>
              </div>
            </div>

            {/* Үр дүн */}
            {picked ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-success/30 bg-success-soft px-4 py-3">
                  <div className="text-[11px] font-semibold tracking-wide text-ink-soft uppercase">
                    {t.inventory.convertOut}
                  </div>
                  <div className="num text-2xl font-bold text-success-dark">
                    {formatQty(outQty, picked.bulk_product_unit)}
                  </div>
                </div>
                <div className="rounded-xl border border-line bg-surface-alt px-4 py-3">
                  <div className="text-[11px] font-semibold tracking-wide text-ink-soft uppercase">
                    {t.inventory.convertCost}
                  </div>
                  <div className="num text-2xl font-bold text-ink">{formatMNT(cost)}</div>
                </div>
              </div>
            ) : null}

            {picked && pieces > stock ? (
              <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm font-semibold text-warning-dark">
                {t.pos.outOfStock} · {formatQty(picked.stock_qty, picked.unit)}
              </p>
            ) : null}
          </>
        )}

        {error ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

export default BulkConvertDialog;
