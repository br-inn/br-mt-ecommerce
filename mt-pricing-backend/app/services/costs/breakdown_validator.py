"""Validador de `breakdown` JSONB contra `schemes.cost_components_template`.

Reglas (US-1A-04-03 AC#2 y AC#3):
- ``required`` declarado en template → si falta en el breakdown → REJECT
  (raise ``MissingRequiredField``).
- Claves no declaradas → WARNING (no rechaza). El frontend puede mostrarlas
  como banner pero el create persiste igual (BR-1a-03 — costo extra raro
  vale más persistirlo que perderlo).

`cost_components_template` shape ejemplo (definido en cost_scheme seed):
    {
        "required": ["fob_eur", "freight_eur", "customs_aed", "fba_fees_aed"],
        "optional": ["payment_fees_pct", "marketing_aed", "storage_aed"]
    }

Convención de sufijos en las claves:
- ``*_aed``: importes ya en AED, no convierten.
- ``*_eur`` / ``*_<currency_lower>``: importes en moneda origen,
  convierten via FX rate.
- ``*_pct``: porcentaje aplicado sobre el subtotal (fee variable).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cost_scheme import CostScheme


class BreakdownValidationError(Exception):
    """422 — required field missing."""

    def __init__(self, code: str, field_name: str, message: str | None = None) -> None:
        self.code = code
        self.field_name = field_name
        super().__init__(message or f"{code}: {field_name}")


class MissingRequiredField(BreakdownValidationError):
    """422 `missing_required_breakdown_field`."""

    def __init__(self, field_name: str) -> None:
        super().__init__(
            "missing_required_breakdown_field",
            field_name,
            f"Required breakdown field missing: {field_name}",
        )


@dataclass
class BreakdownValidationResult:
    """Resultado del validator. Si `errors` no vacío, no debe persistirse."""

    valid: bool
    warnings: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


async def _get_template(session: AsyncSession, scheme_code: str) -> dict[str, Any] | None:
    """Lee `cost_components_template` del scheme. Retorna None si scheme no existe."""
    stmt = select(CostScheme).where(CostScheme.code == scheme_code)
    result = await session.execute(stmt)
    scheme = result.scalar_one_or_none()
    if scheme is None:
        return None
    return scheme.cost_components_template or {}


def _required_fields(template: dict[str, Any]) -> list[str]:
    raw = template.get("required") or []
    return [f for f in raw if isinstance(f, str)]


def _declared_fields(template: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for bucket in ("required", "optional"):
        for f in template.get(bucket, []) or []:
            if isinstance(f, str):
                out.add(f)
    return out


async def validate_breakdown(
    session: AsyncSession,
    scheme_code: str,
    breakdown: dict[str, Any],
    *,
    raise_on_missing_required: bool = True,
) -> BreakdownValidationResult:
    """Valida `breakdown` contra el template del scheme.

    - Si scheme no existe → error 'scheme_not_found' + valid=False.
    - Si template vacío → todo se considera optional → valid=True, sin warnings.
    - Required missing → error 'missing_required_breakdown_field'.
        * Si `raise_on_missing_required=True` (default), levanta
          MissingRequiredField directamente para mapeo HTTP 422.
    - Unknown field (no declarado en required ni optional) → warning,
      no rechaza.
    """
    template = await _get_template(session, scheme_code)
    if template is None:
        return BreakdownValidationResult(
            valid=False,
            errors=[{"code": "scheme_not_found", "field": scheme_code}],
        )

    required = _required_fields(template)
    declared = _declared_fields(template)

    breakdown_keys = set(breakdown.keys())
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    # Required check
    for req in required:
        if req not in breakdown_keys:
            errors.append({"code": "missing_required_breakdown_field", "field": req})
            if raise_on_missing_required:
                raise MissingRequiredField(req)

    # Unknown keys → warnings (declared empty → no warnings, todo se acepta).
    if declared:
        for k in breakdown_keys - declared:
            warnings.append({"code": "unknown_breakdown_field", "field": k})

    return BreakdownValidationResult(valid=not errors, warnings=warnings, errors=errors)


def known_keys(declared: Iterable[str]) -> set[str]:
    """Helper público — útil para frontend hint de campos esperados."""
    return {k for k in declared if isinstance(k, str)}


__all__ = [
    "BreakdownValidationError",
    "BreakdownValidationResult",
    "MissingRequiredField",
    "known_keys",
    "validate_breakdown",
]
