---
story_key: US-ERP-06-04
title: AP Aging automatico + Payment Run configurable
status: review
sprint: S14
story_points: 8
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/finance, 3821763).

**Migraciones:**
- `20260527_110_finance_gl_accounts_posting_periods.py` — tabla `vendor_open_items` segun diseno del archivo FIN.
- `20260527_113_finance_ap_payment.py` — tabla `payment_runs` (status: draft→proposed→approved→executed). Tabla `payment_run_items` con descuento por pronto pago.

**Modelos:** `app/db/models/finance.py` — clases `VendorOpenItem`, `PaymentRun`, `PaymentRunItem`.

**Rutas:** `app/api/routes/finance.py`:
- `GET /finance/ap-aging` — AP aging con 5 buckets (current/1-30/31-60/61-90/90+). DPO calculado.
- `POST /finance/payment-runs` — crear payment run (status=draft)
- `POST /finance/payment-runs/{run_id}/approve` — aprobar payment run (proposal revisable antes de ejecutar)
- `POST /finance/payment-runs/{run_id}/execute` — ejecutar payment run, genera archivo bancario CSV/MT940

**Logica descuento:** Si `payment_date <= discount_days_deadline` → aplicar `discount_pct` automaticamente.

## ACs verificados

- ✅ Tabla `vendor_open_items` segun diseno del archivo de investigacion FIN
- ✅ Endpoint `/api/v1/finance/ap-aging` con 5 buckets (current/1-30/31-60/61-90/90+). DPO calculado.
- ✅ Tabla `payment_runs` (status: draft→proposed→approved→executed). Generar archivo bancario CSV/MT940 al ejecutar.
- ✅ Pre-step Proposal obligatorio: mostrar que se va a pagar antes de ejecutar (revisable y editable)
- ✅ Descuento por pronto pago: si `payment_date <= discount_days_deadline` → aplicar `discount_pct` automaticamente
