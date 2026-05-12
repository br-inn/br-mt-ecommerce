"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import { ProductsApiError } from "./products";
import type {
  AssetLink,
  AssetLinkCreatePayload,
  AssetLinkOwnerType,
  AssetLinkWithAsset,
} from "../types-assets-extended";

/**
 * Wrappers tipados para endpoints Fase 4 `/api/v1/asset-links` y
 * `/api/v1/{owner_type}/{owner_id}/asset-links`.
 */

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
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new ProductsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const assetLinksApi = {
  listForOwner: (
    ownerType: AssetLinkOwnerType,
    ownerId: string,
  ): Promise<AssetLinkWithAsset[]> =>
    authedFetch<AssetLinkWithAsset[]>(
      `/api/v1/${ownerType}/${encodeURIComponent(ownerId)}/asset-links`,
    ),

  create: (payload: AssetLinkCreatePayload): Promise<AssetLink> =>
    authedFetch<AssetLink>(`/api/v1/asset-links`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  remove: (linkId: string): Promise<void> =>
    authedFetch<void>(`/api/v1/asset-links/${linkId}`, {
      method: "DELETE",
    }),
};
