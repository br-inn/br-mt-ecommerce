"""Feature flag service — runtime toggles backed by ``feature_flags`` table.

US-1A-09-08 (Sprint 5) — plumbing para ``MT_LIVE_NETWORK`` y kill-switch global.

Diseño:
- :class:`FlagService` lee/escribe ``feature_flags`` con cache Redis 60s TTL.
- :func:`is_enabled` es la API hot-path (lookup cacheado).
- :class:`KillSwitch` capa adicional: si ``KILL_SWITCH`` está ``true`` corta
  toda la familia ``MT_LIVE_NETWORK_*`` independientemente del valor del flag
  individual (defensa en profundidad ante incidente).
- :func:`set_flag` audita ``updated_by`` + ``updated_at`` y bombardea cache
  Redis para propagación cross-worker.

Sin red real — sólo plumbing: los adapter registries empezarán a leer de aquí
en lugar de ``os.getenv("MT_LIVE_NETWORK")``.
"""

from __future__ import annotations

from app.services.feature_flags.flag_service import (
    FlagService,
    is_enabled,
    is_live_network_enabled,
)
from app.services.feature_flags.kill_switch import (
    KillSwitch,
    KillSwitchEngaged,
    is_kill_switch_engaged,
)

__all__ = [
    "FlagService",
    "KillSwitch",
    "KillSwitchEngaged",
    "is_enabled",
    "is_kill_switch_engaged",
    "is_live_network_enabled",
]
