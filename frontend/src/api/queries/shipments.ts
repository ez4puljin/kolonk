import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  BranchSummary,
  FuelShipment,
  FuelShipmentCreate,
  FuelShipmentDetail,
  Paged,
  SettlementBalance,
  SettlementEntry,
  SettlementPaymentCreate,
  ShipmentDeliverGoodsRequest,
  ShipmentDeliverManyRequest,
  ShipmentDeliverRequest,
  ShipmentDeliveryRow,
  ShipmentGoodsDeliveryRow,
  ShipmentOutflow,
  ShipmentOutflowRequest,
  UUID,
} from "../types";

export interface ShipmentListParams {
  status?: string;
  supplier_id?: UUID;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface SettlementListParams {
  branch_id?: UUID;
  entry_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export const shipmentKeys = {
  all: ["fuel-shipments"] as const,
  list: (params?: ShipmentListParams) => ["fuel-shipments", "list", params ?? {}] as const,
  detail: (id: UUID) => ["fuel-shipments", "detail", id] as const,
  settlements: ["branch-settlements"] as const,
  settlementBalances: ["branch-settlements", "balances"] as const,
  settlementList: (params?: SettlementListParams) =>
    ["branch-settlements", "list", params ?? {}] as const,
  branchSummary: (dateFrom: string, dateTo: string) =>
    ["branch-summary", dateFrom, dateTo] as const,
};

// -------------------------------------------------------------------------
// Ачилт
// -------------------------------------------------------------------------

export function useFuelShipments(params?: ShipmentListParams) {
  return useQuery({
    queryKey: shipmentKeys.list(params),
    queryFn: () => api.get<Paged<FuelShipment>>("/api/fuel-shipments", { params: { ...params } }),
  });
}

export function useFuelShipment(id: UUID | null | undefined) {
  return useQuery({
    queryKey: shipmentKeys.detail(id ?? ""),
    queryFn: () => api.get<FuelShipmentDetail>(`/api/fuel-shipments/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateShipmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FuelShipmentCreate) =>
      api.post<FuelShipment>("/api/fuel-shipments", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shipmentKeys.all });
    },
  });
}

export function useUpdateShipmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: Partial<FuelShipmentCreate> }) =>
      api.patch<FuelShipment>(`/api/fuel-shipments/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shipmentKeys.all });
    },
  });
}

export function useDeleteShipmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/fuel-shipments/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shipmentKeys.all });
    },
  });
}

/** Буулгалтын дараа шинэчлэгдэх бүх зүйл: сав, нөөц, худалдан авалт, тооцоо. */
function invalidateAfterDelivery(queryClient: ReturnType<typeof useQueryClient>): void {
  void queryClient.invalidateQueries({ queryKey: shipmentKeys.all });
  void queryClient.invalidateQueries({ queryKey: ["fuel-receipts"] });
  void queryClient.invalidateQueries({ queryKey: ["tanks"] });
  void queryClient.invalidateQueries({ queryKey: ["products"] });
  void queryClient.invalidateQueries({ queryKey: ["inventory"] });
  void queryClient.invalidateQueries({ queryKey: ["purchases"] });
  void queryClient.invalidateQueries({ queryKey: shipmentKeys.settlements });
}

export function usePostShipmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<FuelShipment>(`/api/fuel-shipments/${id}/post`),
    // Бүртгэхэд хуваарилалтын төлөвлөгөө тэр дороо буулгагддаг тул сав,
    // нөөц ч өөрчлөгдөнө.
    onSuccess: () => invalidateAfterDelivery(queryClient),
  });
}

export function useShipmentDeliverMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ShipmentDeliverRequest }) =>
      api.post<ShipmentDeliveryRow>(`/api/fuel-shipments/${id}/deliver`, payload),
    onSuccess: () => invalidateAfterDelivery(queryClient),
  });
}

/** Нэг зогсолтоор олон саванд — салбар бүрийн саванд өөр хэмжээгээр. */
export function useShipmentDeliverManyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ShipmentDeliverManyRequest }) =>
      api.post<ShipmentDeliveryRow[]>(`/api/fuel-shipments/${id}/deliver-many`, payload),
    onSuccess: () => invalidateAfterDelivery(queryClient),
  });
}

/** Нэг салбарт бараа буулгах. */
export function useShipmentDeliverGoodsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ShipmentDeliverGoodsRequest }) =>
      api.post<ShipmentGoodsDeliveryRow[]>(`/api/fuel-shipments/${id}/deliver-goods`, payload),
    onSuccess: () => invalidateAfterDelivery(queryClient),
  });
}

export function useShipmentOutflowMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ShipmentOutflowRequest }) =>
      api.post<ShipmentOutflow>(`/api/fuel-shipments/${id}/outflow`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shipmentKeys.all });
    },
  });
}

export function useCloseShipmentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<FuelShipment>(`/api/fuel-shipments/${id}/close`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shipmentKeys.all });
    },
  });
}

// -------------------------------------------------------------------------
// Салбарын тооцоо
// -------------------------------------------------------------------------

export function useSettlementBalances() {
  return useQuery({
    queryKey: shipmentKeys.settlementBalances,
    queryFn: () => api.get<SettlementBalance[]>("/api/branch-settlements/balances"),
  });
}

export function useSettlementEntries(params?: SettlementListParams) {
  return useQuery({
    queryKey: shipmentKeys.settlementList(params),
    queryFn: () =>
      api.get<Paged<SettlementEntry>>("/api/branch-settlements", { params: { ...params } }),
  });
}

export function useSettlementPaymentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SettlementPaymentCreate) =>
      api.post<SettlementEntry>("/api/branch-settlements/payments", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shipmentKeys.settlements });
      void queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
    },
  });
}

// -------------------------------------------------------------------------
// Салбарын харьцуулсан тайлан
// -------------------------------------------------------------------------

export function useBranchSummary(dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: shipmentKeys.branchSummary(dateFrom, dateTo),
    queryFn: () =>
      api.get<BranchSummary>("/api/accounting/statements/branch-summary", {
        params: { date_from: dateFrom, date_to: dateTo },
      }),
  });
}
