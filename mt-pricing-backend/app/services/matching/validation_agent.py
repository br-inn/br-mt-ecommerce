"""MatchValidationAgent — agente semi-autónomo de validación de matches.

Señal de decisión:
- Bootstrap (sin calibrador): usa _enhanced.auto_validate + method.
- Calibrada (calibrador activo): usa review_priority del ConformalWrapper.

Filtro negativo duro: method == 'vision_rejected' SIEMPRE descarta.

Modo (de match_agent_config):
- shadow: registra el veredicto en match_agent_decisions, NO toca match_candidates.
- active: además aplica status validated/discarded e inyecta specs_jsonb._agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_candidate import MatchCandidate
from app.repositories.match_agent import (
    MatchAgentConfigRepository,
    MatchAgentDecisionRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentDecision:
    """Veredicto del agente para un candidato."""

    verdict: str  # "auto_validate" | "auto_discard" | "human"
    signal: str  # "conformal" | "bootstrap"


def decide_verdict(
    *,
    score: int,
    enhanced: dict[str, Any],
    review_priority: str | None,
    has_calibrator: bool,
) -> AgentDecision:
    """Función pura de decisión — sin efectos secundarios."""
    method = str(enhanced.get("method") or "")

    # Filtro negativo duro — aplica en cualquier fase.
    if method == "vision_rejected":
        signal = "conformal" if has_calibrator else "bootstrap"
        return AgentDecision(verdict="auto_discard", signal=signal)

    if has_calibrator:
        if review_priority == "low":
            return AgentDecision(verdict="auto_validate", signal="conformal")
        if review_priority == "high":
            return AgentDecision(verdict="auto_discard", signal="conformal")
        return AgentDecision(verdict="human", signal="conformal")

    # Bootstrap — signal sin calibrar.
    if enhanced.get("auto_validate") is True:
        return AgentDecision(verdict="auto_validate", signal="bootstrap")
    return AgentDecision(verdict="human", signal="bootstrap")


class MatchValidationAgent:
    """Orquesta la decisión + aplicación del agente sobre los candidatos de un SKU."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._config_repo = MatchAgentConfigRepository(session)
        self._decision_repo = MatchAgentDecisionRepository(session)

    async def run(self, sku: str) -> int:
        """Procesa todos los candidatos `pending` de un SKU. Devuelve nº decididos.

        Nunca lanza excepción hacia el caller — si algo falla, loguea y sigue.
        """
        try:
            config = await self._config_repo.get()
            if config is None:
                logger.warning("validation_agent.no_config — skipping")
                return 0
            mode = config.mode

            has_calibrator = await self._has_active_calibrator()

            stmt = select(MatchCandidate).where(
                MatchCandidate.product_sku == sku,
                MatchCandidate.status == "pending",
            )
            candidates = list((await self._session.execute(stmt)).scalars().all())

            decided = 0
            for cand in candidates:
                # Idempotencia: si ya hay una decisión aplicada, saltar.
                existing = await self._decision_repo.latest_for_candidate(cand.id)
                if existing is not None and existing.applied:
                    continue

                specs = dict(cand.specs_jsonb or {})
                enhanced = dict(specs.get("_enhanced") or {})
                review_priority = getattr(cand, "review_priority", None)

                decision = decide_verdict(
                    score=cand.score,
                    enhanced=enhanced,
                    review_priority=review_priority,
                    has_calibrator=has_calibrator,
                )

                applied = mode == "active" and decision.verdict != "human"
                if applied:
                    self._apply(cand, decision, mode)

                calibrator_version = (
                    await self._active_calibrator_version()
                    if has_calibrator
                    else None
                )
                await self._decision_repo.record(
                    candidate_id=cand.id,
                    product_sku=cand.product_sku,
                    verdict=decision.verdict,
                    mode=mode,
                    applied=applied,
                    signal=decision.signal,
                    score=cand.score,
                    calibrated_confidence=getattr(cand, "calibrated_confidence", None),
                    review_priority=review_priority,
                    calibrator_version=calibrator_version,
                )
                decided += 1

            await self._session.flush()
            logger.info(
                "validation_agent.run.done",
                extra={"sku": sku, "mode": mode, "decided": decided},
            )
            return decided
        except Exception:  # noqa: BLE001 — el agente nunca rompe el worker
            logger.exception("validation_agent.run.error", extra={"sku": sku})
            return 0

    def _apply(self, cand: MatchCandidate, decision: AgentDecision, mode: str) -> None:
        """Aplica el veredicto al candidato (solo modo active)."""
        if decision.verdict == "auto_validate":
            cand.status = "validated"
        elif decision.verdict == "auto_discard":
            cand.status = "discarded"
        else:
            return
        specs = dict(cand.specs_jsonb or {})
        specs["_agent"] = {
            "verdict": decision.verdict,
            "mode": mode,
            "signal": decision.signal,
            "decided_at": datetime.now(tz=timezone.utc).isoformat(),
            "applied": True,
        }
        cand.specs_jsonb = specs

    async def _has_active_calibrator(self) -> bool:
        """Returns True if there is an active calibrator version in the DB."""
        try:
            from app.db.models.golden_label import CalibratorVersion  # noqa: PLC0415
            stmt = select(CalibratorVersion.id).where(
                CalibratorVersion.is_active.is_(True)
            ).limit(1)
            return (await self._session.execute(stmt)).scalar_one_or_none() is not None
        except Exception:  # noqa: BLE001 — if table doesn't exist yet, no calibrator
            return False

    async def _active_calibrator_version(self) -> str | None:
        """Returns the version string of the active calibrator, if any."""
        try:
            from app.db.models.golden_label import CalibratorVersion  # noqa: PLC0415
            stmt = select(CalibratorVersion.version).where(
                CalibratorVersion.is_active.is_(True)
            ).limit(1)
            return (await self._session.execute(stmt)).scalar_one_or_none()
        except Exception:  # noqa: BLE001
            return None
