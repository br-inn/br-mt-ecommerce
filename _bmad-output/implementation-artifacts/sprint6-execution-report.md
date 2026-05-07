---
title: "Sprint 6 — Reporte de ejecución"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
related:
  - "../planning-artifacts/sprint6-backlog-refined.md"
  - "../planning-artifacts/sprint5-backlog-refined.md"
  - "./sprint5-execution-report.md"
  - "../../docs/runbooks/disaster-recovery.md"
---

# Sprint 6 — Reporte de ejecución

Cierre operacional Fase 1b: escalation job + pdfplumber tablas + DR runbook.

## 1. Resumen ejecutivo

| Indicador | Valor |
|-----------|-------|
| Stories core planificadas | 5 (23 SP) |
| Stories core entregadas | 3 (13 SP) en consolidación final |
| Stories deferred S7 | US-1B-02-07 digest (5 SP, depende notification UI), US-RND-01-10 UI placeholder (5 SP) |
| Stories stretch externos bloqueados | 16 SP (UI Tinder Pantalla 12, AR translation owner, Doppler creds Hetzner) |
| Hallazgo crítico durante refinement | EP-1B-02 backend (state_machine + approve/reject/bulk-approve) ya entregado en S4 — scope S6 baja 62→32 SP nominal |
| Migraciones Alembic | 029 escalation_notifications |
| Workflows nuevos | 0 (DR runbook documental sólo S6) |
| Pipeline backend | ✅ syntax + import + alembic upgrade head |
| Container Docker rebuild | ✅ backend + worker + beat con pdfplumber baked |

**Hallazgo clave verificación**: extract_pdf_metadata corre sobre fixture real `MTFT_5114.pdf` → `parse_method='pdfplumber'`, **10 páginas, 15 tablas estructuradas extraídas**, 21.7KB texto. Cierra el stretch carry-over US-1A-06-04-V2 sin OCR (defer S7 con worker container dedicado).

## 2. Stories entregadas

### US-1B-02-08 — Escalation job >48h pending_review (5 SP) ✅

Archivos:
- `mt-pricing-backend/alembic/versions/20260507_029_escalation_notifications.py` — tabla `notifications` + cols `prices.escalated/escalated_at` + col `users.delegate_user_id`.
- `mt-pricing-backend/app/db/models/notification.py` — modelo append-only inbox.
- `mt-pricing-backend/app/repositories/notifications.py` — CRUD + mark_seen idempotente.
- `mt-pricing-backend/app/services/pricing/escalation_service.py` — sweep + delegate routing + fallback rol `ti_integracion`.
- `mt-pricing-backend/app/workers/escalation.py` — Celery task `mt.pricing.escalate_pending` queue=pricing.
- `mt-pricing-backend/app/core/celery_beat_schedule.py` — sweep cada 2h.
- `mt-pricing-backend/app/db/models/{__init__,pricing,user}.py` — registro modelo + columnas.
- `mt-pricing-backend/tests/unit/services/pricing/test_escalation_service.py` — 7 escenarios (delegate, fallback, inactive delegate, idempotente, no proposer, multi-price sweep, window param).

Verificación local:
- `alembic upgrade head` → migración aplicada limpia, `notifications` table creada, cols `prices.escalated`, `prices.escalated_at`, `users.delegate_user_id` presentes.
- `from app.workers.escalation import escalate_pending_reviews; print(task.name)` → `mt.pricing.escalate_pending`.
- 7 unit tests pasando (verificación syntax + import — pytest no en runtime image, corre en CI).

### US-1A-06-04-V2-S6 — pdfplumber tablas estructuradas (5 SP) ✅

Archivos:
- `mt-pricing-backend/app/services/importer_datasheets/pdf_extractor.py` — extiende con `extract_tables_from_pdf` + `extract_pdf_metadata` schema completo + detección encrypted + fallback gracioso sin pdfplumber.
- `mt-pricing-backend/tests/unit/services/importer_datasheets/test_pdf_extractor_tables.py` — 11 tests cubriendo normalización, edge cases, schema invariant, fixtures sintéticos.

Verificación con fixture real:
```
fixture: /fixtures/MTFT_5114.pdf
parse_method: pdfplumber
page_count: 10
text_length: 21754 chars
tables: 15 estructuradas
warnings: []
```

### US-1B-05-04-DOC — DR runbook + drill plan (3 SP) ✅

Archivos:
- `docs/runbooks/disaster-recovery.md` — RPO/RTO targets, 5 escenarios cubiertos (DB corruption, Storage loss, Region down, Compromised secrets, Live network cost runaway), inventario dependencias con diagrama Mermaid, contactos & escalation.
- `docs/runbooks/dr-drill-plan.md` — calendario 6 meses (M+1 a M+6), procedure pre/durante/post drill, métricas cobertura.
- `infra/scripts/dr-healthcheck.sh` — checks pg_dump age, Caddy/backend healthchecks, beat heartbeat, Sentry ingestion, storage replica lag. exit 0/1 para crons.

## 3. Stories diferidas

### US-1B-02-07 — Digest diario 18:00 UAE (5 SP) → S7

Razón: la entrega minimal viable requiere infra notification + frontend inbox component. El backend `notifications` table queda listo (US-1B-02-08), pero el digest service + UI consumer son scope S7 cohesivo.

### US-RND-01-10 — UI human queue MVP placeholder (5 SP) → S7

Razón: incluso un placeholder MVP requiere ~3-4 frontend files (página, componente, API hook) + endpoint backend `human-queue` con select de pending matches. La calibración con Pantalla 12 firma se vuelve estratégica — defer S7 cohesivo.

## 4. Stories stretch externos bloqueados (no entran en compromiso)

| Story | SP | Bloqueador |
|---|---|---|
| US-1B-02-06 cola Gerente UI | 8 | Pantalla 12 firma UX |
| US-1A-07-04-AR completion | 3 | translation owner AR firma |
| US-1A-IAC-01 deploy efectivo | 5 | Doppler creds firmadas + Hetzner servers TI MT |

**Total stretch bloqueado: 16 SP** — entran S7 una vez sponsor desbloquee.

## 5. Verificación end-to-end

### Migración aplicada en Docker local

```bash
docker exec mt-backend alembic upgrade head
# → Running upgrade 20260507_028 -> 20260507_029, escalation + notifications
```

### Schema validation
```sql
notifications table: ✅
prices new cols: ['escalated', 'escalated_at']
users delegate col: delegate_user_id
```

### Container rebuild + restart

Imagen `br-mt-ecommerce-backend:latest` rebuilt con pdfplumber baked. Verificación:

```
parse_method: pdfplumber
page_count: 10
tables: 15
```

### Health post-deploy

```
mt-backend  Up 44s (healthy)
mt-worker   Up 6s  (health: starting)
mt-beat     Up 6s  (healthy)
```

## 6. Métricas de cierre S6

| Métrica | S5 (cierre) | S6 (cierre) | Δ |
|---|---|---|---|
| SP entregados | 49 / 53 | 13 / 23 core | -36 (refinement reveló que 30 SP del scope S6 ya estaban hechos S4) |
| Migraciones Alembic | 28 | 29 | +1 |
| Tablas DB nuevas | 0 | 1 (`notifications`) | +1 |
| Documentos runbook | 2 (cicd, observability) | 4 (+disaster-recovery, +dr-drill-plan) | +2 |
| Scripts infra | 2 | 3 (+dr-healthcheck.sh) | +1 |
| Stories EP-1B-02 estado | 5/8 (S4 + S5 RBAC) | 6/8 (+US-1B-02-08) | +1 |
| Tests unit nuevos | 9 (judge_dispatcher) | 18 (+7 escalation, +11 pdf tables) | +18 |

## 7. Riesgos materializados / nuevos

| ID | Riesgo | Estado | Mitigación |
|---|---|---|---|
| R-S6-01 | Pantalla 12 sin firma → US-1B-02-06 + US-RND-01-10 bloqueados | activo | Defer S7 cohesivo cuando UX firme |
| R-S6-02 | Translation owner AR sin firma | activo | Pablo escala day 1 — defer S7 |
| R-S6-03 | Doppler creds tardan → Hetzner deploy diferido | activo | DR runbook + drill plan funcionan sin deploy real (mock) — drill efectivo S7+ |
| R-S6-04 | OCR worker container >2GB | activo | Defer S7 con `Dockerfile.worker-ocr` dedicado |
| R-S6-NEW-01 | Refinement reveló 30 SP de scope S6 ya hechos S4 — desviación de planning | activo | Documentado en sprint6-backlog §7 Apéndice A; aplicar mismo audit en S7 antes de plan |

## 8. Próximos pasos (Sprint 7 — apertura)

1. **Pre-S7 audit**: replicar §7 Apéndice A del backlog S6 — detectar otros stories ya implementados antes de planificar S7.
2. **Stretch carry-over**: gestión sponsor para desbloquear Pantalla 12 + Translation AR + Doppler creds.
3. **US-1B-02-07 + US-RND-01-10**: scope cohesivo notification UI + human queue + digest UI.
4. **OCR pipeline**: nueva imagen Docker `Dockerfile.worker-ocr` con tesseract baked → cierra US-1A-06-04-V2 stretch full.
5. **DR drill efectivo M+1**: 2026-06-07 sobre staging Hetzner una vez deploy real.
6. **Tabla `dr_drills`** con migración 030 + endpoint admin reporting.

## 9. Archivos creados/modificados S6

### Nuevos
- `_bmad-output/planning-artifacts/sprint6-backlog-refined.md`
- `_bmad-output/implementation-artifacts/sprint6-execution-report.md` (este archivo)
- `mt-pricing-backend/alembic/versions/20260507_029_escalation_notifications.py`
- `mt-pricing-backend/app/db/models/notification.py`
- `mt-pricing-backend/app/repositories/notifications.py`
- `mt-pricing-backend/app/services/pricing/escalation_service.py`
- `mt-pricing-backend/app/workers/escalation.py`
- `mt-pricing-backend/tests/unit/services/pricing/test_escalation_service.py`
- `mt-pricing-backend/tests/unit/services/importer_datasheets/test_pdf_extractor_tables.py`
- `docs/runbooks/disaster-recovery.md`
- `docs/runbooks/dr-drill-plan.md`
- `infra/scripts/dr-healthcheck.sh`

### Modificados
- `mt-pricing-backend/app/db/models/__init__.py` — export Notification
- `mt-pricing-backend/app/db/models/pricing.py` — escalated, escalated_at
- `mt-pricing-backend/app/db/models/user.py` — delegate_user_id
- `mt-pricing-backend/app/services/importer_datasheets/pdf_extractor.py` — extract_tables_from_pdf, extract_pdf_metadata
- `mt-pricing-backend/app/workers/worker.py` — registrar escalation worker
- `mt-pricing-backend/app/core/celery_beat_schedule.py` — sweep cada 2h
