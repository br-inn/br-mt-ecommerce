"""Better Stack HTTP log handler con redacción PII (US-1A-OBS-01, ADR-077).

Diseño:
- `BetterStackHandler` — `logging.Handler` que bufferiza records y los envía via
  POST HTTPS a la sink Better Stack (`https://in.logs.betterstack.com`).
- Buffer: 50 records o 5s, lo que ocurra primero (fire-and-forget thread).
- Redacción PII: cualquier `extra` con clave en `_REDACTED_KEYS` se reemplaza
  por `***REDACTED***` ANTES de enviar.
- Si `BETTER_STACK_LOGS_TOKEN` está vacío (dev/local), el `attach` es no-op.

Nota: en Sprint 5 NO conectamos a Better Stack real (Doppler secret pendiente).
El handler está listo para activarse con sólo seedear el secret.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any

import httpx

from app.core.config import settings

# Misma lista que app/core/logging.py — duplicada aquí para mantener este módulo
# auto-contenido (no importa structlog runtime).
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

DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0
DEFAULT_BUFFER_SIZE = 50
DEFAULT_HTTP_TIMEOUT_SECONDS = 5.0


def _redact(value: Any) -> Any:
    """Redacta valores en dicts/lists recursivamente."""
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if k.lower() in _REDACTED_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _record_to_payload(record: logging.LogRecord) -> dict[str, Any]:
    """Serializa un LogRecord a JSON-friendly dict con redacción PII."""
    payload: dict[str, Any] = {
        "dt": record.created,
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    # Atributos custom inyectados via `logger.info(..., extra={...})`.
    standard = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
    for key, value in record.__dict__.items():
        if key in standard:
            continue
        if key.startswith("_"):
            continue
        if key.lower() in _REDACTED_KEYS:
            payload[key] = "***REDACTED***"
        else:
            payload[key] = _redact(value)
    if record.exc_info:
        payload["exc_info"] = logging.Formatter().formatException(record.exc_info)
    return payload


class BetterStackHandler(logging.Handler):
    """Buffering HTTP handler para Better Stack `https://in.logs.betterstack.com`.

    Args:
        token: Source token Better Stack (obligatorio, sino el handler queda
            inutilizable y `emit` simplemente descarta).
        host: Host alternativo (EU/US) — Better Stack provee dos endpoints.
        buffer_size: máx records en buffer antes de flush.
        flush_interval: segundos entre flushes background.
        client: httpx.Client opcional (inyectable para tests).
    """

    def __init__(
        self,
        token: str,
        host: str = "https://in.logs.betterstack.com",
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__()
        self._token = token
        self._host = host.rstrip("/")
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=buffer_size * 4)
        self._client = client or httpx.Client(timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)
        self._stop_event = threading.Event()
        self._owns_client = client is None
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        """Arranca el worker thread. Idempotente."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._run_worker,
            name="better-stack-flush",
            daemon=True,
        )
        self._worker.start()

    def emit(self, record: logging.LogRecord) -> None:
        """Convierte record a payload y lo encola. Nunca raise."""
        if not self._token:
            return
        try:
            payload = _record_to_payload(record)
            self._queue.put_nowait(payload)
        except queue.Full:
            # buffer full: drop silently — alarma se sube via Sentry si crítico
            pass
        except Exception:  # pragma: no cover — defensive, never crash logging
            self.handleError(record)

    def flush(self) -> None:
        """Drena el buffer ahora — útil para tests."""
        batch = self._drain()
        if batch:
            self._send(batch)

    def close(self) -> None:
        """Detiene worker y dispara flush final."""
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
        try:
            self.flush()
        finally:
            if self._owns_client:
                try:
                    self._client.close()
                except Exception:
                    pass
            super().close()

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------
    def _drain(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while len(items) < self._buffer_size:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def _send(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        try:
            self._client.post(
                self._host,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(batch),
            )
        except Exception:  # pragma: no cover — best-effort, no crash app
            pass

    def _run_worker(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(self._flush_interval)
            try:
                self.flush()
            except Exception:  # pragma: no cover
                pass


def attach_better_stack_handler() -> BetterStackHandler | None:
    """Crea y monta el handler Better Stack al root logger.

    No-op (devuelve None) si `BETTER_STACK_LOGS_TOKEN` está vacío.
    """
    token = getattr(settings, "BETTER_STACK_LOGS_TOKEN", "") or ""
    if not token:
        return None

    host = getattr(settings, "BETTER_STACK_LOGS_HOST", "") or "https://in.logs.betterstack.com"
    handler = BetterStackHandler(token=token, host=host)
    handler.setLevel(logging.INFO)
    handler.start()
    logging.getLogger().addHandler(handler)
    return handler
