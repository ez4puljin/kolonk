import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  CurrentShift,
  DailyCloseRequest,
  DailyClosingRow,
  DailyPreview,
  Paged,
  PriceMark,
  PriceMarkInput,
  ShiftAttachment,
  ShiftCloseRequest,
  ShiftOpenRequest,
  ShiftReport,
  ShiftSummary,
  TotalizerReadingInput,
  UUID,
} from "../types";
import { useAuthStore } from "../../stores/auth";
import { useShiftStore } from "../../stores/shift";

export interface ShiftListParams {
  date_from?: string;
  date_to?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export const shiftKeys = {
  all: ["shifts"] as const,
  current: () => ["shifts", "current"] as const,
  list: (params?: ShiftListParams) => ["shifts", "list", params ?? {}] as const,
  report: (id: UUID) => ["shifts", "report", id] as const,
};

/** Нээлттэй ээлж (байхгүй бол `null`). Store-той автоматаар синк болно. */
export function useCurrentShift(enabled = true) {
  const setFromSummary = useShiftStore((state) => state.setFromSummary);
  const setShift = useAuthStore((state) => state.setShift);

  return useQuery({
    queryKey: shiftKeys.current(),
    queryFn: async () => {
      const data = await api.get<CurrentShift | null>("/api/shifts/current");
      setFromSummary(data?.shift ?? null);
      setShift(Boolean(data), data?.shift.id ?? null, data?.shift.number ?? null);
      return data;
    },
    enabled,
    refetchInterval: 30_000,
  });
}

export function useShifts(params?: ShiftListParams, enabled = true) {
  return useQuery({
    queryKey: shiftKeys.list(params),
    queryFn: () => api.get<Paged<ShiftSummary>>("/api/shifts", { params: { ...params } }),
    enabled,
  });
}

export function useShiftReport(id: UUID | null | undefined) {
  return useQuery({
    queryKey: shiftKeys.report(id ?? ""),
    queryFn: () => api.get<ShiftReport>(`/api/shifts/${id}/report`),
    enabled: Boolean(id),
  });
}

export function useOpenShiftMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ShiftOpenRequest) => api.post<CurrentShift>("/api/shifts/open", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shiftKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["tanks"] });
      void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useCloseShiftMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: ShiftCloseRequest }) =>
      api.post<ShiftReport>(`/api/shifts/${id}/close`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shiftKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["tanks"] });
      void queryClient.invalidateQueries({ queryKey: ["accounting"] });
      void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

/** Ээлжийн тайланг Excel-ээр татна. */
export function downloadShiftReport(id: UUID, number: number | null): Promise<void> {
  return api.download(`/api/shifts/${id}/report.xlsx`, undefined, `Ээлж-${number ?? id}-тайлан.xlsx`);
}

// --------------------------------------------------------------------------
// Түгээгчийн өдрийн ээлж
// --------------------------------------------------------------------------

/** Ээлжид зураг хавсаргах (миль, кассын тоолол, settlement). */
export function useUploadShiftPhotoMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shiftId, kind, file }: { shiftId: UUID; kind: string; file: File }) =>
      api.upload<ShiftAttachment>(
        `/api/shifts/${shiftId}/attachments?kind=${encodeURIComponent(kind)}`,
        file,
      ),
    onSuccess: (_data, vars) => {
      void queryClient.invalidateQueries({ queryKey: ["shifts", "attachments", vars.shiftId] });
    },
  });
}

export function useShiftAttachments(shiftId: UUID | null) {
  return useQuery({
    queryKey: ["shifts", "attachments", shiftId ?? ""],
    queryFn: () => api.get<ShiftAttachment[]>(`/api/shifts/${shiftId}/attachments`),
    enabled: Boolean(shiftId),
  });
}

export function usePriceMarks(shiftId: UUID | null) {
  return useQuery({
    queryKey: ["shifts", "price-marks", shiftId ?? ""],
    queryFn: () => api.get<PriceMark[]>(`/api/shifts/${shiftId}/price-marks`),
    enabled: Boolean(shiftId),
  });
}

export function useAddPriceMarkMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shiftId, payload }: { shiftId: UUID; payload: PriceMarkInput }) =>
      api.post<PriceMark>(`/api/shifts/${shiftId}/price-marks`, payload),
    onSuccess: (_data, vars) => {
      void queryClient.invalidateQueries({ queryKey: ["shifts", "price-marks", vars.shiftId] });
    },
  });
}

/** Хаалтын өмнөх миль×үнэ тулгалт — юу ч бичихгүй. */
export function useDailyPreviewMutation() {
  return useMutation({
    mutationFn: ({
      shiftId,
      readings,
    }: {
      shiftId: UUID;
      readings: TotalizerReadingInput[];
    }) =>
      api.post<DailyPreview>(`/api/shifts/${shiftId}/daily-preview`, {
        totalizer_readings: readings,
      }),
  });
}

/** Өдөр бүрийн түгээгчийн тооцооны жагсаалт. */
export function useDailyClosings(params?: { date_from?: string; date_to?: string }) {
  return useQuery({
    queryKey: ["shifts", "daily-closings", params ?? {}],
    queryFn: () =>
      api.get<DailyClosingRow[]>("/api/shifts/daily-closings", { params: { ...params } }),
  });
}

export function useDailyCloseMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shiftId, payload }: { shiftId: UUID; payload: DailyCloseRequest }) =>
      api.post<ShiftReport>(`/api/shifts/${shiftId}/daily-close`, payload),
    onSuccess: () => {
      for (const key of [
        ["shifts"],
        ["dashboard"],
        ["tanks"],
        ["accounting"],
        ["contracts"],
        ["customers"],
        ["expenses"],
        ["products"],
        ["auth", "me"],
      ]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
}
