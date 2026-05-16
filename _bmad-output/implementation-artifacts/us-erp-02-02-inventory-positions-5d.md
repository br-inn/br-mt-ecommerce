# US-ERP-02-02 — Stock types diferenciados + inventory_positions 5D

**Status:** review
**Sprint:** S13
**Story Points:** 8
**Epic:** EP-ERP-02 — Inventario v2
**Fecha implementación:** 2026-05-16

## Resumen

Extensión de la tabla `inventory_positions` con el modelo 5D (product × warehouse × location × lot × stock_type) y diferenciación de tipos de stock para ATP check.

## Componentes implementados

### Migración
- `mt-pricing-backend/alembic/versions/20260515_106_inventory_positions_5d.py`
  - Columnas añadidas: `warehouse_id`, `lot_id`, `location_id`, `stock_type`
  - Constraint: `ck_inv_pos_stock_type` — IN('unrestricted','quality_inspection','restricted','in_transit')
  - Índices: `uix_inv_pos_5d` (único 5D), `ix_inv_pos_unrestricted` (solo unrestricted)
  - `down_revision = "20260515_105"` ✓

### Modelos
- `mt-pricing-backend/app/db/models/inventory.py` — `InventoryPosition` con campos 5D

### Endpoints (prefijo `/api/v1/inventory`)
- `GET /inventory/positions` — lista con filtros sku, warehouse_id, stock_type
- `GET /inventory/positions/{sku}` — posiciones por SKU
- `GET /inventory/positions/{sku}/availability` — solo unrestricted (ATP)

## Verificación

- DB al HEAD `20260531_133` — tablas con columnas 5D correctas
- Solo stock `unrestricted` aparece en ATP checks
