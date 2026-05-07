---
adr: "ADR-069"
title: "Golden numbers + bundling psicológico AED — 4-tier seed con tabla editable por TI"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Paula (validador pricing MT)", "Champion MT", "TI MT", "Equipo backend BR"]
related:
  - "ADR-068-pricing-state-machine-v51.md"
  - "ADR-049-migration-discipline.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-069 — Golden numbers + bundling psicológico AED

## 1. Contexto

El kit v5.1 (`MT_Pricing_Run_Kit/src/pricing.py` + macros VBA) aplica **bundling psicológico** sobre el precio crudo — snapping a terminaciones percibidas como "redondas" o "agresivas" (`.49`, `.95`, `.99`) y/o múltiplos discretos (5 / 10 AED) según el rango de precio. Esto es estándar en retail UAE (Amazon UAE, Noon UAE, B2C direct) y Paula lo firmó como obligatorio en S0.

Decisiones a documentar (US-1B-01-03 + US-1B-01-02 alcance v5.1):

1. **Cuántos tiers** y dónde están los breakpoints.
2. **Qué terminaciones** y qué módulos por tier.
3. **Defaults por canal** (Amazon/Noon/B2C/B2B/marketplace).
4. **Fallback** cuando aplicar el snap reduciría el margen por debajo del mínimo (`pvp_min_aed`).
5. **Quién puede editar la tabla** sin redeploy.

## 2. Decisión

### 2.1 Cuatro tiers por banda de precio

| tier            | upper_bound (AED) | endings              | modulus      | tolerance |
|-----------------|-------------------|----------------------|--------------|-----------|
| `tier_1_small`  | 10.00             | `.49`, `.99`         | —            | ±0.30     |
| `tier_2_medium` | 100.00            | `.95`, `.99`         | —            | ±0.30     |
| `tier_3_large`  | 1 000.00          | `.95`, `.99`         | 5            | ±0.50     |
| `tier_4_xlarge` | 999 999 999.00    | `.99`                | 10           | ±2.00     |

Justificación firmada por Paula:

- **Tier 1 (≤10 AED)**: piezas pequeñas (juntas, espárragos). `.49 / .99` ya son convención retail UAE. Tolerancia 0.30 AED es ~3-6 % del precio — elasticidad alta en este rango.
- **Tier 2 (10-100 AED)**: filtros, válvulas pequeñas. Mantenemos `.95 / .99` (Amazon UAE prefiere `.99`, Noon UAE acepta `.95`). Tolerancia 0.30 AED.
- **Tier 3 (100-1000 AED)**: válvulas medianas, accesorios. Añadimos `modulus=5` para snappear al múltiplo de 5 más cercano (e.g. 234.99 → 234.99, 237 → 234.99 o 239.99). Tolerancia 0.50 AED.
- **Tier 4 (>1000 AED)**: válvulas industriales grandes. Solo `.99` con `modulus=10` — el cliente B2B de este rango no se mueve por 9.99 AED, solo importa la magnitud. Tolerancia 2 AED (~0.2 %).

### 2.2 Defaults por canal (`channel_default_strategy`)

Tabla `_CHANNEL_DEFAULTS` en `golden_numbers.py`:

| channel_code         | strategy   | Razón                                                      |
|----------------------|------------|------------------------------------------------------------|
| `amazon_uae`         | `auto`     | Tier 1 .49/.99, Tier 2-3 .95/.99, Tier 4 .99 — match Amazon UAE Buy Box conventions. |
| `noon_uae`           | `auto`     | Idem — Noon es similar a Amazon en UAE.                    |
| `b2c_direct`         | `.99`      | Más agresivo retail directo MT-valves.es / canal propio.   |
| `b2b_direct`         | `none`     | Precios netos, sin bundling — Comercial negocia margen.    |
| `marketplace_listing`| `auto`     | Default seguro hasta que Champion confirme canal específico. |

### 2.3 Fallback "off when margin tight"

Cuando el snap del bundling reduce el margen por debajo del `pvp_min_aed` configurado, el motor v5.1 marca `applied=false` con `rejected_best_candidate` y `rejected_delta` en `bundling_info` (audit), y emite un **alert `severity=warning` code=`bundling_rejected_margin_floor`** para que Comercial vea por qué quedó en raw round. La política `delta_margin` de ADR-068 puede empujar a `pending_review` si esto coincide con un cambio de coste grande.

Como fallback, el motor también acepta `disable_bundling=true` por request — usado por el flujo B2B y por overrides puntuales firmados por Paula.

### 2.4 Tabla `pricing_golden_tiers` editable por TI sin redeploy (TODO S5)

**Decisión Sprint 4 (estado proposed)**: el `TIER_CONFIG` vive como tupla constante en `golden_numbers.py` para Sprint 4. **A partir de Sprint 5** se migra a tabla `pricing_golden_tiers` (Alembic) con:

```
id UUID PK
tier_name TEXT UNIQUE
upper_bound NUMERIC(12,2) NOT NULL
endings NUMERIC(4,2)[] NOT NULL
modulus NUMERIC(8,2) NULL
tolerance NUMERIC(6,2) NOT NULL
channel_overrides JSONB DEFAULT '{}'::jsonb
active BOOLEAN DEFAULT true
created_by UUID, created_at TIMESTAMPTZ
```

RLS: SELECT abierto a `pricing_user`; INSERT/UPDATE solo `pricing_admin` (TI MT). Audit trigger genérico (S3 pattern). Cache in-memory en backend con TTL 60s + Redis pub/sub `pricing:golden_tiers:invalidate` para forzar reload tras edit.

Esto da a TI MT capacidad de retunear tiers en respuesta a feedback Q3-2026 sin pasar por release ni PR.

## 3. Alternativas consideradas

### 3.1 Tabla en BD desde Sprint 4

**Rechazada (defer S5)**. Bundling lógica core necesita estabilidad en S4 para certificar paridad ≥ 99 % con golden numbers v5.1 (US-1B-01-01). Mover la tabla a BD añade un punto más de configuración (RLS, cache invalidation) que no compensa con 4 tiers estables. En S5 ya hay endpoint admin necesario para `pricing_admin` workflow.

### 3.2 Más tiers (5-7 con sub-bandas)

**Rechazada**. Paula validó que 4 tiers cubren los rangos del catálogo PVF actual con menos de 1 % de SKUs en boundary cases. Más tiers = más superficie de bug, más coste de validar paridad v5.1.

### 3.3 Solo `.99` como terminación universal

**Rechazada**. Noon UAE y Amazon UAE prefieren `.95` en bandas medianas (datos de scrape interno BR-2024-Q3). Limitar a `.99` cede precisión vs. la compra del cliente final.

### 3.4 Bundling siempre on, sin fallback

**Rechazada**. Margen mínimo es deal-breaker contractual MT. Si bundling fuerza precio bajo `pvp_min_aed`, prima la regla de negocio (margin floor) sobre la cosmética del precio.

## 4. Consecuencias

### Positivas

- 4 tiers compactos = paridad v5.1 fácil de verificar (30 SKUs golden numbers).
- Defaults por canal centralizados → cambios de política comercial se hacen en 1 dict.
- Override flags explícitos (`disable_bundling`, `bundle_strategy`, `tolerance_override`) cubren casos edge sin tocar tier config.
- Roadmap a tabla editable (S5) sin refactor del motor — la API `apply_golden_numbers` ya acepta `overrides` dict.

### Negativas

- Fallback "off when margin tight" reduce el % de SKUs con bundling aplicado en SKUs de bajo margen. Aceptable; Paula prefiere margin floor.
- Hardcode S4: si Paula descubre que tier 3 necesita modulus=10 en algún sub-rango, requiere PR+release (no edit en BD). Mitigación: defer S5 explícito.
- **Tier 4 tolerancia 2 AED**: candidatos pueden quedar 2 AED por debajo del raw, lo que en válvulas industriales medianas (~1500 AED) es 0.13 % — aceptable.

## 5. Open questions

- **Q1 (TODO Paula)**: confirmar tolerancia tier 1 (0.30 AED en rango ≤ 10 AED puede ser hasta 6 % del precio). Si Paula encuentra falsos snaps, recalibrar a 0.20 AED.
- **Q2 (TODO Champion MT)**: validar que `b2b_direct=none` es la política correcta. Si Comercial prefiere bundling también en B2B, switch a `auto`.
- **Q3 (TODO TI MT, S5)**: agendar US-1B-01-XX "tabla `pricing_golden_tiers` + endpoint admin" para Sprint 5.

## 6. Implementation status

- `mt-pricing-backend/app/services/pricing/golden_numbers.py` — implementado Sprint 4:
  - `TIER_CONFIG` (líneas 71-100) — 4 tiers según tabla §2.1.
  - `_CHANNEL_DEFAULTS` (líneas 103-109) — defaults por canal §2.2.
  - `snap_to_tier` (líneas 175-254) — algoritmo de snap con tolerancia + rechazo por fuera de tolerancia (línea 237 `if delta > tolerance`).
  - `apply_golden_numbers` (líneas 257-304) — API pública que el `state_machine_v51` consume.
- Integración con state machine: ADR-068 §6 (`apply_v51` invoca `apply_golden_numbers` antes de decidir status).
- Tests esperados: `tests/services/pricing/test_golden_numbers.py` con cobertura por tier × strategy × channel + 30 golden numbers v5.1 paridad.

## 7. Trazabilidad

- Sprint 4 backlog US-1B-01-03 (Notas técnicas: "TODO ADR-069").
- `sprint0-v51-rules-extraction.md` — Paula firma tiers + endings.
- ADR-068 — consume golden numbers en state machine v5.1.
- PRD §pricing-engine — paridad v5.1.
- Risk register: R-pricing-margin-floor-bypass (mitigado por fallback off when tight).
