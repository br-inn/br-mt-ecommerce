"""JobDefinition + JobRun (DatabaseScheduler — ADR-046).

Plano cf. `mt-jobs-module-design.md` §6.4.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import JobOwner, JobStatus, ScheduleType, values_csv
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class JobDefinition(UuidPkMixin, Base):
    __tablename__ = "job_definitions"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    task_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'infra'"))

    schedule_type: Mapped[str] = mapped_column(String(16), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(Text)
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Asia/Dubai'"))
    queue: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'default'"))

    args: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    kwargs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_celery_task_id: Mapped[str | None] = mapped_column(Text)

    edited_by: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("users.id", ondelete="SET NULL")
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    runs: Mapped[list["JobRun"]] = relationship(
        back_populates="definition", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(f"owner IN {values_csv(JobOwner)}", name="ck_jobs_owner"),
        CheckConstraint(
            f"schedule_type IN {values_csv(ScheduleType)}",
            name="ck_jobs_schedule_type",
        ),
        CheckConstraint(
            "(schedule_type='cron' AND cron_expression IS NOT NULL) OR "
            "(schedule_type='interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)",
            name="ck_jobs_schedule_complete",
        ),
        CheckConstraint(
            f"last_status IS NULL OR last_status IN {values_csv(JobStatus)}",
            name="ck_jobs_last_status",
        ),
        Index(
            "idx_jobs_enabled",
            "enabled",
            postgresql_where=text("enabled = true"),
        ),
        Index("idx_jobs_next_run", "next_run_at"),
    )


class JobRun(UuidPkMixin, Base):
    __tablename__ = "job_runs"

    job_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("job_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'idle'"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    celery_task_id: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    definition: Mapped[JobDefinition] = relationship(back_populates="runs")

    __table_args__ = (
        CheckConstraint(f"status IN {values_csv(JobStatus)}", name="ck_job_runs_status"),
        Index("idx_job_runs_job_started", "job_id", "started_at"),
        Index(
            "idx_job_runs_running",
            "status",
            postgresql_where=text("status IN ('idle','running')"),
        ),
    )
