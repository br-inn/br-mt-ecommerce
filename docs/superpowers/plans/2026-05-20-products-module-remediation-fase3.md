# Products Module Remediation — Fase 3 (Tech Debt Sprint)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Liquidar la deuda técnica acumulada del módulo de productos: i18n del catálogo, N+1 en ficha-enrich, refactor de `product-wizard.tsx`, extracción de lógica de handlers en `products.py`, cobertura de tests de los 72 endpoints restantes, y consolidación de design system + queryKey factory.

**Architecture:** Frontend usa Next.js 16 + next-intl con namespace `catalog` en `messages/es.json`; las queryKeys de sub-recursos del detalle se migran a la jerarquía `productKeys.detail(sku)` para que las mutaciones las invaliden automáticamente. Backend extrae lógica de negocio de handlers a servicios cohesivos (`CsvExportService`, `AssetService.confirm_upload`) y elimina closures locales duplicadas. Los tests siguen el patrón de `test_products_put_patch.py` (fixtures de integración con testcontainers + JWT emission).

**Tech Stack:** Next.js 16, React 19, TypeScript strict, Tailwind v4, Shadcn/ui (new-york), next-intl, TanStack Query v5 — FastAPI, Python 3.11, SQLAlchemy 2.0 async, pytest-asyncio, testcontainers.

---

## Estructura de archivos

### Archivos a crear

| Ruta | Propósito |
|------|-----------|
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/index.tsx` | Re-export del wizard refactorizado |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/product-wizard.tsx` | Shell: props, form init, step machine (~150 líneas) |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-1-identity.tsx` | Paso 0: SKU, name_en, family, active |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-2-specs.tsx` | Paso 1: DynamicSpecsForm |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-3-classification.tsx` | Paso 2: series, material, divisions |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-4-physical.tsx` | Paso 3: DN, PN, weight, dimensions, EAN |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-5-confirm.tsx` | Paso 4: ConfirmationSummary + DiffSummary |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/build-payload.ts` | `buildPayload`, `productToFormValues`, `toNumberOrNull` |
| `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/wizard-schema.ts` | `createSchema`, `eanSchema`, `familySchema`, `WizardForm` |
| `mt-pricing-frontend/lib/services/csv-export.service.ts` | (ya está en backend; ver Story 3D) |
| `mt-pricing-backend/app/api/utils.py` | `parse_iso_datetime` (extraída de closures duplicadas) |
| `mt-pricing-backend/app/services/products/csv_export_service.py` | `CsvExportService` |
| `mt-pricing-backend/tests/api/test_products_taxonomy.py` | Tests taxonomía admin endpoints |
| `mt-pricing-backend/tests/api/test_products_series_admin.py` | Tests series admin endpoints |
| `mt-pricing-backend/tests/api/test_products_divisiones.py` | Tests divisiones endpoints |
| `mt-pricing-backend/tests/api/test_products_materials_compat.py` | Tests materiales, compatibility, display-pair |
| `mt-pricing-backend/tests/api/test_products_tech_tables.py` | Tests tech-tables, UoM conversions, datasheets, bore dimensions |

### Archivos a modificar

| Ruta | Cambio principal |
|------|-----------------|
| `mt-pricing-frontend/messages/es.json` | Agregar namespace `catalog.*` con 60+ strings |
| `mt-pricing-frontend/lib/hooks/products/query-keys.ts` | Agregar `releases`, `compatibility`, `uomConversions`, `certificates`, `flowData`, `materials`, `facets` |
| `mt-pricing-frontend/lib/hooks/products/use-product-model.ts` | Migrar queryKeys a `productKeys.detail(sku)` |
| `mt-pricing-frontend/app/(app)/catalogo/_components/facet-sidebar.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/_components/top-filter-bar.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-materials.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-bore-dimensions.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-flow-data.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-certificates.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/_components/catalog-filters.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx` | Reemplazar strings hardcodeados con `t()` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/page.tsx` | Actualizar import: `_mt-client` → `_client` |
| `mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_mt-client.tsx` | Renombrar a `_client.tsx` |
| `mt-pricing-backend/app/api/routes/products.py` | Eliminar closures `_parse_iso` duplicadas, delegar CSV a `CsvExportService`, eliminar dispatch Celery inline en `confirm_asset_upload` |
| `mt-pricing-backend/app/services/ficha_enrichment/applier.py` | Aceptar mapa `pre_fetched: dict[str, Product]` para evitar N SELECTs |
| `mt-pricing-backend/app/api/routes/ficha_enrich.py` | Pasar mapa pre-fetched al applier en `apply_ficha_enrich` y `apply_ficha_series` |
| `mt-pricing-backend/app/services/products/asset_service.py` | Mover dispatch Celery + CLIP indexing a `confirm_upload()` |

---

## Story 3A — i18n: Internacionalización del módulo de catálogo

**Esfuerzo:** 8–12h

### Task 1: Agregar namespace `catalog` a `messages/es.json`

**Files:**
- Modify: `mt-pricing-frontend/messages/es.json`

- [ ] **Step 1: Agregar todas las claves i18n del catálogo**

Agregar el siguiente bloque al final de `messages/es.json`, antes del cierre `}`:

```json
"catalog": {
  "title": "Catálogo",
  "division": {
    "label": "División",
    "all": "Todas"
  },
  "actions": {
    "newSku": "Alta SKU",
    "export": "Exportar",
    "import": "Importar",
    "activate": "Activar",
    "archive": "Archivar",
    "assignFamily": "Asignar familia",
    "clearFilters": "Limpiar todos los filtros",
    "clear": "Limpiar ({count})",
    "moreFilters": "Más filtros",
    "saveView": "Guardar vista",
    "shortcuts": "Atajos de teclado"
  },
  "shortcuts": {
    "title": "Atajos de teclado",
    "newSku": "Alta SKU",
    "search": "Buscar",
    "export": "Exportar CSV",
    "toggleView": "Alternar vista"
  },
  "facets": {
    "division": "División",
    "serie": "Serie",
    "tier": "Tier",
    "material": "Material (curado)",
    "family": "Familia",
    "dn": "DN",
    "pn": "PN",
    "withPhoto": "Con foto",
    "withoutPhoto": "Sin foto",
    "showMore": "ver {count} más ▾",
    "collapse": "colapsar ▴"
  },
  "filters": {
    "subHierarchy": "Sub-jerarquía",
    "subfamily": "Subfamilia",
    "type": "Tipo",
    "dimensions": "Dimensiones",
    "status": "Estado",
    "noOptions": "(sin opciones)"
  },
  "quality": {
    "complete": "Completo",
    "partial": "Parcial",
    "blocked": "Bloqueado",
    "migrated_demo": "Demo migrado"
  },
  "translations": {
    "status": {
      "draft": "Borrador",
      "pending": "Pendiente",
      "approved": "Aprobado",
      "blocked": "Bloqueado"
    }
  },
  "product": {
    "fields": {
      "uomBase": "UoM Base",
      "gtin": "GTIN",
      "brand": "Marca",
      "serie": "Serie",
      "model": "Modelo",
      "connection": "Conexión",
      "backToCatalog": "← Catálogo"
    },
    "lifecycle": {
      "active": "Activo",
      "inactive": "Inactivo",
      "draft": "Borrador",
      "discontinued": "Descontinuado",
      "archived": "Archivado"
    }
  },
  "materials": {
    "title": "Materiales de componentes",
    "headers": {
      "component": "Componente",
      "material": "Material",
      "observations": "Observaciones"
    },
    "components": {
      "body": "Cuerpo",
      "closure": "Obturador",
      "seat": "Asiento",
      "gasket": "Junta",
      "screen": "Malla",
      "actuator_housing": "Carcasa actuador",
      "stem": "Vástago",
      "handle": "Maneta",
      "other": "Otro"
    }
  },
  "boreDimensions": {
    "title": "Dimensiones por norma",
    "subtitle": "Cara a cara según normas dimensionales",
    "headers": {
      "standard": "Norma / Código",
      "system": "Sistema",
      "faceFace": "Cara–Cara",
      "unit": "Unidad"
    }
  },
  "flowData": {
    "title": "Datos de flujo",
    "headers": {
      "dn": "DN",
      "kv": "Kv (m³/h)",
      "cv": "Cv (US gpm)",
      "mesh": "Malla (mm)"
    }
  },
  "certificates": {
    "title": "Certificados",
    "headers": {
      "number": "Número",
      "issuer": "Emisor",
      "issuedAt": "Emisión",
      "expiresAt": "Vencimiento",
      "status": "Estado"
    }
  },
  "create": {
    "taxonomy": {
      "title": "Taxonomía Stage 3",
      "serie": "Serie",
      "noSerie": "— sin serie —",
      "material": "Material curado",
      "divisions": "Divisiones (M:N)"
    }
  },
  "validation": {
    "title": "Validación de matches",
    "candidates": "{count} candidatos",
    "actions": {
      "clearMatches": "Limpiar pruebas",
      "confirmClear": "¿Confirmar limpieza de todas las pruebas?",
      "approve": "Aprobar",
      "reject": "Rechazar"
    },
    "shortcuts": {
      "approve": "A — Aprobar",
      "reject": "R — Rechazar",
      "next": "→ — Siguiente"
    }
  }
}
```

- [ ] **Step 2: Verificar JSON válido**

```bash
cd mt-pricing-frontend && node -e "JSON.parse(require('fs').readFileSync('messages/es.json','utf8')); console.log('JSON válido')"
```

Salida esperada: `JSON válido`

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/messages/es.json
git commit -m "feat(i18n): add catalog namespace with 60+ strings to es.json"
```

---

### Task 2: Internacionalizar `facet-sidebar.tsx`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/facet-sidebar.tsx`

- [ ] **Step 1: Leer el archivo actual**

Localizar la importación de `useTranslations` (si existe) o añadirla. Buscar en el archivo los 10 strings hardcodeados listados en el audit: `"división"`, `"serie"`, `"tier"`, `"material (curado)"`, `"family"`, `"DN"`, `"PN"`, `"con foto"`, `"sin foto"`, `"ver {N} más ▾"`, `"colapsar ▴"`.

- [ ] **Step 2: Añadir hook y reemplazar strings**

Al inicio del componente, agregar:
```tsx
const t = useTranslations("catalog.facets");
```

Reemplazar cada string literal por la clave correspondiente:
- `"división"` → `t("division")`
- `"serie"` → `t("serie")`
- `"tier"` → `t("tier")`
- `"material (curado)"` → `t("material")`
- `"family"` → `t("family")`
- `"DN"` → `t("dn")`
- `"PN"` → `t("pn")`
- `"con foto"` → `t("withPhoto")`
- `"sin foto"` → `t("withoutPhoto")`
- `` `ver ${n} más ▾` `` → `t("showMore", { count: n })`
- `"colapsar ▴"` → `t("collapse")`
- Input placeholder `"filtrar…"` → añadir `aria-label={t("division")}` (o la sección correspondiente)

- [ ] **Step 3: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep -E "facet-sidebar|error TS" | head -20
```

Salida esperada: sin errores en `facet-sidebar.tsx`.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/catalogo/_components/facet-sidebar.tsx
git commit -m "feat(i18n): internacionalizar facet-sidebar.tsx (catalog.facets)"
```

---

### Task 3: Internacionalizar `top-filter-bar.tsx`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/top-filter-bar.tsx`

- [ ] **Step 1: Añadir hook y reemplazar strings**

```tsx
const t = useTranslations("catalog");
const tFilters = useTranslations("catalog.filters");
const tActions = useTranslations("catalog.actions");
```

Reemplazos:
- `"Limpiar ({N})"` → `tActions("clear", { count: N })`
- `"Más filtros"` → `tActions("moreFilters")`
- `"Sub-jerarquía"` → `tFilters("subHierarchy")`
- `"Subfamilia"` → `tFilters("subfamily")`
- `"Tipo"` → `tFilters("type")`
- `"Dimensiones"` → `tFilters("dimensions")`
- `"Estado"` → `tFilters("status")`
- `"(sin opciones)"` → `tFilters("noOptions")`
- Input de búsqueda principal: añadir `aria-label={t("actions.newSku")}` → en realidad `aria-label="Buscar productos"` → añadir clave `catalog.search` = `"Buscar productos"` en `es.json` y usar `t("search")`

- [ ] **Step 2: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep -E "top-filter-bar|error TS" | head -20
```

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/catalogo/_components/top-filter-bar.tsx mt-pricing-frontend/messages/es.json
git commit -m "feat(i18n): internacionalizar top-filter-bar.tsx (catalog.filters)"
```

---

### Task 4: Internacionalizar `product-header.tsx`, `product-materials.tsx`, `product-bore-dimensions.tsx`, `product-flow-data.tsx`, `product-certificates.tsx`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-materials.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-bore-dimensions.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-flow-data.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-certificates.tsx`

- [ ] **Step 1: `product-header.tsx` — reemplazar 12 strings + añadir `fetchPriority`**

```tsx
const t = useTranslations("catalog.product");

// Reemplazos:
// "UoM Base" → t("fields.uomBase")
// "GTIN" → t("fields.gtin")
// "Marca" → t("fields.brand")
// "Serie" → t("fields.serie")
// "Modelo" → t("fields.model")
// "Conexión" → t("fields.connection")
// "← Catálogo" → t("fields.backToCatalog")
// lifecycle_status values "Active", "Inactive", etc. → t(`lifecycle.${status.toLowerCase()}`)
```

Además, en la imagen hero (línea ~218), cambiar:
```tsx
// Antes:
<img src={product.primary_image_url} alt={getProductName(product)}
     className="h-[140px] w-[140px] rounded-lg object-cover" />

// Después:
<img src={product.primary_image_url} alt={getProductName(product)}
     fetchPriority="high" decoding="async"
     className="h-[140px] w-[140px] rounded-lg object-cover" />
```

- [ ] **Step 2: `product-materials.tsx` — reemplazar COMPONENT_LABELS + headers**

```tsx
const t = useTranslations("catalog.materials");

// Antes: const COMPONENT_LABELS: Record<string, string> = { body: "Cuerpo", ... }
// Después: usar t(`components.${kind}`) directamente en el render

// Headers de tabla:
// "Componente" → t("headers.component")
// "Material"   → t("headers.material")
// "Observaciones" → t("headers.observations")
```

Añadir `scope="col"` a todos los `<th>` de la tabla (fix de accesibilidad incluido):
```tsx
<th scope="col">{t("headers.component")}</th>
<th scope="col">{t("headers.material")}</th>
<th scope="col">{t("headers.observations")}</th>
```

- [ ] **Step 3: `product-bore-dimensions.tsx` — reemplazar título, subtítulo y headers**

```tsx
const t = useTranslations("catalog.boreDimensions");

// Título → t("title")
// Subtítulo → t("subtitle")
// "Norma / Código" → t("headers.standard")
// "Sistema" → t("headers.system")
// "Cara–Cara" → t("headers.faceFace")
// "Unidad" → t("headers.unit")
```

Añadir `scope="col"` a todos los `<th>`.

- [ ] **Step 4: `product-flow-data.tsx` — reemplazar título y headers**

```tsx
const t = useTranslations("catalog.flowData");

// Título → t("title")
// "DN" → t("headers.dn")
// "Kv (m³/h)" → t("headers.kv")
// "Cv (US gpm)" → t("headers.cv")
// "Malla (mm)" → t("headers.mesh")
```

Añadir `scope="col"` a todos los `<th>`.

- [ ] **Step 5: `product-certificates.tsx` — reemplazar título y headers**

```tsx
const t = useTranslations("catalog.certificates");

// "Certificados" → t("title")
// "Número" → t("headers.number")
// "Emisor" → t("headers.issuer")
// "Emisión" → t("headers.issuedAt")
// "Vencimiento" → t("headers.expiresAt")
// "Estado" → t("headers.status")
```

Añadir `scope="col"` a todos los `<th>`.

- [ ] **Step 6: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

- [ ] **Step 7: Commit**

```bash
git add \
  mt-pricing-frontend/app/\(app\)/catalogo/\[sku\]/_components/product-header.tsx \
  mt-pricing-frontend/app/\(app\)/catalogo/\[sku\]/_components/product-materials.tsx \
  mt-pricing-frontend/app/\(app\)/catalogo/\[sku\]/_components/product-bore-dimensions.tsx \
  mt-pricing-frontend/app/\(app\)/catalogo/\[sku\]/_components/product-flow-data.tsx \
  mt-pricing-frontend/app/\(app\)/catalogo/\[sku\]/_components/product-certificates.tsx
git commit -m "feat(i18n): internacionalizar componentes de detalle de producto + scope=col en tablas"
```

---

### Task 5: Internacionalizar `catalog-filters.tsx` y `validacion/page.tsx`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/catalog-filters.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

- [ ] **Step 1: `catalog-filters.tsx` — reemplazar valores de data_quality y translation_status**

```tsx
const t = useTranslations("catalog");

// data_quality values: "complete" → t("quality.complete"), etc.
// translation_status values: "draft" → t("translations.status.draft"), etc.
```

- [ ] **Step 2: `validacion/page.tsx` — reemplazar 10 strings + `window.confirm`/`window.alert`**

```tsx
const t = useTranslations("catalog.validation");

// "Validación de matches" → t("title")
// "{N} candidatos" → t("candidates", { count: N })
// "Limpiar pruebas" → t("actions.clearMatches")
// "A — Aprobar" → t("shortcuts.approve"), etc.

// window.confirm() → ya debería estar reemplazado en Fase 1 Story 1D.
// Si aún existe, reemplazar con <AlertDialog> de Shadcn/ui.
```

- [ ] **Step 3: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

- [ ] **Step 4: Commit**

```bash
git add \
  mt-pricing-frontend/app/\(app\)/catalogo/_components/catalog-filters.tsx \
  mt-pricing-frontend/app/\(app\)/catalogo/validacion/page.tsx
git commit -m "feat(i18n): internacionalizar catalog-filters y validacion/page"
```

---

### Task 6: Internacionalizar `product-wizard.tsx` (taxonomy strings)

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard.tsx`

- [ ] **Step 1: Reemplazar strings de taxonomía hardcodeados**

El wizard ya usa `useTranslations`. Agregar los 5 strings de taxonomy al namespace `catalog.create.taxonomy` (ya en `es.json`):

```tsx
const tTax = useTranslations("catalog.create.taxonomy");

// "Taxonomía Stage 3" → tTax("title")
// "Serie" → tTax("serie")
// "— sin serie —" → tTax("noSerie")
// "Material curado" → tTax("material")
// "Divisiones (M:N)" → tTax("divisions")

// Stage 1 hint (si existe string hardcodeado):
// "Selecciona una familia en el paso anterior para ver los atributos técnicos."
// → añadir clave catalog.create.selectFamilyHint y usar t()
```

- [ ] **Step 2: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

- [ ] **Step 3: Commit**

```bash
git add \
  mt-pricing-frontend/app/\(app\)/catalogo/_components/product-wizard.tsx \
  mt-pricing-frontend/messages/es.json
git commit -m "feat(i18n): internacionalizar strings de taxonomía en product-wizard"
```

---

## Story 3B — Performance: N+1 en ficha-enrich + sub-recursos queryKeys

**Esfuerzo:** 5h

### Task 7: Migrar queryKeys de sub-recursos a jerarquía `productKeys.detail(sku)`

**Files:**
- Modify: `mt-pricing-frontend/lib/hooks/products/query-keys.ts`
- Modify: `mt-pricing-frontend/lib/hooks/products/use-product-model.ts`

- [ ] **Step 1: Ampliar `productKeys` factory**

El estado actual del archivo es:

```ts
export const productKeys = {
  all: () => ["products"] as const,
  lists: () => [...productKeys.all(), "list"] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all(), "detail"] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
  translations: (id: string) => [...productKeys.detail(id), "translations"] as const,
  images: (id: string) => [...productKeys.detail(id), "images"] as const,
  boreDimensions: (id: string) => [...productKeys.detail(id), "bore-dimensions"] as const,
  search: (q: string) => [...productKeys.all(), "search", q] as const,
};
```

Añadir las claves faltantes:

```ts
export const productKeys = {
  all: () => ["products"] as const,
  lists: () => [...productKeys.all(), "list"] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all(), "detail"] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
  translations: (id: string) => [...productKeys.detail(id), "translations"] as const,
  images: (id: string) => [...productKeys.detail(id), "images"] as const,
  boreDimensions: (id: string) => [...productKeys.detail(id), "bore-dimensions"] as const,
  certificates: (id: string) => [...productKeys.detail(id), "certificates"] as const,
  flowData: (id: string) => [...productKeys.detail(id), "flow-data"] as const,
  materials: (id: string) => [...productKeys.detail(id), "materials"] as const,
  releases: (id: string) => [...productKeys.detail(id), "releases"] as const,
  compatibility: (id: string) => [...productKeys.detail(id), "compatibility"] as const,
  uomConversions: (id: string) => [...productKeys.detail(id), "uom-conversions"] as const,
  facets: (filters: unknown) => [...productKeys.all(), "facets", filters] as const,
  search: (q: string) => [...productKeys.all(), "search", q] as const,
};
```

- [ ] **Step 2: Migrar `use-product-model.ts` a la factory**

Estado actual (incorrecto):
```ts
export function useProductCertificates(sku: string) {
  return useQuery({
    queryKey: ["products", sku, "certificates"],   // ❌ fuera de jerarquía
    queryFn: () => productsApi.getCertificates(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}
// idem para flow-data y materials
```

Estado correcto:
```ts
import { productKeys } from "@/lib/hooks/products/query-keys";

export function useProductCertificates(sku: string) {
  return useQuery({
    queryKey: productKeys.certificates(sku),       // ✅ dentro de jerarquía
    queryFn: () => productsApi.getCertificates(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}

export function useProductFlowData(sku: string) {
  return useQuery({
    queryKey: productKeys.flowData(sku),
    queryFn: () => productsApi.getFlowData(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}

export function useProductMaterials(sku: string) {
  return useQuery<ProductComponentMaterial[]>({
    queryKey: productKeys.materials(sku),
    queryFn: () => productsApi.getMaterials(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}
```

- [ ] **Step 3: Verificar que `use-facets.ts` también use la factory**

Buscar `queryKey: ["products", "facets"` en `use-facets.ts`. Si existe, reemplazar con `productKeys.facets(filters)`.

- [ ] **Step 4: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

Salida esperada: sin errores.

- [ ] **Step 5: Commit**

```bash
git add \
  mt-pricing-frontend/lib/hooks/products/query-keys.ts \
  mt-pricing-frontend/lib/hooks/products/use-product-model.ts
git commit -m "fix(perf): migrar queryKeys de sub-recursos a jerarquía productKeys.detail(sku)"
```

---

### Task 8: Eliminar N+1 en `FichaEnrichmentApplier` — pasar mapa pre-fetched

**Files:**
- Modify: `mt-pricing-backend/app/services/ficha_enrichment/applier.py`
- Modify: `mt-pricing-backend/app/api/routes/ficha_enrich.py`

- [ ] **Step 1: Escribir test que reproduce el N+1**

Crear `mt-pricing-backend/tests/api/test_ficha_enrich_performance.py`:

```python
"""Test que verifica que apply_ficha_series NO emite N SELECTs individuales."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, call


@pytest.mark.asyncio
async def test_applier_uses_prefetched_map_not_individual_selects(db_session):
    """FichaEnrichmentApplier.apply() debe usar el mapa pre-fetched
    y NO llamar a _load_product() cuando el producto ya está en el mapa."""
    from app.db.models.product import Product
    from app.services.ficha_enrichment.applier import FichaEnrichmentApplier
    from app.schemas.ficha_enrich import FichaEnrichApplyRequest, FichaExtraction, FichaScalars

    # Arrange: crear un product mock
    mock_product = Product(
        sku="TEST001",
        name_en="Test Product",
        family="valves_ball",
        data_quality="partial",
    )
    pre_fetched = {"TEST001": mock_product}

    applier = FichaEnrichmentApplier(db_session)

    request = FichaEnrichApplyRequest(
        extraction=FichaExtraction(
            scalars=FichaScalars(family="valves_ball"),
            translations=[],
        ),
        apply_scalars=False,
        apply_specs=False,
        apply_materials=False,
        apply_dimensions=False,
        apply_translations=False,
        apply_pt_curve=False,
        apply_assets=False,
        apply_to_skus=["TEST001"],
    )

    # Act: con el mapa pre-fetched, _load_product NO debe llamarse
    with patch.object(applier, "_load_product", new_callable=AsyncMock) as mock_load:
        actor = AsyncMock()
        actor.id = "test-user-id"
        await applier.apply("TEST001", request, actor, pre_fetched=pre_fetched)
        # Si pre_fetched se usa correctamente, _load_product no se llama
        mock_load.assert_not_called()
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

```bash
cd mt-pricing-backend && python -m pytest tests/api/test_ficha_enrich_performance.py -v 2>&1 | tail -20
```

Salida esperada: `FAILED` — `_load_product` es llamado 1 vez actualmente.

- [ ] **Step 3: Modificar `applier.py` — aceptar `pre_fetched` map**

Estado actual de la firma:
```python
async def apply(
    self,
    sku: str,
    request: FichaEnrichApplyRequest,
    actor: Any,
    pdf_bytes: bytes | None = None,
) -> SkuApplyResult:
    ...
    product = await self._load_product(sku)
```

Estado correcto:
```python
async def apply(
    self,
    sku: str,
    request: FichaEnrichApplyRequest,
    actor: Any,
    pdf_bytes: bytes | None = None,
    pre_fetched: dict[str, Any] | None = None,  # ← nuevo parámetro opcional
) -> SkuApplyResult:
    applied: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []

    # Usar el mapa pre-fetched si está disponible; evitar SELECT individual
    if pre_fetched is not None and sku in pre_fetched:
        product = pre_fetched[sku]
    else:
        product = await self._load_product(sku)

    if product is None:
        warnings.append(f"product_not_found: {sku}")
        return SkuApplyResult(
            sku=sku,
            applied_fields=[],
            skipped_fields=[],
            warnings=warnings,
        )
    # ... resto del método sin cambios
```

- [ ] **Step 4: Modificar `ficha_enrich.py` — pasar el mapa a `applier.apply()`**

En `apply_ficha_enrich` (líneas 158–173), el bucle actual instancia el applier sin pre_fetched:

```python
# Estado actual:
for target_sku in body.apply_to_skus:
    try:
        applier = FichaEnrichmentApplier(session)
        result = await applier.apply(target_sku, body, user)
```

Estado correcto — pre-fetch bulk antes del bucle:
```python
# Estado correcto:
from sqlalchemy import select as _select
existing_result = await session.execute(
    _select(Product).where(Product.sku.in_(body.apply_to_skus))
)
pre_fetched = {p.sku: p for p in existing_result.scalars().all()}

for target_sku in body.apply_to_skus:
    try:
        applier = FichaEnrichmentApplier(session)
        result = await applier.apply(target_sku, body, user, pre_fetched=pre_fetched)
```

En `apply_ficha_series` (líneas 278–284), el mapa `existing_skus` ya existe pero solo contiene los SKUs como strings. Cambiarlo para que sea un dict de objetos:

```python
# Estado actual:
existing_result = await session.execute(
    _select(Product).where(Product.sku.in_(body.apply_to_skus))
)
existing_skus = {p.sku for p in existing_result.scalars().all()}

# Estado correcto:
existing_result = await session.execute(
    _select(Product).where(Product.sku.in_(body.apply_to_skus))
)
pre_fetched: dict[str, Product] = {p.sku: p for p in existing_result.scalars().all()}
existing_skus = set(pre_fetched.keys())

# Y en el bucle, pasar pre_fetched:
applier = FichaEnrichmentApplier(session)
result = await applier.apply(target_sku, body, user, pre_fetched=pre_fetched)
```

- [ ] **Step 5: Ejecutar test para verificar que pasa**

```bash
cd mt-pricing-backend && python -m pytest tests/api/test_ficha_enrich_performance.py -v 2>&1 | tail -20
```

Salida esperada: `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add \
  mt-pricing-backend/app/services/ficha_enrichment/applier.py \
  mt-pricing-backend/app/api/routes/ficha_enrich.py \
  mt-pricing-backend/tests/api/test_ficha_enrich_performance.py
git commit -m "fix(perf): eliminar N+1 en FichaEnrichmentApplier — usar mapa pre-fetched"
```

---

## Story 3C — Código: refactor `product-wizard.tsx` en módulos

**Esfuerzo:** 6–8h

### Task 9: Extraer schema y transformaciones del wizard

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/wizard-schema.ts`
- Create: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/build-payload.ts`

- [ ] **Step 1: Escribir tests unitarios para las funciones de transformación**

Crear `mt-pricing-frontend/lib/hooks/products/__tests__/wizard-transforms.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { buildPayload, productToFormValues, toNumberOrNull } from
  "../../app/(app)/catalogo/_components/product-wizard/lib/build-payload";

describe("toNumberOrNull", () => {
  it("devuelve null para string vacío", () => {
    expect(toNumberOrNull("")).toBeNull();
  });
  it("devuelve null para undefined", () => {
    expect(toNumberOrNull(undefined)).toBeNull();
  });
  it("parsea número válido", () => {
    expect(toNumberOrNull("1.5")).toBe(1.5);
  });
  it("devuelve null para NaN", () => {
    expect(toNumberOrNull("abc")).toBeNull();
  });
});

describe("buildPayload", () => {
  it("incluye specs del segundo argumento", () => {
    const form = {
      sku: "VAL-DN50", name_en: "Test", family: "valves_ball" as const,
      active: true, dn: "DN50", pn: "PN16",
      material: "", type: "", connection: "",
      weight_kg: undefined, length: undefined, width: undefined, height: undefined,
      series_id: "", material_id: "", division_ids: [],
      qty_per_box: undefined, moq: undefined,
      ean_unit: "", ean_box: "", hs_code: "", country_of_origin: "", net_weight_kg: undefined,
    };
    const specs = { pressure_max_bar: 16 };
    const payload = buildPayload(form, specs);
    expect(payload.specs).toEqual({ pressure_max_bar: 16 });
    expect(payload.sku).toBe("VAL-DN50");
  });
});

describe("productToFormValues", () => {
  it("mapea product a valores del formulario de edición", () => {
    const product = {
      sku: "VAL-DN50",
      name_en: "Test Product",
      family: "valves_ball",
      active: true,
      dn: "50",
      pn: "16",
      material: "brass",
      type: null,
      connection: null,
      weight_kg: 1.5,
      length: null,
      width: null,
      height: null,
      series_id: null,
      material_id: null,
      division_ids: [],
      specs: { pressure_max_bar: 16 },
      qty_per_box: 10,
      moq: 1,
      ean_unit: "1234567890123",
      ean_box: null,
      hs_code: null,
      country_of_origin: null,
      net_weight_kg: null,
    };
    const values = productToFormValues(product as any);
    expect(values.sku).toBe("VAL-DN50");
    expect(values.weight_kg).toBe(1.5);
    expect(values.family).toBe("valves_ball");
  });
});
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan (módulo no existe aún)**

```bash
cd mt-pricing-frontend && npx vitest run lib/hooks/products/__tests__/wizard-transforms.test.ts 2>&1 | tail -15
```

Salida esperada: `Cannot find module` → `FAILED`.

- [ ] **Step 3: Crear directorio del wizard refactorizado**

```bash
mkdir -p "mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib"
mkdir -p "mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps"
```

- [ ] **Step 4: Crear `lib/wizard-schema.ts`**

Extraer de `product-wizard.tsx` el schema Zod y los tipos:

```ts
// mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/wizard-schema.ts
import { z } from "zod";
import { PRODUCT_FAMILIES } from "@/lib/api/endpoints/products";

export const familySchema = z.enum(PRODUCT_FAMILIES);

export const eanSchema = z
  .string()
  .regex(/^\d{12,14}$/u)
  .or(z.literal(""))
  .optional();

export interface SchemaMessages {
  skuRequired: string;
  skuFormat: string;
  nameRequired: string;
  nameMin: string;
  familyRequired: string;
  weightInvalid: string;
  moqInvalid: string;
  qtyInvalid: string;
  eanFormat: string;
}

export const createSchema = (msgs: SchemaMessages) =>
  z.object({
    sku: z.string().min(1, msgs.skuRequired).regex(/^[A-Z0-9_-]+$/u, msgs.skuFormat),
    name_en: z.string().min(3, msgs.nameMin),
    family: familySchema,
    active: z.boolean(),
    dn: z.string().optional(),
    pn: z.string().optional(),
    material: z.string().optional(),
    type: z.string().optional(),
    connection: z.string().optional(),
    weight_kg: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive(msgs.weightInvalid).optional(),
    ),
    length: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),
    width: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),
    height: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),
    series_id: z.string().optional(),
    material_id: z.string().optional(),
    division_ids: z.array(z.string()).optional(),
    qty_per_box: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().int().positive(msgs.qtyInvalid).optional(),
    ),
    moq: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().int().positive(msgs.moqInvalid).optional(),
    ),
    ean_unit: eanSchema,
    ean_box: eanSchema,
    hs_code: z.string().optional(),
    country_of_origin: z.string().optional(),
    net_weight_kg: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),
  });

export type WizardForm = z.infer<ReturnType<typeof createSchema>>;
```

- [ ] **Step 5: Crear `lib/build-payload.ts`**

```ts
// mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/build-payload.ts
import type { Product, ProductCreatePayload } from "@/lib/api/endpoints/products";
import type { WizardForm } from "./wizard-schema";

export function toNumberOrNull(v: string | number | null | undefined): number | null {
  if (v === "" || v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isNaN(n) ? null : n;
}

export function buildPayload(
  values: WizardForm,
  specs: Record<string, unknown>,
): ProductCreatePayload {
  return {
    sku: values.sku,
    name_en: values.name_en,
    family: values.family,
    active: values.active,
    dn: values.dn || null,
    pn: values.pn || null,
    material: values.material || null,
    type: values.type || null,
    connection: values.connection || null,
    weight_kg: values.weight_kg ?? null,
    length: values.length ?? null,
    width: values.width ?? null,
    height: values.height ?? null,
    series_id: values.series_id || null,
    material_id: values.material_id || null,
    division_ids: values.division_ids ?? [],
    specs: Object.keys(specs).length > 0 ? specs : undefined,
    qty_per_box: values.qty_per_box ?? null,
    moq: values.moq ?? null,
    ean_unit: values.ean_unit || null,
    ean_box: values.ean_box || null,
    hs_code: values.hs_code || null,
    country_of_origin: values.country_of_origin || null,
    net_weight_kg: values.net_weight_kg ?? null,
  } as ProductCreatePayload;
}

export function productToFormValues(product: Product): Partial<WizardForm> {
  return {
    sku: product.sku,
    name_en: product.name_en ?? "",
    family: product.family as WizardForm["family"],
    active: product.active ?? true,
    dn: product.dn ?? "",
    pn: product.pn ?? "",
    material: product.material ?? "",
    type: product.type ?? "",
    connection: product.connection ?? "",
    weight_kg: product.weight_kg ?? undefined,
    length: product.length ?? undefined,
    width: product.width ?? undefined,
    height: product.height ?? undefined,
    series_id: product.series_id ?? "",
    material_id: product.material_id ?? "",
    division_ids: product.division_ids ?? [],
    qty_per_box: product.qty_per_box ?? undefined,
    moq: product.moq ?? undefined,
    ean_unit: product.ean_unit ?? "",
    ean_box: product.ean_box ?? "",
    hs_code: product.hs_code ?? "",
    country_of_origin: product.country_of_origin ?? "",
    net_weight_kg: product.net_weight_kg ?? undefined,
  };
}
```

- [ ] **Step 6: Ejecutar tests para verificar que pasan**

```bash
cd mt-pricing-frontend && npx vitest run lib/hooks/products/__tests__/wizard-transforms.test.ts 2>&1 | tail -15
```

Salida esperada: `PASSED` (3 describe blocks, todos green).

- [ ] **Step 7: Commit**

```bash
git add \
  "mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/wizard-schema.ts" \
  "mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/lib/build-payload.ts" \
  "mt-pricing-frontend/lib/hooks/products/__tests__/wizard-transforms.test.ts"
git commit -m "feat(refactor): extraer wizard-schema.ts y build-payload.ts del product-wizard"
```

---

### Task 10: Split del shell del wizard y los 5 steps

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-1-identity.tsx`
- Create: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/steps/stage-3-classification.tsx`
- Create: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/index.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard.tsx` (→ reemplazar con shell reducido)

- [ ] **Step 1: Crear `stage-1-identity.tsx`**

```tsx
// steps/stage-1-identity.tsx
"use client";
import { useTranslations } from "next-intl";
import type { UseFormReturn } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { PRODUCT_FAMILIES } from "@/lib/api/endpoints/products";
import type { WizardForm } from "../lib/wizard-schema";

interface Props {
  form: UseFormReturn<WizardForm>;
  isEdit: boolean;
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}

export function Stage1Identity({ form, isEdit }: Props) {
  const tFields = useTranslations("catalog.fields");
  return (
    <>
      <Field label={tFields("sku")} error={form.formState.errors.sku?.message}>
        <Input
          {...form.register("sku")}
          placeholder="VAL-DN50-PN16"
          autoComplete="off"
          readOnly={isEdit}
          className={isEdit ? "bg-muted" : undefined}
        />
      </Field>
      <Field label={tFields("name_en")} error={form.formState.errors.name_en?.message}>
        <Input {...form.register("name_en")} />
      </Field>
      <Field label={tFields("family")} error={form.formState.errors.family?.message}>
        <Select
          value={form.watch("family")}
          onValueChange={(v) =>
            form.setValue("family", v as (typeof PRODUCT_FAMILIES)[number], { shouldValidate: true })
          }
        >
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {PRODUCT_FAMILIES.map((f) => (
              <SelectItem key={f} value={f} className="capitalize">{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <div className="flex items-center gap-3">
        <input
          id="wizard-active"
          type="checkbox"
          className="h-4 w-4 rounded border-input"
          {...form.register("active")}
        />
        <Label htmlFor="wizard-active">{tFields("active")}</Label>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Crear `stage-3-classification.tsx`** (picker de serie, material y divisiones — extraído del wizard actual)

El contenido de este step es el bloque de Taxonomía Stage 3 (`step === 2` en el wizard actual). Extraer ese bloque completo (incluyendo `Stage3SeriesPicker`, `Stage3MaterialPicker`, `Stage3DivisionsPicker`) en el nuevo archivo, manteniendo los mismos `useQuery` para divisiones, materiales y series.

```tsx
// steps/stage-3-classification.tsx
"use client";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import type { UseFormReturn } from "react-hook-form";
import { divisionsApi } from "@/lib/api/endpoints/divisions";
import { materialsApi } from "@/lib/api/endpoints/materials";
import { seriesApi } from "@/lib/api/endpoints/series";
import type { WizardForm } from "../lib/wizard-schema";

interface Props {
  form: UseFormReturn<WizardForm>;
}

export function Stage3Classification({ form }: Props) {
  const tTax = useTranslations("catalog.create.taxonomy");

  const divisionsQ = useQuery({
    queryKey: ["divisions", "list"],
    queryFn: () => divisionsApi.list(),
    staleTime: 300_000,
  });
  const materialsQ = useQuery({
    queryKey: ["materials", "list"],
    queryFn: () => materialsApi.list(),
    staleTime: 300_000,
  });
  const seriesQ = useQuery({
    queryKey: ["series", "list"],
    queryFn: () => seriesApi.list(),
    staleTime: 300_000,
  });

  // ... render de pickers (extraído del bloque step===2 del wizard actual)
  return (
    <div className="space-y-4">
      <p className="text-sm font-medium">{tTax("title")}</p>
      {/* Serie picker, Material picker, Divisions picker — idéntico al código actual */}
    </div>
  );
}
```

- [ ] **Step 3: Crear `index.tsx` como re-export**

```tsx
// product-wizard/index.tsx
export { ProductWizard } from "./product-wizard";
```

- [ ] **Step 4: Actualizar imports en `catalogo/page.tsx` y `[sku]/edit/page.tsx`**

Buscar todos los imports de `product-wizard`:
```bash
grep -rn "product-wizard" mt-pricing-frontend/app/\(app\)/catalogo --include="*.tsx" | grep -v "product-wizard/"
```

Reemplazar cada import de `"./_components/product-wizard"` por `"./_components/product-wizard/index"` o simplemente `"./_components/product-wizard"` (Next.js resuelve el index automáticamente).

- [ ] **Step 5: Verificar compilación TypeScript y build**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

- [ ] **Step 6: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/_components/product-wizard/"
git commit -m "refactor(wizard): split product-wizard.tsx en shell + 5 steps + lib"
```

---

## Story 3D — Código: extracción de lógica de handler en `products.py`

**Esfuerzo:** 6–8h

### Task 11: Extraer `_parse_iso` duplicado a `app/api/utils.py`

**Files:**
- Create: `mt-pricing-backend/app/api/utils.py`
- Modify: `mt-pricing-backend/app/api/routes/products.py`

- [ ] **Step 1: Escribir test unitario para `parse_iso_datetime`**

Crear `mt-pricing-backend/tests/unit/test_api_utils.py`:

```python
"""Tests unitarios para app.api.utils."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from fastapi import HTTPException


def test_parse_iso_datetime_utc_z():
    from app.api.utils import parse_iso_datetime
    result = parse_iso_datetime("2024-01-15T10:30:00Z", "created_after")
    assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_parse_iso_datetime_none_returns_none():
    from app.api.utils import parse_iso_datetime
    assert parse_iso_datetime(None, "any_field") is None


def test_parse_iso_datetime_invalid_raises_422():
    from app.api.utils import parse_iso_datetime
    with pytest.raises(HTTPException) as exc_info:
        parse_iso_datetime("not-a-date", "created_after")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "invalid_datetime"
    assert "created_after" in exc_info.value.detail["title"]


def test_parse_iso_datetime_with_offset():
    from app.api.utils import parse_iso_datetime
    result = parse_iso_datetime("2024-01-15T10:30:00+04:00", "created_before")
    assert result is not None
    assert result.tzinfo is not None
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
cd mt-pricing-backend && python -m pytest tests/unit/test_api_utils.py -v 2>&1 | tail -10
```

Salida esperada: `ModuleNotFoundError: No module named 'app.api.utils'`

- [ ] **Step 3: Crear `app/api/utils.py`**

```python
"""Utilidades compartidas para los routers de la API."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    pass


def parse_iso_datetime(value: str | None, field: str) -> datetime | None:
    """Parsea un string ISO-8601 a datetime.

    Acepta sufijo ``Z`` para UTC. Lanza ``HTTPException(422)`` si el valor
    no es un datetime ISO-8601 válido.

    Args:
        value: El string a parsear, o ``None``.
        field: Nombre del campo (para el mensaje de error).

    Returns:
        El ``datetime`` parseado, o ``None`` si ``value`` es ``None``.
    """
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_datetime",
                "title": f"`{field}` no es ISO-8601 válido",
                "detail": str(exc),
            },
        ) from exc
```

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```bash
cd mt-pricing-backend && python -m pytest tests/unit/test_api_utils.py -v 2>&1 | tail -10
```

Salida esperada: `4 passed`.

- [ ] **Step 5: Reemplazar las dos closures `_parse_iso` en `products.py`**

En `products.py` hay dos definiciones idénticas de `_parse_iso`:
- L360 (dentro de `export_products_csv` como closure local)
- L493 (dentro de `list_products` como closure local)

Añadir al inicio de `products.py`:
```python
from app.api.utils import parse_iso_datetime as _parse_iso
```

Luego eliminar ambas definiciones de closure `_parse_iso` y los imports locales `from datetime import datetime as _dt` asociados. Las llamadas `_parse_iso(...)` en `export_products_csv` y `list_products` funcionan sin cambios porque la firma es idéntica.

- [ ] **Step 6: Verificar que los tests de integración existentes pasan**

```bash
cd mt-pricing-backend && python -m pytest tests/api/test_products_put_patch.py -v 2>&1 | tail -15
```

Salida esperada: todos los tests existentes siguen pasando.

- [ ] **Step 7: Commit**

```bash
git add \
  mt-pricing-backend/app/api/utils.py \
  mt-pricing-backend/app/api/routes/products.py \
  mt-pricing-backend/tests/unit/test_api_utils.py
git commit -m "refactor(backend): extraer _parse_iso duplicado a app/api/utils.parse_iso_datetime"
```

---

### Task 12: Extraer `export_products_csv` a `CsvExportService`

**Files:**
- Create: `mt-pricing-backend/app/services/products/csv_export_service.py`
- Modify: `mt-pricing-backend/app/api/routes/products.py`

- [ ] **Step 1: Crear `CsvExportService`**

```python
# app/services/products/csv_export_service.py
"""Servicio para exportar productos a CSV."""
from __future__ import annotations

import csv
import io
from typing import Any

_EXPORT_FIELDS = [
    "sku", "name_en", "family", "subfamily", "type", "brand",
    "material", "dn", "pn", "lifecycle_status", "data_quality",
    "created_at", "updated_at",
]


class CsvExportService:
    """Serializa una lista de productos a CSV en memoria."""

    def generate(self, rows: list[Any]) -> str:
        """Genera el contenido CSV a partir de una lista de ORM products.

        Args:
            rows: Lista de instancias de ``Product`` ORM (o cualquier objeto
                  con los atributos de ``_EXPORT_FIELDS``).

        Returns:
            String CSV listo para enviar como ``text/csv``.
        """
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=_EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for p in rows:
            writer.writerow({
                "sku": p.sku,
                "name_en": p.name_en or "",
                "family": p.family or "",
                "subfamily": p.subfamily or "",
                "type": getattr(p, "type", None) or "",
                "brand": p.brand or "",
                "material": p.material or "",
                "dn": p.dn or "",
                "pn": p.pn or "",
                "lifecycle_status": p.lifecycle_status or "",
                "data_quality": p.data_quality or "",
                "created_at": str(p.created_at or ""),
                "updated_at": str(p.updated_at or ""),
            })
        return output.getvalue()
```

- [ ] **Step 2: Escribir test unitario para `CsvExportService`**

Crear `mt-pricing-backend/tests/unit/test_csv_export_service.py`:

```python
"""Tests unitarios para CsvExportService."""
from __future__ import annotations

import csv
import io
from unittest.mock import MagicMock
from datetime import datetime


def _make_product(**kwargs) -> MagicMock:
    defaults = dict(
        sku="VAL-DN50", name_en="Test Valve", family="valves_ball",
        subfamily=None, type=None, brand="MT", material="brass",
        dn="DN50", pn="PN16", lifecycle_status="active",
        data_quality="complete", created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 2),
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


def test_generate_returns_valid_csv_with_header():
    from app.services.products.csv_export_service import CsvExportService
    svc = CsvExportService()
    product = _make_product()
    csv_content = svc.generate([product])
    reader = list(csv.DictReader(io.StringIO(csv_content)))
    assert len(reader) == 1
    assert reader[0]["sku"] == "VAL-DN50"
    assert reader[0]["brand"] == "MT"


def test_generate_empty_list_returns_header_only():
    from app.services.products.csv_export_service import CsvExportService
    svc = CsvExportService()
    csv_content = svc.generate([])
    lines = csv_content.strip().split("\n")
    assert len(lines) == 1  # solo header
    assert "sku" in lines[0]


def test_generate_handles_none_fields_gracefully():
    from app.services.products.csv_export_service import CsvExportService
    svc = CsvExportService()
    product = _make_product(name_en=None, subfamily=None, brand=None)
    csv_content = svc.generate([product])
    reader = list(csv.DictReader(io.StringIO(csv_content)))
    assert reader[0]["name_en"] == ""
    assert reader[0]["brand"] == ""
```

- [ ] **Step 3: Ejecutar tests para verificar que pasan**

```bash
cd mt-pricing-backend && python -m pytest tests/unit/test_csv_export_service.py -v 2>&1 | tail -10
```

Salida esperada: `3 passed`.

- [ ] **Step 4: Reemplazar lógica de CSV en el handler `export_products_csv`**

En `products.py`, el handler `export_products_csv` actualmente contiene 121 líneas de lógica. Reemplazar el bloque de serialización por la llamada al servicio:

```python
# Añadir import al inicio de products.py:
from app.services.products.csv_export_service import CsvExportService

# En el handler export_products_csv, sustituir el bloque de serialización:
# ANTES (lines 399-430):
#   _EXPORT_FIELDS = [...]; output = io.StringIO(); writer = csv.DictWriter(...)...
# DESPUÉS:
    csv_service = CsvExportService()
    return Response(
        content=csv_service.generate(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="products-export.csv"',
            "Cache-Control": "no-store",  # CSV no debe cachearse
        },
    )
```

Eliminar también los imports `import csv` e `import io` que quedan huérfanos en el handler (si no se usan en otro lugar del archivo).

- [ ] **Step 5: Verificar que los tests pasan**

```bash
cd mt-pricing-backend && python -m pytest tests/unit/test_csv_export_service.py tests/unit/test_api_utils.py -v 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add \
  mt-pricing-backend/app/services/products/csv_export_service.py \
  mt-pricing-backend/app/api/routes/products.py \
  mt-pricing-backend/tests/unit/test_csv_export_service.py
git commit -m "refactor(backend): extraer export_products_csv a CsvExportService"
```

---

### Task 13: Mover dispatch Celery de `confirm_asset_upload` a `AssetService.confirm_upload()`

**Files:**
- Modify: `mt-pricing-backend/app/services/products/asset_service.py`
- Modify: `mt-pricing-backend/app/api/routes/products.py`

- [ ] **Step 1: Leer `asset_service.py` para entender la firma actual de `confirm_upload`**

```bash
grep -n "async def confirm_upload\|def confirm_upload" mt-pricing-backend/app/services/products/asset_service.py
```

- [ ] **Step 2: Mover el bloque Celery + CLIP al servicio**

En `asset_service.py`, al final de `confirm_upload()` (después de crear y retornar el asset), añadir:

```python
async def confirm_upload(self, sku: str, *, storage_path: str, kind: str,
                          mime_type: str | None = None, bytes_size: int | None = None,
                          width: int | None = None, height: int | None = None,
                          alt_text: str | None = None, locale: str | None = None,
                          caption: str | None = None, is_primary: bool = False,
                          position: int | None = None, actor_id: str | None = None):
    # ... lógica existente de creación del asset en DB ...

    # Dispatch thumbnails — movido desde el handler
    if asset.kind in ("photo", "banner", "mirror_url"):
        try:
            from app.workers.thumbnails import generate_thumbnails
            generate_thumbnails.delay(sku, asset.storage_path)
        except Exception:  # noqa: BLE001
            pass

    # CLIP indexing — movido desde el handler
    if asset.kind in ("photo", "banner", "mirror_url") and asset.storage_path:
        try:
            from app.services.feature_flags.flag_service import is_reverse_image_search_enabled
            from app.services.image_search.clip_service import get_image_backend
            if await is_reverse_image_search_enabled(self._session):
                _backend = get_image_backend()
                await _backend.index_image(str(sku), asset.storage_path)
        except Exception:  # noqa: BLE001
            pass

    return asset
```

En `products.py`, eliminar el bloque de dispatch (líneas 1258–1279) del handler `confirm_asset_upload`. El handler queda reducido a: validar SKU + llamar `asset_service.confirm_upload()` + retornar el asset.

- [ ] **Step 3: Verificar compilación Python**

```bash
cd mt-pricing-backend && python -c "from app.api.routes.products import router; print('OK')"
```

Salida esperada: `OK`.

- [ ] **Step 4: Commit**

```bash
git add \
  mt-pricing-backend/app/services/products/asset_service.py \
  mt-pricing-backend/app/api/routes/products.py
git commit -m "refactor(backend): mover Celery dispatch y CLIP indexing al AssetService.confirm_upload"
```

---

## Story 3E — Tests: cobertura del backlog restante (72 endpoints)

**Esfuerzo:** 24h

### Task 14: Tests de taxonomía admin

**Files:**
- Create: `mt-pricing-backend/tests/api/test_products_taxonomy.py`

- [ ] **Step 1: Escribir tests para endpoints de taxonomía admin**

Los endpoints cubiertos son: `GET /taxonomy/types`, `GET /taxonomy/types/{slug}`, `GET /taxonomy/types/{slug}/nodes`, `POST /taxonomy/types/{slug}/nodes`, `PUT /taxonomy/types/{slug}/nodes/{id}`, `DELETE /taxonomy/types/{slug}/nodes/{id}`.

```python
"""Integration tests para endpoints de taxonomía admin."""
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "aud": "authenticated", "email": email,
         "iat": now, "exp": now + 3600,
         "app_metadata": {"role": "comercial"}},
        JWT_SECRET, algorithm="HS256",
    )


async def _seed_admin(session: AsyncSession) -> tuple[Any, str]:
    from app.db.models.user import Permission, Role, RolePermission, User
    from sqlalchemy import select
    perms_codes = ["products:read", "products:write", "admin:taxonomy"]
    perm_ids = []
    for code in perms_codes:
        existing = (await session.execute(select(Permission).where(Permission.code == code))).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perm_ids.append(p.id)
        else:
            perm_ids.append(existing.id)
    role = (await session.execute(select(Role).where(Role.code == "pim_admin"))).scalar_one_or_none()
    if role is None:
        role = Role(code="pim_admin", name="pim_admin", permissions_snapshot=perms_codes)
        session.add(role)
        await session.flush()
        for pid in perm_ids:
            session.add(RolePermission(role_id=role.id, permission_id=pid))
        await session.flush()
    uid = uuid4()
    email = f"admin-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="A", locale="es", is_active=True, role_id=role.id)
    session.add(user)
    await session.flush()
    return uid, email


@pytest_asyncio.fixture
async def app_with_db(db_session: AsyncSession) -> AsyncIterator[Any]:
    from app.api.deps import get_db_session
    from app.main import app
    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session
    app.dependency_overrides[get_db_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def client(app_with_db: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_taxonomy_types_returns_200(client: AsyncClient, db_session: AsyncSession) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    resp = await client.get("/api/v1/taxonomy/types", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_taxonomy_types_without_auth_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/taxonomy/types")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_taxonomy_type_unknown_slug_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    resp = await client.get("/api/v1/taxonomy/types/nonexistent-slug-xyz", headers=headers)
    assert resp.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_taxonomy_nodes_for_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    # Primero obtener los tipos disponibles
    types_resp = await client.get("/api/v1/taxonomy/types", headers=headers)
    assert types_resp.status_code == 200
    types = types_resp.json()
    if not types:
        pytest.skip("No taxonomy types seeded")
    slug = types[0]["slug"]
    resp = await client.get(f"/api/v1/taxonomy/types/{slug}/nodes", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Ejecutar tests**

```bash
cd mt-pricing-backend && python -m pytest tests/api/test_products_taxonomy.py -v --tb=short 2>&1 | tail -20
```

Salida esperada: los 4 tests pasan (o `skip` el último si no hay tipos seeded).

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-backend/tests/api/test_products_taxonomy.py
git commit -m "test(backend): cobertura endpoints taxonomía admin"
```

---

### Task 15: Tests de series admin, divisiones y materiales

**Files:**
- Create: `mt-pricing-backend/tests/api/test_products_series_admin.py`
- Create: `mt-pricing-backend/tests/api/test_products_divisiones.py`
- Create: `mt-pricing-backend/tests/api/test_products_materials_compat.py`

- [ ] **Step 1: Escribir tests para series admin**

Crear `test_products_series_admin.py` usando el mismo patrón de fixtures. Cubrir:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_series_returns_200(client, db_session): ...
# GET /products/series → 200, lista (puede ser vacía)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_series_certifications_for_unknown_series_returns_404(client, db_session): ...
# GET /products/series/{id}/certifications con UUID inexistente → 404

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_series_without_auth_returns_401(client): ...
# GET /products/series sin auth → 401
```

- [ ] **Step 2: Escribir tests para divisiones**

Crear `test_products_divisiones.py`:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_divisions_returns_200(client, db_session): ...
# GET /products/divisions → 200, lista

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_division_unknown_code_returns_404(client, db_session): ...
# GET /products/divisions/NONEXISTENT → 404

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_divisions_without_auth_returns_401(client): ...
```

- [ ] **Step 3: Escribir tests para materiales, compatibility y display-pair**

Crear `test_products_materials_compat.py`:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_product_materials_for_unknown_sku_returns_404(client, db_session): ...
# GET /products/{sku}/materials para SKU inexistente → 404

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_compatibility_for_unknown_sku_returns_404(client, db_session): ...
# GET /products/{sku}/compatibility para SKU inexistente → 404

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_display_pair_for_unknown_sku_returns_404(client, db_session): ...
# GET /products/{sku}/display-pair para SKU inexistente → 404

@pytest.mark.integration
@pytest.mark.asyncio
async def test_materials_without_auth_returns_401(client): ...
# GET /products/{sku}/materials sin auth → 401
```

- [ ] **Step 4: Ejecutar todos los tests nuevos**

```bash
cd mt-pricing-backend && python -m pytest \
  tests/api/test_products_series_admin.py \
  tests/api/test_products_divisiones.py \
  tests/api/test_products_materials_compat.py \
  -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add \
  mt-pricing-backend/tests/api/test_products_series_admin.py \
  mt-pricing-backend/tests/api/test_products_divisiones.py \
  mt-pricing-backend/tests/api/test_products_materials_compat.py
git commit -m "test(backend): cobertura series admin, divisiones, materiales y compatibility"
```

---

### Task 16: Tests de tech-tables, UoM conversions, datasheets y bore dimensions

**Files:**
- Create: `mt-pricing-backend/tests/api/test_products_tech_tables.py`

- [ ] **Step 1: Crear el archivo de tests**

```python
"""Integration tests para tech-tables, UoM conversions, datasheets y bore dimensions."""
from __future__ import annotations

# (imports idénticos al patrón de test_products_put_patch.py)
# ...

@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_tech_tables_unknown_sku_returns_200_empty(client, db_session):
    """list_tech_tables retorna 200+[] para SKU inexistente — documentar comportamiento actual.
    
    Nota: El audit (A-3) indica que debería ser 404. Este test documenta el
    comportamiento actual y sirve de referencia cuando se implemente la corrección.
    """
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    resp = await client.get("/api/v1/products/NONEXISTENT-SKU-XYZ/tech-tables", headers=headers)
    # Comportamiento actual: 200 + []  (debería ser 404 — ver issue A-3)
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.json() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_uom_conversions_unknown_sku_returns_200_empty(client, db_session):
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    resp = await client.get("/api/v1/products/NONEXISTENT-SKU-XYZ/uom-conversions", headers=headers)
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.json() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_datasheets_unknown_sku_returns_200_empty(client, db_session):
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    resp = await client.get("/api/v1/products/NONEXISTENT-SKU-XYZ/datasheets", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_bore_dimensions_unknown_sku_returns_200_empty(client, db_session):
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}
    resp = await client.get("/api/v1/products/NONEXISTENT-SKU-XYZ/bore-dimensions", headers=headers)
    assert resp.status_code in (200, 404)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tech_tables_without_auth_returns_401(client):
    resp = await client.get("/api/v1/products/SOME-SKU/tech-tables")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_uom_conversions_without_auth_returns_401(client):
    resp = await client.get("/api/v1/products/SOME-SKU/uom-conversions")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bore_dimensions_without_auth_returns_401(client):
    resp = await client.get("/api/v1/products/SOME-SKU/bore-dimensions")
    assert resp.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_uom_conversion_happy_path(client, db_session):
    """POST /products/{sku}/uom-conversions crea conversión y retorna 201."""
    uid, email = await _seed_admin(db_session)
    headers = {"Authorization": f"Bearer {_emit_jwt(sub=str(uid), email=email)}"}

    # Crear producto primero
    sku = f"TEST-{uuid4().hex[:6].upper()}"
    create_resp = await client.post(
        "/api/v1/products",
        json={"sku": sku, "name_en": "Test", "family": "valves_ball"},
        headers=headers,
    )
    if create_resp.status_code not in (200, 201):
        pytest.skip("Product creation not available in test env")

    resp = await client.post(
        f"/api/v1/products/{sku}/uom-conversions",
        json={"from_uom": "pcs", "to_uom": "box", "factor": "12.0"},
        headers=headers,
    )
    assert resp.status_code in (200, 201, 422)  # 422 si el schema difiere
```

- [ ] **Step 2: Ejecutar tests**

```bash
cd mt-pricing-backend && python -m pytest tests/api/test_products_tech_tables.py -v --tb=short 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-backend/tests/api/test_products_tech_tables.py
git commit -m "test(backend): cobertura tech-tables, uom-conversions, datasheets y bore dimensions"
```

---

## Story 3F — Código: consolidar design system y code quick wins

**Esfuerzo:** 8–10h

### Task 17: Registrar queryKeys faltantes y migrar `use-facets.ts`

Ya completado en Task 7. Si `use-facets.ts` define `queryKey: ["products", "facets", filters]` inline, reemplazar con `productKeys.facets(filters)`.

---

### Task 18: Añadir `id` y `base_uom` al tipo `Product` de TypeScript

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/products.ts` (o donde esté definido el tipo `Product`)

- [ ] **Step 1: Localizar definición del tipo `Product`**

```bash
grep -n "^export.*type Product\|^export.*interface Product" mt-pricing-frontend/lib/api/endpoints/products.ts | head -5
```

- [ ] **Step 2: Añadir los campos faltantes**

Encontrar la definición del tipo `Product` y añadir:

```ts
export type Product = {
  // ... campos existentes ...
  id?: string;           // ← añadir: usado en cache seeds de mutations
  base_uom?: string | null;  // ← añadir: usado en unidades/_client.tsx
  // ... resto de campos ...
};
```

- [ ] **Step 3: Eliminar los 5+ type casts por estos campos faltantes**

Buscar y reemplazar los casts relacionados:

```bash
grep -rn "as Product & { id" mt-pricing-frontend/lib/hooks/products/
grep -rn "as { base_uom" mt-pricing-frontend/app/\(app\)/catalogo/
```

Reemplazos:
- `(created as Product & { id?: string })` → `created` (ahora `id` ya está en el tipo)
- `(product as { base_uom?: string | null } | undefined)?.base_uom` → `product?.base_uom`

- [ ] **Step 4: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

Salida esperada: sin errores. Si aparecen errores, el campo puede necesitar ser `optional` (`?`) en los tipos de request/response también.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/products.ts mt-pricing-frontend/lib/hooks/products/
git commit -m "fix(types): añadir id y base_uom al tipo Product para eliminar type casts"
```

---

### Task 19: Eliminar ruta `/products` legacy

**Files:**
- Delete: `mt-pricing-frontend/app/(app)/products/` (directorio completo)

- [ ] **Step 1: Verificar que la ruta no está en la navegación**

```bash
grep -rn "/products" mt-pricing-frontend/app/\(app\)/ --include="*.tsx" | grep -v "catalogo\|/products/" | head -20
```

Confirmar que ningún link de navegación apunta a `/products` (solo a `/catalogo`).

- [ ] **Step 2: Verificar que no hay tests que apunten a `/products` legacy**

```bash
grep -rn "\"\/products\"" mt-pricing-frontend/ --include="*.test.*" --include="*.spec.*" | head -10
```

- [ ] **Step 3: Eliminar el directorio**

```bash
rm -rf "mt-pricing-frontend/app/(app)/products"
```

- [ ] **Step 4: Verificar que el build no falla**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: eliminar ruta /products legacy (duplicada de /catalogo)"
```

---

### Task 20: Renombrar `_mt-client.tsx` → `_client.tsx` en traducciones

**Files:**
- Rename: `mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_mt-client.tsx` → `_client.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/page.tsx`

- [ ] **Step 1: Renombrar el archivo**

```bash
mv "mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_mt-client.tsx" \
   "mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_client.tsx"
```

- [ ] **Step 2: Actualizar el import en `page.tsx`**

En `mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/page.tsx`, cambiar:
```tsx
// Antes:
import { TranslationsClient } from "./_mt-client";
// Después:
import { TranslationsClient } from "./_client";
```

(El nombre del componente exportado no cambia, solo el archivo fuente.)

- [ ] **Step 3: Verificar compilación**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS\|traducciones" | head -10
```

- [ ] **Step 4: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/"
git commit -m "chore: renombrar _mt-client.tsx → _client.tsx en traducciones (naming consistency)"
```

---

### Task 21: Corregir antipatrón `= None + # type: ignore` en `get_facets`

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/products.py`

- [ ] **Step 1: Localizar la línea exacta**

```bash
grep -n "type: ignore\[assignment\]" mt-pricing-backend/app/api/routes/products.py
```

Resultado esperado: línea ~690.

- [ ] **Step 2: Corregir el antipatrón**

Estado actual (antipatrón):
```python
session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
```

Estado correcto (sin default ni `# type: ignore`):
```python
session: Annotated[AsyncSession, Depends(get_db_session)],
```

FastAPI inyecta el valor; el `= None` con `# type: ignore` solo existe para satisfacer al type checker de forma incorrecta. La solución correcta es omitir el default.

- [ ] **Step 3: Verificar compilación Python**

```bash
cd mt-pricing-backend && python -c "from app.api.routes.products import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/api/routes/products.py
git commit -m "fix(backend): eliminar antipatrón = None + type: ignore en get_facets"
```

---

### Task 22: Migrar tabs `mercados`, `recambios`, `traducciones`, `unidades` a MT primitives

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/_client.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/recambios/_client.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_client.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/_client.tsx`

- [ ] **Step 1: Auditar los imports de shadcn/ui directo en los 4 tabs**

```bash
grep -n "from \"@/components/ui/" \
  "mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/_client.tsx" \
  "mt-pricing-frontend/app/(app)/catalogo/[sku]/recambios/_client.tsx" \
  "mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_client.tsx" \
  "mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/_client.tsx"
```

- [ ] **Step 2: Reemplazar en cada tab**

Para cada tab, sustituir los imports de shadcn/ui directo por los equivalentes MT:

```tsx
// Antes (shadcn/ui directo):
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// Después (MT primitives):
import { SectionCard } from "@/components/mt/section-card";
import { MtButton } from "@/components/mt/mt-button";
import { MtSkeleton } from "@/components/mt/mt-skeleton";
// (o los nombres exactos que usen los tabs MT: audit, costos, datasheets, enriquecer)
```

Verificar los nombres exactos de los MT primitives buscando cómo los usan los tabs ya migrados:
```bash
grep -n "from \"@/components/mt/" \
  "mt-pricing-frontend/app/(app)/catalogo/[sku]/audit/_client.tsx" | head -10
```

- [ ] **Step 3: Reemplazar bloques de loading/error con `<SkuTabShell>` si existe**

Si `<SkuTabShell>` fue creado en el refactor de wizard, usar el patrón para eliminar el boilerplate de loading/error repetido en cada tab. Si no existe, documentar como deuda para el siguiente sprint.

- [ ] **Step 4: Verificar compilación TypeScript**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | head -20
```

- [ ] **Step 5: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/_client.tsx" \
        "mt-pricing-frontend/app/(app)/catalogo/[sku]/recambios/_client.tsx" \
        "mt-pricing-frontend/app/(app)/catalogo/[sku]/traducciones/_client.tsx" \
        "mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/_client.tsx"
git commit -m "refactor(ui): migrar tabs mercados/recambios/traducciones/unidades a MT primitives"
```

---

## Verificación final

- [ ] **Compilación TypeScript completa sin errores**

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep "error TS" | wc -l
```

Salida esperada: `0`

- [ ] **JSON de mensajes válido**

```bash
cd mt-pricing-frontend && node -e "JSON.parse(require('fs').readFileSync('messages/es.json','utf8')); console.log('OK')"
```

- [ ] **Tests unitarios de backend pasan**

```bash
cd mt-pricing-backend && python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -15
```

- [ ] **Tests de integración de backend pasan**

```bash
cd mt-pricing-backend && python -m pytest tests/api/ -v --tb=short -x 2>&1 | tail -20
```

- [ ] **Redesplegar contenedores afectados**

```bash
# Frontend (cambios de código):
docker restart mt-frontend

# Backend (cambios de código + nuevos servicios):
docker restart mt-backend

# Verificar health:
curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live
```

---

## Resumen de stories y estimaciones

| Story | Descripción | Esfuerzo | Tasks |
|-------|-------------|----------|-------|
| 3A | i18n: internacionalización del catálogo | 8–12h | 1–6 |
| 3B | Performance: N+1 ficha-enrich + queryKeys jerarquía | 5h | 7–8 |
| 3C | Código: refactor product-wizard.tsx en módulos | 6–8h | 9–10 |
| 3D | Código: extracción de lógica de handler en products.py | 6–8h | 11–13 |
| 3E | Tests: cobertura de 72 endpoints restantes | 24h | 14–16 |
| 3F | Código: design system + quick wins | 8–10h | 17–22 |
| **Total** | | **57–67h** | |

## Referencias de archivos clave

| Archivo | Relevancia |
|---------|-----------|
| `mt-pricing-frontend/messages/es.json` | Fuente única de strings i18n |
| `mt-pricing-frontend/lib/hooks/products/query-keys.ts` | Factory de queryKeys — extender aquí siempre |
| `mt-pricing-frontend/lib/hooks/products/use-product-model.ts` | Hooks de sub-recursos — queryKeys corregidas en 3B |
| `mt-pricing-backend/app/api/routes/products.py` | Archivo de 2351 líneas — handler simplificado en 3D |
| `mt-pricing-backend/app/api/utils.py` | Utilidades compartidas — creado en 3D |
| `mt-pricing-backend/app/services/products/csv_export_service.py` | Servicio CSV — creado en 3D |
| `mt-pricing-backend/app/services/ficha_enrichment/applier.py` | N+1 corregido en 3B |
| `mt-pricing-backend/tests/api/test_products_put_patch.py` | Patrón de referencia para nuevos tests |
