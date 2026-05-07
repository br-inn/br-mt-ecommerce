"""Channel Mirror — Sprint 3 fundación.

Sincronía MT canonical ↔ canales externos (Amazon UAE / Noon UAE).

Arquitectura hexagonal:
- ``ports.ChannelMirrorPort`` — interfaz que define qué necesita el orchestrator
  de un adapter de canal externo. Cada canal implementa este puerto.
- ``adapters/`` — implementaciones concretas (stubs Sprint 3, HTTP real Sprint 4+).
- ``diff_engine.canonical_vs_live`` — pure function field-by-field comparator.
- ``mirror_service.MirrorService`` — orchestrator (pull → diff → persist; push stub).

NO hace HTTP real en Sprint 3 — los adapters devuelven canned data.
"""

from __future__ import annotations

from app.services.channel_mirror.diff_engine import (
    DIFF_STATUS_DRIFT,
    DIFF_STATUS_MATCH,
    DIFF_STATUS_MISSING,
    DIFF_STATUS_QUEUED,
    FieldDiff,
    canonical_vs_live,
)
from app.services.channel_mirror.mirror_service import MirrorService
from app.services.channel_mirror.ports import (
    ChannelMirrorPort,
    LiveListing,
    PublishResult,
)

__all__ = [
    "DIFF_STATUS_DRIFT",
    "DIFF_STATUS_MATCH",
    "DIFF_STATUS_MISSING",
    "DIFF_STATUS_QUEUED",
    "ChannelMirrorPort",
    "FieldDiff",
    "LiveListing",
    "MirrorService",
    "PublishResult",
    "canonical_vs_live",
]
