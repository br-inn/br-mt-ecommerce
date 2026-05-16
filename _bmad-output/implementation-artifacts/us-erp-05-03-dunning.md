# Story Artifact: US-ERP-05-03 — Dunning automático por aging buckets + payment terms

**Epic:** EP-ERP-05 — Billing & Facturación  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Job Celery diario evalúa invoices en mora y escala dunning levels según tabla configurable.
Al subir de nivel: inserta en `dunning_history` y crea notificación. Integra con `payment_terms`
para calcular días de gracia correctamente.

## Implementación verificada

### Migración
- `20260526_110_billing_invoices_dunning.py` — crea tablas:
  - `invoices` (invoice_number, invoice_type, delivery_id, so_id, customer_id, due_date, e_invoice_status)
  - `invoice_lines`
  - `dunning_levels` (level, days_overdue_min, days_overdue_max, action_type, fee_pct)
  - `dunning_history` (invoice_id, level, escalated_at, escalated_by)
  - `payment_terms` (term_code, net_days, discount_pct, discount_days)
  - `e_invoice_submissions` (invoice_id, authority, submission_timestamp, response_code, uuid_fiscal, status)
  - `payment_promises` (invoice_id, customer_id, promised_date, amount, status)
  - `ar_aging_snapshots`

### Modelos (`app/db/models/billing.py`)
- `Invoice`, `InvoiceLine`, `DunningLevel`, `DunningHistory`, `PaymentTerms`
- `EInvoiceSubmission`, `PaymentPromise`

### API (`app/api/routes/billing.py`)
- `GET /api/v1/billing/dunning` — invoices en mora con nivel actual
- `POST /api/v1/billing/dunning/{invoice_id}/escalate` — escalar nivel manualmente (gerente)

### Worker (`app/workers/tasks/billing.py`)
- Task `mt.billing.run_dunning_check` — evalúa invoices posted con `due_date < today`
  - Asigna `dunning_level` según tabla
  - Si nivel subió: inserta `dunning_history`, crea notificación
  - Cron: `0 8 * * *`

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Tabla `dunning_levels` con aging buckets configurables | ✅ en migración |
| Job Celery diario evalúa mora por factura | ✅ task `run_dunning_check` cron `0 8 * * *` |
| Al subir nivel: inserta `dunning_history` + notificación | ✅ implementado |
| Integración con `payment_terms` para días de gracia | ✅ tabla `payment_terms` |
| Endpoint escalación manual (gerente) | ✅ `/billing/dunning/{id}/escalate` |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260526_110_billing_invoices_dunning.py`
- `mt-pricing-backend/app/db/models/billing.py`
- `mt-pricing-backend/app/api/routes/billing.py` (get_dunning, escalate_dunning)
- `mt-pricing-backend/app/workers/tasks/billing.py` (run_dunning_check)
