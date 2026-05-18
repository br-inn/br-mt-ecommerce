"""Utilidad de embeddings locales con sentence-transformers.

Modelo: all-MiniLM-L6-v2 (384 dims, ~90MB, Apache 2.0)
Se descarga automáticamente al primer uso y queda cacheado en el container.

Carga lazy: el modelo NO se instancia al importar el módulo — solo cuando
se llama por primera vez a `embed_offer()`. Esto evita penalizar el startup
del backend (que no necesita embeddings) y solo afecta al worker.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def _get_model() -> Any:
    global _model  # noqa: PLW0603
    if _model is None:
        from sentence_transformers import SentenceTransformer  # lazy import

        logger.info("embeddings.model_loading", extra={"model": _MODEL_NAME})
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("embeddings.model_ready", extra={"model": _MODEL_NAME, "dims": 384})
    return _model


def embed_offer(title: str, brand: str | None, specs: dict[str, Any]) -> list[float]:
    """Genera embedding de 384 dims para una oferta scrapeada.

    Concatena los campos más discriminantes separados por ' | '.
    El modelo normaliza los vectores (cosine similarity = dot product).
    """
    parts = [
        brand or "",
        title,
        specs.get("mpn") or specs.get("part_number") or "",
        specs.get("material") or "",
        specs.get("size") or "",
        specs.get("thread") or "",
        specs.get("pn") and f"PN{specs['pn']}" or "",
    ]
    text = " | ".join(p for p in parts if p)
    model = _get_model()
    vector: list[float] = model.encode(text, normalize_embeddings=True).tolist()
    return vector


def embed_sku(sku_dict: dict[str, Any]) -> list[float]:
    """Genera embedding para un SKU del catálogo MT.

    Usa los mismos campos que embed_offer para que los vectores
    sean comparables en el mismo espacio semántico.
    """
    specs = sku_dict.get("specs", {}) or {}
    parts = [
        sku_dict.get("brand") or "",
        sku_dict.get("name") or sku_dict.get("title") or "",
        sku_dict.get("mpn") or sku_dict.get("sku") or "",
        specs.get("material") or sku_dict.get("material") or "",
        specs.get("size") or sku_dict.get("size") or "",
        specs.get("thread") or sku_dict.get("thread") or "",
        sku_dict.get("pn") and f"PN{sku_dict['pn']}" or "",
    ]
    text = " | ".join(p for p in parts if p)
    model = _get_model()
    vector: list[float] = model.encode(text, normalize_embeddings=True).tolist()
    return vector
