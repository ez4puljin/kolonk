import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { LoginResponse, MeResponse, UserTile } from "../api/types";

export const AUTH_STORAGE_KEY = "kolonk.auth";

interface AuthState {
  token: string | null;
  user: UserTile | null;
  permissions: string[];
  shiftOpen: boolean;
  shiftId: string | null;
  shiftNumber: number | null;

  login: (payload: LoginResponse) => void;
  applyMe: (payload: MeResponse) => void;
  setShift: (open: boolean, shiftId: string | null, shiftNumber: number | null) => void;
  logout: () => void;
  can: (code: string) => boolean;
  canAny: (codes: readonly string[]) => boolean;
  isAuthenticated: () => boolean;
}

const emptySession = {
  token: null,
  user: null,
  permissions: [] as string[],
  shiftOpen: false,
  shiftId: null,
  shiftNumber: null,
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      ...emptySession,

      login: (payload) =>
        set({
          token: payload.token,
          user: payload.user,
          permissions: payload.permissions,
        }),

      applyMe: (payload) =>
        set({
          user: payload.user,
          permissions: payload.permissions,
          shiftOpen: payload.shift_open,
          shiftId: payload.shift_id,
          shiftNumber: payload.shift_number,
        }),

      setShift: (open, shiftId, shiftNumber) =>
        set({ shiftOpen: open, shiftId, shiftNumber }),

      logout: () => set({ ...emptySession }),

      can: (code) => get().permissions.includes(code),

      canAny: (codes) => {
        if (codes.length === 0) return true;
        const granted = get().permissions;
        return codes.some((code) => granted.includes(code));
      },

      isAuthenticated: () => Boolean(get().token),
    }),
    {
      name: AUTH_STORAGE_KEY,
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        permissions: state.permissions,
      }),
    },
  ),
);

/** React-ээс гадуур (api/client.ts, WebSocket) хандах хялбар туслахууд. */
export function getToken(): string | null {
  return useAuthStore.getState().token;
}

export function clearSession(): void {
  useAuthStore.getState().logout();
}
