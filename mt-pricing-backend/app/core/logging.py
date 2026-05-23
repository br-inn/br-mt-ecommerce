"""Structlog setup — JSON en prod, human-readable en dev.

Convenciones (ADR-047):
- Eventos estructurados con `logger.info("event_name", **kwargs)`.
- Bind de `trace_id`, `request_id`, `user_id` desde `app.core.middleware`.
- PII redaction: ningún campo `password|token|secret|jwt|key|...` aparece nunca,
  y los emails se enmascaran (`fo***@dominio.com`).
- Stdout únicamente; el orquestador (Better Stack / Loki) recoge desde ahí.

Pipeline:
- structlog procesa el `event_dict` (incluyendo redacción).
- Lo entrega a `ProcessorFormatter` de stdlib → mismo formato/render para
  logs estructurados Y para logs foráneos (uvicorn / sqlalchemy / celery).
- Renderer final: ConsoleRenderer en dev, JSONRenderer en prod.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

# Campos que SIEMPRE se redactan si aparecen en el event_dict.
_REDACTED_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "api_key",
        "apikey",
        "service_role_key",
        "anon_key",
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-supabase-auth",
    }
)


def _mask_email(value: str) -> str:
    """Enmascara local-part de un email — preserva 2 chars + dominio."""
    if "@" not in value:
        return value
    local, domain = value.split("@", 1)
    visible = local[:2] if len(local) >= 2 else local[:1]
    return f"{visible}***@{domain}"


def _redact_pii(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Reemplaza valores de claves sensibles por `***REDACTED***`."""
    for key in list(event_dict.keys()):
        lower = key.lower()
        if lower in _REDACTED_KEYS:
            event_dict[key] = "***REDACTED***"
            continue
        if lower == "email":
            value = event_dict[key]
            if isinstance(value, str):
                event_dict[key] = _mask_email(value)
    return event_dict


def configure_logging() -> None:
    """Idempotente — llamar una vez en lifespan startup."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _redact_pii,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_dev:
        renderer: Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    # structlog → ProcessorFormatter (stdlib): un único pipeline para todo.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            # Quita campos internos antes de renderizar.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Limpia handlers previos (idempotencia + tests).
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Silencia ruido de librerías chatty en INFO.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Helper tipado — usar `logger = get_logger(__name__)` en módulos."""
    return structlog.get_logger(name)
