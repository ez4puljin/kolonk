import { useMemo, useState } from "react";
import { Package, Pencil, Plus, Power, Scissors, TrendingUp } from "lucide-react";

import { errorMessage } from "../../api/client";
import { useCreatePriceChangeMutation } from "../../api/queries/approvals";
import {
  useCreateProductMutation,
  useDeleteProductMutation,
  useProductCategories,
  useProducts,
  useUpdateProductMutation,
} from "../../api/queries/products";
import type { Product, ProductSaleMode } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { BulkConvertDialog } from "../../components/pos/BulkConvertDialog";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type Column } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { StatBox } from "../../components/ui/StatBox";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useCan } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { PAGE_SIZE } from "../../lib/constants";
import { dSub, dSum, dToNumber } from "../../lib/decimal";
import { formatMNT, formatQty } from "../../lib/format";
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
  ToggleField,
} from "./_shared";

type StockFilter = "all" | "low" | "inactive";
type ModeFilter = "all" | ProductSaleMode;

interface ProductForm {
  sku: string;
  barcode: string;
  name_mn: string;
  category_id: string;
  unit: string;
  price: string;
  min_stock: string;
  is_active: boolean;
  sale_mode: ProductSaleMode;
  bulk_product_id: string;
  bulk_factor: string;
}

const EMPTY_FORM: ProductForm = {
  sku: "",
  barcode: "",
  name_mn: "",
  category_id: "",
  unit: "ш",
  price: "",
  min_stock: "",
  is_active: true,
  sale_mode: "piece",
  bulk_product_id: "",
  bulk_factor: "",
};

export function ProductsPage() {
  const canManage = useCan("products.manage");
  const canRequestPrice = useCan("prices.request");
  const toastSuccess = useUiStore((state) => state.toastSuccess);

  const [query, setQuery] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [stockFilter, setStockFilter] = useState<StockFilter>("all");
  const [modeFilter, setModeFilter] = useState<ModeFilter>("all");
  const [offset, setOffset] = useState(0);
  const [converting, setConverting] = useState<Product | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const [priceTarget, setPriceTarget] = useState<Product | null>(null);
  const [newPrice, setNewPrice] = useState("");
  const [priceReason, setPriceReason] = useState("");
  const [priceError, setPriceError] = useState<string | null>(null);

  const [deactivating, setDeactivating] = useState<Product | null>(null);

  const categoriesQuery = useProductCategories();
  const productsQuery = useProducts({
    category_id: categoryId || undefined,
    low_stock: stockFilter === "low" ? true : undefined,
    sale_mode: modeFilter === "all" ? undefined : modeFilter,
    limit: 500,
  });
  // Задлалтын зорилтод зөвхөн грам бүтээгдэхүүн сонгогдоно.
  const bulkQuery = useProducts({ sale_mode: "bulk", limit: 200 });
  const createMutation = useCreateProductMutation();
  const updateMutation = useUpdateProductMutation();
  const deleteMutation = useDeleteProductMutation();
  const priceMutation = useCreatePriceChangeMutation();

  const categories = useMemo(() => categoriesQuery.data?.items ?? [], [categoriesQuery.data]);
  const allProducts = useMemo(() => productsQuery.data?.items ?? [], [productsQuery.data]);

  // Сервер `search`/`is_active` нэртэй параметр хүлээдэг тул клиент талд шүүнэ.
  const filtered = useMemo(
    () =>
      allProducts
        .filter((product) => matchesQuery([product.name_mn, product.sku, product.barcode], query))
        .filter((product) => (stockFilter === "inactive" ? !product.is_active : product.is_active)),
    [allProducts, query, stockFilter],
  );
  const rows = useMemo(() => filtered.slice(offset, offset + PAGE_SIZE), [filtered, offset]);

  const totals = useMemo(
    () => ({
      value: dSum(filtered.map((product) => product.stock_value)),
      low: filtered.filter((product) => product.is_low).length,
    }),
    [filtered],
  );

  const bulkOptions = useMemo(
    () =>
      (bulkQuery.data?.items ?? [])
        .filter((product) => product.is_active && product.id !== editing?.id)
        .map((product) => ({ value: product.id, label: `${product.name_mn} (${product.unit})` })),
    [bulkQuery.data, editing],
  );

  const categoryOptions = useMemo(
    () => categories.map((category) => ({ value: category.id, label: category.name_mn })),
    [categories],
  );

  const openForm = (product: Product | null): void => {
    setEditing(product);
    setFormError(null);
    setForm(
      product
        ? {
            sku: product.sku,
            barcode: product.barcode ?? "",
            name_mn: product.name_mn,
            category_id: product.category_id,
            unit: product.unit,
            price: product.price,
            min_stock: product.min_stock,
            is_active: product.is_active,
            sale_mode: product.sale_mode,
            bulk_product_id: product.bulk_product_id ?? "",
            bulk_factor: product.bulk_factor,
          }
        : { ...EMPTY_FORM, category_id: categories[0]?.id ?? "" },
    );
    setFormOpen(true);
  };

  /** Задлалтын холбоос — зөвхөн ширхэг бараанд утгатай. */
  const bulkLink =
    form.sale_mode === "piece" && form.bulk_product_id !== ""
      ? { id: form.bulk_product_id, factor: form.bulk_factor === "" ? "0" : form.bulk_factor }
      : { id: null, factor: "0" };

  const submitForm = (): void => {
    setFormError(null);
    const onSuccess = (): void => {
      toastSuccess(t.common.saved);
      setFormOpen(false);
    };
    const onError = (error: unknown): void => setFormError(errorMessage(error));

    if (editing) {
      updateMutation.mutate(
        {
          id: editing.id,
          payload: {
            sku: form.sku.trim(),
            barcode: form.barcode.trim() || null,
            name_mn: form.name_mn.trim(),
            category_id: form.category_id,
            unit: form.unit.trim(),
            min_stock: form.min_stock === "" ? "0" : form.min_stock,
            is_active: form.is_active,
            sale_mode: form.sale_mode,
            bulk_product_id: bulkLink.id,
            bulk_factor: bulkLink.factor,
          },
        },
        { onSuccess, onError },
      );
    } else {
      createMutation.mutate(
        {
          sku: form.sku.trim(),
          barcode: form.barcode.trim() || null,
          name_mn: form.name_mn.trim(),
          category_id: form.category_id,
          unit: form.unit.trim() || "ш",
          price: form.price === "" ? "0" : form.price,
          min_stock: form.min_stock === "" ? "0" : form.min_stock,
          is_active: form.is_active,
          sale_mode: form.sale_mode,
          bulk_product_id: bulkLink.id,
          bulk_factor: bulkLink.factor,
        },
        { onSuccess, onError },
      );
    }
  };

  const openPriceRequest = (product: Product): void => {
    setPriceTarget(product);
    setNewPrice(product.price);
    setPriceReason("");
    setPriceError(null);
  };

  const submitPriceRequest = (): void => {
    if (!priceTarget || dToNumber(newPrice) <= 0) return;
    setPriceError(null);
    priceMutation.mutate(
      {
        target_type: "product",
        product_id: priceTarget.id,
        new_price: newPrice,
        reason: priceReason.trim() || null,
      },
      {
        onSuccess: () => {
          toastSuccess(t.refunds.requested);
          setPriceTarget(null);
        },
        onError: (error) => setPriceError(errorMessage(error)),
      },
    );
  };

  const confirmDeactivate = (): void => {
    if (!deactivating) return;
    deleteMutation.mutate(deactivating.id, {
      onSuccess: () => {
        toastSuccess(t.common.saved);
        setDeactivating(null);
      },
      onError: () => setDeactivating(null),
    });
  };

  const columns: Column<Product>[] = [
    { key: "name", header: t.products.product, primary: true, render: (row) => <span className="font-semibold">{row.name_mn}</span> },
    { key: "sku", header: t.products.sku, numeric: true, render: (row) => row.sku },
    {
      key: "category",
      header: t.products.category,
      hideOnMobile: true,
      render: (row) => row.category_name ?? "—",
    },
    {
      key: "sale_mode",
      header: t.products.saleMode,
      hideOnMobile: true,
      render: (row) => (
        <span className="flex flex-col gap-0.5">
          <StatusBadge
            size="sm"
            tone={row.sale_mode === "bulk" ? "action" : "neutral"}
            label={row.sale_mode === "bulk" ? t.products.saleBulk : t.products.salePiece}
          />
          {row.bulk_product_name ? (
            <span className="num text-xs text-ink-soft">
              → {row.bulk_product_name} · {formatQty(row.bulk_factor)}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "price",
      header: t.common.price,
      align: "right",
      numeric: true,
      render: (row) => <span className="font-bold">{formatMNT(row.price)}</span>,
    },
    {
      key: "avg_cost",
      header: t.tanks.avgCost,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.avg_cost),
    },
    {
      key: "stock",
      header: t.products.stockQty,
      align: "right",
      numeric: true,
      render: (row) => (
        <span className="inline-flex items-center gap-2">
          <span className={row.is_low ? "font-bold text-danger-dark" : ""}>
            {formatQty(row.stock_qty, row.unit)}
          </span>
          {row.is_low ? <StatusBadge size="sm" tone="danger" label={t.pos.lowStock} /> : null}
        </span>
      ),
    },
    {
      key: "stock_value",
      header: t.inventory.value,
      align: "right",
      numeric: true,
      hideOnMobile: true,
      render: (row) => formatMNT(row.stock_value),
    },
    {
      key: "actions",
      header: t.common.actions,
      align: "right",
      render: (row) => (
        <div className="flex flex-wrap justify-end gap-2">
          {row.is_convertible ? (
            <Button variant="secondary" size="md" icon={<Scissors />} onClick={() => setConverting(row)}>
              {t.inventory.convert}
            </Button>
          ) : null}
          {canRequestPrice ? (
            <Button variant="secondary" size="md" icon={<TrendingUp />} onClick={() => openPriceRequest(row)}>
              {t.prices.request}
            </Button>
          ) : null}
          {canManage ? (
            <>
              <Button variant="secondary" size="md" icon={<Pencil />} onClick={() => openForm(row)}>
                {t.common.edit}
              </Button>
              {row.is_active ? (
                <Button variant="ghost" size="md" icon={<Power />} onClick={() => setDeactivating(row)}>
                  {t.admin.deactivate}
                </Button>
              ) : null}
            </>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={t.products.title}
        subtitle={t.products.priceChangeOnly}
        actions={
          canManage ? (
            <Button variant="primary" size="lg" icon={<Plus />} onClick={() => openForm(null)}>
              {t.products.newProduct}
            </Button>
          ) : null
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatBox label={t.products.title} value={filtered.length} tone="neutral" />
        <StatBox label={t.inventory.value} value={formatMNT(totals.value)} tone="success" />
        <StatBox label={t.pos.lowStock} value={totals.low} tone={totals.low > 0 ? "danger" : "neutral"} />
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-white px-4 py-3.5">
        <SearchInput
          value={query}
          onChange={(next) => {
            setQuery(next);
            setOffset(0);
          }}
        />
        <PickerField
          label={t.products.category}
          value={categoryId}
          options={[{ value: "", label: t.pos.allCategories }, ...categoryOptions]}
          onChange={(next) => {
            setCategoryId(next);
            setOffset(0);
          }}
          className="min-w-[14rem]"
        />
        <ChipGroup<ModeFilter>
          value={modeFilter}
          onChange={(next) => {
            setModeFilter(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "piece", label: t.products.salePiece },
            { value: "bulk", label: t.products.saleBulk },
          ]}
        />
        <ChipGroup<StockFilter>
          value={stockFilter}
          onChange={(next) => {
            setStockFilter(next);
            setOffset(0);
          }}
          options={[
            { value: "all", label: t.common.all },
            { value: "low", label: t.inventory.lowStockOnly },
            { value: "inactive", label: t.common.inactive },
          ]}
        />
      </div>

      <Card flush>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.id}
          loading={productsQuery.isLoading}
          rowClassName={(row) => (row.is_low ? "bg-danger-soft/30" : "")}
          empty={
            <EmptyState
              icon={<Package className="h-7 w-7" />}
              title={t.common.empty}
              hint={t.common.emptyHint}
              action={
                canManage ? (
                  <Button variant="primary" size="md" onClick={() => openForm(null)}>
                    {t.products.newProduct}
                  </Button>
                ) : undefined
              }
            />
          }
          footer={<Pager offset={offset} limit={PAGE_SIZE} total={filtered.length} onChange={setOffset} />}
        />
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        size="md"
        title={editing ? t.common.edit : t.products.newProduct}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setFormOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={form.sku.trim() === "" || form.name_mn.trim() === "" || form.category_id === ""}
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={submitForm}
            >
              {t.common.save}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <TextField
            label={t.common.name}
            value={form.name_mn}
            onChange={(value) => setForm({ ...form, name_mn: value })}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label={t.products.sku}
              value={form.sku}
              onChange={(value) => setForm({ ...form, sku: value })}
            />
            <TextField
              label={t.products.barcode}
              value={form.barcode}
              onChange={(value) => setForm({ ...form, barcode: value })}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <PickerField
              label={t.products.category}
              value={form.category_id}
              options={categoryOptions}
              onChange={(value) => setForm({ ...form, category_id: value })}
            />
            <TextField
              label={t.products.unit}
              value={form.unit}
              onChange={(value) => setForm({ ...form, unit: value })}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {editing ? (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
                  {t.common.price}
                </span>
                <div className="num flex h-14 items-center rounded-xl border border-line bg-surface-alt px-4 text-xl font-bold text-ink-soft">
                  {formatMNT(editing.price)}
                </div>
                <span className="text-xs text-ink-soft">{t.products.priceChangeOnly}</span>
              </div>
            ) : (
              <NumberField
                name="product-price"
                label={t.common.price}
                value={form.price}
                onChange={(value) => setForm({ ...form, price: value })}
                suffix={t.units.mnt}
              />
            )}
            <NumberField
              name="product-min-stock"
              label={t.products.minStock}
              value={form.min_stock}
              onChange={(value) => setForm({ ...form, min_stock: value })}
              maxDecimals={3}
            />
          </div>
          <ChipGroup<ProductSaleMode>
            label={t.products.saleMode}
            value={form.sale_mode}
            onChange={(value) =>
              setForm({
                ...form,
                sale_mode: value,
                // Грам бүтээгдэхүүн өөрөө задрахгүй — холбоосыг цэвэрлэнэ.
                ...(value === "bulk" ? { bulk_product_id: "", bulk_factor: "" } : {}),
                unit: value === "bulk" && form.unit === "ш" ? "л" : form.unit,
              })
            }
            options={[
              { value: "piece", label: t.products.salePiece },
              { value: "bulk", label: t.products.saleBulk },
            ]}
          />
          <p className="text-sm text-ink-soft">{t.products.saleModeHint}</p>

          {form.sale_mode === "piece" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <PickerField
                label={t.products.bulkTarget}
                value={form.bulk_product_id}
                options={[{ value: "", label: t.products.bulkNone }, ...bulkOptions]}
                onChange={(value) => setForm({ ...form, bulk_product_id: value })}
              />
              <NumberField
                name="product-bulk-factor"
                label={t.products.bulkFactor}
                value={form.bulk_factor}
                onChange={(value) => setForm({ ...form, bulk_factor: value })}
                maxDecimals={3}
                disabled={form.bulk_product_id === ""}
              />
            </div>
          ) : null}

          <ToggleField
            label={t.common.active}
            value={form.is_active}
            onChange={(value) => setForm({ ...form, is_active: value })}
          />
          {formError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {formError}
            </p>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={priceTarget !== null}
        onClose={() => setPriceTarget(null)}
        size="md"
        title={t.prices.request}
        subtitle={priceTarget?.name_mn}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={() => setPriceTarget(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="primary"
              size="md"
              disabled={dToNumber(newPrice) <= 0}
              loading={priceMutation.isPending}
              onClick={submitPriceRequest}
            >
              {t.refunds.request}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-line bg-surface-alt px-4 py-3">
              <div className="text-[11px] font-semibold tracking-wide text-ink-faint uppercase">
                {t.prices.oldPrice}
              </div>
              <div className="num text-2xl font-bold text-ink">{formatMNT(priceTarget?.price ?? "0")}</div>
            </div>
            <div className="rounded-xl border border-action/30 bg-action-soft px-4 py-3">
              <div className="text-[11px] font-semibold tracking-wide text-action-dark uppercase">
                {t.prices.diff}
              </div>
              <div className="num text-2xl font-bold text-action-dark">
                {formatMNT(dSub(newPrice === "" ? "0" : newPrice, priceTarget?.price ?? "0"))}
              </div>
            </div>
          </div>
          <NumberField
            name="product-new-price"
            label={t.prices.newPrice}
            value={newPrice}
            onChange={setNewPrice}
            suffix={t.units.mnt}
          />
          <TextAreaField label={t.common.reason} value={priceReason} onChange={setPriceReason} />
          <p className="text-sm text-ink-soft">{t.prices.approveConfirm}</p>
          {priceError ? (
            <p className="rounded-xl bg-danger-soft px-4 py-3 text-sm font-medium text-danger-dark">
              {priceError}
            </p>
          ) : null}
        </div>
      </Modal>

      <BulkConvertDialog
        open={converting !== null}
        onClose={() => setConverting(null)}
        sourceProductId={converting?.id ?? null}
      />

      <ConfirmDialog
        open={deactivating !== null}
        title={t.admin.deactivate}
        message={deactivating?.name_mn}
        variant="danger"
        confirmLabel={t.admin.deactivate}
        loading={deleteMutation.isPending}
        onConfirm={confirmDeactivate}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}

export default ProductsPage;
