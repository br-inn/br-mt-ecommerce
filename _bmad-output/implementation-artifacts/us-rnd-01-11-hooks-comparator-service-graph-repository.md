# US-RND-01-11 — Hooks ComparatorService + GraphRepository (FR-CMP-GRAPH-01)

**Estado**: DONE  
**SP**: 8 | **Épica**: EP-RND-01  
**Fecha**: 2026-05-12  
**Autor**: psierra  

---

## Resumen ejecutivo

Implementación completa de las abstracciones backend que permiten introducir
Knowledge Graph en Fase 2+ sin refactor de endpoints ni callers existentes.
Los tres ACs fueron verificados con 38 tests unitarios (todos green).

---

## Qué existía antes

| Componente | Estado previo |
|---|---|
| `ComparatorPort` (interface ABC) | Existía en `comparator/interfaces.py` |
| `NoopComparatorService` | Existía — stub Fase 1, todas ops no-op |
| `ComparatorServiceFactory` | Existía — siempre devolvía Noop (flag-based, sin COMPARATOR_ADAPTER) |
| `GraphStorePort` | Existía en `graphrag/ports.py` — operaciones de grafo genéricas |
| `Neo4jStubGraphStore` | Existía — in-memory dict-based |
| `Neo4jGraphStore` | Existía — driver real Neo4j 5 |
| `graphrag/adapters/factory.py` | Existía — `GRAPHRAG_BACKEND=stub|neo4j` |
| Tests `test_noop_service.py` | Existían (4 tests) |
| Tests `test_factory.py` | Existían (4 tests, probaban solo Noop path) |

**Faltaba**: adapters estratificados (`RagOnly/Hybrid/FullGraphRag`), `GraphRepository` de dominio (vs `GraphStorePort` genérico), config `COMPARATOR_ADAPTER`, factory que resuelva los tres adapters.

---

## Qué se añadió

### Archivos nuevos

| Archivo | Descripción |
|---|---|
| `mt-pricing-backend/app/services/comparator/adapters.py` | Los tres adapters: `RagOnlyComparatorAdapter` (activo), `HybridComparatorAdapter` (stub Fase 2), `FullGraphRagComparatorAdapter` (stub Fase 2+) |
| `mt-pricing-backend/app/services/comparator/graph_repository.py` | `GraphRepository` (port ABC) + `PostgresGraphRepository` (activo Fase 1) + `Neo4jGraphRepository` (stub Fase 2+) + `get_graph_repository()` factory |
| `mt-pricing-backend/tests/unit/services/comparator/test_adapters.py` | 15 tests — todos los adapters, comportamiento correcto vs stubs |
| `mt-pricing-backend/tests/unit/services/comparator/test_graph_repository.py` | 12 tests — PostgresGraphRepository activo, Neo4jGraphRepository stub, swap por config |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `mt-pricing-backend/app/core/config.py` | Añadido `COMPARATOR_ADAPTER: Literal["rag_only", "hybrid", "full_graph_rag"] = "rag_only"` |
| `mt-pricing-backend/app/services/comparator/factory.py` | Reescrito para soportar los tres adapters vía `COMPARATOR_ADAPTER`; flag OFF sigue devolviendo Noop (backward compat) |
| `mt-pricing-backend/app/services/comparator/__init__.py` | Exporta los nuevos símbolos: adapters + GraphRepository |
| `mt-pricing-backend/tests/unit/services/comparator/test_factory.py` | Ampliado con tests AC-1 + AC-3 (adapter swap vía env) |

---

## Acceptance Criteria

### AC-1: ComparatorService con RagOnlyComparatorAdapter activo + stubs

**Status: DONE**

- `RagOnlyComparatorAdapter` implementa `ComparatorPort`:
  - `find_candidates` → `[]` (tabla vacía Fase 1, pgvector ANN en Fase 1.5+)
  - `confirm_match` / `reject_match` → no-op (INSERT real en Fase 1.5+)
  - `get_stats` → `ComparisonStats(all=0)`
- `HybridComparatorAdapter` → todos los métodos lanzan `NotImplementedError`
- `FullGraphRagComparatorAdapter` → todos los métodos lanzan `NotImplementedError`
- `ComparatorServiceFactory.create()` devuelve `RagOnlyComparatorAdapter` cuando flag ON + `COMPARATOR_ADAPTER=rag_only`

### AC-2: GraphRepository con PostgresGraphRepository activo + Neo4jGraphRepository stub

**Status: DONE**

- `GraphRepository` (ABC) con métodos: `get_product_neighbors`, `get_competitor_context`, `health_check`
- `PostgresGraphRepository(GraphRepository)` activo Fase 1:
  - `get_product_neighbors` → `[]` (relaciones Postgres vacías; JOIN real en Fase 1.5+)
  - `get_competitor_context` → dict con campos vacíos + `graph_confidence=0.0`
  - `health_check` → `{"healthy": True, "backend": "postgres_graph_repository"}`
- `Neo4jGraphRepository(GraphRepository)` stub Fase 2+:
  - `get_product_neighbors` / `get_competitor_context` → lanzan `NotImplementedError`
  - `health_check` → `{"healthy": False}` (no lanza error — safe para monitoring)
- `get_graph_repository()` respeta `GRAPHRAG_BACKEND`:
  - `stub` (default) → `PostgresGraphRepository`
  - `neo4j` → `Neo4jGraphRepository` delegando a `GraphStorePort`

### AC-3: Swap de adapter vía config sin cambiar endpoints

**Status: DONE**

`COMPARATOR_ADAPTER` en `app/core/config.py` controla el adapter activo:
- `rag_only` → `RagOnlyComparatorAdapter` (Fase 1 default)
- `hybrid` → `HybridComparatorAdapter` (stub)
- `full_graph_rag` → `FullGraphRagComparatorAdapter` (stub)
- valor desconocido → fallback seguro a `RagOnlyComparatorAdapter` + WARNING log

Swap no requiere modificar `app/api/routes/` — el factory resuelve por settings.

---

## Tests

```
38 passed in 6.23s

tests/unit/services/comparator/test_adapters.py     15 passed
tests/unit/services/comparator/test_factory.py       7 passed  (incluye AC-1 + AC-3)
tests/unit/services/comparator/test_graph_repository.py  12 passed  (AC-2 + AC-3)
tests/unit/services/comparator/test_noop_service.py  4 passed  (backward compat)
```

---

## Notas técnicas

- `GraphRepository` vs `GraphStorePort`: el primero habla el lenguaje de dominio del comparator (product_neighbors, competitor_context); el segundo es genérico para cualquier KG (merge_node, merge_edge, query_neighbors). Ambos coexisten.
- `Neo4jGraphRepository` delega en `get_default_graph_store()` de `graphrag/adapters/factory.py`, que ya resuelve stub vs real por `GRAPHRAG_BACKEND` — no hay duplicación de lógica.
- Los stubs `Hybrid` y `FullGraphRag` lanzan `NotImplementedError` (no `NotImplemented`) para señal explícita; el factory nunca los instancia con la config default (Fase 1).
- `NoopComparatorService` se mantiene intacto — usado cuando `COMPARATOR_ENABLED=OFF` (default seguro Fase 1).
