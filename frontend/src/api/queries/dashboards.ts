import { useQuery } from "@tanstack/react-query";

import { api } from "../client";
import type { CashierDashboard, OwnerDashboard } from "../types";

export const dashboardKeys = {
  all: ["dashboard"] as const,
  cashier: () => ["dashboard", "cashier"] as const,
  owner: (from?: string, to?: string) => ["dashboard", "owner", from ?? "", to ?? ""] as const,
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
