import { create } from "zustand";

import type { ShiftStatus, ShiftSummary, UUID } from "../api/types";

/**
 * Идэвхтэй ээлжийн хөнгөн толь. Жинхэнэ эх сурвалж нь
 * `GET /api/shifts/current` (TanStack Query) — энэ store зөвхөн касс дээр
 * дахин дуудалт хийхгүйгээр шалгах зорилготой.
 */
interface ShiftState {
  currentShiftId: UUID | null;
  currentShiftNumber: number | null;
  status: ShiftStatus | null;
  openedAt: string | null;

  setFromSummary: (shift: ShiftSummary | null | undefined) => void;
  setShiftId: (id: UUID | null, number?: number | null) => void;
  clear: () => void;
  hasOpenShift: () => boolean;
}

const empty = {
  currentShiftId: null,
  currentShiftNumber: null,
  status: null,
  openedAt: null,
};

export const useShiftStore = create<ShiftState>()((set, get) => ({
  ...empty,

  setFromSummary: (shift) => {
    if (!shift) {
      set({ ...empty });
      return;
    }
    set({
      currentShiftId: shift.id,
      currentShiftNumber: shift.number,
      status: shift.status === "closed" ? "closed" : "open",
      openedAt: shift.opened_at,
    });
  },

  setShiftId: (id, number = null) =>
    set({
      currentShiftId: id,
      currentShiftNumber: number,
      status: id ? "open" : null,
    }),

  clear: () => set({ ...empty }),

  hasOpenShift: () => {
    const state = get();
    return state.currentShiftId !== null && state.status === "open";
  },
}));
