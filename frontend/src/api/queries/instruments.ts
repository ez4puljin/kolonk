import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  CardBlockRequest,
  CardOperationResult,
  CardTopupRequest,
  CardTransaction,
  Paged,
  PrepaidCard,
  PrepaidCardCreate,
  UUID,
  Voucher,
  VoucherIssueRequest,
  VoucherSellRequest,
  VoucherValidateResult,
  VoucherVoidRequest,
} from "../types";
import { searchOnly, voucherParams } from "./_params";

export interface VoucherListParams {
  status?: string;
  q?: string;
  customer_id?: UUID;
  limit?: number;
  offset?: number;
}

export interface CardListParams {
  status?: string;
  q?: string;
  customer_id?: UUID;
  limit?: number;
  offset?: number;
}

export const instrumentKeys = {
  vouchers: ["vouchers"] as const,
  voucherList: (params?: VoucherListParams) => ["vouchers", "list", params ?? {}] as const,
  voucherValidate: (code: string) => ["vouchers", "validate", code] as const,
  cards: ["prepaid-cards"] as const,
  cardList: (params?: CardListParams) => ["prepaid-cards", "list", params ?? {}] as const,
  cardDetail: (id: UUID) => ["prepaid-cards", "detail", id] as const,
  cardTransactions: (id: UUID) => ["prepaid-cards", "transactions", id] as const,
};

// -------------------------------------------------------------------------
// Ваучер
// -------------------------------------------------------------------------

export function useVouchers(params?: VoucherListParams) {
  return useQuery({
    queryKey: instrumentKeys.voucherList(params),
    queryFn: () => api.get<Paged<Voucher>>("/api/vouchers", { params: voucherParams(params) }),
  });
}

/** Кассын төлбөрийн дэлгэц дээр ваучерын хүчинтэй эсэхийг шалгана. */
export function useValidateVoucher(code: string | null) {
  return useQuery({
    queryKey: instrumentKeys.voucherValidate(code ?? ""),
    queryFn: () => api.get<VoucherValidateResult>(`/api/vouchers/validate/${encodeURIComponent(code ?? "")}`),
    enabled: Boolean(code && code.length >= 4),
    retry: false,
  });
}

export function useIssueVouchersMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: VoucherIssueRequest) => api.post<Paged<Voucher>>("/api/vouchers/issue-batch", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: instrumentKeys.vouchers });
    },
  });
}

export function useSellVoucherMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: VoucherSellRequest }) =>
      api.post<Voucher>(`/api/vouchers/${id}/sell`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: instrumentKeys.vouchers });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}

export function useVoidVoucherMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: VoucherVoidRequest }) =>
      api.post<Voucher>(`/api/vouchers/${id}/void`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: instrumentKeys.vouchers });
    },
  });
}

// -------------------------------------------------------------------------
// Урьдчилсан төлбөрт карт
// -------------------------------------------------------------------------

export function usePrepaidCards(params?: CardListParams) {
  return useQuery({
    queryKey: instrumentKeys.cardList(params),
    queryFn: () => api.get<Paged<PrepaidCard>>("/api/prepaid-cards", { params: searchOnly(params) }),
  });
}

export function usePrepaidCard(id: UUID | null | undefined) {
  return useQuery({
    queryKey: instrumentKeys.cardDetail(id ?? ""),
    queryFn: () => api.get<PrepaidCard>(`/api/prepaid-cards/${id}`),
    enabled: Boolean(id),
  });
}

export function useCardTransactions(id: UUID | null | undefined) {
  return useQuery({
    queryKey: instrumentKeys.cardTransactions(id ?? ""),
    queryFn: () => api.get<Paged<CardTransaction>>(`/api/prepaid-cards/${id}/transactions`),
    enabled: Boolean(id),
  });
}

export function useCreateCardMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PrepaidCardCreate) =>
      api.post<CardOperationResult>("/api/prepaid-cards", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: instrumentKeys.cards });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}

export function useTopupCardMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: CardTopupRequest }) =>
      api.post<CardOperationResult>(`/api/prepaid-cards/${id}/topup`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: instrumentKeys.cards });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}

export function useBlockCardMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: CardBlockRequest }) =>
      api.post<PrepaidCard>(`/api/prepaid-cards/${id}/block`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: instrumentKeys.cards });
    },
  });
}
