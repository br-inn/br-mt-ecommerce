# Channel Pricing Engine — Plan 3: Frontend Pricing Desk

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el HTML standalone del Pricing Desk de Amazon UAE por una pantalla integrada en `mt-pricing-frontend` que consume los 13 endpoints del motor multi-canal (Plan 1+2 ya en `main`).

**Architecture:** Una sola ruta `app/(app)/pricing-desk/page.tsx` con selectores de canal + selling_model en header. Panel lateral colapsable con parámetros y márgenes. Tabla principal con semáforo + filtros + stepper de margen por producto. Todas las llamadas pasan por un endpoint wrapper tipado en `lib/api/endpoints/pricing-desk.ts` usando `openapi-fetch` + React Query.

**Tech Stack:** Next.js 16 App Router · React 19 · TypeScript estricto · Tailwind v4 · shadcn/ui · TanStack React Table · React Query 5 · openapi-typescript (tipos autogenerados)

**Prerequisito:** PR #128 ya mergeado a main — el backend tiene los 13 endpoints listos.

**Spec de referencia:** `docs/superpowers/specs/2026-05-28-channel-pricing-engine-design.md` (sección 8 - Frontend)

---

## Estructura de ficheros

```
mt-pricing-frontend/
├── lib/
│   └── api/
│       ├── types.ts                              ← REGENERAR (paso 1)
│       └── endpoints/
│           └── pricing-desk.ts                   ← CREAR
├── lib/hooks/pricing-desk/
│   ├── use-pricing-params.ts                     ← CREAR
│   ├── use-catalog-summary.ts                    ← CREAR
│   ├── use-margin-targets.ts                     ← CREAR
│   └── use-optimize-catalog.ts                   ← CREAR
├── app/(app)/pricing-desk/
│   ├── layout.tsx                                ← CREAR (selector canal/modelo)
│   ├── page.tsx                                  ← CREAR (pantalla principal)
│   └── _components/
│       ├── pricing-header.tsx                    ← CREAR (selector canal + KPI)
│       ├── semaforo.tsx                          ← CREAR (6 KPI cards)
│       ├── filters-bar.tsx                       ← CREAR (familia / esquema / señal)
│       ├── catalog-table.tsx                     ← CREAR (tabla principal con stepper)
│       ├── scheme-comparator.tsx                 ← CREAR (modal: 3 esquemas lado a lado)
│       ├── side-panel.tsx                        ← CREAR (wrapper colapsable)
│       ├── cost-params-section.tsx               ← CREAR (parámetros 4 escalones)
│       ├── family-margins-section.tsx            ← CREAR (stepper por familia)
│       ├── optimize-section.tsx                  ← CREAR (3 botones de optimización)
│       └── signal-badge.tsx                      ← CREAR (PÉRDIDA/FRÁGIL/FINO/ÓPTIMO/EXCELENTE)
└── components/data/
    └── numeric-stepper.tsx                       ← CREAR (componente -/+ reutilizable)
```

---

## Task 1: Regenerar tipos OpenAPI y verificar operaciones

**Files:**
- Modify: `mt-pricing-frontend/lib/api/types.ts`

- [ ] **1.1 Verificar que el spec del backend está actualizado**

```bash
cd "C:/BR-Github/br-mt/br-mt-ecommerce/mt-pricing-backend"
docker exec mt-backend sh -c "cd /app && python -m app.scripts.export_openapi" | tail -3
```
Esperado: `Wrote OpenAPI spec to ... (441 paths)` o similar.

- [ ] **1.2 Copiar el spec actualizado al host**

```bash
docker cp mt-backend:/app/_bmad-output/planning-artifacts/mt-api-contract-openapi.json \
  C:/BR-Github/br-mt/br-mt-ecommerce/mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json
```

- [ ] **1.3 Regenerar types.ts**

```bash
cd "C:/BR-Github/br-mt/br-mt-ecommerce/mt-pricing-frontend"
./scripts/openapi-gen.sh 2>&1 | tail -10
```

Si el script no existe, ejecutar directamente:
```bash
pnpm exec openapi-typescript ../mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json -o lib/api/types.ts
```

- [ ] **1.4 Verificar que las 13 operaciones existen**

```bash
cd "C:/BR-Github/br-mt/br-mt-ecommerce/mt-pricing-frontend"
grep -oE '"(getProductPrice|getCatalogSummary|optimizeCatalog|applyOptimization|getPricingParams|updateRouteParams|updateFeeParams|listMarginTargets|upsertMarginTarget|upsertMarginOverride|deleteMarginOverride|importCatalog|importLogistics)"' lib/api/types.ts | sort -u
```
Esperado: las 13 operaciones listadas (los nombres reales pueden diferir si el backend usó otra convención — investigar).

- [ ] **1.5 Commit**

```bash
git add mt-pricing-frontend/lib/api/types.ts
git commit -m "chore(types): regenerate OpenAPI types for pricing desk endpoints"
```

---

## Task 2: Endpoint wrapper y hooks de React Query

**Files:**
- Create: `mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts`
- Create: `mt-pricing-frontend/lib/hooks/pricing-desk/use-pricing-params.ts`
- Create: `mt-pricing-frontend/lib/hooks/pricing-desk/use-catalog-summary.ts`
- Create: `mt-pricing-frontend/lib/hooks/pricing-desk/use-margin-targets.ts`
- Create: `mt-pricing-frontend/lib/hooks/pricing-desk/use-optimize-catalog.ts`

- [ ] **2.1 Lee el patrón existente para entender la convención exacta**

```bash
cat mt-pricing-frontend/lib/api/endpoints/pricing.ts | head -60
```

Aprende:
- Cómo se importa `apiClient` o se hace `createClient`
- Patrón de funciones (async + tipo derivado de `components["schemas"]`)
- Manejo de errores

- [ ] **2.2 Crear `lib/api/endpoints/pricing-desk.ts`**

```typescript
// mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts
/**
 * Channel Pricing Desk endpoints — multi-channel B2C/B2B pricing.
 *
 * Reference: docs/superpowers/specs/2026-05-28-channel-pricing-engine-design.md
 */
import { apiClient, authedDownload } from "@/lib/api/client";
import type { components, operations } from "@/lib/api/types";

// ─── Type aliases ────────────────────────────────────────────────────────

export type SellingModel = "b2c" | "b2b";
export type FulfillmentScheme = "canal_full" | "canal_lastmile" | "merchant_managed";
export type Signal = "PÉRDIDA" | "FRÁGIL" | "FINO" | "ÓPTIMO" | "EXCELENTE";

export type PriceResult = components["schemas"]["PriceResultJSON"];
export type CatalogSummary = components["schemas"]["CatalogSummaryResponse"];
export type ProductPriceResponse = components["schemas"]["ProductPriceResponse"];
export type OptimizeResponse = components["schemas"]["OptimizeResponse"];
export type TradeRouteParams = components["schemas"]["TradeRouteParamsRead"];
export type ChannelFeeParams = components["schemas"]["ChannelFeeParamsRead"];
export type ChannelSchemeParams = components["schemas"]["ChannelSchemeParamsRead"];
export type MarginTarget = components["schemas"]["MarginTargetRead"];
export type CatalogImportResult = components["schemas"]["CatalogImportResult"];

export interface PricingParamsResponse {
  route: TradeRouteParams;
  fees: ChannelFeeParams & { total_fees_pct: number };
  schemes: ChannelSchemeParams[];
}

// ─── API wrapper ─────────────────────────────────────────────────────────

export const pricingDeskApi = {
  /** GET /pricing/{channel_code}/params */
  async getParams(channelCode: string): Promise<PricingParamsResponse> {
    const { data, error } = await apiClient.GET("/api/v1/pricing/{channel_code}/params", {
      params: { path: { channel_code: channelCode } },
    });
    if (error) throw new Error(`Failed to fetch pricing params: ${JSON.stringify(error)}`);
    return data as PricingParamsResponse;
  },

  /** PATCH /pricing/{channel_code}/route-params */
  async updateRouteParams(
    channelCode: string,
    body: Partial<components["schemas"]["TradeRouteParamsUpdate"]>,
  ): Promise<TradeRouteParams> {
    const { data, error } = await apiClient.PATCH(
      "/api/v1/pricing/{channel_code}/route-params",
      { params: { path: { channel_code: channelCode } }, body },
    );
    if (error) throw new Error(`Failed to update route params: ${JSON.stringify(error)}`);
    return data!;
  },

  /** PATCH /pricing/{channel_code}/fee-params */
  async updateFeeParams(
    channelCode: string,
    body: Partial<components["schemas"]["ChannelFeeParamsUpdate"]>,
  ): Promise<ChannelFeeParams> {
    const { data, error } = await apiClient.PATCH(
      "/api/v1/pricing/{channel_code}/fee-params",
      { params: { path: { channel_code: channelCode } }, body },
    );
    if (error) throw new Error(`Failed to update fee params: ${JSON.stringify(error)}`);
    return data!;
  },

  /** GET /pricing/{channel_code}/margin-targets */
  async listMarginTargets(channelCode: string): Promise<MarginTarget[]> {
    const { data, error } = await apiClient.GET(
      "/api/v1/pricing/{channel_code}/margin-targets",
      { params: { path: { channel_code: channelCode } } },
    );
    if (error) throw new Error(`Failed to fetch margin targets: ${JSON.stringify(error)}`);
    return data!;
  },

  /** PUT /pricing/{channel_code}/margin-targets */
  async upsertMarginTarget(
    channelCode: string,
    body: components["schemas"]["MarginTargetUpsert"],
  ): Promise<void> {
    const { error } = await apiClient.PUT(
      "/api/v1/pricing/{channel_code}/margin-targets",
      { params: { path: { channel_code: channelCode } }, body },
    );
    if (error) throw new Error(`Failed to upsert margin target: ${JSON.stringify(error)}`);
  },

  /** PUT /pricing/{channel_code}/margin-overrides/{sku} */
  async upsertMarginOverride(
    channelCode: string,
    sku: string,
    body: components["schemas"]["MarginOverrideUpsert"],
  ): Promise<components["schemas"]["MarginOverrideRead"]> {
    const { data, error } = await apiClient.PUT(
      "/api/v1/pricing/{channel_code}/margin-overrides/{sku}",
      { params: { path: { channel_code: channelCode, sku } }, body },
    );
    if (error) throw new Error(`Failed to upsert margin override: ${JSON.stringify(error)}`);
    return data!;
  },

  /** DELETE /pricing/{channel_code}/margin-overrides/{sku} */
  async deleteMarginOverride(
    channelCode: string,
    sku: string,
    sellingModel: SellingModel = "b2c",
  ): Promise<void> {
    const { error } = await apiClient.DELETE(
      "/api/v1/pricing/{channel_code}/margin-overrides/{sku}",
      {
        params: {
          path: { channel_code: channelCode, sku },
          query: { selling_model: sellingModel },
        },
      },
    );
    if (error) throw new Error(`Failed to delete margin override: ${JSON.stringify(error)}`);
  },

  /** GET /pricing/{channel_code}/product/{sku} */
  async getProductPrice(
    channelCode: string,
    sku: string,
    sellingModel: SellingModel = "b2c",
    marginPct?: number,
  ): Promise<ProductPriceResponse> {
    const { data, error } = await apiClient.GET(
      "/api/v1/pricing/{channel_code}/product/{sku}",
      {
        params: {
          path: { channel_code: channelCode, sku },
          query: {
            selling_model: sellingModel,
            ...(marginPct !== undefined && { margin_pct: marginPct }),
          },
        },
      },
    );
    if (error) throw new Error(`Failed to fetch product price: ${JSON.stringify(error)}`);
    return data!;
  },

  /** GET /pricing/{channel_code}/catalog */
  async getCatalogSummary(
    channelCode: string,
    options: {
      sellingModel?: SellingModel;
      familyId?: string;
      signal?: string;
    } = {},
  ): Promise<CatalogSummary> {
    const { data, error } = await apiClient.GET(
      "/api/v1/pricing/{channel_code}/catalog",
      {
        params: {
          path: { channel_code: channelCode },
          query: {
            selling_model: options.sellingModel ?? "b2c",
            ...(options.familyId && { family_id: options.familyId }),
            ...(options.signal && { signal: options.signal }),
          },
        },
      },
    );
    if (error) throw new Error(`Failed to fetch catalog summary: ${JSON.stringify(error)}`);
    return data!;
  },

  /** POST /pricing/{channel_code}/optimize */
  async optimizeCatalog(
    channelCode: string,
    sellingModel: SellingModel = "b2c",
  ): Promise<OptimizeResponse> {
    const { data, error } = await apiClient.POST(
      "/api/v1/pricing/{channel_code}/optimize",
      {
        params: {
          path: { channel_code: channelCode },
          query: { selling_model: sellingModel },
        },
      },
    );
    if (error) throw new Error(`Failed to optimize catalog: ${JSON.stringify(error)}`);
    return data!;
  },

  /** POST /pricing/{channel_code}/optimize/apply */
  async applyOptimization(
    channelCode: string,
    sellingModel: SellingModel = "b2c",
  ): Promise<void> {
    const { error } = await apiClient.POST(
      "/api/v1/pricing/{channel_code}/optimize/apply",
      {
        params: {
          path: { channel_code: channelCode },
          query: { selling_model: sellingModel },
        },
      },
    );
    if (error) throw new Error(`Failed to apply optimization: ${JSON.stringify(error)}`);
  },

  /** POST /pricing/{channel_code}/catalog/import */
  async importCatalog(
    channelCode: string,
    file: File,
    confirm: boolean = false,
  ): Promise<CatalogImportResult> {
    const formData = new FormData();
    formData.append("file", file);
    const { data, error } = await apiClient.POST(
      "/api/v1/pricing/{channel_code}/catalog/import",
      {
        params: {
          path: { channel_code: channelCode },
          query: { confirm },
        },
        body: formData as never,  // openapi-fetch FormData typing
        bodySerializer: (body: unknown) => body as never,
      },
    );
    if (error) throw new Error(`Failed to import catalog: ${JSON.stringify(error)}`);
    return data!;
  },

  /** POST /pricing/{channel_code}/logistics/import */
  async importLogistics(
    channelCode: string,
    file: File,
    confirm: boolean = false,
  ): Promise<{ total_rows: number; upserted: number; errors: Array<{ row: number; sku: string; error: string }> }> {
    const formData = new FormData();
    formData.append("file", file);
    const { data, error } = await apiClient.POST(
      "/api/v1/pricing/{channel_code}/logistics/import",
      {
        params: {
          path: { channel_code: channelCode },
          query: { confirm },
        },
        body: formData as never,
        bodySerializer: (body: unknown) => body as never,
      },
    );
    if (error) throw new Error(`Failed to import logistics: ${JSON.stringify(error)}`);
    return data as never;
  },
};
```

- [ ] **2.3 Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "pricing-desk" | head -10
```

Esperado: sin errores en `lib/api/endpoints/pricing-desk.ts`.

- [ ] **2.4 Crear `lib/hooks/pricing-desk/use-pricing-params.ts`**

```typescript
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi, type PricingParamsResponse } from "@/lib/api/endpoints/pricing-desk";
import type { components } from "@/lib/api/types";

export function usePricingParams(channelCode: string) {
  return useQuery({
    queryKey: ["pricing-desk", "params", channelCode],
    queryFn: () => pricingDeskApi.getParams(channelCode),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}

export function useUpdateRouteParams(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<components["schemas"]["TradeRouteParamsUpdate"]>) =>
      pricingDeskApi.updateRouteParams(channelCode, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "params", channelCode] });
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}

export function useUpdateFeeParams(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<components["schemas"]["ChannelFeeParamsUpdate"]>) =>
      pricingDeskApi.updateFeeParams(channelCode, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "params", channelCode] });
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}
```

- [ ] **2.5 Crear `lib/hooks/pricing-desk/use-catalog-summary.ts`**

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export interface CatalogFilters {
  familyId?: string;
  signal?: string;
}

export function useCatalogSummary(
  channelCode: string,
  sellingModel: SellingModel,
  filters: CatalogFilters,
) {
  return useQuery({
    queryKey: ["pricing-desk", "catalog", channelCode, sellingModel, filters],
    queryFn: () =>
      pricingDeskApi.getCatalogSummary(channelCode, {
        sellingModel,
        familyId: filters.familyId,
        signal: filters.signal,
      }),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}
```

- [ ] **2.6 Crear `lib/hooks/pricing-desk/use-margin-targets.ts`**

```typescript
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";
import type { components } from "@/lib/api/types";

export function useMarginTargets(channelCode: string) {
  return useQuery({
    queryKey: ["pricing-desk", "margin-targets", channelCode],
    queryFn: () => pricingDeskApi.listMarginTargets(channelCode),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}

export function useUpsertMarginTarget(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["MarginTargetUpsert"]) =>
      pricingDeskApi.upsertMarginTarget(channelCode, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "margin-targets", channelCode] });
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}

export function useUpsertMarginOverride(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sku,
      body,
    }: {
      sku: string;
      body: components["schemas"]["MarginOverrideUpsert"];
    }) => pricingDeskApi.upsertMarginOverride(channelCode, sku, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}

export function useDeleteMarginOverride(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sku, sellingModel }: { sku: string; sellingModel: SellingModel }) =>
      pricingDeskApi.deleteMarginOverride(channelCode, sku, sellingModel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}
```

- [ ] **2.7 Crear `lib/hooks/pricing-desk/use-optimize-catalog.ts`**

```typescript
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useOptimizeCatalog(channelCode: string) {
  return useMutation({
    mutationFn: (sellingModel: SellingModel) =>
      pricingDeskApi.optimizeCatalog(channelCode, sellingModel),
  });
}

export function useApplyOptimization(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sellingModel: SellingModel) =>
      pricingDeskApi.applyOptimization(channelCode, sellingModel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}
```

- [ ] **2.8 Verificar tsc**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep -E "pricing-desk|hooks/pricing" | head -20
```

- [ ] **2.9 Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/pricing-desk.ts mt-pricing-frontend/lib/hooks/pricing-desk/
git commit -m "feat(pricing-desk): API wrapper + React Query hooks for 13 endpoints"
```

---

## Task 3: Componente NumericStepper compartido

**Files:**
- Create: `mt-pricing-frontend/components/data/numeric-stepper.tsx`

Stepper -/+ con casilla editable. Reutilizado para márgenes, parámetros de coste, etc.

- [ ] **3.1 Crear el componente**

```tsx
// mt-pricing-frontend/components/data/numeric-stepper.tsx
"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface NumericStepperProps {
  value: number;
  onChange: (newValue: number) => void;
  min?: number;
  max?: number;
  step?: number;
  decimals?: number;
  suffix?: string;
  className?: string;
  size?: "sm" | "md";
  "aria-label"?: string;
  /** When true, paints the stepper in MT-warning amber (indicates modified/user-edited). */
  modified?: boolean;
  disabled?: boolean;
}

export function NumericStepper({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  decimals = 0,
  suffix = "",
  className,
  size = "md",
  modified = false,
  disabled = false,
  "aria-label": ariaLabel,
}: NumericStepperProps) {
  const [draftText, setDraftText] = useState(value.toFixed(decimals));

  useEffect(() => {
    setDraftText(value.toFixed(decimals));
  }, [value, decimals]);

  const commit = (raw: string) => {
    const clean = raw.replace(",", ".").replace(suffix, "").trim();
    const parsed = parseFloat(clean);
    if (Number.isNaN(parsed)) {
      setDraftText(value.toFixed(decimals));
      return;
    }
    const clamped = Math.max(min, Math.min(max, parsed));
    onChange(clamped);
  };

  const bump = (direction: 1 | -1) => {
    const next = +(value + direction * step).toFixed(decimals);
    const clamped = Math.max(min, Math.min(max, next));
    onChange(clamped);
  };

  const sizeClasses = {
    sm: { button: "h-6 w-5 text-xs", input: "h-6 w-12 text-xs" },
    md: { button: "h-7 w-6 text-sm", input: "h-7 w-16 text-sm" },
  }[size];

  const colorClasses = modified
    ? "border-mt-warning-border bg-mt-warning-soft text-mt-warning"
    : "border-mt-border bg-white text-mt-ink";

  return (
    <div
      className={cn(
        "inline-flex items-center overflow-hidden rounded-md border",
        colorClasses,
        disabled && "opacity-50",
        className,
      )}
      role="spinbutton"
      aria-label={ariaLabel}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
    >
      <button
        type="button"
        onClick={() => bump(-1)}
        disabled={disabled || value <= min}
        className={cn(
          "border-r font-bold transition",
          modified ? "border-mt-warning-border bg-mt-warning hover:bg-mt-warning-deep text-white"
                   : "border-mt-border bg-mt-brand hover:bg-mt-brand-deep text-white",
          sizeClasses.button,
          "disabled:opacity-30",
        )}
        aria-label="decrement"
      >
        −
      </button>
      <input
        type="text"
        value={draftText + (suffix && !draftText.endsWith(suffix) ? suffix : "")}
        onChange={(e) => setDraftText(e.target.value.replace(suffix, ""))}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        disabled={disabled}
        className={cn(
          "mt-tnum border-0 text-center font-semibold focus:outline-none focus:ring-2 focus:ring-mt-brand-soft",
          sizeClasses.input,
        )}
      />
      <button
        type="button"
        onClick={() => bump(1)}
        disabled={disabled || value >= max}
        className={cn(
          "border-l font-bold transition",
          modified ? "border-mt-warning-border bg-mt-warning hover:bg-mt-warning-deep text-white"
                   : "border-mt-border bg-mt-brand hover:bg-mt-brand-deep text-white",
          sizeClasses.button,
          "disabled:opacity-30",
        )}
        aria-label="increment"
      >
        +
      </button>
    </div>
  );
}
```

- [ ] **3.2 Verificar tsc**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "numeric-stepper" | head -5
```

- [ ] **3.3 Commit**

```bash
git add mt-pricing-frontend/components/data/numeric-stepper.tsx
git commit -m "feat(ui): NumericStepper component for pricing desk"
```

---

## Task 4: Layout y página principal con selector de canal/modelo

**Files:**
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/layout.tsx`
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/page.tsx`
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/_components/pricing-header.tsx`
- Create: `mt-pricing-frontend/app/(app)/pricing-desk/_components/signal-badge.tsx`

- [ ] **4.1 Crear `layout.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/layout.tsx
import type { ReactNode } from "react";

export default function PricingDeskLayout({ children }: { children: ReactNode }) {
  return <div className="flex h-full flex-col bg-mt-bg">{children}</div>;
}
```

- [ ] **4.2 Crear `_components/signal-badge.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/_components/signal-badge.tsx
import { cn } from "@/lib/utils";

const SIGNAL_STYLES: Record<string, { bg: string; text: string }> = {
  PÉRDIDA: { bg: "bg-mt-danger-soft", text: "text-mt-danger" },
  FRÁGIL: { bg: "bg-mt-warning-soft", text: "text-mt-warning" },
  FINO: { bg: "bg-amber-100", text: "text-amber-900" },
  ÓPTIMO: { bg: "bg-mt-success-soft", text: "text-mt-success" },
  EXCELENTE: { bg: "bg-mt-brand-soft", text: "text-mt-brand-deep" },
};

export function SignalBadge({ signal }: { signal: string }) {
  const style = SIGNAL_STYLES[signal] ?? { bg: "bg-gray-100", text: "text-gray-700" };
  return (
    <span
      className={cn(
        "mt-mono rounded px-2 py-0.5 text-[10px] font-bold tracking-wider",
        style.bg,
        style.text,
      )}
    >
      {signal}
    </span>
  );
}
```

- [ ] **4.3 Crear `_components/pricing-header.tsx`**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/_components/pricing-header.tsx
"use client";

import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  onChannelChange: (code: string) => void;
  sellingModel: SellingModel;
  onSellingModelChange: (m: SellingModel) => void;
}

const CHANNELS = [
  { code: "amazon_uae", label: "Amazon UAE", emoji: "🛒" },
  { code: "noon_uae", label: "Noon UAE", emoji: "🟡" },
];

const SELLING_MODELS: Array<{ value: SellingModel; label: string }> = [
  { value: "b2c", label: "B2C — por unidad" },
  { value: "b2b", label: "B2B — por caja" },
];

export function PricingHeader({
  channelCode,
  onChannelChange,
  sellingModel,
  onSellingModelChange,
}: Props) {
  return (
    <header className="mt-brand-stripe flex items-center gap-4 px-6 py-3 text-white">
      <div className="mt-mono text-xs uppercase tracking-widest text-mt-brand-soft opacity-80">
        MT Middle East · Pricing Intelligence
      </div>
      <h1 className="font-mt-sans text-lg font-bold tracking-wide">PRICING DESK</h1>
      <div className="ml-auto flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="mt-mono text-[10px] uppercase tracking-wider opacity-80">Canal</span>
          <select
            value={channelCode}
            onChange={(e) => onChannelChange(e.target.value)}
            className="mt-mono rounded border border-white/20 bg-white/10 px-2 py-1 text-sm font-medium text-white backdrop-blur-sm hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-white/40"
          >
            {CHANNELS.map((c) => (
              <option key={c.code} value={c.code} className="text-mt-ink">
                {c.emoji} {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="mt-mono text-[10px] uppercase tracking-wider opacity-80">Modelo</span>
          <select
            value={sellingModel}
            onChange={(e) => onSellingModelChange(e.target.value as SellingModel)}
            className="mt-mono rounded border border-white/20 bg-white/10 px-2 py-1 text-sm font-medium text-white backdrop-blur-sm hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-white/40"
          >
            {SELLING_MODELS.map((m) => (
              <option key={m.value} value={m.value} className="text-mt-ink">
                {m.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </header>
  );
}
```

- [ ] **4.4 Crear `page.tsx` (mínimo viable — sin tabla ni panel aún)**

```tsx
// mt-pricing-frontend/app/(app)/pricing-desk/page.tsx
"use client";

import { useState } from "react";
import { PricingHeader } from "./_components/pricing-header";
import { useCatalogSummary } from "@/lib/hooks/pricing-desk/use-catalog-summary";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

export default function PricingDeskPage() {
  const [channelCode, setChannelCode] = useState("amazon_uae");
  const [sellingModel, setSellingModel] = useState<SellingModel>("b2c");

  const { data, isLoading, error } = useCatalogSummary(channelCode, sellingModel, {});

  return (
    <>
      <PricingHeader
        channelCode={channelCode}
        onChannelChange={setChannelCode}
        sellingModel={sellingModel}
        onSellingModelChange={setSellingModel}
      />
      <main className="flex-1 overflow-auto p-6">
        {isLoading && <p className="text-mt-ink-3">Cargando catálogo…</p>}
        {error && (
          <p className="text-mt-danger">
            Error: {error instanceof Error ? error.message : "unknown"}
          </p>
        )}
        {data && (
          <div className="rounded border bg-white p-4">
            <p className="text-sm">
              <strong>Catálogo:</strong> {data.semaforo.total} productos · Publicables: {data.semaforo.publishable} · Bloqueados: {data.semaforo.blocked} · En pérdida: {data.semaforo.in_loss}
            </p>
          </div>
        )}
      </main>
    </>
  );
}
```

- [ ] **4.5 Verificar app arranca**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "pricing-desk" | head -10
```

Si todo compila, levantar el dev server brevemente y navegar a `/pricing-desk`:
```bash
docker restart mt-frontend && sleep 3 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/pricing-desk
```
Esperado: 200 (puede redirigir a login → 302 también es OK).

- [ ] **4.6 Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/pricing-desk/
git commit -m "feat(pricing-desk): scaffold page with channel + selling_model header"
```

---

## Task 5: Semáforo + filtros + tabla principal

**Files:**
- Create: `_components/semaforo.tsx`
- Create: `_components/filters-bar.tsx`
- Create: `_components/catalog-table.tsx`
- Modify: `page.tsx`

- [ ] **5.1 Crear `semaforo.tsx` (6 KPI cards)**

```tsx
// _components/semaforo.tsx
import { cn } from "@/lib/utils";
import type { CatalogSummary } from "@/lib/api/endpoints/pricing-desk";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  variant: "neutral" | "success" | "danger" | "warning" | "brand";
}

function KpiCard({ label, value, sub, variant }: KpiCardProps) {
  const dotColor = {
    neutral: "bg-mt-ink-4",
    success: "bg-mt-success",
    danger: "bg-mt-danger",
    warning: "bg-mt-warning",
    brand: "bg-mt-brand",
  }[variant];
  return (
    <div className="flex items-center gap-2 border-r border-mt-border-strong/30 bg-mt-ink/95 px-3 py-2 last:border-r-0">
      <div className={cn("h-8 w-1.5 rounded-sm", dotColor)} />
      <div className="min-w-0">
        <div className="mt-mono text-[9px] uppercase tracking-wider text-mt-ink-4">
          {label}
        </div>
        <div className="mt-mono text-lg font-bold leading-tight text-white">{value}</div>
        {sub && <div className="text-[10px] text-mt-ink-4">{sub}</div>}
      </div>
    </div>
  );
}

export function Semaforo({ summary }: { summary: CatalogSummary["semaforo"] }) {
  const byScheme = summary.by_scheme;
  return (
    <div className="sticky top-0 z-10 grid grid-cols-2 border-b-2 border-mt-brand md:grid-cols-3 lg:grid-cols-6">
      <KpiCard label="Catálogo" value={summary.total} sub="con precio" variant="brand" />
      <KpiCard label="Publicables" value={summary.publishable} sub="bajo el techo" variant="success" />
      <KpiCard label="Bloqueados" value={summary.blocked} sub="superan techo" variant="danger" />
      <KpiCard label="En pérdida" value={summary.in_loss} sub="margen neg." variant="warning" />
      <KpiCard
        label="Esquemas"
        value={`${byScheme.canal_full ?? 0}·${byScheme.canal_lastmile ?? 0}·${byScheme.merchant_managed ?? 0}`}
        sub="full·lastmile·merchant"
        variant="neutral"
      />
      <KpiCard label="Total productos" value={summary.total} sub="incluye no publicables" variant="brand" />
    </div>
  );
}
```

- [ ] **5.2 Crear `filters-bar.tsx`**

```tsx
// _components/filters-bar.tsx
"use client";

import { useMarginTargets } from "@/lib/hooks/pricing-desk/use-margin-targets";

interface Props {
  channelCode: string;
  familyId?: string;
  onFamilyChange: (id: string | undefined) => void;
  signal?: string;
  onSignalChange: (s: string | undefined) => void;
  totalShown: number;
  totalAll: number;
}

const SIGNALS = ["PÉRDIDA", "FRÁGIL", "FINO", "ÓPTIMO", "EXCELENTE"];

export function FiltersBar({
  channelCode,
  familyId,
  onFamilyChange,
  signal,
  onSignalChange,
  totalShown,
  totalAll,
}: Props) {
  const { data: targets } = useMarginTargets(channelCode);
  const families = targets ? Array.from(
    new Map(targets.map((t) => [t.family_id, t.family_name])).entries()
  ) : [];

  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-mt-border bg-white px-4 py-2">
      <label className="flex items-center gap-2">
        <span className="mt-mono text-[10px] uppercase tracking-wider text-mt-ink-3">Familia</span>
        <select
          value={familyId ?? ""}
          onChange={(e) => onFamilyChange(e.target.value || undefined)}
          className="rounded border border-mt-border bg-white px-2 py-1 text-sm text-mt-ink"
        >
          <option value="">Todas</option>
          {families.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className="mt-mono text-[10px] uppercase tracking-wider text-mt-ink-3">Señal</span>
        <select
          value={signal ?? ""}
          onChange={(e) => onSignalChange(e.target.value || undefined)}
          className="rounded border border-mt-border bg-white px-2 py-1 text-sm text-mt-ink"
        >
          <option value="">Todas</option>
          {SIGNALS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      {(familyId || signal) && (
        <button
          type="button"
          onClick={() => {
            onFamilyChange(undefined);
            onSignalChange(undefined);
          }}
          className="mt-mono rounded border border-mt-border bg-mt-surface-3 px-2 py-1 text-[10px] uppercase tracking-wider text-mt-brand-deep hover:bg-mt-ink hover:text-white"
        >
          ✕ Limpiar
        </button>
      )}

      <span className="mt-mono ml-auto text-xs text-mt-ink-3">
        Mostrando {totalShown} de {totalAll}
      </span>
    </div>
  );
}
```

- [ ] **5.3 Crear `catalog-table.tsx`**

```tsx
// _components/catalog-table.tsx
"use client";

import { useState } from "react";
import { NumericStepper } from "@/components/data/numeric-stepper";
import { SignalBadge } from "./signal-badge";
import type { CatalogSummary, SellingModel } from "@/lib/api/endpoints/pricing-desk";
import {
  useUpsertMarginOverride,
  useDeleteMarginOverride,
} from "@/lib/hooks/pricing-desk/use-margin-targets";

const SCHEME_LABEL: Record<string, string> = {
  canal_full: "Full",
  canal_lastmile: "Last-mile",
  merchant_managed: "Merchant",
};

const CHANNEL_SCHEMES: Record<string, string[]> = {
  amazon_uae: ["canal_full", "canal_lastmile", "merchant_managed"],
  noon_uae: ["canal_full", "merchant_managed"],
};

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
  rows: CatalogSummary["rows"];
}

export function CatalogTable({ channelCode, sellingModel, rows }: Props) {
  const upsertOverride = useUpsertMarginOverride(channelCode);
  const deleteOverride = useDeleteMarginOverride(channelCode);

  const handleMarginChange = (sku: string, newMargin: number) => {
    upsertOverride.mutate({
      sku,
      body: { margin_override_pct: newMargin, selling_model: sellingModel },
    });
  };

  return (
    <div className="overflow-auto border border-mt-border bg-white">
      <table className="mt-data-table w-full text-sm">
        <thead>
          <tr className="bg-mt-ink text-white">
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">SKU</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">Esquema</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Coste op.</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Techo</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">Margen</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Precio</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Benef./ud</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">ROI</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">Señal</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.sku}
              className={
                r.is_publishable
                  ? "border-b border-mt-border"
                  : "border-b border-mt-border bg-mt-danger-soft/30"
              }
            >
              <td className="mt-mono px-3 py-1.5 text-xs text-mt-brand-deep">{r.sku}</td>
              <td className="px-3 py-1.5 text-xs">
                <span className="mt-mono rounded bg-mt-brand-soft px-2 py-0.5 text-[10px] font-bold text-mt-brand-deep">
                  {r.scheme_label}
                </span>
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs">
                {r.cost_op_aed.toFixed(2)}
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs">
                {r.ceiling_aed?.toFixed(2) ?? "—"}
              </td>
              <td className="px-3 py-1.5">
                <NumericStepper
                  value={r.margin_pct}
                  onChange={(v) => handleMarginChange(r.sku, v)}
                  min={-10}
                  max={80}
                  step={1}
                  decimals={0}
                  suffix="%"
                  size="sm"
                  aria-label={`Margen de ${r.sku}`}
                />
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs font-semibold">
                {r.selling_price_aed?.toFixed(2) ?? "—"}
              </td>
              <td
                className={`mt-mono mt-tnum px-3 py-1.5 text-right text-xs font-semibold ${r.benefit_per_unit_aed < 0 ? "text-mt-danger" : "text-mt-success"}`}
              >
                {r.benefit_per_unit_aed > 0 ? "+" : ""}
                {r.benefit_per_unit_aed.toFixed(2)}
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs">
                {r.roi_pct.toFixed(0)}%
              </td>
              <td className="px-3 py-1.5">
                <SignalBadge signal={r.signal} />
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={9} className="px-3 py-6 text-center text-sm text-mt-ink-3">
                No hay productos con los filtros actuales.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **5.4 Actualizar `page.tsx` para integrar semáforo + filters + tabla**

```tsx
// app/(app)/pricing-desk/page.tsx
"use client";

import { useState } from "react";
import { PricingHeader } from "./_components/pricing-header";
import { Semaforo } from "./_components/semaforo";
import { FiltersBar } from "./_components/filters-bar";
import { CatalogTable } from "./_components/catalog-table";
import { useCatalogSummary } from "@/lib/hooks/pricing-desk/use-catalog-summary";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

export default function PricingDeskPage() {
  const [channelCode, setChannelCode] = useState("amazon_uae");
  const [sellingModel, setSellingModel] = useState<SellingModel>("b2c");
  const [familyId, setFamilyId] = useState<string | undefined>();
  const [signal, setSignal] = useState<string | undefined>();

  const { data, isLoading, error } = useCatalogSummary(
    channelCode,
    sellingModel,
    { familyId, signal },
  );

  return (
    <>
      <PricingHeader
        channelCode={channelCode}
        onChannelChange={(c) => {
          setChannelCode(c);
          setFamilyId(undefined);
          setSignal(undefined);
        }}
        sellingModel={sellingModel}
        onSellingModelChange={setSellingModel}
      />

      {data && <Semaforo summary={data.semaforo} />}

      <FiltersBar
        channelCode={channelCode}
        familyId={familyId}
        onFamilyChange={setFamilyId}
        signal={signal}
        onSignalChange={setSignal}
        totalShown={data?.rows.length ?? 0}
        totalAll={data?.semaforo.total ?? 0}
      />

      <main className="flex-1 overflow-auto px-4 pb-6">
        {isLoading && <p className="p-4 text-mt-ink-3">Cargando catálogo…</p>}
        {error && (
          <p className="p-4 text-mt-danger">
            Error: {error instanceof Error ? error.message : "unknown"}
          </p>
        )}
        {data && (
          <CatalogTable
            channelCode={channelCode}
            sellingModel={sellingModel}
            rows={data.rows}
          />
        )}
      </main>
    </>
  );
}
```

- [ ] **5.5 Verificar tsc y arrancar**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "pricing-desk" | head -10
docker restart mt-frontend && sleep 3 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/pricing-desk
```

- [ ] **5.6 Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/pricing-desk/
git commit -m "feat(pricing-desk): semaforo + filters + table with margin stepper"
```

---

## Task 6: Panel lateral con parámetros, márgenes por familia y optimización

**Files:**
- Create: `_components/side-panel.tsx`
- Create: `_components/cost-params-section.tsx`
- Create: `_components/family-margins-section.tsx`
- Create: `_components/optimize-section.tsx`
- Modify: `page.tsx`

- [ ] **6.1 Crear `cost-params-section.tsx`**

```tsx
"use client";

import { useState } from "react";
import { NumericStepper } from "@/components/data/numeric-stepper";
import {
  usePricingParams,
  useUpdateRouteParams,
  useUpdateFeeParams,
} from "@/lib/hooks/pricing-desk/use-pricing-params";

const ESCALONES = [
  {
    title: "1 · Compra a MT",
    params: [
      { key: "mt_discount_pct", label: "Descuento factura", source: "fee", pct: true, max: 50 },
      { key: "fx_rate", label: "Tipo cambio EUR→AED", source: "route", pct: false, step: 0.01, max: 6, decimals: 2 },
      { key: "fx_buffer_pct", label: "Colchón FX", source: "route", pct: true, max: 15 },
    ],
  },
  {
    title: "2 · Importación y almacén",
    params: [
      { key: "import_tariff_pct", label: "Arancel importación", source: "route", pct: true, max: 50 },
      { key: "local_warehouse_pct", label: "Almacén propio", source: "route", pct: true, max: 20 },
      { key: "handling_pct", label: "Manipulación", source: "route", pct: true, max: 20 },
      { key: "freight_rate_per_kg", label: "Flete €/kg", source: "route", pct: false, step: 0.1, decimals: 2, max: 50 },
      { key: "freight_min_aed", label: "Flete mínimo AED", source: "route", pct: false, step: 5, decimals: 0, max: 5000 },
    ],
  },
  {
    title: "3 · Comisiones del canal",
    params: [
      { key: "commission_pct", label: "Referral", source: "fee", pct: true, max: 30 },
      { key: "vat_pct", label: "IVA UAE", source: "fee", pct: true, max: 30 },
      { key: "advertising_pct", label: "Publicidad PPC", source: "fee", pct: true, max: 30 },
      { key: "returns_pct", label: "Devoluciones", source: "fee", pct: true, max: 15 },
    ],
  },
  {
    title: "4 · Logística del canal",
    params: [
      { key: "storage_multiplier", label: "Mult. almacén", source: "fee", pct: false, step: 0.1, decimals: 2, max: 5 },
    ],
  },
] as const;

export function CostParamsSection({ channelCode }: { channelCode: string }) {
  const { data: params } = usePricingParams(channelCode);
  const updateRoute = useUpdateRouteParams(channelCode);
  const updateFee = useUpdateFeeParams(channelCode);
  const [open, setOpen] = useState(true);

  if (!params) return null;

  const getValue = (key: string, source: "fee" | "route"): number => {
    const src = source === "fee" ? params.fees : params.route;
    return Number((src as Record<string, unknown>)[key] ?? 0);
  };

  const handleChange = (key: string, source: "fee" | "route", value: number) => {
    if (source === "fee") updateFee.mutate({ [key]: value });
    else updateRoute.mutate({ [key]: value });
  };

  return (
    <section className="border-b border-mt-border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between bg-mt-surface-2 px-3 py-2 text-left"
      >
        <span className="mt-mono text-xs font-semibold uppercase tracking-wider text-mt-ink">
          ⚙ Parámetros
        </span>
        <span className="text-xs text-mt-brand-deep">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="p-3">
          {ESCALONES.map((escalon) => (
            <div key={escalon.title} className="mb-3">
              <div className="mt-mono mb-2 rounded-r border-l-2 border-mt-brand bg-mt-brand-soft px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-mt-brand-deep">
                {escalon.title}
              </div>
              {escalon.params.map((p) => (
                <div key={p.key} className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="text-xs text-mt-ink-2">{p.label}</span>
                  <NumericStepper
                    value={getValue(p.key, p.source)}
                    onChange={(v) => handleChange(p.key, p.source, v)}
                    min={0}
                    max={p.max ?? 100}
                    step={p.step ?? 0.5}
                    decimals={p.decimals ?? 1}
                    suffix={p.pct ? "%" : ""}
                    size="sm"
                  />
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **6.2 Crear `family-margins-section.tsx`**

```tsx
"use client";

import { NumericStepper } from "@/components/data/numeric-stepper";
import {
  useMarginTargets,
  useUpsertMarginTarget,
} from "@/lib/hooks/pricing-desk/use-margin-targets";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

const PRESETS = [0, 15, 25, 40];

export function FamilyMarginsSection({ channelCode, sellingModel }: Props) {
  const { data: targets } = useMarginTargets(channelCode);
  const upsert = useUpsertMarginTarget(channelCode);

  const filtered = targets?.filter((t) => t.selling_model === sellingModel) ?? [];

  const handleChange = (familyId: string, value: number) => {
    upsert.mutate({
      family_id: familyId,
      selling_model: sellingModel,
      margin_target_pct: value,
    });
  };

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-3 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        Margen por familia
      </div>
      {filtered.length === 0 && (
        <p className="text-xs text-mt-ink-3">
          No hay márgenes objetivo configurados para este canal+modelo.
        </p>
      )}
      {filtered.map((t) => (
        <div key={t.id} className="mb-3">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-xs font-semibold text-mt-ink">{t.family_name}</span>
            <span className="mt-mono text-[10px] font-bold text-mt-brand-deep">
              {Number(t.margin_target_pct).toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <NumericStepper
              value={Number(t.margin_target_pct)}
              onChange={(v) => handleChange(t.family_id, v)}
              min={-10}
              max={80}
              step={1}
              decimals={0}
              suffix="%"
              size="sm"
            />
            <div className="flex gap-1">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => handleChange(t.family_id, p)}
                  className="mt-mono rounded border border-mt-border bg-white px-1.5 py-0.5 text-[10px] font-bold text-mt-brand-deep hover:bg-mt-ink hover:text-white"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **6.3 Crear `optimize-section.tsx`**

```tsx
"use client";

import { useState } from "react";
import {
  useApplyOptimization,
} from "@/lib/hooks/pricing-desk/use-optimize-catalog";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

export function OptimizeSection({ channelCode, sellingModel }: Props) {
  const applyOpt = useApplyOptimization(channelCode);
  const [confirming, setConfirming] = useState(false);

  const handleApply = () => {
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 4000);
      return;
    }
    applyOpt.mutate(sellingModel);
    setConfirming(false);
  };

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-3 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        Optimización
      </div>
      <button
        type="button"
        onClick={handleApply}
        disabled={applyOpt.isPending}
        className={
          "w-full rounded px-3 py-2 text-sm font-semibold text-white transition " +
          (confirming
            ? "bg-mt-warning hover:bg-mt-warning-deep"
            : "bg-mt-brand hover:bg-mt-brand-deep") +
          " disabled:opacity-50"
        }
      >
        {applyOpt.isPending
          ? "Aplicando…"
          : confirming
            ? "¿Confirmas? — pulsa de nuevo"
            : "★ Optimización completa"}
      </button>
      <p className="mt-2 text-[11px] leading-tight text-mt-ink-3">
        Para cada producto prueba todos los esquemas y el mejor margen bajo techo. Persiste como overrides.
      </p>
    </section>
  );
}
```

- [ ] **6.4 Crear `side-panel.tsx` wrapper**

```tsx
"use client";

import { CostParamsSection } from "./cost-params-section";
import { FamilyMarginsSection } from "./family-margins-section";
import { OptimizeSection } from "./optimize-section";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

export function SidePanel({ channelCode, sellingModel }: Props) {
  return (
    <aside className="mt-thin-scroll sticky top-0 flex h-[calc(100vh-3.5rem)] w-[320px] flex-col overflow-y-auto border-r border-mt-border bg-white">
      <CostParamsSection channelCode={channelCode} />
      <FamilyMarginsSection channelCode={channelCode} sellingModel={sellingModel} />
      <OptimizeSection channelCode={channelCode} sellingModel={sellingModel} />
    </aside>
  );
}
```

- [ ] **6.5 Actualizar `page.tsx` para mostrar el panel**

Modificar el `<main>` block:

```tsx
return (
  <>
    <PricingHeader ... />
    {data && <Semaforo summary={data.semaforo} />}
    <div className="flex flex-1 overflow-hidden">
      <SidePanel channelCode={channelCode} sellingModel={sellingModel} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <FiltersBar ... />
        <main className="flex-1 overflow-auto px-4 pb-6">
          ...
        </main>
      </div>
    </div>
  </>
);
```

Importar `SidePanel` y agregarlo al JSX.

- [ ] **6.6 Verificar tsc + smoke**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep "pricing-desk" | head -10
docker restart mt-frontend
```

- [ ] **6.7 Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/pricing-desk/
git commit -m "feat(pricing-desk): side panel with params, family margins, optimize action"
```

---

## Task 7: Tests E2E mínimos

**Files:**
- Create: `mt-pricing-frontend/tests/e2e/pricing-desk.spec.ts`

- [ ] **7.1 Leer la convención de tests E2E**

```bash
ls mt-pricing-frontend/tests/e2e/
cat mt-pricing-frontend/tests/e2e/$(ls mt-pricing-frontend/tests/e2e/ | head -1)
```

- [ ] **7.2 Crear el test E2E**

```typescript
// mt-pricing-frontend/tests/e2e/pricing-desk.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Pricing Desk", () => {
  test("loads and shows channel/selling_model selectors", async ({ page }) => {
    // login flow placeholder — adjust to project's auth helper
    await page.goto("/pricing-desk");

    // Header should be visible
    await expect(page.getByText("PRICING DESK")).toBeVisible();

    // Both selectors are present
    await expect(page.getByLabel(/canal/i)).toBeVisible();
    await expect(page.getByLabel(/modelo/i)).toBeVisible();
  });

  test("changing channel reloads the catalog", async ({ page }) => {
    await page.goto("/pricing-desk");
    const select = page.getByLabel(/canal/i);
    await select.selectOption("noon_uae");
    // The catalog re-fetches — wait for response to settle
    await page.waitForResponse(/\/api\/v1\/pricing\/noon_uae\/catalog/);
  });
});
```

- [ ] **7.3 Run the tests if e2e infra exists**

```bash
cd mt-pricing-frontend && pnpm playwright test pricing-desk.spec.ts 2>&1 | tail -10
```

Si la infra de auth no está montada, marcar `test.fixme` y commitear de todos modos.

- [ ] **7.4 Commit**

```bash
git add mt-pricing-frontend/tests/e2e/pricing-desk.spec.ts
git commit -m "test(pricing-desk): smoke E2E for channel/model selectors"
```

---

## Task 8: Verificación final y PR

- [ ] **8.1 Suite TypeScript completa**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | tail -5
```
Esperado: sin errores en pricing-desk.

- [ ] **8.2 Lint check**

```bash
cd mt-pricing-frontend && pnpm lint 2>&1 | grep -E "pricing-desk|numeric-stepper" | head -10
```

- [ ] **8.3 Build production**

```bash
cd mt-pricing-frontend && pnpm build 2>&1 | tail -20
```

- [ ] **8.4 Smoke test en navegador**

Abrir `http://localhost:3000/pricing-desk`, autenticarse, verificar:
- Header con selectores
- Semáforo con cifras
- Panel lateral con parámetros
- Tabla con productos
- Cambiar margen de un producto y ver actualizar el precio

- [ ] **8.5 Crear PR**

```bash
git push -u origin feat/pricing-desk-frontend
gh pr create --base main \
  --title "feat(pricing-desk): frontend Pricing Desk integrado en la app" \
  --body "$(cat <<'EOF'
## Summary

- Reemplaza el HTML standalone del Pricing Desk de Amazon UAE por una pantalla integrada en mt-pricing-frontend
- Selector de canal (Amazon UAE / Noon UAE) y modelo de venta (B2C / B2B) en el header
- Semáforo de 6 KPIs con conteo por esquema de fulfillment
- Tabla principal con filtros por familia y señal, stepper de margen por producto
- Panel lateral colapsable con parámetros de coste (4 escalones), márgenes objetivo por familia, y acción de optimización completa
- 13 endpoints del backend cubiertos via React Query hooks
- Componente `NumericStepper` reutilizable
- Tests E2E smoke con Playwright

## Test plan

- [ ] Navegar a `/pricing-desk` y verificar que carga la pantalla con Amazon UAE B2C por defecto
- [ ] Cambiar canal a Noon UAE — verificar que el catálogo se recarga
- [ ] Cambiar modelo a B2B — verificar que cambian los márgenes objetivo y precios
- [ ] Aplicar filtro por familia — verificar que la tabla y semáforo reflejan los productos filtrados
- [ ] Ajustar margen de un SKU con el stepper — verificar que precio y señal se actualizan
- [ ] Modificar el FX rate en el panel — verificar que toda la tabla se recalcula
- [ ] Cambiar margen objetivo de una familia — verificar que los productos sin override siguen el nuevo valor
- [ ] Pulsar "Optimización completa" dos veces — verificar persistencia de overrides
- [ ] `pnpm tsc --noEmit` sin errores
- [ ] `pnpm lint` sin errores nuevos
- [ ] `pnpm build` exitoso

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Checklist de cobertura del spec (sección 8)

| Req spec | Task | Estado |
|----------|------|--------|
| Selector canal + modelo en header | Task 4 | ✅ |
| Semáforo (6 indicadores) | Task 5 | ✅ |
| Tabla con stepper margen + selector esquema | Task 5 | ✅ |
| Filtros familia + señal | Task 5 | ✅ |
| Panel parámetros 4 escalones | Task 6 | ✅ |
| Márgenes por familia con presets | Task 6 | ✅ |
| Acción optimización completa | Task 6 | ✅ |
| Tests E2E smoke | Task 7 | ✅ |
| **Comparador 3 esquemas** (modal) | — | 📋 v2 |
| **Escenarios A/B con persistencia** | — | 📋 v2 |
| **Importación Excel desde UI** | — | 📋 v2 |
| **Exportación Excel** | — | 📋 v2 |

Las 4 funcionalidades marcadas v2 se abordan en un sprint siguiente (no son críticas para el primer release).
