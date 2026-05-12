"""HumanQueueService — cola de validación humana (US-RND-01-10).

Filtra match candidates con calibrated_confidence < threshold y expone
la operación de labeling (accept / reject / skip) que persiste en DB.

Diseño:
- ``list_queue``: SELECT con filtro + ORDER BY calibrated_confidence ASC,
  con fallback a score/100.0 si calibrated_confidence es NULL.
- ``label_match``: UPDATE match_candidates SET label, reviewer_user_id,
  reviewed_at = now().
- Errores de negocio: ``HumanQueueError`` (mapea a 4xx en routes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import asc, nulls_last, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_candidate import MatchCandidate

LabelType = Literal["accept", "reject", "skip"]

_DEFAULT_THRESHOLD = 0.85
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


class HumanQueueError(Exception):
    """Errores de negocio de la cola humana — map a 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class HumanQueueNotFoundError(HumanQueueError):
    def __init__(self, match_id: UUID) -> None:
        super().__init__(
            code="human_queue_not_found",
            message=f"Match candidate {match_id} no encontrado.",
            status_code=404,
        )


class HumanQueueService:
    """Servicio de cola de validación humana.

    Args:
        session: SQLAlchemy AsyncSession inyectada por FastAPI.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_queue(
        self,
        limit: int = _DEFAULT_LIMIT,
        offset: int = 0,
        confidence_threshold: float = _DEFAULT_THRESHOLD,
    ) -> list[MatchCandidate]:
        """Lista candidatos con calibrated_confidence < threshold.

        Si calibrated_confidence es NULL, se incluye igualmente (NULL < cualquier
        valor en lógica de negocio = confianza desconocida → requiere revisión).
        Orden: calibrated_confidence ASC NULLS LAST (peor confianza primero).

        Args:
            limit: Máximo de filas devueltas (1-200).
            offset: Desplazamiento para paginación clásica.
            confidence_threshold: Umbral (por defecto 0.85).
        """
        limit = max(1, min(limit, _MAX_LIMIT))
        stmt = (
            select(MatchCandidate)
            .where(
                (MatchCandidate.calibrated_confidence < confidence_threshold)
                | (MatchCandidate.calibrated_confidence.is_(None))
            )
            .order_by(
                nulls_last(asc(MatchCandidate.calibrated_confidence)),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def label_match(
        self,
        match_id: UUID,
        label: LabelType,
        reviewer_user_id: UUID,
    ) -> MatchCandidate:
        """Persiste un veredicto humano sobre el match candidate.

        Args:
            match_id: UUID del MatchCandidate a etiquetar.
            label: Veredicto del revisor ('accept' / 'reject' / 'skip').
            reviewer_user_id: UUID del usuario que revisa.

        Returns:
            MatchCandidate actualizado.

        Raises:
            HumanQueueNotFoundError: Si no existe el match_id.
        """
        row = await self._session.get(MatchCandidate, match_id)
        if row is None:
            raise HumanQueueNotFoundError(match_id)

        row.label = label
        row.reviewer_user_id = reviewer_user_id
        row.reviewed_at = datetime.now(tz=timezone.utc)

        await self._session.flush()
        await self._session.refresh(row)
        return row
