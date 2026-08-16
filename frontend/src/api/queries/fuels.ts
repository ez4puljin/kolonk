import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type { Fuel, FuelCreate, FuelUpdate, Paged, UUID } from "../types";

export interface FuelListParams {
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export const fuelKeys = {
  all: ["fuels"] as const,
  list: (params?: FuelListParams) => ["fuels", "list", params ?? {}] as const,
  detail: (id: UUID) => ["fuels", "detail", id] as const,
};

export function useFuels(params?: FuelListParams) {
  return useQuery({
    queryKey: fuelKeys.list(params),
    queryFn: () => api.get<Paged<Fuel>>("/api/fuels", { params: { ...params } }),
    staleTime: 120_000,
  });
}

export function useFuel(id: UUID | null | undefined) {
  return useQuery({
    queryKey: fuelKeys.detail(id ?? ""),
    queryFn: () => api.get<Fuel>(`/api/fuels/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateFuelMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FuelCreate) => api.post<Fuel>("/api/fuels", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: fuelKeys.all });
    },
  });
}

export function useUpdateFuelMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: FuelUpdate }) =>
      api.patch<Fuel>(`/api/fuels/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: fuelKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["pumps"] });
    },
  });
}
