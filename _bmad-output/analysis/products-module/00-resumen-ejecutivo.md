# Auditoría Módulo de Productos — Resumen Ejecutivo
**Fecha:** 2026-05-20
**Rama:** analysis/products-module-audit
**Tracks completados:** A (Backend), B (Frontend), C (UX), D (Seguridad), E (Performance), F (Código)

---

## Estado general del módulo

| Dimensión | Estado | Issues críticos | Issues medios |
|-----------|--------|----------------|---------------|
| A — Funcionalidad Backend | 🔴 Crítico | 2 | 3 |
| B — Funcionalidad Frontend | 🟡 Atención | 0 | 4 |
| C — UX / Usabilidad | 🟡 Atención | 1 | 4 |
| D — Seguridad | 🟡 Atención | 0 | 4 |
| E — Performance | 🟡 Atención | 0 | 4 |
| F — Calidad de Código | 🟡 Atención | 0 | 4 |

**Veredicto general:** El módulo es funcionalmente completo y tiene buenas bases (auth en 100% de endpoints, FSM de traducciones bien testeada, patrones React Query consistentes), pero acumula deuda técnica significativa centrada en cobertura de tests (62% de endpoints sin ningún test), hasta +3 round-trips extra por request de detalle de producto, y 4 tabs del detalle que fallan silenciosamente ante errores de red.

---

## Matriz de hallazgos

| ID | Track | Hallazgo | Severidad | Esfuerzo | Quick win? |
|----|-------|---------|-----------|----------|-----------|
| A-1 | Backend | 90/146 endpoints sin cobertura de tests (62%) — assets, releases, taxonomía admin, ficha-enrich/series/apply | Crítico | 40–60h | No |
| A-2 | Backend | `apply_ficha_series` hace `session.commit()` explícito mid-handler — posible commit parcial ante excepción | Alto | 2h | No |
| A-3 | Backend | `list_releases`, `list_uom_conversions`, `list_tech_tables` retornan 200+`[]` para SKUs inexistentes en lugar de 404 | Alto | 2h | Sí |
| A-4 | Backend | `set_primary_asset`, `archive_asset`, `restore_asset` retornan JSONResponse 200 en lugar de HTTPException 404 | Medio | 1h | Sí |
| A-5 | Backend | `list_datasheets` silencia fallos de Supabase Storage: `except Exception: signed_url = ""` sin logging | Medio | 1h | Sí |
| A-6 | Backend | `admin_list_series_certifications` y `get_resolved_view` sin `response_model` — sin validación ni contrato OpenAPI | Medio | 2h | No |
| A-7 | Backend | `list_releases` y `create_release` retornan ORM object directamente con `response_model` declarado — frágil con lazy-loads | Medio | 2h | No |
| B-1 | Frontend | 4 tabs (`edit`, `imagenes`, `traducciones`, `unidades`) devuelven `null` silencioso cuando `useProduct` falla | Alto | 3h | No |
| B-2 | Frontend | Bulk actions (Activar, Archivar, Asignar familia) expuestas en UI pero solo invocan `toast.info("…próximamente")` | Alto | — | No |
| B-3 | Frontend | `useProductTranslations`, `useProductImages`, recambios, unidades: staleTime 30s en lugar de ≥60s | Medio | 1h | Sí |
| B-4 | Frontend | Ruta `/products` legacy desvinculada de navegación — duplica `/catalogo` con versión de Sprint 1 | Medio | 4h | No |
| B-5 | Frontend | Error states sin botón retry en tabs `mercados` y `recambios` | Bajo | 1h | Sí |
| C-1 | UX | `window.confirm()` / `window.alert()` nativos en `validacion/page.tsx` — bloquean hilo, inaccesibles | Crítico | 2h | Sí |
| C-2 | UX | 5 tablas del módulo con `<th>` sin `scope="col"` — lectores de pantalla no pueden asociar headers | Mayor | 1h | Sí |
| C-3 | UX | Campos obligatorios (SKU, Nombre EN) sin indicación visual `*` en pasos 0, 2 y 3 del wizard | Mayor | 2h | Sí |
| C-4 | UX | Más de 60 strings hardcodeados sin i18n — bloqueante para añadir soporte de idioma inglés | Mayor | 8–12h | No |
| C-5 | UX | Inputs de búsqueda principal y facetas sin `<label>` ni `aria-label` — inaccesibles para lectores de pantalla | Mayor | 1h | Sí |
| C-6 | UX | Tab "Enriquecer" enterrado en overflow junto a "Auditoría" — acción operacional frecuente de difícil acceso | Menor | 0.5h | Sí |
| C-7 | UX | Mensajes de error en inglés visibles al usuario final en `product-specs-eav.tsx` | Menor | 0.5h | Sí |
| D-1 | Seguridad | Módulos adyacentes (`billing.py`, `finance.py`, `rule_engine.py`, `hitl_queue_price.py`) sin protección de auth | Alto | 4–6h | No |
| D-2 | Seguridad | `list_price`, `price_currency`, `tax_class` accesibles a todos los `products:read` sin permiso granular | Medio | 3h | No |
| D-3 | Seguridad | Granularidad de `products:write` demasiado amplia — desde edición de metadata hasta activación de releases | Medio | 4h | No |
| D-4 | Seguridad | `bytes_size` opcional en confirm upload — cliente puede eludir el límite de tamaño no enviando el campo | Medio | 3h | No |
| D-5 | Seguridad | `apiClient` (openapi-fetch) no adjunta Bearer token — rutas que lo usen directamente fallarán con 401 silencioso | Medio | 2h | No |
| D-6 | Seguridad | `text(f"...")` con parámetro `int` en `unmatched_offers.py:281` — anti-patrón SQL dinámico | Bajo | 0.5h | Sí |
| D-7 | Seguridad | `require_role` no tiene bypass de admin — inconsistente con `require_permissions` | Bajo | 1h | Sí |
| E-1 | Performance | Hero image en `product-header.tsx` sin `fetchPriority="high"` ni `decoding="async"` — impacto directo en LCP | Alto | 0.25h | Sí |
| E-2 | Performance | `_build_product_detail` ejecuta hasta +3 queries secuenciales por cada GET /products/{sku} | Alto | 4h | No |
| E-3 | Performance | `FichaEnrichmentApplier` hace N SELECTs individuales para N SKUs en bucle (aplica a toda la serie) | Medio | 3h | No |
| E-4 | Performance | `selectinload(Product.model)` sobre relación many-to-one — debería ser `joinedload` | Medio | 1h | Sí |
| E-5 | Performance | Sub-recursos detalle (`certificates`, `flow-data`, `materials`) con queryKeys fuera de jerarquía — no se invalidan con PATCH/PUT | Medio | 2h | No |
| E-6 | Performance | `GET /products/export` recibe `Cache-Control: private, max-age=60` del middleware — CSV no debería ser cacheado | Bajo | 0.25h | Sí |
| F-1 | Código | `product-wizard.tsx` — 977 líneas, 12 sub-componentes, lógica de negocio mezclada con render | Medio | 6–8h | No |
| F-2 | Código | `products.py` — 2 351 líneas, `_build_product_detail` y `export_products_csv` con lógica de negocio en el handler | Medio | 6–8h | No |
| F-3 | Código | `catalogo/page.tsx` — 1 209 líneas god component con tabla, filtros, modales, atajos de teclado | Medio | 8–10h | No |
| F-4 | Código | `_parse_iso` definido dos veces en `products.py` (L360 y L493) como closures locales independientes | Bajo | 1h | Sí |
| F-5 | Código | Design system mixto: 4 tabs usan MT primitives, 4 tabs usan shadcn/ui directo | Bajo | 3–4h | No |
| F-6 | Código | 5+ casts TypeScript (`Product & { id?: string }`, `base_uom`) por campos faltantes en tipo `Product` | Bajo | 2h | No |
| F-7 | Código | queryKeys inline en `use-product-model.ts`, `use-facets.ts`, tabs mercados/recambios/unidades — fuera de factory | Bajo | 1–2h | Sí |
| F-8 | Código | `# type: ignore[assignment]` en `get_facets` L690 por anti-patrón `= None` default en Depends | Bajo | 0.25h | Sí |
| F-9 | Código | `traducciones/_mt-client.tsx` — naming inconsistente con convención `_client.tsx` | Bajo | 0.25h | Sí |

---

## Top 10 hallazgos críticos

### 1. [Crítico] 90 endpoints sin cobertura de tests (62%)
**Track:** A — Backend | **Esfuerzo:** 40–60h | **Archivos:** `tests/integration/`, `tests/api/`
**Descripción:** Solo 38 de 146 endpoints tienen tests completos (happy + unhappy paths). Los endpoints sin ningún test incluyen todo el árbol de assets (upload, confirm, archive, restore), todos los releases (5 endpoints), todo el árbol de taxonomía admin, y `ficha-enrich/series/apply` que crea productos en masa.
**Impacto:** Un cambio en cualquiera de los 90 endpoints no cubiertos puede romper producción sin que CI lo detecte. `POST /ficha-enrich/series/apply` tiene el mayor riesgo — crea/modifica múltiples productos en una sola llamada.
**Acción requerida:** Plan de tests por sprints: priorizar assets + releases (funcionalidades M1), luego taxonomía admin, luego series apply. Usar fixtures de integración existentes como base.

### 2. [Alto] `apply_ficha_series` hace `session.commit()` explícito mid-handler
**Track:** A — Backend | **Esfuerzo:** 2h | **Archivos:** `app/api/routes/ficha_enrich.py:319`
**Descripción:** Es el único endpoint del módulo que llama `session.commit()` explícitamente en el handler. Si `write_model_data` o `save_ficha_document` lanzan una excepción después de que algunos SKUs se han aplicado, el commit parcial ya ocurrió y no hay rollback automático.
**Impacto:** Puede dejar la DB con productos parcialmente creados o enriquecidos en un estado inconsistente. La operación afecta hasta decenas de SKUs de una vez.
**Acción requerida:** Remover el `session.commit()` explícito y confiar en el session middleware de la aplicación. Envolver toda la operación en una transacción única mediante context manager si se necesita atomicidad garantizada.

### 3. [Alto] Módulos financieros sin protección de autenticación
**Track:** D — Seguridad | **Esfuerzo:** 4–6h | **Archivos:** `billing.py`, `finance.py`, `rule_engine.py`, `hitl_queue_price.py`
**Descripción:** Fuera del módulo de productos pero en la misma aplicación: estos módulos tienen endpoints completamente sin protección de auth. Exponen facturas, P&L, balance sheet, aging de cobros y configuración de reglas de pricing.
**Impacto:** Cualquier usuario sin autenticar puede acceder a datos financieros críticos. Es el hallazgo de seguridad más grave de toda la auditoría.
**Acción requerida:** Añadir `Depends(require_permissions("finance:read"))` / `Depends(require_permissions("admin:pricing"))` a todos los endpoints afectados. Auditar también `channels.py` y `price_intelligence.py` mencionados en el reporte.

### 4. [Alto] 4 tabs del detalle fallan silenciosamente ante errores de red
**Track:** B — Frontend | **Esfuerzo:** 3h | **Archivos:** `edit/_client.tsx:20`, `imagenes/_client.tsx:11`, `traducciones/_client.tsx:65`, `unidades/_client.tsx:187`
**Descripción:** Los tabs `edit`, `imagenes`, `traducciones` y `unidades` devuelven `null` cuando `useProduct` falla (error de red, 401, 500). El usuario ve una pantalla en blanco sin ningún mensaje de error ni opción de retry.
**Impacto:** Fallo silencioso en 4 de las 10 pantallas del detalle de producto. Usuario sin capacidad de diagnosticar ni recuperarse del error.
**Acción requerida:** Reemplazar `if (isError || !product) return null` por render de `<MtError message={...} onRetry={() => refetch()} />` en cada tab afectado, siguiendo el patrón ya implementado en `datasheets/_client.tsx`.

### 5. [Alto] `_build_product_detail` ejecuta hasta +3 round-trips por cada GET /products/{sku}
**Track:** E — Performance | **Esfuerzo:** 4h | **Archivos:** `app/api/routes/products.py:250–286`
**Descripción:** Por cada request de detalle de producto, se ejecutan hasta 3 queries adicionales secuenciales: `SELECT Series WHERE id=series_id`, `SELECT Material WHERE id=material_id`, `SELECT Product WHERE sku=display_pair_sku`. Con el servidor en UAE y latencia ~10–20ms por round-trip, esto añade hasta 60ms de latencia extra por request.
**Impacto:** Directriz de performance de CLAUDE.md violada. Afecta a todas las páginas de detalle de producto — la pantalla más visitada del módulo.
**Acción requerida:** Mover `_build_product_detail` a `ProductService`. Reemplazar las 3 queries secuenciales con `joinedload` para `series_id` y `material_id`, y un self-join para `display_pair_sku`.

### 6. [Alto] Bulk actions expuestas en UI sin implementación
**Track:** B — Frontend | **Esfuerzo:** — (decisión de producto) | **Archivos:** `catalogo/page.tsx:766–793`
**Descripción:** Las acciones "Activar", "Archivar" y "Asignar familia" aparecen en la barra de selección múltiple del catálogo pero solo invocan `toast.info("…próximamente")`.
**Impacto:** Genera expectativa de funcionalidad que no existe. Los usuarios pueden intentar operaciones masivas críticas y recibir solo una notificación de "próximamente". Daña la confianza en el sistema.
**Acción requerida:** Implementar las acciones (requiere endpoints backend de bulk update) o remover temporalmente de la UI hasta que estén listas. Decisión de producto requerida.

### 7. [Crítico UX] Diálogos nativos bloqueantes en flujo de validación de matches
**Track:** C — UX | **Esfuerzo:** 2h | **Archivos:** `validacion/page.tsx:138–143`
**Descripción:** El flujo de validación de matches usa `window.confirm()` y `window.alert()` para confirmar borrados masivos y reportar errores. Estos diálogos bloquean el hilo principal del navegador, no pueden ser estilizados con el design system, son inaccesibles en algunos lectores de pantalla y son bloqueados por defecto en Chrome en iframes.
**Impacto:** Todos los usuarios del flujo de validación de matches están afectados. Este flujo es operacional y se usa frecuentemente para la carga de precios y compatibilidades.
**Acción requerida:** Reemplazar `window.confirm()` con el componente `<AlertDialog>` de Shadcn/ui (ya disponible en el proyecto) y `window.alert()` con `toast.error()`.

### 8. [Medio] `list_price`, `price_currency` y `tax_class` accesibles a todos los `products:read`
**Track:** D — Seguridad | **Esfuerzo:** 3h | **Archivos:** `app/api/routes/products.py` (GET /{sku}/releases)
**Descripción:** `ProductReleaseResponse` expone datos de pricing (precio de lista por mercado, moneda, clase de impuesto) a cualquier usuario autenticado con `products:read`. No existe un permiso granular para separar quién puede ver precios de lista.
**Impacto:** En un sistema PIM interno con usuarios de roles variados (comercial, logística, TI), el precio de lista es información de negociación sensible que no todos los roles deberían ver.
**Acción requerida:** Crear permiso `products:releases:read` y reemplazar la dependency en el endpoint `GET /{sku}/releases`. Actualizar la asignación de roles en `public.roles`.

### 9. [Alto] Hero image sin `fetchPriority="high"` — impacto directo en LCP
**Track:** E — Performance | **Esfuerzo:** 0.25h | **Archivos:** `catalogo/[sku]/_components/product-header.tsx:~218`
**Descripción:** La imagen principal de 140×140px en el detalle de producto no tiene `fetchPriority="high"` ni `decoding="async"`. Es el candidato LCP más probable de la página de detalle.
**Impacto:** Penaliza el LCP (Largest Contentful Paint) en todas las páginas de detalle de producto. Fix trivial con impacto medible en Core Web Vitals para todos los usuarios.
**Acción requerida:** Añadir `fetchPriority="high" decoding="async"` a la imagen en `product-header.tsx`. Es un cambio de 1 línea.

### 10. [Alto] 5 tablas del módulo sin `scope="col"` en headers
**Track:** C — UX | **Esfuerzo:** 1h | **Archivos:** `product-certificates.tsx:44–49`, `product-bore-dimensions.tsx:84–110`, `product-materials.tsx:55–69`, `product-flow-data.tsx:30–33`, `page.tsx:860–880`
**Descripción:** Las tablas de certificados, dimensiones por norma, materiales, coeficientes de flujo y la tabla principal del catálogo usan `<th>` sin el atributo `scope="col"`. Los lectores de pantalla (NVDA, JAWS, VoiceOver) no pueden asociar correctamente los headers a las celdas.
**Impacto:** Las tablas de dimensiones y certificados son el núcleo de la ficha técnica del producto. Todos los usuarios con discapacidad visual que usen lectores de pantalla no pueden navegar estas tablas correctamente.
**Acción requerida:** Añadir `scope="col"` a todos los `<th>` en las tablas listadas. Cambio de 1 atributo por tabla, sin riesgo de regresión.

---

## Quick wins (< 2h)

| # | Hallazgo | Track | Acción | Esfuerzo |
|---|---------|-------|--------|----------|
| 1 | `list_releases`/`list_uom_conversions`/`list_tech_tables` retornan 200+`[]` para SKUs inexistentes | A | Añadir validación de existencia de SKU antes de retornar lista vacía | 2h |
| 2 | `set_primary_asset`, `archive_asset`, `restore_asset` retornan JSONResponse 200 en lugar de HTTPException 404 | A | Cambiar `_problem()` por `raise HTTPException(status_code=404, ...)` | 1h |
| 3 | `list_datasheets` silencia fallos de storage sin logging | A | Añadir `logger.error(...)` en el `except` y devolver error parcial al cliente | 1h |
| 4 | staleTime incorrecto en 4 hooks de datos de detalle (30s → 60s) | B | Actualizar `staleTime` en `use-product-images.ts`, `use-translations.ts`, hooks inline de recambios y unidades | 1h |
| 5 | Error states sin botón retry en `mercados` y `recambios` | B | Añadir `onRetry={() => refetch()}` al componente de error en ambos tabs | 1h |
| 6 | `window.confirm()` / `window.alert()` en `validacion/page.tsx` | C | Reemplazar con `<AlertDialog>` de Shadcn/ui y `toast.error()` | 2h |
| 7 | 5 tablas sin `scope="col"` en headers | C | Añadir `scope="col"` a todos los `<th>` de las tablas listadas | 1h |
| 8 | Campos obligatorios sin indicación visual `*` en wizard pasos 0, 2 y 3 | C | Añadir `<span className="text-destructive ml-0.5">*</span>` junto a labels requeridos | 2h |
| 9 | Inputs de búsqueda (principal + facetas) sin `aria-label` | C | Añadir `aria-label="Buscar productos"` y `aria-label="Filtrar {sección}"` | 1h |
| 10 | Tab "Enriquecer" en overflow — mover a tabs primarios | C | Reorganizar el array de tabs en `product-tabs.tsx` | 0.5h |
| 11 | Mensajes de error en inglés en `product-specs-eav.tsx` | C | Mover strings a `messages/es.json` y usar `t()` | 0.5h |
| 12 | Hero image sin `fetchPriority="high"` | E | Añadir atributos `fetchPriority` y `decoding` a `<img>` en `product-header.tsx` | 0.25h |
| 13 | `selectinload(Product.model)` sobre many-to-one | E | Cambiar a `joinedload(Product.model)` en `product.py` L52 y L79 | 1h |
| 14 | `GET /products/export` recibe Cache-Control incorrecto | E | Añadir `response.headers["Cache-Control"] = "no-store"` en `export_products_csv` | 0.25h |
| 15 | `_parse_iso` duplicado en `products.py` | F | Extraer función al nivel del módulo o a `app/api/utils.py` | 1h |
| 16 | queryKeys inline fuera de factory (`use-product-model.ts`, `use-facets.ts`, tabs) | F | Añadir `productKeys.releases()`, `.compatibility()`, `.uomConversions()` a `query-keys.ts` y usarlos | 1–2h |
| 17 | `# type: ignore[assignment]` en `get_facets` L690 | F | Eliminar `= None` default y dejar solo `Annotated[..., Depends(...)]` | 0.25h |
| 18 | `traducciones/_mt-client.tsx` — naming inconsistente | F | Renombrar a `_client.tsx` y actualizar import en `page.tsx` | 0.25h |
| 19 | `text(f"...")` con `int` en `unmatched_offers.py:281` | D | Reescribir con `text(...).bindparams(days=...)` | 0.5h |
| 20 | `require_role` sin bypass de admin | D | Añadir bypass de admin en `require_role` de `deps.py` consistente con `require_permissions` | 1h |

---

## Plan de remediation

### Fase 1 — Críticos (Sprint inmediato)

**Story 1A — Seguridad: autenticación en módulos financieros**
Añadir `require_permissions` a todos los endpoints de `billing.py`, `finance.py`, `rule_engine.py`, `hitl_queue_price.py`. Auditar también `channels.py` y `price_intelligence.py`.
Esfuerzo: 4–6h | Tipo: implementación directa

**Story 1B — Backend: atomicidad en `apply_ficha_series`**
Remover `session.commit()` explícito del handler `apply_ficha_series`. Verificar que el session middleware del framework cubre la transacción. Añadir test de integración que simule fallo mid-apply.
Esfuerzo: 2h | Tipo: implementación directa

**Story 1C — Performance: fix hero image LCP (Quick Win)**
Añadir `fetchPriority="high" decoding="async"` a la imagen de `product-header.tsx`. Añadir `response.headers["Cache-Control"] = "no-store"` en `export_products_csv`. Cambiar `selectinload` → `joinedload` para `Product.model` en `product.py`.
Esfuerzo: 1.5h | Tipo: quick wins agrupados

**Story 1D — Frontend: errores silenciosos en 4 tabs + Quick Wins UX**
Reemplazar retornos `null` silenciosos en tabs `edit`, `imagenes`, `traducciones`, `unidades` con `<MtError>`. Reemplazar `window.confirm`/`window.alert` con `<AlertDialog>`. Añadir `scope="col"` a las 5 tablas. Corregir `aria-label` en inputs de búsqueda. Corregir `*` en campos obligatorios del wizard.
Esfuerzo: 6h | Tipo: implementación directa

### Fase 2 — Altos (Próximo sprint)

**Story 2A — Performance: eliminar N+1 en `_build_product_detail`**
Mover `_build_product_detail` de `products.py` a `ProductService`. Reemplazar las 3 queries secuenciales con `joinedload` para `series` y `material`, y JOIN/subquery para `display_pair_sku`.
Requiere: spike de 2h para evaluar impacto en ORM antes de implementar.
Esfuerzo: 4h + 2h spike | Tipo: spike técnico requerido primero

**Story 2B — Backend: corregir error handling (Quick Wins)**
`list_releases`/`list_uom_conversions`/`list_tech_tables`: añadir validación de existencia de SKU. `set_primary_asset`/`archive_asset`/`restore_asset`: cambiar JSONResponse → HTTPException. `list_datasheets`: añadir logging en except. `admin_list_series_certifications` y `get_resolved_view`: añadir `response_model`.
Esfuerzo: 5h | Tipo: implementación directa

**Story 2C — Seguridad: granularidad de permisos en releases y write**
Crear permiso `products:releases:read`. Actualizar `GET /{sku}/releases` para requerir el nuevo permiso. Validar `bytes_size` en el confirm de upload llamando a Supabase Storage API. Añadir interceptor de auth a `apiClient`.
Esfuerzo: 8h | Tipo: requiere spike para definir modelo de permisos ampliado

**Story 2D — Tests: cobertura mínima en endpoints de mayor riesgo**
Escribir tests de integración para: assets (upload → confirm → primary → archive → restore → delete), releases (create → activate → deactivate), `ficha-enrich/series/apply` (happy path + fallo mid-apply).
Esfuerzo: 16h | Tipo: implementación directa (usando fixtures existentes)

### Fase 3 — Medios (Sprint de deuda técnica)

**Story 3A — i18n: internacionalización del módulo de catálogo**
Mover los 60+ strings hardcodeados a `messages/es.json`. Organizar bajo namespaces `catalog.facets.*`, `catalog.filters.*`, `catalog.product.fields.*`, `catalog.materials.*`, `catalog.validation.*`. Bloqueante para soporte de inglés.
Esfuerzo: 8–12h | Tipo: implementación directa

**Story 3B — Performance: N+1 en ficha-enrich y sub-recursos de detalle**
`FichaEnrichmentApplier`: pasar el mapa de productos pre-fetched al applier para evitar N SELECTs individuales. Sub-recursos (`certificates`, `flow-data`, `materials`): migrar queryKeys a jerarquía `productKeys.detail(sku)`.
Esfuerzo: 5h | Tipo: implementación directa

**Story 3C — Código: refactor `product-wizard.tsx` en módulos**
Split del componente de 977 líneas en: wizard shell + 5 stages + lib de transformaciones (`buildPayload`, `productToFormValues`) + schema. Añadir tests unitarios para las funciones de transformación.
Esfuerzo: 6–8h | Tipo: refactor con riesgo medio (usar feature flag si es posible)

**Story 3D — Código: extracción de lógica de handler en `products.py`**
Extraer `export_products_csv` a `CsvExportService`. Mover dispatch de Celery en `confirm_asset_upload` a `AssetService.confirm_upload()`. Extraer `_parse_iso` duplicado a `app/api/utils.py`.
Esfuerzo: 6–8h | Tipo: refactor

**Story 3E — Tests: cobertura del backlog restante (72 endpoints)**
Escribir tests para los 72 endpoints sin cobertura que no están en Story 2D: taxonomía admin, series admin, divisiones, materiales, compatibility, display-pair, tech-tables, UoM conversions, datasheets, bore dimensions.
Esfuerzo: 24h | Tipo: implementación directa

**Story 3F — Código: consolidar design system y quick wins de código**
Migrar tabs mercados, recambios, traducciones, unidades a MT primitives. Crear `<SkuTabShell>` y `useSkuDialog()`. Añadir `id` y `base_uom` al tipo `Product`. Eliminar ruta `/products` legacy. Registrar queryKeys faltantes en factory.
Esfuerzo: 8–10h | Tipo: refactor

### Spikes técnicos requeridos

1. **Spike A — Modelo de permisos ampliado** (antes de Story 2C): Definir el mapa completo de permisos necesarios (`products:releases`, `products:classify`, `finance:read`, `admin:pricing`). Evaluar impacto en tabla `public.roles` y en el frontend `RbacGuard`. Duración estimada: 2–3h.

2. **Spike B — Transacción en `_build_product_detail`** (antes de Story 2A): Evaluar si mover las queries al ORM con `joinedload` puede hacerse sin refactorizar el repositorio completo, o si requiere un `ProductDetailRepository` nuevo. Duración estimada: 2h.

3. **Spike C — Límites de tamaño en Supabase Storage** (antes de Story 2C): Verificar si los bucket policies de Supabase Storage ya tienen límites configurados para `product-images`. Si los hay, la validación server-side en confirm puede ser una segunda línea de defensa en lugar de la primera. Duración estimada: 1h.

---

## Estadísticas

- **Total hallazgos:** 40
- **Críticos:** 2 | **Altos:** 9 | **Medios:** 20 | **Bajos:** 9
- **Quick wins (< 2h):** 20
- **Endpoints sin test:** 90/146 (62%)
- **Hooks con staleTime incorrecto:** 4/16 (25%)
- **Strings hardcodeados sin i18n:** 60+
- **Problemas de accesibilidad (tablas sin scope):** 5 tablas
- **Deuda técnica total estimada:**
  - Backend: ~50–70h (tests) + ~12–16h (refactors)
  - Frontend: ~20–25h (refactors) + ~8–12h (i18n)
  - Quick wins acumulados: ~14–16h
  - **Total aproximado: ~100–130h** repartidas en 3 fases de sprint
