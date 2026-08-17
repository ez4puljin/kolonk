import { useQuery } from "@tanstack/react-query";

import { api } from "../client";
import type {
  BranchShiftOverview,
  CashierDashboard,
  FuelTrend,
  OwnerDashboard,
  UUID,
} from "../types";

export const dashboardKeys = {
  all: ["dashboard"] as const,
  cashier: () => ["dashboard", "cashier"] as const,
  owner: (from?: string, to?: string) => ["dashboard", "owner", from ?? "", to ?? ""] as const,
  branchShifts: () => ["dashboard", "branch-shifts"] as const,
  fuelTrend: (days: number, branchId?: UUID | null) =>
    ["dashboard", "fuel-trend", days, branchId ?? ""] as const,
};

/** Түгээгч/менежерийн самбар — идэвхтэй ээлжийн шууд үзүүлэлт. */
export function useCashierDashboard(enabled = true) {
  return useQuery({
    queryKey: dashboardKeys.cashier(),
    queryFn: () => api.get<CashierDashboard>("/api/dashboards/cashier"),
    enabled,
    refetchInterval: 30_000,
  });
}

/** Салбар бүрийн нээлттэй түгээгчийн ээлж — хошууны милээр тооцсон явц. */
export function useBranchShifts(enabled = true) {
  return useQuery({
    queryKey: dashboardKeys.branchShifts(),
    queryFn: () => api.get<BranchShiftOverview[]>("/api/dashboards/branch-shifts"),
    enabled,
    refetchInterval: 60_000,
  });
}

/**
 * Салбар тус бүрийн сүүлийн хоногуудын түлшний зарлага.
 *
 * Түгээгчийн горимд борлуулалт зөвхөн өдрийн хаалтаар бүртгэгддэг тул
 * дүнг хошууны миль (тоолуурын заалт)-аас тооцно.
 */
export function useFuelTrend(days = 7, branchId?: UUID | null, enabled = true) {
  return useQuery({
    queryKey: dashboardKeys.fuelTrend(days, branchId),
    queryFn: () =>
      api.get<FuelTrend>("/api/dashboards/fuel-trend", {
        params: { days, branch_id: branchId ?? undefined },
      }),
    enabled,
    staleTime: 120_000,
  });
}

/** Эзний самбар — санхүү, нөөц, анхааруулга. */
export function useOwnerDashboard(dateFrom?: string, dateTo?: string, enabled = true) {
  return useQuery({
    queryKey: dashboardKeys.owner(dateFrom, dateTo),
    queryFn: () =>
      api.get<OwnerDashboard>("/api/dashboards/owner", {
        params: { date_from: dateFrom, date_to: dateTo },
      }),
    enabled,
    refetchInterval: 60_000,
  });
}
