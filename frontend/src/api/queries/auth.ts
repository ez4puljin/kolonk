import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type { CurrentShift, HealthResponse, LoginRequest, LoginResponse, MeResponse, UserTile } from "../types";
import { useAuthStore } from "../../stores/auth";
import { useShiftStore } from "../../stores/shift";

export const authKeys = {
  all: ["auth"] as const,
  tiles: () => ["auth", "tiles"] as const,
  me: () => ["auth", "me"] as const,
  health: () => ["auth", "health"] as const,
};

/** Нэвтрэх дэлгэцийн хэрэглэгчийн плиткууд — нэвтрэлт шаардахгүй. */
export function useLoginTiles() {
  return useQuery({
    queryKey: authKeys.tiles(),
    queryFn: () => api.get<UserTile[]>("/api/auth/users", { anonymous: true }),
    staleTime: 60_000,
  });
}

/** Серверийн эрүүл мэнд — нэвтрэх дэлгэц дээр холболтын заагч. */
export function useHealth(enabled = true) {
  return useQuery({
    queryKey: authKeys.health(),
    queryFn: () => api.get<HealthResponse>("/api/health", { anonymous: true, silent: true }),
    enabled,
    refetchInterval: 20_000,
    retry: false,
  });
}

/**
 * Нэвтрэх дэлгэцэд ээлжийн төлвийг харуулах оролдлого.
 * Токенгүй үед сервер 401 буцаана — чимээгүй алгасна.
 */
export function useShiftStatusPreview(enabled = true) {
  return useQuery({
    queryKey: ["auth", "shift-preview"] as const,
    queryFn: () => api.get<CurrentShift | null>("/api/shifts/current", { silent: true }),
    enabled,
    retry: false,
    staleTime: 30_000,
  });
}

export function useMe(enabled = true) {
  const applyMe = useAuthStore((state) => state.applyMe);
  const setFromSummary = useShiftStore((state) => state.setFromSummary);

  return useQuery({
    queryKey: authKeys.me(),
    queryFn: async () => {
      const me = await api.get<MeResponse>("/api/auth/me");
      applyMe(me);
      if (!me.shift_open) setFromSummary(null);
      return me;
    },
    enabled,
    staleTime: 60_000,
  });
}

export function useLoginMutation() {
  const queryClient = useQueryClient();
  const login = useAuthStore((state) => state.login);

  return useMutation({
    mutationFn: (payload: LoginRequest) =>
      api.post<LoginResponse>("/api/auth/login", payload, { anonymous: true, silent: true }),
    onSuccess: (data) => {
      login(data);
      void queryClient.invalidateQueries();
    },
  });
}

export function useLogoutMutation() {
  const queryClient = useQueryClient();
  const logout = useAuthStore((state) => state.logout);
  const clearShift = useShiftStore((state) => state.clear);

  return useMutation({
    mutationFn: () => api.post<{ ok: boolean }>("/api/auth/logout", {}, { silent: true }),
    onSettled: () => {
      logout();
      clearShift();
      queryClient.clear();
    },
  });
}
