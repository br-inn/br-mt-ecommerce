"""Unit tests — PmoEventEmitter (US-RND-01-12)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.pmo_bus import PMO_EVENT_WHITELIST, PmoEventEmitter
from app.services.pmo_bus.ports import PmoEvent, PmoEventPublisherPort


class _StubPublisher(PmoEventPublisherPort):
    def __init__(self) -> None:
        self.calls: list[PmoEvent] = []

    def publish(self, event: PmoEvent) -> None:
        self.calls.append(event)


# -----------------------------------------------------------------------------
# Whitelist enforcement
# -----------------------------------------------------------------------------
def test_whitelist_contains_expected_events() -> None:
    expected = {
        "price.approved",
        "price.rejected",
        "cost.upserted",
        "translation.approved",
    }
    assert PMO_EVENT_WHITELIST == expected


def test_emit_rejects_event_not_in_whitelist() -> None:
    emitter = PmoEventEmitter(_StubPublisher())
    with pytest.raises(ValueError, match="not in PMO whitelist"):
        emitter.emit("user.created", {"foo": "bar"})


def test_emit_accepts_whitelisted_event() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit("price.approved", {"sku": "SKU-1", "price_aed": 10.0})

    assert len(publisher.calls) == 1
    assert publisher.calls[0].event_name == "price.approved"
    assert publisher.calls[0].payload == {"sku": "SKU-1", "price_aed": 10.0}


# -----------------------------------------------------------------------------
# PII sanitization
# -----------------------------------------------------------------------------
def test_emit_strips_pii_keys_from_payload() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)

    emitter.emit(
        "price.approved",
        {
            "sku": "SKU-1",
            "email": "user@example.com",  # blocklisted
            "token": "secret-jwt",  # blocklisted
            "approver_id": "user-42",
        },
    )

    payload = publisher.calls[0].payload
    assert "email" not in payload
    assert "token" not in payload
    assert payload["sku"] == "SKU-1"
    assert payload["approver_id"] == "user-42"


def test_emit_pii_blocklist_is_case_insensitive() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit("price.approved", {"Email": "x@y.com", "AUTHORIZATION": "Bearer x"})

    payload = publisher.calls[0].payload
    assert "Email" not in payload
    assert "AUTHORIZATION" not in payload


# -----------------------------------------------------------------------------
# correlation_id propagation
# -----------------------------------------------------------------------------
def test_emit_propagates_correlation_id() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit("price.approved", {"sku": "X"}, correlation_id="trace-abc")

    assert publisher.calls[0].correlation_id == "trace-abc"


# -----------------------------------------------------------------------------
# Convenience helpers
# -----------------------------------------------------------------------------
def test_emit_price_approved_helper_shape() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit_price_approved(
        sku="SKU-9",
        channel="amazon_ae",
        scheme="standard",
        price_aed=99.5,
        approver_id="user-7",
        correlation_id="t1",
    )
    event = publisher.calls[0]
    assert event.event_name == "price.approved"
    assert event.payload["sku"] == "SKU-9"
    assert event.payload["channel"] == "amazon_ae"
    assert event.payload["scheme"] == "standard"
    assert event.payload["price_aed"] == 99.5
    assert event.payload["approver_id"] == "user-7"
    assert event.correlation_id == "t1"


def test_emit_price_rejected_helper_shape() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit_price_rejected(
        sku="SKU-9",
        channel="noon_ae",
        scheme="standard",
        reason="margin_below_floor",
        rejecter_id="user-7",
    )
    event = publisher.calls[0]
    assert event.event_name == "price.rejected"
    assert event.payload["reason"] == "margin_below_floor"


def test_emit_cost_upserted_helper_shape() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit_cost_upserted(
        material_code="MAT-100",
        supplier_id="SUP-1",
        cost_eur=12.34,
        delta_pct=0.07,
    )
    event = publisher.calls[0]
    assert event.event_name == "cost.upserted"
    assert event.payload["material_code"] == "MAT-100"
    assert event.payload["delta_pct"] == 0.07


def test_emit_cost_upserted_without_delta() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit_cost_upserted(
        material_code="MAT-100",
        supplier_id="SUP-1",
        cost_eur=12.34,
    )
    payload = publisher.calls[0].payload
    assert "delta_pct" not in payload


def test_emit_translation_approved_helper_shape() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit_translation_approved(
        entity_type="product",
        entity_id="PROD-1",
        locale="ar",
        approver_id="translator-1",
    )
    event = publisher.calls[0]
    assert event.event_name == "translation.approved"
    assert event.payload["locale"] == "ar"


# -----------------------------------------------------------------------------
# PmoEvent dataclass round-trip
# -----------------------------------------------------------------------------
def test_pmo_event_to_dict_serializes_timestamp_iso() -> None:
    publisher = _StubPublisher()
    emitter = PmoEventEmitter(publisher)
    emitter.emit("price.approved", {"sku": "X"})

    event = publisher.calls[0]
    payload: dict[str, Any] = event.to_dict()
    assert "T" in payload["emitted_at"]
    assert payload["source"] == "mt-pricing-backend"


# -----------------------------------------------------------------------------
# Publisher delegation contract
# -----------------------------------------------------------------------------
def test_emitter_delegates_to_publisher_via_mock() -> None:
    publisher = MagicMock(spec=PmoEventPublisherPort)
    emitter = PmoEventEmitter(publisher)
    emitter.emit("price.approved", {"sku": "X"})
    publisher.publish.assert_called_once()
    arg = publisher.publish.call_args.args[0]
    assert isinstance(arg, PmoEvent)
    assert arg.event_name == "price.approved"
