"""VLM Judge — visual matching scoring (Sprint 4 SCAFFOLD, US-1A-09-06).

Wraps un cliente LLM con vision (OpenAI / Anthropic / Gemini) detrás de
un Protocol mockeable. El servicio core sólo depende del Protocol — los
adapters concretos se registran via env (``VLM_JUDGE_PROVIDER``).

MODO INFRAESTRUCTURAL: la implementación ``OpenAIVisionJudge`` /
``AnthropicVisionJudge`` está cableada (httpx + retry + parser JSON
estricto) pero NO se ejecutan llamadas reales mientras
``MT_LIVE_NETWORK != true`` o no hay ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY``.
En esos casos el ``VLMJudge`` retorna un veredicto neutro
``uncertain`` con confidence 0.5 — el pipeline aguas abajo ya derivaba
estos casos al ``human_queue``.

Output schema (criterio US-1A-09-06):
    ``{verdict: 'match'|'drift'|'reject'|'uncertain', confidence: float in [0,1],
       reasoning: str}``

Pipeline ref: ``mt-product-matching-pipeline-detail.md`` §10.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

Verdict = Literal["match", "drift", "reject", "uncertain"]


@dataclass(frozen=True)
class JudgeResult:
    verdict: Verdict
    confidence: float
    reasoning: str
    raw: dict[str, Any] | None = None


class VLMClient(Protocol):
    """Cliente LLM con vision — contrato testable."""

    async def judge(
        self, *, canonical_image_url: str, candidate_image_url: str, context: str | None = None
    ) -> JudgeResult: ...


_PROMPT_TEMPLATE = (
    "You are an industrial PVF (pipes/valves/fittings) catalog auditor. Compare "
    "two product images and decide if they represent the same SKU. Respond ONLY "
    "with a JSON object with these fields:\n"
    '  "verdict": one of "match" | "drift" | "reject" | "uncertain"\n'
    '  "confidence": float in [0.0, 1.0]\n'
    '  "reasoning": short string in Spanish, max 280 chars.\n'
    "Canonical image: {canonical}\n"
    "Candidate image: {candidate}\n"
    "Context: {context}\n"
)


def parse_judge_response(text: str) -> JudgeResult:
    """Parsea el JSON estricto del LLM a un :class:`JudgeResult`.

    Robusto: si el LLM devolvió texto extra antes/después del JSON, busca
    el primer ``{`` y último ``}``.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return JudgeResult(verdict="uncertain", confidence=0.5, reasoning=text[:280])
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return JudgeResult(verdict="uncertain", confidence=0.5, reasoning=text[:280])

    verdict_raw = str(data.get("verdict", "uncertain")).lower()
    if verdict_raw not in {"match", "drift", "reject", "uncertain"}:
        verdict_raw = "uncertain"
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    reasoning = str(data.get("reasoning", ""))[:280]
    return JudgeResult(
        verdict=verdict_raw,  # type: ignore[arg-type]
        confidence=confidence,
        reasoning=reasoning,
        raw=data,
    )


class OpenAIVisionJudge:
    """Adapter VLM sobre OpenAI Vision API (gpt-4o / gpt-4o-mini)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        http_client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._http_client = http_client
        self._owns_client = http_client is None
        self._base_url = base_url

    async def _http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def judge(
        self, *, canonical_image_url: str, candidate_image_url: str, context: str | None = None
    ) -> JudgeResult:
        prompt = _PROMPT_TEMPLATE.format(
            canonical=canonical_image_url,
            candidate=candidate_image_url,
            context=context or "n/a",
        )
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": canonical_image_url}},
                        {"type": "image_url", "image_url": {"url": candidate_image_url}},
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        client = await self._http()
        retryer = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.0, max=4.0),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async for attempt in retryer:
            with attempt:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return parse_judge_response(content)
        raise RuntimeError("unreachable")


class AnthropicVisionJudge:
    """Adapter VLM sobre Anthropic Messages API (claude-3.5-sonnet vision)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-latest",
        http_client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.anthropic.com/v1",
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._http_client = http_client
        self._owns_client = http_client is None
        self._base_url = base_url

    async def _http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def judge(
        self, *, canonical_image_url: str, candidate_image_url: str, context: str | None = None
    ) -> JudgeResult:
        prompt = _PROMPT_TEMPLATE.format(
            canonical=canonical_image_url,
            candidate=candidate_image_url,
            context=context or "n/a",
        )
        body = {
            "model": self._model,
            "max_tokens": 512,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "source": {"type": "url", "url": canonical_image_url}},
                        {"type": "image", "source": {"type": "url", "url": candidate_image_url}},
                    ],
                }
            ],
        }
        client = await self._http()
        retryer = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.0, max=4.0),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async for attempt in retryer:
            with attempt:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    json=body,
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                blocks = data.get("content") or []
                text = ""
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text = b.get("text", "")
                        break
                return parse_judge_response(text)
        raise RuntimeError("unreachable")


class VLMJudge:
    """Servicio público — selecciona adapter por env y aplica fallbacks.

    ``MT_LIVE_NETWORK=false`` → siempre veredicto neutro ``uncertain``,
    NO se llama a ningún proveedor.
    """

    def __init__(self, *, client: VLMClient | None = None) -> None:
        self._client = client

    def _live_enabled(self) -> bool:
        val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
        return val in {"1", "true", "yes", "on"}

    def _resolve_client(self) -> VLMClient | None:
        if self._client is not None:
            return self._client
        provider = os.environ.get("VLM_JUDGE_PROVIDER", "openai").lower()
        if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
            return OpenAIVisionJudge()
        if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            return AnthropicVisionJudge()
        return None

    async def judge(
        self,
        *,
        canonical_image_url: str,
        candidate_image_url: str,
        context: str | None = None,
    ) -> JudgeResult:
        if not self._live_enabled():
            return JudgeResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning="VLM judge disabled (MT_LIVE_NETWORK=false) — derive to human queue.",
            )
        client = self._resolve_client()
        if client is None:
            return JudgeResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning="VLM provider not configured — derive to human queue.",
            )
        try:
            return await client.judge(
                canonical_image_url=canonical_image_url,
                candidate_image_url=candidate_image_url,
                context=context,
            )
        except (RetryError, httpx.HTTPError) as exc:
            logger.exception("vlm_judge: provider call failed: %s", exc)
            return JudgeResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning=f"VLM provider error: {exc.__class__.__name__}",
            )


__all__ = [
    "AnthropicVisionJudge",
    "JudgeResult",
    "OpenAIVisionJudge",
    "VLMClient",
    "VLMJudge",
    "parse_judge_response",
]
