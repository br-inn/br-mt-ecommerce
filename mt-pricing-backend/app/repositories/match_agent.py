"""Repositorios de match_agent_config (singleton) y match_agent_decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_agent import MatchAgentConfig, MatchAgentDecision


class MatchAgentConfigRepository:
    """Acceso a la fila singleton match_agent_config (id=1)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> MatchAgentConfig | None:
        return await self.session.get(MatchAgentConfig, 1)

    async def update(
        self,
        *,
        mode: str | None = None,
        alpha: Decimal | None = None,
        min_labels_gate: int | None = None,
        updated_by: UUID | None = None,
    ) -> MatchAgentConfig:
        values: dict[str, Any] = {
            "updated_at": datetime.now(tz=timezone.utc),
            "updated_by": updated_by,
        }
        if mode is not None:
            values["mode"] = mode
        if alpha is not None:
            values["alpha"] = alpha
        if min_labels_gate is not None:
            values["min_labels_gate"] = min_labels_gate
        await self.session.execute(
            update(MatchAgentConfig).where(MatchAgentConfig.id == 1).values(**values)
        )
        await self.session.flush()
        row = await self.session.get(MatchAgentConfig, 1)
        assert row is not None  # noqa: S101 — el seed garantiza id=1
        return row


class MatchAgentDecisionRepository:
    """CRUD de match_agent_decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        candidate_id: UUID,
        product_sku: str,
        verdict: str,
        mode: str,
        applied: bool,
        signal: str,
        score: int,
        calibrated_confidence: Decimal | None = None,
        review_priority: str | None = None,
        calibrator_version: str | None = None,
    ) -> MatchAgentDecision:
        row = MatchAgentDecision(
            candidate_id=candidate_id,
            product_sku=product_sku,
            verdict=verdict,
            mode=mode,
            applied=applied,
            signal=signal,
            score=score,
            calibrated_confidence=calibrated_confidence,
            review_priority=review_priority,
            calibrator_version=calibrator_version,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def latest_for_candidate(self, candidate_id: UUID) -> MatchAgentDecision | None:
        stmt = (
            select(MatchAgentDecision)
            .where(MatchAgentDecision.candidate_id == candidate_id)
            .order_by(MatchAgentDecision.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_human_outcome(self, candidate_id: UUID, outcome: str) -> None:
        """Rellena human_outcome en la última decisión del candidato."""
        latest = await self.latest_for_candidate(candidate_id)
        if latest is not None:
            latest.human_outcome = outcome
            await self.session.flush()

    async def count_shadow(self) -> int:
        stmt = (
            select(func.count())
            .select_from(MatchAgentDecision)
            .where(MatchAgentDecision.mode == "shadow")
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def shadow_precision(self) -> tuple[int, float | None]:
        """Precisión de sombra: aciertos / decisiones con human_outcome conocido."""
        stmt = select(MatchAgentDecision.verdict, MatchAgentDecision.human_outcome).where(
            MatchAgentDecision.human_outcome.is_not(None)
        )
        rows = (await self.session.execute(stmt)).all()
        scored = [(v, o) for v, o in rows if v in ("auto_validate", "auto_discard")]
        if not scored:
            return 0, None
        hits = sum(
            1
            for v, o in scored
            if (v == "auto_validate" and o == "validated")
            or (v == "auto_discard" and o == "discarded")
        )
        return len(scored), hits / len(scored)
