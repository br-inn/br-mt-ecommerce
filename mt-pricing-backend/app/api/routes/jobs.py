"""Jobs admin routes — DatabaseScheduler editable (ADR-046).

Endpoints expuestos:
- ``GET    /admin/jobs``                — list job_definitions.
- ``POST   /admin/jobs``                — alta nueva job_definition.
- ``GET    /admin/jobs/{id}``           — detalle.
- ``PATCH  /admin/jobs/{id}``           — toggle enabled, editar cron/args/etc.
- ``POST   /admin/jobs/{id}/run-now``   — dispara Celery task ad-hoc.
- ``GET    /admin/jobs/{id}/runs``      — paginado historial JobRun.

RBAC:
- ``jobs:read``  → list/detail/runs.
- ``jobs:write`` → create/update.
- ``jobs:run``   → run-now.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.db.models.job import JobDefinition, JobRun
from app.db.models.user import User
from app.repositories.job import JobDefinitionRepository, JobRunRepository
from app.schemas.common import ProblemDetails
from app.schemas.jobs import (
    JobDefinitionCreate,
    JobDefinitionListItem,
    JobDefinitionResponse,
    JobDefinitionUpdate,
    JobRunNowResponse,
    JobRunResponse,
    JobRunsPage,
)

router = APIRouter(prefix="/admin/jobs", tags=["Jobs Admin"])


def _serialize_run(run: JobRun) -> JobRunResponse:
    duration_ms: int | None = None
    if run.started_at and run.finished_at:
        duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    return JobRunResponse(
        id=run.id,
        job_id=run.job_id,
        job_code=run.job_code,
        status=run.status,  # type: ignore[arg-type]
        started_at=run.started_at,
        finished_at=run.finished_at,
        retries=run.retries,
        celery_task_id=run.celery_task_id,
        result=run.result,
        error=run.error,
        created_at=run.created_at,
        duration_ms=duration_ms,
    )


@router.get(
    "",
    response_model=list[JobDefinitionListItem],
    dependencies=[Depends(require_permissions("jobs:read"))],
    summary="List job_definitions (paginado por next_run_at)",
)
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    enabled: Annotated[bool | None, Query()] = None,
    owner: Annotated[str | None, Query(pattern=r"^(infra|business)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobDefinitionListItem]:
    stmt = select(JobDefinition)
    if enabled is not None:
        stmt = stmt.where(JobDefinition.enabled.is_(enabled))
    if owner is not None:
        stmt = stmt.where(JobDefinition.owner == owner)
    stmt = stmt.order_by(JobDefinition.next_run_at.asc().nullslast()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [JobDefinitionListItem.model_validate(j) for j in rows]


@router.post(
    "",
    response_model=JobDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("jobs:write"))],
    summary="Crear job_definition",
    responses={409: {"model": ProblemDetails, "description": "code duplicado"}},
)
async def create_job(
    payload: JobDefinitionCreate,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobDefinitionResponse:
    # Validación de schedule completo (mismo CHECK que la BD).
    if payload.schedule_type == "cron" and not payload.cron_expression:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://mtme.ae/errors/job-schedule-incomplete",
                "title": "schedule_type=cron requiere cron_expression",
                "status": 422,
            },
        )
    if payload.schedule_type == "interval" and not payload.interval_seconds:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://mtme.ae/errors/job-schedule-incomplete",
                "title": "schedule_type=interval requiere interval_seconds > 0",
                "status": 422,
            },
        )

    repo = JobDefinitionRepository(session)
    existing = await repo.get_by_code(payload.code)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://mtme.ae/errors/job-duplicate-code",
                "title": f"Ya existe job_definition con code={payload.code}",
                "status": 409,
            },
        )
    obj = await repo.create(
        code=payload.code,
        task_name=payload.task_name,
        description=payload.description,
        owner=payload.owner,
        schedule_type=payload.schedule_type,
        cron_expression=payload.cron_expression,
        interval_seconds=payload.interval_seconds,
        timezone=payload.timezone,
        queue=payload.queue,
        args=payload.args,
        kwargs=payload.kwargs,
        enabled=payload.enabled,
        edited_by=actor.id,
        edited_at=datetime.now(tz=timezone.utc),
    )
    return JobDefinitionResponse.model_validate(obj)


@router.get(
    "/{job_id}",
    response_model=JobDefinitionResponse,
    dependencies=[Depends(require_permissions("jobs:read"))],
    summary="Detalle job_definition",
    responses={404: {"model": ProblemDetails}},
)
async def get_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobDefinitionResponse:
    repo = JobDefinitionRepository(session)
    obj = await repo.get(job_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/job-not-found",
                "title": "Job not found",
                "status": 404,
            },
        )
    return JobDefinitionResponse.model_validate(obj)


@router.patch(
    "/{job_id}",
    response_model=JobDefinitionResponse,
    dependencies=[Depends(require_permissions("jobs:write"))],
    summary="Actualizar job_definition (toggle, cron, args, kwargs, queue)",
    responses={404: {"model": ProblemDetails}},
)
async def update_job(
    job_id: UUID,
    payload: JobDefinitionUpdate,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobDefinitionResponse:
    repo = JobDefinitionRepository(session)
    obj = await repo.get(job_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/job-not-found",
                "title": "Job not found",
                "status": 404,
            },
        )
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    obj.edited_by = actor.id
    obj.edited_at = datetime.now(tz=timezone.utc)
    await session.flush()
    return JobDefinitionResponse.model_validate(obj)


@router.post(
    "/{job_id}/run-now",
    response_model=JobRunNowResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_permissions("jobs:run"))],
    summary="Disparar ejecución ad-hoc del job",
    responses={
        404: {"model": ProblemDetails},
        503: {"model": ProblemDetails, "description": "Celery no disponible"},
    },
)
async def run_job_now(
    job_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobRunNowResponse:
    """Crea un JobRun en estado `idle` y encola la task en Celery.

    No espera a que finalice — el worker actualizará el JobRun al terminar
    via `mark_run_outcome`. El frontend hace polling de `/runs`.
    """
    repo = JobDefinitionRepository(session)
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/job-not-found",
                "title": "Job not found",
                "status": 404,
            },
        )

    now = datetime.now(tz=timezone.utc)
    run = JobRun(
        id=uuid4(),
        job_id=job.id,
        job_code=job.code,
        status="idle",
        started_at=None,
        retries=0,
    )
    session.add(run)
    await session.flush()

    # Disparar Celery via send_task (no acoplamos al Task object para mantener
    # esta ruta independiente de los workers concretos). Si Celery no está
    # disponible, marcamos el run failed y devolvemos 503.
    celery_task_id: str | None = None
    try:
        from app.workers.celery_app import celery_app  # type: ignore[import-not-found]

        async_result = celery_app.send_task(
            job.task_name,
            args=list(job.args or []),
            kwargs=dict(job.kwargs or {}),
            queue=job.queue,
            headers={"job_id": str(job.id), "job_run_id": str(run.id)},
        )
        celery_task_id = async_result.id
        run.celery_task_id = celery_task_id
        await session.flush()
    except Exception as exc:  # noqa: BLE001
        run.status = "failure"
        run.error = f"Celery dispatch failed: {exc}"
        run.finished_at = datetime.now(tz=timezone.utc)
        await session.flush()
        # No 503 fatal — el frontend muestra el run failed. Devolvemos 503 sólo
        # si la app está corriendo en modo donde Celery debería existir.
        # Para coherencia con `imports.py`, igualamos a 503.
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "https://mtme.ae/errors/celery-unavailable",
                "title": "Celery no respondió, run marcado como failed.",
                "status": 503,
            },
        ) from exc

    # Marcamos el job_definition con el último celery_task_id (consistencia con
    # el scheduler real cuando dispara via cron).
    job.last_celery_task_id = celery_task_id
    job.edited_by = actor.id
    job.edited_at = now

    return JobRunNowResponse(
        job_id=job.id,
        run_id=run.id,
        celery_task_id=celery_task_id,
        enqueued_at=now,
    )


@router.get(
    "/{job_id}/runs",
    response_model=JobRunsPage,
    dependencies=[Depends(require_permissions("jobs:read"))],
    summary="Historial paginado de JobRun para el job",
    responses={404: {"model": ProblemDetails}},
)
async def list_job_runs(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobRunsPage:
    repo = JobDefinitionRepository(session)
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://mtme.ae/errors/job-not-found",
                "title": "Job not found",
                "status": 404,
            },
        )
    runs_repo = JobRunRepository(session)
    # Reusamos list_for_job pero ofreciendo offset paging.
    stmt = (
        select(JobRun)
        .where(JobRun.job_id == job_id)
        .order_by(desc(JobRun.started_at).nullslast(), desc(JobRun.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    count_stmt = select(func.count(JobRun.id)).where(JobRun.job_id == job_id)
    total = (await session.execute(count_stmt)).scalar_one()
    items = [_serialize_run(r) for r in rows]
    next_cursor = str(offset + limit) if offset + limit < (total or 0) else None
    # Silenciamos warning unused — repo se usa para asegurar el módulo importa.
    _ = runs_repo
    return JobRunsPage(items=items, count=total or 0, next_cursor=next_cursor)


__all__ = ["router"]
