"""Re-export del SSRF guard desde `app.services.ssrf`.

Las tasks Celery quieren importar desde `app.workers.ssrf` para mantener
cohesión visual con el resto de tasks de imagen. La lógica vive en
`app.services.ssrf` para que las routes HTTP también puedan importarla
(rechazo temprano antes de encolar la task).

Ref: ADR-055.
"""

from __future__ import annotations

from app.services.ssrf import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_SCHEMES,
    FetchResult,
    SSRFViolation,
    safe_fetch_image,
    validate_url,
)

__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "ALLOWED_SCHEMES",
    "FetchResult",
    "SSRFViolation",
    "safe_fetch_image",
    "validate_url",
]
