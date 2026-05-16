# Story Artifact: US-ERP-02-05 — FEFO automático + alertas expiración

**Epic:** EP-ERP-02 — Inventario v2  
**Sprint:** S15  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

FEFO automático en picking: al generar un pick para un producto con `rotation_strategy = 'FEFO'`, el sistema
ordena los lotes disponibles por `expiry_date ASC` y retorna la sugerencia óptima. Job Celery diario detecta
lotes próximos a vencer y crea alertas `LOT_EXPIRY_WARNING`.

## Implementación verificada

### Migración
- `20260522_110_fefo_replenishment_abc_kpis.py` — crea tablas:
  - `expiry_alert_thresholds` (threshold por producto, default 30 días)
  - `inventory_alerts` (alertas tipo LOT_EXPIRY_WARNING/STOCKOUT/ROP_BREACH)

### Modelos (`app/db/models/inventory.py`)
- `ExpiryAlertThreshold` — `__tablename__ = "expiry_alert_thresholds"`
- `InventoryAlert` — `__tablename__ = "inventory_alerts"`, campo `alert_type` con CHECK constraint

### API (`app/api/routes/inventory.py`)
- `GET /api/v1/inventory/expiry-alerts` — lotes próximos a vencer agrupados por producto, filtrables por `warehouse_id` y `threshold_days`
- `POST /api/v1/inventory/picking/suggest` — sugerencia FEFO: ordena lotes por `expiry_date ASC`

### Worker (`app/workers/tasks/inventory.py`)
- Task `mt.inventory.check_lot_expiry_warnings` — detecta lotes con `expiry_date < today + threshold_days`, crea `InventoryAlert` de tipo `LOT_EXPIRY_WARNING`
- Registrada en `worker.py` (`include: app.workers.tasks.inventory`)
- Job definition seed en migración: cron `0 6 * * *`

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Si `product.rotation_strategy = 'FEFO'` y `tracking = 'LOT'`: ordenar lotes por `expiry_date ASC` | ✅ endpoint `/picking/suggest` implementado |
| Job Celery diario detecta lotes con `expiry_date < today + threshold_days` | ✅ task `check_lot_expiry_warnings` cron `0 6 * * *` |
| `threshold_days` configurable por producto (default 30 días) | ✅ tabla `expiry_alert_thresholds` |
| API `GET /inventory/expiry-alerts` con lotes agrupados por producto | ✅ endpoint implementado |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260522_110_fefo_replenishment_abc_kpis.py`
- `mt-pricing-backend/app/db/models/inventory.py` (líneas ~710-760)
- `mt-pricing-backend/app/api/routes/inventory.py` (sección US-ERP-02-05)
- `mt-pricing-backend/app/workers/tasks/inventory.py` (líneas ~215-325)
