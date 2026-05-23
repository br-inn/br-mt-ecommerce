"""Tests unitarios — AmazonSPFetcherStub + get_fetcher() — US-F15-02-01."""

from __future__ import annotations

import pytest

from app.services.comparator.fetchers import CompetitorPrice, FetcherPort
from app.services.comparator.fetchers.amazon_sp_fetcher_stub import AmazonSPFetcherStub


# ---------------------------------------------------------------------------
# Stub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_returns_competitor_price() -> None:
    """Stub retorna CompetitorPrice con datos sintéticos."""
    stub = AmazonSPFetcherStub()
    result = await stub.fetch_competitor_price("B08N5WRWNW")

    assert isinstance(result, CompetitorPrice)
    assert result.asin == "B08N5WRWNW"
    assert 10.0 <= result.price_aed <= 1000.0
    assert result.currency == "AED"
    assert result.marketplace_id == "A2VIGQ35RCS4UG"
    assert result.source == "stub"


@pytest.mark.asyncio
async def test_stub_price_is_deterministic() -> None:
    """Mismo ASIN → mismo precio en llamadas distintas."""
    stub = AmazonSPFetcherStub()
    r1 = await stub.fetch_competitor_price("B08N5WRWNW")
    r2 = await stub.fetch_competitor_price("B08N5WRWNW")
    assert r1.price_aed == r2.price_aed


@pytest.mark.asyncio
async def test_stub_different_asins_give_different_prices() -> None:
    """ASINs distintos dan precios distintos (con alta probabilidad)."""
    stub = AmazonSPFetcherStub()
    r1 = await stub.fetch_competitor_price("B08N5WRWNW")
    r2 = await stub.fetch_competitor_price("B09G9HD6PD")
    # Dos ASINs aleatorios deben tener precios distintos salvo colisión de hash
    assert r1.price_aed != r2.price_aed


@pytest.mark.asyncio
async def test_stub_health_check() -> None:
    """Stub health_check retorna healthy True."""
    stub = AmazonSPFetcherStub()
    result = await stub.health_check()
    assert result == {"healthy": True, "source": "stub"}


def test_stub_implements_fetcher_port() -> None:
    """AmazonSPFetcherStub satisface el protocolo FetcherPort."""
    stub = AmazonSPFetcherStub()
    assert isinstance(stub, FetcherPort)


# ---------------------------------------------------------------------------
# Fallback: MT_LIVE_NETWORK=false → usa stub automáticamente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_adapter_fallback_when_live_network_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con MT_LIVE_NETWORK=false, AmazonSPApiFetcherAdapter usa stub sin llamadas HTTP."""
    from app.core.config import settings
    from app.services.comparator.fetchers.amazon_sp_fetcher import AmazonSPApiFetcherAdapter

    monkeypatch.setattr(settings, "MT_LIVE_NETWORK", "false")

    adapter = AmazonSPApiFetcherAdapter()
    result = await adapter.fetch_competitor_price("B08N5WRWNW")

    # Debe ser resultado del stub (source="stub")
    assert result.source == "stub"
    assert isinstance(result, CompetitorPrice)


@pytest.mark.asyncio
async def test_real_adapter_fallback_when_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con MT_LIVE_NETWORK=true pero sin credenciales, cae a stub."""
    from app.core.config import settings
    from app.services.comparator.fetchers.amazon_sp_fetcher import AmazonSPApiFetcherAdapter
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "MT_LIVE_NETWORK", "true")
    monkeypatch.setattr(settings, "SP_API_REFRESH_TOKEN", "")
    monkeypatch.setattr(settings, "SP_API_LWA_CLIENT_ID", "")
    monkeypatch.setattr(settings, "SP_API_LWA_CLIENT_SECRET", SecretStr(""))

    adapter = AmazonSPApiFetcherAdapter()
    result = await adapter.fetch_competitor_price("B08N5WRWNW")

    assert result.source == "stub"


# ---------------------------------------------------------------------------
# get_fetcher() factory
# ---------------------------------------------------------------------------


def test_get_fetcher_returns_stub_when_live_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_fetcher() retorna AmazonSPFetcherStub cuando MT_LIVE_NETWORK != 'true'."""
    from app.core.config import settings
    from app.services.comparator.fetchers.amazon_sp_fetcher import get_fetcher

    monkeypatch.setattr(settings, "MT_LIVE_NETWORK", "false")

    fetcher = get_fetcher()
    assert isinstance(fetcher, AmazonSPFetcherStub)


def test_get_fetcher_returns_adapter_when_live_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_fetcher() retorna AmazonSPApiFetcherAdapter cuando MT_LIVE_NETWORK='true'."""
    from app.core.config import settings
    from app.services.comparator.fetchers.amazon_sp_fetcher import (
        AmazonSPApiFetcherAdapter,
        get_fetcher,
    )

    monkeypatch.setattr(settings, "MT_LIVE_NETWORK", "true")

    fetcher = get_fetcher()
    assert isinstance(fetcher, AmazonSPApiFetcherAdapter)


def test_get_fetcher_result_implements_fetcher_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_fetcher() siempre retorna algo que cumple FetcherPort."""
    from app.core.config import settings
    from app.services.comparator.fetchers.amazon_sp_fetcher import get_fetcher

    monkeypatch.setattr(settings, "MT_LIVE_NETWORK", "false")

    fetcher = get_fetcher()
    assert isinstance(fetcher, FetcherPort)


# ---------------------------------------------------------------------------
# health_check del adapter real (fallback a stub_fallback sin credenciales)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_adapter_health_check_no_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """health_check retorna healthy True aunque sin live network."""
    from app.core.config import settings
    from app.services.comparator.fetchers.amazon_sp_fetcher import AmazonSPApiFetcherAdapter

    monkeypatch.setattr(settings, "MT_LIVE_NETWORK", "false")

    adapter = AmazonSPApiFetcherAdapter()
    result = await adapter.health_check()

    assert result["healthy"] is True
    assert result["source"] == "stub_fallback"
    assert result["live_network"] is False
