# ADR-038: Roadmap evolutivo del comparador — RAG → Hybrid → GraphRAG

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT, Ontólogo PVF (TBD)
- Supersedes: —
- Refines: ADR-012 (research workstream), ADR-026 (Hybrid Search Fase 1.5)
- Relacionados: ADR-039 (ontología KG), ADR-040 (seed compatibilidad materiales), ADR-041 (CDC Postgres↔Neo4j)

## Contexto

El subsistema de comparación de productos PVF tiene targets de precisión muy altos (FP < 2 %, FN < 10 %, calibración ECE < 5 %, cobertura ≥ 90 %). Una arquitectura puramente RAG vectorial llega a 85-92 % en escenarios típicos PVF, pero el dominio es estructuralmente grafo: equivalencias entre marcas (`Crane ↔ Apollo ↔ Milwaukee`), cumplimiento de normas (`API 598`, `ISO 7-1`, `UNE-EN 1074-3`), compatibilidades mecánicas (DN, PN, conexión, material × temperatura) y jerarquías Producto → Serie → Modelo → Variante. Para ese dominio, un knowledge graph permite queries deterministas que el LLM no puede igualar.

A la vez, **arrancar con GraphRAG en Fase 1 es sobre-ingeniería**: requiere ontólogo experto en PVF, 2-4 meses de construcción del grafo y CDC desde el PIM. El catálogo Fase 1 (224 SKUs reales, ~5 086 PIM, ~4 182 catálogo) se puede comparar con éxito con RAG + reglas duras.

La recomendación externa (2026-05-06) propone una arquitectura híbrida en 4 capas (KG + embeddings como properties + Cypher determinista + LLM judge sobre subgrafo), introducida en fases.

## Decisión

**El comparador evoluciona en 3 fases. Las abstracciones se preservan desde Fase 1 para no requerir refactor cuando se introduzca el grafo.**

| Fase | Ventana | Stack | Target precisión |
|------|---------|-------|------------------|
| **Fase 1** (actual) | 0-3 m | RAG vectorial (pgvector + HNSW) + reglas duras (BR-CMP-01 deal breakers) + VLM judge en zona gris. **Sin Neo4j en producción.** | **85-92 %** |
| **Fase 1.5 / 2** | 3-6 m | Hybrid Graph + RAG. Knowledge graph inicial en Neo4j con entidades core (`Producto`, `Fabricante`, `Material`, `Norma`, `Tamaño`). Vector search top-50 → graph filter por hard constraints. Seed desde compatibilidad materiales + whitelist fabricantes + estándares. | **92-95 %** |
| **Fase 2.5 / 3** | 6-12 m | GraphRAG completo. LLM razona sobre subgrafo enriquecido (fabricante + equivalencias + normas + imagen). Cypher determinista para deal breakers; LLM solo judge. | **96-98 %** |

**Hooks Fase 1 que evitan refactor**:

- Puerto `ComparatorService` con adapter `RagOnlyComparatorAdapter` en Fase 1; `HybridGraphRagAdapter` en Fase 2; `FullGraphRagAdapter` en Fase 3.
- Puerto `GraphRepository` (ya documentado en ADR-037). Backend `PostgresGraphRepository` Fase 1 (joins / recursive CTEs); backend `Neo4jGraphRepository` Fase 2+ (Cypher).
- Reglas duras (`BR-CMP-01`) ya hoy se ejecutan en código separadas del LLM; en Fase 2 migran a Cypher sin tocar el orquestador.

## Alternativas evaluadas

- **GraphRAG desde Fase 1**: rechazada. Sobre-ingeniería: 2-4 m de construcción de grafo bloquearían el cierre de Fase 1; sin ontólogo PVF contratado el modelo de datos sería pobre; coste operativo Neo4j + CDC para 224 SKUs no se amortiza.
- **RAG-only forever**: rechazada. No escala a 96-98 % de precisión que el dominio PVF requiere para procurement industrial; equivalencias entre marcas y matching por norma no se resuelven con embeddings + reglas planas.
- **Hybrid Search lexical + vector (Elasticsearch + RRF)** como sustituto del KG: no es alternativa; es **complementaria**. Documentada en ADR-026 como upgrade path Fase 1.5/2 sobre el lado retrieval; el KG ataca el lado del razonamiento. Pueden convivir.
- **Apache AGE (Postgres con Cypher)** en lugar de Neo4j: queda como **fallback open-source** de Fase 2 si Neo4j Aura genera lock-in o issues de costo en UAE. No es default por madurez del ecosistema (`neo4j-graphrag`, integraciones LlamaIndex/LangChain).

## Consecuencias positivas

- **Roadmap explícito** alineado con presupuesto y equipo: cada fase suma valor sin requerir el siguiente nivel.
- **Sin refactor**: las abstracciones desde Fase 1 absorben el cambio.
- **Decisión gateada por evidencia**: si Fase 1 alcanza 92 % por sí sola, Fase 2 se prioriza por otros criterios (cross-sell, intercambiabilidad).
- **MT puede contratar al ontólogo PVF al cierre de Fase 1** sin presión de bloqueo.

## Consecuencias negativas / riesgos

- **Riesgo de sobre-ingeniería en Fase 1** si algún equipo lee el roadmap y empuja Neo4j ya: mitigación — vetado explícitamente en este ADR; pgvector+HNSW único almacén Fase 1.
- **Riesgo de lock-in Cypher** en Fase 2+: mitigación — Apache AGE como fallback documentado.
- **Recurso ontólogo PVF es escaso**: mitigación — flag al programa, reclutamiento al cierre Fase 1.
- **CDC Postgres↔Neo4j puede dejar el grafo stale**: ver ADR-041.

## Cuándo revisar

- **Cierre Fase 1b (G4)**: revisar precisión real del RAG-only vs target 85-92 %. Si alcanza 92 %+, validar que Fase 2 sigue justificada por casos de uso (cross-sell, intercambiabilidad) y no solo por precisión incremental.
- **Antes de S1 Fase 2**: confirmar contratación del ontólogo PVF; sin ese recurso, NO arrancar construcción del grafo.
- **Cierre Fase 2**: revisar si el salto a GraphRAG completo (Fase 3) entrega 96-98 % real o se queda en 94-95 %.
