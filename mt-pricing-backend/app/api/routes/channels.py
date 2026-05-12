"""Channel API — US-1B-03-02 (Sprint 8).

Endpoints:
- ``GET  /channels``                      — listar todos los canales.
- ``GET  /channels/{channel_id}/history`` — historial de transiciones.
- ``POST /channels/{channel_id}/transition`` — ejecutar transición de estado.

RBAC:
- ``channels:read``   — lectura de canales e historial.
- ``channels:manage`` — ti_integracion, admin (también cubre read).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _user_permission_codes, get_current_user, get_db_session, require_permissions
from app.db.models.channels import Channel, ChannelStateHistory
from app.db.models.user import User
from app.schemas.channels import (
    ChannelHistoryEntry,
    ChannelHistoryResponse,
    ChannelListResponse,
    ChannelRead,
    ChannelTransitionRequest,
    ChannelTransitionResponse,
)
from app.services.channels.transition_service import (
    ChannelTransitionError,
    ChannelTransitionService,
    MissingApprovedPricesError,
)

router = APIRouter(prefix="/channels", tags=["Channels"])

# Permisos que otorgan acceso de lectura a canales (OR logic).
_CHANNEL_READ_PERMS: frozenset[str] = frozenset({"channels:read", "channels:manage"})


async def _require_channel_read_access(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency OR: pasa si el usuario tiene channels:read O channels:manage."""
    if not (_CHANNEL_READ_PERMS & _user_permission_codes(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://mtme.ae/errors/permission-denied",
                "title": "Permission denied",
                "status": 403,
                "detail": "Requiere channels:read o channels:manage",
                "missing_permissions": ["channels:read|channels:manage"],
            },
        )
    return user


@router.get(
    "",
    response_model=ChannelListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar canales",
    description="Retorna todos los canales ordenados por código.",
    operation_id="listChannels",
    responses={
        403: {"description": "Sin permiso channels:read o channels:manage"},
    },
)
async def list_channels(
    session: AsyncSession = Depends(get_db_session),
    _actor: User = Depends(_require_channel_read_access),
) -> ChannelListResponse:
    """GET /channels — lista completa de canales."""
    result = await session.execute(select(Channel).order_by(Channel.code))
    channels = result.scalars().all()
    items = [ChannelRead.model_validate(ch) for ch in channels]
    return ChannelListResponse(items=items, total=len(items))


@router.get(
    "/{channel_id}/history",
    response_model=ChannelHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Historial de transiciones de un canal",
    description=(
        "Retorna el audit log de transiciones de estado del canal "
        "ordenado cronológicamente descendente."
    ),
    operation_id="channelHistory",
    responses={
        403: {"description": "Sin permiso channels:read o channels:manage"},
        404: {"description": "Canal no encontrado"},
    },
)
async def get_channel_history(
    channel_id: UUID = Path(..., description="UUID del canal"),
    session: AsyncSession = Depends(get_db_session),
    _actor: User = Depends(_require_channel_read_access),
) -> ChannelHistoryResponse:
    """GET /channels/{channel_id}/history — historial desc de transiciones."""
    channel = await session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal no encontrado",
        )

    result = await session.execute(
        select(ChannelStateHistory)
        .where(ChannelStateHistory.channel_id == channel_id)
        .order_by(ChannelStateHistory.created_at.desc())
    )
    history_rows = result.scalars().all()
    items = [ChannelHistoryEntry.model_validate(row) for row in history_rows]
    return ChannelHistoryResponse(channel_id=channel_id, items=items)


@router.post(
    "/{channel_id}/transition",
    response_model=ChannelTransitionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transicionar estado de canal",
    description=(
        "Ejecuta una transición de estado en la FSM del canal. "
        "La transición pre_launch → pilot valida que los subset_skus "
        "tengan precios aprobados. Si override_warnings=True y hay SKUs "
        "faltantes, se transiciona con pilot_with_warnings=True."
    ),
    operation_id="channelTransition",
    responses={
        400: {"description": "Transición inválida o SKUs faltantes sin override"},
        403: {"description": "Sin permiso channels:manage"},
        404: {"description": "Canal no encontrado"},
    },
)
async def transition_channel(
    channel_id: UUID = Path(..., description="UUID del canal"),
    body: ChannelTransitionRequest = ...,
    actor: User = Depends(require_permissions("channels:manage")),
    session: AsyncSession = Depends(get_db_session),
) -> ChannelTransitionResponse:
    """POST /channels/{channel_id}/transition."""
    channel = await session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal no encontrado",
        )

    service = ChannelTransitionService(session)

    try:
        history, missing_skus = await service.transition(
            channel_id=channel_id,
            target_state=body.target_state,
            actor=actor,
            subset_skus=body.subset_skus,
            comment=body.comment,
            override_warnings=body.override_warnings,
        )
    except MissingApprovedPricesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "missing_approved_prices",
                "message": str(exc),
                "missing_skus": exc.missing_skus,
            },
        ) from exc
    except ChannelTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await session.commit()

    return ChannelTransitionResponse(
        channel_id=str(channel.id),
        channel_code=channel.code,
        from_state=history.from_state,
        to_state=history.to_state,
        pilot_with_warnings=history.pilot_with_warnings,
        missing_skus=missing_skus,
        history_id=str(history.id),
    )
