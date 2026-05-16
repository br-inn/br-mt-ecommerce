# US-ERP-01-01 — LifecycleStatusBadge + Quick Facts header

**Status:** review
**Sprint:** S13
**Story Points:** 5
**Epic:** EP-ERP-01 — UX Producto: SAP Fiori / Akeneo patterns
**Completed:** 2026-05-31

## Resumen de implementación

Implementa el badge semántico de ciclo de vida del producto y la fila de Quick Facts
(SAP Fiori Object Page pattern) en el header de la página de detalle de producto.

## Cambios realizados

### Backend — Migración Alembic
- **`mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`**
  - M1-05: `ALTER TYPE lifecycle_status ADD VALUE IF NOT EXISTS 'in_review'`
  - Enum final: `draft | in_review | active | deprecated | replaced | discontinued`

- **`mt-pricing-backend/app/db/models/product.py`**
  - `lifecycle_status`: `PG_ENUM(..., create_type=False)` con los 6 valores
  - `gtin`: `String(14)` nullable
  - `base_uom`: `String(10)` NOT NULL DEFAULT 'UNIT'

### Frontend — Componentes
- **`mt-pricing-frontend/components/ui/lifecycle-status-badge.tsx`** (nuevo)
  - Renderiza badge con dot de color semántico:
    - `draft` = gris (`secondary`)
    - `in_review` = amarillo (`outline` + `bg-yellow-500`)
    - `active` = verde (`default` + `bg-green-500`)
    - `deprecated` / `replaced` = naranja (`outline`)
    - `discontinued` = rojo (`destructive`)
  - Props: `status: ProductLifecycleStatus | null | undefined`

- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`** (modificado)
  - Reemplaza badge binario `active/inactive` por `LifecycleStatusBadge`
  - Quick Facts row (grid 2-col móvil / 4-col desktop):
    - UoM Base (con ícono Ruler)
    - GTIN (con ícono Barcode)
    - Marca
    - Serie
  - Quick Facts editables en modo edit (inline editing de lifecycle_status, marca y GTIN)
  - `CompletenessRing` integrado junto al nombre del producto (US-ERP-01-05 pre-impl)

## Criterios de aceptación verificados

- [x] `LifecycleStatusBadge` con 6 estados y colores semánticos
- [x] Reemplaza badge binario en `ProductHeader`
- [x] Quick Facts row con 4 KVPs (UoM Base · GTIN · Marca · Serie)
- [x] KVPs muestran `—` si el campo está vacío (no se ocultan)
- [x] Responsive: 2 columnas en móvil (`grid-cols-2`), 4 en desktop (`sm:grid-cols-4`)

## Archivos impactados

- `mt-pricing-frontend/components/ui/lifecycle-status-badge.tsx` (creado)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx` (modificado)
- `mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py` (migración)
- `mt-pricing-backend/app/db/models/product.py` (columnas lifecycle_status, gtin, base_uom)
