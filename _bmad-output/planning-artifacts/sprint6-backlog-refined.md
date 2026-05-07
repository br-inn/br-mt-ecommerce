---
title: "Sprint 6 — Backlog refinado"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
sprint: 6
capacity_target_sp: 32
sprint_goal: "Cerrar la cola operacional Fase 1b: completar workflow aprobación end-to-end (escalation + digest), entregar pdfplumber tablas estructuradas (US-1A-06-04-V2 carry-over), publicar DR runbook + drill plan, e iniciar UI human queue (US-RND-01-10) sobre pmo_bus existente. Externos bloqueantes (Hetzner deploy efectivo, Pantalla 12 firma, AR translation owner) explícitos para gestión sponsor."
related:
  - "sprint5-backlog-refined.md"
  - "../implementation-artifacts/sprint5-execution-report.md"
  - "epics-and-stories-mt-pricing-mdm-phase1.md"
  - "architecture-mt-pricing-mdm-phase1.md"
  - "risk-register-consolidado.md"
---

# Sprint 6 — Backlog refinado — MT Middle East Fase 1b cierre operacional

## 1. Resumen ejecutivo

Sprint 5 cerró el gate Fase 1b (red real adapters + RBAC + observability + IaC + CI/CD + judge_dispatcher). Sprint 6 cierra la **cola operacional**: jobs nocturnos de escalación + digest, pdfplumber tablas estructuradas para datasheets, DR runbook completo, y arranque de UI human queue (R&D path). Los stretch goals incluyen workflow de aprobación UI completa (US-1B-02-06) si Pantalla 12 firma a tiempo.

**Hallazgo crítico durante refinement**: la mayor parte de **EP-1B-02 backend** ya estaba entregada en S4 (state_machine, exception_evaluator, approve/reject/bulk-approve endpoints, RBAC `prices:approve`, audit `price_approval_events`). El scope S6 baja de ~62 SP candidatos a ~32 SP reales gestionables.

**Incluye (P0/P1)**: escalation job (US-1B-02-08), digest in-app (US-1B-02-07 sin email), pdfplumber tablas (US-1A-06-04-V2 stretch), DR runbook (US-1B-05-04 doc-only), reverse image search infra-only flag-off (US-RND-01-09), UI human queue scaffold (US-RND-01-10).

**Stretch (P2/P3)**: UI cola Gerente (US-1B-02-06) si Pantalla 12 firmada, AR translation completion (carry-over US-1A-07-04-AR si owner firma), Hetzner staging deploy efectivo (US-1A-IAC-01 carry-over creds Doppler).

## 2. Capacidad asumida

Capacidad nominal multi-agente: 35-40 SP basado en velocity sostenida S1-S5 (35/35 S1, 41/41 S2, 38/38 S3, 35/35 S4, 49/53 S5).

Si capacidad real cae a 25-28 SP: bajar US-RND-01-09 (-3) + US-RND-01-10 (-5) = 24 SP core (jobs + pdfplumber + DR runbook).

Bloqueadores externos críticos:
- **Pantalla 12 firma** (UX) → US-RND-01-10, US-1B-02-06.
- **Translation owner AR firma** → US-1A-07-04-AR completion.
- **Doppler creds firmadas** + Hetzner servers TI MT provisioned → US-1A-IAC-01 deploy efectivo.
- **Comercial signoff** sobre qué tablas extraer (cabezales, dim nominal, materiales) → cierra pdfplumber DoD.

## 3. Tabla maestra de stories

| ID | Título | Épica | SP | Prioridad | Dominio | Agente sugerido | Depende de | Estado pre-S6 |
|----|--------|-------|----|-----------| --------|------------------|------------|----------------|
| US-1B-02-08 | Job escalado >48h `pending_review` + delegado | EP-1B-02 | 5 | P0 | backend (workers+models) | A | US-1B-02-04 (S4) | ✅ approve/reject endpoints listos |
| US-1B-02-07 | Digest diario 18:00 UAE in-app (email opcional) | EP-1B-02 | 5 | P1 | backend (workers) | A | US-1B-02-08 | — |
| US-1A-06-04-V2-S6 | Pdfplumber tablas estructuradas + screenshots por página en `parsed_content` | EP-1A-06 | 5 | P1 | backend (importer) | B | US-1A-06-04 (S4) | ✅ judge_dispatcher S5 listo |
| US-1B-05-04-DOC | DR runbook + drill plan documentación + chequeos automáticos | EP-1B-05 | 3 | P1 | DevOps (docs+scripts) | E | US-1A-IAC-01 (S5) IaC | — |
| US-RND-01-09 | Reverse image search infra (Sphinx/CLIP embeddings) — flag off | EP-RND-01 | 5 | P2 | backend (R&D) | C | US-1A-09-08 (S5), pgvector | ✅ pgvector S5 fix |
| US-RND-01-10 | UI human queue Tinder mockup-driven (sin Pantalla 12 firma → MVP placeholder) | EP-RND-01 | 5 | P2 | frontend (R&D) | D | calibrator estable S5 | ✅ calibrator_trainer S5 |
| US-1B-02-06 | Cola Gerente tabla + bulk-select + sidebar (stretch, condicional UX firma) | EP-1B-02 | 8 | P3 | frontend | D | Pantalla 12 firmada | ❌ blocked external |
| US-1A-07-04-AR-S6 | AR translation completion carry-over (stretch, condicional translation owner) | EP-1A-07 | 3 | P3 | frontend | D | translation owner firma | ❌ blocked external |
| US-1A-IAC-01-DEPLOY | Hetzner staging deploy efectivo (stretch, condicional Doppler creds) | EP-1A-01 | 5 | P3 | DevOps | E | Doppler workspace firmado | ❌ blocked external |
| **TOTAL CORE** |  |  | **23 SP** |  |  |  |  |  |
| **TOTAL STRETCH desbloqueable** |  |  | **+5 SP (R&D)** |  |  |  |  |  |
| **TOTAL STRETCH externos bloqueados** |  |  | **+16 SP (deferred S7 si no firman)** |  |  |  |  |  |

> **Comprometidos S6 (23 SP core)**: US-1B-02-08 (5) + US-1B-02-07 (5) + US-1A-06-04-V2-S6 (5) + US-1B-05-04-DOC (3) + US-RND-01-10 (5) = **23 SP**. **Stretch desbloqueable (5 SP)**: US-RND-01-09 reverse image. **Stretch bloqueado externo (16 SP)**: queda fuera del compromiso, gestión sponsor.

## 4. Fichas detalladas

### US-1B-02-08 — Job escalado >48h `pending_review` + delegado

**Épica**: EP-1B-02
**Como** Gerente
**Quiero** que propuestas con > 48h en `pending_review` se escalen automáticamente con notificación al delegado configurado
**Para** que ausencias no bloqueen la cola.

#### Contexto
Approve/reject endpoints + state machine entregados S4. Falta el job nocturno + columna `escalated` + relación `delegate_user_id` en User.

#### Criterios de aceptación
1. **Dado** una propuesta con > 48h en `pending_review` **Cuando** se ejecuta el job (cada 2h) **Entonces** marca `prices.escalated=true` + `escalated_at=now()` + emite audit `price.escalated`.
2. **Dado** un Gerente con `User.delegate_user_id` configurado **Cuando** se escala **Entonces** crea registro `notifications` (in-app) al delegado.
3. **Dado** un Gerente sin delegado **Cuando** se escala **Entonces** notifica al rol `ti` con flag `no_delegate=true`.
4. **Dado** una propuesta `approved` después de escalada **Cuando** se aprueba **Entonces** queda histórico en `audit_events` con `was_escalated=true`.
5. **Dado** una propuesta ya `escalated=true` **Cuando** vuelve a evaluarse **Entonces** NO duplica notificación (idempotente).

#### Notas técnicas
- Migración Alembic 029: `prices.escalated BOOLEAN DEFAULT false`, `prices.escalated_at TIMESTAMPTZ`, `users.delegate_user_id UUID FK users(id) NULL`.
- Tabla `notifications`: `id, recipient_user_id, kind, payload JSONB, seen_at, created_at`.
- Worker `app/workers/escalation.py` con task `escalate_pending_reviews` triggered cada 2h (Celery beat).
- Service `app/services/pricing/escalation_service.py` con `find_overdue_pending_reviews(window_hours=48)` + `escalate(price)`.
- Audit append-only via `AuditRepository.record(action="price.escalated", ...)`.
- Notification persist via `NotificationsRepository.create(...)`.

#### Archivos esperados
- `mt-pricing-backend/app/services/pricing/escalation_service.py`
- `mt-pricing-backend/app/services/notifications/notifications_service.py`
- `mt-pricing-backend/app/repositories/notifications.py`
- `mt-pricing-backend/app/db/models/notification.py`
- `mt-pricing-backend/app/workers/escalation.py`
- `mt-pricing-backend/alembic/versions/20260507_029_escalation.py`
- Tests: unit + integration cubriendo idempotencia + delegado + fallback `ti`.

#### DoD
- [ ] Coverage ≥ 85 %.
- [ ] 6+ tests integration.
- [ ] Smoke en Docker local con 1 propuesta marcada vieja a mano.
- [ ] Beat schedule actualizado.

#### SP: 5

---

### US-1B-02-07 — Digest diario 18:00 UAE in-app (email opcional)

**Épica**: EP-1B-02
**Como** Gerente
**Quiero** un digest diario al final de la jornada con auto-aprobados + pendientes + escaladas + top razones
**Para** orientarme al día siguiente.

#### Contexto
Hook hacia notification infra (introducida en US-1B-02-08). Email queda como stretch — sólo in-app firme en S6.

#### Criterios de aceptación
1. **Dado** las 18:00 Asia/Dubai **Cuando** el job se ejecuta **Entonces** persiste 1 notification por Gerente activo con resumen del día.
2. **Dado** un Gerente sin propuestas en su cola **Cuando** corre el digest **Entonces** envía notif "all clear" (no se omite).
3. **Dado** un Gerente con `digest_hour=20` **Cuando** corre el job sweep **Entonces** dispara su notif a las 20:00 (no a las 18:00).
4. **Dado** un email opt-in **Cuando** el gerente activa flag `email_digests=true` **Entonces** se envía además email (placeholder Mailgun, no efectivo S6).

#### Archivos esperados
- `mt-pricing-backend/app/services/pricing/digest_service.py`
- `mt-pricing-backend/app/workers/digest.py`
- `mt-pricing-backend/alembic/versions/20260507_030_digest_prefs.py` — añade `users.digest_hour INT NULL`, `users.email_digests BOOLEAN DEFAULT false`.
- Tests: unit (3 escenarios) + integration (2).

#### SP: 5

---

### US-1A-06-04-V2-S6 — Pdfplumber tablas estructuradas + screenshots por página

**Épica**: EP-1A-06
**Como** R&D Champion
**Quiero** que los datasheets PDF importados extraigan tablas estructuradas + screenshots por página al `parsed_content` JSONB
**Para** que matching disponga de evidencia auditable de dimensiones y materiales por SKU.

#### Contexto
S5 cerró judge_dispatcher + extractor texto plano. Falta `pdfplumber` extracting tables (`page.extract_tables()`) + page screenshots (vía `pdfplumber.Page.to_image()`). OCR diferido S7+ (requiere imagen Docker dedicada con tesseract).

#### Criterios de aceptación
1. **Dado** un PDF nativo `MTFT_5114.pdf` **Cuando** se procesa post-importer **Entonces** `parsed_content.tables` tiene lista normalizada `[{page, headers, rows}]`.
2. **Dado** un PDF nativo **Cuando** se procesa **Entonces** `parsed_content.page_screenshots` tiene lista `[{page, storage_path}]` (PNG por página, ≤ 5 páginas).
3. **Dado** PDF escaneado/imagen **Cuando** se procesa **Entonces** `parse_method='text_only'` + warning + tablas vacías (NO falla — gracia).
4. **Dado** PDF cifrado **Cuando** se procesa **Entonces** retorna `parse_method='encrypted'` + audit warning.
5. Coverage ≥ 80 % `pdf_extractor` extendido + 1 fixture cifrado + 11 fixtures reales.

#### Archivos esperados
- `mt-pricing-backend/app/services/importer_datasheets/pdf_extractor.py` (extender con `extract_tables` + `render_page_screenshots`).
- `mt-pricing-backend/app/services/importer_datasheets/spec_parser.py` (consume tablas para enriquecer specs).
- Migración: `parsed_content` ya existía (S5); añadir índice GIN si falta.
- Tests: unit + 1 integration con fixture real `MTFT_5114.pdf`.

#### SP: 5

---

### US-1B-05-04-DOC — DR runbook + drill plan + chequeos automáticos

**Épica**: EP-1B-05
**Como** TI MT + Champion
**Quiero** un runbook DR completo con RPO/RTO documentados + script de health-check + drill plan
**Para** que ante incidente real (corruption / supabase down / Hetzner fuera) el equipo sepa exactamente qué hacer.

#### Contexto
S5 entregó IaC Terraform + observability. Falta DR procedure documentation + automated checks. El drill EFECTIVO requiere Hetzner provisioned (depende firma Doppler) → diferido S7 una vez deployment real.

#### Criterios de aceptación
1. Documento `docs/runbooks/disaster-recovery.md` con secciones: RPO/RTO targets, escenarios (DB corruption, Storage loss, Region down, Compromised secrets), procedure por escenario con comandos.
2. Script `infra/scripts/dr-healthcheck.sh` que verifica: pg_dump backups recientes < 24h, Storage replication lag, Sentry events flow, Caddy responding, Celery beat heartbeat.
3. Diagrama Mermaid de la cadena de dependencias (Caddy → Backend → Postgres+Redis → Storage Supabase).
4. Plan de drill mensual con 3 escenarios secuenciales (chaos eng lite).

#### Archivos esperados
- `docs/runbooks/disaster-recovery.md`
- `infra/scripts/dr-healthcheck.sh`
- `docs/runbooks/dr-drill-plan.md`

#### SP: 3

---

### US-RND-01-09 — Reverse image search infra (CLIP embeddings) — flag off (stretch)

**Épica**: EP-RND-01
**Como** R&D Champion
**Quiero** vector store con CLIP embeddings de imágenes canónicas + similar search
**Para** que ante una imagen subida (Tinder UI) podamos encontrar SKUs candidatos visualmente similares.

#### Contexto
Pgvector ya extendido S5. El embedding model puede ser CLIP via OpenAI text-embedding-large variant o sentence-transformers `clip-ViT-B-32`. En S6 entregamos infra desactivada por flag `RND_REVERSE_IMAGE_ENABLED=false`.

#### Criterios de aceptación
1. Tabla `image_embeddings` (sku FK, model_version, embedding vector(512), created_at).
2. Worker `embed_canonical_images` que procesa nuevas imágenes batch.
3. Endpoint `POST /matching/reverse-image-search` que retorna top-N (flag off → 501 Not Implemented).
4. Tests con vectores sintéticos + cosine similarity validada.

#### SP: 5

---

### US-RND-01-10 — UI human queue Tinder MVP placeholder (stretch sin Pantalla 12 firma)

**Épica**: EP-RND-01
**Como** matcher humano
**Quiero** una UI minimal para revisar parejas pendientes con verdict humano
**Para** alimentar el feedback loop del calibrator (US-1A-09-07 S5).

#### Contexto
Pantalla 12 mockup pendiente de firma UX (psierra). En S6 entregamos un MVP placeholder funcional (sin polish) que persiste verdicts a `match_decisions.human_verdict` y queda accesible vía `/matching/human-queue`. Cuando UX firme, S7 reemplaza con UI definitiva.

#### Criterios de aceptación
1. Página `/matching/human-queue` lista pares pendientes con imagen canonical + candidate + 3 botones (match / drift / reject) + textarea reasoning.
2. Submit POST a endpoint backend que persiste verdict.
3. Skip/Cancel disponible.
4. Tests E2E Playwright: 3 verdicts → 3 rows persistidas.

#### SP: 5

## 5. Riesgos consolidados S6

| ID | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|
| R-S6-01 | Pantalla 12 sin firma → US-RND-01-10 + US-1B-02-06 bloqueados | Alta | Media | MVP placeholder S6, UX firma + reemplazo S7 |
| R-S6-02 | Translation owner AR sin firma → carry-over crece | Media | Media | Pablo escala day 1; defer S7 si no firma |
| R-S6-03 | Doppler creds tardan → Hetzner deploy diferido | Media | Alta | DR runbook + drill plan funcionan sin deploy real (mock); deploy efectivo S7 |
| R-S6-04 | OCR images >2GB en CI (carry-over R-S5-NEW-01) | Activo | Media | Mantener defer S7 con worker container dedicado |
| R-S6-05 | Capacidad real < 25 SP por incidente prod tras live network | Media | Alta | Bajar US-RND-01-09 (-5) + US-RND-01-10 (-5) → 13 SP minimum core (jobs + pdfplumber + DR doc) |

## 6. Próximos pasos

1. **Inmediato (consolidación S6)**: cerrar US-1B-02-08 (escalation) + pdfplumber tablas + DR runbook (~13 SP server-side, sin blockers externos).
2. **Mid-sprint**: US-1B-02-07 digest job + US-RND-01-10 UI placeholder.
3. **Cierre sprint**: gestión sponsor para desbloquear Pantalla 12 + AR + Doppler. Sprint 7 retoma stretch bloqueados.
4. **Sprint 7 preview**: UI Tinder definitiva, AR completion, Hetzner staging real, OCR pipeline con worker container, US-1B-02-06 cola Gerente UI completa.

## 7. Apéndice A — Items ya entregados pre-S6 (descubiertos en refinement)

Hallazgo: refactor BMAD inicial sobreestimaba el scope EP-1B-02 al planear S5/S6. La realidad post-S5:

| Story | Estado | Sprint donde se entregó |
|---|---|---|
| US-1B-02-01 (state machine) | ✅ | S4 (`app/services/pricing/state_machine.py` + `state_machine_v51.py`) |
| US-1B-02-02 backend (exception_rules) | ✅ | S4 (`app/services/pricing/exception_evaluator.py`, `GET /pricing/exception-rules`) |
| US-1B-02-03 (auto_approved vs pending_review) | ✅ | S4 (`state_machine_v51.decide_initial_status`) |
| US-1B-02-04 (approve/reject endpoints) | ✅ | S4 (`POST /pricing/prices/{id}/approve`, `/reject`) |
| US-1B-02-05 (bulk-approve) | ✅ | S4 (`POST /pricing/prices/bulk-approve`) |
| `price_approval_events` audit | ✅ | S4 (modelo `pricing.py:265+`) |
| RBAC `prices:approve` | ✅ | S5 (US-1A-07-04-RBAC) |

Esto desbloquea S6 — el scope baja de 62 → 32 SP nominal y permite enfocar sprint en jobs + R&D + DR.
