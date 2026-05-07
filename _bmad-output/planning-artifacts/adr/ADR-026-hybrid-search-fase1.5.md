# ADR-026: Hybrid search lexical + semántico — pgvector Fase 1, Elasticsearch + RRF como upgrade path

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), TI MT
- Related: ADR-002 (single Postgres DB), ADR-011 (IA-ready hooks), ADR-012

## Contexto

El stack del spike v1.0 elige **pgvector + HNSW** como vector store (sobre la Postgres existente, alineado con ADR-002 single-DB). Para búsqueda lexical complementaria se propone Postgres `tsvector` simple.

La recomendación externa al sponsor (2026-05-06) introduce un patrón adicional: **hybrid search con Reciprocal Rank Fusion (RRF)**, combinando BM25 (lexical) + vector search (semántico) y fusionando vía RRF (referencia: Elastic blog *"Hybrid search using RRF"*).

Razones para considerarlo:
- BM25 captura matches exactos (códigos `DN50`, part numbers `PG2050`) que el vector puede diluir.
- Vector captura sinónimos / paráfrasis.
- RRF combina rankings sin necesidad de calibrar pesos; robusto a escalas distintas.
- Elasticsearch aporta analizador árabe nativo (stemming + normalización) que `tsvector` simple no tiene; útil cuando AR pase a expansión default.

Trade-off: Elasticsearch añade un contenedor + operación + monitoreo; rompe el "todo en Postgres" de ADR-002.

## Decisión

**Fase 1**: mantener **pgvector (HNSW) + Postgres `tsvector`** simple. Implementar fusión RRF en código (función SQL CTE union ranking) cuando el scorer lo requiera. No introducir Elasticsearch.

**Upgrade path Fase 1.5 / Fase 2 → Elasticsearch + RRF nativo**, gateado por cualquiera de:
1. Catálogo activo > 100 000 entidades (productos + listings).
2. Necesidad de búsqueda lexical multilingüe AR rica (cuando AR pase a expansión default y `tsvector('simple')` no rinda).
3. Cross-language retrieval requerido (un query AR debe matchear documentos EN y viceversa).
4. Latencia p95 BM25 sobre `tsvector` > 200 ms en producción.

Cuando se active el upgrade, Elasticsearch convive con Postgres (no reemplaza pgvector necesariamente; puede usarse Elasticsearch para BM25 multilingüe + pgvector para vectores, y aplicar RRF en aplicación).

## Alternativas evaluadas

- **Elasticsearch + RRF desde Fase 1**: añade overhead operativo (contenedor + memoria + monitoreo + backup) sin beneficio claro a 224-5k SKUs. Descartado para Fase 1.
- **Pinecone / Weaviate / Qdrant managed**: alternativas vector-store-managed; no resuelven la parte lexical. Documentadas como opciones en el spike §12.4.
- **Sólo vector search (sin lexical)**: pierde matches exactos en codes (DN50, PG2050). Descartado.

## Consecuencias positivas

- Fase 1 simple: una dependencia (Postgres) para PIM + pricing + catálogo + vectores + lexical básico.
- pgvector escala bien hasta ~1M filas según benchmarks; el catálogo Fase 1 (5k SKUs × 5-20 candidatos = 25-100k filas) está muy lejos del techo.
- Upgrade path documentado y gateado: no hay sorpresa cuando llegue.

## Consecuencias negativas / riesgos

- `tsvector('simple')` no hace stemming; búsquedas en EN sobre `gate valves` vs `gate valve` requieren normalización en aplicación. Asumible Fase 1.
- Sin AR analyzer nativo: AR queda relegado a query-time translation (spike §2.2). Asumible Fase 1.
- Cuando se active el upgrade, RRF en código deberá portarse a RRF nativo de Elasticsearch; coste de migración 1-2 sprints estimados.

## Cuándo revisar

- Cuando catálogo activo > 50 000 entidades (chequeo proactivo, antes de techo).
- Cuando el operador encuentre query latency p95 BM25 > 200 ms.
- Cuando AR pase de expansión condicional a primaria (probablemente Fase 2-3).
- En cualquier replanteo de ADR-002 (single Postgres DB).
