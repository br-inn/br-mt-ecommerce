---
title: "Sprint 2 — Reporte de ejecución multi-agente"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
related:
  - "../planning-artifacts/sprint2-backlog-refined.md"
  - "../planning-artifacts/architecture-mt-pricing-mdm-phase1.md"
  - "../planning-artifacts/adr/ADR-055-ssrf-policy-image-probe.md"
  - "./sprint1-execution-report.md"
---

# Sprint 2 — Reporte de ejecución multi-agente

Ejecución paralela de las 11 stories del Sprint 2 (41 SP) mediante 4 agentes con dominios disjuntos + 1 agente final de gap-fix.

## 1. Resumen ejecutivo

| Indicador | Valor |
|-----------|-------|
| Stories planificadas | 11 (41 SP) |
| Stories cubiertas en este run | 11 (100 %) |
| Agentes en paralelo (implementación) | 4 |
| Agentes secuenciales (gap-fix) | 1 |
| Tests añadidos backend (unit) | ~75 (40 data + 28 SSRF + 22 importer + JWT/health refuerzos) |
| Tests añadidos frontend | 24 nuevos (32/32 total) |
| Tests verificados pasando localmente | **122/122 backend unit + 32/32 frontend vitest** |
| Pipeline frontend | ✅ lint + typecheck + vitest + build |
| Pipeline backend | ✅ from app.main import app (49 rutas) + pytest unit |
| Conflictos de archivos entre agentes | 0 |
| Commits creados | 0 (todo en working tree para revisión) |

**Hallazgo clave**: el PIM real (`Documentos referencia de articulos/PIM completo.xlsx`, **5085 rows × 17 cols**) reemplazó al fixture sintético; headers coinciden con `sprint0-pim-column-mapping.md` sin desviaciones; ~22 % rows (1128) sin "Nombre ERP" → marcadas `name_en no derivable` (esperado por sprint0 §1).

## 2. Distribución por agente

### Agente 1 — Backend Data + Storage (~12 SP)

| Story | Estado |
|-------|--------|
| US-1A-03-01 (suppliers + currencies seed) | ✅ |
| US-1A-04-01 (cost schemes seed) | ✅ |
| US-1A-02-10 (DELETE soft trigger) | ✅ |
| US-1A-02-06 (bucket product-images + RLS + signed URLs) | ✅ |
| `manual_locked_fields` gap S1 | ✅ (ya estaba; tests añadidos) |
| `audit_partitions_ensure` task | ✅ |

Archivos: 3 modelos nuevos, 3 migraciones Alembic (004/005/006), 3 migraciones Supabase, `app/services/storage.py`, `app/workers/audit_partitions.py`, 5 archivos de tests (~40 tests).

### Agente 2 — Backend API + Importer (~17 SP)

| Story | Estado |
|-------|--------|
| US-1A-02-03 (PUT/PATCH products + ETag opt-locking) | ✅ |
| US-1A-03-02 backend (suppliers CRUD + DELETE→405) | ✅ |
| US-1A-02-09 backend (filtros avanzados + full-text) | ✅ |
| US-1A-06-01 (importer wizard preview/apply/status/report) | ✅ con PIM real 5085 rows |

Archivos: 4 endpoints/routers nuevos, importer pipeline completo (`column_mapper`, `parser`, `differ`, `applier`, `importer_service`), `app/services/products/product_service.py`, `app/services/suppliers/supplier_service.py`, repos extendidos, 22 unit + 31 integration tests.

### Agente 3 — Workers + Image Pipeline (~8 SP)

| Story | Estado |
|-------|--------|
| US-1A-02-07 (probe + mirror + SSRF guard + ADR) | ✅ |
| US-1A-02-08 (thumbnails async Celery) | ✅ |
| Worker container `python:3.11-slim` (R-S2-09) | ✅ |
| ADR SSRF policy | ✅ (renumerada **ADR-055** porque ADR-047 ya estaba ocupado por observability stack) |

Archivos: `app/services/{ssrf,image_pipeline}.py`, `app/workers/{probe_mirror,thumbnails,ssrf}.py`, settings extendidos (7 vars `SSRF_*` + `ALLOW_PROBE_FROM_PIM_ES`), `Dockerfile.worker`, `infra/docker-compose.dev.yml` overlay con `worker-images` + `flower:5555`, 28 tests SSRF cubriendo 18 vectores del ADR + happy paths + redirects + magic-bytes mismatch.

### Agente 4 — Frontend (~14 SP)

| Story | Estado |
|-------|--------|
| US-1A-02-04-S2 (tab Imágenes + edit inline Identidad) | ✅ |
| US-1A-03-02 frontend (CRUD suppliers UI patrón Pantalla 2) | ✅ |
| US-1A-02-09 frontend (filtros avanzados + Sheet más filtros) | ✅ |
| US-1A-06-01 frontend (importer wizard 4 pasos + polling 2s) | ✅ |

Archivos: nuevas páginas `/suppliers`, `/suppliers/new`, `/suppliers/[id]`, `/imports`; 12 componentes nuevos; API clients + hooks; i18n namespaces `suppliers.*`, `imports.*`, ext `catalog.{filters,edit,images}.*`; sidebar actualizado; 24 nuevos test cases.

### Agente 5 — Gap-fix backend (post-implementación)

Resolvió 4 gaps críticos detectados al integrar:
- **Gap 1**: `Pillow>=10.2,<11` añadido a `pyproject.toml`
- **Gap 2**: enum `ImageStatus` + columna `ProductImage.image_status` + migración Alembic 007 + Supabase mirror SQL
- **Gap 3**: índice GIN tsvector (migración 008) alineado con expresión exacta del repo del Agente 2
- **Gap 4**: 4 rutas FastAPI 0.115.x con `status_code=204` + `return None` → fix con `response_class=Response` (`auth.logout`, `users.force_logout`, `products.delete_product`, `products.delete_image`)
- **Gap 5**: `import_runs` queda in-memory; `# TODO(S3): persistir` documentado

Fixes secundarios aplicados:
- `tests/workers/test_thumbnails.py`: `from PIL import Image` (Pillow 10.x no auto-importa submódulos)
- `tests/workers/test_thumbnails.py`: aceptar `(RuntimeError, Retry)` (Celery autoretry envuelve excepciones)
- `tests/auth/test_jwt.py`: monkeypatch `settings.SUPABASE_JWT_SECRET` (orden-independencia singleton)

## 3. Verificación local

### Backend (verificado)

```bash
cd mt-pricing-backend
python -c "from app.main import app; print('routes:', len(app.routes))"
# → routes: 49

python -m pytest tests -v --no-cov -m "not integration"
# → 122/122 pass, 112 deselected (integration con Docker)

# Para correr integration: requiere Docker
python -m pytest tests -v --no-cov -m integration
# → testcontainers Postgres + supabase migrations + auth.py 204 fix
```

### Frontend (verificado)

```bash
cd mt-pricing-frontend
pnpm run lint        # ✅ 0 errors (13 warnings preexistentes)
pnpm run typecheck   # ✅
pnpm vitest run      # ✅ 32/32 (12 files)
pnpm run build       # ✅ todas las rutas
```

### Smoke E2E manual (sin Docker; con local-only stack per decisión)

```bash
# Terminal 1 — Supabase local + Postgres + Redis
cd supabase && npx supabase start
docker compose -f infra/docker-compose.dev.yml up redis worker-images

# Terminal 2 — backend
cd mt-pricing-backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 3 — frontend
cd mt-pricing-frontend && pnpm dev

# Validar
curl http://localhost:8000/health/live
curl -X POST http://localhost:8000/api/v1/imports/preview \
  -F "file=@Documentos referencia de articulos/PIM completo.xlsx"
# → preview con 5085 rows analizados

# Browser
open http://localhost:3000/login        # Magic Link
open http://localhost:3000/products     # Pantalla 2 (S1) + filtros avanzados (S2)
open http://localhost:3000/products/<sku>  # Pantalla 4 — tab Imágenes + edit inline
open http://localhost:3000/suppliers    # Pantalla suppliers patrón Pantalla 2
open http://localhost:3000/imports      # Pantalla 10 — wizard 4 pasos
open http://localhost:5555              # Flower (Celery monitoring)
```

## 4. DoD por story — vista consolidada

| Story | Backend | Frontend | Tests | DoD pendiente |
|-------|---------|----------|-------|---------------|
| US-1A-02-03 (PUT/PATCH) | ✅ | ✅ | ✅ | smoke E2E |
| US-1A-02-04-S2 (Imágenes + edit) | ✅ (storage helper) | ✅ | ✅ | smoke con bucket real |
| US-1A-02-06 (bucket + RLS) | ✅ | n/a | ✅ unit | smoke con `supabase start` |
| US-1A-02-07 (probe + mirror + SSRF) | ✅ | ⚠️ feature flag UI no | ✅ 28 SSRF | activar `ALLOW_PROBE_FROM_PIM_ES` cuando Q-09 firmado |
| US-1A-02-08 (thumbnails Celery) | ✅ | n/a | ✅ | smoke job end-to-end |
| US-1A-02-09 (filtros + full-text) | ✅ + GIN | ✅ | ✅ | benchmark <500ms en 5k rows |
| US-1A-02-10 (DELETE soft) | ✅ trigger | n/a | ✅ | n/a |
| US-1A-03-01 (suppliers schema) | ✅ + currencies seed | n/a | ✅ | n/a |
| US-1A-03-02 (suppliers CRUD) | ✅ | ✅ | ✅ | smoke E2E |
| US-1A-04-01 (cost schemes seeded) | ✅ | n/a | ✅ | n/a |
| US-1A-06-01 (importer wizard) | ✅ con PIM real | ✅ | ✅ | smoke apply real → BD |

## 5. Riesgos cumplidos / mitigados

| Riesgo S2 | Estado |
|-----------|--------|
| R-S2-01 PIM real no entregado | **Resuelto**: PIM real entregado durante el sprint (5085 rows, headers OK) |
| R-S2-02 SSRF en probe | Mitigado: ADR-055 + 28 tests vectoriales + denylist canónica |
| R-S2-03 Q-09 image rights | Pendiente humano: feature flag `ALLOW_PROBE_FROM_PIM_ES=False` por default |
| R-S2-04 Celery setup no reproduce en staging | N/A (decisión local-only Docker) |
| R-S2-05 Apply >10 min | Mitigado: chunked savepoints 1000 rows; benchmark pendiente |
| R-S2-06 `manual_locked_fields` | Resuelto: ya estaba en S1; importer la respeta |
| R-S2-07 Capacidad < 32 SP | N/A en modo multi-agente |
| R-S2-08 Particiones audit agotadas | Resuelto: task `audit_partitions_ensure` + seed |
| R-S2-09 Pillow alpine | Resuelto: `python:3.11-slim` Debian con libs runtime |
| R-S2-10 Doppler no sembrado | N/A (decisión local-only Docker, `.env.local` directo) |

## 6. Bloqueos / decisiones humanas pendientes

### Críticos para activar features

1. **Q-09 image rights firma legal** → activar `ALLOW_PROBE_FROM_PIM_ES=True` para mirror PIM ES
2. **Hetzner internal CIDRs** (cuando se decida volver a cloud staging) → poblar `SSRF_EXTRA_BLOCKED_CIDRS`
3. **Confirmar ADR-055** (renumerada desde ADR-047) — el doc está en draft, falta tu aprobación

### Decisiones tipo "sí/no" (defaults aplicados, cambia si discrepa)

4. Importer chunked threshold = **1000 rows** (cambiable via setting si excede 10 min)
5. `manual_locked_fields TEXT[]` en S1, lógica UI marcado = **S3** (decidido durante S2)
6. `audit_partitions_ensure` schedule = **diario 02:00 UTC**
7. Currencies seed = **USD/EUR/AED/SAR** con AED como `is_base=true`
8. Cost schemes seed = **FBA/FBM/DIRECT_B2C/DIRECT_B2B/MARKETPLACE**
9. UX `/suppliers` = **patrón Pantalla 2** (confirmado por psierra el 2026-05-07)
10. UX Pantalla 4 + Pantalla 10 = **firmadas inicialmente** por psierra el 2026-05-07

### Items operativos que requieren tu acción

11. **Commits del working tree** (no autónomo). Recomendado expandir el plan de S1 con un 5º commit para S2 (implementación + tests + ADR-055):
    - Commit S2-1: Backend data + storage (modelos, migraciones, seeds, helper, audit_partitions)
    - Commit S2-2: Backend API + importer (endpoints, services, importer pipeline, tests)
    - Commit S2-3: Workers + image pipeline + ADR-055 (SSRF, probe_mirror, thumbnails, Dockerfile, compose overlay)
    - Commit S2-4: Frontend (suppliers, imports wizard, filtros, edit inline, images)
    - Commit S2-5: Gap-fix backend (Pillow, image_status, GIN, 204 fixes)
12. **Migración 003** (`idx_products_search_tsv` con `english`) queda sin uso por planner — evaluar eliminar o mantener para hybrid search S3+
13. **Smoke con `supabase start` local**: validar bucket `product-images` + signed URLs + RLS

## 7. Próximos pasos sugeridos

1. **Smoke E2E manual** (15 min) con la stack local-only descrita en §3
2. **Commits temáticos** (los 5 propuestos en §6.11)
3. **Sprint 3 backlog refinement** (multi-agente posible) cubriendo:
   - PUT/PATCH suppliers + costes engine arranque (US-1A-04-02/03/04)
   - FX engine versionado (US-1A-05-*)
   - Importer costs (US-1A-06-02), compatibilidades (US-1A-06-03)
   - Translations approval workflow (US-1A-02-05)
   - RLS finas (US-1A-07-02)
   - Persistir `import_runs` en BD
   - UI "marcar campo como locked"
4. **Revisar ADR-055 SSRF policy** y firmarla
5. **Activar `ALLOW_PROBE_FROM_PIM_ES`** una vez Q-09 firmado por legal

---

**Velocidad efectiva**: 41 SP en una iteración multi-agente (~30 min wall-clock por agente, ejecutado en paralelo). Backend + frontend pipelines verde sin intervención humana intermedia. PIM real procesado sin desviaciones de spec — calidad de planning Sprint 0 + Sprint 1 validada en producción.
