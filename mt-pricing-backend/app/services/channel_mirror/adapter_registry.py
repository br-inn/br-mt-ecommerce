"""Registry/factory para los adapters de channel mirror (Sprint 4 → Sprint 5).

Decide entre los stubs Sprint 3 y los adapters reales (SP-API real, Noon
partner API real). En Sprint 5 (US-1A-09-08) usamos
:mod:`app.services.feature_flags.flag_service` para leer flags por canal.
Mismo contrato que :mod:`app.services.matching.adapter_registry`.

Kill-switch global: :func:`is_kill_switch_engaged` overridea siempre.

Ports: :class:`app.services.channel_mirror.ports.ChannelMirrorPort`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.services.feature_flags.flag_service import (
    FLAG_LIVE_NETWORK_NOON_API,
    FLAG_LIVE_NETWORK_SP_API,
    get_default_service,
    is_enabled,
)
from app.services.feature_flags.kill_switch import is_kill_switch_engaged

if TYPE_CHECKING:
    from app.services.channel_mirror.ports import ChannelMirrorPort


_LIVE_ENV = "MT_LIVE_NETWORK"


def _env_fallback_enabled() -> bool:
    val = os.environ.get(_LIVE_ENV, "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _live_for(flag_key: str) -> bool:
    if is_kill_switch_engaged():
        return False
    if get_default_service() is not None:
        return is_enabled(flag_key)
    return _env_fallback_enabled()


def get_channel_adapter(channel_code: str) -> ChannelMirrorPort:
    """Devuelve el adapter de canal mirror.

    Args:
        channel_code: ``amazon_uae`` o ``noon_uae``.
    """
    if channel_code == "amazon_uae":
        if _live_for(FLAG_LIVE_NETWORK_SP_API):
            from app.services.channel_mirror.adapters.amazon_sp_api import (
                AmazonSPApiAdapter,
            )

            return AmazonSPApiAdapter()
        from app.services.channel_mirror.adapters.amazon_sp_api_stub import (
            AmazonSPApiStub,
        )

        return AmazonSPApiStub()

    if channel_code == "noon_uae":
        if _live_for(FLAG_LIVE_NETWORK_NOON_API):
            from app.services.channel_mirror.adapters.noon_real_api import (
                NoonRealApiAdapter,
            )

            return NoonRealApiAdapter()
        from app.services.channel_mirror.adapters.noon_api_stub import NoonApiStub

        return NoonApiStub()

    raise ValueError(f"Unknown channel mirror code: {channel_code!r}")


__all__ = ["get_channel_adapter"]
