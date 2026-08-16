import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  AdvanceCreate,
  Employee,
  EmployeeAdvance,
  EmployeeCreate,
  EmployeeUpdate,
  Paged,
  PayrollLineUpdate,
  PayrollPayRequest,
  PayrollPeriod,
  PayrollPeriodRow,
  UUID,
} from "../types";
import { clean } from "./_params";

export const payrollKeys = {
  employees: ["employees"] as const,
  employeeList: (params?: object) => ["employees", "list", params ?? {}] as const,
  periods: ["payroll", "periods"] as const,
  period: (id: UUID) => ["payroll", "period", id] as const,
  advances: ["payroll", "advances"] as const,
};

/** Цалин, ажилтны өгөгдөл өөрчлөгдөхөд НББ болон самбарыг мөн шинэчилнэ. */
function invalidateAll(queryClient: ReturnType<typeof useQueryClient>): void {
  void queryClient.invalidateQueries({ queryKey: payrollKeys.employees });
  void queryClient.invalidateQueries({ queryKey: ["payroll"] });
  void queryClient.invalidateQueries({ queryKey: ["accounting"] });
  void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  void queryClient.invalidateQueries({ queryKey: ["shift"] });
}

// --------------------------------------------------------------------- //
// Ажилтан
// --------------------------------------------------------------------- //
export interface EmployeeListParams {
  active_only?: boolean;
  is_active?: boolean;
  search?: string;
  branch_id?: UUID;
  hired_from?: string;
  hired_to?: string;
  created_from?: string;
  created_to?: string;
}

export function useEmployees(params?: EmployeeListParams) {
  return useQuery({
    queryKey: payrollKeys.employeeList(params),
    queryFn: () => api.get<Paged<Employee>>("/api/employees", { params: clean(params) }),
  });
}

export function useCreateEmployeeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmployeeCreate) => api.post<Employee>("/api/employees", payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useUpdateEmployeeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: EmployeeUpdate & { id: UUID }) =>
      api.patch<Employee>(`/api/employees/${id}`, payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

// --------------------------------------------------------------------- //
// Цалингийн хугацаа
// --------------------------------------------------------------------- //
export function usePayrollPeriods() {
  return useQuery({
    queryKey: payrollKeys.periods,
    queryFn: () => api.get<Paged<PayrollPeriodRow>>("/api/payroll/periods"),
  });
}

export function usePayrollPeriod(id: UUID | null) {
  return useQuery({
    queryKey: payrollKeys.period(id ?? ("" as UUID)),
    queryFn: () => api.get<PayrollPeriod>(`/api/payroll/periods/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreatePeriodMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { year: number; month: number; employee_ids?: UUID[] | null }) =>
      api.post<PayrollPeriod>("/api/payroll/periods", payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useUpdatePayrollLineMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: PayrollLineUpdate & { id: UUID }) =>
      api.patch<PayrollPeriod>(`/api/payroll/lines/${id}`, payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/** Ажилтны бүртгэлтэй тааруулж дахин тооцоолно (шинэ ажилтан нэмэгдэнэ). */
export function useRecalculatePayrollMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) =>
      api.post<PayrollPeriod>(`/api/payroll/periods/${id}/recalculate`, {}),
    onSuccess: () => invalidateAll(queryClient),
  });
}

/** Ноорог тооцоог цуцална (батлагдсаныг цуцлах боломжгүй). */
export function useCancelPeriodMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<void>(`/api/payroll/periods/${id}`),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function useApprovePayrollMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<PayrollPeriod>(`/api/payroll/periods/${id}/approve`, {}),
    onSuccess: () => invalidateAll(queryClient),
  });
}

export function usePayPayrollMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: PayrollPayRequest & { id: UUID }) =>
      api.post<PayrollPeriod>(`/api/payroll/periods/${id}/pay`, payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}

// --------------------------------------------------------------------- //
// Урьдчилгаа
// --------------------------------------------------------------------- //
export function useAdvances(employeeId?: UUID | null) {
  return useQuery({
    queryKey: [...payrollKeys.advances, employeeId ?? "all"],
    queryFn: () =>
      api.get<Paged<EmployeeAdvance>>("/api/payroll/advances", {
        params: clean(employeeId ? { employee_id: employeeId } : undefined),
      }),
  });
}

export function useGiveAdvanceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdvanceCreate) =>
      api.post<EmployeeAdvance>("/api/payroll/advances", payload),
    onSuccess: () => invalidateAll(queryClient),
  });
}
