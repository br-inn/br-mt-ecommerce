"""Tests unitarios — TradelingAdapter + TradelingFetcherFactory — US-F15-02-05.

Usa respx para mockear httpx sin tocar la red real.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from app.services.comparator.fetchers.tradeling_adapter import (
    TradelingAdapter,
    TradelingAuthError,
    TradelingFetcherFactory,
    TradelingListing,
)

# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

_SEARCH_URL = "https://api.tradeling.com/v1/products/search"

_SAMPLE_ITEM = {
    "id": "TRD-12345",
    "title": "Wilo Pump 2-Stage 220V",
    "price": {"amount": "345.50", "currency": "AED"},
    "brand": {"name": "Wilo"},
    "seller": {"name": "Al Futtaim Industrial"},
    "url": "https://tradeling.com/products/TRD-12345",
    "images": [
        {"url": "https://cdn.tradeling.com/img/TRD-12345-1.jpg"},
        {"url": "https://cdn.tradeling.com/img/TRD-12345-2.jpg"},
    ],
}

_SAMPLE_RESPONSE = {"items": [_SAMPLE_ITEM]}


# ---------------------------------------------------------------------------
# AC#1 + AC#2: fetch exitoso normaliza respuesta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_success_normalizes_response() -> None:
    """Mock 200 con JSON válido → lista de TradelingListing correctamente normalizada."""
    respx.get(_SEARCH_URL).mock(return_value=Response(200, json=_SAMPLE_RESPONSE))

    adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
    results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert len(results) == 1
    listing = results[0]
    assert isinstance(listing, TradelingListing)
    assert listing.external_id == "TRD-12345"
    assert listing.title == "Wilo Pump 2-Stage 220V"
    assert listing.price == Decimal("345.50")
    assert listing.currency == "AED"
    assert listing.brand == "Wilo"
    assert listing.seller_name == "Al Futtaim Industrial"
    assert listing.product_url == "https://tradeling.com/products/TRD-12345"
    assert len(listing.image_urls) == 2
    assert listing.image_urls[0] == "https://cdn.tradeling.com/img/TRD-12345-1.jpg"
    assert listing.source == "tradeling"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_uses_name_field_when_title_missing() -> None:
    """Si 'title' no existe, usa 'name' del item."""
    item = {**_SAMPLE_ITEM, "name": "Wilo Pump Alt Name"}
    item.pop("title")
    respx.get(_SEARCH_URL).mock(return_value=Response(200, json={"items": [item]}))

    adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
    results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert results[0].title == "Wilo Pump Alt Name"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_empty_items_returns_empty_list() -> None:
    """Respuesta con items vacíos retorna lista vacía."""
    respx.get(_SEARCH_URL).mock(return_value=Response(200, json={"items": []}))

    adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
    results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert results == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_missing_optional_fields_use_defaults() -> None:
    """Campos opcionales ausentes usan valores por defecto seguros."""
    minimal_item = {"id": "TRD-MIN", "price": {"amount": "100"}}
    respx.get(_SEARCH_URL).mock(return_value=Response(200, json={"items": [minimal_item]}))

    adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
    results = await adapter.fetch(product_title="Any", category_id="cat1")

    listing = results[0]
    assert listing.external_id == "TRD-MIN"
    assert listing.title == ""
    assert listing.brand == ""
    assert listing.seller_name == ""
    assert listing.product_url == ""
    assert listing.image_urls == []
    assert listing.currency == "AED"


# ---------------------------------------------------------------------------
# AC#3: Rate limiting + retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_429_retries_and_succeeds() -> None:
    """Mock 429 → 429 → 200 → éxito (3 llamadas httpx en total)."""
    call_count = 0

    def side_effect(request: object) -> Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return Response(429, json={"error": "rate_limited"})
        return Response(200, json=_SAMPLE_RESPONSE)

    respx.get(_SEARCH_URL).mock(side_effect=side_effect)

    adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
    results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert call_count == 3
    assert len(results) == 1
    assert results[0].external_id == "TRD-12345"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_5xx_retries_and_succeeds() -> None:
    """Mock 503 → 503 → 200 → éxito (retry en 5xx igual que 429)."""
    call_count = 0

    def side_effect(request: object) -> Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return Response(503, json={"error": "service_unavailable"})
        return Response(200, json=_SAMPLE_RESPONSE)

    respx.get(_SEARCH_URL).mock(side_effect=side_effect)

    adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
    results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert call_count == 3
    assert len(results) == 1


@pytest.mark.asyncio
@respx.mock
async def test_fetch_exhausted_retries_returns_empty() -> None:
    """3 intentos fallidos consecutivos retorna [] (no lanza)."""
    respx.get(_SEARCH_URL).mock(return_value=Response(503, json={"error": "service_unavailable"}))

    with patch(
        "app.services.comparator.fetchers.tradeling_adapter._log_fetch_error",
        new_callable=AsyncMock,
    ):
        adapter = TradelingAdapter(api_key="test-key-abc", rate_limit=100.0)
        results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert results == []


# ---------------------------------------------------------------------------
# AC#3: HTTP 401/403 → TradelingAuthError sin retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_401_raises_auth_error() -> None:
    """Mock 401 → lanza TradelingAuthError inmediatamente (no retry)."""
    call_count = 0

    def side_effect(request: object) -> Response:
        nonlocal call_count
        call_count += 1
        return Response(401, json={"error": "unauthorized"})

    respx.get(_SEARCH_URL).mock(side_effect=side_effect)

    adapter = TradelingAdapter(api_key="bad-key", rate_limit=100.0)
    with pytest.raises(TradelingAuthError):
        await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    # Solo 1 intento — no retry en auth errors
    assert call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_fetch_403_raises_auth_error() -> None:
    """Mock 403 → lanza TradelingAuthError inmediatamente (no retry)."""
    call_count = 0

    def side_effect(request: object) -> Response:
        nonlocal call_count
        call_count += 1
        return Response(403, json={"error": "forbidden"})

    respx.get(_SEARCH_URL).mock(side_effect=side_effect)

    adapter = TradelingAdapter(api_key="bad-key", rate_limit=100.0)
    with pytest.raises(TradelingAuthError):
        await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert call_count == 1


# ---------------------------------------------------------------------------
# AC#3: Sin api_key → [] + no llamada httpx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_no_api_key_returns_empty() -> None:
    """api_key='' → retorna [], no llama httpx, emite WARNING."""
    # respx.mock sin rutas definidas — cualquier llamada HTTP fallaría
    adapter = TradelingAdapter(api_key="", rate_limit=100.0)

    results = await adapter.fetch(product_title="Wilo Pump", category_id="pumps")

    assert results == []
    # Verificar que no hubo llamadas HTTP (respx registra las llamadas)
    assert len(respx.calls) == 0


# ---------------------------------------------------------------------------
# AC#5: Factory
# ---------------------------------------------------------------------------


def test_factory_returns_none_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings sin TRADELING_API_KEY → factory retorna None."""
    from app.core.config import get_settings
    from pydantic import SecretStr

    mock_settings = MagicMock()
    mock_settings.TRADELING_API_KEY = SecretStr("")

    with patch(
        "app.services.comparator.fetchers.tradeling_adapter.get_settings",
        return_value=mock_settings,
    ):
        result = TradelingFetcherFactory.create()

    assert result is None


def test_factory_returns_adapter_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings con TRADELING_API_KEY válida → factory retorna TradelingAdapter."""
    from pydantic import SecretStr

    mock_settings = MagicMock()
    mock_settings.TRADELING_API_KEY = SecretStr("valid-api-key-abc123")

    with patch(
        "app.services.comparator.fetchers.tradeling_adapter.get_settings",
        return_value=mock_settings,
    ):
        result = TradelingFetcherFactory.create()

    assert isinstance(result, TradelingAdapter)


# ---------------------------------------------------------------------------
# Normalización: price siempre Decimal, nunca float
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_fetch_price_is_decimal_not_float() -> None:
    """El precio retornado es siempre Decimal, nunca float."""
    respx.get(_SEARCH_URL).mock(return_value=Response(200, json=_SAMPLE_RESPONSE))

    adapter = TradelingAdapter(api_key="test-key", rate_limit=100.0)
    results = await adapter.fetch(product_title="Test", category_id="cat")

    assert isinstance(results[0].price, Decimal)
    assert not isinstance(results[0].price, float)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_uses_results_key_as_fallback() -> None:
    """Respuesta con 'results' en lugar de 'items' también funciona."""
    respx.get(_SEARCH_URL).mock(return_value=Response(200, json={"results": [_SAMPLE_ITEM]}))

    adapter = TradelingAdapter(api_key="test-key", rate_limit=100.0)
    results = await adapter.fetch(product_title="Wilo", category_id="pumps")

    assert len(results) == 1
    assert results[0].source == "tradeling"
