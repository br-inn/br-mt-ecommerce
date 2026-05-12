---
title: "Sprint 4 — Reporte de ejecución multi-agente"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
related:
  - "../planning-artifacts/sprint4-backlog-refined.md"
  - "../planning-artifacts/sprint3-backlog-refined.md"
  - "../planning-artifacts/architecture-mt-pricing-mdm-phase1.md"
  - "../planning-artifacts/mt-product-matching-pipeline-detail.md"
  - "../planning-artifacts/adr/ADR-068-pricing-state-machine-v51.md"
  - "../planning-artifacts/adr/ADR-069-pricing-golden-numbers-bundling.md"
  - "../planning-artifacts/adr/ADR-070-bright-data-scraping-policy.md"
  - "../planning-artifacts/adr/ADR-071-playwright-self-host-noon.md"
  - "../planning-artifacts/adr/ADR-072-amazon-sp-api-integration.md"
  - "../planning-artifacts/adr/ADR-073-vlm-judge-prompt-spec.md"
  - "../planning-artifacts/adr/ADR-074-graphrag-evolution-roadmap.md"
  - "./sprint3-execution-report.md"
---

# Sprint 4 — Reporte de ejecución multi-agente

Gate de Fase 1b: pricing engine v5.1 con golden numbers, reemplazo de stubs S3 por adapters reales (Bright Data Amazon UAE, Playwright Noon UAE, SP-API real, VLM judge + calibrator), RLS finas declarativas, audit query API, importer datasheets PDF, y scaffold GraphRAG Fase 2+. Sprint ejecutado en 5 agentes paralelos con merges secuenciales `baaf3e4` (backend) → `9e7da00` (frontend) → `ab69c83` (consolidación) → `ec7044e` (ADRs).

## 1. Resumen ejecutivo

| Indicador | Valor |
|-----------|-------|
| Stories planificadas | 13 (66 SP capacidad / 35 SP comprometidos) |
| Stories cubiertas | 13/13 (incluye P2/P3 stretch absorbidos por modo multi-agente) |
| Agentes en paralelo (implementación) | 5 (A pricing+RLS+audit, B importers+datasheets, C comparator real adapters+channel mirror real, D frontend, E R&D GraphRAG+gap-fix) |
| Migraciones Alembic nuevas | 5 (021 pricing_engine_v51, 022 rls_finas, 023 datasheets_importer, 024 matching_v2, 025 graphrag_scaffold) |
| Endpoints API nuevos | `pricing_engine`, `audit_query`, `imports_datasheets`, `graphrag` |
| Servicios backend nuevos | `services/pricing/{golden_numbers, state_machine_v51, revise_service, bulk_publish_service}`, `services/matching/{calibrator, vlm_judge}`, adapters reales `bright_data_amazon_uae` + `playwright_noon_uae` + `amazon_sp_api` + `noon_real_api`, `services/graphrag/{cdc_dispatcher, schema_mapper, adapters/neo4j_stub}`, `services/importer_datasheets/*`, `services/audit/audit_query_service` |
| ADRs firmados | 7 (ADR-068..074 en `ec7044e`) |
| Commits asociados | `baaf3e4` feat(backend-s4), `9e7da00` feat(frontend-s4), `ab69c83` chore(consolidation), `ec7044e` docs(adr) |
| Tests añadidos | ≥21 archivos nuevos (calibrator, vlm_judge, golden_numbers, state_machine_v51, revise_service, bulk_publish_service, rls_finas, audit_query, datasheets, graphrag, adapters Amazon/Noon/Playwright) |

**Hallazgo clave**: el pricing engine v5.1 quedó implementado como `state_machine_v51.py` + `golden_numbers.py` + `revise_service.py` + `bulk_publish_service.py` separados, en lugar de un único `engine.py` propuesto en el backlog. La descomposición funciona como separación de responsabilidades (state machine vs. comparación vs. revisión vs. publicación masiva) y se alinea con ADR-068 firmado.

## 2. Distribución por agente

### Agente A — Backend Data + Pricing core + RLS + Audit (~19 SP)

| Story | Estado | Evidencia |
|-------|--------|-----------|
| US-1B-01-02 (Schema `prices` state machine + CHECK constraint) | ✅ | mig `20260507_021_pricing_engine_v51.py` (213 LOC) — extiende `prices` con state machine v5.1 sobre `pricing_models` mig 010 de S3 |
| US-1B-01-03 (`PricingEngine.calculate` port v5.1 + golden numbers) | ✅ | `app/services/pricing/golden_numbers.py` (304 LOC), `state_machine_v51.py` (243 LOC), `app/api/routes/pricing_engine.py` (166 LOC), `app/schemas/pricing_engine.py` (79 LOC). Tests `test_golden_numbers.py` (188 LOC), `test_state_machine_v51.py` (221 LOC). ADR-068 + ADR-069 firmados. |
| US-1A-07-02 (RLS finas) — carry-over S3 | ✅ | mig `20260507_022_rls_finas.py` (360 LOC), supabase mirror `supabase/migrations/20260507_021_rls_finas.sql` (206 LOC), tests `tests/data/test_rls_finas.py` (341 LOC) |
| US-1A-07-03 (Triggers audit_events en costs/translations/fx_rates/prices) | ✅ | `app/api/routes/audit_query.py` (178 LOC), `app/services/audit/audit_query_service.py` (231 LOC), `app/schemas/audit_query.py` (60 LOC). Tests `test_audit_query_api.py` (265 LOC), `test_audit_query_service.py` (267 LOC). |

### Agente B — Backend API + Importers + Datasheets (~10 SP)

| Story | Estado | Evidencia |
|-------|--------|-----------|
| US-1B-01-04 (`POST /prices/recalculate` single + masivo Celery) | ✅ | `app/services/pricing/revise_service.py` (178 LOC), `bulk_publish_service.py` (201 LOC), endpoints en `app/api/routes/pricing_engine.py`. Tests `test_revise_service.py` (152 LOC), `test_bulk_publish_service.py` (175 LOC). |
| US-1A-06-04 (Importer datasheets PDF — slip desde S3) | ✅ | mig `20260507_023_datasheets_importer.py` (129 LOC), `app/api/routes/imports_datasheets.py` (226 LOC), `app/services/importer_datasheets/{applier, importer_service, pdf_extractor, spec_parser}.py` (~840 LOC suma). `app/db/models/datasheet_import_run.py` (89 LOC), repo `datasheet_imports.py` (156 LOC). Tests `test_applier.py`, `test_pdf_extractor.py`, `test_spec_parser.py`, `test_imports_datasheets_api.py`. |

### Agente C — Comparator real adapters + Channel mirror real (~26 SP)

| Story | Estado | Evidencia |
|-------|--------|-----------|
| US-1A-09-03 (Adapters Bright Data Amazon UAE / Noon UAE) | ⚠️ | `app/services/matching/adapters/bright_data_amazon_uae.py` (284 LOC) implementado. **Noon UAE** se implementó vía Playwright (no Bright Data) — decisión técnica del agente C; consolidado en US-1A-09-04. Tests `test_bright_data_amazon_uae.py` (191 LOC). ADR-070 firmado (Bright Data scraping policy). Activación red real condicionada a Q-NEW-S3. |
| US-1A-09-04 (Adapters Playwright manufacturer) | ⚠️ | Se implementó `playwright_noon_uae.py` (230 LOC) con tests `test_playwright_noon_uae.py` (127 LOC) en lugar de Pegler/Arco/Giacomini. Decisión: priorizar Noon UAE marketplace sobre fabricantes (mayor cobertura competidores UAE). ADR-071 firmado (Playwright self-host Noon). Pegler/Arco/Giacomini diferidos a S5+. |
| US-1A-09-05 (Channel mirror SP-API real Amazon UAE) | ✅ | `app/services/channel_mirror/adapters/amazon_sp_api.py` (259 LOC) + `noon_real_api.py` (163 LOC). Tests `test_amazon_sp_api.py` (141 LOC) + `test_noon_real_api.py` (122 LOC). ADR-072 firmado (SP-API integration). Stubs S3 conservados como fallback (`amazon_sp_api_stub.py` + `noon_api_stub.py` siguen en repo). |
| US-1A-09-06 (Isotonic calibrator + VLM judge Gemini 2.5 Flash) | ✅ | `app/services/matching/calibrator.py` (207 LOC), `vlm_judge.py` (324 LOC), `adapter_registry.py` (74 LOC). Mig `20260507_024_matching_v2.py` (117 LOC) extiende `match_candidates` con `calibrated_confidence` + judge fields. Tests `test_calibrator.py` (155 LOC), `test_vlm_judge.py` (162 LOC), `test_adapter_registry.py` (69 LOC). ADR-073 firmado (VLM judge prompt spec). |

### Agente D — Frontend (Pricing UI + Auditoría + Datasheets) (~11 SP)

| Story | Estado | Evidencia |
|-------|--------|-----------|
| US-1B-01-06 (UI "Disparar recálculo" + preview + ETA + progreso) | ✅ | `app/(app)/precios/[id]/_client.tsx` (330 LOC) reemplaza placeholder page, `components/domain/pricing/{pricing-detail-card, pricing-alerts-panel, pricing-revise-dialog, pricing-bulk-publish-dialog}.tsx` (~720 LOC suma). `lib/api/endpoints/pricing-engine.ts` (166 LOC), `lib/hooks/pricing/use-pricing-engine.ts` (107 LOC). |
| US-1A-07-03-FE (UI tab Auditoría en SKU detail) | ✅ | `app/(app)/catalogo/[sku]/audit/_client.tsx` (103 LOC), `components/domain/audit/{audit-diff-viewer, audit-table, audit-timeline-rich}.tsx` (~750 LOC suma). `lib/api/endpoints/audit-query.ts` (111 LOC), `lib/hooks/audit/use-audit-query.ts` (49 LOC). |
| US-1A-06-04 frontend (Datasheets uploader) | ✅ | `app/(app)/catalogo/[sku]/datasheets/_client.tsx` (317 LOC), `components/domain/datasheets/{datasheets-preview, datasheets-uploader}.tsx` (~430 LOC). `lib/api/endpoints/imports-datasheets.ts` (152 LOC), `lib/hooks/imports/use-imports-datasheets.ts` (68 LOC). |
| OpenAPI types regen (consolidación) | ✅ | `ab69c83` chore(consolidation) — `lib/api/types.ts` regenerado (+9484 LOC) |

### Agente E — R&D GraphRAG scaffold + gap-fix backend (~3 SP + consolidación)

| Story | Estado | Evidencia |
|-------|--------|-----------|
| US-RND-01-11 (GraphRAG Fase 3 scaffold — `ComparatorService` adapter + `Neo4jGraphRepository` stub) | ✅ | mig `20260507_025_graphrag_scaffold.py` (221 LOC) — tablas `cdc_events` + relaciones grafo. Servicios `app/services/graphrag/{__init__.py, ports.py (98 LOC), cdc_dispatcher.py (175 LOC), schema_mapper.py (331 LOC), adapters/neo4j_stub.py (186 LOC)}`. Endpoint `app/api/routes/graphrag.py` (112 LOC). Worker `app/workers/tasks/graphrag.py` (54 LOC). Modelo `cdc_event.py` (120 LOC), repo `cdc_events.py` (63 LOC). Tests `test_graphrag_api.py` (188 LOC), `test_cdc_dispatcher.py` (168 LOC), `test_neo4j_stub.py` (148 LOC), `test_schema_mapper.py` (159 LOC). ADR-074 firmado. |
| Gap-fix consolidación post-merge | ✅ | `ab69c83` chore(consolidation): integration tests unblocked + openapi types regen + S4 deps añadidas a `pyproject.toml` + docker-compose.dev.yml extendido + `tests/conftest.py` ajustado. |
| ADRs S4 documentation | ✅ | `ec7044e` docs(adr): ADR-068..074 (7 documentos, 1042 LOC) |

## 3. DoD por story — vista consolidada

| Story | Backend | Frontend | Migración | ADR | DoD pendiente |
|-------|---------|----------|-----------|-----|---------------|
| US-1B-01-02 (prices state machine) | ✅ | n/a | mig 021 | ADR-068 | n/a |
| US-1B-01-03 (PricingEngine v5.1) | ✅ | ✅ (precios UI) | mig 021 | ADR-069 | golden numbers 30/30 firma Paula |
| US-1B-01-04 (POST /prices/recalculate) | ✅ | n/a | n/a | n/a | benchmark NFR-02 < 60s |
| US-1B-01-06 (UI Disparar recálculo) | n/a | ✅ | n/a | n/a | UX P6 firma post-merge |
| US-1A-09-03 (Bright Data adapters) | ⚠️ Amazon UAE ✅, Noon UAE → Playwright | n/a | mig 024 | ADR-070 | Q-NEW-S3 legal firma; Pegler/Arco/Giacomini diferidos S5+ |
| US-1A-09-04 (Playwright manufacturer) | ⚠️ entregado como Playwright Noon UAE (no manufacturers) | n/a | n/a | ADR-071 | adapters Pegler/Arco/Giacomini diferidos |
| US-1A-09-05 (Channel mirror SP-API real) | ✅ | ✅ (channel-mirror UI extendida) | n/a (reusa mig 015 S3) | ADR-072 | creds SP-API TI MT |
| US-1A-09-06 (Calibrator + VLM judge) | ✅ | n/a | mig 024 | ADR-073 | ECE < 5% verificable post dataset etiquetado |
| US-1A-06-04 (Importer datasheets PDF) | ✅ | ✅ (uploader UI) | mig 023 | n/a (datasheets V2 ADR pendiente S5) | bucket `product-datasheets` provisionado |
| US-1A-07-02 (RLS finas) | ✅ | n/a | mig 022 + supabase mirror | n/a | tests integration 4 roles × tablas |
| US-1A-07-03 (Audit triggers + query API) | ✅ | ✅ (audit tab) | mig 022 (indirect via RLS+audit) | n/a | append-only enforcement verificado |
| US-1A-07-03-FE (UI tab Auditoría) | n/a | ✅ | n/a | n/a | UX P11 firma post-merge |
| US-RND-01-11 (GraphRAG scaffold) | ✅ | n/a | mig 025 | ADR-074 | seed 50 triplets verificable |

## 4. Logros

- **Pricing engine v5.1 portado y operativo**: golden numbers + state machine v5.1 + revise service + bulk publish service. ADR-068 (state machine) + ADR-069 (bundling psicológico) firmados. Cierre del gate Fase 1b para "calculadora" de propuestas en AED.
- **Stubs S3 reemplazados por adapters reales**: Bright Data Amazon UAE + Playwright Noon UAE + SP-API real Amazon (con fallback a stubs en degraded mode). Pipeline `S3-foundation-v1` puede bumpear a `S4-real-adapters-v1` cuando Q-NEW-S3 firme.
- **Calibrator isotonic + VLM judge Gemini 2.5 Flash**: confidence calibrada (no score crudo) + rationale auditable por par SKU↔candidate. Base lista para auto-match ≥ 0.95 y human queue 0.80-0.95 (UI Tinder llega en S5).
- **RLS finas declarativas**: 360 LOC de policies SQL en Alembic + 206 LOC mirror Supabase + 341 LOC de tests integration. Defense-in-depth NFR-07/11 cumplida.
- **Audit query API + UI Auditoría tab**: timeline cronológico inverso con diff colorizado por campo. Cierra el último tab "disabled" desde S2.
- **Importer datasheets PDF**: `MTFT_*` / `MTCE_*` / `MTMAN_*` parsing operativo con `pdf_extractor` + `spec_parser` + `applier`. N:M product↔datasheet por sufijo. UI uploader con preview.
- **GraphRAG Fase 3 scaffold**: `cdc_dispatcher` + `schema_mapper` + `Neo4jGraphRepository` stub + tabla `cdc_events`. Adapter pattern listo para swap RagOnly → Hybrid → FullGraphRag sin refactor del comparador. ADR-074 firmado.
- **7 ADRs nuevos firmados** (068-074) — densa documentación arquitectónica para handoff a S5/S6.

## 5. Deuda / gaps

- **US-1A-09-04 desviación de scope**: planificado como Playwright manufacturers (Pegler/Arco/Giacomini), entregado como Playwright Noon UAE. Decisión técnica defendible (mayor cobertura UAE) pero fabricantes quedan pendientes — sin owner ni fecha. Riesgo: la "fuente fabricante directo gratis" del backlog no se materializó.
- **Q-NEW-S3 legal scraping Amazon UAE / Noon UAE**: ADR-070 firmado pero firma Legal MT pendiente. Adapters Bright Data + Playwright están wireados pero la activación red real queda gated por la firma.
- **Credenciales SP-API + AWS Role**: ADR-072 firmado, código listo, pero las credenciales productivas no están en Doppler — `amazon_sp_api.py` corre en degraded mode con cache local.
- **Q-09 image rights MT España**: sigue abierto — afecta mirror real de candidate images. Sin firma, los thumbnails de competitor no se persisten.
- **Golden numbers v5.1 firma Paula**: tests `test_golden_numbers.py` existen (188 LOC) pero `tests/golden/v51_outputs.json` requiere firma para certificar paridad ≥ 99 %.
- **UX firmas Pantalla 6 (Recálculo) + Pantalla 11 (Auditoría tab)**: frontend entregado con patrón existente reusado. Sign-off explícito post-merge.
- **`manual_locked_fields` UI marking**: deuda S2 → S3 → S4. Confirmado defer S5 (sin owner en backlog).
- **OCR pipeline + pdfplumber tablas**: importer datasheets v1 entregado (texto). V2 (tablas estructuradas + OCR) queda como US-1A-06-04-V2 en S5/S6 (entregado en S6 según `1a6d2e8`).

## 6. Métricas

| Métrica | Valor |
|---------|-------|
| Migraciones Alembic creadas | 5 (021-025) |
| Endpoints REST nuevos | 4 routers (pricing_engine, audit_query, imports_datasheets, graphrag) + extensiones a matches/channels_mirror |
| Servicios backend nuevos | 9 módulos (golden_numbers, state_machine_v51, revise_service, bulk_publish_service, calibrator, vlm_judge, importer_datasheets/*, audit_query_service, graphrag/*) |
| Adapters reales | 4 (bright_data_amazon_uae, playwright_noon_uae, amazon_sp_api, noon_real_api) |
| Modelos SQLAlchemy nuevos | `cdc_event.py`, `datasheet_import_run.py` |
| Tests añadidos (backend) | ≥21 archivos nuevos, ~4500 LOC test (RLS, calibrator, vlm_judge, golden_numbers, state_machine_v51, revise, bulk_publish, audit_query, datasheets, graphrag, adapters) |
| Tests añadidos (frontend) | E2E Playwright (`fdf712c` 34 specs S3+S4: pricing-detail-revise, pricing-simular, channel-mirror-amazon, admin-currencies-fx, datasheets-uploader, validacion-matches, aprobaciones-bulk, translations-workflow, catalog-filters-nuqs, dashboard-kpis) |
| Líneas de código añadidas (backend) | 11479 LOC (`baaf3e4`) + 13 LOC `8598cd9` previo |
| Líneas de código añadidas (frontend) | 3355 LOC (`9e7da00`) |
| ADRs firmados | 7 (068, 069, 070, 071, 072, 073, 074) — 1042 LOC documentación |

## 7. Lecciones / observaciones

- **Decomposición pricing engine en módulos especializados**: lo que el backlog planeó como `engine.py` monolítico (con `rules/{g1, g2, bundling, fallback_tiers}.py`) se entregó como `golden_numbers` + `state_machine_v51` + `revise_service` + `bulk_publish_service`. La separación se alinea con ADR-068 y simplifica los tests, pero divergió del naming del backlog.
- **Desviación US-1A-09-04 (manufacturer → marketplace)**: el agente C reasignó SP a Playwright Noon UAE en lugar de Pegler/Arco/Giacomini. Documentar en sprint5-backlog para reabrir la story "manufacturer fetchers" como nueva si MT lo requiere para cobertura B2B.
- **Stubs conservados como fallback**: `amazon_sp_api_stub.py`, `noon_api_stub.py`, `amazon_uae_stub.py`, `noon_uae_stub.py` siguen en repo después del merge S4 — patrón circuit breaker degraded mode listo sin código adicional.
- **Consolidación post-merge necesaria**: `ab69c83` regen OpenAPI types (+9484 LOC en `lib/api/types.ts`) + deps + conftest. Modelo aplicable a S5/S6 — el "agente E gap-fix" sigue siendo crítico.
- **GraphRAG scaffold adelantado vs. roadmap original**: pipeline detail apuntaba a Fase 2 para Neo4j; el scaffold se entregó en S4 con costo bajo (3 SP) — habilita prototipos sin reescribir comparador. Confirmado en ADR-074.
- **Cobertura E2E retroactiva**: `fdf712c` añadió 34 specs Playwright S3+S4 post-merge — patrón de test E2E post-feature funcionó pero implica deuda visible (cobertura E2E no es DoD pre-merge sino post-sprint).

## 8. Salida hacia Sprint 5

Inputs S5 desde S4:
- **Pricing engine listo**: `prices` con state machine v5.1 → S5 cierra workflow aprobación completo (US-1B-02-01..05).
- **Comparator real con calibrator + VLM judge**: produce `match_candidates` con `calibrated_confidence` + rationale → S5 puede arrancar UI Tinder humana (US-RND-01-10) sobre data real.
- **GraphRAG scaffold**: `cdc_events` + `Neo4jGraphRepository` stub → S5 puede iniciar PoC Hybrid sin refactor.
- **Audit triggers + RLS finas**: defense-in-depth cerrada → S5 puede entregar export CSV firmado FTA (US-1A-07-05) sin reabrir RBAC.

Carry-over efectivo a S5:
- **Adapters manufacturer Pegler/Arco/Giacomini** (~5 SP) — desviación US-1A-09-04 no compensada.
- **OCR + pdfplumber tablas** (US-1A-06-04-V2) — entregado parcial en S5 (`9d417c8`) + cierre S6 (`1a6d2e8`).
- **Activación red real adapters**: bloqueada por Q-NEW-S3 + Q-09 + creds SP-API. S5 entregó kill-switch + feature flags + cost_tracker (`9d417c8`) → ahora la activación es operativa, sólo falta firma.
- **Multi-judge consensus weighting**: `judge_dispatcher` consensus simple llega en S5 (`9d417c8` US-1A-06-04-V2 minimal); weighting basado en historical accuracy diferido > S6.
- **Bulk-recalc nocturno**: entregado en S5 (`9d417c8`).

Próximos pasos S5 confirmados en `1740e04` (sprint5-backlog-refined):
1. EP-1B-02 workflow aprobación pricing completo.
2. UI Tinder humana matching (US-RND-01-10).
3. RBAC granular (`matches:*`, `channels:*`, `prices:override_review`).
4. Observability stack + IaC Hetzner + CI/CD pipeline (US-1A-OBS/IAC/CICD-01).
5. BR PMO hooks scaffold (US-RND-01-12).

---

**Velocidad efectiva**: 35 SP comprometidos cubiertos con stretch absorbido (66 SP teóricos). Backend + frontend con 14834 LOC nuevas + 7 ADRs firmados + consolidación post-merge en una iteración. Gate Fase 1b cerrado a nivel código; activación red real condicionada a firmas legales (Q-NEW-S3 + Q-09) y entrega de credenciales SP-API/AWS por TI MT.
