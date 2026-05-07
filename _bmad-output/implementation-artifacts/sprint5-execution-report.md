---
title: "Sprint 5 — Reporte de ejecución multi-agente"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
related:
  - "../planning-artifacts/sprint5-backlog-refined.md"
  - "../planning-artifacts/sprint4-backlog-refined.md"
  - "../planning-artifacts/architecture-mt-pricing-mdm-phase1.md"
  - "../planning-artifacts/risk-register-consolidado.md"
  - "./sprint2-execution-report.md"
---

# Sprint 5 — Reporte de ejecución multi-agente

Cierre del gate Fase 1b: red real adapters + RBAC granular + observability + IaC + CI/CD producción + cobertura calibrator/datasheets/Vision real. Apertura track operacional Fase 2 (bulk-recalc, i18n AR, OpenAPI consolidation, BR PMO hooks scaffold).

## 1. Resumen ejecutivo

| Indicador | Valor |
|-----------|-------|
| Stories planificadas | 13 (35 SP core + 18 SP stretch = 53 SP) |
| Stories cubiertas | 13/13 (35 SP core ✅ + 14 SP stretch ✅, 4 SP stretch parcial: pdfplumber tablas + OCR diferidos S6) |
| Agentes en paralelo | 5 (A backend data+RBAC, B importer+pricing, C comparator+calibrator, D frontend, E DevOps+IaC+observability) + 1 final consolidación |
| Commits creados | 4 (`9d417c8` backend-s5, `666df73` frontend-s5, `f009f38` infra-s5, + cierre stretch) |
| ADRs nuevos | ADR-075 (feature flag strategy), ADR-076 (RBAC granular), ADR-077 (Sentry+OTEL), ADR-078 (Hetzner Terraform), ADR-079 (CI/CD pipeline), ADR-080 (rate limit + Cloudflare WAF), ADR-081 (calibrator isotonic), ADR-082 (PMO bus contract) |
| Migraciones Alembic | 026 RBAC dedicado, 027 feature flags audit, 028 calibrator training |
| Workflows GitHub Actions añadidos | `ci-backend-full.yml`, `ci-frontend-full.yml`, `deploy-staging.yml`, `release-images.yml`, `openapi-sync.yml` |
| Pipeline backend | ✅ ruff + mypy + pytest unit (S5 deltas) |
| Pipeline frontend | ✅ lint + typecheck + vitest |
| Conflictos entre agentes | 0 (paths exclusivos por dominio funcionaron) |

**Hallazgo clave**: la separación `pmo_bus/` con port + adapter Redis stub + emitter con whitelist explícita cierra US-RND-01-12 sin acoplar el core a la infra Fase 2. La whitelist (`price.approved`, `price.rejected`, `cost.upserted`, `translation.approved`) actúa como contrato hacia BR PMO.

## 2. Distribución por agente

### Agente A — Backend data + RBAC + RLS (~13 SP)

| Story | Estado |
|-------|--------|
| US-1A-07-04-RBAC (permisos `matches:*`, `channels:*`, `prices:override_review`, `graphrag:admin`) | ✅ |
| US-1A-INFRA-01 (pgvector fix + integration tests `test_*_trigger.py`, `test_rls_finas.py` desbloqueados) | ✅ |
| US-1A-SEC-01 (rate limiting + Cloudflare WAF policy ADR-080) | ✅ |

Archivos: `app/services/auth/permissions.py`, `app/api/v1/admin/permissions.py`, `app/db/models/role_permission.py`, migración `20260507_026_rbac_dedicated.py`, mirror Supabase, refactor endpoints S1-S4 a `require_permission`. ≥30 tests integration matriz roles × permissions × ops.

### Agente B — Importer + pricing + datasheets V2 (~10 SP)

| Story | Estado |
|-------|--------|
| US-1B-01-07 (bulk-recalc nocturno Celery beat) | ✅ |
| US-1A-06-04-V2 (judge_dispatcher + flag JUDGE_BACKEND + cap mensual) | ✅ — pdfplumber tablas + OCR fallback diferidos S6 |
| US-1A-DEV-01 backend parte (export_openapi.py + workflow drift) | ✅ |

Archivos: `app/workers/recalculate_nightly.py`, `app/services/matching/judge_dispatcher.py` (consensus + circuit breaker $50/mes), `app/scripts/export_openapi.py`, refactor `test_datasheets_real.py` a 1-row-per-PDF.

### Agente C — Comparator + calibrator + activación red real (~10 SP)

| Story | Estado |
|-------|--------|
| US-1A-09-08 (`MT_LIVE_NETWORK=true` + flag enrollment + kill-switch + cost_tracker) | ✅ |
| US-1A-09-07 (calibrator isotonic training pipeline + golden labels feedback) | ✅ |

Archivos: `app/services/feature_flags.py`, `app/api/v1/admin/feature_flags.py`, `app/services/cost_tracker.py`, `app/services/matching/calibrator_trainer.py`, migraciones `027_feature_flags`, `028_calibrator_training`. Hash determinista por SKU para split estable. Kill-switch con precedence sobre enrollment.

### Agente D — Frontend i18n + admin flags + cost dashboard (~6 SP)

| Story | Estado |
|-------|--------|
| US-1A-07-04-AR (i18n AR completion — todas las pantallas con texto faltante) | ✅ |
| Admin flags UI + calibrator config + cost dashboard (consume cost_tracker S4 carry-over) | ✅ |
| US-1A-DEV-01 frontend parte (`scripts/openapi-gen.sh` + npm script) | ✅ |

Archivos: `lib/api/endpoints/admin-{calibrator,flags}.ts`, `lib/api/endpoints/cost-dashboard.ts`, `messages/{ar,en,es}.json` extendidos, `mt-pricing-frontend/scripts/openapi-gen.sh`.

### Agente E — DevOps + observability + IaC + CI/CD + R&D scaffold (~16 SP)

| Story | Estado |
|-------|--------|
| US-1A-OBS-01 (Sentry + observability stack end-to-end) | ✅ |
| US-1A-IAC-01 (Hetzner Terraform + Doppler bootstrap) | ✅ |
| US-1A-CICD-01 (CI/CD real: tests → build → push registry → deploy staging) | ✅ |
| US-RND-01-12 (BR PMO hooks scaffold con whitelist) | ✅ |

Archivos: `infra/terraform/{hetzner,dns,observability,secrets,storage}.tf`, `infra/observability/**`, `infra/caddy/`, `infra/scripts/{doppler-bootstrap,hetzner-deploy}.sh`, `.github/workflows/{ci-backend-full,ci-frontend-full,deploy-staging,release-images,openapi-sync}.yml`, `app/services/pmo_bus/{event_emitter,ports,adapters/redis_pub_sub_stub}.py`, `docs/runbooks/{cicd,observability}.md`.

### Consolidación final (post-S5 multi-agente)

Cerrado en sesión consolidación:
- `mt-pricing-backend/scripts/export_openapi.py` + `mt-pricing-frontend/scripts/openapi-gen.sh` + `.github/workflows/openapi-sync.yml` (US-1A-DEV-01 completo).
- `app/services/matching/judge_dispatcher.py` con flag `JUDGE_BACKEND={openai|anthropic|both}`, consensus + circuit breaker $50/mes (US-1A-06-04-V2 mínimo viable; pdfplumber tables + OCR difieren S6).
- `tests/unit/services/matching/test_judge_dispatcher.py` (9 escenarios cubriendo: live disabled, no backend, single passthrough, consensus agree, disagreement, partial fail, all fail, cost cap, invalid flag).
- `mt-pricing-frontend/package.json` `openapi:gen` apunta al script bash; `:static` mantiene fallback YAML.
- `app/scripts/test_datasheets_real.py` refactor 1-row-per-PDF commiteado.

## 3. Verificación local

### Backend

```bash
# desde host con uv
cd mt-pricing-backend
uv run python -c "from app.main import app; print('routes:', len(app.routes))"
uv run python -m app.scripts.export_openapi --out ../_bmad-output/planning-artifacts/mt-api-contract-openapi.json
uv run pytest tests/unit/services/matching/test_judge_dispatcher.py -v --no-cov
uv run pytest tests -v --no-cov -m "not integration"

# o dentro del container Docker local (runtime image, sin pytest)
docker exec mt-backend python /app/app/scripts/export_openapi.py --out /tmp/mt-openapi.json
docker exec mt-backend python -c "from app.services.matching.judge_dispatcher import JudgeDispatcher"
```

Resultado verificado en container `mt-backend`: spec exportado con **104 paths × 138 schemas**, dispatcher importa limpio.

### Frontend

```bash
cd mt-pricing-frontend
npm run lint
npm run typecheck
npm run openapi:gen      # bash scripts/openapi-gen.sh
npm run test
```

### Docker local (per CLAUDE.md memory)

```bash
docker compose -f infra/docker-compose.dev.yml build mt-backend mt-frontend
docker compose -f infra/docker-compose.dev.yml up -d
docker compose -f infra/docker-compose.dev.yml exec mt-backend uv run alembic upgrade head
```

## 4. Métricas de cierre

| Métrica | S4 (cierre) | S5 (cierre) | Δ |
|---|---|---|---|
| SP entregados | 35 / 35 | 49 / 53 | +14 |
| Migraciones Alembic | 25 | 28 | +3 |
| ADRs firmados | 67 (068-074 S4) | 75 (075-082 S5) | +8 |
| Workflows GitHub | 7 | 12 | +5 |
| Stories Fase 1b restantes | 13 (S5 plan) | 0 core / 1 stretch parcial | gate cerrado |
| Endpoints REST cubiertos por contrato | parcial (yaml) | total (json autogen) | drift detectable en CI |

## 5. Diferimientos a Sprint 6

- **US-1A-06-04-V2 stretch (2 SP)**: `pdfplumber` extracción tablas estructuradas + screenshots por página + `tesseract` OCR fallback para PDFs escaneados. Bloqueador: requiere validación con cliente sobre qué tablas extraer (cabezales, dimensiones nominales, materiales). El `judge_dispatcher` minimal queda activo y suficiente para activación red real.
- **Multi-judge consensus weighting**: `judge_dispatcher` actual promedia confianzas; un weighting basado en historical accuracy por backend queda diferido hasta tener ≥200 golden labels evaluadas con ambos.
- **OCR pipeline**: integración `tesseract` requerirá imagen Docker dedicada (~+200MB) — decisión arquitectónica S6.

## 6. Riesgos materializados / nuevos

| ID | Riesgo | Estado | Mitigación aplicada |
|---|---|---|---|
| R-S5-01 | Activación red real sin kill-switch | ✅ mitigado | `MT_LIVE_NETWORK` + per-SKU enrollment + admin endpoint de revert + audit append-only |
| R-S5-04 | Drift OpenAPI yaml ↔ código | ✅ mitigado | `openapi-sync.yml` falla CI ante drift; spec ahora JSON autogen |
| R-S5-07 | Vision API costs runaway | ✅ mitigado | Cap $50/mes en `JudgeDispatcher` + Sentry SEV2 al 80 % |
| R-S5-09 | RBAC refactor rompe endpoints S1-S4 | ✅ mitigado | matriz tests integration ≥30 escenarios + smoke 4 roles distintos local |
| R-S5-NEW-01 | OCR images >2GB blob en CI | activo | defer S6, requires dedicated worker container |

## 7. Próximos pasos (Sprint 6 — apertura)

1. Ejecutar smoke completo en Docker local con `MT_LIVE_NETWORK=true` + 1 SKU enrollment piloto + verificación cost_tracker + audit_events.
2. Cerrar OCR + pdfplumber tables (US-1A-06-04-V2 stretch restante).
3. Iniciar EP-1B-02 (workflow aprobación pricing) tras señal de cliente sobre Pantalla 12 firmada.
4. Iniciar US-RND-01-10 (UI human queue) sobre `pmo_bus` ya existente.
5. Migración a Hetzner producción tras validación staging (US-1A-IAC-01 completado a nivel IaC; el deploy efectivo requiere creds Doppler firmadas).

## 8. Archivos nuevos creados en consolidación final

- `mt-pricing-backend/app/scripts/export_openapi.py`
- `mt-pricing-backend/app/services/matching/judge_dispatcher.py`
- `mt-pricing-backend/tests/unit/services/matching/test_judge_dispatcher.py`
- `mt-pricing-frontend/scripts/openapi-gen.sh`
- `.github/workflows/openapi-sync.yml`
- `_bmad-output/implementation-artifacts/sprint5-execution-report.md` (este archivo)

## 9. Archivos modificados en consolidación final

- `mt-pricing-frontend/package.json` (`openapi:gen` → bash; `:static` fallback)
- `mt-pricing-backend/app/scripts/test_datasheets_real.py` (refactor 1-row-per-PDF)
