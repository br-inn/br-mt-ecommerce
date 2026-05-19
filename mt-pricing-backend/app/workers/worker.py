"""Celery app factory — 6 queues nombradas, routing por prefijo `mt.<module>.*`.

Refs:
- `mt-jobs-module-design.md` §Configuración Celery
- ADR-030 (Celery elegida sobre alternativas)
- ADR-046 (DatabaseScheduler — beat config)

Comando local típico (un proceso por queue, o pool por grupo):

    celery -A app.workers.worker worker \
        -Q imports,pricing,images,comparator,notifications,audit \
        -l info

Beat:

    celery -A app.workers.worker beat \
        --scheduler app.scheduler.database_scheduler:DatabaseScheduler \
        -l info
"""

from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

# --- Queue topology ---------------------------------------------------------
# Cada queue tiene su propio exchange/routing-key idéntico al nombre. Permite
# escalar workers por queue sin tocar tasks (mt-jobs-module-design §3).
_QUEUE_NAMES: tuple[str, ...] = (
    "default",
    "imports",
    "pricing",
    "images",
    "comparator",
    "notifications",
    "audit",
    "scraper",
    "scraper.price_monitor",  # EP-SCR-04 — cola dedicada monitoreo de precios
)

QUEUES: tuple[Queue, ...] = tuple(
    Queue(name, Exchange(name), routing_key=name) for name in _QUEUE_NAMES
)


def make_celery() -> Celery:
    """Construye e inicializa la Celery app — usable en producción y en tests."""
    app = Celery(
        "mt_pricing",
        broker=str(settings.CELERY_BROKER_URL),
        backend=str(settings.CELERY_RESULT_BACKEND),
        include=[
            "app.workers.tasks.imports",
            "app.workers.tasks.products",
            "app.workers.tasks.pricing",
            "app.workers.tasks.images",
            "app.workers.tasks.comparator",
            "app.workers.tasks.notifications",
            "app.workers.tasks.audit",
            # S4 — graphrag CDC processor (US-RND-01-11)
            "app.workers.tasks.graphrag",
            # S5 — calibrator nightly retrain (US-1A-09-07)
            "app.workers.tasks.calibrator",
            # S5 — pricing engine bulk-recalc nocturno (US-1B-01-07)
            "app.workers.tasks.pricing_recalc",
            # S6 — pricing escalation pending_review > 48h (US-1B-02-08)
            "app.workers.escalation",
            # S7 — last-known-good exports snapshot diario (US-1B-04-05)
            "app.workers.export_jobs",
            # Observabilidad: heartbeat publisher (signal + task periódica)
            "app.workers.heartbeat",
            # Mantenimiento DB: particiones audit_events (R-S2-08, US-1A-07-01)
            "app.workers.audit_partitions",
            # S2 — image pipeline (US-1A-02-07/08, ADR-055)
            "app.workers.probe_mirror",
            "app.workers.thumbnails",
            # F15-03-02 — embedding fine-tune ML task
            "app.workers.tasks.ml_finetuning",
            # EP-INV-01 — MAP Engine (US-INV-01-02)
            "app.workers.tasks.inventory",
            # EP-INV-01 — ERP outbox processor (US-INV-01-07)
            "app.workers.tasks.erp_sync",
            # EP-ERP-03 — Procurement P2P timeout escalation (US-ERP-03-02)
            "app.workers.tasks.procurement",
            # EP-ERP-04 — Ventas O2C backorders re-evaluation
            "app.workers.tasks.sales",
            # EP-ERP-05 — Billing dunning + alertas entrega (US-ERP-05-03/05/06)
            "app.workers.tasks.billing",
            # EP-ERP-06 — Finanzas: FX reval, period close, price variance (US-ERP-06-01..09)
            "app.workers.tasks.finance",
            # EP-SCR-01 — Scraper Amazon UAE (batch scraping semanal)
            "app.workers.tasks.scraper",
            # EP-SCR-04 — Price monitor tasks (US-SCR-04-02/03)
            "app.workers.tasks.price_monitor",
            # Silver layer — re-matching periódico del candidate pool
            "app.workers.tasks.rematch_pool",
            # Rule Engine — análisis periódico de performance + sugerencias IA
            "app.workers.tasks.rule_engine_analyzer",
        ],
    )

    app.conf.update(
        # --- Serialization ---
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        # --- Timezone (MT Asia/Dubai) ---
        timezone=settings.TIMEZONE,
        enable_utc=True,
        # --- Reliability ---
        broker_connection_retry_on_startup=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # --- Limits ---
        task_time_limit=600,
        task_soft_time_limit=540,
        result_expires=60 * 60 * 24,  # 24h
        # --- Topology ---
        task_queues=QUEUES,
        task_default_queue="default",
        task_default_exchange="default",
        task_default_routing_key="default",
        task_routes={
            "mt.imports.*": {"queue": "imports"},
            "mt.products.*": {"queue": "imports"},
            "mt.pricing.*": {"queue": "pricing"},
            "mt.images.*": {"queue": "images"},
            "mt.comparator.*": {"queue": "comparator"},
            "mt.notifications.*": {"queue": "notifications"},
            "mt.audit.*": {"queue": "audit"},
            "mt.graphrag.*": {"queue": "comparator"},
            "mt.calibrator.*": {"queue": "comparator"},
            "ml.*": {"queue": "comparator"},
            "mt.inventory.*": {"queue": "default"},
            "mt.scraper.*": {"queue": "scraper"},
            "mt.scraper.price_monitor": {"queue": "scraper.price_monitor"},
            "mt.scraper.bootstrap_price_monitoring": {"queue": "scraper.price_monitor"},
            "mt.scraper.refresh_price_daily_stats": {"queue": "scraper.price_monitor"},
        },
        # --- Beat (ADR-046 — scheduler custom sobre job_definitions) ---
        # All periodic tasks are defined in job_definitions (DB), not here.
        # check-approval-timeouts was moved to job_definitions in mig 20260519_148.
        beat_scheduler="app.scheduler.database_scheduler:DatabaseScheduler",
        beat_schedule={},
    )

    return app


celery_app: Celery = make_celery()
