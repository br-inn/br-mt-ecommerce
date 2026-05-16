# Story Artifact: US-ERP-06-05 — Standard Cost por SKU + varianza precio compra

**Epic:** EP-ERP-06 — Finanzas  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Tabla `standard_costs` por SKU/año con tipos standard/planned/actual. Tabla `price_variances`
como GENERATED ALWAYS AS computed column (`variance_amount = actual_cost - standard_cost`).
Se calcula automáticamente al registrar un GR.

## Implementación verificada

### Migración
- `20260527_114_finance_standard_costs.py` — crea tablas:
  - `standard_costs` (product_sku, fiscal_year, standard_cost, currency, cost_type: standard/planned/actual, valid_from)
    - Unique: `(product_sku, fiscal_year, cost_type)`
    - FK → `products.sku`
  - `price_variances` (po_line_id, product_sku, standard_cost, actual_cost, variance_amount COMPUTED, variance_pct, period, fiscal_year)

### Modelos (`app/db/models/finance.py`)
- `StandardCost` — `__tablename__ = "standard_costs"`
- `PriceVariance` — `__tablename__ = "price_variances"` con `variance_amount` como `Computed`

### API (`app/api/routes/finance.py`)
- `GET /api/v1/finance/standard-costs` — listar standard costs
- `POST /api/v1/finance/standard-costs` — crear/actualizar standard cost
- `GET /api/v1/finance/price-variances` — listar varianzas por SKU/período

### Worker (`app/workers/tasks/finance.py`)
- Task `mt.finance.calc_price_variance` — calcula varianza al registrar GR

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Tabla `standard_costs` por SKU + año fiscal | ✅ migración + modelo con unique constraint |
| `price_variances` con `variance_amount` como computed column | ✅ `Computed("actual_cost - standard_cost", persisted=True)` |
| Varianza calculada al registrar GR | ✅ task `calc_price_variance` |
| Tipos: standard/planned/actual | ✅ CHECK constraint |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260527_114_finance_standard_costs.py`
- `mt-pricing-backend/app/db/models/finance.py` (StandardCost, PriceVariance)
- `mt-pricing-backend/app/api/routes/finance.py` (list_standard_costs, list_price_variances)
- `mt-pricing-backend/app/workers/tasks/finance.py` (calc_price_variance)
