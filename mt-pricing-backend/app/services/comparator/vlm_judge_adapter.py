"""ClaudeVlmJudgeAdapter — VLM judge via Anthropic SDK (US-F15-02-02).

Adapter concreto de :class:`VlmJudgePort` que llama a claude-sonnet-4-6 con
imágenes del SKU master y candidato.

Rate limit: 1 req/s vía Redis token bucket cross-worker (INCR+EXPIRE).
Fallback a AsyncLimiter proceso-local cuando redis_url es None (dev/test).

Prompt solicita respuesta JSON estricta:
  {verdict, confidence, reasoning, deal_breakers_triggered, image_regions}
Si la respuesta no es JSON válido → fallback uncertain/0.0 (AC#2).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

import anthropic
from aiolimiter import AsyncLimiter

from app.schemas.vlm_judge import ClaudeJudgeResponse
from app.services.comparator.interfaces import VlmJudgePort, VlmJudgeVerdict

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_RATE_LIMIT_REDIS_KEY = "vlm_judge:rate_per_second"
_MAX_CONTEXT_BYTES = 4096
_CONTEXT_SAFE_KEYS = frozenset({"dn", "pn", "material", "category", "brand", "title"})
_ALLOWED_IMAGE_SCHEMES = frozenset({"https"})

_SYSTEM_PROMPT = (
    "You are an industrial PVF (pipes, valves, fittings) catalog auditor. "
    "Compare two product images and decide if they represent the same SKU. "
    "Respond ONLY with a valid JSON object — no text outside the JSON. "
    'Schema: {"verdict":"match|reject|uncertain","confidence":0.0-1.0,'
    '"reasoning":"<1-3 sentences>","deal_breakers_triggered":["..."],'
    '"image_regions":[{"side":"sku|candidate","description":"..."}]}'
)

_UNCERTAIN_FALLBACK = VlmJudgeVerdict(
    decision="uncertain",
    confidence=0.0,
    rationale="",
    deal_breakers_triggered=(),
)


def _validate_image_url(
    url: str,
    param_name: str,
    sku: str,
    allowed_domains: frozenset[str],
) -> bool:
    """Valida scheme (https) y dominio contra allowlist. Retorna False → rechazar."""
    try:
        parsed = urlparse(url)
    except Exception:
        logger.error(
            "comparator.vlm_judge: URL inválida param=%s sku=%s", param_name, sku
        )
        return False
    if parsed.scheme not in _ALLOWED_IMAGE_SCHEMES:
        logger.error(
            "comparator.vlm_judge: scheme rechazado param=%s sku=%s scheme=%r",
            param_name,
            sku,
            parsed.scheme,
        )
        return False
    if allowed_domains and parsed.hostname not in allowed_domains:
        logger.error(
            "comparator.vlm_judge: dominio no en allowlist param=%s sku=%s domain=%r",
            param_name,
            sku,
            parsed.hostname,
        )
        return False
    return True


def _sanitize_context(context: dict[str, Any], sku: str) -> str:
    """Serializa context con cap de bytes; filtra a claves seguras si supera el límite."""
    text = json.dumps(context)
    if len(text.encode()) <= _MAX_CONTEXT_BYTES:
        return text
    safe = {k: v for k, v in context.items() if k in _CONTEXT_SAFE_KEYS}
    text = json.dumps(safe)
    if len(text.encode()) > _MAX_CONTEXT_BYTES:
        text = text.encode()[:_MAX_CONTEXT_BYTES].decode(errors="replace")
    logger.warning(
        "comparator.vlm_judge: context truncado sku=%s keys_original=%d",
        sku,
        len(context),
    )
    return text


class ClaudeVlmJudgeAdapter(VlmJudgePort):
    """VLM judge que invoca claude-sonnet-4-6 vía Anthropic SDK async.

    Args:
        api_key: Anthropic API key.  Obtenido de settings.ANTHROPIC_API_KEY.
        redis_url: URL de Redis para rate limiting cross-worker (1 req/s).
                   Si None, usa AsyncLimiter proceso-local (dev/test).
        allowed_image_domains: Dominios permitidos para URLs de imagen.
                   Vacío = sólo se valida el scheme https.
    """

    def __init__(
        self,
        *,
        api_key: str,
        redis_url: str | None = None,
        allowed_image_domains: frozenset[str] = frozenset(),
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._redis_url = redis_url
        self._allowed_domains = allowed_image_domains
        self._local_limiter = AsyncLimiter(rate=1, time_period=1.0)

    async def _acquire_rate_limit(self) -> None:
        """1 req/s: Redis token bucket cross-worker o AsyncLimiter como fallback."""
        if self._redis_url:
            import redis.asyncio as aioredis

            async with aioredis.from_url(self._redis_url) as r:
                bucket = f"{_RATE_LIMIT_REDIS_KEY}:{int(time.time())}"
                count = await r.incr(bucket)
                if count == 1:
                    await r.expire(bucket, 2)
                if count > 1:
                    await asyncio.sleep(1.0)
        else:
            async with self._local_limiter:
                pass

    async def judge(
        self,
        *,
        product_sku: str,
        candidate_image_url: str,
        product_image_url: str,
        context: dict[str, Any],
    ) -> VlmJudgeVerdict:
        for url, param in (
            (product_image_url, "product_image_url"),
            (candidate_image_url, "candidate_image_url"),
        ):
            if not _validate_image_url(url, param, product_sku, self._allowed_domains):
                return VlmJudgeVerdict(
                    decision="uncertain",
                    confidence=0.0,
                    rationale="url_rejected",
                    deal_breakers_triggered=(),
                )

        context_text = _sanitize_context(context, product_sku)

        await self._acquire_rate_limit()
        try:
            response = await self._client.messages.create(
                model=_MODEL,
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "url", "url": product_image_url},
                            },
                            {
                                "type": "image",
                                "source": {"type": "url", "url": candidate_image_url},
                            },
                            {
                                "type": "text",
                                "text": f"Context: {context_text}\nRespond ONLY with valid JSON.",
                            },
                        ],
                    }
                ],
            )
        except anthropic.AuthenticationError as exc:
            logger.error(
                "comparator.vlm_judge: autenticación fallida sku=%s — "
                "verificar ANTHROPIC_API_KEY: %s",
                product_sku,
                exc,
            )
            return VlmJudgeVerdict(
                decision="uncertain",
                confidence=0.0,
                rationale="auth_error",
                deal_breakers_triggered=(),
            )
        except anthropic.RateLimitError as exc:
            logger.error(
                "comparator.vlm_judge: rate limit de API sku=%s: %s",
                product_sku,
                exc,
            )
            return VlmJudgeVerdict(
                decision="uncertain",
                confidence=0.0,
                rationale="rate_limit",
                deal_breakers_triggered=(),
            )
        except Exception as exc:
            logger.warning(
                "comparator.vlm_judge: API call fallida sku=%s: %s",
                product_sku,
                exc,
            )
            return _UNCERTAIN_FALLBACK

        if not response.content:
            logger.warning(
                "comparator.vlm_judge: respuesta vacía (content=[]) sku=%s",
                product_sku,
            )
            return _UNCERTAIN_FALLBACK

        raw_text = response.content[0].text
        try:
            parsed = ClaudeJudgeResponse.model_validate_json(raw_text)
        except Exception:
            logger.warning(
                "comparator.vlm_judge: JSON inválido sku=%s raw=%r",
                product_sku,
                raw_text[:200],
            )
            return _UNCERTAIN_FALLBACK

        return VlmJudgeVerdict(
            decision=parsed.verdict,
            confidence=parsed.confidence,
            rationale=parsed.reasoning,
            deal_breakers_triggered=tuple(parsed.deal_breakers_triggered),
            image_regions=tuple(
                {str(k): str(v) for k, v in region.items()}
                for region in parsed.image_regions
            ),
        )


__all__ = ["ClaudeVlmJudgeAdapter"]
