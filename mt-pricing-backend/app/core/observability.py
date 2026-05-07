"""Observability wiring — Sentry traces + structured logs + propagation IDs.

Composición end-to-end (US-1A-OBS-01, ADR-077):

- `configure_observability()` — punto de entrada idempotente que invoca el bootstrap
  de logging (`app.core.logging.configure_logging`), Sentry (`app.core.sentry.configure_sentry`)
  y agrega el handler Better Stack (`app.core.log_handlers.attach_better_stack_handler`).
- `bind_request_context()` — ayudante para el middleware de request: liga `trace_id`,
  `request_id`, `tenant`, `actor_id` al contextvars de structlog para que cada log
  emitido durante el request los incluya automáticamente.
- `current_trace_id()` — recupera el trace_id activo (fallback a UUID4 si no hay
  Sentry init).

NO toca `app/main.py` ni middleware (lo cablea Sprint 6 cuando rotemos a uvicorn).
Aquí sólo definimos las funciones; el wiring final se hará en lifespan startup.

Sample rates por defecto (override via env / Doppler):
- traces_sample_rate = 0.1 (staging) / 0.05 (prod)  — config.py
- profiles_sample_rate = 0.0 por defecto (tier paid Sentry, opt-in)

Better Stack:
- env vars `BETTER_STACK_LOGS_TOKEN` + `BETTER_STACK_LOGS_HOST`.
- Handler HTTP sink con buffering 50 lines / 5s flush.
- Si `BETTER_STACK_LOGS_TOKEN` vacío → handler no-op (dev/local).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

_OBS_INITIALIZED = False


def configure_observability() -> None:
    """Inicializa el stack completo en orden correcto.

    Orden (importa):
    1. logging — handlers stdout + ProcessorFormatter listos antes que Sentry.
    2. Sentry — engancha breadcrumbs sobre logging existente.
    3. Better Stack handler — inyectado al root logger AFTER stdout handler.
    """
    global _OBS_INITIALIZED
    if _OBS_INITIALIZED:
        return

    # 1) logging stdout pipeline
    from app.core.logging import configure_logging

    configure_logging()

    # 2) Sentry (no-op si DSN vacío)
    from app.core.sentry import configure_sentry

    configure_sentry()

    # 3) Better Stack handler (no-op si token vacío)
    from app.core.log_handlers import attach_better_stack_handler

    attach_better_stack_handler()

    _OBS_INITIALIZED = True
    logger.info(
        "observability.configured",
        sentry_enabled=bool(settings.SENTRY_DSN),
        better_stack_enabled=bool(getattr(settings, "BETTER_STACK_LOGS_TOKEN", "")),
        environment=settings.ENV,
    )


def reset_observability_state_for_tests() -> None:
    """Idempotency reset — sólo para tests."""
    global _OBS_INITIALIZED
    _OBS_INITIALIZED = False


def bind_request_context(
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
    tenant: str | None = None,
    actor_id: str | None = None,
    **extra: Any,
) -> dict[str, str]:
    """Liga IDs al contextvars de structlog y devuelve dict aplicado.

    Llamar al inicio de cada request en middleware. Limpiar con
    `structlog.contextvars.clear_contextvars()` al final.
    """
    bound: dict[str, str] = {}
    if request_id is None:
        request_id = uuid.uuid4().hex
    bound["request_id"] = request_id

    if trace_id is None:
        trace_id = current_trace_id()
    bound["trace_id"] = trace_id

    if tenant:
        bound["tenant"] = tenant
    if actor_id:
        bound["actor_id"] = actor_id
    for key, value in extra.items():
        if value is None:
            continue
        bound[key] = str(value)

    structlog.contextvars.bind_contextvars(**bound)
    return bound


def current_trace_id() -> str:
    """Devuelve el `trace_id` activo en Sentry, o un UUID4 nuevo si no hay scope."""
    try:
        import sentry_sdk

        scope = sentry_sdk.Hub.current.scope
        span = getattr(scope, "span", None)
        if span is not None:
            trace_id = getattr(span, "trace_id", None)
            if trace_id:
                return str(trace_id)
        # Fallback: si hay transaction sin span activo todavía
        transaction = getattr(scope, "transaction", None)
        if transaction is not None:
            trace_id = getattr(transaction, "trace_id", None)
            if trace_id:
                return str(trace_id)
    except Exception:  # pragma: no cover — defensive
        pass
    return uuid.uuid4().hex


def emit_breadcrumb(category: str, message: str, **data: Any) -> None:
    """Emite breadcrumb Sentry — no-op si SDK no está init."""
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category=category,
            message=message,
            level="info",
            data=data,
        )
    except Exception:  # pragma: no cover
        logger.debug("breadcrumb.emit_failed", category=category, message=message)


def root_logger_handler_count() -> int:
    """Helper para tests — verifica que se montó al menos 1 handler."""
    return len(logging.getLogger().handlers)
