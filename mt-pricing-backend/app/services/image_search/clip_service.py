"""
CLIP-based reverse image search service.
Flag: reverse_image_search (OFF by default — R&D only)

US-RND-01-09

Architecture:
- Embeddings stored in Neo4j vector index OR PostgreSQL pgvector (configurable)
- GRAPHRAG_BACKEND=neo4j → Neo4j; default → stub/pgvector

Note: `clip` and `torch` are NOT imported — they are optional R&D dependencies
not present in requirements.txt. The actual embedding generation is deferred to
a future sprint implementation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class ImageSearchResult:
    product_id: str
    sku: str
    similarity: float
    image_url: str | None = None


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------
class ImageEmbeddingBackend(Protocol):
    async def index_image(self, product_id: str, image_url: str) -> bool: ...
    async def search_similar(self, image_url: str, top_k: int = 10) -> list[ImageSearchResult]: ...


# ---------------------------------------------------------------------------
# Stub backend — development / testing (no external deps)
# ---------------------------------------------------------------------------
class StubBackend:
    """Stub para desarrollo/testing. No requiere Neo4j ni pgvector."""

    async def index_image(self, product_id: str, image_url: str) -> bool:
        logger.debug("clip.stub.index_image product_id=%s url=%s", product_id, image_url)
        return True

    async def search_similar(self, image_url: str, top_k: int = 10) -> list[ImageSearchResult]:
        logger.debug("clip.stub.search_similar url=%s top_k=%d", image_url, top_k)
        return []


# ---------------------------------------------------------------------------
# Neo4j backend stub — opt-in via GRAPHRAG_BACKEND=neo4j
# ---------------------------------------------------------------------------
class Neo4jCLIPBackend:
    """
    Conecta a Neo4j 7687 (bolt://neo4j:7687 en Docker).
    Usa Neo4j vector index para búsqueda de similitud CLIP.

    TODO (R&D sprint siguiente):
    - Descargar imagen desde image_url
    - Generar embedding CLIP (openai/clip-vit-base-patch32 o similar)
    - Indexar en Neo4j via vector index (Neo4j 5.x vector support)
    - Búsqueda: generar embedding de query image → db.index.vector.queryNodes()

    Por ahora: stub funcional — no conexión real a Neo4j ni a CLIP model.
    """

    _NEO4J_URI = "bolt://neo4j:7687"

    async def index_image(self, product_id: str, image_url: str) -> bool:
        # TODO: descargar imagen, generar embedding CLIP, indexar en Neo4j
        # Por ahora: stub que retorna True sin conectar
        logger.debug(
            "clip.neo4j.index_image (stub) product_id=%s url=%s neo4j_uri=%s",
            product_id,
            image_url,
            self._NEO4J_URI,
        )
        return True

    async def search_similar(self, image_url: str, top_k: int = 10) -> list[ImageSearchResult]:
        # TODO: generar embedding de imagen de query, buscar en Neo4j vector index
        logger.debug(
            "clip.neo4j.search_similar (stub) url=%s top_k=%d neo4j_uri=%s",
            image_url,
            top_k,
            self._NEO4J_URI,
        )
        return []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_image_backend() -> ImageEmbeddingBackend:
    """Devuelve el backend activo según GRAPHRAG_BACKEND env var.

    - ``GRAPHRAG_BACKEND=neo4j`` → :class:`Neo4jCLIPBackend`
    - default → :class:`StubBackend`
    """
    if os.getenv("GRAPHRAG_BACKEND") == "neo4j":
        return Neo4jCLIPBackend()
    return StubBackend()


__all__ = [
    "ImageEmbeddingBackend",
    "ImageSearchResult",
    "Neo4jCLIPBackend",
    "StubBackend",
    "get_image_backend",
]
