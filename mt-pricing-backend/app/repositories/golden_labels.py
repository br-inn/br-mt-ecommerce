"""Repositorios para ``golden_labels`` y ``calibrator_versions`` (US-1A-09-07).

Operaciones expuestas:
- :class:`GoldenLabelRepository` — UPSERT por (sku, candidate_id),
  list_for_training (filtra por judged_at >= cutoff).
- :class:`CalibratorVersionRepository` — store, get_active, promote (atomic
  flip vía single-row constraint), list (admin).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.golden_label import CalibratorVersion, GoldenLabel


class GoldenLabelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        sku: str,
        candidate_id: UUID,
        label: int,
        score: float,
        judged_by: UUID | None = None,
        notes: str | None = None,
    ) -> GoldenLabel:
        """Last-write-wins por (sku, candidate_id)."""
        if label not in (0, 1):
            raise ValueError(f"label debe ser 0 ó 1; recibido {label}")
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"score debe estar en [0,1]; recibido {score}")

        stmt = pg_insert(GoldenLabel).values(
            sku=sku,
            candidate_id=candidate_id,
            label=label,
            score=score,
            judged_by=judged_by,
            notes=notes,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_golden_labels_sku_candidate",
            set_={
                "label": label,
                "score": score,
                "judged_by": judged_by,
                "notes": notes,
            },
        )
        await self.session.execute(stmt)
        await self.session.flush()

        # Reload el row final.
        out = (
            await self.session.execute(
                select(GoldenLabel).where(
                    GoldenLabel.sku == sku,
                    GoldenLabel.candidate_id == candidate_id,
                )
            )
        ).scalar_one()
        return out

    async def list_for_training(
        self,
        *,
        since: datetime | None = None,
        limit: int = 50_000,
    ) -> Sequence[GoldenLabel]:
        """Devuelve labels recientes para entrenamiento."""
        stmt = select(GoldenLabel)
        if since is not None:
            stmt = stmt.where(GoldenLabel.judged_at >= since)
        stmt = stmt.order_by(GoldenLabel.judged_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(GoldenLabel)
        return int((await self.session.execute(stmt)).scalar_one() or 0)


class CalibratorVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def store(
        self,
        *,
        version: str,
        model_json: dict[str, Any],
        trained_on_count: int,
        brier_score: float | None = None,
        ece: float | None = None,
        trained_by: UUID | None = None,
    ) -> CalibratorVersion:
        row = CalibratorVersion(
            version=version,
            model_json=model_json,
            trained_on_count=trained_on_count,
            brier_score=brier_score,
            ece=ece,
            trained_by=trained_by,
            is_active=False,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_by_version(self, version: str) -> CalibratorVersion | None:
        stmt = select(CalibratorVersion).where(CalibratorVersion.version == version)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_active(self) -> CalibratorVersion | None:
        stmt = select(CalibratorVersion).where(CalibratorVersion.is_active.is_(True))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_recent(self, limit: int = 20) -> Sequence[CalibratorVersion]:
        stmt = select(CalibratorVersion).order_by(CalibratorVersion.trained_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def promote(
        self,
        version: str,
        *,
        promoted_at: datetime | None = None,
    ) -> CalibratorVersion:
        """Flip atomic: desactiva el actual + activa la versión target.

        Constraint ``idx_calibrator_versions_active`` UNIQUE WHERE
        is_active=true garantiza que sólo haya un activo. Hacemos:

            1. UPDATE … SET is_active=false WHERE is_active=true
            2. UPDATE … SET is_active=true WHERE version=target

        Si version target no existe → ValueError. La transacción se commit
        a nivel route handler.
        """
        target = await self.get_by_version(version)
        if target is None:
            raise ValueError(f"calibrator version {version!r} no existe")

        await self.session.execute(
            update(CalibratorVersion)
            .where(CalibratorVersion.is_active.is_(True))
            .values(is_active=False)
        )
        await self.session.execute(
            update(CalibratorVersion)
            .where(CalibratorVersion.version == version)
            .values(is_active=True, promoted_at=promoted_at)
        )
        await self.session.flush()
        target = await self.get_by_version(version)
        assert target is not None  # noqa: S101
        return target


__all__ = ["CalibratorVersionRepository", "GoldenLabelRepository"]
