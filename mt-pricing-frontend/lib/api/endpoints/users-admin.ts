"use client";

/**
 * Admin facade sobre `usersApi` + `rolesApi`.
 *
 * El cliente original (`lib/api/endpoints/users.ts`) sigue siendo la única
 * fuente; este módulo sólo re-exporta y añade tipos derivados específicos
 * de la pantalla `/admin/usuarios`.
 */

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import {
  usersApi,
  type RoleSummary,
  type UserDetail,
  type UserListItem,
} from "@/lib/api/endpoints/users";

export type { RoleSummary, UserDetail, UserListItem };

export interface PermissionSummary {
  id: string;
  code: string;
  description: string | null;
}

export interface RoleWithPermissions extends RoleSummary {
  permissions: PermissionSummary[];
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new Error(
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const usersAdminApi = {
  ...usersApi,
  getRolePermissions: (roleId: string) =>
    authedFetch<RoleWithPermissions>(`/api/v1/roles/${roleId}/permissions`),
};
