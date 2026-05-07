# Validación E2E — Sprint 1 + 2

Suite Playwright para validar los flows críticos de las Pantallas 2, 3, 4, 10
y los CRUD de Suppliers + Healthchecks contra la stack local del developer.

## Decisiones clave

| Tema                | Decisión                                                                |
| ------------------- | ----------------------------------------------------------------------- |
| Magic Link          | Solo se valida que dispara `signInWithOtp` + toast (sin completar OTP). |
| Auth bypass         | Mocks `route()` por defecto; opcional Supabase real con env flag.       |
| Importer apply      | **NO** se ejecuta en E2E — solo `preview`. Apply es destructivo.        |
| Browsers            | Solo `chromium` (instalado idempotentemente por el orquestador).        |
| Stack target        | Caddy single entry-point (`localhost:8080`) — backend y frontend ocultos. |
| Cleanup suppliers   | Mocks usan store en memoria; en modo real, seed scripts limpian.        |
| RBAC                | `loginAsRole(role)` simula permisos por rol vía `/api/v1/me` mock.      |

## Flows cubiertos

### Críticos (must-pass para demo S1+S2)

| # | Spec file                          | Flow                                                                                |
| - | ---------------------------------- | ----------------------------------------------------------------------------------- |
| 1 | `01-healthchecks.spec.ts`          | `/health/live`, `/health/ready`, Flower (skip si no up).                            |
| 2 | `02-auth-login.spec.ts`            | Guest redirect, magic-link toast, password login, signout.                          |
| 3 | `03-products-list.spec.ts`         | `/products` table render, columnas, filtros family/q/brand.                         |
| 4 | `04-product-detail-edit.spec.ts`   | `/products/[sku]` Pantalla 3+4: header, edit form, tab Imágenes.                    |
| 5 | `05-suppliers-crud.spec.ts`        | `/suppliers` empty state → crear → aparece en lista → soft-deactivate.              |
| 6 | `06-importer-preview.spec.ts`      | `/imports` Pantalla 10 — upload `PIM completo.xlsx` → preview (NO apply).           |
| 7 | `07-i18n-switcher.spec.ts`         | Topbar locale switcher ES↔EN, persiste cookie `mt-locale`.                          |

### Secundarios

| # | Spec file                          | Flow                                                              |
| - | ---------------------------------- | ----------------------------------------------------------------- |
| 8 | `08-filtros-avanzados.spec.ts`     | Sheet "Más filtros" en Pantalla 2 (DN, material) + clear filtros. |

### Pendientes (no implementados — bloqueos)

- **RBAC comercial sin permisos delete**: requiere seed user con rol `comercial`
  real en Supabase. Stub disponible vía `loginAsRole(page, "comercial")` —
  añadir spec cuando el seed esté wired.
- **Magic Link end-to-end**: requeriría inbucket o mailpit local. No vale la
  pena en validación automática.

## Ejecutar

Ver [`scripts/README.md`](../scripts/README.md) para el orquestador.

### Solo Playwright (sin orquestador)

```bash
cd mt-pricing-frontend

# Asume stack ya arriba en localhost:8080
pnpm test:e2e

# Smoke healthcheck
pnpm validate:stack

# Browser visible (debug)
pnpm test:e2e:headed

# UI mode (Playwright trace viewer)
pnpm test:e2e:ui
```

### Variables de entorno útiles

```bash
# Apuntar a Next dev directo en :3000 (sin Caddy)
export E2E_BASE_URL=http://localhost:3000
export E2E_BACKEND_URL=http://localhost:8000

# Usar Supabase real (sin mocks de auth)
export E2E_USE_REAL_SUPABASE=1
export E2E_USER_EMAIL=qa@mt.ae
export E2E_USER_PASSWORD=...
```

## Helpers

- `tests/e2e/fixtures/env.ts` — resolución central de URLs y flags
- `tests/e2e/fixtures/api.ts` — `getLive()`, `getReady()`, `getFlowerHealth()`
- `tests/e2e/fixtures/auth.ts` — `loginAsRole(page, role)`, `installAuthMocks(page, role)`
- `tests/e2e/fixtures/seed.ts` — `installProductsMocks`, `installSuppliersMocks`, `installImportsMocks`

## Troubleshooting

### "Backend no responde en localhost:8080/health/live"

La stack no está arriba o Caddy no proxy correctamente. Verifica:

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs caddy --tail=20
docker compose -f docker-compose.dev.yml logs backend --tail=40
```

Alternativa: levanta backend + frontend directos sin Caddy y override:

```bash
export E2E_BASE_URL=http://localhost:3000
export E2E_BACKEND_URL=http://localhost:8000
```

### "Test 'lists products' tarda > 30s"

Next.js dev primer render compila on-demand. Pre-warm con:

```bash
curl -s http://localhost:8080/products >/dev/null
curl -s http://localhost:8080/suppliers >/dev/null
curl -s http://localhost:8080/imports >/dev/null
```

### Playwright reporta browser no instalado

```bash
cd mt-pricing-frontend
pnpm test:e2e:install  # solo chromium
```

### "PIM real no encontrado" en `06-importer-preview`

El archivo `Documentos referencia de articulos/PIM completo.xlsx` debe existir
en el repo root. Si no, el test se marca skip con instrucciones.

## Mantenimiento

Cuando se añadan nuevas Pantallas / flujos:

1. Crear `NN-feature.spec.ts` con `data-testid` selectors (no CSS classes)
2. Reusar `loginAsRole()` y los mocks de `seed.ts`
3. Añadir el path al describe `@critico` o `@secundario` para taxonomía
4. Documentar el flow en este archivo bajo "Flows cubiertos"

## Referencias

- ADR-035: Caddy reverse proxy (`docs/adr/`)
- US-1A-02-03-S1, US-1A-02-04-S2: Pantalla 2 + Pantalla 4
- US-1A-03-02: Suppliers CRUD
- US-1A-06-01: Importer wizard
- Reportes Sprint: `_bmad-output/implementation-artifacts/sprint{1,2}-execution-report.md`
