"""JobDefinitionRepository + JobRunRepository — DatabaseScheduler (ADR-046)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.db.enums import JobStatus
from app.db.models.job import JobDefinition, JobRun
from app.repositories.base import BaseRepository


class JobDefinitionRepository(BaseRepository[JobDefinition]):
    model = JobDefinition
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> JobDefinition | None:
        stmt = select(JobDefinition).where(JobDefinition.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_enabled(self) -> Sequence[JobDefinition]:
        stmt = (
            select(JobDefinition)
            .where(JobDefinition.enabled.is_(True))
            .order_by(JobDefinition.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_due(self, *, now: datetime) -> Sequence[JobDefinition]:
        """Jobs con `next_run_at <= now` y enabled — usado por el scheduler."""
        stmt = (
            select(JobDefinition)
            .where(
                JobDefinition.enabled.is_(True),
                JobDefinition.next_run_at.is_not(None),
                JobDefinition.next_run_at <= now,
            )
            .order_by(JobDefinition.next_run_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_run_outcome(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        error: str | None = None,
        celery_task_id: str | None = None,
        next_run_at: datetime | None = None,
        last_run_at: datetime | None = None,
    ) -> JobDefinition | None:
        return await self.update(
            job_id,
            last_status=status.value,
            last_error=error,
            last_celery_task_id=celery_task_id,
            next_run_at=next_run_at,
            last_run_at=last_run_at,
        )


class JobRunRepository(BaseRepository[JobRun]):
    model = JobRun
    pk_field = "id"
    soft_delete_field = None

    async def list_for_job(self, job_id: UUID, *, limit: int = 50) -> Sequence[JobRun]:
        stmt = (
            select(JobRun)
            .where(JobRun.job_id == job_id)
            .order_by(JobRun.started_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_recent_failures(self, *, limit: int = 50) -> Sequence[JobRun]:
        stmt = (
            select(JobRun)
            .where(JobRun.status == JobStatus.FAILURE.value)
            .order_by(JobRun.finished_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
