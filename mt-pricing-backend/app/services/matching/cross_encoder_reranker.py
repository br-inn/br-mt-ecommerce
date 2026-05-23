"""cross_encoder_reranker.py — Re-ranking con ms-marco-MiniLM-L-6-v2 + Redis cache (US-SCR-04-08a).

Pipeline:
1. Recibe lista de (query_text, candidate_text) pares.
2. Hash SHA256 de la lista serializada → cache key ``rerank:{hash}`` en Redis TTL 1h.
3. Si hay cache hit → return cached scores.
4. Si no → cross-encoder ms-marco-MiniLM-L-6-v2 vía sentence-transformers.
5. Store en Redis + return scores.

Anthropic prompt caching:
- Los prompts de sistema del LLM matching (en llm_spec_extractor.py y llm_query_generator.py)
  son candidatos a cache_control ephemeral. Esta función se integra antes del LLM en el
  pipeline para reducir las llamadas LLM en candidatos ya bien rankeados.

Graceful degradation:
- Si sentence-transformers no está instalado → log WARNING, return scores vacíos.
- Si Redis no disponible → skip cache, run model.
- Si modelo falla → log ERROR, return original order (scores = None).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_REDIS_TTL = 3600  # 1 hora
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_CACHE_PREFIX = "rerank:"

# Singleton lazy para el modelo — no cargarlo hasta primera llamada
_cross_encoder_model: Any = None


def _get_model() -> Any:
    """Carga el cross-encoder con lazy init. Devuelve None si no disponible."""
    global _cross_encoder_model
    if _cross_encoder_model is not None:
        return _cross_encoder_model
    try:
        from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

        _cross_encoder_model = CrossEncoder(_MODEL_NAME)
        logger.info("cross_encoder.loaded", extra={"model": _MODEL_NAME})
    except ImportError:
        logger.warning(
            "cross_encoder.not_available",
            extra={"reason": "sentence-transformers not installed", "model": _MODEL_NAME},
        )
        _cross_encoder_model = None
    except Exception as exc:
        logger.error(
            "cross_encoder.load_failed",
            extra={"model": _MODEL_NAME, "error": str(exc)},
        )
        _cross_encoder_model = None
    return _cross_encoder_model


def _pairs_hash(pairs: list[tuple[str, str]]) -> str:
    """SHA256 de la lista serializada de pares (query, candidate)."""
    serialized = json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


async def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    text_field: str = "title",
    redis_client: Any = None,
) -> list[dict[str, Any]]:
    """Re-rankea candidatos usando cross-encoder ms-marco-MiniLM-L-6-v2.

    Args:
        query: Texto de búsqueda original (ej. SKU o descripción del producto MT).
        candidates: Lista de candidatos scrapeados (dicts con campo ``text_field``).
        text_field: Campo del dict candidato que contiene el texto a comparar.
        redis_client: Cliente Redis async opcional para cache. Si None, skip cache.

    Returns:
        Lista de candidatos reordenada por score cross-encoder DESC.
        Cada candidato recibe una clave ``rerank_score`` con el score raw.
        Si el modelo no está disponible, retorna la lista original sin modificar.
    """
    if not candidates:
        return candidates

    texts = [c.get(text_field, "") or "" for c in candidates]
    pairs = [(query, t) for t in texts]
    cache_key = f"{_CACHE_PREFIX}{_pairs_hash(pairs)}"

    # ── Try cache ─────────────────────────────────────────────────────────────
    scores: list[float] | None = None
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                scores = json.loads(cached)
                logger.debug("cross_encoder.cache_hit", extra={"key": cache_key})
        except Exception as redis_exc:
            logger.warning(
                "cross_encoder.redis_get_failed",
                extra={"error": str(redis_exc)[:120]},
            )

    # ── Run model if no cache ──────────────────────────────────────────────────
    if scores is None:
        model = _get_model()
        if model is None:
            # Graceful degradation: retornar orden original
            for c in candidates:
                c.setdefault("rerank_score", None)
            return candidates

        try:
            raw_scores = model.predict(pairs)
            scores = [float(s) for s in raw_scores]
            logger.info(
                "cross_encoder.scored",
                extra={"query": query[:80], "n_candidates": len(candidates)},
            )

            # Store en Redis
            if redis_client is not None:
                try:
                    await redis_client.set(cache_key, json.dumps(scores), ex=_REDIS_TTL)
                except Exception as redis_set_exc:
                    logger.warning(
                        "cross_encoder.redis_set_failed",
                        extra={"error": str(redis_set_exc)[:120]},
                    )
        except Exception as exc:
            logger.error(
                "cross_encoder.predict_failed",
                extra={"error": str(exc), "query": query[:80]},
            )
            for c in candidates:
                c.setdefault("rerank_score", None)
            return candidates

    # ── Attach scores y reordenar ─────────────────────────────────────────────
    for candidate, score in zip(candidates, scores, strict=False):
        candidate["rerank_score"] = score

    reranked = sorted(
        candidates, key=lambda c: c.get("rerank_score") or float("-inf"), reverse=True
    )
    return reranked


__all__ = ["rerank_candidates"]
