"""Tasks para la queue `notifications` — email, KPIs semanales."""

from __future__ import annotations

from app.workers.worker import celery_app


@celery_app.task(name="mt.notifications.health_ping")
def health_ping() -> str:
    return "ok"
