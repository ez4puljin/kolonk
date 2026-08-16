import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type { Paged, Tank, TankAdjustment, TankCreate, TankMovement, TankUpdate, UUID } from "../types";

export interface TankListParams {
  fuel_id?: UUID;
  active_only?: boolean;
  branch_id?: UUID;
  limit?: number;
  offset?: number;
}

export interface TankMovementParams {
  movement_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const tankKeys = {
  all: ["tanks"] as const,
  list: (params?: TankListParams) => ["tanks", "list", params ?? {}] as const,
  detail: (id: UUID) => ["tanks", "detail", id] as const,
  movements: (id: UUID, params?: TankMovementParams) =>
    ["tanks", "movements", id, params ?? {}] as const,
};

export function useTanks(params?: TankListParams) {
  return useQuery({
    queryKey: tankKeys.list(params),
    queryFn: () => api.get<Paged<Tank>>("/api/tanks", { params: { ...params } }),
    staleTime: 30_000,
  });
}

export function useTank(id: UUID | null | undefined) {
  return useQuery({
    queryKey: tankKeys.detail(id ?? ""),
    queryFn: () => api.get<Tank>(`/api/tanks/${id}`),
    enabled: Boolean(id),
  });
}

export function useTankMovements(id: UUID | null | undefined, params?: TankMovementParams) {
  return useQuery({
    queryKey: tankKeys.movements(id ?? "", params),
    queryFn: () => api.get<Paged<TankMovement>>(`/api/tanks/${id}/movements`, { params: { ...params } }),
    enabled: Boolean(id),
  });
}

export function useCreateTankMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TankCreate) => api.post<Tank>("/api/tanks", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tankKeys.all });
    },
  });
}

export function useUpdateTankMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: TankUpdate }) =>
      api.patch<Tank>(`/api/tanks/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tankKeys.all });
    },
  });
}

export function useAdjustTankMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: TankAdjustment }) =>
      api.post<Tank>(`/api/tanks/${id}/adjustments`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tankKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}

export function useDeactivateTankMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/tanks/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: tankKeys.all });
    },
  });
}
