"""Unit tests for AmazonListingGenerator — Anthropic SDK mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.marketplace_export.listing_generator import (
    _DEFAULT_MODEL,
    AmazonListingGenerator,
    GeneratedListingContent,
)


def _mock_claude_response(content: dict) -> MagicMock:
    """Build a mock Anthropic API response with tool_use content."""
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.input = content

    message = MagicMock()
    message.content = [tool_use]
    message.stop_reason = "tool_use"
    return message


def _make_product_context() -> dict:
    return {
        "sku": "4097015",
        "dn": '1/2"',
        "material": "Brass CW617N",
        "connection_type": "Threaded BSP",
        "pressure_rating": 30,
        "temp_min": -20,
        "temp_max": 120,
        "certifications": ["CE", "ACS"],
        "family": "ball_valve",
        "description_en": "Long neck ball valve PN30 threaded ends.",
    }


@pytest.mark.asyncio
async def test_generate_returns_structured_content():
    mock_response = _mock_claude_response({
        "listing_title": "MT Valves PN30 Ball Valve 1/2 Brass",
        "listing_description": "Long neck ball valve threaded BSP.",
        "bullet_points": [
            "PN30 pressure rated",
            "Brass CW617N body",
            "BSP threaded",
            "Temp -20°C to 120°C",
            "CE and ACS certified",
        ],
        "search_keywords": "ball valve brass PN30 BSP 1/2",
    })

    with patch(
        "app.services.marketplace_export.listing_generator.anthropic.AsyncAnthropic"
    ) as MockClient:
        client_instance = AsyncMock()
        client_instance.messages.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = client_instance

        generator = AmazonListingGenerator()
        result = await generator.generate(_make_product_context())

    assert isinstance(result, GeneratedListingContent)
    assert result.listing_title == "MT Valves PN30 Ball Valve 1/2 Brass"
    assert len(result.bullet_points) == 5
    assert result.search_keywords == "ball valve brass PN30 BSP 1/2"
    assert result.ai_model == _DEFAULT_MODEL


@pytest.mark.asyncio
async def test_generate_raises_on_non_tool_use_response():
    bad_response = MagicMock()
    bad_response.stop_reason = "end_turn"
    bad_response.content = []

    with patch(
        "app.services.marketplace_export.listing_generator.anthropic.AsyncAnthropic"
    ) as MockClient:
        client_instance = AsyncMock()
        client_instance.messages.create = AsyncMock(return_value=bad_response)
        MockClient.return_value = client_instance

        generator = AmazonListingGenerator()
        with pytest.raises(ValueError, match="did not return tool_use"):
            await generator.generate(_make_product_context())
