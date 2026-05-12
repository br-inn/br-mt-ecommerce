"""Tests del :class:`ComparatorServiceFactory` (ADR-012 hooks Fase 1)."""

from __future__ import annotations

import pytest

from app.services.comparator import (
    FLAG_COMPARATOR_ENABLED,
    ComparatorServiceFactory,
    NoopComparatorService,
)
from app.services.feature_flags.flag_service import (
    clear_local_cache,
    set_local_flag,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_flags() -> None:
    clear_local_cache()
    yield
    clear_local_cache()


def test_factory_returns_noop_when_flag_off() -> None:
    """Default: flag OFF (sin bootstrap) → stub."""
    instance = ComparatorServiceFactory.create()
    assert isinstance(instance, NoopComparatorService)


def test_factory_returns_noop_when_flag_explicitly_false() -> None:
    set_local_flag(FLAG_COMPARATOR_ENABLED, False)
    instance = ComparatorServiceFactory.create()
    assert isinstance(instance, NoopComparatorService)


def test_factory_falls_back_to_noop_when_flag_on_but_no_real_impl() -> None:
    """Fase 1: incluso con flag ON, devuelve stub porque la implementación
    real ``ProductComparisonService`` aún no existe."""
    set_local_flag(FLAG_COMPARATOR_ENABLED, True)
    instance = ComparatorServiceFactory.create()
    # Fase 1: sigue siendo Noop hasta Fase 1.5+.
    assert isinstance(instance, NoopComparatorService)


def test_factory_each_call_returns_compatible_instance() -> None:
    """Cada call devuelve una instancia que satisface ComparatorPort."""
    from app.services.comparator.interfaces import ComparatorPort

    a = ComparatorServiceFactory.create()
    b = ComparatorServiceFactory.create()
    assert isinstance(a, ComparatorPort)
    assert isinstance(b, ComparatorPort)
