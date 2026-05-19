# Historia US-SCR-02-01: Fix Empty State en Pool de Candidatos

**Épica:** EP-SCR-02 — Revisión y Validación UI
**Sprint:** S13
**Story Points:** 3
**FR cubiertos:** FR-15
**NFRs:** NFR-03 (i18n ES/EN/AR)

## Story

Como miembro del equipo de TI o Comercial,
quiero que /comparator/pool muestre un estado vacío claro cuando no hay candidatos,
para poder saber inmediatamente que el pool está vacío y no confundirlo con un error de carga.

## Acceptance Criteria

**AC-1:** Pool vacío (sin competitor_listings)
- Given que no hay registros o los filtros no devuelven resultados
- When el usuario visita /comparator/pool
- Then los KPI cards muestran valores numéricos (0) en lugar de skeleton indefinido
- And la tabla muestra empty state con icono y mensaje "No hay candidatos en el pool"
- And el empty state incluye CTA "Lanzar scraping" que lleva a /admin/scraper

**AC-2:** Filtros activos sin resultados
- Given que hay candidatos pero el filtro activo no retorna resultados
- When el usuario aplica el filtro
- Then la tabla transiciona de datos a empty state sin pasar por skeleton
- And el mensaje indica "No hay candidatos con estos filtros" con botón "Limpiar filtros"

**AC-3:** Timeout de carga (anti skeleton infinito)
- Given que el componente está cargando datos reales (loading=true)
- When la request está en vuelo
- Then skeleton aparece máximo durante el tiempo de la request (timeout 10s)
- And si la request falla, muestra error state con "Reintentar" — nunca skeleton infinito

## Tasks / Subtasks

- [x] T1: Fix StatCard — `(value ?? 0).toLocaleString()` en lugar de `value ?? "—"`
- [x] T2: Añadir `cta?: React.ReactNode` prop a `MtEmpty` en components/mt/states.tsx
- [x] T3: Añadir `useLoadingTimeout(isLoading, 10_000)` en pool/page.tsx para cortar skeleton infinito
- [x] T4: Empty state diferenciado: pool vacío (CTA Lanzar scraping) vs filtros activos (Limpiar filtros)
- [x] T5: i18n — keys `comparator.pool.*` en messages/es.json, en.json, ar.json

## Dev Notes

- Hook `useUnmatchedOffersStats` usa `useQuery` sin retry configurado — falla silenciosamente en 3 reintentos
- `StatCard` con `value ?? "—"` muestra "—" cuando stats es undefined (error) o cuando backend retorna null
- La condición de empty state existente (`!isLoading && items.length === 0 && !isError`) no diferencia pool vacío vs sin filtros
- `MtEmpty` no tiene soporte para CTA buttons — necesita nuevo prop `cta?: React.ReactNode`
- i18n solo para textos NUEVOS; los strings hardcodeados existentes se mantienen para no aumentar scope

## File List

- `mt-pricing-frontend/app/(app)/comparator/pool/page.tsx`
- `mt-pricing-frontend/components/mt/states.tsx`
- `mt-pricing-frontend/messages/es.json`
- `mt-pricing-frontend/messages/en.json`
- `mt-pricing-frontend/messages/ar.json`

## Change Log

- 2026-05-16: Implementación inicial — fix skeleton infinito FR-15

## Dev Agent Record

### Implementation Notes

Bugs raíz identificados:
1. `StatCard`: `value?.toLocaleString() ?? "—"` → muestra "—" cuando stats API falla o retorna null/undefined
2. Table body: `isLoading ? skeleton : items` sin timeout → si API cuelga, skeleton infinito
3. Empty state: un único `MtEmpty` genérico sin CTA y sin distinción filtros/vacío

Fixes aplicados:
- `MtEmpty` extendido con `cta?: React.ReactNode` para botones de acción opcionales
- `StatCard` cambiado a `(value ?? 0).toLocaleString()`
- `useLoadingTimeout` local en pool page — 10s de guarda para tabla y stats
- Dos empty states diferenciados: pool vacío → /admin/scraper; filtros → limpiar filtros
- i18n keys `comparator.pool.*` añadidas en ES/EN/AR

## Status

review
