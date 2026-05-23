from __future__ import annotations
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.services.matching.rule_engine_cache import RuleEngineCache


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_profile_returns_db_weights(mock_session):
    """Cache retorna pesos desde DB para familia conocida."""
    profile = MagicMock()
    profile.family = "ball_valve"
    profile.weights = {"material": 0.17, "pn": 0.11, "dn": 0.17}
    profile.hard_blockers = ["dn_mismatch"]

    cache = RuleEngineCache(ttl_seconds=300)
    cache._profiles = {"ball_valve": profile}
    cache._loaded_at = time.monotonic()

    result = cache.get_profile("ball_valve")
    assert result is not None
    assert result.weights["material"] == 0.17


@pytest.mark.asyncio
async def test_cache_expired_triggers_reload(mock_session):
    """Cache expirado llama a reload."""
    cache = RuleEngineCache(ttl_seconds=1)
    cache._loaded_at = time.monotonic() - 2  # expirado
    cache._profiles = {}

    with pytest.raises(Exception):
        # Sin session real, espera fallo de DB — lo que prueba que intentó recargar
        await cache.ensure_loaded(mock_session)


@pytest.mark.asyncio
async def test_get_config_value_returns_default_on_miss(mock_session):
    """get_config_value retorna default si key no existe en cache."""
    cache = RuleEngineCache(ttl_seconds=300)
    cache._config = {}
    cache._loaded_at = time.monotonic()

    result = cache.get_config_value("nonexistent_key", default=42)
    assert result == 42
