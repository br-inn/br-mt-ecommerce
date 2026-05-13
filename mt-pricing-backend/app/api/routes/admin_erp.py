"""ERP Integration admin routes — US-INV-01-06.

Endpoints:
- ``GET /admin/erp/health`` — verifica conectividad con el ERP configurado.
  Requiere rol ``admin``.

Responde con el estado del adapter activo (``ERP_ADAPTER`` setting) sin
lanzar excepciones — cualquier error del adapter se captura y se retorna
como ``healthy: false`` para no interrumpir el health-check global.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.core.config import settings
from app.db.models.user import User
from app.integrations.erp.factory import get_erp_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/erp", tags=["ERP Admin"])


@router.get(
    "/health",
    summary="ERP adapter health check (admin only)",
)
async def erp_health(
    current_user: Annotated[User, Depends(require_role("admin"))],
) -> dict:
    """Retorna el estado de conectividad del ERP adapter activo.

    - ``adapter``: valor de ``ERP_ADAPTER`` (``"noop"``, ``"sap"``, ``"odoo"``).
    - ``healthy``: ``true`` si ``health_check()`` retorna ``True``.
    - ``checked_at``: timestamp ISO-8601 UTC.
    - ``error``: presente sólo si ocurre una excepción.
    """
    adapter = get_erp_adapter()
    try:
        healthy = await adapter.health_check()
        return {
            "adapter": settings.ERP_ADAPTER,
            "healthy": healthy,
            "checked_at": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ERP:health] adapter=%s error=%s", settings.ERP_ADAPTER, exc)
        return {
            "adapter": settings.ERP_ADAPTER,
            "healthy": False,
            "error": str(exc),
            "checked_at": datetime.now(UTC).isoformat(),
        }
