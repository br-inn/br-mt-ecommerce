# Story Artifact: US-ERP-02-08 — Dashboard KPIs inventario

**Epic:** EP-ERP-02 — Inventario v2  
**Sprint:** S16  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Endpoint `/inventory/kpis` que retorna KPIs de inventario en tiempo real: Inventory Turnover,
Days on Hand (DOH), Fill Rate y Stockout Rate, calculados desde `inventory_positions` y `stock_movements`.

## Implementación verificada

### Migración
- No requiere migración nueva — calcula desde tablas existentes (`inventory_positions`, `stock_movements`)
- Migración `20260522_110_fefo_replenishment_abc_kpis.py` ya creó las tablas de soporte

### API (`app/api/routes/inventory.py`)
- `GET /api/v1/inventory/kpis` — retorna `InventoryKPIOut`:
  - `inventory_turnover`: COGS_12m / avg_inventory_value
  - `days_on_hand`: 365 / inventory_turnover
  - `fill_rate_pct`: pedidos_entregados_completos / pedidos_totales × 100
  - `stockout_rate_pct`: SKUs con `qty_unrestricted = 0` / total SKUs activos × 100
- Filtrable por `warehouse_id`, `period_days` (default 365)

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| KPI Inventory Turnover calculado en tiempo real | ✅ endpoint `/inventory/kpis` |
| KPI Days on Hand (DOH) | ✅ calculado desde Turnover |
| KPI Fill Rate | ✅ desde deliveries vs orders |
| KPI Stockout Rate | ✅ desde inventory_positions unrestricted=0 |

## Archivos clave

- `mt-pricing-backend/app/api/routes/inventory.py` (sección US-ERP-02-08 `/kpis`)
- `mt-pricing-backend/app/db/models/inventory.py`
