"""Sentry SDK init — FastAPI + Celery integrations + PII redaction.

Idempotente: si `SENTRY_DSN` está vacío (dev/local), se salta init y queda no-op.
PII redaction: hook `before_send` reemplaza valores de claves sensibles antes
de salir hacia Sentry.
"""

from __future__ import annotations

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "jwt",
        "api_key",
        "authorization",
        "cookie",
    }
)


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Redacta headers/body sensibles antes de enviar a Sentry."""
    request = event.get("request") or {}
    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in _SENSITIVE_KEYS:
                headers[key] = "***REDACTED***"
    # extra/contexts
    for ctx in event.get("extra", {}).values() if isinstance(event.get("extra"), dict) else []:
        if isinstance(ctx, dict):
            for k in list(ctx.keys()):
                if k.lower() in _SENSITIVE_KEYS:
                    ctx[k] = "***REDACTED***"
    return event


def configure_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENV,
        release=settings.APP_VERSION,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            CeleryIntegration(monitor_beat_tasks=True),
            SqlalchemyIntegration(),
            AsyncioIntegration(),
        ],
        before_send=_scrub,
    )
