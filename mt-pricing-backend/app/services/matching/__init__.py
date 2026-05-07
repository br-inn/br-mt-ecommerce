"""Matching pipeline foundation — Sprint 3.

Implementa las dos primeras etapas del pipeline descrito en
``_bmad-output/planning-artifacts/mt-product-matching-pipeline-detail.md``
(Etapa 1 Query Builder + Etapa 2 Multi-Source Fetcher) usando stubs canned y
expone la lógica de scoring G1/G2 + score multi-dimensional 0-100.

Decisiones explícitas:
- Stubs (no HTTP real) — cumplen el contrato ``FetcherPort`` (puerto + adapter
  hexagonal, ver ``ports.py``). El cableado de Bright Data / Playwright se
  difiere a sprints siguientes.
- Scoring sin ML — pesos hardcodeados con TODO de ADR cuando entren los
  embeddings (ADR-024 / ADR-042).

Exports públicos:
- ``MatchService`` — orquestador SKU → candidatos persistidos.
- ``QueryBuilder`` — Etapa 1, traduce SKU a queries multi-fuente.
- ``compute_scoring`` / ``compute_g1_target`` / ``compute_g2_target`` —
  helpers puros del scorer (G1 mediana × 1.10, G2 coste × multiplicador).
- ``FetcherPort`` — protocolo para adapters de scraping.
"""

from __future__ import annotations

from app.services.matching.match_service import MatchService
from app.services.matching.ports import CandidateRaw, FetcherPort, Query
from app.services.matching.query_builder import QueryBuilder, build_queries
from app.services.matching.scoring import (
    DEFAULT_WEIGHTS,
    SCORING_WEIGHTS,
    ScoringBreakdown,
    compute_g1_target,
    compute_g2_target,
    compute_scoring,
)

__all__ = [
    "CandidateRaw",
    "DEFAULT_WEIGHTS",
    "FetcherPort",
    "MatchService",
    "Query",
    "QueryBuilder",
    "SCORING_WEIGHTS",
    "ScoringBreakdown",
    "build_queries",
    "compute_g1_target",
    "compute_g2_target",
    "compute_scoring",
]
