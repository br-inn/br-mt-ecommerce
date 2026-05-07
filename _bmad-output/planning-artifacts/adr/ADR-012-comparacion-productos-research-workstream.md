# ADR-012: Sistema de comparación de productos como research workstream (no port directo de v5.1)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Comercial Online MT, Gerente Comercial

## Contexto

El motor v5.1 actual (`match_scorer_v2.py`) usa matcher tier-keyword (T0 brand → T2 técnico → T3 funcional → T4 product_name → T5 fallback → NONE). **Falla en 15 % del catálogo** (34/224 sin match + 34 NONE en tier).

Trasplantar esa lógica reproduce el problema. Decisión adoptada en brief: **rediseñar el subsistema de comparación de productos como investigación dedicada**, no como "port".

Este es el workstream de mayor riesgo de Fase 1.

## Decisión

### Tratamiento como research workstream paralelo (S0–S7)

- Workstream **separado** del desarrollo Fase 1a / 1b.
- **Bloquea**: motor de pricing Fase 1 ≤ recomendación-de-canal. Si la investigación tarda más de lo esperado, Fase 1 entrega PIM + costos + pricing-sin-comparador y la comparación se difiere a **Fase 1.5**.
- Decisión gateada en S0.

### Preguntas de investigación a responder con evidencia

| Pregunta | Entregable |
|----------|-----------|
| Estrategia de búsqueda — cómo se generan candidatos por SKU (queries Amazon UAE / Noon / supplier sites; uso de specs vs nombre comercial; multi-idioma EN/AR) | Documento de estrategia con tasa de cobertura medida sobre las 224 referencias |
| Sourcing de datos — scraping vs API oficial vs datasets pagos (Keepa, DataForSEO, RapidAPI) vs partnership marketplace; coste, sostenibilidad, legalidad UAE | Decisión sourcing firmada con presupuesto mensual estimado |
| Comparación de imágenes — GPT-4o vision / Claude vision / Gemini / CLIP / SigLIP / open-CLIP / Pinecone Image / AWS Rekognition; latencia, coste por SKU, accuracy en hardware industrial | Benchmark con dataset etiquetado ≥ 50 pares true-match / true-mismatch + tabla coste-vs-accuracy |
| Comparación de datos técnicos — reglas duras (DN, PN, material, tipo, conexión) + similitud semántica; pesos justificados + tabla de "deal breakers" (DN distinto = no-match aunque imagen coincida) | Esquema scoring multi-dimensional |
| Calibración de confianza — Platt / isotonic / conformal prediction; threshold operativo | Curva de calibración + threshold sobre dataset etiquetado |
| Validación humana asistida — UI workflow para revisar candidatos sin ser cuello de botella; integración con flujo aprobación Gerente | Diseño UX "validación rápida" + estimación de carga semanal |

### Hipótesis a validar (no decisiones)

- Combinar embeddings imagen + embeddings texto técnico + reglas duras > cualquier dimensión sola.
- Modelos visión generales no rinden bien en hardware industrial sin fine-tuning ni specs estructuradas como contexto.
- pgvector + HNSW alcanza con < 1M filas; decisión de embeddings independiente del stack.

### Métricas objetivo

- False-positive < 2 %.
- False-negative < 10 %.
- Calibración: cuando dice 85 % → 85 % real.
- Cobertura ≥ 90 % de SKUs con candidato auditado por humano.

### Dataset de calibración

- **Real, etiquetado por humano** (no datos demo del Excel).
- Mínimo 50 pares true-match / true-mismatch para benchmark.
- Quién etiqueta + plazo: pregunta abierta S0 — candidato Champion del cambio + apoyo Comercial.

### Hooks dejados en Fase 1 (independientemente de si el research entrega o no)

- Tabla `competitor_listings` creada (ver ADR-011) con campos `match_score`, `match_status`, `match_method`, `embedding`.
- Service skeleton `ProductComparisonService` con interfaz pero implementación stub que retorna `not_implemented` o `manual_only`.
- UI placeholder "Sistema de comparación" con mensaje "research en curso, contacte Gerente Comercial".
- Cuando research entregue, se inyecta implementación real sin tocar el resto del sistema.

### Si no llega Fase 1

- Comunicar 2 semanas antes del cierre Fase 1b si los umbrales no se alcanzan.
- Diferir a Fase 1.5 (T+3 meses post Fase 1).
- Documentar lo aprendido + descartar lo que no rindió.

## Alternativas evaluadas

### Alternativa A: Port directo de v5.1 (`match_scorer_v2.py` → TypeScript)
- **Pros**: rápido, conocido.
- **Contras**: reproduce el problema (15 % del catálogo sin resolver). Esfuerzo de port sin valor añadido.
- **Veredicto**: descartada explícitamente en brief.

### Alternativa B: Comprar herramienta dedicada (Trax, Bossa, ProductIQ)
- **Pros**: capacidades probadas.
- **Contras**: dominio (válvulas industriales en UAE) es nicho — herramientas genéricas optimizan para retail consumer. Coste enterprise. Lock-in.
- **Veredicto**: descartada.

### Alternativa C: Dejarlo entero para Fase 1.5+ desde el día uno
- **Pros**: foco máximo en PIM + costos + pricing en Fase 1.
- **Contras**: research toma tiempo de incubación. Si arrancamos en Fase 1.5+ desde cero, arrancamos tarde. Mejor incubar en paralelo.
- **Veredicto**: descartada — research paralelo es más eficiente que serial.

## Consecuencias positivas

- Investigación dedicada = no se compromete arquitectura sin evidencia.
- Hooks reservados Fase 1 → integración no requiere refactor.
- Si research falla, Fase 1 no se compromete (fallback a Fase 1.5).
- Métricas objetivo claras → criterio go/no-go objetivo.

## Consecuencias negativas / riesgos

- Workstream paralelo requiere atención + dataset etiquetado humano. Mitigación: Champion del cambio dedica % a etiquetado.
- Si research no entrega, Fase 1 cierra sin comparador y MT sigue dependiendo del 85 % manual del Excel para esa funcionalidad.
- Coste sourcing puede ser bloqueador (scraping legal UAE incierto, APIs pagas $$$). Mitigación: decisión firmada en S0 con presupuesto.

## Cuándo revisar

- **S0**: confirmar dataset etiquetado + responsable + plazo.
- **S2**: primer benchmark intermedio.
- **S5**: primer go/no-go intermedio.
- **S7 menos 2 semanas**: go/no-go final — entregar Fase 1 o diferir a 1.5.
