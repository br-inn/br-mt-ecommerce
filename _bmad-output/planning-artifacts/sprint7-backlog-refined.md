---
title: "Sprint 7 — Backlog refinado"
status: "draft"
version: "1.0"
created: "2026-05-12"
project_name: "mt-pricing-mdm-phase1"
sprint: 7
capacity_target_sp: 37
sprint_goal: "Cerrar EP-1B-02 workflow aprobación por excepción completo (state machine + exception rules + auto_approved + bulk-approve + digest + audit trail), entregar UI human queue cohesiva con digest (US-RND-01-10), e iniciar hardening pre-cutover (EP-1B-05). Externos bloqueantes (Pantalla 12 firma, Doppler creds) explícitos para gestión sponsor."
related:
  - "sprint6-backlog-refined.md"
  - "../implementation-artifacts/sprint6-execution-report.md"
  - "epics-and-stories-mt-pricing-mdm-phase1.md"
  - "architecture-mt-pricing-mdm-phase1.md"
  - "risk-register-consolidado.md"
---

# Sprint 7 — Backlog refinado — MT Middle East Fase 1b cierre aprobación + hardening

## 1. Resumen ejecutivo

### Contexto pre-S7

Sprint 6 cerró 13 SP core (escalation job + pdfplumber tablas + DR runbook). **Post-S6, fuera del plan formal**, se ejecutó un volumen significativo de trabajo no comprometido:

| Trabajo | Commits principales | SP estimados |
|---------|---------------------|-------------|
| Taxonomy registry polimórfico data-driven + frontend completo | `d006a0e`..`13fade0` (14 commits) | ~25 SP |
| PIM: EAV typed attributes + polymorphic catalog overhaul | `28632a2` | ~10 SP |
| PIM frontend: dynamic specs form + spare parts + documents UI | `0283299` | ~8 SP |
| Comparator Fase 1 hooks (ADR-012) | `05d00d7` | ~3 SP |

**Pre-S7 audit (Apéndice A):** Este trabajo no cierra ninguna story pendiente de EP-1B-02 ni EP-1B-05. Es infraestructura PIM/catálogo valiosa pero no acerca el gate de cutover Fase 1b. Sprint 7 debe reenfocarse en el camino crítico: **workflow de aprobación + hardening operacional**.

### Capacidad asumida

| Concepto | Valor |
|----------|-------|
| Modo | Multi-agente (5 agentes) |
| Velocity asumida | 35–45 SP (conservador post-S6) |
| Sprint length | 2 semanas (10 días lab.) |
| **Capacidad target S7** | **37 SP comprometidos + 21 SP stretch** |

---

## 2. Capacidad asumida

- **Comprometido (P0+P1):** 37 SP
- **Stretch desbloqueable (P2):** 21 SP adicionales si capacidad permite o externos firman
- **Carry-over S6:** US-1B-02-07 (5 SP) + US-RND-01-10 (5 SP) = 10 SP (ya en P0/P1)

---

## 3. Tabla maestra de stories

| ID | Título | Épica | SP | Prioridad | Dominio | Agente sugerido | Depende de | Estado pre-S7 |
|----|--------|-------|----|-----------| --------|------------------|------------|----------------|
| US-1B-02-01 | State machine `prices.status` enforcement (servicio + DB) | EP-1B-02 | 5 | P0 | backend (core) | A | — | ⬜ backlog |
| US-1B-02-02 | Tabla `exception_rules` con versionado + UI configuración Gerente | EP-1B-02 | 8 | P0 | backend + frontend | A+D | US-1B-02-01 | ⬜ backlog |
| US-1B-02-03 | Lógica `auto_approved` vs `pending_review` con triggers (delta margen, FX swing, margen mínimo) | EP-1B-02 | 5 | P0 | backend (service) | A | US-1B-02-01 | ⬜ backlog |
| US-1B-02-05 | Endpoint `POST /prices/bulk-approve` con comentario obligatorio | EP-1B-02 | 3 | P0 | backend (API) | A | US-1B-02-04 (S4 ✅) | ⬜ backlog |
| US-1B-02-07 | Digest diario 18:00 UAE in-app + email opcional | EP-1B-02 | 5 | P1 | backend (workers) | B | US-1B-02-08 (S6 ✅) | ▶ carry-over S6 |
| US-1B-02-09 | Audit trail extendido a `prices`, `exception_rules`, transición de canal | EP-1B-02 | 3 | P1 | backend (audit) | A | US-1B-02-01 | ⬜ backlog |
| US-RND-01-10 | UI human queue validación humana asistida MVP + cohesivo con digest | EP-RND-01 | 5 | P1 | frontend (R&D) | D | US-1B-02-08 (S6 ✅), calibrator S5 ✅ | ▶ carry-over S6 |
| US-1B-05-01 | Reporte diario diff app vs Excel demo durante parallel run | EP-1B-05 | 3 | P1 | backend (scripts) | B | pricing engine S4 ✅ | ⬜ backlog |
| US-1B-02-06 | Cola Gerente tabla + bulk-select + sidebar detalle | EP-1B-02 | 8 | P3 | frontend | D | Pantalla 12 firmada | ❌ blocked external |
| US-1B-05-07 | Dashboards observabilidad (lag aprobación, % auto, top razones, escaladas) | EP-1B-05 | 5 | P2 | DevOps/frontend | E | Sentry S5 ✅ | ⬜ stretch |
| US-1B-05-06 | Performance hardening (índices, query plans, p95 endpoints CRUD) | EP-1B-05 | 5 | P2 | backend (DevOps) | E | — | ⬜ stretch |
| US-1B-05-02 | Manual operativo `docs/handbook-es.md` validado por Champion | EP-1B-05 | 5 | P2 | docs | E | — | ⬜ stretch |
| OCR-S7 | `Dockerfile.worker-ocr` con tesseract baked (>2GB container fix) | EP-1A-06 | 3 | P2 | DevOps | E | US-1A-06-04-V2-S6 ✅ | ⬜ stretch |
| DR-DRILLS | Tabla `dr_drills` + mig 030 + endpoint admin reporting | EP-1B-05 | 3 | P2 | backend (DevOps) | B | US-1B-05-04-DOC S6 ✅ | ⬜ stretch |
| **TOTAL CORE (P0+P1)** | | | **37 SP** | | | | | |
| **TOTAL STRETCH** | | | **+21 SP** | | | | | |
| **TOTAL BLOQUEADO EXTERNO** | | | **+8 SP** | | | | | |

> **Comprometidos S7 (37 SP)**: US-1B-02-01 (5) + US-1B-02-02 (8) + US-1B-02-03 (5) + US-1B-02-05 (3) + US-1B-02-07 (5) + US-1B-02-09 (3) + US-RND-01-10 (5) + US-1B-05-01 (3) = **37 SP**.

---

## 4. Fichas detalladas

### US-1B-02-01 — State machine `prices.status` enforcement (servicio + DB)

**Épica**: EP-1B-02
**Como** TI Integración
**Quiero** que `prices.status` solo pueda transicionar por caminos válidos (draft → pending_review → approved/rejected, approved → published, etc.)
**Para** garantizar que ningún precio inválido llegue a canal.

**Criterios de aceptación**
- `Enum PriceStatus` con valores: `draft`, `pending_review`, `auto_approved`, `approved`, `rejected`, `published`, `archived`
- Service `PriceStateMachine.transition(price, target_status, actor_user_id)` valida camino + lanza `InvalidTransitionError` si no permitido
- Trigger DB `ck_price_status_transition` como segunda línea de defensa
- Unit tests: 8 escenarios de transición (válidas + inválidas)

**Archivos esperados**
- `mt-pricing-backend/app/services/pricing/state_machine.py` — PriceStateMachine
- `mt-pricing-backend/app/db/models/pricing.py` — Enum + constraints update
- `mt-pricing-backend/alembic/versions/20260512_030_price_status_enum.py`
- `mt-pricing-backend/tests/unit/services/pricing/test_state_machine.py`

**SP**: 5

---

### US-1B-02-02 — Tabla `exception_rules` con versionado + UI configuración Gerente

**Épica**: EP-1B-02
**Como** Gerente
**Quiero** configurar reglas de excepción versionadas (delta margen, FX swing, margen mínimo) que determinen cuándo un precio requiere aprobación manual
**Para** calibrar el workflow sin intervención de TI.

**Criterios de aceptación**
- Tabla `exception_rules` con campos: `id, rule_type ENUM(margin_delta, fx_swing, min_margin), threshold NUMERIC, channel_code, active, version, created_by, created_at`
- Cierre automático de versión anterior al activar nueva (`effective_to = now()`)
- API: `GET/POST /exception-rules`, `PATCH /exception-rules/{id}/activate`, `GET /exception-rules/history`
- RLS: solo `gerente` puede crear/activar reglas; `ti_integracion` lee
- UI `/admin/exception-rules`: tabla versionada + form create + toggle active + historial drawer
- 6 unit tests (crear, activar, cierre versión anterior, RLS read, RLS write gerente, RLS write no-gerente)

**Archivos esperados**
- `mt-pricing-backend/alembic/versions/20260512_031_exception_rules.py`
- `mt-pricing-backend/app/db/models/exception_rule.py`
- `mt-pricing-backend/app/repositories/exception_rules.py`
- `mt-pricing-backend/app/services/pricing/exception_rules_service.py`
- `mt-pricing-backend/app/api/routes/exception_rules.py`
- `mt-pricing-frontend/app/(app)/admin/exception-rules/` — page + _client.tsx
- `mt-pricing-frontend/components/domain/exception-rules/` — table + form + history-drawer
- Tests unit + integration (6 escenarios)

**SP**: 8

---

### US-1B-02-03 — Lógica `auto_approved` vs `pending_review` con triggers

**Épica**: EP-1B-02
**Como** sistema
**Quiero** que al recalcular un precio se evalúen las `exception_rules` activas y el precio quede en `auto_approved` o `pending_review` automáticamente
**Para** minimizar carga manual del Gerente.

**Criterios de aceptación**
- `ExceptionEvaluator.evaluate(price, prev_price) → PriceStatus` aplica reglas activas en orden: min_margin → fx_swing → margin_delta
- Si cualquier regla se dispara → `pending_review`; si ninguna → `auto_approved`
- `PricingEngine.calculate()` llama a `ExceptionEvaluator` antes de persistir
- Unit tests: 5 escenarios (sin reglas, solo min_margin dispara, solo fx_swing, múltiples + primera dispara, ninguna dispara)

**Archivos esperados**
- `mt-pricing-backend/app/services/pricing/exception_evaluator.py`
- `mt-pricing-backend/app/services/pricing/pricing_engine.py` — integración evaluator
- `mt-pricing-backend/tests/unit/services/pricing/test_exception_evaluator.py`

**SP**: 5

---

### US-1B-02-05 — Endpoint `POST /prices/bulk-approve` con comentario obligatorio

**Épica**: EP-1B-02
**Como** Gerente
**Quiero** aprobar en lote precios en `pending_review` con un comentario obligatorio
**Para** reducir tiempo en cola de aprobación.

**Criterios de aceptación**
- `POST /prices/bulk-approve` con body `{price_ids: [UUID], comment: str (min 10 chars)}`
- Transición `pending_review → approved` vía `PriceStateMachine` (reutiliza US-1B-02-01)
- Auditado en `audit_events` con actor + comment + ids
- Error si algún price_id no está en `pending_review` → 422 con lista de IDs inválidos
- Unit tests: 3 escenarios (éxito, precio en estado incorrecto, comentario vacío)

**Archivos esperados**
- `mt-pricing-backend/app/api/routes/prices.py` — nuevo endpoint
- `mt-pricing-backend/app/services/pricing/bulk_approve_service.py`
- `mt-pricing-backend/tests/unit/services/pricing/test_bulk_approve_service.py`

**SP**: 3

---

### US-1B-02-07 — Digest diario 18:00 UAE in-app (email opcional)

**Épica**: EP-1B-02
**Como** Gerente
**Quiero** recibir un digest diario a las 18:00 UAE con el resumen de precios pendientes de aprobación, aprobados y escalados
**Para** tener visibilidad sin revisar la cola continuamente.

**Contexto**: Carry-over S6. US-1B-02-08 (escalation + notifications) ya entregado.

**Criterios de aceptación**
- Celery task `mt.pricing.daily_digest` disparado a 18:00 UAE (UTC+4 → 14:00 UTC) vía beat schedule
- Digest summary: count `pending_review`, count `auto_approved`, count `escalated`, count `approved` del día
- Notificación in-app creada vía `NotificationsRepository` (model ya existe, mig 029)
- Email opcional: si `SMTP_ENABLED=true` → enviar via SMTP con template HTML básico
- SPF/DKIM/DMARC: documentar proveedor elegido en ADR (Resend/Postmark) — no bloqueante para S7
- Unit tests: 3 escenarios (sin pending, con pending, con escalados)

**Archivos esperados**
- `mt-pricing-backend/app/workers/daily_digest.py` — task `daily_digest`
- `mt-pricing-backend/app/services/pricing/digest_service.py` — query + aggregation
- `mt-pricing-backend/app/core/celery_beat_schedule.py` — añadir `mt.pricing.daily_digest`
- `mt-pricing-backend/app/templates/email/daily_digest.html` — template básico (si SMTP_ENABLED)
- `mt-pricing-backend/tests/unit/services/pricing/test_digest_service.py`

**SP**: 5

---

### US-1B-02-09 — Audit trail extendido

**Épica**: EP-1B-02
**Como** auditor FTA
**Quiero** que `prices`, `exception_rules` y transiciones de canal queden registradas en `audit_events` con actor, antes y después
**Para** cumplir trazabilidad regulatoria.

**Criterios de aceptación**
- Trigger `audit_prices` captura INSERT/UPDATE en `prices` con `old_status`, `new_status`, `actor_user_id`
- Trigger `audit_exception_rules` captura INSERT/UPDATE en `exception_rules`
- Audit service expone `GET /audit/prices/{price_id}/timeline` con eventos ordenados
- Unit tests: 2 escenarios (price status change, exception rule activate)

**Archivos esperados**
- `mt-pricing-backend/alembic/versions/20260512_032_audit_extended.py` — triggers SQL
- `mt-pricing-backend/app/api/routes/audit.py` — endpoint timeline
- `mt-pricing-backend/tests/unit/api/test_audit_timeline.py`

**SP**: 3

---

### US-RND-01-10 — UI human queue validación humana asistida MVP

**Épica**: EP-RND-01
**Como** R&D Champion
**Quiero** una UI tipo "cola de validación" donde el operador ve pares candidato vs producto MT y puede aceptar/rechazar el match
**Para** generar golden labels y mejorar el calibrator.

**Contexto**: Carry-over S6. Calibrator (S5 ✅) + match_candidates con calibrated_confidence (S4 ✅) listos. Cohesivo con digest UI (misma sesión de desarrollo que US-1B-02-07).

**Criterios de aceptación**
- `GET /human-queue` devuelve matches con `calibrated_confidence < 0.85` ordenados por confidence ASC
- UI `/admin/human-queue`: tabla con thumbnail comparación + confidence badge + botones Accept/Reject/Skip
- `POST /human-queue/{match_id}/label` persiste `{label: accept|reject, reviewer_user_id, reviewed_at}` en `match_candidates`
- Flag off en prod si `HUMAN_QUEUE_ENABLED=false` (default true en dev)
- Unit tests: 2 escenarios (GET filtra correctamente, POST persiste label)

**Archivos esperados**
- `mt-pricing-backend/app/api/routes/human_queue.py`
- `mt-pricing-backend/app/services/matching/human_queue_service.py`
- `mt-pricing-frontend/app/(app)/admin/human-queue/page.tsx`
- `mt-pricing-frontend/app/(app)/admin/human-queue/_client.tsx`
- `mt-pricing-frontend/components/domain/matching/match-card.tsx`
- Tests (2 unit)

**SP**: 5

---

### US-1B-05-01 — Reporte diario diff app vs Excel demo (parallel run)

**Épica**: EP-1B-05
**Como** Champion MT
**Quiero** un reporte diario que compare precios calculados por la app vs el Excel de referencia v5.1
**Para** validar paridad durante el período de parallel run antes del cutover.

**Criterios de aceptación**
- Script `scripts/parallel_run_diff.py` compara `prices` (status=published/auto_approved) vs Excel cargado en tabla `price_reference_excel`
- Tabla `price_reference_excel` con columna `sku`, `channel`, `reference_price_aed`, `loaded_at`
- Output: JSON + CSV con diff por SKU+canal, % desviación, flag si > 0.5%
- Endpoint `GET /parallel-run/report?date=YYYY-MM-DD` devuelve el último reporte
- Celery task `mt.pricing.parallel_run_diff` diario 08:00 UAE

**Archivos esperados**
- `mt-pricing-backend/alembic/versions/20260512_033_price_reference_excel.py`
- `mt-pricing-backend/app/services/pricing/parallel_run_service.py`
- `mt-pricing-backend/app/workers/parallel_run.py`
- `mt-pricing-backend/app/api/routes/parallel_run.py`

**SP**: 3

---

## 5. Riesgos consolidados S7

| ID | Riesgo | Estado | Mitigación |
|----|--------|--------|------------|
| R-S7-01 | Pantalla 12 sin firma → US-1B-02-06 (Cola Gerente UI) bloqueada | activo | Defer cohesivo con S8; MVP tabla simple sin sidebar si sponsor urgente |
| R-S7-02 | Doppler creds sin firma → Hetzner staging deploy diferido | activo | Usar Docker local para DR drill + parallel run |
| R-S7-03 | US-1B-02-02 (exception_rules) más complejo de lo esperado (UI + versionado) | alto | 8 SP buffer — si 1 agente, partir en backend (5 SP) + frontend (3 SP) separados |
| R-S7-04 | Scope creep post-S6 (taxonomy + PIM EAV) consume attention → S7 pierde foco | activo | Lock scope S7 a EP-1B-02 + EP-1B-05; cualquier PIM/taxonomy → S8 |
| R-S7-05 | Email transaccional sin SPF/DKIM/DMARC → digest a spam | activo | In-app digest primero; email documenta ADR proveedor pero no bloquea S7 |

---

## 6. Próximos pasos

1. **S7 kick-off**: ejecutar `bmad-sprint-planning` para registrar stories en sprint-status.yaml
2. **US-1B-02-01 primero**: state machine es prerequisito de 02-03 y 02-05 — Agente A arranca día 1
3. **Gestión sponsor**: escalar Pantalla 12 + Doppler creds day 1 para no bloquear P3 stretch
4. **Parallel run**: cargar Excel v5.1 en `price_reference_excel` al arrancar S7
5. **DR drill**: programar para 2026-06-07 sobre Docker local (no esperar Hetzner)

---

## 7. Apéndice A — Pre-S7 audit (scope ya implementado fuera del plan)

Los siguientes items fueron implementados post-S6 sin estar en el backlog S7 formal. **No requeieren SP en S7.**

| Trabajo | Commits | Cobertura épica |
|---------|---------|-----------------|
| Taxonomy registry polimórfico + frontend completo (drag-drop, filtros catálogo, sidebar data-driven) | `d006a0e`..`13fade0` | EP-1A-02 extensión (no en epic original) |
| PIM EAV typed attributes + polymorphic catalog overhaul | `28632a2` | EP-1A-02 extensión |
| PIM frontend: specs dinámico + spare parts + documents UI | `0283299` | EP-1A-02 extensión |
| Comparator Fase 1 hooks (ADR-012) | `05d00d7` | EP-RND-01 extensión |
| Reports Fase 0 cierre + auditoría modelo datos | `d70e1a4` | EP-1B-05 docs parcial |

**Impacto en S7**: ninguno de estos cierra stories EP-1B-02 ni EP-1B-05. El camino crítico del gate de cutover Fase 1b (workflow aprobación + hardening) sigue completamente pendiente.
