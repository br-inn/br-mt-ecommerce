"""Tests del :class:`ComparatorServiceFactory` (ADR-012 / US-RND-01-11).

Cubre:
  AC-1: ComparatorServiceFactory devuelve RagOnlyComparatorAdapter cuando el
        flag está ON y COMPARATOR_ADAPTER=rag_only (default).
  AC-3: Swap de adapter vía COMPARATOR_ADAPTER sin cambiar API.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.comparator import (
    FLAG_COMPARATOR_ENABLED,
    ComparatorServiceFactory,
    FullGraphRagComparatorAdapter,
    HybridComparatorAdapter,
    NoopComparatorService,
    RagOnlyComparatorAdapter,
)
from app.services.comparator.interfaces import ComparatorPort
from app.services.feature_flags.flag_service import (
    clear_local_cache,
    get_default_service,
    set_default_service,
    set_local_flag,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_flags() -> None:
    # FlagService needs _default_service != None for is_enabled() to read
    # _local_cache. Use a minimal mock so set_local_flag works end-to-end.
    prev = get_default_service()
    from unittest.mock import MagicMock
    set_default_service(MagicMock())
    clear_local_cache()
    yield
    clear_local_cache()
    set_default_service(prev)


# ---------------------------------------------------------------------------
# Flag OFF → Noop (backward compat)
# ---------------------------------------------------------------------------

def test_factory_returns_noop_when_flag_off() -> None:
    """Default: flag OFF (sin bootstrap) → stub."""
    instance = ComparatorServiceFactory.create()
    assert isinstance(instance, NoopComparatorService)


def test_factory_returns_noop_when_flag_explicitly_false() -> None:
    set_local_flag(FLAG_COMPARATOR_ENABLED, False)
    instance = ComparatorServiceFactory.create()
    assert isinstance(instance, NoopComparatorService)


# ---------------------------------------------------------------------------
# AC-1 — flag ON + COMPARATOR_ADAPTER=rag_only → RagOnlyComparatorAdapter
# ---------------------------------------------------------------------------

def test_factory_returns_rag_only_when_flag_on_and_adapter_rag_only() -> None:
    """AC-1: flag ON + rag_only → RagOnlyComparatorAdapter (Fase 1 activo)."""
    set_local_flag(FLAG_COMPARATOR_ENABLED, True)
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.COMPARATOR_ADAPTER = "rag_only"
        instance = ComparatorServiceFactory.create()
    assert isinstance(instance, RagOnlyComparatorAdapter)


# ---------------------------------------------------------------------------
# AC-3 — swap via COMPARATOR_ADAPTER
# ---------------------------------------------------------------------------

def test_factory_returns_hybrid_when_adapter_hybrid() -> None:
    """AC-3: COMPARATOR_ADAPTER=hybrid → HybridComparatorAdapter (stub Fase 2)."""
    set_local_flag(FLAG_COMPARATOR_ENABLED, True)
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.COMPARATOR_ADAPTER = "hybrid"
        instance = ComparatorServiceFactory.create()
    assert isinstance(instance, HybridComparatorAdapter)


def test_factory_returns_full_graph_rag_when_adapter_full_graph_rag() -> None:
    """AC-3: COMPARATOR_ADAPTER=full_graph_rag → FullGraphRagComparatorAdapter."""
    set_local_flag(FLAG_COMPARATOR_ENABLED, True)
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.COMPARATOR_ADAPTER = "full_graph_rag"
        instance = ComparatorServiceFactory.create()
    assert isinstance(instance, FullGraphRagComparatorAdapter)


def test_factory_falls_back_to_rag_only_for_unknown_adapter() -> None:
    """Valor desconocido en COMPARATOR_ADAPTER → fallback seguro a rag_only."""
    set_local_flag(FLAG_COMPARATOR_ENABLED, True)
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.COMPARATOR_ADAPTER = "unknown_future_adapter"
        instance = ComparatorServiceFactory.create()
    assert isinstance(instance, RagOnlyComparatorAdapter)


# ---------------------------------------------------------------------------
# Port compatibility — backward compat
# ---------------------------------------------------------------------------

def test_factory_each_call_returns_comparator_port_instance() -> None:
    """Cada call devuelve una instancia que satisface ComparatorPort."""
    a = ComparatorServiceFactory.create()
    b = ComparatorServiceFactory.create()
    assert isinstance(a, ComparatorPort)
    assert isinstance(b, ComparatorPort)
