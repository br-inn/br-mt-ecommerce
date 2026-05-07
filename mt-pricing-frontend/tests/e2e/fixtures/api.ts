/**
 * HTTP helpers for talking to the backend directly from Playwright tests.
 *
 * Usamos `request` (APIRequestContext) en lugar de fetch para que las cookies
 * vivan en el mismo contexto del browser cuando hace falta. Para llamadas
 * "puras" (healthchecks, seed) basta con APIRequestContext standalone.
 */

import { request, type APIRequestContext } from "@playwright/test";
import { BACKEND_URL, FLOWER_URL } from "./env";

export const HEALTH_LIVE_PATH = "/health/live";
export const HEALTH_READY_PATH = "/health/ready";

/** Crea un APIRequestContext desechable para llamadas one-shot (healthchecks). */
export async function createApiContext(): Promise<APIRequestContext> {
  return await request.newContext({
    baseURL: BACKEND_URL,
    extraHTTPHeaders: { "X-Test-Source": "playwright-e2e" },
  });
}

export interface HealthResult {
  status: number;
  ok: boolean;
  body: unknown;
}

export async function getLive(): Promise<HealthResult> {
  const ctx = await createApiContext();
  try {
    const res = await ctx.get(HEALTH_LIVE_PATH);
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    return { status: res.status(), ok: res.ok(), body };
  } finally {
    await ctx.dispose();
  }
}

export async function getReady(): Promise<HealthResult> {
  const ctx = await createApiContext();
  try {
    const res = await ctx.get(HEALTH_READY_PATH);
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    return { status: res.status(), ok: res.ok(), body };
  } finally {
    await ctx.dispose();
  }
}

/** Flower healthcheck (basic auth admin:devpassword por defecto en dev). */
export async function getFlowerHealth(): Promise<HealthResult> {
  const ctx = await request.newContext({
    baseURL: FLOWER_URL,
    httpCredentials: { username: "admin", password: "devpassword" },
  });
  try {
    const res = await ctx.get("/healthcheck");
    return {
      status: res.status(),
      ok: res.ok(),
      body: await res.text().catch(() => null),
    };
  } finally {
    await ctx.dispose();
  }
}

/**
 * Borra suppliers creados por tests (via API REST). Best-effort — si requiere
 * auth, confiamos en seed-time RLS bypass o un service-role key configurado.
 */
export async function deleteSupplierByCode(
  ctx: APIRequestContext,
  code: string,
  bearer?: string,
): Promise<void> {
  const headers: Record<string, string> = bearer
    ? { Authorization: `Bearer ${bearer}` }
    : {};
  // Intentamos por filtro `code` — el backend devuelve list, luego DELETE por id.
  const list = await ctx.get("/api/v1/suppliers", {
    params: { search: code },
    headers,
  });
  if (!list.ok()) return;
  const data = (await list.json()) as { items?: Array<{ id: string; code: string }> };
  for (const item of data.items ?? []) {
    if (item.code === code) {
      await ctx.delete(`/api/v1/suppliers/${item.id}`, { headers }).catch(() => null);
    }
  }
}
