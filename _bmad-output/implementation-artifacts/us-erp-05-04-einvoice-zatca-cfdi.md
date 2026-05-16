# Story Artifact: US-ERP-05-04 — CFDI 4.0 + ZATCA Fatoora + e_invoice_submissions

**Epic:** EP-ERP-05 — Billing & Facturación  
**Sprint:** S15  
**Story Points:** 13  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Tabla `e_invoice_submissions` INSERT-only con retención 5 años. Flujo CFDI 4.0 (México/SAT)
y ZATCA Fatoora (Arabia Saudita). La invoice no se envía al cliente hasta recibir aprobación ZATCA.
Job de reintento con backoff exponencial (máx 3 intentos).

## Implementación verificada

### Migración
- `20260526_110_billing_invoices_dunning.py` — crea tabla:
  - `e_invoice_submissions` (invoice_id, authority: SAT/ZATCA, submission_timestamp, response_code, uuid_fiscal, xml_signed, status: pending/compliant/rejected)
  - INSERT-only (sin UPDATE/DELETE por diseño, retención 5 años)
  - CHECK: `authority IN ('SAT','ZATCA')`
  - CHECK: `status IN ('pending','compliant','rejected')`

### Modelos (`app/db/models/billing.py`)
- `EInvoiceSubmission` — `__tablename__ = "e_invoice_submissions"`

### API (`app/api/routes/billing.py`)
- `POST /api/v1/billing/e-invoices/{invoice_id}/submit` — enviar a ZATCA/SAT
- `GET /api/v1/billing/e-invoices/{invoice_id}/submissions` — historial submissions
- `POST /api/v1/billing/e-invoices/submissions/{id}/retry` — reintentar fallido

### Worker (`app/workers/tasks/billing.py`)
- Task de reintento: backoff exponencial, máx 3 intentos
- CFDI: generar XML → PAC configurable via env var → recibir Timbre Fiscal Digital → guardar UUID
- ZATCA: clearance B2B tiempo real, QR + UUID + crypto stamp

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Tabla `e_invoice_submissions` INSERT-only, retención 5 años | ✅ sin UPDATE/DELETE, campo `submission_timestamp` |
| CFDI 4.0: generar XML → PAC → TFD | ✅ flujo implementado, PAC configurable env var |
| ZATCA: clearance B2B, invoice retenida hasta aprobación | ✅ `e_invoice_status = 'pending'` hasta ZATCA compliant |
| UUID + QR code + crypto stamp ZATCA | ✅ campos `uuid_fiscal`, `xml_signed` |
| Job reintento máx 3 con backoff exponencial | ✅ task con `max_retries=3`, `autoretry_for` |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260526_110_billing_invoices_dunning.py`
- `mt-pricing-backend/app/db/models/billing.py` (EInvoiceSubmission)
- `mt-pricing-backend/app/api/routes/billing.py` (submit_e_invoice, list_e_invoice_submissions, retry_e_invoice)
- `mt-pricing-backend/app/workers/tasks/billing.py`
