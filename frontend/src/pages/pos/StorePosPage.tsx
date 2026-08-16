import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Droplets, Fuel, Package } from "lucide-react";

import { useProductCategories, useProducts } from "../../api/queries/products";
import { useCurrentShift } from "../../api/queries/shifts";
import type { Product, ProductSaleMode, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { CartPanel } from "../../components/pos/CartPanel";
import { CategoryTabs, ALL_CATEGORIES } from "../../components/pos/CategoryTabs";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { ProductSearch } from "../../components/pos/ProductSearch";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { t } from "../../i18n/mn";
import { formatLiters, formatMNT, formatQty } from "../../lib/format";
import { useAuthStore } from "../../stores/auth";
import { useCartStore, type CartLine } from "../../stores/cart";
import { useFuelSaleStore } from "../../stores/fuelSale";
import { useUiStore } from "../../stores/ui";

const QTY_PREFIX = "cart.qty:";

function matches(product: Product, query: string): boolean {
  if (query === "") return true;
  const needle = query.toLocaleLowerCase("mn-MN");
  return (
    product.name_mn.toLocaleLowerCase("mn-MN").includes(needle) ||
    product.sku.toLocaleLowerCase("mn-MN").includes(needle) ||
    (product.barcode ?? "").toLocaleLowerCase("mn-MN").includes(needle)
  );
}

function stockTone(product: Product): { chip: string; label: string } {
  const stock = Number(product.stock_qty);
  if (!Number.isFinite(stock) || stock <= 0) {
    return { chip: "bg-danger-soft text-danger-dark", label: t.pos.outOfStock };
  }
  if (product.is_low) {
    return { chip: "bg-warning-soft text-warning-dark", label: t.pos.lowStock };
  }
  return { chip: "bg-surface-sunken text-ink-soft", label: formatQty(product.stock_qty, product.unit) };
}

export function StorePosPage() {
  const navigate = useNavigate();

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const { data: categoriesPage } = useProductCategories();
  const [categoryId, setCategoryId] = useState<UUID | "">(ALL_CATEGORIES);
  const [query, setQuery] = useState("");
  /** Ширхэг эсвэл задлан (грам) бараа — талбайн бүтээгдэхүүнийг эндээс ч зарна. */
  const [saleMode, setSaleMode] = useState<ProductSaleMode>("piece");

  // Түгээгчийн салбарын үлдэгдэл, үнээр харуулна (салбаргүй хэрэглэгчид — нийт).
  const branchId = useAuthStore((state) => state.user?.branch?.id);
  const { data: productsPage, isLoading: productsLoading } = useProducts({
    category_id: categoryId === ALL_CATEGORIES ? undefined : categoryId,
    branch_id: branchId ?? undefined,
    sale_mode: saleMode,
    limit: 500,
  });

  /** Түлшний мөр аль хэдийн бүртгэгдсэн бол нэг борлуулалтад нийлнэ. */
  const fuelSale = useFuelSaleStore();
  const pendingFuel =
    fuelSale.phase === "awaiting_payment" && fuelSale.finalAmount !== null
      ? { name: fuelSale.fuelName, liters: fuelSale.finalLiters, amount: fuelSale.finalAmount }
      : null;

  const lines = useCartStore((state) => state.lines);
  const add = useCartStore((state) => state.add);
  const inc = useCartStore((state) => state.inc);
  const dec = useCartStore((state) => state.dec);
  const setQty = useCartStore((state) => state.setQty);
  const remove = useCartStore((state) => state.remove);
  const clear = useCartStore((state) => state.clear);
  const lineTotal = useCartStore((state) => state.lineTotal);
  const cartTotal = useCartStore((state) => state.total);

  const openNumPad = useUiStore((state) => state.openNumPad);
  const pushToast = useUiStore((state) => state.pushToast);
  const toastError = useUiStore((state) => state.toastError);

  const shiftOpen = Boolean(current?.shift);

  const products = useMemo(() => {
    const all = productsPage?.items ?? [];
    return all.filter((product) => product.is_active && matches(product, query.trim()));
  }, [productsPage, query]);

  const total = cartTotal();

  const handleAdd = (product: Product): void => {
    if (Number(product.stock_qty) <= 0) {
      toastError(t.pos.outOfStock);
      return;
    }
    // Задлан зарах бараа литр/дүнгээр зарагддаг тул талбайн дэлгэц рүү.
    if (product.sale_mode === "bulk") {
      navigate(`/pos/bulk?product=${product.id}`);
      return;
    }
    add(product, 1);
  };

  /** Штрих код / Enter — яг таарсан бараа байвал шууд сагсанд. */
  const handleSubmitSearch = (value: string): void => {
    const needle = value.trim();
    if (needle === "") return;
    const all = productsPage?.items ?? [];
    const exact = all.find(
      (product) =>
        product.is_active && (product.barcode === needle || product.sku.toUpperCase() === needle.toUpperCase()),
    );
    if (exact) {
      handleAdd(exact);
      setQuery("");
      pushToast(`${exact.name_mn} · ${formatMNT(exact.price)}`, "success", 1800);
      return;
    }
    const hits = all.filter((product) => product.is_active && matches(product, needle));
    if (hits.length === 1) {
      handleAdd(hits[0]);
      setQuery("");
      return;
    }
    if (hits.length === 0) toastError(t.pos.productNotFound);
  };

  const openQtyPad = (line: CartLine): void => {
    openNumPad({
      target: `${QTY_PREFIX}${line.productId}`,
      title: `${line.name} — ${t.common.qty}`,
      value: String(line.qty),
      allowDecimal: true,
      suffix: line.unit,
    });
  };

  const handleNumPad = (target: string, value: string): void => {
    if (!target.startsWith(QTY_PREFIX)) return;
    const productId = target.slice(QTY_PREFIX.length);
    const qty = Number(value);
    setQty(productId, Number.isFinite(qty) && qty > 0 ? qty : 0);
  };

  if (!shiftLoading && !shiftOpen) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.pos.store} />
        <div className="flex flex-1 items-center justify-center">
          <div className="flex w-full max-w-lg flex-col items-center gap-6 rounded-2xl border-2 border-warning bg-warning-soft px-6 py-12 text-center">
            <h2 className="text-2xl font-bold text-ink">{t.shift.noOpen}</h2>
            <p className="text-ink-soft">{t.pos.noOpenShift}</p>
            <Button variant="warning" size="lg" onClick={() => navigate("/shift")} className="min-w-56">
              {t.pos.openShiftNow}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4">
      <PageHeader
        title={t.pos.store}
        actions={
          <Button variant="secondary" size="md" icon={<Fuel />} onClick={() => navigate("/pos")}>
            {t.pos.forecourt}
          </Button>
        }
      />

      {pendingFuel ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border-2 border-action bg-action-soft/40 px-4 py-3">
          <Fuel className="h-5 w-5 shrink-0 text-action-dark" />
          <span className="min-w-0 flex-1 text-[15px] font-semibold text-ink">
            {t.pos.fuelInSale}: {pendingFuel.name} · {formatLiters(pendingFuel.liters, 2)}
          </span>
          <span className="num text-lg font-bold text-ink">{formatMNT(pendingFuel.amount)}</span>
        </div>
      ) : null}

      {/* Борлуулах хэлбэр — ширхэг эсвэл задлан (грам) */}
      <div className="flex flex-wrap gap-2">
        {(
          [
            { value: "piece", label: t.products.salePiece, icon: <Package className="h-5 w-5" /> },
            { value: "bulk", label: t.products.saleBulk, icon: <Droplets className="h-5 w-5" /> },
          ] as const
        ).map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setSaleMode(option.value)}
            className={[
              "flex h-12 items-center gap-2 rounded-xl border-2 px-4 text-[15px] font-bold transition-colors",
              saleMode === option.value
                ? "border-action bg-action text-white"
                : "border-line-strong bg-white text-ink active:bg-surface-sunken",
            ].join(" ")}
          >
            {option.icon}
            {option.label}
          </button>
        ))}
      </div>

      <CategoryTabs
        categories={categoriesPage?.items ?? []}
        value={categoryId}
        onChange={setCategoryId}
      />

      <ProductSearch value={query} onChange={setQuery} onSubmit={handleSubmitSearch} />

      <div className="flex min-h-0 flex-1 gap-5">
        {/* Барааны плиткууд */}
        <div className="min-w-0 flex-1 pb-28 lg:pb-0">
          {productsLoading ? (
            <div className="flex items-center justify-center py-20 text-ink-soft">
              <Spinner size="lg" label={t.common.loading} />
            </div>
          ) : products.length === 0 ? (
            <EmptyState
              title={t.pos.productNotFound}
              hint={t.common.emptyHint}
              icon={<Package className="h-7 w-7" />}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {products.map((product) => {
                const tone = stockTone(product);
                const soldOut = Number(product.stock_qty) <= 0;
                return (
                  <button
                    key={product.id}
                    type="button"
                    onClick={() => handleAdd(product)}
                    disabled={soldOut}
                    className={[
                      "flex min-h-36 flex-col justify-between gap-2 rounded-2xl border-2 bg-white px-3.5 py-3 text-left transition-colors",
                      soldOut
                        ? "border-danger/40 opacity-55"
                        : product.is_low
                          ? "border-warning hover:bg-warning-soft/40 active:bg-warning-soft"
                          : "border-line-strong hover:bg-surface-alt active:bg-surface-sunken",
                    ].join(" ")}
                  >
                    <span className="line-clamp-3 text-[15px] leading-snug font-bold text-ink">
                      {product.name_mn}
                    </span>
                    <span className="flex flex-col gap-1.5">
                      <span className="num text-2xl leading-none font-black text-ink">
                        {product.sale_mode === "bulk"
                          ? `${formatMNT(product.price)}/${product.unit}`
                          : formatMNT(product.price)}
                      </span>
                      <span
                        className={`num inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-bold ${tone.chip}`}
                      >
                        {tone.label}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Сагс */}
        <CartPanel
          lines={lines}
          total={total}
          lineTotal={lineTotal}
          onInc={inc}
          onDec={dec}
          onRemove={remove}
          onEditQty={openQtyPad}
          onClear={clear}
          onPay={() => navigate("/pos/payment")}
        />
      </div>

      <NumPadModal onSubmit={handleNumPad} />
    </div>
  );
}

export default StorePosPage;
