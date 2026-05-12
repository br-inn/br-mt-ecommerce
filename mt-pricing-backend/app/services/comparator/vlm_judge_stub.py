"""NoopVlmJudgeAdapter — stub cuando VLM_JUDGE_ENABLED=false (US-F15-02-02, AC#7).

Retorna uncertain/0.0 sin llamadas externas.  Usado como safe default cuando
el flag está OFF o la API key está vacía.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.comparator.interfaces import VlmJudgePort, VlmJudgeVerdict


class NoopVlmJudgeAdapter(VlmJudgePort):
    """VLM judge stub — retorna veredicto neutro sin llamadas externas."""

    async def judge(
        self,
        *,
        product_sku: str,
        candidate_image_url: str,
        product_image_url: str,
        context: dict[str, Any],
    ) -> VlmJudgeVerdict:
        return VlmJudgeVerdict(
            decision="uncertain",
            confidence=0.0,
            rationale="vlm_disabled",
            deal_breakers_triggered=(),
        )


__all__ = ["NoopVlmJudgeAdapter"]
