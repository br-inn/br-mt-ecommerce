"use client";

import { useMemo } from "react";
import { useAuth } from "@/components/auth/auth-provider";

export type Permission = string;

export interface UsePermissionsResult {
  permissions: Permission[];
  isAdmin: boolean;
  isLoading: boolean;
  /** Backwards compat — equivalente a `hasPermission`. */
  can: (permission: Permission) => boolean;
  hasPermission: (permission: Permission) => boolean;
  hasPermissions: (permissions: Permission[]) => boolean;
  hasAnyPermission: (permissions: Permission[]) => boolean;
}

export function usePermissions(): UsePermissionsResult {
  const { permissions, user, isLoading } = useAuth();
  const isAdmin = user?.role?.code === "admin";
  const set = useMemo(() => new Set(permissions), [permissions]);

  return useMemo(
    () => ({
      permissions,
      isAdmin,
      isLoading,
      can: (p) => isAdmin || set.has(p),
      hasPermission: (p) => isAdmin || set.has(p),
      hasPermissions: (required) => isAdmin || required.every((p) => set.has(p)),
      hasAnyPermission: (required) => isAdmin || required.some((p) => set.has(p)),
    }),
    [permissions, set, isAdmin, isLoading],
  );
}
