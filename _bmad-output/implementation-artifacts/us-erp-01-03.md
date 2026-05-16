# US-ERP-01-03 — Tab "Unidades" — base_uom + conversiones

**Status:** review
**Sprint:** S13
**Story Points:** 5
**Epic:** EP-ERP-01 — UX Producto: SAP Fiori / Akeneo patterns
**Completed:** 2026-05-31

## Resumen de implementación

Tab "Unidades" en la página de detalle del producto con la unidad de medida base
y tabla de conversiones entre unidades alternativas (patrón SAP MM UoM alternativas).

## Cambios realizados

### Backend — Base de datos
- **`mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`**
  - M1-04: columna `products.base_uom TEXT NOT NULL DEFAULT 'UNIT'`
  - M1-04: tabla `product_uom_conversions`:
    - `id UUID PK`
    - `product_sku TEXT FK products(sku) CASCADE`
    - `uom_from STRING(10)`, `uom_to STRING(10)`
    - `factor NUMERIC(18,6)` > 0
    - `is_active BOOLEAN DEFAULT true`
    - `created_at TIMESTAMPTZ`
    - CHECK: `uom_from <> uom_to`
    - CHECK: `factor > 0`
    - Índice compuesto en (product_sku, uom_from, uom_to)

- **`mt-pricing-backend/app/db/models/product.py`**
  - ORM `ProductUomConversion` con relación `Product.uom_conversions`
  - `products.base_uom` columna en ORM Product

### Backend — API
- **`mt-pricing-backend/app/api/routes/products.py`**
  - `GET /{sku}/uom-conversions` — lista conversiones (retorna `[]` si no hay)
  - `POST /{sku}/uom-conversions` — crea conversión (requiere `products:write`)
  - `DELETE /{sku}/uom-conversions/{uom_from}/{uom_to}` — elimina conversión

- **`mt-pricing-backend/app/schemas/products.py`**
  - `ProductUomConversionBase`, `ProductUomConversionCreate`, `ProductUomConversionResponse`
  - Campo `direction: str | None` para indicar dirección canónica (ej: "1 BOX = 12 UNIT")

### Frontend — Componentes
- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx`** (modificado)
  - Tab "Unidades" incluido (href `/catalogo/${sku}/unidades`)

- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/page.tsx`** (creado)
  - Server component que monta `UnidadesClient`

- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/_client.tsx`** (creado)
  - Card "Unidad de Medida Base" con badge prominente de `base_uom`
  - Tabla "Conversiones de Unidades":
    - Columnas: De (badge mono) → A (badge outline) × Factor | Dirección | Estado
    - Botón Eliminar (RBAC `products:write`)
  - Estado vacío: "No hay conversiones definidas para este producto"
  - Mensaje contextual: "Solo unidad base configurada" cuando lista vacía

## Criterios de aceptación verificados

- [x] Tab "Unidades" visible en la página de detalle
- [x] Muestra `base_uom` del producto
- [x] Tabla de conversiones: unidad alternativa, factor, dirección
- [x] `GET /api/v1/products/{sku}/uom-conversions` retorna `[]` si no hay conversiones
- [x] Mensaje "No hay conversiones definidas" cuando lista vacía

## Archivos impactados

- `mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/page.tsx` (creado)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/unidades/_client.tsx` (creado)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx` (tab Unidades)
- `mt-pricing-backend/app/api/routes/products.py` (endpoints uom-conversions)
- `mt-pricing-backend/app/schemas/products.py` (ProductUomConversion schemas)
- `mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`
