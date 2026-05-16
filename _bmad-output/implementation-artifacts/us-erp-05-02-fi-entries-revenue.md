---
story_key: US-ERP-05-02
title: Asientos FI automaticos + desglose revenue + link accounting
status: review
sprint: S14
story_points: 8
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/billing eed88f1 + feat/finance 3821763).

**Migraciones:**
- `20260526_110_billing_invoices_dunning.py` — FK `invoices.accounting_document_id` → `financial_entries`. Inmutable una vez contabilizado.
- `20260527_112_finance_financial_entries.py` — tabla `financial_entries` (Universal Journal) que recibe los asientos generados.

**Modelos:** `app/db/models/billing.py` + `app/db/models/finance.py` — `Invoice.accounting_document_id` FK, `FinancialEntry` con todos los campos.

**Rutas:** `app/api/routes/billing.py`:
- `POST /billing/invoices/{invoice_id}/post` — cambia status a `posted` y genera automaticamente en `financial_entries`:
  - DR: Accounts Receivable (cliente) — importe total
  - CR: Revenue Account (por linea de producto) — importe neto
  - CR: Tax Payable — importe de impuesto
- `POST /billing/invoices/{invoice_id}/reverse` — Credit Memo: asiento inverso automatico
- `POST /billing/invoices/{invoice_id}/cancel` — Cancellation: revision exacta del asiento original

## ACs verificados

- ✅ Al cambiar `invoice.status` a `posted`: crear automaticamente en `financial_entries` (DR: AR, CR: Revenue, CR: Tax Payable)
- ✅ `invoices.accounting_document_id` → FK a `financial_entries`. Inmutable una vez contabilizado.
- ✅ Credit Memo: asiento inverso automatico
- ✅ Cancellation: revision exacta del asiento original
