"""Tests para TranslationCompletionService."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.translations.completion_service import TranslationCompletionService


@pytest.mark.asyncio
async def test_complete_calls_llm_and_returns_completed_count():
    session = AsyncMock()
    actor_id = uuid4()

    # Mock DB: 1 product with English name in product_translations
    mock_row = MagicMock()
    mock_row.sku = "MT-001"
    mock_row.name = "Ball valve DN25"
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [(mock_row,)]
    session.execute = AsyncMock(return_value=mock_scalars)

    llm_response = json.dumps([
        {"sku": "MT-001", "lang": "fr", "name": "Robinet à bille DN25"}
    ])

    with patch("app.services.translations.completion_service.anthropic") as mock_anthropic, \
         patch("app.services.translations.completion_service.TranslationWriter") as MockTW:

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=llm_response)]
        mock_client.messages.create.return_value = mock_msg

        mock_tw_instance = MagicMock()
        mock_tw_instance.write = AsyncMock()
        MockTW.return_value = mock_tw_instance

        service = TranslationCompletionService(session)
        result = await service.complete(
            skus=["MT-001"],
            target_langs=["fr"],
            source_lang="en",
            actor_id=actor_id,
        )

    assert result.completed == 1
    assert result.errors == 0


@pytest.mark.asyncio
async def test_complete_returns_zero_when_no_source_names():
    """If no source translations exist in DB, returns completed=0."""
    session = AsyncMock()
    # DB returns empty
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    session.execute = AsyncMock(return_value=mock_scalars)

    with patch("app.services.translations.completion_service.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[]")]
        mock_client.messages.create.return_value = mock_msg

        service = TranslationCompletionService(session)
        result = await service.complete(
            skus=["MT-001"],
            target_langs=["fr"],
            source_lang="en",
            actor_id=uuid4(),
        )

    assert result.completed == 0
    assert result.errors == 0


@pytest.mark.asyncio
async def test_complete_empty_skus_returns_zero():
    session = AsyncMock()
    service = TranslationCompletionService(session)
    result = await service.complete(
        skus=[], target_langs=["fr"], source_lang="en", actor_id=uuid4()
    )
    assert result.completed == 0
    assert result.errors == 0
    session.execute.assert_not_called()
