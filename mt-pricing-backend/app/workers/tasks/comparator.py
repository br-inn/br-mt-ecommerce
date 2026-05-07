"""Tasks para la queue `comparator` — matching pipeline (research)."""

from __future__ import annotations

from app.workers.worker import celery_app


@celery_app.task(name="mt.comparator.health_ping")
def health_ping() -> str:
    return "ok"
