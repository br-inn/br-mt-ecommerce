# Track F — Calidad de Código
**Fecha:** 2026-05-20
**Alcance:** Módulo products — frontend (catalogo + hooks) + backend (products.py + products_display.py)

---

## F1 — product-wizard.tsx: análisis de complejidad

- **Líneas totales:** 977
- **useState calls:** 2 (`specs`, `specsErrors`)
- **useEffect calls:** 2
- **Funciones / componentes exportados:** 12 (incluye sub-componentes: `Stepper`, `Stage3SeriesPicker`, `Stage3MaterialPicker`, `Stage3DivisionsPicker`, `Field`, `ConfirmationSummary`, `DiffSummary`, `fmtValue`)
- **Tipos `: any`:** 0 instancias
- **`@ts-ignore` / `@ts-expect-error`:** 0
- **`as Type` casts:** 9 (ver sección F3)
- **Dependencias suprimidas en useEffect:** 1 (`// eslint-disable-next-line react-hooks/exhaustive-deps` en el effect de reset de specs-por-familia)

### useEffect — análisis de dependencias

| # | Trigger | Deps declaradas | Evaluación |
|---|---------|----------------|------------|
| 1 | Reset form en modo edit | `[isEdit && props.product?.sku]` | Dep correcta conceptualmente, pero usa expresión condicional en deps array — antipatrón; debería ser `[isEdit ? props.product?.sku : undefined]` |
| 2 | Reset specs cuando cambia family | `[family]` — el efecto compara `prevFamilyRef.current !== family` internamente | Correcto. La supresión del exhaustive-deps eslint es innecesaria aquí porque `setSpecs`/`setSpecsErrors` son estables |

### Lógica de negocio mezclada en render: Sí

Las funciones `buildPayload`, `productToFormValues` y `toNumberOrNull` (transformaciones de datos) viven en el mismo módulo que el componente. Son pure functions bien definidas pero mezclan capa de transformación con capa de presentación. Esto complica testear las transformaciones de forma aislada.

El componente `ProductWizard` gestiona 5 stages de wizard, validación Zod, lógica de diff (`DiffSummary`), reset de formulario en modo edición, y 3 `useQuery` directos para divisiones, materiales y series — todo en un único componente de 977 líneas.

### Propuesta de split

```
product-wizard/
  index.tsx                  ← re-export, 10 líneas
  product-wizard.tsx         ← shell: props, form init, step machine (~150 líneas)
  product-wizard-steps/
    stage-1-identity.tsx     ← SKU, name_en, family, active
    stage-2-specs.tsx        ← DynamicSpecsForm + specs state
    stage-3-classification.tsx ← series, material, divisions (pickers)
    stage-4-physical.tsx     ← dn, pn, weight, dimensions, EAN
    stage-5-confirm.tsx      ← ConfirmationSummary + DiffSummary
  lib/
    build-payload.ts         ← buildPayload, productToFormValues, toNumberOrNull
    wizard-schema.ts         ← createSchema, eanSchema, familySchema, WizardForm type
```

Impacto: `ProductWizard` bajaría a ~150–200 líneas. Los steps serían testables en aislamiento. Las funciones de transformación tendrían su propio test unit.

---

## F2 — Consistencia de hooks

**Todos los hooks usan React Query v5** (`useQuery` / `useInfiniteQuery` / `useMutation`). No hay hooks que usen `useEffect + useState` para fetching. Patrón general consistente y correcto.

### Desvíos encontrados

| Hook | Problema |
|------|---------|
| `use-product-model.ts` | Define 3 queryKeys inline (`["products", sku, "certificates"]`, `["products", sku, "flow-data"]`, `["products", sku, "materials"]`) en lugar de usar `productKeys` factory. Si en el futuro se invalidan estas queries desde mutations, el string manual puede no coincidir. |
| `use-facets.ts` | Define `queryKey: ["products", "facets", filters]` inline. Inconsistente con el resto que usa `productKeys.*`. |
| `use-product-mutations.ts` | Los `id`-based cache seeds usan el cast `(created as Product & { id?: string })` porque `Product` no expone `id` directamente — señal de que el tipo `Product` en el API endpoint debería incluir `id` explícitamente. |
| `use-translation-workflow.ts` | Usa `productKeys.*` correctamente, pero mezcla lógica de workflow de traducción (approve, request-review, mark-stale) con productKeys — podría tener su propio namespace de keys (`translationKeys`). |

### staleTime — consistencia con CLAUDE.md

| Hook | staleTime configurado | Directriz CLAUDE.md | Estado |
|------|----------------------|---------------------|--------|
| `use-product.ts` | 60 000 ms | 60 000 ms (detalle) | Correcto |
| `use-products.ts` | 30 000 ms | 30 000 ms (listados) | Correcto |
| `use-product-model.ts` | 120 000 ms | — (no especificado) | Aceptable |
| `use-facets.ts` | 30 000 ms | 30 000 ms | Correcto |
| `use-product-images.ts` | 30 000 ms | — | Aceptable |
| `use-bore-dimensions.ts` | 60 000 ms | — | Aceptable |

---

## F3 — TypeScript strictness

### Resumen

| Tipo de problema | Instancias |
|-----------------|-----------|
| `: any` explícito | 0 |
| `as any` / `as unknown` | 2 |
| `@ts-ignore` / `@ts-expect-error` | 0 |
| `as Type` casts (narrowing necesario) | ~35 en todos los archivos |
| `!` non-null assertion | 2 |

### Instancias críticas por archivo

| Archivo | Línea aprox. | Código | Tipo de problema |
|---------|-------------|--------|-----------------|
| `product-wizard.tsx` | 308 | `form.reset({ ...initialValues } as WizardForm)` | Cast forzado — `initialValues` parcial no coincide con tipo completo |
| `product-wizard.tsx` | 311 | `[isEdit && (props as EditProps).product?.sku]` | Expresión booleana en deps array + prop cast |
| `product-wizard.tsx` | 370 | `await updateMut.mutateAsync(rest as ProductUpdatePayload)` | Cast en submit — sugiere que `buildPayload` debería tipar su retorno explícitamente |
| `page.tsx` (catalogo) | 116 | `(r as unknown as Record<string, unknown>)[h]` | `as unknown as` — doble cast para CSV export; merece tipo utilitario |
| `top-filter-bar.tsx` | 353, 371 | `facets!.dn`, `facets!.pn` | Non-null assertions en datos opcionales de API |
| `top-filter-bar.tsx` | 453 | `(config?.filterKey ?? slug as keyof FacetsFilters) as keyof FacetsFilters` | Cast doble por falta de tipos de discriminación en `SYSTEM_FILTER_CONFIG` |
| `top-filter-bar.tsx` | 462 | `(facets as unknown as Record<string, ...>)?.[...]` | `as unknown as` para acceso dinámico a buckets de facets |
| `unidades/_client.tsx` | 198 | `(product as { base_uom?: string \| null } \| undefined)?.base_uom` | Product type no incluye `base_uom` — falta campo en schema |
| `use-product-mutations.ts` | 26, 62, 114 | `(created as Product & { id?: string })` (×3) | `Product` no expone `id` — campo faltante en tipo |
| `_client.tsx` (costos) | 199–200 | `err.detail as Record<string, unknown>` | Manejo de error sin tipo discriminado |
| `mercados/_client.tsx` | — | `useMutation` sin tipo genérico explícito en `onError: (err: unknown)` | Minor — pero inconsistente con otros hooks |

**Total instancias relevantes:** ~12 que representan deuda real (non-null + doble cast + campos faltantes en tipos).

---

## F4 — Duplicación en tabs [sku]

### Líneas por tab

| Tab | Líneas |
|-----|--------|
| audit | 106 |
| costos | 398 |
| datasheets | 318 |
| edit | 26 |
| enriquecer | 454 |
| imagenes | 36 |
| mercados | 472 |
| recambios | 198 |
| traducciones | 341 |
| unidades | 327 |
| **Total** | **2 676** |

### Patrones duplicados detectados

**1. Skeleton de carga (8/10 tabs):** Cada tab implementa su propio bloque `isLoading → <Skeleton>` + `isError → <error UI>` con variaciones menores. Plantilla copia-pega de ~8–15 líneas.

**2. Dialog de acción multi-step (mercados + unidades):** Ambas tabs implementan un `Dialog` con estado local (`open`, `form`, `error`), mutation inline con `onSuccess/onError`, y `handleOpenChange` con reset de estado. El patrón es idéntico salvo campos del formulario. ~80 líneas duplicadas netas.

**3. queryKey inline no registrados en factory (mercados, recambios, unidades):** Tres tabs definen sus propios string-arrays de queryKey (ver F2) que aparecen 3–4 veces cada uno dentro del mismo archivo (query + 2 invalidaciones). Debería usarse la factory `productKeys`.

**4. Design system mixto:** 4 tabs usan primitivos MT (`SectionCard`, `MtButton`, `MtError`) mientras que 4 tabs usan componentes shadcn (`Card`, `Button`, `Skeleton` from `@/components/ui`). Esto produce experiencia visual inconsistente y duplica imports.

| Grupo | Tabs |
|-------|------|
| MT primitives | audit, costos, datasheets, enriquecer |
| shadcn/ui directo | mercados, recambios, traducciones, unidades |
| Mixto / ninguno | edit, imagenes |

**Estimación de duplicación:** ~300–350 líneas de código estructuralmente redundante en 2 676 líneas totales (~12–13%).

### Refactor sugerido

1. **`<SkuTabShell>`** — wrapper genérico que acepta `isLoading`, `isError`, `onRetry`, `title` y renderiza skeleton/error/children. Eliminaría ~80 líneas de boilerplate repetido.

2. **`useSkuDialog<TForm>()`** — hook que encapsula `open`, `form`, `error`, `handleOpenChange` con reset. Aplicable a mercados y unidades.

3. **Migrar mercados, recambios, unidades a MT primitives** — consolidar design system. Los 4 tabs con shadcn directo están en sprints más viejos.

4. **Añadir `productKeys.releases()`, `productKeys.compatibility()`, `productKeys.uomConversions()`** en `query-keys.ts`.

---

## F5 — Server vs Client components

### Hallazgos

**Patrón correcto implementado:** El patrón server-wrapper → client island está bien aplicado. Cada tab tiene:
- `page.tsx` — Server Component: resuelve `params`, opcionalmente llama `getTranslations()`, y pasa `sku` al cliente.
- `_client.tsx` — Client Component: toda la interactividad y data fetching.

**`catalogo/page.tsx` (1 209 líneas):** Es un Client Component puro (`"use client"`). No hace trabajo de servidor. Es una mega-página que mezcla tabla, grid, filtros, modales, atajos de teclado, exportación CSV, vistas guardadas y quick-edit. No viola las reglas de server/client pero sí es un god component candidato a refactor (ver F1 equivalente para este archivo).

**`[sku]/layout.tsx`:** Server Component correcto — usa `getTranslations()` de next-intl/server, resuelve `params` y renderiza breadcrumb/tabs de navegación.

**Sin `cookies()`/`headers()` en client components.** No se encontraron violaciones de server-only APIs en contextos `"use client"`.

**`traducciones/page.tsx`:** Importa de `_mt-client.tsx` en lugar del convencional `_client.tsx`. Inconsistencia de naming que puede confundir.

**Server pages que no hacen trabajo real de servidor:**
- `enriquecer/page.tsx` (11 líneas): solo `await params` + render cliente. No hay beneficio de ser Server Component salvo la resolución de params.
- `mercados/page.tsx` (11 líneas): ídem.
- `unidades/page.tsx` (11 líneas): ídem.

Estas tres pages son thin wrappers válidos (el patrón es correcto en Next.js 15+), pero si no se necesita SSR de metadata, se podrían simplificar con `use client` + `useParams()`.

---

## F6 — Calidad de rutas backend

### `products.py` — 2 351 líneas

**Es el archivo más grande del proyecto backend.** Concentra ~70 endpoints que abarcan: productos, imágenes, assets, traducciones, materiales, conexiones, releases, UoM conversions, bore dimensions, datasheets, compatibility, facets, CSV export, y specs.

### Funciones que deberían delegarse a un servicio

| Función | Líneas | Problema |
|---------|--------|---------|
| `_build_product_detail` | 92 | Private helper con 3 queries directas a sesión (`Series`, `Material`, `display_pair_sku`). Debería ser método de `ProductService`. |
| `list_products` | 168 | Contiene 2 `session.execute()` directas para foto primaria + division_codes tras obtener el listado del servicio. Lógica de enriquecimiento mezclada en el handler. |
| `export_products_csv` | 121 | Toda la lógica de serialización CSV y la query paginada viven en el handler. Debería delegarse a un `CsvExportService`. |
| `confirm_asset_upload` | 68 | Despacha Celery tasks (`generate_thumbnails`) e indexación CLIP directamente desde el handler. Debería estar en `AssetService.confirm_upload()`. |

### `_parse_iso` duplicado (bug latente)

La función `_parse_iso` está definida **dos veces** en el mismo módulo: L360 (dentro de `export_products_csv` como closure local) y L493 (dentro de `list_products` como closure local). Si la lógica de parsing ISO cambia en una, la otra queda desincronizada. Debería extraerse al nivel del módulo o a `app/api/utils.py`.

### Dead code / comentarios como documentación

Los comentarios detectados en L461–463 y L537–539 son comentarios explicativos válidos (no código comentado activo). No hay dead code real.

### `products_display.py` — 124 líneas

Bien estructurado. 3 endpoints, cada uno de ~15–20 líneas, todos delegan a `EffectiveDisplayService` o `DisplayPairService`. Patrón correcto: handler = validate + delegate + map error.

### Inconsistencia: `get_facets` usa sesión directa

`get_facets` recibe `session` como inyectado directamente (no a través de `get_product_service`) y llama `compute_facets(session, filters)`. Es correcto funcionalmente pero inconsistente con el resto del módulo donde el servicio encapsula el acceso a sesión.

### `# type: ignore[assignment]` en get_facets

```python
session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
```
Línea L690 — antipatrón. El `= None` default es para satisfacer al type checker porque FastAPI inyecta el valor, pero el `# type: ignore` indica que el tipo no está correctamente modelado. El patrón correcto es omitir el default y usar `Annotated[..., Depends(...)]` sin default value.

---

## Estimación de deuda técnica

### Refactors mayores (> 4h cada uno)

- **Split `product-wizard.tsx`** en 6–8 archivos: wizard shell + 5 stages + lib de transformaciones + schema. Estimado: **6–8h** (incluye tests unitarios para `buildPayload` y `productToFormValues`).
- **Migrar `catalogo/page.tsx` (1 209 líneas)** a componentes: separar la vista tabla/grid de la gestión de filtros/modales. Estimado: **8–10h** (riesgo alto de regresión de comportamiento en atajos de teclado y saved views).
- **Extraer lógica de handler a servicios en `products.py`**: `_build_product_detail` → `ProductService`, `export_products_csv` → `CsvExportService`, asset dispatch → `AssetService`. Estimado: **6–8h** (incluye tests de integración).

### Refactors medianos (2–4h)

- **Unificar design system en tabs [sku]**: migrar mercados, recambios, traducciones, unidades a MT primitives. Estimado: **3–4h**.
- **Crear `<SkuTabShell>` + `useSkuDialog()`**: eliminar boilerplate de loading/error/dialog en tabs. Estimado: **2–3h**.
- **Registrar queryKeys faltantes en `query-keys.ts`**: `releases`, `compatibility`, `uomConversions` y mover `use-product-model.ts` y `use-facets.ts` a la factory. Estimado: **1–2h**.
- **Extraer `_parse_iso` duplicado** a módulo compartido + añadir test. Estimado: **1h**.
- **Añadir `id` explícito al tipo `Product`** y `base_uom` al tipo Product para eliminar los 5+ casts en hooks y tabs. Estimado: **2h** (requiere coordinar con backend schema).

### Quick wins (< 1h)

- Corregir el antipatrón `= None + # type: ignore` en `get_facets` (L690 products.py).
- Normalizar naming de `_mt-client.tsx` → `_client.tsx` en traducciones (+ actualizar import en page.tsx).
- Añadir `"use client"` guard explícito a `use-patch-data-quality.ts` (el único hook sin él).
- Cambiar `[isEdit && props.product?.sku]` por `[isEdit ? props.product?.sku : undefined]` en useEffect deps.
- Eliminar supresión innecesaria de `react-hooks/exhaustive-deps` en el segundo useEffect (las setters son estables).

### Deuda total estimada

**~30–38 horas** de trabajo de refactor, con riesgo de regresión concentrado en `catalogo/page.tsx` y en `products.py`.

---

## Top 5 refactors de mayor impacto

1. **Split `product-wizard.tsx`** — el componente más complejo del módulo. Un bug aquí afecta tanto alta como edición de productos. El split permite testear cada stage en aislamiento y reduce el riesgo de regresiones al editar una sola funcionalidad. Impacto: alta mantenibilidad, facilita onboarding.

2. **Extraer lógica de handler a servicios en `products.py`** — en especial `_build_product_detail` (que hace 3 queries directas) y `export_products_csv` (121 líneas de lógica en handler). El objetivo CLAUDE.md de "nunca queries secuenciales donde se puede usar subquery o JOIN" se aplica aquí: las 3 queries en `_build_product_detail` (`Series`, `Material`, `display_pair_sku`) son candidatas a un JOIN o `selectinload` en el servicio.

3. **Migrar tabs viejos al design system MT** (mercados, recambios, traducciones, unidades) — actualmente los 4 tabs más nuevos/activos usan shadcn/ui directo mientras los 4 iniciales usan MT primitives. Esto crea inconsistencia visual directamente visible al usuario y duplica el mantenimiento de estilos.

4. **Resolver los 5+ casts por `id` y `base_uom` faltantes en tipo `Product`** — los casts `(created as Product & { id?: string })` son síntoma de un contrato API/tipo desalineado. Añadir `id` al schema de Product en el frontend elimina los casts y hace el tipo sound.

5. **Corregir `_parse_iso` duplicado y extraer a módulo compartido** — pequeño en esfuerzo pero el doble de riesgo: si la lógica de parsing de fechas ISO cambia en un handler (ej. para soportar nanosegundos o zonas horarias alternativas), la copia en el otro handler queda silenciosamente desincronizada.
