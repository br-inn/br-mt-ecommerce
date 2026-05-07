"""Global kill-switch — atomic override sobre toda la familia ``MT_LIVE_NETWORK_*``.

US-1A-09-08 (Sprint 5).

Diseño:
- Bandera in-process atomica + persistencia en ``feature_flags`` (key
  ``KILL_SWITCH``). Cuando está engaged, ningún flag de red real se considera
  active — ``flag_service.is_live_network_enabled()`` devuelve False
  inmediatamente sin tocar Redis ni DB.
- Engage es síncrono y O(1) — se usa en hot-path de adapter registries y
  workers. No depende de Redis (defensa en profundidad ante caída Redis).
- Mecanismo de sync cross-worker (DB + Redis pub/sub) está documentado
  en ADR-072 — la implementación S5 sólo bombardea cache Redis y refresca
  on-next-touch (TTL 60s). En incidente operativo, redeploy + RESET via
  endpoint admin garantiza propagación instantánea.

API:
- :func:`engage` / :func:`disengage` / :func:`is_kill_switch_engaged` — sync.
- :class:`KillSwitch` wrapper persistente que combina memoria + DB
  (delegando en ``FlagService`` para audit + propagación).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.services.feature_flags.flag_service import FlagService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-process atomic flag — se evalúa en cada lookup sin IO
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()
_engaged = False


def is_kill_switch_engaged() -> bool:
    """Lookup atómico O(1) sin IO. Hot-path para registries / workers."""
    return _engaged


def engage() -> None:
    """Set in-process kill-switch (NO persiste; tests usan esto)."""
    global _engaged
    with _state_lock:
        _engaged = True
    logger.warning("kill_switch.engaged_in_memory")


def disengage() -> None:
    """Reset in-process kill-switch (NO persiste; tests + recovery usan esto)."""
    global _engaged
    with _state_lock:
        _engaged = False
    logger.info("kill_switch.disengaged_in_memory")


def reset() -> None:
    """Alias para teardown de tests."""
    disengage()


# ---------------------------------------------------------------------------
# Persistent wrapper — combina memoria + DB via FlagService
# ---------------------------------------------------------------------------
class KillSwitchEngaged(Exception):
    """Lanzada por endpoints/services cuando se intenta llamar a red real
    con kill-switch active. Mappable a HTTP 503 en routes."""

    def __init__(self, message: str = "Kill-switch engaged — live network blocked") -> None:
        super().__init__(message)


class KillSwitch:
    """Wrapper sobre :class:`FlagService` que actúa el global kill-switch.

    En vez de llamar ``flag_service.set_flag('KILL_SWITCH', True)`` los
    callers usan esta clase, que mantiene el flag persistente + el toggle
    in-memory consistentes y emite un audit event explícito.
    """

    def __init__(self, flag_service: FlagService) -> None:
        self.flag_service = flag_service

    async def engage(
        self,
        *,
        updated_by: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Set en DB + cache + memoria. Sync cross-worker via Redis cache."""
        from app.services.feature_flags.flag_service import (
            FLAG_KILL_SWITCH,
            set_local_flag,
        )

        await self.flag_service.set_flag(
            FLAG_KILL_SWITCH, True, updated_by=updated_by
        )
        engage()  # in-memory sync
        set_local_flag(FLAG_KILL_SWITCH, True)
        logger.warning(
            "kill_switch.engaged",
            extra={"updated_by": str(updated_by), "reason": reason},
        )

    async def disengage(
        self,
        *,
        updated_by: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        from app.services.feature_flags.flag_service import (
            FLAG_KILL_SWITCH,
            set_local_flag,
        )

        await self.flag_service.set_flag(
            FLAG_KILL_SWITCH, False, updated_by=updated_by
        )
        disengage()
        set_local_flag(FLAG_KILL_SWITCH, False)
        logger.info(
            "kill_switch.disengaged",
            extra={"updated_by": str(updated_by), "reason": reason},
        )

    async def hydrate_from_db(self) -> None:
        """Lee el estado actual de DB y sincroniza memoria.

        Llamar en lifespan startup. Si DB dice ``KILL_SWITCH=true`` el
        proceso arranca con el toggle engaged.
        """
        from app.services.feature_flags.flag_service import FLAG_KILL_SWITCH

        try:
            value = await self.flag_service.is_enabled(FLAG_KILL_SWITCH)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "kill_switch.hydrate_failed",
                extra={"error": str(exc)},
            )
            return
        if value:
            engage()
        else:
            disengage()


__all__ = [
    "KillSwitch",
    "KillSwitchEngaged",
    "disengage",
    "engage",
    "is_kill_switch_engaged",
    "reset",
]
