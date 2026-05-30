---
tags: [design, pricing-desk, optimization, drift, diff, celery]
created: 2026-05-31
status: approved
audience: claude-code, backend
target_repo: br-mt-ecommerce
component: mt-pricing-backend
related: ["[[02-target-architecture]]", "[[07-implementation-plan]]", "2026-05-31-pricing-fx-auto-snapshots-f2-design", "2026-05-30-pricing-lineage-freshness-f4-design"]
---

# Diseño — F8: Optimización automática + diff

## 1. Contexto y objetivo
F2 dejó FX automático (`fx_rates`) + snapshots auto. F4 expone frescura/lineage. **F8** (doc 07 §F8, riesgo Medio)
cierra el lazo: cuando los parámetros del canal (FX / comisión / arancel) **derivan** respecto al último
estado optimizado, un **job background** detecta el drift, **re-optimiza en memoria**, calcula un **diff**
("X SKUs cambiarían de esquema, Y de señal"), guarda un **snapshot** de revert y **alerta** al usuario.
**Clave (AC): NO aplica propuestas automáticas** — solo alerta + diff; el humano decide.

**Solo backend** este ciclo. La vista diff 9.7 (UI) es ciclo aparte. F8 **se apoya en F2** (snapshots,
patrón job) y **F4** (modelo de frescura). Rama nueva off `main`.

## 2. Alcance
**Dentro:**
- Tabla `pricing_optimization_runs` — registro/alerta de cada detección de drift con su diff.
- `drift_detector` service: baseline (último snapshot) vs params actuales → re-optimiza ambos → diff por SKU.
- Task Celery `mt.pricing.auto_optimize_check` (periódica) + seed `job_definitions`.
- Endpoints lectura: `GET /pricing/{channel}/optimization-runs` (lista) + `/{run_id}` (detalle diff) +
  `POST /{run_id}/ack` (marcar revisada).
- Settings: umbrales de drift.
- Migración: tabla `pricing_optimization_runs` + seed del job.
- Tests integración + unit.

**Fuera:** UI diff 9.7; aplicar la optimización (sigue siendo el botón manual `optimize/apply` de F2); envío de
email/NOTIFY de la alerta (se registra la fila; la notificación es otro concern); drift de **pe_eur por-SKU**
(requiere baseline de costes por SKU — nota para fase posterior). **Revert** = reutiliza `load_scenario` existente
(no se construye nada nuevo).

## 3. Decisiones de diseño

### D1 — Drift a nivel resultado (no solo delta de parámetro)
El disparador es **el impacto en el resultado**, directamente medible y alineado con el AC ("X SKUs cambiaron de
esquema"):
1. **Baseline** = el `PricingScenario` más reciente del `(channel, selling_model)` (cualquier `kind`), vía
   `snapshot_at DESC`. Su `config_jsonb` tiene `route` (fx_rate, import_tariff_pct, …) + `fees` (commission_pct, …).
2. Reconstruir `RouteParams`/`ChannelFees` desde el `config_jsonb` baseline → correr `ChannelOptimizer` con los
   **productos actuales** → `baseline_results`.
3. Cargar params **actuales** (`ParameterLoader`, que ya lee FX de `fx_rates` por F2) → `current_results`.
4. **Diff** por SKU: comparar `fulfillment_scheme` y `signal`. Contar `skus_scheme_changed`, `skus_signal_changed`.
5. **Dispara alerta** si `skus_scheme_changed + skus_signal_changed ≥ DRIFT_MIN_SKUS` (default 1, configurable)
   **o** algún delta de param supera su umbral (registro de transparencia; ver D3).
- **Por qué a nivel resultado**: "param cambió 0.6%" no siempre mueve precios; "12 SKUs cambian de esquema" sí. Y
  el catálogo es pequeño (~232 SKUs, optimizer ~200 ms) → re-optimizar en el job es barato.

### D2 — Alerta + snapshot, NUNCA auto-aplicar (AC duro)
Al detectar drift:
- `create_auto_snapshot(kind=AUTO_PRE_SYNC_PARAM)` — punto de revert del estado actual (enum ya existe, F1).
- INSERT en `pricing_optimization_runs` con el diff + razones + `baseline_snapshot_id` + `acknowledged_at=NULL`.
- **No** se hace upsert de overrides ni se crean `prices`. El usuario revisa el diff y aplica con el flujo manual.

### D3 — Umbrales (settings, configurables)
```python
DRIFT_MIN_SKUS: int = 1                  # nº mínimo de SKUs con cambio para alertar
FX_DRIFT_PCT: Decimal = Decimal("0.5")   # |Δ fx_rate| % (transparencia)
COMMISSION_DRIFT_PP: Decimal = Decimal("1.0")   # |Δ commission_pct| en puntos
TARIFF_DRIFT_PP: Decimal = Decimal("1.0")       # |Δ import_tariff_pct| en puntos
AUTO_OPTIMIZE_CHECK_CRON: str = "30 1 * * *"    # 01:30 (tras fx-sync 01:00)
```
Los deltas de param se calculan y **guardan en `drift_reasons`** aunque el disparo sea por SKUs — dan contexto
("FX +0.7%, comisión +0.0pp; 12 SKUs cambian de esquema").

### D4 — Idempotencia / ruido
- Si **no hay baseline** (canal sin snapshots) → skip (nada con qué comparar). Log + run no creado.
- Si **0 cambios** → no se crea run (no alerta). Solo se registra en logs.
- Para no duplicar: si ya existe un run `acknowledged_at IS NULL` para el `(channel, selling_model)` con el
  **mismo diff** (mismos contadores y baseline), no se inserta otro (UPDATE `detected_at`). Evita spam diario.

## 4. Modelo de datos — `pricing_optimization_runs`
```
id                  uuid pk
channel_id          uuid fk channels.id
selling_model       enum selling_model ('b2c'|'b2b')
baseline_snapshot_id uuid fk pricing_scenarios.id (nullable)
revert_snapshot_id  uuid fk pricing_scenarios.id (nullable)  -- el auto_pre_sync_param creado
skus_scheme_changed int not null default 0
skus_signal_changed int not null default 0
drift_reasons       jsonb not null default '{}'  -- {fx_pct, commission_pp, tariff_pp, ...}
diff_detail         jsonb not null default '[]'  -- [{sku, old_scheme, new_scheme, old_signal, new_signal}] (cap 200)
detected_at         timestamptz not null default now()
acknowledged_at     timestamptz null
acknowledged_by     uuid fk users.id null
created_at/updated_at (mixins)
índices: (channel_id, selling_model, detected_at desc); parcial (acknowledged_at IS NULL)
```
Tabla `public.*` → Alembic. Sin enums nuevos (usa `selling_model` existente).

## 5. Componentes (archivos)
| Archivo | Responsabilidad | Nuevo/Mod |
|---|---|---|
| `app/db/models/optimization_run.py` | modelo `PricingOptimizationRun` | Nuevo |
| `app/services/pricing/drift_detector.py` | `detect_drift(session, channel_id, selling_model) -> DriftResult` | Nuevo |
| `app/services/pricing/optimization_diff.py` | `diff_results(old, new) -> DiffSummary` (puro, testeable) | Nuevo |
| `app/workers/tasks/pricing_auto_optimize.py` | task `mt.pricing.auto_optimize_check` (todos los canales×modelos) | Nuevo |
| `app/api/routes/channel_pricing.py` | 3 handlers: list, detalle, ack | Mod (rutas nuevas → OpenAPI) |
| `app/schemas/optimization_run.py` | schemas de respuesta | Nuevo |
| `app/core/config.py` | umbrales D3 | Mod |
| `app/services/pricing/scenarios.py` | reutiliza `build_scenario_config` para reconstruir baseline params | Mod menor (helper `route_fees_from_config`) |
| `alembic/versions/20260603_151_optimization_runs.py` | tabla + seed job | Nuevo |

## 6. Flujo
**Job diario (01:30):** para cada `(channel, selling_model)` con baseline:
`drift_detector.detect_drift` → reconstruye params baseline desde `config_jsonb`, optimiza baseline + actual,
`optimization_diff.diff_results` → si `≥ DRIFT_MIN_SKUS` cambios: `create_auto_snapshot(AUTO_PRE_SYNC_PARAM)` +
INSERT `pricing_optimization_runs` (dedup D4). Commit. Nunca aplica.

**Lectura (UI/usuario):** `GET /pricing/{channel}/optimization-runs?selling_model=&unacknowledged=true` → lista;
`GET /…/{run_id}` → diff_detail; `POST /…/{run_id}/ack` → marca revisada. **Revert** → `load_scenario` existente.

## 7. Errores y rendimiento
- Optimizer ×2 por canal×modelo en el job (~400 ms/canal, pocos canales) — aceptable en background.
- `detect_drift` puro salvo lectura de snapshot/productos; el task captura excepciones por canal (un canal que
  falla no tumba el resto; log + continúa). El beat nunca cae (try/except por iteración).
- `diff_detail` capado a 200 SKUs (resto agregado en contadores) — evita JSONB gigante.
- Endpoints GET → `CacheControlMiddleware` aplica; sin headers manuales. Índices cubren los listados.

## 8. Reutilización vs nuevo
| Existe (reutiliza) | Nuevo (F8) |
|---|---|
| `ChannelOptimizer`, `ParameterLoader`, `PriceResult` (.fulfillment_scheme/.signal), `build_scenario_config`, `create_auto_snapshot` + `AUTO_PRE_SYNC_PARAM`, `load_scenario` (revert), patrón task+job_definitions (F2) | tabla `pricing_optimization_runs`, `drift_detector`, `optimization_diff`, task auto-check, 3 endpoints + schemas, settings, migración |

## 9. Pruebas (integración Postgres _151 + unit)
- **optimization_diff** (unit, puro): dos listas de `PriceResult` → cuenta scheme/signal cambiados correctamente; sin cambios → 0.
- **drift_detector** (integración): baseline snapshot con commission distinta → re-optimiza → detecta N cambios; sin baseline → None/skip.
- **task** (integración): con drift → crea snapshot `auto_pre_sync_param` + 1 fila `pricing_optimization_runs`; 2ª corrida con mismo diff → no duplica (dedup D4); sin drift → 0 filas.
- **endpoints**: list (filtra unacknowledged), detalle (diff_detail), ack (set acknowledged_at/by). Permiso `prices:read`/`prices:propose`.
- **migración**: tabla creada, FKs, índices; downgrade limpia. `alembic check` sin drift de modelos.
- Regresión pricing verde; cobertura ≥70%. **OpenAPI**: F8 añade rutas → regenerar spec raíz + `lib/api/types.ts`.

## 10. Decisiones abiertas (resolver en el plan)
- Permiso exacto de los endpoints (`prices:read` para GET, `prices:propose` para ack) — confirmar set de permisos.
- Forma exacta de reconstruir `RouteParams`/`ChannelFees` desde `config_jsonb` (tipos `Decimal` desde str) — el
  plan añade `route_fees_from_config` en `scenarios.py`.
- Cadencia del job: 01:30 diario (tras FX). Evaluable a "tras mutación de param" en una iteración futura (event-driven).
