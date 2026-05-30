"""Task: detecta drift por canal×modelo y registra alerta + snapshot (F8).

No aplica nada — solo crea un snapshot de revert (`auto_pre_sync_param`) y una
fila en `pricing_optimization_runs` con el diff. Dedup D4: no duplica una alerta
no-ack con el mismo baseline + contadores.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.db.enums import SnapshotKind
from app.db.models.channels import Channel
from app.db.models.optimization_run import PricingOptimizationRun
from app.services.pricing.drift_detector import detect_drift
from app.services.pricing.scenarios import create_auto_snapshot
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


async def _check_one(session: AsyncSession, channel_id: UUID, selling_model: str) -> dict[str, Any]:
    res = await detect_drift(session, channel_id=channel_id, selling_model=selling_model)
    if res is None or not res.should_alert:
        return {
            "channel_id": str(channel_id),
            "selling_model": selling_model,
            "alerted": False,
        }
    # dedup D4: ¿run no-ack con mismo diff/baseline ya existe?
    existing = (
        await session.execute(
            select(PricingOptimizationRun).where(
                PricingOptimizationRun.channel_id == channel_id,
                PricingOptimizationRun.selling_model == selling_model,
                PricingOptimizationRun.acknowledged_at.is_(None),
                PricingOptimizationRun.baseline_snapshot_id == res.baseline_snapshot_id,
                PricingOptimizationRun.skus_scheme_changed == res.summary.skus_scheme_changed,
                PricingOptimizationRun.skus_signal_changed == res.summary.skus_signal_changed,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "channel_id": str(channel_id),
            "selling_model": selling_model,
            "alerted": False,
            "dedup": True,
        }
    revert_id = await create_auto_snapshot(
        session,
        channel_id=channel_id,
        selling_model=selling_model,
        kind=SnapshotKind.AUTO_PRE_SYNC_PARAM,
    )
    session.add(
        PricingOptimizationRun(
            channel_id=channel_id,
            selling_model=selling_model,
            baseline_snapshot_id=res.baseline_snapshot_id,
            revert_snapshot_id=revert_id,
            skus_scheme_changed=res.summary.skus_scheme_changed,
            skus_signal_changed=res.summary.skus_signal_changed,
            drift_reasons=res.drift_reasons,
            diff_detail=res.summary.detail,
        )
    )
    return {
        "channel_id": str(channel_id),
        "selling_model": selling_model,
        "alerted": True,
    }


async def _run() -> dict[str, Any]:
    session_factory = get_sessionmaker()
    out: list[dict[str, Any]] = []
    async with session_factory() as session:
        channels = (await session.execute(select(Channel.id))).scalars().all()
        for cid in channels:
            for model in ("b2c", "b2b"):
                try:
                    out.append(await _check_one(session, cid, model))
                except Exception:
                    logger.exception(
                        "auto_optimize.check.failed",
                        extra={"channel_id": str(cid), "model": model},
                    )
                    await session.rollback()
        await session.commit()
    return {"status": "ok", "checks": out}


@celery_app.task(name="mt.pricing.auto_optimize_check", bind=True, acks_late=True)
def auto_optimize_check(self) -> dict[str, Any]:
    result = asyncio.run(_run())
    logger.info("auto_optimize.check.done", extra={"n": len(result.get("checks", []))})
    return result


__all__ = ["auto_optimize_check"]
