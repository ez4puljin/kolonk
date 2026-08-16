import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronLeft, Droplets, Scissors, ShoppingBasket } from "lucide-react";

import { useProducts } from "../../api/queries/products";
import { useCurrentShift } from "../../api/queries/shifts";
import type { Product, UUID } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { AmountLiterToggle, type EntryMode } from "../../components/pos/AmountLiterToggle";
import { BulkConvertDialog } from "../../components/pos/BulkConvertDialog";
import { NumPadModal } from "../../components/pos/NumPadModal";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/Spinner";
import { useCan } from "../../hooks/usePermission";
import { t } from "../../i18n/mn";
import { PRESET_AMOUNTS, PRESET_LITERS } from "../../lib/constants";
import { dCmp, dDiv, dMul, dToQty } from "../../lib/decimal";
import { formatMNT, formatNumber, formatQty } from "../../lib/format";
import { useAuthStore } from "../../stores/auth";
import { useCartStore } from "../../stores/cart";
import { useUiStore } from "../../stores/ui";

const NUMPAD_ENTRY = "bulk.entry";

/**
 * Грам бүтээгдэхүүн — задлан зарах тос, шингэн.
 *
 * Кассын харагдац түлш зарахтай яг адил: бүтээгдэхүүнээ сонгоод литрээр
 * эсвэл мөнгөн дүнгээр оруулахад нөгөө тал нь автоматаар тооцоологдоно.
 * Дүнгээр оруулсан үед кассын бичсэн дүн тогтмол — сагсны мөр яг тэр дүнгээр
 * бүртгэгдэнэ (литр 3 оронтой тул `тоо × үнэ` 1-2₮ зөрдөг).
 */
export function BulkPosPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const canConvert = useCan("inventory.convert");

  const { data: current, isLoading: shiftLoading } = useCurrentShift();
  const branchId = useAuthStore((state) => state.user?.branch?.id) ?? null;

  const { data: page, isLoading } = useProducts({
    sale_mode: "bulk",
    branch_id: branchId ?? undefined,
    limit: 200,
  });

  const addBulk = useCartStore((state) => state.addBulk);
  const cartLines = useCartStore((state) => state.lines);
  const cartTotal = useCartStore((state) => state.total);
  const openNumPad = useUiStore((state) => state.openNumPad);
  const toastError = useUiStore((state) => state.toastError);
  const pushToast = useUiStore((state) => state.pushToast);

  const [entryMode, setEntryMode] = useState<EntryMode>("amount");
  const [entry, setEntry] = useState("");
  const [convertOpen, setConvertOpen] = useState(false);

  const products = useMemo(
    () => (page?.items ?? []).filter((product) => product.is_active),
    [page],
  );

  // Сонгосон бүтээгдэхүүн URL-д байна — дэлгүүрээс шууд орж ирж болно.
  const selectedId = (params.get("product") ?? "") as UUID | "";
  const selected: Product | null = products.find((product) => product.id === selectedId) ?? null;

  const select = (product: Product | null): void => {
    setEntry("");
    if (product === null) {
      params.delete("product");
      setParams(params, { replace: true });
      return;
    }
    params.set("product", product.id);
    setParams(params, { replace: true });
  };

  // Ээлж хаагдвал сонголтыг цэвэрлэнэ.
  const shiftOpen = Boolean(current?.shift);
  useEffect(() => {
    if (!shiftOpen && !shiftLoading && selectedId !== "") select(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shiftOpen, shiftLoading]);

  const unitPrice = selected?.price ?? "0";

  /** Оруулсан утгаас нөгөөг нь тооцоолно: тоо хэмжээ ⇄ дүн. */
  const computed = useMemo(() => {
    if (entry === "" || dCmp(entry, "0") <= 0 || dCmp(unitPrice, "0") <= 0) {
      return { qty: "0", amount: "0.00" };
    }
    if (entryMode === "liters") {
      return { qty: entry.trim(), amount: dMul(unitPrice, dToQty(entry)) };
    }
    return { qty: dDiv(entry, unitPrice, 3), amount: entry };
  }, [entry, entryMode, unitPrice]);

  const stock = selected ? dToQty(selected.stock_qty) : 0;
  const enough = dToQty(computed.qty) <= stock;
  const canSell =
    selected !== null && dCmp(computed.qty, "0") > 0 && dCmp(computed.amount, "0") > 0 && enough;

  const handleSell = (next: "payment" | "stay"): void => {
    if (!selected || !canSell) return;
    addBulk(selected, dToQty(computed.qty), computed.amount);
    setEntry("");
    if (next === "payment") {
      navigate("/pos/payment");
      return;
    }
    pushToast(`${selected.name_mn} · ${formatMNT(computed.amount)}`, "success", 1800);
    select(null);
  };

  const openEntryPad = (): void => {
    openNumPad({
      target: NUMPAD_ENTRY,
      title: entryMode === "liters" ? t.pos.presetLiters : t.pos.presetAmount,
      value: entry,
      allowDecimal: true,
      suffix: entryMode === "liters" ? (selected?.unit ?? t.units.liter) : t.units.mnt,
    });
  };

  // ---------------------------------------------------------------- Ээлжгүй
  if (!shiftLoading && !shiftOpen) {
    return (
      <div className="flex flex-1 flex-col gap-6">
        <PageHeader title={t.pos.bulkProducts} />
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

  // ------------------------------------------------- Бүтээгдэхүүн сонгосон үе
  if (selected) {
    return (
      <div className="flex flex-1 flex-col gap-5">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => select(null)}
            className="flex h-12 items-center gap-2 rounded-xl border border-line-strong bg-white px-4 font-semibold text-ink active:bg-surface-sunken"
          >
            <ChevronLeft className="h-5 w-5" />
            {t.pos.bulkProducts}
          </button>
          <h1 className="min-w-0 flex-1 truncate text-2xl font-bold text-ink">{selected.name_mn}</h1>
          {canConvert ? (
            <Button variant="secondary" size="md" icon={<Scissors />} onClick={() => setConvertOpen(true)}>
              {t.inventory.convert}
            </Button>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <div className="flex flex-col gap-5">
            <Card>
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
                    {t.common.unitPrice}
                  </div>
                  <div className="num text-3xl font-black text-ink">
                    {formatNumber(selected.price)} ₮/{selected.unit}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
                    {t.pos.bulkStock}
                  </div>
                  <div
                    className={`num text-3xl font-black ${stock <= 0 ? "text-danger-dark" : "text-success-dark"}`}
                  >
                    {formatQty(selected.stock_qty, selected.unit)}
                  </div>
                </div>
              </div>
            </Card>

            <AmountLiterToggle
              value={entryMode}
              onChange={(mode) => {
                setEntryMode(mode);
                setEntry("");
              }}
            />
          </div>

          <div className="flex flex-col gap-5">
            <button
              type="button"
              onClick={openEntryPad}
              className="flex min-h-28 w-full flex-col justify-center gap-1 rounded-2xl border-2 border-line-strong bg-surface-alt px-6 py-4 text-left active:bg-surface-sunken"
            >
              <span className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
                {entryMode === "liters" ? t.pos.presetLiters : t.pos.presetAmount}
              </span>
              <span className="num text-[48px] leading-none font-black text-ink">
                {entry === ""
                  ? "0"
                  : entryMode === "liters"
                    ? `${formatNumber(entry, 2)} ${selected.unit}`
                    : formatMNT(entry)}
              </span>
            </button>

            <div className="grid grid-cols-4 gap-2">
              {(entryMode === "liters" ? PRESET_LITERS : PRESET_AMOUNTS).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setEntry(String(value))}
                  className="num h-14 rounded-xl border-2 border-line-strong bg-white text-[15px] font-bold text-ink active:bg-surface-sunken"
                >
                  {entryMode === "liters" ? `${value}${selected.unit}` : formatNumber(value, 0)}
                </button>
              ))}
            </div>

            <div className="rounded-2xl border border-line-strong bg-white px-5 py-4">
              <div className="num flex items-baseline justify-between gap-3">
                <span className="text-sm font-semibold tracking-wide text-ink-soft uppercase">
                  {entryMode === "liters" ? t.common.amount : t.common.qty}
                </span>
                <span className="text-[40px] leading-none font-black text-success-dark">
                  {entryMode === "liters"
                    ? formatMNT(computed.amount)
                    : formatQty(computed.qty, selected.unit)}
                </span>
              </div>
            </div>

            {!enough ? (
              <div className="rounded-xl border border-danger bg-danger-soft px-4 py-3 text-[15px] font-semibold text-danger-dark">
                {t.pos.outOfStock} · {formatQty(selected.stock_qty, selected.unit)}
              </div>
            ) : null}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Button
                variant="secondary"
                size="lg"
                icon={<ShoppingBasket />}
                disabled={!canSell}
                onClick={() => handleSell("stay")}
              >
                {t.pos.addToCart}
              </Button>
              <Button variant="success" size="lg" disabled={!canSell} onClick={() => handleSell("payment")}>
                {t.pos.toPayment}
              </Button>
            </div>
          </div>
        </div>

        <NumPadModal onSubmit={(target, value) => target === NUMPAD_ENTRY && setEntry(value.trim())} />
        <BulkConvertDialog
          open={convertOpen}
          onClose={() => setConvertOpen(false)}
          targetProductId={selected.id}
          branchId={branchId}
        />
      </div>
    );
  }

  // ------------------------------------------------------- Бүтээгдэхүүний жагсаалт
  return (
    <div className="flex flex-1 flex-col gap-5">
      <PageHeader
        title={t.pos.bulkProducts}
        subtitle={t.pos.bulkHint}
        actions={
          <>
            {canConvert ? (
              <Button variant="secondary" size="lg" icon={<Scissors />} onClick={() => setConvertOpen(true)}>
                {t.inventory.convert}
              </Button>
            ) : null}
            <Button variant="secondary" size="lg" icon={<ChevronLeft />} onClick={() => navigate("/pos")}>
              {t.pos.forecourt}
            </Button>
            {cartLines.length > 0 ? (
              <Button variant="success" size="lg" onClick={() => navigate("/pos/payment")}>
                {t.pos.payNow} · {formatMNT(cartTotal())}
              </Button>
            ) : null}
          </>
        }
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-24 text-ink-soft">
          <Spinner size="lg" label={t.common.loading} />
        </div>
      ) : products.length === 0 ? (
        <EmptyState
          icon={<Droplets className="h-7 w-7" />}
          title={t.pos.bulkEmpty}
          hint={t.products.saleModeHint}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {products.map((product) => {
            const empty = dToQty(product.stock_qty) <= 0;
            return (
              <button
                key={product.id}
                type="button"
                disabled={empty}
                onClick={() => {
                  if (empty) {
                    toastError(t.pos.outOfStock);
                    return;
                  }
                  select(product);
                }}
                className={[
                  "flex min-h-40 flex-col justify-between gap-3 rounded-2xl border-2 bg-white px-4 py-4 text-left transition-colors",
                  empty
                    ? "border-danger/40 opacity-55"
                    : product.is_low
                      ? "border-warning hover:bg-warning-soft/40 active:bg-warning-soft"
                      : "border-line-strong hover:bg-surface-alt active:bg-surface-sunken",
                ].join(" ")}
              >
                <span className="flex items-start gap-3">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-action text-white">
                    <Droplets className="h-6 w-6" />
                  </span>
                  <span className="line-clamp-3 text-[17px] leading-snug font-bold text-ink">
                    {product.name_mn}
                  </span>
                </span>
                <span className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="num text-2xl leading-none font-black text-ink">
                    {formatNumber(product.price)} ₮/{product.unit}
                  </span>
                  <span
                    className={`num rounded-full px-2.5 py-1 text-xs font-bold ${
                      empty
                        ? "bg-danger-soft text-danger-dark"
                        : product.is_low
                          ? "bg-warning-soft text-warning-dark"
                          : "bg-surface-sunken text-ink-soft"
                    }`}
                  >
                    {formatQty(product.stock_qty, product.unit)}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      <BulkConvertDialog
        open={convertOpen}
        onClose={() => setConvertOpen(false)}
        branchId={branchId}
      />
    </div>
  );
}

export default BulkPosPage;
