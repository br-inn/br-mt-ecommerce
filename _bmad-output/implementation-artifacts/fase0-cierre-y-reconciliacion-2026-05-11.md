# Fase 0 — cierre + plan reconciliación branches

**Fecha:** 2026-05-11
**Sesión:** ejecución plan PDF PIM (PDF v1.0 07/05/2026)
**Estado:** Fase 0 completa en main (sin commitear). Fases 1+ bloqueadas por divergencia de ramas.

---

## TL;DR (3 líneas)

- Fase 0 + Stage 2 cleanup + fix FastAPI 204 ejecutados en `main` (working tree). Tests **1034 pass, 0 fail**.
- Docker corre `feat/taxonomy-registry` desde worktree paralelo `C:\BR-Github\br-mt\br-mt-ecommerce-taxonomy\` — no se puede redeployar mi trabajo sin clobberear el suyo.
- Fase 1 (taxonomy) **ya implementada en feat/taxonomy-registry** (commits acab332 … 13fade0); Fases 2-5 bloqueadas hasta que el usuario reconcilie ramas.

---

## 1. Trabajo ejecutado (uncommitted, working tree `main`)

### 1.1 Fase 0 backend — drop legacy promised por mig 030

| Archivo | Cambio |
|---|---|
| `alembic/versions/20260511_049_drop_legacy_image_and_role.py` | **Nuevo.** Drop `products.{image_url, image_origin_url, image_status}` + `product_assets.role`. Downgrade reversible. |
| `app/db/models/product.py` | Removidas 4 columnas + `CheckConstraint("ck_products_image_status")` |
| `app/schemas/products.py` | Removidos campos `image_url`, `image_status` de `ProductBase`/`ProductPatch`/`ProductResponse` |
| `app/schemas/facets.py` | Removido `image_status` de `FacetsResponse` |
| `app/services/products/facets_service.py` | `image_status` → re-derivado vía `EXISTS(product_assets kind='photo' status='active')` |
| `app/services/products/product_service.py` | Removido `image_url` de `_AUDIT_FIELDS`; `confirm_image_upload` ya no setea `role`/`image_status` |
| `app/services/importer/differ.py` | Removido `image_url` del tuple de diff |
| `app/api/routes/products.py` | Removido query param `image_status` y arg `ProductFilters` en `/facets`; `display_pair.primary_image_url=None` |
| `app/repositories/product.py` | `ProductImageRepository.list_for_sku` ordena por `(is_primary, kind, position)` (era `role`) |
| `scripts/populate_demo_product.py` | Removido `image_status='mirrored'` |
| `scripts/sql/inspect_product.sql` | Quitada sección "Imágenes legacy" |
| Tests: `test_products_wave2.py`, `test_facets.py`, `test_facets_service.py`, `test_products_api_stage3.py` | Actualizados |

### 1.2 Fase 0 frontend — unify ProductAsset + active helper

| Archivo | Cambio |
|---|---|
| `lib/api/endpoints/products.ts` | Eliminados `ProductImage` y `ProductImageRecord`; añadido `ProductAsset` único con `AssetKind`+`AssetStatus`+`ProductAssetUrls`; removido `role?` de `ImageConfirmPayload` |
| `lib/hooks/products/use-product-images.ts` | Migrado a `ProductAsset` |
| `components/domain/image-gallery.tsx` | Consume `img.alt_text` + `img.urls.thumb_400 ?? urls.original ?? original_url` (bug latente fixeado: FE asumía `img.url`/`img.alt`, backend devolvía `urls`/`alt_text`) |
| `components/domain/image-uploader.tsx` | Callback `onUploaded` tipado como `ProductAsset` |
| `lib/utils/product-lifecycle.ts` | **Nuevo.** Exporta `isProductActive(p) = p.lifecycle_status === "active"` |

### 1.3 FastAPI 204 + `from __future__ import annotations` — bug cross-cutting

**Causa raíz:** con `from __future__ import annotations`, `-> None` se evalúa como `NoneType` (truthy) en lugar de `None` (falsy). FastAPI 0.115 `APIRoute.__init__` línea 506 `if self.response_model: assert is_body_allowed_for_status_code(status_code)` dispara para `status_code=204`.

**Fix aplicado:** añadir `response_model=None` explícito a ~22 rutas en 4 archivos:

| Archivo | Endpoints fixeados |
|---|---|
| `app/api/routes/vocabularies.py` | 8 (certifications, applications, brands, families, subfamilies, types — admin + product sub-resource) |
| `app/api/routes/products_display.py` | 2 (PUT/DELETE `/display-pair`) |
| `app/api/routes/taxonomy_extras.py` | 10 (divisions, series-tiers, series, links, translations) |
| `app/api/routes/products.py` | 3 (delete_material, delete_connection, delete_tech_table) |

**Impacto:** antes bloqueaba colección de `tests/unit/api/*` enteros. Ahora todos los tests/api se ejecutan.

### 1.4 Stage 2 cleanup (heredado del trabajo en flight)

| Archivo | Cambio |
|---|---|
| `app/schemas/products.py` | Removidos `dn_real`, `iso5211_interface` de `ProductBase`/`ProductPatch`/`ProductResponse`. Removidos validators huérfanos `_validate_manufacturing_method` y `_validate_actuator` (campos viven en `specs` JSONB desde mig 043) |

**Decisión usuario aplicada:** `dn` ≡ `dn_real` → `dn_real` se droppea de Pydantic (la mig 043 lo había movido a `specs`; el usuario lo ratifica como duplicado).

### 1.5 Bug fix — `ProductAssetResponse.asset_meta` alias bidireccional

| Archivo | Cambio |
|---|---|
| `app/schemas/assets.py:325` | `asset_meta` ahora tiene `validation_alias="metadata"` + `serialization_alias="metadata"` (antes solo serialization). Permite input JSON con clave `metadata` y output JSON con `metadata`, sin chocar con `MetaData()` de SQLAlchemy en `from_attributes`. |

---

## 2. Estado de tests

| Suite | Antes | Después |
|---|---|---|
| `tests/unit/*` excluding api | 848 pass / 5 fail / 4 skip | **1034 pass / 0 fail / 4 skip** |
| `tests/unit/api/*` | 2 errores de colección (no cargaban) | Todos cargan y corren |

Tiempo: ~96s end-to-end.

---

## 3. Divergencia de ramas — el bloqueador

### 3.1 Estado git

```
worktree main                          → C:\BR-Github\br-mt\br-mt-ecommerce\           (HEAD: 1da0cc9)
worktree feat/taxonomy-registry        → C:\BR-Github\br-mt\br-mt-ecommerce-taxonomy\  (HEAD: 13fade0)
```

### 3.2 Migraciones divergentes

| Revisión | En main (working tree) | En feat/taxonomy-registry (committed) |
|---|---|---|
| `20260508_041` | committed (compartido) | committed (compartido) |
| `20260508_042` | `taxonomy.py` (uncommitted) | `brands_families_subfamilies_types.py` (committed) |
| `20260508_043` | `specs_consolidation.py` (uncommitted) | — (no existe) |
| `20260509_044` | committed (compartido) | committed (compartido) |
| `20260509_045` | committed (compartido) | committed (compartido) |
| `20260509_046` | committed (compartido) | committed (compartido) |
| `20260509_047` | committed (compartido) | committed (compartido) |
| `20260509_048` | committed (compartido) | committed (compartido) |
| `20260511_049` | `drop_legacy_image_and_role.py` (mi Fase 0, uncommitted) | `taxonomy_registry.py` (committed) |
| `20260511_050` | — | `taxonomy_backfill_sync.py` (committed) |
| `20260511_051` | — | `fix_closure_trigger_on_delete.py` (committed) |
| `20260512_052` | — | `family_to_registry.py` (committed) |

### 3.3 Docker container

```
mt-backend mount: C:\BR-Github\br-mt\br-mt-ecommerce-taxonomy\mt-pricing-backend\app  →  /app/app
mt-backend mount: C:\BR-Github\br-mt\br-mt-ecommerce-taxonomy\mt-pricing-backend\alembic  →  /app/alembic
```

El Docker compose se levantó desde el worktree de taxonomy (no desde main). Por tanto **redesplegar Docker con mi código de main es imposible sin cambiar de directorio de compose** — y al hacerlo se pierde el estado activo de taxonomy.

### 3.4 Working tree changes en feat/taxonomy-registry

```
M docker-compose.dev.yml
M mt-pricing-backend/app/api/routes/__init__.py
M mt-pricing-backend/app/api/routes/products.py
M mt-pricing-backend/app/api/routes/vocabularies.py        ← conflicto certero con mi 204 fix
M mt-pricing-frontend/...catalogo/...                       ← varios FE
D mt-pricing-frontend/app/(app)/products/...                ← borrado masivo (consolidación catalogo)
D mt-pricing-frontend/tests/unit/products/*                 ← borrado tests viejos
... (≈ 25 archivos modificados/borrados)
```

---

## 4. Por qué no procedí con Fase 1+

| Fase | Razón de bloqueo |
|---|---|
| 1 (catálogo families/categories/series/brands) | **Ya implementada** en feat/taxonomy-registry (commits acab332 → 13fade0). Reimplementar en main es duplicación; mergear sin reconciliación previa es destructivo. |
| 2 (EAV tipado) | Depende de Fase 1 estabilizada en una sola rama. |
| 3 (tablas técnicas granulares) | Depende de Fase 2. |
| 4 (assets polimórficos + documents) | Independiente técnicamente pero requiere base estable. |
| 5 (spare parts DN range) | Depende de Fase 1 (taxonomy de productos). |
| B (drop name_en/description_en/marketing_copy_en/tags/active) | Requiere todas las fases anteriores completas. |

---

## 5. Lo que necesita el usuario (acciones humanas)

### 5.1 Decisiones de proceso (no técnicas, no las puedo tomar yo)

1. **Branch strategy para Fase 0:** opciones
   - (a) Commit mi Fase 0 en main → mergear taxonomy → main → rebase Fase 0 sobre el merge
   - (b) Cherry-pick mi Fase 0 a feat/taxonomy-registry → rename mig 049 a 053 → reaplicar 204 fix donde no coincida
   - (c) Esperar a que taxonomy termine y mergee a main, luego aplicar Fase 0 limpio encima

2. **Estrategia de continuación de fases:** ¿paralelo o secuencial?
   - Paralelo requiere coordinación cuidadosa de migraciones y schemas
   - Secuencial es seguro pero lento (12 semanas estimadas)

### 5.2 Acciones técnicas autorizadas explícitamente para mí

- ⚠️ NO he commiteado nada — esperando autorización explícita ("commitea Fase 0 a main")
- ⚠️ NO he tocado el worktree de taxonomy — esperando instrucción explícita
- ⚠️ NO he redeployado Docker — clobbearea trabajo activo

---

## 6. Archivos que cambié (lista completa para code review)

### Backend (`mt-pricing-backend/`)
```
alembic/versions/20260511_049_drop_legacy_image_and_role.py   (NEW)
app/db/models/product.py                                      (M)
app/schemas/products.py                                       (M)
app/schemas/assets.py                                         (M)
app/schemas/facets.py                                         (M)
app/services/products/facets_service.py                       (M)
app/services/products/product_service.py                      (M)
app/services/importer/differ.py                               (M)
app/api/routes/products.py                                    (M)
app/api/routes/vocabularies.py                                (M)
app/api/routes/products_display.py                            (M)
app/api/routes/taxonomy_extras.py                             (M)
app/repositories/product.py                                   (M)
scripts/populate_demo_product.py                              (M)
scripts/sql/inspect_product.sql                               (M)
tests/unit/schemas/test_products_wave2.py                     (M)
tests/unit/schemas/test_facets.py                             (M)
tests/unit/services/products/test_facets_service.py           (M)
tests/unit/api/test_products_api_stage3.py                    (M)
```

### Frontend (`mt-pricing-frontend/`)
```
lib/api/endpoints/products.ts                                 (M)
lib/hooks/products/use-product-images.ts                      (M)
lib/utils/product-lifecycle.ts                                (NEW)
components/domain/image-gallery.tsx                           (M)
components/domain/image-uploader.tsx                          (M)
```

### Documentación
```
_bmad-output/implementation-artifacts/comparativa-modelo-pim-propuesto-vs-implementado-2026-05-11.md
_bmad-output/implementation-artifacts/fase0-cierre-y-reconciliacion-2026-05-11.md   (este archivo)
```

---

## 7. Recomendación próximo paso (mi voto)

**Opción (c)** — esperar a que el usuario cierre taxonomy y mergee a main, después aplicar Fase 0 limpio.

Razones:
- Taxonomy está mucho más avanzado y maduro (5+ commits específicos + UI completa)
- Fase 0 es 4 columnas + 22 fixes triviales — se rehacen rápido sobre cualquier base
- Evita conflictos en `vocabularies.py`, `products.py`, `facets_service.py` que ambas ramas modifican
- No requiere reescribir mi migración 049 (rename + rebase down_revision)

**Tiempo estimado de reaplicación post-merge:** 30-60 min con un agente dedicado.

— Fin —
