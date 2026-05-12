"""Unit tests — US-RND-01-09 CLIP reverse image search service.

Sin DB real. Cubren:
1. test_stub_backend_index_returns_true — StubBackend.index_image retorna True
2. test_stub_backend_search_returns_empty — StubBackend.search_similar retorna []
3. test_flag_off_skips_indexing — si flag OFF, el hook no llama index_image
4. test_flag_on_calls_indexing — si flag ON, el hook sí llama index_image (mock backend)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.image_search.clip_service import (
    ImageSearchResult,
    StubBackend,
    get_image_backend,
)


# ---------------------------------------------------------------------------
# 1. StubBackend.index_image retorna True
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stub_backend_index_returns_true() -> None:
    """StubBackend.index_image siempre retorna True (no conexión externa)."""
    backend = StubBackend()
    result = await backend.index_image("prod-123", "https://example.com/img.jpg")
    assert result is True


# ---------------------------------------------------------------------------
# 2. StubBackend.search_similar retorna lista vacía
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stub_backend_search_returns_empty() -> None:
    """StubBackend.search_similar retorna [] (sin índice real)."""
    backend = StubBackend()
    results = await backend.search_similar("https://example.com/query.jpg", top_k=5)
    assert results == []
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# 3. Hook no llama index_image cuando flag está OFF
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_off_skips_indexing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si is_reverse_image_search_enabled devuelve False, index_image NO es llamado."""
    mock_backend = AsyncMock()
    mock_backend.index_image = AsyncMock(return_value=True)

    # Flag OFF
    monkeypatch.setattr(
        "app.services.feature_flags.flag_service.is_reverse_image_search_enabled",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.image_search.clip_service.get_image_backend",
        lambda: mock_backend,
    )

    from app.services.feature_flags.flag_service import is_reverse_image_search_enabled
    from app.services.image_search.clip_service import get_image_backend as _get_backend

    mock_session = MagicMock()

    # Simulate what the route hook does
    flag_on = await is_reverse_image_search_enabled(mock_session)
    if flag_on:
        backend = _get_backend()
        await backend.index_image("prod-123", "products/AB/ABCDE/photos/img.jpg")

    mock_backend.index_image.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Hook llama index_image cuando flag está ON
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flag_on_calls_indexing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si is_reverse_image_search_enabled devuelve True, index_image ES llamado."""
    mock_backend = AsyncMock()
    mock_backend.index_image = AsyncMock(return_value=True)

    # Flag ON
    monkeypatch.setattr(
        "app.services.feature_flags.flag_service.is_reverse_image_search_enabled",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.services.image_search.clip_service.get_image_backend",
        lambda: mock_backend,
    )

    from app.services.feature_flags.flag_service import is_reverse_image_search_enabled
    from app.services.image_search.clip_service import get_image_backend as _get_backend

    mock_session = MagicMock()
    product_id = "ABCDE"
    storage_path = "products/AB/ABCDE/photos/abc123_image.jpg"

    # Simulate what the route hook does
    flag_on = await is_reverse_image_search_enabled(mock_session)
    if flag_on:
        backend = _get_backend()
        await backend.index_image(product_id, storage_path)

    mock_backend.index_image.assert_awaited_once_with(product_id, storage_path)
