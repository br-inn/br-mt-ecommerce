# Story Artifact: US-ERP-05-05 — AR Aging Report + promesas de pago

**Epic:** EP-ERP-05 — Billing & Facturación  
**Sprint:** S16  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

AR Aging Report en tiempo real con buckets 0-30, 31-60, 61-90, >90 días. Gestión de promesas
de pago: crear, confirmar, actualizar estado. Job Celery marca promesas vencidas como `broken`.

## Implementación verificada

### Migración
- `20260526_110_billing_invoices_dunning.py` — crea tablas:
  - `payment_promises` (invoice_id, customer_id, promised_date, promised_amount, status: active/fulfilled/broken)
  - `ar_aging_snapshots` para histórico

### API (`app/api/routes/billing.py`)
- `GET /api/v1/billing/ar-aging` — aging report tiempo real, agrupado por cliente y bucket días
- `POST /api/v1/billing/payment-promises` — registrar promesa de pago
- `PATCH /api/v1/billing/payment-promises/{id}` — actualizar estado (fulfilled/broken)

### Worker (`app/workers/tasks/billing.py`)
- Task `mt.billing.mark_broken_promises` — marca como `broken` promesas con `promised_date < today`
- Cron: `0 8 * * *`

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| AR Aging buckets 0-30/31-60/61-90/>90 días | ✅ endpoint `/billing/ar-aging` |
| Promesas de pago CRUD | ✅ POST/PATCH `/billing/payment-promises` |
| Job marca promesas vencidas como `broken` | ✅ task `mark_broken_promises` |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260526_110_billing_invoices_dunning.py`
- `mt-pricing-backend/app/api/routes/billing.py` (get_ar_aging, create_payment_promise)
- `mt-pricing-backend/app/workers/tasks/billing.py` (mark_broken_promises)
