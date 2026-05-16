# US-ERP-03-01 — Purchase Requisition entity + lifecycle + log inmutable

**Status:** review
**Sprint:** S13
**Story Points:** 8
**Epic:** EP-ERP-03 — Compras P2P
**Fecha implementación:** 2026-05-16

## Resumen

Implementación de la entidad Purchase Requisition con lifecycle completo y log de aprobaciones inmutable (append-only).

## Componentes implementados

### Migración
- `mt-pricing-backend/alembic/versions/20260516_105_purchase_requisitions.py`
  - Tablas: `purchase_requisitions`, `approval_decisions`
  - `down_revision` corregido a `"20260513_104"` (bifurcación paralela desde base ERP)
  - Lifecycle: draft → pending_approval → approved/rejected/cancelled/converted_to_po

### Modelos
- `mt-pricing-backend/app/db/models/procurement.py` — `PurchaseRequisition`, `ApprovalDecision`

### Repositorio
- `mt-pricing-backend/app/repositories/procurement.py` — `ProcurementRepository`
  - `create_pr()`, `list_prs()`, `get_pr()`, transiciones de estado
  - `ApprovalDecision` es solo INSERT (no UPDATE/DELETE por diseño)

### Endpoints (prefijo `/api/v1/procurement`)
- `POST /procurement/requisitions` — crear PR en draft
- `GET /procurement/requisitions` — listar con filtros status, requester
- `GET /procurement/requisitions/{id}` — detalle
- `PATCH /procurement/requisitions/{id}/submit` — draft → pending_approval
- `PATCH /procurement/requisitions/{id}/approve` — pending → approved (roles: gerente/ti)
- `PATCH /procurement/requisitions/{id}/reject` — pending → rejected (con justificación)
- `PATCH /procurement/requisitions/{id}/cancel` — cancelar

## Restricciones de seguridad

- Usuario solo ve sus propias PRs (RLS en repositorio)
- Aprobadores requieren rol gerente o ti
- `approval_decisions` es tabla append-only (sin UPDATE/DELETE)

## Verificación

- DB al HEAD — tablas `purchase_requisitions` y `approval_decisions` existentes
- Endpoints registrados en `/api/v1/procurement`
