"""Specs validation services — registry + validator."""

from app.services.specs.specs_registry import SpecsRegistry
from app.services.specs.specs_validator import SpecsValidationError, SpecsValidator

__all__ = ["SpecsRegistry", "SpecsValidator", "SpecsValidationError"]
