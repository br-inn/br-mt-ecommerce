"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  usersAdminApi,
  type RoleSummary,
  type RoleWithPermissions,
  type UserDetail,
  type UserListItem,
  type PermissionSummary,
} from "@/lib/api/endpoints/users-admin";
import type {
  InvitePayload,
  RoleAssignPayload,
  UpdateUserPayload,
} from "@/lib/api/endpoints/users";

export const usersKeys = {
  all: () => ["users-admin"] as const,
  list: (params: {
    role?: string | undefined;
    is_active?: boolean | undefined;
  }) => [...usersKeys.all(), "list", params] as const,
  detail: (id: string) => [...usersKeys.all(), "detail", id] as const,
  roles: () => ["roles-catalog"] as const,
  rolePerms: (roleId: string) => ["roles-catalog", roleId, "permissions"] as const,
  permissions: () => ["permissions-catalog"] as const,
};

export function useUsersList(
  params: {
    role?: string | undefined;
    is_active?: boolean | undefined;
    limit?: number | undefined;
    offset?: number | undefined;
  } = {},
) {
  return useQuery<UserListItem[], Error>({
    queryKey: usersKeys.list({
      ...(params.role !== undefined ? { role: params.role } : {}),
      ...(params.is_active !== undefined ? { is_active: params.is_active } : {}),
    }),
    queryFn: () => usersAdminApi.list(params),
    staleTime: 30_000,
  });
}

export function useUserDetail(id: string | undefined) {
  return useQuery<UserDetail, Error>({
    queryKey: usersKeys.detail(id ?? ""),
    queryFn: () => usersAdminApi.get(id as string),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useRolesCatalog() {
  return useQuery<RoleSummary[], Error>({
    queryKey: usersKeys.roles(),
    queryFn: () => usersAdminApi.listRoles(),
    staleTime: 5 * 60_000,
  });
}

export function useRolePermissions(roleId: string | undefined) {
  return useQuery<RoleWithPermissions, Error>({
    queryKey: usersKeys.rolePerms(roleId ?? ""),
    queryFn: () => usersAdminApi.getRolePermissions(roleId as string),
    enabled: !!roleId,
    staleTime: 5 * 60_000,
  });
}

export function usePermissionsCatalog() {
  return useQuery<PermissionSummary[], Error>({
    queryKey: usersKeys.permissions(),
    queryFn: () => usersAdminApi.listPermissions(),
    staleTime: 5 * 60_000,
  });
}

export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation<UserDetail, Error, InvitePayload>({
    mutationFn: (payload) => usersAdminApi.invite(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.all() });
    },
  });
}

export function useUpdateUser(id: string) {
  const qc = useQueryClient();
  return useMutation<UserDetail, Error, UpdateUserPayload>({
    mutationFn: (payload) => usersAdminApi.update(id, payload),
    onSuccess: (data) => {
      qc.setQueryData(usersKeys.detail(id), data);
      void qc.invalidateQueries({ queryKey: usersKeys.all() });
    },
  });
}

export function useAssignRole(id: string) {
  const qc = useQueryClient();
  return useMutation<UserDetail, Error, RoleAssignPayload>({
    mutationFn: (payload) => usersAdminApi.assignRole(id, payload),
    onSuccess: (data) => {
      qc.setQueryData(usersKeys.detail(id), data);
      void qc.invalidateQueries({ queryKey: usersKeys.all() });
    },
  });
}

export function useRevokeRole(id: string) {
  const qc = useQueryClient();
  return useMutation<UserDetail, Error, { reason?: string }>({
    mutationFn: ({ reason }) => usersAdminApi.revokeRole(id, reason),
    onSuccess: (data) => {
      qc.setQueryData(usersKeys.detail(id), data);
      void qc.invalidateQueries({ queryKey: usersKeys.all() });
    },
  });
}

export function useForceLogout(id: string) {
  return useMutation<void, Error, { reason?: string }>({
    mutationFn: ({ reason }) => usersAdminApi.forceLogout(id, reason),
  });
}
