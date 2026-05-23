"""ForceLogoutPublisher — emite evento Realtime para deslogueo inmediato (ADR-032).

Cuando TI Integración revoca un rol o ejecuta `force_logout`, además de invalidar
las sessions en Supabase Auth (vía `auth.admin.sign_out`) necesitamos que la
aplicación SPA del usuario afectado se desloguee inmediatamente sin esperar al
TTL del JWT (1h). Para eso publicamos un row en `force_logout_events` que tiene
publication enabled para Supabase Realtime.

Diseño:
- **Tabla cola**: `public.force_logout_events` con publication `supabase_realtime`.
- **Filter por user**: cada cliente sólo recibe los suyos vía RLS + filter
  Realtime (`user_id=eq.<self>`).
- **Fail-soft**: si la inserción falla (Supabase abajo, network), el JWT
  eventualmente expira en TTL → no rompemos la operación.
- **Cleanup**: filas > 24h se borran via Celery task
  `mt.audit.cleanup_force_logout_events` (cron diario 03:00).

API: `await publisher.publish(user_id, reason, actor_id)` — silencioso en fallo.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.supabase import get_supabase_admin

logger = logging.getLogger(__name__)


class ForceLogoutPublisher:
    """Publica evento `force_logout` al canal Supabase Realtime.

    Usa el cliente service_role (bypass RLS) para insertar en
    `force_logout_events`. La inserción dispara un evento Realtime
    `INSERT` que el frontend del usuario afectado consume desde
    `AuthProvider` para disparar `signOut` local.
    """

    TABLE = "force_logout_events"

    async def publish(
        self,
        user_id: UUID,
        reason: str,
        actor_id: UUID | None = None,
    ) -> bool:
        """Inserta evento de force-logout. Devuelve True si OK, False en fallo.

        Fail-soft — un fallo NO levanta excepción ni rompe la transacción
        del caller. El JWT expira en TTL aunque Realtime se pierda.
        """
        try:
            client = get_supabase_admin()
        except Exception:
            logger.exception("ForceLogoutPublisher: no se pudo obtener admin client")
            return False

        payload: dict[str, Any] = {
            "user_id": str(user_id),
            "reason": reason,
            "actor_id": str(actor_id) if actor_id else None,
        }
        try:
            # supabase-py 2.x: `.table().insert().execute()` síncrono. El SDK
            # no expone API async todavía; al ser un solo INSERT lo dejamos
            # bloqueante — el handler ya está awaited y el call es sub-ms en
            # path normal.
            client.table(self.TABLE).insert(payload).execute()
        except Exception:
            logger.exception("ForceLogoutPublisher fallo al insertar evento user_id=%s", user_id)
            return False
        logger.info(
            "force_logout_event.published",
            extra={"user_id": str(user_id), "actor_id": str(actor_id) if actor_id else None},
        )
        return True


# Singleton — sin estado interno, reusable en múltiples requests.
_publisher: ForceLogoutPublisher | None = None


def get_force_logout_publisher() -> ForceLogoutPublisher:
    """DI factory para FastAPI Depends."""
    global _publisher
    if _publisher is None:
        _publisher = ForceLogoutPublisher()
    return _publisher
