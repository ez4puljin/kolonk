import { create } from "zustand";

import type { MoneyStr, Product, UUID } from "../api/types";
import { dAdd, dMul, D_ZERO } from "../lib/decimal";

export interface CartLine {
  productId: UUID;
  sku: string;
  name: string;
  unit: string;
  unitPrice: MoneyStr;
  qty: number;
  /** Нөөцийн дээд хязгаар — сөрөг үлдэгдэл гаргахгүй. */
  stockQty: number | null;
  /** Задлан (грамлаж) зарсан мөр — тоо хэмжээ бутархай. */
  bulk: boolean;
  /**
   * Мөрийн яг мөнгөн дүн.
   *
   * Задлан зарахад касс дүнгээр оруулдаг: тоо хэмжээ 3 оронтой тул
   * `тоо × үнэ` нь 1-2₮ зөрдөг.  Энэ талбар байвал кассын оруулсан дүнг
   * барина (сервер нь мөн адил хүлээж авдаг).
   */
  amount: MoneyStr | null;
}

interface CartState {
  lines: CartLine[];

  add: (product: Product, qty?: number) => void;
  /** Задлан зарах — тоо хэмжээ бутархай, дүн нь кассын оруулсан яг дүн. */
  addBulk: (product: Product, qty: number, amount: MoneyStr) => void;
  inc: (productId: UUID) => void;
  dec: (productId: UUID) => void;
  setQty: (productId: UUID, qty: number) => void;
  remove: (productId: UUID) => void;
  clear: () => void;
  count: () => number;
  lineTotal: (line: CartLine) => MoneyStr;
  total: () => MoneyStr;
  isEmpty: () => boolean;
}

function toQtyNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export const useCartStore = create<CartState>()((set, get) => ({
  lines: [],

  add: (product, qty = 1) =>
    set((state) => {
      const stock = toQtyNumber(product.stock_qty);
      const existing = state.lines.find((line) => line.productId === product.id);
      if (existing) {
        return {
          lines: state.lines.map((line) =>
            line.productId === product.id
              ? { ...line, qty: Math.round((line.qty + qty) * 1000) / 1000 }
              : line,
          ),
        };
      }
      const line: CartLine = {
        productId: product.id,
        sku: product.sku,
        name: product.name_mn,
        unit: product.unit,
        unitPrice: product.price,
        qty,
        stockQty: Number.isFinite(stock) ? stock : null,
        bulk: false,
        amount: null,
      };
      return { lines: [...state.lines, line] };
    }),

  addBulk: (product, qty, amount) =>
    set((state) => {
      const stock = toQtyNumber(product.stock_qty);
      const existing = state.lines.find((line) => line.productId === product.id);
      if (existing) {
        return {
          lines: state.lines.map((line) =>
            line.productId === product.id
              ? {
                  ...line,
                  qty: Math.round((line.qty + qty) * 1000) / 1000,
                  bulk: true,
                  amount: dAdd(line.amount ?? dMul(line.unitPrice, line.qty), amount),
                }
              : line,
          ),
        };
      }
      return {
        lines: [
          ...state.lines,
          {
            productId: product.id,
            sku: product.sku,
            name: product.name_mn,
            unit: product.unit,
            unitPrice: product.price,
            qty,
            stockQty: Number.isFinite(stock) ? stock : null,
            bulk: true,
            amount,
          },
        ],
      };
    }),

  inc: (productId) =>
    set((state) => ({
      lines: state.lines.map((line) =>
        line.productId === productId
          ? { ...line, qty: Math.round((line.qty + 1) * 1000) / 1000, amount: null }
          : line,
      ),
    })),

  dec: (productId) =>
    set((state) => ({
      lines: state.lines.flatMap((line) => {
        if (line.productId !== productId) return [line];
        const next = Math.round((line.qty - 1) * 1000) / 1000;
        return next <= 0 ? [] : [{ ...line, qty: next, amount: null }];
      }),
    })),

  setQty: (productId, qty) =>
    set((state) => ({
      lines: state.lines.flatMap((line) => {
        if (line.productId !== productId) return [line];
        return qty <= 0 ? [] : [{ ...line, qty, amount: null }];
      }),
    })),

  remove: (productId) =>
    set((state) => ({ lines: state.lines.filter((line) => line.productId !== productId) })),

  clear: () => set({ lines: [] }),

  count: () => get().lines.reduce((sum, line) => sum + line.qty, 0),

  lineTotal: (line) => line.amount ?? dMul(line.unitPrice, line.qty),

  total: () => {
    let sum = D_ZERO;
    for (const line of get().lines) sum = dAdd(sum, line.amount ?? dMul(line.unitPrice, line.qty));
    return sum;
  },

  isEmpty: () => get().lines.length === 0,
}));
