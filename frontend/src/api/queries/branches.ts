import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  Branch,
  BranchCreate,
  BranchPaymentMethod,
  BranchUpdate,
  UUID,
} from "../types";

export const branchKeys = {
  all: ["branches"] as const,
};

/** Салбарын жагсаалт — нэвтэрсэн бүх хэрэглэгч харна. */
export function useBranches() {
  return useQuery({
    queryKey: branchKeys.all,
    queryFn: () => api.get<Branch[]>("/api/branches"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateBranchMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BranchCreate) => api.post<Branch>("/api/branches", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: branchKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["report-center"] });
    },
  });
}

export function useUpdateBranchMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: BranchUpdate & { id: UUID }) =>
      api.patch<Branch>(`/api/branches/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: branchKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["report-center"] });
    },
  });
}


/** Салбарын төлбөрийн хэрэгслүүд (тохируулаагүй бол бүгд идэвхтэй). */
export function useBranchPaymentMethods(branchId: UUID | null | undefined) {
  return useQuery({
    queryKey: [...branchKeys.all, branchId ?? "", "payment-methods"],
    queryFn: () => api.get<BranchPaymentMethod[]>(`/api/branches/${branchId}/payment-methods`),
    enabled: Boolean(branchId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSetBranchPaymentMethodsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      branchId,
      methods,
    }: {
      branchId: UUID;
      methods: { method: string; is_enabled: boolean }[];
    }) => api.put<BranchPaymentMethod[]>(`/api/branches/${branchId}/payment-methods`, methods),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: branchKeys.all });
    },
  });
}
