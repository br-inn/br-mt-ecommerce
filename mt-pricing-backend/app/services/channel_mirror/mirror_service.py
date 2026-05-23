"""MirrorService — orchestrator del Channel Mirror.

Pipeline:
1. ``sync(sku)``: pull al canal externo (via adapter) → diff vs canonical →
   persist ChannelListing + log ChannelSyncEvent(``pull`` y ``diff``).
2. ``compute_diff(sku)``: lee snapshots persistidos y devuelve la lista
   ``FieldDiff`` sin tocar canal externo (lectura barata para UI).
3. ``publish(sku, fields=None)``: empuja diferencias al canal (stub Sprint 3,
   real Sprint 4+) y loggea ``push`` event.

NO hace HTTP real — los adapters Sprint 3 son stubs canned.

Notas de diseño:
- ``MirrorService`` no conoce qué canales existen — recibe un dict
  ``adapters: dict[channel_code, ChannelMirrorPort]`` en constructor.
- Si el caller pide un canal sin adapter registrado → ``UnknownChannelError``.
- ``canonical_loader`` es un callable async ``(sku) -> dict``: permite a los
  tests inyectar canonical sin pasar por DB y al runtime tirar de la tabla
  ``products``/``product_translations``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.repositories.channel_listings import (
    ChannelListingRepository,
    ChannelSyncEventRepository,
)
from app.services.channel_mirror.diff_engine import (
    FieldDiff,
    canonical_vs_live,
    summarize,
)
from app.services.channel_mirror.ports import (
    ChannelMirrorPort,
    LiveListing,
    PublishResult,
)

CanonicalLoader = Callable[[str], Awaitable[dict[str, Any]]]


class MirrorServiceError(Exception):
    """Base error del MirrorService."""


class UnknownChannelError(MirrorServiceError):
    """Canal no registrado en el orchestrator."""


class CanonicalNotFoundError(MirrorServiceError):
    """SKU no existe en MT canonical (no podemos diff)."""


@dataclass(frozen=True)
class SyncOutcome:
    """Resultado de un ``sync()`` — combina pull + diff."""

    listing_id: str
    channel_code: str
    sku: str
    external_id: str
    diffs: list[FieldDiff]
    summary: dict[str, int]
    duration_ms: int


class MirrorService:
    """Orchestrator hexagonal del Channel Mirror."""

    def __init__(
        self,
        *,
        listings_repo: ChannelListingRepository,
        events_repo: ChannelSyncEventRepository,
        adapters: dict[str, ChannelMirrorPort],
        canonical_loader: CanonicalLoader,
    ) -> None:
        self.listings_repo = listings_repo
        self.events_repo = events_repo
        self.adapters = adapters
        self.canonical_loader = canonical_loader

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _adapter(self, channel_code: str) -> ChannelMirrorPort:
        adapter = self.adapters.get(channel_code)
        if adapter is None:
            raise UnknownChannelError(
                f"No hay adapter registrado para canal '{channel_code}'. "
                f"Disponibles: {sorted(self.adapters.keys())}"
            )
        return adapter

    async def _load_canonical(self, sku: str) -> dict[str, Any]:
        canonical = await self.canonical_loader(sku)
        if not canonical:
            raise CanonicalNotFoundError(
                f"SKU '{sku}' no existe en MT canonical (canonical_loader vacío)."
            )
        return canonical

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def sync(
        self,
        channel_code: str,
        sku: str,
        *,
        external_id: str | None = None,
        queued_fields: set[str] | None = None,
    ) -> SyncOutcome:
        """Pull del canal → diff → persist + log."""
        adapter = self._adapter(channel_code)
        canonical = await self._load_canonical(sku)

        t0 = time.perf_counter()
        live: LiveListing = await adapter.pull_listing(sku, external_id=external_id)
        pull_duration = int((time.perf_counter() - t0) * 1000)

        await self.events_repo.log(
            channel_code=channel_code,
            event_type="pull",
            ok=True,
            product_sku=sku,
            summary=f"pull {channel_code} sku={sku} fields={len(live.fields)}",
            payload={
                "external_id": live.external_id,
                "fields_count": len(live.fields),
            },
            duration_ms=pull_duration,
        )

        diffs = canonical_vs_live(
            canonical=canonical,
            live=live.fields,
            queued_fields=queued_fields,
        )
        diff_summary = summarize(diffs)

        listing = await self.listings_repo.upsert(
            channel_code=channel_code,
            product_sku=sku,
            external_id=live.external_id,
            canonical_snapshot=canonical,
            live_snapshot=live.fields,
            diff_summary=diff_summary,
            buybox_state=live.buybox_state,
            buybox_pct_7d=live.buybox_pct_7d,
            stock_qty=live.stock_qty,
            rating=live.rating,
            reviews_count=live.reviews_count,
            last_sync_at=live.fetched_at or datetime.now(tz=UTC),
        )

        total_duration = int((time.perf_counter() - t0) * 1000)
        await self.events_repo.log(
            channel_code=channel_code,
            event_type="diff",
            ok=True,
            product_sku=sku,
            summary=(
                f"diff {channel_code} sku={sku} "
                f"match={diff_summary['match']} drift={diff_summary['drift']} "
                f"missing={diff_summary['missing']} queued={diff_summary['queued']}"
            ),
            payload={"summary": diff_summary},
            duration_ms=total_duration - pull_duration,
        )

        return SyncOutcome(
            listing_id=str(listing.id),
            channel_code=channel_code,
            sku=sku,
            external_id=live.external_id,
            diffs=diffs,
            summary=diff_summary,
            duration_ms=total_duration,
        )

    async def compute_diff(
        self,
        channel_code: str,
        sku: str,
        *,
        queued_fields: set[str] | None = None,
    ) -> tuple[list[FieldDiff], dict[str, int]]:
        """Lectura: usa snapshots persistidos (no toca canal externo).

        Si no hay listing aún, lanza ``CanonicalNotFoundError`` para que el
        caller (route) responda 404. Esto evita un pull involuntario en el
        endpoint de diff (que es solo lectura por contrato del frontend).
        """
        listing = await self.listings_repo.get_by_channel_sku(channel_code, sku)
        if listing is None:
            raise CanonicalNotFoundError(
                f"No hay listing sincronizado para channel='{channel_code}' sku='{sku}'. "
                "Ejecuta POST /sync primero."
            )
        diffs = canonical_vs_live(
            canonical=listing.canonical_snapshot_jsonb,
            live=listing.live_snapshot_jsonb,
            queued_fields=queued_fields,
        )
        return diffs, summarize(diffs)

    async def publish(
        self,
        channel_code: str,
        sku: str,
        *,
        fields: list[str] | None = None,
    ) -> PublishResult:
        """Empuja diferencias al canal (stub Sprint 3 → solo persiste intento)."""
        adapter = self._adapter(channel_code)
        listing = await self.listings_repo.get_by_channel_sku(channel_code, sku)
        if listing is None:
            raise CanonicalNotFoundError(
                f"Sin listing previo para sku='{sku}' channel='{channel_code}'."
            )

        canonical = listing.canonical_snapshot_jsonb
        if fields:
            payload = {f: canonical.get(f) for f in fields}
        else:
            # Default: empujamos todos los campos canonical (deja al adapter
            # decidir qué soporta). El stub acepta todo.
            payload = dict(canonical)

        t0 = time.perf_counter()
        result = await adapter.push_diff(
            sku=sku,
            external_id=listing.external_id,
            diff_payload=payload,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)

        await self.events_repo.log(
            channel_code=channel_code,
            event_type="push",
            ok=result.ok,
            product_sku=sku,
            summary=(
                f"push {channel_code} sku={sku} "
                f"submitted={len(payload)} accepted={len(result.accepted_fields)} "
                f"rejected={len(result.rejected_fields)}"
            ),
            payload={
                "submission_id": result.submission_id,
                "accepted_fields": result.accepted_fields,
                "rejected_fields": result.rejected_fields,
                "stub_message": result.message,
            },
            duration_ms=duration_ms,
        )
        return result


__all__ = [
    "CanonicalLoader",
    "CanonicalNotFoundError",
    "MirrorService",
    "MirrorServiceError",
    "SyncOutcome",
    "UnknownChannelError",
]
