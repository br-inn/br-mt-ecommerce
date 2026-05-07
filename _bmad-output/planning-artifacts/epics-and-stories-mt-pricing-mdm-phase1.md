---
title: "Épicas e Historias de Usuario — MT Middle East MDM + Pricing (Fase 1)"
status: "draft"
version: "1.1"
created: "2026-05-06"
updated: "2026-05-06"
project_name: "mt-pricing-mdm-phase1"
phase: "1 (1a + 1b)"
inputs:
  - "prd-mt-pricing-mdm-phase1.md v1.4"
  - "architecture-mt-pricing-mdm-phase1.md v1.4"
changelog:
  - "1.0 (2026-05-06): versión inicial — 56 historias, ~400 SP."
  - "1.1 (2026-05-06): integra ADR-045 (persistencia híbrida) y ADR-046 (DatabaseScheduler). Añade US-1A-01-08 (Bootstrap SQLAlchemy 2.0 async + Alembic, 5 SP) y US-1A-01-09 (Cliente supabase-py + dual config, 3 SP) en EP-1A-01. Nueva épica EP-1A-08 — Scheduler editable + UI Jobs admin (S3-S4, ~23 SP) con 5 historias. EP-1A-07 referencia force-logout en revocación de rol. Total nuevas: 31 SP. Total operativo actualizado: ~321 SP; total con R&D: ~431 SP."
---

# Épicas e Historias de Usuario — MT Middle East MDM + Pricing (Fase 1)

> Documento Agile derivado del PRD v1.3 y la Arquitectura v1.3. Lenguaje de trabajo: español. Identificadores (FR, BR, NFR, UC, ADR) reciclados desde el PRD para permitir trazabilidad bidireccional. El equipo Scrum debería poder arrancar refinement con este documento sin entrevistas adicionales.

---

## 1. Resumen del enfoque Agile

### 1.1 Estructura general

- **Sprint 0 (1 semana)** — Gate de arranque: stack firmado, archivos PIM/costos recibidos, reglas v5.1 extraídas, demos comerciales del comparador iniciadas.
- **Fase 1a — Datos Maestros (S1-S3, 6-8 semanas)**: PIM, proveedores, costes, monedas, audit trail, RBAC, importers.
- **Fase 1b — Pricing y Aprobación (S4-S7, 6-8 semanas)**: motor de pricing, workflow excepción, estados de canal, connectors base, hardening + cutover.
- **Workstream R&D paralelo (S0-S7)**: comparador de productos (RAG vectorial Fase 1, abstracciones para Hybrid+GraphRAG Fase 2/3).

### 1.2 Cadencia y capacidad

- **Sprints**: 2 semanas calendario.
- **Equipo asumido**: 2-3 devs FTE (1 frontend Next.js, 1-2 backend FastAPI/Celery), capacidad **30-40 story points por sprint**.
- **Story points**: Fibonacci `1 / 2 / 3 / 5 / 8 / 13`.
  - 1-2 = trivial, configuración o ajuste menor.
  - 3-5 = historia normal con tests.
  - 8 = historia compleja (transversal o con integración externa).
  - 13 = historia épica que probablemente debería partirse.
- **Workstream R&D** corre con su propio capítulo de capacidad (~20 % del equipo + freelance externo del POC), no compite con backlog operativo.

### 1.3 Gates de fase

| Gate | Cuándo | Criterio |
|------|--------|----------|
| **G0** | Cierre Sprint 0 | Stack firmado, archivos reales recibidos, ADRs 028-037 confirmados |
| **G1** | Cierre S1 | PIM operativo, mapping Excel documentado |
| **G2** | Cierre S3 (cierre 1a) | Demo "puedo mantener catálogo y costos sin Excel" + decisión build-vs-buy comparador (números POC) |
| **G3** | Cierre S5 | Workflow aprobación operativo + reglas paramétricas firmadas por Gerente |
| **G4** | Cierre S7 | Cutover firmado por Gerente + TI + Sponsor; Excel archivado read-only; comparador con números reales (decisión Fase 1 vs 1.5) |

### 1.4 Definition of Ready (DoR) y Definition of Done (DoD)

Ver §7 y §8.

---

## 2. Épicas Fase 1a — Datos Maestros

### EP-1A-01 — Setup técnico y Sprint 0

**Objetivo**: provisionar infraestructura, repositorios y pipelines CI/CD para que S1 arranque con build verde, deploy automatizado a staging y RBAC base operativo.

**Sprints**: S0.

**Métricas de cierre**:
- Repos `mt-pricing-frontend/`, `mt-pricing-backend/`, `mt-pricing-infra/` creados, con README y Codeowners.
- Supabase projects (staging + prod) provisionados; migrations runnable.
- Servidor Hetzner (staging) operativo con Caddy + Docker Compose.
- Pipeline GitHub Actions: lint + test + build + deploy a staging desde `main`.
- Healthchecks `/health/live` y `/health/ready` responden 200.
- Sentry integrado (frontend + backend) con sourcemaps.
- ADRs 028-037 firmados o explícitamente sustituidos.

### EP-1A-02 — PIM (Product Information Management)

**Objetivo**: CRUD de artículos con specs técnicas, multi-idioma EN/ES/AR (EN canónico NOT NULL), imágenes en Supabase Storage, flag `data_quality`, y persistencia con audit_events.

**Sprints**: S1, S2.

**Métricas de cierre**:
- 224+ SKUs cargables vía UI o importer.
- `name_en` 100 % NOT NULL.
- Cobertura traducción ES/AR ≥ 95 % en SKUs publicables.
- Mirror obligatorio de imágenes externas a `product-images/` (BR-IMG-01/02).
- FR-1a-01, FR-1a-02, FR-1a-03, FR-IMG-01/02/03 cubiertos por tests.

### EP-1A-03 — Master de proveedores

**Objetivo**: maestro de proveedores con condiciones contractuales, lead time, contacto, moneda contractual y soft-deactivate.

**Sprints**: S2.

**Métricas de cierre**:
- CRUD UI + API de proveedores con audit.
- Soft-deactivate preserva costes históricos (BR-1a-07 análogo).
- FR-1a-04 + UC-1a-04, UC-1a-15 cubiertos por tests.

### EP-1A-04 — Master de costes

**Objetivo**: motor de costes por SKU × esquema de venta (FBA, FBM, Direct B2C, Direct B2B, Marketplace) con breakdown desglosado y FX as-of stamping.

**Sprints**: S2.

**Métricas de cierre**:
- Schemas seeded: `FBA / FBM / DIRECT_B2C / DIRECT_B2B / MARKETPLACE`.
- 100 % SKUs con coste por al menos 1 esquema.
- FX as-of estampado por línea (BR-1a-04).
- FR-1a-05, BR-1a-03 cubiertos por tests.

### EP-1A-05 — Sistema de monedas + FX versionado

**Objetivo**: tabla `currencies` (default AED) + `fx_rates` versionada con cierre automático de `effective_to`, fuente registrada, y FX as-of stamping en costos/precios.

**Sprints**: S3.

**Métricas de cierre**:
- AED como base configurable; EUR + USD seeded.
- `fx_rates` versionada con índice lookup por `(from, to, effective_from DESC)`.
- Trigger Postgres asegura FX as-of en INSERT de `costs`/`prices`.
- FR-1a-09 + NFR-29/30 cubiertos por tests.

### EP-1A-06 — Importers y carga inicial

**Objetivo**: importers dedicados para PIM completo, costos, compatibilidad de materiales y fichas técnicas PDF, con preview, validación cruzada y reporte de reconciliación.

**Sprints**: S1, S2, S3.

**Métricas de cierre**:
- Importer `PIM completo.xlsx` (5086 filas) ejecuta < 5 min sin errores.
- Importer costos (~1000 líneas) ejecuta < 10 min.
- Importer `Compatibilidad Materiales V4` (657 filas) carga `material_compatibilities`.
- Importer fichas técnicas PDF asocia ≥ 6 PDFs MTFT a SKUs vía sufijo numérico.
- Reporte de reconciliación PIM ↔ costos generado al cierre S2.
- FR-1a-06, FR-1a-07, FR-1a-08, FR-1a-13, FR-DOC-01, FR-MAT-01 cubiertos.

### EP-1A-07 — RBAC + i18n UI + Audit trail

**Objetivo**: 3 roles operativos (Comercial, Gerente, TI), Supabase Auth con RLS policies, UI ES+EN con next-intl, y audit_events poblado por triggers Postgres en todas las tablas críticas. **Force-logout** (`supabase.auth.admin.sign_out(user_id)`) en revocación / cambio de rol para minimizar lag de propagación del JWT (decidido en `mt-users-module-design.md` v1.1).

**Sprints**: S3.

**Métricas de cierre**:
- 3 roles operativos con denegación por defecto (NFR-07).
- RLS policies sobre `products`, `costs`, `prices`, `audit_events`, `storage.objects`.
- Selector idioma ES/EN persiste en `users.ui_locale`.
- Triggers `audit_events` en `products`, `costs`, `suppliers`, `currencies`, `fx_rates`, `product_translations`.
- Revocación de rol fuerza `sign_out` del usuario afectado (test e2e: el JWT viejo es rechazado en el siguiente request).
- FR-1a-10, FR-1a-11, FR-1a-12, NFR-11 cubiertos.

### EP-1A-08 — Scheduler editable + UI Jobs admin (ADR-046)

**Objetivo**: Celery Beat con DatabaseScheduler (tabla `job_definitions`) editable sin redeploy, UI admin `/admin/jobs` con CRUD + cron preview + "Run now" + audit drawer, y RLS que separa edición de jobs `business` (gerente_comercial) de jobs `infra` (solo ti_integracion). Reemplaza el patrón previo de schedules estáticos en `app/celery_config.py:beat_schedule`.

**Sprints**: S3-S4 (puente entre cierre 1a y arranque 1b).

**Métricas de cierre**:
- Tabla `job_definitions` creada via Alembic + RLS policies + audit trigger + 6 seeds base (daily_digest, weekly_kpi, nightly_audit_archival, nightly_image_orphan_cleanup, hourly_fx_recalc, daily_pim_diff_audit).
- Contenedor `beat` corre con DatabaseScheduler + healthcheck verde.
- UI `/admin/jobs` permite a TI editar todos los jobs y al Gerente solo los `owner='business'` con campos restringidos (cron_expression, enabled, timezone).
- "Run now" encola task con `trigger_source='MANUAL'` y crea fila `job_runs`.
- Audit drawer muestra histórico de cambios con diff `before/after`.

---

## 3. Épicas Fase 1b — Pricing y Aprobación

### EP-1B-01 — Motor de pricing multi-canal/esquema

**Objetivo**: portar (o reescribir según decisión Q-10 en S0) las reglas v5.1 del Excel/VBA al motor Python: cálculo SKU × canal × esquema con `rule_applied`, `breakdown`, `alerts`, simulación what-if, y benchmarks contra golden numbers extraídos en S0.

**Sprints**: S4.

**Métricas de cierre**:
- Recálculo SKU N canales < 5 s p95 (NFR-01).
- Recálculo masivo 224 × 5 × 4 < 60 s (NFR-02).
- 100 % paridad con golden numbers v5.1 sobre 30 SKUs muestra.
- Simulación what-if multi-canal sin persistir en `prices` activos.
- FR-1b-01, FR-1b-02, FR-1b-11, FR-1b-14 cubiertos.

### EP-1B-02 — Workflow de aprobación por excepción

**Objetivo**: state machine completa `draft → auto_approved | pending_review → approved | rejected | revised → exported`, reglas paramétricas versionadas por canal/esquema, bulk review, digest diario y escalado >48 h.

**Sprints**: S5.

**Métricas de cierre**:
- 0 SKUs publicables con estado ≠ `approved` ∧ ≠ `auto_approved` (BR-1b-01).
- Digest diario operativo a las 18:00 UAE (FR-1b-05).
- Escalado >48 h dispara notificación (FR-1b-13).
- Reglas paramétricas versionadas (FR-1b-04, BR-1b-13).
- FR-1b-03, FR-1b-04, FR-1b-05, FR-1b-12, FR-1b-13, FR-1b-14 cubiertos.

### EP-1B-03 — Estados de canal + simulación

**Objetivo**: 6 estados de canal (`inactive`, `pre_launch`, `pilot`, `live`, `paused`, `deprecated`) con transiciones gobernadas por TI, validaciones cruzadas (precios `approved`/`auto_approved` para SKUs pilot) y simulación what-if entre canales `live` (feature flag, off Fase 1).

**Sprints**: S6.

**Métricas de cierre**:
- 6 estados implementados con `channel_state_history`.
- Transición a `pilot`/`live` valida cobertura de precios aprobados.
- Feature flag `channel_recommendation = off` por defecto.
- FR-1b-06, FR-1b-10, BR-1b-08/09/10 cubiertos.

### EP-1B-04 — Connectors base + shadow publish

**Objetivo**: puerto `ChannelPublisher` con adapters skeleton para Amazon UAE / Noon UAE / Shopify; shadow publish a sandbox; export CSV/XLSX con filter runtime de la regla dura "no aprobado no integra"; archivado last-known-good diario.

**Sprints**: S6.

**Métricas de cierre**:
- Export por canal genera CSV con sólo `approved`/`auto_approved` (BR-1b-01).
- Shadow publish a sandbox Amazon UAE captura respuesta + errores estructurados (FR-1b-09).
- Last-known-good export regenerado diariamente (BR-1b-15).
- FR-1b-07, FR-1b-08, FR-1b-09 + BR-1b-14 cubiertos.

### EP-1B-05 — Hardening + cutover

**Objetivo**: parallel run ≥ 2 semanas con Excel demo, gate de cutover firmado, last-known-good, rollback playbook, manual operativo en español, capacitación backup operator.

**Sprints**: S7.

**Métricas de cierre**:
- Parallel run con 0 diff durante ≥ 5 días consecutivos.
- Excel `stock_dubai_v23` archivado read-only `_ARCHIVE_YYYY-MM-DD` (BR-1a-10).
- Backup operator ejecutó ≥ 1 import + 1 aprobación.
- `docs/handbook-es.md` aprobado.
- Cutover gate firmado por Gerente + TI + Sponsor.

---

## 4. Épica del workstream R&D (transversal S0-S7)

### EP-RND-01 — Sistema de comparación de productos

**Objetivo**: rediseñar el comparador (v5.1 falla 15 % del catálogo), construir RAG vectorial Fase 1 (target 85-92 %), POC 500 SKUs × 3 marketplaces con métricas reales, demos comerciales paralelas (Centric/Skuuudle/Intelligence Node/DataWeave), VLM judge audit-grade, OCR sobre imágenes de competidor, hooks reverse image search detrás de feature flag, UI de validación humana como infraestructura permanente, y abstracciones (`ComparatorService`, `GraphRepository`) para introducir Hybrid+GraphRAG Fase 2/3 sin refactor.

**Sprints**: S0-S7 (paralelo).

**Métricas de cierre**:
- POC 500 SKUs × 3 marketplaces ejecutado con métricas reales (no proxy).
- False-positive < 2 %, false-negative < 10 %, ECE < 5 %, cobertura ≥ 90 % (sec. 8.3 PRD).
- ≥ 2 demos comerciales con números reales (Intelligence Node + Skuuudle como mínimo).
- Hooks `FR-CMP-GRAPH-01` (`ComparatorService` + `GraphRepository`) con tests de adapter swap.
- Decisión G4 build-vs-buy con números reales.

---

## 5. Historias de usuario por épica

> Convención de IDs: `US-{epic}-{nn}` (p. ej. `US-1A-01-03`). BDD con mínimo 3 escenarios. Story points en Fibonacci. Sprint asignado. Dependencias y notas técnicas con FR/BR/UC/ADR del PRD.

---

### EP-1A-01 — Setup técnico y Sprint 0

#### US-1A-01-01 — Crear repos `mt-pricing-frontend`, `mt-pricing-backend`, `mt-pricing-infra` con scaffolding base

**Como** TI Integración
**quiero** que existan tres repos GitHub con scaffolding base (Next.js 16, FastAPI 0.x, docker-compose.prod.yml + Caddyfile)
**para** que el equipo pueda hacer commits desde el día 1 con CI verde.

**Acceptance Criteria (BDD)**:
- **Dado** que el repo `mt-pricing-frontend` no existe **Cuando** el TI ejecuta el bootstrap **Entonces** queda creado con Next.js 16 + React 19 + Tailwind v4 + Shadcn/ui (new-york), `next-intl`, lockfile commiteado y README en español.
- **Dado** el repo `mt-pricing-backend` recién creado **Cuando** se ejecuta `pytest` localmente **Entonces** corre 0 tests con exit code 0 y reporta cobertura 0 %.
- **Dado** el repo `mt-pricing-infra` **Cuando** se inspecciona **Entonces** contiene `docker-compose.prod.yml`, `Caddyfile`, `scripts/deploy.sh` y un `.env.example` con variables documentadas.

**Story points**: 5
**Sprint**: S0
**Dependencias**: ninguna.
**Notas técnicas**: ADR-028 (frontend), ADR-029 (backend), ADR-034 (Hetzner), ADR-035 (Caddy), ADR-036 (repos separados).

#### US-1A-01-02 — Provisionar Supabase projects (staging + prod) con RLS, pgvector y uuidv7

**Como** TI Integración
**quiero** dos proyectos Supabase configurados (staging, prod) con extensiones `pgvector`, `pg_uuidv7` y RLS habilitado
**para** que las migrations Alembic puedan correr y la BD esté lista para Sprint 1.

**Acceptance Criteria (BDD)**:
- **Dado** un proyecto Supabase nuevo **Cuando** el TI aplica el SQL de bootstrap **Entonces** las extensiones `pgvector` y `pg_uuidv7` quedan habilitadas y `select uuidv7()` retorna un UUID válido.
- **Dado** el proyecto staging **Cuando** se intenta `select * from auth.users` desde un JWT con rol `anon` **Entonces** la consulta falla por RLS denegada.
- **Dado** los secrets de Supabase **Cuando** el TI los carga al GitHub Actions environment **Entonces** el pipeline puede ejecutar `alembic upgrade head` contra staging.

**Story points**: 5
**Sprint**: S0
**Dependencias**: US-1A-01-01.
**Notas técnicas**: ADR-031 (Supabase), ADR-032 (Auth), NFR-11.

#### US-1A-01-03 — Configurar GitHub Actions CI/CD (lint + test + build + deploy a staging)

**Como** TI Integración
**quiero** un pipeline CI/CD que ejecute lint, type-check, tests y deploy automático a staging desde `main`
**para** que cada PR mergeado quede deployable sin intervención manual.

**Acceptance Criteria (BDD)**:
- **Dado** un PR a `main` con cambios en `mt-pricing-backend` **Cuando** se abre **Entonces** el pipeline corre `ruff`, `mypy`, `pytest`, y reporta status check verde o rojo.
- **Dado** un merge a `main` **Cuando** los checks pasan **Entonces** se dispara deploy a Hetzner staging vía `scripts/deploy.sh` y healthcheck `/health/ready` retorna 200.
- **Dado** un fallo en deploy **Cuando** ocurre **Entonces** se notifica a Sentry y al canal Slack/email del equipo con `request_id` y diff del commit.

**Story points**: 5
**Sprint**: S0
**Dependencias**: US-1A-01-01, US-1A-01-02.
**Notas técnicas**: NFR-25, NFR-26.

#### US-1A-01-04 — Definir y firmar ADRs 028-037 con TI MT

**Como** sponsor / TI MT
**quiero** firmar formalmente los ADRs de stack (frontend, backend, BD, auth, storage, deploy, proxy, repos)
**para** que las decisiones queden trazadas y no re-cuestionadas.

**Acceptance Criteria (BDD)**:
- **Dado** ADR-028 a ADR-037 en draft **Cuando** se revisan en reunión S0 con Paula y Christian **Entonces** quedan en estado `accepted` o `superseded` con fecha y firmantes registrados.
- **Dado** un ADR rechazado **Cuando** se sustituye **Entonces** el nuevo ADR referencia al rechazado en `supersedes:` y al rechazado se le actualiza `status: superseded`.
- **Dado** los ADRs aceptados **Cuando** un dev nuevo lee `_bmad-output/planning-artifacts/adr/` **Entonces** puede reconstruir el stack sin preguntar.

**Story points**: 3
**Sprint**: S0
**Dependencias**: ninguna.
**Notas técnicas**: ADRs 028-037; resolución de Q-01.

#### US-1A-01-05 — Provisionar Hetzner (staging + prod) con Caddy + Docker Compose

**Como** TI Integración
**quiero** dos servidores Hetzner (staging + prod) con Docker Compose corriendo Caddy + FastAPI + Celery + Redis
**para** que los deploys del pipeline tengan target.

**Acceptance Criteria (BDD)**:
- **Dado** un servidor Hetzner Cloud nuevo **Cuando** se ejecuta `scripts/bootstrap.sh` **Entonces** queda configurado con Docker, Docker Compose v2, firewall UFW y SSH hardening.
- **Dado** Caddy levantado **Cuando** se accede al subdominio staging **Entonces** Caddy obtiene certificado TLS automático y proxy a backend FastAPI.
- **Dado** Redis + Celery worker corriendo **Cuando** se ejecuta `celery -A app.tasks inspect ping` **Entonces** responde `pong` desde al menos 1 worker.

**Story points**: 5
**Sprint**: S0
**Dependencias**: US-1A-01-01.
**Notas técnicas**: ADR-034, ADR-035, NFR-19.

#### US-1A-01-06 — Integrar Sentry + Loguru/structlog + healthchecks

**Como** TI Integración
**quiero** observabilidad mínima funcionando desde S0 (Sentry frontend+backend, logs JSON estructurados, healthchecks)
**para** que cualquier bug post-deploy sea diagnosticable.

**Acceptance Criteria (BDD)**:
- **Dado** un error sin manejar en backend FastAPI **Cuando** ocurre en staging **Entonces** Sentry recibe el evento con `request_id`, `user_id` (si auth) y stacktrace con sourcemap.
- **Dado** un endpoint **Cuando** se invoca **Entonces** los logs estructurados JSON contienen `request_id`, `actor`, `entity`, `action`.
- **Dado** un healthcheck `/health/ready` **Cuando** la DB cae **Entonces** retorna 503 y Caddy lo refleja en el status del servicio.

**Story points**: 3
**Sprint**: S0
**Dependencias**: US-1A-01-03.
**Notas técnicas**: NFR-25, NFR-26, NFR-28.

#### US-1A-01-07 — Configurar baseline Supabase Auth con 3 roles + RLS denegación por defecto

**Como** TI Integración
**quiero** Supabase Auth configurado con providers email/password + magic link y los 3 roles (`comercial`, `gerente`, `ti`) declarados con RLS denegación por defecto
**para** que el resto de épicas tengan auth desde el día 1.

**Acceptance Criteria (BDD)**:
- **Dado** un usuario nuevo registrado vía magic link **Cuando** verifica el email **Entonces** queda creado en `auth.users` y en la tabla espejo `public.users` con rol `comercial` por default.
- **Dado** un usuario sin rol asignado **Cuando** llama `GET /products` **Entonces** la RLS deniega y la API retorna 403.
- **Dado** un admin **Cuando** asigna rol `gerente` a un usuario **Entonces** el cambio queda registrado en `audit_events`.

**Story points**: 5
**Sprint**: S0
**Dependencias**: US-1A-01-02.
**Notas técnicas**: ADR-032, NFR-07, NFR-11.

#### US-1A-01-08 — Bootstrap SQLAlchemy 2.0 async + Alembic (ADR-045)

**Como** dev backend
**quiero** SQLAlchemy 2.0 async configurado con asyncpg + Alembic init + factory de sesión por request + primer migration con tabla básica
**para** que las historias de S1 puedan modelar `products`, `costs`, `prices` sobre ORM tipado.

**Acceptance Criteria (BDD)**:
- **Dado** `mt-pricing-backend/app/core/db.py` recién creado **Cuando** se importa `engine` y `AsyncSessionLocal` **Entonces** ambos quedan disponibles, configurados con driver `asyncpg`, pool size adaptado al worker mode (web=20, worker=10), y `pool_pre_ping=True`.
- **Dado** Alembic inicializado bajo `mt-pricing-backend/alembic/` con `env.py` configurado para autogenerate sobre los modelos de `app.db.models` **Cuando** ejecuto `alembic revision --autogenerate -m "init"` **Entonces** se genera una migración válida con la primera tabla aplicativa (ej. `health_probe` trivial) que aplica con `alembic upgrade head` contra Supabase staging.
- **Dado** un endpoint FastAPI con `Depends(get_session)` **Cuando** se invoca **Entonces** la sesión se crea por request, se commitea al final si no hay excepción y se cierra sin leak (verificado con integration test que cuenta conexiones activas en `pg_stat_activity`).
- **Dado** el rol Postgres `mt_app` (creado en Supabase migration previa) **Cuando** el backend se conecta con DSN `postgresql+asyncpg://mt_app@...` **Entonces** las RLS policies aplican (verificado con test que prueba que `mt_app` NO puede SELECT filas de otro usuario).

**Story points**: 5
**Sprint**: S0
**Dependencias**: US-1A-01-02 (Supabase project), US-1A-01-04 (ADRs firmados — incluye ADR-045).
**Notas técnicas**: ADR-045, arquitectura §8.0, §22.1 (estructura `app/core/db.py`, `app/repositories/`, `app/services/`).

#### US-1A-01-09 — Cliente supabase-py + dual config (ADR-045)

**Como** dev backend
**quiero** `mt-pricing-backend/app/core/supabase.py` con factories diferenciadas (`get_supabase_client` anon / `get_supabase_admin` service-role) + Pydantic Settings + smoke test contra Supabase Auth
**para** que las historias de auth y storage puedan invocar `auth.admin.*` y `storage.from_(...)` sin re-implementar boilerplate.

**Acceptance Criteria (BDD)**:
- **Dado** `app/core/supabase.py` recién creado **Cuando** se importa `get_supabase_admin` **Entonces** retorna un cliente supabase-py inicializado con `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (cargados via Pydantic Settings) y validados al boot (rechaza service_role key vacía en producción).
- **Dado** un smoke test de integración **Cuando** se ejecuta `sb.auth.admin.list_users(per_page=1)` contra Supabase staging **Entonces** la llamada retorna 200 sin error.
- **Dado** una petición desde un endpoint **Cuando** invoca tanto SQLAlchemy (`Depends(get_session)`) como supabase-py (`Depends(get_supabase_admin)`) en la misma request **Entonces** ambos clientes coexisten sin conflicto y el test e2e verifica que un flujo `invite_user` puede usar ambos en una transacción coordinada.
- **Dado** logs estructurados **Cuando** una llamada a supabase-py falla **Entonces** el error se loggea con `request_id` + `supabase_error_code` y se reporta a Sentry (no se traga el error).

**Story points**: 3
**Sprint**: S0
**Dependencias**: US-1A-01-02, US-1A-01-06 (Sentry + logger).
**Notas técnicas**: ADR-045, arquitectura §8.0.2 patrón de dos clientes.

---

### EP-1A-02 — PIM (Product Information Management)

#### US-1A-02-01 — Crear schema `products` con campos identidad, specs JSONB y embedding reservado

**Como** dev backend
**quiero** la migración Alembic que crea `products` con todos los campos del PRD (incluyendo `embedding VECTOR(1536)` reservado)
**para** que UC-1a-01 a UC-1a-15 tengan tabla destino.

**Acceptance Criteria (BDD)**:
- **Dado** la migración inicial aplicada **Cuando** se inserta una fila con `name_en` NULL **Entonces** el INSERT falla por NOT NULL constraint (BR-1a-02).
- **Dado** una fila con `sku` duplicado **Cuando** se intenta insertar **Entonces** el INSERT falla por UNIQUE (BR-1a-01).
- **Dado** la columna `embedding VECTOR(1536)` **Cuando** se consulta `\d products` **Entonces** existe pero todas las filas tienen NULL (reservado Fase 1.5+, NFR-20).

**Story points**: 3
**Sprint**: S1
**Dependencias**: US-1A-01-02.
**Notas técnicas**: PRD §10.1, NFR-20.

#### US-1A-02-02 — Endpoint `POST /products` (alta de SKU manual)

**Como** Comercial
**quiero** crear un SKU desde la app con `name_en`, `family`, `dn`, `pn`, `material`, `type`
**para** catalogar un producto nuevo sin tocar Excel.

**Acceptance Criteria (BDD)**:
- **Dado** que soy Comercial autenticado **Cuando** envío `POST /products` con payload válido **Entonces** el sistema persiste el SKU con `data_quality = partial`, registra `audit_events(action='create')` y retorna 201 con el ID.
- **Dado** un payload sin `name_en` **Cuando** lo envío **Entonces** el sistema retorna 422 con `error.code = "BR_1A_02"` y `error.field = "name_en"`.
- **Dado** un SKU duplicado **Cuando** intento crearlo **Entonces** el sistema retorna 409 `Conflict`.

**Story points**: 3
**Sprint**: S1
**Dependencias**: US-1A-02-01, US-1A-01-07.
**Notas técnicas**: FR-1a-01, UC-1a-01.

#### US-1A-02-03 — Endpoint `PUT /products/{id}` y `PATCH /products/{id}/data-quality`

**Como** Comercial
**quiero** editar specs técnicas y cambiar el flag `data_quality` de un SKU
**para** mantener la ficha actualizada y gobernar publicabilidad.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU existente con `dn = 50` **Cuando** envío `PUT` con `dn = 65` **Entonces** el sistema persiste, registra `audit_events(action='update', diff)` y dispara recálculo de precios dependientes (Fase 1b: marca como pendiente para job).
- **Dado** un SKU `data_quality = blocked` **Cuando** intento publicar a marketplace **Entonces** el sistema bloquea (BR-1a-13).
- **Dado** un cambio de `data_quality` **Cuando** se persiste **Entonces** queda en `audit_events` con autor + timestamp.

**Story points**: 3
**Sprint**: S1
**Dependencias**: US-1A-02-02.
**Notas técnicas**: FR-1a-01, BR-1a-06, BR-1a-13, UC-1a-02.

#### US-1A-02-04 — UI "Editar SKU" con tabs (Identidad / Imágenes / Traducciones / Costes / Precios / Auditoría)

**Como** Comercial
**quiero** una pantalla unificada de edición de SKU
**para** trabajar la ficha completa sin saltar entre vistas.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU existente **Cuando** abro la pantalla **Entonces** veo los tabs Identidad, Imágenes, Traducciones, Costes, Precios, Auditoría con datos cargados (lazy por tab).
- **Dado** que estoy en tab Identidad **Cuando** edito `dn` y guardo **Entonces** la UI muestra toast "Guardado" y refresca el tab Auditoría con la entrada nueva.
- **Dado** que estoy en tab Auditoría **Cuando** scrolleo **Entonces** veo paginación cronológica descendente con `actor`, `action`, `diff`.

**Story points**: 8
**Sprint**: S1
**Dependencias**: US-1A-02-02, US-1A-02-03.
**Notas técnicas**: PRD §12.2.

#### US-1A-02-05 — Tabla `product_translations` con `translation_status` por idioma

**Como** Comercial
**quiero** registrar traducciones ES/AR con estado (`pending` / `draft` / `approved`) por idioma
**para** que la cobertura sea medible y sólo se exporten traducciones aprobadas.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU con `name_en = "Brass gate valve DN50 PN16"` **Cuando** envío `POST /products/{id}/translations` con `lang=es, name="Válvula de compuerta de latón DN50 PN16", translation_status=draft` **Entonces** se persiste y queda visible en el tab Traducciones.
- **Dado** una traducción AR `draft` **Cuando** llamo `POST /products/{id}/translations/ar/approve` **Entonces** el estado pasa a `approved`, se registra `approved_by` + `approved_at` y queda exportable.
- **Dado** un SKU publicable **Cuando** consulto cobertura **Entonces** el sistema reporta % EN/ES/AR `approved`.

**Story points**: 5
**Sprint**: S1
**Dependencias**: US-1A-02-01.
**Notas técnicas**: FR-1a-02, BR-1a-09, NFR-22, UC-1a-03.

#### US-1A-02-06 — Bucket `product-images` privado con signed URLs y RLS por rol

**Como** TI Integración
**quiero** un bucket Supabase Storage `product-images` privado con paths convencionales y RLS por rol
**para** cumplir el requisito explícito del cliente de que toda imagen viva en Supabase.

**Acceptance Criteria (BDD)**:
- **Dado** el bucket `product-images` recién creado **Cuando** un usuario `comercial` intenta listar `master/{sku}/` **Entonces** sólo ve sus propias subidas y el master mirroreado.
- **Dado** una imagen subida a `master/MT-V-038/primary.jpg` **Cuando** un usuario `comercial` solicita signed URL **Entonces** el backend retorna URL con TTL 24 h.
- **Dado** un usuario sin rol **Cuando** intenta acceder al bucket **Entonces** la RLS deniega.

**Story points**: 5
**Sprint**: S1
**Dependencias**: US-1A-01-02, US-1A-01-07.
**Notas técnicas**: ADR-033, FR-IMG-01, sec. 14.6 PRD.

#### US-1A-02-07 — Probe + mirror obligatorio de imágenes externas

**Como** Comercial
**quiero** que cualquier `image_url` externa se descargue automáticamente al bucket interno
**para** no depender de hot-links de fabricantes.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU con `image_url_pim = "https://pim.mt-valves.es/img/MT-V-038.jpg"` **Cuando** ejecuto `POST /products/{id}/image/probe` **Entonces** el sistema descarga, valida formato (JPEG/PNG/WebP/AVIF, ≤ 10 MB), persiste en `product-images/master/{sku}/primary.jpg`, actualiza `image_url` interna, conserva `image_origin_url` para auditoría.
- **Dado** una imagen no descargable (404) **Cuando** ejecuto el probe **Entonces** el sistema marca `image_status = broken_link` y registra el evento.
- **Dado** una imagen 11 MB **Cuando** ejecuto el probe **Entonces** el sistema rechaza con `image_status = too_large` y reporta al Champion.

**Story points**: 5
**Sprint**: S1
**Dependencias**: US-1A-02-06.
**Notas técnicas**: FR-1a-03, FR-IMG-02, FR-IMG-03, BR-IMG-01/02, sec. 14.6.4 PRD.

#### US-1A-02-08 — Generación async de thumbnails (256/512/1024 px) en WebP

**Como** TI Integración
**quiero** que cada imagen subida genere thumbnails async vía Celery
**para** que la UI cargue rápido sin servir originales pesados.

**Acceptance Criteria (BDD)**:
- **Dado** una imagen subida a `master/{sku}/primary.jpg` **Cuando** la tarea Celery `generate_thumbnails` se ejecuta **Entonces** se persisten 3 variantes WebP en `thumbnails/{sku}/{256|512|1024}/primary.webp`.
- **Dado** la UI **Cuando** renderiza thumbnail 256 **Entonces** sirve la variante 256 con caché 1 año.
- **Dado** un fallo de generación **Cuando** ocurre **Entonces** Sentry captura el error y la imagen original sigue accesible como fallback.

**Story points**: 3
**Sprint**: S1
**Dependencias**: US-1A-02-06, US-1A-01-05.
**Notas técnicas**: ADR-030 (Celery), sec. 14.6.3.

#### US-1A-02-09 — Listado paginado `GET /products` con filtros (`family`, `active`, `data_quality`)

**Como** Comercial
**quiero** un listado filtrable y paginado
**para** encontrar SKUs rápidamente entre 5000+ filas.

**Acceptance Criteria (BDD)**:
- **Dado** 224 SKUs cargados **Cuando** envío `GET /products?family=gate_valve&page=1&page_size=50` **Entonces** retorna ≤ 50 filas con `meta.total`, `page`, `page_size`.
- **Dado** un filtro `data_quality=blocked` **Cuando** consulto **Entonces** retorna sólo SKUs en ese estado.
- **Dado** un `page_size=500` **Cuando** consulto **Entonces** retorna 422 (max 200, NFR-06 / sec. 11.1).

**Story points**: 3
**Sprint**: S1
**Dependencias**: US-1A-02-01.
**Notas técnicas**: PRD §11.1.

#### US-1A-02-10 — Bloqueo de borrado físico (sólo soft-deactivate)

**Como** TI Integración
**quiero** que `DELETE /products/{id}` esté deshabilitado y solo `PATCH /products/{id}/active = false` funcione
**para** preservar histórico VAT-compliant.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU activo **Cuando** intento `DELETE /products/{id}` **Entonces** el sistema retorna 405 Method Not Allowed.
- **Dado** un SKU activo **Cuando** lo desactivo **Entonces** `active=false`, queda invisible en exports pero presente en `audit_events`.
- **Dado** un SKU desactivado **Cuando** consulto su histórico **Entonces** veo todos los cambios anteriores.

**Story points**: 2
**Sprint**: S1
**Dependencias**: US-1A-02-02.
**Notas técnicas**: BR-1a-07, NFR-35.

---

### EP-1A-03 — Master de proveedores

#### US-1A-03-01 — Schema `suppliers` con moneda contractual + lead time

**Como** dev backend
**quiero** la migración Alembic que crea `suppliers`
**para** soportar costos por proveedor en EP-1A-04.

**Acceptance Criteria (BDD)**:
- **Dado** la migración aplicada **Cuando** inserto un proveedor con `contractual_currency = 'EUR'` **Entonces** se persiste correctamente y la FK a `currencies` valida.
- **Dado** un proveedor sin `lead_time_days` **Cuando** se inserta **Entonces** queda con NULL (campo opcional).
- **Dado** una moneda no registrada **Cuando** intento crear el proveedor **Entonces** falla por FK.

**Story points**: 2
**Sprint**: S2
**Dependencias**: US-1A-05-01 (currencies seed).
**Notas técnicas**: PRD §10.1, FR-1a-04.

#### US-1A-03-02 — CRUD UI + API de proveedores con audit

**Como** Comercial
**quiero** crear/editar/desactivar proveedores
**para** mantener el maestro sin pasar por TI.

**Acceptance Criteria (BDD)**:
- **Dado** que soy Comercial **Cuando** creo "MT Valves España" con `contractual_currency=EUR, lead_time_days=45` **Entonces** se persiste y registra `audit_events`.
- **Dado** un proveedor activo con costes asociados **Cuando** intento desactivarlo **Entonces** el sistema solicita confirmación y mantiene los costes históricos.
- **Dado** un proveedor desactivado **Cuando** filtro `active=true` **Entonces** no aparece.

**Story points**: 3
**Sprint**: S2
**Dependencias**: US-1A-03-01.
**Notas técnicas**: FR-1a-04, UC-1a-04, UC-1a-15.

---

### EP-1A-04 — Master de costes

#### US-1A-04-01 — Schemas seeded (FBA, FBM, DIRECT_B2C, DIRECT_B2B, MARKETPLACE) con `cost_components_template`

**Como** dev backend
**quiero** los 5 esquemas seeded en migration con plantilla de componentes
**para** que el motor de costes valide breakdown por esquema.

**Acceptance Criteria (BDD)**:
- **Dado** la migration `seed_schemes` aplicada **Cuando** consulto `SELECT * FROM schemes` **Entonces** existen las 5 filas con `cost_components_template` JSONB poblada.
- **Dado** el esquema FBA **Cuando** consulto su template **Entonces** incluye `['fob', 'freight', 'customs', 'fba_fees', 'payment_fees']`.
- **Dado** un código `FBA` **Cuando** intento crearlo de nuevo **Entonces** falla por UNIQUE.

**Story points**: 2
**Sprint**: S2
**Dependencias**: US-1A-02-01.
**Notas técnicas**: PRD §10.1, sec. 14.1 (Tarifas FBA & FBM).

#### US-1A-04-02 — Schema `costs` con FX as-of stamping vía trigger

**Como** dev backend
**quiero** la tabla `costs` con `fx_rate_id` autopoblado por trigger BEFORE INSERT
**para** que ningún coste pueda persistirse sin FX as-of.

**Acceptance Criteria (BDD)**:
- **Dado** un INSERT en `costs` sin `fx_rate_id` y `currency_origin = 'EUR'` **Cuando** se ejecuta **Entonces** el trigger busca el `fx_rate` vigente EUR→AED y lo estampa.
- **Dado** un INSERT con `fx_rate_id` explícito **Cuando** se ejecuta **Entonces** el trigger respeta el explícito y no sobrescribe.
- **Dado** un coste migrado **Cuando** se importa con `fx_inferred = true` **Entonces** queda marcado como tal.

**Story points**: 5
**Sprint**: S2
**Dependencias**: US-1A-05-02 (fx_rates).
**Notas técnicas**: BR-1a-04, BR-1a-05, BR-1a-14, NFR-30.

#### US-1A-04-03 — Endpoint `POST /costs` con breakdown desglosado

**Como** Comercial
**quiero** registrar un coste por SKU × esquema con breakdown JSONB
**para** que el motor de pricing tenga inputs.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU `MT-V-038` y esquema FBA **Cuando** envío `POST /costs` con `breakdown={fob_eur:12.40, freight_eur:1.80, customs_aed:2.10, fba_fees_aed:8.50, payment_fees_pct:2.49}` **Entonces** el sistema persiste, calcula `total_aed` con FX vigente, registra `audit_events`.
- **Dado** un SKU sin coste para FBA **Cuando** consulto `GET /products?missing_cost_scheme=FBA` **Entonces** el sistema lo retorna en la lista.
- **Dado** un breakdown con campos no declarados en `cost_components_template` **Cuando** se persiste **Entonces** el sistema acepta pero registra un warning.

**Story points**: 5
**Sprint**: S2
**Dependencias**: US-1A-04-01, US-1A-04-02, US-1A-03-02.
**Notas técnicas**: FR-1a-05, BR-1a-03.

#### US-1A-04-04 — UI tab "Costes" con tabla por esquema y breakdown editor

**Como** Comercial
**quiero** ver y editar costes por esquema desde la ficha de SKU
**para** no necesitar APIs ni Excel.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU con costes en FBA y FBM **Cuando** abro el tab Costes **Entonces** veo dos filas con breakdown expandible.
- **Dado** que edito el `fob_eur` de 12,40 a 13,00 **Cuando** guardo **Entonces** el sistema crea una nueva versión (`status=active`, anterior pasa a `superseded`).
- **Dado** un coste superseded **Cuando** lo consulto **Entonces** sigue en histórico y `audit_events` lo registra.

**Story points**: 5
**Sprint**: S2
**Dependencias**: US-1A-04-03.
**Notas técnicas**: PRD §12.2.

---

### EP-1A-05 — Sistema de monedas + FX versionado

#### US-1A-05-01 — Tabla `currencies` seeded con AED base + EUR + USD + SAR

**Como** dev backend
**quiero** las monedas iniciales seeded
**para** que `suppliers` y `costs` puedan referenciar FK válidas.

**Acceptance Criteria (BDD)**:
- **Dado** la migration `seed_currencies` aplicada **Cuando** consulto **Entonces** existen AED (`is_base=true`), EUR, USD, SAR.
- **Dado** una segunda moneda con `is_base=true` **Cuando** intento insertarla **Entonces** un constraint impide tener > 1 base activa.
- **Dado** AED base **Cuando** se desactiva **Entonces** el sistema rechaza (no se puede operar sin base).

**Story points**: 2
**Sprint**: S3
**Dependencias**: US-1A-01-02.
**Notas técnicas**: NFR-29.

#### US-1A-05-02 — Tabla `fx_rates` con cierre automático de `effective_to`

**Como** dev backend
**quiero** que insertar un `fx_rate` nuevo cierre automáticamente el anterior con el mismo par
**para** no tener solapamientos en lookup.

**Acceptance Criteria (BDD)**:
- **Dado** un `fx_rate` activo EUR→AED `rate=4.29 effective_from=2026-04-01 effective_to=NULL` **Cuando** inserto otro EUR→AED `rate=4.18 effective_from=2026-06-12` **Entonces** el anterior queda con `effective_to = 2026-06-12`.
- **Dado** un `effective_from` posterior a otro existente que ya tiene `effective_to` cerrado **Cuando** se inserta **Entonces** queda nueva fila vigente.
- **Dado** un INSERT con `effective_from` < último vigente **Cuando** se ejecuta **Entonces** el sistema rechaza (no se permiten retroactivos sin flag).

**Story points**: 5
**Sprint**: S3
**Dependencias**: US-1A-05-01.
**Notas técnicas**: FR-1a-09, NFR-30.

#### US-1A-05-03 — Endpoint `POST /fx-rates` y UI consola TI para registrar tasas

**Como** TI Integración
**quiero** registrar manualmente tasas de cambio
**para** mantener el sistema actualizado mientras no haya proveedor automatizado.

**Acceptance Criteria (BDD)**:
- **Dado** que soy TI **Cuando** envío `POST /fx-rates` con par EUR→AED `rate=4.18 source='manual' effective_from=now()` **Entonces** se persiste y `audit_events` lo registra.
- **Dado** que soy Comercial **Cuando** intento `POST /fx-rates` **Entonces** RBAC deniega 403.
- **Dado** una tasa registrada **Cuando** la veo en la consola TI **Entonces** queda en la tabla con histórico de versiones.

**Story points**: 3
**Sprint**: S3
**Dependencias**: US-1A-05-02.
**Notas técnicas**: FR-1a-09, UC-1a-08, A-06.

#### US-1A-05-04 — Trigger FX as-of stamping en `prices` (preparación Fase 1b)

**Como** dev backend
**quiero** el trigger BEFORE INSERT en `prices` que estampa `fx_rate_id` si no se provee
**para** que cuando arranque Fase 1b el motor de pricing tenga FX inmutable garantizado.

**Acceptance Criteria (BDD)**:
- **Dado** un INSERT en `prices` sin `fx_rate_id` **Cuando** se ejecuta **Entonces** el trigger lo estampa con la tasa AED→AED 1:1 vigente (ya que precios ya están en AED).
- **Dado** un INSERT con `fx_rate_id` explícito **Cuando** se ejecuta **Entonces** el trigger respeta.
- **Dado** una tasa antigua **Cuando** se inserta un precio referenciándola **Entonces** queda con `fx_inferred = true`.

**Story points**: 3
**Sprint**: S3
**Dependencias**: US-1A-05-02.
**Notas técnicas**: BR-1a-14, BR-1b-12.

---

### EP-1A-06 — Importers y carga inicial

#### US-1A-06-01 — Importer `PIM completo.xlsx` con preview + confirm

**Como** Comercial / TI
**quiero** subir el archivo `PIM completo.xlsx` (5086 filas) en modo preview, ver diff, y luego confirmar
**para** cargar el catálogo sin riesgo de overwrites silenciosos.

**Acceptance Criteria (BDD)**:
- **Dado** el archivo PIM real **Cuando** ejecuto `POST /imports/pim` modo `preview` **Entonces** el sistema muestra `N nuevos, M actualizados, P rechazados` con razones por fila.
- **Dado** el preview confirmado **Cuando** ejecuto modo `confirm` **Entonces** el sistema persiste con FX as-of del batch, registra `audit_events` por cada fila, emite reporte de reconciliación.
- **Dado** un archivo con SKU duplicado en una fila **Cuando** intento importar **Entonces** la fila queda en el reporte de errores y el resto se procesa.

**Story points**: 8
**Sprint**: S1
**Dependencias**: US-1A-02-01, US-1A-04-02.
**Notas técnicas**: FR-1a-06, UC-1a-05, sec. 14.2.1, NFR-03.

#### US-1A-06-02 — Importer de archivos de costos con validación cruzada PIM

**Como** Comercial
**quiero** importar archivos de costos (líneas SKU × esquema × proveedor) con preview y reporte de huérfanos
**para** cargar costes sin tocar la BD directamente.

**Acceptance Criteria (BDD)**:
- **Dado** un archivo de costos con N líneas **Cuando** ejecuto `POST /imports/costs` modo preview **Entonces** el sistema reporta SKUs huérfanos (sin PIM), esquemas desconocidos, errores de breakdown.
- **Dado** preview confirmado **Cuando** ejecuto `confirm` **Entonces** cada línea persiste con FX as-of del batch, `audit_events` poblado.
- **Dado** un SKU huérfano **Cuando** se importa **Entonces** queda registrado en reporte con `assignable_owner=NULL` para resolución del Champion.

**Story points**: 8
**Sprint**: S2
**Dependencias**: US-1A-04-03, US-1A-06-01.
**Notas técnicas**: FR-1a-07, UC-1a-06, NFR-04.

#### US-1A-06-03 — Importer `Compatibilidad de Materiales V4` (657 filas) → `material_compatibilities`

**Como** Comercial / TI
**quiero** cargar la tabla de compatibilidades de material como referencia consultable
**para** que la ficha de producto muestre la matriz materiales × T °C y Fase 2 use la tabla en deal breakers.

**Acceptance Criteria (BDD)**:
- **Dado** el archivo `Copia de Compatibilidad de Materiales MT V4.xlsx` **Cuando** ejecuto el importer **Entonces** el sistema persiste 657 filas en `material_compatibilities` con columnas (`producto_descriptor`, `temperatura_c`, columnas por material).
- **Dado** un descriptor matcheable a un SKU **Cuando** consulto compatibilidades en la ficha **Entonces** el sistema muestra la matriz aplicable.
- **Dado** filas con formato inválido **Cuando** se importan **Entonces** quedan en el reporte de rechazos con razón.

**Story points**: 5
**Sprint**: S2
**Dependencias**: US-1A-02-01.
**Notas técnicas**: FR-MAT-01, sec. 14.2.3.

#### US-1A-06-04 — Importer fichas técnicas PDF (`MTFT_*`, `MTCE_*`, `MTMAN_*`) → `product_datasheets`

**Como** Comercial / TI
**quiero** asociar PDFs (técnicas, compliance, manuales) a SKUs por sufijo numérico de filename
**para** que el cliente pueda descargar la ficha desde la app.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU `MT-V-5114` y un PDF `MTFT_5114.pdf` **Cuando** subo la ficha **Entonces** el sistema persiste el archivo en `product-datasheets/MTFT_5114.pdf`, crea fila en `product_datasheets` con FK al SKU y registra `audit_events`.
- **Dado** una ficha que cubre varios SKUs **Cuando** la asocio a la lista **Entonces** el sistema crea N filas N:M sin duplicar el archivo.
- **Dado** un SKU con ficha asociada **Cuando** consulto la ficha **Entonces** la app muestra preview + botón descarga (signed URL TTL 24 h).

**Story points**: 5
**Sprint**: S3
**Dependencias**: US-1A-02-06.
**Notas técnicas**: FR-DOC-01, sec. 14.2.4.

#### US-1A-06-05 — Hooks indexación texto fichas técnicas (FR-DOC-02, off Fase 1)

**Como** TI Integración
**quiero** los hooks Celery + tabla `product_datasheet_text` listos pero detrás de feature flag
**para** que Fase 1.5+ encienda búsqueda semántica sin migration.

**Acceptance Criteria (BDD)**:
- **Dado** una ficha subida **Cuando** `feature.datasheet_indexing_enabled = false` **Entonces** sólo se persiste archivo + metadata.
- **Dado** el flag activado en Fase 1.5+ **Cuando** se sube ficha **Entonces** una tarea Celery extrae texto via PDF parsing + OCR y lo persiste en `product_datasheet_text` con embeddings pgvector.
- **Dado** el flag off **Cuando** llamo `GET /datasheets/search?q=...` **Entonces** retorna 501 Not Implemented con explicación.

**Story points**: 3
**Sprint**: S3
**Dependencias**: US-1A-06-04.
**Notas técnicas**: FR-DOC-02, NFR-20.

#### US-1A-06-06 — Importer Excel demo `stock_dubai_v23` modo fixture

**Como** TI / Champion
**quiero** un importer parametrizable que cargue las sheets del Excel demo a tablas staging
**para** validar mapping y generar fixtures de pruebas sin contaminar prod.

**Acceptance Criteria (BDD)**:
- **Dado** el archivo `stock_dubai_v23` **Cuando** ejecuto el importer en modo `fixture` **Entonces** el sistema carga sheets en tablas staging con prefijo `stg_` y genera reporte de mapping para validación humana.
- **Dado** que se completó el import del PIM real **Cuando** se confirme cierre Sprint 2 **Entonces** el Excel demo queda archivado read-only `_ARCHIVE_YYYY-MM-DD`.
- **Dado** una segunda ejecución del importer fixture **Cuando** se dispara **Entonces** trunca staging y recarga (idempotente).

**Story points**: 5
**Sprint**: S1
**Dependencias**: US-1A-01-02.
**Notas técnicas**: FR-1a-08, BR-1a-10, UC-1a-07, UC-1a-14, sec. 14.1.

#### US-1A-06-07 — Reporte de validación cruzada PIM ↔ costos al cierre S2

**Como** Champion
**quiero** un reporte automático que liste SKUs en PIM sin costes y costes huérfanos sin SKU
**para** asignar owner + due-date a cada uno antes del cutover.

**Acceptance Criteria (BDD)**:
- **Dado** un PIM con 224 SKUs y un master de costos con 220 SKUs **Cuando** ejecuto `GET /reports/cross-validation` **Entonces** el sistema reporta 4 SKUs sin costes y 0 huérfanos (o viceversa).
- **Dado** cada SKU sin coste **Cuando** lo veo en la UI **Entonces** puedo asignar owner + due-date.
- **Dado** el reporte **Cuando** lo descargo **Entonces** queda como CSV con timestamp y como entregable obligatorio S2 (BR-1a-15).

**Story points**: 5
**Sprint**: S2
**Dependencias**: US-1A-06-01, US-1A-06-02.
**Notas técnicas**: FR-1a-13, BR-1a-15, UC-1a-09.

---

### EP-1A-07 — RBAC + i18n UI + Audit trail

#### US-1A-07-01 — Tabla `users` espejo de `auth.users` con campo `role` y `ui_locale`

**Como** dev backend
**quiero** la tabla `public.users` con FK a `auth.users` y campos `role` + `ui_locale`
**para** RBAC declarativo y persistencia de preferencia de idioma.

**Acceptance Criteria (BDD)**:
- **Dado** el trigger `on_auth_user_created` **Cuando** un usuario se registra **Entonces** se inserta en `public.users` con `role='comercial'` (default) y `ui_locale='es'`.
- **Dado** un admin **Cuando** asigna rol `gerente` **Entonces** queda en `audit_events`.
- **Dado** un usuario **Cuando** cambia `ui_locale` a `en` **Entonces** persiste y la sesión recarga UI en inglés.

**Story points**: 3
**Sprint**: S3
**Dependencias**: US-1A-01-07.
**Notas técnicas**: FR-1a-10, FR-1a-12, NFR-21.

#### US-1A-07-02 — RLS policies `products`, `costs`, `prices`, `audit_events`

**Como** dev backend
**quiero** RLS policies declarativas que enforcen RBAC en BD
**para** defense in depth (auth en API + RLS en BD).

**Acceptance Criteria (BDD)**:
- **Dado** que soy `comercial` autenticado **Cuando** intento `INSERT INTO prices ... status='approved'` **Entonces** RLS deniega (sólo `gerente` puede aprobar).
- **Dado** que soy `ti` **Cuando** intento `UPDATE products SET name_en = ...` **Entonces** RLS deniega (write reservado a `comercial`).
- **Dado** que soy `gerente` **Cuando** consulto `SELECT * FROM audit_events` **Entonces** RLS permite.

**Story points**: 5
**Sprint**: S3
**Dependencias**: US-1A-07-01.
**Notas técnicas**: NFR-07, NFR-11, FR-1a-10.

#### US-1A-07-03 — Triggers `audit_events` en tablas críticas

**Como** dev backend
**quiero** triggers `BEFORE UPDATE/INSERT/DELETE` en `products`, `costs`, `suppliers`, `currencies`, `fx_rates`, `product_translations` que persistan `payload_before`, `payload_after`, `diff`
**para** auditabilidad VAT-compliant.

**Acceptance Criteria (BDD)**:
- **Dado** un UPDATE en `products.name_en` **Cuando** se persiste **Entonces** el trigger registra `audit_events(entity='products', entity_id, field='name_en', payload_before, payload_after, diff, actor=auth.uid(), source='ui')`.
- **Dado** una consulta `GET /audit?entity=products&entity_id=42` **Cuando** la ejecuto como Gerente **Entonces** retorna histórico cronológico.
- **Dado** un intento de UPDATE en `audit_events` **Cuando** se ejecuta **Entonces** falla (append-only, BR-1a-12, NFR-34).

**Story points**: 5
**Sprint**: S3
**Dependencias**: US-1A-02-01, US-1A-04-02, US-1A-05-02.
**Notas técnicas**: FR-1a-11, BR-1a-12, NFR-33, NFR-34, UC-1a-11.

#### US-1A-07-04 — i18n UI con next-intl (ES + EN, selector usuario)

**Como** Comercial / Gerente
**quiero** elegir idioma de la UI (ES o EN) y que persista
**para** trabajar cómodo según preferencia.

**Acceptance Criteria (BDD)**:
- **Dado** un usuario con `ui_locale='es'` **Cuando** entra a la app **Entonces** todos los strings se renderizan en español.
- **Dado** un usuario que cambia a `en` **Cuando** confirma **Entonces** el cambio persiste en `users.ui_locale` y la sesión recarga UI en inglés.
- **Dado** un string sin traducción EN **Cuando** se renderiza **Entonces** se muestra en español con un warning en consola dev (no bloqueante).

**Story points**: 3
**Sprint**: S3
**Dependencias**: US-1A-07-01.
**Notas técnicas**: FR-1a-12, NFR-21, NFR-24, UC-1a-12.

#### US-1A-07-05 — Endpoint `GET /audit/export.csv` firmado para FTA

**Como** Gerente / TI
**quiero** exportar `audit_events` como CSV firmado por rango de fechas
**para** cumplir con auditorías FTA (VAT UAE 2026).

**Acceptance Criteria (BDD)**:
- **Dado** un Gerente **Cuando** llama `GET /audit/export.csv?from=2026-01-01&to=2026-12-31` **Entonces** el sistema retorna CSV con todos los eventos del rango y un hash SHA-256 firmado.
- **Dado** un usuario `comercial` **Cuando** intenta el endpoint **Entonces** RBAC deniega.
- **Dado** el CSV descargado **Cuando** se valida el hash **Entonces** coincide con el reportado en la respuesta.

**Story points**: 5
**Sprint**: S3
**Dependencias**: US-1A-07-03.
**Notas técnicas**: NFR-08, NFR-36, Q-13.

#### US-1A-07-06 — Dashboard "SKUs que requieren atención" para Comercial

**Como** Comercial
**quiero** un hero dashboard con SKUs `partial`/`blocked`, propuestas pendientes y cards de acción rápida
**para** orientarme al inicio de jornada.

**Acceptance Criteria (BDD)**:
- **Dado** que soy Comercial **Cuando** entro a la app **Entonces** veo "Hola {nombre} — N SKUs partial, M blocked, P propuestas pending con tu Gerente".
- **Dado** que clico la card "Importar PIM" **Cuando** lo hago **Entonces** abre el wizard de import.
- **Dado** la tabla "SKUs que requieren atención" **Cuando** la filtro por `image_status=broken_link` **Entonces** veo sólo esos.

**Story points**: 5
**Sprint**: S3
**Dependencias**: US-1A-02-09, US-1A-02-04.
**Notas técnicas**: PRD §12.1.

---

### EP-1A-08 — Scheduler editable + UI Jobs admin (ADR-046)

#### US-1A-08-01 — Tabla `job_definitions` + RLS + seeds Alembic

**Como** dev backend
**quiero** la migración Alembic que crea `public.job_definitions` con sus enums (`schedule_type_t`, `job_owner_t`, `job_status_t`), índices, RLS policies y seeds iniciales (6 jobs base)
**para** que el DatabaseScheduler tenga estructura y datos de arranque sin tocar código.

**Acceptance Criteria (BDD)**:
- **Dado** la migración aplicada **Cuando** consulto `\d public.job_definitions` **Entonces** existen columnas `code, task_name, owner, schedule_type, cron_expression, interval_seconds, timezone, queue, args, kwargs, enabled, last_run_at, next_run_at, last_status, last_error, edited_by, edited_at` con los tipos del DDL en `mt-jobs-module-design.md` §6.4.1.
- **Dado** la migración seed **Cuando** consulto `select code, owner, cron_expression from public.job_definitions order by code` **Entonces** retorna las 6 filas base con timezone `Asia/Dubai`: `daily_digest`, `daily_pim_diff_audit`, `hourly_fx_recalc`, `nightly_audit_archival`, `nightly_image_orphan_cleanup`, `weekly_kpi`.
- **Dado** un usuario `gerente_comercial` autenticado **Cuando** ejecuta `UPDATE public.job_definitions SET cron_expression='0 9 * * *' WHERE code='daily_digest'` **Entonces** la RLS lo permite.
- **Dado** un usuario `gerente_comercial` **Cuando** intenta `UPDATE public.job_definitions SET cron_expression='0 9 * * *' WHERE code='nightly_audit_archival'` (owner=infra) **Entonces** la RLS deniega.
- **Dado** un usuario `comercial` **Cuando** intenta cualquier UPDATE **Entonces** la RLS deniega; SELECT está permitido.

**Story points**: 3
**Sprint**: S3
**Dependencias**: US-1A-01-08 (Alembic bootstrap), US-1A-07-01 (tabla `users` + roles).
**Notas técnicas**: ADR-046, mt-jobs-module-design.md §6.4.1-6.4.3, arquitectura §10.5.

#### US-1A-08-02 — DatabaseScheduler integrado a Celery beat

**Como** dev backend
**quiero** un DatabaseScheduler operativo (librería `celery-sqlalchemy-scheduler` o scheduler custom de ~150 líneas) que polea `public.job_definitions` cada N segundos y dispara tasks via `celery_app.send_task` respetando `enabled`, `cron_expression`/`interval_seconds`, `timezone`, `queue`, `args`, `kwargs`, y persiste `last_run_at` / `next_run_at` / `last_status`
**para** que cambios en la tabla se reflejen en el siguiente ciclo del beat sin redeploy.

**Acceptance Criteria (BDD)**:
- **Dado** un job `daily_digest` con `cron_expression='*/2 * * * *'` (cada 2 min, para test) y `enabled=true` **Cuando** el contenedor `celery-beat` corre **Entonces** la task `mt.notifications.send_daily_digest` se encola cada 2 minutos y `last_run_at` / `next_run_at` se actualizan.
- **Dado** un admin que cambia `cron_expression` a `*/5 * * * *` via SQL **Cuando** transcurre el siguiente ciclo de poll del scheduler (≤ 30 s) **Entonces** la próxima ejecución respeta el nuevo cron sin restart del beat.
- **Dado** un job con `enabled=false` **Cuando** llega su `next_run_at` **Entonces** NO se encola la task.
- **Dado** una falla en el dispatch (broker Redis caído) **Cuando** ocurre **Entonces** `last_status='failure'`, `last_error` se rellena con el mensaje, y Sentry recibe el evento.
- **Dado** el contenedor `celery-beat` **Cuando** se ejecuta `docker inspect mt-celery-beat` **Entonces** el healthcheck retorna healthy (heartbeat < 90 s).
- **Dado** se reinicia `celery-beat` **Cuando** vuelve a arrancar **Entonces** continúa con los `next_run_at` persistidos en BD (no salta horarios ni dispara duplicados).

**Story points**: 8
**Sprint**: S3
**Dependencias**: US-1A-08-01.
**Notas técnicas**: ADR-046, mt-jobs-module-design.md §6.4 + §6.6 (docker-compose). **Decisión Sprint 0**: validar si `celery-sqlalchemy-scheduler` encaja con SQLAlchemy 2.0 async; si no, scheduler custom en `app/scheduler/database_scheduler.py`.

#### US-1A-08-03 — Audit trigger sobre `job_definitions`

**Como** dev backend
**quiero** un trigger Postgres `trg_audit_job_definitions` que registre INSERT/UPDATE/DELETE sobre `job_definitions` en `audit_events` con `payload_before`, `payload_after`, `actor_id`
**para** que cualquier cambio de horario quede trazable para FTA/VAT y para troubleshooting.

**Acceptance Criteria (BDD)**:
- **Dado** un UPDATE en `job_definitions.cron_expression` **Cuando** se persiste **Entonces** `audit_events` registra una fila con `entity='job_definitions'`, `entity_id=<uuid>`, `action='update'`, `payload_before` y `payload_after` JSONB con la fila completa, `actor_id` resuelto desde `request.jwt.claim.sub`.
- **Dado** un INSERT desde la migration seed **Cuando** se aplica **Entonces** registra `action='create'` con `actor_id=null` (sistema).
- **Dado** un DELETE **Cuando** se ejecuta **Entonces** registra `action='delete'` con `payload_after=null`.
- **Dado** una consulta `GET /admin/jobs/{id}/audit?limit=20` **Cuando** se invoca como TI **Entonces** retorna las últimas 20 entradas con diff legible.

**Story points**: 2
**Sprint**: S3
**Dependencias**: US-1A-08-01, US-1A-07-03 (audit_events table + triggers pattern).
**Notas técnicas**: ADR-046, mt-jobs-module-design.md §6.4.4.

#### US-1A-08-04 — UI admin `/admin/jobs` lista + edit + enable

**Como** TI Integración / Gerente Comercial
**quiero** una pantalla `/admin/jobs` con tabla de jobs (TanStack Table), filtros por owner/enabled/last_status, toggle de `enabled` inline y dialog de edit con react-hook-form + Zod
**para** ajustar horarios sin abrir un PR.

**Acceptance Criteria (BDD)**:
- **Dado** que soy `ti_integracion` **Cuando** entro a `/admin/jobs` **Entonces** veo todos los jobs con sus columnas y puedo editar cualquier campo.
- **Dado** que soy `gerente_comercial` **Cuando** entro a `/admin/jobs` **Entonces** veo todos los jobs, pero el dialog de edit solo me deja modificar `cron_expression`, `timezone`, `enabled` y solo si `owner='business'`.
- **Dado** que toggleo `enabled` de `daily_digest` a off **Cuando** confirmo **Entonces** el cambio persiste, la UI muestra toast "Job daily_digest deshabilitado" y `audit_events` registra el cambio.
- **Dado** que soy `comercial` **Cuando** intento entrar a `/admin/jobs` **Entonces** el `RbacGuard` me redirige y la API retorna 403.

**Story points**: 5
**Sprint**: S4
**Dependencias**: US-1A-08-01, US-1A-08-02, US-1A-08-03, US-1A-07-02 (RLS).
**Notas técnicas**: ADR-046, mt-jobs-module-design.md §6.4.6.

#### US-1A-08-05 — UI cron preview + Run now + audit drawer

**Como** TI Integración / Gerente Comercial
**quiero** que la pantalla `/admin/jobs` muestre las próximas 5 ejecuciones de un cron antes de guardar, un botón "Run now" para encolar la task manualmente, y un drawer lateral con el audit trail del job
**para** validar cambios y diagnosticar incidentes sin ssh al server.

**Acceptance Criteria (BDD)**:
- **Dado** que edito `cron_expression='0 8 * * *'` con timezone `Asia/Dubai` en el dialog **Cuando** el campo cambia **Entonces** la UI llama `GET /admin/jobs/{id}/cron-preview?expr=0+8+*+*+*&tz=Asia/Dubai&n=5` y renderiza las próximas 5 ejecuciones en formato humano (ej. "Hoy 08:00 GST, Mañana 08:00 GST, ...").
- **Dado** que clico "Run now" en `daily_digest` **Cuando** confirmo **Entonces** el backend encola la task con `trigger_source='MANUAL'`, crea fila en `job_runs` y la UI muestra toast "Encolado, run_id=<uuid>" con link a la página de seguimiento del run.
- **Dado** que abro el drawer "Audit" del job **Cuando** se renderiza **Entonces** veo las últimas 20 entradas con `actor`, `action`, `at`, y un diff visual de `payload_before` ↔ `payload_after`.
- **Dado** que un cron expression inválido **Cuando** lo escribo **Entonces** el preview muestra error "expresión cron inválida" y el botón "Guardar" queda disabled.

**Story points**: 5
**Sprint**: S4
**Dependencias**: US-1A-08-04.
**Notas técnicas**: ADR-046, mt-jobs-module-design.md §6.4.6.

---

### EP-1B-01 — Motor de pricing multi-canal/esquema

#### US-1B-01-01 — Extracción de reglas v5.1 a pseudocódigo + golden numbers (S0)

**Como** TI MT + BR
**quiero** las reglas v5.1 del Excel/VBA documentadas como pseudocódigo + 30 SKUs golden numbers
**para** que la decisión port-vs-rewrite sea informada y la implementación sea testeable.

**Acceptance Criteria (BDD)**:
- **Dado** el archivo `MT_Pricing_Run_Kit/src/pricing.py` v5.1 + macros VBA **Cuando** se documenta **Entonces** el doc `docs/pricing-rules-v51.md` describe G1/G2, alertas, fallback tiers, bundling psicológico (XX,99 / XX,49 AED) en español.
- **Dado** 30 SKUs muestra **Cuando** se ejecuta v5.1 sobre ellos **Entonces** se persisten outputs como `tests/golden/v51_outputs.json` (input/expected).
- **Dado** los golden numbers **Cuando** Paula los revisa **Entonces** firma el doc como representativo.

**Story points**: 8
**Sprint**: S0
**Dependencias**: ninguna.
**Notas técnicas**: PRD §13.1 entregable 4-5, Q-10.

#### US-1B-01-02 — Schema `prices` con state machine y constraint CHECK

**Como** dev backend
**quiero** la migration que crea `prices` con `status` enum (CHECK constraint) y los índices del PRD
**para** que el motor de pricing tenga tabla destino e impedir estados inválidos.

**Acceptance Criteria (BDD)**:
- **Dado** la migration aplicada **Cuando** intento INSERT con `status='aprobado'` (typo) **Entonces** el CHECK falla.
- **Dado** un INSERT válido con `status='draft'` **Cuando** se ejecuta **Entonces** persiste.
- **Dado** los índices declarados **Cuando** consulto `\d prices` **Entonces** existen `idx_prices_lookup`, `idx_prices_status`, `idx_prices_pending`.

**Story points**: 3
**Sprint**: S4
**Dependencias**: US-1A-04-02.
**Notas técnicas**: PRD §10.1.

#### US-1B-01-03 — Servicio `PricingEngine.calculate(sku, channel, scheme, fx_rate_id)` (Python puerto v5.1)

**Como** dev backend
**quiero** el servicio puro `PricingEngine.calculate` que dado un SKU + canal + esquema + FX retorna `{price_aed, pvp_min, margin_pct, rule_applied, breakdown, alerts}`
**para** centralizar las reglas y testearlas con golden numbers.

**Acceptance Criteria (BDD)**:
- **Dado** un SKU con coste FBA y canal Amazon UAE **Cuando** invoco `PricingEngine.calculate(sku, 'AMAZON_UAE', 'FBA', fx_rate_id)` **Entonces** retorna estructura completa con `rule_applied` (string), `breakdown` (JSON), `alerts` array.
- **Dado** los 30 SKUs golden **Cuando** ejecuto los tests **Entonces** 100 % paridad de outputs vs `tests/golden/v51_outputs.json`.
- **Dado** un coste superior al `pvp_min` permitido **Cuando** se calcula **Entonces** retorna `alerts=[{level:'critical', code:'price_below_pvp_min'}]`.

**Story points**: 13
**Sprint**: S4
**Dependencias**: US-1B-01-01, US-1B-01-02.
**Notas técnicas**: FR-1b-01, NFR-01, sec. 13.3 S4.

#### US-1B-01-04 — Endpoint `POST /prices/recalculate` (single SKU + masivo)

**Como** Comercial
**quiero** disparar recálculo de precios (single o masivo)
**para** mantener propuestas actualizadas tras cambios de coste/FX.

**Acceptance Criteria (BDD)**:
- **Dado** `POST /prices/recalculate` con `scope='single', product_id=42` **Cuando** se ejecuta **Entonces** el sistema calcula propuestas para los canales/esquemas activos del SKU < 5 s y retorna IDs.
- **Dado** `scope='all', trigger='fx_change', fx_rate_id=1234` **Cuando** se ejecuta **Entonces** el sistema dispara job Celery, retorna `task_id`, y el job procesa < 60 s para 224 × 5 × 4.
- **Dado** un job en curso **Cuando** consulto `GET /tasks/{task_id}` **Entonces** retorna progreso (% completado, ETA).

**Story points**: 8
**Sprint**: S4
**Dependencias**: US-1B-01-03.
**Notas técnicas**: FR-1b-11, NFR-01, NFR-02, UC-1b-10, UC-1b-11.

#### US-1B-01-05 — Simulación what-if multi-canal sin persistir como activo

**Como** Comercial / Gerente
**quiero** simular escenarios (FX hipotético, canal en `pre_launch`) sin tocar `prices` activos
**para** evaluar antes de comprometer.

**Acceptance Criteria (BDD)**:
- **Dado** Noon UAE en `pre_launch` **Cuando** envío `POST /prices/simulate` con `fx_rate=4.18 AED/EUR` y `scope=all` **Entonces** el sistema retorna precios simulados sin INSERT en `prices`.
- **Dado** un escenario simulado **Cuando** lo guardo como "escenario nombrado" en `pricing_scenarios` **Entonces** queda disponible para comparación.
- **Dado** dos escenarios guardados **Cuando** llamo `GET /pricing_scenarios/compare?a=X&b=Y` **Entonces** el sistema retorna diff por SKU.

**Story points**: 8
**Sprint**: S4
**Dependencias**: US-1B-01-03.
**Notas técnicas**: FR-1b-02, UC-1b-02.

#### US-1B-01-06 — Pantalla "Disparar recálculo" con preview + ETA + progreso

**Como** Comercial
**quiero** una pantalla guiada para disparar recálculo
**para** entender qué afecta antes de ejecutar.

**Acceptance Criteria (BDD)**:
- **Dado** un cambio de FX **Cuando** abro la pantalla **Entonces** veo selector trigger + dropdown FX, preview "Esto afecta 187 SKUs × 4 × 5 = 3.740 propuestas".
- **Dado** que clico Ejecutar **Cuando** confirmo **Entonces** veo barra de progreso refrescando cada 2 s con ETA.
- **Dado** que finaliza **Cuando** veo el resultado **Entonces** la pantalla muestra totales `auto_approved` / `pending_review` y link directo a la cola del Gerente.

**Story points**: 5
**Sprint**: S4
**Dependencias**: US-1B-01-04.
**Notas técnicas**: PRD §12.3.

---

### EP-1B-02 — Workflow de aprobación por excepción

#### US-1B-02-01 — State machine `prices.status` enforcement (servicio + DB)

**Como** dev backend
**quiero** un servicio `PriceStateMachine` que valide transiciones y un trigger Postgres como segunda barrera
**para** que la state machine sea inviolable.

**Acceptance Criteria (BDD)**:
- **Dado** un precio en `draft` **Cuando** intento transicionar a `approved` **Entonces** el servicio rechaza con `InvalidTransition` (debe pasar por `auto_approved` o `pending_review`).
- **Dado** un precio `pending_review` **Cuando** Gerente aprueba **Entonces** transita a `approved` y queda registrado.
- **Dado** un INSERT directo a la BD con transición inválida **Cuando** se intenta **Entonces** el trigger lo rechaza.

**Story points**: 5
**Sprint**: S5
**Dependencias**: US-1B-01-02.
**Notas técnicas**: BR-1b-04, sec. 7.4 PRD.

#### US-1B-02-02 — Tabla `exception_rules` con versionado + UI configuración (Gerente)

**Como** Gerente
**quiero** editar reglas de excepción (umbrales delta margen, FX swing, margen mínimo) por canal/esquema
**para** ajustar política sin ticket TI.

**Acceptance Criteria (BDD)**:
- **Dado** que soy Gerente **Cuando** edito la regla "Amazon UAE × FBA" a `delta margen > 8 %` **Entonces** el sistema crea versión nueva con `effective_from=now()`, cierra la anterior con `effective_to=now()`, y aplica a propuestas futuras.
- **Dado** una propuesta vieja **Cuando** la consulto **Entonces** referencia `exception_rule_version_id` vigente al momento.
- **Dado** que soy Comercial **Cuando** intento editar la regla **Entonces** RBAC deniega.

**Story points**: 5
**Sprint**: S5
**Dependencias**: US-1B-01-02, US-1A-07-02.
**Notas técnicas**: FR-1b-04, BR-1b-13, FR-1b-14, UC-1b-06.

#### US-1B-02-03 — Lógica `auto_approved` vs `pending_review` con triggers (delta margen, FX swing, margen mínimo)

**Como** dev backend
**quiero** que tras `recalculate`, cada propuesta nueva entre automáticamente a `auto_approved` (delta ≤ X %) o `pending_review` (delta > X % o alerta crítica)
**para** que el motor decida sin intervención.

**Acceptance Criteria (BDD)**:
- **Dado** una propuesta con delta margen 3 % y sin alertas **Cuando** se persiste **Entonces** estado pasa a `auto_approved`.
- **Dado** una propuesta con delta margen 12 % **Cuando** se persiste **Entonces** estado pasa a `pending_review`.
- **Dado** una propuesta que cruza `min_margin_pct` **Cuando** se persiste **Entonces** estado pasa a `pending_review` aunque delta margen sea pequeño.

**Story points**: 5
**Sprint**: S5
**Dependencias**: US-1B-01-03, US-1B-02-02.
**Notas técnicas**: FR-1b-03, BR-1b-02, BR-1b-03.

#### US-1B-02-04 — Endpoints `POST /prices/{id}/approve` y `POST /prices/{id}/reject` con audit

**Como** Gerente
**quiero** aprobar o rechazar propuestas individuales
**para** decidir caso por caso.

**Acceptance Criteria (BDD)**:
- **Dado** una propuesta `pending_review` **Cuando** envío `POST /prices/{id}/approve` con `comment="aprobado"` **Entonces** el estado pasa a `approved`, queda con `approved_by`, `approved_at`, `approval_comment` y registra `audit_events`.
- **Dado** una propuesta **Cuando** envío `reject` con comentario **Entonces** estado pasa a `rejected` y vuelve al Comercial como `revised`.
- **Dado** que soy Comercial **Cuando** intento `approve` **Entonces** RBAC deniega 403.

**Story points**: 3
**Sprint**: S5
**Dependencias**: US-1B-02-01.
**Notas técnicas**: FR-1b-03, UC-1b-03, UC-1b-05.

#### US-1B-02-05 — Endpoint `POST /prices/bulk-approve` con comentario obligatorio

**Como** Gerente
**quiero** aprobar lotes homogéneos con un único comentario justificativo
**para** procesar 32 FX-swing en un click.

**Acceptance Criteria (BDD)**:
- **Dado** una cola de 32 pendientes **Cuando** envío `POST /prices/bulk-approve` con `ids=[…]` y `comment="variación FX legítima 2026-06-12"` **Entonces** los 32 pasan a `approved` con el comentario asociado y `audit_events` por cada uno.
- **Dado** un `bulk-approve` sin comentario **Cuando** se envía **Entonces** retorna 422 (BR-1b-11).
- **Dado** un Comercial **Cuando** intenta **Entonces** RBAC deniega.

**Story points**: 3
**Sprint**: S5
**Dependencias**: US-1B-02-04.
**Notas técnicas**: FR-1b-05, BR-1b-11, UC-1b-04.

#### US-1B-02-06 — Cola del Gerente con tabla + bulk-select + sidebar detalle

**Como** Gerente
**quiero** una pantalla con la cola filtrable (hoy / semana / pendientes / escaladas) y bulk-select
**para** trabajar la cola en una pantalla.

**Acceptance Criteria (BDD)**:
- **Dado** que soy Gerente **Cuando** entro a "Mi cola" **Entonces** veo resumen sticky "142 auto / 45 pendientes / 3 escaladas" + tabla con columnas SKU, canal, esquema, precio anterior/nuevo, margen anterior/nuevo, alerta, razón excepción, edad (h).
- **Dado** que selecciono 32 pendientes con FX swing **Cuando** clico "Aprobar lote" **Entonces** se abre modal de comentario y al confirmar dispara `bulk-approve`.
- **Dado** que clico una fila **Cuando** se abre el sidebar **Entonces** veo breakdown completo, regla aplicada, FX, audit trail.

**Story points**: 8
**Sprint**: S5
**Dependencias**: US-1B-02-04, US-1B-02-05.
**Notas técnicas**: PRD §12.4, NFR-27.

#### US-1B-02-07 — Job digest diario a las 18:00 UAE con notificación in-app + email

**Como** Gerente
**quiero** un digest diario al final de la jornada con auto-aprobados + pendientes + escaladas + top razones
**para** orientarme al día siguiente.

**Acceptance Criteria (BDD)**:
- **Dado** las 18:00 UAE **Cuando** el job de digest se ejecuta **Entonces** el Gerente recibe notificación in-app + email con resumen del día y deep-links a la cola.
- **Dado** un Gerente con email opt-out **Cuando** se ejecuta **Entonces** sólo recibe in-app.
- **Dado** una zona horaria diferente del Gerente **Cuando** configura `digest_hour=20` **Entonces** el job dispara a las 20:00 según preferencia.

**Story points**: 5
**Sprint**: S5
**Dependencias**: US-1B-02-06.
**Notas técnicas**: FR-1b-05, UC-1b-12, sec. 12.7 PRD.

#### US-1B-02-08 — Job de escalado >48 h con flag `escalated=true` + delegación

**Como** Gerente
**quiero** que propuestas con > 48 h en `pending_review` se escalen automáticamente con notificación al delegado
**para** que ausencias no bloqueen.

**Acceptance Criteria (BDD)**:
- **Dado** una propuesta con > 48 h en `pending_review` **Cuando** se ejecuta el job (cada 2 h) **Entonces** el sistema marca `escalated=true` y notifica al delegado configurado.
- **Dado** un Gerente sin delegado configurado **Cuando** se escala **Entonces** notifica al `ti` con flag.
- **Dado** una propuesta `approved` después de escalada **Cuando** se aprueba **Entonces** queda con histórico de escalación en `audit_events`.

**Story points**: 5
**Sprint**: S5
**Dependencias**: US-1B-02-04.
**Notas técnicas**: FR-1b-13, BR-1b-06, UC-1b-13, Q-17.

#### US-1B-02-09 — Audit trail extendido a `prices`, `exception_rules`, transición de canal

**Como** TI / Gerente
**quiero** que cada cambio de precio, regla o estado de canal quede en `audit_events` con `rule_version_id`, `fx_rate_id`, `breakdown_snapshot`
**para** reproducibilidad regulatoria.

**Acceptance Criteria (BDD)**:
- **Dado** una aprobación de Gerente **Cuando** se persiste **Entonces** `audit_events` registra `entity='prices', action='approve', actor=gerente_id, timestamp, comment, rule_version, fx_rate_id, breakdown_snapshot`.
- **Dado** una transición de canal **Cuando** ocurre **Entonces** `audit_events` registra el cambio de estado.
- **Dado** un cambio de regla **Cuando** se persiste **Entonces** queda registrado con versión.

**Story points**: 3
**Sprint**: S5
**Dependencias**: US-1A-07-03, US-1B-02-04.
**Notas técnicas**: FR-1b-12, NFR-33, BR-1b-05, UC-1b-14.

---

### EP-1B-03 — Estados de canal + simulación

#### US-1B-03-01 — Tabla `channels` con 6 estados + `channel_state_history`

**Como** dev backend
**quiero** la migration con la tabla `channels` (CHECK constraint en `state`) y `channel_state_history`
**para** soportar transiciones gobernadas.

**Acceptance Criteria (BDD)**:
- **Dado** la migration aplicada **Cuando** intento INSERT con `state='active'` (no enum válido) **Entonces** el CHECK falla.
- **Dado** un canal seeded `AMAZON_UAE` con `state='inactive'` **Cuando** se transiciona **Entonces** la fila se actualiza y `channel_state_history` registra `from_state, to_state, actor, comment`.
- **Dado** los canales seeded **Cuando** consulto **Entonces** existen Amazon UAE, Noon UAE, B2C Direct, B2B Direct.

**Story points**: 3
**Sprint**: S6
**Dependencias**: US-1A-04-01.
**Notas técnicas**: PRD §10.1, FR-1b-06.

#### US-1B-03-02 — Endpoint `POST /channels/{id}/transition` con validación de prerequisitos

**Como** TI Integración
**quiero** transicionar canal `pre_launch → pilot` y validar que los SKUs subset tengan precios `approved`/`auto_approved`
**para** evitar pilotos con datos a medias.

**Acceptance Criteria (BDD)**:
- **Dado** Noon UAE en `pre_launch` **Cuando** TI lo pasa a `pilot` con `subset_skus=[1,2,3,...]` **Entonces** el sistema valida que esos SKUs tengan precio `approved`/`auto_approved` para esquema Marketplace × Noon UAE y reporta los faltantes.
- **Dado** un subset con SKUs faltantes **Cuando** TI confirma con override **Entonces** se transiciona pero queda flag `pilot_with_warnings=true` en `channel_state_history`.
- **Dado** que soy Comercial **Cuando** intento `transition` **Entonces** RBAC deniega (sólo TI, BR-1b-08).

**Story points**: 8
**Sprint**: S6
**Dependencias**: US-1B-03-01, US-1B-02-04.
**Notas técnicas**: FR-1b-06, BR-1b-08, UC-1b-07.

#### US-1B-03-03 — Pause de canal congela exports activos sin tocar precios aprobados

**Como** TI Integración
**quiero** que al pasar un canal a `paused` los exports activos se bloqueen pero los precios aprobados se preserven
**para** poder despausar sin re-aprobar.

**Acceptance Criteria (BDD)**:
- **Dado** Amazon UAE en `live` con 50 SKUs `exported` **Cuando** TI lo pasa a `paused` **Entonces** el sistema bloquea exports activos y emite alerta a Comercial + Gerente.
- **Dado** un canal `paused` **Cuando** TI lo retorna a `live` **Entonces** los precios aprobados siguen vigentes y los exports se rehabilitan.
- **Dado** un canal `deprecated` **Cuando** TI intenta crear propuesta nueva **Entonces** el sistema rechaza (BR-1b-10).

**Story points**: 5
**Sprint**: S6
**Dependencias**: US-1B-03-02.
**Notas técnicas**: FR-1b-06, BR-1b-09, BR-1b-10.

#### US-1B-03-04 — Feature flag `channel_recommendation` (default off Fase 1)

**Como** TI Integración
**quiero** un feature flag global que controle si el sistema muestra `canal_recomendado`
**para** mantenerlo off en Fase 1 (no hay canales `live`) y encenderlo en Fase 3.

**Acceptance Criteria (BDD)**:
- **Dado** `feature.channel_recommendation = off` **Cuando** consulto un SKU **Entonces** la respuesta no incluye `canal_recomendado`.
- **Dado** flag `on` y 2 canales `live` **Cuando** consulto un SKU **Entonces** retorna `canal_recomendado` con justificación.
- **Dado** que soy `ti` **Cuando** llamo `PATCH /feature-flags/channel_recommendation` **Entonces** se persiste y registra `audit_events`.

**Story points**: 3
**Sprint**: S6
**Dependencias**: US-1B-03-01.
**Notas técnicas**: FR-1b-10, BR-1b-07, UC-1b-15, Q-11.

#### US-1B-03-05 — Consola TI "Canales" con tabla + transiciones + histórico

**Como** TI Integración
**quiero** una pantalla con la tabla de canales, estado, schemes_supported, último cambio y botón transicionar
**para** operar sin APIs.

**Acceptance Criteria (BDD)**:
- **Dado** la consola TI **Cuando** entro **Entonces** veo tabla con todos los canales y sus estados.
- **Dado** un canal seleccionado **Cuando** clico "Transicionar" **Entonces** abre modal con destino válido + comentario obligatorio + preview de SKUs faltantes.
- **Dado** que clico "Histórico" **Cuando** se carga **Entonces** veo línea de tiempo de cambios con actores y comentarios.

**Story points**: 5
**Sprint**: S6
**Dependencias**: US-1B-03-02, US-1B-03-03.
**Notas técnicas**: PRD §12.6.

---

### EP-1B-04 — Connectors base + shadow publish

#### US-1B-04-01 — Puerto `ChannelPublisher` con adapter skeleton Amazon UAE / Noon UAE / Shopify

**Como** dev backend
**quiero** una interfaz Python `ChannelPublisher` con métodos `validate_payload`, `shadow_publish`, `export_csv` y 3 implementaciones skeleton
**para** swap de adapters sin refactor.

**Acceptance Criteria (BDD)**:
- **Dado** la interfaz `ChannelPublisher` **Cuando** consulto la API interna **Entonces** existe con métodos abstractos.
- **Dado** los 3 adapters skeleton (`AmazonUAEAdapter`, `NoonUAEAdapter`, `ShopifyAdapter`) **Cuando** ejecuto tests **Entonces** cada uno responde a `validate_payload({sku, price, ...})` y retorna estructura conocida.
- **Dado** un adapter en producción **Cuando** se reemplaza por mock **Entonces** los tests pasan sin cambios fuera del bind.

**Story points**: 5
**Sprint**: S6
**Dependencias**: US-1B-03-01.
**Notas técnicas**: arquitectura ports/adapters.

#### US-1B-04-02 — Endpoint `POST /exports/{channel_code}` con filter runtime de la regla dura

**Como** TI / Comercial
**quiero** generar export CSV/XLSX por canal/esquema con filter runtime que excluye registros no aprobados
**para** cumplir BR-1b-01.

**Acceptance Criteria (BDD)**:
- **Dado** un canal Amazon UAE × esquema FBA con 220 SKUs aprobados + 4 pendientes **Cuando** ejecuto `POST /exports/AMAZON_UAE?scheme=FBA` **Entonces** el CSV contiene 220 filas (sólo `approved`/`auto_approved`), FX as-of estampado, y los 4 pendientes quedan en reporte como "bloqueado por estado".
- **Dado** el export ejecutado **Cuando** lo audito **Entonces** todas las filas tienen estado válido (verificación post-export).
- **Dado** un export **Cuando** finaliza **Entonces** se archiva como `last-known-good` con timestamp.

**Story points**: 8
**Sprint**: S6
**Dependencias**: US-1B-04-01, US-1B-02-04.
**Notas técnicas**: FR-1b-07, FR-1b-08, BR-1b-01, NFR-05, UC-1b-08.

#### US-1B-04-03 — Constraint DB que enforce regla dura no-export sin aprobación

**Como** dev backend
**quiero** un constraint declarativo (vista materializada o función de export) que impida exportar registros con estado inválido
**para** que la regla dura sea defense in depth (DB + runtime).

**Acceptance Criteria (BDD)**:
- **Dado** una función `export_for_channel(channel_id, scheme_id)` **Cuando** se invoca **Entonces** retorna sólo filas con `status IN ('approved','auto_approved')`.
- **Dado** un INSERT directo en una tabla `exports_manifest` con un `price_id` no aprobado **Cuando** se intenta **Entonces** la FK + CHECK lo rechazan.
- **Dado** auditoría sobre 1000 exports históricos **Cuando** se valida **Entonces** 0 registros con estado inválido.

**Story points**: 5
**Sprint**: S6
**Dependencias**: US-1B-04-02.
**Notas técnicas**: FR-1b-07, BR-1b-01, A-10.

#### US-1B-04-04 — Shadow publish a sandbox Amazon UAE con captura de respuesta + errores estructurados

**Como** TI Integración
**quiero** enviar el export a sandbox de Amazon UAE Seller Central y capturar respuesta + errores
**para** validar formato sin tocar producción.

**Acceptance Criteria (BDD)**:
- **Dado** un export Amazon UAE generado **Cuando** ejecuto `POST /exports/AMAZON_UAE/shadow-publish` **Entonces** el sistema lo carga al endpoint sandbox y persiste respuesta + errores estructurados en `shadow_publish_runs`.
- **Dado** un fallo de formato **Cuando** ocurre **Entonces** el reporte detalla campo, fila, código de error.
- **Dado** un éxito **Cuando** se confirma **Entonces** el run queda como `success` con timestamp.

**Story points**: 8
**Sprint**: S6
**Dependencias**: US-1B-04-01, US-1B-04-02.
**Notas técnicas**: FR-1b-09, BR-1b-14, UC-1b-09.

#### US-1B-04-05 — Job diario `last-known-good` regenera + archiva exports por canal

**Como** TI Integración
**quiero** un job que regenere y archive el último export aprobado por canal cada día
**para** tener red de seguridad de publicación manual.

**Acceptance Criteria (BDD)**:
- **Dado** las 23:00 UAE **Cuando** el job se ejecuta **Entonces** regenera export por canal en estado `live`/`pilot` y archiva en bucket `exports/last-known-good/{channel}/{YYYY-MM-DD}/`.
- **Dado** un archivo > 90 días **Cuando** el job de retención corre **Entonces** se purga (BR-1b-15).
- **Dado** un fallo **Cuando** ocurre **Entonces** Sentry captura y notifica a TI.

**Story points**: 3
**Sprint**: S6
**Dependencias**: US-1B-04-02.
**Notas técnicas**: BR-1b-15, sec. 15.4 PRD.

---

### EP-1B-05 — Hardening + cutover

#### US-1B-05-01 — Reporte diario de diff app vs Excel demo durante parallel run

**Como** Champion / Gerente
**quiero** un reporte automático que compare precios aprobados en app vs Excel demo
**para** identificar discrepancias durante parallel run.

**Acceptance Criteria (BDD)**:
- **Dado** parallel run en curso **Cuando** el job diario corre **Entonces** genera reporte CSV `parallel-run-diff-{YYYY-MM-DD}.csv` con SKUs donde precio app ≠ precio Excel.
- **Dado** un diff **Cuando** se detecta **Entonces** el reporte indica origen probable (FX inferido, regla cambiada, error import).
- **Dado** 0 diff durante 5 días consecutivos **Cuando** el job lo detecta **Entonces** marca el flag `cutover_ready=true`.

**Story points**: 5
**Sprint**: S7
**Dependencias**: US-1B-04-02, US-1A-06-06.
**Notas técnicas**: sec. 15.3 PRD, KR2 O1b.4.

#### US-1B-05-02 — Manual operativo `docs/handbook-es.md` validado por Champion

**Como** Backup Operator / Champion
**quiero** un manual operativo en español con runbooks (import, recálculo, aprobación, rollback)
**para** operar sin entrenamiento sincrónico.

**Acceptance Criteria (BDD)**:
- **Dado** el manual escrito **Cuando** el Champion lo revisa **Entonces** firma checklist de cobertura (import PIM, import costos, recálculo masivo, aprobación, escalado, rollback).
- **Dado** un Backup Operator nuevo **Cuando** sigue el manual **Entonces** completa import + 1 aprobación sin asistencia.
- **Dado** capturas de pantalla **Cuando** se incluyen **Entonces** corresponden a la versión actual de UI (no antigua).

**Story points**: 5
**Sprint**: S7
**Dependencias**: todas las US de Fase 1a/1b.
**Notas técnicas**: sec. 15.5 PRD.

#### US-1B-05-03 — Capacitación Backup Operator (≥ 2 sesiones hands-on + ejecución supervisada)

**Como** Sponsor / Champion
**quiero** que el Backup Operator complete ≥ 2 sesiones hands-on + 1 import + 1 aprobación
**para** mitigar single-point-of-failure (R-02).

**Acceptance Criteria (BDD)**:
- **Dado** el plan de capacitación **Cuando** se ejecutan las sesiones **Entonces** quedan grabadas y listadas en `docs/training-log.md`.
- **Dado** el Backup Operator **Cuando** ejecuta 1 import + 1 aprobación supervisado **Entonces** completa sin errores y firma el log.
- **Dado** el cutover **Cuando** se evalúa **Entonces** el Backup Operator está listado como ready.

**Story points**: 3
**Sprint**: S7
**Dependencias**: US-1B-05-02.
**Notas técnicas**: sec. 15.1 PRD, R-02.

#### US-1B-05-04 — Rollback playbook + Excel restorable 90 días

**Como** TI Integración
**quiero** un playbook de rollback documentado y verificado con un drill
**para** estar preparado si la plataforma cae.

**Acceptance Criteria (BDD)**:
- **Dado** `docs/runbook-cutover.md` **Cuando** se revisa **Entonces** detalla pasos de rollback a Excel demo + restore de DB desde backup.
- **Dado** un drill ensayado **Cuando** se ejecuta **Entonces** se completa < 4 h (NFR-16) y queda registrado en `docs/drill-log.md`.
- **Dado** 90 días post-cutover **Cuando** se intenta restaurar el Excel **Entonces** sigue accesible (read-only).

**Story points**: 5
**Sprint**: S7
**Dependencias**: US-1B-05-02.
**Notas técnicas**: NFR-16, NFR-17, sec. 15.4 PRD.

#### US-1B-05-05 — Cutover gate firmado por Gerente + TI + Sponsor

**Como** Sponsor MT
**quiero** firmar formalmente el cutover gate basado en checklist
**para** que el go-live sea formal y trazable.

**Acceptance Criteria (BDD)**:
- **Dado** el checklist de cutover (100 % migrado, 0 diff X días, audit muestra 50, backup operator OK, manual aprobado) **Cuando** se evalúa **Entonces** todos los items están en verde.
- **Dado** el gate listo **Cuando** los firmantes lo aprueban en `docs/cutover-signoff.md` **Entonces** queda firmado con fecha.
- **Dado** el cutover firmado **Cuando** la app va a prod **Entonces** Excel `stock_dubai_v23` queda como `_ARCHIVE_YYYY-MM-DD` read-only.

**Story points**: 3
**Sprint**: S7
**Dependencias**: US-1B-05-01, US-1B-05-02, US-1B-05-03, US-1B-05-04.
**Notas técnicas**: sec. 15.2 PRD, BR-1a-10.

#### US-1B-05-06 — Performance hardening (índices, query plans, p95 endpoints CRUD)

**Como** dev backend
**quiero** revisar query plans, agregar índices faltantes y validar latencia p95 < 250 ms en endpoints CRUD
**para** cumplir NFR-06.

**Acceptance Criteria (BDD)**:
- **Dado** los endpoints clave (`GET /products`, `GET /prices`, `GET /audit`) **Cuando** ejecuto load test con 50 RPS **Entonces** p95 < 250 ms.
- **Dado** un query plan con sequential scan en > 1k filas **Cuando** lo detecto **Entonces** agrego índice o reescribo query.
- **Dado** post-hardening **Cuando** corro el load test **Entonces** todos los KPIs cumplen.

**Story points**: 5
**Sprint**: S7
**Dependencias**: todas las US de Fase 1a/1b.
**Notas técnicas**: NFR-06, NFR-01, NFR-02.

#### US-1B-05-07 — Configurar dashboards observabilidad (lag aprobación, % auto, top razones, escaladas)

**Como** TI Integración / Gerente
**quiero** dashboards en Grafana / Better Stack con métricas de aprobación + salud sistema
**para** monitorear la operación post-cutover.

**Acceptance Criteria (BDD)**:
- **Dado** un dashboard "Aprobaciones" **Cuando** lo abro **Entonces** veo lag mediano del Gerente, % auto-aprobado, top razones de excepción, escaladas semanales.
- **Dado** un dashboard "Salud" **Cuando** lo abro **Entonces** veo DB conn pool, cola Celery (depth, latencia), exports diarios, jobs FX.
- **Dado** una métrica fuera de umbral **Cuando** ocurre **Entonces** Better Stack alerta a TI.

**Story points**: 5
**Sprint**: S7
**Dependencias**: US-1A-01-06.
**Notas técnicas**: NFR-27, NFR-28.

---

### EP-RND-01 — Sistema de comparación de productos (workstream R&D paralelo)

#### US-RND-01-01 — Iniciar demos comerciales paralelas (Intelligence Node + Skuuudle, S0)

**Como** Sponsor / R&D Champion
**quiero** lanzar demos comerciales con NDA y 200-500 SKUs reales en S0
**para** tener números build-vs-buy en G2 (S2-S3) y G4 (S6).

**Acceptance Criteria (BDD)**:
- **Dado** un dataset de 500 SKUs MT estratificados **Cuando** lo envío a Intelligence Node + Skuuudle **Entonces** ambos vendors firman NDA y aceptan el plazo.
- **Dado** las demos en curso **Cuando** finalizan (S2-S3) **Entonces** se entrega tabla comparativa accuracy / coste / cobertura.
- **Dado** los resultados **Cuando** se evalúan en G2 **Entonces** alimentan decisión build-vs-buy (ADR-027).

**Story points**: 5
**Sprint**: S0
**Dependencias**: ninguna.
**Notas técnicas**: R-10, sec. 8.9 PRD, ADR-027.

#### US-RND-01-02 — Doc estrategia de búsqueda + decisión sourcing (Q-08)

**Como** R&D Champion
**quiero** documentar estrategia de búsqueda por SKU (queries Amazon UAE / Noon / supplier sites, multi-idioma EN/AR) y decidir sourcing (scraping vs API pagada vs partnership)
**para** desbloquear el build del comparador.

**Acceptance Criteria (BDD)**:
- **Dado** el doc `docs/comparator/search-strategy.md` **Cuando** se entrega en S1 **Entonces** define cómo se generan candidatos por SKU con cobertura medida.
- **Dado** la decisión de sourcing firmada **Cuando** se documenta en ADR **Entonces** incluye presupuesto mensual y SLA del proveedor.
- **Dado** la cobertura medida sobre 224 SKUs **Cuando** se reporta **Entonces** alcanza ≥ 90 % SKUs con al menos 1 candidato.

**Story points**: 5
**Sprint**: S0-S1
**Dependencias**: ninguna.
**Notas técnicas**: R-1, R-2, Q-08.

#### US-RND-01-03 — Dataset etiquetado ≥ 50 pares (escalable a 500 POC)

**Como** R&D Champion
**quiero** un dataset etiquetado por humano con ≥ 50 pares true-match / true-mismatch
**para** benchmark de modelos.

**Acceptance Criteria (BDD)**:
- **Dado** el dataset entregado en S2 **Cuando** se inspecciona **Entonces** tiene ≥ 50 pares con ground truth y diversidad por familia/marca.
- **Dado** el dataset POC **Cuando** se escala **Entonces** alcanza 500 SKUs × 3 marketplaces para gate G2.
- **Dado** owner + plazo **Cuando** se confirman en S0 **Entonces** quedan firmados (Q-07).

**Story points**: 8
**Sprint**: S1-S2
**Dependencias**: US-RND-01-02.
**Notas técnicas**: R-3, sec. 8.5 PRD, Q-07.

#### US-RND-01-04 — Benchmark de modelos imagen (GPT-4o, Claude vision, Gemini, CLIP/SigLIP)

**Como** R&D Champion
**quiero** correr ≥ 4 modelos sobre el dataset etiquetado y producir tabla coste-vs-accuracy
**para** elegir el modelo de visión.

**Acceptance Criteria (BDD)**:
- **Dado** los 4 modelos **Cuando** corren sobre 50 pares **Entonces** se reporta accuracy + coste por par + latencia.
- **Dado** la tabla **Cuando** se entrega en S3 **Entonces** queda en ADR como base de decisión.
- **Dado** el modelo elegido **Cuando** se integra **Entonces** se documenta dim de embedding para pgvector.

**Story points**: 8
**Sprint**: S2-S3
**Dependencias**: US-RND-01-03.
**Notas técnicas**: R-3, NFR-20.

#### US-RND-01-05 — Implementar capa OCR (Google Vision default; Tesseract fallback)

**Como** dev R&D
**quiero** la capa OCR sobre imágenes de competidor con persistencia en `competitor_listing_ocr`
**para** que el scorer multi-dimensional consuma OCR text como dimensión de alto peso.

**Acceptance Criteria (BDD)**:
- **Dado** una imagen de competidor fetcheada **Cuando** la capa OCR la procesa **Entonces** persiste `ocr_text`, `ocr_provider`, `ocr_at`, `ocr_confidence`, `ocr_blocks` (bounding boxes).
- **Dado** 100 imágenes etiquetadas **Cuando** se evalúa accuracy de OCR **Entonces** ≥ baseline establecido.
- **Dado** el scorer **Cuando** consume OCR text **Entonces** otorga peso adicional si match con marca esperada o regex part-number.

**Story points**: 8
**Sprint**: S1-S2
**Dependencias**: US-RND-01-02.
**Notas técnicas**: FR-CMP-OCR-01, R-7, ADR-022.

#### US-RND-01-06 — Esquema de scoring multi-dimensional con deal breakers (BR-CMP-01)

**Como** dev R&D
**quiero** el scorer multi-dimensional (imagen + texto técnico + OCR + reglas duras DN/PN/material/conexión)
**para** que el sistema bloquee candidatos con deal breakers aún si imagen coincide.

**Acceptance Criteria (BDD)**:
- **Dado** un par SKU↔candidato con DN distinto **Cuando** el scorer evalúa **Entonces** el candidato queda descartado y `match_candidates.hard_rules_killed_by` registra el motivo.
- **Dado** materiales en familias incompatibles (ej. brass vs ss316) **Cuando** se detecta **Entonces** el deal breaker se dispara.
- **Dado** un par sin deal breakers **Cuando** se score **Entonces** retorna `confidence` ponderada con todas las dimensiones.

**Story points**: 13
**Sprint**: S3-S4
**Dependencias**: US-RND-01-04, US-RND-01-05.
**Notas técnicas**: BR-CMP-01, BR-CMP-GRAPH-01, R-4.

#### US-RND-01-07 — Calibración de confianza (Platt / isotonic / conformal) + threshold operativo

**Como** R&D Champion
**quiero** que cuando el sistema diga 85 % sea 85 % real (calibración medible)
**para** poder operar el threshold con confianza.

**Acceptance Criteria (BDD)**:
- **Dado** los outputs del scorer sobre dataset etiquetado **Cuando** aplico Platt/isotonic **Entonces** la curva de calibración mejora (ECE < 5 %).
- **Dado** el threshold definido en S2 **Cuando** se evalúa **Entonces** auto-match `≥ 0.75`, revisión humana `0.5–0.75`, descarte `< 0.5` (hipótesis del PRD).
- **Dado** la curva final **Cuando** se aprueba **Entonces** queda en `docs/comparator/calibration.md`.

**Story points**: 8
**Sprint**: S4-S5
**Dependencias**: US-RND-01-06.
**Notas técnicas**: R-5, sec. 8.4 PRD, Q-15.

#### US-RND-01-08 — VLM judge audit-grade con verdict + rationale + image_regions + deal_breakers

**Como** dev R&D
**quiero** que el VLM judge (Gemini 2.5 Flash o equivalente) retorne payload estructurado y se persista en `match_decisions`
**para** auditabilidad y para que la UI de validación humana lo muestre.

**Acceptance Criteria (BDD)**:
- **Dado** un par en zona gris **Cuando** invoco el VLM judge **Entonces** retorna `verdict ∈ {match, no_match, uncertain}, rationale (1-3 frases idioma operador), image_regions, deal_breakers_triggered`.
- **Dado** el payload **Cuando** se persiste **Entonces** los 4 campos quedan en `match_decisions.judge_*`.
- **Dado** la UI de validación **Cuando** se carga **Entonces** muestra rationale + image_regions resaltadas.

**Story points**: 8
**Sprint**: S4-S5
**Dependencias**: US-RND-01-06.
**Notas técnicas**: FR-CMP-JUDGE-01, R-9, ADR-024.

#### US-RND-01-09 — Hooks reverse image search detrás de feature flag (default off)

**Como** dev R&D
**quiero** un adapter de reverse image search activable por flag, invocado cuando `calibrated_confidence < 0.50`
**para** tener fallback opcional sin coste fijo.

**Acceptance Criteria (BDD)**:
- **Dado** `feature.reverse_image_search_enabled = false` **Cuando** un candidato tiene `confidence=0.40` **Entonces** se descarta sin invocar el adapter.
- **Dado** flag `on` **Cuando** confidence < 0.50 **Entonces** se invoca TinEye/Google Lens via SerpAPI/Bing Visual y resultado persiste en `competitor_listings.reverse_image_hits` (JSONB).
- **Dado** el adapter desactivado por default **Cuando** se entrega Fase 1 **Entonces** los hooks están listos pero off (R-8).

**Story points**: 5
**Sprint**: S5-S6
**Dependencias**: US-RND-01-06.
**Notas técnicas**: FR-CMP-REVIMG-01, R-8, ADR-023.

#### US-RND-01-10 — UI validación humana asistida (infraestructura permanente)

**Como** Comercial / validador freelance
**quiero** una UI tipo Tinder con par SKU↔candidato, score, rationale, deal breakers y botones aprobar/rechazar/dudar
**para** validar a 250 pares/h sin agotamiento.

**Acceptance Criteria (BDD)**:
- **Dado** un par pendiente **Cuando** abro la UI **Entonces** veo imagen master + imagen candidato + specs + rationale del judge + deal breakers + score.
- **Dado** que clico aprobar **Cuando** confirmo **Entonces** se persiste decisión en `match_decisions` y se carga el siguiente par.
- **Dado** un validador **Cuando** completa N pares **Entonces** las métricas (productividad, accuracy revisada) quedan registradas para SLA (≥ 250 pares/h, ≤ 24 h SLA).

**Story points**: 13
**Sprint**: S5-S6
**Dependencias**: US-RND-01-08.
**Notas técnicas**: R-6, sec. 8.10 PRD, ADR-025.

#### US-RND-01-11 — Hooks `ComparatorService` + `GraphRepository` (FR-CMP-GRAPH-01)

**Como** dev R&D
**quiero** abstracciones backend (`ComparatorService` con adapters Rag/Hybrid/FullGraphRag y `GraphRepository` con backends Postgres/Neo4j)
**para** introducir KG Fase 2+ sin refactor.

**Acceptance Criteria (BDD)**:
- **Dado** la interfaz `ComparatorService` **Cuando** consulto API interna **Entonces** existe con adapter `RagOnlyComparatorAdapter` (Fase 1) y stubs para `Hybrid` y `FullGraphRag`.
- **Dado** la interfaz `GraphRepository` **Cuando** consulto **Entonces** existe con `PostgresGraphRepository` activo y `Neo4jGraphRepository` stub.
- **Dado** el swap del adapter vía configuración **Cuando** ocurre **Entonces** los endpoints de la API no cambian.

**Story points**: 8
**Sprint**: S5-S6
**Dependencias**: US-RND-01-06.
**Notas técnicas**: FR-CMP-GRAPH-01, BR-CMP-GRAPH-01, ADR-038, ADR-011.

#### US-RND-01-12 — POC 500 SKUs × 3 marketplaces con métricas reales + decisión G4

**Como** R&D Champion
**quiero** ejecutar el POC final y producir números reales (FP, FN, ECE, cobertura, coste tecnológico, tiempo humano)
**para** la decisión G4 build-vs-buy.

**Acceptance Criteria (BDD)**:
- **Dado** el sistema completo **Cuando** corre el POC en S6-S7 **Entonces** se reportan FP < 2 %, FN < 10 %, ECE < 5 %, cobertura ≥ 90 %.
- **Dado** los resultados **Cuando** se comparan vs demos comerciales **Entonces** la decisión G4 queda firmada (Fase 1 vs diferir a 1.5).
- **Dado** la decisión "diferir" **Cuando** se aplica **Entonces** los hooks (`ComparatorService`, OCR, VLM judge) quedan listos pero el comparador completo es Fase 1.5+.

**Story points**: 13
**Sprint**: S6-S7
**Dependencias**: US-RND-01-06, US-RND-01-07, US-RND-01-08, US-RND-01-10, US-RND-01-11.
**Notas técnicas**: sec. 8.9 PRD, ADR-027, OR.1 OKRs.

---

## 6. Sprint backlog inicial sugerido

> Capacidad asumida: **30-40 pts/sprint** para 2-3 devs FTE. R&D consume ~20 % del equipo + freelance externo (no cuenta contra el cap operativo).

### Sprint 0 — Gate (1 semana) — capacidad reducida ~20 pts

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1A-01 | US-1A-01-01, 01-02, 01-03, 01-04, 01-05, 01-06, 01-07, **01-08, 01-09** | 5+5+5+3+5+3+5+5+3 = **39** |
| EP-1B-01 | US-1B-01-01 | 8 |
| EP-RND-01 | US-RND-01-01, 01-02 | 5+5 = 10 |

**Riesgos**: stack no firmado por TI MT (Q-01); archivos PIM/costos no entregados a tiempo (Q-03).
**Entregables**: stack firmado, repos + CI/CD operativos, Supabase + Hetzner provisionados, reglas v5.1 documentadas, demos comerciales lanzadas, SQLAlchemy + supabase-py bootstrapped (ADR-045).

> Nota: S0 está sobrecargado a **57 pts** (con US-1A-01-08 y US-1A-01-09 añadidas para ADR-045) en hipótesis "1 semana". Si TI MT no asigna recursos extra, US-1B-01-01 (golden numbers) y US-1A-01-09 (smoke test supabase-py) pueden slipear a S1 sin bloquear EP-1A-02.

### Sprint 1 (S1) — PIM + i18n + importer PIM real

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1A-02 | US-1A-02-01, 02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09, 02-10 | 3+3+3+8+5+5+5+3+3+2 = **40** |
| EP-1A-06 | US-1A-06-01, 06-06 | 8+5 = 13 |
| EP-RND-01 | US-RND-01-02 (continuación), 01-03 (inicio), 01-05 (inicio) | parcial |

**Total operativo**: ~40 pts (al límite).
**Riesgos**: Excel demo + PIM real diff inesperado; calidad imágenes fabricantes; mapeo `Nombre ERP - AX` ambiguo.
**Entregables**: catálogo navegable, 224 SKUs cargados, EN canónico 100 %, mapping Excel documentado.

### Sprint 2 (S2) — Proveedores + costes + importer costos + cross-validation

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1A-03 | US-1A-03-01, 03-02 | 2+3 = 5 |
| EP-1A-04 | US-1A-04-01, 04-02, 04-03, 04-04 | 2+5+5+5 = 17 |
| EP-1A-06 | US-1A-06-02, 06-03, 06-07 | 8+5+5 = 18 |
| EP-RND-01 | US-RND-01-03 (cierre), 01-04 (inicio) | parcial |

**Total operativo**: ~40 pts.
**Riesgos**: archivos costos con SKUs huérfanos > 10 %; FX as-of stamping requiere refinar trigger.
**Entregables**: 100 % SKUs con coste por al menos 1 esquema; reporte cross-validation; SKUs huérfanos con owner.

### Sprint 3 (S3) — Monedas + FX + audit + RBAC + i18n UI + cierre 1a + scheduler editable (parcial)

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1A-05 | US-1A-05-01, 05-02, 05-03, 05-04 | 2+5+3+3 = 13 |
| EP-1A-06 | US-1A-06-04, 06-05 | 5+3 = 8 |
| EP-1A-07 | US-1A-07-01, 07-02, 07-03, 07-04, 07-05, 07-06 | 3+5+5+3+5+5 = 26 |
| EP-1A-08 | **US-1A-08-01, 08-02, 08-03** | 3+8+2 = 13 |
| EP-RND-01 | US-RND-01-04 (cierre) | parcial |

**Total operativo**: ~60 pts (muy sobrecargado; opciones: deslizar US-1A-07-06 dashboard a S4 y/o partir US-1A-08-02 si la decisión Sprint 0 sobre `celery-sqlalchemy-scheduler` se complica).
**Riesgos**: triggers `audit_events` impactan performance; políticas RLS interactúan con queries existentes (regresiones); scheduler custom mal implementado puede saltar horarios.
**Entregables**: AED+EUR+USD+SAR seeded, fx_rates versionada, audit triggers en críticas, 3 roles operativos, UI ES/EN, **DatabaseScheduler operativo con 6 jobs base seeded**, demo "puedo mantener catálogo y costos sin Excel" (G2).

### Sprint 4 (S4) — Motor de pricing + simulación + UI Jobs admin

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1B-01 | US-1B-01-02, 01-03, 01-04, 01-05, 01-06 | 3+13+8+8+5 = 37 |
| EP-1A-08 | **US-1A-08-04, 08-05** | 5+5 = 10 |
| EP-RND-01 | US-RND-01-06 (inicio), 01-07 (inicio), 01-08 (inicio) | parcial |

**Total operativo**: ~47 pts (sobrecargado; alternativa: mover US-1A-08-05 a S5 si el motor de pricing necesita el cap completo).
**Riesgos**: divergencia vs golden numbers en SKUs edge; performance recálculo masivo no cumple < 60 s; UI jobs admin con cron-preview puede inflarse si la lib elegida (croniter / cron-parser) no soporta timezones bien.
**Entregables**: motor portado/reescrito, recálculo SKU < 5 s, masivo < 60 s, what-if multi-canal funcional, **UI `/admin/jobs` con CRUD + cron preview + Run now + audit drawer operativos**.

### Sprint 5 (S5) — Workflow excepción + reglas paramétricas + digest + escalado

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1B-02 | US-1B-02-01, 02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09 | 5+5+5+3+3+8+5+5+3 = **42** |
| EP-RND-01 | US-RND-01-07 (cierre), 01-08 (cierre), 01-09 (inicio), 01-10 (inicio), 01-11 (inicio) | parcial |

**Total operativo**: ~42 pts (sobrecargado; alternativa: mover 02-09 a S6).
**Riesgos**: Gerente no disponible para validar reglas paramétricas; SLA 24 h difícil sin delegación clara (Q-17).
**Entregables**: state machine completa, digest funcional, reglas versionadas, SLA aprobación medible.

### Sprint 6 (S6) — Estados de canal + connectors base + shadow publish + exports

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1B-03 | US-1B-03-01, 03-02, 03-03, 03-04, 03-05 | 3+8+5+3+5 = 24 |
| EP-1B-04 | US-1B-04-01, 04-02, 04-03, 04-04, 04-05 | 5+8+5+8+3 = 29 |
| EP-RND-01 | US-RND-01-09 (cierre), 01-10 (cierre), 01-11 (cierre) | parcial |

**Total operativo**: ~53 pts (sobrecargado; mover US-1B-04-04 shadow publish a S7).
**Riesgos**: formato Amazon UAE Seller Central + Noon UAE no documentado al detalle (Q-16); credenciales sandbox no entregadas a tiempo.
**Entregables**: 6 estados canal, regla dura no-export sin aprobación enforced, shadow publish probado, last-known-good operativo.

### Sprint 7 (S7) — Hardening + parallel run + handoff + cutover gate

| Épica | Historias | Pts |
|-------|-----------|-----|
| EP-1B-05 | US-1B-05-01, 05-02, 05-03, 05-04, 05-05, 05-06, 05-07 | 5+5+3+5+3+5+5 = 31 |
| EP-RND-01 | US-RND-01-12 (POC final + decisión G4) | 13 |

**Total operativo**: ~31 pts + R&D 13 pts.
**Riesgos**: parallel run con diff persistente impide cutover; backup operator no disponible; comparador no llega al threshold y debe diferirse a 1.5.
**Entregables**: parallel run con 0 diff ≥ 5 días, manual aprobado, backup capacitado, cutover gate firmado, decisión G4 build-vs-buy.

---

## 7. Definition of Ready (DoR)

Una historia es **Ready** para entrar a sprint cuando:

1. **Título corto** y formato narrativo "Como… quiero… para…" presente y claro.
2. **Acceptance criteria** en BDD (mínimo 3) revisados y entendidos por el equipo.
3. **Story points** estimados por el equipo (póker o consenso).
4. **Dependencias** identificadas y marcadas (otras US, ADRs, entregables S0).
5. **FR/BR/UC del PRD** referenciados (trazabilidad).
6. **Mockups o referencia UX** disponibles si la historia toca UI (PRD §12 o Figma si existe).
7. **Datos de prueba** disponibles (fixtures, golden numbers, archivos PIM/costos reales o mock).
8. **Cuestiones bloqueantes** (Q-XX del PRD) resueltas o documentadas como risk-aceptado.
9. **Owner identificado** (dev FE / dev BE / dev R&D / TI / Champion).
10. **Capacidad de testing** clara (unit / integration / E2E / manual).

---

## 8. Definition of Done (DoD)

Una historia está **Done** cuando:

1. **Código mergeado** a `main` vía PR aprobado por al menos 1 reviewer.
2. **Tests automatizados**: unit + integration coverage del nuevo código ≥ 80 %; E2E si aplica.
3. **CI verde**: lint (ruff / eslint), type-check (mypy / tsc), tests, build, deploy a staging.
4. **Code review** firmado en GitHub con checklist de seguridad (RLS, auth, input validation).
5. **Documentación actualizada**: README, OpenAPI auto-gen, ADRs nuevos si aplica, `docs/handbook-es.md` si es funcionalidad operativa.
6. **Audit event verificado**: si la historia toca tabla crítica, prueba E2E o manual confirma `audit_events` poblado.
7. **NFR cumplido**: latencia, performance, security checks (NFR aplicables) verificados.
8. **i18n**: strings nuevos en archivos `next-intl` (ES + EN) si toca UI.
9. **Telemetría**: logs estructurados con `request_id` + métricas relevantes (NFR-26, NFR-27).
10. **Demo en staging**: la historia es demostrable a Champion / Gerente / TI.
11. **Sentry sin errores nuevos** en los 24 h post-deploy.
12. **PR cierra issue / historia** con link bidireccional.

---

## 9. Mapping FR/BR del PRD ↔ Historias

> Cada FR y BR del PRD aparece en al menos una historia. Cuestiones abiertas (Q-XX) marcan dependencias.

### 9.1 Fase 1a

| ID | Tipo | Historias |
|----|------|-----------|
| FR-1a-01 | FR | US-1A-02-02, US-1A-02-03, US-1A-02-04 |
| FR-1a-02 | FR | US-1A-02-05 |
| FR-1a-03 | FR | US-1A-02-07 |
| FR-1a-04 | FR | US-1A-03-01, US-1A-03-02 |
| FR-1a-05 | FR | US-1A-04-01, US-1A-04-02, US-1A-04-03, US-1A-04-04 |
| FR-1a-06 | FR | US-1A-06-01 |
| FR-1a-07 | FR | US-1A-06-02 |
| FR-1a-08 | FR | US-1A-06-06 |
| FR-1a-09 | FR | US-1A-05-01, US-1A-05-02, US-1A-05-03 |
| FR-1a-10 | FR | US-1A-07-01, US-1A-07-02 |
| FR-1a-11 | FR | US-1A-07-03 |
| FR-1a-12 | FR | US-1A-07-04 |
| FR-1a-13 | FR | US-1A-06-07 |
| FR-DOC-01 | FR | US-1A-06-04 |
| FR-DOC-02 | FR | US-1A-06-05 |
| FR-MAT-01 | FR | US-1A-06-03 |
| FR-IMG-01 | FR | US-1A-02-06 |
| FR-IMG-02 | FR | US-1A-02-07 |
| FR-IMG-03 | FR | US-1A-02-07 |
| BR-1a-01 | BR | US-1A-02-01 |
| BR-1a-02 | BR | US-1A-02-01, US-1A-02-02 |
| BR-1a-03 | BR | US-1A-04-03 |
| BR-1a-04 | BR | US-1A-04-02, US-1A-06-01, US-1A-06-02 |
| BR-1a-05 | BR | US-1A-04-02 |
| BR-1a-06 | BR | US-1A-02-03 |
| BR-1a-07 | BR | US-1A-02-10, US-1A-03-02 |
| BR-1a-08 | BR | US-1A-02-07 |
| BR-1a-09 | BR | US-1A-02-05 |
| BR-1a-10 | BR | US-1A-06-06, US-1B-05-05 |
| BR-1a-11 | BR | US-1A-07-02 |
| BR-1a-12 | BR | US-1A-07-03 |
| BR-1a-13 | BR | US-1A-02-03 |
| BR-1a-14 | BR | US-1A-05-04 |
| BR-1a-15 | BR | US-1A-06-07 |
| BR-IMG-01 | BR | US-1A-02-07 |
| BR-IMG-02 | BR | US-1A-02-07 |

### 9.2 Fase 1b

| ID | Tipo | Historias |
|----|------|-----------|
| FR-1b-01 | FR | US-1B-01-03, US-1B-01-04 |
| FR-1b-02 | FR | US-1B-01-05, US-1B-01-06 |
| FR-1b-03 | FR | US-1B-02-03, US-1B-02-04 |
| FR-1b-04 | FR | US-1B-02-02 |
| FR-1b-05 | FR | US-1B-02-05, US-1B-02-07 |
| FR-1b-06 | FR | US-1B-03-02, US-1B-03-03, US-1B-03-05 |
| FR-1b-07 | FR | US-1B-04-02, US-1B-04-03 |
| FR-1b-08 | FR | US-1B-04-02 |
| FR-1b-09 | FR | US-1B-04-04 |
| FR-1b-10 | FR | US-1B-03-04 |
| FR-1b-11 | FR | US-1B-01-04 |
| FR-1b-12 | FR | US-1B-02-09 |
| FR-1b-13 | FR | US-1B-02-08 |
| FR-1b-14 | FR | US-1B-02-02, US-1B-01-03 |
| BR-1b-01 | BR | US-1B-04-02, US-1B-04-03 |
| BR-1b-02 | BR | US-1B-02-03 |
| BR-1b-03 | BR | US-1B-02-03 |
| BR-1b-04 | BR | US-1B-02-01 |
| BR-1b-05 | BR | US-1B-02-09 |
| BR-1b-06 | BR | US-1B-02-08 |
| BR-1b-07 | BR | US-1B-03-04 |
| BR-1b-08 | BR | US-1B-03-02 |
| BR-1b-09 | BR | US-1B-03-03 |
| BR-1b-10 | BR | US-1B-03-03 |
| BR-1b-11 | BR | US-1B-02-05 |
| BR-1b-12 | BR | US-1A-05-04 |
| BR-1b-13 | BR | US-1B-02-02 |
| BR-1b-14 | BR | US-1B-04-04 |
| BR-1b-15 | BR | US-1B-04-05 |

### 9.3 Workstream R&D

| ID | Tipo | Historias |
|----|------|-----------|
| FR-CMP-OCR-01 | FR | US-RND-01-05 |
| FR-CMP-REVIMG-01 | FR | US-RND-01-09 |
| FR-CMP-JUDGE-01 | FR | US-RND-01-08 |
| FR-CMP-GRAPH-01 | FR | US-RND-01-11 |
| BR-CMP-01 | BR | US-RND-01-06 |
| BR-CMP-GRAPH-01 | BR | US-RND-01-06, US-RND-01-11 |
| R-1, R-2 | RND | US-RND-01-02 |
| R-3 | RND | US-RND-01-04 |
| R-4 | RND | US-RND-01-06 |
| R-5 | RND | US-RND-01-07 |
| R-6 | RND | US-RND-01-10 |
| R-7 | RND | US-RND-01-05 |
| R-8 | RND | US-RND-01-09 |
| R-9 | RND | US-RND-01-08 |
| R-10 | RND | US-RND-01-01 |

### 9.4 NFR

| ID | Historias |
|----|-----------|
| NFR-01 | US-1B-01-03, US-1B-05-06 |
| NFR-02 | US-1B-01-04, US-1B-05-06 |
| NFR-03 | US-1A-06-01 |
| NFR-04 | US-1A-06-02 |
| NFR-05 | US-1B-04-02 |
| NFR-06 | US-1A-02-09, US-1B-05-06 |
| NFR-07 | US-1A-07-02, US-1A-01-07 |
| NFR-08 | US-1A-07-05 |
| NFR-11 | US-1A-01-07, US-1A-07-02 |
| NFR-19 | US-1A-01-05, US-1A-02-08 |
| NFR-20 | US-1A-02-01, US-1A-06-05 |
| NFR-21 / NFR-22 / NFR-24 | US-1A-07-04, US-1A-02-05 |
| NFR-25 / NFR-26 | US-1A-01-06 |
| NFR-27 / NFR-28 | US-1B-05-07 |
| NFR-29 / NFR-30 | US-1A-05-01, US-1A-05-02 |
| NFR-33 / NFR-34 | US-1A-07-03, US-1B-02-09 |
| NFR-35 / NFR-36 | US-1A-07-05 |

---

## 10. Cuestiones abiertas y dependencias

> Historias bloqueadas o sujetas a refinamiento hasta resolver cada Q-XX del PRD §20.

| Q | Descripción corta | Historias dependientes | Impacto si no se resuelve |
|---|-------------------|------------------------|---------------------------|
| **Q-01** | Stack tecnológico firmado por TI MT | US-1A-01-01 a US-1A-01-07 (todas) | Bloquea S0 completo si stack rechazado |
| **Q-02** | Cloud + residencia UAE | US-1A-01-02, US-1A-01-05 | Si se exige UAE, cambia provisioning Hetzner → AWS me-central-1 |
| **Q-03** | Archivos PIM real + costos entregados | US-1A-06-01, US-1A-06-02, US-1B-01-01 | Sin archivos, S1 trabaja con Excel demo como fallback |
| **Q-04** | Threshold X % delta margen auto-approve | US-1B-02-02, US-1B-02-03 | Sin Gerente firmando default, hardcode 5 % temporal |
| **Q-05** | TI Integración FTE / role-share / vendor | US-1A-01-04 a US-1A-01-07 | Sin TI MT, BR provee role; impacta velocidad S0-S2 |
| **Q-07** | Owner + plazo dataset etiquetado comparador | US-RND-01-03 | Bloquea benchmark modelos si no se resuelve en S1 |
| **Q-08** | Sourcing competidores firmado + presupuesto | US-RND-01-02, US-RND-01-04 | Sin sourcing, R&D queda en research-only sin POC real |
| **Q-09** | Acuerdo derechos imagen MT España ↔ MT ME | US-1A-02-07 | Sin acuerdo legal, mirror se ejecuta con riesgo legal del sponsor |
| **Q-10** | Decisión port-vs-rewrite motor v5.1 | US-1B-01-01, US-1B-01-03 | Sin decisión S0, US-1B-01-03 puede inflarse a 21 pts (rewrite) |
| **Q-11** | Definición "óptimo" recomendador canal | US-1B-03-04 | Feature flag off Fase 1, no bloquea pero gating Fase 3 |
| **Q-13** | Política retención `audit_events` (default 7 años) | US-1A-07-05 | Default 7 años aplicable; cambio post-implementación es config |
| **Q-15** | Threshold calibración comparador | US-RND-01-07 | Definición S2 con primera curva |
| **Q-16** | Formato exacto exports por canal | US-1B-04-02, US-1B-04-04 | Sin spec Amazon UAE / Noon UAE, S6 trabaja con CSV genérico |
| **Q-17** | Política delegación Gerente | US-1B-02-08 | Sin delegado configurado, escalado notifica a TI por default |

---

## 11. Apéndice — Resumen ejecutivo del backlog

### 11.1 Totales

- **Total historias**: 63 (56 operativas + 7 R&D). +7 historias vs v1.0 por ADR-045 (US-1A-01-08, 01-09) y ADR-046 (EP-1A-08 con 5 historias).
  - Fase 1a: 36 historias (EP-1A-01 a EP-1A-08).
  - Fase 1b: 27 historias (EP-1B-01 a EP-1B-05).
  - R&D: 12 historias (EP-RND-01).

- **Total story points por fase**:
  - **Sprint 0**: ~57 pts (49 originales + 8 de ADR-045: US-1A-01-08 5pt + US-1A-01-09 3pt). Sobrecargado; partir si TI MT no asigna recursos extra.
  - **Fase 1a (S1-S3)**: ~140 pts (40 + 40 + 60). S3 a 60 pts incluye EP-1A-08 parcial (13 pts).
  - **Fase 1b (S4-S7)**: ~173 pts (47 + 42 + 53 + 31). S4 a 47 pts incluye EP-1A-08 cierre (10 pts).
  - **R&D (S0-S7)**: ~110 pts.
  - **Total operativo**: ~321 pts (~290 v1.0 + 31 ADR-045/046); **total con R&D**: ~431 pts.

> **Nota.** Los 31 pts adicionales de ADR-045/046 son: 5 (US-1A-01-08) + 3 (US-1A-01-09) + 3 (US-1A-08-01) + 8 (US-1A-08-02) + 2 (US-1A-08-03) + 5 (US-1A-08-04) + 5 (US-1A-08-05) = **31 SP**. EP-1A-08 totaliza 23 SP por sí sola.

### 11.2 Las 3 historias más riesgosas

1. **US-1B-01-03 — `PricingEngine.calculate` (port v5.1)** — 13 pts, S4.
   - **Por qué riesgosa**: paridad exacta con golden numbers depende de extracción correcta de reglas v5.1 desde VBA (US-1B-01-01) y de decisión port-vs-rewrite (Q-10 en S0). Si Paula encuentra discrepancias en SKUs edge, el sprint se desliza. Bundling psicológico (XX,99 / XX,49) y fallback tiers son fuente histórica de bugs. Impacta directamente NFR-01, NFR-02 y todos los OKRs Fase 1b.

2. **US-RND-01-12 — POC 500 SKUs × 3 marketplaces con métricas reales + decisión G4** — 13 pts, S6-S7.
   - **Por qué riesgosa**: depende de toda la cadena R&D (sourcing, dataset etiquetado, scorer, calibración, VLM judge, UI validación). Cualquier eslabón débil hace que las métricas reales no alcancen FP < 2 % / FN < 10 %. Si no llega al threshold en S7, dispara la decisión "diferir a Fase 1.5" — sin bloquear el resto de Fase 1, pero con impacto en expectativa del sponsor. Demos comerciales paralelas (US-RND-01-01) deben llegar con números a tiempo para informar G4.

3. **US-1B-05-05 — Cutover gate firmado** — 3 pts, S7.
   - **Por qué riesgosa**: aunque es 3 pts (la firma es ligera), depende de que **toda la cadena anterior** esté verde: parallel run sin diff ≥ 5 días (US-1B-05-01), backup operator capacitado (US-1B-05-03), manual aprobado (US-1B-05-02), drill rollback exitoso (US-1B-05-04). Cualquier falla cascada bloquea cutover y posterga go-live, atrasando Fase 2. Riesgos R-01 (dependencia Excel), R-02 (single-point-of-failure), R-10 (cambio operativo Comercial) convergen aquí.

---

**Fin del documento — Épicas e Historias Fase 1 (1a + 1b)**
