import { useState } from "react";
import { ChevronRight, Minus, Plus, ShoppingCart, Trash2 } from "lucide-react";

import type { MoneyStr, UUID } from "../../api/types";
import { t } from "../../i18n/mn";
import { formatMNT, formatQty } from "../../lib/format";
import type { CartLine } from "../../stores/cart";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { Modal } from "../ui/Modal";

export interface CartPanelProps {
  lines: readonly CartLine[];
  total: MoneyStr;
  lineTotal: (line: CartLine) => MoneyStr;
  onInc: (productId: UUID) => void;
  onDec: (productId: UUID) => void;
  onRemove: (productId: UUID) => void;
  onEditQty: (line: CartLine) => void;
  onClear: () => void;
  onPay: () => void;
}

function Stepper({
  line,
  onInc,
  onDec,
  onEditQty,
}: {
  line: CartLine;
  onInc: (productId: UUID) => void;
  onDec: (productId: UUID) => void;
  onEditQty: (line: CartLine) => void;
}) {
  const capped = line.stockQty !== null && line.qty >= line.stockQty;

  // Задлан зарсан мөрд ±1 нэгж утгагүй (2.609 л → 3.609 л) — зөвхөн засах.
  if (line.bulk) {
    return (
      <button
        type="button"
        onClick={() => onEditQty(line)}
        aria-label={t.common.qty}
        className="num h-12 min-w-24 rounded-xl border border-line-strong bg-surface-alt px-3 text-lg font-bold text-ink active:bg-surface-sunken"
      >
        {formatQty(line.qty, line.unit)}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={() => onDec(line.productId)}
        aria-label={t.common.less}
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-line-strong bg-white text-ink active:bg-surface-sunken"
      >
        <Minus className="h-5 w-5" />
      </button>

      <button
        type="button"
        onClick={() => onEditQty(line)}
        aria-label={t.common.qty}
        className="num h-12 min-w-16 rounded-xl border border-line-strong bg-surface-alt px-2 text-lg font-bold text-ink active:bg-surface-sunken"
      >
        {formatQty(line.qty)}
      </button>

      <button
        type="button"
        disabled={capped}
        onClick={() => onInc(line.productId)}
        aria-label={t.common.more}
        className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-line-strong bg-white text-ink active:bg-surface-sunken disabled:opacity-40"
      >
        <Plus className="h-5 w-5" />
      </button>
    </div>
  );
}

function CartBody({
  lines,
  lineTotal,
  onInc,
  onDec,
  onRemove,
  onEditQty,
}: Pick<CartPanelProps, "lines" | "lineTotal" | "onInc" | "onDec" | "onRemove" | "onEditQty">) {
  if (lines.length === 0) {
    return <EmptyState title={t.pos.cartEmpty} hint={t.pos.addToCart} icon={<ShoppingCart className="h-7 w-7" />} />;
  }

  return (
    <ul className="flex flex-col gap-2.5">
      {lines.map((line) => (
        <li key={line.productId} className="rounded-xl border border-line bg-white px-3 py-3">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <div className="truncate text-[15px] font-bold text-ink">{line.name}</div>
              <div className="num truncate text-xs text-ink-soft">
                {formatMNT(line.unitPrice)} / {line.unit}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onRemove(line.productId)}
              aria-label={t.pos.removeLine}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-danger-dark active:bg-danger-soft"
            >
              <Trash2 className="h-4.5 w-4.5" />
            </button>
          </div>

          <div className="mt-2.5 flex items-center justify-between gap-3">
            <Stepper line={line} onInc={onInc} onDec={onDec} onEditQty={onEditQty} />
            <span className="num text-xl font-black text-ink">{formatMNT(lineTotal(line))}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * Сагс — ≥1024px дээр баруун талын багана, доор нь доод хуудас (bottom sheet).
 */
export function CartPanel({
  lines,
  total,
  lineTotal,
  onInc,
  onDec,
  onRemove,
  onEditQty,
  onClear,
  onPay,
}: CartPanelProps) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const count = lines.reduce((sum, line) => sum + line.qty, 0);
  const empty = lines.length === 0;

  const summary = (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-sm font-semibold tracking-wide text-ink-soft uppercase">{t.pos.totalDue}</span>
      <span className="num text-[40px] leading-none font-black text-ink">{formatMNT(total)}</span>
    </div>
  );

  return (
    <>
      {/* --- Ширээний хувилбар --- */}
      <aside className="hidden w-[380px] shrink-0 flex-col gap-4 rounded-2xl border border-line bg-surface-alt p-4 lg:flex">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-base font-bold text-ink">
            <ShoppingCart className="h-5 w-5" />
            {t.pos.cart}
            {count > 0 ? (
              <span className="num rounded-full bg-action px-2.5 py-0.5 text-sm font-bold text-white">
                {formatQty(count)}
              </span>
            ) : null}
          </span>
          {!empty ? (
            <button
              type="button"
              onClick={onClear}
              className="h-12 rounded-xl px-3 text-sm font-semibold text-danger-dark active:bg-danger-soft"
            >
              {t.pos.clearCart}
            </button>
          ) : null}
        </div>

        <div className="scroll-touch min-h-0 flex-1 overflow-y-auto">
          <CartBody
            lines={lines}
            lineTotal={lineTotal}
            onInc={onInc}
            onDec={onDec}
            onRemove={onRemove}
            onEditQty={onEditQty}
          />
        </div>

        <div className="flex flex-col gap-3 border-t border-line-strong pt-4">
          {summary}
          <Button variant="success" size="lg" block disabled={empty} onClick={onPay} iconRight={<ChevronRight />}>
            {t.nav.payment}
          </Button>
        </div>
      </aside>

      {/* --- Гар утасны доод самбар --- */}
      <div className="no-print safe-bottom fixed inset-x-0 bottom-16 z-20 border-t border-line-strong bg-white px-3 py-2.5 shadow-[0_-8px_24px_rgba(15,23,42,0.12)] lg:hidden">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            disabled={empty}
            className="flex min-h-14 flex-1 items-center gap-3 rounded-xl border border-line-strong bg-surface-alt px-3 text-left disabled:opacity-50"
          >
            <span className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-action text-white">
              <ShoppingCart className="h-5 w-5" />
              {count > 0 ? (
                <span className="num absolute -top-1.5 -right-1.5 rounded-full bg-danger px-1.5 text-[11px] font-bold text-white">
                  {formatQty(count)}
                </span>
              ) : null}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-semibold text-ink-soft">{t.pos.totalDue}</span>
              <span className="num block truncate text-2xl leading-tight font-black text-ink">
                {formatMNT(total)}
              </span>
            </span>
          </button>

          <Button variant="success" size="lg" disabled={empty} onClick={onPay}>
            {t.nav.payment}
          </Button>
        </div>
      </div>

      <Modal
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        size="md"
        title={t.pos.cart}
        subtitle={formatMNT(total)}
        footer={
          <>
            <Button variant="secondary" size="md" onClick={onClear}>
              {t.pos.clearCart}
            </Button>
            <Button
              variant="success"
              size="md"
              disabled={empty}
              onClick={() => {
                setSheetOpen(false);
                onPay();
              }}
            >
              {t.nav.payment}
            </Button>
          </>
        }
      >
        <CartBody
          lines={lines}
          lineTotal={lineTotal}
          onInc={onInc}
          onDec={onDec}
          onRemove={onRemove}
          onEditQty={onEditQty}
        />
      </Modal>
    </>
  );
}

export default CartPanel;
