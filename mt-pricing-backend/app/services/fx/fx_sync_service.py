"""Sincroniza EUR→AED desde ECB hacia fx_rates con provenance (F2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SourceOp
from app.db.models.provenance import SourceHealth
from app.services.fx.ecb_adapter import EcbFxAdapter
from app.services.fx.fx_rate_service import FXRateService
from app.services.pricing.provenance import record_observation

logger = logging.getLogger(__name__)


async def _ecb_rate_exists_today(session: AsyncSession) -> bool:
    # asyncpg exige un objeto `date` para el param de tipo date (no un str ISO,
    # que provoca DataError: 'str' object has no attribute 'toordinal').
    today = datetime.now(UTC).date()
    row = (
        await session.execute(
            text(
                "SELECT 1 FROM fx_rates WHERE from_currency='EUR' AND to_currency='AED' "
                "AND source='ecb' AND effective_from::date = :d LIMIT 1"
            ),
            {"d": today},
        )
    ).first()
    return row is not None


async def _touch_health(
    session: AsyncSession, *, success: bool, rows: int, error: str | None
) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(SourceHealth)
        .where(SourceHealth.source_op == SourceOp.TESORERIA_FX.value)
        .values(
            last_sync_attempt_at=now,
            last_sync_success_at=now if success else SourceHealth.last_sync_success_at,
            last_error=None if success else error,
            rows_last_sync=rows,
            updated_at=now,
        )
    )


async def sync_ecb_eur_aed(
    session: AsyncSession, *, adapter: EcbFxAdapter | None = None, commit: bool = True
) -> dict[str, Any]:
    """Idempotente: si ya hay rate ecb de hoy, no inserta. Nunca lanza al beat.

    `commit=True` (default, producción) hace commit del trabajo. Los tests de
    integración pasan `commit=False` y usan la fixture `db_session` (rollback)
    para aislarse sin contaminar `fx_rates` del resto de la suite.
    """
    adapter = adapter or EcbFxAdapter()
    try:
        if await _ecb_rate_exists_today(session):
            await _touch_health(session, success=True, rows=0, error=None)
            if commit:
                await session.commit()
            return {"status": "ok", "inserted": 0, "reason": "already_synced_today"}
        quote = await adapter.fetch_eur_aed()
        svc = FXRateService(session)
        await svc.create_rate(
            from_code="EUR",
            to_code="AED",
            rate=quote.eur_aed,
            effective_from=datetime.now(UTC),
            source="ecb",
            actor=None,
        )
        await record_observation(
            session,
            source_op=SourceOp.TESORERIA_FX.value,
            target_table="fx_rates",
            target_field="rate",
            value=str(quote.eur_aed),
            source_ref=quote.source_ref,
        )
        await _touch_health(session, success=True, rows=1, error=None)
        if commit:
            await session.commit()
        return {"status": "ok", "inserted": 1, "eur_aed": str(quote.eur_aed)}
    except Exception as exc:
        logger.exception("fx.sync.failed")
        await session.rollback()
        await _touch_health(session, success=False, rows=0, error=str(exc)[:500])
        if commit:
            await session.commit()
        return {"status": "error", "inserted": 0, "error": str(exc)[:200]}
