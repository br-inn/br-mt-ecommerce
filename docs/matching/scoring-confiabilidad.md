# Evaluación de Confiabilidad del Match de Artículos

> **Versión**: 1.0 — Mayo 2026  
> **Módulo**: `mt-pricing-backend/app/services/matching/`  
> **Archivos clave**: `scoring.py`, `taxonomy_rules.py`, `match_service.py`

---

## 1. Visión General

El pipeline de matching asigna a cada candidato externo (Amazon UAE, Noon UAE) un **score de 0 a 100** que mide qué tan bien representa al SKU MT evaluado. Este score es multidimensional: cada dimensión evalúa un atributo técnico del artículo y contribuye al total ponderado.

```
Score final (0–100) = Σ (score_dimensión × peso_dimensión) × 100
```

El score determina la **clasificación del candidato** y su uso en el motor de pricing:

| Clasificación | Score | Uso |
|---|---|---|
| `peer` | ≥ 70 | Precio de mercado G1 (mediana × 1.10) |
| `drop` | 40–69 | Referencia secundaria, sin G1 |
| `unknown` | < 40 ó blocker | Descartado automáticamente |

---

## 2. Dimensiones de Scoring

### 2.1 Material (`material`)

Evalúa si el material del candidato es compatible con el SKU MT.

**Lógica:**
- Match exacto por homologación → `1.0`
- Misma familia de material (ej. `brass` vs `brass_cw617n`) → `0.75`
- Materiales distintos → `0.0` → genera nota `material_mismatch`
- Sin datos del candidato → `0.3` (penalización por datos incompletos)
- Sin datos de ambos → `0.5` (neutral)

**Scoring compuesto (body/ball/seat/stem):**  
Cuando el SKU define materiales por componente (tabla `product_materials`), se pondera por componente con pesos fijos: body=50%, ball=30%, seat=15%, stem=5%. Si el candidato no especifica un componente, recibe penalización leve (0.4) en lugar de mismatch.

**Detección desde título:**  
Para candidatos SERP-only (sin acceso a PDP), el material se extrae automáticamente del título cuando el campo `specs.material` está vacío. Ejemplo: "304 Stainless Steel" → `stainless_steel`.

---

### 2.2 Presión Nominal / PN (`pn`)

Evalúa si la presión nominal del candidato cumple o supera el requisito del SKU.

**Escala estándar**: PN6, PN10, PN16, PN25, PN40, PN63, PN100, PN160, PN250, PN400

| Caso | Score | Nota |
|---|---|---|
| Igual al SKU | 1.0 | — |
| +1 grado (ej. PN25 para PN16) | 0.85 | — |
| +2 grados | 0.55 | — |
| +3 grados | 0.20 | — |
| +4 grados o más | 0.0 | `pn_too_far_above` |
| Inferior al SKU | 0.0 | `pn_below_sku_requirement` |
| Sin datos | 0.5 | neutral |

Los candidatos de Amazon suelen expresar presión en PSI/WOG; el sistema convierte automáticamente (1 bar ≈ 14.5 PSI) y aproxima al grado PN más cercano.

---

### 2.3 DN / Tamaño (`dn`)

Evalúa si el diámetro nominal del candidato coincide exactamente con el SKU.

**Normalización cross-formato** — `_normalize_dn()` unifica:
- Pulgadas: `1/2"`, `1/2 inch`, `1/2in`, `½"` (comillas tipográficas)
- Métrico: `DN15`, `DN 15` → convertido a pulgadas canónicas
- Entero puro: `15` → lookup en tabla DN→inch

**Tabla de conversión DN↔pulgadas:**

| DN | Pulgadas |
|---|---|
| DN8 | 1/4" |
| DN15 | 1/2" |
| DN20 | 3/4" |
| DN25 | 1" |
| DN40 | 1-1/2" |
| DN50 | 2" |

| Caso | Score | Nota |
|---|---|---|
| Coincide (normalizado) | 1.0 | — |
| No coincide | 0.0 | `dn_mismatch` |
| Sin datos de alguno | 0.5 | neutral |

**Extracción desde título:** Cuando `specs.dn` y `specs.size` están vacíos, el sistema intenta extraer el tamaño del título del candidato. Ejemplo: "Ball Valve 1/2 Inch" → `size = "1/2"`.

---

### 2.4 Estándar de Rosca (`thread_standard`)

Evalúa compatibilidad del estándar de conexión. El sistema reconoce tres familias:

| Familia | Patrones detectados |
|---|---|
| `bsp` | BSP, BSPP, BSPT, G thread, ISO 228 |
| `npt` | NPT, NPTF, ANSI B1.20 |
| `metric` | Metric, DIN, M10–M20 |

| Caso | Score | Nota |
|---|---|---|
| Mismo estándar | 1.0 | — |
| Estándares distintos | 0.0 | `thread_standard_mismatch` |
| No se reconoce el estándar | comparación literal | — |
| Sin datos suficientes | 0.5 | neutral |

---

### 2.5 Tipo de Producto (`product_type`)

Evalúa si el candidato es del mismo tipo de artículo que el SKU.

- Detecta el tipo por palabras clave en el título/specs del candidato según la familia MT.
- Ejemplo: familia `HIDROSANITARIO` → busca "ball valve", "ball-valve" en el candidato.
- Incluye **mini qualifier**: si el SKU es "mini-ball" y el candidato no (o viceversa), genera `mini_mismatch`.

| Caso | Score | Nota |
|---|---|---|
| Tipo correcto | 1.0 | — |
| Tipo diferente | 0.0 | `product_type_mismatch` |
| Mini mismatch | 0.0 | `mini_mismatch` |
| Sin familia definida | 0.5 | neutral |

---

### 2.6 Número de Vías (`ways`)

Evalúa si el candidato tiene el mismo número de vías (2-way vs 3-way).

- Solo aplica cuando ambos el SKU y el candidato declaran número de vías.
- Sin información de alguno → neutral (0.5), no blocker.

| Caso | Score | Nota |
|---|---|---|
| Igual (ej. ambos 2-way) | 1.0 | — |
| Diferente | 0.0 | `ways_mismatch` |
| Sin datos | 0.5 | neutral |

---

### 2.7 Norma / Estándar (`norma`)

Evalúa si el candidato cumple la misma norma técnica que el SKU.

| Caso | Score |
|---|---|
| Misma norma exacta | 1.0 |
| Una contiene a la otra (ej. "ISO 228" vs "ISO 228/1") | 0.7 |
| Normas distintas | 0.2 |
| Solo uno tiene norma | 0.4 |
| Ninguno tiene norma | 0.5 |

---

### 2.8 Tier de Marca (`brand_tier`)

Evalúa la reputación de la marca del candidato.

| Caso | Score |
|---|---|
| Misma marca que el SKU MT | 1.0 |
| Marca tier-1 reconocida (Pegler, Arco, Giacomini, Apollo, Nibco, Viega) | 0.7 |
| Marca desconocida | 0.4 |
| Sin marca | 0.3 |

---

### 2.9 Entrega (`delivery`)

Evalúa la rapidez de entrega estimada del candidato.

| Plazo | Score |
|---|---|
| Mismo día / siguiente día | 1.0 |
| 2–3 días | 0.9 |
| 4–7 días | 0.7 |
| 8–14 días | 0.5 |
| Más de 2 semanas | 0.3 |
| Sin información | 0.5 |

---

### 2.10 Completitud de Datos (`data_completeness`)

Mide qué fracción de los **6 campos clave** tiene el candidato poblados. Penaliza candidatos donde todos los scores anteriores serían 0.5 neutral por falta de datos, distinguiéndolos de candidatos con specs reales que confirman el match.

**Campos evaluados:**
1. Material
2. Presión nominal (PN)
3. Rosca / conexión
4. DN / tamaño
5. Marca
6. Información de entrega

```
score = campos_presentes / 6
```

| Campos presentes | Score | Interpretación |
|---|---|---|
| 6/6 | 1.0 | Datos completos — score muy confiable |
| 4/6 | 0.67 | Datos suficientes |
| 2/6 | 0.33 | Datos mínimos — score incierto |
| 0/6 | 0.0 | Sin datos — score completamente especulativo |

---

## 3. Pesos por Familia de Producto

Los pesos de cada dimensión varían según la **familia del SKU MT**, priorizando las dimensiones más discriminantes para cada tipo de artículo.

### Válvulas de Bola / Ball Valves (`ball_valve`, `HIDROSANITARIO`)

| Dimensión | Peso |
|---|---|
| Material | **0.17** |
| DN / Tamaño | **0.17** |
| Estándar de rosca | **0.14** |
| Tipo de producto | 0.11 |
| PN | 0.11 |
| Completitud | 0.08 |
| Brand tier | 0.07 |
| Entrega | 0.06 |
| Vías | 0.05 |
| Norma | 0.04 |

### Filtros / Strainers (`strainer`, `FILTROS`)

| Dimensión | Peso |
|---|---|
| Material | **0.18** |
| DN / Tamaño | **0.18** |
| Tipo de producto | **0.14** |
| Estándar de rosca | **0.14** |
| PN | 0.11 |
| Completitud | 0.08 |
| Brand tier | 0.07 |
| Norma | 0.05 |
| Entrega | 0.05 |
| Vías | 0.00 |

### Manómetros (`pressure_gauge`, `MANOMETROS`)

| Dimensión | Peso |
|---|---|
| PN | **0.19** |
| Material | **0.18** |
| Tipo de producto | **0.18** |
| DN / Tamaño | 0.09 |
| Estándar de rosca | 0.09 |
| Completitud | 0.08 |
| Brand tier | 0.07 |
| Entrega | 0.07 |
| Norma | 0.05 |
| Vías | 0.00 |

### Default (familias sin perfil específico)

| Dimensión | Peso |
|---|---|
| Material | **0.18** |
| Brand tier | **0.18** |
| PN | 0.14 |
| Estándar de rosca | 0.14 |
| Norma | 0.14 |
| Entrega | 0.14 |
| Completitud | 0.08 |
| DN / Tamaño | 0.00 |
| Tipo de producto | 0.00 |
| Vías | 0.00 |

---

## 4. Blockers Duros (Hard Blockers)

Los blockers duros son notas de scoring que **fuerzan `kind=unknown`** y eliminan al candidato independientemente del score final. Representan incompatibilidades físicas donde cualquier precio sería engañoso.

### Blockers de Válvulas (`_BASE_VALVE_BLOCKERS`)

Aplican a todas las familias de válvulas (ball, gate, globe, check, butterfly, strainers):

| Nota | Descripción |
|---|---|
| `dn_mismatch` | Diámetro nominal diferente — artículo físicamente distinto |
| `material_mismatch` | Material incompatible — precio no comparable |
| `product_type_mismatch` | Tipo de producto diferente |
| `thread_standard_mismatch` | Estándar de rosca incompatible (BSP vs NPT) |
| `pn_below_sku_requirement` | Presión nominal inferior — no cumple especificación mínima |
| `pn_too_far_above` | Presión nominal excesivamente superior (+4 grados) |

### Blockers adicionales — Válvulas de Bola

| Nota | Descripción |
|---|---|
| `mini_mismatch` | Mini-ball vs full-size ball valve |
| `ways_mismatch` | 2 vías vs 3 vías |

### Blockers — Mariposa (`butterfly_valve`)

Incluye `ways_mismatch` por ser crítico en este tipo.

### Blockers — Manómetros

Solo bloquean: `product_type_mismatch`, `pn_below_sku_requirement`, `pn_too_far_above`. El DN no es blocker porque los manómetros se comparan principalmente por rango de presión.

---

## 5. Flujo Completo de Evaluación

```
SKU MT
  │
  ├─► QueryBuilder → genera query de búsqueda por canal (LLM cache)
  │
  ├─► Adapter (curl_cffi/patchright) → SERP → lista de candidatos raw
  │
  └─► Para cada candidato:
        │
        ├─► Normalización de campos
        │     ├── material_type → material
        │     ├── thread_type  → thread
        │     ├── thread_size  → size (si no hay size)
        │     ├── maximum_pressure → PN (convirtiendo PSI→bar→PN)
        │     ├── title → material (si specs vacío)
        │     └── title → size/DN (si specs vacío)
        │
        ├─► compute_scoring(sku_dict, cand_dict)
        │     ├── Obtiene perfil de taxonomía según familia del SKU
        │     ├── Calcula las 10 dimensiones
        │     └── Aplica pesos del perfil → score 0-100
        │
        ├─► _classify_candidate(score, notes, family)
        │     ├── Si alguna nota está en hard_blockers → unknown
        │     ├── score ≥ 70 → peer
        │     ├── score ≥ 40 → drop
        │     └── score < 40 → unknown
        │
        └─► Si kind == unknown o score < 40 → DELETE
            Si no → upsert en match_candidates
```

---

## 6. Clasificaciones de Candidatos y Uso en Pricing

### `peer` (score ≥ 70)
El candidato representa el mismo artículo con suficiente confianza. Se usa para calcular el **precio G1**:

```
Precio G1 = mediana(precios peers) × 1.10
```

### `drop` (40 ≤ score < 70)
Candidato relacionado pero no suficientemente similar. Se conserva como **referencia secundaria** pero no entra en el cálculo G1.

### `unknown` (score < 40 ó blocker duro)
Candidato incompatible o sin datos suficientes. Se **elimina automáticamente** de la base de datos al re-scrape.

---

## 7. Homologación de Materiales

El sistema mantiene una tabla de aliases de materiales (`material_aliases`) que permite reconocer equivalencias técnicas:

- `cw617n` → `brass` (latón naval)  
- `sw4nf` → `stainless_steel`
- `polypropylene` = `pp`
- `aisi316` = `ss316` = `stainless_steel`

La clase `MaterialNormalizer` se carga desde DB y expone dos métodos:
- `same_canonical(a, b)` → True si ambos materiales mapean al mismo canónico
- `same_family(a, b)` → True si pertenecen a la misma familia (ej. `brass` y `brass_dezincification_resistant`)

---

## 8. Limitaciones Actuales y Mejoras Planificadas

| Limitación | Impacto | Plan |
|---|---|---|
| Datos SERP-only (sin PDP) limitan score a ~69 | Candidatos buenos quedan en `drop` en lugar de `peer` | Pipeline LLM+visión extrae specs completas del PDP (patchright en producción) |
| Pesos hardcoded por familia | Requiere ajuste manual | Externalizar a tabla `comparator_config` |
| Tiers de marca limitados (6 marcas) | Muchas marcas válidas puntúan 0.4 | Seed desde tabla `brand_tiers` |
| Thread standard solo BSP/NPT/Metric | Algunos estándares industriales no se detectan | Ampliar `_THREAD_STD_PATTERNS` |
| Score por rosca solo detecta estándar, no tamaño | 1/4" BSP vs 1/2" BSP no se distinguen | Añadir dimensión `thread_size` separada |
