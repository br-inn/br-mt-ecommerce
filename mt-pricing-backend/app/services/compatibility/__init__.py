"""Compatibility service — Wave 7 (recambios M:N)."""

from app.services.compatibility.compatibility_service import (
    CompatibilityDomainError,
    CompatibilityDuplicateError,
    CompatibilityNotFoundError,
    CompatibilitySelfLoopError,
    CompatibilityService,
    CompatibilitySkuNotFoundError,
)

__all__ = [
    "CompatibilityService",
    "CompatibilityDomainError",
    "CompatibilitySkuNotFoundError",
    "CompatibilitySelfLoopError",
    "CompatibilityDuplicateError",
    "CompatibilityNotFoundError",
]
