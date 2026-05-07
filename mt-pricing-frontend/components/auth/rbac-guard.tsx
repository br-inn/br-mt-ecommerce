"use client";

import type { ReactNode } from "react";
import { usePermissions } from "@/lib/hooks/use-permissions";

interface RbacGuardProps {
  /**
   * Permission codes required (ALL must match — `hasPermissions`).
   * Si pasas un solo permiso, equivale a `hasPermission`.
   */
  permissions: string[];
  /** Si true, basta con UNO de los permisos (OR). */
  any?: boolean;
  fallback?: ReactNode;
  children: ReactNode;
}

/**
 * Render-prop style RBAC guard.
 *
 * Uso::
 *   <RbacGuard permissions={["users:invite"]}><InviteButton /></RbacGuard>
 *   <RbacGuard permissions={["prices:approve", "prices:bulk_approve"]} any>
 *     <ApprovalsLink />
 *   </RbacGuard>
 */
export function RbacGuard({
  permissions,
  any = false,
  fallback = null,
  children,
}: RbacGuardProps) {
  const { hasPermissions, hasAnyPermission } = usePermissions();
  const allowed = any ? hasAnyPermission(permissions) : hasPermissions(permissions);
  if (!allowed) return <>{fallback}</>;
  return <>{children}</>;
}

/** Backwards-compat alias usado por código pre-Wave2. */
export { RbacGuard as RBACGuard };
