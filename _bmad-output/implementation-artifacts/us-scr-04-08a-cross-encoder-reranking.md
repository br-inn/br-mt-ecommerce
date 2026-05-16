# US-SCR-04-08a — Cross-Encoder Re-ranking + Cache Redis + Anthropic Prompt Caching

**Epic**: EP-SCR-04 — Monitoreo Autónomo + Price Intelligence  
**Sprint**: S16  
**Story Points**: 8 SP  
**Estado**: review  
**Fecha**: 2026-05-16

## Componentes implementados

### Cross-Encoder Reranker
- **Archivo**: `mt-pricing-backend/app/services/matching/cross_encoder_reranker.py`
- Modelo: `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`
- Cache Redis: key `rerank:{sha256_hash}` TTL 1h (3600s)
- Lazy init del modelo (singleton) — no carga hasta primera llamada
- Degradación graceful:
  - Si `sentence-transformers` no instalado → log WARNING, retorna orden original
  - Si Redis no disponible → skip cache, ejecuta modelo
  - Si modelo falla → log ERROR, retorna orden original (scores = None)

### Integración en Pipeline de Matching
- **Archivo**: `mt-pricing-backend/app/services/matching/match_service.py` ← **MODIFICADO en esta sesión**
- Bloque añadido al final de `refresh_candidates()` (después del sort por score determinista)
- Import lazy (`from app.services.matching.cross_encoder_reranker import rerank_candidates`)
- Si el reranker falla por cualquier motivo → except silencioso, mantiene orden original
- `redis_client=None` por ahora — opt-in cuando se wire el cliente Redis al servicio

### Anthropic Prompt Caching
- **Archivo**: `mt-pricing-backend/app/services/matching/llm_spec_extractor.py`
- `cache_control: {"type": "ephemeral"}` añadido al system prompt
- Ahorra tokens de input en llamadas repetidas al mismo system prompt largo

## Notas técnicas
- sentence-transformers NO está en `pyproject.toml` base — se instala en la imagen scraper-worker
- En dev local con Docker: el modelo se descargará en primera ejecución (~90MB)
- El fallback heurístico (title similarity × brand match) es el sort por `score` determinista existente
- Redis client wire-up: pendiente de conectar `settings.REDIS_URL` al MatchService constructor
