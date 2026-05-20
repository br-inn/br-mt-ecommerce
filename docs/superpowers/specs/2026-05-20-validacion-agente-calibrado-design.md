# Diseño — Completar `/catalogo/validacion` + Agente de validación calibrado

**Fecha:** 2026-05-20
**Autor:** psierra (con Claude Code)
**Estado:** Propuesta — pendiente de revisión
**Módulo:** `mt-pricing-frontend/app/(app)/catalogo/validacion` + pipeline de matching backend

---

## 1. Contexto y objetivo

`/catalogo/validacion` es la **cola de validación humana** del pipeline de price
intelligence: un revisor compara candidatos scrapeados de Amazon UAE / Noon contra
productos del catálogo MT y los valida o descarta uno a uno.

El backend ya tiene un **pipeline de 3 capas (LLM + visión)** en
`enhanced_match_service.py` que, por cada candidato, calcula un score y una
**decisión** (`deterministic` → auto-validar, `vision_rejected` → descartar,
`human_queue` → revisar). El problema central: **la UI nunca actúa sobre esa
decisión** — todo candidato queda en `pending` y exige un clic humano.

**Objetivo:** dejar el módulo totalmente funcional para su propósito (validar a
escala con poco esfuerzo humano) y construir un **agente de IA semi-autónomo**
que cierre ese lazo, arrancando conservador (modo sombra) y escalando hacia
automatización completa mediante un ciclo de *active learning* calibrado.

---

## 2. Hallazgos del análisis (estado actual)

### 2.1 Brechas funcionales del módulo

| # | Brecha | Impacto |
|---|--------|---------|
| 1 | El footer muestra atajos `V` validar / `X` descartar, pero el handler de teclado (`page.tsx:196-205`) solo conecta `←`/`→` | Atajos muertos |
| 2 | "Siguiente sin validar" solo hace `goNext`, no salta al siguiente SKU *sin validar* | Etiqueta engañosa |
| 3 | Dos `useQuery` distintos (`usePendingSkuQueue` + `sku-queue-stats`) piden el **mismo** `list({status:pending,limit:200})` con queryKeys diferentes | 2 round-trips idénticos (viola regla perf #7 de CLAUDE.md) |
| 4 | `fmtAED` en `page.tsx:65` está sin usar | Código muerto |
| 5 | Validar/descartar nunca setea `label` (accept/reject) ni escribe `golden_labels` | El calibrador y el export del dataset comparador no reciben señal de esta pantalla |
| 6 | Descartar nunca pide motivo (el backend acepta `MatchDiscardRequest.reason`, la UI manda `null`) | Se pierde trazabilidad |
| 7 | No hay acción en bloque — con 20 candidatos `auto_validate`, son 20 clics | Sin escala |
| 8 | `calibrated_confidence` / `review_priority` no se muestran (el backend ya ordena por confianza) | Falta señal de confianza en la UI |
| + | El E2E `tests/e2e/13-validacion-matches.spec.ts` espera el header "Validación humana asistida" — la página renderiza solo "Validación" | Test stale / probablemente rojo |

### 2.2 Estado de la infraestructura de calibración

Existe y es sólido, **pero no está conectado al pipeline en vivo**:

- `IsotonicCalibrator` (Pool Adjacent Violators, pure Python) — fit/calibrate/serialize.
- `ConformalWrapper` (MAPIE o Venn-Abers interno) — `predict_with_interval()` →
  `ConformalPrediction(point_estimate, lower_bound, upper_bound, review_priority)`.
  `alpha=0.02` → objetivo de tasa de falsos positivos < 2%.
  `review_priority`: `low` si `lower > 0.70`, `high` si `upper < 0.50`, `None` (banda gris) en otro caso.
- `CalibratorTrainer` — entrena desde `golden_labels` (mín. 50 muestras; mín. 200 para `ConformalWrapper.fit`),
  computa Brier + ECE, persiste vía `CalibratorStorage`.
- Tablas `golden_labels` + `calibrator_versions`; columnas `calibrated_confidence`,
  `conf_lower`, `conf_upper`, `review_priority` en `match_candidates`.

**Lo que NO está conectado:**

- `calibrated_confidence` hoy se escribe como `sigmoid(rerank_score)` del cross-encoder
  (`match_service.py:308-315`) — **no** es la salida de un `IsotonicCalibrator` entrenado.
- `ConformalWrapper` nunca se invoca → `conf_lower`/`conf_upper`/`review_priority` quedan NULL.
- **Nadie escribe `golden_labels` desde la UI.** Ni `/catalogo/validacion` (API `matches`,
  basada en `status`) ni la API `human-queue` (`HumanQueueService.label_match` setea
  `MatchCandidate.label` pero no `golden_labels`). El calibrador no tiene de qué entrenar.
- Existen **dos conceptos de validación desconectados**: la pantalla (API `matches`,
  `status`) y la API `human-queue` (`label` + `calibrated_confidence`).

**Conclusión:** el enfoque elegido ("C — calibrado desde el inicio") requiere un
**bootstrap obligatorio**: hasta acumular ~200 `golden_labels`, el agente corre con
el signal sin calibrar. Eso coincide exactamente con el modo sombra elegido — la
fase de sombra *es* el bootstrap que genera el dataset de entrenamiento.

---

## 3. Decisiones de diseño (acordadas)

| Decisión | Elección | Implicación |
|----------|----------|-------------|
| Autonomía del agente | **Semi-autónomo con umbral** | Auto-valida/descarta los extremos, deja la banda gris al humano |
| Disparador | **Inline en el scrape** | El agente aplica la decisión al final de `refresh_sku_task` |
| Arranque | **Modo sombra → activo** | Fase 1 registra sin aplicar; un flag lo activa cuando las métricas convencen |
| Señal de confianza | **Conformal (C)** | Umbral sobre `review_priority` del `ConformalWrapper`; score crudo solo como fallback de bootstrap |
| Infra config/auditoría | **Completa (híbrido B+C)** | Tabla `match_agent_config` (singleton) + tabla `match_agent_decisions` (serie temporal) |

**Alcance del entregable:** se construye **todo el código** de las 3 fases (agente,
wiring conformal, UI, métricas, tab de auditoría, tests). El sistema **ships en
Fase 0 (modo sombra)**; las Fases 1 y 2 se activan por configuración cuando el
dataset de labels crezca. El módulo queda totalmente funcional desde el día 1; el
agente trabaja de forma conservadora.

---

## 4. Arquitectura — Agente con active learning en 3 fases

```
scrape → pipeline 3-capas (score) → ConformalWrapper (calibrated_confidence + review_priority)
       → MatchValidationAgent (veredicto: auto-validar / auto-descartar / banda gris)
       → [modo sombra: registra en match_agent_decisions]
       → [modo activo: aplica a match_candidates inline]
humano valida la banda gris → golden_labels  ← señal de entrenamiento
nightly CalibratorTrainer → nueva CalibratorVersion → promote → mejor calibración
```

| Fase | Qué corre | Gatillo de avance |
|------|-----------|-------------------|
| **0 — Bootstrap / sombra** | Módulo completo; cada validar/descartar escribe `golden_labels`. El agente calcula veredicto con el signal sin calibrar (`_enhanced.auto_validate` + score) y lo **registra** en `match_agent_decisions` sin aplicar. Panel de métricas muestra labels acumulados (X / 200) + precisión de sombra. | ≥ 200 `golden_labels` |
| **1 — Calibración** | `CalibratorTrainer.train()` → `ConformalWrapper.fit()` → promover `CalibratorVersion`. Se conecta `predict_with_interval()` al scoring → puebla `conf_lower`/`conf_upper`/`review_priority`. El agente cambia su función de decisión a la señal conformal. | Métricas de sombra OK (Brier/ECE bajos, precisión aceptable) |
| **2 — Activo** | `match_agent_config.mode = 'active'`. El agente aplica decisiones inline en `refresh_sku_task`. Tab "Auto-validados" + revertir. Reentrenamiento nightly con `auto_promote=True`. | — |

El **diferencial** frente a soluciones de mercado: la banda de auto-decisión se
deriva de **conformal prediction con garantía de cobertura** (`alpha=0.02` →
FP < 2%), no de un umbral heurístico fijo.

---

## 5. SP1 — Completar el módulo

Fichero principal: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx` +
`_components/*`.

| # | Fix | Detalle |
|---|-----|---------|
| 1 | Teclado `V`/`X` | Extender el handler de `page.tsx:196-205`: `V` → validar el primer candidato `pending` visible; `X` → descartar |
| 2 | "Siguiente sin validar" | Cambiar `goNext` por una función que avanza al próximo SKU de la cola con `candidateCount > 0` pendiente |
| 3 | Dedupe de queries | Un único hook `useSkuQueue()` que devuelve `{ skus, statsBySku }` desde **una** llamada `list({status:pending,limit:200})`; eliminar `sku-queue-stats` |
| 4 | Código muerto | Borrar `fmtAED` no usado en `page.tsx` |
| 5 | Cerrar el lazo de feedback | Validar → `status=validated` + `label=accept` + upsert `golden_labels(label=1)`; descartar → `status=discarded` + `label=reject` + `golden_labels(label=0)`. Ver §6.4 (cambios backend) |
| 6 | Motivo de descarte | Mini-`ConfirmDialog` con `<textarea>` opcional; pasa `reason` a `discardApi` |
| 7 | Acción en bloque | Barra superior "Aceptar N recomendados por el agente" — valida en lote todos los candidatos con `_agent.verdict='auto_validate'` del SKU actual |
| 8 | Señal de confianza en la card | `CandidateCard` muestra `calibrated_confidence` y un chip de `review_priority` (low=verde, high=rojo, gris=banda de revisión) |
| + | E2E stale | Alinear `13-validacion-matches.spec.ts` con el header real (o ajustar el header de la página) — ver SP3 |

---

## 6. SP2 — `MatchValidationAgent`

### 6.1 Servicio

Nuevo: `app/services/matching/validation_agent.py` — clase `MatchValidationAgent`.
Se invoca **inline al final de `refresh_sku_task`** (worker), después de que el
pipeline puntuó y persistió los candidatos.

**Función de decisión:**

- **Fase 0 (bootstrap, calibrador no entrenado):** usa `_enhanced.auto_validate`
  + `score`. `auto_validate=True` → veredicto `auto_validate`; `vision_rejected`
  → `auto_discard`; resto → `human` (banda gris).
- **Fase 1+ (calibrador activo):** carga el `IsotonicCalibrator` activo vía
  `CalibratorStorage.load_active()`, envuelve en `ConformalWrapper`, llama
  `predict_with_interval(score)`:
  - `review_priority == 'low'` → `auto_validate`
  - `review_priority == 'high'` → `auto_discard`
  - `review_priority is None` (banda gris) → `human`
  - `method == 'vision_rejected'` (different_type) → `auto_discard` siempre (filtro negativo duro)

**Modo (de `match_agent_config`):**

- `shadow` → registra el veredicto en `match_agent_decisions`, **no toca**
  `match_candidates.status`.
- `active` → además aplica: `status` → `validated`/`discarded`, estampa
  `specs_jsonb._agent = {verdict, mode, signal, calibrator_version, decided_at, applied: true}`.

> **El agente NO escribe `golden_labels`.** El calibrador debe entrenarse solo con
> verdad humana — si las decisiones del propio agente alimentaran el dataset se
> crearía un lazo de confirmación que amplifica sus errores. `golden_labels` se
> escribe únicamente cuando un humano valida/descarta (§6.4).

El agente nunca lanza excepción hacia el worker — si falla, deja el candidato
`pending` y registra el error en `match_agent_decisions`.

### 6.2 Modelo de datos (migraciones Alembic — `public.*`)

**Tabla `match_agent_config`** — fila singleton (config editable sin redeploy):

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | smallint PK | siempre `1` (CHECK `id = 1`) |
| `mode` | varchar(16) | `shadow` \| `active` (CHECK) |
| `alpha` | numeric(4,3) | objetivo FP del `ConformalWrapper` (default `0.02`) |
| `min_labels_gate` | integer | labels mínimos antes de permitir `active` (default `200`) |
| `updated_by` | uuid FK users | audit |
| `updated_at` | timestamptz | |

**Tabla `match_agent_decisions`** — serie temporal de cada veredicto:

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | uuid PK | |
| `candidate_id` | uuid FK match_candidates (CASCADE) | |
| `product_sku` | text | desnormalizado para query rápida |
| `verdict` | varchar(16) | `auto_validate` \| `auto_discard` \| `human` |
| `mode` | varchar(16) | `shadow` \| `active` (modo al decidir) |
| `applied` | boolean | `true` si tocó `match_candidates` |
| `signal` | varchar(24) | `conformal` \| `bootstrap` |
| `score` | integer | score crudo en el momento |
| `calibrated_confidence` | numeric(5,4) nullable | si había calibrador |
| `review_priority` | varchar(16) nullable | |
| `calibrator_version` | text nullable | versión usada |
| `human_outcome` | varchar(16) nullable | `validated`/`discarded` real del humano — se rellena al validar (para precisión de sombra) |
| `created_at` | timestamptz | |

Índices: `(product_sku)`, `(created_at)`, `(verdict, mode)`.

> **Split de migraciones:** ambas tablas son `public.*` → Alembic. No tocan
> `auth.*`/`storage.*`. Enums como columnas `varchar` + `CHECK` (no `pg enum`),
> consistente con `match_candidates`.

### 6.3 Endpoints nuevos (router `matches`)

- `GET /api/v1/matches/agent/config` — lee la fila singleton (`matches:read`).
- `PUT /api/v1/matches/agent/config` — actualiza `mode`/`alpha`/`min_labels_gate`
  (`matches:write`). Rechaza `mode=active` si `golden_labels` < `min_labels_gate`.
- `GET /api/v1/matches/agent/metrics` — devuelve: total `golden_labels`,
  progreso hacia el gate, **precisión de sombra** (de `match_agent_decisions`
  donde `human_outcome` no es NULL: veredicto-agente vs. resultado-humano),
  salud del calibrador activo (Brier/ECE/versión/`trained_on_count`).
- `POST /api/v1/matches/{id}/revert` — solo candidatos con `_agent.applied=true`:
  vuelve a `status=pending` y limpia `_agent`. No toca `golden_labels` (el agente
  no escribe ahí); el candidato vuelve a la cola para que un humano decida, y esa
  decisión humana sí generará el `golden_label`.

### 6.4 Cambios en el backend existente

- `MatchService.validate_candidate` / `discard_candidate`: además de mover
  `status`, setear `label` (`accept`/`reject`) y hacer `GoldenLabelRepository.upsert`
  (`label` 1/0, `score = score/100`). Si existe una fila en `match_agent_decisions`
  para ese candidato, rellenar `human_outcome`.
- `refresh_sku_task` (`app/workers/tasks/comparator.py`): tras puntuar, invocar
  `MatchValidationAgent.run(sku)`.
- Wiring conformal (Fase 1): en el path de scoring de `match_service.py`, tras
  obtener el score, si hay calibrador activo → `ConformalWrapper.predict_with_interval`
  → persistir `conf_lower`/`conf_upper`/`review_priority`/`calibrated_confidence`.

### 6.5 Feature flags / config

- `MATCH_AGENT_ENABLED` (settings, env) — flag maestro. `false` → el agente no corre.
- `mode` (`shadow`/`active`) vive en `match_agent_config` (DB, sin redeploy).
- El gate `min_labels_gate` impide pasar a `active` sin dataset suficiente.

---

## 7. SP3 — Pruebas automatizadas

### 7.1 E2E (Playwright — `mt-pricing-frontend/tests/e2e`)

- **Auditar y arreglar** `13-validacion-matches.spec.ts` (header stale).
- Casos nuevos: atajos `V`/`X`; "siguiente sin validar"; acción en bloque
  "Aceptar N recomendados"; tab "Auto-validados" + revertir; panel de métricas
  del agente; descartar con motivo.
- Extender los mocks `installMatchesMocks` / `FAKE_MATCHES` en
  `tests/e2e/fixtures/seed-extended.ts` (incluir `_agent`, `_enhanced`,
  `review_priority`, endpoints `agent/config`, `agent/metrics`, `revert`).

### 7.2 Tests backend (pytest — `mt-pricing-backend/tests`)

- `MatchValidationAgent`: decisión en bootstrap vs conformal; `shadow` no toca
  `status`; `active` aplica; idempotencia (re-ejecución no duplica decisiones);
  `vision_rejected` siempre descarta; fallo del agente deja `pending`.
- Wiring `ConformalWrapper` en scoring → columnas pobladas.
- `validate`/`discard` → upsert en `golden_labels` + `human_outcome` rellenado.
- Endpoints `agent/config` (gate de `min_labels_gate`), `agent/metrics`, `revert`.
- Migraciones: revisar con `migration-reviewer` (split `public.*`, CHECKs, índices, reversibilidad).

---

## 8. Soluciones de mercado (referencia)

El patrón **"match-confidence threshold + auto-match band + human review queue +
active learning"** es estándar en *competitive price intelligence*:

| Solución | Qué hace relevante |
|----------|--------------------|
| **Intelligence Node** | Product matching con IA, confidence scoring, cola de revisión humana |
| **DataWeave** | Competitive intelligence; ML matching con "match confidence" + review workflow |
| **Wiser (WisePricer)** | Price intelligence; matching automatizado de productos |
| **Competera** | Pricing con IA; ML matching de competidores |
| **Prisync / Price2Spy** | Monitoreo de precios; matching asistido (manual + sugerido) |
| **Skuuudle / 42Signals** | Product matching as a service |

El ciclo human-in-the-loop labeling lo formalizan plataformas de *data labeling* y
*active learning*: **Label Studio**, **Snorkel**, **Scale AI** — el revisor humano
genera etiquetas que reentrenan el modelo.

**Diferencial del diseño:** la banda de auto-decisión se deriva de **conformal
prediction con garantía de cobertura empírica** (≥ 1 − α). La mayoría de productos
comerciales usan umbrales heurísticos sin garantía estadística de la tasa de error.

---

## 9. Plan de ejecución con agentes en paralelo

Tras aprobar este spec → `writing-plans` genera el plan de implementación →
`subagent-driven-development` ejecuta en **3 tracks**:

| Track | Alcance | Depende de |
|-------|---------|------------|
| **T0 — Contratos** | Definir schemas Pydantic + tipos TS de `agent/config`, `agent/metrics`, `revert`, `_agent` block | — |
| **T1 — Backend** | Migraciones (`match_agent_config`, `match_agent_decisions`), `MatchValidationAgent`, wiring conformal, golden_labels en validate/discard, endpoints, pytest | T0 |
| **T2 — Frontend** | Brechas SP1, UI del agente (barra en bloque, chips de confianza, tab "Auto-validados", panel de métricas, motivo de descarte) | T0 |
| **T3 — Tests E2E** | Arreglar/extender `13-validacion-matches.spec.ts`, mocks `seed-extended.ts` | T0, contratos de T2 |

T1/T2/T3 corren en paralelo una vez fijado T0. Cierre: redeploy de contenedores
afectados (`mt-backend`, `mt-worker`, `mt-beat`, `mt-frontend`) + migración
(`./infra/scripts/migrate.sh`), verificación `curl .../health/live`.

---

## 10. Fuera de alcance (YAGNI)

- No se fuerza el entrenamiento del calibrador sin ≥ 200 labels — el bootstrap corre solo.
- No se tocan el scraper ni los adapters (Amazon UAE / Noon).
- No se fusionan las APIs `human-queue` y `matches` en una sola — solo se conecta
  el feedback (`golden_labels`). Una refactorización mayor de ambas queda fuera.
- No se implementa `cache_control` de Anthropic — los prompts del pipeline son
  cortos (< 600 tokens), por debajo del mínimo de caché (regla #9 de CLAUDE.md).
- No se construye un panel de administración del calibrador nuevo — ya existe
  `admin_calibrator.py`.

---

## 11. Criterios de aceptación

1. Las 8 brechas de SP1 cerradas; el E2E `13-validacion-matches.spec.ts` pasa.
2. Cada validar/descartar escribe `golden_labels` y `match_candidates.label`.
3. `MatchValidationAgent` corre inline en `refresh_sku_task`, en modo `shadow`
   por defecto, y registra cada veredicto en `match_agent_decisions`.
4. El panel de métricas muestra labels acumulados, progreso al gate y precisión de sombra.
5. El wiring conformal puebla `conf_lower`/`conf_upper`/`review_priority` cuando
   hay un calibrador activo; sin él, el agente cae al signal de bootstrap sin error.
6. Pasar a `mode=active` está bloqueado hasta alcanzar `min_labels_gate`.
7. En modo `active`: el tab "Auto-validados" lista lo que tocó el agente y
   "revertir" devuelve a `pending` + re-juzga el `golden_label`.
8. Suite pytest backend + E2E Playwright en verde; migraciones revisadas por `migration-reviewer`.

---

## 12. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| El dataset de labels nunca llega a 200 → el agente queda en bootstrap indefinido | El modo sombra es funcional y útil igualmente (recomienda + acción en bloque); el progreso es visible en el panel |
| Calibrador mal entrenado auto-valida basura al pasar a `active` | Gate `min_labels_gate` + precisión de sombra revisable antes del flip; `revert` siempre disponible; `alpha=0.02` conservador |
| `MAPIE` / `numpy` no instalados en el contenedor | `ConformalWrapper` ya cae a Venn-Abers interno (pure Python) sin numpy |
| Doble ejecución del agente sobre el mismo candidato | Idempotencia: `match_agent_decisions` se consulta antes de re-decidir; aplicar solo si `status=pending` |
| Migración sobre tabla grande `match_candidates` | Las tablas nuevas son independientes; no se altera `match_candidates` salvo lectura/escritura de columnas ya existentes |
