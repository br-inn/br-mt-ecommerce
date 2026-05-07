"""Middleware FastAPI — request_id, structlog context binding, access log.

Responsabilidades:
- Genera/lee `X-Request-ID` (UUID4 si el cliente no lo manda).
- Bindea contextvars de structlog: `request_id`, `method`, `path`, `client_ip`.
- Si el request trae `X-User-Id` (post-auth, set por dependency JWT), bindea `user_id`.
- Loguea inicio + fin de request con duración y status_code.
- Anexa `X-Request-ID` al response — los clientes pueden correlacionar logs.

NOTA: el binding usa `structlog.contextvars.bind_contextvars` (per-task) para
no contaminar otros requests concurrentes. Limpia al salir.
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

    from collections.abc import Awaitable, Callable

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware ASGI que enriquece logs con datos de cada request."""

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        client_ip = request.client.host if request.client else "unknown"

        # Bind contextvars — toda call dentro de este request los heredará.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        # `user_id` lo bindea downstream el dependency `get_current_user`
        # cuando esté implementado. Si llega por header (interno), también.
        user_header = request.headers.get("X-User-Id")
        if user_header:
            structlog.contextvars.bind_contextvars(user_id=user_header)

        # No loguea start de healthchecks — ruido innecesario.
        is_health = request.url.path.startswith("/health/")
        if not is_health:
            logger.info("request.start")

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            logger.exception("request.failed")
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            if not is_health:
                logger.info(
                    "request.end",
                    status_code=status_code,
                    duration_ms=duration_ms,
                )
            structlog.contextvars.clear_contextvars()

        response.headers["X-Request-ID"] = request_id
        return response


def install_request_context(app: ASGIApp) -> None:
    """Helper para instalar el middleware desde `main.py`."""
    # `add_middleware` espera una clase/factory, lo gestionamos en main.py.
    # Esta función queda para referencia pero no se llama.
    raise NotImplementedError("Usar app.add_middleware(RequestContextMiddleware)")
