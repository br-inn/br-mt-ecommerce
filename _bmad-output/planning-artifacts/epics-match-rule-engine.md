---
stepsCompleted: [1]
inputDocuments:
  - _bmad-output/brainstorming/brainstorming-session-2026-05-16-1430.md
  - mt-pricing-backend/app/services/matching/scoring.py
  - mt-pricing-backend/app/services/matching/taxonomy_rules.py
  - mt-pricing-backend/app/services/matching/material_normalizer.py
  - mt-pricing-backend/app/services/matching/match_service.py
---

# Match Rule Engine — Epic Breakdown

## Overview

Este documento desglosa el epic "Match Rule Engine" en historias implementables. El objetivo es reemplazar el motor de matching hardcodeado por un sistema data-driven configurable por el administrador, con agente IA de optimización continua.

**Fuente:** Brainstorming session 2026-05-16, análisis del código existente en `mt-pricing-backend/app/services/matching/`.

---

## Requirements Inventory

### Functional Requirements

FR1: El administrador puede configurar pesos por dimensión de scoring (material, pn, dn, thread, norma, brand_tier, delivery, product_type, ways) por familia de producto, sin redeploy.
FR2: Los perfiles de taxonomía (familia + pesos + hard_blockers) se persisten en BD, reemplazando las constantes hardcodeadas en `taxonomy_rules.py`.
FR3: Los thresholds de clasificación (peer/drop) se persisten en `comparator_config`, editables por el administrador.
FR4: Las transformaciones de unidades (PSI→PN, DN métrico→pulgadas) se persisten en tabla `unit_transforms`, editables y extensibles.
FR5: El sistema soporta tablas de equivalencia de materiales (AISI 304 = EN 1.4301 = SUS304) mantenibles por el administrador.
FR6: El sistema soporta tablas de equivalencia de normas (DIN 912 ↔ ISO 4762 ↔ ASME B18.3) con tipos de equivalencia (exact/subset/compatible).
FR7: El sistema soporta equivalencias nominales (DN50 ↔ 2" NPS, PN16 ↔ Class 150) como tipo separado en `unit_transforms`.
FR8: El motor de matching lee la configuración desde BD en lugar de constantes hardcodeadas, con cache TTL 5 minutos.
FR9: Los cambios de reglas aplican solo a matches futuros — sin recálculo retroactivo.
FR10: El administrador puede simular una regla en borrador (dry-run) viendo qué matches generaría sobre el catálogo existente antes de activarla.
FR11: El sistema registra estadísticas por match: regla aplicada, score breakdown por dimensión, resultado HITL, tiempo hasta confirmación.
FR12: Un agente IA (Celery beat + Claude API) analiza periódicamente las estadísticas y genera sugerencias de optimización en lenguaje natural.
FR13: Las sugerencias del agente se clasifican por tipo de brecha: falso positivo, falso negativo, confirmación lenta.
FR14: El administrador ve las sugerencias del agente contextualmente dentro del editor de la regla afectada.
FR15: El administrador puede aplicar o descartar sugerencias del agente.
FR16: La UI incluye editor de pesos con sliders y validación en tiempo real de que la suma = 1.0.
FR17: La UI muestra estadísticas de performance por familia (tasa confirmación, FP rate, avg tiempo confirmación) en los últimos 30 días.
FR18: Las reglas actuales migran automáticamente desde el código hardcodeado como "reglas semilla" — primera configuración visible y editable.
FR19: El sistema provee endpoints REST CRUD para perfiles de taxonomía, transformaciones, equivalencias de normas y configuración global.
FR20: La reglas compartidas entre múltiples tipos de producto son posibles (muchos-a-muchos familia↔config).

### NonFunctional Requirements

NFR1: Cache en memoria con TTL 5 minutos — el motor de reglas no genera latencia adicional en el pipeline Celery de scraping.
NFR2: Cambios de configuración aplican sin redeploy de contenedores (hot config).
NFR3: La UI de administración es accesible solo para roles con permisos de administrador (RBAC existente).
NFR4: Las migraciones Alembic incluyen datos semilla compatibles con el estado actual del código hardcodeado.
NFR5: El agente IA opera en background vía Celery beat — nunca bloquea la UI ni el pipeline de matching.
NFR6: Integridad referencial: no se puede eliminar una familia si tiene `match_rule_stats` asociados.

### Additional Requirements

- Stack: FastAPI + SQLAlchemy 2.0 async + Alembic + Celery + Redis + Next.js 16 + React 19 + Tailwind v4 + Shadcn/ui
- Nuevas tablas en schema `public.*` via Alembic (no Supabase migrations)
- Claude API vía Python `anthropic` SDK para el agente IA
- Cache implementado en memoria del worker Celery (no Redis adicional)
- Endpoints bajo `/api/v1/rule-engine/` siguiendo patrones existentes del proyecto
- Migración de seed: traducción exacta del código actual a datos (sin cambio de comportamiento en producción)
- El módulo reemplaza completamente `taxonomy_rules.py` y las constantes de `scoring.py` — no convive

### UX Design Requirements

UX-DR1: Página principal `/admin/rule-engine` — tabla de familias con métricas (total matches, tasa confirmación, sugerencias pendientes) y badges de alerta.
UX-DR2: Editor de familia — panel de pesos con sliders, validación suma=1.0 en tiempo real, con feedback visual de error si no suma.
UX-DR3: Editor de familia — sección hard blockers como checkboxes con descripción legible de cada blocker.
UX-DR4: Editor de familia — sección estadísticas con gráfico de tasa de confirmación últimos 30 días.
UX-DR5: Banner contextual de sugerencias del agente dentro del editor de familia — resumen en lenguaje natural con acciones "Aplicar" / "Descartar".
UX-DR6: Modal de simulación (dry-run) — muestra preview de matches nuevos que generaría la regla propuesta con diff vs. estado actual.
UX-DR7: Página de transformaciones `/admin/rule-engine/transforms` — tabs Unidades | Normas | Materiales con tabla editable inline.
UX-DR8: Importación de equivalencias desde CSV (normas DIN/ASME).

### FR Coverage Map

| FR | Epic | Story |
|----|------|-------|
| FR1, FR2, FR18 | EP-MRE-01 | MRE-01-01, MRE-01-02 |
| FR3, FR4, FR5, FR6, FR7 | EP-MRE-01 | MRE-01-03, MRE-01-04 |
| FR8, FR9 | EP-MRE-02 | MRE-02-01, MRE-02-02 |
| FR10 | EP-MRE-02 | MRE-02-03 |
| FR11 | EP-MRE-02 | MRE-02-04 |
| FR19 | EP-MRE-02 | MRE-02-05 |
| FR16, FR17, UX-DR1..8 | EP-MRE-03 | MRE-03-01..04 |
| FR12, FR13, FR14, FR15 | EP-MRE-04 | MRE-04-01..03 |
| FR20 | EP-MRE-01 | MRE-01-02 |

## Epic List

- **EP-MRE-01**: Fundación de Datos — Migraciones y Seed
- **EP-MRE-02**: Motor Data-Driven — Refactor Backend + API REST
- **EP-MRE-03**: UI Admin — Editor de Reglas
- **EP-MRE-04**: Agente IA — Optimizador de Reglas

---

## EP-MRE-01: Fundación de Datos — Migraciones y Seed

**Objetivo:** Crear las tablas necesarias en BD y poblarlas con los datos semilla equivalentes al código hardcodeado actual. Al finalizar este epic, el sistema tiene las mismas reglas que hoy pero en base de datos, listas para ser editadas.

**Valor:** Habilita todo lo demás — sin este epic, ningún otro puede arrancar.

---

### Story MRE-01-01: Migración `taxonomy_profiles` con seed

Como administrador,
quiero que los perfiles de taxonomía (pesos por dimensión y hard blockers por familia) estén almacenados en base de datos,
para poder modificarlos sin tocar el código.

**Acceptance Criteria:**

**Given** que la migración se ejecuta
**When** se consulta `public.taxonomy_profiles`
**Then** existen registros para todas las familias actuales: `ball_valve`, `valves_ball`, `HIDROSANITARIO`, `gate_valve`, `globe_valve`, `check_valve`, `butterfly_valve`, `strainer`, `FILTROS`, `pressure_gauge`, `MANOMETROS`, `_default`
**And** los pesos de cada familia suman exactamente 1.0
**And** los hard_blockers de cada familia coinciden exactamente con los definidos en `taxonomy_rules.py`

**Given** que existe un perfil de taxonomía en BD
**When** el scoring engine llama `get_profile(family)`
**Then** retorna el perfil desde BD (no desde el dict hardcodeado)

**Notas técnicas:**
- Columnas: `id UUID PK`, `family TEXT UNIQUE NOT NULL`, `weights JSONB NOT NULL`, `hard_blockers TEXT[] NOT NULL`, `description TEXT`, timestamps
- Validación DB: CHECK que los valores de weights sumen 1.0 (±0.001 tolerancia)
- Seed data: traducción exacta de `TAXONOMY_PROFILES` en `taxonomy_rules.py`
- Alembic migration: `20260517_XXX_taxonomy_profiles.py`

---

### Story MRE-01-02: Migración `comparator_config` con seed

Como administrador,
quiero que los escalares de configuración global (thresholds peer/drop, multiplicadores G1/G2) estén en base de datos,
para ajustarlos sin redeploy.

**Acceptance Criteria:**

**Given** que la migración se ejecuta
**When** se consulta `public.comparator_config`
**Then** existen registros: `peer_threshold=70`, `drop_threshold=40`, `g1_median_multiplier=1.10`, `g2_multipliers={"default":2.5,"stainless":3.0,"cast_iron":2.0}`

**Given** que se actualiza `peer_threshold` a 65 en la tabla
**When** el motor de matching corre en el siguiente ciclo (tras expirar TTL de cache)
**Then** usa threshold 65 sin redeploy

**Notas técnicas:**
- Columnas: `id UUID PK`, `key TEXT UNIQUE NOT NULL`, `value JSONB NOT NULL`, `description TEXT`, timestamps
- Seed data: valores hardcodeados actuales en `match_service.py` y `scoring.py`

---

### Story MRE-01-03: Migración `unit_transforms` con seed

Como administrador,
quiero que las transformaciones de unidades (PSI→PN, DN métrico→pulgadas, equivalencias nominales DN/NPS) estén en base de datos,
para extenderlas con nuevas unidades sin cambiar el código.

**Acceptance Criteria:**

**Given** que la migración se ejecuta
**When** se consulta `public.unit_transforms`
**Then** existen registros para: PSI→PN (tipo numeric, formula `floor(value/14.5)`), DN metric→inches lookup table (DN15→1/2", DN20→3/4", DN25→1", DN32→1¼", DN40→1½", DN50→2", DN65→2½", DN80→3", DN100→4")

**Given** un candidato con PN expresado en PSI
**When** el scoring engine compara con el PN del SKU en bar
**Then** aplica la transformación desde `unit_transforms` (no la fórmula hardcodeada)

**Notas técnicas:**
- Columnas: `id UUID PK`, `transform_type TEXT` (numeric/lookup/nominal), `from_unit TEXT`, `to_unit TEXT`, `formula TEXT` (para numeric), `lookup_table JSONB` (para lookup), `description TEXT`, timestamps

---

### Story MRE-01-04: Migración `norm_equivalences` y `match_rule_stats`

Como sistema,
quiero tener las tablas de equivalencias de normas y estadísticas de matching listas,
para que el administrador pueda poblar normas y el sistema registre el performance de cada regla.

**Acceptance Criteria:**

**Given** que las migraciones se ejecutan
**When** se consultan `public.norm_equivalences` y `public.match_rule_stats`
**Then** ambas tablas existen con el esquema correcto y `norm_equivalences` está vacía (el admin la llena)

**Given** que se procesa un candidato en el pipeline
**When** `_score_and_upsert` completa
**Then** se inserta un registro en `match_rule_stats` con `match_candidate_id`, `taxonomy_profile_id`, `score_breakdown` (JSONB), `dimensions_fired`

**Notas técnicas:**
- `norm_equivalences`: `id`, `norm_a TEXT`, `system_a TEXT`, `norm_b TEXT`, `system_b TEXT`, `equivalence_type TEXT` (exact/subset/compatible), `notes TEXT`, timestamps
- `match_rule_stats`: `id`, `match_candidate_id UUID FK`, `taxonomy_profile_id UUID FK nullable`, `score_breakdown JSONB`, `dimensions_fired TEXT[]`, `created_at`

---

## EP-MRE-02: Motor Data-Driven — Refactor Backend + API REST

**Objetivo:** Refactorizar el motor de scoring para leer desde BD con cache, y exponer la configuración vía API REST. Al finalizar, el motor es data-driven y el admin puede gestionar reglas vía API.

---

### Story MRE-02-01: Refactor `scoring.py` + `taxonomy_rules.py` data-driven

Como sistema,
quiero que el motor de scoring lea pesos, hard_blockers y thresholds desde base de datos con cache TTL,
para que los cambios de configuración apliquen sin redeploy.

**Acceptance Criteria:**

**Given** que `taxonomy_profiles` tiene el perfil `ball_valve` con pesos en BD
**When** `compute_scoring()` se ejecuta para un SKU de familia `ball_valve`
**Then** usa los pesos de BD (no los de `_VALVE_WEIGHTS` hardcodeado)
**And** la latencia adicional es < 1ms (por cache en memoria)

**Given** que se modifica un peso en `taxonomy_profiles`
**When** han pasado 5 minutos (TTL del cache)
**Then** la siguiente ejecución de scoring usa el peso actualizado

**Given** que BD no está disponible en arranque del worker
**When** el worker intenta cargar la configuración
**Then** hace fallback a los valores hardcodeados actuales (backwards compatibility)

**Notas técnicas:**
- Nuevo `RuleEngineCache` — singleton en el worker con TTL 5min
- `taxonomy_rules.py`: `get_profile(family)` → consulta `TaxonomyProfileRepository` vía cache
- `scoring.py`: eliminar `_VALVE_WEIGHTS`, `_STRAINER_WEIGHTS`, `_GAUGE_WEIGHTS`, `_DEFAULT_WEIGHTS`, `SCORING_WEIGHTS` como constantes — leerlos del cache
- `match_service.py`: `PEER_SCORE_THRESHOLD` y `DROP_SCORE_THRESHOLD` → `ComparatorConfigRepository`
- Mantener constantes como fallback en caso de error de BD

---

### Story MRE-02-02: Refactor transformaciones de unidades data-driven

Como sistema,
quiero que las conversiones PSI→PN y DN métrico→pulgadas lean desde `unit_transforms` en BD,
para que el administrador pueda agregar nuevas transformaciones sin cambiar el código.

**Acceptance Criteria:**

**Given** que `unit_transforms` tiene la conversión PSI→PN
**When** el scoring compara PN de un candidato expresado en PSI con el PN del SKU
**Then** aplica la transformación desde BD

**Given** que el admin agrega una nueva transformación "WOG→PN" en `unit_transforms`
**When** el cache TTL expira y el siguiente candidato tiene presión en WOG
**Then** el scoring aplica la nueva conversión automáticamente

**Notas técnicas:**
- `UnitTransformRepository` con `get_by_units(from_unit, to_unit)` y cache integrado
- Conversiones numéricas: evaluar formula string de forma segura (ast.literal_eval o función predefinida)
- Conversiones lookup: buscar en `lookup_table` JSONB

---

### Story MRE-02-03: Endpoint de simulación (dry-run)

Como administrador,
quiero poder simular una regla antes de activarla,
para ver qué matches generaría sin afectar el sistema en producción.

**Acceptance Criteria:**

**Given** que el admin envía un `POST /api/v1/rule-engine/taxonomy-profiles/{family}/simulate` con pesos propuestos
**When** el endpoint procesa la solicitud
**Then** retorna los matches que generaría la regla propuesta sobre los últimos 100 SKUs activos
**And** incluye un diff: matches nuevos que se generarían, matches que dejarían de generarse, matches con score diferente
**And** la simulación NO persiste candidatos en `match_candidates`

**Given** que la simulación tarda más de 10 segundos
**When** el frontend hace el request
**Then** el endpoint responde 202 con task_id y el admin puede consultar el resultado

---

### Story MRE-02-04: Instrumentación de estadísticas en el pipeline

Como sistema,
quiero registrar qué regla aplicó en cada match y con qué resultado por dimensión,
para que el agente IA tenga datos confiables para analizar.

**Acceptance Criteria:**

**Given** que `_score_and_upsert` completa exitosamente
**When** se persiste el candidato
**Then** se inserta en `match_rule_stats`: `match_candidate_id`, `taxonomy_profile_id`, breakdown JSON con score por dimensión, lista de `dimensions_fired`

**Given** que se consulta `GET /api/v1/rule-engine/taxonomy-profiles/{family}/stats`
**When** el endpoint responde
**Then** incluye: total matches últimos 30 días, tasa de confirmación, FP rate (validado→rechazado), FN rate estimado, avg tiempo hasta confirmación

---

### Story MRE-02-05: API REST rule-engine CRUD completa

Como administrador,
quiero gestionar todas las reglas a través de una API REST,
para que la UI y futuros clientes puedan leer y modificar la configuración.

**Acceptance Criteria:**

**Given** que el admin hace `GET /api/v1/rule-engine/taxonomy-profiles`
**When** el endpoint responde
**Then** retorna lista de familias con pesos, blockers y métricas de performance

**Given** que el admin hace `PUT /api/v1/rule-engine/taxonomy-profiles/{family}` con pesos que no suman 1.0
**When** el endpoint valida
**Then** retorna 422 con mensaje claro "Los pesos deben sumar 1.0"

**Endpoints requeridos:**
- `GET/PUT /taxonomy-profiles`, `GET/PUT /taxonomy-profiles/{family}`
- `GET/POST/PUT/DELETE /unit-transforms`
- `GET/POST/PUT/DELETE /norm-equivalences`
- `GET/PUT /comparator-config/{key}`
- `GET /taxonomy-profiles/{family}/stats`
- `POST /taxonomy-profiles/{family}/simulate`
- `GET /rule-suggestions`, `POST /rule-suggestions/{id}/apply`, `POST /rule-suggestions/{id}/dismiss`

---

## EP-MRE-03: UI Admin — Editor de Reglas

**Objetivo:** Interfaz visual para que el administrador gestione reglas, vea estadísticas y actúe sobre sugerencias del agente.

---

### Story MRE-03-01: Página principal `/admin/rule-engine`

Como administrador,
quiero ver un dashboard de todas las familias de producto con sus métricas de matching,
para identificar rápidamente qué familias necesitan atención.

**Acceptance Criteria:**

**Given** que el admin navega a `/admin/rule-engine`
**When** la página carga
**Then** muestra tabla con columnas: Familia, Total Matches (30d), Tasa Confirmación, FP Rate, Sugerencias IA pendientes
**And** familias con sugerencias pendientes muestran badge amarillo
**And** familias con FP Rate > 15% muestran badge rojo
**And** hay botón "Nueva familia" para crear un perfil nuevo

---

### Story MRE-03-02: Editor de familia — pesos y blockers

Como administrador,
quiero editar los pesos por dimensión y hard blockers de una familia,
para ajustar cómo se calcula el score de matching para ese tipo de producto.

**Acceptance Criteria:**

**Given** que el admin abre `/admin/rule-engine/{family}`
**When** la página carga
**Then** muestra sliders para cada dimensión con su peso actual (0.00–1.00)
**And** muestra suma total en tiempo real con indicador verde (=1.00) o rojo (≠1.00)
**And** el botón "Guardar" está deshabilitado si la suma ≠ 1.0

**Given** que el admin ajusta los sliders y suma = 1.0
**When** hace clic en "Guardar"
**Then** se llama `PUT /api/v1/rule-engine/taxonomy-profiles/{family}`
**And** aparece toast de confirmación "Regla guardada — aplica a nuevos matches"

**Given** que el admin marca/desmarca hard blockers
**When** hace clic en "Guardar"
**Then** los nuevos blockers aplican a matches futuros

---

### Story MRE-03-03: Simulación y estadísticas en el editor

Como administrador,
quiero simular los cambios antes de activarlos y ver el historial de performance,
para tomar decisiones informadas sobre ajustes de reglas.

**Acceptance Criteria:**

**Given** que el admin modifica pesos sin guardar
**When** hace clic en "Simular"
**Then** se abre modal con preview de matches afectados: nuevos, perdidos, con score diferente
**And** el modal muestra spinner mientras procesa y resultado en < 30 segundos

**Given** que la página de familia carga
**When** la sección de estadísticas renderiza
**Then** muestra gráfico de tasa de confirmación por semana (últimas 4 semanas)
**And** muestra métricas: FP rate, FN rate estimado, avg tiempo a confirmación

---

### Story MRE-03-04: Gestión de transformaciones y equivalencias

Como administrador,
quiero gestionar las tablas de transformación de unidades y equivalencias de normas,
para mantener actualizada la base de conocimiento que usa el motor de matching.

**Acceptance Criteria:**

**Given** que el admin navega a `/admin/rule-engine/transforms`
**When** la página carga
**Then** muestra tabs: "Unidades" | "Normas" | "Materiales"
**And** cada tab muestra tabla editable con inline edit

**Given** que el admin agrega una nueva equivalencia en la tab "Normas"
**When** completa `norm_a`, `system_a`, `norm_b`, `system_b`, `equivalence_type` y guarda
**Then** se crea el registro en `norm_equivalences`
**And** aparece en la tabla inmediatamente

**Given** que el admin importa un CSV de equivalencias DIN/ASME
**When** el archivo se sube correctamente
**Then** se crean los registros en batch y se muestra resumen "N equivalencias importadas"

---

## EP-MRE-04: Agente IA — Optimizador de Reglas

**Objetivo:** Agente inteligente que analiza el performance de las reglas y sugiere mejoras al administrador.

---

### Story MRE-04-01: Tabla `rule_suggestions` y Celery beat de análisis

Como sistema,
quiero una task Celery periódica que analice el performance de cada familia y detecte brechas,
para alimentar al administrador con insights accionables sin intervención manual.

**Acceptance Criteria:**

**Given** que la task `mt.rule_engine.analyze_performance` corre (schedule: diario)
**When** analiza los datos de `match_rule_stats` + `match_candidates.label` de los últimos 7 días
**Then** para cada familia calcula: FP rate, FN rate estimado, avg tiempo confirmación
**And** si alguna métrica supera threshold (FP > 15% o FN > 20% o avg > 72h)
**Then** genera una entrada en `rule_suggestions` con `status=pending`

**Given** que la tabla `rule_suggestions` ya tiene una sugerencia pending para la familia
**When** la task corre de nuevo
**Then** NO genera una nueva sugerencia duplicada para la misma brecha

---

### Story MRE-04-02: Generación de sugerencias con Claude API

Como administrador,
quiero que las sugerencias de optimización estén redactadas en lenguaje natural con propuestas concretas,
para entender qué cambiar y por qué sin necesidad de interpretar datos crudos.

**Acceptance Criteria:**

**Given** que la task detecta una brecha de FP > 15% en la familia `ball_valve`
**When** llama a Claude API con el contexto de la regla y las métricas
**Then** Claude genera una sugerencia en español con: descripción del problema, causa probable, cambio propuesto (ej. "Aumentar peso de `dn` de 0.17 a 0.22 y reducir `brand_tier` de 0.07 a 0.02")
**And** el `proposed_change` se persiste como JSONB con los deltas concretos de pesos

**Given** que Claude API no está disponible
**When** la task intenta generar la sugerencia
**Then** persiste la sugerencia sin texto de IA (solo métricas crudas) y no propaga el error

---

### Story MRE-04-03: UI de sugerencias contextual en el editor

Como administrador,
quiero ver las sugerencias del agente directamente en el editor de la regla afectada y poder aplicarlas con un clic,
para cerrar la brecha de performance sin necesidad de calcular manualmente los ajustes.

**Acceptance Criteria:**

**Given** que existe una sugerencia `pending` para la familia `ball_valve`
**When** el admin abre `/admin/rule-engine/ball_valve`
**Then** aparece banner amarillo con el resumen de la sugerencia en lenguaje natural
**And** muestra botones "Aplicar cambio sugerido" y "Descartar"

**Given** que el admin hace clic en "Aplicar cambio sugerido"
**When** el sistema procesa
**Then** actualiza los pesos en `taxonomy_profiles` con los deltas del `proposed_change`
**And** marca la sugerencia como `status=applied`
**And** muestra toast "Cambio aplicado — aplica a nuevos matches"

**Given** que el admin hace clic en "Descartar"
**When** confirma el diálogo
**Then** marca la sugerencia como `status=dismissed`
**And** el banner desaparece de la vista

---

## Resumen de Implementación

| Epic | Historias | Complejidad | Dependencias |
|------|-----------|-------------|--------------|
| EP-MRE-01 Fundación de Datos | 4 | Media | Ninguna — arrancar aquí |
| EP-MRE-02 Motor Data-Driven + API | 5 | Alta | EP-MRE-01 completo |
| EP-MRE-03 UI Admin | 4 | Media | EP-MRE-02 completo |
| EP-MRE-04 Agente IA | 3 | Media | EP-MRE-02 + Claude API key |

**Orden de implementación recomendado:** EP-MRE-01 → EP-MRE-02 → EP-MRE-03 + EP-MRE-04 en paralelo (son independientes entre sí).
