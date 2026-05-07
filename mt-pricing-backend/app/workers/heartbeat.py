"""Worker heartbeat publisher — ADR-048.

Cada worker Celery publica su `last_seen` en Redis bajo la key
`mt:worker:heartbeat:<queue>` con TTL 120s. El endpoint `/health/celery` lee
esas keys y reporta queues vivas (age < 60s) vs muertas.

Mecanismos:
1. **`worker_ready` signal** — al arrancar el worker, escribimos heartbeat para
   cada queue que está consumiendo (puede ser una sola si el worker corre con
   `-Q imports`, o varias si con `-Q imports,pricing`).
2. **Task periódica `mt.system.publish_heartbeat`** — disparada por Beat
   (DatabaseScheduler) cada 30s a cada queue. Mantiene la key viva entre
   restarts ocasionales y refleja que el worker está procesando trabajo.

Nota: usamos el cliente Redis SÍNCRONO porque las signals y tasks Celery
corren en un loop síncrono — meter asyncio aquí es contraproducente.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from celery.signals import worker_ready
from redis import Redis as SyncRedis
from redis import from_url as sync_from_url

from app.core.config import settings
from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

# TTL un poco mayor que la cadencia de la task periódica (30s) más margen.
_HEARTBEAT_TTL_SECONDS: int = 120
# Cliente síncrono cacheado a nivel de módulo — los workers son procesos
# separados, no comparten estado con el server FastAPI.
_sync_client: SyncRedis | None = None


def _get_sync_redis() -> SyncRedis:
    """Cliente Redis sync para publishers en signals/tasks."""
    global _sync_client
    if _sync_client is None:
        _sync_client = sync_from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=2,
        )
    return _sync_client


def _publish(queue: str) -> None:
    """Escribe el heartbeat de una queue puntual con TTL."""
    redis = _get_sync_redis()
    now_iso = datetime.now(timezone.utc).isoformat()
    redis.set(f"mt:worker:heartbeat:{queue}", now_iso, ex=_HEARTBEAT_TTL_SECONDS)


# -----------------------------------------------------------------------------
# Signal: worker_ready — al arrancar publica heartbeats de cada queue listened
# -----------------------------------------------------------------------------
@worker_ready.connect
def on_worker_ready(sender: Any = None, **_: Any) -> None:
    """Publica heartbeat inicial para cada queue que el worker consume."""
    try:
        consumer = getattr(sender, "consumer", None)
        task_consumer = getattr(consumer, "task_consumer", None) if consumer else None
        if task_consumer and getattr(task_consumer, "queues", None):
            queues = [q.name for q in task_consumer.queues]
        else:
            # Fallback: la queue por defecto del app.
            default_q = sender.app.conf.task_default_queue if sender else "default"
            queues = [default_q]
        for q in queues:
            _publish(q)
        logger.info("worker_heartbeat.boot", extra={"queues": queues})
    except Exception:  # noqa: BLE001 — un fallo en heartbeat no debe tumbar el worker
        logger.exception("worker_heartbeat.boot_failed")


# -----------------------------------------------------------------------------
# Periodic task — agendada por DatabaseScheduler cada 30s a cada queue
# -----------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="mt.system.publish_heartbeat",
    acks_late=False,
    ignore_result=True,
)
def publish_heartbeat(self: Any) -> dict[str, str]:
    """Publica heartbeat para la queue por la que llegó la task.

    Beat agenda esta task en CADA queue (routing_key explícito), de modo que
    cada queue refresca su propia key. Si una queue se queda sin worker, su
    heartbeat caduca y `/health/celery` reporta `alive=false`.
    """
    routing_key = "default"
    if self.request is not None:
        delivery_info = getattr(self.request, "delivery_info", None) or {}
        routing_key = delivery_info.get("routing_key", "default")
    _publish(routing_key)
    return {"queue": routing_key}
