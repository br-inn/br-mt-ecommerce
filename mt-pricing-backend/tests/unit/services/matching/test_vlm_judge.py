"""Tests para VLMJudge + adapters OpenAI / Anthropic (Sprint 4 SCAFFOLD).

Sin red real — los clientes LLM se inyectan mock y se usa httpx.MockTransport
para los adapters concretos.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.matching.vlm_judge import (
    AnthropicVisionJudge,
    JudgeResult,
    OpenAIVisionJudge,
    VLMJudge,
    parse_judge_response,
)

pytestmark = pytest.mark.unit


# ----------------------------- parser --------------------------------- #


def test_parse_judge_response_handles_pure_json() -> None:
    txt = '{"verdict":"match","confidence":0.92,"reasoning":"mismo material y rosca"}'
    r = parse_judge_response(txt)
    assert r.verdict == "match"
    assert r.confidence == 0.92
    assert "rosca" in r.reasoning


def test_parse_judge_response_extracts_json_from_noisy_text() -> None:
    txt = 'Sure, here is the verdict: {"verdict":"reject","confidence":0.1,"reasoning":"diff brand"} thanks!'
    r = parse_judge_response(txt)
    assert r.verdict == "reject"


def test_parse_judge_response_clamps_confidence_to_unit_range() -> None:
    r = parse_judge_response('{"verdict":"match","confidence":2.5,"reasoning":""}')
    assert r.confidence == 1.0
    r2 = parse_judge_response('{"verdict":"match","confidence":-1,"reasoning":""}')
    assert r2.confidence == 0.0


def test_parse_judge_response_falls_back_on_invalid_json() -> None:
    r = parse_judge_response("not a json at all")
    assert r.verdict == "uncertain"
    assert r.confidence == 0.5


def test_parse_judge_response_invalid_verdict_becomes_uncertain() -> None:
    r = parse_judge_response('{"verdict":"weird","confidence":0.9,"reasoning":"x"}')
    assert r.verdict == "uncertain"


# ----------------------------- VLMJudge service ------------------------ #


async def test_judge_returns_uncertain_when_live_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    judge = VLMJudge()
    r = await judge.judge(canonical_image_url="a", candidate_image_url="b")
    assert r.verdict == "uncertain"
    assert r.confidence == 0.5


async def test_judge_returns_uncertain_when_no_provider_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    judge = VLMJudge()
    r = await judge.judge(canonical_image_url="a", candidate_image_url="b")
    assert r.verdict == "uncertain"


async def test_judge_uses_injected_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")

    class _Stub:
        async def judge(
            self, *, canonical_image_url: str, candidate_image_url: str, context: str | None = None
        ) -> JudgeResult:
            return JudgeResult(verdict="match", confidence=0.95, reasoning="ok")

    judge = VLMJudge(client=_Stub())
    r = await judge.judge(canonical_image_url="a", candidate_image_url="b")
    assert r.verdict == "match"
    assert r.confidence == 0.95


async def test_judge_returns_uncertain_when_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")

    class _Broken:
        async def judge(self, **_: object) -> JudgeResult:
            raise httpx.ConnectError("boom")

    judge = VLMJudge(client=_Broken())
    r = await judge.judge(canonical_image_url="a", candidate_image_url="b")
    assert r.verdict == "uncertain"
    assert "ConnectError" in r.reasoning


# ------------------------- OpenAIVisionJudge -------------------------- #


async def test_openai_vision_judge_calls_api_and_parses() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"verdict":"match","confidence":0.88,'
                                '"reasoning":"mismo brand y rosca"}'
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    j = OpenAIVisionJudge(api_key="key", http_client=client)
    r = await j.judge(canonical_image_url="https://x/a", candidate_image_url="https://x/b")
    await client.aclose()
    assert r.verdict == "match"
    assert r.confidence == 0.88


async def test_anthropic_vision_judge_calls_api_and_parses() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": '{"verdict":"drift","confidence":0.7,"reasoning":"PN diferente"}',
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    j = AnthropicVisionJudge(api_key="key", http_client=client)
    r = await j.judge(canonical_image_url="https://x/a", candidate_image_url="https://x/b")
    await client.aclose()
    assert r.verdict == "drift"
    assert r.confidence == 0.7
