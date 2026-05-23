"""DatabaseScheduler — Celery Beat scheduler custom (ADR-046).

Implementación real que reemplaza el stub. Lee `public.job_definitions` cada
`UPDATE_INTERVAL` segundos y dispara las tasks Celery cuyos `next_run_at <= now()`.

Diseño:
- **Polling DB**: cada `tick()` (default cada 30s) consulta `job_definitions`
  con `enabled=true AND next_run_at <= now()`. No mantiene caché en memoria —
  la DB es source-of-truth (ADR-046).
- **Dispatch**: `celery_app.send_task(task_name, args, kwargs, queue=...)` con
  `task_id = JobRun.id` para correlación cross-broker.
- **Próxima ejecución**: croniter para `cron`; `now + interval_seconds` para
  `interval`. Persistido en `job_definitions.next_run_at`.
- **JobRun**: cada dispatch crea row con `status='idle'` (lifecycle real lo
  gobierna el worker via signals — out of scope aquí).
- **Sync I/O**: Celery beat es síncrono, así que usamos un engine síncrono
  (`create_engine`) en lugar del async; evita `asyncio.run()` reentrancy.
- **Single beat**: asume un único proceso Beat (Hetzner single-host). Para
  HA multi-instancia usar Redis lock NX EX (TODO Sprint 3).

Compatibilidad celery.beat:
- `setup_schedule()` — inicializa `self.schedule = {}` (no usamos schedule
  estático, todo dinámico via DB).
- `tick()` — devuelve segundos hasta el siguiente poll.
- `schedules_equal()` — comparación trivial (no leemos schedule estático).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from celery.beat import Scheduler
from croniter import croniter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class DatabaseScheduler(Scheduler):
    """Beat scheduler que lee `job_definitions` desde Postgres (ADR-046).

    Cada `tick()`:
        1. SELECT enabled jobs con next_run_at <= now().
        2. Para cada uno: dispatch + INSERT job_runs(status='idle') +
           UPDATE last_run_at + recompute next_run_at.
        3. Devuelve UPDATE_INTERVAL segundos hasta el siguiente poll.

    En fallo de dispatch (broker abajo): marca last_status='failed' y
    last_error en la fila — Beat continúa (no levanta excepción).
    """

    #: Intervalo entre polls (segundos). 30s razonable para cron de granularidad min.
    UPDATE_INTERVAL: int = 30
    #: Compatibilidad celery.beat — máximo entre ticks.
    max_interval: int = 30

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._engine: Engine = self._make_engine()
        logger.info(
            "DatabaseScheduler inicializado",
            extra={"poll_interval_s": self.UPDATE_INTERVAL},
        )

    # ------------------------------------------------------------------ Engine
    def _make_engine(self) -> Engine:
        """Engine síncrono. Beat es síncrono — no podemos usar asyncpg aquí.

        Usa `ALEMBIC_DATABASE_URL` (psycopg sync) para evitar mezclar con el
        pool asyncpg de la app FastAPI.
        """
        sync_url = str(settings.ALEMBIC_DATABASE_URL)
        return create_engine(sync_url, future=True, pool_pre_ping=True, pool_size=2)

    # ----------------------------------------------------------- Celery hooks
    def setup_schedule(self) -> None:
        """No usamos schedule estático — todo viene de DB en cada tick()."""
        self.schedule = {}

    def tick(self, *args: Any, **kwargs: Any) -> float:
        """Beat invoca esto cada `max_interval` segundos. Devuelve delay próximo."""
        try:
            self._dispatch_due_jobs()
        except Exception:
            logger.exception("DatabaseScheduler.tick fallo")
        return float(self.UPDATE_INTERVAL)

    def schedules_equal(
        self,
        old: Mapping[str, Any] | None,
        new: Mapping[str, Any] | None,
    ) -> bool:
        return old == new

    # ----------------------------------------------------------------- Logic
    def _dispatch_due_jobs(self) -> int:
        """Despacha jobs maduros. Devuelve count dispatched."""
        now = datetime.now(UTC)
        dispatched = 0

        # Lazy import — circular si lo ponemos al top (worker importa scheduler).
        from app.workers.worker import celery_app

        with self._engine.begin() as conn:
            # Lock pessimista por fila (FOR UPDATE SKIP LOCKED) — si un día
            # corremos múltiples beats, solo uno gana el dispatch.
            rows = (
                conn.execute(
                    text(
                        """
                    SELECT id, code, task_name, queue, args, kwargs,
                           schedule_type, cron_expression, interval_seconds,
                           timezone
                    FROM job_definitions
                    WHERE enabled = true
                      AND next_run_at IS NOT NULL
                      AND next_run_at <= :now
                    ORDER BY next_run_at ASC
                    FOR UPDATE SKIP LOCKED
                    """
                    ).bindparams(now=now)
                )
                .mappings()
                .all()
            )

            for job in rows:
                next_run = self._compute_next_run(
                    schedule_type=job["schedule_type"],
                    cron_expression=job["cron_expression"],
                    interval_seconds=job["interval_seconds"],
                    reference=now,
                    tz_name=job["timezone"] or "UTC",
                )
                try:
                    # 1. Insert JobRun row (status idle inicial; worker lo
                    #    promueve a 'running' al recoger la task).
                    run_id = conn.execute(
                        text(
                            """
                            INSERT INTO job_runs
                                (job_id, job_code, status, started_at, celery_task_id)
                            VALUES (:job_id, :job_code, 'idle', :now, NULL)
                            RETURNING id
                            """
                        ).bindparams(job_id=job["id"], job_code=job["code"], now=now)
                    ).scalar_one()

                    # 2. Dispatch a Celery — task_id = JobRun.id para correlación.
                    celery_app.send_task(
                        job["task_name"],
                        args=list(job["args"] or []),
                        kwargs=dict(job["kwargs"] or {}),
                        queue=job["queue"] or "default",
                        task_id=str(run_id),
                    )

                    # 3. Update job_definitions con last_run + next_run.
                    conn.execute(
                        text(
                            """
                            UPDATE job_definitions
                            SET last_run_at = :now,
                                next_run_at = :next_run,
                                last_status = 'running',
                                last_celery_task_id = :celery_task_id,
                                last_error = NULL,
                                updated_at = now()
                            WHERE id = :job_id
                            """
                        ).bindparams(
                            now=now,
                            next_run=next_run,
                            celery_task_id=str(run_id),
                            job_id=job["id"],
                        )
                    )

                    # 4. Update JobRun con celery_task_id.
                    conn.execute(
                        text("UPDATE job_runs SET celery_task_id = :tid WHERE id = :id").bindparams(
                            tid=str(run_id), id=run_id
                        )
                    )

                    dispatched += 1
                    logger.info(
                        "DatabaseScheduler.dispatch",
                        extra={
                            "job_code": job["code"],
                            "task_name": job["task_name"],
                            "queue": job["queue"],
                            "next_run_at": next_run.isoformat() if next_run else None,
                            "run_id": str(run_id),
                        },
                    )
                except Exception as exc:
                    logger.exception("DatabaseScheduler.dispatch_failed code=%s", job["code"])
                    conn.execute(
                        text(
                            """
                            UPDATE job_definitions
                            SET last_status = 'failed',
                                last_error = :err,
                                next_run_at = :next_run,
                                updated_at = now()
                            WHERE id = :job_id
                            """
                        ).bindparams(
                            err=str(exc)[:500],
                            next_run=next_run,
                            job_id=job["id"],
                        )
                    )

        return dispatched

    @staticmethod
    def _compute_next_run(
        *,
        schedule_type: str,
        cron_expression: str | None,
        interval_seconds: int | None,
        reference: datetime,
        tz_name: str,
    ) -> datetime | None:
        """Calcula el siguiente `next_run_at` desde `reference`.

        - cron: croniter en la timezone del job. Devuelve UTC tz-aware.
        - interval: reference + interval_seconds (UTC).
        - schedule_type desconocido: None (job se desactiva implícitamente
          al no tener next_run, hasta que admin lo reedite).
        """
        if schedule_type == "cron" and cron_expression:
            # croniter acepta tz-aware datetime y devuelve mismo tz.
            try:
                cron = croniter(cron_expression, reference)
                next_dt = cron.get_next(datetime)
                # croniter respeta el tz del input; aseguramos UTC para storage.
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=UTC)
                else:
                    next_dt = next_dt.astimezone(UTC)
                return next_dt
            except Exception:
                logger.exception("DatabaseScheduler.cron_parse_failed expr=%s", cron_expression)
                return None
        if schedule_type == "interval" and interval_seconds:
            return reference + timedelta(seconds=interval_seconds)
        return None
