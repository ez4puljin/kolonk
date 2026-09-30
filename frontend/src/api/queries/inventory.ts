import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  BranchTransferInput,
  BranchTransferResult,
  BulkConversionInput,
  BulkConversionResult,
  InventoryAdjustment,
  OpeningBalanceRequest,
  OpeningBalanceResult,
  OpeningFixInput,
  OpeningFixResult,
  OpeningRecord,
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

/** Салбар хоорондын шилжүүлэг — нийт нөөц хөдлөхгүй, өртөг хамт шилжинэ. */
export function useBranchTransferMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BranchTransferInput) =>
      api.post<BranchTransferResult>("/api/inventory/transfers", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
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

/**
 * Эхний үлдэгдэл — системд шилжих үеийн нөөцийг салбараар нэг дор тогтооно.
 *
 * Оруулсан тоо хэмжээ нь ЭЦСИЙН үлдэгдэл (нэмэгдэл биш) тул дахин
 * оруулахад давхардахгүй — зөвхөн зөрүүг нь хөдөлгөнө.
 */
export function useOpeningBalanceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OpeningBalanceRequest) =>
      api.post<OpeningBalanceResult>("/api/inventory/opening-balances", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}

/** Эхний үлдэгдлийн түүх — өмнө оруулсан бичлэгүүд (засахад). */
export function useOpeningRecords(params: { branch_id?: UUID; search?: string }, enabled = true) {
  return useQuery({
    queryKey: ["inventory", "openings", params],
    queryFn: () => api.get<OpeningRecord[]>("/api/inventory/openings", { params: { ...params } }),
    enabled,
  });
}

/** Засварын нөлөөг урьдчилан бодно — юу ч бичихгүй. */
export function useOpeningFixPreviewMutation() {
  return useMutation({
    mutationFn: ({ txId, payload }: { txId: UUID; payload: OpeningFixInput }) =>
      api.post<OpeningFixResult>(`/api/inventory/openings/${txId}/preview`, payload),
  });
}

/**
 * Эхний үлдэгдлийг засна — тэр мөчөөс хойших дундаж өртөг, борлуулалтын
 * өртөг, ашиг, журнал бүгд дахин бодогдоно.
 */
export function useOpeningFixMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ txId, payload }: { txId: UUID; payload: OpeningFixInput }) =>
      api.post<OpeningFixResult>(`/api/inventory/openings/${txId}/correct`, payload),
    onSuccess: () => {
      for (const key of [inventoryKeys.all, ["products"], ["accounting"], ["shifts"], ["sales"], ["reports"], ["dashboard"]]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
}
