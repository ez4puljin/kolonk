import { create } from "zustand";

import type { PumpTelemetry, UUID } from "../api/types";

export type ConnectionState = "connecting" | "online" | "offline";

interface PumpsState {
  /** pump_id → сүүлийн телеметр. */
  telemetry: Record<UUID, PumpTelemetry>;
  connection: ConnectionState;
  lastMessageAt: number | null;

  upsert: (telemetry: PumpTelemetry) => void;
  replaceAll: (list: PumpTelemetry[]) => void;
  setConnection: (state: ConnectionState) => void;
  get: (pumpId: UUID) => PumpTelemetry | undefined;
  statusOf: (pumpId: UUID) => string | null;
  clear: () => void;
}

export const usePumpsStore = create<PumpsState>()((set, get) => ({
  telemetry: {},
  connection: "connecting",
  lastMessageAt: null,

  upsert: (telemetry) =>
    set((state) => ({
      telemetry: { ...state.telemetry, [telemetry.pump_id]: telemetry },
      lastMessageAt: Date.now(),
    })),

  replaceAll: (list) =>
    set(() => {
      const next: Record<UUID, PumpTelemetry> = {};
      for (const item of list) next[item.pump_id] = item;
      return { telemetry: next, lastMessageAt: Date.now() };
    }),

  setConnection: (connection) => set({ connection }),

  get: (pumpId) => get().telemetry[pumpId],

  statusOf: (pumpId) => get().telemetry[pumpId]?.status ?? null,

  clear: () => set({ telemetry: {}, lastMessageAt: null }),
}));
