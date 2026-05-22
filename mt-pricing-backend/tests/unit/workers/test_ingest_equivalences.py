"""Tests para ingest_equivalences_from_pdf — US-F15-01-05.

Estrategia:
- use_fixture=True: no necesita PDF real ni Neo4j.
- Patchea get_default_graph_store para inyectar un MagicMock.
- Verifica conteo de merge_node y merge_edge calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_PATCH_TARGET = "app.workers.tasks.graphrag.get_default_graph_store"


def _make_mock_graph() -> MagicMock:
    return MagicMock()


def test_fixture_mode_syncs_edges() -> None:
    """use_fixture=True procesa 5 pares sin leer PDF."""
    mock_graph = _make_mock_graph()
    with patch(_PATCH_TARGET, return_value=mock_graph):
        from app.workers.tasks.graphrag import _ingest_equivalences

        result = asyncio.run(_ingest_equivalences(pdf_path="dummy.pdf", use_fixture=True))

    assert result["pairs_found"] == 5
    assert result["synced"] == 5
    assert mock_graph.merge_edge.call_count == 5


def test_fixture_mode_merges_nodes() -> None:
    """Cada par hace MERGE de 2 nodos Product (5 pares × 2 = 10 calls)."""
    mock_graph = _make_mock_graph()
    with patch(_PATCH_TARGET, return_value=mock_graph):
        from app.workers.tasks.graphrag import _ingest_equivalences

        asyncio.run(_ingest_equivalences(pdf_path="dummy.pdf", use_fixture=True))

    assert mock_graph.merge_node.call_count == 10


def test_ingest_idempotent_fixture() -> None:
    """Segunda ejecución con fixture devuelve misma cantidad de edges (MERGE idempotente)."""
    mock_graph = _make_mock_graph()
    with patch(_PATCH_TARGET, return_value=mock_graph):
        from app.workers.tasks.graphrag import _ingest_equivalences

        asyncio.run(_ingest_equivalences(pdf_path="dummy.pdf", use_fixture=True))
        asyncio.run(_ingest_equivalences(pdf_path="dummy.pdf", use_fixture=True))

    assert mock_graph.merge_edge.call_count == 10  # 5 + 5
    assert mock_graph.merge_node.call_count == 20  # 10 + 10


def test_fixture_edge_type_is_equivalent_to() -> None:
    """Todos los edges tienen type EQUIVALENT_TO."""
    mock_graph = _make_mock_graph()
    with patch(_PATCH_TARGET, return_value=mock_graph):
        from app.workers.tasks.graphrag import _ingest_equivalences

        asyncio.run(_ingest_equivalences(pdf_path="dummy.pdf", use_fixture=True))

    for call in mock_graph.merge_edge.call_args_list:
        edge = call.args[0]
        assert edge.type == "EQUIVALENT_TO"


def test_fixture_result_pdf_path() -> None:
    """El resultado incluye el pdf_path original."""
    mock_graph = _make_mock_graph()
    with patch(_PATCH_TARGET, return_value=mock_graph):
        from app.workers.tasks.graphrag import _ingest_equivalences

        result = asyncio.run(_ingest_equivalences(pdf_path="my_catalog.pdf", use_fixture=True))

    assert result["pdf_path"] == "my_catalog.pdf"


def test_celery_task_returns_dict(celery_app_eager: object) -> None:
    """La task Celery devuelve el dict de resultado (modo eager)."""
    mock_graph = _make_mock_graph()
    with patch(_PATCH_TARGET, return_value=mock_graph):
        from app.workers.tasks.graphrag import ingest_equivalences_from_pdf

        result = ingest_equivalences_from_pdf.apply(
            kwargs={"pdf_path": "dummy.pdf", "use_fixture": True}
        ).get()

    assert result["pairs_found"] == 5
    assert result["synced"] == 5


def test_pdf_extraction_returns_pairs(sample_equivalences_pdf: object) -> None:
    """_extract_from_pdf parsea el PDF de fixture y encuentra al menos 2 pares."""
    from app.workers.tasks.graphrag import _extract_from_pdf

    pairs = _extract_from_pdf(str(sample_equivalences_pdf))
    # El PDF contiene: MT-VALVE-001 = MT-VALVE-002 y MT-PUMP-100 equiv. MT-PUMP-101
    assert len(pairs) >= 2
    skus = {(p[0], p[1]) for p in pairs}
    assert ("MT-VALVE-001", "MT-VALVE-002") in skus or ("MT-PUMP-100", "MT-PUMP-101") in skus
