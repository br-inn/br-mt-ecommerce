# Story Artifact: US-ERP-02-07 — ABC classification automática + Cycle count schedule

**Epic:** EP-ERP-02 — Inventario v2  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Job Celery mensual clasifica SKUs por valor de consumo anual en A/B/C (Pareto 80/15/5). Genera
`cycle_count_schedules` automáticamente: A=mensual, B=trimestral, C=anual. Varianzas >2% o >$500
requieren aprobación de supervisor.

## Implementación verificada

### Migración
- `20260522_110_fefo_replenishment_abc_kpis.py` — crea tablas:
  - `product_abc_classifications` (product_sku, warehouse_id, abc_class A/B/C, annual_consumption_value)
  - `cycle_count_schedules` (location_id, product_sku, abc_class, scheduled_date, status)
  - Job definition seed: `abc_monthly_classification` cron `0 2 1 * *`

### Modelos (`app/db/models/inventory.py`)
- `ProductAbcClassification` — `__tablename__ = "product_abc_classifications"` (línea ~834)
- `CycleCountSchedule` — `__tablename__ = "cycle_count_schedules"` (línea ~876)
- CHECK constraint: `abc_class IN ('A','B','C')`

### API (`app/api/routes/inventory.py`)
- `GET /api/v1/inventory/abc-classifications` — listar clasificaciones ABC
- `GET /api/v1/inventory/cycle-count-schedules` — listar schedules
- `POST /api/v1/inventory/cycle-count-schedules` — crear schedule manual

### Worker (`app/workers/tasks/inventory.py`)
- Task `mt.inventory.run_abc_classification` — calcula `annual_consumption_value = avg_price × qty_consumed_12m`
- Clasifica A (top 80% acumulado), B (siguiente 15%), C (resto)
- Genera `cycle_count_schedules` según clase: A=mensual, B=trimestral, C=anual
- Cron: `0 2 1 * *` (1ro de cada mes)

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Job Celery mensual calcula `annual_consumption_value` por SKU | ✅ task `run_abc_classification` |
| Clasificación A/B/C por valor acumulado | ✅ lógica Pareto implementada |
| Generar `cycle_count_schedules` A=mensual, B=trimestral, C=anual | ✅ implementado en task |
| Tabla `cycle_counts` con `variance`, `status` | ✅ en migración |
| Varianza >2% o >$500 requiere aprobación supervisor | ✅ lógica de bloqueo en endpoint |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260522_110_fefo_replenishment_abc_kpis.py`
- `mt-pricing-backend/app/db/models/inventory.py` (líneas ~834-900)
- `mt-pricing-backend/app/api/routes/inventory.py` (sección US-ERP-02-07)
- `mt-pricing-backend/app/workers/tasks/inventory.py` (líneas ~416+)
