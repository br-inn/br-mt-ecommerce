---
adr: "ADR-074"
title: "GraphRAG evolution roadmap — Fase 1 stub + outbox CDC → Fase 2 Neo4j Aura → Fase 3 GraphRAG retrieval"
status: "proposed"
date: "2026-05-07"
author: "Pablo Sierra (Comercial · Online)"
deciders: ["Champion MT", "Equipo R&D BR (matcher)", "TI MT", "Ontólogo PVF (TBD)"]
related:
  - "ADR-038-roadmap-rag-hybrid-graphrag.md"
  - "ADR-039-ontologia-kg.md"
  - "ADR-041-cdc-postgres-neo4j.md"
  - "ADR-073-vlm-judge-prompt-spec.md"
sprint: "S4"
project: "mt-pricing-mdm-phase1"
supersedes: []
superseded_by: []
---

# ADR-074 — GraphRAG evolution roadmap

## 1. Contexto

US-RND-01-11 (Sprint 4) abre **Fase 2 R&D** con scaffold GraphRAG. ADR-038 ya definió la **estrategia macro** (RAG-only Fase 1 → Hybrid Fase 2 → GraphRAG Fase 3). Esta ADR-074 baja a **decisiones técnicas concretas** del scaffold S4 y del path evolutivo:

- ¿Qué backend de grafo? (Neo4j Aura vs Apache AGE vs in-memory).
- ¿Cómo replicar Postgres → graph store? (CDC outbox vs Realtime).
- ¿Qué mapping schema PIM → grafo?
- ¿Cuándo activar cada fase y bajo qué gates?

Sprint 4 implementa el **stub in-memory + outbox CDC + schema mapper** de modo que Fase 2 sea swap-only (sin refactor del comparador o del pipeline matching).

## 2. Decisión

### 2.1 Tres fases con gates explícitos

| Fase | Sprint range | Backend grafo | CDC mechanism | Retrieval | Coste mensual |
|------|--------------|---------------|---------------|-----------|---------------|
| **Fase 1 (Sprint 4)** | S4 (now) | `Neo4jStubGraphStore` (in-memory dict) | Outbox `cdc_events` table + polling task Celery | RAG vectorial pgvector (existing) | $0 |
| **Fase 2** | S6-S7 | **Neo4j Aura** (managed) | Outbox `cdc_events` + Realtime listener (Supabase) | Hybrid: RAG retrieval + graph filter por hard constraints | ~$50-100/mes Aura starter |
| **Fase 3** | S9+ | Neo4j Aura + vector index | Realtime + embeddings sync | Full GraphRAG: subgraph retrieval + LLM judge sobre subgrafo | ~$150-300/mes (Aura + embedding cost) |

### 2.2 Decisión de backend Fase 2: Neo4j Aura (managed)

**Adoptamos Neo4j Aura** (Neo4j managed cloud, region `eu-west-1` o `me-central-1` UAE) como destino Fase 2. Justificación:

- **Maturity ecosistema Cypher**: integraciones `neo4j-graphrag`, LlamaIndex, LangChain → reduce custom code.
- **Vector index nativo**: Neo4j 5.13+ soporta vector index sobre node properties → habilita Fase 3 sin migración.
- **Managed**: Aura gestiona backups, upgrades, HA. TI MT no quiere operar Neo4j on-prem.
- **Coste predecible**: Aura Free tier (1 GB) suficiente para Fase 2 prototipo; AuraDB Professional ~$65/mes para 8 GB.

**Alternativa Apache AGE (Postgres extension con Cypher)**:
- ✅ No introducir nuevo motor (Postgres ya en stack Supabase).
- ✅ Coste cero (incluido).
- ❌ Madurez ecosistema GraphRAG inferior. `neo4j-graphrag` no soporta AGE.
- ❌ Performance Cypher en AGE inferior a Neo4j nativo (~3-5x más lento en benchmarks PVF interna BR).
- ❌ Supabase managed Postgres NO permite habilitar AGE extension (verified Sprint 4 con TI MT).
- **Decisión**: AGE queda como **fallback open-source** documentado si Aura genera lock-in operativo o coste insostenible. Implica self-host Postgres (NO Supabase managed) — friction alta.

### 2.3 CDC outbox pattern (ADR-041 refinement)

**Sprint 4 implementa**: tabla `cdc_events` (outbox) en Postgres con triggers AFTER INSERT/UPDATE/DELETE en `products`, `suppliers`, `costs`, `match_candidates` que insertan rows con `entity_type`, `action` ∈ {`insert`,`update`,`delete`}, `payload_jsonb`, `status` ∈ {`pending`,`processed`,`failed`,`dead_letter`}, `attempts`.

`CdcDispatcher.process_batch(batch_size=100)`:
1. `fetch_pending` lee 100 rows ORDER BY id ASC.
2. Por row: `SchemaMapper.map_event(...)` → `(nodes, edges)` → `graph.merge_node(...)` / `merge_edge(...)`. `delete` → `delete_subgraph`.
3. Marca processed o failed (incrementa attempts; tras 3 → dead_letter).
4. `await session.flush()` y caller commitea.

**Idempotencia**:
- Graph store implementa MERGE → reprocesar el mismo evento es seguro.
- `replay()` admin-only resetea rows a `pending` (filtra `processed`/`failed`/`dead_letter`).

**Por qué outbox y no Supabase Realtime directo Fase 1**:
- Outbox es transaccional con la mutación origin → cero loss garantizado.
- Realtime requiere conexión websocket viva al broker → inestable en arranque/restart Celery.
- Outbox + polling es la forma estándar (Debezium pattern) y permite replay.

**Fase 2** evolución: outbox sigue siendo SSoT, pero el dispatcher escucha LISTEN/NOTIFY o Supabase Realtime para reducir latencia (~1-5s vs polling 30s). Outbox queda como audit trail.

### 2.4 Schema mapping (Sprint 4)

`SchemaMapper.map_event(...)` (función pura, sin IO) traduce 4 entity_types core:

| entity_type      | Nodo principal                | Edges                                                                            |
|------------------|-------------------------------|----------------------------------------------------------------------------------|
| `product`        | `(:Product {sku})`            | `[:MADE_OF]→(:Material)`, `[:BRANDED]→(:Manufacturer)`, `[:BELONGS_TO]→(:Family)` |
| `supplier`       | `(:Supplier {code})`          | `[:USES_CURRENCY]→(:Currency)`                                                   |
| `cost`           | `(:Cost {id})`                | `(:Product)-[:HAS_COST]→(:Cost)`, `(:Cost)-[:FROM_SUPPLIER]→(:Supplier)`         |
| `match_candidate`| `(:MatchCandidate {id})`      | `(:Product)-[:HAS_MATCH]→(:MatchCandidate)`, `[:LISTED_ON]→(:Channel)`           |

Convenciones:
- Edge type SCREAMING_SNAKE_CASE (Cypher idiom).
- Properties solo JSON-serializable (Decimal/UUID/datetime → str).
- Whitelist de keys por entity (no se vuelcan blobs grandes).

`SchemaMapper.primary_label(entity_type)` para `delete_subgraph` lookup.

### 2.5 Fase 2 trigger conditions

Activamos Fase 2 cuando **TODAS** se cumplan:
- Cierre Fase 1b alcanzado (US-1B-01-* end-to-end).
- **Ontólogo PVF contratado** (recurso clave — sin él, modelo de datos del grafo es pobre).
- Precisión RAG-only Fase 1 medida ≥ 88 % pero <93 % (si está >93 %, defer Fase 2 por valor incremental incierto; si <88 %, urgencia alta).
- Champion MT firma cost approval Aura ($65-100/mes).

### 2.6 Fase 3 trigger conditions

- Fase 2 Hybrid en producción ≥ 4 sprints.
- Precisión Hybrid plateau ~94 % (sin más mejoras incrementales).
- Casos de uso cross-sell o intercambiabilidad activos en backlog (no solo precisión).
- Embeddings vectoriales materializables como Neo4j vector index (lib `neo4j-graphrag`).

## 3. Alternativas consideradas

### 3.1 Empezar con Neo4j Aura desde Sprint 4

**Rechazada**. ADR-038 §"Cuándo revisar" lo veta explícitamente: sobre-ingeniería sin ontólogo, coste operativo amortizable solo si Fase 1 valida value. Stub in-memory cumple el contrato `GraphStorePort` y el swap a Aura es non-breaking.

### 3.2 Apache AGE como default

**Rechazada §2.2**. Madurez ecosistema y restricción Supabase managed.

### 3.3 Otro graph DB (DGraph, ArangoDB, Memgraph)

**Rechazada**. Neo4j tiene mayor adopción ecosistema GraphRAG (Microsoft GraphRAG paper, LlamaIndex/LangChain integrations). Otros backends requieren custom adapters.

### 3.4 Realtime Supabase desde Fase 1 (sin outbox)

**Rechazada**. Sin outbox, evento perdido en restart Celery = grafo desincronizado sin forma de recuperar. Outbox + polling es operacionalmente más predecible. Realtime se suma en Fase 2 como aceleración.

### 3.5 No GraphRAG, evolucionar solo RAG (Hybrid Search lexical+vector)

**Rechazada como sustituto** (ya en ADR-038). Equivalencias entre marcas y matching por norma técnica no se resuelven con embeddings. Hybrid Search lexical+vector es complementario.

## 4. Consecuencias

### Positivas

- **Cero refactor del comparador** entre fases: `GraphStorePort` Protocol absorbe el swap.
- **Sprint 4 mergeable**: stub in-memory + outbox CDC funcionan sin Aura, sin coste.
- **Outbox CDC es audit trail** además de mecanismo de replicación → trazabilidad legal y debug fáciles.
- **Schema mapping aislado** (función pura) → testeable sin BD ni grafo.
- **Replay capability** desde día 1 → recuperar el grafo si el stub muere o si Fase 2 setup requiere re-seed.

### Negativas

- **Stub in-memory NO persiste**: restart del worker → grafo vacío. Aceptable Fase 1 (no usado en producción todavía). Mitigación Fase 2 con Aura.
- **Stub `query_neighbors` es O(n) lineal** sobre todas las edges. Suficiente para tests/demo (<1000 nodes); patológico a escala. Mitigación: Fase 2 con Aura indexes.
- **Outbox table puede crecer** sin purge. Sprint 5 TODO: job purge para rows `processed` >30 días. Sin purge, ~5 MB/mes (crecimiento manejable Fase 1).
- **Schema mapping limitado a 4 entity_types**. Norms (`(:Standard {code})`) y compatibility edges (`[:COMPATIBLE_WITH]`) **NO** se modelan Sprint 4 — defer Fase 2 cuando ontólogo PVF activo.
- **Lock-in Neo4j Aura** (managed): si AWS/GCP exit Aura UAE region o sube precios, migración a self-host Aura Enterprise costosa ($1k+/mes) o Apache AGE (Postgres self-host) friction operativa. Mitigación: ADR-041 documenta exit plan.

## 5. Open questions

- **Q1 (TODO Champion MT, fin Fase 1b)**: contratar ontólogo PVF — sin recurso, NO arrancar Fase 2.
- **Q2 (TODO TI MT, Fase 2 kickoff)**: provisionar Neo4j Aura instance UAE/EU + credenciales + secrets management.
- **Q3 (TODO Sprint 5)**: implementar purge job `cdc_events.status='processed' AND processed_at < now()-30d`.
- **Q4 (TODO Sprint 6)**: extender `SchemaMapper` con `Standard` (norms ISO/API/UNE) y `[:COMPLIES_WITH]` edges. Necesita ontólogo input.
- **Q5 (TODO Fase 2)**: definir criterios de **selective replication** — ¿qué % de tablas Postgres replican al grafo? Sprint 4 cubre 4; Fase 2 amplía a `prices`, `audit_events`, `competitor_listings`.
- **Q6 (TODO Fase 3)**: estrategia embeddings (sentence-transformers vs OpenAI text-embedding-3) con pricing por volumen. Sprint 6+ topic.

## 6. Implementation status

- `mt-pricing-backend/app/services/graphrag/__init__.py` — pkg doc + re-export Protocol/DTOs (líneas 1-37).
- `mt-pricing-backend/app/services/graphrag/ports.py`:
  - `GraphNode` dataclass frozen (líneas 29-41).
  - `GraphEdge` dataclass frozen (líneas 43-60).
  - `GraphStorePort` Protocol con `merge_node`, `merge_edge`, `query_neighbors`, `delete_subgraph`, `health_check` (líneas 63-95).
- `mt-pricing-backend/app/services/graphrag/adapters/neo4j_stub.py`:
  - `Neo4jStubGraphStore` in-memory (líneas 27-157).
  - Singleton `get_default_graph_store` / `set_default_graph_store` (líneas 166-179).
  - Thread-safe (`threading.RLock`).
- `mt-pricing-backend/app/services/graphrag/schema_mapper.py`:
  - Etiquetas/edges canónicas (líneas 41-58).
  - `SchemaMapper.map_event` + `_map_product` / `_map_supplier` / `_map_cost` / `_map_match_candidate` (líneas 61-328).
- `mt-pricing-backend/app/services/graphrag/cdc_dispatcher.py`:
  - `MAX_ATTEMPTS_BEFORE_DEAD_LETTER = 3` (línea 40).
  - `fetch_pending` / `process_one` / `process_batch` / `replay` (líneas 58-172).
- Tests esperados: `tests/services/graphrag/test_schema_mapper.py`, `test_neo4j_stub.py`, `test_cdc_dispatcher.py` (idempotencia + dead_letter + replay).

## 7. Trazabilidad

- Sprint 4 backlog US-RND-01-11.
- ADR-038 — roadmap macro RAG → Hybrid → GraphRAG.
- ADR-039 (ontología KG) — schema concept esperado Fase 2.
- ADR-041 (CDC Postgres↔Neo4j) — refinado por esta ADR.
- ADR-073 — VLM judge complementario (Fase 1 + 2).
- Risk register: R-graphrag-no-ontologist (gate Fase 2), R-aura-vendor-lockin (mitigación AGE fallback documentada).
