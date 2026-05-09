"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export interface CertificationRef {
  id: string;
  code: string;
  name: string;
  issued_by: string | null;
  scope: string | null;
  logo_url: string | null;
}

export interface EffectiveDisplayResponse {
  tags: string[];
  certifications: CertificationRef[];
}

export interface DisplayPairSetRequest {
  paired_sku: string;
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
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
    throw new Error(`effective-display: HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const effectiveDisplayApi = {
  get: (sku: string): Promise<EffectiveDisplayResponse> =>
    authedFetch<EffectiveDisplayResponse>(
      `/api/v1/products/${encodeURIComponent(sku)}/effective-display`,
    ),
  setPair: (sku: string, paired_sku: string): Promise<void> =>
    authedFetch<void>(
      `/api/v1/products/${encodeURIComponent(sku)}/display-pair`,
      {
        method: "PUT",
        body: JSON.stringify({ paired_sku }),
      },
    ),
  clearPair: (sku: string): Promise<void> =>
    authedFetch<void>(
      `/api/v1/products/${encodeURIComponent(sku)}/display-pair`,
      { method: "DELETE" },
    ),
};
