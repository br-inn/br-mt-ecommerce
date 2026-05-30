"""Cleanup de snapshots auto vencidos (F2).

Borra `PricingScenario` con `kind LIKE 'auto_%'` y `retention_until < now()`.
Los snapshots `manual_a/b` (retention_until NULL) nunca se tocan.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def cleanup_expired_auto_snapshots(session: AsyncSession) -> int:
    """Borra snapshots auto vencidos. Devuelve el número de filas eliminadas."""
    res = await session.execute(
        text(
            # `kind` es enum PG (`snapshot_kind`); LIKE no opera sobre enum → castear a
            # text (asyncpg: `operator does not exist: snapshot_kind ~~ text`).
            "DELETE FROM pricing_scenarios WHERE kind::text LIKE 'auto\\_%' ESCAPE '\\' "
            "AND retention_until IS NOT NULL AND retention_until < now()"
        )
    )
    return res.rowcount or 0


__all__ = ["cleanup_expired_auto_snapshots"]
