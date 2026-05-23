"""Adapter Amazon SP-API — STUB Sprint 3.

Devuelve listings canned por ASIN/SKU. NO hace HTTP real.

Datos hardcodeados alineados con el mockup
``mt-pricing-frontend/app/(app)/canales/amazon-uae/page.tsx`` (SKU MTV-1004,
ASIN B0CXR4M7Z9). Para SKUs no conocidos, devuelve listing vacío
(``external_id=""``) → todos los campos serán ``missing`` en el diff.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.channel_mirror.ports import LiveListing, PublishResult

# Listing canned para SKU MTV-1004 (ASIN B0CXR4M7Z9). Reproduce los campos
# del mockup exactamente para que el frontend muestre los mismos drift/match.
_CANNED_LISTINGS: dict[str, dict[str, Any]] = {
    "MTV-1004": {
        "external_id": "B0CXR4M7Z9",
        "fields": {
            "title_en": "Ball Valve PN16 DN25 Brass — MT",
            "title_ar": "",  # missing en canal
            "bullet_1": "2-piece body, full bore, BSP F/F",
            "bullet_2": "Suitable for water, ≤10 bar / 80 °C",  # drift
            "brand": "Genebre",
            "HS_code": "8481.80.81",
            "material": "Brass",  # drift (canonical: "Brass CW617N")
            "DN": "25 mm",
            "PN": "16 bar",
            "weight": "0,38 kg",
            "price_aed": "147,75 AED",
            "image_main": "amazon-cdn/.../71kQ_…",
            "image_4 (AR)": "",  # queued
        },
        "buybox_state": "own",
        "buybox_pct_7d": 0.87,
        "stock_qty": 312,
        "rating": 4.6,
        "reviews_count": 184,
    },
}


class AmazonSPApiStub:
    """Stub Amazon SP-API. Implementa ``ChannelMirrorPort`` (structural)."""

    channel_code: str = "amazon_uae"

    async def pull_listing(self, sku: str, external_id: str | None = None) -> LiveListing:
        canned = _CANNED_LISTINGS.get(sku)
        if canned is None:
            # SKU desconocido → listing inexistente.
            return LiveListing(
                channel_code=self.channel_code,
                external_id=external_id or "",
                sku=sku,
                fields={},
                buybox_state="none",
                fetched_at=datetime.now(tz=UTC),
                raw={"stub": True, "reason": "sku_not_found_in_canned"},
            )
        return LiveListing(
            channel_code=self.channel_code,
            external_id=canned["external_id"],
            sku=sku,
            fields=dict(canned["fields"]),
            buybox_state=canned["buybox_state"],
            buybox_pct_7d=canned["buybox_pct_7d"],
            stock_qty=canned["stock_qty"],
            rating=canned["rating"],
            reviews_count=canned["reviews_count"],
            fetched_at=datetime.now(tz=UTC),
            raw={"stub": True, "asin": canned["external_id"]},
        )

    async def push_diff(
        self,
        sku: str,
        external_id: str | None,
        diff_payload: dict[str, Any],
    ) -> PublishResult:
        # Stub: aceptamos todo lo que venga; en Sprint 4+ el adapter real
        # llamará a SP-API submitListings y hará polling del feedId.
        accepted = list(diff_payload.keys())
        return PublishResult(
            ok=True,
            submission_id=f"sp_stub_{sku}",
            accepted_fields=accepted,
            rejected_fields=[],
            message="stub: persisted intent only, no HTTP call",
            raw={"stub": True, "diff_payload_keys": accepted},
        )
