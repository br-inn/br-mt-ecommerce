"""Unit tests para `app.services.pricing.bulk_recalc_service` (US-1B-01-07).

Sin DB ni Celery — Protocols inyectados (PricingService, ProductRepo, AuditRepo).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.pricing.bulk_recalc_service import (
    FAILURE_RATE_ALERT_THRESHOLD,
    NIGHTLY_RECALC_CRON,
    NIGHTLY_RECALC_TASK_NAME,
    BulkRecalcResult,
    BulkRecalcService,
)
from app.services.pricing.pricing_service import PricingDomainError

pytestmark = pytest.mark.unit


def _mk_user() -> Any:
    user = MagicMock()
    user.id = uuid4()
    user.email = "system@mt.ae"
    return user


def _mk_price(*, status: str = "auto_approved", margin: str = "0.30") -> Any:
    p = MagicMock()
    p.id = uuid4()
    p.status = status
    p.margin_pct = Decimal(margin)
    return p


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------
def test_constants_match_spec() -> None:
    """Garantiza que el seed beat / DatabaseScheduler use estos valores."""
    assert NIGHTLY_RECALC_CRON == "0 2 * * *"
    assert NIGHTLY_RECALC_TASK_NAME == "mt.pricing.bulk_recalc"


def test_constructor_requires_session_or_protocols() -> None:
    with pytest.raises(ValueError):
        BulkRecalcService()


# ---------------------------------------------------------------------------
# Empty catalogue
# ---------------------------------------------------------------------------
async def test_run_empty_catalog() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(return_value=[])
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=[])
    audit = MagicMock()
    audit.record = AsyncMock()

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    assert result.skus_total == 0
    assert result.skus_processed == 0
    assert result.errors == []
    assert result.skipped is False
    assert result.failure_rate_alert is False
    audit.record.assert_awaited_once()
    kwargs = audit.record.await_args.kwargs
    assert kwargs["action"] == "nightly_recalc_batch"
    assert kwargs["entity_type"] == "pricing_batch"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
async def test_run_happy_path_status_counts_and_avg_margin() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(
        side_effect=[
            [
                _mk_price(status="auto_approved", margin="0.30"),
                _mk_price(status="pending_review", margin="0.20"),
            ],
            [_mk_price(status="auto_approved", margin="0.40")],
        ]
    )
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-001", "MT-V-002"])
    audit = MagicMock()
    audit.record = AsyncMock()

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    assert result.skus_total == 2
    assert result.skus_processed == 2
    assert result.skus_failed == 0
    assert result.status_counts == {"auto_approved": 2, "pending_review": 1}
    # avg = (0.3+0.2+0.4)/3 = 0.30
    assert result.avg_margin_delta == Decimal("0.30")
    assert result.failure_rate == 0.0
    assert result.failure_rate_alert is False


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------
async def test_run_continues_on_pricing_domain_error() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(
        side_effect=[
            PricingDomainError("cost_not_found", "no cost", 422),
            [_mk_price()],
        ]
    )
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-A", "MT-V-B"])
    audit = MagicMock()
    audit.record = AsyncMock()

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    assert result.skus_failed == 1
    assert result.skus_processed == 1
    assert result.errors[0]["code"] == "cost_not_found"
    assert result.errors[0]["sku"] == "MT-V-A"


async def test_run_continues_on_unhandled_exception() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(side_effect=[RuntimeError("boom"), [_mk_price()]])
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-A", "MT-V-B"])
    audit = MagicMock()
    audit.record = AsyncMock()

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    assert result.skus_failed == 1
    assert result.errors[0]["code"] == "unhandled_exception"


async def test_run_failure_rate_alert_at_threshold() -> None:
    """Si > 5% SKUs failed → flag failure_rate_alert=True."""
    skus = [f"MT-V-{i:03d}" for i in range(20)]
    # 2 fail / 18 ok → failure_rate ~= 2/(20-0) procesados? Cuenta sólo
    # processed (skus exitosos). Vamos a configurar 1 fail + 19 ok primero.
    side_effect: list[Any] = []
    # 19 succeed:
    for _ in range(19):
        side_effect.append([_mk_price()])
    # 1 fail (PricingDomainError):
    side_effect.append(PricingDomainError("x", "y", 422))

    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(side_effect=side_effect)
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=skus)
    audit = MagicMock()
    audit.record = AsyncMock()

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    # 19 procesados, 1 fail → failure_rate = 1/19 ≈ 0.0526 > 0.05
    assert result.skus_processed == 19
    assert result.skus_failed == 1
    assert result.failure_rate >= FAILURE_RATE_ALERT_THRESHOLD
    assert result.failure_rate_alert is True


# ---------------------------------------------------------------------------
# Mutex
# ---------------------------------------------------------------------------
async def test_run_skips_when_mutex_returns_false() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock()
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-A"])
    audit = MagicMock()
    audit.record = AsyncMock()
    mutex = AsyncMock(return_value=False)

    svc = BulkRecalcService(
        pricing_service=pricing,
        product_repo=products,
        audit_repo=audit,
        mutex_acquire=mutex,
    )
    result = await svc.run(actor=_mk_user())

    assert result.skipped is True
    assert result.skip_reason == "manual_recalc_in_progress"
    pricing.recalculate_for_product.assert_not_awaited()


async def test_run_continues_when_mutex_succeeds() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(return_value=[_mk_price()])
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-A"])
    audit = MagicMock()
    audit.record = AsyncMock()
    mutex = AsyncMock(return_value=True)

    svc = BulkRecalcService(
        pricing_service=pricing,
        product_repo=products,
        audit_repo=audit,
        mutex_acquire=mutex,
    )
    result = await svc.run(actor=_mk_user())

    assert result.skipped is False
    assert result.skus_processed == 1


async def test_run_audit_failure_doesnt_break_run() -> None:
    """Si audit.record explota, el resultado se devuelve igual."""
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(return_value=[_mk_price()])
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-A"])
    audit = MagicMock()
    audit.record = AsyncMock(side_effect=RuntimeError("audit DB down"))

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    assert result.skus_processed == 1


# ---------------------------------------------------------------------------
# Skipped SKUs
# ---------------------------------------------------------------------------
async def test_run_marks_skus_with_no_prices_as_skipped() -> None:
    pricing = MagicMock()
    pricing.recalculate_for_product = AsyncMock(side_effect=[[], [_mk_price()]])
    products = MagicMock()
    products.list_active_skus = AsyncMock(return_value=["MT-V-NO-COST", "MT-V-OK"])
    audit = MagicMock()
    audit.record = AsyncMock()

    svc = BulkRecalcService(pricing_service=pricing, product_repo=products, audit_repo=audit)
    result = await svc.run(actor=_mk_user())

    assert result.skus_skipped == 1
    assert result.skus_processed == 1


# ---------------------------------------------------------------------------
# Result serialization
# ---------------------------------------------------------------------------
def test_to_dict_round_trip() -> None:
    from datetime import datetime, timezone

    r = BulkRecalcResult(
        started_at=datetime(2026, 5, 7, 2, 0, tzinfo=timezone.utc),
    )
    r.skus_total = 5
    r.skus_processed = 3
    r.skus_failed = 1
    r.skus_skipped = 1
    r.status_counts = {"auto_approved": 3}
    r.avg_margin_delta = Decimal("0.25")
    payload = r.to_dict()
    assert payload["skus_total"] == 5
    assert payload["status_counts"] == {"auto_approved": 3}
    assert payload["avg_margin_delta"] == "0.25"
    assert "failure_rate" in payload
