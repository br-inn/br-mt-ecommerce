"""Admin calibrator routes — US-1A-09-07 (Sprint 5).

Endpoints:
- ``GET   /admin/calibrator/active``           — info del calibrator activo.
- ``POST  /admin/calibrator/train``            — train + persist (perm
  ``calibrator:train``). Optional auto-promote si ECE mejora ≥ 5%.
- ``POST  /admin/calibrator/promote/{version}`` — atomic flip (perm
  ``calibrator:train``).

RBAC seed (migración 028):
- ``calibrator:train`` → ``ti_integracion``, ``admin``.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.golden_labels import (
    CalibratorVersionRepository,
    GoldenLabelRepository,
)
from app.schemas.calibrator import (
    CalibratorActiveResponse,
    CalibratorPromoteResponse,
    CalibratorTrainRequest,
    CalibratorTrainResponse,
)
from app.services.matching.calibrator_storage import CalibratorStorage
from app.services.matching.calibrator_trainer import (
    CalibratorTrainer,
    CalibratorTrainingNotReady,
)

router = APIRouter(prefix="/admin/calibrator", tags=["Calibrator Admin"])


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_calibrator_storage(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CalibratorStorage:
    repo = CalibratorVersionRepository(session)
    return CalibratorStorage(repo)


def get_calibrator_trainer(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[CalibratorStorage, Depends(get_calibrator_storage)],
) -> CalibratorTrainer:
    golden_repo = GoldenLabelRepository(session)
    return CalibratorTrainer(golden_repo=golden_repo, storage=storage)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/active",
    response_model=CalibratorActiveResponse,
    summary="Info del calibrator activo (admin only — calibrator:train)",
)
async def get_active(
    storage: Annotated[CalibratorStorage, Depends(get_calibrator_storage)],
    _user: User = Depends(require_permissions("calibrator:train")),
) -> CalibratorActiveResponse:
    row = await storage.repo.get_active()
    if row is None:
        return CalibratorActiveResponse(is_active=False)
    return CalibratorActiveResponse(
        version=row.version,
        trained_on_count=row.trained_on_count,
        brier_score=float(row.brier_score) if row.brier_score is not None else None,
        ece=float(row.ece) if row.ece is not None else None,
        is_active=row.is_active,
        trained_at=row.trained_at,
        promoted_at=row.promoted_at,
    )


@router.post(
    "/train",
    response_model=CalibratorTrainResponse,
    summary="Entrena calibrator (perm calibrator:train)",
)
async def train_calibrator(
    payload: CalibratorTrainRequest,
    trainer: Annotated[CalibratorTrainer, Depends(get_calibrator_trainer)],
    user: User = Depends(require_permissions("calibrator:train")),
) -> CalibratorTrainResponse:
    since = None
    if payload.since_days is not None:
        from datetime import UTC, datetime as _dt

        since = _dt.now(tz=UTC) - timedelta(days=payload.since_days)
    try:
        result = await trainer.train(
            since=since,
            version=payload.version,
            trained_by=user.id,
            auto_promote=payload.auto_promote,
        )
    except CalibratorTrainingNotReady as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://mtme.ae/errors/calibrator-not-ready",
                "title": "Calibrator training not ready",
                "status": 409,
                "detail": str(exc),
                "found": exc.found,
                "required": exc.required,
            },
        ) from exc
    return CalibratorTrainResponse(
        version=result.version,
        trained_on_count=result.trained_on_count,
        brier_before=result.brier_before,
        brier_after=result.brier_after,
        ece_before=result.ece_before,
        ece_after=result.ece_after,
        auto_promoted=result.auto_promoted,
    )


@router.post(
    "/promote/{version}",
    response_model=CalibratorPromoteResponse,
    summary="Atomic flip — promueve versión a is_active=true (perm calibrator:train)",
)
async def promote_version(
    version: str,
    storage: Annotated[CalibratorStorage, Depends(get_calibrator_storage)],
    _user: User = Depends(require_permissions("calibrator:train")),
) -> CalibratorPromoteResponse:
    try:
        info = await storage.promote(version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/calibrator-version-not-found",
                "title": "Calibrator version not found",
                "status": 404,
                "detail": str(exc),
            },
        ) from exc
    return CalibratorPromoteResponse(
        version=info["version"],
        is_active=info["is_active"],
        promoted_at=info.get("promoted_at"),
    )


__all__ = [
    "get_calibrator_storage",
    "get_calibrator_trainer",
    "router",
]
