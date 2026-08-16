import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  BulkConversionInput,
  BulkConversionResult,
  InventoryAdjustment,
  InventoryRow,
  InventoryTransaction,
  Paged,
  ProductSaleMode,
  UUID,
} from "../types";
import { searchIsActive } from "./_params";

export interface InventoryListParams {
  q?: string;
  category_id?: UUID;
  branch_id?: UUID;
  low_stock?: boolean;
  sale_mode?: ProductSaleMode;
  limit?: number;
  offset?: number;
}

export interface InventoryTxParams {
  product_id?: UUID;
  tx_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const inventoryKeys = {
  all: ["inventory"] as const,
  list: (params?: InventoryListParams) => ["inventory", "list", params ?? {}] as const,
  transactions: (params?: InventoryTxParams) => ["inventory", "transactions", params ?? {}] as const,
};

export function useInventory(params?: InventoryListParams) {
  return useQuery({
    queryKey: inventoryKeys.list(params),
    queryFn: () => api.get<Paged<InventoryRow>>("/api/inventory", { params: searchIsActive(params) }),
    staleTime: 30_000,
  });
}

export function useInventoryTransactions(params?: InventoryTxParams) {
  return useQuery({
    queryKey: inventoryKeys.transactions(params),
    queryFn: () =>
      api.get<Paged<InventoryTransaction>>("/api/inventory/transactions", { params: { ...params } }),
  });
}

export function useAdjustInventoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InventoryAdjustment) =>
      api.post<InventoryRow>("/api/inventory/adjustments", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}

/** Задлан хөрвүүлэлт — 1 ширхэг → `bulk_factor` нэгж грам бүтээгдэхүүн. */
export function useConvertToBulkMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BulkConversionInput) =>
      api.post<BulkConversionResult>("/api/inventory/conversions", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}
