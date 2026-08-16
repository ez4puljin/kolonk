import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  ArInvoice,
  ArPaymentCreate,
  ArPaymentResult,
  Contract,
  ContractCreate,
  ContractStatement,
  ContractUpdate,
  Customer,
  CustomerCreate,
  CustomerUpdate,
  Paged,
  UUID,
} from "../types";
import { searchActiveOnly, searchOnly } from "./_params";

export interface CustomerListParams {
  q?: string;
  type?: string;
  province?: string;
  district?: string;
  created_from?: string;
  created_to?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export interface ContractListParams {
  customer_id?: UUID;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface ArInvoiceListParams {
  customer_id?: UUID;
  contract_id?: UUID;
  status?: string;
  limit?: number;
  offset?: number;
}

export const partnerKeys = {
  customers: ["customers"] as const,
  customerList: (params?: CustomerListParams) => ["customers", "list", params ?? {}] as const,
  customerDetail: (id: UUID) => ["customers", "detail", id] as const,
  contracts: ["contracts"] as const,
  contractList: (params?: ContractListParams) => ["contracts", "list", params ?? {}] as const,
  contractDetail: (id: UUID) => ["contracts", "detail", id] as const,
  statement: (id: UUID, from?: string, to?: string) =>
    ["contracts", "statement", id, from ?? "", to ?? ""] as const,
  arInvoices: ["ar-invoices"] as const,
  arInvoiceList: (params?: ArInvoiceListParams) => ["ar-invoices", "list", params ?? {}] as const,
};

// -------------------------------------------------------------------------
// Харилцагч
// -------------------------------------------------------------------------

export function useCustomers(params?: CustomerListParams) {
  return useQuery({
    queryKey: partnerKeys.customerList(params),
    queryFn: () => api.get<Paged<Customer>>("/api/customers", { params: searchActiveOnly(params) }),
    staleTime: 60_000,
  });
}

/** Гэрээний сканнердсан PDF хавсаргана. */
export function useUploadContractFileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, file }: { id: UUID; file: File }) =>
      api.upload<Customer>(`/api/customers/${id}/contract-file`, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useDeleteContractFileMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<Customer>(`/api/customers/${id}/contract-file`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useCustomer(id: UUID | null | undefined) {
  return useQuery({
    queryKey: partnerKeys.customerDetail(id ?? ""),
    queryFn: () => api.get<Customer>(`/api/customers/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateCustomerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CustomerCreate) => api.post<Customer>("/api/customers", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: partnerKeys.customers });
    },
  });
}

export function useUpdateCustomerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: CustomerUpdate }) =>
      api.patch<Customer>(`/api/customers/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: partnerKeys.customers });
    },
  });
}

// -------------------------------------------------------------------------
// Гэрээ
// -------------------------------------------------------------------------

export function useContracts(params?: ContractListParams) {
  return useQuery({
    queryKey: partnerKeys.contractList(params),
    queryFn: () => api.get<Paged<Contract>>("/api/contracts", { params: searchOnly(params) }),
    staleTime: 60_000,
  });
}

export function useContract(id: UUID | null | undefined) {
  return useQuery({
    queryKey: partnerKeys.contractDetail(id ?? ""),
    queryFn: () => api.get<Contract>(`/api/contracts/${id}`),
    enabled: Boolean(id),
  });
}

export function useContractStatement(id: UUID | null | undefined, dateFrom?: string, dateTo?: string) {
  return useQuery({
    queryKey: partnerKeys.statement(id ?? "", dateFrom, dateTo),
    queryFn: () =>
      api.get<ContractStatement>(`/api/contracts/${id}/statement`, {
        params: { date_from: dateFrom, date_to: dateTo },
      }),
    enabled: Boolean(id),
  });
}

export function useCreateContractMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ContractCreate) => api.post<Contract>("/api/contracts", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: partnerKeys.contracts });
      void queryClient.invalidateQueries({ queryKey: partnerKeys.customers });
    },
  });
}

export function useUpdateContractMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ContractUpdate }) =>
      api.patch<Contract>(`/api/contracts/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: partnerKeys.contracts });
      void queryClient.invalidateQueries({ queryKey: partnerKeys.customers });
    },
  });
}

// -------------------------------------------------------------------------
// Авлагын нэхэмжлэх / төлбөр
// -------------------------------------------------------------------------

export function useArInvoices(params?: ArInvoiceListParams) {
  return useQuery({
    queryKey: partnerKeys.arInvoiceList(params),
    queryFn: () => api.get<Paged<ArInvoice>>("/api/ar-invoices", { params: { ...params } }),
  });
}

export function useGenerateArInvoicesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      contractId,
      periodStart,
      periodEnd,
    }: {
      contractId: UUID;
      periodStart: string;
      periodEnd: string;
    }) =>
      api.post<ArInvoice>(`/api/contracts/${contractId}/invoices/generate`, {
        period_start: periodStart,
        period_end: periodEnd,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: partnerKeys.arInvoices });
      void queryClient.invalidateQueries({ queryKey: partnerKeys.contracts });
    },
  });
}

export function useCreateArPaymentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ArPaymentCreate) => api.post<ArPaymentResult>("/api/ar-payments", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: partnerKeys.arInvoices });
      void queryClient.invalidateQueries({ queryKey: partnerKeys.contracts });
      void queryClient.invalidateQueries({ queryKey: partnerKeys.customers });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
    },
  });
}
