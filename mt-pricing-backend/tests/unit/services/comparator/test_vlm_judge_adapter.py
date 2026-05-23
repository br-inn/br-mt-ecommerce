"""Tests unitarios para ClaudeVlmJudgeAdapter y NoopVlmJudgeAdapter (US-F15-02-02, AC#9).

Cubre:
  T10.3 — JSON válido → veredicto correcto
  T10.4 — JSON inválido → fallback uncertain/0.0
  T10.5 — uncertain + confidence < 0.50 → enqueue llamado con reason='vlm_uncertain'
  T10.6 — VLM_JUDGE_ENABLED=false → NoopVlmJudgeAdapter sin llamada HTTP

anthropic y aiolimiter se mockean a nivel sys.modules para que los tests
funcionen sin instalar las dependencias en el entorno de pruebas.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pre-mock anthropic y aiolimiter ANTES de cualquier import del módulo bajo test
# ---------------------------------------------------------------------------
_mock_anthropic = MagicMock()
_mock_aiolimiter = MagicMock()
_rate_limiter_instance = MagicMock()
_rate_limiter_instance.__aenter__ = AsyncMock(return_value=None)
_rate_limiter_instance.__aexit__ = AsyncMock(return_value=False)
_mock_aiolimiter.AsyncLimiter.return_value = _rate_limiter_instance

sys.modules["anthropic"] = _mock_anthropic
sys.modules["aiolimiter"] = _mock_aiolimiter

from app.services.comparator.interfaces import VlmJudgeVerdict
from app.services.comparator.vlm_judge_stub import NoopVlmJudgeAdapter

pytestmark = pytest.mark.unit

_CTX: dict[str, Any] = {"dn": '2"', "pn": "PN-001", "material": "SS316"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client_mock(text_content: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text_content
    response = MagicMock()
    response.content = [content_block]
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# T10.3 — JSON válido → veredicto correcto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_json_returns_correct_verdict() -> None:
    valid_json = (
        '{"verdict":"match","confidence":0.92,"reasoning":"Mismas dimensiones y PN",'
        '"deal_breakers_triggered":[],"image_regions":[]}'
    )
    client_mock = _make_client_mock(valid_json)
    _mock_anthropic.AsyncAnthropic.return_value = client_mock

    from app.services.comparator.vlm_judge_adapter import ClaudeVlmJudgeAdapter

    adapter = ClaudeVlmJudgeAdapter(api_key="test-key")
    verdict = await adapter.judge(
        product_sku="SKU-001",
        candidate_image_url="https://cdn.example.com/cand.jpg",
        product_image_url="https://cdn.example.com/prod.jpg",
        context=_CTX,
    )

    assert verdict.decision == "match"
    assert abs(verdict.confidence - 0.92) < 0.001
    assert "Mismas" in verdict.rationale
    assert verdict.deal_breakers_triggered == ()


# ---------------------------------------------------------------------------
# T10.4 — JSON inválido → fallback uncertain/0.0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_json_returns_uncertain_fallback() -> None:
    bad_text = "Lo siento, no puedo analizar las imágenes."
    client_mock = _make_client_mock(bad_text)
    _mock_anthropic.AsyncAnthropic.return_value = client_mock

    from app.services.comparator.vlm_judge_adapter import ClaudeVlmJudgeAdapter

    adapter = ClaudeVlmJudgeAdapter(api_key="test-key")
    verdict = await adapter.judge(
        product_sku="SKU-002",
        candidate_image_url="https://cdn.example.com/cand.jpg",
        product_image_url="https://cdn.example.com/prod.jpg",
        context=_CTX,
    )

    assert verdict.decision == "uncertain"
    assert verdict.confidence == 0.0


# ---------------------------------------------------------------------------
# T10.5 — uncertain + confidence < 0.50 → enqueue llamado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uncertain_low_confidence_enqueues_to_human_queue() -> None:
    from uuid import uuid4

    from app.services.comparator.adapters import RagOnlyComparatorAdapter

    # Mock de session: execute devuelve result con scalar_one_or_none=None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session_mock = MagicMock()
    session_mock.execute = AsyncMock(return_value=mock_result)
    session_mock.add = MagicMock()
    session_mock.flush = AsyncMock(return_value=None)

    enqueue_mock = AsyncMock(return_value=1)

    listing_id = uuid4()
    decided_by = uuid4()
    evidence: dict[str, Any] = {
        "vlm": {
            "verdict": "uncertain",
            "confidence": 0.30,
            "rationale": "No se puede determinar",
            "deal_breakers_triggered": [],
            "image_regions": [],
            "model_version": "claude-sonnet-4-6",
        }
    }

    # HumanQueueService se importa lazy dentro de confirm_match — parcheamos
    # el módulo de origen para que el import dentro de la función use el mock.
    with patch(
        "app.services.matching.human_queue_service.HumanQueueService.enqueue_vlm_uncertain",
        enqueue_mock,
    ):
        adapter = RagOnlyComparatorAdapter(session=session_mock)
        await adapter.confirm_match(
            listing_id=listing_id,
            product_sku="SKU-003",
            decided_by=decided_by,
            evidence=evidence,
        )

    enqueue_mock.assert_awaited_once()
    kwargs = enqueue_mock.call_args.kwargs
    assert kwargs["product_sku"] == "SKU-003"
    assert kwargs["rationale"] == "No se puede determinar"


# ---------------------------------------------------------------------------
# T10.6 — NoopVlmJudgeAdapter → uncertain sin llamadas HTTP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_adapter_returns_uncertain_without_http_call() -> None:
    adapter = NoopVlmJudgeAdapter()
    verdict = await adapter.judge(
        product_sku="SKU-004",
        candidate_image_url="https://cdn.example.com/cand.jpg",
        product_image_url="https://cdn.example.com/prod.jpg",
        context=_CTX,
    )

    assert isinstance(verdict, VlmJudgeVerdict)
    assert verdict.decision == "uncertain"
    assert verdict.confidence == 0.0
    assert verdict.rationale == "vlm_disabled"


# ---------------------------------------------------------------------------
# T10.7 — response.content vacío → fallback uncertain/0.0 (F-16)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_response_content_returns_uncertain_fallback() -> None:
    """Cuando el modelo devuelve content=[], el adapter retorna uncertain/0.0."""
    response = MagicMock()
    response.content = []
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    _mock_anthropic.AsyncAnthropic.return_value = client

    from app.services.comparator.vlm_judge_adapter import ClaudeVlmJudgeAdapter

    adapter = ClaudeVlmJudgeAdapter(api_key="test-key")
    verdict = await adapter.judge(
        product_sku="SKU-007",
        candidate_image_url="https://cdn.example.com/cand.jpg",
        product_image_url="https://cdn.example.com/prod.jpg",
        context=_CTX,
    )

    assert verdict.decision == "uncertain"
    assert verdict.confidence == 0.0


# ---------------------------------------------------------------------------
# T10.8 — VlmJudgeFactory con ANTHROPIC_API_KEY vacío → NoopVlmJudgeAdapter (F-19)
# ---------------------------------------------------------------------------


def test_factory_returns_noop_when_api_key_empty() -> None:
    """VlmJudgeFactory devuelve Noop cuando ANTHROPIC_API_KEY está vacío (AC#9)."""
    from unittest.mock import patch

    from app.services.comparator.factory import VlmJudgeFactory
    from app.services.comparator.vlm_judge_stub import NoopVlmJudgeAdapter

    with (
        patch.object(VlmJudgeFactory, "_is_enabled", return_value=True),
        patch.object(VlmJudgeFactory, "_get_api_key", return_value=""),
    ):
        adapter = VlmJudgeFactory.create()

    assert isinstance(adapter, NoopVlmJudgeAdapter)
