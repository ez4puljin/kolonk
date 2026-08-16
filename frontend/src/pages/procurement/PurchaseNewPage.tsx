import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Save, Trash2 } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useBranches } from "../../api/queries/branches";
import { useCreatePurchaseMutation, useSuppliers } from "../../api/queries/procurement";
import { useProducts } from "../../api/queries/products";
import { useSettings } from "../../api/queries/system";
import type { PurchaseItemCreate } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { t } from "../../i18n/mn";
import { dAdd, dMul, dSum, dToQty } from "../../lib/decimal";
import { formatMNT, formatQty, todayInput } from "../../lib/format";
import { useUiStore } from "../../stores/ui";
import { DateField, NumberField, PickerField, TextAreaField, TextField } from "../catalog/_shared";

const DEFAULT_VAT_RATE = 0.1;

function vatRateOf(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed >= 0 && parsed < 1) return parsed;
  }
  return DEFAULT_VAT_RATE;
}

interface DraftLine extends PurchaseItemCreate {
  key: string;
  name: string;
  unit: string;
  /** qty × unit_cost — string-decimal арифметикаар бодогдсон мөрийн дүн. */
  amount: string;
}

let lineSeq = 0;

export function PurchaseNewPage() {
  const navigate = useNavigate();
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const suppliersQuery = useSuppliers({ limit: 200 });
  const productsQuery = useProducts({ limit: 500 });
  const branchesQuery = useBranches();
  const settingsQuery = useSettings();
  const createMutation = useCreatePurchaseMutation();

  const branches = useMemo(
    () => (branchesQuery.data ?? []).filter((branch) => branch.is_active),
    [branchesQuery.data],
  );

  const [supplierId, setSupplierId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [purchaseDate, setPurchaseDate] = useState(todayInput());
  const [invoiceNo, setInvoiceNo] = useState("");
  const [note, setNote] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draftProductId, setDraftProductId] = useState("");
  const [draftQty, setDraftQty] = useState("");
  const [draftCost, setDraftCost] = useState("");

  const products = useMemo(
    () => (productsQuery.data?.items ?? []).filter((product) => product.is_active),
    [productsQuery.data],
  );

  const vatRate = vatRateOf(settingsQuery.data?.vat_rate);
  const subtotal = dSum(lines.map((line) => line.amount));
  const vatAmount = dMul(subtotal, vatRate);
  const totalGross = dAdd(subtotal, vatAmount);

  const supplierOptions = useMemo(
    () =>
      (suppliersQuery.data?.items ?? [])
        .filter((supplier) => supplier.is_active)
        .map((supplier) => ({ value: supplier.id, label: supplier.name })),
    [suppliersQuery.data],
  );

  const productOptions = useMemo(
    () =>
      products.map((product) => ({
        value: product.id,
        label: product.name_mn,
        hint: `${product.sku} · ${formatQty(product.stock_qty, product.unit)}`,
      })),
    [products],
  );

  const openEditor = (line: DraftLine | null): void => {
    setEditingKey(line?.key ?? null);
    setDraftProductId(line?.product_id ?? "");
    setDraftQty(line?.qty ?? "");
    setDraftCost(line?.unit_cost ?? "");
    setEditorOpen(true);
  };

  const saveLine = (): void => {
    const product = products.find((item) => item.id === draftProductId);
    if (!product || dToQty(draftQty) <= 0) return;

    const unitCost = draftCost === "" ? "0" : draftCost;
    const next: DraftLine = {
      key: editingKey ?? `line-${(lineSeq += 1)}`,
      product_id: product.id,
      qty: draftQty,
      unit_cost: unitCost,
      name: product.name_mn,
      unit: product.unit,
      amount: dMul(unitCost, dToQty(draftQty)),
    };

    setLines((current) =>
      editingKey === null
        ? [...current, next]
        : current.map((line) => (line.key === editingKey ? next : line)),
    );
    setEditorOpen(false);
  };

  const removeLine = (key: string): void => {
    setLines((current) => current.filter((line) => line.key !== key));
  };

  const canSubmit = supplierId !== "" && lines.length > 0;

  const submit = (): void => {
    if (!canSubmit) return;
    setError(null);
    createMutation.mutate(
      {
        supplier_id: supplierId,
        branch_id: branchId || null,
        purchase_date: purchaseDate,
        invoice_no: invoiceNo.trim() || null,
        note: note.trim() || null,
        items: lines.map((line) => ({
          product_id: line.product_id,
          qty: line.qty,
          unit_cost: line.unit_cost,
        })),
      },
      {
        onSuccess: () => {
          toastSuccess(t.common.saved);
          navigate("/purchases");
        },
        onError: (mutationError) => setError(errorMessage(mutationError)),
      },
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader title={t.procurement.newPurchase} back="/purchases" />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex flex-col gap-6">
          <Card title={t.procurement.purchase}>
            <div className="grid gap-4 sm:grid-cols-2">
              <PickerField
                label={t.procurement.supplier}
                value={supplierId}
                options={supplierOptions}
                onChange={setSupplierId}
              />
              {branches.length > 1 ? (
                <PickerField
                  label={t.procurement.stockBranch}
                  value={branchId}
                  options={branches.map((branch) => ({ value: branch.id, label: branch.name }))}
                  onChange={setBranchId}
                />
              ) : null}
              <DateField label={t.procurement.purchaseDate} value={purchaseDate} onChange={setPurchaseDate} />
              <TextField label={t.procurement.invoiceNo} value={invoiceNo} onChange={setInvoiceNo} />
            </div>
          </Card>

          <Card
            title={t.sales.items}
            actions={
              <Button variant="primary" size="md" icon={<Plus />} onClick={() => openEditor(null)}>
                {t.procurement.addLine}
              </Button>
            }
            flush
          >
            {lines.length === 0 ? (
              <EmptyState compact title={t.pos.cartEmpty} hint={t.common.emptyHint} />
            ) : (
              <div className="flex flex-col">
                {lines.map((line) => (
                  <div
                    key={line.key}
                    className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5 last:border-b-0"
                  >
                    <button
                      type="button"
                      onClick={() => openEditor(line)}
                      className="touch-target flex min-w-0 flex-1 flex-col justify-center text-left"
                    >
                      <span className="block truncate text-[15px] font-semibold text-ink">{line.name}</span>
                      <span className="num block truncate text-sm text-ink-soft">
                        {formatQty(line.qty, line.unit)} × {formatMNT(line.unit_cost)}
                      </span>
                    </button>
                    <span className="num shrink-0 text-lg font-bold text-ink">
                      {formatMNT(line.amount)}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeLine(line.key)}
                      aria-label={t.common.delete}
                      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-danger-dark transition-colors hover:bg-danger-soft"
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title={t.common.note}>
            <TextAreaField label={t.common.note} value={note} onChange={setNote} />
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card title={t.common.total} tone="dark">
            <dl className="flex flex-col gap-3">
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-ink-faint">{t.common.net}</dt>
                <dd className="num text-lg font-semibold text-ink-invert">{formatMNT(subtotal)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-ink-faint">{t.common.vat}</dt>
                <dd className="num text-lg font-semibold text-ink-invert">{formatMNT(vatAmount)}</dd>
              </div>
              <div className="flex items-baseline justify-between gap-3 border-t border-brand-700 pt-3">
                <dt className="text-base font-semibold text-ink-invert">{t.common.gross}</dt>
                <dd className="num text-[40px] leading-none font-bold text-success">
                  {formatMNT(totalGross)}
                </dd>
              </div>
            </dl>
          </Card>

          {error ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">{error}</p>
          ) : null}

          <Button
            variant="primary"
            size="lg"
            block
            icon={<Save />}
            disabled={!canSubmit}
            loading={createMutation.isPending}
            onClick={submit}
          >
            {t.common.save}
          </Button>
          <Button variant="secondary" size="md" block onClick={() => navigate("/purchases")}>
            {t.common.cancel}
          </Button>
          <p className="text-sm text-ink-soft">{t.procurement.postConfirm}</p>
        </div>
      </div>

      <Modal
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        size="md"
        title={editingKey === null ? t.procurement.addLine : t.common.edit}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setEditorOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={draftProductId === "" || dToQty(draftQty) <= 0}
              onClick={saveLine}
            >
              {t.common.ok}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <PickerField
            label={t.products.product}
            value={draftProductId}
            options={productOptions}
            onChange={setDraftProductId}
          />
          <NumberField
            name="purchase-line-qty"
            label={t.common.qty}
            value={draftQty}
            onChange={setDraftQty}
            maxDecimals={3}
          />
          <NumberField
            name="purchase-line-cost"
            label={t.common.unitCost}
            value={draftCost}
            onChange={setDraftCost}
            suffix={t.units.mnt}
          />
          <div className="flex items-baseline justify-between gap-3 rounded-xl border border-line bg-surface-alt px-4 py-3">
            <span className="text-sm text-ink-soft">{t.common.amount}</span>
            <span className="num text-2xl font-bold text-ink">
              {formatMNT(dMul(draftCost === "" ? "0" : draftCost, dToQty(draftQty)))}
            </span>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default PurchaseNewPage;
