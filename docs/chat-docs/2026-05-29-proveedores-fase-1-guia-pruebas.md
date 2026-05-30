# Guía de pruebas — Proveedores Fase 1 (PR #141, merge `01da086`)

Cómo verificar los cambios de la puesta a punto del módulo de proveedores:
pruebas automatizadas, smoke test manual E2E, y cómo correr el suite backend
completo en un entorno tipo-CI.

---

## 0. Resumen de lo que se prueba

| Bloque | Cambio | Tipo de prueba |
|--------|--------|----------------|
| A | UI huérfana `/suppliers` borrada; UI viva `/proveedores` | tsc + smoke manual |
| A | Tab Auditoría real (`AuditTimelineRich`) | vitest + smoke manual |
| A | `soft_delete_supplier` eliminado | pytest (no regresión) |
| A | +6 tests CRUD backend | pytest |
| A | Tests migrados a `/proveedores` | vitest + e2e |
| B | CI frontend `--diff-filter=ACMR` | CI (PR checks) |
| C | `CAST(:kwargs AS jsonb)` en competitor_brands | pytest + smoke manual |

---

## 1. Pruebas automatizadas

### 1.1 Frontend (desde `mt-pricing-frontend/`)

```bash
# Tests unitarios del módulo proveedores
node_modules/.bin/vitest run tests/unit/proveedores      # esperado: 5/5 passed

# Typecheck completo
node_modules/.bin/tsc --noEmit -p tsconfig.json          # esperado: 0 errores

# Lint de los archivos tocados
node_modules/.bin/eslint \
  "app/(app)/proveedores/_components/proveedor-detail.tsx" \
  "tests/unit/proveedores/proveedor-form.test.tsx" \
  "tests/unit/proveedores/proveedores-table.test.tsx"
```

### 1.2 Backend (contenedor `mt-backend`)

> **Importante:** el contenedor dev usa auth en modo `jwks`. Los tests de API
> firman JWT HS256 con un secreto de test, así que hay que **sobreescribir el
> entorno de auth** (es exactamente lo que hace CI):
> `SUPABASE_JWT_VERIFICATION_MODE=hs256`, `SUPABASE_JWT_SECRET=<secreto test>`,
> `JWT_ALGORITHM=HS256`.

```bash
# CRUD de suppliers (incluye los 6 escenarios nuevos)
docker exec -e SUPABASE_JWT_VERIFICATION_MODE=hs256 \
  -e SUPABASE_JWT_SECRET='test-jwt-secret-deterministic-32chars!' \
  -e JWT_ALGORITHM=HS256 \
  mt-backend pytest tests/api/test_suppliers_crud.py \
  -p no:cacheprovider --no-cov -o addopts=""        # esperado: 15/15 passed

# Fix competitor_brands (CAST jsonb)
docker exec -e SUPABASE_JWT_VERIFICATION_MODE=hs256 \
  -e SUPABASE_JWT_SECRET='test-jwt-secret-deterministic-32chars!' \
  -e JWT_ALGORITHM=HS256 \
  mt-backend pytest tests/api/test_competitor_brands_crud.py \
  -p no:cacheprovider --no-cov -o addopts=""        # esperado: 5/5 passed

# Lint + tipos del backend
docker exec mt-backend ruff check app/ tests/api/test_suppliers_crud.py
docker exec mt-backend ruff format --check app/services/suppliers/supplier_service.py
docker exec mt-backend mypy app/services/suppliers/supplier_service.py
```

---

## 2. Smoke test manual end-to-end (UI)

### 2.1 Prerrequisitos — levantar el stack local

```bash
npx supabase start
docker compose -f docker-compose.dev.yml up -d
# Frontend: http://localhost:3000  ·  Backend: http://localhost:8000
# Health:   curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live
```

Inicia sesión con un usuario que tenga los permisos:
- `suppliers:read` + `suppliers:write` (roles `ti_integracion` o `admin`)
- `audit:read` (roles `gerente`/`ti`) para ver el tab Auditoría.

### 2.2 Flujo a verificar (`/proveedores`)

| Paso | Acción | Resultado esperado |
|------|--------|--------------------|
| 1 | Ir a `/proveedores` | Lista (o estado vacío) + botón "Nuevo" si tienes `suppliers:write`. El sidebar apunta aquí (no a `/suppliers`). |
| 2 | "Nuevo" → `/proveedores/nuevo` | Form con code, name, moneda (selector), lead time, email, teléfono, términos de pago, notas, activo. |
| 3 | Crear con code inválido (ej. `ab c`) | Error de formato inline (no se envía). |
| 4 | Crear válido (`SUP_TEST`, moneda AED) | Toast de éxito + redirige al detalle. |
| 5 | Volver a la lista | El proveedor aparece en la tabla. |
| 6 | Crear de nuevo con el mismo code | Error 409 mapeado al campo `code` ("ya existe"). |
| 7 | Abrir detalle → tab **Datos** | Muestra todos los campos. |
| 8 | Tab **Costos asociados** | Lista costes con `supplier_code = code` (vacío si no hay). |
| 9 | Tab **Auditoría** | Timeline con el evento `supplier.created` (si tienes `audit:read`; si no, aviso de permiso). |
| 10 | Editar (`/proveedores/{code}/editar`) | Cambiar lead time → guardar → toast + dato actualizado. El tab Auditoría ahora muestra también `supplier.patched`. |
| 11 | Menú de acciones → "Archivar" | Diálogo de confirmación → confirma → toast "archivado"; el badge pasa a inactivo. |
| 12 | Reactivar desde el menú | Vuelve a activo. |
| 13 | Intentar `DELETE /api/v1/suppliers/{code}` (curl) | `405` con `code: vat_compliance_block`. |

### 2.3 Smoke del fix backend (competitor_brands)

```bash
# Debe responder 201 (antes del fix devolvía 500 por la tx abortada)
curl -X POST http://localhost:8000/api/v1/competitor-brands \
  -H "Authorization: Bearer <token con products:write>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Marca Smoke Test"}'
```

Verificar que se creó también el `job_definition` (`code = scrape_brand_marca_smoke_test`).

---

## 3. Suite backend completo en entorno tipo-CI (DB fresca)

El suite completo no corre fielmente contra la DB dev (el rol de la app no puede
tocar el schema `auth` de Supabase). Para reproducir CI hay que usar un Postgres
`pgvector` efímero donde el rol es dueño.

```bash
# 1) Postgres fresco en la red del backend
docker run -d --name pg-test-repro --network mt-pricing-dev \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres \
  pgvector/pgvector:pg16
# esperar a que esté listo
until docker exec pg-test-repro pg_isready -U postgres; do sleep 1; done

# 2) Correr pytest apuntando a esa DB (conftest aplica migraciones Alembic)
docker exec \
  -e DATABASE_URL='postgresql+asyncpg://postgres:postgres@pg-test-repro:5432/postgres' \
  -e ALEMBIC_DATABASE_URL='postgresql+psycopg://postgres:postgres@pg-test-repro:5432/postgres' \
  -e SUPABASE_JWT_VERIFICATION_MODE=hs256 \
  -e SUPABASE_JWT_SECRET='test-jwt-secret-deterministic-32chars!' \
  -e JWT_ALGORITHM=HS256 \
  mt-backend pytest tests/api/test_suppliers_crud.py tests/api/test_competitor_brands_crud.py \
  -p no:cacheprovider --no-cov -o addopts=""

# 3) Limpieza
docker rm -f pg-test-repro
```

### Interpretar el suite completo

Si corres **todo** el suite (`pytest` sin filtrar), `Tests (pytest)` muestra
~37 fallos que **NO** son de estos cambios. Son **pre-existentes y de entorno**:

- `tests/data/test_rls_finas.py`, `tests/db/test_best_practices.py` (RLS):
  CI corre solo migraciones Alembic, sin las migraciones Supabase que crean los
  roles RLS (`comercial`, `mt_app`, etc.) → fallan por roles ausentes.
- `tests/data/test_costs_fx_trigger.py`: el trigger lanza
  `fx_retroactive_not_allowed` → falta seed de `fx_rates`.

Estos fallos aparecen igual en `main` y en otros PRs backend; el job está marcado
`continue-on-error: true` en `ci-backend.yml` (no bloquea el merge). Arreglarlos
es una tarea de infraestructura de CI aparte (montar roles RLS + seed), fuera del
alcance de proveedores Fase 1.

---

## 4. Estado verificado (al cierre del PR #141)

- CI del PR: todos los checks **bloqueantes** en verde.
- `Tests (pytest)` (no-bloqueante): 41→37 fallos tras el fix de competitor_brands;
  el resto es pre-existente de entorno.
- Merge a `main` por squash (`01da086`); los 9 cambios validados en `main`.
