import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  AuthorizeRequest,
  AuthorizeResponse,
  NozzleCreate,
  NozzleUpdate,
  Paged,
  Pump,
  PumpActionResponse,
  PumpCreate,
  PumpNozzle,
  PumpUpdate,
  UUID,
} from "../types";

export interface PumpListParams {
  active_only?: boolean;
  branch_id?: UUID;
  limit?: number;
  offset?: number;
}

export const pumpKeys = {
  all: ["pumps"] as const,
  list: (params?: PumpListParams) => ["pumps", "list", params ?? {}] as const,
  detail: (id: UUID) => ["pumps", "detail", id] as const,
};

export function usePumps(params?: PumpListParams) {
  return useQuery({
    queryKey: pumpKeys.list(params),
    queryFn: () => api.get<Paged<Pump>>("/api/pumps", { params: { ...params } }),
    staleTime: 15_000,
  });
}

export function usePump(id: UUID | null | undefined) {
  return useQuery({
    queryKey: pumpKeys.detail(id ?? ""),
    queryFn: () => api.get<Pump>(`/api/pumps/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreatePumpMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PumpCreate) => api.post<Pump>("/api/pumps", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

export function useUpdatePumpMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: PumpUpdate }) =>
      api.patch<Pump>(`/api/pumps/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

export function useDeletePumpMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/pumps/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

export function useCreateNozzleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pumpId, payload }: { pumpId: UUID; payload: NozzleCreate }) =>
      api.post<PumpNozzle>(`/api/pumps/${pumpId}/nozzles`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

export function useUpdateNozzleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pumpId, nozzleId, payload }: { pumpId: UUID; nozzleId: UUID; payload: NozzleUpdate }) =>
      api.patch<PumpNozzle>(`/api/pumps/${pumpId}/nozzles/${nozzleId}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

export function useDeleteNozzleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pumpId, nozzleId }: { pumpId: UUID; nozzleId: UUID }) =>
      api.del<void>(`/api/pumps/${pumpId}/nozzles/${nozzleId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

/** Хошуу зөвшөөрөх — таталт эхэлнэ. Хариу: authorization_id. */
export function useAuthorizePumpMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pumpId, payload }: { pumpId: UUID; payload: AuthorizeRequest }) =>
      api.post<AuthorizeResponse>(`/api/pumps/${pumpId}/authorize`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}

export function useStopPumpMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pumpId: UUID) => api.post<PumpActionResponse>(`/api/pumps/${pumpId}/stop`, {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: pumpKeys.all });
    },
  });
}
