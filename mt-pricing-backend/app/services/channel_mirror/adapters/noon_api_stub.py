"""Adapter Noon UAE Partner API — STUB Sprint 3.

Mismo contrato que ``AmazonSPApiStub``, datos canned distintos para el
canal Noon. Sprint 4+ → implementación real.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.channel_mirror.ports import LiveListing, PublishResult


_CANNED_LISTINGS: dict[str, dict[str, Any]] = {
    "MTV-1004": {
        "external_id": "N0ON-MTV1004",
        "fields": {
            "title_en": "Ball Valve PN16 DN25 - Brass",
            "title_ar": "صمام كروي PN16",  # parcial vs canonical (drift)
            "bullet_1": "2-piece body, full bore, BSP F/F",
            "bullet_2": "≤16 bar / 80 °C",
            "brand": "Genebre",
            "HS_code": "8481.80.81",
            "material": "Brass CW617N",
            "DN": "25 mm",
            "PN": "16 bar",
            "weight": "0,38 kg",
            "price_aed": "149,00 AED",  # drift
            "image_main": "noon-cdn/.../mtv1004_main.jpg",
            "image_4 (AR)": "",
        },
        "buybox_state": "competitor",
        "buybox_pct_7d": 0.42,
        "stock_qty": 78,
        "rating": 4.3,
        "reviews_count": 22,
    },
}


class NoonApiStub:
    """Stub Noon partner API. Implementa ``ChannelMirrorPort`` (structural)."""

    channel_code: str = "noon_uae"

    async def pull_listing(
        self, sku: str, external_id: str | None = None
    ) -> LiveListing:
        canned = _CANNED_LISTINGS.get(sku)
        if canned is None:
            return LiveListing(
                channel_code=self.channel_code,
                external_id=external_id or "",
                sku=sku,
                fields={},
                buybox_state="none",
                fetched_at=datetime.now(tz=timezone.utc),
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
            fetched_at=datetime.now(tz=timezone.utc),
            raw={"stub": True, "noon_id": canned["external_id"]},
        )

    async def push_diff(
        self,
        sku: str,
        external_id: str | None,
        diff_payload: dict[str, Any],
    ) -> PublishResult:
        accepted = list(diff_payload.keys())
        return PublishResult(
            ok=True,
            submission_id=f"noon_stub_{sku}",
            accepted_fields=accepted,
            rejected_fields=[],
            message="stub: persisted intent only, no HTTP call",
            raw={"stub": True, "diff_payload_keys": accepted},
        )
