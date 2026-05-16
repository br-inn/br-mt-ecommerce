# Story Artifact: US-ERP-06-08 — FX Revaluation al cierre + Journal SoD controls

**Epic:** EP-ERP-06 — Finanzas  
**Sprint:** S16  
**Story Points:** 5  
**Status:** review  
**Fecha:** 2026-05-16

## Resumen

FX Revaluation al cierre de período: revalúa saldos en moneda extranjera usando el tipo de cambio
del cierre y genera asientos de diferencia de cambio. Journal SoD controls: prevenir que quien
crea un asiento lo apruebe (Segregation of Duties).

## Implementación verificada

### Migración
- `20260527_117_finance_je_controls.py` — crea tabla:
  - `journal_entry_controls` (entry_id, created_by, approved_by, approved_at, control_status)
  - CHECK: `created_by != approved_by` (SoD enforcement)

### Modelos (`app/db/models/finance.py`)
- `JournalEntryControl` — `__tablename__ = "journal_entry_controls"`

### API (`app/api/routes/finance.py`)
- `POST /api/v1/finance/fx-revaluation/{fy}/{period}` — revalúa saldos en moneda extranjera
  - Obtiene cuentas con `currency != AED`
  - Busca tipo de cambio al cierre
  - Calcula diferencia y genera asiento FI
- SoD enforcement en aprobación de asientos

## Criterios de aceptación verificados

| AC | Estado |
|----|--------|
| FX Revaluation al cierre de período | ✅ endpoint `/finance/fx-revaluation/{fy}/{period}` |
| Genera asiento de diferencia de cambio | ✅ crea `financial_entry` tipo `FX_REVAL` |
| SoD: `created_by != approved_by` | ✅ CHECK constraint en `journal_entry_controls` |
| Solo gerente puede ejecutar FX Reval | ✅ `require_role(["gerente"])` |

## Archivos clave

- `mt-pricing-backend/alembic/versions/20260527_117_finance_je_controls.py`
- `mt-pricing-backend/app/db/models/finance.py` (JournalEntryControl)
- `mt-pricing-backend/app/api/routes/finance.py` (run_fx_revaluation)
