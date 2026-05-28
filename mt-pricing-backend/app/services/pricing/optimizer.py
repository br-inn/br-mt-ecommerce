# app/services/pricing/optimizer.py
"""ChannelOptimizer — picks best scheme + finds optimal margin.

Best = highest benefit_per_unit_aed among publishable results.
Tie-breaking: CANAL_FULL > CANAL_LASTMILE > MERCHANT_MANAGED.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.db.enums import FulfillmentScheme
from app.services.pricing.engine import PricingEngine
from app.services.pricing.schemas import (
    ChannelFees,
    PriceResult,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)

# Lower index = higher priority for tie-break
_SCHEME_PRIORITY = [
    FulfillmentScheme.CANAL_FULL,
    FulfillmentScheme.CANAL_LASTMILE,
    FulfillmentScheme.MERCHANT_MANAGED,
]


class ChannelOptimizer:
    """Find the best fulfillment scheme + margin per product."""

    @staticmethod
    def best_scheme_b2c(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margin_pct: Decimal,
    ) -> Optional[PriceResult]:
        """Return best PriceResult among available schemes at the given margin."""
        candidates = [
            PricingEngine.compute_b2c(product, route, fees, scheme, margin_pct)
            for scheme in schemes
            if scheme.is_available
        ]
        if not candidates:
            return None
        return _pick_best(candidates)

    @staticmethod
    def optimal_margin_b2c(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margin_step: Decimal = Decimal("1"),
    ) -> Optional[PriceResult]:
        """Find the maximum margin under ceiling across all schemes.

        Iterates margin from 80% down to -10% in margin_step increments.
        Returns the highest publishable margin combination.
        """
        margin = Decimal("80")
        floor = Decimal("-10")

        while margin >= floor:
            candidate = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, margin)
            if candidate and candidate.is_publishable:
                return candidate
            margin -= margin_step

        # No publishable margin found → return the least-bad at floor margin
        return ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, floor)

    @staticmethod
    def optimize_catalog_b2c(
        products: list[ProductPricingData],
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margins: dict[str, Decimal],
    ) -> list[PriceResult]:
        """Compute best scheme per product at its assigned margin."""
        results = []
        for product in products:
            margin = margins.get(product.sku, Decimal("12"))
            result = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, margin)
            if result:
                results.append(result)
        return results

    @staticmethod
    def full_optimize_catalog_b2c(
        products: list[ProductPricingData],
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
    ) -> list[PriceResult]:
        """For each product, find the scheme+margin maximizing benefit under ceiling.

        PERFORMANCE: Up to ~273 PricingEngine calls per product (3 schemes × 91 margin steps).
        For catalogs > 50 SKUs, prefer calling this from a Celery task — not directly
        from a FastAPI request handler. Typical 232-SKU catalog: ~100-200ms total.
        """
        results = []
        for product in products:
            result = ChannelOptimizer.optimal_margin_b2c(product, route, fees, schemes)
            if result:
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # B2B mirrors
    # ------------------------------------------------------------------

    @staticmethod
    def best_scheme_b2b(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margin_pct: Decimal,
    ) -> Optional[PriceResult]:
        """Return best PriceResult among available schemes at the given margin (B2B)."""
        candidates = [
            PricingEngine.compute_b2b(product, route, fees, scheme, margin_pct)
            for scheme in schemes
            if scheme.is_available
        ]
        if not candidates:
            return None
        return _pick_best(candidates)

    @staticmethod
    def optimal_margin_b2b(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margin_step: Decimal = Decimal("1"),
    ) -> Optional[PriceResult]:
        """Find the maximum margin under ceiling across all schemes (B2B).

        Iterates margin from 80% down to -10% in margin_step increments.
        Returns the highest publishable margin combination.
        """
        margin = Decimal("80")
        floor = Decimal("-10")

        while margin >= floor:
            candidate = ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, margin)
            if candidate and candidate.is_publishable:
                return candidate
            margin -= margin_step

        # No publishable margin found → return the least-bad at floor margin
        return ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, floor)

    @staticmethod
    def optimize_catalog_b2b(
        products: list[ProductPricingData],
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margins: dict[str, Decimal],
    ) -> list[PriceResult]:
        """Compute best scheme per product at its assigned margin (B2B)."""
        results = []
        for product in products:
            margin = margins.get(product.sku, Decimal("12"))
            result = ChannelOptimizer.best_scheme_b2b(product, route, fees, schemes, margin)
            if result:
                results.append(result)
        return results

    @staticmethod
    def full_optimize_catalog_b2b(
        products: list[ProductPricingData],
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
    ) -> list[PriceResult]:
        """For each product, find the scheme+margin maximizing benefit under ceiling (B2B).

        PERFORMANCE: Up to ~273 PricingEngine calls per product (3 schemes × 91 margin steps).
        For catalogs > 50 SKUs, prefer calling this from a Celery task — not directly
        from a FastAPI request handler. Typical 232-SKU catalog: ~100-200ms total.
        """
        results = []
        for product in products:
            result = ChannelOptimizer.optimal_margin_b2b(product, route, fees, schemes)
            if result:
                results.append(result)
        return results


def _pick_best(candidates: list[PriceResult]) -> PriceResult:
    """Pick best result. Prefer publishable. Tie-break: scheme priority + benefit."""
    publishable = [r for r in candidates if r.is_publishable]
    pool = publishable if publishable else candidates

    def priority_rank(r: PriceResult) -> int:
        # Lower rank = higher priority
        try:
            return _SCHEME_PRIORITY.index(r.fulfillment_scheme)
        except ValueError:
            return len(_SCHEME_PRIORITY)  # unknown schemes get lowest priority

    return max(pool, key=lambda r: (r.benefit_per_unit_aed, -priority_rank(r)))
