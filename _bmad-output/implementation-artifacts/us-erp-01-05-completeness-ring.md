# US-ERP-01-05 — Completeness Ring + Breadcrumb navegable

**Sprint:** S14 | **Story Points:** 5 | **Status:** review | **Fecha:** 2026-05-16

## Resumen de implementación

### CompletenessRing (UX-06)

**Archivo:** `mt-pricing-frontend/components/ui/completeness-ring.tsx`

Mejoras implementadas sobre la versión preexistente:
- Tooltip agrupado por categoría al estilo Akeneo: **Datos básicos / Traducciones / Imagen / Especificaciones**
- Reemplazados colores hex hardcodeados por clases Tailwind v4 (`stroke-green-500`, `stroke-lime-500`, `stroke-yellow-500`, `stroke-red-500`, `stroke-muted-foreground/20`)
- Lógica de completeness con 8 campos: `name_es`, `brand`, `base_uom`, `gtin`, `lifecycle_status`, `name_en`, `name_ar`, `primary_image_url`
- `aria-label` y `role="tooltip"` para accesibilidad
- Estructura de `groups` por categoría en lugar de lista plana

### ProductBreadcrumb (UX-08)

**Archivo:** `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-breadcrumb.tsx`

- Añadido segmento `especificaciones` y `enrich` al mapa de tabs
- Corregida etiqueta `Imagenes` → `Imágenes` (con tilde)
- Corregida etiqueta `Auditoria` → `Auditoría`
- El tab activo ahora es un `<Link>` en lugar de `<span>` (con `aria-current="page"`)
- Breadcrumb visible en todas las sub-páginas del producto (implementado en `layout.tsx`)

### Layout breadcrumb

**Archivo:** `mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx`

Ya tenía la estructura `Catálogo > [SKU] > [Tab activo]` correctamente implementada usando `ProductBreadcrumb`.

### i18n

Nuevas keys añadidas en `es.json`, `en.json`, `ar.json` bajo `catalog.product.completeness`:
- `label`, `allComplete`, `groups.basic`, `groups.translations`, `groups.image`, `groups.specs`

## ACs verificados

- [x] Ring SVG circular con porcentaje en el header del producto
- [x] Tooltip con campos faltantes agrupados por categoría
- [x] Lógica de completeness dinámica basada en campos del producto
- [x] Breadcrumb `Catálogo > [SKU] > [Tab activo]` navegable
- [x] Breadcrumb visible en todas las sub-páginas del producto
- [x] Colores del ring basados en design tokens (no hex hardcoded)
