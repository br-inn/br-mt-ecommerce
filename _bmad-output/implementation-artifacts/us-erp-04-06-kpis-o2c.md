# Story Artifact: US-ERP-04-06 — Dashboard O2C KPIs + Backorder report

**Epic:** EP-ERP-04 — Ventas O2C  
**Sprint:** S16  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

KPIs del ciclo Order-to-Cash en tiempo real: Order Fulfillment Rate, Perfect Order Rate,
Delivery Cycle Time, Backorder Rate. Reporte de backorders con desglose por cliente/producto/almacén.

## Implementación verificada

### API (`app/api/routes/sales.py`)
- `GET /api/v1/sales/kpis` — KPIs O2C calculados desde `sales_orders`, `outbound_deliveries`, `invoices`
- `GET /api/v1/sales/backorders` — listado de líneas de SO con `status = 'backorder'`

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Endpoint KPIs O2C (Fulfillment Rate, Perfect Order, Cycle Time, Backorder Rate) | ✅ `/sales/kpis` |
| Backorder report con desglose | ✅ `/sales/backorders` |

## Archivos clave

- `mt-pricing-backend/app/api/routes/sales.py` (get_kpis, get_backorders)
