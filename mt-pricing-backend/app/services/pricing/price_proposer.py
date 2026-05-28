"""Propose computed prices to the approval workflow.

Takes a list of SKUs + selling_model, calls the engine via ParameterLoader +
ChannelOptimizer, and inserts the resulting prices into the `prices` table
with status='pending_review'. The breakdown JSONB carries the full cost
detail for auditability.

prices table notes (verified against actual schema):
- proposed_by   : uuid  (nullable) — no current user available; stored as NULL
- breakdown     : jsonb NOT NULL, default '{}'
- valid_from    : timestamptz NOT NULL, default now()
- currency      : varchar, default 'AED'
- notes column  : does not exist — notes stored inside breakdown JSONB
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SellingModel
from app.schemas.channel_pricing import (
    ProposeSelectedItemResult,
    ProposeSelectedResult,
)
from app.services.pricing.loader import ParameterLoader
from app.services.pricing.optimizer import ChannelOptimizer


class PriceProposer:
    """Propose prices in bulk for the approval workflow."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def propose(
        self,
        channel_id: uuid.UUID,
        skus: list[str],
        selling_model: SellingModel,
        proposed_by: str | None = None,
        notes: str | None = None,
    ) -> ProposeSelectedResult:
        loader = ParameterLoader(self._session)
        route, fees, schemes = await loader.load_route_and_fees(channel_id)
        products = await loader.load_product_data(channel_id, skus=skus)
        margins = await loader.load_effective_margins(channel_id, selling_model, skus)

        items: list[ProposeSelectedItemResult] = []
        products_by_sku = {p.sku: p for p in products}

        for sku in skus:
            product = products_by_sku.get(sku)
            if product is None:
                items.append(
                    ProposeSelectedItemResult(
                        sku=sku,
                        status="skipped",
                        reason="product not found or has no channel_product_logistics",
                    )
                )
                continue

            margin = margins.get(sku, Decimal("12"))
            if selling_model == SellingModel.B2C:
                best = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, margin)
            else:
                best = ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, margin)

            if best is None or best.selling_price_aed == Decimal("Infinity"):
                items.append(
                    ProposeSelectedItemResult(
                        sku=sku,
                        status="error",
                        reason="no feasible scheme at current parameters",
                    )
                )
                continue

            price_id = uuid.uuid4()
            # scheme_code is the scheme_label (e.g. "FBA") — stored as varchar in prices
            scheme_code = best.scheme_label

            breakdown_dict = {
                **best.breakdown.to_dict(),
                "selling_model": selling_model.value,
                "fulfillment_scheme": best.fulfillment_scheme.value,
                "scheme_label": best.scheme_label,
                "ceiling_aed": str(best.ceiling_aed),
                "is_publishable": best.is_publishable,
                "signal": best.signal,
                "notes": notes,
            }

            # proposed_by is uuid in DB — NULL since no current user UUID is threaded
            # TODO: pass real user UUID once get_current_user is available in this service
            await self._session.execute(
                text("""
                    INSERT INTO prices
                        (id, product_sku, channel_id, scheme_code, currency, amount,
                         margin_pct, status, breakdown)
                    VALUES
                        (:id, :sku, :ch, :scheme_code, 'AED', :amount,
                         :margin, 'pending_review', CAST(:breakdown AS jsonb))
                """),
                {
                    "id": price_id,
                    "sku": sku,
                    "ch": channel_id,
                    "scheme_code": scheme_code,
                    "amount": float(best.selling_price_aed),
                    "margin": float(best.margin_pct),
                    "breakdown": json.dumps(breakdown_dict),
                },
            )
            items.append(
                ProposeSelectedItemResult(
                    sku=sku,
                    status="proposed",
                    price_id=price_id,
                    selling_price_aed=float(best.selling_price_aed),
                )
            )

        await self._session.commit()
        return ProposeSelectedResult(
            total_requested=len(skus),
            proposed=sum(1 for i in items if i.status == "proposed"),
            skipped=sum(1 for i in items if i.status == "skipped"),
            errors=sum(1 for i in items if i.status == "error"),
            items=items,
        )
