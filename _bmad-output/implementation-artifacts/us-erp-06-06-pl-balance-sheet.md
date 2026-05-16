# Story Artifact: US-ERP-06-06 — P&L real-time + Balance Sheet reconciliación

**Epic:** EP-ERP-06 — Finanzas  
**Sprint:** S15  
**Story Points:** 8  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

Vista materializada `mv_pl_summary` para P&L en tiempo real por profit_center/período.
Balance Sheet con verificación de ecuación contable (Activos = Pasivos + Patrimonio).
Trial Balance para validación pre-cierre.

## Implementación verificada

### Migración
- `20260527_115_finance_pl_mv.py` — crea:
  - Vista materializada `mv_pl_summary` (account_type, profit_center_id, period_num, fiscal_year, net_balance)
  - Índice UNIQUE para REFRESH CONCURRENTLY

### Modelos (`app/db/models/finance.py`)
- Vista materializada accedida via `text()` en queries

### API (`app/api/routes/finance.py`)
- `GET /api/v1/finance/pl` — P&L desde `mv_pl_summary`, filtrables por profit_center/período
- `GET /api/v1/finance/balance-sheet` — Balance Sheet: Activos, Pasivos, Patrimonio con verificación ecuación
- `GET /api/v1/finance/trial-balance` — Trial Balance por cuenta

### Worker (`app/workers/tasks/finance.py`)
- Task `mt.finance.refresh_pl_mv` — REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pl_summary
- Cron: nightly post-cierre asientos

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| Vista materializada P&L por profit_center/período | ✅ `mv_pl_summary` con índice UNIQUE |
| REFRESH CONCURRENTLY soportado | ✅ migración crea índice único |
| Balance Sheet con verificación ecuación contable | ✅ `/finance/balance-sheet` |
| Trial Balance pre-cierre | ✅ `/finance/trial-balance` |
| Refresh nightly automático | ✅ task `refresh_pl_mv` |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260527_115_finance_pl_mv.py`
- `mt-pricing-backend/app/api/routes/finance.py` (get_pl, get_balance_sheet, get_trial_balance)
- `mt-pricing-backend/app/workers/tasks/finance.py` (refresh_pl_mv)
