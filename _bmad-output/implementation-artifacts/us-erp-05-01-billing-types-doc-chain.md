---
story_key: US-ERP-05-01
title: Billing types + doc chain + precio copiado del SO
status: review
sprint: S14
story_points: 5
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/billing, eed88f1 + merge a9a64c0).

**Migraciones:**
- `20260526_110_billing_invoices_dunning.py` — campo `billing_type` en `invoices` (STANDARD/PROFORMA/CREDIT_MEMO/DEBIT_MEMO/CANCELLATION). `invoices.delivery_id` y `invoices.so_id` NOT NULL. `credit_memos.original_invoice_id` NOT NULL.

**Modelos:** `app/db/models/billing.py` — clase `Invoice` con `billing_type` enum y FKs delivery_id + so_id.

**Rutas:** `app/api/routes/billing.py`:
- `POST /billing/invoices` — crear invoice (billing_type requerido, precio copiado desde SO lines sin re-ejecutar pricing engine)
- `POST /billing/invoices/from-delivery/{delivery_id}` — crear invoice directamente desde delivery (copia unit_price, discount, tax_amount del SO)
- `GET /billing/invoices/{invoice_id}/chain` — cadena documental SO→Delivery→Invoice

**Logica PROFORMA:** no genera asiento contable (informativo para aduanas). **CANCELLATION:** revierte exactamente el asiento del documento original.

## ACs verificados

- ✅ Campo `billing_type` en `invoices`: `STANDARD` / `PROFORMA` / `CREDIT_MEMO` / `DEBIT_MEMO` / `CANCELLATION`
- ✅ `PROFORMA`: no genera asiento contable (informativo para aduanas)
- ✅ `CANCELLATION`: revierte exactamente el asiento del documento original
- ✅ `invoices.delivery_id` + `invoices.so_id` obligatorios (NOT NULL)
- ✅ Al crear invoice: copiar `unit_price`, `discount`, `tax_amount` desde SO lines. El pricing engine NO se re-ejecuta.
- ✅ `credit_memos.original_invoice_id` NOT NULL
