import { useQuery } from "@tanstack/react-query";

import { api } from "../client";
import type { FuelReport, Paged, SalesReport, ShiftSummary } from "../types";

export type SalesGroupBy = "day" | "fuel" | "cashier" | "tender" | "category" | "product";

export interface ReportRange {
  date_from: string;
  date_to: string;
}

export interface SalesReportParams extends ReportRange {
  group_by?: SalesGroupBy;
  shift_id?: string;
  cashier_id?: string;
}

export const reportKeys = {
  all: ["reports"] as const,
  sales: (params: SalesReportParams) => ["reports", "sales", params] as const,
  fuel: (params: ReportRange) => ["reports", "fuel", params] as const,
  shifts: (params: ReportRange) => ["reports", "shifts", params] as const,
};

export function useSalesReport(params: SalesReportParams, enabled = true) {
  return useQuery({
    queryKey: reportKeys.sales(params),
    queryFn: () => api.get<SalesReport>("/api/reports/sales", { params: { ...params } }),
    enabled: enabled && Boolean(params.date_from && params.date_to),
  });
}

export function useFuelReport(params: ReportRange, enabled = true) {
  return useQuery({
    queryKey: reportKeys.fuel(params),
    queryFn: () => api.get<FuelReport>("/api/reports/fuel", { params: { ...params } }),
    enabled: enabled && Boolean(params.date_from && params.date_to),
  });
}

export function useShiftsReport(params: ReportRange, enabled = true) {
  return useQuery({
    queryKey: reportKeys.shifts(params),
    queryFn: () => api.get<Paged<ShiftSummary>>("/api/shifts", { params: { ...params } }),
    enabled: enabled && Boolean(params.date_from && params.date_to),
  });
}

/** Борлуулалтын тайланг Excel-ээр татах. */
export function downloadSalesReport(params: SalesReportParams): Promise<void> {
  return api.download("/api/reports/sales.xlsx", { ...params }, "Борлуулалтын-тайлан.xlsx");
}

/** Шатахууны тайланг Excel-ээр татах. */
export function downloadFuelReport(params: ReportRange): Promise<void> {
  return api.download("/api/reports/fuel.xlsx", { ...params }, "Шатахууны-тайлан.xlsx");
}
