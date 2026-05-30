---
tags: [design, pricing-desk, fx, ecb, snapshots, celery]
created: 2026-05-31
status: approved
audience: claude-code, backend
target_repo: br-mt-ecommerce
component: mt-pricing-backend
related: ["[[02-target-architecture]]", "[[07-implementation-plan]]", "2026-05-30-pricing-provenance-audit-f1-design", "2026-05-30-pricing-lineage-freshness-f4-design"]
---

# Diseño — F2: FX auto + Snapshots auto

## 1. Contexto y objetivo
F0 cableó el coste real (MAP→engine); F1 dejó provenance/audit/`source_health`; F4 expone lineage/frescura.
**F2** resuelve dos síntomas visibles del Desk (doc 07 §F2, riesgo Bajo):

1. **FX stale / dual**: el engine lee `trade_route_params.fx_rate` (un número tecleado a mano) en vez de la tabla
   de primer nivel `fx_rates`. F2 conecta el engine a `fx_rates` y añade un **job diario** que la puebla desde
   **ECB** (con provenance `tesoreria_fx` + `source_health`).
2. **Pérdida de trabajo al optimizar/importar**: no hay snapshot previo. F2 crea **snapshots auto**
   (`auto_pre_optimization` / `auto_pre_import`) antes de mutar, recuperables, con limpieza > 90 d.

**Solo backend.** Drawers/badges de UI = ciclo aparte. F2 **se apoya en F1** (provenance helpers, `source_health`,
enum `SnapshotKind`). Rama nueva off `main` (F1+F4 ya mergeados).

## 2. Alcance
**Dentro:**
- `EcbFxAdapter` — fetch EUR→USD de ECB (XML diario) → deriva EUR→AED vía peg USD/AED.
- Task Celery `mt.fx.sync_daily` + seed `job_definitions` (cron diario) → `fx_rates` (source='ecb') con provenance.
- Engine/loader leen FX de `fx_rates` (`rate_at('EUR','AED', now)`); `trade_route_params.fx_rate` = **fallback**.
- Migración: **backfill** del `fx_rate` actual de cada ruta → `fx_rates` (source='manual') si no hay rate activo;
  seed de los 2 `job_definitions`. (La fila `source_health(tesoreria_fx)` **ya la sembró F1**, SLA 1440 — el job
  solo la **UPDATE**.)
- Snapshots auto antes de `optimize/apply` e `import/apply` (`PricingScenario` kind=`auto_pre_*`, `retention_until`).
- Task Celery `mt.pricing.cleanup_auto_snapshots` + seed job → borra snapshots auto con `retention_until < now`.
- Tests integración (Postgres) + unit (adapter con httpx mockeado).

**Fuera:** badges/drawer UI; optimización automática por umbral (F5); override manual de FX vía endpoint nuevo
(ya existe `POST` de `create_rate` con `source='manual'`; el override se hace con eso — F2 no añade endpoint).
**Sin cambios en `app/api/routes/` ni `app/schemas/`** ⇒ **no hay drift de OpenAPI** (verificar igualmente).

## 3. Decisiones de diseño

### D1 — `fx_rates` como única verdad (sin columna nueva)
- El engine lee el rate **vigente** `EUR→AED` de `fx_rates` vía `FXRateService.rate_at('EUR','AED', now)`.
- **`source` distingue origen**: `ecb` = automático; `manual` = override humano. El **último rate activo gana**
  (el trigger `fx_rates_close_previous_trg` cierra el anterior). El badge "manual desde X" se deriva de
  `source='manual'` en el rate activo (lo consumirá la UI vía F4 `freshness`; F2 no lo expone).
- **Fallback**: si `fx_rates` no tiene rate activo `EUR→AED` (p.ej. canal nuevo) → engine usa
  `trade_route_params.fx_rate` (comportamiento legacy). Esto hace la convergencia **no destructiva**.
- **Backfill no destructivo**: la migración inserta el `fx_rate` actual de cada `trade_route_params` distinto en
  `fx_rates` como `EUR→AED`, `source='manual'`, `effective_from=now()`, **solo si no existe ya un rate activo**.
  Resultado: en el deploy los precios **no cambian** (engine lee el mismo número, ahora desde `fx_rates`); el job
  ECB lo actualiza al día siguiente.
- **Por qué sin columna nueva**: reutiliza `fx_rates.source` + el trigger + `FXRateService`. Menos superficie,
  menos riesgo, alineado con doc 02 §179 ("el Channel Engine pasa a leer FX de `fx_rates`").

### D2 — ECB no cotiza AED → peg USD/AED
ECB publica *euro reference rates* (~30 divisas, **incluye USD, no AED**). AED está **clavado a USD** desde 1997
por el UAE Central Bank: **1 USD = 3.6725 AED**. Por tanto:
```
EUR→AED = (EUR→USD de ECB) × USD_AED_PEG
```
- `USD_AED_PEG` = constante configurable en `app/core/config.py` (`FX_USD_AED_PEG: Decimal = Decimal("3.6725")`),
  por si el banco central revisa el peg.
- Fuente ECB: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` (XML, sin auth, 1 req/día).
- `source_ref` de la observación = `f"ecb:{ecb_date}:eurusd={eur_usd}"` para trazabilidad del cálculo.

### D3 — Idempotencia del job
- El job comprueba si ya existe un rate `EUR→AED` `source='ecb'` con `effective_from` del **día de hoy** (UTC);
  si existe, **no inserta** (evita duplicados en reintentos). Actualiza `source_health` igualmente.
- Falla controlada: si ECB no responde / parsea mal → `source_health.last_error` poblado,
  `last_sync_success_at` intacto; **no** lanza excepción que tumbe el beat (log + return dict con `status:error`).

### D4 — Snapshots auto: reutiliza F1
- `SnapshotKind` ya tiene `AUTO_PRE_OPTIMIZATION` / `AUTO_PRE_IMPORT`; el índice único parcial solo cubre
  `manual_a/b` ⇒ se permiten **N** snapshots auto por slot. **Sin migración de enum/índice.**
- Antes de persistir en `apply_optimization` (y en el import/apply), insertar un `PricingScenario` con el
  **estado actual** (mismo `config_jsonb` que arma `save_scenario`), `kind=auto_pre_*`, `slot` libre (se usa `'A'`
  por convención de auto-snapshot; el índice no lo restringe para auto), `retention_until = now + 90d`.
- Helper compartido `build_scenario_config(session, channel_id, selling_model)` extraído de `save_scenario` para
  no duplicar el armado del snapshot (DRY).

## 4. Componentes (archivos)
| Archivo | Responsabilidad | Nuevo/Mod |
|---|---|---|
| `app/services/fx/ecb_adapter.py` | `EcbFxAdapter.fetch_eur_aed() -> EcbQuote` (httpx+tenacity, parsea XML, aplica peg) | Nuevo |
| `app/services/fx/fx_sync_service.py` | `sync_ecb_eur_aed(session)` — orquesta adapter→`create_rate`→observation→`source_health` | Nuevo |
| `app/workers/tasks/fx.py` | `@celery_app.task mt.fx.sync_daily` (asyncio.run → fx_sync_service) | Nuevo |
| `app/workers/tasks/pricing_snapshots.py` | `@celery_app.task mt.pricing.cleanup_auto_snapshots` | Nuevo |
| `app/services/pricing/loader.py` | leer `fx_rates` (rate_at) con fallback a `route_row.fx_rate` | Mod |
| `app/services/pricing/scenarios.py` | `build_scenario_config()` + `create_auto_snapshot(kind)` (DRY desde route) | Nuevo |
| `app/api/routes/channel_pricing.py` | `apply_optimization` + import/apply llaman `create_auto_snapshot` | Mod (no firma) |
| `app/core/config.py` | `FX_USD_AED_PEG`, `ECB_FX_URL`, `AUTO_SNAPSHOT_RETENTION_DAYS=90` | Mod |
| `alembic/versions/2026XXXX_15X_fx_backfill_and_jobs.py` | backfill fx_rates + upsert source_health(tesoreria_fx) + seed 2 jobs | Nuevo |

## 5. Flujo
**FX diario:** beat lee `job_definitions(mt.fx.sync_daily)` → task → `fx_sync_service.sync_ecb_eur_aed`:
`EcbFxAdapter.fetch_eur_aed()` → `FXRateService.create_rate(EUR,AED,rate,source='ecb',actor=system)` →
`record_observation(tesoreria_fx, fx_rates, rate, source_ref)` → update `source_health(tesoreria_fx)`.

**Pricing:** `loader.load_route_and_fees` → `FXRateService.rate_at('EUR','AED', now)` → si hay, `RouteParams.fx_rate =`
ese rate; si no, `route_row.fx_rate`. El resto del engine **no cambia** (sigue usando `route.fx_rate`).

**Optimize/Import:** handler → `create_auto_snapshot(session, channel_id, selling_model, kind)` **antes** de
upsert de overrides/precios → procede. Cleanup nightly borra `kind LIKE 'auto_%' AND retention_until < now`.

## 6. Errores y rendimiento
- Adapter ECB: timeout 30 s, 3 reintentos (tenacity, backoff). Error → `source_health.last_error`, no excepción al beat.
- `rate_at` ya lanza `FXRateNotFoundError`; el loader lo captura y cae al fallback (no 500 en pricing).
- Backfill: 1 query por par distinto (pocos canales); idempotente (`WHERE NOT EXISTS rate activo`).
- Auto-snapshot: 1 INSERT extra por optimize/import (barato, < 5 ms con datos en memoria).
- Sin headers cache nuevos (middleware ya aplica). Loader: +1 query `fx_rates` por carga de ruta — indexado
  (`idx_fx_active`), ~sub-ms en UAE.

## 7. Pruebas (integración Postgres _15X + unit)
- **adapter** (unit, httpx mock): XML ECB de ejemplo → `EUR→AED = eur_usd × 3.6725` correcto; 5xx → reintenta→error.
- **fx_sync_service** (integración): inserta rate `source='ecb'`, observación `tesoreria_fx`, `source_health` poblado;
  2ª corrida mismo día = idempotente (no duplica).
- **loader**: con rate `fx_rates` activo → engine usa ese; sin rate → usa `route_row.fx_rate` (fallback).
- **backfill (migración)**: tras upgrade, cada ruta con `fx_rate` tiene rate activo `EUR→AED source='manual'`; precio
  del engine **idéntico** pre/post backfill (test de no-regresión de precio).
- **auto-snapshot**: `optimize/apply` crea `PricingScenario kind='auto_pre_optimization'` recuperable con
  `retention_until≈now+90d`; import/apply crea `auto_pre_import`.
- **cleanup**: snapshot auto con `retention_until` pasado → borrado; `manual_a/b` y auto recientes → intactos.
- Regresión: suite de pricing verde; cobertura ≥ 70 %.
- **OpenAPI**: F2 no toca rutas/schemas → spec sin cambios (verificar `export_openapi` no produce diff).

## 8. Reutilización vs nuevo
| Existe (reutiliza) | Nuevo (F2) |
|---|---|
| `fx_rates`+trigger, `FXRateService` (rate_at/create_rate), `SnapshotKind` (auto_*), `PricingScenario`, provenance helpers (`record_observation`/`emit_audit`), `source_health`, patrón job_definitions+task (calibrator) | `EcbFxAdapter`, `fx_sync_service`, 2 tasks Celery, `scenarios.py` (build/create_auto_snapshot), loader seam, migración backfill+seeds, config FX |

## 9. Decisiones abiertas (resolver en el plan)
- **Actor "system"** para `create_rate` del job: `FXRateService.create_rate` exige `actor: User`. Opciones: (a) usuario
  de sistema sembrado, (b) relajar a `actor: User | None` + `created_by` nullable (la columna ya es nullable). El plan
  elige (b) si no rompe audit, evitando sembrar un usuario fantasma; el `audit_events.actor_id` quedará NULL (válido).
- **Slot de auto-snapshot**: usar `'A'` fijo (el índice no restringe auto) vs un slot dedicado. El plan fija `'A'`.
- **Import/apply**: confirmar el handler exacto del import (nombre/ruta en `channel_pricing.py`) donde insertar el
  `auto_pre_import` (el explore lo ubicará en el plan).
