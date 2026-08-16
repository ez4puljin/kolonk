import { useQuery } from "@tanstack/react-query";

import { api } from "../client";
import type {
  ReportCenterOptions,
  ReportDrillResult,
  ReportCenterParams,
  ReportCenterResult,
  TransactionDetail,
} from "../types";

export const reportCenterKeys = {
  options: ["report-center", "options"] as const,
  run: (p: ReportCenterParams) => ["report-center", "run", p] as const,
  transaction: (type: string, id: string) => ["transaction", type, id] as const,
  drill: (p: ReportCenterParams, path: string[]) =>
    ["report-center", "drill", p, path] as const,
};

/**
 * Олон утгатай шүүлтийг давтагдах query параметр болгоно
 * (`?account_code=1101&account_code=1102`). Хоосон массивыг огт илгээхгүй —
 * сервер талд "Бүгд" гэсэн утгатай.
 */
function toQuery(params: ReportCenterParams): string {
  const search = new URLSearchParams();
  search.set("report", params.report);
  search.set("date_from", params.date_from);
  search.set("date_to", params.date_to);
  if (params.include_details) search.set("include_details", "true");
  const lists: [string, string[] | undefined][] = [
    ["account_code", params.account_code],
    ["branch_id", params.branch_id],
    ["fuel_id", params.fuel_id],
    ["category_id", params.category_id],
    ["employee_id", params.employee_id],
    ["tx_type", params.tx_type],
    ["group_by", params.group_by],
  ];
  for (const [key, values] of lists) {
    for (const value of values ?? []) search.append(key, value);
  }
  return search.toString();
}

export function useReportCenterOptions() {
  return useQuery({
    queryKey: reportCenterKeys.options,
    queryFn: () => api.get<ReportCenterOptions>("/api/report-center/options"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useReportCenterRun(params: ReportCenterParams | null) {
  return useQuery({
    queryKey: reportCenterKeys.run(params ?? ({} as ReportCenterParams)),
    queryFn: () => api.get<ReportCenterResult>(`/api/report-center/run?${toQuery(params!)}`),
    enabled: Boolean(params?.date_from && params?.date_to),
  });
}

/** Задаргааны мөр дээр давхар товшиход дуудагдана. */
export function useTransactionDetail(sourceType: string | null, sourceId: string | null) {
  return useQuery({
    queryKey: reportCenterKeys.transaction(sourceType ?? "", sourceId ?? ""),
    queryFn: () => api.get<TransactionDetail>(`/api/transactions/${sourceType}/${sourceId}`),
    enabled: Boolean(sourceType && sourceId),
  });
}

export function downloadReportCenter(params: ReportCenterParams, filename: string): Promise<void> {
  return api.download(`/api/report-center/run.xlsx?${toQuery(params)}`, undefined, filename);
}

/**
 * Тайлангийн мөрийн задаргаа — мөр дээр давхар товшиход дуудагдана.
 * `path` нь тухайн мөрийн бүрэн зам; дээд түвшний мөр бол дэд бүх гүйлгээг авна.
 */
export function useReportDrill(params: ReportCenterParams | null, path: string[] | null) {
  return useQuery({
    queryKey: reportCenterKeys.drill(params ?? ({} as ReportCenterParams), path ?? []),
    queryFn: () => {
      const search = toQuery(params!);
      const extra = path!.map((p) => `path=${encodeURIComponent(p)}`).join("&");
      return api.get<ReportDrillResult>(
        `/api/report-center/drill?${search}${extra ? `&${extra}` : ""}`,
      );
    },
    enabled: Boolean(params && path && path.length > 0),
    staleTime: 60 * 1000,
  });
}
