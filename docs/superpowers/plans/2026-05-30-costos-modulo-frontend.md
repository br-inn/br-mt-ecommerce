# Costos por esquema — Módulo Frontend `/costos` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Construir el módulo de primera clase `/costos` (resumen + listado global con vigencia + timeline de rangos + importar) y migrar la UI de costes existente al contrato `valid_from`/`valid_to`, reusando el sistema de diseño (MT primitives + shadcn).

**Architecture:** El backend (PR #144) ya expone vigencia por rangos. Este plan actualiza el cliente API + hooks al nuevo contrato, adapta el editor por-SKU a rangos, añade un componente `CostTimeline`, y eleva `/costos` a un módulo con `Tabs` (Resumen/Costes/Importar). Diferido: aprobación/notificaciones (D).

**Tech Stack:** Next.js 16 + React 19 + TS estricto + Tailwind v4 + shadcn (new-york) + MT primitives + TanStack Query + next-intl + vitest. Spec: `docs/superpowers/specs/2026-05-30-costos-vigencia-modulo-design.md` §5.

**Pre-requisito:** rama `feat/costos-modulo-frontend` desde `main`. Verificación: `node_modules/.bin/vitest run <files>`, `node_modules/.bin/tsc --noEmit -p tsconfig.json`, `node_modules/.bin/eslint <files>` (desde `mt-pricing-frontend/`). El backend NO necesita correr para vitest/tsc/eslint.

**Contrato backend (de PR #144) — referencia:**
- `Cost`: ahora `valid_from: string (date)`, `valid_to: string | null`; `status` sigue en la respuesta (hybrid derivado), `effective_at` ya NO se envía en requests.
- `POST /costs` body: `{ sku, scheme_code, supplier_code?, currency_origin, breakdown, valid_from (date), fx_rate_id?, fx_inferred? }` → `{ cost, warnings }`. (Schemas `extra="forbid"` → NO mandar `effective_at`.)
- `PATCH`/`PUT /costs/{id}`: corrección in-situ, body con `valid_from?`, `breakdown?`, `currency_origin?`...
- **NUEVO** `POST /costs/{id}/close` body `{ valid_to (date) }`.
- **NUEVO** `GET /costs/as-of?sku=&scheme_code=&supplier_code=&date=` → un `Cost` (404 si no hay).
- `GET /costs?sku=&scheme=&supplier=&valid_on=&include_history=&cursor=&limit=&include_total=` (default: solo vigentes hoy; `include_history=true`: todos los rangos).
- `GET /products/{sku}/costs?as_of=`; `GET /costs/missing?scheme_code=&as_of=`.
- Errores: cuerpo `{"detail": {"code": ...}}` → leer `detail.code`. Overlap → 409 `cost_range_overlap`.

---

## File Structure

| Archivo | Acción |
|---------|--------|
| `lib/api/endpoints/costs.ts` | Modificar — contrato `valid_from`/`valid_to`, `asOf`, `close`, filtros `valid_on`/`include_history`/`as_of` |
| `lib/hooks/costs/use-costs.ts` (+ query-keys) | Modificar — `useCostAsOf`, `useCloseCost`, filtros nuevos en `useCosts` |
| `app/(app)/catalogo/[sku]/costos/_client.tsx` | Modificar — `effective_at`→`valid_from`, rangos, acciones close/corrección |
| `components/domain/costs/cost-table.tsx` | Modificar — columnas `valid_from`/`valid_to`, badge estado por fecha |
| `components/domain/costs/cost-timeline.tsx` | Crear — timeline de vigencias por clave |
| `app/(app)/costos/page.tsx` + `_client.tsx` | Modificar — `Tabs` (Resumen/Costes/Importar) |
| `app/(app)/costos/_components/costos-table.tsx` | Crear — listado global |
| `app/(app)/costos/_components/costos-toolbar.tsx` + `costos-filters.ts` | Crear — filtros URL |
| `app/(app)/proveedores/_components/proveedor-detail.tsx` | Modificar — `SupplierCostsList` a rangos |
| `messages/{es,en,ar}.json` | Modificar — claves nuevas `costos.*` |
| `tests/unit/costos/*` | Crear — vitest |

---

## Task 1: Cliente API + hooks → contrato de vigencia

**Files:** Modify `lib/api/endpoints/costs.ts`, `lib/hooks/costs/use-costs.ts`, `lib/hooks/costs/query-keys.ts`. Test `tests/unit/costos/use-costs.test.ts`.

- [ ] **Step 1: Test (falla)** — un test que mockea `costsApi` y verifica que `useCostAsOf` llama `GET /costs/as-of` y `useCreateCost` envía `valid_from` (no `effective_at`).
- [ ] **Step 2: Correr → FAIL.**
- [ ] **Step 3: Implementar `costs.ts`:**
  - `Cost`: quitar el alias confuso; `valid_from: string` (date), `valid_to: string | null` reales (ya existían como alias — ahora son el contrato). Mantener `status` (derivado) en la respuesta. Quitar `effective_at` de los payloads.
  - `CostCreatePayload`: `effective_at` → `valid_from: string` (YYYY-MM-DD).
  - `CostUpdatePayload`: `effective_at?` → `valid_from?: string`.
  - `CostFilters`: añadir `valid_on?: string`, `include_history?: boolean`. Mantener `product_sku`/`scheme`/`supplier`/cursor/limit/include_total. (El backend usa `sku` y `scheme` — verificar los nombres de query param reales contra `routes/costs.py`/OpenAPI y alinear.)
  - `costsApi`: `create`/`update` envían `valid_from`; **nuevo** `asOf(params: {sku, scheme_code, supplier_code?, date})` → `GET /costs/as-of`; **nuevo** `close(id, valid_to)` → `POST /costs/{id}/close`. `listForSku(sku, asOf?)` y `missingForScheme(scheme, asOf?)` con `as_of`.
  - `CostsApiError`: leer `detail.code` (el backend devuelve `{"detail": {"code": ...}}`).
- [ ] **Step 4: Implementar hooks:** `useCostAsOf(params, enabled)`, `useCloseCost()` (mutation, invalida lists+detail), `useCosts(filters)` acepta `valid_on`/`include_history`. Mantener los existentes.
- [ ] **Step 5: Correr → PASS.** `tsc` + `eslint`.
- [ ] **Step 6: Commit** `feat(costos-fe): cliente API + hooks de vigencia`.

## Task 2: Editor por-SKU + CostTable a rangos (`valid_from`)

**Files:** Modify `app/(app)/catalogo/[sku]/costos/_client.tsx`, `components/domain/costs/cost-table.tsx`. Test `tests/unit/costos/cost-form.test.tsx`.

- [ ] **Step 1: Test (falla)** — el form (`CostFormSheet`) tiene campo `valid_from` (date) y al crear llama `useCreateCost` con `valid_from`; la tabla muestra columnas `valid_from`/`valid_to` y un badge Vigente/Programado/Caducado por fecha.
- [ ] **Step 2: FAIL. Step 3: Implementar:**
  - `_client.tsx`: renombrar el state `effectiveAt`→`validFrom`; el input envía `valid_from` (YYYY-MM-DD, sin convertir a ISO datetime). Añadir acciones: **Nuevo coste desde fecha** (POST), **Corregir** (PATCH in-situ), **Descatalogar** (`useCloseCost`). Mostrar historial vía `useCosts({ sku, include_history: true })` o `listForSku`.
  - `cost-table.tsx`: columnas `valid_from`/`valid_to`; badge derivado por fecha (`Pill`): Vigente (hoy ∈ rango), Programado (`valid_from` futuro), Caducado (`valid_to` < hoy). Quitar la columna `Effective at`/`Version`/`Status` antigua basada en supersede.
- [ ] **Step 4: PASS. Step 5: Commit** `feat(costos-fe): editor por-SKU a rangos + acciones close/corregir`.

## Task 3: Componente `CostTimeline`

**Files:** Create `components/domain/costs/cost-timeline.tsx`. Test `tests/unit/costos/cost-timeline.test.tsx`.

- [ ] **Step 1: Test (falla)** — `CostTimeline` recibe `costs: Cost[]` (historial de una clave ordenado) y renderiza una fila por rango con `valid_from→valid_to`, `scheme_landed_aed`, y badge de estado; marca el vigente hoy.
- [ ] **Step 2: FAIL. Step 3: Implementar** con `SectionCard` + `Pill` + tokens MT (sin librería de charts), siguiendo el mock ASCII del spec §5. Props `{ costs, currentDate? }`. **Step 4: PASS. Step 5: Commit** `feat(costos-fe): componente CostTimeline`.

## Task 4: Módulo `/costos` con Tabs + listado global

**Files:** Modify `app/(app)/costos/page.tsx` + `_client.tsx`; Create `app/(app)/costos/_components/{costos-table.tsx, costos-toolbar.tsx, costos-filters.ts}`. Test `tests/unit/costos/costos-table.test.tsx`.

- [ ] **Step 1: Test (falla)** — `CostosTable` renderiza filas (sku/esquema/proveedor/valid_from/valid_to/landed/estado) desde `useCosts`; `CostosToolbar` aplica filtros en URL (sku, esquema, proveedor, vigente-a-fecha, toggle historial).
- [ ] **Step 2: FAIL. Step 3: Implementar:**
  - `costos-filters.ts`: hook de filtros en URL (patrón `proveedores-filters.ts`): `sku`, `scheme`, `supplier`, `valid_on`, `include_history`.
  - `costos-table.tsx`: `DataTable` (o tabla MT) con `useCosts(filters)`; badge estado por fecha; link a la clave (timeline).
  - `costos-toolbar.tsx`: search SKU + select esquema (`useSchemes`) + select proveedor (`useSuppliers`) + date "vigente a" + toggle historial.
  - `_client.tsx`: `Tabs` — **Resumen** (mover el dashboard de cobertura actual aquí), **Costes** (toolbar+tabla), **Importar** (link/placeholder al flujo de import existente con la nota de `valid_from`).
- [ ] **Step 4: PASS. Step 5: Commit** `feat(costos-fe): modulo /costos con tabs + listado global`.

## Task 5: Lista de costes del proveedor → rangos

**Files:** Modify `app/(app)/proveedores/_components/proveedor-detail.tsx`. Test: ampliar el unit test del detalle si existe.

- [ ] **Step 1: Test (falla)** — `SupplierCostsList` muestra rangos (`valid_from`/`valid_to`) y badge Vigente/Caducado por fecha (no por `valid_to != null`), con link al módulo `/costos`.
- [ ] **Step 2: FAIL. Step 3: Implementar** — usar `c.valid_from`/`c.valid_to`/`c.scheme_landed_aed`; badge por fecha. **Step 4: PASS. Step 5: Commit** `feat(costos-fe): costes del proveedor a rangos`.

## Task 6: i18n + verificación final

**Files:** Modify `messages/{es,en,ar}.json`. 

- [ ] **Step 1:** Añadir claves nuevas bajo `costos.*` (timeline, badges Programado, columnas valid_from/valid_to, acciones nuevo/corregir/descatalogar, toolbar) en **las 3 locales**. Reusar las existentes de `costs`/`costsDashboard` donde aplique.
- [ ] **Step 2: Verificación final:**
  - `node_modules/.bin/vitest run tests/unit/costos` → todo verde.
  - `node_modules/.bin/tsc --noEmit -p tsconfig.json` → 0 errores.
  - `node_modules/.bin/eslint "app/(app)/costos/**" "components/domain/costs/**" "lib/api/endpoints/costs.ts" "lib/hooks/costs/**"` → 0.
- [ ] **Step 3: Commit** `feat(costos-fe): i18n del modulo de costos` (o incluir en los commits previos).

---

## Cierre
- [ ] PR `feat(costos): módulo frontend de vigencia` con `## Summary` + `## Test plan`.
- [ ] Depende del backend (PR #144) en producción — mergear #144 primero.
