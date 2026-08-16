import { create } from "zustand";

import type { MoneyStr, LitersStr, PresetType, UUID } from "../api/types";

/**
 * Түлш зарах урсгалын төлөв.
 *
 * idle → preset → authorizing → fueling → awaiting_payment → (reset)
 */
export type FuelSalePhase = "idle" | "preset" | "authorizing" | "fueling" | "awaiting_payment";

interface FuelSaleState {
  phase: FuelSalePhase;

  pumpId: UUID | null;
  pumpNumber: number | null;
  nozzleId: UUID | null;
  nozzleNumber: number | null;
  fuelId: UUID | null;
  fuelName: string | null;
  fuelColor: string | null;
  tankId: UUID | null;
  unitPrice: MoneyStr | null;

  presetType: PresetType;
  presetValue: MoneyStr | null;

  authorizationId: UUID | null;

  liveLiters: LitersStr;
  liveAmount: MoneyStr;
  liveFlow: string;

  finalLiters: LitersStr | null;
  finalAmount: MoneyStr | null;
  /** Гар борлуулалтад касс юугаар оруулсан (насосны борлуулалтад null). */
  entryMode: "amount" | "liters" | null;

  error: string | null;

  selectNozzle: (input: {
    pumpId: UUID;
    pumpNumber: number | null;
    nozzleId: UUID;
    nozzleNumber: number | null;
    fuelId: UUID;
    fuelName: string;
    fuelColor: string;
    tankId: UUID;
    unitPrice: MoneyStr;
  }) => void;
  setPreset: (type: PresetType, value: MoneyStr | null) => void;
  beginAuthorize: () => void;
  authorized: (authorizationId: UUID) => void;
  tick: (liters: LitersStr, amount: MoneyStr, flow?: string) => void;
  complete: (liters: LitersStr, amount: MoneyStr) => void;
  /** Тоног төхөөрөмжгүй гар борлуулалт — шууд төлбөрийн шатанд.

  `mode` нь касс юугаар оруулсныг заана: "amount" бол мөнгөн дүн тогтмол
  (гэрээний хөнгөлөлт орвол литр нэмэгдэнэ), "liters" бол литр тогтмол. */
  manual: (liters: LitersStr, amount: MoneyStr, mode: "amount" | "liters") => void;
  fail: (message: string) => void;
  toPayment: () => void;
  reset: () => void;
}

const empty = {
  phase: "idle" as FuelSalePhase,
  pumpId: null,
  pumpNumber: null,
  nozzleId: null,
  nozzleNumber: null,
  fuelId: null,
  fuelName: null,
  fuelColor: null,
  tankId: null,
  unitPrice: null,
  presetType: "full" as PresetType,
  presetValue: null,
  authorizationId: null,
  liveLiters: "0.000",
  liveAmount: "0.00",
  liveFlow: "0.0",
  finalLiters: null,
  finalAmount: null,
  entryMode: null,
  error: null,
};

export const useFuelSaleStore = create<FuelSaleState>()((set, get) => ({
  ...empty,

  selectNozzle: (input) =>
    set({
      ...empty,
      phase: "preset",
      pumpId: input.pumpId,
      pumpNumber: input.pumpNumber,
      nozzleId: input.nozzleId,
      nozzleNumber: input.nozzleNumber,
      fuelId: input.fuelId,
      fuelName: input.fuelName,
      fuelColor: input.fuelColor,
      tankId: input.tankId,
      unitPrice: input.unitPrice,
    }),

  setPreset: (type, value) => set({ presetType: type, presetValue: value, error: null }),

  beginAuthorize: () => set({ phase: "authorizing", error: null }),

  authorized: (authorizationId) =>
    set({
      phase: "fueling",
      authorizationId,
      liveLiters: "0.000",
      liveAmount: "0.00",
      liveFlow: "0.0",
      error: null,
    }),

  tick: (liters, amount, flow) => {
    const state = get();
    if (state.phase !== "fueling" && state.phase !== "authorizing") return;
    set({
      phase: "fueling",
      liveLiters: liters,
      liveAmount: amount,
      liveFlow: flow ?? state.liveFlow,
    });
  },

  complete: (liters, amount) =>
    set({
      phase: "awaiting_payment",
      liveLiters: liters,
      liveAmount: amount,
      liveFlow: "0.0",
      finalLiters: liters,
      finalAmount: amount,
    }),

  manual: (liters, amount, mode) =>
    set({
      phase: "awaiting_payment",
      entryMode: mode,
      liveLiters: liters,
      liveAmount: amount,
      liveFlow: "0.0",
      finalLiters: liters,
      finalAmount: amount,
      error: null,
    }),

  fail: (message) => set({ phase: "preset", error: message }),

  toPayment: () => set({ phase: "awaiting_payment" }),

  reset: () => set({ ...empty }),
}));
