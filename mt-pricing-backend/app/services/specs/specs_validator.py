"""SpecsValidator — validates product specs JSONB against family/subfamily schema.

Uses ``jsonschema.Draft202012Validator``.  Errors are returned as
``ValidationResult`` (Pydantic v2) — valid flag + list of ``FieldError``.

The API layer maps ``SpecsValidationError`` → HTTP 422 ProblemDetails.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from app.services.specs.specs_registry import SpecsRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models (Pydantic v2)
# ---------------------------------------------------------------------------
class FieldError(BaseModel):
    """Single field-level validation error — maps to FastAPI 422 error item."""

    field: str
    message: str
    value: Any = None


class ValidationResult(BaseModel):
    """Outcome of a specs validation pass."""

    valid: bool
    errors: list[FieldError] = []


# ---------------------------------------------------------------------------
# Domain exception
# ---------------------------------------------------------------------------
class SpecsValidationError(Exception):
    """Raised by ProductService when specs fail schema validation.

    Mapped to HTTP 422 by the products router.
    """

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__(f"specs validation failed: {len(errors)} error(s)")
        self.errors = errors
        self.status_code = 422
        self.code = "specs_validation_error"


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------
class SpecsValidator:
    """Validates specs dicts against family/subfamily JSON Schemas.

    Args:
        registry: :class:`SpecsRegistry` instance providing schema lookup.
    """

    def __init__(self, registry: SpecsRegistry) -> None:
        self._registry = registry

    def validate(
        self,
        specs: dict[str, Any],
        family: str,
        subfamily: str | None = None,
    ) -> ValidationResult:
        """Validate *specs* against the schema for *family*/*subfamily*.

        Returns a :class:`ValidationResult`; never raises — callers decide
        whether to raise based on ``result.valid``.
        """
        # Import here so the module loads even if jsonschema is absent at
        # import time (though it should always be present).
        try:
            import jsonschema
            from jsonschema import Draft202012Validator
        except ImportError:
            logger.error("jsonschema not installed — skipping specs validation")
            return ValidationResult(valid=True, errors=[])

        schema = self._registry.get_schema(family, subfamily)
        if not schema:
            # No schema at all (shouldn't happen — _default always present).
            return ValidationResult(valid=True, errors=[])

        validator = Draft202012Validator(schema)
        raw_errors = list(validator.iter_errors(specs))

        if not raw_errors:
            return ValidationResult(valid=True, errors=[])

        field_errors: list[FieldError] = []
        for err in raw_errors:
            # Build a dotted path from the JSON path.
            if err.absolute_path:
                path = ".".join(str(p) for p in err.absolute_path)
            elif err.validator == "required":
                # Extract missing property name from the message.
                # err.validator_value is the required array; err.message has it.
                path = _extract_required_field(err.message)
            elif err.validator == "additionalProperties":
                # Extract unexpected property name from the message.
                # Messages look like: "Additional properties are not allowed ('foo' was unexpected)".
                path = _extract_additional_property(err.message)
            else:
                path = "specs"

            field_errors.append(
                FieldError(
                    field=f"specs.{path}" if path and path != "specs" else "specs",
                    message=err.message,
                    value=_safe_value(err.instance),
                )
            )

        return ValidationResult(valid=False, errors=field_errors)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_required_field(message: str) -> str:
    """Parse field name from jsonschema required error message.

    Messages look like: ``'dn' is a required property``
    """
    import re

    m = re.match(r"['\"]([^'\"]+)['\"] is a required property", message)
    if m:
        return m.group(1)
    return "specs"


def _extract_additional_property(message: str) -> str:
    """Parse unexpected property name from jsonschema additionalProperties error.

    Messages look like:
      ``Additional properties are not allowed ('foo' was unexpected)``
      ``Additional properties are not allowed ('foo', 'bar' were unexpected)``
    """
    import re

    m = re.search(r"['\"]([^'\"]+)['\"]", message)
    if m:
        return m.group(1)
    return "specs"


def _safe_value(v: Any) -> Any:
    """Truncate large values for error reporting."""
    if isinstance(v, (dict, list)):
        return None  # Don't echo back large nested objects.
    if isinstance(v, str) and len(v) > 200:
        return v[:200] + "…"
    return v
