# US-ERP-01-02 — Tab "Mercados" + product_releases + "Activar mercado"

**Status:** review
**Sprint:** S13
**Story Points:** 8
**Epic:** EP-ERP-01 — UX Producto: SAP Fiori / Akeneo patterns
**Completed:** 2026-05-31

## Resumen de implementación

Tab "Mercados" en la página de detalle de producto con listado de releases por mercado
y dialog multi-step para activar un producto en un nuevo mercado (patrón D365 Released Products).

## Cambios realizados

### Backend — Base de datos
- **`mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`**
  - Crea tabla `product_releases`:
    - `id UUID PK`
    - `product_sku TEXT FK products(sku) CASCADE`
    - `market_code TEXT` (UAE, KSA, MX…)
    - `local_name`, `local_description`, `local_sku`, `local_uom`
    - `list_price NUMERIC(18,4)`, `price_currency CHAR(3)`, `tax_class`
    - `status TEXT` (draft | active | suspended | discontinued)
    - `is_active BOOLEAN`
    - `released_at TIMESTAMPTZ`, `released_by UUID → users`, `created_by UUID → users`
    - UNIQUE(product_sku, market_code)
  - Índice parcial `idx_product_releases_status_active` (en mig 20260514_105)

- **`mt-pricing-backend/app/db/models/product.py`**
  - ORM `ProductRelease` con relación `Product.releases`

### Backend — API
- **`mt-pricing-backend/app/api/routes/products.py`**
  - `GET /{sku}/releases` — lista releases del producto
  - `POST /{sku}/releases` — crea release (requiere `products:write`)
  - `PATCH /{sku}/releases/{market_code}` — actualiza release
  - `POST /{sku}/releases/{market_code}/activate` — activa release
  - `POST /{sku}/releases/{market_code}/deactivate` — desactiva release

- **`mt-pricing-backend/app/schemas/products.py`**
  - `ProductReleaseBase`, `ProductReleaseCreate`, `ProductReleasePatch`, `ProductReleaseResponse`

### Frontend — Componentes
- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx`** (modificado)
  - Tab "Mercados" ya incluido (href `/catalogo/${sku}/mercados`)

- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/page.tsx`** (creado)
  - Server component que monta `MercadosClient`

- **`mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/_client.tsx`** (creado)
  - Tabla de releases con: mercado (flag+código), nombre local, SKU local, precio, clase fiscal, estado
  - `ReleaseStatusIcon` con colores SAP Fiori semánticos
  - `AgregarMercadoDialog` multi-step (3 pasos):
    - Paso 1: código de mercado
    - Paso 2: moneda, precio local, clase fiscal
    - Paso 3: resumen + confirmación
  - Botones Activar/Suspender por release (RBAC `products:write`)
  - Estado vacío con icono Globe

## Criterios de aceptación verificados

- [x] Tab "Mercados" visible en la página de detalle
- [x] Tabla de mercados con país, moneda, precio local, clase fiscal, estado, fecha activación
- [x] Botón "Agregar mercado" con dialog multi-step (3 pasos)
- [x] `POST /api/v1/products/{sku}/releases` crea registro en `product_releases`
- [x] Solo `products:write` puede crear/activar releases (RBAC)

## Archivos impactados

- `mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/page.tsx` (creado)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/_client.tsx` (creado)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx` (tab Mercados)
- `mt-pricing-backend/app/api/routes/products.py` (endpoints releases)
- `mt-pricing-backend/app/schemas/products.py` (ProductRelease schemas)
- `mt-pricing-backend/alembic/versions/20260521_097_m1_product_releases_uom_gtin.py`
