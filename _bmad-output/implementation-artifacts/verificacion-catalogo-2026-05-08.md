# Verificación módulo /catalogo — 2026-05-08

Entorno: Docker local (mt-frontend, mt-backend, mt-caddy en :8081, postgres-supabase, redis, neo4j).

## Estado BD vs UI (causa raíz "no se muestran los datos")

| Tabla | Filas | Notas |
|---|---:|---|
| products | **5085** | name_en, family, dn, pn, material, type, data_quality poblados |
| product_translations | 0 | badges EN/ES/AR salen "—" hasta que se siembre |
| product_images | 0 | thumbs muestran placeholder hasta que se siembre |

Causas raíz identificadas (ahora corregidas):

1. **Paginación rota**: backend devuelve `{ items, cursor:{ next }, total, page_size }` pero el cliente leía `last.next_cursor` (campo inexistente). `hasNextPage` siempre falso → solo veías 25 de 5085 productos. Fix: adapter en `productsApi.list` mapea `cursor.next → next_cursor`.
2. **Drift de contrato `id` vs `internal_id`**: backend retorna `internal_id` (UUID); el TS declaraba `id`. Como `key={r.id}` resolvía siempre a `undefined`, React duplicaba keys y emitía warning. Fix: `ProductListItem.id → internal_id` y `<tr key={r.sku}>` (la PK estable).
3. **Campos faltantes en list response**: backend `ProductResponse` no exponía `translation_status_es/_ar` ni `primary_image_url`. La UI los leía como `undefined`. Fix: extendido `ProductResponse` + el handler `list_products` ahora hace batch fetch (un select sobre `product_translations` y otro sobre `product_images is_primary`) y rellena los 3 campos por sku.
4. **Endpoints por SKU pasaban `product.id` (undefined)**: imágenes, traducciones, eliminación, toggle activo. Corregidos a `product.sku` (el path PK del backend).

## Resumen

| Capa | Estado |
|---|---|
| Stack Docker | OK — todos los contenedores healthy |
| Routing frontend (`/catalogo`, `/catalogo/nuevo`, `/catalogo/validacion`, `/catalogo/[sku]/*`) | OK — 307 sin sesión, 200 con sesión (3.0s primer hit, 373 ms cache) |
| Backend `/api/v1/products*` | OK — 401 sin token, 200 con token |
| OpenAPI | Servido en `/openapi.json` (no `/api/v1/openapi.json`) |
| Tests unit products | 25/25 OK |
| Tests api/integración con testcontainers | No corren dentro de mt-backend (no docker-in-docker) — entorno, no bug |
| Typecheck frontend | OK |
| Lint catalogo | OK |

## Bugs confirmados

### 1. Drift de contrato `ProductListItem.id` ↔ backend `internal_id` (alta)

[mt-pricing-backend/app/schemas/products.py:250-282](mt-pricing-backend/app/schemas/products.py#L250-L282) → `ProductResponse` expone `sku: str` + `internal_id: UUID`. **No expone `id`.**

[mt-pricing-frontend/lib/api/endpoints/products.ts:59-74](mt-pricing-frontend/lib/api/endpoints/products.ts#L59-L74) → `ProductListItem.id: string`.

[mt-pricing-frontend/app/(app)/catalogo/page.tsx:434](mt-pricing-frontend/app/(app)/catalogo/page.tsx#L434) → `<tr key={r.id}>` para cada fila renderizada.

Consecuencia runtime: `r.id` siempre `undefined` → React warn `Each child in a list should have a unique "key" prop. Check the render method of tbody. It was passed a child from CatalogPage` (visible en logs frontend). En presencia de muchos rerenders puede degradar performance de la tabla y romper diff de filas.

Fix sugerido (mínimo): cambiar key a `r.sku` (PK garantizado) y eliminar `id` del tipo. Si se prefiere conservar UUID, alinear el tipo a `internal_id: string` y la key a `r.internal_id`.

### 2. Campos faltantes en backend que el frontend lee (media)

`ProductListItem` declara — y la página consume — campos que **NO** están en `ProductResponse`:

- `translation_status_es: TranslationStatus | null` ([page.tsx:430-431](mt-pricing-frontend/app/(app)/catalogo/page.tsx#L430-L431))
- `translation_status_ar: TranslationStatus | null`
- `primary_image_url: string | null`

Resultado: badges traducción siempre "unknown" y thumbnail vacío para todas las filas. La página igualmente renderiza (statusToVal trata null/undefined), pero el dato útil del listado se pierde.

Fix sugerido: extender `ProductResponse` (o usar un `ProductListResponse` separado) con join lateral a `product_translations` (por lang ES y AR → status) y `product_images` (primaria). Alternativa: dejar la sección de traducción/thumb sólo en `ProductDetail` y simplificar la grilla.

### 3. Endpoint `/api/v1/auth/login` no existe (baja)

Smoke probó `POST /api/v1/auth/login` → endpoint inexistente. La autenticación va por Supabase Auth en frontend y el backend valida el JWT (`/api/v1/me` 200 con cookie). No es bug, pero debe documentarse para QA scripts.

## Hallazgos menores

- Logs frontend repiten warnings de `@sentry/nextjs` + `@opentelemetry/instrumentation`: `Critical dependency: require function ... cannot be statically extracted`. Es ruido conocido del bundler de Next.js cuando carga Sentry server-side; no afecta runtime. Suprimir en `next.config.js` con `serverComponentsExternalPackages` o silenciar por config si molesta.
- Caddy y todos los contenedores healthy.
- TTFB primer hit de `/catalogo` 3 s (server-side render + proxy). Cache caliente 373 ms.

## Acciones recomendadas (orden de prioridad)

1. Decidir fuente de verdad del PK del listado y reconciliar tipo + key (#1). 5 min.
2. Decidir si `translation_status_*` y `primary_image_url` se exponen en list o sólo en detail; ajustar backend o frontend (#2). 30 min – 2 h según opción.
3. Tests api con testcontainers: documentar que requieren correr fuera del contenedor backend (`pytest` desde host con DOCKER_HOST montado), o reemplazar por Postgres in-memory si se quieren ejecutar dentro. Operativo, no bloquea.
