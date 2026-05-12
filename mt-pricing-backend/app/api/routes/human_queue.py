"""Human Queue routes — US-RND-01-10.

Endpoints:
- ``GET  /human-queue``              — lista matches con calibrated_confidence
  < threshold, paginado, ordenado ASC.
- ``POST /human-queue/{match_id}/label`` — persiste label (accept/reject/skip).

Feature flag: ``HUMAN_QUEUE_ENABLED`` en settings. Si False → 503.
RBAC:
- GET  → ``matches:read``
- POST → ``matches:write``
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.core.config import settings
from app.db.models.match_candidate import MatchCandidate
from app.db.models.user import User
from app.schemas.human_queue import HumanQueueItem, HumanQueueList, LabelRequest
from app.services.matching.human_queue_service import (
    HumanQueueError,
    HumanQueueService,
)

_VLM_ALLOWED_ROLES = frozenset({"admin", "gerente", "validador"})

router = APIRouter(prefix="/human-queue", tags=["human-queue"])

_DEFAULT_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# Feature flag guard
# ---------------------------------------------------------------------------
def _check_feature_enabled() -> None:
    if not settings.HUMAN_QUEUE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "human_queue_disabled",
                "title": "Human Queue deshabilitado",
                "detail": "HUMAN_QUEUE_ENABLED=false — feature no disponible.",
            },
        )


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_human_queue_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HumanQueueService:
    return HumanQueueService(session)


def _raise_domain(err: HumanQueueError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _build_item(row: MatchCandidate, user: User) -> HumanQueueItem:
    """Construye HumanQueueItem aplicando RBAC sobre campos VLM (AC#6)."""
    item = HumanQueueItem.model_validate(row)

    # Extraer datos VLM desde specs_jsonb['vlm_judge']
    vlm_data = (row.specs_jsonb or {}).get("vlm_judge", {})
    if vlm_data:
        item.judge_rationale = vlm_data.get("rationale")
        item.judge_image_regions = vlm_data.get("image_regions") or None

    # Ocultar campos VLM a viewers (AC#6)
    role_code = (user.role.code if user.role else None) or ""
    if role_code not in _VLM_ALLOWED_ROLES:
        item.judge_rationale = None
        item.judge_image_regions = None

    return item


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=HumanQueueList,
    summary="Lista cola de validación humana (calibrated_confidence < threshold)",
    description=(
        "Devuelve match candidates cuya ``calibrated_confidence`` es menor que "
        "``confidence_threshold`` (default 0.85), ordenados ASC (peor confianza "
        "primero). Los candidatos con ``calibrated_confidence NULL`` se incluyen "
        "al final. Paginación clásica vía ``limit`` + ``offset``."
    ),
    operation_id="humanQueueList",
)
async def list_human_queue(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    confidence_threshold: Annotated[float, Query(ge=0.0, le=1.0)] = _DEFAULT_THRESHOLD,
    _user: User = Depends(require_permissions("matches:read")),
    service: HumanQueueService = Depends(get_human_queue_service),
) -> HumanQueueList:
    _check_feature_enabled()
    rows = await service.list_queue(
        limit=limit,
        offset=offset,
        confidence_threshold=confidence_threshold,
    )
    return HumanQueueList(
        items=[_build_item(r, _user) for r in rows],
        total=len(rows),
        limit=limit,
        offset=offset,
        confidence_threshold=confidence_threshold,
    )


@router.post(
    "/{match_id}/label",
    response_model=HumanQueueItem,
    summary="Etiquetar match candidate (accept / reject / skip)",
    description=(
        "Persiste el veredicto del revisor humano sobre un match candidate. "
        "Actualiza ``label``, ``reviewer_user_id`` y ``reviewed_at``."
    ),
    operation_id="humanQueueLabel",
    responses={
        404: {"description": "Match candidate no encontrado"},
        503: {"description": "Human Queue deshabilitado (HUMAN_QUEUE_ENABLED=false)"},
    },
)
async def label_match(
    match_id: UUID,
    payload: LabelRequest,
    user: Annotated[User, Depends(require_permissions("matches:write"))],
    service: Annotated[HumanQueueService, Depends(get_human_queue_service)],
) -> HumanQueueItem:
    _check_feature_enabled()
    try:
        row = await service.label_match(
            match_id=match_id,
            label=payload.label,
            reviewer_user_id=user.id,
        )
    except HumanQueueError as e:
        _raise_domain(e)
    return _build_item(row, user)
