"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Wrapper tipado para los endpoints `/api/v1/me`.
 *
 * NOTA: usamos `fetch` con auth header explícito (Bearer Supabase access_token)
 * en vez del openapi-fetch client porque éste se construye sin auth y el
 * `me` endpoint depende del token vivo del usuario en sesión.
 */

export interface MeResponse {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  locale: "es" | "en" | "ar";
  is_active: boolean;
  role: { id: string; code: string; name: string } | null;
  permissions: string[];
  created_at: string;
  last_login_at: string | null;
}

export interface MeUpdatePayload {
  full_name?: string;
  avatar_url?: string;
  locale?: "es" | "en" | "ar";
}

async function authedFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
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
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      // ignore
    }
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(message);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const authApi = {
  getMe: () => authedFetch<MeResponse>("/api/v1/me"),
  updateMe: (payload: MeUpdatePayload) =>
    authedFetch<MeResponse>("/api/v1/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  logout: () =>
    authedFetch<void>("/api/v1/me/logout", {
      method: "POST",
    }),
};
