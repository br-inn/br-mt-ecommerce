---
adr: "ADR-068"
title: "Pricing state machine v5.1 — capa fina sobre FSM legacy con auto-approve / pending-review"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Champion MT", "Paula (validador pricing MT)", "TI MT", "Equipo backend BR"]
related:
  - "ADR-049-migration-discipline.md"
  - "ADR-069-pricing-golden-numbers-bundling.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-068 — Pricing state machine v5.1

## 1. Contexto

US-1B-01-02 / US-1B-01-03 (Sprint 4) cierran Fase 1b con el motor `PricingEngine.calculate(...)` portado del kit v5.1. Durante S3 se introdujo `app/services/pricing/state_machine.py` (FSM "legacy") con las transiciones canónicas declaradas en el PRD: `draft → auto_approved | pending_review → approved → published → superseded` (+ `rejected`). La política v5.1 firmada por Paula (Sprint 0 — `sprint0-v51-rules-extraction.md`) requiere ahora:

1. **Aplicar golden numbers / bundling psicológico** al output del motor antes de persistir (ADR-069).
2. **Clasificar alerts** del motor en `critical` / `warning` / `info` y derivar `pending_review` automático cuando hay críticos.
3. **Bloquear auto-approve** si el delta de margen vs. precio anterior excede un umbral (default 10 puntos %).
4. **Permitir overrides explícitos** por request: `force_pending_review` / `force_auto_approved` / `disable_bundling` / `bundle_strategy` / `tolerance_override` / `delta_warn_pct_override`.
5. **NO refactorizar** el FSM legacy (sigue siendo SSoT de `transition()` legales para evitar regresiones de S3 en `costs`-style versioning).

La pregunta arquitectural: ¿extender el FSM existente o crear un módulo paralelo que orqueste el FSM?

## 2. Decisión

Adoptamos un **módulo orquestador `state_machine_v51.py`** como capa fina sobre `state_machine.py`. Reglas:

### 2.1 División de responsabilidades

- `state_machine.py` (legacy): SSoT de `ALLOWED_TRANSITIONS`, `is_valid_transition`, `InvalidTransition`. **Nunca se edita** desde v5.1 — el v5.1 lo re-exporta para preservar compat con consumidores de S3.
- `state_machine_v51.py` (capa fina): aplica golden numbers, clasifica alerts y **decide el `initial_status`** (`draft → auto_approved | pending_review`) que luego el caller pasa a `transition()`.

### 2.2 Reglas de decisión `decide_initial_status`

Orden estricto (primer match gana):

1. Override `force_pending_review` ∧ `force_auto_approved` ⇒ `InvalidV51Override`.
2. `force_pending_review=True` ⇒ `pending_review` (reason: `override:force_pending_review`).
3. `force_auto_approved=True` ⇒ `auto_approved` (reason: `override:force_auto_approved`). El caller debe validar permission `prices:override_review` antes de pasar el flag.
4. `classified.critical` no vacío ⇒ `pending_review` (reason: `critical_alerts_present`).
5. `|delta_margin_pct| > delta_warn_pct` (default `10.0`) ⇒ `pending_review` (reason: `delta_margin_pct_above_threshold:10.0%`).
6. `classified.warning` no vacío ⇒ `auto_approved` con reason `warnings_present_auto_approved` (warnings sólos no bloquean).
7. `auto_approved` con reason `clean_no_alerts`.

### 2.3 API pública

- `apply_v51(raw_amount, alerts, channel_code, delta_margin_pct, delta_warn_pct, overrides) -> V51Decision`. El `PricingService` lo invoca DESPUÉS de `engine.calculate(...)` y ANTES de persistir en `prices`. Devuelve:
  - `final_amount` (Decimal con bundling aplicado o raw redondeado si bundling off).
  - `initial_status` (`auto_approved` | `pending_review`).
  - `bundling_info` (tier, strategy, delta_aed, applied flag — para audit).
  - `classified_alerts` y `decision_reasons` (trazabilidad legal).
  - `overrides_applied` (qué flags efectivamente aplicaron).

### 2.4 Threshold delta_margin_pct = 10 %

Justificación numérica firmada por Paula:

- En el catálogo PVF actual (~224 SKUs), un cambio de margen >10 puntos típicamente refleja: (a) cambio de coste fundamental (proveedor, scheme, FX) que merece revisión humana; (b) error de captura. Por debajo de 10 puntos los cambios entran en la banda normal de fluctuación FX EUR/AED ±2.5 %.
- 10 % es configurable globalmente vía setting `PRICING_DELTA_WARN_PCT` y por request via `delta_warn_pct_override` (override en `apply_v51`).
- Métricas a observar en S5 para recalibrar: `pricing_v51_pending_review_rate{reason="delta_*"}` y feedback de Comercial sobre falsos positivos.

## 3. Alternativas consideradas

### 3.1 Extender `state_machine.py` legacy con golden + alerts

**Rechazada**. Acopla responsabilidades (transiciones FSM + lógica de bundling + clasificación alerts + thresholds margen) en un módulo. Aumenta superficie de regresión sobre el FSM heredado de S3 (versioning `costs`-style). Pruebas unitarias complejas.

### 3.2 Orquestador en `PricingService` directo (sin módulo dedicado)

**Rechazada**. La lógica v5.1 (clasificación alerts, override flags, decisión status) se reusa en al menos 3 callers (recalc single, recalc bulk Celery, scaffold S5 `prices/{id}/approve` workflow). Centralizar en un módulo evita duplicación.

### 3.3 Diseño event-sourced (separar `decide_initial_status` del `apply_golden_numbers`)

**Rechazada para Fase 1b**. Sobre-ingeniería: agregar un bus de eventos para 1 transición síncrona no compensa la complejidad operativa. Reconsiderar en Fase 2 si aparecen más reglas asíncronas (fraud check, supplier credit limit).

## 4. Consecuencias

### Positivas

- **Cero refactor del FSM legacy** → S3 (`costs` versioning) no se desestabiliza.
- **Testabilidad**: `apply_v51` es función pura (entradas/salidas explícitas), suite unitaria cubre cada rama del árbol de decisión.
- **Auditoría**: `decision_reasons[]` y `overrides_applied{}` quedan en `breakdown.v51` del `prices` row → trail completo para Paula y Champion MT.
- **Override gradient**: permite a Comercial forzar pending_review (defensivo) o auto_approved (con permission) sin abrir un endpoint nuevo.

### Negativas

- **Doble módulo** en `app/services/pricing/`: devs deben saber que `state_machine_v51.apply_v51` se llama DESPUÉS del motor. Mitigado por docstring explícito y por la integración en `PricingService` (caller único).
- **Threshold delta hardcoded 10 %**: si Paula recalibra a 7 % o 15 % se puede ajustar via env, pero el default vive en código (`_DEFAULT_DELTA_WARN_PCT`). Aceptable para Fase 1b.
- **`force_auto_approved` requires caller-side permission check**. Si el caller olvida, abre boquete de governance. Mitigación: en S5 se mueve la verificación de permission al middleware del endpoint `POST /prices/recalculate` (carry).

## 5. Open questions

- **Q1 (TODO Paula)**: confirmar si delta_warn_pct=10 % aplica igual a canales pre-launch (B2C / B2B direct sin histórico). Por ahora el motor pasa `simulation=True` para canales pre-launch y NO emite delta — la v5.1 nunca dispara la rama 5.
- **Q2 (TODO TI MT)**: definir métrica SLA `pending_review_rate` aceptable. Paula sugiere ≤ 30 % en steady state. Si en S5 el rate excede, recalibrar threshold.

## 6. Implementation status

- `mt-pricing-backend/app/services/pricing/state_machine_v51.py` — implementado (Sprint 4):
  - `classify_alerts` (líneas 87-108).
  - `decide_initial_status` (líneas 120-162) — incluye guard de overrides excluyentes, ramas críticas/delta/warnings/clean.
  - `apply_v51` (líneas 165-243) — pipeline público integrando `apply_golden_numbers`.
  - `_DEFAULT_DELTA_WARN_PCT = Decimal("10.0")` (línea 55).
- Tests esperados: `mt-pricing-backend/tests/services/pricing/test_state_machine_v51.py` (≥ 12 tests cubriendo cada rama del árbol + override conflicts + delta boundary).

## 7. Trazabilidad

- Sprint 4 backlog US-1B-01-02 + US-1B-01-03.
- PRD §pricing-engine.
- `sprint0-v51-rules-extraction.md` (Paula firma reglas v5.1).
- ADR-069 (golden numbers) — dependencia hard.
- Risk register: R-pricing-auto-approve-loose (mitigado por threshold delta + critical alerts).
