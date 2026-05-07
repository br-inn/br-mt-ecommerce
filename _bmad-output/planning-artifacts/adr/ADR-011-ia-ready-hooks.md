# ADR-011: IA-ready hooks (columnas embedding VECTOR(1536) reservadas, sin uso Fase 1)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

El brief explicita "IA-ready hooks (columnas `embedding VECTOR(1536)` reservadas, sin uso Fase 1)". La capa IA real arranca Fase 1.5+ (sistema de comparación de productos como research workstream) o Fase 2.5+ (recomendador, anomaly detection, búsqueda semántica).

Decisión: ¿reservamos columnas vacías ahora o ALTER TABLE más tarde?

## Decisión

**Reservar hooks en Fase 1, pero NO activar pgvector hasta que se necesite**:

### En Fase 1

- **Crear extension pgvector** en migrations (`CREATE EXTENSION IF NOT EXISTS vector;`) → habilitada en DB pero sin uso.
- En tablas candidate, añadir columnas `embedding VECTOR(1536) NULL` y `embedding_model TEXT NULL` y `embedding_at TIMESTAMPTZ NULL`. Default NULL, no se llena.
- Tablas que reciben hooks Fase 1:
  - `products` (para futuro match semántico SKU↔competidor; búsqueda interna).
  - `competitor_listings` (tabla reservada Fase 1.5+, creada vacía).
- **NO crear índices HNSW Fase 1** (índices en columna vacía son innecesarios y frenan INSERTs). Los índices se crean cuando la columna se empieza a llenar.
- Documentar en código (`-- ADR-011: reserved for Fase 1.5+ semantic match`) cada columna.

### En Fase 1.5+ (cuando se active)

- Decidir modelo de embedding (decisión pendiente: OpenAI text-embedding-3-small vs modelo abierto). Independiente del stack — es plug-and-play.
- Backfill embeddings en background job.
- Crear índice HNSW: `CREATE INDEX ON products USING hnsw (embedding vector_cosine_ops);`.
- Agregar trigger que invalide `embedding` cuando cambien campos relevantes (`name_en`, `description_en`, `dn`, `material`, etc.) y encole job de re-embedding.

### Justificación de la dimensión 1536

- Compatible con OpenAI `text-embedding-3-small` (1536) y `text-embedding-ada-002` (1536, legacy).
- Aceptable para CLIP (512) o SigLIP (768) — sólo se ocupa el prefijo (técnicamente desperdicia espacio pero es marginal y permite no migrar schema).
- Si Fase 1.5+ elige modelo de menor dimensión (512), se puede `ALTER COLUMN ... TYPE VECTOR(512)` con migration controlada.

### `competitor_listings` (tabla reservada)

```sql
CREATE TABLE competitor_listings (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel       TEXT NOT NULL,        -- 'amazon_uae' | 'noon_uae' | 'supplier_x' | ...
  external_id   TEXT NOT NULL,        -- ASIN, NIN, supplier SKU
  brand         TEXT,
  title         TEXT,
  price_aed     NUMERIC(18,4),
  image_url     TEXT,
  url           TEXT,
  raw           JSONB,                -- payload completo del scraper / API
  matched_sku   TEXT REFERENCES products(sku),
  match_score   NUMERIC(5,4),         -- 0..1
  match_method  TEXT,                 -- 'manual' | 'rules' | 'embedding' | 'hybrid'
  match_status  TEXT,                 -- 'unmatched' | 'candidate' | 'confirmed' | 'rejected'
  embedding     VECTOR(1536),         -- ADR-011 reserved
  embedding_model TEXT,
  embedding_at  TIMESTAMPTZ,
  scraped_at    TIMESTAMPTZ NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (channel, external_id)
);
```

Tabla creada Fase 1, **sin datos**. Los procesos de scraping / sourcing son Fase 1.5+.

## Alternativas evaluadas

### Alternativa A: No reservar nada Fase 1; ALTER TABLE en Fase 1.5+
- **Pros**: schema más limpio inicial.
- **Contras**: ALTER TABLE en producción con datos requiere downtime / migración cuidadosa. Coste de coordinación Fase 1.5+.
- **Veredicto**: descartada — el coste de reservar columnas NULL es despreciable (Postgres almacena NULL en bitmap, ~ 0 bytes por fila).

### Alternativa B: Activar pgvector + crear índices vacíos Fase 1
- **Pros**: ready out-of-the-box.
- **Contras**: índice HNSW en columna vacía es waste; cuando se haga backfill, hay que reindexar igual. Sin valor añadido Fase 1.
- **Veredicto**: descartada.

### Alternativa C: Sistema vectorial externo (Pinecone, Qdrant, Weaviate) desde Fase 1.5+
- **Pros**: optimizado para vectores.
- **Contras**: federación con Postgres añade latencia + complejidad. Sin necesidad < 1M vectores. Fase 1 no decide aún.
- **Veredicto**: decisión deferida — Fase 1 no compromete a pgvector ni a externo, sólo reserva hooks.

## Consecuencias positivas

- Cero coste Fase 1 (NULL columns, no índices).
- Activación Fase 1.5+ es backfill + index, sin migration de schema.
- Mantiene opción abierta entre pgvector y servicio externo.
- Respeta el principio "hooks ahora, decisión después".

## Consecuencias negativas / riesgos

- Si Fase 1.5+ elige modelo con dimensión incompatible (e.g. 768), sigue requiriendo `ALTER COLUMN`. Mitigación: la migración es local a una columna, no altera el schema relacional, baja fricción.
- Hay tentación de "usar el embedding ya que está" — disciplina del equipo para no tocar hasta tener decisión de modelo.

## Cuándo revisar

- **Antes de Fase 1.5** (cuando se aborde el sistema de comparación): decidir modelo + activar índices HNSW.
- **Fase 2.5** (recomendador): re-evaluar si pgvector basta o conviene servicio externo.
