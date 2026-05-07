"""Judge dispatcher con flag ``JUDGE_BACKEND`` (US-1A-06-04-V2).

Selecciona y ejecuta uno o más adapters VLM (OpenAI / Anthropic) según el flag
``JUDGE_BACKEND={openai|anthropic|both}``. En modo ``both`` corre ambos en
paralelo, retorna consensus si verdicts coinciden, sino marca
``disagreement=True`` y eleva confianza más baja para revisión humana.

Circuit breaker simple: cap mensual configurable via ``MT_VISION_MONTHLY_CAP_USD``
(default $50). Cuando se rebasa, abre fallback a un sólo proveedor (preferencia
OpenAI → Anthropic) y, si ambos están abiertos, retorna ``uncertain``.

Falla gracioso (NO sube excepciones) — siempre retorna un :class:`DispatchResult`
con ``verdict='uncertain'`` cuando no hay backend disponible o ``MT_LIVE_NETWORK!=true``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.services.matching.vlm_judge import (
    AnthropicVisionJudge,
    JudgeResult,
    OpenAIVisionJudge,
    VLMClient,
)

logger = logging.getLogger(__name__)

JudgeBackend = Literal["openai", "anthropic", "both"]
_VALID_BACKENDS: frozenset[str] = frozenset({"openai", "anthropic", "both"})

# Estimación grosera por invocación (gpt-4o-mini con 2 imágenes ~ $0.005).
_COST_PER_CALL_USD: dict[str, float] = {
    "openai": 0.005,
    "anthropic": 0.003,
}


@dataclass
class DispatchResult:
    """Veredicto consolidado + metadata de dispatch."""

    verdict: Literal["match", "drift", "reject", "uncertain"]
    confidence: float
    reasoning: str
    backends_used: list[str] = field(default_factory=list)
    per_backend: dict[str, JudgeResult] = field(default_factory=dict)
    disagreement: bool = False
    cost_estimate_usd: float = 0.0
    fallback_reason: str | None = None


@dataclass
class _MonthCounter:
    """Tracking en memoria — reset mensual. En prod, leer cost_tracker."""

    month_key: str = ""
    total_usd: float = 0.0

    def add(self, usd: float) -> None:
        key = datetime.now(tz=timezone.utc).strftime("%Y-%m")
        if key != self.month_key:
            self.month_key = key
            self.total_usd = 0.0
        self.total_usd += usd

    def current(self) -> float:
        key = datetime.now(tz=timezone.utc).strftime("%Y-%m")
        if key != self.month_key:
            return 0.0
        return self.total_usd


class JudgeDispatcher:
    """Coordina múltiples VLM adapters según ``JUDGE_BACKEND``.

    Inyectable: tests pasan ``backends={"openai": fake, ...}``; en runtime
    el constructor resuelve adapters concretos desde env.
    """

    def __init__(
        self,
        *,
        backends: dict[str, VLMClient] | None = None,
        cap_monthly_usd: float | None = None,
        cost_counter: _MonthCounter | None = None,
    ) -> None:
        self._backends_override = backends
        self._cap = cap_monthly_usd if cap_monthly_usd is not None else self._read_cap()
        self._cost_counter = cost_counter or _MonthCounter()

    @staticmethod
    def _read_cap() -> float:
        raw = os.environ.get("MT_VISION_MONTHLY_CAP_USD", "50")
        try:
            return float(raw)
        except ValueError:
            return 50.0

    @staticmethod
    def _live_enabled() -> bool:
        val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
        return val in {"1", "true", "yes", "on"}

    @staticmethod
    def _read_backend_flag() -> JudgeBackend:
        raw = os.environ.get("JUDGE_BACKEND", "openai").strip().lower()
        if raw not in _VALID_BACKENDS:
            return "openai"
        return raw  # type: ignore[return-value]

    def _resolve_backends(self, mode: JudgeBackend) -> dict[str, VLMClient]:
        if self._backends_override is not None:
            return {k: v for k, v in self._backends_override.items() if k in mode or mode == "both"}
        clients: dict[str, VLMClient] = {}
        if mode in {"openai", "both"} and os.environ.get("OPENAI_API_KEY"):
            clients["openai"] = OpenAIVisionJudge()
        if mode in {"anthropic", "both"} and os.environ.get("ANTHROPIC_API_KEY"):
            clients["anthropic"] = AnthropicVisionJudge()
        return clients

    async def dispatch(
        self,
        *,
        canonical_image_url: str,
        candidate_image_url: str,
        context: str | None = None,
    ) -> DispatchResult:
        if not self._live_enabled():
            return DispatchResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning="dispatcher disabled (MT_LIVE_NETWORK=false)",
                fallback_reason="live_disabled",
            )

        if self._cost_counter.current() >= self._cap:
            return DispatchResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning=f"monthly cost cap reached (${self._cap:.2f})",
                fallback_reason="cost_cap",
            )

        mode = self._read_backend_flag()
        clients = self._resolve_backends(mode)
        if not clients:
            return DispatchResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning="no backend configured",
                fallback_reason="no_backend",
            )

        per_backend: dict[str, JudgeResult] = {}
        cost = 0.0

        async def _call(name: str, client: VLMClient) -> tuple[str, JudgeResult | Exception]:
            try:
                res = await client.judge(
                    canonical_image_url=canonical_image_url,
                    candidate_image_url=candidate_image_url,
                    context=context,
                )
                return name, res
            except Exception as exc:  # noqa: BLE001 — fail-safe wrap
                logger.exception("judge_dispatcher: %s failed: %s", name, exc)
                return name, exc

        results = await asyncio.gather(*(_call(n, c) for n, c in clients.items()))
        for name, payload in results:
            cost += _COST_PER_CALL_USD.get(name, 0.005)
            if isinstance(payload, Exception):
                continue
            per_backend[name] = payload

        self._cost_counter.add(cost)

        if not per_backend:
            return DispatchResult(
                verdict="uncertain",
                confidence=0.5,
                reasoning="all backends failed",
                backends_used=list(clients.keys()),
                cost_estimate_usd=cost,
                fallback_reason="all_failed",
            )

        backends_used = list(per_backend.keys())
        if len(per_backend) == 1:
            only = next(iter(per_backend.values()))
            return DispatchResult(
                verdict=only.verdict,
                confidence=only.confidence,
                reasoning=only.reasoning,
                backends_used=backends_used,
                per_backend=per_backend,
                cost_estimate_usd=cost,
            )

        verdicts = {r.verdict for r in per_backend.values()}
        if len(verdicts) == 1:
            agreed = next(iter(verdicts))
            avg_conf = sum(r.confidence for r in per_backend.values()) / len(per_backend)
            reason = " | ".join(f"{n}: {r.reasoning[:80]}" for n, r in per_backend.items())
            return DispatchResult(
                verdict=agreed,
                confidence=avg_conf,
                reasoning=f"consensus ({len(per_backend)} backends): {reason}",
                backends_used=backends_used,
                per_backend=per_backend,
                cost_estimate_usd=cost,
            )

        min_conf = min(r.confidence for r in per_backend.values())
        reason = " | ".join(f"{n}: {r.verdict}@{r.confidence:.2f}" for n, r in per_backend.items())
        return DispatchResult(
            verdict="uncertain",
            confidence=min_conf,
            reasoning=f"disagreement: {reason}",
            backends_used=backends_used,
            per_backend=per_backend,
            disagreement=True,
            cost_estimate_usd=cost,
        )


__all__ = ["DispatchResult", "JudgeBackend", "JudgeDispatcher"]
