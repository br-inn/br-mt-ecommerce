---
story_key: US-ERP-06-03
title: Universal Journal — financial_entries table
status: review
sprint: S14
story_points: 8
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/finance, 3821763).

**Migraciones:**
- `20260527_112_finance_financial_entries.py` — tabla `financial_entries` completa con todos los campos requeridos: entry_number, journal_date, posting_period, entry_type, source_module, source_document, gl_account_id, cost_center_id, profit_center_id, debit_amount, credit_amount, currency_code, amount_local, fx_rate, preparer_id, reviewer_id, approver_id. Indices en posting_period, gl_account_id, journal_date. Constraint de balance validado.

**Modelo:** `app/db/models/finance.py` — clase `FinancialEntry` con todos los campos y relaciones.

**Rutas:** `app/api/routes/finance.py`:
- `POST /finance/entries` — crear asiento (con validacion debit = credit por source_document)
- `GET /finance/entries` — listar asientos (filtros por periodo, cuenta, modulo origen)
- `POST /finance/entries/{entry_id}/reverse` — reversion de asiento
- `POST /finance/entries/{entry_id}/review` — revision de asiento por revisor
- `POST /finance/entries/{entry_id}/approve` — aprobacion de asiento

Los modulos billing, compras e inventario inscriben sus asientos aqui via `source_module`.

## ACs verificados

- ✅ Tabla `financial_entries` segun diseno completo con todos los campos clave
- ✅ Campos: entry_number, journal_date, posting_period, entry_type, source_module, source_document, gl_account_id, cost_center_id, profit_center_id, debit_amount, credit_amount, currency_code, amount_local, fx_rate, preparer_id, reviewer_id, approver_id
- ✅ Trigger de balance: validar que la suma de `debit_amount = credit_amount` por `source_document`
- ✅ Indices: `posting_period`, `gl_account_id`, `journal_date`
- ✅ Los modulos billing, compras e inventario inscriben sus asientos aqui via `source_module`
