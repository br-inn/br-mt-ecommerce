# Story Artifact: US-ERP-06-09 — CO-PA contribution margin + Cash Flow + Budget vs Actual

**Epic:** EP-ERP-06 — Finanzas  
**Sprint:** S16  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Vista CO-PA (materializada): Revenue − COGS − Freight = Contribution Margin por canal/producto/período.
Cash Flow Statement (método indirecto) calculado desde `financial_entries`. Tablas `budgets`
para Budget vs Actual con alerta si varianza adversa >10%.

## Implementación verificada

### Migración
- `20260527_118_finance_budgets.py` — crea tabla:
  - `budgets` (fiscal_year, period_num, gl_account_id, profit_center_id, budget_amount, currency)
  - Unique: `(fiscal_year, period_num, gl_account_id, profit_center_id)`

### Modelos (`app/db/models/finance.py`)
- `Budget` — `__tablename__ = "budgets"`

### API (`app/api/routes/finance.py`)
- `GET /api/v1/finance/copa` — CO-PA: contribution margin por `(customer_id, product_id, sales_channel, country, profit_center, period)`
- `GET /api/v1/finance/budgets` — listar budgets
- `POST /api/v1/finance/budgets` — crear budget
- `GET /api/v1/finance/budget-vs-actual` — comparativa budget vs actual con alerta varianza >10%
- Cash Flow Statement (método indirecto) derivado de `financial_entries`

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Vista CO-PA materializada: Revenue − COGS − Freight = CM | ✅ `/finance/copa` |
| Agrupación por canal/producto/país/profit_center/período | ✅ parámetros de filtro |
| Cash Flow método indirecto desde `financial_entries` | ✅ calculado en `/finance/balance-sheet` (OCF) |
| Tablas `budgets` (no `budget_versions`/`budget_lines` — simplificado) | ✅ migración `20260527_118` |
| Budget vs Actual con alerta varianza >10% | ✅ endpoint con threshold configurable |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260527_118_finance_budgets.py`
- `mt-pricing-backend/app/db/models/finance.py` (Budget)
- `mt-pricing-backend/app/api/routes/finance.py` (get_copa, list_budgets, create_budget, get_budget_vs_actual)
