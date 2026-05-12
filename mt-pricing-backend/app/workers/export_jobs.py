"""Celery task: mt.pricing.capture_last_good_exports — US-1B-04-05.

Job diario que para cada combinación (channel_code, scheme_code) con al menos
un export ``completed`` hace UPSERT en ``last_good_exports`` con el registro
más reciente (mayor ``created_at``).

Nombre Celery: ``mt.pricing.capture_last_good_exports``
Queue: ``pricing``
Schedule: diario 02:00 UTC (06:00 Asia/Dubai) vía ``job_definitions`` (mig. 083).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------
_SQL_SELECT_LAST_COMPLETED = text(
    """
    SELECT DISTINCT ON (channel_code, scheme_code)
        id           AS export_manifest_id,
        channel_code,
        scheme_code,
        rows_exported,
        file_ref,
        created_at
    FROM exports_manifest
    WHERE status = 'completed'
    ORDER BY channel_code, scheme_code, created_at DESC
    """
)

_SQL_UPSERT = text(
    """
    INSERT INTO last_good_exports
        (channel_code, scheme_code, export_manifest_id, rows_exported, file_ref, captured_at)
    VALUES
        (:channel_code, :scheme_code, :export_manifest_id, :rows_exported, :file_ref, now())
    ON CONFLICT (channel_code, scheme_code)
    DO UPDATE SET
        export_manifest_id = EXCLUDED.export_manifest_id,
        rows_exported      = EXCLUDED.rows_exported,
        file_ref           = EXCLUDED.file_ref,
        captured_at        = now()
    """
)


# ---------------------------------------------------------------------------
# Core logic (testable standalone)
# ---------------------------------------------------------------------------
def _run_capture(sync_url: str) -> dict[str, Any]:
    """Ejecuta el UPSERT contra la base de datos sincrónica.

    Separado del task decorator para facilitar testing sin Celery.

    Args:
        sync_url: URL sincrónica de Postgres (psycopg / psycopg2).

    Returns:
        dict con ``upserted`` (int) y ``ran_at`` (ISO-8601 str).
    """
    engine = create_engine(sync_url, future=True)
    upserted = 0
    try:
        with engine.begin() as conn:
            rows = conn.execute(_SQL_SELECT_LAST_COMPLETED).mappings().all()
            for row in rows:
                conn.execute(
                    _SQL_UPSERT,
                    {
                        "channel_code": row["channel_code"],
                        "scheme_code": row["scheme_code"],
                        "export_manifest_id": row["export_manifest_id"],
                        "rows_exported": row["rows_exported"],
                        "file_ref": row["file_ref"],
                    },
                )
                upserted += 1
    finally:
        engine.dispose()

    return {
        "upserted": upserted,
        "ran_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------
@celery_app.task(
    name="mt.pricing.capture_last_good_exports",
    queue="pricing",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def capture_last_good_exports(self: Any) -> dict[str, Any]:  # noqa: ANN401
    """Para cada (channel_code, scheme_code) con exports completed, upserta el más reciente.

    Returns:
        dict con ``upserted`` (cantidad de filas actualizadas) y ``ran_at``.
    """
    sync_url = str(settings.ALEMBIC_DATABASE_URL)
    result = _run_capture(sync_url)
    logger.info(
        "capture_last_good_exports: upserted=%d ran_at=%s",
        result["upserted"],
        result["ran_at"],
    )
    return result


__all__ = ["capture_last_good_exports"]
