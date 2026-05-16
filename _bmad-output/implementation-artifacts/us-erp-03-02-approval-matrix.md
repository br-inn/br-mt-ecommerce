---
story_key: US-ERP-03-02
title: Approval matrix configurable + escalacion automatica PR/PO
status: review
sprint: S14
story_points: 8
---

## Implementacion

La implementacion ya existia completamente en el codebase, comprometida en commits previos (feat/erp-03-p2p, a36abf9 / merge 0727e56).

**Migraciones:**
- `20260516_106_approval_rules.py` — tabla `approval_rules` con campos document_type, min_amount, max_amount, category_id, approver_role, approver_user_id, timeout_hours.

**Modelo:** `app/db/models/procurement.py` — clase `ApprovalRule`. Clase `ApprovalDecision` (inmutable INSERT-only).

**Rutas:** `app/api/routes/procurement.py`:
- `GET /procurement/approval-rules` — listar reglas configuradas
- `POST /procurement/approval-rules` — crear regla
- `PATCH /procurement/approval-rules/{id}` — actualizar regla
- `PATCH /procurement/requisitions/{id}/submit` — evalua reglas en orden min_amount ASC al someter PR

**Worker Celery:** task de escalacion que detecta aprobaciones con `created_at + timeout_hours < now` y escala al siguiente nivel. Notificacion in-app al solicitante.

## ACs verificados

- ✅ Tabla `approval_rules` (document_type, min_amount, max_amount, category_id, approver_role, approver_user_id, timeout_hours)
- ✅ Al someter PR: evaluar reglas en orden de `min_amount ASC`. Asignar aprobador.
- ✅ Job Celery Beat (cada hora): detectar aprobaciones con `created_at + timeout_hours < now`. Escalar al siguiente nivel.
- ✅ Al aprobar/rechazar: notificacion in-app al solicitante con razon
- ✅ Configuracion minima: < $1,000 → auto-aprobado; $1k–$10k → manager; > $10k → CFO
