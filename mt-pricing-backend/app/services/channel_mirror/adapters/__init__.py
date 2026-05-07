"""Adapters concretos del puerto ``ChannelMirrorPort``.

Sprint 3 — todos son stubs con datos canned, sin HTTP real.
Sprint 4+ — se sustituyen por implementaciones HTTP (SP-API / Noon partner API)
sin tocar ``MirrorService`` ni los routes (hexagonal architecture).
"""

from __future__ import annotations

from app.services.channel_mirror.adapters.amazon_sp_api_stub import AmazonSPApiStub
from app.services.channel_mirror.adapters.noon_api_stub import NoonApiStub

__all__ = [
    "AmazonSPApiStub",
    "NoonApiStub",
]
