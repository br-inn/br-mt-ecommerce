# Stage 3 — Plan de adopción completo del modelo de catálogo

**Fecha**: 2026-05-09 · **Estado**: ready to execute (paralelo en worktrees)

> Cierra el loop end-to-end del refactor de jerarquía Stage 3 (Wave 11):
> divisions, series rica, materials. Backend ya tiene tablas + ORM + repos +
> services + routes + 16 schema tests verdes. Falta consumirlo en producto
> API, frontend, importer, y limpieza de datos.

---

## 1. Lo que ya está hecho (commits sin push)

| Pieza | Estado | Archivo |
|---|---|---|
| Migration 044 (divisions) | ✅ | [20260509_044_divisions.py](../../mt-pricing-backend/alembic/versions/20260509_044_divisions.py) |
| Migration 045 (series + tiers + translations + junctions) | ✅ | [20260509_045_series.py](../../mt-pricing-backend/alembic/versions/20260509_045_series.py) |
| Migration 046 (materials vocab) | ✅ | [20260509_046_materials.py](../../mt-pricing-backend/alembic/versions/20260509_046_materials.py) |
| ORM models (8 entidades + Product FKs) | ✅ | [vocabularies.py](../../mt-pricing-backend/app/db/models/vocabularies.py), [product.py](../../mt-pricing-backend/app/db/models/product.py) |
| Pydantic schemas | ✅ | [schemas/vocabularies.py](../../mt-pricing-backend/app/schemas/vocabularies.py) |
| Repositories | ✅ | [repositories/vocabularies.py](../../mt-pricing-backend/app/repositories/vocabularies.py) |
| Services CRUD | ✅ | [services/vocabularies/vocabulary_service.py](../../mt-pricing-backend/app/services/vocabularies/vocabulary_service.py) |
| API routes (~30 endpoints) | ✅ | [routes/taxonomy_extras.py](../../mt-pricing-backend/app/api/routes/taxonomy_extras.py) |
| Schema smoke tests (16) | ✅ verde | [tests/unit/schemas/test_taxonomy_extras.py](../../mt-pricing-backend/tests/unit/schemas/test_taxonomy_extras.py) |
| Alembic head | ✅ `20260509_046` | docker exec mt-backend |
| Backfill | ✅ | 2 divisions seed · 5 tiers · 22 materials (16 EN backfill + 6 ES seed) · 1 series backfilled |

---

## 2. Lo que falta — checklist por capa

### 2.1 Backend

- [ ] **Mig 047 — limpieza materials** — dedupe EN/ES (brass↔laton, cast_iron↔fundicion, stainless_steel↔acero_inoxidable, …). Mantener codes ES canónicos, remapear `products.material_id`, desactivar duplicados EN.
- [ ] **Product API extensions**:
  - Filtros nuevos en `GET /products`: `division=`, `series_id=`, `material_id=`, `tier_code=`.
  - Update `ProductResponse` para exponer `series_id`, `material_id`, `display_pair_sku`, `divisions[]` (lista compacta).
  - Update `ProductDetail` para incluir `series` (objeto rico expandido), `material` (objeto), `display_pair` (objeto producto).
- [ ] **Facets endpoint** — extender `GET /products/facets` con dimensiones: `division`, `series`, `tier_code`, `material_curated` (FK), preservando las existentes.
- [ ] **Merge helpers** — service `effective_tags(product)` y `effective_certifications(product)` que unen series + product. Endpoint `GET /products/{sku}/effective-display` que devuelve la unión.
- [ ] **Display pair sync** — endpoint `PUT /products/{sku}/display-pair` que establece bidireccionalmente `display_pair_sku` en ambos extremos. `DELETE /products/{sku}/display-pair` que limpia ambos.
- [ ] **Tests** — repos, services, route tests para los 4 bloques.

### 2.2 Importer

- [ ] **Mapping division por origen** — Daterium runs → `industrial`, mtspain.net → `hidrosanitario`, override por `category_id` si aplica.
- [ ] **Backfill** — script one-shot que asigna `product_divisions` para los 5,085 SKUs existentes según source recordado en import_runs.
- [ ] **Materials mapper** — al crear/actualizar products desde fuente, asignar `material_id` desde el vocabulario curado (no el TEXT libre).

### 2.3 Frontend — admin

- [ ] **Tipos API** — `Division`, `Series`, `SeriesTier`, `Material`, `ProductDivisionLink` en `lib/api/endpoints/`.
- [ ] **`/admin/divisions`** — list + create + edit + soft-delete.
- [ ] **`/admin/series-tiers`** — list + create + edit + delete (vocab cerrado).
- [ ] **`/admin/series`** — list + detail. Detail tiene 4 tabs: General · Translations (es/ar/en) · Divisions (junction) · Certifications (junction). Tier picker, banner color picker.
- [ ] **`/admin/materials`** — list + create + edit + delete.

### 2.4 Frontend — catálogo

- [ ] **Selector de división** en header `/catalogo` — tabs (Hidrosanitario / Industrial), persiste en saved view + URL query.
- [ ] **FacetSidebar** — añadir facets: `division`, `series` (con badge tier color), `tier_code`, `material` (FK curated).
- [ ] **Saved views** — incluir `division_id` en el state de saved view.
- [ ] **ProductsTable** — chip de tier color en filas con serie asignada.

### 2.5 Frontend — series landing + product detail

- [ ] **`/series/[code]`** — landing pública por serie: hero (banner_color + hero_image), bullets ES, certificaciones default, listado de productos filtrado por serie.
- [ ] **Product detail** — renderizar `effective_tags` + `effective_certifications` (badges visibles); link al display pair si existe; chip de la serie con su color.
- [ ] **Wizard** — selector de división (M:N) + serie (FK opcional con autocomplete) en el step de catalog metadata.

### 2.6 Validación / deploy

- [ ] **E2E tests** — Playwright: filtro división + facet sidebar + landing serie.
- [ ] **Hetzner staging** — apply migrations + smoke endpoints.
- [ ] **Docs** — actualizar [catalog-modeling-execution-report](../implementation-artifacts/catalog-modeling-execution-report-2026-05-08.md) con sección Stage 3.

---

## 3. Distribución a agentes (paralelo en git worktrees)

Cada agente trabaja en un worktree aislado para evitar conflictos. Cuando todos terminen, se mergean en orden topológico → fast-forward sobre `main`.

| Agente | Worktree branch | Scope | Depende de |
|---|---|---|---|
| **A — materials-hygiene** | `wt-stage3-a-materials-hygiene` | Migration 047 dedupe EN/ES, remapear product.material_id, mantener `family_kind`. Tests. | – |
| **B — product-api-ext** | `wt-stage3-b-product-api` | Filtros nuevos en list, ProductResponse/Detail con series_id/material_id/display_pair/divisions[], facets +4 dimensiones. Tests + integration. | – |
| **C — merge-and-pair** | `wt-stage3-c-merge-pair` | Service `effective_tags`/`effective_certifications` (union series+product), endpoint `GET /products/{sku}/effective-display`, display_pair sync bidireccional con endpoints PUT/DELETE. Tests. | – |
| **D — importer-division** | `wt-stage3-d-importer` | Importer mapping source→division (Daterium=industrial, mtspain.net=hidrosanitario), backfill script por import_runs. Tests. | – |
| **E — fe-admin** | `wt-stage3-e-fe-admin` | API types + 4 admin pages (divisions, series-tiers, series, materials) en `mt-pricing-frontend/app/(app)/admin/`. | – |
| **F — fe-catalog** | `wt-stage3-f-fe-catalog` | Selector división header, facets nuevos en sidebar, saved views, chip tier en tabla. | (B para facets) |
| **G — fe-series-detail** | `wt-stage3-g-fe-series` | `/series/[code]` landing + product detail enriched (effective tags/certs + display pair). | (C para effective endpoint) |

### Orden de merge

1. **A**, **D** (datos / importer — no tocan código compartido).
2. **B** (extiende product API — base para FE).
3. **C** (helpers + display pair — base para detail FE).
4. **E** (admin FE — independiente del catálogo).
5. **F** (catálogo FE — necesita B mergeado).
6. **G** (series + detail FE — necesita C mergeado).

### Conflict map (qué archivos toca cada uno)

| Archivo | A | B | C | D | E | F | G |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `alembic/versions/20260509_047_*.py` | ✅ | | | | | | |
| `repositories/product.py` | | ✅ | | | | | |
| `repositories/vocabularies.py` | | | ✅ | | | | |
| `services/products/product_service.py` | | ✅ | ✅ | | | | |
| `services/vocabularies/*.py` | | | ✅ | | | | |
| `api/routes/products.py` | | ✅ | | | | | |
| `api/routes/taxonomy_extras.py` | | | ✅ | | | | |
| `schemas/products.py` | | ✅ | | | | | |
| `schemas/vocabularies.py` | | | ✅ | | | | |
| `tests/unit/**` | ✅ | ✅ | ✅ | ✅ | | | |
| `services/imports/**` | | | | ✅ | | | |
| `lib/api/endpoints/**` (FE) | | | | | ✅ | ✅ | ✅ |
| `app/(app)/admin/**` (FE) | | | | | ✅ | | |
| `app/(app)/catalogo/**` (FE) | | | | | | ✅ | |
| `app/(app)/series/**` (FE) | | | | | | | ✅ |
| `app/(app)/products/_components/product-detail.tsx` | | | | | | | ✅ |

Conflictos potenciales:
- **B + C** ambos tocan `services/products/product_service.py` → C debe mergear DESPUÉS de B.
- **E + F + G** todos tocan `lib/api/endpoints/` (types) → mergear secuencialmente; el primero crea archivos nuevos, los siguientes solo añaden endpoints.

---

## 4. Criterios de "Done" por agente

### A — materials-hygiene
- Migration 047 reversible.
- Tras upgrade: 0 productos quedan con FK a un material EN duplicado del ES.
- Materials EN duplicados quedan `active=false` (no se borran — preservan FK histórica si la hubiera).
- Test: `pytest tests/unit/repositories/test_material_dedupe.py` verde.

### B — product-api-ext
- `GET /products?division=industrial` filtra correctamente.
- `GET /products?series_id=<uuid>` filtra correctamente.
- `GET /products?material_id=<uuid>` filtra correctamente.
- `ProductResponse` incluye `series_id`, `material_id`, `display_pair_sku`, `division_codes: list[str]`.
- `ProductDetail` incluye `series: SeriesResponse | None`, `material: MaterialResponse | None`, `display_pair: ProductMini | None`.
- `GET /products/facets` devuelve dimensión `division`, `series`, `tier_code`, `material_curated`.
- Tests verdes; openapi schema actualizado.

### C — merge-and-pair
- `GET /products/{sku}/effective-display` devuelve `{tags: [...], certifications: [...]}` con union.
- `PUT /products/{sku}/display-pair` con body `{paired_sku: "..."}` actualiza ambos extremos.
- `DELETE /products/{sku}/display-pair` limpia ambos.
- Tests cubren symmetric set/unset y caso self-reference (sku=paired_sku → 400).

### D — importer-division
- Importer asigna `product_divisions` al crear/actualizar product.
- Script `scripts/backfill_divisions_from_import_runs.py` mapea SKUs existentes por history of import_runs.
- Tests cubren mapeo Daterium→industrial, mtspain.net→hidrosanitario.

### E — fe-admin
- `/admin/divisions`, `/admin/materials`, `/admin/series-tiers`: list + create/edit/delete forms.
- `/admin/series`: list + detail con 4 tabs (General/Translations/Divisions/Certifications).
- TS typecheck verde.
- pnpm build verde.

### F — fe-catalog
- Selector división en header de `/catalogo`.
- Facets `division`, `series`, `tier_code`, `material_curated` en sidebar.
- Saved views guardan/restauran `division_id`.
- Chip tier color en filas de la tabla.

### G — fe-series-detail
- `/series/[code]` landing renderiza hero, bullets, productos filtrados.
- Product detail muestra `effective_tags`, `effective_certifications`, link a display pair si existe.
- TS typecheck verde.

---

## 5. Comandos comunes para los agentes

```bash
# Worktree setup (paralelo)
git worktree add ../wt-stage3-<X> -b wt-stage3-<X>

# Validación backend
docker exec mt-backend pytest tests/unit -q --no-cov \
  --deselect tests/unit/schemas/test_assets.py::test_asset_response_validates_from_dict \
  --ignore=tests/unit/services/importer_datasheets/test_dual_extractor.py

docker exec mt-backend alembic current
docker exec mt-backend alembic upgrade head

# Validación frontend
docker exec mt-frontend pnpm tsc --noEmit
docker exec mt-frontend pnpm build

# Redeploy local
docker restart mt-backend mt-frontend
```

---

## 6. Notas de coordinación

- Ningún agente hace push o merge a `main`.
- Cada agente reporta: archivos creados/modificados + comandos de validación + cualquier blocker.
- Yo (orquestador) merger en orden topológico tras revisión.
- Si dos agentes terminan en conflicto sobre el mismo archivo (poco probable por el conflict map), el segundo en mergear hace rebase manual.
