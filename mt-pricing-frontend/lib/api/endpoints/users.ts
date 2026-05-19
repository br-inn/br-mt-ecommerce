"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export interface RoleSummary {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_system: boolean;
}

export interface UserListItem {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  role: RoleSummary | null;
  last_login_at: string | null;
  created_at: string;
}

export interface UserDetail extends UserListItem {
  avatar_url: string | null;
  locale: "es" | "en" | "ar";
}

export interface InvitePayload {
  email: string;
  full_name: string;
  role_code: string;
  locale?: "es" | "en" | "ar";
}

export interface UpdateUserPayload {
  full_name?: string;
  locale?: "es" | "en" | "ar";
  is_active?: boolean;
}

export interface RoleAssignPayload {
  role_code: string;
  note?: string;
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
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

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const usersApi = {
  list: (params: {
    role?: string | undefined;
    is_active?: boolean | undefined;
    limit?: number | undefined;
    offset?: number | undefined;
  } = {}) =>
    authedFetch<UserListItem[]>(`/api/v1/users${buildQuery(params)}`),
  get: (id: string) => authedFetch<UserDetail>(`/api/v1/users/${id}`),
  invite: (payload: InvitePayload) =>
    authedFetch<UserDetail>("/api/v1/users/invite", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: UpdateUserPayload) =>
    authedFetch<UserDetail>(`/api/v1/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  assignRole: (id: string, payload: RoleAssignPayload) =>
    authedFetch<UserDetail>(`/api/v1/users/${id}/roles`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  revokeRole: (id: string, reason?: string) =>
    authedFetch<UserDetail>(
      `/api/v1/users/${id}/roles${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`,
      { method: "DELETE" },
    ),
  resendInvite: (id: string) =>
    authedFetch<void>(`/api/v1/users/${id}/resend-invite`, { method: "POST" }),
  forceLogout: (id: string, reason?: string) =>
    authedFetch<void>(
      `/api/v1/users/${id}/force-logout${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`,
      { method: "POST" },
    ),
  listRoles: () => authedFetch<RoleSummary[]>("/api/v1/roles"),
  listPermissions: () =>
    authedFetch<{ id: string; code: string; description: string | null }[]>(
      "/api/v1/permissions",
    ),
};
