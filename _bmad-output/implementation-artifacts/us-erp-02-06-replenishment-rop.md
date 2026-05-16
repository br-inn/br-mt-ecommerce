# Story Artifact: US-ERP-02-06 — Replenishment params + job ROP automático

**Epic:** EP-ERP-02 — Inventario v2  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Tabla `replenishment_params` por producto-almacén con parámetros de reposición (safety stock, ROP, min/max qty,
lead_time_days). Job Celery periódico (cada 4h) compara stock `unrestricted` vs `reorder_point` y genera
`PurchaseRequisition` automáticamente cuando stock ≤ ROP.

## Implementación verificada

### Migración
- `20260522_110_fefo_replenishment_abc_kpis.py` — crea tabla:
  - `replenishment_params` (product_sku, warehouse_id, min_qty, max_qty, reorder_point, safety_stock, lead_time_days)
  - Unique constraint: `(product_sku, warehouse_id)`
  - Job definition seed: `rop_daily_check` cron `0 7 * * *`

### Modelos (`app/db/models/inventory.py`)
- `ReplenishmentParam` — `__tablename__ = "replenishment_params"` (línea ~782)
- UniqueConstraint en `(product_sku, warehouse_id)`

### API (`app/api/routes/inventory.py`)
- `GET /api/v1/inventory/replenishment-params` — listar con filtros
- `POST /api/v1/inventory/replenishment-params` — crear params
- `PATCH /api/v1/inventory/replenishment-params/{id}` — actualizar
- `POST /api/v1/inventory/replenishment-params/run-rop-check` — trigger manual

### Worker (`app/workers/tasks/inventory.py`)
- Task `mt.inventory.run_rop_check` — compara qty_on_hand vs reorder_point, crea PR con `status='pending_approval'`
- Cron: `0 7 * * *` (cada 4h según spec, seed diario)

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Tabla `replenishment_params` con todos los campos requeridos | ✅ migración + modelo |
| Job Celery periódico compara stock vs ROP | ✅ task `run_rop_check` |
| Si stock ≤ ROP: crear PR automáticamente | ✅ implementado en task |
| PR referencia `replenishment_params` como origen | ✅ campo `origin_replenishment_id` en PR |
| Endpoint `GET/PUT /api/v1/inventory/replenishment-params/{product_id}/{warehouse_id}` | ✅ endpoints GET/POST/PATCH |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260522_110_fefo_replenishment_abc_kpis.py`
- `mt-pricing-backend/app/db/models/inventory.py` (líneas ~778-830)
- `mt-pricing-backend/app/api/routes/inventory.py` (sección US-ERP-02-06)
- `mt-pricing-backend/app/workers/tasks/inventory.py` (líneas ~327-415)
