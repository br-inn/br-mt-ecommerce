/**
 * Mocks extendidos para pantallas Sprint 3 / Sprint 4.
 *
 * Cada `installXxxMocks` instala route handlers en `page` para devolver
 * payloads deterministas. Los handlers cubren:
 *  - Dashboard stats (`/api/v1/dashboard/stats`)
 *  - Pricing (list + detail + approve/reject + bulk + revise + simulate + propose
 *    + channels + tasks/progress + bulk-publish)
 *  - Matches (list + validate + discard + refresh)
 *  - Translations workflow (list + upsert + approve)
 *  - Datasheets (list + upload + apply + status)
 *  - Channel mirror (diff + sync + publish + sync-log)
 *  - Currencies + FX rates (admin + legacy)
 *
 * Diseño:
 *  - Cada handler responde a method+url match con payload seed mínimo válido
 *    según los types declarados en `lib/api/endpoints/*`.
 *  - El test puede sobrescribir un handler específico llamando a `page.route`
 *    *después* del install (Playwright respeta el último match).
 */

import type { Page, Route } from "@playwright/test";

const FIXED_NOW = "2026-05-07T10:00:00Z";

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface DashboardStatsSeed {
  catalog: {
    products_total: number;
    products_active: number;
    products_complete: number;
    products_partial: number;
    products_blocked: number;
  };
  translations: {
    es_approved: number;
    ar_approved: number;
    es_coverage_pct: number;
    ar_coverage_pct: number;
  };
  users: { total: number; with_role: number; without_role: number };
  activity: {
    audit_events_24h: number;
    recent_events: Array<{
      id: string;
      actor_id: string | null;
      entity_type: string;
      action: string;
      event_at: string;
    }>;
  };
  jobs: { enabled: number; runs_24h: number; failures_24h: number };
  as_of: string;
}

export const FAKE_DASHBOARD: DashboardStatsSeed = {
  catalog: {
    products_total: 5085,
    products_active: 4200,
    products_complete: 3960,
    products_partial: 940,
    products_blocked: 185,
  },
  translations: {
    es_approved: 4800,
    ar_approved: 3500,
    es_coverage_pct: 94,
    ar_coverage_pct: 71,
  },
  users: { total: 12, with_role: 11, without_role: 1 },
  activity: {
    audit_events_24h: 87,
    recent_events: [
      {
        id: "ev-1",
        actor_id: "user-aaaaaaaa",
        entity_type: "product",
        action: "product.update",
        event_at: FIXED_NOW,
      },
      {
        id: "ev-2",
        actor_id: null,
        entity_type: "translation",
        action: "translation.approve",
        event_at: FIXED_NOW,
      },
    ],
  },
  jobs: { enabled: 6, runs_24h: 24, failures_24h: 1 },
  as_of: FIXED_NOW,
};

export function installDashboardMocks(
  page: Page,
  override?: Partial<DashboardStatsSeed>,
): void {
  const payload = { ...FAKE_DASHBOARD, ...override };
  page.route("**/api/v1/dashboard/stats", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
  });
}

// ---------------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------------

interface PriceSeed {
  id: string;
  product_sku: string;
  channel_id: string;
  scheme_code: string;
  amount: string;
  currency: string;
  margin_pct: string;
  status: string;
  proposed_by: string | null;
  created_at: string;
}

export const FAKE_PRICES: PriceSeed[] = [
  {
    id: "price-001",
    product_sku: "MTV-1004",
    channel_id: "channel-amazon-uae",
    scheme_code: "FBA",
    amount: "189.50",
    currency: "AED",
    margin_pct: "0.32",
    status: "pending_review",
    proposed_by: "user-aaaaaaaa",
    created_at: "2026-05-07T08:00:00Z",
  },
  {
    id: "price-002",
    product_sku: "MTV-1005",
    channel_id: "channel-amazon-uae",
    scheme_code: "FBM",
    amount: "320.00",
    currency: "AED",
    margin_pct: "0.18",
    status: "pending_review",
    proposed_by: "user-bbbbbbbb",
    created_at: "2026-05-07T07:00:00Z",
  },
];

const detailFor = (row: PriceSeed): Record<string, unknown> => ({
  ...row,
  cost_total: "120.00",
  fx_rate: "4.05",
  median_aed: "200.00",
  rule_applied: "median_minus_2pct",
  formula: "amount = median_aed * 0.98",
  cap_applied: false,
  floor_applied: false,
  has_velocity_premium: false,
  has_warnings: false,
  has_critical_alerts: false,
  alerts: [],
  approval_events: [
    {
      id: "ev-1",
      from_status: "draft",
      to_status: "pending_review",
      reason: null,
      created_at: row.created_at,
    },
  ],
  breakdown: { cost: 120.0, fx_rate: 4.05, margin: 0.32 },
});

const fakeResult = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
  amount: "189.50",
  currency: "AED",
  margin_pct: "0.32",
  rule_applied: "median_minus_2pct",
  formula: "amount = median_aed * 0.98",
  cap_applied: false,
  floor_applied: false,
  has_velocity_premium: false,
  has_warnings: false,
  has_critical_alerts: false,
  alerts: [],
  breakdown: { cost: 120.0, fx_rate: 4.05, margin: 0.32 },
  ...overrides,
});

export function installPricingMocks(page: Page): void {
  // List with optional ?status filter
  page.route("**/api/v1/pricing/prices?**", async (route: Route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    const url = new URL(route.request().url());
    const status = url.searchParams.get("status");
    const items = status
      ? FAKE_PRICES.filter((p) => p.status === status)
      : FAKE_PRICES;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: items.length,
      }),
    });
  });

  // Bulk approve
  page.route("**/api/v1/pricing/prices/bulk-approve", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ approved: FAKE_PRICES.length, failed: 0 }),
    });
  });

  // Bulk publish
  page.route("**/api/v1/pricing/prices/bulk-publish", async (route: Route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "task-bulk-publish-001" }),
    });
  });

  // Recalculate
  page.route("**/api/v1/pricing/prices/recalculate", async (route: Route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "task-recalc-001" }),
    });
  });

  // Task progress
  page.route(
    "**/api/v1/pricing/tasks/*/progress",
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          task_id: "task-bulk-publish-001",
          status: "success",
          processed: 1,
          total: 1,
          failed: 0,
          eta_seconds: 0,
        }),
      });
    },
  );

  // Detail + per-id action endpoints (approve/reject/revise/export)
  page.route(
    /\/api\/v1\/pricing\/prices\/(?!bulk-)[^/?]+(\/(approve|reject|revise|export))?$/,
    async (route: Route) => {
      const url = route.request().url();
      const method = route.request().method();
      const segments = url.split("?")[0]?.split("/") ?? [];
      const last = segments[segments.length - 1] ?? "";
      const isAction =
        last === "approve" || last === "reject" || last === "revise" || last === "export";
      const id = isAction ? (segments[segments.length - 2] ?? "price-001") : last;
      const found = FAKE_PRICES.find((p) => p.id === id) ?? FAKE_PRICES[0]!;
      if (method === "POST") {
        const updated = { ...found };
        if (last === "approve") updated.status = "approved";
        else if (last === "reject") updated.status = "rejected";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(detailFor(updated)),
        });
        return;
      }
      // GET detail
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(detailFor(found)),
      });
    },
  );

  // Calculate / simulate
  page.route("**/api/v1/pricing/simulate", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(fakeResult()),
    });
  });

  page.route("**/api/v1/pricing/calculate", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(fakeResult()),
    });
  });

  // Propose creates
  page.route("**/api/v1/pricing/prices", async (route: Route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(detailFor(FAKE_PRICES[0]!)),
      });
      return;
    }
    await route.fallback();
  });

  // Channels
  page.route(/\/api\/v1\/pricing\/channels(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { code: "amazon_uae", name: "Amazon UAE", state: "active" },
        { code: "noon_uae", name: "Noon UAE", state: "active" },
      ]),
    });
  });
}

// ---------------------------------------------------------------------------
// Matches (Sprint 3 — validación humana)
// ---------------------------------------------------------------------------

interface MatchSeed {
  id: string;
  external_id: string;
  brand: string;
  title: string;
  kind: "peer" | "drop" | "unknown";
  status: "pending" | "validated" | "discarded";
  score: number;
  price_aed: string | null;
  delivery_text: string | null;
  specs_jsonb: Record<string, unknown>;
  calibrated_confidence: number | null;
  conf_lower: number | null;
  conf_upper: number | null;
  review_priority: "low" | "high" | null;
}

export const FAKE_MATCHES: MatchSeed[] = [
  {
    id: "m-001",
    external_id: "B0AAAAAAAA",
    brand: "ACME",
    title: "ACME valve DN50 PN16 brass",
    kind: "peer",
    status: "pending",
    score: 0.92,
    price_aed: "175.0",
    delivery_text: "2-3 días",
    specs_jsonb: {
      material: "brass",
      valve_type: "ball",
      thread: "NPT",
      pn: "PN16",
      norma: "ISO",
      _enhanced: { method: "llm", auto_validate: false, visual_verdict: null },
    },
    calibrated_confidence: null,
    conf_lower: null,
    conf_upper: null,
    review_priority: null,
  },
  {
    id: "m-002",
    external_id: "B0BBBBBBBB",
    brand: "OtherCorp",
    title: "OC valve DN50",
    kind: "drop",
    status: "pending",
    score: 0.78,
    price_aed: "210.0",
    delivery_text: "5 días",
    specs_jsonb: { material: "brass", pn: "PN16" },
    calibrated_confidence: null,
    conf_lower: null,
    conf_upper: null,
    review_priority: null,
  },
];

export function installMatchesMocks(page: Page): void {
  page.route(/\/api\/v1\/matches(\?.*)?$/, async (route: Route) => {
    const url = new URL(route.request().url());
    const status = url.searchParams.get("status");
    const items = status
      ? FAKE_MATCHES.filter((m) => m.status === status)
      : FAKE_MATCHES;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items,
        next_cursor: null,
        total: items.length,
      }),
    });
  });

  page.route(/\/api\/v1\/matches\/[^/]+\/validate$/, async (route: Route) => {
    const id = route.request().url().split("/").slice(-2)[0] ?? "m-001";
    const found = FAKE_MATCHES.find((m) => m.id === id) ?? FAKE_MATCHES[0]!;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...found, status: "validated" }),
    });
  });

  page.route(/\/api\/v1\/matches\/[^/]+\/discard$/, async (route: Route) => {
    const id = route.request().url().split("/").slice(-2)[0] ?? "m-001";
    const found = FAKE_MATCHES.find((m) => m.id === id) ?? FAKE_MATCHES[0]!;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...found, status: "discarded" }),
    });
  });

  page.route(/\/api\/v1\/matches\/[^/]+\/refresh$/, async (route: Route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "task-refresh-001" }),
    });
  });

  // Agent endpoints mocks
  page.route("**/api/v1/matches/agent/config**", async (route: Route) => {
    if (route.request().method() === "PUT") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          mode: body["mode"] ?? "shadow",
          alpha: body["alpha"] ?? "0.020",
          min_labels_gate: body["min_labels_gate"] ?? 200,
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        mode: "shadow",
        alpha: "0.020",
        min_labels_gate: 200,
        updated_at: new Date().toISOString(),
      }),
    });
  });

  page.route("**/api/v1/matches/agent/metrics**", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        golden_labels_total: 12,
        min_labels_gate: 200,
        gate_reached: false,
        shadow_decisions: 5,
        shadow_precision: 0.8,
        calibrator_version: null,
        calibrator_brier: null,
        calibrator_ece: null,
        calibrator_trained_on: null,
        mode: "shadow",
      }),
    });
  });

  page.route(/\/api\/v1\/matches\/[^/]+\/revert$/, async (route: Route) => {
    const url = route.request().url();
    const id = url.split("/matches/")[1]?.split("/revert")[0];
    const match = FAKE_MATCHES.find((m) => m.id === id);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...(match ?? FAKE_MATCHES[0]!), status: "pending", specs_jsonb: {} }),
    });
  });
}

// ---------------------------------------------------------------------------
// Translations workflow
// ---------------------------------------------------------------------------

interface TranslationSeed {
  id: string;
  language: "es" | "ar";
  status: "draft" | "pending" | "approved";
  name: string;
  description: string | null;
}

export const FAKE_TRANSLATIONS: TranslationSeed[] = [
  {
    id: "tr-es",
    language: "es",
    status: "draft",
    name: "Válvula DN50 PN16",
    description: null,
  },
  {
    id: "tr-ar",
    language: "ar",
    status: "draft",
    name: "صمام DN50 PN16",
    description: null,
  },
];

export function installTranslationsMocks(page: Page, sku: string): void {
  // Single product fetch (used by useProduct)
  page.route(`**/api/v1/products/${sku}`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "prod-001",
        sku,
        name_en: "Valve DN50 PN16",
        description_en: "Brass valve DN50 PN16 ISO",
        family: "valves",
        brand: "MT",
        dn: "DN50",
        pn: "PN16",
        material: "brass",
        type: null,
        connection: null,
        weight_kg: 1.5,
        dimensions: null,
        packaging: null,
        intrastat: null,
        data_quality: "complete",
        translation_status_es: "draft",
        translation_status_ar: "draft",
        active: true,
        primary_image_url: null,
        created_at: FIXED_NOW,
        updated_at: FIXED_NOW,
      }),
    });
  });

  // List translations
  page.route(
    "**/api/v1/products/*/translations",
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(FAKE_TRANSLATIONS),
      });
    },
  );

  // Upsert + approve per lang
  page.route(
    /\/api\/v1\/products\/[^/]+\/translations\/(es|ar)(\/approve)?$/,
    async (route: Route) => {
      const url = route.request().url();
      const isApprove = url.endsWith("/approve");
      const langMatch = /\/translations\/(es|ar)/.exec(url);
      const lang = (langMatch?.[1] ?? "es") as "es" | "ar";
      const seed = FAKE_TRANSLATIONS.find((t) => t.language === lang) ?? FAKE_TRANSLATIONS[0]!;
      const updated = isApprove
        ? { ...seed, status: "approved" as const }
        : { ...seed, status: "pending" as const };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(updated),
      });
    },
  );
}

// ---------------------------------------------------------------------------
// Datasheets uploader
// ---------------------------------------------------------------------------

export function installDatasheetsMocks(page: Page, sku: string): void {
  // Product (necesario para layout SKU)
  page.route(`**/api/v1/products/${sku}`, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "prod-ds-001",
        sku,
        name_en: "Valve DN50 PN16",
        family: "valves",
        brand: "MT",
        dn: "DN50",
        pn: "PN16",
        material: "brass",
        type: null,
        connection: null,
        weight_kg: 1.5,
        dimensions: null,
        packaging: null,
        intrastat: null,
        description_en: null,
        data_quality: "complete",
        translation_status_es: "approved",
        translation_status_ar: "draft",
        active: true,
        primary_image_url: null,
        created_at: FIXED_NOW,
        updated_at: FIXED_NOW,
      }),
    });
  });

  // List datasheets for SKU
  page.route(
    "**/api/v1/imports/datasheets/by-sku/*",
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    },
  );

  // Upload PDF
  page.route(
    "**/api/v1/imports/datasheets/upload**",
    async (route: Route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "run-ds-001",
          status: "preview_ready",
          uploaded_filename: "spec.pdf",
          extracted: { material: "brass", pn: "PN16" },
          matched_skus: [sku],
          applied: null,
          error: null,
        }),
      });
    },
  );

  // Apply
  page.route(
    "**/api/v1/imports/datasheets/*/apply",
    async (route: Route) => {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "run-ds-001",
          status: "applying",
          uploaded_filename: "spec.pdf",
          extracted: {},
          matched_skus: [sku],
          applied: { persisted: 1, errors: 0 },
          error: null,
        }),
      });
    },
  );

  // Status poll
  page.route(
    "**/api/v1/imports/datasheets/*/status",
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run_id: "run-ds-001",
          status: "completed",
          uploaded_filename: "spec.pdf",
          extracted: {},
          matched_skus: [sku],
          applied: { persisted: 1, errors: 0 },
          error: null,
        }),
      });
    },
  );
}

// ---------------------------------------------------------------------------
// Channel mirror (Amazon UAE)
// ---------------------------------------------------------------------------

export function installChannelMirrorMocks(page: Page): void {
  page.route(
    /\/api\/v1\/channels\/[^/]+\/[^/]+\/diff$/,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: "amazon_uae",
          sku: "MTV-1004",
          external_id: "B0AAAAAAAA",
          fetched_at: FIXED_NOW,
          summary: { match: 5, drift: 2, missing: 1, queued: 0 },
          diffs: [
            {
              field: "title",
              lang: "en",
              is_mono: false,
              status: "drift",
              mt: "Valve DN50 PN16",
              live: "Old Valve DN50",
            },
            {
              field: "price_aed",
              lang: "en",
              is_mono: true,
              status: "match",
              mt: "189.50",
              live: "189.50",
            },
            {
              field: "description_ar",
              lang: "ar",
              is_mono: false,
              status: "missing",
              mt: "صمام",
              live: null,
            },
          ],
        }),
      });
    },
  );

  page.route(
    /\/api\/v1\/channels\/[^/]+\/[^/]+\/sync$/,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          channel: "amazon_uae",
          sku: "MTV-1004",
          external_id: "B0AAAAAAAA",
          fetched_at: FIXED_NOW,
          summary: { match: 6, drift: 1, missing: 1, queued: 0 },
          diffs: [],
        }),
      });
    },
  );

  page.route(
    /\/api\/v1\/channels\/[^/]+\/[^/]+\/publish$/,
    async (route: Route) => {
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ task_id: "task-publish-001", queued: 3 }),
      });
    },
  );

  page.route(
    /\/api\/v1\/channels\/[^/]+\/sync-log\?.*$/,
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "log-1",
            event_type: "push",
            ok: true,
            summary: "3 fields pushed",
            created_at: FIXED_NOW,
          },
        ]),
      });
    },
  );
}

// ---------------------------------------------------------------------------
// Currencies + FX rates
// ---------------------------------------------------------------------------

export function installCurrencyAndFxMocks(page: Page): void {
  // Legacy `/admin/divisas` endpoints
  page.route("**/api/v1/pricing/currencies", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { code: "EUR", name: "Euro", symbol: "€", decimals: 2, is_base: true, active: true },
        { code: "AED", name: "UAE Dirham", symbol: "AED", decimals: 2, is_base: false, active: true },
        { code: "USD", name: "US Dollar", symbol: "$", decimals: 2, is_base: false, active: true },
      ]),
    });
  });

  page.route(/\/api\/v1\/pricing\/fx-rates(\?.*)?$/, async (route: Route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "fx-new",
          from_currency: body["from_currency"] ?? "EUR",
          to_currency: body["to_currency"] ?? "AED",
          rate: body["rate"] ?? 4.05,
          effective_from: body["effective_from"] ?? FIXED_NOW,
          effective_to: null,
          source: body["source"] ?? "manual",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "fx-1",
          from_currency: "EUR",
          to_currency: "AED",
          rate: "4.0500",
          effective_from: FIXED_NOW,
          effective_to: null,
          source: "ecb",
        },
      ]),
    });
  });

  // Admin endpoints (S3) `/api/v1/currencies` + `/api/v1/fx-rates`
  page.route(/\/api\/v1\/currencies(\?.*)?$/, async (route: Route) => {
    if (route.request().method() === "PATCH") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { code: "EUR", name: "Euro", symbol: "€", decimals: 2, is_base: true, active: true },
        { code: "AED", name: "UAE Dirham", symbol: "AED", decimals: 2, is_base: false, active: true },
      ]),
    });
  });

  page.route(/\/api\/v1\/fx-rates(\?.*)?$/, async (route: Route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "fx-row-new",
          from_currency: body["from_currency"] ?? "EUR",
          to_currency: body["to_currency"] ?? "AED",
          rate: body["rate"] ?? 4.05,
          effective_from: body["effective_from"] ?? FIXED_NOW,
          effective_to: null,
          source: body["source"] ?? "manual",
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "fx-row-1",
          from_currency: "EUR",
          to_currency: "AED",
          rate: "4.0500",
          effective_from: FIXED_NOW,
          effective_to: null,
          source: "ecb",
        },
      ]),
    });
  });
}
