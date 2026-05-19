---
stepsCompleted: [1, 2]
inputDocuments: []
session_topic: 'Módulo de gestión de reglas de matching de productos'
session_goals: 'Diseñar una propuesta de módulo que permita a usuarios modificar reglas de matching y evaluar los cambios arquitectónicos necesarios para implementarlo'
selected_approach: 'ai-recommended'
techniques_used: ['Question Storming', 'Morphological Analysis', 'Solution Matrix']
ideas_generated: []
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** psierra
**Date:** 2026-05-16

## Session Overview

**Topic:** Módulo de gestión de reglas de matching de productos
**Goals:** Diseñar una propuesta de módulo que permita a usuarios modificar reglas de matching y evaluar los cambios arquitectónicos necesarios para implementarlo

### Session Setup

_Sesión iniciada para explorar opciones de diseño de un módulo que permita a los usuarios configurar y ajustar las reglas del pipeline de matching de productos (Amazon/Noon)._

## Técnicas Seleccionadas

**Enfoque:** AI-Recommended — Secuencia estructurada para diseño técnico con evaluación arquitectónica

- **Técnica 1 — Question Storming [deep]:** Generar las preguntas correctas antes de buscar soluciones. Scope, constraints y requisitos clave.
- **Técnica 2 — Morphological Analysis [deep]:** Explorar sistemáticamente todas las dimensiones del problema: tipos de reglas × configuración × UI × backend.
- **Técnica 3 — Solution Matrix [structured]:** Grilla de tipos de reglas vs. enfoques de implementación para identificar combinaciones óptimas.

**Racional IA:** Topic técnico complejo con sistema existente — secuencia prioriza definición correcta del problema antes de soluciones, luego exploración sistemática del espacio de soluciones.

## Técnica 2: Morphological Analysis — Resultados

**[Matching #17]**: Anatomía Real — 9 Dimensiones de Scoring Hardcodeadas
_Concepto_: `material`, `pn`, `dn`, `thread_standard`, `norma`, `brand_tier`, `delivery`, `product_type`, `ways` + `data_completeness`. TODOs en código dicen explícitamente `externalizar a comparator_config`.
_Novedad_: El nombre de la tabla destino ya existe en los TODOs del código.

**[Matching #18]**: Mapa Externalizar vs. Crear
_Concepto_: (A) Externalizar: pesos, thresholds, blockers, G2 multipliers, brand_tiers → tablas configurables. (B) Crear nuevas: `norm_equivalences`, `nominal_mappings`, extender `material_aliases`.
_Novedad_: Migración incremental — las reglas semilla son el código actual traducido a datos.

**[Matching #19]**: Arquitectura de Datos — 5 Tablas Especializadas
_Concepto_: `taxonomy_profiles` + `unit_transforms` + `norm_equivalences` + `comparator_config` + `material_aliases`. Cada tabla con esquema validable, no JSONB genérico.
_Novedad_: Híbrido que mantiene integridad referencial sin explotar en complejidad migratoria.

**[Matching #20]**: Agente IA — Celery Beat + Claude API
_Concepto_: Task periódica de Celery analiza estadísticas, Claude interpreta y genera sugerencias en lenguaje natural persistidas en `rule_suggestions`. Admin las ve pre-computadas al abrir una regla.
_Novedad_: Async por diseño — LLM nunca bloquea la UI. Reutiliza infraestructura Celery existente.

## Técnica 3: Solution Matrix — Plan de Implementación

### Decisión arquitectónica: Backend + Frontend juntos en un solo epic

**Justificación:** El admin necesita ver y editar reglas desde el primer entregable. UI sin backend no tiene valor; backend sin UI obliga al admin a editar SQL directamente. Se implementan juntos.

---

### EPIC: Match Rule Engine — Motor de Reglas Configurable

#### FASE 1 — Fundación de Datos (Alembic Migrations)

**Migración 1: `comparator_config`**
- Tabla de escalares globales: `key` (string) + `value` (JSONB) + `description`
- Seed: `peer_threshold=70`, `drop_threshold=40`, `g1_median_multiplier=1.10`, `g2_multipliers={default:2.5, stainless:3.0, cast_iron:2.0}`
- Reemplaza constantes en `match_service.py` y `scoring.py`

**Migración 2: `taxonomy_profiles`**
- Columnas: `id`, `family` (unique), `weights` (JSONB), `hard_blockers` (text[]), `description`, timestamps
- Seed: traducción exacta de `TAXONOMY_PROFILES` dict en `taxonomy_rules.py` (ball_valve, gate_valve, strainer, pressure_gauge, _default, etc.)
- Reemplaza `taxonomy_rules.py` hardcoded

**Migración 3: `unit_transforms`**
- Columnas: `id`, `transform_type` (numeric/lookup/nominal), `from_unit`, `to_unit`, `formula` (para numeric), `lookup_table` (JSONB para tablas), `description`
- Seed: PSI→PN (formula: `PN = floor(PSI/14.5)`), DN metric→inches lookup table
- Reemplaza conversiones hardcodeadas en `scoring.py`

**Migración 4: `norm_equivalences`**
- Columnas: `id`, `norm_a`, `system_a`, `norm_b`, `system_b`, `equivalence_type` (exact/subset/compatible), `notes`
- Seed vacío — el admin carga las equivalencias DIN↔ISO↔ASME

**Migración 5: `match_rule_stats`**
- Columnas: `id`, `match_candidate_id` (FK), `taxonomy_profile_id` (FK nullable), `score_breakdown` (JSONB), `dimensions_fired` (text[]), `created_at`
- Instrumenta qué reglas se aplicaron y con qué resultado

**Migración 6: `rule_suggestions`**
- Columnas: `id`, `taxonomy_profile_id` (FK nullable), `suggestion_type` (false_positive/false_negative/slow_confirmation), `analysis_summary` (text), `proposed_change` (JSONB), `status` (pending/applied/dismissed), timestamps

---

#### FASE 2 — Motor Data-Driven (Backend Refactor)

**Refactor `scoring.py`:**
- Eliminar `SCORING_WEIGHTS`, `_VALVE_WEIGHTS`, `_STRAINER_WEIGHTS`, `_GAUGE_WEIGHTS`, `_DEFAULT_WEIGHTS` hardcodeados
- `compute_scoring()` recibe `weights: dict` desde DB vía `TaxonomyProfileRepository`
- Conversiones PSI→PN y DN→inches leen desde `UnitTransformRepository`

**Refactor `taxonomy_rules.py`:**
- `get_profile(family)` consulta `taxonomy_profiles` en DB
- Cache en memoria con TTL (5 min) para no ir a DB en cada match del worker
- `TaxonomyProfileRepository` con `get_by_family()` y `list_all()`

**Refactor `match_service.py`:**
- `PEER_SCORE_THRESHOLD` y `DROP_SCORE_THRESHOLD` leen de `comparator_config`
- Instrumentación: después de `upsert_candidate()`, insertar en `match_rule_stats`

**Nuevo `RuleEngineRepository`:**
- Carga lazy + cache de toda la configuración activa
- Invalida cache cuando admin modifica una regla (event via Redis pub/sub o simple TTL)

---

#### FASE 3 — API de Gestión de Reglas (FastAPI)

**Nuevos endpoints `/api/v1/rule-engine/`:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/taxonomy-profiles` | Lista todos los perfiles de familia |
| GET | `/taxonomy-profiles/{family}` | Detalle con weights + blockers + stats |
| PUT | `/taxonomy-profiles/{family}` | Actualizar pesos y blockers |
| POST | `/taxonomy-profiles/{family}/simulate` | Dry-run con regla propuesta |
| GET | `/unit-transforms` | Lista transformaciones de unidades |
| POST | `/unit-transforms` | Crear nueva transformación |
| PUT | `/unit-transforms/{id}` | Editar transformación |
| GET | `/norm-equivalences` | Lista equivalencias de normas |
| POST | `/norm-equivalences` | Crear equivalencia |
| GET | `/comparator-config` | Leer configuración global |
| PUT | `/comparator-config/{key}` | Editar valor global |
| GET | `/rule-suggestions` | Sugerencias del agente pendientes |
| POST | `/rule-suggestions/{id}/apply` | Aplicar sugerencia (genera PUT automático) |
| POST | `/rule-suggestions/{id}/dismiss` | Descartar sugerencia |

---

#### FASE 4 — UI Admin (Frontend Next.js)

**Ruta: `/admin/rule-engine`**

**Página principal:**
- Tabla de familias con métricas: total matches, tasa confirmación, FP rate, sugerencias pendientes
- Badge de alerta si el agente detectó deficiencias
- Botón "Nueva familia"

**Página de familia `/admin/rule-engine/[family]`:**
- Panel izquierdo: editor de pesos con sliders + validación suma=1.0
- Panel derecho: hard blockers — checkboxes con descripción de cada blocker
- Sección inferior: estadísticas (gráfico de tasa confirmación últimos 30 días)
- Banner amarillo si hay sugerencias del agente pendientes con resumen en lenguaje natural
- Botón "Simular cambios" → dry-run que muestra preview de matches afectados

**Página de transformaciones `/admin/rule-engine/transforms`:**
- Tabs: Unidades | Normas | Materiales
- Tabla editable de conversiones con inline edit
- Importar equivalencias DIN/ASME desde archivo CSV

---

#### FASE 5 — Agente IA (Celery Beat + Claude API)

**Nueva task Celery: `mt.rule_engine.analyze_performance`**
- Schedule: cada 24h (configurable desde `job_definitions`)
- Lógica:
  1. Para cada `taxonomy_profile` activo, calcular métricas de los últimos 7 días: FP rate, FN rate, avg time to confirm
  2. Si alguna métrica supera threshold (FP > 15%, FN > 20%, avg_confirm > 72h)
  3. Enviar análisis a Claude API con contexto de la regla actual + métricas
  4. Claude genera sugerencia en español con cambio propuesto concreto
  5. Persistir en `rule_suggestions` con `status=pending`

**Prompt Claude:**
```
Eres un experto en matching de productos industriales.
Familia: {family}, Pesos actuales: {weights}, Blockers: {blockers}
Métricas últimos 7 días: FP={fp_rate}%, FN={fn_rate}%, tiempo_confirmacion={avg_hours}h
Analiza y propone 1 ajuste concreto para mejorar el performance.
```

---

#### RESUMEN DE CAMBIOS POR CAPA

| Capa | Archivos modificados | Archivos nuevos |
|---|---|---|
| **DB** | — | 6 migraciones Alembic |
| **Models** | — | `taxonomy_profile.py`, `unit_transform.py`, `norm_equivalence.py`, `match_rule_stat.py`, `rule_suggestion.py` |
| **Repositories** | — | `taxonomy_profile.py`, `rule_engine.py`, `unit_transform.py` |
| **Services** | `scoring.py`, `taxonomy_rules.py`, `match_service.py` | `rule_engine_cache.py` |
| **Workers** | `celery_config.py` (job_definitions) | `rule_engine_analyzer.py` |
| **API Routes** | `__init__.py` | `rule_engine.py` |
| **Frontend** | — | `/admin/rule-engine/` (página principal + familia + transforms) |
| **Tests** | — | Tests unitarios scoring data-driven, tests API rule-engine |

## Técnica 1: Question Storming — Resultados

**[Matching #1]**: Pipeline en Capas por Tipo de Producto
_Concepto_: Matching opera en capas — primero specs técnicas, luego comparación visual. La lógica de escalado varía por tipo de producto.
_Novedad_: Configuración jerárquica por tipo de producto, no regla global única.

**[Matching #2]**: Reglas Dinámicas en Base de Datos
_Concepto_: Reglas NO en código — persistidas en BD, editables en runtime sin redeploy.
_Novedad_: Motor de reglas interpretado en tiempo de ejecución.

**[Matching #3]**: Perfil de Configurador — Administrador
_Concepto_: Usuario con conocimiento técnico del dominio pero no developer. UI poderosa pero no de código.
_Novedad_: Editor visual con validaciones, no texto libre ni IDE.

**[Matching #4]**: Tablas de Transformación de Unidades
_Concepto_: Normalización de unidades antes de comparar (1 inch = 25.4mm). Librería de conversiones configurable y reutilizable.
_Novedad_: Normalización como ciudadano de primera clase, no hack ad-hoc.

**[Matching #5]**: Tablas de Equivalencia de Materiales
_Concepto_: AISI 304 = EN 1.4301 = SUS304. Relación muchos-a-muchos entre nomenclaturas.
_Novedad_: Editor de equivalencias diferente al de unidades — no es fórmula matemática.

**[Matching #6]**: Equivalencia de Normas DIN/ASME
_Concepto_: DIN 912 ↔ ISO 4762 ↔ ASME B18.3. Normas con niveles de compatibilidad (exacto, subconjunto, compatible con restricciones).
_Novedad_: Equivalencia con grados de precisión, más rica que igual/distinto.

**[Matching #7]**: DN y PN — Equivalencias Nominales con Tolerancia
_Concepto_: DN50 ↔ 2" NPS, PN16 ↔ Class 150. Mapeo de tablas normativas con equivalencia aproximada por estándar.
_Novedad_: Cuarto tipo de transformación — nominal con grados de precisión.

**[Matching #8]**: Agente IA de Optimización de Reglas
_Concepto_: Analiza historial HITL vs. matches propuestos, identifica deficiencias, sugiere ajustes concretos.
_Novedad_: Ciclo de retroalimentación inteligente — evidencia empírica informa optimización de reglas.

**[Matching #9]**: Tres Brechas que el Agente Debe Cerrar
_Concepto_: (1) Falsos positivos — alta confianza pero humano rechaza; (2) Falsos negativos — sin match pero debería tenerlo; (3) Confirmaciones lentas — confianza baja que bloquea HITL.
_Novedad_: Cada brecha requiere estrategia distinta del agente.

**[Matching #10]**: Reglas Prospectivas + Modo Simulación
_Concepto_: Cambios aplican solo a matches futuros. Dry run contra catálogo existente antes de activar.
_Novedad_: Estados de regla: borrador → simulado → activo. El admin ve impacto antes de comprometerse.

**[Matching #11]**: Reglas Compartidas Entre Tipos de Producto
_Concepto_: Una regla puede aplicar a múltiples tipos de producto. Reutilización de lógica común sin duplicar.
_Novedad_: Modelo muchos-a-muchos entre reglas y tipos de producto, con overrides específicos por tipo.

**[Matching #12]**: Sistema Auto-Evolutivo — Agente con Memoria Acumulativa
_Concepto_: Agente acumula conocimiento de cada ciclo de confirmaciones. Aprende qué reglas funcionan para qué tipos, qué transformaciones reducen FP, qué patrones de rechazo se repiten.
_Novedad_: Motor que mejora solo — el admin interviene cada vez menos.

**[Matching #13]**: Agente Contextual en la Gestión de Reglas
_Concepto_: Agente integrado dentro del editor de reglas. Admin ve estadísticas de performance al abrir una regla. Cuando detecta deficiencia, alerta desde ahí. Admin solicita ajuste, agente formula propuesta para aprobar.
_Novedad_: Co-piloto contextual — sugerencia + aprobación humana. No automático, no externo.

**[Matching #14]**: Reemplazo Total con Migración de Reglas Semilla
_Concepto_: Nuevo módulo reemplaza completamente el motor actual. Reglas hardcodeadas migran como "reglas semilla" — primera configuración inicial visible y modificable por el admin.
_Novedad_: Conversión de lógica implícita (código) a lógica explícita (datos). Nada se tira, todo se convierte.

**[Matching #15]**: Estadísticas de Matching — Capa Nueva
_Concepto_: Instrumentar pipeline para registrar por match: regla aplicada, score de confianza, resultado HITL, tiempo hasta confirmación.
_Novedad_: Estadísticas como datos operacionales en tiempo real, no reportes.

**[Matching #16]**: Reglas Globales por Producto, Ejecutadas en Scraping
_Concepto_: Reglas agnósticas al marketplace. Se ejecutan en Celery durante scraping al generar candidatos por SKU.
_Novedad_: Una sola regla cubre todos los marketplaces. Marketplace es metadata del candidato, no dimensión de la regla.
