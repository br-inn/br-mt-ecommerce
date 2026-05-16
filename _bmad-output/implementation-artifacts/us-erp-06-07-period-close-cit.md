# Story Artifact: US-ERP-06-07 — Period Close Checklist + UAE CIT provisioning

**Epic:** EP-ERP-06 — Finanzas  
**Sprint:** S15  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Checklist automatizado de cierre de período con ítems configurables en JSONB. UAE Corporate
Income Tax (CIT) provisioning: cálculo automático de provisión 9% sobre Net Income con asiento
automático al GL de CIT Payable.

## Implementación verificada

### Migración
- `20260527_116_finance_period_close_tax.py` — crea tablas:
  - `period_close_checklists` (fiscal_year, period_num, checklist_items JSONB, status: open/in_progress/closed)
    - Unique: `(fiscal_year, period_num)`
    - CHECK: `status IN ('open','in_progress','closed')`
  - `tax_provisions` (fiscal_year, provision_type, taxable_income, tax_rate, provision_amount, currency)

### Modelos (`app/db/models/finance.py`)
- `PeriodCloseChecklist` — `__tablename__ = "period_close_checklists"` (línea ~)
- `TaxProvision` — `__tablename__ = "tax_provisions"`

### API (`app/api/routes/finance.py`)
- `POST /api/v1/finance/period-close/{fy}/{period}` — iniciar checklist
- `PATCH /api/v1/finance/period-close/{id}/item` — marcar ítem completado
- `POST /api/v1/finance/period-close/{id}/close` — cerrar período (requiere todos los ítems OK)
- `POST /api/v1/finance/cit-provision/{fiscal_year}` — calcular provisión CIT UAE (9% sobre Net Income)

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Checklist de cierre con ítems configurables en JSONB | ✅ `period_close_checklists.checklist_items` JSONB |
| Unique constraint por (fiscal_year, period_num) | ✅ UniqueConstraint |
| UAE CIT provisioning (9% sobre Net Income) | ✅ endpoint `cit-provision` + tabla `tax_provisions` |
| Asiento automático al GL CIT Payable | ✅ crea `financial_entry` al calcular |
| No cerrar período con ítems pendientes | ✅ validación en `close` endpoint |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260527_116_finance_period_close_tax.py`
- `mt-pricing-backend/app/db/models/finance.py` (PeriodCloseChecklist, TaxProvision)
- `mt-pricing-backend/app/api/routes/finance.py` (start_period_close, update_checklist_item, close_period_checklist, calculate_cit_provision)
