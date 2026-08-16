import { useQuery } from "@tanstack/react-query";

import { api } from "../client";
import type {
  InventoryFilterOptions,
  InventoryReport,
  InventoryReportParams,
} from "../types";
import { clean } from "./_params";

export const inventoryReportKeys = {
  options: ["inventory-report", "options"] as const,
  report: (params: InventoryReportParams) => ["inventory-report", params] as const,
};

/** Шүүлтийн цонхны бүх сонголт — нэг дуудлагаар. */
export function useInventoryReportOptions() {
  return useQuery({
    queryKey: inventoryReportKeys.options,
    queryFn: () => api.get<InventoryFilterOptions>("/api/inventory-report/options"),
    staleTime: 5 * 60 * 1000,
  });
}

/** `enabled=false` үед тайлан татахгүй — хэрэглэгч "Тайлан авах" дарах хүртэл. */
export function useInventoryReport(params: InventoryReportParams | null) {
  return useQuery({
    queryKey: inventoryReportKeys.report(params ?? ({} as InventoryReportParams)),
    queryFn: () =>
      api.get<InventoryReport>("/api/inventory-report", { params: clean(params ?? undefined) }),
    enabled: Boolean(params?.date_from && params?.date_to),
  });
}

/** Excel татах — шүүлтийн параметрүүд тайлантай ижил. */
export function downloadInventoryReport(params: InventoryReportParams): Promise<void> {
  return api.download(
    "/api/inventory-report.xlsx",
    clean(params),
    `Бараа_материал_${params.date_from}_${params.date_to}.xlsx`,
  );
}
