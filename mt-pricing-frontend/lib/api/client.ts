import createClient from "openapi-fetch";
import env from "@/lib/env";
import type { paths } from "@/lib/api/types";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Typed backend client.
 *
 * Agente G enriches `paths` via `pnpm openapi:gen` and adds endpoint helpers
 * under `lib/api/endpoints/`.
 */
export const apiClient = createClient<paths>({
  baseUrl: env.NEXT_PUBLIC_BACKEND_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export type ApiClient = typeof apiClient;

// ---------------------------------------------------------------------------
// Auth-aware fetch helper — shared across endpoint modules
// ---------------------------------------------------------------------------

/**
 * Descarga un archivo con autenticación Bearer y lo dispara como descarga del navegador.
 * Alternativa a window.open() que sí incluye el token de sesión.
 */
export async function authedDownload(
  path: string,
  fallbackFilename: string,
  init: RequestInit = {},
): Promise<void> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
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
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(msg);
  }
  // Prefer server-sent filename from Content-Disposition header
  const cd = res.headers.get("Content-Disposition") ?? "";
  const match = /filename[^;=\n]*=\s*((['"])(?<q>.*?)\2|(?<bare>[^;\n"]+))/i.exec(cd);
  const filename = match?.groups?.q ?? match?.groups?.bare?.trim() ?? fallbackFilename;

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
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
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
