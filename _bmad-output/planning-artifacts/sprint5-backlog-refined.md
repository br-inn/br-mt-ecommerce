---
title: "Sprint 5 — Backlog refinado"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
sprint: 5
capacity_target_sp: 35
sprint_goal: "Cerrar gate Fase 1b con activación red real (Amazon UAE / Noon UAE / SP-API), endurecer RBAC granular + RLS verificada, llevar observability + IaC + CI/CD a producción Hetzner, y subir cobertura del calibrator + datasheets PDF + Vision API real. Apertura de track operacional Fase 2 (bulk-recalc nocturno, i18n AR completo, OpenAPI consolidation, BR PMO hooks)."
related:
  - "epics-and-stories-mt-pricing-mdm-phase1.md"
  - "sprint4-backlog-refined.md"
  - "../implementation-artifacts/sprint4-execution-report.md"
  - "mt-product-matching-pipeline-detail.md"
  - "architecture-mt-pricing-mdm-phase1.md"
  - "prd-mt-pricing-mdm-phase1.md"
  - "ux-mockups-mt-pricing-mdm-phase1.md"
  - "risk-register-consolidado.md"
  - "adr/ADR-055-ssrf-policy-image-probe.md"
---

# Sprint 5 — Backlog refinado — MT Middle East MDM + Pricing Fase 1b → cutover

## 1. Resumen ejecutivo

Sprint 5 es el **gate de cutover Fase 1b → producción interna** para el equipo Comercial MT. Tras S4 (pricing engine + adapters reales con red shadow + audit triggers + RLS finas declarativas), S5 cierra los huecos no funcionales que separan "stack que corre en local Docker" de "stack desplegado en Hetzner con observabilidad real, CI/CD verde, deploy reproducible y RBAC granular auditado".

**Eje 1 — Activación red real condicional**: si Q-NEW-S3 firma legal + creds SP-API llegan al kickoff, US-1A-09-08 activa `MT_LIVE_NETWORK=true` con feature flag enrollment + kill-switch (puede revertir a stubs en < 5 min sin redeploy). Sin firma: story degrada a "ensayo offline".

**Eje 2 — Endurecimiento RBAC + tests integration desbloqueados**: permisos dedicados (`matches:read/write`, `channels:read/manage`, `prices:override_review`, `graphrag:admin`) seedeados parcialmente en S4 → completos S5. Pgvector fix en `tests/conftest.py::postgres_container` desbloquea ~24 integration tests `test_*_trigger.py` + `test_rls_finas.py` actualmente skipped → cierre de coverage real RLS.

**Eje 3 — Producción Hetzner end-to-end**: Sentry (errors + traces + logs aggregation con Better Stack) + Terraform IaC con secrets vault Doppler + CI/CD pipeline real (tests → build images → push registry → deploy staging) + rate limiting/WAF Cloudflare (ADR-054). Output: deploy reproducible + rollback en un comando + SLOs medibles.

**Eje 4 — Cierre features Fase 1b retrasadas**: calibrator isotonic training pipeline + golden labels feedback loop (US-1A-09-07), datasheets PDF parsing real con `pdfplumber` + `OpenAIVisionJudge` activo cuando `OPENAI_API_KEY` esté seedeada, i18n AR 100% catálogo aprobado por translation owner, pricing engine bulk-recalc nocturno Celery beat con audit batch.

**Eje 5 — Apertura track operacional**: BR PMO integration hooks (notificación eventos clave hacia Fase 2), OpenAPI spec consolidation con frontend types regen automatizado.

**Incluye (P0/P1)**: Activación red real (US-1A-09-08), permisos RBAC dedicados (US-1A-07-04-RBAC), pgvector fix + integration tests desbloqueados (US-1A-INFRA-01), Sentry + observability stack (US-1A-OBS-01), Terraform IaC Hetzner + Doppler (US-1A-IAC-01), CI/CD real (US-1A-CICD-01), rate limiting + WAF (US-1A-SEC-01), calibrator training pipeline (US-1A-09-07), datasheets PDF + Vision real (US-1A-06-04-V2), i18n AR completion (US-1A-07-04-AR), bulk-recalc nocturno (US-1B-01-07), OpenAPI consolidation + frontend types regen (US-1A-DEV-01).

**Stretch (P2/P3)**: BR PMO integration hooks (US-RND-01-12), workflow aprobación delta (US-1B-02-01..03 carry-over de S5 plan original — defer S6 si capacidad presiona), reverse image search (US-RND-01-09 → S6 con flag off).

**Gates de Fase 1b al cerrar S5**: deploy Hetzner verde con observabilidad real (Sentry + traces + logs); CI/CD pipeline ejecuta tests + build images + push staging deploy en < 15 min; RBAC granular auditado con 24 integration tests passing; activación red real funcional con kill-switch (incluso si flag stays off al cierre, infra está lista); calibrator entrenado sobre dataset etiquetado ≥ 100 pares con ECE < 5%; i18n AR firmado al 100%; bulk-recalc nocturno running en staging.

**Dependencias críticas pre-kickoff**:
- (a) **Q-NEW-S3 firma legal** (Champion + Legal MT) — bloquea US-1A-09-08 activación real.
- (b) **Credenciales SP-API + AWS Role + LWA tokens** producidos por TI MT — carry-over crítico de S4.
- (c) **OPENAI_API_KEY** programa MT España — bloquea Vision real US-1A-06-04-V2.
- (d) **Doppler workspace MT** provisionado por TI MT con secrets seedeados (Bright Data, Gemini, OpenAI, SP-API, Sentry DSN, AWS credentials).
- (e) **Hetzner servers provisionados** (1× api/web + 1× worker + 1× db-cache si separación) por TI MT.
- (f) **Cloudflare zone `app.mtme.ae`** delegada por TI MT (incluso si dominio principal sigue parked R-013 register).
- (g) **Sentry DSN + Better Stack source token** firmado.
- (h) **Translation owner AR** firma calendario de revisión (recuperación de US-1A-02-05 stretch).
- (i) **Golden labels v2 ≥ 100 pares** producidos por R&D Champion (US-RND-01-03 cierre).

## 2. Capacidad asumida

| Concepto | Valor |
|----------|-------|
| Devs FTE | 2-3 + TI Integración part-time + R&D Champion (calibrator) + DevOps (IaC + CI/CD + observability dedicado) |
| Velocity asumida | 35-42 SP/sprint humano (modo multi-agente sostuvo 50+ en S1/S2/S3/S4) |
| Sprint length | 2 semanas (10 días lab.) |
| Reservas | 25 % buffer (territorio nuevo: IaC + activación red real con cost burst risk) + 15 % refinement secrets/Doppler/Cloudflare |
| **Capacidad target S5** | **35 SP** (modo multi-agente) / 60 SP capacidad teórica si 5 agentes |
| Carry-over S4 | 0-8 SP esperado: si Q-NEW-S3 / SP-API creds no llegaron en S4, US-1A-09-03/05 quedaron en "wire degraded" → carry SP residual S5; UX firmas Pantalla 6/11 firmadas o no. Asumimos 0 si S4 ejecuta como S1-S4. |

Si la capacidad real cae a 28-30 SP, aplicar §6 priorización: bajar US-RND-01-12 BR PMO hooks (-3) + US-1A-DEV-01 OpenAPI consolidation (-3) + US-1A-09-07 calibrator training pipeline (-5) → 24 SP core (red real activación + permisos + pgvector fix + Sentry + IaC + CI/CD).

## 3. Tabla maestra de stories

| ID | Título | Épica | SP | Prioridad | Dominio | Agente sugerido | Depende de |
|----|--------|-------|----|-----------| --------|------------------|------------|
| US-1A-09-08 | Activación red real adapters (`MT_LIVE_NETWORK=true`) + flag enrollment + kill-switch | EP-1A-09 | 5 | P0 | backend (workers+integrations) | C | US-1A-09-03 (S4), US-1A-09-05 (S4), Q-NEW-S3 firma, creds SP-API |
| US-1A-07-04-RBAC | Permisos RBAC dedicados (`matches:*`, `channels:*`, `prices:override_review`, `graphrag:admin`) | EP-1A-07 | 5 | P0 | backend (data+api) | A | US-1A-07-02 (S4), US-1A-07-03 (S4) |
| US-1A-INFRA-01 | Pgvector fix + integration tests desbloqueados (`test_*_trigger.py` + `test_rls_finas.py`) | EP-1A-01 | 3 | P0 | backend (infra+tests) | A | US-1A-07-02 (S4), US-1A-07-03 (S4) |
| US-1A-OBS-01 | Sentry + observability stack end-to-end (errors + traces + logs aggregation) | EP-1A-01 / EP-1A-08 | 5 | P0 | backend (infra) | E | ADR-019 + ADR-047 |
| US-1A-IAC-01 | Hetzner deploy IaC vía Terraform + Doppler secrets vault wiring | EP-1A-01 | 5 | P0 | DevOps (IaC) | E | Hetzner servers TI MT, Doppler workspace |
| US-1A-CICD-01 | CI/CD pipeline real (tests → build images → push registry → deploy staging) | EP-1A-01 | 5 | P1 | DevOps (CI) | E | US-1A-IAC-01 |
| US-1A-SEC-01 | Rate limiting + WAF Cloudflare (ADR-054) | EP-1A-07 | 3 | P1 | backend (security) | A | US-1A-IAC-01 (Cloudflare zone) |
| US-1A-09-07 | Calibrator isotonic training pipeline + golden labels feedback loop | EP-1A-09 / EP-RND-01 | 5 | P1 | backend (R&D) | C | US-1A-09-06 (S4), golden labels v2 ≥ 100 |
| US-1A-06-04-V2 | Datasheets PDF parsing real (`pdfplumber`) + `OpenAIVisionJudge` activo | EP-1A-06 / EP-RND-01 | 5 | P1 | backend (importer+R&D) | B | US-1A-06-04 (S4), `OPENAI_API_KEY` |
| US-1A-07-04-AR | i18n AR completion (revisar todas las pantallas con texto faltante en árabe) | EP-1A-07 | 3 | P1 | frontend | D | translation owner AR firma |
| US-1B-01-07 | Pricing engine bulk-recalc nocturno (Celery beat task + audit batch) | EP-1B-01 | 3 | P1 | backend (workers) | B | US-1B-01-04 (S4) |
| US-1A-DEV-01 | OpenAPI spec consolidation + frontend types regen automatizado | EP-1A-01 | 3 | P2 | backend+frontend | B/D | US-1A-09-08, US-1A-09-07 (consumers) |
| US-RND-01-12 | BR PMO integration hooks (notificación eventos clave hacia Fase 2) | EP-RND-01 | 3 | P3 | backend (R&D arch) | E | US-1A-07-03 (S4) |
| **TOTAL** |  |  | **53 SP capacidad / 35 SP comprometidos** |  |  |  |  |

> **Comprometidos S5 (35 SP)**: US-1A-09-08 (5) + US-1A-07-04-RBAC (5) + US-1A-INFRA-01 (3) + US-1A-OBS-01 (5) + US-1A-IAC-01 (5) + US-1A-CICD-01 (5) + US-1A-SEC-01 (3) + US-1A-07-04-AR (3) + US-1B-01-07 (3) = **35 SP** core. **Stretch (18 SP)**: US-1A-09-07 (5) + US-1A-06-04-V2 (5) + US-1A-DEV-01 (3) + US-RND-01-12 (3) — incorporar si modo multi-agente sostiene velocity S1/S2/S3/S4.

## 4. Fichas detalladas

---

### US-1A-09-08 — Activación red real adapters (`MT_LIVE_NETWORK=true`) + flag enrollment + kill-switch

**Épica**: EP-1A-09
**Como** Champion R&D + TI MT
**Quiero** activar adapters de red real (Bright Data Amazon UAE + Noon UAE, SP-API real Amazon UAE, Playwright manufacturer) con un único flag global `MT_LIVE_NETWORK=true` y kill-switch de emergencia
**Para** transitar de "shadow mode" (stubs canned) a "live network" sin redeploy y revertir en < 5 min si hay incidente legal/cost/quality.

#### Contexto
S4 entregó adapters reales pero condicionales a Q-NEW-S3 firma legal + creds SP-API. S5 implementa el mecanismo de **enrollment progresivo** del flag: por defecto OFF (stubs activos del S3-S4), al activar SE incrementa fase de % SKUs enrollados (10% → 50% → 100%) con métricas en tiempo real. Kill-switch via setting `MT_LIVE_NETWORK_KILL_SWITCH=true` (override `MT_LIVE_NETWORK`) que se puede flippear desde Doppler en < 5 min.

Patrón **gradual rollout** con audit trail completo: cada activación deja `audit_events(entity='feature_flag', action='enroll', payload={percent, source, actor})`.

#### Criterios de aceptación
1. **Dado** `MT_LIVE_NETWORK=false` (default) **Cuando** se invoca `comparator_service.find_candidates(sku)` **Entonces** sistema usa adapters stub canned (S3 behaviour preserved).
2. **Dado** `MT_LIVE_NETWORK=true` y `MT_LIVE_NETWORK_PERCENT=10` **Cuando** se procesan SKUs **Entonces** sistema usa adapters reales en 10% de los casos (selección determinista por hash SKU), 90% sigue con stubs. Métricas Sentry tag `live_network=true|false`.
3. **Dado** `MT_LIVE_NETWORK_PERCENT=100` y `MT_LIVE_NETWORK_KILL_SWITCH=true` **Cuando** se procesa **Entonces** sistema fuerza stubs (kill-switch tiene precedencia), Sentry alert SEV2 + Slack `#mt-alerts`.
4. **Dado** un cambio de flag en Doppler **Cuando** ocurre **Entonces** los workers Celery refrescan el flag dentro de 60s (no requiere restart). Endpoint `GET /admin/feature-flags` muestra estado actual.
5. **Dado** un TI MT con role `ti+` **Cuando** llama `POST /admin/feature-flags/MT_LIVE_NETWORK_PERCENT` con `{percent: 50, reason: "rampa fase 2 enrollment"}` **Entonces** se persiste en config + audit_events.
6. **Dado** activación de red real **Cuando** se ejecuta primer batch matching **Entonces** dashboard muestra: `cost_bright_data_today_usd`, `cost_gemini_today_usd`, `cost_sp_api_calls_today`, `circuit_breaker_open_count`, `match_decisions_real_count`.
7. **Dado** quota Bright Data hit (presupuesto $150 mensual ya consumido) **Cuando** se intenta nuevo fetch **Entonces** circuit breaker abre + fallback automático a stub + Slack alert SEV1.

#### Notas técnicas
- `app/services/feature_flags.py` con `FeatureFlagService` que lee de Doppler/env + cache Redis con TTL 60s.
- Helper `is_live_network_for_sku(sku) -> bool` con hash determinista para split estable.
- Endpoints `app/api/v1/admin/feature_flags.py` para CRUD (RBAC `ti+`).
- Migración Alembic 0024: tabla `feature_flag_audit` (flag_name, old_value, new_value, actor, reason, changed_at) — append-only.
- Cost dashboard: `app/services/cost_tracker.py` con tags Sentry custom + métricas Prometheus exportadas.
- TODO ADR-075 "Feature flag strategy MT live network" — gradual rollout, kill-switch precedence, cost ceiling, audit, rollback procedure.

#### Archivos esperados
- `mt-pricing-backend/app/services/feature_flags.py`
- `mt-pricing-backend/app/api/v1/admin/feature_flags.py`
- `mt-pricing-backend/app/services/cost_tracker.py`
- `mt-pricing-backend/alembic/versions/0024_create_feature_flag_audit.py`
- `mt-pricing-backend/app/db/models/feature_flag_audit.py`
- Tests: unit + integration con flag transitions + 1 E2E enrollment progression.

#### DoD
- [ ] Coverage ≥ 85 % en `feature_flags.py`, `cost_tracker.py`.
- [ ] Kill-switch verificado en < 5 min tras flip Doppler (smoke real con flag toggle).
- [ ] Cost dashboard funcional (Better Stack panel).
- [ ] ADR-075 firmado.
- [ ] Smoke real con activación 10% sobre 5 SKUs vs 5 SKUs stub mode comparativo.
- [ ] Rollback procedure documentado en `docs/runbook-live-network-rollback.md`.

#### SP: 5

---

### US-1A-07-04-RBAC — Permisos RBAC dedicados (`matches:*`, `channels:*`, `prices:override_review`, `graphrag:admin`)

**Épica**: EP-1A-07
**Como** dev backend
**Quiero** la matriz RBAC granular con permisos dedicados por dominio (matches, channels, prices override, graphrag admin)
**Para** que cada role (Comercial / Gerente / TI / R&D Champion) tenga only-the-permissions-needed según principio least-privilege (NFR-07/11).

#### Contexto
**Carry-over parcial S4**. Migración 0021 (S4) seedó policies RLS por role, pero seeds de permisos dedicados quedaron incompletos: `matches:read/write`, `channels:read/manage`, `prices:override_review` (Gerente puede aprobar fuera del workflow normal), `graphrag:admin` (R&D Champion puede mutar `product_relations`). S5 cierra: tabla `role_permissions` declarativa + endpoints CRUD admin + integration tests por permission.

Helper `auth_user_has_permission(permission TEXT) RETURNS BOOL` extiende el `auth_user_has_role` ya existente de S4. Migración refresca policies RLS para usar permission-based en lugar de role-only en tablas críticas.

#### Criterios de aceptación
1. **Dado** un Comercial con permission `matches:read` **Cuando** consulta `GET /api/v1/match/decisions` **Entonces** RBAC permite. Sin permission → 403.
2. **Dado** un Gerente con permission `prices:override_review` **Cuando** llama `POST /api/v1/prices/{id}/override` **Entonces** sistema permite saltar workflow normal con audit `action='price_override_review'`.
3. **Dado** un R&D Champion con `graphrag:admin` **Cuando** llama `POST /api/v1/graph/relations` **Entonces** RBAC permite. Sin permission → 403.
4. **Dado** un TI con `channels:manage` **Cuando** llama `POST /api/v1/channels/amazon_ae/refresh-cache` **Entonces** RBAC permite.
5. **Dado** un Comercial sin `channels:manage` **Cuando** intenta refresh-cache **Entonces** retorna 403 (puede `read` pero no `manage`).
6. **Dado** la tabla `role_permissions` **Cuando** consulto `\d role_permissions` **Entonces** existe con (role, permission, granted_at, granted_by) y seed para 4 roles × matriz definida.
7. **Dado** un cambio en permissions vía endpoint admin **Cuando** se ejecuta **Entonces** queda audit_events con diff completo.

#### Notas técnicas
- Migración Alembic 0025: tabla `role_permissions` + seed (4 roles × ~15 permissions = 60 filas).
- `infra/supabase/migrations/0025_role_permissions.sql` con RLS policies refrescadas usando `auth_user_has_permission`.
- `app/services/auth/permissions.py` con `require_permission(permission)` decorator FastAPI.
- `app/api/v1/admin/permissions.py` con CRUD (RBAC `ti+` o `gerente+`).
- TODO ADR-076 "RBAC permission matrix Fase 1b" — documentar matriz completa + flujo grant/revoke + rationale por permission.
- Permissions catalog (mínimo): `products:read`, `products:write`, `costs:read`, `costs:write`, `prices:read`, `prices:write`, `prices:approve`, `prices:override_review`, `matches:read`, `matches:write`, `channels:read`, `channels:manage`, `audit:read`, `graphrag:admin`, `feature_flags:manage`, `users:manage`.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0025_role_permissions.py`
- `infra/supabase/migrations/0025_role_permissions.sql`
- `mt-pricing-backend/app/services/auth/permissions.py`
- `mt-pricing-backend/app/api/v1/admin/permissions.py`
- `mt-pricing-backend/app/db/models/role_permission.py`
- Tests: integration matriz roles × permissions × ops (≥ 30 escenarios).

#### DoD
- [ ] Coverage ≥ 85 %.
- [ ] 30+ tests integration cubriendo allow/deny por permission.
- [ ] ADR-076 firmado.
- [ ] Smoke con 4 roles distintos en local.
- [ ] Documentación `mt-security-compliance-design.md` actualizada con matriz.
- [ ] Endpoints existentes (S1-S4) refactored para usar `require_permission` (no `require_role`).

#### SP: 5

---

### US-1A-INFRA-01 — Pgvector fix + integration tests desbloqueados

**Épica**: EP-1A-01
**Como** dev backend
**Quiero** corregir el setup `tests/conftest.py::postgres_container` para que active la extensión `pgvector` y desbloquee las suites integration `test_*_trigger.py` + `test_rls_finas.py`
**Para** correr ~24 tests actualmente skipped y verificar RLS + audit triggers contra Postgres real.

#### Contexto
**Deuda técnica acumulada de S4**. La fixture `postgres_container` levanta testcontainers Postgres 15 pero sin instalar `pgvector` extension. Algunas migraciones Alembic (0019b para `competitor_calibrators` con `embedding_vector`, futuras de matching) requieren `CREATE EXTENSION vector`. Resultado: ~24 tests integration con marker `integration` se skipean en CI por error `extension "vector" is not available`.

S5 fix: usar `pgvector/pgvector:pg15` image en lugar de `postgres:15-alpine` + ejecutar `CREATE EXTENSION IF NOT EXISTS vector` en setup hook. Esto desbloquea: `test_audit_triggers_extended.py` (8 tests), `test_rls_finas.py` (16 tests) y posibles futuros.

#### Criterios de aceptación
1. **Dado** la fixture `postgres_container` **Cuando** se inicializa **Entonces** levanta image `pgvector/pgvector:pg15` con `vector` extension instalada.
2. **Dado** las migraciones Alembic con `CREATE EXTENSION vector` **Cuando** corren en CI **Entonces** no falla.
3. **Dado** los tests `test_audit_triggers_extended.py` **Cuando** corren con marker `integration` **Entonces** 8/8 pasan (cubren costs, prices, fx_rates, translations triggers).
4. **Dado** `test_rls_finas.py` **Cuando** corre **Entonces** 16/16 pasan (cubren 4 roles × 4 tablas críticas × allow/deny).
5. **Dado** CI workflow **Cuando** corre `pytest -m integration` **Entonces** ≥ 24 tests previamente skipped ahora pasan; total integration suite no skip > 90 %.
6. **Dado** un dev en local **Cuando** corre `pytest -m integration` con Docker disponible **Entonces** misma suite verde sin overrides especiales.

#### Notas técnicas
- `mt-pricing-backend/tests/conftest.py`: cambiar image string + añadir setup hook con `CREATE EXTENSION IF NOT EXISTS vector`.
- Verificar compatibility con resto de fixtures (no break Supabase migrations apply).
- Si pgvector image trae diferencias en defaults de Postgres, ajustar config (e.g. `shared_preload_libraries`).
- TODO documentar en `docs/testing-guide.md` la nueva imagen base para integration tests.

#### Archivos esperados
- `mt-pricing-backend/tests/conftest.py` (modificación postgres_container fixture)
- `mt-pricing-backend/tests/integration/test_audit_triggers_extended.py` (verificar pasa)
- `mt-pricing-backend/tests/integration/test_rls_finas.py` (verificar pasa)
- `docs/testing-guide.md` (documentación update)
- `.github/workflows/test-backend.yml` (verificar integration job verde)

#### DoD
- [ ] 24+ tests integration pasando que antes skipeaban.
- [ ] CI workflow `test-integration` verde.
- [ ] Documentación testing-guide.md actualizada.
- [ ] Pgvector verificado en local + CI.
- [ ] No regresión en suites unit (122/122 backend + 32/32 frontend siguen passing).

#### SP: 3

---

### US-1A-OBS-01 — Sentry + observability stack end-to-end (errors + traces + logs aggregation)

**Épica**: EP-1A-01 / EP-1A-08 ([ADR-019 + ADR-047](architecture-mt-pricing-mdm-phase1.md))
**Como** TI MT + DevOps + on-call
**Quiero** stack completo de observabilidad funcionando end-to-end (Sentry errors + tracing OpenTelemetry + logs aggregation Better Stack)
**Para** detectar y diagnosticar incidentes en prod en < 5 min, cumplir con NFR-13 (observability) y SLOs definidos en ADR-052.

#### Contexto
**Deuda crítica para cutover Hetzner**. ADR-019 firmó Sentry SaaS (region EU) + Better Stack para logs. ADR-047 firmó OpenTelemetry traces. S0-S4 dejaron skeleton (`sentry_sdk.init`) pero sin tracing real, sin scrubbing PII consistente, sin sampling rates configurados, sin breadcrumbs estructurados, sin alertas configuradas.

S5 cierra: (a) Sentry FastAPI integration con tracing 10% sample + scrubbing PII server-side, (b) Celery integration con same DSN + tags `worker_name`, (c) Better Stack source token wiring + log forwarding desde containers via Vector o Fluentbit, (d) alertas SEV1/SEV2/SEV3 según ADR-052 SLOs (availability `/health/ready` < 99.5%, approval latency p95 > 24h, recálculo p95 > 60s), (e) dashboards: cost tracker (US-1A-09-08), match_decisions stream, audit events stream.

#### Criterios de aceptación
1. **Dado** un endpoint que lanza `RuntimeError` **Cuando** se ejecuta en staging Hetzner **Entonces** Sentry captura con stacktrace + breadcrumbs + tags (`environment=staging`, `service=mt-pricing-backend`).
2. **Dado** un request cualquiera **Cuando** se procesa **Entonces** trace OpenTelemetry generado con spans `http.server.request → service.* → db.query` con duración + tags. Sample rate 10% en staging, 100% en errors.
3. **Dado** un PII en payload (e.g. email) **Cuando** Sentry lo captura **Entonces** scrubbing server-side enmascara según `before_send_filter`.
4. **Dado** logs structured de FastAPI + Celery **Cuando** containers escriben stdout **Entonces** Vector/Fluentbit envía a Better Stack con parsing JSON + tags estandarizados.
5. **Dado** SLO availability `/health/ready` **Cuando** error rate excede 0.5% en 5 min **Entonces** Sentry alert SEV1 + Slack `#mt-alerts` + Better Stack on-call escalation.
6. **Dado** un job Celery que falla **Cuando** ocurre **Entonces** Sentry tag `task_name`, `task_id`, `retry_count` + breadcrumb.
7. **Dado** un dashboard Better Stack `MT Pricing — Production overview` **Cuando** se carga **Entonces** muestra: req/s, p95 latency, error rate, cost LLM today, match_decisions today, audit events today.

#### Notas técnicas
- `mt-pricing-backend/app/observability/sentry.py` con `init_sentry()` + `before_send_filter` scrubbing.
- `mt-pricing-backend/app/observability/tracing.py` con OpenTelemetry FastAPI + SQLAlchemy + Celery instrumentation.
- `mt-pricing-frontend/lib/observability/sentry.ts` con browser SDK + replay sample 1%.
- `infra/observability/vector.toml` config para forwarding logs Docker → Better Stack.
- Env vars: `SENTRY_DSN_BACKEND`, `SENTRY_DSN_FRONTEND`, `BETTER_STACK_SOURCE_TOKEN`, `OTEL_EXPORTER_OTLP_ENDPOINT`.
- TODO ADR-077 "Observability operating runbook" — alert tier matrix, dashboard catalog, cost ceiling Sentry/Better Stack, on-call rotation policy.

#### Archivos esperados
- `mt-pricing-backend/app/observability/sentry.py`
- `mt-pricing-backend/app/observability/tracing.py`
- `mt-pricing-backend/app/main.py` (integración init)
- `mt-pricing-frontend/lib/observability/sentry.ts`
- `infra/observability/vector.toml`
- `infra/observability/dashboards/{mt-pricing-overview.json, cost-tracker.json}` (Better Stack export)
- `docs/runbook-observability.md`

#### DoD
- [ ] Errores capturados visibles en Sentry EU project.
- [ ] Traces visibles en Sentry Performance + spans estructurados.
- [ ] Logs en Better Stack con parsing JSON OK.
- [ ] PII scrubbing verificado con payloads sintéticos.
- [ ] 3 alertas SEV configuradas + smoke test alarm fire.
- [ ] ADR-077 firmado.
- [ ] Smoke en staging Hetzner durante 24h sin gaps.

#### SP: 5

---

### US-1A-IAC-01 — Hetzner deploy IaC vía Terraform + Doppler secrets vault wiring

**Épica**: EP-1A-01
**Como** DevOps + TI MT
**Quiero** infraestructura Hetzner declarativa con Terraform + secrets centralizados en Doppler
**Para** que el deploy sea reproducible, auditado, rollback-friendly y disconnected del laptop de Pablo (R-050 bus factor mitigation).

#### Contexto
`infra/terraform/*` ya tiene scaffold de S0 (modules `hetzner-server`, `cloudflare-zone`, `caddy-config`) pero sin wiring real: backend state local en lugar de remote, sin secrets vault Doppler, sin docker-compose deploy reproducible. S5 cierra: state remoto en Terraform Cloud o S3-compatible (Backblaze B2 EU), Doppler workspace MT con secrets seedeados, scripts de bootstrap que provisiona server + instala docker + clona repo + ejecuta `docker compose up -d` con `.env` pulled de Doppler CLI.

Local-only Docker dev (memoria proyecto) sigue intacto: S5 IaC sólo aplica a staging Hetzner, dev developer sigue con `docker-compose.dev.yml` + `.env.local`.

#### Criterios de aceptación
1. **Dado** `terraform apply` con módulo `hetzner-server` **Cuando** se ejecuta **Entonces** provisiona 1× CX31 server (api/web), 1× CX21 worker, instala Docker + Caddy + cloud-init básico.
2. **Dado** `terraform apply` con módulo `cloudflare-zone` **Cuando** se ejecuta **Entonces** crea zone `app.mtme.ae` con DNS A record + SSL flexible + WAF managed rules + rate limiting básico (ADR-054).
3. **Dado** Doppler config `mt_pricing_staging` **Cuando** se consulta vía CLI `doppler secrets get` **Entonces** retorna todos los secrets (DB url, JWT, Bright Data, Gemini, OpenAI, SP-API, Sentry DSN, AWS).
4. **Dado** un script `scripts/deploy-staging.sh` **Cuando** se ejecuta con `doppler run` **Entonces** SSH al Hetzner server, pull repo, `docker compose pull`, `docker compose up -d` con `.env` inyectado.
5. **Dado** un rollback necesario **Cuando** se ejecuta `scripts/rollback-staging.sh <previous_image_tag>` **Entonces** cambia tag en `docker-compose.yml`, restart containers en < 2 min.
6. **Dado** state remoto en Backblaze B2 **Cuando** un dev distinto corre `terraform plan` **Entonces** ve el estado actualizado (no diff porque "state local").
7. **Dado** secrets en Doppler **Cuando** rotan un secret **Cuando** containers reciben la nueva versión via `doppler run --watch` o redeploy en < 5 min.

#### Notas técnicas
- `infra/terraform/main.tf`, `variables.tf`, `outputs.tf`.
- `infra/terraform/modules/{hetzner-server, cloudflare-zone, caddy-config}/`.
- `infra/terraform/backend.tf` con backend `s3` apuntando a Backblaze B2 EU.
- `scripts/deploy-staging.sh`, `scripts/rollback-staging.sh`, `scripts/bootstrap-server.sh`.
- Doppler secret naming convention: `MT_<DOMAIN>_<NAME>` (e.g. `MT_DB_URL`, `MT_BRIGHT_DATA_API_KEY`).
- TODO ADR-078 "IaC + secrets management strategy" — Terraform state location, Doppler workspace structure, rotation policy, disaster recovery (ADR-051 keys custodia dual BR + MT).

#### Archivos esperados
- `infra/terraform/main.tf`
- `infra/terraform/modules/hetzner-server/{main.tf, variables.tf, outputs.tf}`
- `infra/terraform/modules/cloudflare-zone/*`
- `infra/terraform/modules/caddy-config/*`
- `infra/terraform/backend.tf`
- `scripts/deploy-staging.sh`
- `scripts/rollback-staging.sh`
- `scripts/bootstrap-server.sh`
- `docs/runbook-deploy-hetzner.md`

#### DoD
- [ ] `terraform apply` provisiona staging desde cero en < 30 min.
- [ ] Doppler secrets accessible via CLI desde laptop dev y desde Hetzner box.
- [ ] Rollback verificado con cambio de tag.
- [ ] State remoto Backblaze B2 con encryption + versioning.
- [ ] ADR-078 firmado.
- [ ] Smoke deploy completo en staging.

#### SP: 5

---

### US-1A-CICD-01 — CI/CD pipeline real (tests → build images → push registry → deploy staging)

**Épica**: EP-1A-01
**Como** dev BR + TI MT
**Quiero** pipeline GitHub Actions que ejecute tests + build images + push registry + deploy staging en cada merge a `main`
**Para** que cada cambio merged genere un release reproducible en staging en < 15 min sin intervención manual.

#### Contexto
S0-S4 dejaron CI básico (lint + typecheck + tests) pero sin build de imágenes Docker, sin registry push, sin deploy automatizado. S5 cierra: workflow `release.yml` que (a) corre full test suite + integration tests con pgvector (después de US-1A-INFRA-01), (b) build images backend + frontend + worker con tag `git_sha` + `latest`, (c) push a registry (GitHub Container Registry o Docker Hub MT), (d) trigger deploy via SSH usando `scripts/deploy-staging.sh` (S5 US-1A-IAC-01).

Stages: PR → preview deploy en branch (opcional, behind flag); main merge → staging auto deploy; tag `v*` → production manual approval.

#### Criterios de aceptación
1. **Dado** un PR **Cuando** se abre **Entonces** GitHub Actions corre `lint + typecheck + test:unit + test:integration` con pgvector container; falla bloquea merge.
2. **Dado** merge a `main` **Cuando** ocurre **Entonces** workflow `release.yml` (a) corre tests, (b) build images backend/frontend/worker con tag `${git_sha}` + `staging`, (c) push a `ghcr.io/br-innovation/mt-pricing-*`, (d) trigger SSH deploy a Hetzner staging.
3. **Dado** un deploy fallido (e.g. healthcheck timeout) **Cuando** ocurre **Entonces** workflow rollback automático al tag previo + Slack alert SEV2 + GitHub Issue creado.
4. **Dado** tag `v0.5.0` push **Cuando** ocurre **Entonces** workflow `production.yml` requiere manual approval (environment protection rule) + después deploy a prod.
5. **Dado** secrets necesarios (Doppler service token, SSH key) **Cuando** workflow corre **Entonces** los obtiene de GitHub Encrypted Secrets sin exponerlos en logs.
6. **Dado** test coverage delta **Cuando** PR se ejecuta **Entonces** GitHub Action comenta con coverage diff + fail si decrece > 2 %.
7. **Dado** un image build **Cuando** se ejecuta **Entonces** corre Trivy scan + cosign sign (ADR-051 supply chain) + SBOM CycloneDX export.

#### Notas técnicas
- `.github/workflows/test.yml` (PR-triggered).
- `.github/workflows/release.yml` (main-triggered).
- `.github/workflows/production.yml` (tag-triggered).
- `.github/workflows/security-scan.yml` (Trivy + gitleaks + npm audit + pip-audit + cosign).
- Deploy step usa `appleboy/ssh-action` con private key de Doppler.
- Docker images multi-stage: `Dockerfile.backend`, `Dockerfile.frontend`, `Dockerfile.worker` ya existen (S2). Verificar buildx caching habilitado.
- TODO documentar en `docs/runbook-cicd.md` el flujo completo + troubleshooting.

#### Archivos esperados
- `.github/workflows/test.yml`
- `.github/workflows/release.yml`
- `.github/workflows/production.yml`
- `.github/workflows/security-scan.yml`
- `mt-pricing-backend/Dockerfile.backend` (verificar/actualizar)
- `mt-pricing-frontend/Dockerfile.frontend` (verificar)
- `docs/runbook-cicd.md`

#### DoD
- [ ] PR triggers tests en < 8 min.
- [ ] Main merge triggers full release pipeline en < 15 min wall-clock.
- [ ] Rollback automático verificado con deploy fallido sintético.
- [ ] Coverage report en PR comments.
- [ ] Trivy + cosign verificados.
- [ ] Documentación runbook completa.

#### SP: 5

---

### US-1A-SEC-01 — Rate limiting + WAF Cloudflare (ADR-054)

**Épica**: EP-1A-07
**Como** TI MT + security
**Quiero** rate limiting + WAF managed rules en Cloudflare delante de Caddy/FastAPI
**Para** mitigar brute force (R-023), DDoS, scraping abuse, y SQL injection bypass (defense-in-depth).

#### Contexto
ADR-054 firmó Cloudflare como WAF. S5 implementa: (a) rate limiting por IP en endpoints `/auth/*` (5 req/min con lockout 15 min), `/api/*` (100 req/min sustained, burst 200), (b) WAF managed rules OWASP Top 10 + Cloudflare Bot Management lite, (c) bot detection score → rechazo > 30 (configurable), (d) geo-fencing opcional (allow UAE + EU + US, block CN/RU pesados).

Implementación 100% via Terraform módulo `cloudflare-zone` (US-1A-IAC-01) — declarativo, replicable.

#### Criterios de aceptación
1. **Dado** un cliente que excede 5 req/min en `/auth/login` **Cuando** intenta el 6º **Entonces** Cloudflare retorna 429 con `Retry-After: 60`. Después de 15 min lockout, normalidad.
2. **Dado** un payload con SQLi pattern (e.g. `' OR 1=1 --`) **Cuando** llega a Cloudflare **Entonces** WAF bloquea con 403. Sentry alert tag `cf_waf_block`.
3. **Dado** un bot score > 30 **Cuando** Cloudflare detecta **Entonces** challenge JS / CAPTCHA antes de pasar a Caddy.
4. **Dado** geo-fencing config `allow=[AE, EU-*, US-*]` **Cuando** request desde IP china **Entonces** bloqueado con 403.
5. **Dado** dashboard Cloudflare **Cuando** se carga **Entonces** muestra: req total, blocked req, top countries, top URIs, threat score distribution.
6. **Dado** flag `MT_WAF_PERMISSIVE=true` **Cuando** está activo **Entonces** WAF en log-only mode (no bloquea, sólo registra) — útil tuning fase inicial.
7. **Dado** un usuario internal MT con IP fija **Cuando** se whitelist en Cloudflare **Entonces** rate limits no aplican.

#### Notas técnicas
- `infra/terraform/modules/cloudflare-zone/waf.tf` con resources `cloudflare_rate_limit`, `cloudflare_ruleset` (managed rules), `cloudflare_filter`.
- `infra/terraform/modules/cloudflare-zone/geo.tf` con expressions geo-based.
- TODO ADR-079 "WAF + rate limiting policy" — documentar matriz endpoint × rate limit, exceptions, monitoring strategy.
- Caddy config (S2) ya tiene `request_body_size_limit` para defense en profundidad.
- slowapi (S0) en FastAPI sigue activo como capa app-level (5/min auth endpoints).

#### Archivos esperados
- `infra/terraform/modules/cloudflare-zone/waf.tf`
- `infra/terraform/modules/cloudflare-zone/rate_limits.tf`
- `infra/terraform/modules/cloudflare-zone/geo.tf`
- `docs/runbook-waf-tuning.md`

#### DoD
- [ ] Rate limit verificado con load test sintético (`hey` o `wrk`).
- [ ] WAF bloquea SQLi/XSS payloads conocidos.
- [ ] Geo-fencing verificado (VPN test desde región blocked).
- [ ] ADR-079 firmado.
- [ ] Whitelist MT internal IPs configurada.

#### SP: 3

---

### US-1A-09-07 — Calibrator isotonic training pipeline + golden labels feedback loop

**Épica**: EP-1A-09 / EP-RND-01
**Como** R&D Champion
**Quiero** pipeline reproducible que reentrena el isotonic calibrator (US-1A-09-06 S4) sobre dataset etiquetado actualizado + feedback humano de UI Tinder (S6+) + script CLI para promoción de versiones
**Para** que el calibrator drifta-recovery sea automatizable mensualmente y entrenamientos sean auditables.

#### Contexto
S4 entregó isotonic calibrator inicial (`competitor_calibrators` v1) con dataset ≥ 50 pares. S5 entrega: (a) script `scripts/train_calibrator.py` con CLI args (`--dataset-path`, `--version`, `--promote-active`), (b) feedback loop que recoge labels desde `match_decisions.human_verdict` (cuando UI Tinder S6 esté), (c) métricas comparativas (Brier, ECE, AUC) entre versión actual y candidata, (d) política de promoción: nueva versión activa solo si ECE mejora ≥ 1% absoluto sin degradar AUC > 2%.

Persistir entrenamientos en `competitor_calibrators` con version + métricas + dataset hash + fitted_at; modelo serializado en Supabase Storage `comparator/calibrators/v{n}.pkl`.

#### Criterios de aceptación
1. **Dado** dataset path `data/golden_labels_v2.csv` con 100 pares **Cuando** ejecuto `python scripts/train_calibrator.py --dataset-path ... --version v2` **Entonces** entrena, persiste artefacto + métricas en `competitor_calibrators`.
2. **Dado** un entrenamiento exitoso con ECE 4.2% (mejora vs v1 5.8%) **Cuando** ejecuto `--promote-active` **Entonces** flippea `active=true` para v2 + `active=false` para v1.
3. **Dado** métricas v2 con ECE 6.5% (peor que v1) **Cuando** ejecuto `--promote-active` **Entonces** rechaza con mensaje "ECE regression vs active version" y exit 1.
4. **Dado** UI Tinder feedback (US-RND-01-10 S6+) **Cuando** se actualiza `match_decisions.human_verdict` **Entonces** script `scripts/build_dataset_from_feedback.py` lo extrae a CSV con stratified sampling.
5. **Dado** un Celery beat job mensual **Cuando** se dispara **Entonces** ejecuta train + promote si mejora, alerta SEV3 si no mejora.
6. **Dado** un dataset hash **Cuando** ya fue usado en una versión **Entonces** script avisa "dataset_hash_already_trained" para evitar overfitting circular.

#### Notas técnicas
- `scripts/train_calibrator.py` con CLI `argparse` + sklearn IsotonicRegression.
- `scripts/build_dataset_from_feedback.py` (Python).
- `app/workers/calibrator_retrain.py` Celery task (mensual).
- Storage helper `app/services/comparator/calibrator_storage.py` para upload/download artefactos pkl.
- TODO ADR-080 "Calibrator training + promotion policy" — documentar criterios, schedule, dataset versioning, rollback.

#### Archivos esperados
- `mt-pricing-backend/scripts/train_calibrator.py`
- `mt-pricing-backend/scripts/build_dataset_from_feedback.py`
- `mt-pricing-backend/app/workers/calibrator_retrain.py`
- `mt-pricing-backend/app/services/comparator/calibrator_storage.py`
- Tests: unit + integration sobre dataset sintético.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Smoke con dataset real ≥ 100 pares (golden v2).
- [ ] ECE mejorado vs v1 reportado (o aceptado degraded mode).
- [ ] ADR-080 firmado.
- [ ] Beat job mensual configurado en `scheduler` config.
- [ ] Documentación `docs/comparator/calibrator-training.md`.

#### SP: 5

---

### US-1A-06-04-V2 — Datasheets PDF parsing real (`pdfplumber`) + `OpenAIVisionJudge` activo

**Épica**: EP-1A-06 / EP-RND-01
**Como** R&D Champion + comercial
**Quiero** que los PDFs importados (S4 US-1A-06-04) sean parseados con `pdfplumber` para extraer texto/tablas + el `OpenAIVisionJudge` activo cuando `OPENAI_API_KEY` esté disponible
**Para** que el pipeline matching disponga del contenido de fichas técnicas como evidencia auditable y el judge pueda razonar sobre datasheet + listing image.

#### Contexto
S4 entregó importer datasheets PDF + storage + UI tab. S5 cierra: (a) parser `pdfplumber` extrae texto + tablas estructuradas + screenshots de páginas → persiste en `product_datasheets.parsed_content` JSONB, (b) OCR fallback `tesseract` para PDFs escaneados (no nativos), (c) `OpenAIVisionJudge` (gpt-4o) como segundo judge complementario al Gemini (US-1A-09-06 S4), elegible via flag `JUDGE_BACKEND=openai|gemini|both` con consensus.

Cost ceiling: Vision OpenAI ~$5 per 1000 invocaciones — cap mensual $50 en S5 (fase eval).

#### Criterios de aceptación
1. **Dado** un PDF nativo `MTFT_5114.pdf` **Cuando** se procesa post-importer **Entonces** `parsed_content` tiene `{text, tables, page_screenshots}` extraído.
2. **Dado** un PDF escaneado **Cuando** se procesa **Entonces** sistema detecta y aplica tesseract OCR; flag `parse_method='ocr'` en payload.
3. **Dado** `JUDGE_BACKEND=openai` **Cuando** se invoca `judge.evaluate(sku, candidate)` **Entonces** llama `gpt-4o` con prompt audit-grade + datasheet text como context.
4. **Dado** `JUDGE_BACKEND=both` **Cuando** se invoca **Entonces** llama Gemini + OpenAI en paralelo, retorna consensus si verdict coincide, sino marca `disagreement=true` para revisión humana.
5. **Dado** `OPENAI_API_KEY=null` **Cuando** se intenta invoke OpenAI **Entonces** sistema falla gracioso a Gemini sólo + log warning.
6. **Dado** cap mensual $50 hit **Cuando** se invoca OpenAI **Entonces** circuit breaker abre + fallback Gemini + Sentry SEV2.
7. **Dado** un dataset con datasheets parseadas **Cuando** comparator pipeline corre **Entonces** judge incluye `datasheet_evidence` en rationale (e.g. "datasheet página 2 confirma DN50 PN16").

#### Notas técnicas
- `mt-pricing-backend/app/importers/datasheets_parser_v2.py` con pdfplumber + tesseract fallback.
- `mt-pricing-backend/app/services/comparator/judge_openai.py` con `OpenAIVisionJudge`.
- `mt-pricing-backend/app/services/comparator/judge_dispatcher.py` con backend selection logic.
- Migración Alembic 0026: extiende `product_datasheets` con `parsed_content` JSONB + `parse_method` ENUM.
- TODO ADR-081 "Vision judge backend strategy" — documentar OpenAI vs Gemini cost/latency/quality tradeoffs, consensus algorithm, fallback.
- libs: `pdfplumber>=0.11`, `pytesseract>=0.3.10`, `openai>=1.40`.

#### Archivos esperados
- `mt-pricing-backend/app/importers/datasheets_parser_v2.py`
- `mt-pricing-backend/app/services/comparator/judge_openai.py`
- `mt-pricing-backend/app/services/comparator/judge_dispatcher.py`
- `mt-pricing-backend/alembic/versions/0026_extend_product_datasheets_parsed_content.py`
- Tests: unit + integration con PDFs reales fixtures.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] 5 PDFs reales parseados (mix nativos + escaneados).
- [ ] Smoke con OpenAI judge + Gemini judge + consensus over 3 pares.
- [ ] ADR-081 firmado.
- [ ] Cost dashboard tracking OpenAI calls.
- [ ] Cap mensual configurado + verified.

#### SP: 5

---

### US-1A-07-04-AR — i18n AR completion (revisar pantallas con texto faltante en árabe)

**Épica**: EP-1A-07
**Como** Translation owner AR + Frontend dev
**Quiero** auditar todas las pantallas frontend (S1-S4) por texto faltante en árabe + completar el catálogo i18n AR
**Para** que el toggle AR en UI muestre todas las pantallas correctamente con dirección RTL + traducciones aprobadas (gate Fase 2 storefront B2C).

#### Contexto
S0 firmó Q-18 (AR sólo data en Fase 1, UI optional). S5 cierra: (a) script audit `scripts/i18n_audit.py` que detecta keys EN/ES sin AR equivalente en `messages/ar/*.json`, (b) traduction owner (interno MT España AR-fluent o vendor externo) firma 100% del catálogo, (c) RTL handling validado en componentes críticos (Pantalla 2 productos, Pantalla 4 SKU detail, Pantalla 6 recálculo, Pantalla 10 importer, Pantalla 11 audit), (d) tests E2E en AR locale para los 4 flows críticos.

#### Criterios de aceptación
1. **Dado** `pnpm i18n:audit` **Cuando** corre **Entonces** reporta keys missing AR + percentage coverage (target 100%).
2. **Dado** un usuario con locale AR **Cuando** carga `/products` **Entonces** ve todos los textos en árabe + RTL aplicado.
3. **Dado** un componente con texto literal hardcoded (no via t()) **Cuando** corre el audit **Entonces** falla con lista de strings.
4. **Dado** el catálogo AR completo **Cuando** translation owner firma `docs/i18n/ar-approval.md` **Entonces** PR puede mergear con label `i18n-ar-approved`.
5. **Dado** smoke test E2E con Playwright en AR locale **Cuando** corre **Entonces** 4 flows críticos pasan (login → products → SKU detail → recálculo → audit tab).
6. **Dado** RTL CSS issues (e.g. iconos espejados) **Cuando** se detectan **Entonces** se corrigen con `dir="rtl"` + Tailwind logical properties.

#### Notas técnicas
- `mt-pricing-frontend/scripts/i18n-audit.ts`.
- `mt-pricing-frontend/messages/ar/*.json` (completar todos los namespaces existentes: `auth`, `catalog`, `pricing`, `imports`, `audit`, `suppliers`, `match`).
- Componentes RTL: `next-intl` ya soporta; verificar que componentes shadcn no rompen en RTL.
- TODO `docs/i18n/ar-approval.md` con firma owner.

#### Archivos esperados
- `mt-pricing-frontend/scripts/i18n-audit.ts`
- `mt-pricing-frontend/messages/ar/*.json` (completar)
- `mt-pricing-frontend/tests/e2e/ar-locale.spec.ts`
- `docs/i18n/ar-approval.md`

#### DoD
- [ ] 100% keys AR coverage.
- [ ] Translation owner firma ar-approval.md.
- [ ] 4 flows E2E AR pasan.
- [ ] RTL visual QA OK (psierra firma).
- [ ] Audit script integrated en CI (fail si coverage < 100%).

#### SP: 3

---

### US-1B-01-07 — Pricing engine bulk-recalc nocturno (Celery beat task + audit batch)

**Épica**: EP-1B-01
**Como** Comercial + TI MT
**Quiero** un job nocturno que recalcule precios automáticamente para todos los SKUs activos × canales × esquemas
**Para** que cambios FX nocturnos / cost adjustments del día propaguen sin necesidad de trigger manual y para mantener `prices` siempre actualizado para reportes.

#### Contexto
S4 entregó `POST /prices/recalculate` manual (US-1B-01-04). S5 añade el beat job: `recalculate_all_prices_nightly_task` corriendo a 02:30 UTC (06:30 GST), procesa 224 SKUs × 5 canales × 4 esquemas = ~4480 propuestas, persiste batch `audit_events(action='nightly_recalc_batch', summary={total, succeeded, failed, fx_rate_id})`, alerta si > 5% failed.

Mutex con manual recalc (US-1B-01-04 mutex Redis): si manual está corriendo, beat espera o skipea con log.

#### Criterios de aceptación
1. **Dado** `celery beat` schedule a 02:30 UTC **Cuando** llega la hora **Entonces** worker dispara `recalculate_all_prices_nightly_task`.
2. **Dado** el job corriendo **Cuando** procesa todos los SKUs **Entonces** completa < 5 min para 4480 propuestas (NFR-02 modular).
3. **Dado** un SKU con coste missing **Cuando** se procesa **Entonces** queda en `failed` con `error_code='cost_missing_for_scheme'`, no aborta el job.
4. **Dado** > 5% failed **Cuando** completa **Entonces** Sentry alert SEV2 + Slack `#mt-alerts` con resumen.
5. **Dado** un manual recalc en curso **Cuando** beat job arranca **Entonces** detecta mutex Redis activo, skipea con log "manual recalc in progress, deferred".
6. **Dado** el job completa **Cuando** se persiste **Entonces** `audit_events(action='nightly_recalc_batch', payload_after={...summary})` queda registrado.
7. **Dado** un endpoint `GET /admin/jobs/last-run/recalculate_all_prices_nightly` **Cuando** se consulta **Entonces** retorna last execution status + duration + failed count.

#### Notas técnicas
- `mt-pricing-backend/app/workers/recalculate_nightly.py` Celery beat task.
- `mt-pricing-backend/app/scheduler/seeds.py` extender con nueva entrada `recalculate_all_prices_nightly` cron `30 2 * * *`.
- Reusa `app/services/pricing/recalc_service.py` (S4) con flag `source='nightly_beat'`.
- TODO añadir métrica Sentry `nightly_recalc.duration_seconds` y `nightly_recalc.failed_pct`.

#### Archivos esperados
- `mt-pricing-backend/app/workers/recalculate_nightly.py`
- `mt-pricing-backend/app/scheduler/seeds.py` (modificación)
- Tests: unit + integration con Celery eager mode.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Smoke con beat job ejecutado en staging Hetzner durante 1 noche real.
- [ ] Audit batch event persistido y verificable.
- [ ] Mutex coexistence con manual recalc verificada.
- [ ] Métricas Sentry visibles.

#### SP: 3

---

### US-1A-DEV-01 — OpenAPI spec consolidation + frontend types regen automatizado

**Épica**: EP-1A-01
**Como** dev BR + frontend
**Quiero** un script `pnpm openapi:gen` que consolide la spec OpenAPI + regen tipos TypeScript del frontend automáticamente en cada PR
**Para** que cambios de API se reflejen instantáneamente en el cliente sin drift backend ↔ frontend.

#### Contexto
`openapi:gen` script ya existe en `package.json` (S0) pero corre on-demand y a veces queda desincronizado. S5 cierra: (a) GitHub Action hook que detecta cambios en `mt-pricing-backend/app/api/**` o `app/schemas/**` y dispara regen, (b) PR comment con diff de tipos generados, (c) failed CI si dev forgot regen y types están stale, (d) consolidate openapi.yaml a partir de FastAPI runtime spec (no manual edits).

#### Criterios de aceptación
1. **Dado** `pnpm openapi:gen` **Cuando** se ejecuta en root **Entonces** (a) starts backend en mode CI, (b) curl `/openapi.json`, (c) regen `mt-pricing-frontend/lib/api/types.ts` via `openapi-typescript`.
2. **Dado** un PR que modifica `app/schemas/pricing.py` **Cuando** se abre **Entonces** GitHub Action detecta cambio + corre `openapi:gen` + falla si types frontend están out-of-sync.
3. **Dado** types regen **Cuando** ocurre **Entonces** PR comment muestra diff `+ added type X, - removed type Y`.
4. **Dado** types desactualizados **Cuando** dev hace local merge sin regen **Entonces** CI falla con mensaje "run pnpm openapi:gen and commit".
5. **Dado** types regenerados **Cuando** dev commits **Entonces** CI pasa sin regenerar internamente (idempotent).

#### Notas técnicas
- `mt-pricing-frontend/scripts/openapi-gen.sh` con steps backend up + curl + openapi-typescript.
- `.github/workflows/openapi-sync.yml`.
- `mt-pricing-frontend/lib/api/types.ts` (generado, en gitignore opcional o committed con CI check).
- TODO documentar workflow en `docs/dev-onboarding.md`.

#### Archivos esperados
- `mt-pricing-frontend/scripts/openapi-gen.sh`
- `.github/workflows/openapi-sync.yml`
- `package.json` scripts root extender
- `docs/dev-onboarding.md` (update sección OpenAPI)

#### DoD
- [ ] Script funciona end-to-end en local + CI.
- [ ] PR comment con diff types funcional.
- [ ] CI fail si dev forgot regen.
- [ ] Documentación actualizada.

#### SP: 3

---

### US-RND-01-12 — BR PMO integration hooks (notificación eventos clave hacia Fase 2)

**Épica**: EP-RND-01
**Como** R&D arquitect + BR PMO Fase 2 owner
**Quiero** abstracciones backend `PMOEventBus` con adapter por defecto `NoOpAdapter` y stub `SlackAdapter` / `WebhookAdapter` para Fase 2
**Para** que eventos clave del MT pricing (price_approved, match_auto_decided, fx_change_published, audit_critical) se puedan publicar hacia BR PMO en Fase 2 sin refactor del core.

#### Contexto
Carry-over Fase 2. Patrón **outbox** + EventBus con adapters. S5 entrega scaffold sin habilitar webhooks reales (defer Fase 2). En S5: tabla `pmo_events_outbox` con events draft, EventBus interface, NoOp/Slack stubs, suite tests verificando interface.

#### Criterios de aceptación
1. **Dado** la interfaz `PMOEventBus` **Cuando** consulto **Entonces** existe con métodos `publish(event_name, payload)`, `register_listener(event_name, callback)`.
2. **Dado** `PMO_EVENT_BUS_ADAPTER='noop'` (default) **Cuando** se llama `publish` **Entonces** no-op, registra solo en log debug.
3. **Dado** un price approved **Cuando** workflow termina **Entonces** se llama `bus.publish('price_approved', {sku, price_aed, channel, scheme, approver})`.
4. **Dado** la tabla `pmo_events_outbox` **Cuando** se inserta **Entonces** queda con `status='pending'` y un Celery worker (post-Fase-2) lo procesará.
5. **Dado** flag `PMO_EVENT_BUS_ADAPTER='slack_stub'` **Cuando** se llama `publish` **Entonces** raise `NotImplementedError("Activated in Phase 2")`.
6. **Dado** la migración 0027 **Cuando** corre **Entonces** crea `pmo_events_outbox` (id, event_name, payload JSONB, status, created_at, processed_at).

#### Notas técnicas
- `app/services/pmo/event_bus.py` Protocol.
- `app/services/pmo/adapters/{noop.py, slack_stub.py, webhook_stub.py}`.
- Migración Alembic 0027.
- TODO ADR-082 "PMO event bus Fase 2 readiness" — documentar interface, retry policy, guarantees.

#### Archivos esperados
- `mt-pricing-backend/app/services/pmo/event_bus.py`
- `mt-pricing-backend/app/services/pmo/adapters/{noop.py, slack_stub.py, webhook_stub.py}`
- `mt-pricing-backend/alembic/versions/0027_create_pmo_events_outbox.py`
- `mt-pricing-backend/app/db/models/pmo_event_outbox.py`
- Tests: unit + integration interface compliance.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Interface tests passing.
- [ ] ADR-082 firmado.
- [ ] Workflow approve_price (S6) tiene hook listo para llamar `bus.publish`.
- [ ] Migración up/down testeada.

#### SP: 3

---

## 5. Plan de ejecución multi-agente

Patrón S1/S2/S3/S4 demostró que 4-5 agentes paralelos con dominios disjuntos sostienen velocity de ~50 SP en una iteración. Para S5 mantenemos 5 agentes con dominios reorganizados según naturaleza de las stories (más DevOps + Security en S5).

### Agente A — Backend Data + RBAC + RLS + Security app-layer (~13 SP)

**Stories**: US-1A-07-04-RBAC (5), US-1A-INFRA-01 (3), US-1A-SEC-01 (3 — config Cloudflare via Terraform pero policies app-side coordinadas con E), pgvector related test fixtures.

**Paths exclusivos**:
- `mt-pricing-backend/alembic/versions/0025_*`
- `mt-pricing-backend/app/services/auth/permissions.py`
- `mt-pricing-backend/app/api/v1/admin/permissions.py`
- `mt-pricing-backend/app/db/models/role_permission.py`
- `mt-pricing-backend/tests/conftest.py` (pgvector fix)
- `mt-pricing-backend/tests/integration/test_audit_triggers_extended.py` (verify)
- `mt-pricing-backend/tests/integration/test_rls_finas.py` (verify)
- `infra/supabase/migrations/0025_role_permissions.sql`

**No toca**: comparator/, channels/, frontend, IaC infra/terraform.

### Agente B — Backend Pricing operations + Datasheets V2 + OpenAPI sync (~11 SP)

**Stories**: US-1B-01-07 (3), US-1A-06-04-V2 (5), US-1A-DEV-01 backend parte (3 — script + workflow).

**Paths exclusivos**:
- `mt-pricing-backend/app/workers/recalculate_nightly.py`
- `mt-pricing-backend/app/scheduler/seeds.py`
- `mt-pricing-backend/app/importers/datasheets_parser_v2.py`
- `mt-pricing-backend/app/services/comparator/judge_openai.py`
- `mt-pricing-backend/app/services/comparator/judge_dispatcher.py`
- `mt-pricing-backend/alembic/versions/0026_*`
- `mt-pricing-frontend/scripts/openapi-gen.sh`
- `.github/workflows/openapi-sync.yml`

**No toca**: RBAC schemas, infra/terraform, frontend UI work.

### Agente C — Comparator activación red real + Calibrator training (~10 SP)

**Stories**: US-1A-09-08 (5), US-1A-09-07 (5).

**Paths exclusivos**:
- `mt-pricing-backend/app/services/feature_flags.py`
- `mt-pricing-backend/app/api/v1/admin/feature_flags.py`
- `mt-pricing-backend/app/services/cost_tracker.py`
- `mt-pricing-backend/alembic/versions/0024_*`
- `mt-pricing-backend/app/db/models/feature_flag_audit.py`
- `mt-pricing-backend/scripts/train_calibrator.py`
- `mt-pricing-backend/scripts/build_dataset_from_feedback.py`
- `mt-pricing-backend/app/workers/calibrator_retrain.py`
- `mt-pricing-backend/app/services/comparator/calibrator_storage.py`

**No toca**: pricing engine, datasheets, IaC, frontend, RBAC.

### Agente D — Frontend (i18n AR + tipos OpenAPI + Cost dashboard UI) (~6 SP)

**Stories**: US-1A-07-04-AR (3), US-1A-DEV-01 frontend parte (~1 SP partial), Cost dashboard UI consume cost_tracker (S4 carry-over visible — share Agent E observability dashboards).

**Paths exclusivos**:
- `mt-pricing-frontend/scripts/i18n-audit.ts`
- `mt-pricing-frontend/messages/ar/*.json`
- `mt-pricing-frontend/tests/e2e/ar-locale.spec.ts`
- `mt-pricing-frontend/lib/api/types.ts` (generado, no edit manual)
- `mt-pricing-frontend/components/admin/feature-flags-page.tsx` (consume US-1A-09-08 endpoints)
- `mt-pricing-frontend/components/admin/cost-dashboard.tsx`
- `mt-pricing-frontend/messages/{es,en}/admin.json` (namespaces nuevos)

**No toca**: backend, IaC, comparator adapters.

### Agente E — DevOps + Observability + IaC + CI/CD + R&D scaffold (~16 SP)

**Stories**: US-1A-OBS-01 (5), US-1A-IAC-01 (5), US-1A-CICD-01 (5), US-RND-01-12 (3).

**Paths exclusivos**:
- `mt-pricing-backend/app/observability/sentry.py`
- `mt-pricing-backend/app/observability/tracing.py`
- `mt-pricing-frontend/lib/observability/sentry.ts`
- `infra/observability/**`
- `infra/terraform/**`
- `scripts/{deploy-staging.sh, rollback-staging.sh, bootstrap-server.sh}`
- `.github/workflows/{test.yml, release.yml, production.yml, security-scan.yml}`
- `mt-pricing-backend/app/services/pmo/**`
- `mt-pricing-backend/alembic/versions/0027_*`
- `mt-pricing-backend/app/db/models/pmo_event_outbox.py`
- `docs/runbook-{observability, deploy-hetzner, cicd, waf-tuning}.md`

**No toca**: comparator core, pricing engine, RBAC seeds, datasheets parsers, frontend UI work (excepto sentry browser SDK).

Patrón S2/S3/S4: corre tests en master integrado al final, detecta gaps tipo schema drift / config mismatch, fixes secundarios, persiste deuda técnica si Agente C se atasca con activación red real (Q-NEW-S3) o Agente E con creds Doppler.

### Conflictos previstos (mitigación)

- `mt-pricing-backend/app/main.py`: Agente E modifica para `init_sentry()` + `init_tracing()`. **Solución**: módulo `observability/__init__.py` con función `setup_observability(app)` que se invoca una sola vez; otros agentes no editan `main.py`.
- `mt-pricing-backend/alembic/versions/`: A usa 0025, C usa 0024, B usa 0026, E usa 0027. **Solución**: lock vía PR título + Agente E verifica orden + pre-commit hook `alembic check`.
- `infra/terraform/modules/cloudflare-zone/`: Agente E (IaC base) y Agente A (WAF rules apuntando a config). **Solución**: A entrega `policies.tf` como sub-módulo dentro de `cloudflare-zone/`, E hace merge final.
- `package.json` scripts root: Agente B añade openapi:gen, D consume. **Solución**: B edita, D solo consume (no conflicto).
- `messages/ar/*.json`: solo Agente D edita. **Cero conflicto**.
- `mt-pricing-backend/app/db/models/`: A (role_permission), B (—), C (feature_flag_audit), E (pmo_event_outbox). **Sin overlap**.
- `.github/workflows/`: solo Agente E + Agente B (openapi-sync). **Solución**: B y E coordinan archivos (separación clara).
- `docs/`: cada agente sus propios runbooks; psierra revisa cross-runbook.

## 6. Riesgos y bloqueos

| ID | Riesgo | Severidad | Probabilidad | Mitigación |
|----|--------|-----------|--------------|------------|
| R-S5-01 | **Q-NEW-S3 firma legal** sigue abierta — bloqueante para US-1A-09-08 activación real | Crítica | Alta | Champion + Legal MT firma antes day 1 sprint. Sin firma, US-1A-09-08 entrega infraestructura del flag pero `MT_LIVE_NETWORK=false` queda lock con doc explicación. (-2 SP). Carry-over de R-S4-01. |
| R-S5-02 | **Credenciales SP-API + AWS Role** si no llegaron en S4 — bloquea cierre activación red real Amazon UAE | Alta | Media | Champion + TI MT trámite ya cerrado en S4 idealmente. Si no, US-1A-09-08 funciona con Bright Data Amazon UAE pero SP-API stub. (R-S4-03 carry). |
| R-S5-03 | **OPENAI_API_KEY no provisionada** por programa MT España — bloquea US-1A-06-04-V2 OpenAI Vision | Media | Media | Pablo escala con MT España programa. Sin key, V2 entrega solo pdfplumber + Gemini (no OpenAI), -1 SP. Story sigue válida. |
| R-S5-04 | **Doppler workspace MT no provisionado** por TI MT — bloquea US-1A-IAC-01 (deploy con secrets) | Crítica | Media | TI MT trámite empieza pre-kickoff. Si no listo day 3, fallback `.env.staging` archivos cifrados con `age` (R-051 carry) — degraded pero deploya. |
| R-S5-05 | **Hetzner servers no provisionados** por TI MT — bloquea staging deploy reproducible | Crítica | Media | Champion + TI MT escala. Si no listo day 5, deploy en cuenta Hetzner BR temporal con doc `docs/runbook-temporary-staging.md`. |
| R-S5-06 | **Translation owner AR** no firma 100% del catálogo en time | Media | Alta | Pablo escala desde day 1. Si no firma, defer US-1A-07-04-AR a S6 con stretch goal. Owner: psierra. |
| R-S5-07 | **Pgvector image incompatibilidad** (testcontainers Postgres 15 ↔ pgvector image custom) | Media | Baja | Validación pre-kickoff Agente A con smoke local. Si incompatibility, fallback `apt-get install postgresql-15-pgvector` post-startup script (~30s extra setup). |
| R-S5-08 | **Cost burst Sentry / Better Stack** durante onboarding rampa | Media | Baja | Free tier verificado para Fase 1 volumen (224 SKUs); upgrade Pro alert al 80% cuota. |
| R-S5-09 | **CI pipeline lento** (>15 min) por integration tests + builds | Media | Media | Buildx caching + matrix parallelism + integration tests selectivos por changed files. Owner: Agente E. |
| R-S5-10 | **Capacidad real < 30 SP** | Alta | Media | Ver §3 priorización: defer US-RND-01-12 (-3) + US-1A-DEV-01 (-3) + US-1A-09-07 (-5) → 24 SP core. |
| R-S5-11 | **WAF false positives** bloquea legitimate traffic durante tuning | Media | Alta | Flag `MT_WAF_PERMISSIVE=true` log-only mode primera semana; análisis de logs día 7; flippea a enforce. |
| R-S5-12 | **i18n AR RTL bugs** en componentes Shadcn no testados en RTL antes | Media | Media | Smoke E2E AR locale en CI; QA visual psierra firma día 7. |
| R-S5-13 | **Activación red real cost burst** > $200/mes Bright Data + Gemini + OpenAI combined | Alta | Media | Hard caps por proveedor: Bright Data $150, Gemini $50, OpenAI $50 = $250 max. Cost dashboard alerta 80% cap. Kill-switch lista. |
| R-S5-14 | **Conflictos OpenAPI merge** entre 5 agentes editando schemas | Baja | Alta | Agente E como merger final con responsabilidad explícita. Tags YAML distintivos. |
| R-S5-15 | **Doppler service token GitHub Actions** secret leak | Baja | Baja | Token con scope mínimo (read solo `mt_pricing_staging`); rotación trimestral; gitleaks pre-commit. |

### Top 5 bloqueadores legales/técnicos

1. **Q-NEW-S3 firma legal scraping Amazon UAE / Noon UAE** (legal, R-S5-01) — bloquea activación red real US-1A-09-08. Owner: Champion + Legal MT. Deadline pre-kickoff.
2. **Credenciales SP-API + AWS Role + LWA tokens** (técnico/operacional, R-S5-02) — bloquea Amazon UAE channel mirror real. Owner: TI MT. Carry-over crítico de S4.
3. **Doppler workspace MT + Hetzner servers provisionados** (operacional/IaC, R-S5-04 + R-S5-05) — bloquea US-1A-IAC-01 + US-1A-CICD-01 deploy real. Owner: TI MT. Deadline day 3 sprint.
4. **OPENAI_API_KEY + Sentry DSN + Better Stack source token** (operacional/secrets, R-S5-03) — bloquea US-1A-06-04-V2 + US-1A-OBS-01 production. Owner: Pablo + programa MT España + TI MT.
5. **Translation owner AR firma calendario** (legal/operacional, R-S5-06) — bloquea US-1A-07-04-AR cierre. Owner: Sponsor MT (define vendor o interno). Deadline day 1.

### Decisiones humanas pendientes (kickoff S5)

1. **Q-NEW-S3 firma legal** — owner Champion + Legal MT, deadline pre-kickoff S5.
2. **Doppler workspace MT** + secrets seedeados — owner TI MT, deadline day 3.
3. **Hetzner servers provisionados** (1× api/web + 1× worker) — owner TI MT, deadline day 3.
4. **Cloudflare zone `app.mtme.ae`** delegada — owner TI MT, deadline day 3.
5. **OPENAI_API_KEY** provisionada — owner Pablo + MT España programa.
6. **Translation owner AR** designado — owner Sponsor MT.
7. **Hard cap presupuestos** Bright Data ($150) + Gemini ($50) + OpenAI ($50) — owner Champion + Sponsor.
8. **MT_LIVE_NETWORK enrollment plan** — owner Champion (10% → 50% → 100% calendario).
9. **Sentry plan & Better Stack plan** confirmados (Free tier o Pro) — owner TI MT.
10. **PR review cadence** — owner Pablo (proponer 24h SLA review S5+).

## 7. Métricas a trackear durante el sprint

- **Velocity real** (SP done) vs comprometido (35 SP).
- **Burn-down chart** diario; alarma si día 5 < 50 % done.
- **Integration tests desbloqueados**: target ≥ 24 nuevos passing al cierre (US-1A-INFRA-01).
- **Coverage delta**: ≥ 80 % en código nuevo, ≥ 85 % en RBAC + feature_flags.
- **CI pipeline duration** (PR + main): target < 15 min p95 (US-1A-CICD-01).
- **Staging deploy time** (terraform + image push + restart): target < 10 min wall-clock.
- **MT_LIVE_NETWORK enrollment** real pct si Q-NEW-S3 firmado: target 10% al cierre S5 con métricas de cost + match quality.
- **Sentry events captured** in staging: ≥ 1 error per testing flow → 100% capturado.
- **i18n AR coverage**: target 100% al cierre.
- **Calibrator ECE v2**: < 5% (target NFR-CMP) o degraded mode firmado.
- **Bulk-recalc nightly job** ejecutado al menos 3 noches consecutivas en staging sin failure rate > 5%.
- **WAF blocked requests** baseline en staging: contador para tuning.
- **Sprint goal viability**: cada miércoles, demo informal del flujo (deploy via CI/CD → Sentry visible → activar live network 10% → ver costs → triggers nocturno → verify audit batch → AR locale toggle).

## 8. Sprint 6 preview (alto nivel)

Stories candidatas (con racional):

| Story | SP | Racional |
|-------|----|----------|
| US-1B-02-01..05 (Workflow aprobación delta + bulk approve + escalation digest) | 18 | Cierra Fase 1b workflow completo |
| US-RND-01-10 (UI Tinder validación humana matching) | 13 | Permite feedback loop calibrator + ECE drift recovery |
| US-1A-07-05 (Export CSV firmado FTA) | 5 | VAT compliance entregable Q-13 deadline |
| US-RND-01-09 (Reverse image search hooks) behind flag | 5 | Fallback comparador Fase 1.5 |
| US-1A-07-06 (Dashboard SKUs atención) | 5 | Operacional MT |
| US-1B-05-04 (DR drill restore desde backup ensayado) | 5 | R-006 cierre crítico |
| US-1A-07-03-FE2 (Bulk audit export UI) | 3 | UX completa audit |
| Carry-over S5 (cualquiera defer) | 0-8 | Plan B |

**Total candidatos S6**: ~62 SP (aplicar selección a 32-40 SP realistas).

**S6 MUST**: workflow aprobación completo (US-1B-02-01..05) + UI Tinder humana (US-RND-01-10) + DR drill (US-1B-05-04) — primer demo end-to-end del programa con Comercial proponiendo + Gerente aprobando + matcher humano validando + DR plan probado.

**S7+ outlook**: cutover MT internal go-live (Fase 1b cierre) + Fase 2 kickoff (B2C scaffolding via PMO event bus US-RND-01-12).

---

## Apéndice A — Mapeo de stories del doc fuente vs S5

| Doc fuente / origen | Sprint asignado original | S5 backlog refinado | Cambio |
|---------------------|--------------------------|---------------------|--------|
| US-1A-09-08 (NUEVA — activación red real con flag) | S5 | US-1A-09-08 (S5) | Nueva derivada de US-1A-09-03 + US-1A-09-05 (S4) |
| US-1A-07-04-RBAC (NUEVA — permisos dedicados) | S5 | US-1A-07-04-RBAC (S5) | Cierre S4 seedeo parcial |
| US-1A-INFRA-01 (NUEVA — pgvector fix) | S5 | US-1A-INFRA-01 (S5) | Deuda técnica acumulada |
| US-1A-OBS-01 (NUEVA — Sentry stack end-to-end) | S5 | US-1A-OBS-01 (S5) | ADR-019 + ADR-047 cierre |
| US-1A-IAC-01 (NUEVA — Terraform Hetzner) | S5 | US-1A-IAC-01 (S5) | Scaffold S0 → wiring real |
| US-1A-CICD-01 (NUEVA — pipeline real) | S5 | US-1A-CICD-01 (S5) | Cierre Fase 1b pre-cutover |
| US-1A-SEC-01 (NUEVA — WAF Cloudflare) | S5 | US-1A-SEC-01 (S5) | ADR-054 cierre |
| US-1A-09-07 (calibrator training pipeline) | S5+ | US-1A-09-07 (S5 stretch) | Cierre US-RND-01-07 |
| US-1A-06-04-V2 (datasheets PDF parsing real + Vision) | S5 | US-1A-06-04-V2 (S5 stretch) | Continuación S4 US-1A-06-04 |
| US-1A-07-04-AR (i18n AR completion) | S5 | US-1A-07-04-AR (S5) | Cierre Q-18 + gate Fase 2 |
| US-1B-01-07 (bulk-recalc nocturno) | S5 | US-1B-01-07 (S5) | Cierre US-1B-01-04 (manual) → automatizado |
| US-1A-DEV-01 (OpenAPI sync) | S5 | US-1A-DEV-01 (S5 stretch) | Tooling devexp |
| US-RND-01-12 (BR PMO hooks) | S5+ | US-RND-01-12 (S5 stretch) | Carry-over Fase 2 scaffold |
| US-RND-01-11 (GraphRAG scaffold) | S4 | COMPLETADO en S4 | — |
| US-1B-02-01..05 (workflow aprobación) | S5 plan original | DEFER S6 | Capacidad — IaC + observability + activación red prioritarios |
| US-RND-01-10 (UI Tinder humana) | S5+ | DEFER S6 | Necesita UI Pantalla 12 firmada + calibrator estable S5 |

## Apéndice B — TODOs / cosas dudadas

1. **Doppler vs alternative secrets vault (Vault HashiCorp / AWS Secrets Manager)**: confirmado Doppler en S0 (alineado con hppt-iom). Verificar TI MT no veta. TODO ADR-078 alternativa documentada.
2. **Cloudflare account ownership**: ¿BR Innovation o MT? Implica RACI distinto. Owner: Sponsor MT decide pre-kickoff.
3. **Backblaze B2 EU como Terraform state remote**: confirmar privacy policy alineado con PDPL (R-021 sub-procesador). Si no, fallback Terraform Cloud (US region).
4. **Sentry DSN scope**: ¿uno por env (dev/staging/prod) o uno global con tags? Recomendación: uno por env con DSN distintos.
5. **Better Stack plan pricing**: free tier 1 GB/day logs — verificar suficiente para 224 SKUs Fase 1; upgrade Pro $30/mo si no.
6. **OpenAPI types regen target**: ¿`mt-pricing-frontend/lib/api/types.ts` committed o `.gitignore`? Recomendación: committed para CI check.
7. **Pgvector image tag**: `pgvector/pgvector:pg15` últimas releases — confirmar reproducibilidad pin específico (e.g. `pg15-v0.7.0`).
8. **AR translation pipeline**: ¿LLM batch + revisión humana o vendor profesional? Decisión owner Sponsor + Translation owner.
9. **CI/CD secrets**: GitHub Encrypted Secrets vs Doppler service token — recomendación Doppler service token + GitHub secret as wrapper.
10. **Live network enrollment calendario**: ¿10% → 50% → 100% en S5 o spread S5-S6? Recomendación spread con 10% S5 cierre + 50% S6 kickoff + 100% S6 mid-sprint, pendiente Champion firma.
11. **Bulk-recalc nocturno timing**: 02:30 UTC = 06:30 GST — confirmar no conflicta con backup window Supabase (revisar status page).
12. **Demo S5 script**: deploy via CI/CD nuevo merge → ver Sentry en acción (intentional error) → ver Better Stack logs → activar `MT_LIVE_NETWORK_PERCENT=10` → ver match real con cost dashboard → trigger nocturno manual smoke → verify audit batch → toggle AR locale → verify RTL UI. End-to-end visible al cierre miércoles semana 2.
13. **Pipeline version bump**: `S4-real-adapters-v1` → `S5-prod-ready-v1` cuando Sentry + IaC + CI/CD merged. Documentar en `match_decisions.pipeline_version` + healthcheck.
14. **Cost ceilings exact**: confirmar pre-kickoff con Sponsor: Bright Data $150 vs $200; Gemini $50 vs $100; OpenAI $50 vs $100. Reserva buffer.
15. **DR drill (US-1B-05-04)**: defer S6 confirmado pero owner pre-pone fecha — Pablo + TI MT.

---

**Próximos pasos sugeridos pre-kickoff**:

1. **Confirmar firmas legales** (Q-NEW-S3) y **credenciales** (SP-API, OpenAI, Doppler, Sentry, Better Stack, Hetzner, Cloudflare).
2. **Provisionar Hetzner servers** + Cloudflare zone + Doppler workspace (TI MT, day -3).
3. **Confirmar UX firmas** outstanding S4 + dashboard cost tracker mockup.
4. **Champion firma cost ceilings** Bright Data + Gemini + OpenAI.
5. **Translation owner AR** firma calendario.
6. **Kick-off S5** con los 5 agentes en paralelo + agente E gap-fix al final.
