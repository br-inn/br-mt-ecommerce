---
story_key: US-ERP-02-03
title: Lot tracking — inventory_lots + trazabilidad upstream/downstream
status: review
sprint: S14
story_points: 8
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/erp-02-inv, 4ac94e8).

**Migraciones:**
- `20260515_107_inventory_lots_lot_fk.py` — tabla `inventory_lots` con FK a `purchase_order_lines` y columnas lot_number, product_id, manufacture_date, expiry_date, country_of_origin, quality_status (enum: released/hold/blocked), po_line_id.

**Modelo:** `app/db/models/inventory.py` — clase `InventoryLot` con todos los campos requeridos.

**Repositorio:** `app/repositories/inventory.py` — metodos `list_lots`, `get_lot`, `patch_lot_quality`, `get_lot_traceability` (query upstream PO→vendor y downstream sale_order_lines→customers).

**Rutas:** `app/api/routes/inventory.py`:
- `GET /inventory/lots` — listar lotes (filtros product_id, quality_status)
- `GET /inventory/lots/{lot_id}` — detalle de lote
- `PATCH /inventory/lots/{lot_id}/quality-status` — actualizar estado de calidad (roles ti/gerente)
- `GET /inventory/lots/{lot_id}/traceability` — trazabilidad completa (upstream + downstream)

## ACs verificados

- ✅ Tabla `inventory_lots` (lot_number, product_id, manufacture_date, expiry_date, country_of_origin, quality_status, po_line_id)
- ✅ Al registrar GR de producto con tracking=LOT: crear/referenciar `lot_id`
- ✅ Query upstream: dado `lot_id` → PO line → vendor
- ✅ Query downstream: dado `lot_id` → sale_order_lines → customers
- ✅ API: `GET /api/v1/inventory/lots/{lot_id}/traceability`
- ✅ `quality_status` actualizable por roles `ti`, `gerente` (no `comercial`)
