"""Unit tests — US-1B-03-04 feature flag channel_recommendation.

Sin DB. Cubren:
- channel_recommendation presente en KNOWN_FLAGS.
- is_channel_recommendation_enabled retorna False si repo.get devuelve None.
- is_channel_recommendation_enabled retorna False si enabled=false en JSONB.
- is_channel_recommendation_enabled retorna True si enabled=true en JSONB.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.feature_flags.flag_service import (
    FLAG_CHANNEL_RECOMMENDATION,
    KNOWN_FLAGS,
    is_channel_recommendation_enabled,
)


# ---------------------------------------------------------------------------
# KNOWN_FLAGS presence
# ---------------------------------------------------------------------------
def test_channel_recommendation_in_known_flags() -> None:
    """channel_recommendation está en KNOWN_FLAGS."""
    assert "channel_recommendation" in KNOWN_FLAGS


def test_channel_recommendation_constant_value() -> None:
    """FLAG_CHANNEL_RECOMMENDATION es 'channel_recommendation'."""
    assert FLAG_CHANNEL_RECOMMENDATION == "channel_recommendation"


# ---------------------------------------------------------------------------
# is_channel_recommendation_enabled
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_is_channel_recommendation_disabled_when_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retorna False si no hay row en DB (repo.get returns None)."""
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=None)

    mock_repo_cls = MagicMock(return_value=mock_repo)
    # Patch at the repository source module (imported lazily inside helper)
    monkeypatch.setattr(
        "app.repositories.feature_flags.FeatureFlagRepository",
        mock_repo_cls,
    )

    mock_session = MagicMock()
    result = await is_channel_recommendation_enabled(mock_session)

    assert result is False
    mock_repo.get.assert_awaited_once_with("channel_recommendation")


@pytest.mark.asyncio
async def test_is_channel_recommendation_disabled_when_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retorna False si row.value_jsonb tiene enabled=false."""
    row = SimpleNamespace(value_jsonb={"enabled": False})
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=row)

    monkeypatch.setattr(
        "app.repositories.feature_flags.FeatureFlagRepository",
        MagicMock(return_value=mock_repo),
    )

    mock_session = MagicMock()
    result = await is_channel_recommendation_enabled(mock_session)

    assert result is False


@pytest.mark.asyncio
async def test_is_channel_recommendation_enabled_when_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retorna True si row.value_jsonb tiene enabled=true."""
    row = SimpleNamespace(value_jsonb={"enabled": True})
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=row)

    monkeypatch.setattr(
        "app.repositories.feature_flags.FeatureFlagRepository",
        MagicMock(return_value=mock_repo),
    )

    mock_session = MagicMock()
    result = await is_channel_recommendation_enabled(mock_session)

    assert result is True
