"""Tasks para la queue `imports` — PIM, costs, excel demo (Agente G/F)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="mt.imports.health_ping")
def health_ping() -> str:
    """Smoke test — el worker responde y el routing por prefijo funciona."""
    return "ok"


@celery_app.task(
    name="mt.imports.run_pim_import",
    queue="imports",
    bind=True,
    acks_late=True,
    # PIM completo.xlsx tiene 5086 filas × ~1.3s/fila ≈ 110 min worst-case.
    # Default Celery 540s mata el task antes — subimos a 2h hard / 1h45 soft.
    soft_time_limit=6300,  # 105 min — suficiente para los 5086 + buffer
    time_limit=7200,  # 2 h hard cap
)
def run_pim_import_task(
    self,
    run_id: str,
    source_path: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Wrapper sincrono para ejecutar PimImporter (async) desde Celery.

    Args:
        run_id: UUID del ImportRun pre-creado en estado ``queued``.
        source_path: path filesystem del xlsx (volumen montado en el worker).
        actor_id: UUID-string del usuario que disparó el run; None para fixture.

    Returns:
        dict con counters finales del run.
    """
    from uuid import UUID as _UUID

    from app.db.engine import get_sessionmaker
    from app.services.imports.pim_importer import PimImporter

    actor_uuid = _UUID(actor_id) if actor_id else None

    async def _run_async() -> dict[str, Any]:
        SessionFactory = get_sessionmaker()
        async with SessionFactory() as session:
            importer = PimImporter(
                session=session,
                source_path=source_path,
                run_id=run_id,
                actor_id=actor_uuid,
            )
            try:
                run = await importer.run()
                return {
                    "run_id": str(run.id),
                    "status": run.status,
                    "total_rows": run.total_rows,
                    "inserted_rows": run.inserted_rows,
                    "updated_rows": run.updated_rows,
                    "skipped_rows": run.skipped_rows,
                    "error_rows": run.error_rows,
                }
            except Exception as exc:
                logger.exception("run_pim_import_task failed run_id=%s: %s", run_id, exc)
                # PimImporter ya marcó failed en BD si llegó a empezar.
                raise

    # Celery worker corre con un nuevo loop por task — asyncio.run() OK.
    return asyncio.run(_run_async())
