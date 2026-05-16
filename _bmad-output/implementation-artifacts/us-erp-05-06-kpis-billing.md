# Story Artifact: US-ERP-05-06 — Dashboard KPIs billing: DSO, CEI + alerta 24h

**Epic:** EP-ERP-05 — Billing & Facturación  
**Sprint:** S16  
**Story Points:** 3  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

KPIs de billing en tiempo real: DSO (Days Sales Outstanding), CEI (Collection Effectiveness Index),
Time to Invoice. Alerta automática si entrega > 24h sin invoice asociada.

## Implementación verificada

### API (`app/api/routes/billing.py`)
- `GET /api/v1/billing/kpis` — DSO, CEI, Time to Invoice calculados desde `invoices` + `outbound_deliveries`
  - DSO = (AR_balance / Revenue_period) × días_en_período
  - CEI = (Beginning_AR + Credit_Sales - Ending_AR) / (Beginning_AR + Credit_Sales) × 100

### Worker (`app/workers/tasks/billing.py`)
- Task `mt.billing.check_unposted_deliveries` — detecta deliveries `shipped_at < now() - 24h` sin invoice
- Crea notificación `billing_alert_24h`
- Cron: `0 */4 * * *` (cada 4 horas)

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| KPI DSO calculado en tiempo real | ✅ `/billing/kpis` |
| KPI CEI | ✅ calculado desde `invoices` |
| Alerta si delivery >24h sin invoice | ✅ task `check_unposted_deliveries` cada 4h |

## Archivos clave

- `mt-pricing-backend/app/api/routes/billing.py` (kpis endpoint)
- `mt-pricing-backend/app/workers/tasks/billing.py` (check_unposted_deliveries)
