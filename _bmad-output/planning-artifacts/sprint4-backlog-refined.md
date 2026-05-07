---
title: "Sprint 4 — Backlog refinado"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
sprint: 4
capacity_target_sp: 35
sprint_goal: "Cerrar Fase 1b — Pricing engine end-to-end con costs reales (S3) ↔ frontend, reemplazar stubs del matching pipeline por adapters reales (Bright Data + Playwright + SP-API + VLM judge), entregar importer datasheets PDF + RLS finas + auditoría UI; abrir Fase 2 con scaffold GraphRAG."
related:
  - "epics-and-stories-mt-pricing-mdm-phase1.md"
  - "sprint3-backlog-refined.md"
  - "../implementation-artifacts/sprint3-execution-report.md"
  - "mt-product-matching-pipeline-detail.md"
  - "architecture-mt-pricing-mdm-phase1.md"
  - "prd-mt-pricing-mdm-phase1.md"
  - "ux-mockups-mt-pricing-mdm-phase1.md"
  - "risk-register-consolidado.md"
  - "adr/ADR-055-ssrf-policy-image-probe.md"
---

# Sprint 4 — Backlog refinado — MT Middle East MDM + Pricing Fase 1b

## 1. Resumen ejecutivo

Sprint 4 marca el **gate de Fase 1b**: el motor de pricing pasa de "datos en BD" (cierre S3) a **propuestas en AED visibles en UI** end-to-end (US-1B-01-01..06 serie). En paralelo, los **stubs del comparador** introducidos en S3 se sustituyen por adapters reales: Bright Data + Playwright para Amazon UAE / Noon UAE (etapa 2), SP-API real para channel mirror, y VLM judge + isotonic calibrator (etapas 6-7 del pipeline). Cierra deuda S3 con importer fichas técnicas PDF, RLS finas declarativas, audit triggers en costs/translations, y la UI tab Auditoría en ficha SKU. Como **R&D track Fase 2**, scaffold GraphRAG (`Neo4jGraphRepository` stub + abstracciones `ComparatorService` con adapter swap por config).

**Incluye**: pricing engine port v5.1 con golden numbers (US-1B-01-03), endpoint `POST /prices/recalculate` (US-1B-01-04), pantalla "Disparar recálculo" (US-1B-01-06), schema `prices` con state machine (US-1B-01-02), adapters Bright Data Amazon UAE + Noon UAE (US-1A-09-03), Playwright manufacturer fetchers (Pegler/Arco/Giacomini, US-1A-09-04), channel mirror SP-API real con SDK Amazon (US-1A-09-05), isotonic calibrator + VLM judge Gemini 2.5 Flash (US-1A-09-06), importer datasheets PDF (US-1A-06-04), RLS finas (US-1A-07-02 carry de S3), audit triggers (US-1A-07-03), UI tab Auditoría (US-1A-07-03-FE), hooks GraphRAG (US-RND-01-11).

**No incluye** (defer S5+): UI Tinder-swipe humana (US-RND-01-10 → S5), workflow aprobación por excepción completo (US-1B-02-* → S5), bulk approve + escalation digest (S5), reverse image search (US-RND-01-09 → S5-S6 con flag off), POC 500 SKUs métricas finales (US-RND-01-12 → S6-S7), connectors base shadow publish (EP-1B-04 → S6).

**Gates de Fase 1b al cerrar S4**: pricing engine calcula `price_aed` por SKU × canal × esquema con paridad ≥ 99 % vs golden numbers v5.1, comparador produce candidates reales con confidence calibrada (auto-match ≥ 0.95 / human queue 0.80-0.95) sobre PIM real, audit append-only enforced en BD, RLS RBAC defense-in-depth activa.

**Dependencias críticas pre-kickoff**: (a) Q-NEW-S3 legal scraping firmado (Champion + Legal MT) — bloquea US-1A-09-03 & 04; (b) Credenciales SP-API + AWS de TI MT — bloquea US-1A-09-05; (c) Q-09 image rights MT España firmado — bloquea mirror real candidates; (d) Golden numbers v5.1 (US-1B-01-01) firmados por Paula desde S0 — bloquea US-1B-01-03; (e) ADR-055 SSRF policy firmado (carry de S3) para activar adapters reales con probe extension; (f) UX firma Pantalla 6 (Disparar recálculo) y Pantalla 11 (Auditoría tab).

## 2. Capacidad asumida

| Concepto | Valor |
|----------|-------|
| Devs FTE | 2-3 + TI Integración part-time + R&D Champion (matcher) |
| Velocity asumida | 32-40 SP/sprint humano (modo multi-agente sostuvo 50+ en S1/S2/S3) |
| Sprint length | 2 semanas (10 días lab.) |
| Reservas | 20 % buffer + 15 % refinement adapters reales (territorio nuevo de red + scraping) |
| **Capacidad target S4** | **35 SP** |
| Carry-over S3 | 0 SP esperado si S3 ejecuta como S1/S2 (RLS finas y datasheets eran stretch S3 confirmado defer formal). En riesgo: US-1A-06-03 importer materials + US-1A-09-02 channel mirror stub si bajaron. |

Si la capacidad real cae a 28-30 SP, aplicar §6 priorización: bajar US-RND-01-11 GraphRAG scaffold (-3) + US-1A-07-03-FE UI Auditoría tab (-3) + US-1A-09-04 Playwright manufacturer (-5) → 24 SP core (pricing engine + adapters Amazon UAE Bright Data + VLM judge).

## 3. Tabla maestra de stories

| ID | Título | Épica | SP | Prioridad | Dominio | Agente sugerido | Depende de |
|----|--------|-------|----|-----------| --------|------------------|------------|
| US-1B-01-02 | Schema `prices` con state machine + CHECK constraint | EP-1B-01 | 3 | P0 | backend (data) | A | US-1A-04-02 (S3) |
| US-1B-01-03 | `PricingEngine.calculate(sku, channel, scheme, fx_rate_id)` port v5.1 | EP-1B-01 | 8 | P0 | backend (service) | A | US-1B-01-01 (S0), US-1B-01-02, US-1A-04-03 (S3) |
| US-1B-01-04 | `POST /prices/recalculate` single + masivo (Celery) | EP-1B-01 | 5 | P0 | backend (api+workers) | B | US-1B-01-03 |
| US-1B-01-06 | UI "Disparar recálculo" con preview + ETA + progreso | EP-1B-01 | 5 | P1 | frontend | D | US-1B-01-04 |
| US-1A-09-03 | Adapters reales Bright Data Amazon UAE + Noon UAE (matching pipeline etapa 2) | EP-1A-09 | 8 | P0 | backend (workers+integrations) | C | US-1A-09-01-S3 (S3), Q-NEW-S3 firma |
| US-1A-09-04 | Adapters Playwright manufacturer (Pegler/Arco/Giacomini) | EP-1A-09 | 5 | P1 | backend (workers) | C | US-1A-09-01-S3 (S3) |
| US-1A-09-05 | Channel mirror SP-API real Amazon UAE (reemplazo `amazon_sp_api_stub.py`) | EP-1A-09 | 5 | P1 | backend (integrations) | C | US-1A-09-02-S3 (S3), creds SP-API TI |
| US-1A-09-06 | Isotonic calibrator + VLM judge Gemini 2.5 Flash (etapas 6-7) | EP-1A-09 / EP-RND-01 | 8 | P0 | backend (R&D+service) | C/E | US-1A-09-01-S3, US-RND-01-04 |
| US-1A-06-04 | Importer datasheets PDF (`MTFT_*`/`MTCE_*`/`MTMAN_*`) → `product_datasheets` | EP-1A-06 | 5 | P1 | backend+frontend | B/D | US-1A-02-06 (S2), US-1A-06-01 (S2) |
| US-1A-07-02 | RLS finas `products`/`costs`/`prices`/`audit_events` (carry-over de S3) | EP-1A-07 | 3 | P1 | backend (data) | A | US-1A-07-01 (S1), US-1A-04-02 (S3), US-1B-01-02 |
| US-1A-07-03 | Triggers `audit_events` en costs/translations/fx_rates | EP-1A-07 | 5 | P1 | backend (data) | A | US-1A-04-02 (S3), US-1A-05-02 (S3) |
| US-1A-07-03-FE | UI tab Auditoría en SKU detail (consume audit feed) | EP-1A-07 | 3 | P2 | frontend | D | US-1A-07-03 |
| US-RND-01-11 | GraphRAG Fase 3 scaffold (`ComparatorService` adapter + `Neo4jGraphRepository` stub) | EP-RND-01 | 3 | P3 | backend (R&D arch) | E | US-1A-09-01-S3 |
| **TOTAL** |  |  | **66 SP capacidad / 35 SP comprometidos** |  |  |  |  |

> **Comprometidos S4 (35 SP)**: US-1B-01-02 (3) + US-1B-01-03 (8) + US-1B-01-04 (5) + US-1A-09-03 (8) + US-1A-09-06 (8) + US-1A-07-03 (5) + US-1A-07-02 (3) — overflow con US-1B-01-06, US-1A-09-04, US-1A-09-05, US-1A-06-04, US-1A-07-03-FE, US-RND-01-11 si modo multi-agente sostiene velocity S1/S2/S3. Stories P2/P3 son stretch.

## 4. Fichas detalladas

---

### US-1B-01-02 — Schema `prices` con state machine y CHECK constraint

**Épica**: EP-1B-01 ([epics-and-stories §1069](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** la migración que crea `prices` con `status` enum (CHECK constraint) e índices del PRD
**Para** que el motor de pricing tenga tabla destino e impedir estados inválidos.

#### Contexto
**MUST de S4** — destino de outputs del `PricingEngine.calculate`. Aún sin workflow de aprobación completo (S5), `prices` debe nacer con state machine declarada (`draft`, `auto_approved`, `pending_review`, `approved`, `rejected`, `published`, `superseded`) para evitar refactor en S5. Constraint CHECK + trigger BEFORE INSERT validan transitions desde día 1.

#### Criterios de aceptación
1. **Dado** la migración aplicada **Cuando** intento `INSERT INTO prices ... status='aprobado'` (typo) **Entonces** el CHECK constraint falla con error `invalid_input_value`.
2. **Dado** un INSERT válido `status='draft'` **Cuando** se ejecuta **Entonces** persiste con `version=1`.
3. **Dado** los índices declarados **Cuando** consulto `\d prices` **Entonces** existen `idx_prices_lookup` (sku, channel_code, scheme_code, status), `idx_prices_status_pending` partial WHERE `status='pending_review'`, `idx_prices_active` partial WHERE `status IN ('approved','published')`.
4. **Dado** un UPDATE de `breakdown` en un price `approved` **Cuando** se ejecuta **Entonces** trigger crea nueva versión (anterior pasa a `superseded`, nuevo nace `draft` requiriendo nueva approval) — versionado igual que `costs` (S3 pattern).
5. **Dado** un INSERT con `status='approved'` directo (sin pasar por draft → pending_review → approved) **Cuando** se ejecuta **Entonces** trigger lo rechaza con `invalid_initial_status` (sólo `draft` o `auto_approved` válidos en INSERT).

#### Notas técnicas
- Migración Alembic 0017: tabla `prices` (id UUID, sku FK, channel_code FK, scheme_code FK, fx_rate_id FK, cost_id FK, price_aed NUMERIC(12,2), pvp_min_aed NUMERIC(12,2), margin_pct NUMERIC(5,2), rule_applied TEXT, breakdown JSONB, alerts JSONB[], status ENUM, version INT, created_by, created_at, approved_by, approved_at).
- Trigger PL/pgSQL `prices_state_machine_trg BEFORE INSERT OR UPDATE` — valida transitions vs tabla `price_state_transitions`.
- Constraint `UNIQUE (sku, channel_code, scheme_code, status) WHERE status='approved'` — sólo 1 active aprobado por combo.
- Audit ya cubierto por trigger genérico de US-1A-07-03.
- TODO: ADR-068 "State machine prices Fase 1b" documentando enum + transitions + reasoning de no permitir INSERT directo a `approved`.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0017_create_prices_table.py`
- `infra/supabase/migrations/0017_prices_state_machine.sql`
- `mt-pricing-backend/app/db/models/price.py`
- `mt-pricing-backend/tests/data/test_prices_state_machine.py` (≥ 8 tests cubriendo cada transition válida e inválida).

#### DoD
- [ ] Migración up + down testeada.
- [ ] CHECK constraint + trigger probados con BDD completo.
- [ ] Coverage ≥ 80 %.
- [ ] Index plan EXPLAIN sobre 1k filas mock dentro de 50 ms.
- [ ] ADR-068 firmado.

#### SP: 3

---

### US-1B-01-03 — `PricingEngine.calculate(sku, channel, scheme, fx_rate_id)` port v5.1

**Épica**: EP-1B-01 ([epics-and-stories §1085](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** el servicio puro `PricingEngine.calculate` que dado un SKU + canal + esquema + FX retorna `{price_aed, pvp_min, margin_pct, rule_applied, breakdown, alerts}`
**Para** centralizar las reglas y testearlas con golden numbers v5.1.

#### Contexto
**Corazón de Fase 1b**. Port directo del v5.1 (`MT_Pricing_Run_Kit/src/pricing.py` + macros VBA) al stack FastAPI. Decisión port-vs-rewrite firmada en S0 (Q-10). Consume `costs.scheme_landed_aed` (S3) y `fx_rate_at(currency, 'AED', t)` (S3). Aplica reglas G1 (margen mínimo por canal/esquema), G2 (delta margen vs precio anterior), bundling psicológico (XX,99 / XX,49 AED), fallback tiers cuando margen mínimo no se alcanza. Output strictly tipado vía Pydantic.

#### Criterios de aceptación
1. **Dado** un SKU con coste FBA y canal Amazon UAE **Cuando** invoco `PricingEngine.calculate(sku, 'AMAZON_UAE', 'FBA', fx_rate_id)` **Entonces** retorna estructura completa con `rule_applied` (string), `breakdown` (JSON), `alerts` array.
2. **Dado** los 30 SKUs golden de US-1B-01-01 **Cuando** ejecuto los tests **Entonces** ≥ 99 % paridad de outputs vs `tests/golden/v51_outputs.json` (margen ε=0.01 AED por bundling psicológico). Discrepancias documentadas en `docs/pricing-port-discrepancies.md`.
3. **Dado** un coste cuyo `price_aed` calculado < `pvp_min` permitido **Cuando** se calcula **Entonces** retorna `alerts=[{level:'critical', code:'price_below_pvp_min'}]` y `rule_applied='fallback_tier'` con tier escalado.
4. **Dado** un SKU sin coste activo para `(channel, scheme)` **Cuando** se invoca **Entonces** retorna 422 estructurado `error.code='cost_missing_for_scheme'` (no calcula con costo nulo — falla rápido).
5. **Dado** un cambio de FX de 4.29 a 4.18 EUR/AED **Cuando** se invoca con nuevo `fx_rate_id` **Entonces** el `breakdown` referencia el rate correcto y `price_aed` refleja el delta proporcional.
6. **Dado** un canal `pre_launch` **Cuando** se invoca **Entonces** calcula con flag `simulation=true` y NO genera alertas críticas por delta margen (canal aún no produce, deltas no significan nada todavía).
7. **Dado** un SKU con bundling psicológico activado en config **Cuando** `price_aed` raw es 145.34 **Entonces** snap a `145.49` (regla XX,49); si raw es 145.78 → `145.99` (regla XX,99). Configurable por canal.

#### Notas técnicas
- `app/services/pricing/__init__.py`, `engine.py` (función pura), `rules/{g1_min_margin.py, g2_delta_margin.py, bundling.py, fallback_tiers.py}`.
- `app/schemas/pricing.py` Pydantic: `PriceCalculationInput`, `PriceCalculationOutput`, `Alert`.
- Tests: 30 golden numbers + 20 unit edge cases (bundling boundaries, fx swap, fallback tier escalation, SKU sin coste, channel pre_launch).
- Performance target: < 5 ms wall-clock por SKU (NFR-01 — sample con `pytest-benchmark`).
- TODO ADR nuevo: ADR-069 "Estrategia bundling psicológico AED" — documentar elección XX,49 vs XX,99 por canal y umbral de snap (default ±0.30 AED del raw).
- Cohabita en el mismo paquete `app/services/pricing/` que las stories S5 (engine se reusa, engine no se reescribe).

#### Archivos esperados
- `mt-pricing-backend/app/services/pricing/engine.py`
- `mt-pricing-backend/app/services/pricing/rules/{g1_min_margin.py,g2_delta_margin.py,bundling.py,fallback_tiers.py}`
- `mt-pricing-backend/app/schemas/pricing.py`
- `mt-pricing-backend/tests/golden/v51_outputs.json` (entregable de US-1B-01-01 S0; verificar ya existe)
- `mt-pricing-backend/tests/services/pricing/` (≥ 30 golden tests + 20 unit)
- `docs/pricing-port-discrepancies.md` (TODO si > 0 discrepancias)

#### DoD
- [ ] Coverage ≥ 85 % en `app/services/pricing/`.
- [ ] 30/30 golden numbers passing (o discrepancias firmadas por Paula).
- [ ] Performance bench < 5 ms p95 sobre 1k iteraciones.
- [ ] ADR-069 firmado.
- [ ] Smoke E2E manual sobre 5 SKUs reales del PIM con cost real S3.
- [ ] OpenAPI no impactado (servicio interno, no expone endpoint directo).

#### SP: 8

---

### US-1B-01-04 — `POST /prices/recalculate` single + masivo (Celery)

**Épica**: EP-1B-01 ([epics-and-stories §1101](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** disparar recálculo de precios (single SKU o masivo)
**Para** mantener propuestas actualizadas tras cambios de coste/FX.

#### Contexto
Capa API + Celery sobre US-1B-01-03. Single mode (síncrono < 5 s) y bulk mode (asíncrono Celery, < 60 s para 224 SKUs × 5 canales × 4 esquemas = ~4480 propuestas, NFR-02). Reusa `app/workers/` pattern de S2 (audit_partitions + S3 importers). Tracker de progreso en Redis con `task_id` retornado al cliente; endpoint `GET /tasks/{id}/progress` ya parcial en S3.

#### Criterios de aceptación
1. **Dado** `POST /prices/recalculate` con `scope='single', sku='MT-V-038'` **Cuando** se ejecuta **Entonces** sistema calcula propuestas para los `(channel, scheme)` activos del SKU < 5 s, persiste en `prices` con `status='draft'`, retorna lista de IDs creados.
2. **Dado** `POST /prices/recalculate` con `scope='all', trigger='fx_change', fx_rate_id=1234` **Cuando** se ejecuta **Entonces** sistema dispara job Celery `recalculate_all_prices_task`, retorna 202 con `task_id`, y el job procesa < 60 s para 224 × 5 × 4 propuestas.
3. **Dado** un job en curso **Cuando** consulto `GET /tasks/{task_id}/progress` **Entonces** retorna `{status:'running', total:4480, processed:1240, eta_seconds:34}`.
4. **Dado** un job completado **Cuando** consulto **Entonces** retorna `{status:'success', total:4480, succeeded:4475, failed:5, failed_details:[{sku, error_code}]}`.
5. **Dado** un Comercial **Cuando** llama **Entonces** RBAC permite. Dado un usuario sin role **Cuando** llama **Entonces** retorna 403.
6. **Dado** dos jobs masivos lanzados simultáneamente **Cuando** se procesan **Entonces** segundo recibe 409 `error.code='recalculate_already_running'` (mutex Redis, evita race conditions sobre `prices`).
7. **Dado** un SKU sin coste para algún `(channel, scheme)` **Cuando** se procesa en bulk **Entonces** queda en `failed` con `error_code='cost_missing_for_scheme'` y resto continúa (no aborta el job entero).

#### Notas técnicas
- `app/api/v1/prices.py` con endpoints `POST /prices/recalculate`, `GET /prices/recalculate/{task_id}`.
- `app/workers/pricing_recalc.py` Celery task con chunking de 100 SKUs por sub-task + progress tracker en Redis (key `pricing:recalc:{task_id}`).
- Mutex Redis vía `app/utils/redis_lock.py` (key `pricing:recalc:lock`, TTL 300s).
- Notificaciones: emit Sentry breadcrumb cada 10% progreso; si `failed_count > 5%`, alerta Slack `#mt-alerts`.

#### Archivos esperados
- `mt-pricing-backend/app/api/v1/prices.py`
- `mt-pricing-backend/app/services/pricing/recalc_service.py`
- `mt-pricing-backend/app/workers/pricing_recalc.py`
- `mt-pricing-backend/app/utils/redis_lock.py` (si no existe ya)
- Tests: unit + integration con Celery eager mode + 1 E2E happy.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Performance benchmark sobre PIM real: 224 × 5 × 4 < 60 s p95 (NFR-02).
- [ ] OpenAPI actualizado.
- [ ] Smoke E2E con FX change real cargado en S3.
- [ ] Mutex testeado con 2 jobs concurrentes.

#### SP: 5

---

### US-1B-01-06 — UI "Disparar recálculo" con preview + ETA + progreso

**Épica**: EP-1B-01 ([epics-and-stories §1133](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** una pantalla guiada para disparar recálculo de precios
**Para** entender qué afecta antes de ejecutar y ver progreso en vivo.

#### Contexto
Pantalla 6 del UX (firma pendiente — ver §6 riesgos). Patrón Wizard en 3 pasos: (1) Trigger + scope (FX change vs cost change vs manual), (2) Preview impacto (`Esto afecta 187 SKUs × 4 × 5 = 3.740 propuestas`), (3) Ejecutar + progreso vivo (refresh 2 s polling al endpoint `/tasks/{id}/progress`).

#### Criterios de aceptación
1. **Dado** un Comercial en `/pricing/recalculate` **Cuando** carga **Entonces** ve wizard step 1 con dropdown trigger (FX change, cost change, manual) y selector scope (all SKUs / canal específico / family / single SKU).
2. **Dado** completa step 1 con `trigger=fx_change, scope=all` **Cuando** click "Continuar" **Entonces** UI llama `POST /prices/recalculate?dry_run=true` y muestra preview "187 SKUs × 5 canales × 4 esquemas = 3.740 propuestas". ETA estimada 47s.
3. **Dado** preview confirmado **Cuando** click "Ejecutar" **Entonces** llama `POST /prices/recalculate` (no dry-run), recibe `task_id`, transiciona a step 3 con barra de progreso polling cada 2s.
4. **Dado** job en curso **Cuando** progress < 100% **Entonces** UI muestra `{processed}/{total} (45%) — ETA 23s`.
5. **Dado** job completado **Cuando** UI recibe `status:success` **Entonces** muestra resultado: totales `auto_approved: N (Fase 1b S5)` / `pending_review: M` / `failed: 0` y link a `/products?has_proposal=true`.
6. **Dado** job con `failed > 0` **Cuando** completa **Entonces** UI muestra warning amarillo con tabla de SKUs fallidos y razones.

#### Notas técnicas
- Frontend: `app/(app)/pricing/recalculate/page.tsx` con stepper Shadcn + react-hook-form.
- Frontend: `lib/api/pricing.ts` con typed fetcher + polling helper `usePollProgress(taskId)`.
- i18n: namespace `pricing.recalculate.*`.
- TODO: confirmar UX wireframe Pantalla 6. Si no firmado al día 3, decisión "reusar patrón Pantalla 5 stepper inline" para no bloquear (escalation owner: psierra).

#### Archivos esperados
- `mt-pricing-frontend/app/(app)/pricing/recalculate/page.tsx`
- `mt-pricing-frontend/components/pricing/recalculate-wizard.tsx`
- `mt-pricing-frontend/components/pricing/recalculate-progress.tsx`
- `mt-pricing-frontend/lib/api/pricing.ts`
- `mt-pricing-frontend/lib/hooks/use-poll-progress.ts`
- Tests: unit wizard + integration polling + 1 E2E happy.

#### DoD
- [ ] Coverage ≥ 80 % UI nueva.
- [ ] UX firmada Pantalla 6 antes de merge (o decisión reuso explícita).
- [ ] Smoke E2E con job real sobre PIM.
- [ ] i18n keys ES/EN.
- [ ] Sentry sin errores; polling no genera memory leak (cleanup verificado).

#### SP: 5

---

### US-1A-09-03 — Adapters reales Bright Data Amazon UAE + Noon UAE (matching pipeline etapa 2)

**Épica**: EP-1A-09 ([apéndice S3 §B + pipeline detail §4](mt-product-matching-pipeline-detail.md))
**Como** dev backend
**Quiero** los adapters Bright Data reales que reemplacen `stub_amazon_ae.py` + `stub_noon_ae.py`
**Para** que el comparador opere sobre listings reales y produzca `match_decisions` con datos verídicos.

#### Contexto
**Bloqueado por Q-NEW-S3 firma legal**. Pipeline detail §4.2 documenta el patrón hexagonal con Protocol `CandidateFetcher`. S3 sólo entregó stubs canned. S4 implementa: `BrightDataAmazonAEFetcher` y `BrightDataNoonAEFetcher` usando Web Scraper API ($1.50/1k success, presupuesto Champion). Rate limiting + circuit breaker `pybreaker` (5 fallos → abre 5 min, fallback a stub canned con flag `degraded_mode=true` en metadata). Compatible 100% con `CandidateFetcherOrchestrator` de S3 — solo se inyecta nuevo adapter en factory.

#### Criterios de aceptación
1. **Dado** un SKU `MT-V-038` y query `"Pegler brass ball valve DN50 BSP"` **Cuando** llamo `BrightDataAmazonAEFetcher.fetch(query)` **Entonces** sistema invoca Bright Data API con dataset_id Amazon UAE, recibe top 20 resultados, retorna lista `CandidateRaw` con `source="amazon_ae"`, `asin`, `title`, `price_aed`, `image_urls`, `seller`, `fetched_at`.
2. **Dado** un job dry-run sobre 5 SKUs reales **Cuando** se ejecuta **Entonces** retorna ≥ 80% SKUs con al menos 1 candidato real (cobertura mínima — alarma si < 80%).
3. **Dado** Bright Data falla 5 veces seguidas **Cuando** se invoca de nuevo **Entonces** circuit breaker abre, fetcher retorna stub canned con metadata `degraded_mode=true`, Sentry alert + Slack `#mt-alerts`.
4. **Dado** Bright Data devuelve precios en USD/EUR (no AED) **Cuando** se procesa **Entonces** sistema convierte a AED usando `fx_rate_at` vigente, marca `price_currency_inferred=true`.
5. **Dado** un candidato con `image_urls` vacío **Cuando** se procesa **Entonces** queda en `CandidateRaw` con flag `has_images=false` (no rompe pipeline downstream).
6. **Dado** rate limit hit (HTTP 429) **Cuando** ocurre **Entonces** retry con exponential backoff (1s, 2s, 4s), max 3 intentos, después fallback al stub.
7. **Dado** un Noon UAE listing **Cuando** se procesa **Entonces** sistema extrae `noon_id` (no ASIN), `arabic_title` cuando exista, fields equivalentes.
8. **Dado** un job dry-run **Cuando** se completa **Entonces** persiste en `match_decisions` con `pipeline_version='S4-real-adapters-v1'` (bump desde `S3-foundation-v1`).

#### Notas técnicas
- `app/services/comparator/adapters/bright_data_amazon_ae.py`, `bright_data_noon_ae.py` implementando `CandidateFetcher` Protocol.
- `app/utils/circuit_breaker.py` envoltorio sobre `pybreaker` (libs: `pybreaker>=1.2.0`).
- Configuración credenciales Bright Data via env vars `BRIGHT_DATA_API_KEY`, `BRIGHT_DATA_AMAZON_AE_DATASET_ID`, `BRIGHT_DATA_NOON_AE_DATASET_ID` — Doppler en prod, `.env.local` en dev local Docker.
- Reuse `mirror_competitor_image(image_url, sku, listing_id)` del pipeline detail §5.2 con extension de SSRF probe per ADR-055.
- TODO ADR-070 "Bright Data integration policy" — documentar SLA proveedor, presupuesto $5-150/mo per source, fallback strategy, PDPL compliance scrape ToS Amazon UAE (Q-NEW-S3 referencia).
- **Bloqueador legal**: Q-NEW-S3 firma de Champion + Legal MT obligatoria antes de habilitar la red real. Si no firmado al día 1 sprint, story queda en stand-by con stubs.

#### Archivos esperados
- `mt-pricing-backend/app/services/comparator/adapters/bright_data_amazon_ae.py`
- `mt-pricing-backend/app/services/comparator/adapters/bright_data_noon_ae.py`
- `mt-pricing-backend/app/services/comparator/adapters/__init__.py`
- `mt-pricing-backend/app/utils/circuit_breaker.py`
- `mt-pricing-backend/tests/services/comparator/adapters/` (mocked HTTP fixtures con `respx`)
- Tests: unit cada adapter + integration con respx mock + 1 E2E con sandbox Bright Data si Champion habilita.

#### DoD
- [ ] Coverage ≥ 80 % en `adapters/`.
- [ ] Circuit breaker probado con 5 fallos consecutivos.
- [ ] ADR-070 firmado.
- [ ] Q-NEW-S3 firma legal en repo (`docs/legal/Q-NEW-S3-amazon-uae-scraping.md`).
- [ ] Smoke real sobre 5 SKUs con red real (sandbox o prod minimal usage).
- [ ] Sentry instrumentation con context `source` + `query` + `result_count`.

#### SP: 8

---

### US-1A-09-04 — Adapters Playwright manufacturer (Pegler / Arco / Giacomini)

**Épica**: EP-1A-09 ([pipeline detail §4.1](mt-product-matching-pipeline-detail.md))
**Como** dev backend
**Quiero** adapters Playwright self-host que crawleen catálogos de fabricantes whitelist
**Para** sumar fuente de candidates "fabricante directo" gratis (USD 0 vs Bright Data) y subir cobertura.

#### Contexto
Pipeline detail §4.1 lista 5 fabricantes target Fase 1: Pegler-Yorkshire, Arco, Giacomini, Apollo Valves, Nibco. S4 implementa los 3 más estratégicos (Pegler + Arco + Giacomini = ~70% catálogo MT). Apollo y Nibco pueden esperar. Patrón hexagonal mismo que US-1A-09-03 — sólo cambia el adapter. Playwright headless sobre Hetzner box compartido (ADR-040 ya firmado).

#### Criterios de aceptación
1. **Dado** un SKU con `brand_canonical='Pegler'` y query `"brass ball valve 2 inch BSP"` **Cuando** llamo `PlaywrightPeglerFetcher.fetch(query)` **Entonces** sistema crawlea pegler-yorkshire.com search page, retorna lista `CandidateRaw` con `source="manufacturer:pegler"`.
2. **Dado** página de producto Pegler con specs estructuradas **Cuando** se parsea **Entonces** extrae `dn`, `pn`, `material`, `connection`, `part_number` con confianza > 80% (alta señal — listing oficial).
3. **Dado** Pegler website cambia HTML structure **Cuando** parser falla > 3 ejecuciones **Entonces** Sentry alert + breadcrumb con DOM snapshot + Slack `#mt-alerts` para ajuste manual del selector.
4. **Dado** los 3 fabricantes funcionando **Cuando** orchestrator ejecuta `fetch_all` **Entonces** retorna candidates de los 3 + Bright Data Amazon UAE + Noon UAE en paralelo asyncio.gather.
5. **Dado** un crawl con `cache_hit` (último < 24h) **Cuando** se invoca **Entonces** retorna desde cache (Redis key `playwright:pegler:{query_hash}`) sin lanzar browser headless.
6. **Dado** Playwright timeout (> 30s) **Cuando** ocurre **Entonces** circuit breaker incrementa, retry 1 vez, después rejecta candidate y registra en metrics.

#### Notas técnicas
- `app/services/comparator/adapters/playwright_pegler.py`, `playwright_arco.py`, `playwright_giacomini.py`.
- `app/services/comparator/adapters/_playwright_base.py` con clase abstracta + Browser pool (1 browser persistente compartido entre adapters, cleanup en shutdown).
- Cache Redis con TTL 24h (key `playwright:{source}:{query_hash}`).
- Selectors HTML por fabricante en `config/playwright_selectors.yaml` (editable sin redeploy).
- Sentry context tag `playwright_source`.
- TODO ADR-071 "Playwright self-host strategy" — documentar Browser pool sizing, memoria estimada, Hetzner GPU box compartido con SigLIP (S5).

#### Archivos esperados
- `mt-pricing-backend/app/services/comparator/adapters/_playwright_base.py`
- `mt-pricing-backend/app/services/comparator/adapters/playwright_pegler.py`
- `mt-pricing-backend/app/services/comparator/adapters/playwright_arco.py`
- `mt-pricing-backend/app/services/comparator/adapters/playwright_giacomini.py`
- `mt-pricing-backend/config/playwright_selectors.yaml`
- Tests: unit + integration con `playwright.mock` o fixtures HTML capturadas.

#### DoD
- [ ] Coverage ≥ 75 % (Playwright integration tests son frágiles, threshold relajado).
- [ ] Cache Redis verificado (TTL 24h).
- [ ] Selectors externalizados en YAML.
- [ ] ADR-071 firmado.
- [ ] Smoke real con browser headless en dev local Docker sobre 3 SKUs por fabricante.
- [ ] Browser pool no leaks (validado con `psutil` durante 100 fetch consecutivos).

#### SP: 5

---

### US-1A-09-05 — Channel mirror SP-API real Amazon UAE (reemplazo `amazon_sp_api_stub.py`)

**Épica**: EP-1A-09 ([sprint3-backlog §US-1A-09-02-S3](sprint3-backlog-refined.md))
**Como** dev backend
**Quiero** el adapter SP-API real Amazon Selling Partner que reemplace `amazon_sp_api_stub.py` de S3
**Para** que el channel mirror detecte drift real entre canonical (`products`) y live (Amazon UAE) — input clave para pricing engine en Fase 1b/2.

#### Contexto
**Bloqueado por credenciales SP-API de TI MT**. S3 entregó stub con datos canned. S4 reemplaza por SDK oficial `sp-api` (Python) o `python-amazon-sp-api`. Endpoints relevantes: `getCatalogItem`, `getInventorySummaries`, `getPricing`. Marketplace ID: `A2VIGQ35RCS4UG` (Amazon.ae). Auth: LWA (Login with Amazon) tokens + AWS IAM Role assumption. Cache estructurado en Postgres `channel_listings_cache` (migración 0018) con TTL configurable por endpoint (catálogo 6h, pricing 30 min, inventario 5 min).

#### Criterios de aceptación
1. **Dado** un SKU `MT-V-038` con `amazon_uae_asin='B07XYZ123'` mapeado **Cuando** llamo `GET /api/v1/channels/amazon_ae/MT-V-038/diff` **Entonces** sistema consulta SP-API real, retorna `{canonical:{...products...}, live:{title, price_aed, in_stock, last_updated}, diff:{...}, status:'in_sync'|'drift_detected'|'not_listed'}`.
2. **Dado** SP-API rate limit (429) **Cuando** ocurre **Entonces** sistema retry con exponential backoff respecting `Retry-After` header, max 3 intentos, después fallback a cache.
3. **Dado** cache hit (TTL no expirado) **Cuando** se consulta **Entonces** retorna desde `channel_listings_cache` sin llamar SP-API.
4. **Dado** SP-API auth falla (LWA token expired) **Cuando** ocurre **Entonces** sistema refresca token automáticamente y reintenta una vez.
5. **Dado** un job Celery `refresh_channel_listings_amazon_ae` corriendo **Cuando** itera sobre todos los SKUs con ASIN mapeado **Entonces** procesa < 10 min para 224 SKUs (con throttling SP-API), persiste en cache.
6. **Dado** un TI Integración **Cuando** llama `POST /api/v1/channels/amazon_ae/refresh-cache` **Entonces** dispara el job (single SKU o all), retorna `task_id`. RBAC `ti+`.
7. **Dado** un SKU sin ASIN mapeado **Cuando** se consulta diff **Entonces** retorna `status:'not_listed', live:null` (no falla — caso normal Fase 1).
8. **Dado** un drift detectado en precio (>2% delta vs canonical proposed) **Cuando** se persiste **Entonces** Sentry breadcrumb + opcional Slack notification (si flag `notify_drift=true`).

#### Notas técnicas
- `app/services/channels/amazon_ae/sp_api_client.py` (real implementation reemplazando stub).
- `app/services/channels/amazon_ae/auth.py` con LWA token refresh logic.
- `app/services/channels/amazon_ae/cache.py` con cache layer Postgres-backed.
- Migración Alembic 0018: tabla `channel_listings_cache` (`id`, `sku` FK, `channel_code`, `external_id` (asin/noon_id), `payload` JSONB, `cached_at`, `expires_at`, `endpoint` ENUM).
- `app/workers/refresh_channels.py` Celery task con throttling SP-API (max 1 req/s sustained).
- Env vars: `SP_API_REFRESH_TOKEN`, `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ROLE_ARN_SP_API`.
- TODO ADR-072 "SP-API integration Fase 1" — documentar marketplace ID, endpoints whitelist, rate limits, throttle policy, cost estimation.
- **Bloqueador**: TI MT debe proveer credenciales antes day 3 del sprint. Si no llegan, story degrada a "wire para inyección posterior" (-2 SP).

#### Archivos esperados
- `mt-pricing-backend/app/services/channels/amazon_ae/sp_api_client.py`
- `mt-pricing-backend/app/services/channels/amazon_ae/auth.py`
- `mt-pricing-backend/app/services/channels/amazon_ae/cache.py`
- `mt-pricing-backend/alembic/versions/0018_channel_listings_cache.py`
- `mt-pricing-backend/app/workers/refresh_channels.py`
- `mt-pricing-backend/app/db/models/channel_listing_cache.py`
- Tests: unit + integration con `respx` mock SP-API responses + 1 E2E con sandbox SP-API si Champion habilita.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Migración up/down testeada.
- [ ] Cache TTL verificado para 3 endpoint types.
- [ ] LWA token refresh probado con token expirado simulado.
- [ ] ADR-072 firmado.
- [ ] Smoke real sobre 3 SKUs con sandbox SP-API.
- [ ] Throttle policy documentada y verificada (no excede SP-API rate limits Amazon.ae oficiales).

#### SP: 5

---

### US-1A-09-06 — Isotonic calibrator + VLM judge Gemini 2.5 Flash (etapas 6-7 pipeline)

**Épica**: EP-1A-09 / EP-RND-01 ([pipeline detail §8 + §10](mt-product-matching-pipeline-detail.md))
**Como** dev R&D + backend
**Quiero** las etapas 6 (RRF + isotonic calibrator) y 7 (VLM judge audit-grade) reales conectadas al pipeline
**Para** que el comparador produzca `calibrated_confidence` real (no score crudo) y rationale auditable por SKU.

#### Contexto
S3 entregó pipeline foundation (etapas 1-3) con scoring G2 multi-dim crudo. S4 cierra el loop:
- **Etapa 6**: RRF (Reciprocal Rank Fusion) sobre rankings por dimensión + Isotonic Regression calibrator (sklearn) entrenado sobre dataset etiquetado de US-RND-01-03 (≥ 50 pares al kickoff S4, target 200 al final). Persistir `competitor_calibrators` con versión + métricas Brier + ECE.
- **Etapa 7**: VLM judge Gemini 2.5 Flash con prompt audit-grade documentado en pipeline detail §10. Output JSON estricto con `verdict / rationale / image_evidence / text_evidence / deal_breakers_observed / confidence_self_assessment`. Persiste en `match_decisions.judge_*` columns.

#### Criterios de aceptación
1. **Dado** los outputs G2 de S3 sobre dataset etiquetado **Cuando** entreno `IsotonicRegression(out_of_bounds='clip')` **Entonces** la curva de calibración mejora (ECE < 5%, Brier score reportado).
2. **Dado** un candidato con `raw_score=0.93` **Cuando** llamo `calibrate(0.93)` **Entonces** retorna `calibrated_confidence` (e.g. 0.87) que refleja "87% probabilidad real de match".
3. **Dado** un par SKU↔candidato en zona gris (calibrated 0.50-0.95) **Cuando** invoco `vlm_judge(sku, candidate, scores, ocr)` **Entonces** Gemini 2.5 Flash retorna JSON con todos los campos estructurados, rationale en español (UI locale operador).
4. **Dado** el VLM judge retorna `verdict='match', confidence_self_assessment=0.95` y calibrated >= 0.95 **Cuando** se procesa **Entonces** sistema marca `match_decisions.status='auto_match'`.
5. **Dado** VLM judge retorna `uncertain` **Cuando** se procesa **Entonces** sistema deriva a `human_queue` (UI Tinder en S5) con todo el reasoning persistido.
6. **Dado** un par auto-match **Cuando** se persiste **Entonces** `match_decisions` tiene `judge_rationale`, `judge_image_regions` JSONB, `judge_deal_breakers` array, `calibrator_version`, `judge_model='gemini-2.5-flash'`, `judge_invoked_at` timestamp.
7. **Dado** Gemini API timeout (> 30s) o quota hit **Cuando** ocurre **Entonces** circuit breaker, fallback: candidato queda `status='judge_pending'` con retry programado en Celery.
8. **Dado** una corrida sobre 50 pares etiquetados (eval set) **Cuando** se completa **Entonces** reporte de métricas: precision ≥ 90%, recall ≥ 80%, ECE < 5%. Reporte persistido en `docs/comparator/calibration-s4.md`.

#### Notas técnicas
- `app/services/comparator/calibrator.py` con `IsotonicCalibrator` (load model from `competitor_calibrators` row by version).
- `app/services/comparator/judge.py` con `GeminiJudge` invocando `google.generativeai` SDK + structured prompt template del pipeline detail §10.
- `app/services/comparator/rrf.py` con `reciprocal_rank_fusion(rankings, k=60)` función pura.
- Migración Alembic 0019: extiende `match_decisions` con columnas `judge_*`, `calibrated_confidence` NUMERIC(4,3), `calibrator_version` TEXT.
- Migración 0019b: tabla `competitor_calibrators` (id, version, brier_score, ece, training_size, fitted_at, model_artifact_path, active BOOL).
- Storage: modelo isotonic serializado en Supabase Storage `comparator/calibrators/v{n}.pkl`.
- Env vars: `GEMINI_API_KEY`, `GEMINI_MODEL='gemini-2.5-flash'`.
- TODO ADR-073 "VLM judge prompt design + cost ceiling" — documentar prompt template, output schema, cost estimation Gemini 2.5 Flash, fallback policy si quota hit.
- Coordinación con US-RND-01-04 (benchmark imagen) — si dataset etiquetado < 50 pares al kickoff S4, calibrator entrega con N=20 (degraded mode, ECE > 5% aceptado, alarm).

#### Archivos esperados
- `mt-pricing-backend/app/services/comparator/calibrator.py`
- `mt-pricing-backend/app/services/comparator/judge.py`
- `mt-pricing-backend/app/services/comparator/rrf.py`
- `mt-pricing-backend/alembic/versions/0019_extend_match_decisions_judge.py`
- `mt-pricing-backend/alembic/versions/0019b_create_competitor_calibrators.py`
- `mt-pricing-backend/app/db/models/competitor_calibrator.py`
- `mt-pricing-backend/scripts/train_calibrator.py` (CLI Champion)
- `docs/comparator/calibration-s4.md` (entregable de cierre).
- Tests: unit + integration + 1 E2E sobre 5 pares con Gemini real.

#### DoD
- [ ] Coverage ≥ 80 % en `calibrator.py`, `judge.py`, `rrf.py`.
- [ ] ECE < 5% reportado o aceptación explícita degraded mode con < 50 labels.
- [ ] Smoke real con Gemini sobre 5 pares.
- [ ] ADR-073 firmado.
- [ ] Cost dashboard: tracking Gemini API calls + cost estimado mensual reportado.
- [ ] `match_decisions` migration verificada con rollback.

#### SP: 8

---

### US-1A-06-04 — Importer datasheets PDF (`MTFT_*`/`MTCE_*`/`MTMAN_*`) → `product_datasheets`

**Épica**: EP-1A-06 ([epics-and-stories §793](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial / TI
**Quiero** asociar PDFs (técnicas, compliance, manuales) a SKUs por sufijo numérico de filename
**Para** que el cliente pueda descargar la ficha desde la app y el VLM judge pueda consultarla en KB.

#### Contexto
Defer S3 → S4. Reusa pipeline importer de S2/S3 (mismo wizard) con `type=datasheets`. Files vienen de carpeta `Documentos referencia de articulos/`. Naming convention: `MTFT_{sku_suffix}.pdf` (ficha técnica), `MTCE_{sku_suffix}.pdf` (compliance), `MTMAN_{sku_suffix}.pdf` (manual). Asociación N:M (un PDF puede cubrir varios SKUs si lista en el contenido). Storage Supabase `product-datasheets/` bucket (crear migración).

#### Criterios de aceptación
1. **Dado** un SKU `MT-V-5114` y un archivo `MTFT_5114.pdf` subido **Cuando** ejecuto importer modo preview **Entonces** sistema reporta `total=1, matched_skus=[MT-V-5114], orphan_files=[], orphan_skus=[]`.
2. **Dado** preview confirmado **Cuando** apply **Entonces** persiste archivo en `product-datasheets/MTFT_5114.pdf`, crea fila en `product_datasheets` con FK al SKU + `kind='ficha_tecnica'`, registra `audit_events`.
3. **Dado** una ficha que cubre varios SKUs (e.g. `MTFT_5114-5115-5116.pdf`) **Cuando** la asocio a la lista **Entonces** sistema crea N filas N:M en `product_datasheet_skus` sin duplicar el archivo en Storage.
4. **Dado** un SKU con ficha asociada **Cuando** consulto `GET /products/{sku}/datasheets` **Entonces** retorna lista con preview URL + signed URL TTL 24h.
5. **Dado** un PDF > 10 MB **Cuando** se sube **Entonces** retorna 422 `error.code='datasheet_too_large'`.
6. **Dado** filename mal formateado (e.g. `random.pdf` sin prefijo) **Cuando** se procesa **Entonces** queda en `orphan_files` con razón.
7. **Dado** un Comercial en `/products/{sku}` **Cuando** click tab "Documentos" **Entonces** ve lista de datasheets asociados con preview embebido (PDF.js) + botón descarga.

#### Notas técnicas
- Migración Alembic 0020: tablas `product_datasheets` (id, kind ENUM, storage_path, original_filename, file_size_bytes, uploaded_by, created_at) + `product_datasheet_skus` (datasheet_id FK, sku FK, PRIMARY KEY composite).
- Storage: bucket `product-datasheets` con RLS `comercial+` read, `ti+` write.
- Backend: `app/importers/datasheets_parser.py`, `datasheets_validator.py`. Reusa `importer_service` factory.
- Backend: `app/api/v1/datasheets.py` con CRUD endpoints + `GET /products/{sku}/datasheets`.
- Frontend: extender wizard `/imports/new?type=datasheets` + tab "Documentos" en SKU detail.
- Hooks indexación texto (US-1A-06-05) NO incluidos — defer Fase 1.5+ con feature flag off.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0020_create_product_datasheets.py`
- `mt-pricing-backend/app/db/models/product_datasheet.py`
- `mt-pricing-backend/app/importers/datasheets_parser.py`
- `mt-pricing-backend/app/api/v1/datasheets.py`
- `mt-pricing-frontend/app/(app)/products/[sku]/_components/datasheets-tab.tsx`
- `mt-pricing-frontend/app/(app)/imports/_components/datasheets-mapping-step.tsx`
- Tests: unit + integration + 1 E2E.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Bucket `product-datasheets` provisionado en Supabase con RLS.
- [ ] Smoke con 5 PDFs reales del directorio `Documentos referencia de articulos/`.
- [ ] OpenAPI actualizado.
- [ ] PDF preview UI funcionando con files > 1 MB.

#### SP: 5

---

### US-1A-07-02 — RLS finas `products`/`costs`/`prices`/`audit_events` (carry-over de S3)

**Épica**: EP-1A-07 ([epics-and-stories §877](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** RLS policies declarativas que enforcen RBAC en BD
**Para** defense in depth (auth en API + RLS en BD, NFR-07/11).

#### Contexto
**Carry-over de S3 (stretch goal no entregado)**. S3 cerró auth en API + RLS básicas (`authenticated` SELECT). S4 endurece: SELECT/INSERT/UPDATE/DELETE policies por rol específico (`comercial`, `gerente`, `ti`) sobre `products`, `costs`, `prices` (S4 nueva), `audit_events` (read-only para `gerente+`, append-only para sistema). Incluye también RLS sobre `match_decisions` y `channel_listings_cache` (entran en S4).

#### Criterios de aceptación
1. **Dado** un `comercial` autenticado **Cuando** intenta `INSERT INTO costs ... status='active'` **Entonces** RLS permite.
2. **Dado** un `comercial` **Cuando** intenta `INSERT INTO prices ... status='approved'` **Entonces** RLS deniega (sólo `gerente+` puede aprobar; comercial sólo `draft`).
3. **Dado** un `comercial` **Cuando** intenta `UPDATE audit_events SET ...` **Entonces** RLS deniega (append-only).
4. **Dado** un `ti` **Cuando** intenta `UPDATE products SET name_en = ...` **Entonces** RLS deniega (write reservado a `comercial+`).
5. **Dado** un `gerente` **Cuando** consulta `SELECT * FROM audit_events WHERE entity='products'` **Entonces** RLS permite y retorna eventos.
6. **Dado** un usuario sin auth **Cuando** intenta cualquier operación **Entonces** RLS deniega 0 filas (defense-in-depth).
7. **Dado** un `comercial` **Cuando** consulta `SELECT * FROM match_decisions` **Entonces** RLS permite (read-only para todos los roles autenticados).
8. **Dado** un `comercial` **Cuando** intenta `INSERT INTO match_decisions ...` **Entonces** RLS deniega (sólo system role / pipeline writes).

#### Notas técnicas
- Migración 0021: policies SQL declarativas en `infra/supabase/migrations/0021_rls_fine_grained.sql`.
- Helper PL/pgSQL `auth_user_has_role(role TEXT) RETURNS BOOL` que lee `public.users.role` desde `auth.uid()` (probablemente ya creada en S3 si llegó a entrar — verificar y reutilizar).
- Tests integration con testcontainers Postgres + Supabase migrations.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0021_rls_fine_grained.py`
- `infra/supabase/migrations/0021_rls_fine_grained.sql`
- Tests: integration con 4 roles (comercial, gerente, ti, anon) × 6 tablas (products, costs, prices, audit_events, match_decisions, channel_listings_cache) × 4 ops = 96 escenarios mínimos pero priorizar 24 críticos.

#### DoD
- [ ] 24 tests integration pasando.
- [ ] Coverage policies cubre al menos 1 deny y 1 allow por (role, tabla, op crítico).
- [ ] Documentación en `mt-security-compliance-design.md` actualizada.
- [ ] Smoke con queries directas como cada role en local.

#### SP: 3

---

### US-1A-07-03 — Triggers `audit_events` en costs / translations / fx_rates

**Épica**: EP-1A-07 ([epics-and-stories §893](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** triggers `BEFORE UPDATE/INSERT/DELETE` en `costs`, `product_translations`, `fx_rates`, `prices` que persistan `payload_before`, `payload_after`, `diff` automáticamente
**Para** auditabilidad VAT-compliant sin depender del código de servicio (defense-in-depth).

#### Contexto
S1/S2 ya cubrieron triggers en `products`, `suppliers`, `currencies` (verificar exec-report S2). S4 extiende a las tablas creadas/modificadas en S3-S4: `costs`, `product_translations` (con state machine S3), `fx_rates` (S3), `prices` (S4). Patrón `audit.log_event()` PL/pgSQL ya establecido. Critical: triggers AFTER, no BEFORE — para no ralentizar writes y para que `payload_after` refleje valores generados (e.g. `scheme_landed_aed`).

#### Criterios de aceptación
1. **Dado** un UPDATE en `costs.breakdown` **Cuando** se persiste **Entonces** trigger registra `audit_events(entity='costs', entity_id, payload_before, payload_after, diff, actor=auth.uid(), source='ui')`.
2. **Dado** un INSERT en `prices` con `status='draft'` **Cuando** se ejecuta **Entonces** trigger registra `audit_events(entity='prices', action='create', payload_after, actor)`.
3. **Dado** un transition en `product_translations.status` (e.g. draft → approved) **Cuando** se ejecuta **Entonces** trigger registra con `action='transition_translation'` y diff incluye old_status + new_status.
4. **Dado** un INSERT en `fx_rates` que dispara cierre del anterior (S3 trigger) **Cuando** se ejecuta **Entonces** se generan 2 audit events (uno por el INSERT nuevo, uno por el UPDATE close del anterior).
5. **Dado** un intento de UPDATE en `audit_events` **Cuando** se ejecuta **Entonces** falla (append-only constraint, BR-1a-12, NFR-34) — refuerza RLS de US-1A-07-02 con trigger `BEFORE UPDATE OR DELETE` que raises.
6. **Dado** una consulta `GET /api/v1/audit?entity=costs&entity_id={id}` **Cuando** la ejecuta un Gerente **Entonces** retorna histórico cronológico con diffs.
7. **Dado** una consulta como `comercial` **Cuando** ejecuta el endpoint **Entonces** RBAC retorna 403 (solo `gerente+`).

#### Notas técnicas
- Migración Alembic 0022: triggers + endpoint API.
- `infra/supabase/migrations/0022_audit_triggers_costs_translations_fx_prices.sql`.
- Reuse `audit.log_event(entity, entity_id, action, payload_before, payload_after, source)` ya establecida.
- `app/api/v1/audit.py` con `GET /audit` filtros (`entity`, `entity_id`, `from`, `to`, `actor`, paginated).
- Append-only: trigger `BEFORE UPDATE OR DELETE ON audit_events` raises `forbidden_audit_mutation`.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0022_audit_triggers_extended.py`
- `infra/supabase/migrations/0022_audit_triggers_extended.sql`
- `mt-pricing-backend/app/api/v1/audit.py`
- Tests: 8+ unit verificando cada tabla cubierta + append-only enforcement.

#### DoD
- [ ] Coverage ≥ 80 % en `app/api/v1/audit.py`.
- [ ] 8+ tests verificando trigger en cada tabla (costs, prices, translations, fx_rates).
- [ ] Append-only trigger probado con UPDATE/DELETE rejected.
- [ ] Smoke E2E: hacer UPDATE en costs vía UI → ver evento en `/audit`.
- [ ] Documentación actualizada en `mt-security-compliance-design.md`.

#### SP: 5

---

### US-1A-07-03-FE — UI tab Auditoría en SKU detail

**Épica**: EP-1A-07
**Como** Gerente / Comercial
**Quiero** ver el histórico de cambios de un SKU desde su ficha
**Para** entender qué cambió, cuándo y quién.

#### Contexto
Cierra el tab "Auditoría" disabled desde S2 (los otros 3 tabs ya activos al cierre S3). Consume `GET /api/v1/audit?entity_id=sku_id&entity=products,costs,product_translations,prices` filtrado al SKU. Patrón Pantalla 11 del UX (firma pendiente — ver §6 riesgos).

#### Criterios de aceptación
1. **Dado** un Gerente en `/products/MT-V-038` **Cuando** click tab Auditoría **Entonces** ve timeline cronológico inverso con cards `{actor, timestamp, entity, action, diff_summary}`.
2. **Dado** un evento con diff complejo **Cuando** click "Ver detalle" **Entonces** modal muestra `payload_before` vs `payload_after` con diff colorizado por campo.
3. **Dado** filtros disponibles (entity, action, fecha) **Cuando** Gerente filtra por `entity=costs` **Entonces** lista refresca.
4. **Dado** un Comercial **Cuando** abre tab **Entonces** ve la misma vista (read-only, sin acciones), RBAC sólo deniega export en US-1A-07-05.
5. **Dado** > 100 eventos en histórico **Cuando** se carga **Entonces** paginación virtual scroll renderiza < 200 ms.
6. **Dado** un evento `entity='prices'` con price aprobado **Cuando** se renderiza **Entonces** muestra badge color por status final + tooltip explicando.

#### Notas técnicas
- Frontend: `app/(app)/products/[sku]/_components/audit-tab.tsx` con virtual scroll + Shadcn Card + Modal.
- Frontend: `lib/api/audit.ts` typed fetcher.
- Frontend: `components/products/audit-event-card.tsx` + `components/products/audit-diff-modal.tsx`.
- i18n: namespace `catalog.audit.*`.
- TODO: confirmar UX wireframe Pantalla 11. Si no firmado al día 3, decisión "reusar timeline pattern de Tracking de propuestas" del UX existente.

#### Archivos esperados
- `mt-pricing-frontend/app/(app)/products/[sku]/_components/audit-tab.tsx`
- `mt-pricing-frontend/components/products/audit-event-card.tsx`
- `mt-pricing-frontend/components/products/audit-diff-modal.tsx`
- `mt-pricing-frontend/lib/api/audit.ts`
- Tests: unit + integration + 1 E2E.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] UX firmada Pantalla 11 (o decisión reuso explícita).
- [ ] Smoke E2E con 20 eventos generados de US-1A-07-03 trigger.
- [ ] i18n keys ES/EN.
- [ ] Performance virtual scroll < 200 ms para 500 eventos.

#### SP: 3

---

### US-RND-01-11 — GraphRAG Fase 3 scaffold (`ComparatorService` adapter + `Neo4jGraphRepository` stub)

**Épica**: EP-RND-01 ([epics-and-stories §1745](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev R&D
**Quiero** abstracciones backend `ComparatorService` con adapters Rag/Hybrid/FullGraphRag y `GraphRepository` con backends Postgres/Neo4j
**Para** introducir KG Fase 2+ sin refactor del comparador.

#### Contexto
**R&D track Fase 2 scaffold**. Pipeline detail menciona ADR-038 (rediseño completo). Aún en Fase 1 con RagOnlyComparatorAdapter. S4 introduce las abstracciones para que en Fase 2 (post-cutover Fase 1) se pueda swapear a Hybrid (RAG + KG) o FullGraphRag con cambio de configuración, sin refactor del pipeline matching. `Neo4jGraphRepository` stub: implementa interfaz pero falla con `NotImplementedError("Fase 2+")` — sólo el wire.

#### Criterios de aceptación
1. **Dado** la interfaz `ComparatorService` (Protocol) **Cuando** consulto API interna **Entonces** existe con 3 adapters: `RagOnlyComparatorAdapter` (activo Fase 1, usa pipeline S3+S4), `HybridComparatorAdapter` (stub raises), `FullGraphRagComparatorAdapter` (stub raises).
2. **Dado** la interfaz `GraphRepository` **Cuando** consulto **Entonces** existe con `PostgresGraphRepository` activo (tabla `product_relations` con triplets básicos: e.g. `MT-V-038 IS_A ball_valve`, `MT-V-038 HAS_MATERIAL brass_CW617N`) y `Neo4jGraphRepository` stub.
3. **Dado** la configuración `COMPARATOR_ADAPTER='rag_only'` **Cuando** arranca app **Entonces** factory inyecta el RagOnly adapter; los endpoints `/match/*` siguen funcionando idéntico.
4. **Dado** la configuración `COMPARATOR_ADAPTER='hybrid'` **Cuando** arranca **Entonces** raise startup error con mensaje "Hybrid adapter not implemented in Fase 1" (defensive).
5. **Dado** un SKU **Cuando** llamo `comparator_service.find_candidates(sku)` **Entonces** retorna lista candidates igual que pipeline directo (sin cambio funcional).
6. **Dado** la BD con tabla `product_relations` **Cuando** ejecuto `PostgresGraphRepository.get_neighbors('MT-V-038', relation='HAS_MATERIAL')` **Entonces** retorna `[brass_CW617N]`.

#### Notas técnicas
- `app/services/comparator/service.py` con `ComparatorService` Protocol + factory.
- `app/services/comparator/adapters/rag_only.py` (wraps pipeline S3+S4 actual).
- `app/services/comparator/adapters/hybrid_stub.py`, `full_graph_rag_stub.py` (raise NotImplementedError).
- `app/services/graph/__init__.py`, `repository.py` (Protocol), `postgres_repository.py` (impl), `neo4j_stub.py`.
- Migración Alembic 0023: tabla `product_relations` (subject, predicate, object, source, confidence).
- TODO ADR-074 "GraphRAG architecture Fase 1 → 2 → 3 evolution" — documentar ADR-038 alignment, swap policy, KG schema.

#### Archivos esperados
- `mt-pricing-backend/app/services/comparator/service.py`
- `mt-pricing-backend/app/services/comparator/adapters/{rag_only.py, hybrid_stub.py, full_graph_rag_stub.py}`
- `mt-pricing-backend/app/services/graph/{__init__.py, repository.py, postgres_repository.py, neo4j_stub.py}`
- `mt-pricing-backend/alembic/versions/0023_create_product_relations.py`
- `mt-pricing-backend/app/db/models/product_relation.py`
- Tests: unit factory + adapters + repository + 1 integration.

#### DoD
- [ ] Coverage ≥ 80 % en `service.py`, `adapters/*.py`, `graph/*.py`.
- [ ] Endpoints `/match/*` pasan tests existentes sin cambio (retrocompat).
- [ ] ADR-074 firmado.
- [ ] Migración 0023 con seed de 50 triplets básicos derivados de PIM (smoke).

#### SP: 3

---

## 5. Plan de ejecución multi-agente

Patrón S1/S2/S3 demostró que 4-5 agentes paralelos con dominios disjuntos sostienen velocity de ~50 SP en una iteración. Para S4 mantenemos 5 agentes (uno dedicado a R&D + gap-fix).

### Agente A — Backend Data + Pricing core + RLS + Audit (~19 SP)

**Stories**: US-1B-01-02 (3), US-1B-01-03 (8), US-1A-07-02 (3), US-1A-07-03 (5).

**Paths exclusivos**:
- `mt-pricing-backend/alembic/versions/0017_*`, `0021_*`, `0022_*`
- `mt-pricing-backend/app/db/models/{price.py}`
- `mt-pricing-backend/app/services/pricing/**` (toda la carpeta nueva)
- `mt-pricing-backend/app/schemas/pricing.py`
- `mt-pricing-backend/app/api/v1/audit.py`
- `infra/supabase/migrations/{0017_*, 0021_*, 0022_*}.sql`

**No toca**: comparator/**, channels/**, frontend, importers.

### Agente B — Backend API + Importers + Datasheets (~10 SP)

**Stories**: US-1B-01-04 (5), US-1A-06-04 (5).

**Paths exclusivos**:
- `mt-pricing-backend/app/api/v1/{prices.py, datasheets.py}`
- `mt-pricing-backend/app/services/pricing/recalc_service.py`
- `mt-pricing-backend/app/workers/{pricing_recalc.py}`
- `mt-pricing-backend/app/importers/{datasheets_*.py}`
- `mt-pricing-backend/alembic/versions/{0020_*}`
- `mt-pricing-backend/app/db/models/{product_datasheet.py}`

**No toca**: comparator/, channels/, frontend (excepto integración OpenAPI).

### Agente C — Comparator real adapters + Channel mirror real (~26 SP)

**Stories**: US-1A-09-03 (8), US-1A-09-04 (5), US-1A-09-05 (5), US-1A-09-06 (8).

**Paths exclusivos**:
- `mt-pricing-backend/app/services/comparator/adapters/**` (carpeta nueva con bright_data + playwright + calibrator + judge)
- `mt-pricing-backend/app/services/comparator/{calibrator.py, judge.py, rrf.py}`
- `mt-pricing-backend/app/services/channels/amazon_ae/{sp_api_client.py, auth.py, cache.py}` (reemplazo del stub)
- `mt-pricing-backend/app/workers/refresh_channels.py`
- `mt-pricing-backend/app/utils/circuit_breaker.py`
- `mt-pricing-backend/alembic/versions/{0018_*, 0019_*, 0019b_*}`
- `mt-pricing-backend/app/db/models/{channel_listing_cache.py, competitor_calibrator.py}`
- `mt-pricing-backend/config/playwright_selectors.yaml`
- `mt-pricing-backend/scripts/train_calibrator.py`

**No toca**: pricing/, frontend, importers, datasheets.

### Agente D — Frontend (Pricing UI + Auditoría tab + Datasheets tab) (~13 SP)

**Stories**: US-1B-01-06 (5), US-1A-07-03-FE (3), US-1A-06-04 frontend parte (~3 SP partial), US-1A-09-* OpenAPI integrations.

**Paths exclusivos**:
- `mt-pricing-frontend/app/(app)/pricing/recalculate/**`
- `mt-pricing-frontend/app/(app)/products/[sku]/_components/{audit-tab.tsx, datasheets-tab.tsx}`
- `mt-pricing-frontend/app/(app)/imports/_components/datasheets-mapping-step.tsx`
- `mt-pricing-frontend/components/{pricing/, products/audit-event-card.tsx, products/audit-diff-modal.tsx}`
- `mt-pricing-frontend/lib/api/{pricing.ts, audit.ts, datasheets.ts}`
- `mt-pricing-frontend/lib/hooks/use-poll-progress.ts`
- `mt-pricing-frontend/messages/{es,en}/*.json` (namespaces nuevos: `pricing.recalculate.*`, `catalog.audit.*`, `catalog.datasheets.*`)

**No toca**: backend, comparator adapters (no UI directa en S4 — UI Tinder es S5).

### Agente E — R&D + Gap-fix backend post-implementación (~3 SP + gap fix)

**Stories**: US-RND-01-11 (3 SP) + role gap-fix (post-merge).

**Paths exclusivos**:
- `mt-pricing-backend/app/services/comparator/{service.py}` y `adapters/{rag_only.py, hybrid_stub.py, full_graph_rag_stub.py}` (NB: `service.py` y `adapters/` carpeta — Agente C trabaja en bright_data/playwright dentro de `adapters/`, Agente E sólo añade los 3 archivos nuevos sin tocar los de C — coordinar via subdir o file-level lock).
- `mt-pricing-backend/app/services/graph/**` (carpeta nueva exclusiva)
- `mt-pricing-backend/alembic/versions/0023_*`
- `mt-pricing-backend/app/db/models/product_relation.py`

Patrón S2/S3: corre tests en master integrado, detecta gaps tipo 4xx/5xx por inconsistencias de schemas (e.g. `prices` ↔ pricing engine mismatch), fixes secundarios, persiste deuda técnica si Agente C se atasca con Q-NEW-S3 o creds SP-API.

### Conflictos previstos (mitigación)

- `mt-pricing-backend/app/services/comparator/adapters/__init__.py`: Agentes C y E ambos exportan adapters. **Solución**: subdivisión de subcarpetas — C en `adapters/bright_data/`, `adapters/playwright/`, E en `adapters/comparator_service/`. `__init__.py` reexporta todo, Agente E hace merge final.
- `mt-pricing-backend/app/api/v1/products.py`: lo modifican Agente B (añade `GET /products/{sku}/datasheets`) y Agente D (consume tab Auditoría). **Solución**: B añade endpoint, D solo consume; conflict cero.
- `mt-pricing-backend/openapi/openapi.yaml`: 4 agentes añaden secciones. **Solución**: cada agente edita YAML en path tag distintivo (`/prices`, `/match`, `/channels`, `/datasheets`, `/audit`) + Agente E consolida.
- `messages/es/common.json`: D añade keys. **Solución**: namespaces separados (`pricing.recalculate.*`, `catalog.audit.*`, `catalog.datasheets.*`) → 0 conflicto.
- Migration numbering: A usa 0017/0021/0022, B usa 0020, C usa 0018/0019/0019b, E usa 0023. **Solución**: lock de número via PR título + Agente E verifica orden.

## 6. Riesgos y bloqueos

| ID | Riesgo | Severidad | Probabilidad | Mitigación |
|----|--------|-----------|--------------|------------|
| R-S4-01 | **Q-NEW-S3 legal scraping Amazon UAE / Noon UAE** sigue abierta — bloqueante para US-1A-09-03 con red real | Crítica | Alta | Champion + Legal MT firma antes day 1 sprint. Si no firmado, US-1A-09-03 degrada a "wire infraestructural sin red" (-3 SP) y stubs S3 siguen activos. Documento `docs/legal/Q-NEW-S3-amazon-uae-scraping.md` requerido pre-kickoff. |
| R-S4-02 | **Q-09 image rights MT España** sigue abierto — afecta mirror real de candidates | Alta | Alta | Mirror local sólo se activa si Q-09 firmado. Sin firma, candidates no se mirrored (ADR-033 + FR-IMG-01); pipeline funciona pero auditabilidad de imágenes degradada. (R-044 register) |
| R-S4-03 | **Credenciales SP-API + AWS Role** no entregados por TI MT — bloquea US-1A-09-05 channel mirror real | Alta | Media | Champion debe iniciar trámite ya en S3 cierre. Si no llegan day 3 S4, story degrada a "wire para inyección posterior" (-2 SP) y stub S3 sigue activo. (R-S3-04 carry-over) |
| R-S4-04 | **ADR-055 SSRF policy sigue draft** desde S2 (carry-over a S3, posible carry-over a S4) | Media | Media | Arquitecto firma día 1 S4 antes de habilitar Bright Data adapters reales. Bloquea US-1A-09-03 hot-path mirror si no firmado. |
| R-S4-05 | **Golden numbers v5.1 (US-1B-01-01)** no firmados por Paula — bloquea US-1B-01-03 paridad | Crítica | Media | Pre-kickoff S4: Paula firma `tests/golden/v51_outputs.json` como representativo. Si discrepancias > 1% sobre 30 SKUs, opción rewrite (Q-10 reabre) — riesgo cascada de re-estimación 8 SP → 13 SP. |
| R-S4-06 | **Dataset etiquetado < 50 pares** al kickoff S4 → calibrator entrega degraded mode | Alta | Media | US-RND-01-03 cierra al kickoff S4 con 50 labels; si no, calibrator con N=20 (ECE > 5% aceptado, alarm). Champion responsable. |
| R-S4-07 | **Bright Data quota / cost burst** descontrolado en pruebas → presupuesto > $150/mo | Media | Media | Hard cap mensual configurado en cuenta Bright Data ($150). Sentry alert al 80%. Champion confirma presupuesto pre-kickoff. (R-009 register) |
| R-S4-08 | **Gemini 2.5 Flash quota / cost** desbordado por ejecuciones repetitivas | Media | Media | Hard cap mensual + cache invocaciones por hash(sku, candidate, scores) con TTL 7 días. ADR-073 incluye cost ceiling. |
| R-S4-09 | **UX firmas pendientes** Pantalla 6 (Recálculo) y Pantalla 11 (Auditoría tab) no firmadas | Media | Media | psierra firma día 3 o decisión "reusar patrón Pantalla 5 stepper / timeline existente". Bloquea US-1B-01-06 + US-1A-07-03-FE a 70% entrega. |
| R-S4-10 | **Capacidad real < 30 SP** si TI Integración no FTE | Alta | Media | Ver §3 priorización: bajar US-RND-01-11 (-3) + US-1A-07-03-FE (-3) + US-1A-09-04 (-5) → 24 SP core. |
| R-S4-11 | **`prices` state machine + workflow aprobación** parcial S4 (solo state machine, no aprobación). Si pricing engine entrega propuestas pero no se pueden aprobar manualmente, demo incompleta | Media | Alta | **Decisión S4**: state machine declarada en S4 (US-1B-01-02) pero workflow `auto_approved` vs `pending_review` con triggers + endpoints `approve`/`reject` se quedan a S5 (US-1B-02-* serie). En S4 las propuestas nacen `draft` y se quedan ahí; demo S4 muestra "calculadora" no "aprobador". |
| R-S4-12 | **Conflicto OpenAPI merge** entre Agentes A/B/C/D/E | Baja | Alta | Agente E como merger final con responsabilidad explícita. Cada agente edita YAML con tag distintivo. |
| R-S4-13 | **Playwright fragility** (sites change HTML) — selectors break frecuentemente post-deploy | Media | Alta | Selectors externalizados en `config/playwright_selectors.yaml` (editable sin redeploy). Sentry alert con DOM snapshot. Owner: Agente C. |
| R-S4-14 | **PDPL compliance scrape ToS Amazon UAE** — si Legal MT determina no permitido, bloquea Fase 2/3 storefront | Crítica | Baja | Q-NEW-S3 firma legal explícita. Si no firmado, defer comparador a Fase 1.5 (R-037 register). |

### Decisiones humanas pendientes (kickoff S4)

1. **Q-NEW-S3 firma legal** — owner Champion + Legal MT, deadline pre-kickoff S4.
2. **ADR-055 firma** (carry-over S2 → S3 → S4) — owner Arquitecto, deadline day 1.
3. **Q-09 image rights MT España** — owner Sponsor MT + legal.
4. **Credenciales SP-API + AWS Role** — owner TI MT, deadline day 3.
5. **Golden numbers v5.1 firma Paula** — owner Paula, deadline pre-kickoff.
6. **UX firma Pantalla 6 + Pantalla 11** — owner psierra.
7. **Hard cap presupuesto Bright Data + Gemini** — owner Champion.
8. **`manual_locked_fields` UI marking → confirmar S4 no incluido** — confirmar con arquitecto.

## 7. Métricas a trackear durante el sprint

- **Velocity real** (SP done) vs comprometido (35 SP).
- **Burn-down chart** diario; alarma si día 5 < 50 % done.
- **Pricing engine paridad**: 30/30 golden numbers passing al cierre. Si < 30, bloquea cutover Fase 1b.
- **`prices` populated**: target ≥ 200 propuestas drafted al cierre S4 sobre PIM real.
- **Comparator real candidates**: target ≥ 80 % SKUs con ≥ 1 candidato real (Amazon UAE + Noon UAE + manufacturer).
- **Calibrator ECE**: < 5 % (target NFR-CMP) o degraded mode firmado.
- **VLM judge cost**: tracking en cost dashboard, alarma 80 % cap.
- **Match decisions auto_match rate**: target ≥ 30 % (pares que pasan threshold ≥ 0.95) sobre eval set 50 pares.
- **Audit events generated**: target ≥ 500 nuevos (de costs + prices + translations).
- **Coverage delta**: ≥ 80 % en código nuevo.
- **Sprint goal viability**: cada miércoles, demo informal del flujo (FX change → recálculo → ver propuestas → match dry-run real → ver judge rationale).

## 8. Sprint 5 preview (alto nivel)

Stories candidatas (con racional):

| Story | SP | Racional |
|-------|----|----------|
| US-1B-02-01 (`PriceStateMachine` enforcement servicio + DB) | 5 | Cierra workflow aprobación |
| US-1B-02-02 (`exception_rules` versionado + UI) | 5 | Configurable por Gerente |
| US-1B-02-03 (auto_approved vs pending_review triggers) | 5 | Lógica delta margen + FX swing |
| US-1B-02-04 (POST /prices/approve/reject) | 3 | Workflow individual |
| US-1B-02-05 (POST /prices/bulk-approve) | 3 | Workflow lote |
| US-RND-01-10 (UI Tinder validación humana) | 13 | UI matching humano permanente |
| US-RND-01-09 (reverse image search hooks behind flag) | 5 | Fallback opcional |
| US-1A-07-04 (i18n UI selector) | 3 | Cierre RBAC |
| US-1A-07-05 (export CSV firmado FTA) | 5 | VAT compliance entregable |
| Carry-over S4 (cualquiera defer) | 0-8 | Plan B |

**Total candidatos S5**: ~50 SP (aplicar selección a 32-40 SP realistas).

**S5 MUST**: workflow aprobación completo (US-1B-02-01..05) + UI Tinder humana (US-RND-01-10) — primer demo end-to-end del programa con Comercial proponiendo + Gerente aprobando + matcher humano validando.

---

## Apéndice A — Mapeo de stories del doc fuente vs S4

| Doc fuente (epics-and-stories v1.1) | Sprint asignado original | S4 backlog refinado | Cambio |
|-------------------------------------|--------------------------|---------------------|--------|
| US-1B-01-02 (prices schema state machine) | S4 | US-1B-01-02 (S4) | Sin cambios |
| US-1B-01-03 (PricingEngine port v5.1) | S4 | US-1B-01-03 (S4) | Sin cambios |
| US-1B-01-04 (POST /prices/recalculate) | S4 | US-1B-01-04 (S4) | Sin cambios |
| US-1B-01-05 (Simulación what-if) | S4 | DEFER S5 | Capacity — pricing engine + matching real prioritarios |
| US-1B-01-06 (UI Disparar recálculo) | S4 | US-1B-01-06 (S4) | Sin cambios |
| US-1A-06-04 (Importer datasheets PDF) | S3 | US-1A-06-04 (S4) | Slip por capacity S3 (priorizó costs + matching foundation) |
| US-1A-06-05 (Hooks indexación texto fichas) | S3 | DEFER Fase 1.5 | Feature flag off, no bloquea Fase 1 |
| US-1A-07-02 (RLS finas) | S3 | US-1A-07-02 (S4) | Carry-over de S3 (stretch goal no entregado) |
| US-1A-07-03 (Audit triggers) | S3 | US-1A-07-03 (S4) | Slip por capacity S3 (priorizó costs schema) |
| US-1A-07-04 (i18n UI selector) | S3 | DEFER S5 | Capacity |
| US-1A-07-05 (Export CSV firmado FTA) | S3 | DEFER S5 | Capacity — VAT compliance no es gate Fase 1b |
| US-1A-07-06 (Dashboard SKUs atención) | S3 | DEFER S5+ | Stretch S3+S4 sin asignar |
| US-1A-08-01..05 (Scheduler editable + UI Jobs) | S3-S4 | DEFER S5 | EP-1A-08 entera defer post Fase 1b cutover |
| US-RND-01-06 (Scoring multi-dim deal breakers) | S3-S4 | EFECTIVAMENTE COMPLETADO en S3 (US-1A-09-01-S3) + S4 (US-1A-09-06) | Re-mapping a stories operativas |
| US-RND-01-07 (Calibración) | S4-S5 | US-1A-09-06 parte calibrator (S4) | Adelantado a S4 |
| US-RND-01-08 (VLM judge) | S4-S5 | US-1A-09-06 parte judge (S4) | Adelantado a S4 |
| US-RND-01-11 (GraphRAG hooks) | S5-S6 | US-RND-01-11 (S4) | Adelantado — scaffold low-cost |
| **NUEVA** US-1A-09-03 | — | Adapters reales Bright Data | Reemplazo stubs S3 |
| **NUEVA** US-1A-09-04 | — | Adapters Playwright manufacturer | Nueva fuente Fase 1 |
| **NUEVA** US-1A-09-05 | — | Channel mirror SP-API real | Reemplazo stub S3 |
| **NUEVA** US-1A-07-03-FE | — | UI tab Auditoría | Frontend complementing US-1A-07-03 |

## Apéndice B — TODOs / cosas dudadas

1. **EP-1A-09 (Comparador) formal en epics-and-stories doc**: en S3 backlog ya se anotó como TODO. Acción S4 día 1: PR a `epics-and-stories-mt-pricing-mdm-phase1.md` para añadir EP-1A-09 con las 6+ stories que ya entran S3-S5.

2. **`PricingEngine` port-vs-rewrite final**: si Q-10 firmó "port" en S0, US-1B-01-03 va con 8 SP. Si reabre por golden numbers discrepantes, escalation a 13 SP. Confirmar con Paula pre-kickoff.

3. **Bright Data dataset_ids específicos Amazon UAE / Noon UAE**: Champion confirma con vendor el `dataset_id` correcto (varía por marketplace). TODO documentar en ADR-070.

4. **Gemini 2.5 Flash availability en EU/UAE region**: confirmar con Google Cloud que el modelo está disponible en `eu-west` o `me-central1` (PDPL compliance). Si no, fallback a `us-central1` con DPA + scrubbing.

5. **`competitor_calibrators.model_artifact_path`**: storage Supabase `comparator/calibrators/v{n}.pkl` → confirmar bucket existe + RLS `service_role` write only.

6. **`product_relations` seed inicial 50 triplets**: derivar de PIM (e.g. todo SKU → `IS_A {family}` + `HAS_MATERIAL {material}`). Script `scripts/seed_product_relations.py` corre post-migration 0023.

7. **UX firma Pantalla 6 (Recálculo) + Pantalla 11 (Auditoría tab)**: si sigue draft al día 3 del sprint, decidir reuso de patrón existente (Pantalla 5 stepper + timeline tracking propuestas).

8. **`manual_locked_fields` UI marking — defer S5 explícito**: confirmar con arquitecto que sigue defer (sin owner aún en backlog).

9. **Playwright Browser pool sizing en Hetzner**: Browser pool comparte box con SigLIP (S5 GPU box). En S4 sólo Playwright corre — single browser persistent. En S5 deberá coexistir. Confirmar memoria estimada (~500MB browser + ~3GB SigLIP).

10. **Bright Data web scraper API ToS Amazon UAE**: Q-NEW-S3 firma. Documentar en ADR-070 si Bright Data afirma que respeta ToS Amazon (o si MT acepta el riesgo).

11. **VLM judge fallback strategy si Gemini quota hit**: opciones (a) cache 7 días + raise stale-while-revalidate, (b) downgrade a Claude Haiku como fallback (Anthropic SDK), (c) skip judge y marcar `judge_pending`. Decisión: (a) + (c). Confirmar en ADR-073.

12. **Cost dashboard real-time** para Bright Data + Gemini + SP-API: instrumentar en S4 con OpenTelemetry → Better Stack ya configurado en S2/S3. Owner: Agente E gap-fix.

13. **Pipeline version bump**: `S3-foundation-v1` → `S4-real-adapters-v1` cuando US-1A-09-03 + US-1A-09-04 + US-1A-09-06 mergean. Documentar en `match_decisions.pipeline_version` y reporte.

14. **`prices` channel_code y scheme_code FK**: confirmar tablas `channels` y `schemes` pobladas correctamente (vienen de S0 según epics §1083). Si no seed completo, US-1B-01-02 falla por FK.

15. **Demo S4 script**: importer cost real → trigger US-1B-01-04 sobre 1 SKU → ver `prices` row en BD → match dry-run sobre el SKU con adapters reales → VLM judge devuelve rationale → ver en `match_decisions`. End-to-end visible al cierre miércoles semana 2.
