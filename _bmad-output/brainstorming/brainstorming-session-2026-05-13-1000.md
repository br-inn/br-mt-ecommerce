---
stepsCompleted: [1, 2, 3, 4]
inputDocuments: []
session_topic: 'Mejora de usabilidad de la pantalla /catalogo/validacion'
session_goals: 'Mejorar comparación specs MT vs Amazon, visibilidad de progreso, densidad de información, flujo de decisión validar/descartar'
selected_approach: 'ai-recommended'
techniques_used: ['Reversal Inversion', 'SCAMPER Method', 'Dream Fusion Laboratory']
ideas_generated: [17]
session_active: false
workflow_completed: true
---

# Brainstorming Session Results

**Facilitador:** psierra
**Fecha:** 2026-05-13

## Contexto técnico

La pantalla `/catalogo/validacion` es un workflow de validación humana de matches de productos MT contra Amazon UAE.
Estado actual: tabla densa de 6 columnas, panel izquierdo con info de SKU, navegación prev/next por cola de SKUs pendientes.

---

## Técnica 1: Reversal Inversion — Mapa de dolores confirmados

| # | Desastre identificado | → Dirección de solución |
|---|---|---|
| T1 | Sin specs MT visibles para comparar | Split-view: ficha MT fija izquierda, candidatos derecha |
| T2 | Sin indicador de progreso de sesión | Barra de progreso `X de N SKUs validados` |
| T3 | Tabla densa, texto ilegible (10px, 6 cols) | Cards expandibles con info jerarquizada |
| T4 | Botones decisión en última columna, lejos del contexto | Botones inline en la card, junto a foto y precio |
| T5 | Sin foto del producto MT para comparar visualmente | Imagen MT prominente en panel fijo izquierdo |
| T8 | Sin salida "sin match" — SKU queda en limbo | Acción "Ninguno aplica" a nivel SKU con motivo opcional |
| T9 | Score no diferenciado visualmente | Score semáforo: verde >0.8, amarillo 0.5–0.8, rojo <0.5 |
| T10 | Sin bulk: cada candidato requiere clic individual | Checkbox multi-select + acción bulk validar/descartar |

---

## Técnica 2: SCAMPER — Ideas por lente

### S — Substitute
**[S2-B]**: Cola de SKUs colapsable a la izquierda
Panel izquierdo con lista de SKUs pendientes (código, nº candidatos, mejor score). Al seleccionar uno, el panel se colapsa automáticamente para dar todo el ancho a la vista de validación. Ícono/tab para re-expandir.
*Novelty*: Combina orientación de carga de trabajo con foco en la tarea — no sacrifica espacio por contexto.

### C — Combine
**[C4]**: Tabs inline Pendientes / Validados / Descartados dentro del panel de candidatos
Las tabs muestran el estado de todas las decisiones del SKU actual sin salir de la pantalla, con fecha y opción de revertir. Convierte la pantalla en el registro de auditoría en tiempo real.
*Novelty*: Elimina la necesidad de ir a `/audit` para consultar historial durante la validación.

### A — Adapt
**[A1]**: Snooze de candidato
Tercer estado temporal: el candidato sale de "Pendientes" y vuelve al final de la cola con nota opcional ("esperar precio actualizado", "consultar con proveedor"). No bloquea el avance al siguiente SKU.
*Novelty*: Elimina la presión de decidir con información incompleta — el "no sé" se convierte en acción explícita.

### M — Modify
**[M4]**: Header colapsado a barra de contexto de 36px
Reemplazar el header gradiente de ~90px por una barra delgada con breadcrumb `Validación › SKU-XXXX`, badge `47 pendientes`, y botón Re-scrape como ícono secundario.
*Novelty*: Recupera ~54px de altura para el área de comparación — cada pixel importa en un workflow de pantalla completa.

### P — Put to other uses
**[P1]**: SKU como elemento interactivo
El código SKU es clickeable (copia al portapapeles), con hover tooltip que muestra nombre del producto, tier y data quality — sin abrir otra pantalla.

**[P3]**: Contadores en tabs de filtro
`Pendientes (12) · Validadas (8) · Descartadas (3)` actualizados en tiempo real. El validador ve el progreso del SKU actual sin cambiar de tab.

### E — Eliminate
**[E1]**: Eliminar texto de deuda técnica expuesta
Remover "Stubs Sprint 3 (scraper Amazon real en S4)" del subtítulo del panel de candidatos.
*Fix inmediato — una línea de código.*

### R — Reverse
**[R1]**: Cola cross-SKU ordenada por nivel de confianza
Vista alternativa donde los candidatos se agrupan por score en lugar de por SKU: "Alta confianza (>0.85): 34 candidatos de 18 SKUs". El validador barre los de alta confianza en bulk primero (decisiones rápidas), luego invierte tiempo en los difíciles.
*Novelty*: Optimiza el throughput real — los fáciles se despachan en los primeros 5 minutos de sesión.

---

## Técnica 3: Dream Fusion Laboratory

**Visión confirmada:** "Todo lo suficiente para validar correctamente, en una sola pantalla."

**[D1]**: Split-view MT ↔ Amazon con campos espejados
Panel izquierdo fijo con ficha MT completa (foto, nombre, specs: material/PN/norma/rosca/tipo, precio objetivo). Panel derecho con cards de candidatos mostrando exactamente los mismos campos en el mismo orden vertical. Las diferencias entre MT y candidato se resaltan automáticamente.
*Novelty*: La comparación es visual, no mental — el ojo detecta diferencias sin leer porque los campos están alineados.

---

## Organización y Priorización

### Por temas

**Tema 1 — Arquitectura de comparación** *(dolor central)*
- D1: Split-view con campos espejados MT ↔ Amazon
- T1→: Specs MT visibles en pantalla
- T5→: Foto MT en panel fijo
- T3→: Cards expandibles reemplazando tabla densa
- T4→: Botones de decisión inline en la card

**Tema 2 — Gestión de la cola de trabajo**
- S2-B: Cola SKUs colapsable a la izquierda
- R1: Cola cross-SKU ordenada por nivel de confianza
- T2→: Barra de progreso de sesión
- P3: Contadores en tabs de filtro

**Tema 3 — Flujo de decisión enriquecido**
- T8→: Acción "Ninguno aplica" por SKU
- T10→: Bulk select + validar/descartar múltiples
- A1: Snooze de candidato
- C4: Tabs inline con histórico de decisiones

**Tema 4 — Señales visuales y polish**
- T9→: Score semáforo con desglose por dimensión
- P1: SKU interactivo con tooltip
- M4: Header reducido a barra 36px
- E1: Eliminar texto de deuda técnica

### Priorización impacto × esfuerzo

| Prioridad | Ideas | Justificación |
|---|---|---|
| 🔴 **Core** — rediseño necesario | D1, T1→, T5→, T3→, S2-B | Sin esto la pantalla sigue rota en su propósito principal |
| 🟡 **Alto valor** — sprint próximo | T8→, C4, T9→, P3, R1 | Mejoran el flujo sin rediseño total |
| 🟢 **Quick wins** — esta semana | E1, M4, P1, T4→ | 1–2 horas cada uno, mejora inmediata y perceptible |

---

## Resumen ejecutivo

**17 ideas generadas** en 3 técnicas sobre el problema de usabilidad de `/catalogo/validacion`.

El rediseño tiene un principio de diseño claro confirmado por el usuario:
> *"Todo lo suficiente para validar correctamente, en una sola pantalla."*

El cambio más impactante es estructural: convertir la pantalla de una **tabla de candidatos** a un **split-view de comparación MT ↔ Amazon** con cola de trabajo colapsable. El resto de las ideas mejoran el flujo sobre esa base.

Los quick wins (E1, M4, P1, P3) pueden entrar en cualquier sprint sin dependencias.
