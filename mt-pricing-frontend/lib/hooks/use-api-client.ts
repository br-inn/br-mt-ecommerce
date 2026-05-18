"use client";

import { useCallback } from "react";
import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
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
    const detail = await res.json().catch(() => res.statusText);
    throw Object.assign(new Error(typeof detail === "string" ? detail : JSON.stringify(detail)), {
      status: res.status,
      detail,
    });
  }
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export function useApiClient() {
  const get = useCallback(<T = unknown>(path: string) => authedFetch<T>(path), []);
  const post = useCallback(
    <T = unknown>(path: string, body: unknown) =>
      authedFetch<T>(path, { method: "POST", body: JSON.stringify(body) }),
    [],
  );
  const put = useCallback(
    <T = unknown>(path: string, body: unknown) =>
      authedFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }),
    [],
  );
  const del = useCallback(<T = unknown>(path: string) => authedFetch<T>(path, { method: "DELETE" }), []);

  return { get, post, put, del };
}
