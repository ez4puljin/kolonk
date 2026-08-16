import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  Paged,
  PriceChange,
  PriceChangeCreate,
  PriceChangeDecision,
  Refund,
  RefundCreate,
  RefundDecision,
  RefundResult,
  UUID,
} from "../types";

export interface ApprovalListParams {
  status?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface RefundListParams extends ApprovalListParams {
  sale_id?: UUID;
  shift_id?: UUID;
}

export const approvalKeys = {
  refunds: ["refunds"] as const,
  refundList: (params?: RefundListParams) => ["refunds", "list", params ?? {}] as const,
  refundDetail: (id: UUID) => ["refunds", "detail", id] as const,
  priceChanges: ["price-changes"] as const,
  priceChangeList: (params?: ApprovalListParams) => ["price-changes", "list", params ?? {}] as const,
};

function invalidateAfterDecision(invalidate: (key: readonly unknown[]) => void): void {
  invalidate(approvalKeys.refunds);
  invalidate(approvalKeys.priceChanges);
  invalidate(["sales"]);
  invalidate(["shifts"]);
  invalidate(["accounting"]);
  invalidate(["dashboard"]);
  invalidate(["fuels"]);
  invalidate(["products"]);
  invalidate(["pumps"]);
}

// -------------------------------------------------------------------------
// Буцаалт
// -------------------------------------------------------------------------

export function useRefunds(params?: RefundListParams) {
  return useQuery({
    queryKey: approvalKeys.refundList(params),
    queryFn: () => api.get<Paged<Refund>>("/api/refunds", { params: { ...params } }),
  });
}

export function useRefund(id: UUID | null | undefined) {
  return useQuery({
    queryKey: approvalKeys.refundDetail(id ?? ""),
    queryFn: () => api.get<Refund>(`/api/refunds/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateRefundMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RefundCreate) => api.post<Refund>("/api/refunds", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.refunds });
      void queryClient.invalidateQueries({ queryKey: ["sales"] });
    },
  });
}

export function useApproveRefundMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload?: RefundDecision }) =>
      api.post<RefundResult>(`/api/refunds/${id}/approve`, payload ?? {}),
    onSuccess: () => {
      invalidateAfterDecision((key) => {
        void queryClient.invalidateQueries({ queryKey: key });
      });
    },
  });
}

export function useRejectRefundMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload?: RefundDecision }) =>
      api.post<Refund>(`/api/refunds/${id}/reject`, payload ?? {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.refunds });
      void queryClient.invalidateQueries({ queryKey: ["sales"] });
    },
  });
}

// -------------------------------------------------------------------------
// Үнийн өөрчлөлт
// -------------------------------------------------------------------------

export function usePriceChanges(params?: ApprovalListParams) {
  return useQuery({
    queryKey: approvalKeys.priceChangeList(params),
    queryFn: () => api.get<Paged<PriceChange>>("/api/price-changes", { params: { ...params } }),
  });
}

export function useCreatePriceChangeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PriceChangeCreate) => api.post<PriceChange>("/api/price-changes", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.priceChanges });
    },
  });
}

export function useApprovePriceChangeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload?: PriceChangeDecision }) =>
      api.post<PriceChange>(`/api/price-changes/${id}/approve`, payload ?? {}),
    onSuccess: () => {
      invalidateAfterDecision((key) => {
        void queryClient.invalidateQueries({ queryKey: key });
      });
    },
  });
}

export function useRejectPriceChangeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload?: PriceChangeDecision }) =>
      api.post<PriceChange>(`/api/price-changes/${id}/reject`, payload ?? {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: approvalKeys.priceChanges });
    },
  });
}
