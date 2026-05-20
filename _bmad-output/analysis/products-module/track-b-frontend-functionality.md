# Track B — Funcionalidad Frontend
**Fecha:** 2026-05-20

## B1 — Flujos de usuario implementados

| Flujo | Estado | Gaps detectados |
|-------|--------|----------------|
| Búsqueda y filtrado en `/catalogo` | Completo | Ninguno. Filtros facetados con URL state, debounce 300ms, saved views, paginación cursor, vista tabla/galería. |
| Crear producto (wizard `/catalogo/nuevo`) | Completo | `ProductWizard` con 4 pasos. Redirige al detalle tras crear. |
| Editar producto (`[sku]/edit`) | Completo | Reutiliza `ProductWizard` con `mode="edit"`. Optimistic update en lista. |
| Enriquecer via PDF (`[sku]/enriquecer`) | Completo | 3 pasos: dropzone → diff review con selección campo/SKU → resultado. Aplica a toda la serie. |
| Enriquecer fichas técnicas (`/fichas`) | Completo | Igual al anterior pero acepta PDFs multi-serie, muestra certificados y flow-data extraídos. |
| Subir imágenes (`[sku]/imagenes`) | Completo | Signed URL → S3 upload → confirm. Galería, set primary, delete con optimistic update. |
| Gestionar traducciones (`[sku]/traducciones`) | Completo | ES + AR con formularios, draft/approve workflow. Expandibles marketing y SEO. |
| Ver costos (`[sku]/costos`) | Completo | Tabla por scheme × supplier con breakdown. Create/edit en sheet lateral. Toggle histórico. |
| Ver datasheets (`[sku]/datasheets`) | Completo | Lista con signed URL download. Wizard upload: dropzone → preview extracción → apply+polling status. |
| Gestionar mercados/releases (`[sku]/mercados`) | Completo | Lista releases con activate/deactivate. Dialog 3 pasos para crear release. |
| Gestionar unidades (`[sku]/unidades`) | Completo | Muestra UoM base + tabla de conversiones. Dialog para crear conversión, delete con optimistic invalidate. |
| Recambios y compatibilidad (`[sku]/recambios`) | Completo | Lista de enlaces outgoing + form para añadir. Remove con mutation. |
| Auditoría (`[sku]/audit`) | Completo | Toggle tabla densa / timeline rico. Filtros por entity type (products, costs, prices, fx_rates, translations). |
| Validación matches (`/catalogo/validacion`) | Completo | SKU queue dinámica, candidates con validate/discard, re-scrape, keyboard nav, CSV export. |
| Exportar CSV (`/catalogo`) | Completo | Exporta página actual o selección. |
| Bulk actions (`/catalogo`) | **Parcial** | Exportar CSV funciona. Activar, Archivar, Asignar familia muestran `toast.info("…próximamente")` — no implementados. |
| Duplicar SKU (hover acción en tabla) | **No implementado** | `toast.info("Duplicar — próximamente")`. |
| Importar PIM (botón Importer) | Redirección a `/imports` | El botón existe pero va a ruta separada no auditada aquí. |

## B2 — Estados loading/error/empty por tab

| Tab | isLoading | isError | isEmpty | Stale data |
|-----|-----------|---------|---------|------------|
| audit | ✅ (delegado a `AuditTable`/`AuditTimelineRich`) | ✅ (delegado) | ✅ (delegado) | ✅ React Query muestra datos previos |
| costos | ✅ `CostTable` muestra skeleton vía prop `loading` | ✅ Renderiza `MtError` con retry a nivel SectionCard | ⚠️ `CostTable` recibe array vacío, comportamiento depende del componente hijo | ✅ |
| datasheets | ✅ `MtSkeleton` ×2 en `DatasheetsList` | ✅ `MtError` con retry | ✅ `MtEmpty` con hint | ✅ |
| edit | ✅ `Skeleton` h-96 | ❌ Retorna `null` silencioso en `isError` sin mensaje ni retry | ❌ No aplica (detalle forzado) | ✅ |
| enriquecer | ✅ Dropzone muestra spinner animado mientras `isPending` | ✅ Banner de error inline en Dropzone y DiffStep | ⚠️ No hay estado "sin datos" separado; la dropzone es el punto de entrada | N/A (mutation) |
| imagenes | ✅ `Skeleton` h-64 | ❌ Retorna `null` silencioso si `!product` (combina loading+error sin distinguirlos) | ❌ No aplica (depende de `useProduct`, no de la query de imágenes) | ✅ |
| mercados | ✅ Card skeleton con `Skeleton` h-40 | ✅ Card con texto `text-destructive`, pero sin botón retry | ✅ Placeholder ilustrado con texto explicativo | ✅ |
| recambios | ✅ `Skeleton` ×2 | ✅ `<p role="alert">` con mensaje de error, sin retry | ✅ `<p>Sin enlaces todavía.</p>` | ✅ |
| traducciones | ✅ Grid de 3 Skeletons | ❌ Retorna `null` silencioso si `!product` (isError no manejado explícitamente) | ❌ No aplica | ✅ |
| unidades | ✅ `Skeleton` ×2 cards | ❌ No hay rama `isError` — si `useProduct` falla retorna `null`, si `useQuery(conversions)` falla muestra nada | ✅ Placeholder ilustrado dentro de la tabla de conversiones | ✅ |
| catalogo (lista) | ✅ 12 filas skeleton (tabla) / 12 cards (grid) | ✅ `MtError` con retry, pero sólo arriba del contenido, no reemplaza la tabla | ✅ "Sin resultados" con chips para limpiar filtros | ✅ isFetchingNextPage visible en Paginator |
| validacion | ✅ 5 skeleton cards de candidatos | ✅ `MtError` con retry | ✅ `MtEmpty` con hint | ✅ |

**Gaps críticos de error handling:**
- `edit/_client.tsx` línea 20–24: `if (isError || !product) return null` — fallo silencioso sin feedback al usuario.
- `imagenes/_client.tsx` línea 11–12: `if (!product) return null` — no distingue entre loading terminado sin datos y error.
- `traducciones/_client.tsx` línea 65: `if (!product) return null` — igual que imagenes.
- `unidades/_client.tsx`: `useProduct` y `useQuery(conversions)` fallan silenciosamente.
- `mercados/_client.tsx` línea 325–328: Error card sin botón retry.
- `recambios/_client.tsx` línea 136: Alert de error sin botón retry.

## B3 — React Query staleTime compliance

| Hook / componente | queryKey | staleTime | Tipo dato | ¿Cumple? |
|-------------------|----------|-----------|-----------|---------|
| `useProduct` | `["products","detail",idOrSku]` | 60_000 ms | Detalle producto | ✅ |
| `useProducts` | `["products","list",filters]` | 30_000 ms | Listado paginado | ✅ |
| `useProductTranslations` | `["products","detail",id,"translations"]` | 30_000 ms | Detalle producto | ❌ Debería ser ≥60_000 |
| `useProductImages` | `["products","detail",id,"images"]` | 30_000 ms | Detalle producto | ❌ Debería ser ≥60_000 |
| `useProductBoreDimensions` | `["products","detail",id,"bore-dimensions"]` | 60_000 ms | Detalle producto | ✅ |
| `useProductCertificates` | `["products",sku,"certificates"]` | 120_000 ms | Detalle producto | ✅ |
| `useProductFlowData` | `["products",sku,"flow-data"]` | 120_000 ms | Detalle producto | ✅ |
| `useProductMaterials` | `["products",sku,"materials"]` | 120_000 ms | Detalle producto | ✅ |
| `useFacets` | `["products","facets",filters]` | 30_000 ms | Listado paginado | ✅ |
| `seriesListQ` (inline `catalogo/page.tsx`) | `["series","public","list-page"]` | 300_000 ms | Vocabulario | ✅ |
| `materialsListQ` (inline `catalogo/page.tsx`) | `["materials","public","list-page"]` | 300_000 ms | Vocabulario | ✅ |
| `useQuery` mercados/releases (inline) | `["product-releases",sku]` | 30_000 ms | Listado paginado | ✅ |
| `useQuery` recambios/compatibility (inline) | `["products","detail",sku,"compatibility"]` | 30_000 ms | Detalle producto | ❌ Debería ser ≥60_000 |
| `useQuery` UoM conversions (inline) | `["product-uom-conversions",sku]` | 30_000 ms | Detalle producto | ❌ Debería ser ≥60_000 |
| `usePendingSkuQueue` (inline `validacion`) | `["matches","pending-sku-queue"]` | 60_000 ms | Listado paginado | ✅ |
| `queueStats` (inline `validacion`) | `["matches","sku-queue-stats"]` | 60_000 ms | Listado paginado | ✅ |

**Total no cumplidos:** 4/16 hooks/queries (25%)

## B4 — Queries duplicadas

**`useProduct(sku)` — riesgo de doble fetch por queryKey asimétrico:**

`useProduct` acepta tanto el SKU string (`"MT-VLV-0001"`) como un UUID. Genera queryKey `productKeys.detail(idOrSku)`. Los tabs `imagenes`, `traducciones`, `unidades` y `product-edit-drawer` llaman `useProduct(sku)` con el SKU string. `useProductImages` y `useConfirmImageUpload` usan `productKeys.images(productId)` donde `productId` es el UUID.

Cuando `useCreateProduct` hace `setQueryData`, siembra el caché en ambas claves (`productKeys.detail(id)` y `productKeys.detail(created.sku)`), lo que es correcto.

Sin embargo, si un componente llama `useProduct(sku)` (key: `detail/SKU`) y otro llama `useProduct(uuid)` (key: `detail/UUID`), React Query los trata como queries distintas y ejecuta dos requests HTTP separados para el mismo producto. Este escenario ocurre en el tab de imágenes: `ImagesTab` llama `useProduct(sku)` para obtener `product.id`, luego pasa ese `product.id` a `ImageGallery` / `ImageUploader`.

**`useProducts` — no hay duplicación.** `/catalogo` y `/products` (legacy) generan queryKeys diferentes por filtros distintos.

**Conclusión:** No hay queries duplicadas activas en la navegación normal. El riesgo de doble fetch SKU/UUID existe pero requiere que dos componentes en el mismo árbol llamen `useProduct` con identificadores de tipo diferente simultáneamente.

## B5 — Ruta /products

**Estado: legacy activa pero desvinculada de la navegación principal.**

- `app/(app)/products/page.tsx` es un Server Component con `ProductsToolbar` + `ProductsTable`. Está completamente funcional con estados loading/error/empty.
- El sidebar **no incluye `/products`**. Las entradas de catálogo en sidebar son: `/catalogo`, `/catalogo/validacion`, `/fichas`.
- `ProductsTable` enlaza los SKUs a `/products/${sku}` (no a `/catalogo/${sku}`). Existe `app/(app)/products/[sku]/` con componentes propios (`product-detail.tsx`, `images-tab.tsx`, `product-edit-form.tsx`).
- `/products` no aprovecha los filtros avanzados de `/catalogo` (sin facetas, sin saved views, sin vista galería). Sus filtros son de Sprint 1.
- Comparte el mismo queryKey factory `productKeys.list(filters)` que `/catalogo`, por lo que React Query reutiliza caché cuando los filtros coinciden.
- **Veredicto:** Ruta legacy de Sprint 1 que sobrevivió como código muerto. No hay entrada de navegación que lleve al usuario a `/products`. Candidata a eliminación.

## Top 5 problemas priorizados

1. **[Alto] Fallos silenciosos en 4 tabs del detalle.** Los tabs `edit`, `imagenes`, `traducciones` y `unidades` devuelven `null` cuando `useProduct` falla, sin ningún mensaje de error ni opción de retry. El usuario ve pantalla en blanco. Archivos: `edit/_client.tsx:20`, `imagenes/_client.tsx:11`, `traducciones/_client.tsx:65`, `unidades/_client.tsx:187`.

2. **[Alto] Bulk actions no implementadas expuestas en UI.** "Activar", "Archivar" y "Asignar familia" aparecen en la barra de selección múltiple pero invocan `toast.info("…próximamente")`. Generan expectativa de funcionalidad que no existe. `catalogo/page.tsx` líneas 766–793.

3. **[Medio] staleTime insuficiente en 4 hooks de datos de detalle.** `useProductTranslations` (30s), `useProductImages` (30s), recambios inline (30s) y unidades inline (30s) deberían usar ≥60_000ms. Genera refetches innecesarios al re-enfocar la ventana.

4. **[Medio] Ruta /products legacy desvinculada.** Duplica funcionalidad de `/catalogo` con versión desactualizada de Sprint 1. Enlaza a `/products/${sku}` en lugar de `/catalogo/${sku}`. Dead code navegacional que confunde a nuevos desarrolladores.

5. **[Bajo] Error states sin botón retry en mercados y recambios.** `mercados/_client.tsx:325` y `recambios/_client.tsx:136` muestran errores sin opción de retry. El usuario debe recargar la página. Difieren del patrón `MtError` establecido.
