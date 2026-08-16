import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  AuditLog,
  BackupDirectory,
  BackupFile,
  BackupResult,
  EbarimtQueueRow,
  JsonValue,
  OkResponse,
  Paged,
  Setting,
  SettingsMap,
  UUID,
} from "../types";

export interface AuditLogParams {
  user_id?: UUID;
  action?: string;
  entity_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface EbarimtQueueParams {
  status?: string;
  limit?: number;
  offset?: number;
}

export const systemKeys = {
  settings: () => ["settings"] as const,
  auditLogs: (params?: AuditLogParams) => ["audit-logs", params ?? {}] as const,
  ebarimt: (params?: EbarimtQueueParams) => ["ebarimt", "queue", params ?? {}] as const,
  backups: () => ["backups"] as const,
};

// -------------------------------------------------------------------------
// Тохиргоо
// -------------------------------------------------------------------------

export function useSettings(enabled = true) {
  return useQuery({
    queryKey: systemKeys.settings(),
    queryFn: () => api.get<SettingsMap>("/api/settings"),
    enabled,
    staleTime: 300_000,
  });
}

export function useUpdateSettingMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: JsonValue }) =>
      api.put<Setting>(`/api/settings/${encodeURIComponent(key)}`, { value }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: systemKeys.settings() });
    },
  });
}

// -------------------------------------------------------------------------
// Аудит
// -------------------------------------------------------------------------

export function useAuditLogs(params?: AuditLogParams) {
  return useQuery({
    queryKey: systemKeys.auditLogs(params),
    queryFn: () => api.get<Paged<AuditLog>>("/api/audit-logs", { params: { ...params } }),
  });
}

// -------------------------------------------------------------------------
// И-баримт
// -------------------------------------------------------------------------

export function useEbarimtQueue(params?: EbarimtQueueParams) {
  return useQuery({
    queryKey: systemKeys.ebarimt(params),
    queryFn: () => api.get<Paged<EbarimtQueueRow>>("/api/ebarimt/queue", { params: { ...params } }),
    refetchInterval: 60_000,
  });
}

export function useRetryEbarimtMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.post<EbarimtQueueRow>(`/api/ebarimt/queue/${id}/retry`, {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ebarimt"] });
      void queryClient.invalidateQueries({ queryKey: ["sales"] });
    },
  });
}

// -------------------------------------------------------------------------
// Нөөцлөлт
// -------------------------------------------------------------------------

export function useBackups(enabled = true) {
  return useQuery({
    queryKey: systemKeys.backups(),
    queryFn: () => api.get<Paged<BackupFile>>("/api/backups"),
    enabled,
  });
}

export function useCreateBackupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<BackupResult>("/api/backups", {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: systemKeys.backups() });
    },
  });
}

export function useRestoreBackupMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, confirm }: { name: string; confirm: string }) =>
      api.post<OkResponse>(`/api/backups/${encodeURIComponent(name)}/restore`, { confirm }),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

/** Нөөцлөлт хадгалах хавтас — унших. */
export function useBackupDirectory(enabled = true) {
  return useQuery({
    queryKey: [...systemKeys.backups(), "directory"],
    queryFn: () => api.get<BackupDirectory>("/api/backups/directory"),
    enabled,
  });
}

/** Хавтас солих — сервер бичих эрхийг шалгаж байж хадгална. */
export function useSetBackupDirectoryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (directory: string) =>
      api.put<BackupDirectory>("/api/backups/directory", { directory }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: systemKeys.backups() });
      void queryClient.invalidateQueries({ queryKey: systemKeys.settings() });
    },
  });
}

export function downloadBackup(name: string): Promise<void> {
  return api.download(`/api/backups/${encodeURIComponent(name)}/download`, undefined, name);
}
