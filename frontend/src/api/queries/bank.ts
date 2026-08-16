import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  BankAccount,
  BankAccountCreate,
  BankAccountList,
  BankAccountUpdate,
  BankStatement,
  BankStatementConfig,
  BankStatementConfigInput,
  BankStatementDetail,
  BankTransactionUpdate,
  Paged,
  PostAllResult,
  UUID,
} from "../types";

export const bankKeys = {
  accounts: ["bank-accounts"] as const,
  statements: (params?: unknown) => ["bank-statements", "list", params ?? {}] as const,
  statement: (id: UUID) => ["bank-statements", "detail", id] as const,
  config: ["bank-statements", "config"] as const,
};

/** Бүх зүйлийг сэргээх — хуулга бүртгэхэд төлбөр, зардал, журнал бүгд хөдөлнө. */
function invalidateAll(queryClient: ReturnType<typeof useQueryClient>): void {
  for (const key of [
    ["bank-accounts"],
    ["bank-statements"],
    ["expenses"],
    ["contracts"],
    ["customers"],
    ["accounting"],
    ["reports"],
  ]) {
    void queryClient.invalidateQueries({ queryKey: key });
  }
}

// --------------------------------------------------------------------------
// Харилцах данс
// --------------------------------------------------------------------------
export function useBankAccounts(params?: { active_only?: boolean }) {
  return useQuery({
    queryKey: [...bankKeys.accounts, params ?? {}],
    queryFn: () => api.get<BankAccountList>("/api/bank-accounts", { params: { ...params } }),
    staleTime: 60_000,
  });
}

export function useCreateBankAccountMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BankAccountCreate) => api.post<BankAccount>("/api/bank-accounts", payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useUpdateBankAccountMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: BankAccountUpdate }) =>
      api.patch<BankAccount>(`/api/bank-accounts/${id}`, payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useDeactivateBankAccountMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/bank-accounts/${id}`),
    onSuccess: () => invalidateAll(queryClient),
  });
}

// --------------------------------------------------------------------------
// Хуулга
// --------------------------------------------------------------------------
export interface StatementListParams {
  date_from?: string;
  date_to?: string;
}

export function useBankStatements(params?: StatementListParams) {
  return useQuery({
    queryKey: bankKeys.statements(params),
    queryFn: () =>
      api.get<Paged<BankStatement>>("/api/bank-statements", { params: { ...params } }),
  });
}

export function useBankStatement(id: UUID | null) {
  return useQuery({
    queryKey: bankKeys.statement(id ?? ""),
    queryFn: () => api.get<BankStatementDetail>(`/api/bank-statements/${id}`),
    enabled: Boolean(id),
  });
}

export function useStatementConfig() {
  return useQuery({
    queryKey: bankKeys.config,
    queryFn: () => api.get<BankStatementConfig>("/api/bank-statements/config"),
    staleTime: 60_000,
  });
}

export function useUpdateStatementConfigMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BankStatementConfigInput) =>
      api.put<BankStatementConfig>("/api/bank-statements/config", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: bankKeys.config });
    },
  });
}

/** Excel хуулга оруулах — `multipart/form-data`. */
export function useUploadStatementMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      api.upload<BankStatementDetail>("/api/bank-statements/upload", file),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useDeleteStatementMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/bank-statements/${id}`),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useSetStatementAccountMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, bankAccountId }: { id: UUID; bankAccountId: UUID | null }) =>
      api.put<BankStatementDetail>(`/api/bank-statements/${id}/bank-account`, {
        bank_account_id: bankAccountId,
      }),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/** Хуулгын нэг товчлол — бүгд дэлгэрэнгүйг буцаадаг тул нэг hook хангалттай. */
export function useStatementActionMutation(action: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: UUID; body?: unknown }) =>
      api.post<BankStatementDetail>(`/api/bank-statements/${id}/${action}`, body ?? {}),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function usePostAllMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<PostAllResult>(`/api/bank-statements/${id}/post-all`, {}),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useUpdateBankTransactionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      statementId,
      txnId,
      payload,
    }: {
      statementId: UUID;
      txnId: UUID;
      payload: BankTransactionUpdate;
    }) =>
      api.patch<BankStatementDetail>(
        `/api/bank-statements/${statementId}/transactions/${txnId}`,
        payload,
      ),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useTransactionActionMutation(action: "post" | "unpost") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ statementId, txnId }: { statementId: UUID; txnId: UUID }) =>
      api.post<BankStatementDetail>(
        `/api/bank-statements/${statementId}/transactions/${txnId}/${action}`,
        {},
      ),
    onSuccess: () => invalidateAll(queryClient),
  });
}
