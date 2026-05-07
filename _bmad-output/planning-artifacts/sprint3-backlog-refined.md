---
title: "Sprint 3 — Backlog refinado"
status: "draft"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
sprint: 3
capacity_target_sp: 35
sprint_goal: "Cerrar el motor de costes (FX versionado + costs CRUD + tab UI) y arrancar el pipeline de matching de competidores (etapas 1-3 con SP-API stub) — Fase 1a empieza a entregar pricing-readiness real."
related:
  - "epics-and-stories-mt-pricing-mdm-phase1.md"
  - "sprint2-backlog-refined.md"
  - "../implementation-artifacts/sprint2-execution-report.md"
  - "mt-product-matching-pipeline-detail.md"
  - "architecture-mt-pricing-mdm-phase1.md"
  - "prd-mt-pricing-mdm-phase1.md"
  - "ux-mockups-mt-pricing-mdm-phase1.md"
  - "risk-register-consolidado.md"
  - "adr/ADR-055-ssrf-policy-image-probe.md"
---

# Sprint 3 — Backlog refinado — MT Middle East MDM + Pricing Fase 1a

## 1. Resumen ejecutivo

Sprint 3 cierra **el motor de costes** (EP-1A-04 + EP-1A-05) e introduce los cimientos del **comparador de competidores** (etapas 1-3 del pipeline detallado). Tras S2 dejamos el PIM real cargado (5085 rows), suppliers CRUD, importer wizard, bucket `product-images` con probe+mirror y filtros backend listos. S3 transforma esa base en algo que ya produce **costo unitario en AED por SKU × esquema** y empieza a recolectar datos canónicos de Amazon UAE para Fase 2.

**Incluye**: FX engine versionado (`currencies` admin + `fx_rates` con cierre auto + `POST /fx-rates` admin UI), `costs` schema con FX as-of trigger + endpoint POST y UI tab Costes con breakdown editor, importers de costos y compatibilidades de materiales, translations approval workflow con state machine + audit, fundamentos del matching pipeline (Query Builder + Multi-Source Fetcher con stubs + Scoring G1 hard-rules / G2 multi-dim), channel mirror Amazon UAE stub (canonical vs live diff con fixtures), wire UI de filtros avanzados `dn`/`pn`/`material`, y RLS finas opcionales.

**No incluye** (defer S4+): UI tab Auditoría (espera US-1A-07-03 trigger pulido), importer de fichas técnicas PDF (US-1A-06-04 → S4), GraphRAG Fase 3 del pipeline, calibrador isotonic + VLM judge real (etapas 6-8 — stubs en S3, real en S4), reverse image search (TinEye/SerpAPI). **Gates de Fase 1a cumplidos al cerrar S3**: PIM operable, costos por SKU × esquema, FX as-of inmutable, suppliers + materials reference, audit append-only — el pricing engine de Fase 1b ya tiene todos sus inputs.

**Dependencias críticas**: ADR-055 SSRF (firmado para activar mirror sobre canales nuevos), Q-09 image rights (sigue abierto), legal scraping Amazon UAE (Q-NEW-S3, ver §5), `manual_locked_fields` UI marking (defer a S4 explícito), SP-API credentials para Amazon UAE (sólo stub con datos canned en S3 — credenciales reales son pre-S4).

## 2. Capacidad asumida

| Concepto | Valor |
|----------|-------|
| Devs FTE | 2-3 + TI Integración part-time |
| Velocity asumida | 32-40 SP/sprint humano (modo multi-agente puede absorber 50+ como en S1/S2) |
| Sprint length | 2 semanas (10 días lab.) |
| Reservas | 20 % buffer + 10 % refinement matching pipeline (territorio nuevo) |
| **Capacidad target S3** | **35 SP** |
| Carry-over de S2 | 0 SP (todas las stories S2 cerradas según execution-report §1) |

Si la capacidad real cae a 28-30 SP, aplicar §6 (stories candidatas a S4): bajar US-1A-07-02 (RLS finas) + US-1A-06-03 (importer materials) primero, manteniendo el bloque costs+FX+matching foundation intacto.

## 3. Tabla maestra de stories

| ID | Título | Épica | SP | Prioridad | Dominio | Agente sugerido | Depende de |
|----|--------|-------|----|-----------| --------|------------------|------------|
| US-1A-05-01-S3 | `currencies` admin UI + RBAC + audit (completar seed S2) | EP-1A-05 | 2 | P1 | backend+frontend | A | US-1A-03-01 (S2) |
| US-1A-05-02 | `fx_rates` con cierre auto `effective_to` + retroactive guard | EP-1A-05 | 5 | P0 | backend (data) | A | US-1A-05-01-S3 |
| US-1A-05-03 | `POST /fx-rates` + UI consola TI | EP-1A-05 | 3 | P1 | backend+frontend | A/D | US-1A-05-02 |
| US-1A-04-02 | `costs` schema con FX as-of stamping vía trigger | EP-1A-04 | 5 | P0 | backend (data) | A | US-1A-05-02, US-1A-03-02 (S2) |
| US-1A-04-03 | `POST /costs` con breakdown desglosado + scheme_landed_aed | EP-1A-04 | 5 | P0 | backend (api) | B | US-1A-04-02, US-1A-04-01 (S2) |
| US-1A-04-04 | UI tab "Costes" con tabla por esquema y breakdown editor | EP-1A-04 | 5 | P1 | frontend | D | US-1A-04-03 |
| US-1A-06-02 | Importer batch costos (Excel) con preview + apply | EP-1A-06 | 5 | P1 | backend+frontend | B/D | US-1A-04-03, US-1A-06-01 (S2) |
| US-1A-06-03 | Importer compatibilidades materiales (657 filas) | EP-1A-06 | 3 | P2 | backend | B | US-1A-02-01 (S1) |
| US-1A-02-05 | Translations approval workflow (state machine + audit) | EP-1A-02 | 5 | P1 | backend+frontend | C/D | US-1A-02-01 (S1), US-1A-07-03 (parcial) |
| US-1A-09-01-S3 | Matching pipeline foundation (Query Builder + Fetcher stubs + Scoring G1/G2) | EP-1A-09 (nueva) | 8 | P0 | backend (data + workers) | C | US-1A-02-01 (S1), US-1A-06-03 |
| US-1A-09-02-S3 | Channel mirror Amazon UAE stub (SP-API canonical vs live diff con datos canned) | EP-1A-09 (nueva) | 3 | P1 | backend (data) | C | US-1A-09-01-S3 |
| US-1A-02-09-FE | Wire UI filtros avanzados `dn`/`pn`/`material` (frontend completing S2 backend) | EP-1A-02 | 2 | P2 | frontend | D | US-1A-02-09 (S2) |
| US-1A-07-02 | RLS finas `products`/`costs`/`prices`/`audit_events` (si capacity) | EP-1A-07 | 3 | P3 | backend (data) | A | US-1A-07-01 (S1), US-1A-04-02 |
| **TOTAL** |  |  | **54 SP capacidad / 35 SP comprometidos** |  |  |  |  |

> **Comprometidos S3 (35 SP)**: US-1A-05-01-S3 (2) + US-1A-05-02 (5) + US-1A-05-03 (3) + US-1A-04-02 (5) + US-1A-04-03 (5) + US-1A-04-04 (5) + US-1A-02-05 (5) + US-1A-09-01-S3 (8) — overflow con US-1A-09-02-S3 + US-1A-06-02 si modo multi-agente sostiene velocity S1/S2. Stories P2/P3 son stretch.

## 4. Fichas detalladas

---

### US-1A-05-01-S3 — `currencies` admin UI + RBAC + audit

**Épica**: EP-1A-05 ([epics-and-stories §677](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** TI Integración
**Quiero** completar el seed `currencies` con admin UI + RBAC + audit
**Para** poder activar/desactivar monedas y mantener integridad de la base AED.

#### Contexto
S2 dejó la tabla `currencies` con 4 filas seed (AED, EUR, USD, SAR) sin admin (US-1A-03-01-S2 explícito). S3 cierra: añade UI de listado/activate/deactivate, enforce constraint "única `is_base=true`", emite audit, RBAC `ti+`. NO permitimos UI de creación de currencies nuevas en S3 (riesgo de FX rates rotos por monedas sin tasas) — sólo activate/deactivate del seed.

#### Criterios de aceptación
1. **Dado** un TI **Cuando** entra a `/admin/currencies` **Entonces** ve DataTable con 4 filas y columnas (`code`, `name`, `symbol`, `is_base`, `active`).
2. **Dado** un TI **Cuando** intenta desactivar `AED` (`is_base=true`) **Entonces** retorna 422 con `error.code="cannot_deactivate_base_currency"` y la UI muestra error inline.
3. **Dado** un TI **Cuando** desactiva `SAR` **Entonces** persiste, audit registra `action='deactivate', entity='currencies', payload_after={active:false}`, lista refresca.
4. **Dado** un Comercial **Cuando** entra a `/admin/currencies` **Entonces** retorna 403 (RBAC `ti+`).
5. **Dado** un INSERT directo a la BD intentando una segunda fila con `is_base=true` **Cuando** se ejecuta **Entonces** falla por check constraint (defense-in-depth).

#### Notas técnicas
- Backend: añadir endpoint `PATCH /api/v1/currencies/{code}/active` (read endpoints ya existen S2). Reusa `audit.log_event()` PL/pgSQL.
- Frontend: ruta `/admin/currencies` con DataTable Shadcn + AlertDialog confirm.
- DB: check constraint `EXCLUDE (is_base WITH =) WHERE (is_base = true)` o partial unique index sobre `is_base WHERE is_base`.

#### Archivos esperados
- `mt-pricing-backend/app/api/v1/currencies.py` (nuevo)
- `mt-pricing-backend/app/services/currency_service.py` (nuevo)
- `mt-pricing-backend/alembic/versions/0009_currencies_constraints.py`
- `mt-pricing-frontend/app/(app)/admin/currencies/page.tsx`
- `mt-pricing-frontend/components/admin/currency-table.tsx`
- Tests: unit service + integration + 1 E2E.

#### DoD
- [ ] Coverage ≥ 80 % nuevo.
- [ ] RLS verificada con SELECT como `comercial` (deniega).
- [ ] Audit event verificado en deactivate.
- [ ] Smoke por dev distinto.
- [ ] OpenAPI actualizado.

#### SP: 2

---

### US-1A-05-02 — `fx_rates` con cierre automático `effective_to` + retroactive guard

**Épica**: EP-1A-05 ([epics-and-stories §693](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** que insertar un `fx_rate` nuevo cierre automáticamente el anterior con el mismo par
**Para** no tener solapamientos en lookup ni ambigüedad de "tasa vigente".

#### Contexto
**MUST de S3** — bloquea US-1A-04-02 (costs FX as-of trigger). El trigger BEFORE INSERT busca el último rate vigente del mismo par (`from_code, to_code`) con `effective_to IS NULL`, lo cierra con `effective_to = NEW.effective_from`, y permite el insert. Bloquea retroactivos sin flag explícito (`allow_retroactive=true` reservado a TI con audit reason).

#### Criterios de aceptación
1. **Dado** un `fx_rate` activo `EUR→AED rate=4.29 effective_from=2026-04-01 effective_to=NULL` **Cuando** inserto otro `EUR→AED rate=4.18 effective_from=2026-06-12` **Entonces** el anterior queda con `effective_to = 2026-06-12` automáticamente y el nuevo queda con `effective_to=NULL`.
2. **Dado** un INSERT con `effective_from` < último vigente y sin flag `allow_retroactive` **Cuando** se ejecuta **Entonces** rechaza con `error.code="fx_retroactive_not_allowed"`.
3. **Dado** un INSERT con `effective_from` igual al último (mismo timestamp) **Cuando** se ejecuta **Entonces** rechaza con `error.code="fx_same_effective_from"` (no se puede tener dos rates iniciando en mismo instante).
4. **Dado** un par `from→to` no inversa (e.g. `EUR→AED` ≠ `AED→EUR`) **Cuando** consulto rate vigente para EUR→AED a una fecha `t` **Entonces** función `fx_rate_at(from, to, t)` retorna la fila única donde `effective_from <= t < effective_to OR effective_to IS NULL`.
5. **Dado** un `fx_rate` con `from_code = to_code` (e.g. AED→AED) **Cuando** se inserta **Entonces** rate forzado a `1.000000` y el trigger acepta (caso identidad para AED→AED requerido por trigger costs).

#### Notas técnicas
- Migración Alembic 0010: tabla `fx_rates` con (`id` UUID, `from_code`, `to_code`, `rate` NUMERIC(20,8), `source` ENUM(`manual`, `cbuae`, `ecb`, `imported`), `effective_from` TIMESTAMPTZ, `effective_to` TIMESTAMPTZ NULL, `created_by` UUID, `created_at`).
- Trigger PL/pgSQL `fx_rates_close_previous_trg BEFORE INSERT` — UPDATE último vigente, validate retroactive guard, set `effective_to=NULL` para nuevo.
- Función `fx_rate_at(from_code TEXT, to_code TEXT, at TIMESTAMPTZ)` SQL stable — usado por trigger costs y futuro pricing.
- Index `(from_code, to_code, effective_from DESC)` y partial `WHERE effective_to IS NULL`.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0010_create_fx_rates.py`
- `infra/supabase/migrations/0010_fx_rates_trigger.sql`
- `mt-pricing-backend/app/db/models/fx_rate.py`
- `mt-pricing-backend/tests/data/test_fx_rates_trigger.py` (cobertura BDD completa).

#### DoD
- [ ] Migración up + down testeada.
- [ ] 8+ unit tests cubriendo todos los caminos del trigger.
- [ ] Coverage ≥ 80 %.
- [ ] Función `fx_rate_at` usada en al menos 1 query smoke.
- [ ] Documentación trigger en `mt-sqlalchemy-models.md` actualizada.

#### SP: 5

---

### US-1A-05-03 — `POST /fx-rates` + UI consola TI

**Épica**: EP-1A-05 ([epics-and-stories §709](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** TI Integración
**Quiero** registrar manualmente tasas de cambio desde la UI
**Para** mantener el sistema actualizado mientras no haya proveedor automatizado.

#### Contexto
Capa API + UI sobre US-1A-05-02. Patrón ya establecido en S2 con `/suppliers` (DataTable + form modal). RBAC `ti+` exclusivo (Comercial NO puede registrar tasas — tiene impacto financiero directo).

#### Criterios de aceptación
1. **Dado** un TI **Cuando** envía `POST /api/v1/fx-rates {from:"EUR", to:"AED", rate:4.18, source:"manual", effective_from:"2026-06-12T00:00:00Z"}` **Entonces** persiste, dispara trigger cierre automático, retorna 201 con la fila creada y `audit_events` registra.
2. **Dado** un Comercial **Cuando** llama el mismo POST **Entonces** retorna 403.
3. **Dado** un TI **Cuando** entra a `/admin/fx-rates` **Entonces** ve DataTable con histórico de versiones agrupadas por par, columnas (`from`, `to`, `rate`, `source`, `effective_from`, `effective_to`, vigente badge).
4. **Dado** un TI **Cuando** completa el form modal "Nueva tasa" con par y rate **Entonces** la lista se refresca y la previa queda cerrada visualmente.
5. **Dado** un payload con `rate <= 0` **Cuando** se envía **Entonces** retorna 422 `error.code="fx_rate_must_be_positive"`.

#### Notas técnicas
- Backend: `app/api/v1/fx_rates.py` (POST + GET list con filter `from`/`to`/`vigente`).
- Frontend: `app/(app)/admin/fx-rates/page.tsx` + form modal `fx-rate-form.tsx` con react-hook-form + zod.
- i18n: namespace `fx_rates.*` (es + en).

#### Archivos esperados
- `mt-pricing-backend/app/api/v1/fx_rates.py`
- `mt-pricing-backend/app/services/fx_rate_service.py`
- `mt-pricing-frontend/app/(app)/admin/fx-rates/page.tsx`
- `mt-pricing-frontend/components/admin/fx-rate-form.tsx`
- Tests: unit + integration + 1 E2E happy.

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] RBAC verificado (Comercial 403).
- [ ] Audit event con `actor=ti_user_id, source=manual` registrado.
- [ ] Sidebar admin actualizado.

#### SP: 3

---

### US-1A-04-02 — `costs` schema con FX as-of stamping vía trigger

**Épica**: EP-1A-04 ([epics-and-stories §625](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** la tabla `costs` con `fx_rate_id` autopoblado por trigger BEFORE INSERT/UPDATE
**Para** que ningún coste pueda persistirse sin FX as-of inmutable.

#### Contexto
**MUST de S3** — corazón del motor de costes. Sin trigger, los costes registrados con `currency_origin='EUR'` no tendrían tasa estampada, rompiendo BR-1a-04. El trigger usa `fx_rate_at(currency_origin, 'AED', NEW.effective_at)` de US-1A-05-02. Si no hay tasa vigente, FAILS HARD (no permitimos inserts sin FX). El campo `scheme_landed_aed` (NUMERIC(14,4) STORED GENERATED) suma `breakdown` × FX → costo total en AED por componente del esquema.

#### Criterios de aceptación
1. **Dado** un INSERT en `costs` sin `fx_rate_id` y `currency_origin='EUR'`, `effective_at='2026-06-12'` **Cuando** se ejecuta **Entonces** trigger busca rate vigente EUR→AED a esa fecha y estampa `fx_rate_id` automáticamente.
2. **Dado** un INSERT con `fx_rate_id` explícito **Cuando** se ejecuta **Entonces** trigger respeta valor explícito y NO sobrescribe (importer reusa esto para preservar FX as-of del batch).
3. **Dado** un INSERT con `currency_origin='EUR'` y NO existe rate vigente para esa fecha **Cuando** se ejecuta **Entonces** falla con `error.code="fx_rate_not_found_at_effective_at"` (no se permite cost sin FX).
4. **Dado** un coste con `breakdown={fob_eur:12.40, freight_eur:1.80}` **Cuando** se persiste **Entonces** `scheme_landed_aed` se calcula automáticamente (vía generated column o function trigger AFTER) sumando componentes × FX.
5. **Dado** un coste migrado vía importer con `fx_inferred=true` **Cuando** se persiste **Entonces** queda marcado para audit y reportes detectan inconsistencias.
6. **Dado** un UPDATE de `breakdown` en un coste existente **Cuando** se ejecuta **Entonces** trigger crea nueva versión (`status='active'`, anterior pasa a `superseded`) — es UPSERT versionado, no UPDATE in-place.

#### Notas técnicas
- Migración Alembic 0011: tabla `costs` (`id` UUID, `sku` FK, `scheme_code` FK, `supplier_code` FK, `currency_origin` FK→currencies, `fx_rate_id` FK→fx_rates, `breakdown` JSONB, `scheme_landed_aed` NUMERIC(14,4), `effective_at` TIMESTAMPTZ, `status` ENUM(`active`, `superseded`), `fx_inferred` BOOL, `version` INT, `created_by`, `created_at`).
- Trigger PL/pgSQL `costs_stamp_fx_trg BEFORE INSERT OR UPDATE` — busca FX, valida, estampa.
- Constraint `UNIQUE (sku, scheme_code, supplier_code, status) WHERE status='active'` — sólo 1 active por combo.
- Audit trigger ya cubierto por patrón S1/S2.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0011_create_costs_table.py`
- `infra/supabase/migrations/0011_costs_fx_trigger.sql`
- `mt-pricing-backend/app/db/models/cost.py`
- Tests: 6+ unit tests cubriendo cada AC.

#### DoD
- [ ] Migración up + down testeada.
- [ ] Tests con FX missing → fail correcto.
- [ ] Coverage trigger ≥ 80 %.
- [ ] `scheme_landed_aed` recalculado en update verificado.
- [ ] Constraint UNIQUE active probado.

#### SP: 5

---

### US-1A-04-03 — `POST /costs` con breakdown desglosado + scheme_landed_aed

**Épica**: EP-1A-04 ([epics-and-stories §641](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** registrar un coste por SKU × esquema × proveedor con breakdown JSONB
**Para** que el motor de pricing tenga inputs completos en AED.

#### Contexto
Capa API sobre US-1A-04-02. Valida `breakdown` keys contra `cost_components_template` del scheme (warning si campo extra; reject si campo required missing). Reusa `compute_diff` helper de S2.

#### Criterios de aceptación
1. **Dado** un Comercial y un SKU `MT-V-038`, esquema `FBA`, supplier `MT_VALVES_ES` **Cuando** envía `POST /api/v1/costs {breakdown:{fob_eur:12.40, freight_eur:1.80, customs_aed:2.10, fba_fees_aed:8.50, payment_fees_pct:2.49}, currency_origin:"EUR", effective_at:"2026-06-12"}` **Entonces** persiste, calcula `scheme_landed_aed`, registra audit, retorna 201.
2. **Dado** un breakdown sin un campo declarado required en `cost_components_template['FBA']` (e.g. `fob` faltante) **Cuando** se envía **Entonces** retorna 422 `error.code="missing_required_breakdown_field"`.
3. **Dado** un breakdown con campo no declarado (e.g. `unknown_fee:5.00`) **Cuando** se envía **Entonces** persiste con warning en respuesta (`warnings:["unknown_breakdown_field:unknown_fee"]`) — no rechaza (BR-1a-03).
4. **Dado** un Comercial **Cuando** consulta `GET /api/v1/products?missing_cost_scheme=FBA` **Entonces** retorna SKUs sin coste activo para FBA.
5. **Dado** un Comercial **Cuando** llama `GET /api/v1/products/{sku}/costs` **Entonces** retorna lista con costes activos por scheme + supplier, con breakdown desglosado y `scheme_landed_aed`.
6. **Dado** un coste activo **Cuando** Comercial llama `PUT /api/v1/costs/{id}` con cambio en `breakdown` **Entonces** se crea nueva versión (anterior `superseded`), audit registra `diff`.

#### Notas técnicas
- Backend: `app/services/cost_service.py` con `create_cost`, `update_cost` (versionado), `list_costs_by_sku`, `compute_landed_aed`.
- Backend: `app/api/v1/costs.py` con endpoints CRUD + `GET /products?missing_cost_scheme=...`.
- Backend: validador `breakdown_validator.py` que lee `schemes.cost_components_template`.
- Pydantic schemas: `CostCreate`, `CostUpdate`, `CostRead`.

#### Archivos esperados
- `mt-pricing-backend/app/api/v1/costs.py`
- `mt-pricing-backend/app/services/cost_service.py`
- `mt-pricing-backend/app/services/breakdown_validator.py`
- Tests: unit + integration end-to-end (POST → trigger → audit → GET).

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] Audit event verificado con `diff` correcto.
- [ ] OpenAPI actualizado.
- [ ] Smoke E2E con un SKU real.
- [ ] Validación cross-currency probada (EUR origin, AED landed).

#### SP: 5

---

### US-1A-04-04 — UI tab "Costes" con tabla por esquema y breakdown editor

**Épica**: EP-1A-04 ([epics-and-stories §657](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** ver y editar costes por esquema desde la ficha de SKU
**Para** no necesitar APIs ni Excel.

#### Contexto
S2 dejó tabs Identidad + Imágenes activos (Costes/Precios/Traducciones/Auditoría disabled). S3 activa **Costes** (las otras 2 quedan: Traducciones cubierta por US-1A-02-05; Precios y Auditoría defer a S4). Patrón Pantalla 5 del UX (firma pendiente — ver Apéndice B).

#### Criterios de aceptación
1. **Dado** un Comercial en `/products/MT-V-038` **Cuando** click tab Costes **Entonces** ve tabla con filas por (scheme × supplier), columnas (`Scheme`, `Supplier`, `Currency origin`, `Total AED landed`, `FX rate`, `Effective at`, `Versión`).
2. **Dado** una fila **Cuando** click Expandir **Entonces** muestra el `breakdown` JSONB con cada componente editable inline.
3. **Dado** edita `fob_eur` de 12.40 a 13.00 y click Guardar **Cuando** la API responde 201 con nueva versión **Entonces** la UI muestra toast "Versión 2 creada" y refresca la tabla con la nueva fila active + anterior superseded oculta por defecto.
4. **Dado** click "Mostrar histórico" **Cuando** se activa **Entonces** ve filas superseded grayed out con timestamps.
5. **Dado** un SKU sin costes para un scheme **Cuando** click "Añadir coste" **Entonces** abre form modal con scheme + supplier + currency + breakdown editor.
6. **Dado** un error 422 (campo required missing) **Cuando** ocurre **Entonces** errores inline por componente.

#### Notas técnicas
- Frontend: `app/(app)/products/[sku]/_components/costs-tab.tsx` con DataTable + expand row + form modal.
- Frontend: `lib/api/costs.ts` con typed fetcher.
- Frontend: i18n `catalog.costs.*`.
- Componente reusable `breakdown-editor.tsx` (mapping component_key → input numérico, lee template de scheme).

#### Archivos esperados
- `mt-pricing-frontend/app/(app)/products/[sku]/_components/costs-tab.tsx`
- `mt-pricing-frontend/components/products/breakdown-editor.tsx`
- `mt-pricing-frontend/components/products/cost-form-modal.tsx`
- `mt-pricing-frontend/lib/api/costs.ts`
- Tests: unit costs-tab + breakdown-editor + 1 E2E happy (crear, editar, ver versión).

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] UX firmada Pantalla 5 antes de merge (o decisión "reusar patrón Pantalla 4 inline edit").
- [ ] Audit verificado en update.
- [ ] Smoke por dev distinto.
- [ ] Sentry sin errores.

#### SP: 5

---

### US-1A-06-02 — Importer batch costos (Excel) con preview + apply

**Épica**: EP-1A-06 ([epics-and-stories §761](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** importar archivos de costos (líneas SKU × esquema × proveedor) con preview y reporte de huérfanos
**Para** cargar costes en bulk sin tocar la BD directamente.

#### Contexto
Reusa la pipeline del importer S2 (`column_mapper`, `parser`, `differ`, `applier`, `importer_service` ya genéricos en S2). Sólo extiende para `type=costs`. Validación cruzada con PIM (`SKU huérfano` si no existe en `products`). FX as-of del batch: usar `effective_at` del batch para todo el lote.

#### Criterios de aceptación
1. **Dado** un Comercial sube `costs_dubai.xlsx` **Cuando** llama `POST /api/v1/imports?type=costs&mode=preview` **Entonces** sistema persiste raw, crea `import_runs`, encola ImportTask, retorna 202.
2. **Dado** preview ready **Cuando** consulto **Entonces** veo summary `{total, new, updated, errors, orphans:{sku_not_in_pim, scheme_unknown, supplier_unknown}}` por categoría.
3. **Dado** un SKU huérfano (no en `products`) **Cuando** se procesa **Entonces** queda en `orphans.sku_not_in_pim` con `assignable_owner=NULL` (Champion resuelve).
4. **Dado** preview confirmado **Cuando** Comercial llama `apply` **Entonces** cada fila válida persiste vía `cost_service.create_cost` (reusa lógica US-1A-04-03), audit emite, FX as-of del batch estampada.
5. **Dado** un batch con FX missing para alguna currency_origin a `effective_at` **Cuando** se aplica **Entonces** el row queda en `errors.fx_missing` y resto continúa.

#### Notas técnicas
- Backend: extender `app/importers/` con `costs_parser.py`, `costs_validator.py`, `costs_differ.py`. La factory `importer_service` ya despacha por `type`.
- Backend: extender `import_runs.preview` JSONB schema con `orphans` sub-section.
- Frontend: extender wizard `/imports/new?type=costs` con step Mapping específico (columnas de costos).
- Persistencia: `import_runs` ya in-memory en S2 según execution-report §2 Gap 5 — **decisión S3**: persistir `import_runs` y `import_run_rows` en BD ahora (la deuda técnica documentada). Migración Alembic 0012.

#### Archivos esperados
- `mt-pricing-backend/app/importers/costs_parser.py`
- `mt-pricing-backend/app/importers/costs_validator.py`
- `mt-pricing-backend/app/importers/costs_differ.py`
- `mt-pricing-backend/alembic/versions/0012_persist_import_runs.py`
- `mt-pricing-frontend/app/(app)/imports/_components/costs-mapping-step.tsx`
- Tests: unit parser + validator + integration full pipeline.

#### DoD
- [ ] Persiste `import_runs` en BD (resuelve deuda S2).
- [ ] Coverage ≥ 80 %.
- [ ] Smoke con fixture costos 100 rows.
- [ ] OpenAPI actualizado.
- [ ] Reporte CSV downloadable.

#### SP: 5

---

### US-1A-06-03 — Importer compatibilidades materiales (657 filas)

**Épica**: EP-1A-06 ([epics-and-stories §777](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial / TI
**Quiero** cargar `Copia de Compatibilidad de Materiales MT V4.xlsx` (657 filas) en `material_compatibilities`
**Para** que la ficha de producto muestre la matriz materiales × T °C y el matching pipeline (deal-breakers) consulte la tabla.

#### Contexto
Tabla referencial. La consume el matching pipeline (US-1A-09-01-S3) en su Etapa 4 (Hard Rules — `are_materials_compatible`). Sin esta tabla, el deal-breaker de materiales del comparador queda con whitelist hardcodeada.

#### Criterios de aceptación
1. **Dado** el archivo **Cuando** ejecuto importer modo preview **Entonces** sistema reporta `total=657, new=657, errors=N, format_invalid=M`.
2. **Dado** preview confirmado **Cuando** apply **Entonces** persiste 657 filas en `material_compatibilities` con columnas (`producto_descriptor` TEXT, `temperatura_c` NUMERIC, `material_xxx` columns por material según el Excel original).
3. **Dado** un descriptor matcheable a un SKU **Cuando** consulto compatibilidades en la ficha **Entonces** sistema retorna matriz aplicable (UI tab "Compatibilidades" — defer S4, sólo data layer en S3).
4. **Dado** filas con `temperatura_c` no numérico **Cuando** se importan **Entonces** quedan en reporte de rechazos con razón.
5. **Dado** una segunda ejecución del importer **Cuando** se dispara con `mode=replace` **Entonces** trunca tabla y recarga (idempotente — material_compatibilities es referencia, no histórica).

#### Notas técnicas
- Migración Alembic 0013: tabla `material_compatibilities` (schema según Excel real, ~10-15 columnas de materiales).
- Backend: `app/importers/material_compat_parser.py`.
- NO se expone endpoint API en S3 (consumo interno por matching pipeline). UI tab Compatibilidades en ficha → S4.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0013_create_material_compatibilities.py`
- `mt-pricing-backend/app/db/models/material_compatibility.py`
- `mt-pricing-backend/app/importers/material_compat_parser.py`
- Tests: unit + integration.

#### DoD
- [ ] 657 filas cargadas con éxito en staging local.
- [ ] Coverage ≥ 80 %.
- [ ] Función helper `are_materials_compatible(mat_a, mat_b, temp_c)` documentada.

#### SP: 3

---

### US-1A-02-05 — Translations approval workflow (state machine + audit)

**Épica**: EP-1A-02 ([epics-and-stories §473](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** Comercial
**Quiero** registrar traducciones ES/AR con estado (`pending`/`draft`/`approved`/`rejected`) y workflow de aprobación
**Para** que la cobertura sea medible y sólo se exporten traducciones aprobadas (BR-1a-09).

#### Contexto
S1/S2 dejaron `product_translations` table existente vía importer PIM (con `name_es` ya cargado de columna `Nombre ERP`). S3 añade el **state machine**: transitions válidos `pending→draft→approved` o `pending→draft→rejected→draft`, con roles permitidos por transición y audit obligatorio. UI tab Traducciones activa con botones de approve/reject.

#### Criterios de aceptación
1. **Dado** un SKU con `name_en="Brass gate valve DN50"` **Cuando** Comercial envía `POST /api/v1/products/{sku}/translations {lang:"es", name:"Válvula compuerta latón DN50", status:"draft"}` **Entonces** persiste, audit registra `action='create_translation'`.
2. **Dado** una traducción `draft` **Cuando** Comercial llama `POST /api/v1/products/{sku}/translations/{lang}/transition {to:"approved"}` **Entonces** sistema valida `comercial NO puede approve own translation` (BR-1a-09 four-eyes), retorna 403.
3. **Dado** una traducción `draft` creada por Comercial A **Cuando** Comercial B (otro user) llama transition `to:"approved"` **Entonces** persiste con `approved_by=B, approved_at=now()`, audit registra.
4. **Dado** una traducción `approved` **Cuando** alguien intenta `transition to:"draft"` **Entonces** sólo permitido si `actor=approver original` o role `gerente+` (re-edit flow).
5. **Dado** un export XLSX de catálogo (preparación Fase 1b) **Cuando** se filtra `translation_status=approved` **Entonces** retorna sólo aprobadas.
6. **Dado** un Comercial en `/products/{sku}` tab Traducciones **Cuando** ve la lista **Entonces** muestra cobertura `EN/ES/AR: 100%/85%/15% approved` con badges por estado.

#### Notas técnicas
- Backend: tabla `product_translations` ya existe (S1/S2). Añadir columnas `approved_by` UUID, `approved_at` TIMESTAMPTZ, `rejection_reason` TEXT. Migración 0014.
- Backend: `app/services/translation_service.py` con state machine (usar `transitions` library o impl manual). Map (current_status, target_status, role) → allowed.
- Backend: `app/api/v1/translations.py` endpoints CRUD + `POST /transition`.
- Frontend: `app/(app)/products/[sku]/_components/translations-tab.tsx` con table EN/ES/AR + actions (Edit, Submit for review, Approve, Reject).
- i18n: namespace `catalog.translations.*`.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0014_translations_approval_columns.py`
- `mt-pricing-backend/app/api/v1/translations.py`
- `mt-pricing-backend/app/services/translation_service.py`
- `mt-pricing-frontend/app/(app)/products/[sku]/_components/translations-tab.tsx`
- `mt-pricing-frontend/components/products/translation-row.tsx`
- Tests: unit state machine + integration + 1 E2E.

#### DoD
- [ ] State machine cubierto con 8+ tests (todas las transitions válidas e inválidas).
- [ ] Four-eyes constraint verificado.
- [ ] Coverage ≥ 80 %.
- [ ] UX firmada para tab Traducciones (o decisión reusar patrón Pantalla 4 grid).
- [ ] Audit eventos verificados (`create_translation`, `transition_translation`).

#### SP: 5

---

### US-1A-09-01-S3 — Matching pipeline foundation (Query Builder + Multi-Source Fetcher stubs + Scoring G1/G2)

**Épica**: EP-1A-09 (NUEVA — comparador de competidores Fase 1a foundation; ver Apéndice B)
**Como** dev backend
**Quiero** las primeras 3 etapas del pipeline de matching operativas con stubs
**Para** que en S4-S5 podamos reemplazar stubs por integraciones reales (Bright Data, Google Vision, VLM judge) sin re-arquitectar.

#### Contexto
Spike el pipeline detallado del comparador. Story principal del sprint. Implementa:
- **Etapa 1 (Query Builder)**: genera 3-5 queries por SKU cubriendo brand+spec EN, spec EN, AR (fallback synthetic vía LLM), DN→pulgadas conversion, part number. Real, sin stubs.
- **Etapa 2 (Multi-Source Fetcher)**: arquitectura hexagonal (Protocol `CandidateFetcher`) + orquestador `CandidateFetcherOrchestrator` con 2 implementaciones: `StubAmazonAEFetcher` (datos canned) y `StubManufacturerFetcher` (Pegler whitelist canned). Estructura lista para inyectar Bright Data adapter en S4.
- **Etapa 3 (Scoring G1 hard-rules + G2 multi-dim)**: `G1` = deal-breaker filter (DN match, PN compatible, family match, material whitelist hardcoded mientras llega US-1A-06-03). `G2` = score multi-dimensional ponderado (specs 40 % + text similarity 30 % + brand match 20 % + price-range 10 %; sin imagen/OCR aún — eso es S4).

NO hay UI en S3 (pipeline backend-only). Output: tabla `match_decisions` poblable + endpoint diagnóstico `POST /api/v1/match/dry-run` que toma un SKU + queries y retorna candidates ranked. UI Tinder-swipe es S5.

#### Criterios de aceptación
1. **Dado** un SKU `MT-V-038` (ball valve, DN50, brass, BSP_F) **Cuando** llamo `POST /api/v1/match/dry-run {sku:"MT-V-038"}` **Entonces** sistema genera ≥ 4 queries (al menos: 1 brand+spec EN, 1 spec EN, 1 AR, 1 part_number) y devuelve estructura `{queries:[...], candidates_raw:[...], candidates_filtered_g1:[...], candidates_scored_g2:[...]}`.
2. **Dado** un SKU sin `brand_canonical` **Cuando** se generan queries **Entonces** se omite la query brand+spec (no hay brand) y se generan 3 queries (spec EN, AR, functional EN).
3. **Dado** un SKU con DN=50 **Cuando** se genera la query EN **Entonces** incluye tanto `DN50` como `2"` (conversión via mapping `DN_TO_INCH`).
4. **Dado** los 2 stubs fetchers configurados **Cuando** orchestrator ejecuta `fetch_all(queries)` **Entonces** retorna lista combinada de `CandidateRaw` con `source` discriminado (amazon_ae stub + pegler stub).
5. **Dado** un candidate con `parsed_specs.dn=65` y SKU `dn=50` **Cuando** pasa por G1 **Entonces** queda excluido con `rejected_reason="dn_mismatch"`.
6. **Dado** un candidate con `parsed_specs.family="gate_valve"` y SKU `family="ball_valve"` **Cuando** pasa por G1 **Entonces** rejected `family_mismatch`.
7. **Dado** un candidate que pasa G1 **Cuando** entra a G2 **Entonces** retorna score multi-dim 0.0-1.0 con breakdown `{specs:0.85, text:0.72, brand:0.5, price:0.9, total:0.78}`.
8. **Dado** una corrida dry-run **Cuando** termina **Entonces** persiste fila en `match_decisions` con `status='draft'`, `pipeline_version='S3-foundation-v1'`, `queries_used` JSONB, `candidates_evaluated` count, `top_candidate` JSONB, `score_breakdown`.

#### Notas técnicas
- **Etapa 1**: `app/services/comparator/query_builder.py` con función pura `build_queries(sku: Product) -> list[Query]`. Mapping `DN_TO_INCH` constante. Para AR: si `product_translations.name_ar` aprobada → usar; si no → marcar `synthetic_ar=True` y NO llamar LLM en S3 (stub: usar template hardcoded `"صمام {family_ar} {material_ar}"`). Query types enum: `brand_spec | spec | functional | spec_ar | part_number | norm_based`.
- **Etapa 2**: `app/services/comparator/sourcing.py` con `Protocol CandidateFetcher` + `CandidateFetcherOrchestrator(fetchers: dict[str, CandidateFetcher])`. Stubs en `app/services/comparator/stubs/{stub_amazon_ae.py, stub_manufacturer.py}` que retornan listas canned desde `tests/fixtures/comparator/canned_candidates.json` (≥ 20 candidates representativos). Circuit breaker placeholder (no-op en stubs, real en S4).
- **Etapa 3**: `app/services/comparator/normalizer.py` con `parse_specs(title, description) -> dict` (regex DN/PN/material/connection — usar mismos parsers que importer PIM si compatibles). `app/services/comparator/g1_filter.py` con `HARD_RULES` lista (DN match strict, PN compatible cand>=sku, family match, material whitelist mientras US-1A-06-03 no esté lista → fallback a la lista hardcoded del pipeline doc §6.2). `app/services/comparator/g2_scorer.py` con `score(sku, candidate) -> ScoreBreakdown` ponderado.
- **Persistencia**: tabla `match_decisions` (UUID, sku FK, candidate_source, candidate_external_id, status ENUM `draft|auto_match|human_match|human_reject|discarded`, queries_used JSONB, candidates_evaluated INT, top_candidate JSONB, score_breakdown JSONB, pipeline_version TEXT, created_at). Migración 0015.
- **NO incluido en S3**: Etapa 3 image mirror real (US-1A-09-03 S4), OCR (US-1A-09-04 S4), embeddings (S4), RRF + isotonic calibrator (US-1A-09-05 S4), VLM judge (US-1A-09-06 S4), Tinder UI (S5).
- **Endpoint dry-run**: solo accesible con role `ti+` en S3 (es herramienta de debug).

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0015_create_match_decisions.py`
- `mt-pricing-backend/app/db/models/match_decision.py`
- `mt-pricing-backend/app/services/comparator/__init__.py`
- `mt-pricing-backend/app/services/comparator/query_builder.py`
- `mt-pricing-backend/app/services/comparator/sourcing.py`
- `mt-pricing-backend/app/services/comparator/stubs/stub_amazon_ae.py`
- `mt-pricing-backend/app/services/comparator/stubs/stub_manufacturer.py`
- `mt-pricing-backend/app/services/comparator/normalizer.py`
- `mt-pricing-backend/app/services/comparator/g1_filter.py`
- `mt-pricing-backend/app/services/comparator/g2_scorer.py`
- `mt-pricing-backend/app/services/comparator/pipeline.py` (orquesta etapas 1-3)
- `mt-pricing-backend/app/api/v1/match.py` (endpoint dry-run)
- `mt-pricing-backend/tests/fixtures/comparator/canned_candidates.json`
- `mt-pricing-backend/tests/services/comparator/` (≥ 25 tests)

#### DoD
- [ ] Coverage ≥ 80 % en `app/services/comparator/`.
- [ ] Pipeline corre dry-run sobre 5 SKUs reales del PIM y produce candidates ranked en < 2 s (sin red por ser stub).
- [ ] Persiste en `match_decisions` con `pipeline_version` correcto.
- [ ] Documentación: ADR nuevo "ADR-066 Pipeline matching foundation S3" con decisiones (hexagonal sourcing, score weights iniciales, fixtures como canned datasets).
- [ ] Smoke por dev distinto.

#### SP: 8

---

### US-1A-09-02-S3 — Channel mirror Amazon UAE stub (SP-API canonical vs live diff con datos canned)

**Épica**: EP-1A-09 (NUEVA)
**Como** dev backend
**Quiero** una infraestructura de "channel mirror" que compare datos canónicos del SKU MT vs lo que el canal Amazon UAE muestra
**Para** detectar drift de listing (precio, disponibilidad, título) cuando en S4-S5 conectemos SP-API real.

#### Contexto
Stub-only en S3. Establece el patrón `ChannelMirror` que en Fase 1b alimenta el pricing engine (detectar competencia de listings propios). Datos canned simulan la respuesta SP-API: `{asin, sku_seller, title, price_aed, in_stock, last_updated}`. Endpoint diagnóstico `GET /api/v1/channels/amazon_ae/{sku}/diff` retorna delta entre canonical (`products`) y live (canned).

#### Criterios de aceptación
1. **Dado** una fixture `tests/fixtures/channels/amazon_ae_canned.json` con 5 listings simulados **Cuando** llamo `GET /api/v1/channels/amazon_ae/MT-V-038/diff` **Entonces** retorna `{canonical:{...products row...}, live:{...canned listing...}, diff:{title:["...","..."], price_aed:[null, 145.50], status:"drift_detected"}}`.
2. **Dado** un SKU sin listing canned **Cuando** consulto **Entonces** retorna `{canonical:{...}, live:null, diff:{}, status:"not_listed"}`.
3. **Dado** un SKU cuyo canonical y live son idénticos **Cuando** consulto **Entonces** `status:"in_sync"`, `diff:{}`.
4. **Dado** el adaptador `StubSpApiClient` configurado **Cuando** se invoca `fetch_listing(sku)` **Entonces** lee de fixture (no hace red) y retorna estructura tipada.
5. **Dado** un endpoint protegido **Cuando** Comercial llama **Entonces** retorna 200 (read-only); si TI llama `POST /api/v1/channels/amazon_ae/refresh-cache` **Entonces** stub no-op + log "stub mode, no real refresh".

#### Notas técnicas
- Backend: `app/services/channels/amazon_ae/__init__.py`, `sp_api_client.py` (Protocol + StubSpApiClient impl), `mirror.py` (compute_diff function pura).
- Backend: `app/api/v1/channels.py` (endpoints diagnóstico).
- Sin migración nueva (no persistencia en S3 — el cache lo añade S4 cuando llegue SP-API real).
- El `diff` algorithm es pure-python dict comparison; reusar `compute_diff` helper existente de S2.

#### Archivos esperados
- `mt-pricing-backend/app/services/channels/__init__.py`
- `mt-pricing-backend/app/services/channels/amazon_ae/sp_api_client.py`
- `mt-pricing-backend/app/services/channels/amazon_ae/mirror.py`
- `mt-pricing-backend/app/api/v1/channels.py`
- `mt-pricing-backend/tests/fixtures/channels/amazon_ae_canned.json`
- Tests: unit + integration (≥ 8 tests cubriendo todos los status).

#### DoD
- [ ] Coverage ≥ 80 %.
- [ ] OpenAPI actualizado con endpoint diagnóstico.
- [ ] ADR nuevo "ADR-067 Channel mirror pattern" — Protocol + Stub + futura impl SP-API real.
- [ ] Stub explícitamente documentado en código + README.

#### SP: 3

---

### US-1A-02-09-FE — Wire UI filtros avanzados `dn`/`pn`/`material` (frontend completing S2 backend)

**Épica**: EP-1A-02
**Como** Comercial
**Quiero** filtrar la lista de productos por `dn`, `pn`, `material` desde la UI
**Para** encontrar SKUs específicos en el catálogo de 5085 rows.

#### Contexto
S2 dejó backend completo (US-1A-02-09 cerrado en execution-report) — endpoint `GET /api/v1/products` ya soporta query params `dn`, `pn`, `material`. UI sólo tiene `family`, `q`, `data_quality`, `active`. S3 expone los 3 filtros restantes en el FilterPanel (Sheet "Más filtros") ya creado en S2.

#### Criterios de aceptación
1. **Dado** un Comercial en `/products` **Cuando** abre el Sheet "Más filtros" **Entonces** ve inputs `DN` (numeric, multi-select chips), `PN` (numeric, single), `Material` (select desde whitelist).
2. **Dado** completa `DN=50, Material=brass` y aplica **Cuando** la URL refleja `?dn=50&material=brass` **Entonces** la lista se actualiza con ≤ N filas.
3. **Dado** chips activos en toolbar **Cuando** click × en chip "DN: 50" **Entonces** quita el filter y refresca.
4. **Dado** click "Limpiar todo" **Cuando** confirma **Entonces** todos los filters se quitan, URL limpia, lista refresca.
5. **Dado** un material no en whitelist **Cuando** se intenta vía URL directo `?material=unobtainium` **Entonces** UI muestra "0 resultados" sin error (el backend retorna lista vacía).

#### Notas técnicas
- Frontend: extender `components/products/products-filters-sheet.tsx` ya existente (S2).
- Frontend: `lib/api/products.ts` types ya soportan los params (S2 backend).
- Lista materials whitelist: derivar de los distinct values de `products.material` (endpoint `GET /api/v1/products/distinct-materials` — añadir en S3 si no está).

#### Archivos esperados
- `mt-pricing-frontend/components/products/products-filters-sheet.tsx` (modificar)
- `mt-pricing-frontend/components/products/active-filters-chips.tsx` (modificar)
- `mt-pricing-backend/app/api/v1/products.py` (añadir `GET /products/distinct-materials` si no existe)
- Tests: unit FilterSheet con nuevos inputs.

#### DoD
- [ ] Coverage ≥ 80 % UI nueva.
- [ ] Smoke con PIM real cargado: filtrar `dn=50` en 5085 rows < 1 s wall-clock.
- [ ] i18n keys ES/EN.
- [ ] Sentry sin errores.

#### SP: 2

---

### US-1A-07-02 — RLS finas `products`/`costs`/`prices`/`audit_events`

**Épica**: EP-1A-07 ([epics-and-stories §877](epics-and-stories-mt-pricing-mdm-phase1.md))
**Como** dev backend
**Quiero** RLS policies declarativas que enforcen RBAC en BD
**Para** defense in depth (auth en API + RLS en BD, NFR-07/11).

#### Contexto
**Stretch goal** — incluir sólo si capacity sostiene 38+ SP. Stories anteriores tenían RLS básicas (S1: `authenticated` SELECT). S3 endurece: SELECT/INSERT/UPDATE/DELETE policies por rol específico (`comercial`, `gerente`, `ti`) sobre `products`, `costs`, `prices` (placeholder), `audit_events` (read-only para `gerente+`, append-only para sistema).

#### Criterios de aceptación
1. **Dado** un usuario `comercial` autenticado **Cuando** intenta `INSERT INTO costs ... status='active'` **Entonces** RLS permite.
2. **Dado** un `comercial` **Cuando** intenta `UPDATE audit_events SET ...` **Entonces** RLS deniega (append-only).
3. **Dado** un `ti` **Cuando** intenta `UPDATE products SET name_en = ...` **Entonces** RLS deniega (write reservado a `comercial+`).
4. **Dado** un `gerente` **Cuando** consulta `SELECT * FROM audit_events WHERE entity='products'` **Entonces** RLS permite y retorna eventos.
5. **Dado** un usuario sin auth **Cuando** intenta cualquier operación **Entonces** RLS deniega 0 filas (defense-in-depth — auth ya rechazó en API, esto es backstop).

#### Notas técnicas
- Migración 0016: policies SQL declarativas en `infra/supabase/migrations/0016_rls_fine_grained.sql`.
- Helper PL/pgSQL `auth_user_has_role(role TEXT) RETURNS BOOL` que lee `public.users.role` desde `auth.uid()`.
- Tests integration con testcontainers Postgres + Supabase migrations.

#### Archivos esperados
- `mt-pricing-backend/alembic/versions/0016_rls_fine_grained.py`
- `infra/supabase/migrations/0016_rls_fine_grained.sql`
- Tests: integration con 4 roles (comercial, gerente, ti, anon) × 4 tablas × 4 ops = 64 escenarios mínimos pero priorizar 16 críticos.

#### DoD
- [ ] 16 tests integration pasando.
- [ ] Coverage policies cubre al menos 1 deny y 1 allow por (role, tabla, op).
- [ ] Documentación en `mt-security-compliance-design.md`.

#### SP: 3

---

## 5. Plan de ejecución multi-agente

Patrón S1/S2 demostró que 4 agentes paralelos con dominios disjuntos sostienen velocity de ~50 SP en una iteración (~30 min wall-clock por agente). Para S3 mantenemos 4 agentes + 1 gap-fix.

### Agente A — Backend Data + FX engine + RLS (~15 SP)

**Stories**: US-1A-05-01-S3, US-1A-05-02, US-1A-05-03 (parte backend), US-1A-04-02, US-1A-07-02 (stretch).

**Paths exclusivos**:
- `mt-pricing-backend/alembic/versions/0009_*` to `0011_*`, `0016_*`
- `mt-pricing-backend/app/db/models/{currency.py, fx_rate.py, cost.py}`
- `mt-pricing-backend/app/api/v1/{currencies.py, fx_rates.py}`
- `mt-pricing-backend/app/services/{currency_service.py, fx_rate_service.py}`
- `infra/supabase/migrations/0010_*`, `0011_*`, `0016_*`

**No toca**: `app/api/v1/costs.py`, `app/services/comparator/**`, frontend.

### Agente B — Backend API + Importers (~13 SP)

**Stories**: US-1A-04-03, US-1A-06-02, US-1A-06-03.

**Paths exclusivos**:
- `mt-pricing-backend/app/api/v1/costs.py`
- `mt-pricing-backend/app/services/{cost_service.py, breakdown_validator.py}`
- `mt-pricing-backend/app/importers/{costs_*, material_compat_*}`
- `mt-pricing-backend/alembic/versions/0012_*`, `0013_*`
- `mt-pricing-backend/app/db/models/material_compatibility.py`

**No toca**: comparator/**, frontend (excepto integración OpenAPI).

### Agente C — Comparator pipeline + Channel mirror (~16 SP)

**Stories**: US-1A-09-01-S3, US-1A-09-02-S3, US-1A-02-05 (backend parte).

**Paths exclusivos**:
- `mt-pricing-backend/app/services/comparator/**` (toda la carpeta nueva)
- `mt-pricing-backend/app/services/channels/**` (toda la carpeta nueva)
- `mt-pricing-backend/app/api/v1/{match.py, channels.py, translations.py}`
- `mt-pricing-backend/app/services/translation_service.py`
- `mt-pricing-backend/alembic/versions/0014_*`, `0015_*`
- `mt-pricing-backend/app/db/models/match_decision.py`
- `mt-pricing-backend/tests/fixtures/{comparator/, channels/}`

**No toca**: costs/, currencies/, fx_rates/, frontend.

### Agente D — Frontend (UI tabs + admin + filters) (~17 SP)

**Stories**: US-1A-04-04 (UI tab Costes), US-1A-05-01-S3 (admin currencies UI), US-1A-05-03 (admin fx_rates UI), US-1A-02-05 (UI tab Traducciones), US-1A-06-02 (UI mapping costs step), US-1A-02-09-FE.

**Paths exclusivos**:
- `mt-pricing-frontend/app/(app)/admin/{currencies,fx-rates}/**`
- `mt-pricing-frontend/app/(app)/products/[sku]/_components/{costs-tab.tsx, translations-tab.tsx}`
- `mt-pricing-frontend/app/(app)/imports/_components/costs-mapping-step.tsx`
- `mt-pricing-frontend/components/{admin/, products/breakdown-editor.tsx, products/cost-form-modal.tsx, products/translation-row.tsx, products/products-filters-sheet.tsx}`
- `mt-pricing-frontend/lib/api/{costs.ts, fx_rates.ts, currencies.ts, translations.ts}`
- `mt-pricing-frontend/messages/{es,en}/*.json` (namespaces nuevos)

**No toca**: backend, comparator stubs (no UI en S3).

### Agente E — Gap-fix backend post-implementación (cuando todos los anteriores merguean)

Patrón S2: corre tests en master integrado, detecta gaps de tipo 4xx/5xx por inconsistencias de schemas, fixes secundarios (ej. typings de Pillow/Pydantic, tests de smoke), persiste `import_runs` en BD si el agente B no lo cerró.

### Conflictos previstos (mitigación)

- `mt-pricing-backend/app/api/v1/products.py`: lo modifican Agente B (añadir `GET /missing_cost_scheme`) y Agente D (añadir `GET /distinct-materials` si no existe). **Solución**: Agente E hace merge final.
- `mt-pricing-backend/openapi/openapi.yaml`: tres agentes añaden secciones. **Solución**: cada agente añade en path único + Agente E consolida.
- `messages/es/common.json`: tres frontends añaden keys. **Solución**: namespaces separados (`fx_rates.*`, `currencies.*`, `costs.*`, `translations.*`) → 0 conflicto.

## 6. Riesgos y bloqueos

| ID | Riesgo | Severidad | Probabilidad | Mitigación |
|----|--------|-----------|--------------|------------|
| R-S3-01 | **ADR-055 SSRF policy sigue draft** (renumerada en S2; psierra firma pendiente) | Media | Media | Cualquier nuevo channel mirror (US-1A-09-02) o probe extension hereda la policy. Bloquea activación `ALLOW_PROBE_FROM_PIM_ES`. **Acción S3 día 1**: arquitecto firma ADR-055 antes de empezar US-1A-09-02. |
| R-S3-02 | **Q-09 image rights MT España** sigue abierto → mirror legal exposición | Alta | Alta | Stub-only en S3 (no llamamos red). Real en S4 sólo si Q-09 firmado. Audit `image_origin_url` siempre. (R-044 register) |
| R-S3-03 | **Scraping Amazon UAE legal review** — Bright Data Web Scraper API ToS UAE: ¿permitido? PDPL? | Alta | Alta | **Q-NEW-S3 abierta**: Champion + Legal MT review antes de S4 con datos reales. En S3 sólo stubs locales (no red). Documentar en ADR-067. |
| R-S3-04 | **Bright Data SP-API credenciales** no entregadas → bloqueante S4 mirror real | Media | Media | Solo stubs en S3, no bloquea S3. Champion debe iniciar trámite ya para tener creds en kickoff S4. |
| R-S3-05 | **`manual_locked_fields` UI marking** sigue defer (Gap S2 #5) → importer respeta locked fields pero UI no permite marcarlos | Baja | Alta | **Decisión S3**: defer formal a S4 (anotar en `manual_locked_fields TEXT[]` API se llena vía PUT product directo en S3 si ocurre). Story US-1A-02-04-S4 cubre la UI. |
| R-S3-06 | **`import_runs` in-memory** queda como deuda S2 → en S3 entra en US-1A-06-02 la persistencia BD. Si bajamos US-1A-06-02 por capacity, deuda persiste a S4 | Media | Media | Migración 0012 va con US-1A-06-02. Si esa story no entra, abrir story dedicada `US-1A-06-08` 2 SP "persistir import_runs" en S4. |
| R-S3-07 | **UX firmas pendientes** Pantalla 5 (Costes) y tab Traducciones no firmadas | Media | Media | Bloquea US-1A-04-04 + US-1A-02-05 frontend a 70 % entrega. Acción: psierra firma o decisión "reusar patrón Pantalla 4 inline edit grid". |
| R-S3-08 | **FX rates seed inicial vacío** → costs.create() falla por `fx_rate_not_found` | Alta | Media | Día 1 del sprint: TI carga 4 rates manuales seed (EUR→AED, USD→AED, SAR→AED, AED→AED identidad) vía `POST /fx-rates`. Story US-1A-05-03 entrega API justo para esto. |
| R-S3-09 | **Capacidad real < 30 SP** si TI Integración no FTE | Alta | Media | Ver §3 priorización: bajar US-1A-07-02 (-3) + US-1A-06-03 (-3) + US-1A-09-02-S3 (-3) → 26 SP core. |
| R-S3-10 | **Material compatibilities Excel** estructura distinta a la documentada → importer rompe | Media | Baja | Día 1: Champion entrega archivo, Agente B inspecciona y ajusta parser. Si estructura cambia, US-1A-06-03 baja a 5 SP. |
| R-S3-11 | **Comparator pipeline OCR/embeddings dependencies** (Pillow, sentence-transformers) cargan tarde | Baja | Baja | NO necesarios en S3 (sólo stubs). Defer setup a S4. |
| R-S3-12 | **Conflicto OpenAPI merge** entre Agentes A/B/C/D | Baja | Alta | Agente E como merger final con responsabilidad explícita. Cada agente edita YAML con tag distintivo en commit. |

### Decisiones humanas pendientes (kickoff S3)

1. **ADR-055 firma** (carry-over S2) — bloqueo soft.
2. **Q-09 image rights** sigue abierto — afecta scope S4.
3. **Q-NEW-S3 legal scraping Amazon UAE** — abrir formalmente con Legal MT, owner Champion.
4. **UX firma Pantalla 5 Costes + tab Traducciones** — psierra ya firmó P4 + P10, falta P5 y nueva.
5. **`manual_locked_fields` UI marking → defer S4 explícito** — confirmar con arquitecto.
6. **TI carga FX seed inicial día 1** — owner TI Integración.

## 7. Métricas a trackear durante el sprint

- **Velocity real** (SP done) vs comprometido (35 SP).
- **Burn-down chart** diario; alarma si día 5 < 50 % done.
- **Stories en review** > 3 días → alarma.
- **Coverage delta**: target ≥ 80 % en código nuevo.
- **`match_decisions` populated**: target ≥ 50 dry-runs sobre PIM real al cierre S3.
- **Costos persistidos en `costs`**: target ≥ 100 (importer demo de 100 rows).
- **FX rates en `fx_rates`**: target 4 (seed) + 1-2 históricas para test.
- **Translations approved**: ≥ 20 (ES) al cierre S3.
- **Sprint goal viability**: cada miércoles, demo informal del flujo (importar costos → ver tab Costes → editar breakdown → match dry-run sobre 1 SKU).

## 8. Sprint 4 preview (alto nivel)

Stories candidatas (con racional):

| Story | SP | Racional |
|-------|----|----------|
| US-1A-09-03 (Image mirror real para candidates + OCR Google Vision) | 8 | Pasa de stubs a red real, requiere ADR-055 firmado + Q-09 |
| US-1A-09-04 (Embeddings imagen + texto técnico) | 5 | Etapa 5 del pipeline real |
| US-1A-09-05 (RRF Ranker + Isotonic Calibrator) | 5 | Etapa 6 |
| US-1A-09-06 (VLM Judge Gemini 2.5 Flash audit-grade) | 8 | Etapa 8 — reasoning auditable |
| US-1A-06-04 (Importer fichas técnicas PDF) | 5 | EP-1A-06 datasheets |
| US-1A-02-04-S4 (UI marcado `manual_locked_fields` + tab Auditoría) | 5 | Cierra ficha SKU |
| US-1A-07-03 (audit triggers en costs/translations) | 3 | Append-only enforcement |
| US-1A-07-05 (export CSV firmado FTA) | 5 | VAT compliance entregable |
| Carry-over S3 (RLS, materials importer si bajaron) | 3-6 | Plan B/C |

**Total candidatos S4**: ~50 SP (aplicar selección a 32-40 SP realistas).

**S4 MUST**: US-1A-09-03 + US-1A-09-06 (matching pipeline pasa de stubs a real con VLM judge — primer demo de comparador funcional).

---

## Apéndice A — Mapeo de stories del doc fuente vs S3

| Doc fuente (epics-and-stories v1.1) | Sprint asignado original | S3 backlog refinado | Cambio |
|-------------------------------------|--------------------------|---------------------|--------|
| US-1A-04-02 (costs schema FX trigger) | S2 | US-1A-04-02 (S3) | Slip por capacity S2 (priorizó importer PIM) |
| US-1A-04-03 (POST /costs) | S2 | US-1A-04-03 (S3) | Slip |
| US-1A-04-04 (UI tab Costes) | S2 | US-1A-04-04 (S3) | Slip |
| US-1A-05-01 (currencies seed completo) | S3 | US-1A-05-01-S3 (S3, scoped a admin UI) | Seed minimal ya hecho en US-1A-03-01-S2; aquí cierra admin |
| US-1A-05-02 (fx_rates trigger) | S3 | US-1A-05-02 (S3) | Sin cambios |
| US-1A-05-03 (POST /fx-rates) | S3 | US-1A-05-03 (S3) | Sin cambios |
| US-1A-06-02 (importer costos) | S2 | US-1A-06-02 (S3) | Slip por capacity S2 |
| US-1A-06-03 (importer materials) | S2 | US-1A-06-03 (S3) | Slip |
| US-1A-02-05 (translations) | S1 | US-1A-02-05 (S3) | Doble slip; ahora con state machine completo |
| US-1A-07-02 (RLS finas) | S3 | US-1A-07-02 (S3, stretch) | Sin cambios; stretch goal |
| **NUEVA** US-1A-09-01-S3 | — | Matching pipeline foundation | Story nueva — Apéndice B propone formalizar EP-1A-09 |
| **NUEVA** US-1A-09-02-S3 | — | Channel mirror Amazon UAE stub | Story nueva |
| **NUEVA** US-1A-02-09-FE | — | Wire UI filtros avanzados | Frontend completing S2 backend |

## Apéndice B — TODOs / cosas dudadas

1. **Crear EP-1A-09 (Comparador) en epics-and-stories doc**: actualmente las épicas llegan a EP-1A-08. Las nuevas US-1A-09-01-S3 y US-1A-09-02-S3 necesitan épica formal "Comparador de Competidores Fase 1a foundation" con descripción acortada del pipeline detallado. Acción: PR a `epics-and-stories-mt-pricing-mdm-phase1.md` para añadir EP-1A-09 con las 6+ stories que vendrán S3-S5.

2. **`manual_locked_fields` UI marking defer S4**: confirmar con arquitecto que el campo TEXT[] vive en `products` (S2 lo añadió en migration 0007 según execution-report Gap 2) y que la UI de marcado/desmarcado va en S4 explícitamente. Sin esto, importer respeta el campo pero usuario no puede fijarlo desde UI.

3. **Persistir `import_runs` en BD**: deuda S2 (Gap 5). En S3 va con migración 0012 dentro de US-1A-06-02. Si esa story baja, abrir story dedicada `US-1A-06-08` 2 SP en S4.

4. **UX firma Pantalla 5 Costes**: si sigue draft al día 3 del sprint, decidir "reusar patrón Pantalla 4 (inline edit grid)" para no bloquear US-1A-04-04 frontend.

5. **UX wireframe tab Traducciones**: ux-mockups no tiene pantalla específica. Decisión propuesta: tabla simple con columnas Lang | Status badge | Translated text | Approved by | Actions. Confirmar con UX.

6. **Material compatibilities tabla — schema dinámico**: el Excel tiene N columnas por material (~10-15). ¿Modelo SQLAlchemy con todas las columnas hardcodeadas o usar JSONB `compat_per_material`? Propuesta: JSONB para flexibilidad (Fase 2 puede añadir materiales sin migration), pero pierde índices. Confirmar con arquitecto.

7. **FX seed día 1**: ¿4 currencies × ~3 pares vivos = 12 rows? Mínimo necesario: EUR→AED, USD→AED, SAR→AED, AED→AED (identidad para trigger). Owner: TI Integración via UI US-1A-05-03 una vez merged.

8. **Score weights G2 iniciales**: pipeline doc no fija weights exactos. Propuesta S3: `specs:0.40, text:0.30, brand:0.20, price_band:0.10`. Calibrar con datos reales en S4 (isotonic regression). Documentar en ADR-066.

9. **Q-NEW-S3 legal scraping Amazon UAE**: pregunta nueva a abrir formalmente. ¿Permitido scrape con Bright Data per ToS Amazon UAE? ¿PDPL UAE 2026 nos afecta como procesador? **Owner: Champion + Legal MT**, antes de kickoff S4.

10. **`pipeline_version` en `match_decisions`**: convenio de versionado. Propuesta: `S3-foundation-v1` → `S4-real-stubs-replaced-v1` → ... cada vez que cambia signature/weights, bump version. Auditable.

11. **Endpoint `/match/dry-run` accesible sólo TI en S3**: en S5 cuando llegue UI Tinder-swipe se abrirá a Comercial. Documentar transición.

12. **Costos legales scraping**: Bright Data $1.50/1k success (USD 5-150/mo Amazon UAE). En S3 son $0 (stubs). Champion confirma presupuesto pre-S4.

13. **Tarea Celery `audit_partitions_ensure`**: ya implementada en S2 según execution-report (`app/workers/audit_partitions.py`) — verificar que está en schedule diario 02:00 UTC en docker-compose dev. Monitor en S3.

14. **Storage thumbnails para candidates**: cuando S4 active mirror real, guardarán en `product-images/competitor/{sku}/{listing_id}/` per pipeline doc §5.2. Confirmar TTL 90 días post-decisión humana (FR-IMG-04). En S3 N/A.

15. **Pipeline foundation tests**: target ≥ 25 unit tests + 5 integration. Si modo multi-agente baja a 15 tests por compresión, gap-fix Agente E completa.
