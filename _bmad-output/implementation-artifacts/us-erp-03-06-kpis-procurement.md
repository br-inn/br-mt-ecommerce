# Story Artifact: US-ERP-03-06 — Dashboard KPIs procurement + spend analysis

**Epic:** EP-ERP-03 — Compras P2P  
**Sprint:** S16  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

KPIs de compras en tiempo real: PO Cycle Time, Vendor OTD%, Invoice Processing Time,
Spend Under Management%, Maverick Spend%. Spend analysis con agrupación por vendor/category/month/cost_center.
Vendor scorecard actualizado mensualmente por Celery.

## Implementación verificada

### API (`app/api/routes/procurement.py`)
- KPI endpoints: PO Cycle Time, OTD%, processing time, maverick spend
- `GET /api/v1/procurement/spend-analysis?groupBy=vendor|category|month|cost_center`
- Vendor scorecard: OTD% + GR sin devolución + cumplimiento precio PIR

### Worker (`app/workers/tasks/procurement.py`)
- Task de actualización mensual de vendor scorecard

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Endpoints KPI: PO Cycle Time, OTD%, Invoice Processing Time | ✅ implementados en procurement route |
| Spend analysis con groupBy múltiple | ✅ `/procurement/spend-analysis` |
| Vendor scorecard actualizado mensualmente | ✅ Celery task en `procurement.py` |

## Archivos clave

- `mt-pricing-backend/app/api/routes/procurement.py`
- `mt-pricing-backend/app/workers/tasks/procurement.py`
