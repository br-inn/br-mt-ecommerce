# Track E — Performance
**Fecha:** 2026-05-20

## E1 — Queries N+1

| Archivo | Línea aprox. | Descripción | Round-trips extra |
|---------|-------------|-------------|-------------------|
| `app/api/routes/products.py` | 250–286 | `_build_product_detail`: tras cargar el producto (1 query), ejecuta hasta 3 queries secuenciales adicionales: `SELECT Series WHERE id=series_id`, `SELECT Material WHERE id=material_id`, `SELECT Product WHERE sku=display_pair_sku`. Cada una es condicional pero independiente. | +3 por request (peor caso) |
| `app/services/products/effective_display_service.py` | 37–71 | `compute()`: Query 1 → `SELECT Product`. Query 2 → `SELECT ProductCertification WHERE product_sku=sku`. Query 3 (condicional) → `SELECT Series WHERE id=series_id`. Tres queries secuenciales que podrían consolidarse. | +2 (producto con serie) |
| `app/api/routes/taxonomy_registry.py` | 187–194, 211–216, 234–240, 377–437 | Todos los endpoints de nodos (`list_nodes`, `get_node`, `list_descendants`, CRUD admin) hacen `type_repo.get_by_slug(type_slug)` + segunda query sobre nodos. El tipo podría resolverse via JOIN. | +1 por cada request de nodo |
| `app/services/products/display_pair_service.py` | 50–51 | `set_pair()`: dos `_get_or_404()` secuenciales — un `SELECT Product WHERE sku=X` por cada SKU. Podría ser `SELECT ... WHERE sku IN (sku_a, sku_b)`. | +1 |
| `app/api/routes/ficha_enrich.py` | 158–173, 278–298 | `apply_ficha_enrich` y `apply_ficha_series`: bucle `for target_sku in body.apply_to_skus` — `FichaEnrichmentApplier.apply()` llama internamente a `_load_product(sku)` (SELECT individual) por cada SKU. `apply_ficha_series` pre-fetcha existencia con `IN` pero `applier.apply()` ignora ese resultado y re-carga. | +N (N = len(apply_to_skus)) |
| `app/api/routes/attributes.py` | 142–147 | `list_attribute_options`: `await service.get_definition(attr_id)` (verificación existencia) + `await service.list_options(attr_id)` (datos). Podrían combinarse retornando 404 si options está vacío. | +1 |

---

## E2 — selectinload vs joinedload

| Archivo | Relación | Tipo usado | Correcto? | Impacto |
|---------|---------|-----------|-----------|---------|
| `app/repositories/product.py:79` | `Product.model` (many-to-one) en `get_with_translations_and_images` | `selectinload` | NO — debería ser `joinedload` | Round-trip extra en cada carga de detalle de producto |
| `app/repositories/product.py:52` | `Product.model` (many-to-one) en `get_by_sku_for_matching` | `selectinload` | NO — debería ser `joinedload` | Round-trip extra en matching pipeline |
| `app/repositories/product.py:74` | `Product.translations` (one-to-many) | `selectinload` | SI | Correcto, evita producto cartesiano |
| `app/repositories/product.py:75` | `Product.assets` (one-to-many) | `selectinload` | SI | Correcto |
| `app/repositories/product.py:76–78` | `Product.product_divisions → division` (M:N) | `selectinload.selectinload` | SI | Correcto |
| `app/repositories/product.py:138` | `Product.translations` en `list_paginated_with_filters` | `selectinload` | SI | Correcto |
| `app/services/products/effective_display_service.py:54` | `ProductCertification.certification` (many-to-one) cargado en colección | `selectinload` | Aceptable | Menor — `joinedload` sería más eficiente |
| `app/services/products/effective_display_service.py:66–68` | `Series.series_certifications` (one-to-many) → `.certification` (many-to-one) | `selectinload.selectinload` | SI para la colección | El segundo nivel podría ser `joinedload` |

**Resumen:** 2 incumplimientos (`selectinload` sobre many-to-one en `Product.model`). No se detectaron `joinedload` sobre colecciones (que causarían producto cartesiano).

---

## E3 — include_total

**Estado: COMPLIANT.**

El flag `include_total` tiene `default=False` en el route `GET /products` (`products.py` línea 476) y en `ProductRepository.list_paginated_with_filters` (`product.py` línea 103). Cuando es `False`, se omite completamente el `SELECT count(*)` adicional.

El hook `useProducts` (`use-products.ts`) no pasa `include_total` en ningún caso. La página de catálogo (`catalogo/page.tsx`) obtiene el conteo de SKUs desde `useFacets` (`facetsData.total` / `facetsData.total_unfiltered`), evitando activar el COUNT caro en el listado.

---

## E4 — React Query staleTime compliance

| Hook | queryKey | staleTime (ms) | Tipo de dato | ¿Cumple? |
|------|----------|---------------|-------------|---------|
| `useProduct` (`use-product.ts`) | `["products","detail",id]` | 60 000 | Detalle producto | SI |
| `useProducts` (`use-products.ts`) | `["products","list",filters]` | 30 000 | Lista paginada | SI |
| `useProductImages` (`use-product-images.ts`) | `["products","detail",id,"images"]` | 30 000 | Sub-recurso detalle | NO (mínimo 60 000) |
| `useProductTranslations` (`use-translations.ts`) | `["products","detail",id,"translations"]` | 30 000 | Sub-recurso detalle | NO (mínimo 60 000) |
| `useProductBoreDimensions` (`use-bore-dimensions.ts`) | `["products","detail",id,"bore-dimensions"]` | 60 000 | Sub-recurso detalle | SI |
| `useProductCertificates` (`use-product-model.ts`) | `["products",sku,"certificates"]` | 120 000 | Sub-recurso detalle | SI |
| `useProductFlowData` (`use-product-model.ts`) | `["products",sku,"flow-data"]` | 120 000 | Sub-recurso detalle | SI |
| `useProductMaterials` (`use-product-model.ts`) | `["products",sku,"materials"]` | 120 000 | Sub-recurso detalle | SI |
| `useFacets` (`use-facets.ts`) | `["products","facets",filters]` | 30 000 | Lista paginada | SI |
| `seriesListQ` (inline `catalogo/page.tsx:197`) | `["series","public","list-page"]` | 300 000 | Vocabulario | SI |
| `materialsListQ` (inline `catalogo/page.tsx:202`) | `["materials","public","list-page"]` | 300 000 | Vocabulario | SI |

**Total no cumplidos: 2/11 hooks** (`useProductImages` y `useProductTranslations`).

**Observación adicional:** `useProductCertificates`, `useProductFlowData` y `useProductMaterials` en `use-product-model.ts` construyen queryKeys ad-hoc (`["products", sku, "certificates"]`) NO anidadas bajo `productKeys.detail(sku)`. Cuando se invalida el detalle con `qc.invalidateQueries({ queryKey: productKeys.detail(sku) })`, estos sub-recursos NO se invalidan automáticamente, generando posible inconsistencia de datos tras mutaciones (PATCH, PUT, etc.).

---

## E5 — Estrategia de carga de imágenes

| Componente | Imagen | fetchPriority | loading | decoding | ¿Correcto? |
|-----------|--------|--------------|---------|----------|-----------|
| `catalogo/[sku]/_components/product-header.tsx` (~línea 218) | Hero — única imagen above-the-fold en página de detalle | AUSENTE | AUSENTE | AUSENTE | NO |
| `catalogo/_components/product-grid-card.tsx` (línea 36) | Imágenes en galería | N/A | `"lazy"` | `"async"` | SI |
| `catalogo/page.tsx` (línea 939, tabla) | Thumbnails 40×40 en tabla de lista | N/A | `"lazy"` | `"async"` | SI |

**Detalle del incumplimiento en `product-header.tsx`:**

```tsx
// Estado actual (incorrecto):
<img src={product.primary_image_url} alt={getProductName(product)}
     className="h-[140px] w-[140px] rounded-lg object-cover" />

// Estado requerido por CLAUDE.md:
<img src={product.primary_image_url} alt={getProductName(product)}
     fetchPriority="high" decoding="async"
     className="h-[140px] w-[140px] rounded-lg object-cover" />
```

Ausencia de `fetchPriority="high"` penaliza el LCP (Largest Contentful Paint). Ausencia de `decoding="async"` bloquea el main thread durante el decode. No se detectó uso de `<Image>` de Next.js sin `width`/`height` explícitos.

---

## E6 — CacheControl

**Estado: COMPLIANT con una observación menor.**

`CacheControlMiddleware` (`app/core/middleware.py` líneas 90–115) está implementado y activo. Aplica `"private, max-age=60, stale-while-revalidate=30"` exclusivamente en respuestas `GET 200`, excluyendo `/health/*` y `/metrics`. Endpoints de mutación excluidos por guarda de método. Correctamente implementado.

**Observación — discrepancia con convención documentada:** `CLAUDE.md` especifica `private, max-age=60`. La implementación añade `stale-while-revalidate=30` (mejora operacional). No es un bug — se recomienda actualizar la convención para reflejar el valor real.

**Anomalía — `GET /products/export`:** Este endpoint devuelve `text/csv` con status `200` GET. El middleware le aplica `private, max-age=60` automáticamente. Un CSV de exportación no debería ser cacheado (refleja el estado en tiempo real). Debería añadir manualmente `response.headers["Cache-Control"] = "no-store"`.

---

## Top 5 cuellos de botella (priorizados por impacto)

1. **[Alto] Hero image sin `fetchPriority="high"` — impacto directo en LCP**
   `catalogo/[sku]/_components/product-header.tsx` (~línea 218). La imagen 140×140px es el candidato LCP más probable de la página de detalle. Fix trivial de 2 atributos con impacto medible en Core Web Vitals para todos los usuarios que abren una ficha de producto.

2. **[Alto] `_build_product_detail` — hasta +3 round-trips secuenciales por cada request de detalle**
   `app/api/routes/products.py` (líneas 250–286). Cada `GET /products/{sku}` y cada mutación que retorna `ProductDetail` ejecuta hasta 3 queries adicionales secuenciales (Series, Material, display_pair). Con el servidor en UAE y latencia ~10–20ms por round-trip a Postgres, esto añade hasta 60ms de latencia pura por request. Solución: `joinedload` para `series_id` y `material_id`, y resolver `display_pair` en la misma query con un self-join.

3. **[Medio] `FichaEnrichmentApplier` — N SELECTs individuales para N SKUs en bucle**
   `app/api/routes/ficha_enrich.py` (líneas 158–173, 278–298). Para una ficha de serie con 10–20 SKUs, el apply ejecuta 10–20 `SELECT Product WHERE sku=X` secuenciales. El pre-fetch bulk (`SELECT ... WHERE sku IN (...)`) que ya existe en `apply_ficha_series` debería pasarse al applier para evitar la recarga individual.

4. **[Medio] `selectinload(Product.model)` sobre many-to-one — round-trip extra en cada carga de detalle**
   `app/repositories/product.py` (líneas 52 y 79). `Product.model` es many-to-one. `selectinload` emite una segunda query en lugar de añadir un JOIN a la query principal. Cambiar a `joinedload` elimina un round-trip en cada carga de detalle y en el matching pipeline.

5. **[Bajo-Medio] queryKeys ad-hoc en sub-recursos del detalle — riesgo de datos stale tras mutaciones**
   `lib/hooks/products/use-product-model.ts`. `useProductCertificates`, `useProductFlowData` y `useProductMaterials` construyen sus queryKeys fuera de la jerarquía `productKeys.detail(sku)`. Tras mutaciones (PATCH, PUT, etc.) estos sub-recursos no se invalidan automáticamente. Corrección: usar `productKeys.detail(sku)` como prefijo, o añadir invalidaciones explícitas en los mutation hooks.
