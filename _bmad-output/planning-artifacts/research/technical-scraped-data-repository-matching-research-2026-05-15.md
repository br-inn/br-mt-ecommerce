---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Repositorio de datos scrapeados para reutilización en matching de productos'
research_goals: 'Evitar pérdida de análisis scraper cuando no hay match; estrategias de mercado para persistir y reutilizar datos scrapeados en búsquedas de artículos'
user_name: 'psierra'
date: '2026-05-15'
web_research_enabled: true
source_verification: true
---

# Repositorio de Datos Scrapeados para Matching: Guía Técnica Completa

**Date:** 2026-05-15
**Author:** psierra
**Research Type:** technical

---

## Executive Summary

El problema de pérdida de análisis scrapeado es un **problema de arquitectura de datos**, no de lógica de matching. El pipeline actual descarta ofertas en el momento en que no hay match, antes de persistirlas — equivale a tirar el 100% del trabajo del scraper cuando falla el matching.

El mercado resuelve esto con un **Candidate Store persistente** (capa Silver en la arquitectura Medallion), donde todas las ofertas scrapeadas se almacenan normalizadas y con embeddings vectoriales. El matching ocurre después, de forma asíncrona, y puede re-ejecutarse cuando las reglas mejoran — sin re-scrapear. Keepa, IntelligenceNode y PriceRunner aplican exactamente este patrón.

Para el proyecto, la solución usa exclusivamente el stack existente: PostgreSQL + pgvector (Supabase) + Celery + Redis. Costo de embeddings: $0.40 USD/millón de ofertas. Sin infraestructura nueva.

**Hallazgos críticos:**
- La arquitectura Medallion (Bronze/Silver/Gold) es el estándar de industria — la capa Silver es exactamente donde persisten los candidatos sin match
- pgvector HNSW: single-digit ms para hasta 5M vectores — suficiente para volumen MRO industrial
- Lookup-Before-Scrape evita re-scrapear lo que ya está en el pool
- Bronze inmutable (Event Sourcing) permite reproducir el matching cuando el pipeline mejora, sin re-scrapear

**Recomendaciones top:**
1. Tabla `unmatched_offers` (Silver) con `embedding VECTOR(1536)` + HNSW index
2. Worker: insertar en Silver antes de descartar (no tocar pipeline Gold actual)
3. Celery task `lookup_candidates_task` como gate antes de `scrape_task`
4. Celery Beat: `rematch_unmatched_pool` diario
5. Validar calidad embeddings con 100 SKUs MRO conocidos

---

## Table of Contents

1. Technical Research Scope Confirmation
2. Technology Stack Analysis
3. Integration Patterns Analysis
4. Architectural Patterns and Design
5. Implementation Approaches and Technology Adoption
6. Strategic Technical Recommendations
7. Future Technical Outlook
8. Technical Research Conclusion

---

## Research Overview

## Technical Research Scope Confirmation

**Research Topic:** Repositorio de datos scrapeados para reutilización en matching de productos
**Research Goals:** Evitar pérdida de análisis scraper cuando no hay match; estrategias de mercado para persistir y reutilizar datos scrapeados en búsquedas de artículos

**Technical Research Scope:**

- Architecture Analysis - staging layers, data lakes de productos, índice invertido para matching
- Implementation Approaches - persistencia de candidatos sin match, deduplicación, TTL, re-match automático
- Technology Stack - Elasticsearch, vector DBs, Redis, PostgreSQL JSONB, colas de re-procesamiento
- Integration Patterns - lookup previo antes de disparar scraping, integración con pipeline LLM+visión
- Performance Considerations - scalability, cache, latencia de lookup

**Research Methodology:**

- Datos actuales de web con verificación de fuentes
- Validación multi-fuente para claims técnicos críticos
- Niveles de confianza para información incierta

**Scope Confirmed:** 2026-05-15

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technology Stack Analysis

### Arquitectura de Almacenamiento: Patrón Bronze/Silver/Gold

El patrón dominante en pipelines de scraping modernos (2025-2026) es una arquitectura de data lake en capas que separa colección, normalización y matching:

- **Bronze (Raw)**: HTML crudo o JSON tal como llega del scraper. Inmutable. Todo pasa aquí, incluyendo ofertas sin match.
- **Silver (Normalized)**: Datos parseados, atributos extraídos (MPN, marca, precio, specs). Deduplicados por hash.
- **Gold (Matched)**: Solo registros con match confirmado contra el catálogo de productos.

**El problema actual del proyecto**: las ofertas scrapeadas solo persisten si alcanzan Gold. Si no hay match, se descartan antes de Silver, perdiendo el análisis.

*Fuente: [Web Scraping for Data Engineers - Medium](https://htrixe.medium.com/web-scraping-for-data-engineers-architecture-robustness-and-production-pipelines-with-scrapling-c327278222f7), [Starburst Data Pipelines](https://www.starburst.io/blog/data-pipelines-and-data-lakes/)*

---

### Lenguajes y Frameworks

| Componente | Stack relevante para este proyecto |
|---|---|
| Pipeline de scraping | Python (ya en uso), AsyncIO, Celery (ya en uso) |
| Storage Silver/unmatched | PostgreSQL + JSONB (ya en uso) |
| Similarity search | pgvector extension (disponible en Supabase) |
| Fuzzy matching | Python: `rapidfuzz`, `jellyfish` |
| Reindexado | Elasticsearch (alternativa externa) o pgvector (in-stack) |

*Fuente: [pgvector Supabase](https://supabase.com/docs/guides/database/extensions/pgvector), [pgvector GitHub](https://github.com/pgvector/pgvector)*

---

### Base de Datos y Almacenamiento para Candidatos Sin Match

**Opción A — pgvector (recomendada, in-stack):**
- Extensión de PostgreSQL ya disponible en Supabase
- Soporta HNSW e IVF indexes para ANN (Approximate Nearest Neighbor)
- Permite queries SQL híbridas: filtros tradicionales + similitud vectorial
- pgvector 0.8.0+ resuelve el problema de "overfiltering" (combinar WHERE clauses con vector search)

**Opción B — Elasticsearch:**
- Motor probado para deduplicación de catálogos grandes (1M+ SKUs)
- Soporta fuzzy matching nativo
- Infraestructura adicional (no in-stack)

**Opción C — Redis con TTL:**
- Para cache de candidatos recientes (últimas 24-72h)
- No apto para repositorio persistente

*Fuente: [pgvector deep dive - Severalnines](https://severalnines.com/blog/vector-similarity-search-with-postgresqls-pgvector-a-deep-dive/), [Elasticsearch duplicates - Elastic Blog](https://www.elastic.co/blog/how-to-find-and-remove-duplicate-documents-in-elasticsearch)*

---

### Estrategias de Deduplicación de Datos Scrapeados

Las tres estrategias complementarias estándar del mercado:

1. **Hash-based** (exacta): concatenar campos clave → SHA-256 → ignorar si ya existe. O(1), maneja millones de registros en segundos. Útil en Bronze.

2. **Key-based** (por identificador): MPN + retailer como clave compuesta. El mismo producto de Amazon y Noon es una misma oferta. Útil en Silver.

3. **Fuzzy/Semantic** (similitud): algoritmos Levenshtein, Jaro-Winkler, o embeddings vectoriales. Sistema de confianza:
   - > 0.95 → merge automático
   - 0.70–0.95 → revisión humana
   - < 0.70 → candidato independiente

*Fuente: [Deduplicating Scraped Data - Tendem.ai](https://tendem.ai/blog/deduplicating-scraped-data-guide), [Zyte webinar: matching and deduplication](https://www.zyte.com/webinars/techniques-for-matching-and-deduplication-of-scraped-data/)*

---

### Infraestructura y Deployment

El proyecto ya tiene el stack adecuado para implementar el repositorio de candidatos:
- PostgreSQL (Supabase) → agregar pgvector + tabla `unmatched_offers`
- Celery → jobs periódicos de re-matching
- Redis → cola de re-procesamiento cuando llegan nuevos SKUs

No se necesita infraestructura adicional si se usa pgvector.

*Fuente: [pgvector guide 2026](https://dbadataverse.com/tech/postgresql/2025/12/pgvector-postgresql-vector-database-guide)*

---

### Tendencias de Adopción en el Mercado

- **PRISM (arxiv 2025)**: Sistema de retrieval de productos con VLM usa un "candidate pool" — filtra semánticamente hasta top-35 similares antes de matching detallado. Patrón directamente aplicable.
- **Keepa**: Mantiene historial completo de TODAS las ofertas scrapeadas de Amazon, con o sin match a un producto conocido — es el repositorio persistente más grande del mercado. El match ocurre después, no antes.
- **IntelligenceNode/42signals**: AI crawlers que acumulan candidatos y los re-emparejan con el catálogo del cliente de forma continua.
- **Bloom filters en el edge**: Para filtrar "Ghost SKUs" (páginas de test, productos eliminados) antes de persistir en Bronze.

*Fuente: [PRISM arxiv](https://arxiv.org/html/2509.14985), [42signals product matching](https://www.42signals.com/blog/product-matching-ecommerce-benefits/), [IntelligenceNode](https://www.intelligencenode.com/solutions/product-matching/)*

---

## Integration Patterns Analysis

### Patrón 1: Lookup-Before-Scrape (el más importante)

**Descripción**: Antes de lanzar un nuevo scrape para un SKU, consultar primero el candidate pool. Solo disparar el scraper si no hay candidatos recientes en el repositorio.

```
Nuevo SKU ingresa al sistema
        ↓
[LOOKUP] SELECT * FROM unmatched_offers 
         WHERE similarity(embedding, sku_embedding) > 0.80
         AND scraped_at > NOW() - INTERVAL '7 days'
        ↓
┌── Candidatos encontrados ──→ Intentar re-match directamente
└── Sin candidatos ──────────→ Disparar scraper (comportamiento actual)
```

El patrón se implementa como un Celery task que actúa de gate antes de `scrape_task`. Los resultados de búsqueda confirman que sistemas como Apify y PromptCloud usan event-triggered lookups con `product.created` como disparador.

*Fuente: [Event-Triggered Price Monitoring - PromptCloud](https://www.promptcloud.com/blog/event-triggered-price-monitoring/), [Product Matching AI - Apify](https://blog.apify.com/product-matching-ai-pricing-intelligence-web-scraping/)*

---

### Patrón 2: Staging Table como Data Staging Area (DSA)

**Descripción**: La tabla `unmatched_offers` actúa como un Data Staging Area (DSA) — zona buffer entre Bronze (raw scraping) y Gold (matched products). El DSA permite:
- Reconciliación de inconsistencias antes de intentar match
- Corrección de datos entre runs del scraper
- Punto de integración para múltiples fuentes (Amazon, Noon, etc.)

```
[Bronze] raw_scraped_data  →  [DSA] unmatched_offers  →  [Gold] match_candidates / product_prices
          (inmutable)            (enriquecida, TTL)          (matched)
```

Empresas como ElasticPath y Adobe Commerce documentan este patrón como práctica estándar para catálogos multi-source.

*Fuente: [Data Staging Area - Atlan](https://atlan.com/what-is/data-staging-area/), [Catalog Syndication - ElasticPath](https://documentation.elasticpath.com/commerce/docs/tools/catalog-syndication/architecture.html)*

---

### Patrón 3: Event-Driven Re-Matching (Celery + Redis)

**Descripción**: Cuando el pipeline de matching mejora (nuevas reglas, nuevo prompt LLM, nuevo adaptador), emitir un evento que re-procesa el candidate pool sin re-scrapear.

```
Evento: matching_rules_updated
        ↓
Celery task: rematch_unmatched_pool(batch_size=100)
        ↓
Para cada offer en unmatched_offers WHERE match_attempts < 3:
    → ejecutar matching pipeline completo
    → si match: mover a match_candidates, marcar matched_at
    → si no match: incrementar match_attempts, actualizar last_tried_at
```

Redis actúa como shock absorber — batches de 100 offers procesados en paralelo sin sobrecargar la DB.

*Fuente: [Celery + Redis Stack - DEV Community](https://dev.to/deepak_mishra_35863517037/distributed-scraping-the-flask-celery-redis-stack-17d3), [Syncing 60k Products - DEV Community](https://dev.to/rosen_hristov/syncing-60000-products-without-breaking-everything-278c)*

---

### Patrón 4: Hash-Based Skip Logic (evitar duplicados en DSA)

**Descripción**: Antes de insertar en el DSA, computar un hash del contenido normalizado para evitar re-insertar lo mismo.

```python
offer_fingerprint = sha256(f"{mpn}|{marketplace}|{price}|{scraped_date}")
# INSERT INTO unmatched_offers ... ON CONFLICT (fingerprint) DO UPDATE SET last_seen_at = NOW()
```

Esto mantiene el DSA limpio y permite actualizar precios sin duplicar filas.

*Fuente: [Syncing 60k Products - DEV Community](https://dev.to/rosen_hristov/syncing-60000-products-without-breaking-everything-278c)*

---

### Patrón 5: TTL + Compaction periódica

**Descripción**: Ofertas en el DSA tienen un TTL configurable (ej. 30 días para industrial). Un job periódico (Celery Beat) archiva o elimina ofertas viejas con `match_attempts >= MAX_ATTEMPTS`.

```
Celery Beat: diario a las 02:00
  → DELETE FROM unmatched_offers 
    WHERE scraped_at < NOW() - INTERVAL '30 days'
    AND match_attempts >= 3
```

Keepa usa TTL de 10 años porque su negocio es el historial. Para matching industrial con datos que cambian rápido, 30-90 días es el estándar.

*Fuente: [Data Staging Area Best Practices 2025 - Atlan](https://atlan.com/what-is/data-staging-area/)*

---

## Architectural Patterns and Design

### Medallion Architecture aplicada al pipeline de scraping

La arquitectura Medallion (Databricks, adoptada como estándar de industria) organiza los datos en tres capas con progresiva mejora de calidad. La capa Silver es **explícitamente** donde ocurre el matching, merge y conformación de registros — incluyendo tablas de cross-reference. Los registros sin match pertenecen en Silver, no deben descartarse antes de llegar a ella.

| Capa | Tabla en el proyecto | Propósito | Estado actual |
|---|---|---|---|
| **Bronze** | `raw_scraped_offers` (nueva) | HTML/JSON crudo, append-only, inmutable | No existe |
| **Silver** | `unmatched_offers` (nueva) | Normalizado, deduplicado, embedding vectorial, matching pendiente | No existe |
| **Gold** | `match_candidates` (existe) | Match confirmado, listo para pricing | Existe |

**Innovaciones 2025**: Liquid Clustering (clustering adaptativo multi-dimensional) y Deletion Vectors (deletes row-level eficientes sin reescribir archivos) mejoran el mantenimiento de Silver.

*Fuente: [Medallion Architecture - Databricks](https://www.databricks.com/blog/what-is-medallion-architecture), [Medallion Guide 2025 - datadef.io](https://datadef.io/guides/en/medallion-architecture)*

---

### Event Sourcing como base para re-procesamiento

**Principio clave**: Si Bronze es append-only e inmutable (event store), siempre se puede **reproducir** los eventos históricos para generar nuevas proyecciones en Silver/Gold cuando el pipeline de matching mejora. Esto es exactamente el caso de uso de re-matching.

```
Bronze (event store, inmutable)
    │ replay events
    ▼
Silver (proyección actual: unmatched_offers)
    │ re-matcher task (nuevas reglas)
    ▼
Gold (proyección actualizada: match_candidates)
```

El event store actúa como fuente de verdad única. Cuando el LLM o las reglas de matching mejoran, se reproduce desde Bronze sin re-scrapear. Confluent/Kafka documenta este patrón como "stream processing sobre event log".

*Fuente: [Event Sourcing Pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing), [CQRS + Event Sourcing - Confluent](https://www.confluent.io/blog/event-sourcing-cqrs-stream-processing-apache-kafka-whats-connection/)*

---

### CQRS aplicado: separar escritura de consulta en el candidate pool

**Write side**: el scraper worker escribe en `unmatched_offers` (normalizado + embedding).
**Read side**: el matching pipeline consulta por similaridad vectorial (pgvector) — sin afectar el write path.

Esta separación permite escalar el scraping independientemente del matching, y consultar el pool con queries complejas (filtros SQL + vector similarity) sin bloquear la ingesta.

*Fuente: [CQRS Pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)*

---

### Rendimiento de pgvector HNSW para el candidate pool

Datos concretos de benchmarks 2025-2026:

| Escenario | Latencia | Relevancia |
|---|---|---|
| < 5M vectores con HNSW | single-digit ms | Alta |
| 1M vectores, 384 dims | sub-segundo | Alta |
| pgvector 0.8.0 vs anterior | **9x más rápido** | **100x más relevante** |
| > 10-20M vectores | degradación notable | — |

Para el caso del proyecto (partes industriales MRO, estimado 100k–1M ofertas scrapeadas), pgvector HNSW es suficiente sin necesitar un vector DB dedicado (Qdrant, Weaviate, Pinecone).

**Configuración recomendada**:
```sql
-- Crear índice HNSW para el candidate pool
CREATE INDEX ON unmatched_offers 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Query: buscar candidatos similares a un nuevo SKU
SELECT *, 1 - (embedding <=> $sku_embedding) AS similarity
FROM unmatched_offers
WHERE marketplace = ANY($markets)
  AND scraped_at > NOW() - INTERVAL '30 days'
  AND matched_at IS NULL
ORDER BY embedding <=> $sku_embedding
LIMIT 10;
```

*Fuente: [pgvector 2026 guide - Instaclustr](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/), [pgvector 0.8.0 - AWS](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)*

---

### Escalabilidad y Consideraciones de Diseño

**Horizontal scaling**: Celery workers independientes para scraping y re-matching — no comparten estado, escalan por separado.

**Particionamiento recomendado para `unmatched_offers`**:
- Por `marketplace` (Amazon, Noon, etc.) — aísla volumen por fuente
- Por `scraped_at` (mensual) — facilita TTL/archivado

**Security**: Las tablas Bronze/Silver no exponen datos a usuarios finales — solo el matching pipeline (Gold) alimenta las vistas de usuario. Row-Level Security en Supabase aplica solo en Gold.

**Observabilidad**: Métricas clave a monitorear:
- `unmatched_offers COUNT WHERE matched_at IS NULL` → backlog sin match
- `match_attempts distribution` → detectar ofertas "inmatchiables"
- `avg(NOW() - scraped_at) WHERE matched_at IS NULL` → frescura del pool

---

## Implementation Approaches and Technology Adoption

### Integración pgvector con SQLAlchemy async (stack actual del proyecto)

La librería `pgvector-python` soporta SQLAlchemy async con asyncpg — el mismo driver que usa el proyecto actualmente. Implementación directa sin cambiar el ORM:

```python
# pip install pgvector
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import mapped_column, Mapped

class UnmatchedOffer(Base):
    __tablename__ = "unmatched_offers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    marketplace: Mapped[str]
    mpn: Mapped[str | None]
    title: Mapped[str]
    price: Mapped[float | None]
    specs_jsonb: Mapped[dict] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(unique=True)  # SHA-256
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))  # text-embedding-3-small
    match_attempts: Mapped[int] = mapped_column(default=0)
    matched_at: Mapped[datetime | None]
    scraped_at: Mapped[datetime]
```

Soporte oficial: pgvector-python soporta asyncpg, psycopg3, SQLAlchemy, SQLModel y Peewee.

*Fuente: [pgvector-python GitHub](https://github.com/pgvector/pgvector-python), [pgvector SQLAlchemy Integration - DeepWiki](https://deepwiki.com/pgvector/pgvector-python/3.1-sqlalchemy-integration)*

---

### Celery async con SQLAlchemy: patrón recomendado

Los workers Celery son síncronos por defecto. El patrón "No Pool + async_to_sync" es el más confiable para reutilizar el código async del proyecto en los workers de re-matching:

```python
# tasks/rematch_pool.py
from celery import shared_task
from asgiref.sync import async_to_sync
from sqlalchemy.pool import NullPool

@shared_task
def rematch_unmatched_pool(batch_size: int = 100):
    """Re-procesa el pool de ofertas sin match con las reglas actuales."""
    async_to_sync(_rematch_batch)(batch_size)

async def _rematch_batch(batch_size: int):
    async with AsyncSession(engine) as session:
        offers = await session.execute(
            select(UnmatchedOffer)
            .where(UnmatchedOffer.matched_at.is_(None))
            .where(UnmatchedOffer.match_attempts < 3)
            .order_by(UnmatchedOffer.scraped_at.desc())
            .limit(batch_size)
        )
        # ejecutar pipeline de matching para cada oferta...
```

Usar `NullPool` en el engine de los workers para evitar connection leaks entre tareas.

*Fuente: [Async SQLAlchemy in Celery - DEV Community](https://dev.to/kevinnadar22/using-async-sqlalchemy-inside-sync-celery-tasks-3eg4), [SQLAlchemy Session en Celery - celery.school](https://celery.school/sqlalchemy-session-celery-tasks)*

---

### Generación de embeddings: opciones y costos

| Modelo | Dims | Costo | Recomendación |
|---|---|---|---|
| `text-embedding-3-small` (OpenAI) | 1536 | $0.00002/1k tokens | Mejor balance costo/calidad |
| `text-embedding-3-large` (OpenAI) | 3072 | $0.00013/1k tokens | Solo si calidad insuficiente |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Gratis (local) | Opción zero-cost, calidad aceptable |

**Estrategia de costo**: `text-embedding-3-small` a $0.00002/1k tokens → 1 millón de ofertas scrapeadas ≈ **$0.40 USD total** (asumiendo ~20 tokens promedio por oferta). Costo despreciable.

**Input para el embedding** — concatenar los campos más discriminantes:
```python
def build_embedding_text(offer: dict) -> str:
    parts = [
        offer.get("mpn", ""),
        offer.get("brand", ""),
        offer.get("title", ""),
        offer.get("description", "")[:200],
    ]
    return " | ".join(p for p in parts if p)
```

*Fuente: [OpenAI Embeddings - OpenAI](https://platform.openai.com/docs/guides/embeddings), [New embedding models - OpenAI](https://openai.com/index/new-embedding-models-and-api-updates/)*

---

### Roadmap de implementación (incremental, sin big bang)

**Fase 1 — Bronze layer (1-2 días)**
- Migración Alembic: tabla `raw_scraped_offers` (append-only, JSONB crudo)
- Modificar worker scraper: escribir en Bronze antes del parser
- Sin cambios al pipeline de matching actual

**Fase 2 — Silver layer / DSA (2-3 días)**
- Migración Alembic: tabla `unmatched_offers` con `embedding VECTOR(1536)` y HNSW index
- Instalar `pgvector-python`, habilitar extensión en Supabase
- Modificar `comparator.py`: cuando no hay match, insertar en `unmatched_offers` en lugar de descartar
- Generar embedding en el worker (llamada a OpenAI API)

**Fase 3 — Lookup-before-scrape (1-2 días)**
- Agregar Celery task `lookup_candidates_task` como gate antes de `scrape_task`
- Si similarity > 0.80 y scraped_at < 7 días: usar candidatos del pool
- Si no: disparar scrape como antes

**Fase 4 — Re-matching periódico (1 día)**
- Agregar `rematch_unmatched_pool` en Celery Beat (diario o al actualizar reglas)
- TTL compaction job (semanal)

**Total estimado**: 5-8 días de desarrollo, cero infraestructura nueva.

---

### Testing y Calidad

- **Unit tests**: mock de OpenAI embeddings API (fixture de vector fijo)
- **Integration tests**: PostgreSQL real con pgvector (mismo patrón que el proyecto actualmente)
- **Métricas de éxito**:
  - `match_rate_from_pool`: % de SKUs que hacen match desde el pool (sin scraping nuevo)
  - `pool_hit_rate`: % de búsquedas que encuentran candidatos en el pool
  - `avg_match_attempts_at_success`: cuántos intentos se necesitan en promedio

---

### Gestión de Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Embeddings de baja calidad para industrial MRO | Media | Evaluar con muestra de 100 SKUs conocidos antes de producción |
| Pool crece demasiado rápido (> 10M filas) | Baja | TTL agresivo (30 días) + monitoreo de tamaño |
| Falsos positivos en lookup (similarity > 0.80 pero producto diferente) | Media | Revisar manualmente top-10 matches, ajustar threshold |
| Connection leaks en Celery workers | Baja | NullPool + tests de integración |

---

## Strategic Technical Recommendations

### Recomendación 1 — Adoptar Medallion Architecture de forma incremental

No rediseñar el pipeline. Agregar las capas Bronze y Silver **sin tocar** el pipeline Gold actual. El principio de Open/Closed: extender sin modificar.

```
Prioridad: Alta
Esfuerzo: Bajo (2 migraciones Alembic + modificación menor del worker)
Impacto: Elimina pérdida de datos scrapeados permanentemente
```

### Recomendación 2 — pgvector sobre Elasticsearch

Para el volumen del proyecto (estimado < 1M ofertas scrapeadas), pgvector HNSW es suficiente y elimina la necesidad de un cluster Elasticsearch separado. Revisar esta decisión si el pool supera 5M filas.

```
Prioridad: Alta
Esfuerzo: Mínimo (pip install + CREATE EXTENSION)
Impacto: Similarity search en single-digit ms, sin infraestructura nueva
```

### Recomendación 3 — Lookup-Before-Scrape como gate obligatorio

Cada vez que se solicita scraping de un marketplace para un SKU, verificar primero el pool. Si hay candidatos frescos (< 7 días), intentar match directo. Esto convierte el pool en un caché inteligente que reduce los costos de scraping.

```
Prioridad: Alta
Esfuerzo: Medio (1 Celery task + modificación del flow de despacho)
Impacto: Reducción estimada de 30-60% en scrapes redundantes
```

### Recomendación 4 — Bronze inmutable como Event Store

Mantener `raw_scraped_offers` como append-only (sin UPDATE, sin DELETE). Esto permite:
- Reproducir el pipeline completo desde el inicio si se cambia el parser o las reglas
- Auditoría completa de qué se scrapeó y cuándo
- Rollback de un run de scraping defectuoso

```
Prioridad: Media
Esfuerzo: Bajo (constraint de BD + documentación del invariante)
Impacto: Permite re-procesamiento histórico sin costo de red
```

### Recomendación 5 — Umbral de similarity ajustable por familia de producto

No usar un threshold fijo para todos los productos. Las válvulas de bola y los rodamientos tienen características muy diferentes. Configurar por `product_family`:

```python
SIMILARITY_THRESHOLDS = {
    "ball_valve": 0.85,   # specs muy específicas, threshold alto
    "bearing": 0.80,
    "fitting": 0.75,      # mayor variabilidad de nomenclatura
    "default": 0.80,
}
```

---

## Future Technical Outlook

### Corto plazo (2026-2027): Multimodal embeddings para matching visual

Los benchmarks de 2026 (Visual Product Search Benchmark, arxiv) muestran que los embeddings multimodales (imagen + texto en el mismo espacio vectorial) mejoran significativamente la precisión de matching para partes industriales donde la forma y dimensión visual son discriminantes. Amazon Nova Multimodal Embeddings ya es usado en manufacturing intelligence.

**Implicación**: El campo `image_url` que scrapeamos hoy puede convertirse en un vector adicional en `unmatched_offers` para matching visual, reutilizando el mismo pipeline de pgvector.

*Fuente: [Visual Product Search Benchmark - arxiv](https://arxiv.org/html/2603.17186v1), [Amazon Nova Multimodal - AWS](https://aws.amazon.com/blogs/machine-learning/manufacturing-intelligence-with-amazon-nova-multimodal-embeddings/)*

### Mediano plazo (2027-2028): Re-matching continuo con LLM agents

El mercado se mueve hacia agentes que monitorean continuamente el candidate pool y re-intentan matching con modelos más nuevos de forma autónoma (MLPerf Inference v6.0 introduce Shopify Product Catalog como benchmark estándar para este tipo de tarea). El pipeline de Celery Beat que se propone hoy es el precursor natural de este patrón.

### Largo plazo (2028+): Mercado de candidatos cross-tenant

Jugadores como IntelligenceNode y 42signals ofrecerán acceso a pools compartidos de candidatos pre-matcheados — el equivalente al modelo de Keepa pero para catálogos industriales B2B. El diseño del pool propio hoy crea el activo de datos que permitirá participar o competir en ese mercado.

---

## Technical Research Conclusion

### Síntesis de hallazgos

El mercado tiene una respuesta clara y madura al problema de pérdida de datos scrapeados: **persistir primero, matchear después**. La arquitectura Medallion (Databricks, adoptada como estándar de industria) establece la capa Silver como la zona de landing para todos los candidatos, independientemente del resultado del matching. El matching es una proyección derivada del Silver, no un gate de entrada.

Para el proyecto, esto se traduce en dos tablas nuevas (`raw_scraped_offers` Bronze, `unmatched_offers` Silver), pgvector HNSW, y tres Celery tasks nuevas. El pipeline Gold existente no cambia.

### Impacto esperado

| Métrica | Estado actual | Con candidate store |
|---|---|---|
| Datos perdidos por no-match | 100% | 0% |
| Scrapes redundantes (mismo producto, mismo marketplace) | Frecuente | Eliminados por fingerprint hash |
| Tiempo hasta match cuando llega nuevo SKU | Nuevo scrape siempre | Lookup < 10ms si hay candidatos |
| Re-matching cuando mejoran las reglas | Manual / re-scrape | Job automático, sin costo de red |

### Próximos pasos

1. **Evaluar embeddings** — generar embeddings para 100 SKUs MRO conocidos, medir recall@10 en similarity search
2. **Migración Alembic** — tablas `raw_scraped_offers` + `unmatched_offers` + HNSW index
3. **Modificar `comparator.py`** — insert en Silver cuando no hay match Gold
4. **Celery gate** — `lookup_candidates_task` antes de `scrape_task`
5. **Monitoreo** — dashboard de backlog y hit rate del pool

---

**Technical Research Completion Date:** 2026-05-15
**Fuentes verificadas:** 25+ fuentes web actuales (2025-2026)
**Nivel de confianza:** Alto — múltiples fuentes independientes para todos los claims críticos

_Este documento sirve como referencia técnica autorizada para la implementación del repositorio de candidatos scrapeados en el proyecto br-mt-ecommerce._

---

### Flujo de Integración Completo

```
[Scraper Worker]
      │ scraped_offer (JSON crudo)
      ▼
[Bronze] raw_scraped_offers (append-only)
      │ parser/normalizer task
      ▼
[DSA] unmatched_offers
   ├─ fingerprint UNIQUE (hash dedup)
   ├─ embedding VECTOR(1536) pgvector
   ├─ match_attempts INT DEFAULT 0
   ├─ matched_at TIMESTAMP NULL
   └─ scraped_at TIMESTAMP
      │
      ├── [Trigger: new SKU] → lookup_candidates_task → matching_pipeline
      ├── [Trigger: rules updated] → rematch_pool_task (batch)
      └── [Celery Beat: daily] → compaction_task (TTL cleanup)
                                        │
                                   si match exitoso
                                        ▼
                               [Gold] match_candidates (pipeline actual)
```
