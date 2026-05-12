---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories"]
inputDocuments:
  - "_bmad-output/planning-artifacts/research-spike-product-comparison.md"
  - "_bmad-output/planning-artifacts/mt-product-matching-pipeline-detail.md"
  - "_bmad-output/planning-artifacts/epics-and-stories-mt-pricing-mdm-phase1.md"
  - "_bmad-output/implementation-artifacts/deferred-work.md"
  - "_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md"
generated: "2026-05-12"
project: "MT Middle East — Fase 1.5 Comparator R&D Extension"
---

# MT Middle East — Fase 1.5 Comparator R&D: Epic Breakdown

## Overview

Extensión del sistema de comparación de productos MT Middle East post-decisión G4 (build confirmado en S9). Transición de stack RAG vectorial (Fase 1, 85-92% precisión) a Hybrid Graph + RAG (Fase 1.5, target 92-95% precisión). Arquitectura ports/adapters ya implementada — hooks `ComparatorService` y `GraphRepository` listos desde US-RND-01-11/12.

**Base:** Fase 1 completada (EP-RND-01 cerrado). Neo4j 5.20 dockerizado. `Neo4jGraphRepository` stub activo. `RagOnlyComparatorAdapter` en producción.

---

## Requirements Inventory

### Functional Requirements

| FR | Descripción | Prioridad |
|----|-------------|-----------|
| FR-F15-01 | Knowledge Graph Neo4j — setup + validación residencia datos UAE/Frankfurt | P0 |
| FR-F15-02 | KG seeding: 657 filas Compat. Materiales V4 + whitelist fabricantes + estándares (ANSI/ASME/DIN/ASTM/API/ISO) | P0 |
| FR-F15-03 | CDC Postgres → Neo4j (Supabase Realtime → Celery → Cypher, fallback Debezium) | P0 |
| FR-F15-04 | Activar `Neo4jGraphRepository` (swap stub → real) + fix W-2 health_check siempre False | P0 |
| FR-F15-05 | `product_equivalences` table: population desde fichas técnicas (ingestión datasheets) | P0 |
| FR-F15-06 | Amazon SP API fetcher real (reemplaza stub — deferred A7 de S8) | P0 |
| FR-F15-07 | VLM Judge audit-grade activación (claude-sonnet-4-6 — ADR-024) | P0 |
| FR-F15-08 | Reverse Image Search activación (feature flag on — ADR-023) | P1 |
| FR-F15-09 | Price Sanity Check implementación (P10/P90 calibration, pre-VLM filter) | P1 |
| FR-F15-10 | Tradeling API integration (MENA B2B fetcher, nuevo adapter) | P1 |
| FR-F15-11 | Pipeline etiquetado humano + exportación dataset ≥1k pares | P1 |
| FR-F15-12 | Embedding fine-tune sobre dataset MT ≥1k pares (AdaptCLIP / sentence-transformers) | P1 |
| FR-F15-13 | KG monitoring dashboard + tests integridad nightly (CDC stale detection) | P1 |
| FR-F15-14 | Conformal Prediction / Venn-Abers sobre calibrator (garantía FP <2%) | P1 |
| FR-F15-15 | Weight tuning por familia de productos + fix deferred W-1/W-4 | P1 |
| FR-F15-16 | Cross-Encoder / Cohere Reranker — spike evaluación coste/latencia | P2 |

### Non-Functional Requirements

| NFR | Descripción |
|-----|-------------|
| NFR-01 | Target precisión matching: 92-95% (vs 85-92% Fase 1) |
| NFR-02 | Residencia datos: UAE/Frankfurt — Neo4j no puede usar AuraDB multi-region fuera de EU/AE |
| NFR-03 | Escala inicial: 5.000 SKUs activos |
| NFR-04 | Latencia P95 pipeline completo: <2s |
| NFR-05 | Garantía cobertura conformal: FP rate <2% por construcción |
| NFR-06 | Rate limits respetados: Amazon SP API 2 req/s, Tradeling 3 req/s, TinEye/SerpAPI limitado a 200/día |

### Additional Requirements

| Req | Descripción |
|-----|-------------|
| DEP-01 | Ontólogo PVF (exp. industria ANSI/ASME/DIN/ASTM/API/ISO) — recurso humano externo, no dev story |
| DEP-02 | ETL Data Engineer para carga continua del grafo — recurso humano externo, no dev story |
| W-2 | Fix `Neo4jGraphRepository.health_check()` siempre `False` (cubierto por FR-F15-04) |
| W-3 | Fix `pytest.mark` lifecycle en tests Neo4j stub (cubierto por FR-F15-04) |
| W-1 | Fix `_verdict()` boundary frágil en `g4_report.py` (cubierto por FR-F15-15) |
| W-4 | Fix `failures` dict trata falsy non-bool como fallos en `metrics_collector.py` (cubierto por FR-F15-15) |

### FR Coverage Map

| FR | Epic |
|----|------|
| FR-F15-01 | Epic 1 |
| FR-F15-02 | Epic 1 |
| FR-F15-03 | Epic 1 |
| FR-F15-04 | Epic 1 |
| FR-F15-05 | Epic 1 |
| FR-F15-06 | Epic 2 |
| FR-F15-07 | Epic 2 |
| FR-F15-08 | Epic 2 |
| FR-F15-09 | Epic 2 |
| FR-F15-10 | Epic 2 |
| FR-F15-11 | Epic 3 |
| FR-F15-12 | Epic 3 |
| FR-F15-13 | Epic 1 (Story 1.6) + Epic 3 (Story 3.1 parcial) |
| FR-F15-14 | Epic 3 |
| FR-F15-15 | Epic 3 |
| FR-F15-16 | Epic 3 (Story 3.4 — spike) |
| W-1, W-4 | Epic 3 (Story 3.5) |
| W-2, W-3 | Epic 1 (Story 1.4) |

---

## Epic List

### Epic 1: EP-F15-01 — Knowledge Graph Foundation
El equipo de TI puede proveer un grafo de conocimiento Neo4j operativo, sembrado con datos de compatibilidad de materiales, fabricantes y estándares, con CDC sincronizando cambios desde Postgres, que el comparador puede consultar para mejorar la precisión de matching.
**FRs cubiertos:** FR-F15-01, FR-F15-02, FR-F15-03, FR-F15-04, FR-F15-05, FR-F15-13, W-2, W-3

### Epic 2: EP-F15-02 — Pipeline Activation
Los usuarios de pricing pueden obtener comparaciones reales de productos contra Amazon UAE, Noon y Tradeling usando el pipeline completo con VLM judge y reverse image search activados, reemplazando todos los stubs de Fase 1.
**FRs cubiertos:** FR-F15-06, FR-F15-07, FR-F15-08, FR-F15-09, FR-F15-10

### Epic 3: EP-F15-03 — Precision Enhancement
El equipo técnico puede mejorar la precisión del comparador de 85-92% (Fase 1) a 92-95% (Fase 1.5) mediante dataset etiquetado, embedding fine-tuning, predicción conformal y ajuste de pesos por familia de producto.
**FRs cubiertos:** FR-F15-11, FR-F15-12, FR-F15-13 (parcial), FR-F15-14, FR-F15-15, FR-F15-16, W-1, W-4

---

## Epic 1: EP-F15-01 — Knowledge Graph Foundation

**Goal:** El equipo de TI puede proveer un grafo de conocimiento Neo4j operativo, sembrado con datos de compatibilidad de materiales, fabricantes y estándares, con CDC sincronizando cambios desde Postgres, que el comparador puede consultar para mejorar la precisión de matching.

---

### Story 1.1: Provisionamiento Neo4j + validación residencia datos UAE

Como ingeniero de infraestructura,
Quiero que el contenedor Neo4j 5.20 esté provisionado, documentado y validado para cumplir con los requisitos de residencia de datos UAE,
Para que el equipo de desarrollo pueda conectarse al grafo local y el equipo legal pueda confirmar que los datos no salen de la región designada.

**Acceptance Criteria:**

**Dado** que `docker-compose.dev.yml` tiene definido el servicio `neo4j` con imagen `neo4j:5.20` y puertos `17474:7474` y `17687:7687`
**Cuando** se ejecuta `docker compose -f docker-compose.dev.yml up neo4j`
**Entonces** el endpoint `http://localhost:17474` responde con HTTP 200 y el endpoint Bolt `bolt://localhost:17687` acepta conexión con las credenciales definidas en `NEO4J_USER` y `NEO4J_PASSWORD`
**Y** el archivo `.env.example` incluye las variables `NEO4J_URI=bolt://neo4j:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD=<secret>`, `NEO4J_DATABASE=neo4j`, `NEO4J_CONNECTION_TIMEOUT_S=10`, `NEO4J_MAX_CONNECTION_POOL_SIZE=50`
**Y** existe un documento `docs/runbooks/neo4j-data-residency-uae.md` que describe: (a) despliegue Hetzner staging en región EU/AE, (b) no se usan Aura cloud ni AuraDB, (c) backups en el mismo host Hetzner, (d) política de retención y responsable de compliance
**Y** el `Healthcheck` del servicio `neo4j` en `docker-compose.dev.yml` usa `cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD "RETURN 1"` con `interval: 15s`, `timeout: 5s`, `retries: 5`

**Story Points:** 3
**FRs cubiertos:** FR-F15-01

---

### Story 1.2: Schema KG + seed Compatibilidad Materiales (657 filas)

Como especialista técnico de producto,
Quiero que el grafo Neo4j tenga un schema definido con constraints e índices, y esté sembrado con 657 filas de compatibilidad de materiales industriales,
Para que el comparador pueda consultar relaciones de compatibilidad material como señal de matching desde el primer día.

**Acceptance Criteria:**

**Dado** que Neo4j está operativo (Story 1.1 completada) y `GRAPHRAG_BACKEND=neo4j`
**Cuando** se ejecuta el script `scripts/seed_kg_materials.py`
**Entonces** Neo4j contiene los constraints: `CONSTRAINT FOR (n:Material) REQUIRE n.primary_key IS UNIQUE`, `CONSTRAINT FOR (n:Standard) REQUIRE n.primary_key IS UNIQUE`, `CONSTRAINT FOR (n:Manufacturer) REQUIRE n.primary_key IS UNIQUE`, `CONSTRAINT FOR (n:ProductFamily) REQUIRE n.primary_key IS UNIQUE`
**Y** la query `MATCH (m:Material) RETURN count(m) AS c` devuelve `c >= 50` (materiales únicos: brass_CW617N, stainless_316, carbon_steel, etc.)
**Y** la query `MATCH ()-[r:COMPATIBLE_WITH]->() RETURN count(r) AS c` devuelve `c >= 657`
**Y** cada relación `COMPATIBLE_WITH` tiene propiedades: `pressure_bar: float`, `temperature_range: string`, `standard: string`, `confidence: float` (0.0-1.0)
**Y** el script es idempotente: ejecutarlo dos veces produce el mismo resultado (usa `MERGE`, no `CREATE`)
**Y** existe el archivo `scripts/seed_data/kg_materials_seed.csv` con 657+ filas y columnas `material_a,material_b,pressure_bar,temperature_range,standard,confidence`
**Y** `pytest tests/integration/scripts/test_seed_kg_materials.py` pasa con Neo4j real (marcado `@pytest.mark.neo4j_real`)

**Story Points:** 5
**FRs cubiertos:** FR-F15-02

---

### Story 1.3: CDC Postgres → Neo4j pipeline (Supabase Realtime → Celery → Cypher)

Como arquitecto de datos,
Quiero que los cambios en tablas clave de Postgres se propaguen automáticamente al grafo Neo4j vía un worker Celery,
Para que el KG esté siempre sincronizado con el catálogo de productos sin intervención manual.

**Acceptance Criteria:**

**Dado** que Supabase Realtime está habilitado para las tablas `products` y `competitor_listings` y `GRAPHRAG_BACKEND=neo4j`
**Cuando** se inserta o actualiza una fila en `products` (campos: `sku`, `name_en`, `family`, `material`, `dn`, `pn`)
**Entonces** el worker Celery `app.workers.tasks.graphrag.sync_product_to_kg` se ejecuta en menos de 5 segundos
**Y** Neo4j contiene un nodo `Product {primary_key: sku, name_en, family, material, dn, pn}` creado/actualizado via `MERGE`
**Cuando** se inserta o actualiza una fila en `competitor_listings`
**Entonces** Neo4j contiene nodo `CompetitorListing` y arista `(:Product)-[:HAS_COMPETITOR_LISTING]->(:CompetitorListing)`
**Y** si Neo4j está caído, la task Celery hace retry con backoff exponencial (max 3 intentos, delays 10s/30s/90s) y loguea `graphrag.cdc.retry sku=<sku> attempt=<n>`
**Y** el modelo `app/db/models/cdc_event.py` registra cada evento con campos `table_name`, `operation`, `record_id`, `processed_at`, `status` (`ok`/`error`/`retry`)
**Y** `pytest tests/unit/workers/test_graphrag_task.py` cubre: propagación exitosa, retry en fallo Neo4j, idempotencia (mismo evento dos veces no crea duplicados)

**Story Points:** 8
**FRs cubiertos:** FR-F15-03

---

### Story 1.4: Activar Neo4jGraphRepository (swap stub → real) + fix health_check

Como desarrollador backend,
Quiero que `Neo4jGraphRepository` implemente `get_product_neighbors` y `get_competitor_context` con Cypher real, y que `health_check()` devuelva `healthy: True` cuando Neo4j responde,
Para resolver los deferred W-2 y W-3 y poder activar el backend Neo4j en staging con `GRAPHRAG_BACKEND=neo4j`.

**Acceptance Criteria:**

**Dado** que `GRAPHRAG_BACKEND=neo4j` está seteado y Neo4j está operativo
**Cuando** se llama a `get_graph_repository()` en `app/services/comparator/graph_repository.py`
**Entonces** devuelve una instancia de `Neo4jGraphRepository` con `_graph_store` de tipo `Neo4jGraphStore` (no `None`)
**Cuando** se llama a `Neo4jGraphRepository.health_check()`
**Entonces** devuelve `{"backend": "neo4j_graph_repository", "healthy": True, "nodes": <int>, "edges": <int>}` — ya no devuelve `healthy: False` hardcodeado (fix W-2)
**Cuando** se llama a `Neo4jGraphRepository.get_product_neighbors(product_sku="MTBR4001050")`
**Entonces** ejecuta Cypher `MATCH (p:Product {primary_key: $sku})-[r]->(n) RETURN ...` y devuelve lista de dicts (lista vacía si no hay vecinos, nunca lanza `NotImplementedError`)
**Cuando** se llama a `Neo4jGraphRepository.get_competitor_context(competitor_listing_id=<uuid>)`
**Entonces** ejecuta traversal Cypher y devuelve dict con `product_matches`, `supplier_hints`, `graph_confidence`
**Y** tests de integración en `tests/integration/services/graphrag/test_neo4j_real.py` usan marca `@pytest.mark.neo4j_real` correctamente (fix W-3)
**Y** `GET /graphrag/health` devuelve HTTP 200 con `{"neo4j": {"healthy": true}}` cuando `GRAPHRAG_BACKEND=neo4j`

**Story Points:** 5
**FRs cubiertos:** FR-F15-04, W-2, W-3

---

### Story 1.5: Tabla product_equivalences + ingestión desde fichas técnicas

Como analista de producto,
Quiero que exista la tabla `product_equivalences` en Postgres y un pipeline que ingiera equivalencias desde fichas técnicas PDF y las refleje como aristas `EQUIVALENT_TO` en Neo4j,
Para que el comparador pueda usar equivalencias cross-fabricante como señal de matching de alta precisión (confidence 0.99).

**Acceptance Criteria:**

**Dado** que no existe la tabla `product_equivalences`
**Cuando** se ejecuta `alembic upgrade head`
**Entonces** existe la tabla con columnas: `id UUID PK`, `sku_mt VARCHAR(64) REFERENCES products(sku)`, `sku_equivalent VARCHAR(64)`, `manufacturer_equivalent VARCHAR(128)`, `standard VARCHAR(64)`, `confidence FLOAT DEFAULT 0.0`, `source VARCHAR(32)` (values: `pdf_extract`|`manual`|`cdc`), `created_at`, `updated_at`; índice `UNIQUE (sku_mt, sku_equivalent)`
**Dado** que existe un PDF de ficha técnica en `supabase/storage/product-images/<product_id>/<filename>.pdf`
**Cuando** se ejecuta la task Celery `app.workers.tasks.equivalences.ingest_equivalences_from_pdf(product_id=<uuid>)`
**Entonces** el worker extrae texto con `pdfplumber` e identifica patrones de equivalencia (regex sobre `"equivalent to"`, `"replaces"`, `"compatible with"`, `"يعادل"`)
**Y** inserta/actualiza filas en `product_equivalences` con `source=pdf_extract` y `confidence` derivada del patrón (exact match=0.95, fuzzy=0.70)
**Y** por cada fila insertada, encola `sync_equivalence_to_kg` que escribe `MERGE (a:Product)-[:EQUIVALENT_TO {confidence, source}]->(b:Product)` en Neo4j
**Y** `pytest tests/unit/workers/test_equivalences_task.py` incluye tests con PDF fixture de 3 páginas y al menos 5 equivalencias esperadas

**Story Points:** 8
**FRs cubiertos:** FR-F15-05

---

### Story 1.6: Dashboard monitoreo KG + tests integridad nightly

Como ingeniero de operaciones,
Quiero un endpoint de métricas del KG y una task Celery Beat nightly que verifique la integridad del grafo,
Para que el equipo pueda detectar degradación de datos o nodos huérfanos antes de que afecten al comparador en producción.

**Acceptance Criteria:**

**Dado** que `GRAPHRAG_BACKEND=neo4j` está seteado y Neo4j está operativo
**Cuando** se llama a `GET /graphrag/metrics`
**Entonces** responde HTTP 200 con JSON que incluye: `nodes` (conteos por tipo), `edges` (conteos por tipo), `orphan_nodes: int`, `last_cdc_event_at: ISO8601|null`, `cdc_lag_seconds: float`, `healthy: bool`
**Y** si `cdc_lag_seconds > 300`, `healthy` es `false` y el endpoint devuelve HTTP 503
**Dado** que Celery Beat tiene la task `kg_integrity_check` programada con `crontab(hour=2, minute=0)` (02:00 UTC)
**Cuando** se ejecuta `app.workers.tasks.graphrag.kg_integrity_check()`
**Entonces** ejecuta validaciones Cypher para: nodos Product huérfanos, aristas EQUIVALENT_TO sin `confidence`, nodos Material sin relaciones COMPATIBLE_WITH
**Y** los resultados se persisten en tabla `kg_integrity_results` (nueva migración Alembic) con campos `id`, `run_at`, `orphan_nodes`, `missing_confidence_edges`, `isolated_materials`, `passed BOOLEAN`
**Y** si `passed = False`, encola notificación vía `send_alert(channel='ops', message='KG integrity check failed: ...')`
**Y** tests unitarios cubren: todo OK, nodos huérfanos detectados, Neo4j caído (task no lanza excepción no manejada)

**Story Points:** 5
**FRs cubiertos:** FR-F15-13

---

## Epic 2: EP-F15-02 — Pipeline Activation

**Goal:** Los usuarios de pricing pueden obtener comparaciones reales de productos contra Amazon UAE, Noon y Tradeling usando el pipeline completo con VLM judge y reverse image search activados, reemplazando todos los stubs de Fase 1.

---

### Story 2.1: Amazon SP API fetcher real

Como analista de pricing de MT,
Quiero que el sistema consulte Amazon UAE mediante el Amazon SP API real (no el stub),
Para que las comparaciones de precios reflejen listings reales del marketplace y no datos simulados.

**Acceptance Criteria:**

**Dado** que las variables `SP_API_REFRESH_TOKEN`, `SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `SP_API_SELLER_ID` y `MT_LIVE_NETWORK=true` están configuradas
**Cuando** el pipeline solicita datos de un ASIN en Amazon.ae (`MARKETPLACE_ID=A2VIGQ35RCS4UG`)
**Entonces** `AmazonSPApiAdapter` realiza `GET /catalog/2022-04-01/items/{ASIN}` a `https://sellingpartnerapi-eu.amazon.com` con token LWA OAuth2
**Y** el token LWA se cachea en memoria con TTL 3500s; se refresca lazy antes del siguiente request al expirar
**Y** el adapter respeta rate limits del endpoint `getCatalogItem` (2 req/s burst 6) mediante token bucket con `aiolimiter`, estado compartido en Redis entre workers
**Y** ante HTTP 429 o error transitorio: backoff exponencial `tenacity` (3 intentos, espera 1-4s); errores 4xx no se reintentan
**Y** si después de 3 intentos falla, se registra en `competitor_fetch_errors` con `source=amazon_sp_api`, `error_code`, `asin`, `retried_at` y el pipeline continúa sin datos Amazon para ese SKU
**Y** si `MT_LIVE_NETWORK != true` o faltan credenciales, cae transparentemente al stub `AmazonSPApiStub`
**Y** tests de integración mockean `httpx.AsyncClient` cubriendo: LWA refresh exitoso/fallido, 200, 429→retry→éxito, 429→retry exhausted→stub fallback

**Story Points:** 8
**FRs cubiertos:** FR-F15-06

---

### Story 2.2: VLM Judge activación (claude-sonnet-4-6 audit-grade)

Como analista de pricing o validador humano de MT,
Quiero que cada comparación de producto pase por un juez VLM basado en `claude-sonnet-4-6` que genere un veredicto estructurado con razonamiento en lenguaje natural,
Para que las decisiones de matching sean auditables y los validadores humanos comprendan el "por qué" antes del score numérico.

**Acceptance Criteria:**

**Dado** que un candidato superó las etapas previas del pipeline y `VLM_JUDGE_ENABLED=true`
**Cuando** `VlmJudgeService` invoca `claude-sonnet-4-6` via Anthropic SDK con imágenes del SKU master y candidato
**Entonces** el prompt solicita respuesta JSON con esquema: `{"verdict": "match|reject|uncertain", "confidence": 0.0-1.0, "reasoning": "<1-3 frases>", "deal_breakers_triggered": ["..."], "image_regions": [{"side": "sku|candidate", "description": "..."}]}` sin texto fuera del JSON
**Y** respuesta validada con Pydantic; si JSON inválido → veredicto `uncertain`, `confidence=0.0`, log WARNING
**Y** resultado persistido en `match_decisions`: `judge_verdict`, `judge_confidence NUMERIC(4,3)`, `judge_rationale`, `judge_image_regions JSONB`, `deal_breakers_triggered TEXT[]`, `judge_model_version=claude-sonnet-4-6`, `judge_at`
**Y** si `judge_verdict='uncertain'` y `confidence < 0.50` → enrutamiento automático a `human_review_queue` con `reason=vlm_uncertain`
**Y** UI de validación humana renderiza `judge_rationale` ANTES del score numérico (anti-anchor bias)
**Y** acceso a `judge_rationale` e `image_regions` restringido por RBAC a roles `admin`, `gerente`, `validador`; rol `viewer` recibe `null`
**Y** tests unitarios cubren: JSON válido, JSON inválido → fallback uncertain, uncertain < 0.50 → cola humana

**Story Points:** 8
**FRs cubiertos:** FR-F15-07

---

### Story 2.3: Reverse Image Search activación (feature flag on)

Como analista de pricing de MT,
Quiero activar la búsqueda inversa de imágenes para candidatos con baja confianza calibrada,
Para que el pipeline rescate matches legítimos cuyas imágenes de catálogo no superan el umbral de embedding/VLM, detectando fotos reutilizadas por múltiples vendors.

**Acceptance Criteria:**

**Dado** que el feature flag `reverse_image_search` está activo y `REVERSE_IMAGE_PROVIDER=tineye` o `google_lens_serpapi`
**Cuando** el pipeline obtiene `calibrated_confidence < 0.50` para un candidato tras embedding, OCR y VLM judge
**Entonces** se invoca `ReverseImageSearchService.search(image_url)` antes del descarte definitivo
**Y** si `REVERSE_IMAGE_PROVIDER=tineye` → adapter `TinEyeAdapter` con `TINEYE_API_KEY`; si `google_lens_serpapi` → `GoogleLensSerpApiAdapter` con `SERPAPI_KEY`
**Y** si se alcanza `REVERSE_IMAGE_DAILY_LIMIT` (default 200) → retorna `{"hits": [], "limit_reached": true}`, candidato continúa al descarte sin error
**Y** si algún hit pertenece a `manufacturers_whitelist.canonical_domains` para ese SKU → re-score con boost `+0.15` sobre `calibrated_confidence`
**Y** resultados persistidos en `competitor_listings`: `reverse_image_hits JSONB`, `reverse_image_searched_at`, `reverse_image_provider`
**Y** si feature flag está OFF → no-op transparente sin latencia adicional ni llamadas externas
**Y** feature flag togglable en caliente desde `flag_service.py` sin reinicio del worker

**Story Points:** 5
**FRs cubiertos:** FR-F15-08

---

### Story 2.4: Price Sanity Check (P10/P90 calibration, pre-VLM filter)

Como analista de pricing de MT,
Quiero que el pipeline descarte o enrute automáticamente candidatos con precios anómalos antes de invocar el VLM judge,
Para que el sistema no gaste tokens VLM en candidatos obviamente incorrectos y los analistas reciban alertas tempranas sobre outliers de precios.

**Acceptance Criteria:**

**Dado** que `price_calibration_ranges` tiene rangos P10/P90 por categoría con campos `category_id`, `expected_min_p10 NUMERIC`, `expected_max_p90 NUMERIC`, `currency CHAR(3)`, `updated_at`
**Cuando** el pipeline evalúa un candidato con precio `candidate_price` en etapa pre-VLM
**Entonces** `PriceSanityCheckService.check(candidate_price, category_id, currency)` compara contra el rango calibrado
**Y** si `candidate_price < expected_min_p10 * 0.30` → flag `price_too_low=True`, enrutamiento a `human_review_queue` con `reason=price_sanity_too_low` sin invocar VLM
**Y** si `candidate_price > expected_max_p90 * 3.00` → flag `price_too_high=True`, enrutamiento a `human_review_queue` con `reason=price_sanity_too_high` sin invocar VLM
**Y** flags `price_too_low` y `price_too_high` persistidos en `competitor_listings` como columnas `BOOLEAN DEFAULT FALSE`
**Y** si la categoría no tiene rango calibrado → chequeo omitido (`sanity_check_skipped=True`), pipeline continúa al VLM sin bloqueo
**Y** job Celery `recalibrate_price_ranges` recalcula P10/P90 por categoría desde últimos 90 días de datos en `competitor_listings`
**Y** métrica Prometheus `price_sanity_rejections_total{reason="price_too_low|price_too_high"}` por candidato rechazado
**Y** tests cubren: precio normal → pass, <30% P10 → cola humana, >300% P90 → cola humana, sin calibración → skip

**Story Points:** 5
**FRs cubiertos:** FR-F15-09

---

### Story 2.5: Tradeling API integration (MENA B2B fetcher)

Como analista de pricing de MT,
Quiero que el pipeline consulte precios y listings del marketplace Tradeling (MENA B2B) mediante su API oficial,
Para que las comparaciones cubran el canal B2B regional más relevante de Middle East además de Amazon UAE y Noon.

**Acceptance Criteria:**

**Dado** que `TRADELING_API_KEY` y `TRADELING_API_BASE_URL` (default `https://api.tradeling.com/v1`) están configuradas
**Cuando** el pipeline solicita datos de un producto en Tradeling para un SKU master
**Entonces** `TradelingAdapter` (implementa `FetcherPort`) realiza `GET /products/search?query={product_title}&category={category_id}&marketplace=UAE` con `Authorization: Bearer {TRADELING_API_KEY}`
**Y** cada candidato retornado se normaliza a `CompetitorListing` con: `external_id`, `title`, `price`, `currency=AED`, `brand`, `seller_name`, `product_url`, `image_urls[]`, `source=tradeling`
**Y** rate limit 3 req/s via `aiolimiter`; ante HTTP 429 → backoff exponencial `tenacity` (3 intentos, espera 2-8s)
**Y** si API devuelve 401/403 → lanza `TradelingAuthError`, detiene pipeline para ese SKU sin retry, registra en `competitor_fetch_errors` con `source=tradeling`, `error_code=auth_error`
**Y** si `TRADELING_API_KEY` no está configurada → retorna `[]` con log WARNING (modo degradado, no rompe pipeline)
**Y** candidatos Tradeling pasan por el mismo pipeline de 9 etapas que Amazon/Noon
**Y** tests cubren: búsqueda exitosa → normalización, 429→retry→éxito, 401→`TradelingAuthError`, clave no configurada→lista vacía

**Story Points:** 8
**FRs cubiertos:** FR-F15-10

---

## Epic 3: EP-F15-03 — Precision Enhancement

**Goal:** El equipo técnico puede mejorar la precisión del comparador de 85-92% (Fase 1) a 92-95% (Fase 1.5) mediante dataset etiquetado, embedding fine-tuning, predicción conformal y ajuste de pesos por familia de producto.

---

### Story 3.1: Pipeline de etiquetado humano + exportación dataset

Como ingeniero de ML del equipo de R&D,
Quiero un endpoint FastAPI y un script CLI que exporten los matches humanos confirmados como pares etiquetados `(sku_mt, candidate_external_id, label)`,
Para que el dataset sirva como base de entrenamiento para fine-tuning de embeddings con ≥1k pares reales.

**Acceptance Criteria:**

**Dado** que `match_candidates` contiene registros con `label IN ('accept','reject')` y `status='validated'`
**Cuando** se llama a `GET /api/v1/comparator/dataset/export?format=jsonl&min_pairs=1000`
**Entonces** responde con archivo JSONL donde cada línea contiene `{"sku_mt": "...", "candidate_id": "...", "title": "...", "specs_jsonb": {...}, "label": 1}` con `label` convertido a int (accept→1, reject→0)
**Y** si pares disponibles < `min_pairs` → HTTP 422 con `{"error": "insufficient_pairs", "available": N, "required": 1000}`
**Dado** un entorno sin acceso HTTP
**Cuando** se ejecuta `python -m scripts.poc.export_dataset --output datasets/labeled_pairs_YYYY-MM-DD.jsonl --min-pairs 1000`
**Entonces** conecta a DB via `DATABASE_URL`, escribe JSONL, imprime resumen `{"total_pairs": N, "accept": N_a, "reject": N_r, "skus_unique": N_s}`; código salida 0 si `total_pairs >= min_pairs`, 1 en caso contrario
**Cuando** se ejecuta validación `--validate <path>`
**Entonces** verifica campos obligatorios, `label` ∈ {0,1}, no duplicados `(sku_mt, candidate_id)`, ratio positivos/negativos ≥0.3 y ≤0.7; anomalías como WARNING sin abortar salvo campos obligatorios faltantes

**Story Points:** 5
**FRs cubiertos:** FR-F15-11

---

### Story 3.2: Embedding fine-tune sobre dataset MT ≥1k pares

Como ingeniero de ML del equipo de R&D,
Quiero una Celery task `finetune_embeddings` que entrene un modelo `sentence-transformers/all-MiniLM-L6-v2` con el dataset etiquetado y persista el modelo en Supabase Storage,
Para que el scorer cargue embeddings especializados en semántica de válvulas y fittings industriales.

**Acceptance Criteria:**

**Dado** que existe JSONL ≥1000 pares en `datasets/labeled_pairs_*.jsonl` o bucket `ml-datasets`
**Cuando** se encola `finetune_embeddings.delay(dataset_path=..., model_base="sentence-transformers/all-MiniLM-L6-v2", epochs=3, batch_size=16)`
**Entonces** entrena usando `CosineSimilarityLoss` con `InputExample(texts=[title_mt, title_candidate], label=float(label))`
**Y** modelo persistido en bucket `ml-models` bajo `embeddings/all-MiniLM-L6-v2-mt-finetuned-YYYY-MM-DD/` con `pytorch_model.bin` + `config.json` + `tokenizer_config.json`
**Y** registro en tabla `comparator_model_registry` (nueva, migración Alembic): `model_name`, `base_model`, `storage_path`, `eval_metrics_jsonb` (contiene `cosine_accuracy_val`, `eval_loss`), `trained_at`, `status='candidate'`
**Y** log estructurado al finalizar: `{"event": "finetune_complete", "model_path": "...", "eval_cosine_accuracy": X.XX, "duration_s": N}`
**Y** si dataset < 1000 pares → task falla con `Retry`, log `{"event": "finetune_aborted", "reason": "insufficient_data", "available_pairs": N}`, no persiste modelo parcial
**Dado** modelo `status='candidate'` en registry
**Cuando** se ejecuta `python -m scripts.poc.promote_model --model-id <uuid> --env staging`
**Entonces** registro actualizado a `status='active'`, `comparator_config.embedding_model_path` apunta a nueva ruta; modelo anterior → `status='retired'`

**Story Points:** 8
**FRs cubiertos:** FR-F15-12

---

### Story 3.3: Conformal Prediction / Venn-Abers sobre calibrator

Como ingeniero de ML del equipo de R&D,
Quiero integrar `MapieRegressor` (o fallback Venn-Abers interno) sobre los scores calibrados del `IsotonicCalibrator` existente para obtener intervalos de predicción con garantía de cobertura ≥98%,
Para que el comparador garantice por construcción que la tasa de falsos positivos sea <2% en producción.

**Acceptance Criteria:**

**Dado** que `IsotonicCalibrator` produce `calibrated_confidence ∈ [0,1]` para cada `MatchCandidate`
**Cuando** se instancia `ConformalWrapper(calibrator=isotonic_cal, method="mapie", alpha=0.02)` y se llama a `wrapper.fit(cal_scores, labels)` (mínimo 200 muestras hold-out)
**Entonces** `wrapper.predict_with_interval(score)` retorna `(point_estimate, lower_bound, upper_bound)` con cobertura empírica hold-out ≥ 0.98
**Y** test unitario `test_conformal_coverage` verifica cobertura ≥ 0.98 sobre 500 pares sintéticos (tolerancia ±0.005)
**Dado** `ConformalWrapper` integrado en `app/services/matching/calibrator.py`
**Cuando** se calcula `MatchCandidate.calibrated_confidence`
**Entonces** campos `conf_lower` y `conf_upper` (nuevas columnas `Numeric(5,4)` en `match_candidates`) se persisten junto a `calibrated_confidence` (migración Alembic incluye índices `idx_mc_conf_lower` y `idx_mc_conf_upper`)
**Y** si `conf_lower > 0.70` → `review_priority='low'`; si `conf_upper < 0.50` → `review_priority='high'`
**Y** si `mapie` no disponible (ImportError) → fallback a Venn-Abers interno con `logger.warning("mapie not available, using built-in Venn-Abers fallback")`

**Story Points:** 8
**FRs cubiertos:** FR-F15-14

---

### Story 3.4: Cross-Encoder / Cohere Reranker — spike evaluación + ADR

Como arquitecto técnico del equipo de R&D,
Quiero ejecutar un spike de evaluación comparativa entre Cohere Reranker v3 y `cross-encoder/ms-marco-MiniLM-L-6-v2` sobre el dataset MT etiquetado,
Para que el equipo tome una decisión documentada build-vs-buy antes de invertir en integración de producción.

**Acceptance Criteria:**

**Dado** que existe el dataset etiquetado de Story 3.1 con ≥500 pares
**Cuando** se ejecuta `python scripts/poc/spike_cross_encoder.py --dataset datasets/labeled_pairs_latest.jsonl --candidates 5`
**Entonces** el script evalúa ambas opciones (Cohere API + cross-encoder local) sobre muestra de 100 SKUs × 5 candidatos, midiendo `precision@1`, `ndcg@3`, `latency_p50_ms`, `latency_p99_ms`, `cost_per_1k_skus_usd`
**Y** genera `docs/rnd/spike-cross-encoder-results-YYYY-MM-DD.json` con métricas comparativas
**Dado** que el spike completó
**Cuando** el equipo revisa resultados
**Entonces** se produce ADR `docs/adr/ADR-0XX-cross-encoder-reranker.md` con: tabla comparativa, decisión explícita (`buy`|`build`|`defer`) y condiciones de revisión
**Y** si decisión es `build` → `RerankerPort` en `app/services/comparator/interfaces.py` acepta `rerank(query: str, candidates: list[str]) -> list[RankedCandidate]` opt-in via feature flag `ENABLE_CROSS_ENCODER_RERANKER=false`
**Y** si decisión es `buy` → ADR incluye estimación coste mensual para 10k SKUs/día y umbral de volumen donde local se vuelve más económico

**Story Points:** 5
**FRs cubiertos:** FR-F15-16

---

### Story 3.5: Weight tuning por familia de producto + fix deferred W-1/W-4

Como ingeniero de backend del equipo de comparador,
Quiero externalizar los pesos del scorer a `scorer_weights_by_family.yaml` con perfiles por familia, y corregir los defects W-1 y W-4 en `g4_report.py` y `metrics_collector.py`,
Para que el scorer use pesos optimizados por familia y el sistema de decisión G4 sea robusto ante expansión futura de ACs y tipos de valores.

**Acceptance Criteria:**

**Dado** `config/scorer_weights_by_family.yaml` con perfiles `default`, `valve_family`, `fitting_family` (5 dimensiones: material, pn, thread, norma, brand_tier, delivery sumando 1.0)
**Cuando** `ScoringService.score(sku_dict, candidate_dict)` detecta `sku_dict["family"] == "valve_family"`
**Entonces** usa pesos de `valve_family` y retorna `ScoringBreakdown` con `metadata.weights_profile="valve_family"`
**Y** si `SCORER_WEIGHTS_PATH` no configurado o archivo no existe → fallback a pesos hardcoded actuales con `logger.warning`
**Dado** fix W-1 en `scripts/poc/g4_report.py`
**Cuando** se evalúa `_verdict(ac_results: dict[str, bool | int | float])` con threshold configurable
**Entonces** `_verdict(results, fail_threshold=2)` usa `fail_threshold` configurable (default 2, mantiene comportamiento actual)
**Y** test `test_verdict_boundary_configurable` verifica: `_verdict({"ac1": False, "ac2": False, "ac3": True}, fail_threshold=1)` → `"DEFER"` y `_verdict({"ac1": False, "ac2": True, "ac3": True}, fail_threshold=2)` → `"BUILD_CONDITIONAL"`
**Dado** fix W-4 en `scripts/poc/metrics_collector.py`
**Cuando** `failures = [...]` evalúa entradas con `v = 0` (int) o `v = 0.0` (float)
**Entonces** solo `False` explícito y valores negativos son fallos; `0` y `0.0` no son fallos
**Y** test `test_failures_falsy_non_bool` verifica `_collect_failures({"ok": 0, "fail": False, "good": 0.0})` → `["fail"]` únicamente
**Y** suite completa `pytest tests/unit/scripts/poc/ tests/unit/services/matching/ -v` pasa sin regresiones; cobertura `g4_report.py` y `metrics_collector.py` ≥ 85%

**Story Points:** 5
**FRs cubiertos:** FR-F15-15, W-1, W-4
