# Proceso end-to-end — MT Middle East MDM + Pricing

**Fecha**: 2026-05-12  
**Proyecto**: mt-pricing-mdm-phase1  
**Estado sprint**: Fase 1 + Fase 1.5 completas (S0–S11, todos los epics `done`)

---

## Visión general

La aplicación es un **MDM + Motor de Pricing multi-canal** para MT Middle East. Toma datos de productos desde Excel/fichas técnicas, los enriquece con IA, calcula precios para canales externos (Amazon UAE, Tradeling), los pasa por aprobación interna y los exporta.

```
Fuentes externas              MT Interno                      Canales
─────────────────    ─────────────────────────────────    ──────────────
Excel v5.1        →  [1] IMPORT PIM          │            Amazon UAE
Fichas técnicas   →  [2] ENRIQUECIMIENTO     │            Tradeling
Amazon SP API     →  [3] PRICING ENGINE      │            (F2: otros)
Tradeling API     →  [4] APROBACIÓN          │
Bright Data       →  [5] CANAL MANAGEMENT    │
                     [6] EXPORT / PUBLISH    ─────────────►
                     [7] AUDIT TRAIL
```

---

## [1] Importación de datos (PIM)

**Actores**: Comercial / TI MT  
**Routes**: `imports`, `imports_costs`, `imports_datasheets`, `imports_materials`

- Sube Excel (v5.1 template) → column mapper detecta cabeceras automáticamente
- Parser extrae SKUs, descripciones, atributos, dimensiones, materiales
- pdfplumber extrae tablas de fichas técnicas PDF
- Crea/actualiza productos en `public.products` + atributos EAV en `product_attributes`
- Genera `import_run` con estado, errores por fila; dry-run disponible antes de aplicar
- Idempotente: mismo archivo 2× no duplica (por `idempotency_key`)

---

## [2] Enriquecimiento del producto (Pipeline IA)

**Actores**: Sistema automático (Celery workers)  
**Routes**: `admin_pim_quality`, `admin_manufacturers`, `matches`, `graphrag`

```
Producto nuevo/actualizado
        │
        ▼
[Price Sanity] → filtro P10/P90 pre-VLM (descarta outliers)
        │
        ▼
[VLM Judge] → claude-sonnet-4-6 valida imagen vs ficha técnica
        │
        ▼
[Reverse Image Search] → CLIP detecta duplicados / variantes
        │
        ▼
[Knowledge Graph] → Neo4j: product_equivalences + compatibilidades
        │
        ▼
[Comparador] → matchea vs Amazon/Tradeling → candidatos con score
        │
        ▼
Producto "enriquecido" listo para pricing
```

Cada paso actualiza columnas en `products` (`vlm_score`, `ris_flags`, `kg_node_id`, `match_confidence`).
El dashboard de calidad PIM muestra cobertura por familia.

---

## [3] Motor de pricing

**Actores**: Sistema automático + Comercial (manual override)  
**Routes**: `pricing.py`, `pricing_engine.py`  
**Servicios**: `app/services/pricing/` (8 módulos)  
**Modelos**: `prices`, `costs`, `fx_rates`, `schemes`, `exception_rules`, `price_approval_events`

### Flujo de cálculo

```
POST /pricing/prices  (propose_price)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 1 — Resolución de inputs                                  │
│  PricingService.propose_price()                                 │
│  · Carga Product (ORM) por SKU                                  │
│  · Carga Cost activo: costs WHERE status='active'               │
│    AND sku=SKU AND scheme_code=SCHEME                           │
│    (si no existe → PricingDomainError 404)                      │
│  · Carga FX Rate vigente: fx_rate_at(currency_origin, 'AED',    │
│    effective_at) — índice idx_fx_active (effective_to IS NULL)  │
│  · Carga Channel por code                                       │
│  · Carga CostScheme por code (FBA/FBM/DIRECT_B2C/…)            │
│  · Carga ExceptionRules activas para (channel_id, scheme_code)  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 2 — PricingRuleEngine.calculate()                         │
│  app/services/pricing/rule_engine.py                            │
│                                                                 │
│  2.1 Conversión AED↔EUR (fx_eur_aed — de fx_rates)             │
│  2.2 Cálculo de mediana (candidatos comparador si disponibles)  │
│  2.3 Cálculo margen_pct = (pvp - total_costes) / pvp           │
│                                                                 │
│  2.7/2.8 PVP_MIN — dos ramas:                                   │
│    · Excel master (pvp_min_viable_aed del master_data)          │
│    · Fórmula global: (coste + logística + FBA_fee) /            │
│                      (1 − VAT 5% − referral 13% −              │
│                           bancos 1.5% − devoluciones 4%)        │
│      FBA fee por banda peso: <0.5kg→8 AED / <2kg→14 / ≥2→35    │
│                                                                 │
│  2.9 Análisis candidatos comparador                             │
│    (median_aed, best_score, delivery_advantage_days, n_china…)  │
│                                                                 │
│  2.10-2.14 Política agresiva (en orden de precedencia):         │
│    premium_velocidad_alta   → mediana × 1.15 (ventaja ≥7d)     │
│    premium_velocidad_media  → mediana × 1.05 (ventaja ≥3d)     │
│    aggressive_match_high    → max(mediana×0.98, PVP_MIN×1.05)  │
│    aggressive_match_low     → max(mediana×1.10, PVP_MIN×1.10)  │
│    aggressive_g2_no_match   → max(coste×mult_G2, PVP_MIN×1.15) │
│      · stainless mult=2.8 / cast_iron=3.0 / default=2.5        │
│    aggressive_g1_no_match   → PVP_MIN × 1.15 (fallback)        │
│                                                                 │
│  Channel multiplier (por defecto: amazon_uae=1.0, b2b=0.85…)   │
│                                                                 │
│  2.16 Cap superior + floor:                                     │
│    · CAP: pvp > mediana×1.20 → clamp (warning)                 │
│    · FLOOR: pvp < PVP_MIN → forzar PVP_MIN (critical alert)    │
│                                                                 │
│  2.4 Refit master (si master_data): recalcula total_costes      │
│      con % calibrados del Excel sobre el PVP final             │
│                                                                 │
│  2.17 Alertas automáticas                                       │
│    severity: info / warning / critical                          │
│    códigos: cap_applied, floor_forced, match_low_quality,       │
│             pvp_min_above_median, velocity_premium,             │
│             product_uncompetitive, margin_below_min, rule_changed│
│                                                                 │
│  Output: PricingResult (amount, pvp_min, margin_pct,            │
│    rule_applied, formula, breakdown JSONB, alerts, fx_at)       │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 3 — ExceptionEvaluator.evaluate()                         │
│  app/services/pricing/exception_evaluator.py                    │
│                                                                 │
│  Decide: 'auto_approved' | 'pending_review'                     │
│                                                                 │
│  Reglas en orden (primera que coincide gana):                   │
│  4. alerts severity=critical → pending_review                   │
│  3. margin_pct < min_margin_pct de rule → pending_review        │
│  1. sin precio previo → auto_approved (primera propuesta)       │
│  2. |delta_margin| > margin_threshold_pct → pending_review      │
│  5. rule_applied cambió vs prev_price → pending_review          │
│  6. |fx_swing| > fx_swing_threshold_pct → pending_review        │
│  7. default → auto_approved                                     │
│                                                                 │
│  Las ExceptionRules se resuelven por especificidad:             │
│  (channel+scheme) > channel-only > scheme-only > global(NULL)   │
│  Toma el threshold MÁS ESTRICTO de los aplicables.              │
└─────────────────────────────────────────────────────────────────┘
         │
         ├── auto_approved ──►
         └── pending_review ──►
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 4 — State machine + persistencia                          │
│  app/services/pricing/state_machine.py                          │
│                                                                 │
│  Estado inicial según evaluador (draft → auto_approved|         │
│  pending_review). Transiciones legales completas:               │
│                                                                 │
│  draft → auto_approved | pending_review | rejected              │
│  auto_approved → approved | exported | published | revised      │
│  pending_review → approved | rejected | revised                 │
│  approved → exported | published | revised                      │
│  rejected → draft                                               │
│  revised → pending_review | rejected                            │
│  published → archived  (terminal operativo)                     │
│  exported → archived   (alias legacy de published)              │
│  superseded → — (terminal)                                      │
│  migrated → approved | rejected  (datos legacy importados)      │
│                                                                 │
│  Doble defensa: FSM en código + trigger DB ck_price_status_     │
│  transition (migración 070)                                     │
│                                                                 │
│  Cada transición persiste 1 PriceApprovalEvent:                 │
│  (price_id, actor_id, from_status, to_status, reason, metadata) │
│                                                                 │
│  Price persiste: amount, pvp_min, margin_pct, currency (AED),   │
│  rule_applied, formula, breakdown JSONB, alerts JSONB, fx_at,   │
│  proposed_by, valid_from, escalated                             │
└─────────────────────────────────────────────────────────────────┘
```

### Endpoints disponibles

| Endpoint | Permiso | Descripción |
|----------|---------|-------------|
| `POST /pricing/prices` | `prices:propose` | Proponer precio (ejecuta motor completo) |
| `POST /pricing/calculate` | `prices:read` | Preview sin persistir |
| `POST /pricing/simulate` | `prices:read` | What-if con overrides arbitrarios (coste, FX, mediana) |
| `POST /pricing/prices/recalculate` | `prices:propose` | Fan-out Celery recálculo masivo catálogo |
| `POST /pricing/prices/recalc-batch` | `prices:propose` | Recálculo por lista de SKUs (devuelve task_ids) |
| `GET /pricing/prices` | `prices:read` | Listado paginado (cursor-based) con filtros sku/canal/scheme/status |
| `GET /pricing/prices/{id}` | `prices:read` | Detalle + historial completo de approval events |
| `POST /pricing/prices/{id}/approve` | `prices:approve` | Gerente aprueba |
| `POST /pricing/prices/{id}/reject` | `prices:approve` | Gerente rechaza (razón obligatoria) |
| `POST /pricing/prices/{id}/revise` | `prices:propose` | Comercial propone monto manual nuevo |
| `POST /pricing/prices/{id}/revise-counter` | `prices:override_review` | Counter-proposal con razón obligatoria |
| `POST /pricing/prices/bulk-approve` | `prices:approve` | Aprobación masiva con comentario |
| `POST /pricing/prices/bulk-publish` | `prices:export` | Batch approved → exported con rollback_on_error |
| `POST /pricing/prices/{id}/export` | `prices:export` | Marca como exported (terminal pre-publish) |
| `GET /pricing/fx-rates` | `fx:read` | Lista FX rates vigentes |
| `POST /pricing/fx-rates` | `fx:write` | Crea FX rate manual (cierra el vigente anterior) |
| `GET /pricing/exception-rules` | `prices:read` | Lista exception rules activas |
| `GET /pricing/channels` | `channels:read` | Lista canales con estado |
| `PATCH /pricing/channels/{code}/state` | `channels:manage` | Transición de estado de canal |

### Modelos de base de datos

| Tabla | Clase Python | Descripción |
|-------|-------------|-------------|
| `fx_rates` | `FXRate` | Tipos de cambio con vigencia temporal `effective_from/to`. Lookup: par + as-of. Índice `idx_fx_active` para vigente actual. |
| `schemes` | `CostScheme` | 5 esquemas inmutables: `FBA`, `FBM`, `DIRECT_B2C`, `DIRECT_B2B`, `MARKETPLACE`. Cada uno con `cost_components_template` JSONB. |
| `costs` | `Cost` | Coste versioned por (sku, scheme, supplier). Un solo `active` por combinación (UNIQUE parcial). Trigger `costs_stamp_fx_trg` autopobla `fx_rate_id`. `breakdown` JSONB con componentes desglosados. `scheme_landed_aed` calculado. |
| `prices` | `Price` | Propuesta de precio por (SKU, canal, scheme). State machine enforced. `breakdown` + `alerts` JSONB para auditoría completa. `fx_at` timestamp del FX usado. |
| `exception_rules` | `ExceptionRule` | Umbrales configurables: `margin_threshold_pct`, `min_margin_pct`, `fx_swing_threshold_pct`. Scope por (channel_id, scheme_code) o global (NULL). Versionadas con `effective_from/to`. |
| `price_approval_events` | `PriceApprovalEvent` | Historial inmutable de cada transición FSM: actor, from/to status, reason, metadata JSONB. |

### Servicios internos

| Módulo | Responsabilidad |
|--------|----------------|
| `rule_engine.py` — `PricingRuleEngine` | 18 reglas determinísticas del motor v5.1. Todo en `Decimal` (ROUND_HALF_UP, compatible Excel). Stateless — permite inyección de market data del comparador. |
| `exception_evaluator.py` — `ExceptionEvaluator` | Decide `auto_approved` vs `pending_review` evaluando 7 condiciones en orden de prioridad. |
| `state_machine.py` — `PriceStateMachine` | FSM con transiciones legales. Genera `PriceApprovalEvent` por transición. Doble defensa con trigger DB. |
| `bulk_publish_service.py` — `BulkPublishService` | Batch `approved → exported` con `rollback_on_error` opcional. |
| `revise_service.py` — `ReviseService` | Counter-proposal con razón obligatoria, permiso `prices:override_review`. |
| `bulk_recalc_service.py` — `BulkRecalcService` | Fan-out Celery tasks para recálculo masivo del catálogo. |
| `escalation_service.py` — `EscalationService` | Job de escalación automática: precios en `pending_review` >48h → escalado + delegación. |
| `digest_service.py` — `DigestService` | Email digest diario 18:00 UAE con resumen de pendientes por gerente. |

### Reglas del motor v5.1 (referencia rápida)

| Regla | Código | Lógica |
|-------|--------|--------|
| `premium_velocidad_alta` | 2.10 | Competidores ≥7d más lentos + match → mediana × 1.15 |
| `premium_velocidad_media` | 2.10 | Competidores ≥3d más lentos + match → mediana × 1.05 |
| `aggressive_match_high` | 2.11 | Score ≥80 → max(mediana×0.98, PVP_MIN×1.05) |
| `aggressive_match_low` | 2.12 | Score 60-79 → max(mediana×1.10, PVP_MIN×1.10) |
| `aggressive_g2_no_match_stainless` | 2.13 | G2 inox sin match → max(coste×2.8, PVP_MIN×1.15) |
| `aggressive_g2_no_match_cast_iron` | 2.13 | G2 fundición → max(coste×3.0, PVP_MIN×1.15) |
| `aggressive_g2_no_match_default` | 2.13 | G2 genérico → max(coste×2.5, PVP_MIN×1.15) |
| `aggressive_g1_no_match` | 2.14 | Fallback → PVP_MIN × 1.15 |
| Cap superior | 2.16 | pvp > mediana×1.20 → clamp (no aplica si velocity premium) |
| Floor | 2.16 | pvp < PVP_MIN → forzar PVP_MIN (alert critical) |

### Capacidad

- Bulk recalculation: 4.480 evaluaciones < 60 s (NFR-02) vía fan-out Celery
- Simulación what-if: sin persistencia, overrides arbitrarios (coste, FX, mediana, grupo)
- `parallel_run_service.py`: compara output motor vs Excel legacy para validación pre-cutover

---

### Mapa URL → Acción → API

Cada paso del motor tiene una o más pantallas en el frontend. A continuación el mapa completo.

#### Pantalla 1 — Pricing Studio (simular + proponer)

**URL frontend**: `/precios/simular`  
**Quién la usa**: Comercial

| Acción del usuario | Llamada API | Resultado |
|--------------------|-------------|-----------|
| Introduce SKU + canal + esquema → pulsa **Simular** | `POST /api/v1/pricing/simulate` con `{ product_sku, channel_code, scheme_code, scenario_overrides }` | Devuelve `PricingResult` (amount, pvp_min, margin_pct, rule_applied, formula, breakdown, alerts) **sin persistir** |
| Modifica overrides (cost_total / fx_rate EUR→AED / median_aed) → pulsa Simular | Mismo endpoint con `scenario_overrides: { cost_total, fx_rate, median_aed }` | Motor recalcula con los valores sobreescritos — útil para validar escenarios de FX o negociación de coste |
| Pulsa **Enviar a aprobación** | `POST /api/v1/pricing/prices` con `{ product_sku, channel_code, scheme_code }` | Ejecuta motor completo + ExceptionEvaluator + state machine → persiste `Price` con estado `auto_approved` o `pending_review` |
| Si el motor devuelve alertas críticas o margen < 30% | Banner de advertencia "puede requerir aprobación del Gerente" con botón Enviar | — |

> **Preview sin persistir alternativo**: `POST /api/v1/pricing/calculate` — misma lógica que simulate pero con parámetros de mercado en lugar de overrides libres.

---

#### Pantalla 2 — Listado de precios

**URL frontend**: `/precios`  
**Quién la usa**: Comercial / Gerente / TI MT

| Acción | Llamada API | Resultado |
|--------|-------------|-----------|
| Ver precios paginados | `GET /api/v1/pricing/prices?sku=&channel=&scheme=&status=&limit=50` | Lista con SKU, esquema, importe AED, margen %, regla aplicada, estado (badge) |
| Filtrar por estado (pending_review, approved…) | `GET /api/v1/pricing/prices?status=pending_review` | Filtra por estado — los colores de badge corresponden: `pending_review` = warning, `approved` = success, `rejected` = destructive |
| Click en SKU o "Ver" | Navega a `/precios/{id}` | — |
| Click en **Simular** (header) | Navega a `/precios/simular` | — |
| Click en **Aprobaciones** (header) | Navega a `/precios/aprobaciones` | — |

---

#### Pantalla 3 — Bandeja del Gerente (aprobaciones)

**URL frontend**: `/precios/aprobaciones`  
**Quién la usa**: Gerente Comercial

| Acción | Llamada API | Resultado |
|--------|-------------|-----------|
| Carga inicial (tab "Pendientes") | `GET /api/v1/pricing/prices?status=pending_review&include_total=true` | Lista de propuestas con SKU, canal, esquema, importe, margen%, edad, autor |
| Cambiar tab (Todo / Aprobadas / Rechazadas) | `GET /api/v1/pricing/prices?status={estado}` | Refiltra la tabla |
| Pulsar ✓ (fila individual) | `POST /api/v1/pricing/prices/{id}/approve` | `pending_review → approved` + `PriceApprovalEvent` persistido |
| Pulsar ✗ (fila individual) | `POST /api/v1/pricing/prices/{id}/reject` con `{ reason: "Rechazado desde bandeja del Gerente" }` | `pending_review → rejected` + `PriceApprovalEvent` persistido |
| Seleccionar varias filas → **Aprobar** (bulk) | `POST /api/v1/pricing/prices/bulk-approve` con `{ price_ids: [...], comment: "" }` | Batch aprobación con rollback automático si falla alguna transición FSM |
| Click **Exportar audit** | — (botón pendiente de implementar) | Planificado: descarga CSV firmado |
| Cargar más (infinite scroll) | `GET /api/v1/pricing/prices?cursor={next_cursor}` | Siguiente página cursor-based |

---

#### Pantalla 4 — Detalle de precio

**URL frontend**: `/precios/{id}`  
**Quién la usa**: Comercial / Gerente

| Acción | Llamada API | Resultado |
|--------|-------------|-----------|
| Carga detalle | `GET /api/v1/pricing/prices/{id}` | `PriceDetail`: todos los campos + `approval_events[]` (historial FSM completo) |
| Revisar con nuevo monto | `POST /api/v1/pricing/prices/{id}/revise` con `{ new_amount, reason }` | Genera nueva propuesta — estado `revised → pending_review` |
| Counter-proposal (override_review) | `POST /api/v1/pricing/prices/{id}/revise-counter` con `{ new_amount, reason }` | Requiere permiso `prices:override_review` — para casos donde el Gerente propone monto concreto |
| Marcar como exported (TI MT) | `POST /api/v1/pricing/prices/{id}/export` | `approved → exported` (pre-publicación en canal) |

---

#### Pantalla 5 — Gestión FX Rates

**URL frontend**: `/costos` (sección FX dentro de costos)  
**Quién la usa**: TI MT / Admin

| Acción | Llamada API | Resultado |
|--------|-------------|-----------|
| Ver tipos de cambio vigentes | `GET /api/v1/pricing/fx-rates?from_currency=EUR&to_currency=AED` | Lista con `rate`, `effective_from`, `source` (manual/cbuae/ecb/imported) |
| Crear nuevo FX rate | `POST /api/v1/pricing/fx-rates` con `{ from_currency, to_currency, rate, effective_from, source }` | Cierra automáticamente el rate vigente anterior (setea `effective_to`) + audit event |

> El FX rate se usa en el motor via `costs_stamp_fx_trg`: trigger DB autopobla `fx_rate_id` al insertar un `Cost` según `effective_at` del coste.

---

#### Pantalla 6 — Gestión de canales

**URL frontend**: `/canales`  
**Quién la usa**: TI MT

| Acción | Llamada API | Resultado |
|--------|-------------|-----------|
| Ver canales con estado | `GET /api/v1/pricing/channels` | Lista con code, name, state, schemes_supported, state_history |
| Filtrar por estado | `GET /api/v1/pricing/channels?state=live` | — |
| Cambiar estado de canal | `PATCH /api/v1/pricing/channels/{code}/state` con `{ state, reason }` | Transición validada + `state_history` JSONB actualizado + audit event |

---

#### Acción de sistema — Recálculo masivo

**Sin URL de usuario** — disparado desde Jobs Admin o API  
**Quién lo usa**: TI MT / Sistema automático

| Disparador | Llamada API | Resultado |
|------------|-------------|-----------|
| Recálculo de todo el catálogo | `POST /api/v1/pricing/prices/recalculate` | Fan-out Celery — 1 task `mt.pricing.recalculate_sku` por SKU, devuelve `{ task_id, status }` |
| Recálculo de lista de SKUs | `POST /api/v1/pricing/prices/recalc-batch` con `{ skus: [...], trigger }` | Devuelve `{ skus_queued, task_ids[] }` para poll posterior |
| Publicación batch en canal | `POST /api/v1/pricing/prices/bulk-publish` con `{ price_ids: [...], rollback_on_error: true }` | Batch `approved → exported` con rollback opcional ante primer fallo FSM |

---

### Resumen visual: URL → paso del motor

```
/precios/simular          →  PASO 1 (inputs) + PASO 2 (motor, preview)
                          →  PASO 1-4 completos al pulsar "Enviar a aprobación"

/precios                  →  Vista resultado: estado post-ExceptionEvaluator
                             (auto_approved vs pending_review visible en badges)

/precios/aprobaciones     →  PASO 4 (state machine): approved / rejected / bulk

/precios/{id}             →  PASO 4 detalle: historial FSM, revise, counter, export

/costos (FX section)      →  Gestión de fx_rates que alimenta PASO 1

/canales                  →  Gestión de channels que parametriza PASO 2 (channel multiplier)

Jobs Admin / API          →  Recálculo masivo (fan-out Celery)
```

---

## [4] Workflow de aprobación

**Actores**: Comercial (propone), Gerente (aprueba/rechaza)  
**Routes**: `exception_rules`, `human_queue`, `translations_workflow`

```
Precio en pending_review
        │
        ▼
[Cola Gerente] → UI lista precios pendientes con contexto
        │
        ├── Aprueba individual / bulk-approve
        ├── Rechaza con comentario
        └── Delega si ausente >48 h (job escalation)
        │
        ▼
[Digest diario 18:00 UAE] → email resumen pendientes
        │
        ▼
Precio aprobado → estado: approved
```

- `exception_rules` define qué necesita aprobación manual
- Cada transición queda en audit trail con actor, timestamp y reason
- Hash chain tamper-evident en `audit_events` (R-005, VAT UAE 2026)

---

## [5] Gestión de canales

**Actores**: TI MT  
**Routes**: `channels`, `channels_mirror`, `admin_flags`

- 6 estados por canal: `draft → active → paused → suspended → deprecated → archived`
- Pausa congela exports + envía notificación in-app
- Feature flags por canal (`channel_recommendation`, `reverse_image_search`)
- Consola TI para transiciones con historial completo

---

## [6] Export / Publicación

**Actores**: Sistema automático (job diario) + TI MT (manual)  
**Routes**: `exports`, `parallel_run`

```
Precios aprobados
        │
        ▼
[Constraint DB] → bloquea export sin aprobación (nivel base de datos)
        │
        ▼
[ChannelPublisher] → adapter por canal
        │
        ├── Amazon UAE → SP API (shadow publish → publish)
        └── Tradeling → Tradeling API
        │
        ▼
Job diario "last-known-good" → re-exporta última versión buena si falla
```

- Parallel run: compara output de la app vs Excel legacy (validación pre-cutover)
- Export CSV firmado disponible para auditoría FTA (VAT UAE)

---

## [7] Audit trail + Compliance

**Transversal a todo el flujo**  
**Routes**: `audit`, `audit_query`

- Toda operación escribe en `audit_events` (particionada, append-only)
- Hash chain: `row_hash = sha256(payload || prev_hash)` — tamper-evident
- Retención 7 años (VAT UAE + Corporate Tax UAE)
- Endpoint `GET /audit/verify/{from}/{to}` detecta manipulación
- Export CSV firmado para FTA

---

## Roles en el proceso

| Rol | Responsabilidad en la app |
|-----|--------------------------|
| **Comercial** | Importa Excel, revisa enriquecimiento, propone precios manuales, ve simulaciones |
| **Gerente** | Aprueba/rechaza precios en cola, configura exception rules, ve dashboards |
| **TI MT** | Gestiona canales, configura jobs/scheduler, opera DR drills, consola admin |
| **Admin** | RBAC, usuarios, feature flags, calibración IA |
| **Sistema (Celery)** | Pipeline IA, recálculo masivo, digest email, exports, CDC→Neo4j, particionado audit |

---

## Stack técnico por capa

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 16 + React 19 + TypeScript + Tailwind v4 + Shadcn/ui |
| Backend | FastAPI + Python 3.11 + Pydantic |
| ORM / Migraciones | SQLAlchemy 2.0 async + Alembic (89 migraciones a 2026-05-12) |
| Auth | Supabase Auth (rol `mt_app`) |
| Storage | Supabase Storage (bucket `product-images`) |
| Worker | Celery + Redis; schedules en `public.job_definitions` |
| Graph / IA | Neo4j 5.20 + Claude (VLM Judge) + CLIP (RIS) |
| Deploy | Hetzner + Docker Compose + Caddy |

---

## Fuera de scope Fase 1

- B2B (Fase 4)
- B2C / marketplace UI — sprint paralelo independiente (Shopify/Saleor)
- RTL UI árabe — AR es export-only Fase 1
- Multi-tenant — single-tenant BR→MT
