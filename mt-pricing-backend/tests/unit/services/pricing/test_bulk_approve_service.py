"""Unit tests para `PricingService.bulk_approve` (US-1B-02-05).

Sin DB — mocks de session, audit y approve().
Tres escenarios: éxito, estado inválido → 422, comentario corto → 422 Pydantic.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.pricing import PriceBulkApproveRequest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk_user() -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.email = "approver@mt.ae"
    return user


def _mk_price(*, price_id: UUID | None = None, status: str = "pending_review") -> Any:
    p = MagicMock()
    p.id = price_id or uuid4()
    p.status = status
    return p


def _mk_service(prices: list[Any]) -> Any:
    """Build a PricingService with mocked session + audit."""
    from app.services.pricing.pricing_service import PricingService

    session = MagicMock()
    # session.execute returns an object whose .scalars().all() gives `prices`
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = prices
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=execute_result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    audit = MagicMock()
    audit.record = AsyncMock()

    svc = PricingService.__new__(PricingService)
    svc.session = session
    svc.audit = audit
    return svc


# ---------------------------------------------------------------------------
# Test 1: success — all prices in pending_review → all approved
# ---------------------------------------------------------------------------
async def test_bulk_approve_success() -> None:
    pid1, pid2 = uuid4(), uuid4()
    price1 = _mk_price(price_id=pid1, status="pending_review")
    price2 = _mk_price(price_id=pid2, status="pending_review")

    svc = _mk_service([price1, price2])
    actor = _mk_user()

    # Mock approve() to return the same price object
    approved1 = _mk_price(price_id=pid1, status="approved")
    approved2 = _mk_price(price_id=pid2, status="approved")
    svc.approve = AsyncMock(side_effect=[approved1, approved2])

    comment = "Aprobado por auditor senior"
    result = await svc.bulk_approve([pid1, pid2], comment, actor)

    assert result["approved"] == [str(pid1), str(pid2)]
    assert svc.approve.await_count == 2
    svc.approve.assert_any_await(pid1, actor, reason=comment)
    svc.approve.assert_any_await(pid2, actor, reason=comment)

    # audit.record called once for batch
    svc.audit.record.assert_awaited_once()
    audit_kwargs = svc.audit.record.await_args.kwargs
    assert audit_kwargs["action"] == "price.bulk_approved"
    assert audit_kwargs["reason"] == comment
    assert str(pid1) in audit_kwargs["payload_diff"]["approved_ids"]
    assert str(pid2) in audit_kwargs["payload_diff"]["approved_ids"]


# ---------------------------------------------------------------------------
# Test 2: price in wrong state (e.g. draft) → 422 with list of invalid IDs
# ---------------------------------------------------------------------------
async def test_bulk_approve_wrong_state_raises_422() -> None:
    pid_ok = uuid4()
    pid_bad = uuid4()
    price_ok = _mk_price(price_id=pid_ok, status="pending_review")
    price_bad = _mk_price(price_id=pid_bad, status="draft")

    svc = _mk_service([price_ok, price_bad])
    actor = _mk_user()
    svc.approve = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await svc.bulk_approve([pid_ok, pid_bad], "Comentario válido largo", actor)

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert "invalid_price_ids" in detail
    assert str(pid_bad) in detail["invalid_price_ids"]
    assert str(pid_ok) not in detail["invalid_price_ids"]

    # approve must NOT have been called
    svc.approve.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 3: comment too short (< 10 chars) → Pydantic ValidationError
# ---------------------------------------------------------------------------
def test_bulk_approve_short_comment_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PriceBulkApproveRequest(price_ids=[uuid4()], comment="corto")

    errors = exc_info.value.errors()
    comment_errors = [e for e in errors if "comment" in str(e.get("loc", ""))]
    assert comment_errors, f"Expected error on 'comment' field, got: {errors}"


def test_bulk_approve_missing_comment_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PriceBulkApproveRequest(price_ids=[uuid4()])  # type: ignore[call-arg]

    errors = exc_info.value.errors()
    assert any("comment" in str(e.get("loc", "")) for e in errors)
