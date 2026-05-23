"""Unit tests para `app.services.pricing.revise_service` (US-1B-01-04)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.pricing.pricing_service import PricingDomainError
from app.services.pricing.revise_service import (
    CounterProposalEmptyError,
    ReviseService,
)

pytestmark = pytest.mark.unit


def _mk_user() -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.email = "tester@mt.ae"
    return user


def _mk_session() -> MagicMock:
    sess = MagicMock()
    sess.add = MagicMock()
    sess.flush = AsyncMock()
    return sess


def _mk_revised_price(
    *,
    amount: Decimal = Decimal("100"),
    margin: Decimal = Decimal("0.30"),
    status: str = "revised",
    previous_amount: Decimal | None = Decimal("90"),
) -> Any:
    price = MagicMock()
    price.id = uuid4()
    price.amount = amount
    price.margin_pct = margin
    price.status = status
    price.breakdown = (
        {"previous_amount": str(previous_amount)} if previous_amount is not None else {}
    )
    return price


async def test_revise_with_counter_happy_path() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    revised = _mk_revised_price()
    pricing.revise = AsyncMock(return_value=revised)

    svc = ReviseService(sess, pricing_service=pricing)
    result = await svc.revise_with_counter(
        price_id=revised.id,
        new_amount=Decimal("100"),
        reason="negociado",
        actor=_mk_user(),
    )
    assert result.status_after == "revised"
    assert result.new_amount == "100"
    assert result.old_amount == "90"
    assert result.margin_pct == "0.30"
    pricing.revise.assert_awaited_once()


async def test_revise_with_counter_zero_amount_raises() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    pricing.revise = AsyncMock()
    svc = ReviseService(sess, pricing_service=pricing)
    with pytest.raises(CounterProposalEmptyError):
        await svc.revise_with_counter(
            price_id=uuid4(),
            new_amount=Decimal("0"),
            reason="x",
            actor=_mk_user(),
        )
    pricing.revise.assert_not_awaited()


async def test_revise_with_counter_empty_reason_raises() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    pricing.revise = AsyncMock()
    svc = ReviseService(sess, pricing_service=pricing)
    with pytest.raises(PricingDomainError):
        await svc.revise_with_counter(
            price_id=uuid4(),
            new_amount=Decimal("100"),
            reason="   ",
            actor=_mk_user(),
        )


async def test_revise_propagates_pricing_domain_error() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    pricing.revise = AsyncMock(
        side_effect=PricingDomainError("invalid_transition", "no se puede", 409)
    )
    svc = ReviseService(sess, pricing_service=pricing)
    with pytest.raises(PricingDomainError) as exc_info:
        await svc.revise_with_counter(
            price_id=uuid4(),
            new_amount=Decimal("100"),
            reason="r",
            actor=_mk_user(),
        )
    assert exc_info.value.code == "invalid_transition"


async def test_revise_no_previous_amount_yields_zero_old() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    revised = _mk_revised_price(previous_amount=None)
    pricing.revise = AsyncMock(return_value=revised)
    svc = ReviseService(sess, pricing_service=pricing)
    result = await svc.revise_with_counter(
        price_id=revised.id,
        new_amount=Decimal("110"),
        reason="reset",
        actor=_mk_user(),
    )
    assert result.old_amount == "0"
    assert result.new_amount == "110"


async def test_result_to_dict_keys() -> None:
    sess = _mk_session()
    pricing = MagicMock()
    revised = _mk_revised_price()
    pricing.revise = AsyncMock(return_value=revised)
    svc = ReviseService(sess, pricing_service=pricing)
    result = await svc.revise_with_counter(
        price_id=revised.id,
        new_amount=Decimal("99.99"),
        reason="r",
        actor=_mk_user(),
    )
    d = result.to_dict()
    assert set(d.keys()) >= {
        "price_id",
        "new_amount",
        "old_amount",
        "reason",
        "status_after",
        "margin_pct",
    }
