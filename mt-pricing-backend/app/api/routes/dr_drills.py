"""DR Drills admin router — CRUD + resumen de ejercicios de Disaster Recovery."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.dr_drills import DrDrill
from app.db.models.user import User

router = APIRouter(prefix="/dr-drills", tags=["DR Drills"])

_ADMIN_PERM = "admin"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class DrDrillCreate(BaseModel):
    drill_type: str
    scheduled_date: date
    executed_date: date | None = None
    outcome: str | None = None
    duration_minutes: int | None = None
    findings: str | None = None
    runbook_ref: str | None = None
    conducted_by_user_id: UUID | None = None
    notes: str | None = None


class DrDrillUpdate(BaseModel):
    executed_date: date | None = None
    outcome: str | None = None
    duration_minutes: int | None = None
    findings: str | None = None
    notes: str | None = None


class DrDrillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    drill_type: str
    scheduled_date: date
    executed_date: date | None
    outcome: str | None
    duration_minutes: int | None
    findings: str | None
    runbook_ref: str | None
    conducted_by_user_id: UUID | None
    notes: str | None


class DrDrillSummary(BaseModel):
    total: int
    by_outcome: dict[str, int]
    last_drill_date: date | None
    next_scheduled_date: date | None
    drills_by_runbook: dict[str, str | None]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=list[DrDrillOut], summary="Listar drills DR")
async def list_drills(
    _user: Annotated[User, Depends(require_permissions(_ADMIN_PERM))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    outcome: Annotated[str | None, Query()] = None,
    runbook_ref: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[DrDrill]:
    stmt = select(DrDrill).order_by(DrDrill.scheduled_date.desc()).limit(limit)
    if outcome is not None:
        stmt = stmt.where(DrDrill.outcome == outcome)
    if runbook_ref is not None:
        stmt = stmt.where(DrDrill.runbook_ref == runbook_ref)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=DrDrillOut, status_code=201, summary="Crear drill DR")
async def create_drill(
    body: DrDrillCreate,
    _user: Annotated[User, Depends(require_permissions(_ADMIN_PERM))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DrDrill:
    drill = DrDrill(
        id=uuid4(),
        drill_type=body.drill_type,
        scheduled_date=body.scheduled_date,
        executed_date=body.executed_date,
        outcome=body.outcome,
        duration_minutes=body.duration_minutes,
        findings=body.findings,
        runbook_ref=body.runbook_ref,
        conducted_by_user_id=body.conducted_by_user_id,
        notes=body.notes,
    )
    session.add(drill)
    await session.commit()
    await session.refresh(drill)
    return drill


@router.patch("/{drill_id}", response_model=DrDrillOut, summary="Actualizar drill DR")
async def update_drill(
    drill_id: UUID,
    body: DrDrillUpdate,
    _user: Annotated[User, Depends(require_permissions(_ADMIN_PERM))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DrDrill:
    drill = await session.get(DrDrill, drill_id)
    if drill is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "dr_drill_not_found", "title": f"Drill {drill_id} no encontrado"},
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(drill, field, value)
    await session.commit()
    await session.refresh(drill)
    return drill


@router.get("/summary", response_model=DrDrillSummary, summary="Resumen de drills DR")
async def get_summary(
    _user: Annotated[User, Depends(require_permissions(_ADMIN_PERM))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DrDrillSummary:
    total_result = await session.execute(select(func.count()).select_from(DrDrill))
    total: int = total_result.scalar_one()

    outcome_rows = await session.execute(
        select(DrDrill.outcome, func.count().label("cnt"))
        .where(DrDrill.outcome.isnot(None))
        .group_by(DrDrill.outcome)
    )
    by_outcome: dict[str, int] = {row.outcome: row.cnt for row in outcome_rows}

    last_result = await session.execute(
        select(DrDrill.executed_date)
        .where(DrDrill.executed_date.isnot(None))
        .order_by(DrDrill.executed_date.desc())
        .limit(1)
    )
    last_drill_date: date | None = last_result.scalar_one_or_none()

    next_result = await session.execute(
        select(DrDrill.scheduled_date)
        .where(DrDrill.executed_date.is_(None))
        .order_by(DrDrill.scheduled_date.asc())
        .limit(1)
    )
    next_scheduled_date: date | None = next_result.scalar_one_or_none()

    runbook_rows = await session.execute(
        select(DrDrill.runbook_ref, DrDrill.outcome, DrDrill.scheduled_date)
        .where(DrDrill.runbook_ref.isnot(None))
        .order_by(DrDrill.runbook_ref, DrDrill.scheduled_date.desc())
    )
    drills_by_runbook: dict[str, str | None] = {}
    for row in runbook_rows:
        if row.runbook_ref not in drills_by_runbook:
            drills_by_runbook[row.runbook_ref] = row.outcome

    return DrDrillSummary(
        total=total,
        by_outcome=by_outcome,
        last_drill_date=last_drill_date,
        next_scheduled_date=next_scheduled_date,
        drills_by_runbook=drills_by_runbook,
    )
