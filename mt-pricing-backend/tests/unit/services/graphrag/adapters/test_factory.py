"""Unit tests del factory de graph stores (`adapters/factory.py`).

Estrategia:

- No tocamos Neo4j real. Mockeamos ``GraphDatabase.driver`` y comprobamos:
    * Override (test fixtures) toma prioridad.
    * ``GRAPHRAG_BACKEND='stub'`` devuelve el singleton stub.
    * ``GRAPHRAG_BACKEND='neo4j'`` invoca el driver con settings y cachea
      el adapter.
    * ``shutdown()`` cierra el driver y permite re-inicializar.

Aislamiento:
- Reseteamos el state global del factory (`_override`, `_neo4j_driver`,
  `_neo4j_store`) al final de cada test via fixture autouse.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_factory_state() -> Iterator[None]:
    """Limpia singletons del factory entre tests para evitar leakage."""
    from app.services.graphrag.adapters import factory as f

    f._override = None
    f._neo4j_driver = None
    f._neo4j_store = None
    yield
    f._override = None
    f._neo4j_driver = None
    f._neo4j_store = None


# ---------------------------------------------------------------------------
# Override path
# ---------------------------------------------------------------------------
def test_set_default_graph_store_override_takes_priority() -> None:
    from app.services.graphrag.adapters import factory as f
    from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore

    custom = Neo4jStubGraphStore()
    f.set_default_graph_store(custom)
    assert f.get_default_graph_store() is custom


def test_set_default_graph_store_none_resets_override() -> None:
    from app.services.graphrag.adapters import factory as f
    from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore

    f.set_default_graph_store(Neo4jStubGraphStore())
    f.set_default_graph_store(None)
    # Sin override, settings por defecto = stub.
    from app.core.config import settings

    prev_backend = settings.GRAPHRAG_BACKEND
    settings.GRAPHRAG_BACKEND = "stub"
    try:
        store = f.get_default_graph_store()
        assert isinstance(store, Neo4jStubGraphStore)
    finally:
        settings.GRAPHRAG_BACKEND = prev_backend


# ---------------------------------------------------------------------------
# Stub backend
# ---------------------------------------------------------------------------
def test_get_default_returns_stub_when_backend_stub() -> None:
    from app.core.config import settings
    from app.services.graphrag.adapters import factory as f
    from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore

    prev = settings.GRAPHRAG_BACKEND
    settings.GRAPHRAG_BACKEND = "stub"
    try:
        store = f.get_default_graph_store()
        assert isinstance(store, Neo4jStubGraphStore)
    finally:
        settings.GRAPHRAG_BACKEND = prev


# ---------------------------------------------------------------------------
# Neo4j backend (driver mocked)
# ---------------------------------------------------------------------------
def test_get_default_initializes_neo4j_driver_with_settings() -> None:
    from app.core.config import settings
    from app.services.graphrag.adapters import factory as f

    prev_backend = settings.GRAPHRAG_BACKEND
    prev_uri = settings.NEO4J_URI
    settings.GRAPHRAG_BACKEND = "neo4j"
    settings.NEO4J_URI = "bolt://test-host:7687"
    fake_driver = MagicMock(name="neo4j_driver")

    try:
        with patch(
            "app.services.graphrag.adapters.factory.GraphDatabase",
            create=True,
        ) as mock_gd:
            # Lazy import en _build_neo4j_driver — patcheamos el módulo neo4j
            # antes de que el factory lo importe.
            with patch.dict(
                "sys.modules",
                {
                    "neo4j": MagicMock(
                        GraphDatabase=MagicMock(driver=MagicMock(return_value=fake_driver))
                    )
                },
            ):
                # Re-importar para obtener nuevo lazy import path:
                # en este caso el factory hace `from neo4j import GraphDatabase`
                # dentro de _build_neo4j_driver, así que el patch.dict basta.
                store = f.get_default_graph_store()
                assert store is not None
                # El driver fake debió ser usado en la construcción.
                assert f._neo4j_driver is fake_driver
                # Segunda llamada cachea (no re-construye).
                store2 = f.get_default_graph_store()
                assert store2 is store
    finally:
        settings.GRAPHRAG_BACKEND = prev_backend
        settings.NEO4J_URI = prev_uri


def test_shutdown_closes_driver_and_allows_reinit() -> None:
    from app.core.config import settings
    from app.services.graphrag.adapters import factory as f

    prev_backend = settings.GRAPHRAG_BACKEND
    settings.GRAPHRAG_BACKEND = "neo4j"
    fake_driver_1 = MagicMock(name="driver_1")
    fake_driver_2 = MagicMock(name="driver_2")

    try:
        with patch.dict(
            "sys.modules",
            {
                "neo4j": MagicMock(
                    GraphDatabase=MagicMock(
                        driver=MagicMock(side_effect=[fake_driver_1, fake_driver_2])
                    )
                )
            },
        ):
            f.get_default_graph_store()
            assert f._neo4j_driver is fake_driver_1

            f.shutdown()
            fake_driver_1.close.assert_called_once()
            assert f._neo4j_driver is None
            assert f._neo4j_store is None

            # Re-build con el segundo driver.
            f.get_default_graph_store()
            assert f._neo4j_driver is fake_driver_2
    finally:
        settings.GRAPHRAG_BACKEND = prev_backend


def test_shutdown_swallows_close_errors() -> None:
    """Driver.close() puede fallar — shutdown no debe propagar."""
    from app.services.graphrag.adapters import factory as f

    bad_driver = MagicMock()
    bad_driver.close.side_effect = RuntimeError("close failed")
    f._neo4j_driver = bad_driver
    f._neo4j_store = MagicMock()

    f.shutdown()  # no raise

    assert f._neo4j_driver is None
    assert f._neo4j_store is None


def test_shutdown_noop_when_driver_not_initialized() -> None:
    from app.services.graphrag.adapters import factory as f

    assert f._neo4j_driver is None
    f.shutdown()  # no raise
    assert f._neo4j_driver is None
