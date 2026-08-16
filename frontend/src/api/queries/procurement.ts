import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  FuelReceipt,
  FuelReceiptCreate,
  Paged,
  Purchase,
  PurchaseCreate,
  Supplier,
  SupplierCreate,
  SupplierUpdate,
  UUID,
} from "../types";
import { searchIsActive } from "./_params";

export interface SupplierListParams {
  q?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export interface DocumentListParams {
  supplier_id?: UUID;
  status?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const procurementKeys = {
  suppliers: ["suppliers"] as const,
  supplierList: (params?: SupplierListParams) => ["suppliers", "list", params ?? {}] as const,
  fuelReceipts: ["fuel-receipts"] as const,
  fuelReceiptList: (params?: DocumentListParams) => ["fuel-receipts", "list", params ?? {}] as const,
  fuelReceiptDetail: (id: UUID) => ["fuel-receipts", "detail", id] as const,
  purchases: ["purchases"] as const,
  purchaseList: (params?: DocumentListParams) => ["purchases", "list", params ?? {}] as const,
  purchaseDetail: (id: UUID) => ["purchases", "detail", id] as const,
};

// -------------------------------------------------------------------------
// Нийлүүлэгч
// -------------------------------------------------------------------------

export function useSuppliers(params?: SupplierListParams) {
  return useQuery({
    queryKey: procurementKeys.supplierList(params),
    queryFn: () => api.get<Paged<Supplier>>("/api/suppliers", { params: searchIsActive(params) }),
    staleTime: 120_000,
  });
}

export function useCreateSupplierMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SupplierCreate) => api.post<Supplier>("/api/suppliers", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procurementKeys.suppliers });
    },
  });
}

export function useUpdateSupplierMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: SupplierUpdate }) =>
      api.patch<Supplier>(`/api/suppliers/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procurementKeys.suppliers });
    },
  });
}

// -------------------------------------------------------------------------
// Шатахуун таталт
// -------------------------------------------------------------------------

export function useFuelReceipts(params?: DocumentListParams) {
  return useQuery({
    queryKey: procurementKeys.fuelReceiptList(params),
    queryFn: () => api.get<Paged<FuelReceipt>>("/api/fuel-receipts", { params: { ...params } }),
  });
}

export function useFuelReceipt(id: UUID | null | undefined) {
  return useQuery({
    queryKey: procurementKeys.fuelReceiptDetail(id ?? ""),
    queryFn: () => api.get<FuelReceipt>(`/api/fuel-receipts/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateFuelReceiptMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FuelReceiptCreate) => api.post<FuelReceipt>("/api/fuel-receipts", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procurementKeys.fuelReceipts });
    },
  });
}

export function usePostFuelReceiptMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<FuelReceipt>(`/api/fuel-receipts/${id}/post`, {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procurementKeys.fuelReceipts });
      void queryClient.invalidateQueries({ queryKey: ["tanks"] });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
      void queryClient.invalidateQueries({ queryKey: ["ap-invoices"] });
    },
  });
}

// -------------------------------------------------------------------------
// Барааны худалдан авалт
// -------------------------------------------------------------------------

export function usePurchases(params?: DocumentListParams) {
  return useQuery({
    queryKey: procurementKeys.purchaseList(params),
    queryFn: () => api.get<Paged<Purchase>>("/api/purchases", { params: { ...params } }),
  });
}

export function usePurchase(id: UUID | null | undefined) {
  return useQuery({
    queryKey: procurementKeys.purchaseDetail(id ?? ""),
    queryFn: () => api.get<Purchase>(`/api/purchases/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreatePurchaseMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PurchaseCreate) => api.post<Purchase>("/api/purchases", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procurementKeys.purchases });
    },
  });
}

export function usePostPurchaseMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<Purchase>(`/api/purchases/${id}/post`, {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: procurementKeys.purchases });
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
      void queryClient.invalidateQueries({ queryKey: ["ap-invoices"] });
    },
  });
}
