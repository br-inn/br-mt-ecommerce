# Track C — UX / Usabilidad
**Fecha:** 2026-05-20

## C1 — Arquitectura de información y navegación

**Pestañas (Tabs):** El producto tiene 10 tabs organizados en dos niveles:

Tabs primarios (siempre visibles, `product-tabs.tsx` lines 27–54):
1. Specs (ruta base `/catalogo/{sku}`)
2. Mercados
3. Imágenes (con badge de advertencia "⚠" si no hay imagen principal)
4. Traducciones
5. Datasheets

Tabs de desbordamiento (en dropdown `...`, lines 56–82):
6. Unidades
7. Costos
8. Recambios
9. Auditoría
10. Enriquecer

**Orden lógico:** El orden es razonable para un flujo de PM de producto. "Specs" como pantalla de inicio es correcto. Sin embargo, "Enriquecer" (acción operacional frecuente de enriquecimiento con LLM) está enterrado en el overflow junto a "Auditoría" (raramente consultado). Dado el enfoque del sistema en la calidad de datos, Enriquecer merece ser un tab primario.

**Breadcrumb:** Presente en `[sku]/layout.tsx` (lines 22–31) como `<nav aria-label="Miga de pan">`. Enlaza de vuelta a `/catalogo` con el texto del título localizado (`tCatalog("title")`). El componente `ProductBreadcrumb` añade dinámicamente el segmento del tab activo. Funciona correctamente.

**Tab activo:** Indicado visualmente con `border-b-2 border-primary text-foreground`. El overflow muestra el nombre del tab activo si uno del overflow está seleccionado, con `border-primary`. La indicación es clara y estándar.

**Problema semántico:** El `<Link>` actúa como `role="tab"` pero es un enlace de navegación real (URL-driven). Los tabs ARIA requieren `aria-controls` y contenido en la misma página. La implementación URL-driven es válida pero `role="tab"` + `aria-selected` en un `<Link>` sin `tabpanel` asociado es semánticamente incorrecto según ARIA 1.2.

---

## C2 — Wizard de creación

**Número de pasos:** El wizard (`product-wizard.tsx`) tiene 5 pasos internos (índices 0–4). Cuando el schema de specs de la familia es "permissivo" (`_default`), el paso 1 (specs dinámicas) se omite automáticamente, mostrando 4 pasos visibles.

Pasos:
- **Paso 0** — Identificación: SKU, Nombre (EN), Familia, Activo
- **Paso 1** — Specs dinámicas: campos EAV basados en el schema JSON de la familia (omitido si permissivo)
- **Paso 2** — Especificaciones técnicas: DN, PN, material, tipo, conexión, peso, dimensiones, taxonomía Stage 3 (serie, material curado, divisiones)
- **Paso 3** — Packaging + Intrastat: qty/caja, MOQ, EANs, HS code, país origen, peso neto
- **Paso 4** — Confirmación: `ConfirmationSummary` (creación) o `DiffSummary` (edición)

**Validación:** El formulario usa `mode: "onBlur"` (line 303). Los campos se validan al perder el foco, no al enviar. La validación de servidor se muestra per-campo via `form.setError()` (line 391) y via `setSpecsErrors` para el paso de specs.

**Campos requeridos:** Solo `DynamicSpecsForm` marca visualmente los requeridos con `<span className="text-destructive ml-0.5">*</span>` (dynamic-specs-form.tsx line 229). Los campos de los pasos 0, 2 y 3 definidos como obligatorios en el schema Zod (SKU, name_en, family) NO tienen indicación visual de requerido — solo muestran error tras el blur.

**Errores de servidor:** Mostrados al usuario. Los errores de campos estándar se mapean via `form.setError()` (line 393). Los errores de specs navegan al usuario de vuelta al paso de specs (line 398: `goTo(1)`). Se muestra además un `toast.error` genérico (line 400).

**Navegación hacia atrás:** Sí, el botón "Anterior" está siempre presente cuando `!isFirst` (line 659). El paso de specs es saltado también al retroceder cuando el schema es permissivo (lines 350–355).

**Indicador de progreso:** Sí, el componente `Stepper` muestra círculos numerados por paso con estados: completado (relleno primario + checkmark), actual (fondo primario/10), pendiente (muted). El stepper NO es clickeable (no permite saltar pasos directamente).

---

## C3 — Catálogo (lista)

**Eliminación individual de filtros:** Sí. El componente `ActiveFiltersBar` muestra chips con botón ✕ individual (`onRemove` callback). El botón `aria-label="Quitar {chip.label}"` está correctamente implementado. Aparece "limpiar todo" solo cuando hay 2 o más chips activos.

**Conteo total de resultados:** Sí, mostrado en el header como `{total} SKUs` o `{items.length} cargados` cuando `total` es null. El `ActiveFiltersBar` muestra la reducción `{totalUnfiltered} → {total}`.

**Paginación:** Muestra `mostrando {loaded} de {total}` en el `Paginator`. El paginador usa cursor-based "load more" — NO muestra página actual / total de páginas (por diseño: backend usa cursors, no offsets). Hay selector de tamaño de página (25/50/100/250).

**Estado vacío:** Presente en ambas vistas (tabla y galería) con icono, texto descriptivo, chips de filtros activos removibles individualmente, y botón "Limpiar todos los filtros".

**Vistas guardadas:** Nombradas, eliminables (botón ✕ con `aria-label`), compartibles (botón de enlace con `aria-label`). Hay 7 vistas de sistema (`SYSTEM_VIEWS`) predefinidas hardcodeadas.

**Diferencia visual tabla/galería:** Sí. Toggle con iconos distintos (`List` vs `LayoutGrid`). Tabla = filas densas con columnas (SKU, nombre, DN, PN, estado, calidad, fecha). Galería = cards de 120px con imagen, SKU, nombre, familia y badges. El botón activo se resalta con `background: MT.brand, color: "white"`.

---

## C4 — Visualización de specs

**Agrupación lógica:** Sí. El componente `ProductSpecs` divide las specs en secciones con `SectionDivider`:
- Bloque 1 (Card): DN, PN, bore, estándar dimensional, rango de temperatura, presión máxima — luego "Construcción" (material, tipo, conexión, tamaño, peso, dimensiones) — luego "Referencias" (ERP name, revisión) si existen.
- Bloque 2 (Packaging): qty/caja, EAN unidad, EAN caja, GTIN, MOQ.
- Bloque 3 (Intrastat): HS code, país de origen, peso neto.

Componentes adicionales: `ProductSpecsCardEAV` (atributos EAV agrupados), `ProductMaterials`, `ProductBoreDimensions`, `DimensionTable`, `PressureTemperatureChart`, `ProductFlowData` (Kv/Cv/malla), `ProductCertificates`.

**Unidades de medida:** Sí mostradas. Ejemplos: `DN ${data.dn}` (prefix), `PN ${data.pn}`, `${data.bore_mm} mm`, `${data.pressure_max_bar} bar`, `${data.weight_kg} kg`. En `ProductBoreDimensions`, cada celda usa `<DimCell unit="mm">`. En `ProductFlowData`, las cabeceras incluyen la unidad ("Kv (m³/h)", "Malla (mm)"). En `ProductSpecsCardEAV`, el helper `renderAttributeValue` concatena la unidad del valor o de la definición del atributo.

**Certificados:** El componente `ProductCertificates` muestra `cert_number` (font-mono), `issuer`, fechas formateadas, y `StatusBadge` con el estado. NO hay nombre descriptivo del tipo de certificación (ej. "CE Marking", "WRAS", "NSF") — solo el número de certificado.

**Tooltips / texto de ayuda:** No hay tooltips en los componentes de specs del detalle. En `DynamicSpecsForm`, si la propiedad del schema tiene `description`, se muestra inline junto al label: `<span className="ml-2 text-muted-foreground font-normal">{property.description}</span>`. Mínimo pero funcional.

**Estructura EAV:** `ProductSpecsCardEAV` agrupa atributos por `group_code` usando `humaniseGroupCode()`. Los grupos se renderizan en Cards separados en una grilla 2 columnas. Cada atributo muestra su `label_en`, el valor tipado (número+unidad, texto, bool con checkmarks, enum, rango), y un badge "Required" en destructive si el campo es obligatorio y está vacío. Estructura clara, no una lista plana.

---

## C5 — Accesibilidad

| Componente | Problema | Severidad |
|-----------|---------|-----------|
| `validacion/page.tsx:138-143` | Usa `window.confirm()` y `window.alert()` nativos para confirmación de "limpiar pruebas" y reporte de error. Bloquean el hilo principal, no accesibles con teclado en todos los contextos, bloqueados por algunos navegadores. | **Crítico** |
| `page.tsx (table checkboxes)` | Checkboxes de selección de fila sin `aria-label` — asociados solo por posición en la fila. | Major |
| `page.tsx:916` | Select-all checkbox sin `aria-label`. | Major |
| `page.tsx:613-636` | Botones toggle vista tabla/galería usan `title` en lugar de `aria-label`. `title` no es confiable en móvil y lectores de pantalla. | Major |
| `page.tsx:860-880` | Tabla principal: `<MtTh>` sin atributo `scope="col"`. Lectores de pantalla no pueden asociar headers a celdas. | Major |
| `product-certificates.tsx:44-49` | Tabla de certificados: `<th>` sin atributo `scope`. | Major |
| `product-bore-dimensions.tsx:84-110` | Tabla de dimensiones por norma: `<th>` sin `scope`. | Major |
| `product-materials.tsx:55-69` | Tabla de materiales: `<th>` sin `scope`. | Major |
| `product-flow-data.tsx:30-33` | Tabla de coeficientes de flujo: `<th>` sin `scope`. | Major |
| `product-grid-card.tsx:78-87` | Botón "Editar rápido" con solo icono `<Pencil>` y `title` pero sin `aria-label`. | Major |
| `facet-sidebar.tsx:195-200` | Input de búsqueda en sidebar de facetas: `placeholder="filtrar…"` sin `<label>` ni `aria-label`. | Major |
| `top-filter-bar.tsx:251-260` | Input de búsqueda principal: sin `<label>` asociado (el label visual es el icono `<Search>`). | Major |
| `product-header.tsx:337-364` | Dos botones "Editar" sin suficiente contexto diferenciador para lectores de pantalla. | Minor |
| `saved-views-bar.tsx:44` | Input de nombre para guardar vista sin `<label>` explícito. | Minor |
| `product-specs-eav.tsx:198` | Mensaje de error en inglés `"Family UUID is not assigned to this product yet — EAV view unavailable."` visible al usuario final. | Minor |
| `product-specs-eav.tsx:224-229` | Mensaje en inglés `"No attribute template configured for this family yet."` visible al usuario final. | Minor |
| `product-specs-eav.tsx:196` | Label de debug `"Specs (Stage 2 — EAV)"` expuesto como CardDescription visible al usuario. | Minor |

---

## C6 — Strings hardcodeados (i18n)

> Se detectaron más de 60 strings hardcodeados en el módulo de catálogo. Se listan los más impactantes:

| Archivo | Strings principales | Claves i18n sugeridas |
|---------|--------------------|-----------------------|
| `page.tsx` | `"División"`, `"Todas"`, `"Alta SKU"`, `"Exportar"`, `"Importer"`, todas las bulk actions y el modal de atajos de teclado (~25 strings) | `catalog.division.*`, `catalog.actions.*`, `catalog.shortcuts.*` |
| `facet-sidebar.tsx` | Títulos de secciones: `"división"`, `"serie"`, `"tier"`, `"material (curado)"`, `"family"`, `"DN"`, `"PN"`, `"con foto"`, `"sin foto"`, `"ver {N} más ▾"`, `"colapsar ▴"` (~10 strings) | `catalog.facets.*` |
| `top-filter-bar.tsx` | `"Limpiar ({N})"`, `"Más filtros"`, `"Sub-jerarquía"`, `"Subfamilia"`, `"Tipo"`, `"Dimensiones"`, `"Estado"`, `"(sin opciones)"` (~10 strings) | `catalog.filters.*` |
| `product-header.tsx` | Labels KVP: `"UoM Base"`, `"GTIN"`, `"Marca"`, `"Serie"`, `"Modelo"`, `"Conexión"`, valores de lifecycle_status (`"Active"`, `"Inactive"`, etc.), `"← Catálogo"` (~12 strings) | `catalog.product.fields.*`, `catalog.lifecycle.*` |
| `product-materials.tsx` | Dict `COMPONENT_LABELS`: `"Cuerpo"`, `"Obturador"`, `"Asiento"`, etc. + headers de tabla (~8 strings) | `catalog.materials.*` |
| `product-bore-dimensions.tsx` | Título, subtítulo, headers de tabla con normas (`"Norma / Código"`, `"Sistema"`, `"Cara–Cara"`, etc.) (~9 strings) | `catalog.boreDimensions.*` |
| `product-flow-data.tsx` | Título y headers de tabla (~3 strings) | `catalog.flowData.*` |
| `product-certificates.tsx` | Título y headers de tabla (~6 strings) | `catalog.certificates.*` |
| `product-wizard.tsx` | Paso de taxonomía: `"Taxonomía Stage 3"`, `"Serie"`, `"— sin serie —"`, `"Material curado"`, `"Divisiones (M:N)"` (~5 strings) | `catalog.create.taxonomy.*` |
| `catalog-filters.tsx` | Valores de `data_quality` y `translation_status` mostrados sin traducción: `"complete"`, `"partial"`, `"blocked"`, `"draft"`, `"pending"`, `"approved"` | `catalog.quality.*`, `catalog.translations.status.*` |
| `validacion/page.tsx` | Título, acciones, contador de candidatos, hints de teclado (~10 strings) | `catalog.validation.*` |

**Impacto:** El archivo `messages/es.json` ya tiene infraestructura i18n robusta para otras áreas. El módulo de catálogo tiene cobertura parcial — los componentes más nuevos (taxonomía, EAV, materiales, bore dimensions, validación) están sin internacionalizar. Bloqueante para añadir soporte de inglés.

---

## Top 5 problemas priorizados por impacto en usuario

1. **[Crítico] Diálogos nativos bloqueantes en validacion/page.tsx** — El flujo de validación de matches usa `window.confirm()` y `window.alert()` para confirmar borrados y reportar errores. Bloquean el hilo principal, no pueden ser estilizados, son inaccesibles en algunos lectores de pantalla, y son bloqueados por defecto en algunos navegadores. Impacto: todos los usuarios del flujo de validación. Solución: reemplazar con el componente `AlertDialog` de Shadcn/ui ya disponible en el proyecto.

2. **[Mayor] Tablas sin `scope` en headers** — Cinco tablas del módulo (ProductCertificates, ProductBoreDimensions, ProductMaterials, ProductFlowData, tabla principal del catálogo) usan `<th>` sin `scope="col"`. Lectores de pantalla (NVDA, JAWS, VoiceOver) no pueden asociar headers a celdas correctamente. Las tablas de dimensiones y certificados son el núcleo de la ficha técnica.

3. **[Mayor] Campos obligatorios sin indicación visual en pasos 0, 2 y 3 del wizard** — SKU y Nombre (EN) son obligatorios en el schema Zod pero no muestran asterisco ni marca visual de requerido. El usuario solo descubre la obligatoriedad tras hacer blur o intentar avanzar. El paso de dynamic specs sí muestra asteriscos — inconsistencia interna. Aumenta el tiempo de tarea y la tasa de error.

4. **[Mayor] Cobertura de i18n incompleta** — Más de 60 strings hardcodeados en los componentes del módulo de productos. El sistema ya usa `next-intl` y tiene `es.json` completo para otras áreas. Los componentes más nuevos (taxonomía, EAV, materiales, bore dimensions) están sin internacionalizar. Bloqueante para lanzar la UI en inglés o añadir nuevos locales.

5. **[Mayor] Inputs de búsqueda sin label accesible** — El input de búsqueda principal en `TopFilterBar` y los inputs de filtro dentro de las secciones de facetas carecen de `<label>` o `aria-label`. Son los elementos de interacción más usados del catálogo. Usuarios de lector de pantalla solo pueden identificar el propósito leyendo el `placeholder`, lo cual no es una práctica accesible.
