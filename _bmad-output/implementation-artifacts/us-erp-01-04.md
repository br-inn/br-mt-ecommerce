# US-ERP-01-04 — GTIN en specs card + lifecycle chip en listado

**Status:** review
**Sprint:** S13
**Story Points:** 3
**Epic:** EP-ERP-01 — UX Producto: SAP Fiori / Akeneo patterns
**Completed:** 2026-05-31

## Resumen de implementación

Muestra el GTIN en la specs card de la página de detalle de producto, y
muestra el chip `LifecycleStatusBadge` en el listado del catálogo (`/catalogo`).

## Cambios realizados

### Backend — Base de datos
- **`mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`**
  - M1-08: columna `products.gtin STRING(14)` nullable
  - CHECK: `gtin IS NULL OR (length(gtin) IN (8,12,13,14) AND gtin ~ '^[0-9]+$')`
  - Índice `idx_products_gtin`

- **`mt-pricing-backend/app/db/models/product.py`**
  - `gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)`

### Frontend — Specs Card con GTIN
- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-specs.tsx`** (modificado)
  - Campo "GTIN (GS1)" en la specs card del detalle de producto
  - Renderiza el código en `font-mono`
  - Muestra badge con tipo (EAN-8, EAN-12, EAN-13, GTIN-14) según longitud
  - `—` cuando el campo está vacío

### Frontend — Lifecycle chip en listado
- **`mt-pricing-frontend/app/(app)/catalogo/page.tsx`** (modificado)
  - Import de `LifecycleStatusBadge`
  - Columna `lifecycle_status` en CSV export
  - Renderiza `<LifecycleStatusBadge status={r.lifecycle_status} />` en cada fila del listado
  - Integrado junto a las otras columnas de la tabla de productos

### Frontend — Tipos TypeScript
- **`mt-pricing-frontend/lib/api/endpoints/products.ts`**
  - `ProductListItem.lifecycle_status?: ProductLifecycleStatus | null`
  - `ProductDetail.gtin?: string | null`
  - `ProductDetail.base_uom?: string | null`
  - `type ProductLifecycleStatus = 'draft' | 'in_review' | 'active' | 'deprecated' | 'replaced' | 'discontinued'`

## Criterios de aceptación verificados

- [x] `gtin` visible en specs card del detalle de producto (`product-specs.tsx`)
- [x] GTIN con formato mono y badge tipo (8d/12d/13d/14d)
- [x] `LifecycleStatusBadge` renderizado en cada fila del listado `/catalogo`
- [x] `lifecycle_status` incluido en CSV export del listado

## Archivos impactados

- `mt-pricing-frontend/app/(app)/catalogo/page.tsx` (lifecycle badge en listado)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-specs.tsx` (GTIN en specs)
- `mt-pricing-frontend/components/ui/lifecycle-status-badge.tsx` (componente compartido)
- `mt-pricing-frontend/lib/api/endpoints/products.ts` (tipos TypeScript)
- `mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`
