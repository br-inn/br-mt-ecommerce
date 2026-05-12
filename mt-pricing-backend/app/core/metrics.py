"""Prometheus instrumentation — base + métricas custom de negocio (ADR-047).

Expone:
- `/metrics` — endpoint estándar para scraper Prometheus.
- Métricas HTTP automáticas (latencia, throughput por endpoint, status codes).
- Métricas de negocio MT específicas (precios aprobados, comparator confidence,
  duración de import runs).

`/metrics` queda EXCLUIDO del schema OpenAPI para no contaminar la doc pública.
Healthcheck endpoints también excluidos del scrape (no son interesantes para
SRE — generan ruido en latency histograms).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

if TYPE_CHECKING:
    from fastapi import FastAPI


# =============================================================================
# Métricas custom de negocio — namespace `mt_*`
# =============================================================================
prices_auto_approved = Counter(
    "mt_prices_auto_approved_total",
    "Precios aprobados automáticamente (no requirieron revisión humana).",
    labelnames=("channel", "scheme"),
)

prices_pending_review = Counter(
    "mt_prices_pending_review_total",
    "Precios que entraron en estado pending_review (requieren aprobación).",
    labelnames=("reason",),
)

import_runs_duration = Histogram(
    "mt_import_runs_duration_seconds",
    "Duración total de cada import run (DOL/Sage/manual).",
    labelnames=("import_type",),
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800),
)

comparator_match_confidence = Histogram(
    "mt_comparator_match_confidence",
    "Distribución de confidence de matches del comparator IA.",
    buckets=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0),
)

celery_task_duration = Histogram(
    "mt_celery_task_duration_seconds",
    "Duración de tasks Celery por queue/task_name.",
    labelnames=("queue", "task_name"),
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 300, 600),
)

price_sanity_rejections_total = Counter(
    "price_sanity_rejections_total",
    "Candidatos rechazados por price sanity check",
    ["reason"],  # labels: price_too_low, price_too_high
)


# =============================================================================
# Setup — llamar desde main.py tras crear la app
# =============================================================================
def setup_metrics(app: FastAPI) -> Instrumentator:
    """Instrumenta la FastAPI app y expone `/metrics`."""
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/health/.*", "/metrics"],
        env_var_name="PROMETHEUS_ENABLED",
    )
    instrumentator.instrument(app)
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)
    return instrumentator
