"""Persistencia + carga de calibrators (US-1A-09-07).

Wrapper sobre :class:`CalibratorVersionRepository` que serializa /
deserializa :class:`IsotonicCalibrator` JSON-only (NO pickle — ADR-073).

Convenciones:
- ``version`` semántico ``v<N>`` o ``s5-<timestamp>`` (caller decide).
- El active calibrator se cachea en memoria por ``MatchService`` —
  promotion debería invalidar ese cache (TODO Sprint 5+).
- Brier + ECE se guardan al store-time para reportar mejora antes de
  promover.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.repositories.golden_labels import CalibratorVersionRepository
from app.services.matching.calibrator import IsotonicCalibrator


class CalibratorStorage:
    """Bridge :class:`IsotonicCalibrator` ↔ DB."""

    def __init__(self, repo: CalibratorVersionRepository) -> None:
        self.repo = repo

    async def save(
        self,
        calibrator: IsotonicCalibrator,
        *,
        version: str,
        trained_on_count: int,
        brier_score: float | None = None,
        ece: float | None = None,
        trained_by: UUID | None = None,
    ) -> dict[str, Any]:
        """Persiste calibrator → DB. Devuelve metadata (sin row ORM)."""
        # Sobrescribe version field del calibrator para coherencia
        calibrator.version = version
        blob = calibrator.serialize()
        model_json = json.loads(blob)

        row = await self.repo.store(
            version=version,
            model_json=model_json,
            trained_on_count=trained_on_count,
            brier_score=brier_score,
            ece=ece,
            trained_by=trained_by,
        )
        return {
            "version": row.version,
            "trained_on_count": row.trained_on_count,
            "brier_score": float(row.brier_score) if row.brier_score is not None else None,
            "ece": float(row.ece) if row.ece is not None else None,
            "is_active": row.is_active,
        }

    async def load_active(self) -> IsotonicCalibrator | None:
        """Devuelve el calibrator marcado is_active, None si no hay."""
        row = await self.repo.get_active()
        if row is None:
            return None
        return IsotonicCalibrator.deserialize(json.dumps(row.model_json))

    async def load_by_version(self, version: str) -> IsotonicCalibrator | None:
        row = await self.repo.get_by_version(version)
        if row is None:
            return None
        return IsotonicCalibrator.deserialize(json.dumps(row.model_json))

    async def promote(self, version: str) -> dict[str, Any]:
        """Marca ``version`` como activa (atomic)."""
        row = await self.repo.promote(version, promoted_at=datetime.now(tz=UTC))
        return {
            "version": row.version,
            "is_active": row.is_active,
            "promoted_at": row.promoted_at,
        }

    async def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self.repo.list_recent(limit=limit)
        return [
            {
                "version": r.version,
                "trained_on_count": r.trained_on_count,
                "brier_score": float(r.brier_score) if r.brier_score is not None else None,
                "ece": float(r.ece) if r.ece is not None else None,
                "is_active": r.is_active,
                "trained_at": r.trained_at,
                "promoted_at": r.promoted_at,
            }
            for r in rows
        ]


__all__ = ["CalibratorStorage"]
