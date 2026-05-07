"""Pydantic schemas — Jobs admin (DatabaseScheduler) API contracts.

Alineado con `app/db/models/job.py`. Idioma de campos = inglés (canónico API).

Endpoints expuestos en `app/api/routes/jobs.py`:
- ``GET    /admin/jobs``
- ``GET    /admin/jobs/{id}``
- ``POST   /admin/jobs``           (alta nueva job_definition)
- ``PATCH  /admin/jobs/{id}``      (toggle enabled, editar cron/args/kwargs/queue)
- ``POST   /admin/jobs/{id}/run-now``
- ``GET    /admin/jobs/{id}/runs`` (paginado JobRun)
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

JobOwnerLit = Literal["infra", "business"]
ScheduleTypeLit = Literal["cron", "interval"]
JobStatusLit = Literal["idle", "running", "success", "failure", "cancelled"]


class JobDefinitionListItem(BaseModel):
    """Listado paginado — versión liviana sin args/kwargs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    task_name: str
    description: str | None = None
    owner: JobOwnerLit
    schedule_type: ScheduleTypeLit
    cron_expression: str | None = None
    interval_seconds: int | None = None
    timezone: str
    queue: str
    enabled: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: JobStatusLit | None = None


class JobDefinitionResponse(JobDefinitionListItem):
    """Detalle completo — incluye args, kwargs, last_error, edited_*."""

    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    last_celery_task_id: str | None = None
    edited_by: UUID | None = None
    edited_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobDefinitionCreate(BaseModel):
    """Alta nueva job_definition — TI Integración."""

    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(min_length=2, max_length=128)]
    task_name: Annotated[str, Field(min_length=2, max_length=200)]
    description: str | None = Field(default=None, max_length=500)
    owner: JobOwnerLit = "infra"
    schedule_type: ScheduleTypeLit
    cron_expression: str | None = None
    interval_seconds: Annotated[int, Field(ge=1)] | None = None
    timezone: str = "Asia/Dubai"
    queue: str = "default"
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class JobDefinitionUpdate(BaseModel):
    """PATCH — sólo los campos que el admin puede editar."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=500)
    cron_expression: str | None = None
    interval_seconds: Annotated[int, Field(ge=1)] | None = None
    queue: str | None = None
    args: list[Any] | None = None
    kwargs: dict[str, Any] | None = None
    enabled: bool | None = None


class JobRunResponse(BaseModel):
    """Una ejecución (JobRun) — historial."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    job_code: str
    status: JobStatusLit
    started_at: datetime | None = None
    finished_at: datetime | None = None
    retries: int
    celery_task_id: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    duration_ms: int | None = None


class JobRunsPage(BaseModel):
    """Página de runs."""

    items: list[JobRunResponse]
    count: int
    next_cursor: str | None = None


class JobRunNowResponse(BaseModel):
    """Respuesta de POST /admin/jobs/{id}/run-now."""

    job_id: UUID
    run_id: UUID
    celery_task_id: str | None = None
    enqueued_at: datetime


__all__ = [
    "JobDefinitionCreate",
    "JobDefinitionListItem",
    "JobDefinitionResponse",
    "JobDefinitionUpdate",
    "JobRunNowResponse",
    "JobRunResponse",
    "JobRunsPage",
]
