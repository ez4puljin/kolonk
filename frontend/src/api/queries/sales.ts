import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  Paged,
  ReceiptPayload,
  Sale,
  SaleCreate,
  SaleCreatedResponse,
  SaleRow,
  UUID,
} from "../types";

export interface SaleListParams {
  shift_id?: UUID;
  cashier_id?: UUID;
  customer_id?: UUID;
  status?: string;
  sale_type?: string;
  method?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export const saleKeys = {
  all: ["sales"] as const,
  list: (params?: SaleListParams) => ["sales", "list", params ?? {}] as const,
  detail: (id: UUID) => ["sales", "detail", id] as const,
  receipt: (id: UUID) => ["sales", "receipt", id] as const,
};

export function useSales(params?: SaleListParams) {
  return useQuery({
    queryKey: saleKeys.list(params),
    queryFn: () => api.get<Paged<SaleRow>>("/api/sales", { params: { ...params } }),
  });
}

export function useSale(id: UUID | null | undefined) {
  return useQuery({
    queryKey: saleKeys.detail(id ?? ""),
    queryFn: () => api.get<Sale>(`/api/sales/${id}`),
    enabled: Boolean(id),
  });
}

export function useSaleReceipt(id: UUID | null | undefined, enabled = true) {
  return useQuery({
    queryKey: saleKeys.receipt(id ?? ""),
    queryFn: () => api.get<ReceiptPayload>(`/api/sales/${id}/receipt`),
    enabled: Boolean(id) && enabled,
  });
}

/** Борлуулалт хаах — хариуд нь борлуулалт + хэвлэх баримт ирнэ. */
export function useCreateSaleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaleCreate) => api.post<SaleCreatedResponse>("/api/sales", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: saleKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["shifts"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["tanks"] });
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["pumps"] });
    },
  });
}
