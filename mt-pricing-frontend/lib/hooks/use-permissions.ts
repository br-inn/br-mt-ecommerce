"use client";

import { useMemo } from "react";
import { useAuth } from "@/components/auth/auth-provider";

export type Permission = string;

export interface UsePermissionsResult {
  permissions: Permission[];
  /** Backwards compat — equivalente a `hasPermission`. */
  can: (permission: Permission) => boolean;
  hasPermission: (permission: Permission) => boolean;
  hasPermissions: (permissions: Permission[]) => boolean;
  hasAnyPermission: (permissions: Permission[]) => boolean;
}

export function usePermissions(): UsePermissionsResult {
  const { permissions } = useAuth();
  const set = useMemo(() => new Set(permissions), [permissions]);

  return useMemo(
    () => ({
      permissions,
      can: (p) => set.has(p),
      hasPermission: (p) => set.has(p),
      hasPermissions: (required) => required.every((p) => set.has(p)),
      hasAnyPermission: (required) => required.some((p) => set.has(p)),
    }),
    [permissions, set],
  );
}
