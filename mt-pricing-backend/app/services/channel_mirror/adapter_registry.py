"""Registry/factory para los adapters de channel mirror (Sprint 4 scaffold).

Decide entre los stubs Sprint 3 y los adapters reales (SP-API real, Noon
partner API real) usando ``MT_LIVE_NETWORK``. Mismo contrato que
:mod:`app.services.matching.adapter_registry`.

Ports: :class:`app.services.channel_mirror.ports.ChannelMirrorPort`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.channel_mirror.ports import ChannelMirrorPort


_LIVE_ENV = "MT_LIVE_NETWORK"


def _live_network_enabled() -> bool:
    val = os.environ.get(_LIVE_ENV, "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


def get_channel_adapter(channel_code: str) -> ChannelMirrorPort:
    """Devuelve el adapter de canal mirror.

    Args:
        channel_code: ``amazon_uae`` o ``noon_uae``.
    """
    if channel_code == "amazon_uae":
        if _live_network_enabled():
            from app.services.channel_mirror.adapters.amazon_sp_api import (
                AmazonSPApiAdapter,
            )

            return AmazonSPApiAdapter()
        from app.services.channel_mirror.adapters.amazon_sp_api_stub import (
            AmazonSPApiStub,
        )

        return AmazonSPApiStub()

    if channel_code == "noon_uae":
        if _live_network_enabled():
            from app.services.channel_mirror.adapters.noon_real_api import (
                NoonRealApiAdapter,
            )

            return NoonRealApiAdapter()
        from app.services.channel_mirror.adapters.noon_api_stub import NoonApiStub

        return NoonApiStub()

    raise ValueError(f"Unknown channel mirror code: {channel_code!r}")


__all__ = ["get_channel_adapter"]
