"""Task periódica que analiza performance de reglas y genera sugerencias IA."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="mt.rule_engine.analyze_performance",
    queue="comparator",
    max_retries=0,
)
def analyze_rule_performance() -> dict[str, Any]:
    """Analiza métricas de cada familia y genera sugerencias vía Claude API.

    Disparado por Beat via job_definitions (code: rule_engine_analyzer).
    Corre diariamente a las 06:00 UTC. Por familia: calcula métricas de los
    últimos 7 días, llama a Claude Haiku si hay brecha FP/FN, y crea una
    RuleSuggestion pendiente de revisión humana.
    """

    async def _run() -> dict[str, Any]:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import settings
        from app.repositories.taxonomy_profile import TaxonomyProfileRepository
        from app.repositories.match_rule_stat import MatchRuleStatRepository
        from app.services.rule_engine.analyzer import analyze_and_suggest

        engine = create_async_engine(
            str(settings.DATABASE_URL),
            poolclass=NullPool,
            connect_args={"statement_cache_size": 0},
        )
        SessionMaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        results: dict[str, str] = {}
        async with SessionMaker() as session:
            tp_repo = TaxonomyProfileRepository(session)
            stat_repo = MatchRuleStatRepository(session)
            profiles = await tp_repo.list_all()

            for profile in profiles:
                if profile.family == "_default":
                    continue
                try:
                    metrics = await stat_repo.get_profile_metrics(profile.id, days=7)
                    await analyze_and_suggest(session, profile.id, profile.family, metrics)
                    await session.commit()
                    results[profile.family] = "analyzed"
                except Exception as exc:
                    logger.warning(
                        "rule_engine.analyze.family_failed",
                        extra={"family": profile.family, "error": str(exc)[:80]},
                    )
                    results[profile.family] = f"error: {str(exc)[:40]}"
                    await session.rollback()

        await engine.dispose()
        return {"analyzed": len(results), "results": results}

    return asyncio.run(_run())
