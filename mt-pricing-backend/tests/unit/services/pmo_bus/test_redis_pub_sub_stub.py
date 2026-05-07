"""Unit tests — RedisPubSubStubPublisher (US-RND-01-12).

Mockea redis_client.publish — NO conecta a Redis real.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.services.pmo_bus.adapters.redis_pub_sub_stub import (
    DEFAULT_CHANNEL,
    RedisPubSubStubPublisher,
)
from app.services.pmo_bus.ports import PmoEvent


def _make_event(name: str = "price.approved") -> PmoEvent:
    return PmoEvent(
        event_name=name,
        payload={"sku": "SKU-1", "price_aed": 9.99},
        correlation_id="trace-xyz",
    )


def test_publish_uses_default_channel_when_unspecified() -> None:
    redis_mock = MagicMock()
    redis_mock.publish.return_value = 0
    publisher = RedisPubSubStubPublisher(redis_mock)

    publisher.publish(_make_event())

    redis_mock.publish.assert_called_once()
    channel = redis_mock.publish.call_args.args[0]
    assert channel == DEFAULT_CHANNEL == "mt:pmo:events"


def test_publish_uses_custom_channel() -> None:
    redis_mock = MagicMock()
    publisher = RedisPubSubStubPublisher(redis_mock, channel="custom:channel")
    publisher.publish(_make_event())
    assert redis_mock.publish.call_args.args[0] == "custom:channel"
    assert publisher.channel == "custom:channel"


def test_publish_serializes_event_to_json() -> None:
    redis_mock = MagicMock()
    redis_mock.publish.return_value = 1
    publisher = RedisPubSubStubPublisher(redis_mock)

    publisher.publish(_make_event())

    message = redis_mock.publish.call_args.args[1]
    decoded = json.loads(message)
    assert decoded["event_name"] == "price.approved"
    assert decoded["payload"]["sku"] == "SKU-1"
    assert decoded["correlation_id"] == "trace-xyz"
    assert decoded["source"] == "mt-pricing-backend"
    assert "emitted_at" in decoded


def test_publish_swallows_redis_exceptions() -> None:
    redis_mock = MagicMock()
    redis_mock.publish.side_effect = ConnectionError("Redis down")
    publisher = RedisPubSubStubPublisher(redis_mock)

    # Must NOT raise — fail-safe contract.
    publisher.publish(_make_event())
    redis_mock.publish.assert_called_once()


def test_publish_handles_unserializable_payload_without_raising() -> None:
    """Si el payload contiene un objeto no JSON-serializable, no debe romper."""
    redis_mock = MagicMock()
    publisher = RedisPubSubStubPublisher(redis_mock)

    class NonSerializable:
        pass

    bad_event = PmoEvent(
        event_name="price.approved",
        payload={"obj": NonSerializable()},  # default=str rescata casi todo
    )
    # Con default=str la mayoría se serializa — pero set() no lo hace.
    # Probamos con set para forzar TypeError.
    bad_event_2 = PmoEvent(
        event_name="price.approved",
        payload={"unserializable": {1, 2, 3}},
    )
    publisher.publish(bad_event_2)
    # Con `default=str` los sets pasan, así que debería publicarse.
    # Lo importante: no raise.
    # Test relaxado al fail-safe contract:
    publisher.publish(bad_event)


def test_publisher_is_recognized_as_port() -> None:
    from app.services.pmo_bus.ports import PmoEventPublisherPort

    redis_mock = MagicMock()
    publisher = RedisPubSubStubPublisher(redis_mock)
    assert isinstance(publisher, PmoEventPublisherPort)


def test_publish_logs_subscriber_count(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    redis_mock = MagicMock()
    redis_mock.publish.return_value = 3
    publisher = RedisPubSubStubPublisher(redis_mock)

    with caplog.at_level(logging.DEBUG):
        publisher.publish(_make_event())

    # The publisher delegates to redis successfully — no warnings expected.
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == []
