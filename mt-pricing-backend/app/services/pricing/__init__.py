"""Pricing engine v5.1 — motor + workflow + state machine.

Wave 2 (motor v5.1 ported). Exports principales:
- `PricingRuleEngine`: motor 18 reglas determinístico.
- `PricingResult`: dataclass output.
- `ExceptionEvaluator`: decide auto_approved vs pending_review.
- `PricingService`: orquestador end-to-end (motor + evaluator + state machine + audit).
- `transition`, `ALLOWED_TRANSITIONS`: state machine.
"""

from __future__ import annotations

from app.services.pricing.exception_evaluator import ExceptionEvaluator
from app.services.pricing.pricing_service import (
    ChannelNotFound,
    CostNotFound,
    PriceNotFound,
    PricingDomainError,
    PricingService,
    ProductNotFound,
    SchemeNotFound,
    TransitionError,
)
from app.services.pricing.rule_engine import (
    EUR_TO_AED_DEFAULT,
    PricingResult,
    PricingRuleEngine,
)
from app.services.pricing.state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidTransition,
    is_valid_transition,
    transition,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "ChannelNotFound",
    "CostNotFound",
    "EUR_TO_AED_DEFAULT",
    "ExceptionEvaluator",
    "InvalidTransition",
    "PriceNotFound",
    "PricingDomainError",
    "PricingResult",
    "PricingRuleEngine",
    "PricingService",
    "ProductNotFound",
    "SchemeNotFound",
    "TransitionError",
    "is_valid_transition",
    "transition",
]
