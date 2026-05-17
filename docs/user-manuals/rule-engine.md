# Manual de Usuario — Motor de Reglas de Matching

## ¿Para qué sirve este módulo?

El Motor de Reglas de Matching permite al administrador configurar **cómo el sistema compara productos** del catálogo MT con ofertas de Amazon y Noon, sin necesidad de tocar código.

Antes de este módulo, los criterios de comparación estaban fijos en el código. Ahora son datos configurables: puedes cambiar el peso de cada dimensión de scoring, ajustar los umbrales de decisión, y recibir sugerencias automáticas del Agente IA cuando detecta que las reglas actuales tienen brechas.

---

## Acceso

Navegar a: `http://localhost:3000/admin/rule-engine`

Requiere rol **admin**.

---

## Conceptos clave

### Familias de producto
Cada tipo de producto (válvula de bola, manómetro, filtro strainer, etc.) tiene su propio perfil de reglas. Los perfiles se llaman **familias**.

### Dimensiones de scoring
Cuando el sistema compara un producto del catálogo con una oferta de Amazon/Noon, evalúa 10 dimensiones:

| Dimensión | Qué compara |
|---|---|
| `material` | Acero inoxidable, fundición, bronce... |
| `pn` | Presión nominal (bar / PN16, PN25...) |
| `dn` | Diámetro nominal (DN50, DN80, 2"...) |
| `product_type` | Válvula vs. filtro vs. manómetro |
| `thread_standard` | BSP, NPT, DIN... |
| `ways` | 2 vías, 3 vías (válvulas) |
| `norma` | DIN, ISO, ASME... |
| `brand_tier` | Marca premium vs. genérica |
| `delivery` | Tiempo de entrega |
| `data_completeness` | Completitud del ficha técnica |

### Pesos
Cada dimensión tiene un **peso** entre 0 y 0.5. Los pesos deben **sumar exactamente 1.0**.

Un peso mayor = esa dimensión tiene más influencia en el score final.

Ejemplo: Si `dn` tiene peso 0.17 y `brand_tier` tiene peso 0.07, el diámetro nominal es 2.4× más importante que la marca al calcular el match.

### Hard Blockers
Condiciones que **descartan automáticamente** un candidato, sin importar el score. Si el candidato activa un blocker, se clasifica como "unknown" directo.

Ejemplos de blockers: `dn_mismatch` (diámetro no coincide), `pn_below_sku_requirement` (presión insuficiente).

### Score de clasificación
El score final (0–100) se clasifica así:
- **≥ 70** → `peer` (match confirmado, pasa al pricing)
- **40–69** → `drop` (candidato descartado)
- **< 40** → `unknown` (encolado en HITL para revisión humana)

Los umbrales 70 y 40 son configurables en **Configuración Global**.

---

## Páginas del módulo

### 1. Dashboard principal `/admin/rule-engine`

Muestra todas las familias configuradas en tarjetas. Cada tarjeta muestra:
- Nombre de la familia
- Total de matches (últimos 30 días)
- Tasa de confirmación humana
- FP rate (falsos positivos)
- Badge amarillo si hay sugerencias del Agente IA pendientes
- Badge rojo si el FP rate supera el 15%

**Botón "Transformaciones de unidades"**: accede a la tabla de conversiones.

---

### 2. Editor de familia `/admin/rule-engine/{familia}`

Al hacer clic en una tarjeta del dashboard, accedes al editor de esa familia.

#### Panel de pesos
- Slider por cada dimensión (rango 0–0.50)
- Indicador de suma en tiempo real: debe mostrar `Suma: 1.000 ✓`
- Si la suma no es exactamente 1.000, el botón **Guardar cambios** permanece deshabilitado

> **Nota importante:** Los cambios solo aplican a **matches futuros**. Los candidatos ya generados no se reevalúan.

#### Hard Blockers
Checkboxes para activar/desactivar cada condición bloqueante. Los blockers marcados se aplican a todos los nuevos candidatos de esta familia.

#### Banner de sugerencias del Agente IA
Si el Agente detectó una brecha en las reglas, aparece un banner amarillo con:
- Descripción del problema en lenguaje natural (3 oraciones en español)
- Botón **Aplicar cambio sugerido**: aplica automáticamente el cambio propuesto
- Botón **Descartar**: ignora la sugerencia

---

### 3. Transformaciones de unidades `/admin/rule-engine/transforms`

Dos tabs:

#### Tab "Unidades"
Tabla de conversiones de unidades. Tipos disponibles:
- **numeric**: conversión por fórmula (ej. PSI → PN: `floor(value / 14.5038)`)
- **lookup**: tabla de equivalencias (ej. DN 50mm → `2"` NPS)
- **nominal**: equivalencias aproximadas (ej. DN50 ≈ 2" NPS, DN65 ≈ 2.5" NPS)

Cada fila tiene un botón **Eliminar** para borrar la transformación.

> **Cuidado:** Eliminar una transformación puede afectar el scoring de nuevos candidatos que dependan de esa conversión.

#### Tab "Normas"
Equivalencias entre estándares de normas (DIN ↔ ISO ↔ ASME). En construcción.

---

## Configuración Global

Accesible via API (no hay UI dedicada aún):

```
GET /api/v1/rule-engine/comparator-config
```

Parámetros configurables:

| Clave | Valor por defecto | Descripción |
|---|---|---|
| `peer_threshold` | 70 | Score mínimo para clasificar como "peer" (match válido) |
| `drop_threshold` | 40 | Score mínimo para clasificar como "drop" |
| `g1_median_multiplier` | 1.10 | Multiplicador sobre mediana del peer-group para precio G1 |
| `g2_multipliers` | `{default: 2.5, ...}` | Multiplicadores G2 por subtipo de material |
| `hitl_value_threshold_aed` | 1000 | Valor mínimo AED para encolar en HITL |

Para modificar un valor:
```
PUT /api/v1/rule-engine/comparator-config/{clave}
Body: { "value": <nuevo_valor> }
```

---

## El Agente IA

### ¿Qué hace?
Una vez al día (06:00 UTC) el sistema ejecuta automáticamente un análisis de las métricas de los últimos 7 días por familia. Si detecta alguna de estas brechas:

- **FP rate > 15%** → demasiados candidatos propuestos que el humano rechaza
- **Tasa de confirmación < 50%** → pocos candidatos son aceptados

El Agente llama a Claude Haiku y genera una sugerencia concreta en español: describe el problema, la causa probable, y propone un cambio exacto de pesos.

### ¿Cómo actuar sobre una sugerencia?
1. Abre la familia afectada en el editor
2. Lee el banner amarillo con el análisis del Agente
3. Si el cambio propuesto te parece razonable → **Aplicar cambio sugerido**
4. Si no estás de acuerdo → **Descartar** y ajusta los pesos manualmente

### Ejecución manual
Para disparar el análisis sin esperar al schedule diario:

```bash
docker exec mt-worker python -c "
from app.workers.tasks.rule_engine_analyzer import analyze_rule_performance
print(analyze_rule_performance())
"
```

---

## Flujo completo de trabajo recomendado

```
1. Dashboard principal
   → Identificar familias con FP rate alto o sugerencias pendientes

2. Editor de familia
   → Revisar sugerencia del Agente (si existe)
   → Aplicar sugerencia IA o ajustar pesos manualmente
   → Verificar que suma de pesos = 1.000
   → Guardar cambios

3. Esperar 24–48h para que el pipeline genere nuevos candidatos con las reglas actualizadas

4. Volver al Dashboard y verificar que mejoraron las métricas
```

---

## Valores iniciales (seed)

Las reglas fueron inicializadas con los valores que tenía el sistema hardcodeado, traducidos a datos configurables:

| Familia | Dimensión más pesada | Hard blockers principales |
|---|---|---|
| `ball_valve` / `valves_ball` | dn (0.17), material (0.17) | dn_mismatch, product_type_mismatch |
| `gate_valve` / `globe_valve` / `check_valve` | dn (0.17), material (0.17) | dn_mismatch, pn_below_sku_requirement |
| `strainer` / `FILTROS` | material (0.18), dn (0.18) | dn_mismatch, pn_below_sku_requirement |
| `pressure_gauge` / `MANOMETROS` | pn (0.19), product_type (0.18) | product_type_mismatch, pn_too_far_above |
| `_default` | brand_tier (0.18), material (0.18) | pn_below_sku_requirement, material_mismatch |

---

## Preguntas frecuentes

**¿Los cambios afectan matches ya procesados?**
No. Solo afectan a candidatos generados después de guardar los cambios.

**¿Puedo poner el mismo peso en todas las dimensiones?**
Sí, mientras sumen 1.0. Por ejemplo, 10 dimensiones con 0.10 cada una.

**¿Qué pasa si pongo un peso de 0.00 en `dn`?**
Esa dimensión no contribuye al score. Úsalo para familias donde el DN no es relevante (como el `_default`).

**¿El Agente IA puede aplicar cambios automáticamente sin mi aprobación?**
No. El Agente solo **sugiere**. La aplicación siempre requiere confirmación manual.

**¿Se puede deshacer un cambio de pesos?**
No hay historial de versiones aún. Anota los valores anteriores antes de cambiar, o restaura desde el seed inicial consultando la tabla `taxonomy_profiles` en la DB.

**¿Con qué frecuencia se actualiza la caché de reglas?**
Cada 5 minutos (TTL = 300s). Al guardar cambios desde la UI, la caché se invalida inmediatamente.
