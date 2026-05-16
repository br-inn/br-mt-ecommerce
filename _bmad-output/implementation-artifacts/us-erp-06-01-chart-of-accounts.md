# US-ERP-06-01 — Chart of Accounts + Posting Periods

**Status:** review
**Sprint:** S13
**Story Points:** 5
**Epic:** EP-ERP-06 — Finanzas
**Fecha implementación:** 2026-05-16

## Resumen

Implementación del Plan de Cuentas (Chart of Accounts) y el control de períodos contables (Posting Periods) para el módulo de finanzas.

## Componentes implementados

### Migración
- `mt-pricing-backend/alembic/versions/20260527_110_finance_gl_accounts_posting_periods.py`
  - Tablas: `gl_accounts`, `posting_periods`
  - Seed: 20 cuentas GL representativas (1000-9999)
  - Seed: 14 períodos contables 2026 (todos open)
  - `down_revision = "20260525_115"` (merge S14 branches)

### Modelos
- `mt-pricing-backend/app/db/models/finance.py` — `GlAccount`, `PostingPeriod`
  - `GlAccount` soporta jerarquía padre/hijo (self-referential)
  - `PostingPeriod` control open/closed/locked

### Endpoints (prefijo `/api/v1/finance`)
- `GET /finance/accounts` — listado con filtros account_type, blocked
- `POST /finance/accounts` — crear cuenta (rol ti/gerente)
- `PATCH /finance/accounts/{id}` — actualizar cuenta
- `GET /finance/posting-periods` — listar períodos
- `POST /finance/posting-periods` — crear período
- `POST /finance/posting-periods/{id}/close` — cerrar período

### Corrección
- Router `finance` tenía `prefix="/api/v1/finance"` incorrecto (double prefix)
- Corregido a `prefix="/finance"` en `app/api/routes/finance.py`

## Verificación

- `GET /api/v1/finance/accounts` → 401 (registrado correctamente)
- `GET /api/v1/finance/posting-periods` → 401 (registrado correctamente)
