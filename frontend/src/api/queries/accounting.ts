import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  Account,
  ApInvoice,
  ApPaymentCreate,
  ApPaymentResult,
  BalanceSheet,
  CashFlow,
  IncomeStatement,
  IntegrityCheck,
  InventoryValuation,
  JournalEntry,
  ManualEntryCreate,
  Paged,
  Settlement,
  SettlementCreate,
  TrialBalance,
  UUID,
} from "../types";

export interface JournalParams {
  date_from?: string;
  date_to?: string;
  account_code?: string;
  source_type?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
}

export interface ApInvoiceParams {
  status?: string;
  supplier_id?: UUID;
  limit?: number;
  offset?: number;
}

export const accountingKeys = {
  all: ["accounting"] as const,
  accounts: (postableOnly?: boolean) => ["accounting", "accounts", postableOnly ?? false] as const,
  journal: (params?: JournalParams) => ["accounting", "journal", params ?? {}] as const,
  entry: (id: UUID) => ["accounting", "journal", "entry", id] as const,
  trialBalance: (asOf?: string) => ["accounting", "trial-balance", asOf ?? ""] as const,
  pnl: (from: string, to: string) => ["accounting", "pnl", from, to] as const,
  balanceSheet: (asOf?: string) => ["accounting", "balance-sheet", asOf ?? ""] as const,
  cashFlow: (from: string, to: string) => ["accounting", "cash-flow", from, to] as const,
  valuation: () => ["accounting", "inventory-valuation"] as const,
  integrity: () => ["accounting", "integrity"] as const,
  apInvoices: (params?: ApInvoiceParams) => ["ap-invoices", "list", params ?? {}] as const,
};

export function useAccounts(postableOnly = false) {
  return useQuery({
    queryKey: accountingKeys.accounts(postableOnly),
    queryFn: () => api.get<Account[]>("/api/accounting/accounts", { params: { postable_only: postableOnly } }),
    staleTime: 600_000,
  });
}

export function useJournal(params?: JournalParams) {
  return useQuery({
    queryKey: accountingKeys.journal(params),
    queryFn: () => api.get<Paged<JournalEntry>>("/api/accounting/journal", { params: { ...params } }),
  });
}

export function useJournalEntry(id: UUID | null | undefined) {
  return useQuery({
    queryKey: accountingKeys.entry(id ?? ""),
    queryFn: () => api.get<JournalEntry>(`/api/accounting/journal/${id}`),
    enabled: Boolean(id),
  });
}

export function useTrialBalance(asOf?: string) {
  return useQuery({
    queryKey: accountingKeys.trialBalance(asOf),
    queryFn: () => api.get<TrialBalance>("/api/accounting/trial-balance", { params: { as_of: asOf } }),
  });
}

export function useIncomeStatement(dateFrom: string, dateTo: string, enabled = true) {
  return useQuery({
    queryKey: accountingKeys.pnl(dateFrom, dateTo),
    queryFn: () =>
      api.get<IncomeStatement>("/api/accounting/statements/pnl", {
        params: { date_from: dateFrom, date_to: dateTo },
      }),
    enabled: enabled && Boolean(dateFrom && dateTo),
  });
}

export function useBalanceSheet(asOf?: string) {
  return useQuery({
    queryKey: accountingKeys.balanceSheet(asOf),
    queryFn: () =>
      api.get<BalanceSheet>("/api/accounting/statements/balance-sheet", { params: { as_of: asOf } }),
  });
}

export function useCashFlow(dateFrom: string, dateTo: string, enabled = true) {
  return useQuery({
    queryKey: accountingKeys.cashFlow(dateFrom, dateTo),
    queryFn: () =>
      api.get<CashFlow>("/api/accounting/statements/cash-flow", {
        params: { date_from: dateFrom, date_to: dateTo },
      }),
    enabled: enabled && Boolean(dateFrom && dateTo),
  });
}

export function useInventoryValuation() {
  return useQuery({
    queryKey: accountingKeys.valuation(),
    queryFn: () => api.get<InventoryValuation>("/api/accounting/statements/inventory-valuation"),
  });
}

export function useIntegrityChecks() {
  return useQuery({
    queryKey: accountingKeys.integrity(),
    queryFn: () => api.get<IntegrityCheck[]>("/api/accounting/integrity"),
  });
}

export function useCreateManualEntryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ManualEntryCreate) =>
      api.post<JournalEntry>("/api/accounting/manual-entries", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountingKeys.all });
    },
  });
}

export function useCreateSettlementMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SettlementCreate) =>
      api.post<Settlement>("/api/accounting/settlements", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: accountingKeys.all });
    },
  });
}

// -------------------------------------------------------------------------
// Нийлүүлэгчийн өглөг
// -------------------------------------------------------------------------

export function useApInvoices(params?: ApInvoiceParams) {
  return useQuery({
    queryKey: accountingKeys.apInvoices(params),
    queryFn: () => api.get<Paged<ApInvoice>>("/api/ap-invoices", { params: { ...params } }),
  });
}

export function useCreateApPaymentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ApPaymentCreate) => api.post<ApPaymentResult>("/api/ap-payments", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ap-invoices"] });
      void queryClient.invalidateQueries({ queryKey: accountingKeys.all });
    },
  });
}
