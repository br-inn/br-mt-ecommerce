# US-ERP-06-02 — Cost Centers + Profit Centers básicos

**Status:** review
**Sprint:** S13
**Story Points:** 5
**Epic:** EP-ERP-06 — Finanzas
**Fecha implementación:** 2026-05-16

## Resumen

Implementación de Cost Centers y Profit Centers para imputación de costos y análisis de rentabilidad por unidad de negocio.

## Componentes implementados

### Migración
- `mt-pricing-backend/alembic/versions/20260527_111_finance_cost_profit_centers.py`
  - Tablas: `cost_centers`, `profit_centers`
  - Seed: 6 cost centers (CC-ADMIN, CC-VENTAS, CC-COMPRAS, CC-TI, CC-LOGISTICA, CC-OPERACIONES)
  - Seed: 3 profit centers (PC-UAE, PC-KSA, PC-EGY)
  - `down_revision = "20260527_110"` (chart of accounts) ✓

### Modelos
- `mt-pricing-backend/app/db/models/finance.py` — `CostCenter`, `ProfitCenter`

### Endpoints (prefijo `/api/v1/finance`)
- `GET /finance/cost-centers` — listar cost centers
- `POST /finance/cost-centers` — crear cost center
- `GET /finance/profit-centers` — listar profit centers
- `POST /finance/profit-centers` — crear profit center

## Verificación

- `GET /api/v1/finance/cost-centers` → 401 (registrado correctamente)
- `GET /api/v1/finance/profit-centers` → 401 (registrado correctamente)
- Tablas `cost_centers` y `profit_centers` existentes en DB
