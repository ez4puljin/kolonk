import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../client";
import type {
  OkResponse,
  Paged,
  PermissionGroupList,
  Role,
  User,
  UserCreate,
  UserUpdate,
  UUID,
} from "../types";

export interface UserListParams {
  is_active?: boolean;
  role_code?: string;
  branch_id?: UUID;
  q?: string;
  limit?: number;
  offset?: number;
}

export const userKeys = {
  all: ["users"] as const,
  list: (params?: UserListParams) => ["users", "list", params ?? {}] as const,
  roles: () => ["roles"] as const,
  permissions: () => ["permissions"] as const,
};

export function useUsers(params?: UserListParams) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () => api.get<Paged<User>>("/api/users", { params: { ...params } }),
  });
}

export function useRoles(enabled = true) {
  return useQuery({
    queryKey: userKeys.roles(),
    queryFn: () => api.get<Paged<Role>>("/api/roles"),
    enabled,
    staleTime: 300_000,
  });
}

export function usePermissionCatalog(enabled = true) {
  return useQuery({
    queryKey: userKeys.permissions(),
    queryFn: () => api.get<PermissionGroupList>("/api/permissions"),
    enabled,
    staleTime: 300_000,
  });
}

export function useCreateUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserCreate) => api.post<User>("/api/users", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userKeys.all });
      void queryClient.invalidateQueries({ queryKey: userKeys.roles() });
    },
  });
}

export function useUpdateUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: UUID; payload: UserUpdate }) =>
      api.patch<User>(`/api/users/${id}`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userKeys.all });
      void queryClient.invalidateQueries({ queryKey: userKeys.roles() });
    },
  });
}

export function useDeactivateUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: UUID) => api.del<OkResponse>(`/api/users/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userKeys.all });
    },
  });
}

export function useResetPinMutation() {
  return useMutation({
    mutationFn: ({ id, pin }: { id: UUID; pin: string }) =>
      api.post<OkResponse>(`/api/users/${id}/reset-pin`, { pin }),
  });
}

export function useSetRolePermissionsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ roleId, codes }: { roleId: UUID; codes: string[] }) =>
      api.put<Role>(`/api/roles/${roleId}/permissions`, { codes }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: userKeys.roles() });
    },
  });
}
