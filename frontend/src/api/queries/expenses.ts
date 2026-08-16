import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  Expense,
  ExpenseCategory,
  ExpenseCreate,
  ExpenseListResult,
  ExpensePaymentMethod,
} from "../types";
import { clean } from "./_params";

export interface ExpenseListParams {
  date_from?: string;
  date_to?: string;
  account_code?: string;
  payment_method?: string;
  limit?: number;
  offset?: number;
}

export const expenseKeys = {
  all: ["expenses"] as const,
  list: (params?: ExpenseListParams) => ["expenses", "list", params ?? {}] as const,
  categories: ["expenses", "categories"] as const,
  methods: ["expenses", "methods"] as const,
};

/** Зардал бүртгэх боломжтой данснууд (том плиткууд). */
export function useExpenseCategories() {
  return useQuery({
    queryKey: expenseKeys.categories,
    queryFn: () => api.get<ExpenseCategory[]>("/api/expense-categories"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useExpensePaymentMethods() {
  return useQuery({
    queryKey: expenseKeys.methods,
    queryFn: () => api.get<ExpensePaymentMethod[]>("/api/expense-payment-methods"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useExpenses(params?: ExpenseListParams) {
  return useQuery({
    queryKey: expenseKeys.list(params),
    queryFn: () => api.get<ExpenseListResult>("/api/expenses", { params: clean(params) }),
  });
}

export function useCreateExpenseMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExpenseCreate) => api.post<Expense>("/api/expenses", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: expenseKeys.all });
      // Зардал нь ерөнхий дэвтэр, ээлжийн касс, самбарын тоонд шууд нөлөөлнө.
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
      void queryClient.invalidateQueries({ queryKey: ["shift"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
}
