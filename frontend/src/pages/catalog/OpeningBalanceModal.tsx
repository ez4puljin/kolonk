/**
 * Эхний үлдэгдэл оруулах цонх — /products, /inventory хоёулаа ашиглана.
 *
 * Систем рүү шилжихэд агуулахад аль хэдийн байгаа барааг бүртгэх зориулалттай.
 * Оруулсан тоо хэмжээ нь тухайн салбарын ЭЦСИЙН үлдэгдэл (нэмэгдэл биш) тул
 * санамсаргүй хоёр удаа хадгалахад нөөц давхардахгүй.
 */

import { useEffect, useMemo, useState } from "react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import { useOpeningBalanceMutation } from "../../api/queries/inventory";
import { useProducts } from "../../api/queries/products";
import type { UUID } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { t } from "../../i18n/mn";
import { dToQty, toDisplay } from "../../lib/decimal";
import { formatMNT, formatQty } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { FieldLabel, NumberField, PickerField, TextField } from "./_shared";

interface Row {
  qty: string;
  cost: string;
}

function todayIso(): string {
  const now = new Date();
  const pad = (value: number): string => String(value).padStart(2, "0");
  return [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())].join("-");
}

export function OpeningBalanceModal({
  open,
  onClose,
  branchId: initialBranchId = "",
}: {
  open: boolean;
  onClose: () => void;
  branchId?: string;
}) {
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [branchId, setBranchId] = useState(initialBranchId);
  const [asOf, setAsOf] = useState(todayIso);
  const [note, setNote] = useState("");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [error, setError] = useState<string | null>(null);

  const branchesQuery = useBranches();
  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );

  // Тухайн салбарын одоогийн үлдэгдлийг талбарт урьдчилж бөглөнө — нягтлан
  // зөвхөн өөрчлөх мөрөө засна.
  const productsQuery = useProducts({
    q: search || undefined,
    branch_id: branchId || undefined,
    active_only: true,
    limit: 300,
  });
  const products = useMemo(() => productsQuery.data?.items ?? [], [productsQuery.data]);

  useEffect(() => {
    if (!open) return;
    setBranchId(initialBranchId);
    setError(null);
    setRows({});
  }, [open, initialBranchId]);

  const mutation = useOpeningBalanceMutation();

  const setRow = (id: string, patch: Partial<Row>, fallback: Row): void =>
    setRows((prev) => ({ ...prev, [id]: { ...(prev[id] ?? fallback), ...patch } }));

  /** Зөвхөн гараар өөрчилсөн мөрүүд илгээгдэнэ. */
  const touched = Object.entries(rows);
  const totalValue = touched.reduce(
    (sum, [, row]) => sum + dToQty(row.qty || "0") * dToQty(row.cost || "0"),
    0,
  );

  const submit = (): void => {
    if (touched.length === 0) return;
    setError(null);
    mutation.mutate(
      {
        branch_id: branchId || null,
        as_of: asOf,
        note: note || null,
        items: touched.map(([productId, row]) => ({
          product_id: productId as UUID,
          qty: row.qty || "0",
          unit_cost: row.cost || "0",
        })),
      },
      {
        onSuccess: (data) => {
          toastSuccess(t.products.openingStock + ": " + data.products_changed);
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
      size="lg"
      title={t.products.openingStock}
      subtitle={t.inventory.openingHint}
      footer={
        <>
          <Button variant="secondary" size="md" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button
            variant="primary"
            size="md"
            disabled={touched.length === 0}
            loading={mutation.isPending}
            onClick={submit}
          >
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {branches.length > 1 ? (
            <PickerField
              label={t.branches.title}
              value={branchId}
              onChange={setBranchId}
              options={branches.map((branch) => ({ value: branch.id, label: branch.name }))}
            />
          ) : null}
          <div className="flex flex-col gap-1.5">
            <FieldLabel>{t.common.date}</FieldLabel>
            <input
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
              className="h-12 rounded-xl border border-line-strong bg-white px-3 text-[15px] text-ink"
            />
          </div>
          <TextField label={t.common.note} value={note} onChange={setNote} />
        </div>

        <TextField label={t.common.search} value={search} onChange={setSearch} />

        {productsQuery.isLoading ? (
          <div className="flex justify-center py-10 text-ink-soft">
            <Spinner label={t.common.loading} />
          </div>
        ) : (
          <div className="flex max-h-[46vh] flex-col divide-y divide-line overflow-y-auto rounded-xl border border-line">
            {products.map((product) => {
              // avg_cost 6 оронтой бутархайтай ирдэг — талбарт 2 болгож харуулна.
              const fallback: Row = {
                qty: product.stock_qty,
                cost: toDisplay(product.avg_cost),
              };
              const row = rows[product.id] ?? fallback;
              const edited = rows[product.id] !== undefined;
              return (
                <div
                  key={product.id}
                  className={[
                    "flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center sm:gap-3",
                    edited ? "bg-action-soft/40" : "",
                  ].join(" ")}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold text-ink">
                      {product.name_mn}
                    </span>
                    <span className="num block text-xs text-ink-soft">
                      {product.sku} · {formatQty(product.stock_qty, product.unit)}
                    </span>
                  </span>
                  <div className="flex items-center gap-2">
                    <NumberField
                      name={"ob-qty-" + product.id}
                      label=""
                      value={row.qty}
                      onChange={(value) => setRow(product.id, { qty: value }, fallback)}
                      maxDecimals={3}
                      className="w-28"
                      suffix={product.unit}
                    />
                    <NumberField
                      name={"ob-cost-" + product.id}
                      label=""
                      value={row.cost}
                      onChange={(value) => setRow(product.id, { cost: value }, fallback)}
                      maxDecimals={2}
                      className="w-32"
                      suffix={t.units.mnt}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="flex items-baseline justify-between rounded-xl bg-surface-alt px-4 py-3">
          <span className="text-sm text-ink-soft">
            {t.common.selected}: {touched.length} {t.common.rows}
          </span>
          <span className="num text-lg font-bold text-ink">{formatMNT(String(totalValue))}</span>
        </div>

        {error ? (
          <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
            {error}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

export default OpeningBalanceModal;
