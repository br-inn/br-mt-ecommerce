"""Unit tests `app.services.costs.breakdown_validator` — sin DB.

Cobertura (US-1A-04-03 AC#2 #3):
- Required field missing → MissingRequiredField (raise_on_missing_required=True).
- Required field missing → result.errors poblado (raise_on_missing_required=False).
- Unknown field declared → warning, no error.
- Empty template → todo se acepta sin warnings.
- Scheme not found → result.valid=False con error 'scheme_not_found'.
- Required + unknown mezcla → tanto error como warning.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.costs.breakdown_validator import (
    BreakdownValidationResult,
    MissingRequiredField,
    validate_breakdown,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — fake AsyncSession that returns a stubbed CostScheme.
# ---------------------------------------------------------------------------
class _FakeScheme:
    def __init__(self, code: str, template: dict[str, Any] | None) -> None:
        self.code = code
        self.cost_components_template = template


def _session_returning(scheme: _FakeScheme | None) -> Any:
    """Build a MagicMock AsyncSession.execute that returns scheme via scalar_one_or_none."""
    sess = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=scheme)
    sess.execute = AsyncMock(return_value=scalar_result)
    return sess


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_required_missing_raises_by_default() -> None:
    template = {
        "required": ["fob_eur", "freight_eur"],
        "optional": ["customs_aed"],
    }
    sess = _session_returning(_FakeScheme("FBA", template))
    with pytest.raises(MissingRequiredField) as exc_info:
        await validate_breakdown(sess, "FBA", {"freight_eur": 1.5})
    assert exc_info.value.field_name == "fob_eur"
    assert exc_info.value.code == "missing_required_breakdown_field"


async def test_required_missing_collects_errors_when_no_raise() -> None:
    template = {"required": ["fob_eur"]}
    sess = _session_returning(_FakeScheme("FBA", template))
    res = await validate_breakdown(
        sess, "FBA", {}, raise_on_missing_required=False
    )
    assert isinstance(res, BreakdownValidationResult)
    assert res.valid is False
    assert any(e["field"] == "fob_eur" for e in res.errors)


async def test_unknown_field_emits_warning_no_error() -> None:
    template = {
        "required": ["fob_eur"],
        "optional": ["freight_eur"],
    }
    sess = _session_returning(_FakeScheme("FBA", template))
    res = await validate_breakdown(
        sess, "FBA", {"fob_eur": 12.40, "weird_extra": 2.0}
    )
    assert res.valid is True
    assert any(
        w["field"] == "weird_extra" and w["code"] == "unknown_breakdown_field"
        for w in res.warnings
    )


async def test_empty_template_accepts_anything_silently() -> None:
    sess = _session_returning(_FakeScheme("CUSTOM", {}))
    res = await validate_breakdown(sess, "CUSTOM", {"x_aed": 1, "y_pct": 2})
    assert res.valid is True
    assert res.warnings == []


async def test_scheme_not_found_returns_invalid_with_error() -> None:
    sess = _session_returning(None)
    res = await validate_breakdown(sess, "DOES_NOT_EXIST", {"fob_eur": 1})
    assert res.valid is False
    assert any(e["code"] == "scheme_not_found" for e in res.errors)


async def test_mixed_required_missing_and_unknown_raises_first() -> None:
    """Required is checked before unknown — required failure short-circuits."""
    template = {"required": ["fob_eur"], "optional": []}
    sess = _session_returning(_FakeScheme("FBA", template))
    with pytest.raises(MissingRequiredField):
        await validate_breakdown(
            sess, "FBA", {"some_unknown": 5}
        )


async def test_partial_required_present_still_raises_for_missing() -> None:
    template = {"required": ["fob_eur", "freight_eur"]}
    sess = _session_returning(_FakeScheme("FBA", template))
    with pytest.raises(MissingRequiredField) as exc_info:
        await validate_breakdown(sess, "FBA", {"fob_eur": 12.40})
    # Specifically the missing one (not the present one).
    assert exc_info.value.field_name == "freight_eur"


async def test_no_warnings_when_all_keys_declared() -> None:
    template = {
        "required": ["fob_eur"],
        "optional": ["freight_eur", "customs_aed"],
    }
    sess = _session_returning(_FakeScheme("FBA", template))
    res = await validate_breakdown(
        sess,
        "FBA",
        {"fob_eur": 10, "freight_eur": 1, "customs_aed": 2},
    )
    assert res.valid is True
    assert res.warnings == []
