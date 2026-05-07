---
title: "Frontend Technical Design — MT Middle East Fase 1"
status: "draft"
version: "1.0"
created: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
stack: "Next.js 16 App Router + React 19 + TS strict + Tailwind v4 + Shadcn (new-york) + Zod + Supabase + next-intl + Sentry"
related: ["ux-mockups-mt-pricing-mdm-phase1.md", "architecture-mt-pricing-mdm-phase1.md", "mt-users-module-design.md"]
---

# Frontend Technical Design — MT Middle East Fase 1

> Documento técnico del frontend `mt-pricing-frontend/` — Next.js 16 App Router + React 19 + TS strict + Tailwind v4 + Shadcn/ui (new-york) + Supabase Auth + next-intl + Sentry. Idioma de prosa: español; código en original.
>
> Inputs:
>
> - `_bmad-output/planning-artifacts/ux-mockups-mt-pricing-mdm-phase1.md` (27 pantallas + 6 flujos + componentes Shadcn).
> - `_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md` v1.4 (§22.1 estructura, §13 i18n, §15 RBAC).
> - `_bmad-output/planning-artifacts/mt-users-module-design.md` v1.1 (Auth + RBAC + JWT firmado con permisos).
> - `_bmad-output/planning-artifacts/reuse-from-hppt-iom.md` (patrones BR Innovation: AuthProvider, BroadcastChannel, sliding session, withPermissionAuth).

---

## Tabla de contenidos

1. [Filosofía y principios](#1-filosofia-y-principios)
2. [Estructura de carpetas](#2-estructura-de-carpetas)
3. [Data fetching strategy](#3-data-fetching-strategy)
4. [State management](#4-state-management)
5. [Forms strategy](#5-forms-strategy)
6. [Routing patterns](#6-routing-patterns)
7. [Auth integration](#7-auth-integration)
8. [i18n](#8-i18n)
9. [Performance](#9-performance)
10. [Testing strategy](#10-testing-strategy)
11. [Patrones de código](#11-patrones-de-codigo)
12. [Error handling](#12-error-handling)
13. [Observability frontend](#13-observability-frontend)
14. [Accesibilidad](#14-accesibilidad)
15. [Build + deploy](#15-build-deploy)
16. [Decisiones explícitas (resumen)](#16-decisiones-explicitas-resumen)
17. [TODOs](#17-todos)

---

## 1. Filosofía y principios

Premisas que gobiernan cada decisión posterior. Si un patrón viola alguna de éstas, se rechaza.

1. **Server Components por default**. La default mental del desarrollador es escribir un Server Component (`async function Page()`). Sólo se promueve a Client Component cuando hay (a) interactividad real (`onClick`, `onChange`, focus, drag), (b) browser APIs (`window`, `localStorage`, `IntersectionObserver`), (c) forms con validación cliente (react-hook-form), (d) hooks que requieren render dinámico (`useState`, `useEffect`, `useSyncExternalStore`). Justificación: la app es un panel interno con tablas masivas (224 → 50k SKUs); el coste de hidratar todo en cliente es prohibitivo. Server Components mantienen el bundle pequeño y trasladan el peso del fetch al edge cercano a Postgres.

2. **Server Actions como API primaria para mutations**. Forms y botones que escriben pasan por Server Actions (`"use server"`). Route Handlers (`app/api/`) sólo se usan para webhooks (Sentry tunnel, Supabase Storage callbacks) y health checks. Justificación: Server Actions le dan al desarrollador un único modelo mental (función tipada) en lugar de la dualidad cliente-fetch + endpoint-handler; integran trivialmente con `revalidatePath`/`revalidateTag` y heredan auth via cookies sin handshakes adicionales.

3. **TypeScript estricto**. `tsconfig.json` con `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`, `noFallthroughCasesInSwitch: true`, `noImplicitOverride: true`. Justificación: el dominio de pricing trabaja con dinero; un `undefined` que se cuela en una multiplicación produce una propuesta NaN AED y rompe la regla "no aprobado no integra". Pagamos el coste de tipar a cambio de prevenir bugs financieros.

4. **A11y first**. Target WCAG 2.1 AA. Todos los componentes interactivos heredan de Radix (vía Shadcn) que ya implementa ARIA roles, focus trap, keyboard navigation. axe-playwright en CI sobre los 5-10 user journeys críticos para evitar regresiones.

5. **Density-first UI**. Padding `px-2 py-1.5`, fuente `text-xs` con `font-feature-settings: "tnum"` para tabulares, alturas de fila 36 px, sin hero gigante en pantallas operativas. La UX del Comercial Canal Online optimiza por escaneo de 224+ filas, no por estética. Conscientemente sacrificamos "respiración" por densidad de información.

6. **Cmd-K omnipresente + keyboard shortcuts ricos**. Cada pantalla expone shortcuts contextual (ver `?` global). Cmd-K es entrada universal: SKU, propuesta, configuración, audit, jump-to-row, "abrir en drawer". Justificación: el usuario pasa horas en pantalla — cada click ahorrado es ROI directo.

7. **Single source of truth para tipos**: el OpenAPI del backend FastAPI (`mt-api-contract-openapi.yaml`) genera los tipos TS del cliente HTTP. Si el backend cambia un campo, el frontend rompe el build en CI.

---

## 2. Estructura de carpetas

> **Nota de divergencia con `architecture-mt-pricing-mdm-phase1.md` §22.1.** La arquitectura propuso `src/app/[locale]/...` con prefijo de URL. Esta tech-design adopta el plan UX (selector de idioma persistido en cookie, **sin prefijo de URL en Fase 1**) para mantener URLs limpias y deep-links estables en el panel interno; la activación del prefijo `/[locale]/` se difiere a Fase 2 si entra el storefront público (ver TODO 1). Resto del árbol queda alineado.

```
mt-pricing-frontend/
├── app/                                  # Next.js 16 App Router (root no [locale] en Fase 1)
│   ├── (auth)/                           # Layout group SIN shell autenticado
│   │   ├── login/
│   │   │   └── page.tsx
│   │   ├── reset-password/
│   │   │   └── page.tsx
│   │   ├── update-password/
│   │   │   └── page.tsx                  # Forced rotation flow (first-login)
│   │   └── layout.tsx                    # Layout minimal centrado (logo + card)
│   ├── (app)/                            # Layout group CON shell autenticado
│   │   ├── dashboard/
│   │   │   └── page.tsx                  # Dashboard rol-aware
│   │   ├── catalogo/
│   │   │   ├── page.tsx                  # Lista SKUs (DataTable virtual)
│   │   │   ├── @drawer/                  # Parallel route: drawer detalle SKU
│   │   │   │   └── (.)[sku]/page.tsx     # Intercepting: abre como drawer
│   │   │   ├── nuevo/
│   │   │   │   └── page.tsx              # Wizard alta SKU
│   │   │   └── [sku]/                    # Detalle SKU (full page deep-link)
│   │   │       ├── page.tsx              # Redirect a tab por default
│   │   │       ├── ficha-tecnica/
│   │   │       │   └── page.tsx
│   │   │       ├── imagenes/
│   │   │       │   └── page.tsx
│   │   │       ├── costes/
│   │   │       │   └── page.tsx
│   │   │       ├── precios/
│   │   │       │   └── page.tsx
│   │   │       ├── traducciones/
│   │   │       │   └── page.tsx
│   │   │       ├── audit/
│   │   │       │   └── page.tsx
│   │   │       └── layout.tsx            # Tabs persistentes
│   │   ├── proveedores/
│   │   │   ├── page.tsx
│   │   │   └── [supplier_id]/page.tsx
│   │   ├── precios/
│   │   │   ├── cola-aprobacion/
│   │   │   │   └── page.tsx              # Solo gerente_comercial
│   │   │   ├── simulador/
│   │   │   │   └── page.tsx              # What-if calculator
│   │   │   ├── bulk/
│   │   │   │   └── page.tsx              # Bulk operations on selection
│   │   │   ├── mis-propuestas/
│   │   │   │   └── page.tsx              # Comercial own proposals
│   │   │   └── page.tsx
│   │   ├── canales/
│   │   │   ├── page.tsx
│   │   │   └── [channel_id]/page.tsx     # shadow-publish + esquemas
│   │   ├── importer/
│   │   │   ├── page.tsx                  # Importer hub
│   │   │   ├── pim/page.tsx
│   │   │   ├── costes/page.tsx
│   │   │   ├── traducciones/page.tsx
│   │   │   └── runs/[run_id]/page.tsx    # Detalle ejecución (poll progress)
│   │   ├── auditoria/
│   │   │   ├── page.tsx                  # Audit timeline + filtros
│   │   │   └── [event_id]/page.tsx
│   │   ├── admin/
│   │   │   ├── usuarios/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [user_id]/page.tsx
│   │   │   ├── roles/
│   │   │   │   └── page.tsx
│   │   │   ├── jobs/
│   │   │   │   └── page.tsx              # job_definitions UI (Beat editable)
│   │   │   ├── canales/
│   │   │   │   └── page.tsx              # Channel master config
│   │   │   ├── reglas-excepcion/
│   │   │   │   └── page.tsx
│   │   │   └── monedas/
│   │   │       └── page.tsx              # FX cron + overrides
│   │   ├── chatbot/                      # Fase 2.5+ shell (placeholder Fase 1)
│   │   │   └── page.tsx
│   │   ├── mi-cuenta/
│   │   │   └── page.tsx
│   │   └── layout.tsx                    # Sidebar + topbar + AuthProvider boundary
│   ├── api/                              # SOLO webhooks + health
│   │   ├── health/
│   │   │   └── route.ts                  # GET /api/health (proxied to /healthz prod)
│   │   ├── web-vitals/
│   │   │   └── route.ts                  # POST sink Web Vitals (Fase 1.5)
│   │   └── webhooks/
│   │       └── sentry/route.ts           # Sentry tunnel (CSP-friendly)
│   ├── auth/
│   │   └── callback/route.ts             # Supabase magic-link / OAuth callback
│   ├── layout.tsx                        # Root layout: Providers (Theme, AuthProvider, Toaster, NextIntl)
│   ├── globals.css                       # Tailwind v4 directives + CSS vars Shadcn
│   ├── not-found.tsx                     # 404 global
│   ├── error.tsx                         # Global error boundary (catch render errors)
│   └── global-error.tsx                  # Last resort (root layout error)
├── components/
│   ├── ui/                               # Shadcn copy-paste (no edit unless intentional)
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── form.tsx
│   │   ├── data-table.tsx                # base de TanStack Table
│   │   ├── command.tsx
│   │   ├── sheet.tsx
│   │   ├── dialog.tsx
│   │   ├── drawer.tsx
│   │   ├── tabs.tsx
│   │   ├── select.tsx
│   │   ├── combobox.tsx
│   │   ├── tooltip.tsx
│   │   ├── popover.tsx
│   │   ├── badge.tsx
│   │   ├── skeleton.tsx
│   │   ├── alert.tsx
│   │   ├── alert-dialog.tsx
│   │   ├── progress.tsx
│   │   ├── sonner.tsx                    # Toaster
│   │   └── ...
│   ├── shell/
│   │   ├── sidebar.tsx                   # Server Component (nav items rol-aware)
│   │   ├── topbar.tsx                    # Mixed: bell + locale + user-menu (client)
│   │   ├── command-palette.tsx           # Client (cmdk + Zustand)
│   │   └── shortcut-sheet.tsx            # Drawer "?" con tabla de shortcuts
│   ├── auth/
│   │   ├── auth-provider.tsx             # Client: hidrata user + cross-tab sync (BroadcastChannel)
│   │   ├── rbac-guard.tsx                # Declarativo: <RbacGuard permissions={...}>
│   │   ├── force-logout-listener.tsx     # Client: Supabase Realtime → re-fetch JWT
│   │   └── login-form.tsx
│   ├── data/
│   │   ├── data-table.tsx                # TanStack Table v8 + virtual + Shadcn
│   │   ├── pagination.tsx
│   │   ├── column-visibility-toggle.tsx
│   │   ├── filters-drawer.tsx
│   │   └── bulk-actions-bar.tsx
│   ├── forms/                            # Form primitives reutilizables
│   │   ├── form-field-text.tsx
│   │   ├── form-field-select.tsx
│   │   ├── form-field-combobox-async.tsx
│   │   ├── form-field-currency.tsx
│   │   ├── form-field-checkbox.tsx
│   │   ├── form-field-textarea-i18n.tsx  # Toggle EN/ES/AR + RTL auto
│   │   ├── form-actions.tsx              # Submit + Cancel + dirty-state warn
│   │   └── submit-button.tsx
│   ├── domain/                           # Componentes específicos del dominio MT
│   │   ├── price-cell.tsx                # Renderiza price con FX tooltip + diff vs proposed
│   │   ├── currency-input.tsx            # Input AED/EUR con masked + Intl.NumberFormat
│   │   ├── fx-display.tsx                # Tooltip con as_of + source + rate
│   │   ├── channel-state-badge.tsx       # active|shadow|paused|error
│   │   ├── translation-status-pill.tsx   # 3 dots EN/ES/AR
│   │   ├── alert-severity-icon.tsx       # critical|warn|info
│   │   ├── breakdown-table.tsx           # Cost breakdown por componente
│   │   ├── audit-timeline.tsx            # Timeline vertical con diffs
│   │   ├── diff-viewer.tsx               # JSON diff before/after
│   │   ├── image-uploader-with-mirror.tsx # Upload + probe + mirror Storage
│   │   ├── import-preview-table.tsx      # Diff preview pre-apply
│   │   ├── exception-rule-editor.tsx
│   │   └── data-quality-badge.tsx
│   ├── layouts/
│   │   ├── page-header.tsx               # Title + breadcrumb + actions
│   │   ├── tabbed-layout.tsx
│   │   └── empty-state.tsx
│   └── icons/
│       └── index.ts                      # Re-export Lucide + custom svgs
├── lib/
│   ├── supabase/
│   │   ├── client.ts                     # createBrowserClient (Client Components)
│   │   ├── server.ts                     # createServerClient cookies (RSC + Server Actions)
│   │   ├── middleware.ts                 # createMiddlewareClient (edge)
│   │   └── admin.ts                      # service-role (solo server actions privilegiadas)
│   ├── api/                              # Cliente HTTP tipado (genera de OpenAPI)
│   │   ├── client.ts                     # openapi-fetch instance + auth interceptor
│   │   ├── types.ts                      # Generado por openapi-typescript (CI)
│   │   ├── errors.ts                     # ApiError, problem+json parser
│   │   └── endpoints/                    # Wrappers tipados por dominio
│   │       ├── products.ts
│   │       ├── prices.ts
│   │       ├── costs.ts
│   │       ├── audit.ts
│   │       ├── channels.ts
│   │       ├── imports.ts
│   │       ├── jobs.ts
│   │       └── users.ts
│   ├── i18n/
│   │   ├── config.ts                     # locales = ['es','en'], default 'es'
│   │   ├── request.ts                    # next-intl getRequestConfig (cookie-based)
│   │   └── formatters.ts                 # currency, date, number per locale + AED/EUR
│   ├── hooks/
│   │   ├── use-user.ts                   # AuthContext consumer
│   │   ├── use-permissions.ts            # hasPermission/hasAny/hasAll
│   │   ├── use-cmd-k.ts                  # Open command palette + register shortcut
│   │   ├── use-debounce.ts
│   │   ├── use-keyboard-shortcuts.ts     # Map j/k/e/Esc/Cmd-Enter
│   │   ├── use-table-state.ts            # nuqs sync sort/filters/pagination
│   │   ├── use-realtime-job.ts           # Supabase Realtime subscription job_runs
│   │   └── use-optimistic-mutation.ts    # TanStack Query wrapper
│   ├── stores/                           # Zustand
│   │   ├── ui-store.ts                   # sidebar collapsed, theme, drawer open
│   │   ├── command-palette-store.ts      # open + scope + query
│   │   └── selection-store.ts            # bulk selection persistente entre paginations
│   ├── utils/
│   │   ├── cn.ts                         # className helper (clsx + tailwind-merge)
│   │   ├── format.ts                     # formatCurrency(aed, locale), formatDate, etc.
│   │   ├── validation.ts                 # Zod schemas comunes (sku, dn, pn, currency)
│   │   ├── permissions.ts                # PERMISSIONS const + helpers
│   │   ├── url.ts                        # encode/decode filtros
│   │   └── arabic-detect.ts              # ¿el string contiene árabe? → dir="rtl"
│   ├── server-actions/                   # Server actions por dominio
│   │   ├── _wrappers.ts                  # withAuth + withPermissions HOFs
│   │   ├── products.ts                   # createProduct, updateProduct, archiveProduct
│   │   ├── prices.ts                     # proposePrice, approvePrice, rejectPrice
│   │   ├── costs.ts
│   │   ├── translations.ts
│   │   ├── images.ts                     # signedUploadUrl, mirrorImage
│   │   ├── imports.ts                    # startImport, abortImport
│   │   ├── exception-rules.ts
│   │   ├── jobs.ts                       # runNow, toggleActive, updateCron
│   │   └── users.ts                      # invite, assignRole (admin)
│   ├── env.ts                            # @t3-oss/env-nextjs runtime validation
│   ├── sentry.ts                         # init helpers
│   └── logger.ts                         # structured logger → /api/logs sink
├── messages/
│   ├── es.json
│   └── en.json
├── public/
│   ├── favicon.ico
│   └── fonts/                            # subset si self-host (default: next/font)
├── tests/
│   ├── e2e/                              # Playwright (5-10 journeys)
│   │   ├── auth.spec.ts
│   │   ├── catalog-create-sku.spec.ts
│   │   ├── pricing-propose-approve.spec.ts
│   │   ├── importer-pim.spec.ts
│   │   ├── simulator.spec.ts
│   │   └── a11y.spec.ts                  # axe-playwright
│   ├── unit/                             # Vitest
│   │   ├── utils/
│   │   ├── hooks/
│   │   └── server-actions/
│   ├── fixtures/
│   └── msw/
│       ├── handlers.ts
│       └── server.ts
├── playwright.config.ts
├── vitest.config.ts
├── next.config.ts                        # React Compiler on, PPR experimental: TODO
├── tailwind.config.ts                    # v4
├── components.json                       # Shadcn (new-york)
├── tsconfig.json                         # strict + noUncheckedIndexedAccess + exactOptionalPropertyTypes
├── eslint.config.mjs                     # next + jsx-a11y + no-console (prod)
├── package.json
├── pnpm-lock.yaml
├── Dockerfile                            # multi-stage (build + standalone)
├── .env.example
└── README.md
```

---

## 3. Data fetching strategy

### 3.1 Reglas de oro

| Caso | Mecanismo |
|------|-----------|
| Render inicial de una página con datos del backend | **Server Component** + `await fetchProducts(...)` con cliente OpenAPI tipado |
| Mutations (forms, button clicks) | **Server Action** (`"use server"`) — re-valida con `revalidatePath` o `revalidateTag` |
| Updates en background, polling, infinite scroll, optimistic UI con rollback | **TanStack Query v5** dentro de un Client Component |
| Webhooks externos (Sentry, Storage callbacks) | **Route Handler** `app/api/...` |
| Healthcheck | **Route Handler** `app/api/health/route.ts` |

### 3.2 Cliente OpenAPI tipado

El backend FastAPI publica `mt-api-contract-openapi.yaml`. CI corre:

```bash
pnpm openapi:generate   # openapi-typescript → lib/api/types.ts
```

Si la API cambia sin actualizar el contrato, el typecheck rompe el PR.

```ts
// lib/api/client.ts
import createClient from "openapi-fetch";
import type { paths } from "./types";
import { createServerClient } from "@/lib/supabase/server";

export async function getApiClient() {
  const supabase = await createServerClient();
  const { data: { session } } = await supabase.auth.getSession();
  return createClient<paths>({
    baseUrl: process.env.MT_API_BASE_URL!,
    headers: session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {},
  });
}

// lib/api/endpoints/products.ts
import { getApiClient } from "../client";
import type { components } from "../types";

export type Product = components["schemas"]["Product"];

export async function fetchProducts(params: {
  family?: string;
  q?: string;
  page?: number;
  limit?: number;
}): Promise<{ items: Product[]; total: number }> {
  const api = await getApiClient();
  const { data, error } = await api.GET("/api/v1/products", { params: { query: params } });
  if (error) throw new ApiError(error);
  return data;
}
```

### 3.3 Cache + revalidation

- Por default, los `fetch()` que dispara `openapi-fetch` van a la cache de Next con `revalidate: 0` para datos críticos (precios, propuestas) y tag-based para datos cuasi-estáticos (channels, currencies).
- Server actions invalidan via `revalidatePath('/catalogo')` o `revalidateTag('products')`.
- **Streaming + Suspense**: la lista de SKUs envuelve la `<DataTable>` en un `<Suspense fallback={<TableSkeleton />}>` para que el shell renderice primero.

### 3.4 Cuándo TanStack Query (Client Component)

Sólo si **uno de estos** aplica:

1. **Polling** (estado de un job, progreso de import, cola de FX). Usar `refetchInterval` con backoff dinámico (ver §11).
2. **Optimistic UI con rollback** (toggle active, edit price single SKU).
3. **Infinite scroll** (lista SKUs con `useInfiniteQuery` + TanStack Virtual).
4. **Updates por usuario rápidos** (typeahead remoto en Combobox de proveedores).

Nunca para "cargar la página". Eso siempre es Server Component.

---

## 4. State management

| Tipo de estado | Solución | Justificación |
|----------------|----------|---------------|
| **Server state** (datos del backend) | TanStack Query (cliente) + RSC fetch (server) | Server fetch para inicial; Query sólo cuando hay polling/optimistic. |
| **Client UI state** (sidebar collapsed, theme, drawer abierto, palette open) | **Zustand** stores en `lib/stores/` | Rendimiento (no re-renders de árbol), API minimal, sin boilerplate. |
| **Form state** | react-hook-form + Zod (resolver `@hookform/resolvers/zod`) | Standard de la industria; integra con Shadcn `<Form>`. |
| **URL state** (filtros tabla, sort, paginación, tab activo) | `useSearchParams` + **nuqs** | Deep-link de filtros, back/forward funcional, no se pierde estado al refrescar. |
| **Auth state** | AuthContext + `useUser()` hook | Único Context — datos verdaderamente globales. |
| **Selección bulk persistente entre páginas** | Zustand `selection-store` | Necesario en lista SKUs paginada con `Shift+Click`. |

**Prohibido**: Redux, Recoil, Jotai (overkill para los pocos estados verdaderamente globales). Context React queda restringido a Auth y Theme/i18n provider de next-intl.

---

## 5. Forms strategy

### 5.1 Stack

`react-hook-form@7` + `zod@3` + `@hookform/resolvers/zod` + Shadcn `<Form>` + Server Action para submit.

### 5.2 Patrón "form atom"

Cada form es un componente reusable que recibe `initialValues`, `mode: "create" | "edit"`, y `onSubmit` (un Server Action). Ejemplo simplificado en §11.4.

### 5.3 Schema compartido

El mismo Zod schema se usa para validación cliente (vía resolver) **y** dentro del Server Action (defense in depth). Si el backend tiene validación más estricta (Pydantic), el Server Action propaga el `422` como error de campo.

### 5.4 Optimistic UI

Mutations frecuentes (toggle active, edit price single, archive SKU) usan `useOptimisticMutation` (wrapper sobre TanStack Query) con rollback automático ante error.

### 5.5 File uploads

Patrón signed URL para imágenes y datasheets (Supabase Storage):

1. Server Action `getSignedUploadUrl({ filename, contentType })` → devuelve URL firmada.
2. Client sube directo a Storage con XHR (para `progress` + `cancel`).
3. Al completar, Server Action `confirmUpload({ key, sku, kind })` registra en DB y dispara probe + mirror.

### 5.6 Defense in depth obligatoria

Server Action **siempre** revalida con Zod incluso si el cliente ya validó. Nunca confiar en el cliente.

---

## 6. Routing patterns

### 6.1 Layout groups

- `(auth)` — login, reset, update-password. Layout minimal.
- `(app)` — todas las rutas autenticadas. Layout con sidebar + topbar + AuthProvider.

### 6.2 Parallel routes

`app/(app)/catalogo/@drawer/...` permite mostrar el detalle del SKU como Drawer **encima** de la lista sin perder la URL ni el estado de filtros. Combinado con interceptación.

### 6.3 Intercepting routes

`app/(app)/catalogo/(.)[sku]/page.tsx` intercepta el clic desde la lista y renderiza el detalle como Drawer. El **deep-link** `/catalogo/MTV-1004` sigue funcionando como página standalone (mismo `[sku]/page.tsx` ruta canónica).

### 6.4 Loading / error / not-found por segmento

Cada segmento crítico expone:

- `loading.tsx` con Skeleton apropiado (tabla → 20 filas skeleton, detalle → tabs skeleton).
- `error.tsx` con retry + Sentry capture.
- `not-found.tsx` cuando aplica (SKU inexistente).

### 6.5 Middleware

`middleware.ts` (Edge runtime) hace tres cosas en orden:

1. **Refresh de sesión Supabase** vía `@supabase/ssr` (necesario para que `getUser()` en RSC vea cookies actualizadas).
2. **Auth gate**: si la ruta no es pública (`/login`, `/auth/callback`, `/api/health`) y no hay sesión → redirect a `/login?next=...`.
3. **Sliding inactivity** (heredado de hppt-iom): cookie `mt-last-activity` se actualiza en cada request; si supera `idle_timeout_minutes` (config en `system_settings`), `signOut` + redirect a `/login?reason=idle`.
4. **First-login forced rotation**: si `user.user_metadata.requires_password_reset === true` y la ruta no es `/update-password`, redirect.

---

## 7. Auth integration

### 7.1 Clientes Supabase

Tres factories (`@supabase/ssr`):

```ts
// lib/supabase/server.ts (RSC + Server Actions)
import { createServerClient as createSSRClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { env } from "@/lib/env";

export async function createServerClient() {
  const cookieStore = await cookies();
  return createSSRClient(env.NEXT_PUBLIC_SUPABASE_URL, env.NEXT_PUBLIC_SUPABASE_ANON_KEY, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll: (toSet) => {
        try { toSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options)); }
        catch { /* ignored in pure RSC */ }
      },
    },
  });
}

// lib/supabase/client.ts (Client Components)
import { createBrowserClient } from "@supabase/ssr";
import { env } from "@/lib/env";

export const supabaseBrowser = () =>
  createBrowserClient(env.NEXT_PUBLIC_SUPABASE_URL, env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
```

`lib/supabase/admin.ts` expone un cliente service-role; **sólo** se importa desde Server Actions explícitamente marcadas (asignar rol, listar usuarios, force-logout). Nunca desde cliente.

### 7.2 AuthProvider

Hereda el patrón de `hppt-iom` (`AuthProvider.tsx` con cross-tab sync):

```tsx
// components/auth/auth-provider.tsx (Client)
"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";

type Ctx = { user: User | null; permissions: string[]; role: string | null; loading: boolean };
const AuthCtx = createContext<Ctx>({ user: null, permissions: [], role: null, loading: true });

export function AuthProvider({ initial, children }: { initial: Ctx; children: React.ReactNode }) {
  const [state, setState] = useState<Ctx>(initial);
  const sb = supabaseBrowser();

  useEffect(() => {
    const { data: sub } = sb.auth.onAuthStateChange((_event, session) => {
      const meta = (session?.user.app_metadata ?? {}) as { role?: string; permissions?: string[] };
      setState({
        user: session?.user ?? null,
        role: meta.role ?? null,
        permissions: meta.permissions ?? [],
        loading: false,
      });
    });
    // Cross-tab logout (BroadcastChannel pattern from hppt-iom)
    const bc = new BroadcastChannel("mt-auth");
    bc.onmessage = (e) => { if (e.data === "SIGNED_OUT") sb.auth.signOut({ scope: "local" }); };
    return () => { sub.subscription.unsubscribe(); bc.close(); };
  }, [sb]);

  return <AuthCtx.Provider value={state}>{children}</AuthCtx.Provider>;
}
export const useUser = () => useContext(AuthCtx);
```

`initial` se hidrata desde el Server Component padre (`app/(app)/layout.tsx`) que llama `supabase.auth.getUser()` y resuelve permisos del JWT (`app_metadata.permissions`, firmados por trigger `sync_user_app_metadata` — ver `mt-users-module-design.md` v1.1).

### 7.3 RbacGuard declarativo

```tsx
// components/auth/rbac-guard.tsx (Client)
"use client";
import { useUser } from "./auth-provider";

export function RbacGuard({
  permissions, mode = "all", fallback = null, children,
}: { permissions: string[]; mode?: "all" | "any"; fallback?: React.ReactNode; children: React.ReactNode }) {
  const { permissions: granted, loading } = useUser();
  if (loading) return null;
  const ok = mode === "all"
    ? permissions.every(p => granted.includes(p))
    : permissions.some(p => granted.includes(p));
  return ok ? <>{children}</> : <>{fallback}</>;
}
```

Para Server Components usar el equivalente síncrono `assertPermissions(['prices:approve'])` desde `lib/utils/permissions.ts` que lee `app_metadata` del JWT del usuario y lanza si falta.

### 7.4 Server Actions: permisos siempre

Todo Server Action escribirá pasa por wrapper:

```ts
// lib/server-actions/_wrappers.ts
import { createServerClient } from "@/lib/supabase/server";
export function withPermissions<T extends (...args: any[]) => Promise<any>>(
  required: string[], mode: "all" | "any", fn: T
): T {
  return (async (...args: Parameters<T>) => {
    const sb = await createServerClient();
    const { data: { user }, error } = await sb.auth.getUser();
    if (error || !user) throw new ActionError("UNAUTHENTICATED", "No session");
    const perms = (user.app_metadata?.permissions ?? []) as string[];
    const ok = mode === "all" ? required.every(p => perms.includes(p)) : required.some(p => perms.includes(p));
    if (!ok) throw new ActionError("FORBIDDEN", `Missing: ${required.join(",")}`);
    return fn(...args);
  }) as T;
}
```

### 7.5 Force-logout cuando cambia el rol

`mt-users-module-design.md` v1.1 fuerza `auth.admin.sign_out(user_id)` al revocar rol — cierra el lag del JWT (que dura hasta 1h sin revocación). En el cliente, `force-logout-listener.tsx` se suscribe a un canal Realtime `user_${user.id}` y, al recibir `force_logout`, llama `supabase.auth.refreshSession()` o redirige a `/login?reason=role-changed`.

---

## 8. i18n

### 8.1 Stack

`next-intl@3` con locales `es` (default) y `en`. Selector persistido en cookie `mt-locale` en topbar; **sin prefijo de URL en Fase 1** (URLs limpias para deep-linking de SKUs); activación de `/[locale]/` se difiere a Fase 2 si el storefront público entra en alcance.

### 8.2 Configuración

```ts
// lib/i18n/config.ts
export const locales = ["es", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";

// lib/i18n/request.ts
import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

export default getRequestConfig(async () => {
  const c = await cookies();
  const locale = (c.get("mt-locale")?.value ?? "es") as Locale;
  return { locale, messages: (await import(`@/messages/${locale}.json`)).default };
});
```

### 8.3 Locale-aware formatting

`lib/i18n/formatters.ts` envuelve `Intl.NumberFormat` y `Intl.DateTimeFormat`:

```ts
// lib/i18n/formatters.ts
export function formatCurrency(amount: number, currency: "AED" | "EUR", locale: Locale): string {
  return new Intl.NumberFormat(locale === "es" ? "es-ES" : "en-AE", {
    style: "currency", currency, currencyDisplay: "code",
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(amount);
}
```

Para AED en panel interno usamos `currencyDisplay: "code"` (renderiza `AED 142.00`) en lugar del símbolo unicode (que confunde a Comerciales acostumbrados al código).

### 8.4 Árabe como **contenido** (no como UI)

En Fase 1 la **UI es siempre LTR** (ES/EN). Sin embargo, los inputs de traducción (`name_ar`, `description_ar`) detectan automáticamente caracteres árabes y aplican `dir="rtl"` al `<input>` o `<textarea>` correspondiente:

```ts
// lib/utils/arabic-detect.ts
const ARABIC_RE = /[؀-ۿ]/;
export const containsArabic = (s: string): boolean => ARABIC_RE.test(s);
```

`<FormFieldTextareaI18n>` lee el valor y aplica `dir` dinámicamente.

### 8.5 Workflow de extracción

Strings en componentes vía `useTranslations("namespace")` o `getTranslations()` (RSC). Convención: namespaces por dominio (`catalog.list`, `pricing.proposal`, `auth.login`). En Fase 1.5+ integramos Crowdin **o** Lokalise (ver TODO 2) para que MT pueda revisar AR profesional sin tocar el repo.

### 8.6 Pluralización

`next-intl` soporta ICU. Reglas configuradas para EN y ES; AR queda como **contenido** (no se localiza la UI a AR en Fase 1).

---

## 9. Performance

### 9.1 React Compiler

`next.config.ts` habilita `experimental.reactCompiler: true`. Reduce el coste de `useMemo`/`useCallback` manuales y memoiza componentes — clave en DataTable virtual con 224+ filas.

### 9.2 Bundle analysis

`@next/bundle-analyzer` corre en CI con `pnpm build:analyze`. Budget: client bundle inicial < 200 KB gzip.

### 9.3 Imágenes

`next/image` con loader Supabase Storage. Las thumbs en lista de SKUs (28 px) se cachean agresivamente con `Cache-Control: public, max-age=31536000, immutable` (key con hash).

### 9.4 Fonts

`next/font/local` con **Geist Sans + Geist Mono** auto-hosted (tabular-nums activado para columnas de precio). Sin Google Fonts (privacidad + un dominio menos en CSP).

### 9.5 Code splitting

`next/dynamic` para componentes pesados:

- `<DataTable>` en lista SKUs (TanStack Table + Virtual + react-resizable).
- `<CommandPalette>` (cmdk + fuse.js).
- `<DiffViewer>` (json-source-map).
- `<ImageUploaderWithMirror>`.

### 9.6 PPR (Partial Prerendering)

Decisión Fase 1: **off por default**, evaluar en Fase 1.5 (ver TODO 3). Justificación: el shell autenticado depende de cookies → la mayor parte de páginas no se beneficia hasta que el shell estático y el dynamic boundary sean estables.

### 9.7 Lighthouse budgets (CI)

| Métrica | Budget |
|---------|--------|
| LCP | < 2.5 s |
| CLS | < 0.1 |
| TBT | < 200 ms |
| Bundle JS inicial | < 200 KB gzip |
| Total HTML+CSS+JS | < 1 MB |

---

## 10. Testing strategy

### 10.1 Pirámide

| Nivel | Stack | Cobertura | Lo que cubre |
|-------|-------|-----------|--------------|
| **Unit** | Vitest + jsdom | 70 % overall, 90 % en `lib/utils/` y `lib/server-actions/` | Funciones puras, hooks aislados, validators Zod |
| **Integration** | Vitest + RTL + MSW | 70 % en componentes domain | Forms + Server Actions mockeados (MSW), DataTable comportamiento |
| **E2E** | Playwright | 5-10 user journeys | Login → catálogo → proponer precio → aprobar → audit visible |
| **A11y** | axe-playwright | mismos journeys E2E | Sin violaciones críticas/serias |
| **Visual regression** | (opcional Fase 1.5) Chromatic o Playwright snapshots | Componentes Shadcn personalizados | TODO 4 |

### 10.2 Journeys E2E críticos (mínimo Fase 1)

1. Login + sesión persistida + logout cross-tab.
2. Crear SKU (wizard 3 pasos, validaciones).
3. Comercial propone precio → Gerente aprueba → audit visible.
4. Importer PIM (subir XLSX → preview diff → apply → ver en lista).
5. Simulador what-if (cambiar coste o margen → recalcular → comparar).
6. Cmd-K + atajos teclado en lista de SKUs.
7. RBAC: Comercial NO puede aprobar; Gerente SÍ.

### 10.3 Cobertura

`pnpm test:coverage` falla CI si overall < 70 %, `lib/utils/` < 90 %, `lib/server-actions/` < 90 %.

---

## 11. Patrones de código

### 11.1 Server action pattern (auth + validation + audit)

```ts
// lib/server-actions/prices.ts
"use server";
import { z } from "zod";
import { revalidatePath } from "next/cache";
import { withPermissions, ActionError } from "./_wrappers";
import { createServerClient } from "@/lib/supabase/server";
import { getApiClient } from "@/lib/api/client";
import * as Sentry from "@sentry/nextjs";

const ProposePriceSchema = z.object({
  sku: z.string().regex(/^MTV-\d{3,6}$/),
  channel_id: z.string().uuid(),
  scheme_id: z.string().uuid(),
  price_aed: z.number().positive().finite(),
  rationale: z.string().min(10).max(500),
});
export type ProposePriceInput = z.infer<typeof ProposePriceSchema>;

export const proposePrice = withPermissions(
  ["prices:propose"], "all",
  async (raw: unknown) => {
    const parsed = ProposePriceSchema.safeParse(raw);
    if (!parsed.success) throw new ActionError("VALIDATION", parsed.error.message, parsed.error.flatten());
    try {
      const api = await getApiClient();
      const { data, error } = await api.POST("/api/v1/prices/propose", { body: parsed.data });
      if (error) throw new ActionError("BACKEND", error.detail ?? "Backend error", error);
      revalidatePath("/precios/mis-propuestas");
      revalidatePath(`/catalogo/${parsed.data.sku}/precios`);
      return { ok: true as const, proposal_id: data.id };
    } catch (e) {
      Sentry.captureException(e, { tags: { action: "proposePrice", sku: parsed.data.sku } });
      throw e;
    }
  }
);
```

### 11.2 Server Component fetch + Suspense

```tsx
// app/(app)/catalogo/page.tsx
import { Suspense } from "react";
import { fetchProducts } from "@/lib/api/endpoints/products";
import { ProductsTable } from "@/components/domain/products-table";
import { TableSkeleton } from "@/components/data/table-skeleton";

export default async function CatalogPage({
  searchParams,
}: { searchParams: Promise<{ family?: string; q?: string; page?: string }> }) {
  const sp = await searchParams;
  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Catálogo" actions={<NewSkuButton />} />
      <Suspense fallback={<TableSkeleton rows={20} />}>
        <ProductsTableLoader family={sp.family} q={sp.q} page={Number(sp.page ?? 1)} />
      </Suspense>
    </div>
  );
}

async function ProductsTableLoader(props: { family?: string; q?: string; page: number }) {
  const data = await fetchProducts({ ...props, limit: 25 });
  return <ProductsTable initialData={data} />;
}
```

### 11.3 Client component con TanStack Query (polling job)

```tsx
// components/domain/import-run-progress.tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchImportRun } from "@/lib/api/endpoints/imports";

export function ImportRunProgress({ runId }: { runId: string }) {
  const q = useQuery({
    queryKey: ["import-run", runId],
    queryFn: () => fetchImportRun(runId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "succeeded" || status === "failed") return false;
      return status === "running" ? 1500 : 5000; // backoff inteligente
    },
    staleTime: 0,
  });
  if (q.isPending) return <Skeleton className="h-6 w-full" />;
  if (q.isError) return <Alert variant="destructive">{q.error.message}</Alert>;
  const { status, processed, total, errors } = q.data;
  return (
    <div className="space-y-2">
      <Progress value={(processed / total) * 100} />
      <p className="text-xs text-muted-foreground">
        {processed} / {total} · errors: {errors.length} · {status}
      </p>
    </div>
  );
}
```

### 11.4 Form pattern (RHF + Zod + Server Action)

```tsx
// components/domain/propose-price-form.tsx
"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTransition } from "react";
import { toast } from "sonner";
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { proposePrice, ProposePriceSchema, type ProposePriceInput } from "@/lib/server-actions/prices";

export function ProposePriceForm({ sku, channelId, schemeId, suggested }: {
  sku: string; channelId: string; schemeId: string; suggested: number;
}) {
  const [pending, start] = useTransition();
  const form = useForm<ProposePriceInput>({
    resolver: zodResolver(ProposePriceSchema),
    defaultValues: { sku, channel_id: channelId, scheme_id: schemeId, price_aed: suggested, rationale: "" },
  });

  const onSubmit = (values: ProposePriceInput) => start(async () => {
    try {
      const res = await proposePrice(values);
      toast.success(`Propuesta ${res.proposal_id} enviada`);
      form.reset();
    } catch (e: any) {
      if (e.code === "VALIDATION") {
        Object.entries(e.fields ?? {}).forEach(([k, v]) =>
          form.setError(k as keyof ProposePriceInput, { message: String(v) }));
      } else {
        toast.error(e.message ?? "Error inesperado");
      }
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField name="price_aed" control={form.control} render={({ field }) => (
          <FormItem>
            <FormLabel>Precio AED</FormLabel>
            <FormControl><Input type="number" step="0.01" {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <FormField name="rationale" control={form.control} render={({ field }) => (
          <FormItem>
            <FormLabel>Justificación</FormLabel>
            <FormControl><Textarea rows={3} {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <Button type="submit" disabled={pending}>Proponer</Button>
      </form>
    </Form>
  );
}
```

### 11.5 Optimistic UI pattern

```tsx
// hooks/use-toggle-active.ts
"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toggleProductActive } from "@/lib/server-actions/products";

export function useToggleActive(sku: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (next: boolean) => toggleProductActive({ sku, active: next }),
    onMutate: async (next) => {
      await qc.cancelQueries({ queryKey: ["product", sku] });
      const prev = qc.getQueryData<{ active: boolean }>(["product", sku]);
      qc.setQueryData(["product", sku], (old: any) => ({ ...old, active: next }));
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(["product", sku], ctx.prev); },
    onSettled: () => qc.invalidateQueries({ queryKey: ["product", sku] }),
  });
}
```

### 11.6 DataTable pattern

```tsx
// components/data/data-table.tsx (resumen)
"use client";
import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";

export function DataTable<T>({ columns, data, onRowClick }: {
  columns: ColumnDef<T>[]; data: T[]; onRowClick?: (row: T) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel(), enableRowSelection: true });
  const virt = useVirtualizer({
    count: table.getRowModel().rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 12,
  });
  return (
    <div ref={parentRef} className="overflow-auto h-full text-xs tabular-nums">
      <table className="w-full">
        <thead className="sticky top-0 bg-background z-10">
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id}>{hg.headers.map(h => (
              <th key={h.id} className="px-2 py-1.5 text-left font-medium">
                {flexRender(h.column.columnDef.header, h.getContext())}
              </th>
            ))}</tr>
          ))}
        </thead>
        <tbody style={{ height: virt.getTotalSize() }} className="relative">
          {virt.getVirtualItems().map(v => {
            const row = table.getRowModel().rows[v.index]!;
            return (
              <tr key={row.id}
                  className="absolute left-0 right-0 cursor-pointer hover:bg-accent"
                  style={{ transform: `translateY(${v.start}px)`, height: 36 }}
                  onClick={() => onRowClick?.(row.original)}>
                {row.getVisibleCells().map(c => (
                  <td key={c.id} className="px-2 py-1.5">
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

### 11.7 Cmd-K pattern

```tsx
// components/shell/command-palette.tsx
"use client";
import { useEffect } from "react";
import { Command, CommandDialog, CommandInput, CommandList, CommandItem, CommandGroup } from "@/components/ui/command";
import { useCommandPaletteStore } from "@/lib/stores/command-palette-store";
import { useRouter } from "next/navigation";

export function CommandPalette() {
  const { open, setOpen, scope, setScope, query, setQuery } = useCommandPaletteStore();
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setOpen(!open); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder={`Buscar ${scope}…`} value={query} onValueChange={setQuery} />
      <CommandList>
        <CommandGroup heading="Saltar a">
          <CommandItem onSelect={() => { router.push("/catalogo"); setOpen(false); }}>Catálogo</CommandItem>
          <CommandItem onSelect={() => { router.push("/precios/cola-aprobacion"); setOpen(false); }}>Cola aprobación</CommandItem>
        </CommandGroup>
        <CommandGroup heading="Acciones">
          <CommandItem onSelect={() => { router.push("/catalogo/nuevo"); setOpen(false); }}>+ Alta SKU</CommandItem>
        </CommandGroup>
        {/* Resultados dinámicos por scope (productos, propuestas, audit) — fetch debounced via use-debounce */}
      </CommandList>
    </CommandDialog>
  );
}
```

---

## 12. Error handling

### 12.1 Boundaries por segmento

`error.tsx` por segmento (`(app)/error.tsx`, `(app)/catalogo/error.tsx`) captura errores de render + data fetch. Cada uno:

1. Llama `Sentry.captureException(error)`.
2. Muestra UI amigable con request-id (extraído del header propagado por el backend).
3. Botón "Reintentar" → `reset()`.
4. Botón "Copiar request-id" para soporte.

### 12.2 Sentry React

`@sentry/nextjs` con sourcemaps subidos en CI (token Sentry en GitHub secrets). Tags por defecto: `user_id`, `role`, `route`, `action`. PII filtrado (email hasheado con SHA-256 antes de enviar).

### 12.3 Toasts (Sonner)

Errores recoverables (validación, conflict, optimistic rollback) → `toast.error()`. Éxitos → `toast.success()` con duration 2-3 s. Sin toasts para errores graves (esos van a modal con request-id).

### 12.4 Modal "algo salió mal"

Errores con HTTP 500/503 muestran un `<AlertDialog>` con copy específica + request-id seleccionable + botón "Reportar" que abre mailto a soporte con el id pre-rellenado.

### 12.5 Retry logic

TanStack Query default: `retry: 2` con `retryDelay: attempt => Math.min(1000 * 2 ** attempt, 10_000)`. Excluye 4xx (no retry). Server Actions sin retry automático (idempotencia no garantizada).

---

## 13. Observability frontend

### 13.1 Sentry

`@sentry/nextjs` con tracing 10 % sample en prod, 100 % en preview. Webhook tunnel via `app/api/webhooks/sentry/route.ts` para evitar bloqueo por adblockers.

### 13.2 Web Vitals

`reportWebVitals` envía a `/api/web-vitals` (Fase 1.5) → tabla `frontend_metrics` para análisis P75. Métricas: LCP, CLS, INP, TTFB.

### 13.3 Console logs prohibidos en prod

ESLint rule `no-console` con `allow: ["warn", "error"]`. CI rompe si hay `console.log`.

### 13.4 Structured logging

`lib/logger.ts` envía eventos importantes (login, logout, server-action error) a un sink en `app/api/logs/route.ts` que reenvía a Better Stack. Formato JSON con `request_id`, `user_id`, `event`, `payload`.

---

## 14. Accesibilidad

| Punto | Implementación |
|-------|----------------|
| WCAG 2.1 AA | axe-playwright en CI sobre journeys críticos |
| Focus visible | `:focus-visible` global con ring tematizado (Tailwind) |
| Skip links | `<a href="#main">Saltar al contenido</a>` en `(app)/layout.tsx` |
| aria-live | Sonner Toaster con `role="status" aria-live="polite"` |
| Color contrast | tokens Shadcn revisados con `pa11y-ci` opcional + Lighthouse |
| Keyboard navigation | Radix por debajo + tests E2E con `await page.keyboard.press(...)` |
| Forms | `<FormLabel htmlFor>` + `aria-describedby` para errores (Shadcn lo hace por default) |
| Tablas | `<th scope>` + `aria-sort` en headers ordenables |
| Iconos | Lucide con `aria-hidden="true"` cuando son decorativos |

---

## 15. Build + deploy

### 15.1 Build

```bash
pnpm build   # next build con output: 'standalone'
```

`next.config.ts` con `output: "standalone"` para que el Dockerfile copie sólo `.next/standalone` + `node_modules` mínimo.

### 15.2 Dockerfile (referencia, detalle en CI/CD doc)

Multi-stage:

1. `deps` — instala `pnpm` y dependencies con cache de `pnpm-lock.yaml`.
2. `builder` — `pnpm build` con todos los `NEXT_PUBLIC_*` inyectados como build args.
3. `runner` — `node:20-alpine`, usuario no-root, `CMD ["node", "server.js"]`, healthcheck en `/api/health`.

### 15.3 ENV variables tipadas

```ts
// lib/env.ts
import { createEnv } from "@t3-oss/env-nextjs";
import { z } from "zod";

export const env = createEnv({
  server: {
    MT_API_BASE_URL: z.string().url(),
    SENTRY_DSN: z.string().min(1),
    SUPABASE_SERVICE_ROLE_KEY: z.string().min(1),
  },
  client: {
    NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
    NEXT_PUBLIC_SUPABASE_ANON_KEY: z.string().min(1),
    NEXT_PUBLIC_SENTRY_DSN: z.string().min(1),
    NEXT_PUBLIC_APP_ENV: z.enum(["dev", "staging", "prod"]),
  },
  runtimeEnv: {
    MT_API_BASE_URL: process.env.MT_API_BASE_URL,
    SENTRY_DSN: process.env.SENTRY_DSN,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
    NEXT_PUBLIC_APP_ENV: process.env.NEXT_PUBLIC_APP_ENV,
  },
});
```

Falta de cualquier var en build → falla (`emptyStringAsUndefined: true` opcional para CI estricto).

---

## 16. Decisiones explícitas (resumen)

| # | Tópico | Decisión | Por qué |
|---|--------|----------|---------|
| 1 | State management | Server state: TanStack Query (cliente) + RSC fetch (server). Client UI state: Zustand. | Bundle pequeño en server, Zustand sin Context churn. |
| 2 | Forms | react-hook-form + Zod + Shadcn Form | Standard maduro; schema compartido cliente/server. |
| 3 | Data fetching | Server Components por default + Server Actions para mutations; TanStack Query sólo en client cuando hay polling/optimistic/infinite. | Default mental simple; menos JS al cliente. |
| 4 | API client | `openapi-typescript` (types) + `openapi-fetch` (runtime), generado en CI desde `mt-api-contract-openapi.yaml`. | Single source of truth; rompe build si backend cambia sin actualizar contrato. |
| 5 | URL state | nuqs (typed search params). | Deep-link de filtros sin `any`. |
| 6 | i18n | next-intl ES/EN; AR como contenido (no UI); cookie-based (sin URL prefix Fase 1). | URLs limpias, panel interno; activación de prefijo Fase 2 si entra storefront. |
| 7 | Routing | App Router + layout groups `(auth)`/`(app)` + parallel/intercepting routes para drawers deep-linkables. | Drawer encima de lista sin perder URL ni filtros. |
| 8 | Auth | `@supabase/ssr` middleware + AuthProvider client + RbacGuard declarativo + permisos firmados en JWT. | Heredado de hppt-iom (probado en producción). |
| 9 | Cmd-K | `cmdk` (Shadcn Command) + Zustand store. | Estándar de la industria; Zustand evita re-renders del provider. |
| 10 | Tables | TanStack Table v8 + TanStack Virtual + Shadcn DataTable shell. | Necesario para 224→50k SKUs. |
| 11 | Tests | Vitest (unit/integration) + Playwright (E2E) + axe-playwright (a11y). | Stack estándar Next 16 + cobertura financiera. |
| 12 | Sentry | `@sentry/nextjs` + sourcemaps en CI + tunnel webhook (anti-adblock). | Trazabilidad de errores con request-id. |
| 13 | Bundle | `@next/bundle-analyzer` + budget 200 KB gzip + `size-limit` en CI. | Prevención de regresiones de peso. |
| 14 | Optimistic UI | TanStack Query `onMutate`/`onError` (rollback) sólo en mutations frecuentes. | UX rápida sin riesgo de mostrar estado inconsistente. |
| 15 | Toasts | Sonner. | Default Shadcn; aria-live nativo. |
| 16 | Iconos | Lucide React. | Tree-shakeable; alineado con Shadcn. |
| 17 | TS config | strict + noUncheckedIndexedAccess + exactOptionalPropertyTypes + noImplicitOverride. | Prevenir bugs financieros (`undefined`/`NaN` en pricing). |
| 18 | ENV | `@t3-oss/env-nextjs` con Zod. | Build falla si falta var crítica. |
| 19 | File uploads | Signed URL Supabase Storage + XHR client (progress/cancel) + Server Action de confirm. | Bypass del proxy Caddy; control de progreso fino. |
| 20 | PPR | Off Fase 1; evaluar Fase 1.5. | Estabilidad primero; ROI bajo en panel autenticado. |
| 21 | Force-logout | Supabase Realtime → channel `user_${id}` → cliente refresca JWT o redirige. | Cierra lag de propagación al revocar rol. |
| 22 | Cross-tab sync | `BroadcastChannel("mt-auth")` para SIGNED_OUT. | Patrón hppt-iom validado. |

---

## 17. TODOs

Cosas que dudé y dejé sin decidir definitivamente. Cada una tiene un dueño sugerido y un timing.

1. **`/[locale]/` URL prefix Fase 2 sí/no** — Esta tech-design omite el prefijo en Fase 1 (UX reciente confirma cookie-based). La arquitectura v1.4 §22.1 lo asumía con prefijo. Confirmar con UX + Christian si Fase 2 storefront público entra en alcance Q3 2026 — si sí, activar prefijo y migrar deep-links existentes con redirects 301. Dueño: Pablo. Timing: Sprint 0 firma final.

2. **Crowdin vs Lokalise** para gestionar traducciones AR profesionales en Fase 1.5+. Crowdin es más barato y tiene mejor soporte de ICU; Lokalise tiene mejor API y editor para traductores no técnicos. POC de 1 día con un namespace pequeño antes de comprometer. Dueño: Pablo + Gerente comercial MT. Timing: Fase 1.5 sprint 1.

3. **Partial Prerendering (PPR) experimental on/off** — Off Fase 1 por riesgo de inestabilidad y porque el shell autenticado depende de cookies (poca ganancia esperada). Re-evaluar en Fase 1.5 cuando Next 16 estabilice PPR y midamos LCP del dashboard. Dueño: Pablo. Timing: Fase 1.5 sprint 2.

4. **Visual regression** — Chromatic (managed, $$) vs Playwright snapshots (gratis, mantenimiento manual de baselines). En Fase 1 vamos sin VR; en 1.5 evaluar si el catálogo de domain components creció lo suficiente para justificarlo. Dueño: Pablo. Timing: Fase 1.5 sprint 3.

5. **`@hookform/resolvers/zod` v4 vs v5** — Zod v4 trae cambios al parsing; resolver v5 los soporta pero está en RC al momento de redactar. Plan: ir con Zod v3 + resolver v4 estables; migrar Fase 1.5 cuando Zod v4 + resolver v5 sean GA. Dueño: Pablo. Timing: Fase 1.5 cierre.

6. **AR como UI completa (RTL del shell)** — Decisión actual: Fase 1 sólo AR como **contenido**. Si MT levanta requisito de UI en AR (Fase 2+), implica RTL del shell (sidebar a la derecha, mirroring de iconos, alineación de tablas). Esfuerzo estimado 2-3 sprints. Dueño: Christian + Paula. Timing: revisión Fase 2 alcance.

7. **Service Worker / offline mode** — No considerado Fase 1 (panel interno con conectividad asumida). Si MT pide modo "ver catálogo en el showroom sin wifi" (improbable pero mencionado en stage2-contextual-discovery), evaluar. Dueño: Pablo. Timing: revisión Fase 2 alcance.

---

## Apéndice A — Mapeo pantallas UX → carpetas

| Pantalla UX | Ruta App Router | Componentes domain clave |
|-------------|-----------------|--------------------------|
| 1. Dashboard Comercial | `(app)/dashboard/page.tsx` | KPI cards, audit-timeline, products-table |
| 2. Lista de SKUs | `(app)/catalogo/page.tsx` | data-table, filters-drawer, bulk-actions-bar |
| Detalle SKU (tabs) | `(app)/catalogo/[sku]/{ficha-tecnica,imagenes,costes,precios,traducciones,audit}/page.tsx` | tabbed-layout, breakdown-table, image-uploader-with-mirror |
| Wizard alta SKU | `(app)/catalogo/nuevo/page.tsx` | form atom + steps |
| Cola aprobación | `(app)/precios/cola-aprobacion/page.tsx` | data-table, diff-viewer, RbacGuard `prices:approve` |
| Simulador what-if | `(app)/precios/simulador/page.tsx` | currency-input, breakdown-table |
| Bulk operations | `(app)/precios/bulk/page.tsx` | bulk-actions-bar |
| Mis propuestas | `(app)/precios/mis-propuestas/page.tsx` | data-table |
| Importer hub + wizards | `(app)/importer/{pim,costes,traducciones}/page.tsx` + `runs/[run_id]` | import-preview-table, import-run-progress |
| Auditoría | `(app)/auditoria/page.tsx` + `[event_id]` | audit-timeline, diff-viewer |
| Admin usuarios | `(app)/admin/usuarios/page.tsx` | data-table + RbacGuard `admin:users:manage` |
| Admin roles | `(app)/admin/roles/page.tsx` | exception-rule-editor variant |
| Admin jobs | `(app)/admin/jobs/page.tsx` | poll job_definitions; CRUD UI |
| Admin canales | `(app)/admin/canales/page.tsx` | channel-state-badge editor |
| Admin reglas excepción | `(app)/admin/reglas-excepcion/page.tsx` | exception-rule-editor |
| Admin monedas | `(app)/admin/monedas/page.tsx` | fx-display + override editor |
| Chatbot (placeholder) | `(app)/chatbot/page.tsx` | empty-state Fase 2.5+ |
| Mi cuenta | `(app)/mi-cuenta/page.tsx` | form atom |
| Login | `(auth)/login/page.tsx` | login-form |
| Reset password | `(auth)/reset-password/page.tsx` | minimal form |
| Update password | `(auth)/update-password/page.tsx` | first-login forced rotation |

---

## Apéndice B — Matriz permisos → RbacGuard

Permisos se firman en JWT (`app_metadata.permissions`) por trigger `sync_user_app_metadata` (ver `mt-users-module-design.md` v1.1). El frontend nunca confía en sí mismo — Server Actions revalidan.

| Permiso | RbacGuard usage | Server Action wrapper |
|---------|-----------------|-----------------------|
| `products:read` | rutas `(app)/catalogo/**` | `withPermissions(["products:read"], "all", ...)` |
| `products:write` | botón `+ Alta SKU` | `withPermissions(["products:write"], "all", ...)` |
| `prices:propose` | form propuesta | idem |
| `prices:approve` | botones aprobar/rechazar en cola | idem |
| `imports:run` | botones Importer | idem |
| `admin:users:manage` | módulo `(app)/admin/usuarios` | idem |
| `admin:jobs:manage` | módulo `(app)/admin/jobs` | idem |
| `audit:read` | módulo auditoría | idem |
| `exceptions:write` | módulo reglas excepción | idem |

---

Fin del documento.
