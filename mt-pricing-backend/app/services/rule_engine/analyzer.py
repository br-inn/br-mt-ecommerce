"""Analiza métricas de una familia y genera sugerencias via Claude API."""

from __future__ import annotations

import logging
from uuid import UUID
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

FP_RATE_THRESHOLD = 0.15
FN_RATE_THRESHOLD = 0.20


async def analyze_and_suggest(
    session: "AsyncSession",
    taxonomy_profile_id: UUID,
    family: str,
    metrics: dict,
) -> None:
    """Genera sugerencias para una familia si hay brechas detectadas."""
    from app.repositories.rule_suggestion import RuleSuggestionRepository
    from app.repositories.taxonomy_profile import TaxonomyProfileRepository

    suggestion_repo = RuleSuggestionRepository(session)
    tp_repo = TaxonomyProfileRepository(session)
    profile = await tp_repo.get(taxonomy_profile_id)
    if not profile:
        return

    fp_rate = metrics.get("fp_rate") or 0.0
    confirmation_rate = metrics.get("confirmation_rate") or 1.0

    suggestion_type: str | None = None
    if fp_rate > FP_RATE_THRESHOLD:
        suggestion_type = "false_positive"
    elif confirmation_rate < 0.5:
        suggestion_type = "false_negative"

    if not suggestion_type:
        return

    already_pending = await suggestion_repo.has_pending_for_type(
        taxonomy_profile_id, suggestion_type
    )
    if already_pending:
        logger.info(
            "rule_engine.suggestion.skip_duplicate",
            extra={"family": family, "type": suggestion_type},
        )
        return

    summary, proposed_change = await _call_claude(profile, metrics, suggestion_type)

    await suggestion_repo.create(
        taxonomy_profile_id=taxonomy_profile_id,
        suggestion_type=suggestion_type,
        analysis_summary=summary,
        proposed_change=proposed_change,
        status="pending",
    )
    logger.info(
        "rule_engine.suggestion.created",
        extra={"family": family, "type": suggestion_type},
    )


async def _call_claude(profile, metrics: dict, suggestion_type: str) -> tuple[str, dict]:
    try:
        import anthropic

        client = anthropic.Anthropic()

        weights_str = "\n".join(f"  - {k}: {v:.2f}" for k, v in profile.weights.items())
        blockers_str = ", ".join(profile.hard_blockers) if profile.hard_blockers else "ninguno"

        prompt = f"""Eres un experto en matching de productos industriales para distribuidores en Middle East.

Familia de producto: {profile.family}
Descripción: {profile.description or "N/A"}

Pesos actuales del scoring:
{weights_str}

Hard blockers activos: {blockers_str}

Métricas últimos {metrics.get("days", 30)} días:
- Total matches generados: {metrics.get("total_matches", 0)}
- Tasa de confirmación humana: {(metrics.get("confirmation_rate") or 0) * 100:.1f}%
- Tasa de falsos positivos: {(metrics.get("fp_rate") or 0) * 100:.1f}%
- Tipo de brecha detectada: {suggestion_type}

Analiza el problema y propone UN ajuste concreto y específico a los pesos o blockers para mejorar el performance.
Responde en español en máximo 3 oraciones: describe el problema, la causa probable, y el cambio exacto propuesto.
Solo el texto del análisis, sin formato adicional."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        summary = message.content[0].text.strip()
        proposed_change = {
            "suggestion_type": suggestion_type,
            "current_weights": dict(profile.weights),
            "metrics_snapshot": metrics,
        }
        return summary, proposed_change

    except Exception as exc:
        logger.warning(
            "rule_engine.claude.failed",
            extra={"error": str(exc)[:120]},
        )
        summary = (
            f"Brecha detectada: {suggestion_type}. "
            f"FP rate: {(metrics.get('fp_rate') or 0) * 100:.1f}%. "
            f"Revisar pesos manualmente."
        )
        proposed_change = {
            "suggestion_type": suggestion_type,
            "metrics_snapshot": metrics,
        }
        return summary, proposed_change
