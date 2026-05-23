"""HITL Queue Price — cola HITL priorizada por uncertainty × value (US-SCR-04-08b).

Endpoints:
- GET   /api/v1/matching/hitl-queue         — lista ordenada por priority_score DESC
- PATCH /api/v1/matching/hitl-queue/{id}    — actualizar status (pending/approved/rejected/skipped)

RBAC: products:read (GET), products:write (PATCH).
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.hitl_queue import HitlQueue, HITL_STATUSES
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/matching", tags=["hitl-queue"])

RequireRead = Annotated[User, Depends(require_permissions("products:read"))]
RequireWrite = Annotated[User, Depends(require_permissions("products:write"))]

HitlStatus = Literal["pending", "approved", "rejected", "skipped"]


class HitlQueueItemOut(BaseModel):
    id: UUID
    match_id: UUID
    uncertainty_score: float
    product_value_aed: float | None
    priority_score: float | None
    status: str
    assigned_to: UUID | None
    notes: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class HitlQueuePatch(BaseModel):
    status: HitlStatus = Field(
        ..., description="Nuevo estado: pending | approved | rejected | skipped"
    )
    notes: str | None = Field(None, description="Notas del revisor")


@router.get("/hitl-queue")
async def list_hitl_queue(
    current_user: RequireRead,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Lista HITL queue ordenada por priority_score DESC (mayor urgencia primero)."""
    stmt = (
        select(HitlQueue)
        .order_by(HitlQueue.priority_score.desc().nulls_last())
        .offset(offset)
        .limit(max(1, min(limit, 200)))
    )
    if status_filter and status_filter in HITL_STATUSES:
        stmt = stmt.where(HitlQueue.status == status_filter)

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    return {
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": str(item.id),
                "match_id": str(item.match_id),
                "uncertainty_score": float(item.uncertainty_score),
                "product_value_aed": float(item.product_value_aed)
                if item.product_value_aed
                else None,
                "priority_score": float(item.priority_score) if item.priority_score else None,
                "status": item.status,
                "assigned_to": str(item.assigned_to) if item.assigned_to else None,
                "notes": item.notes,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ],
    }


@router.patch("/hitl-queue/{queue_id}")
async def update_hitl_queue_item(
    queue_id: Annotated[UUID, Path()],
    payload: Annotated[HitlQueuePatch, Body()],
    current_user: RequireWrite,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Actualiza el status de un item HITL (approved/rejected/skipped)."""
    item = await session.get(HitlQueue, queue_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="HITL queue item not found"
        )

    item.status = payload.status
    if payload.notes is not None:
        item.notes = payload.notes
    item.assigned_to = current_user.id

    await session.flush()
    await session.refresh(item)
    await session.commit()

    logger.info(
        "hitl_queue.updated",
        extra={
            "queue_id": str(queue_id),
            "status": payload.status,
            "reviewer": str(current_user.id),
        },
    )

    return {
        "id": str(item.id),
        "match_id": str(item.match_id),
        "status": item.status,
        "updated_at": item.updated_at.isoformat(),
    }
