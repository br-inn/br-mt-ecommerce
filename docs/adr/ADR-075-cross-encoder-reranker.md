# ADR-075 — Cross-Encoder / Cohere Reranker Decision

**Status:** Proposed
**Date:** 2026-05-12

## Context

El pipeline de matching de productos MT usa embeddings (ANN) para recuperar candidatos competitor listings. La fase de reranking — reordenar los candidatos recuperados con un modelo que evalúa la relevancia pairwise (query, candidato) — no está implementada.

Se evalúan dos opciones:

- **Cohere Rerank v3** (`rerank-multilingual-v3.0`): API cloud, soporte multilingüe nativo (Árabe/Inglés), sin infra local.
- **cross-encoder/ms-marco-MiniLM-L-6-v2**: modelo open-source via `sentence-transformers`, sin coste de API, latencia controlada en host.

El spike `scripts/poc/spike_cross_encoder.py` permite evaluar ambas opciones con datos etiquetados reales (≥500 pares) del dataset `datasets/labeled_pairs_latest.jsonl`.

## Options Evaluated

| Opción | precision@1 | ndcg@3 | p50_ms | cost/1k USD |
|--------|-------------|--------|--------|-------------|
| Cohere Rerank v3 | TBD* | TBD* | TBD* | ~$1.00 |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | TBD* | TBD* | TBD* | $0.00 |

*Rellenar con resultados del spike cuando se ejecute con datos reales.

## Decision

**DEFER** — El spike requiere el dataset etiquetado ≥500 pares (US-F15-03-01). Revisitar en S12 con datos reales.

La interfaz `RerankerPort` ya existe en `app/services/comparator/interfaces.py` como stub. El feature flag `ENABLE_CROSS_ENCODER_RERANKER=false` garantiza que ningún código de producción activa este path.

## Consequences

- `RerankerPort` interface preparada en `app/services/comparator/interfaces.py` (feature flag `ENABLE_CROSS_ENCODER_RERANKER=false`)
- Ningún impacto en producción — flag desactivado por default
- El spike script `scripts/poc/spike_cross_encoder.py` queda listo para ejecutar en S12

## Review Conditions

- Cuando dataset ≥ 1k pares disponible
- Si precision@1 mejora > 3pp vs embedding-only → BUILD
- Si coste Cohere > $500/mes con volumen proyectado → prefer local cross-encoder
