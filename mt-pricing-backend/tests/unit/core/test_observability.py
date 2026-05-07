"""Unit tests — observability bootstrap + Better Stack handler (US-1A-OBS-01)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.core.log_handlers import (
    DEFAULT_BUFFER_SIZE,
    BetterStackHandler,
    _record_to_payload,
    _redact,
    attach_better_stack_handler,
)
from app.core.observability import (
    bind_request_context,
    configure_observability,
    current_trace_id,
    emit_breadcrumb,
    reset_observability_state_for_tests,
    root_logger_handler_count,
)


@pytest.fixture(autouse=True)
def _reset_obs_state():
    reset_observability_state_for_tests()
    yield
    reset_observability_state_for_tests()


# -----------------------------------------------------------------------------
# configure_observability
# -----------------------------------------------------------------------------
def test_configure_observability_is_idempotent() -> None:
    with patch("app.core.logging.configure_logging") as p_log, patch(
        "app.core.sentry.configure_sentry"
    ) as p_sentry, patch(
        "app.core.log_handlers.attach_better_stack_handler"
    ) as p_bs:
        configure_observability()
        configure_observability()
        configure_observability()
        # Each underlying init must have been called exactly once.
        assert p_log.call_count == 1
        assert p_sentry.call_count == 1
        assert p_bs.call_count == 1


def test_configure_observability_attaches_at_least_one_handler() -> None:
    configure_observability()
    assert root_logger_handler_count() >= 1


# -----------------------------------------------------------------------------
# bind_request_context
# -----------------------------------------------------------------------------
def test_bind_request_context_generates_request_id_when_absent() -> None:
    bound = bind_request_context()
    assert "request_id" in bound
    assert len(bound["request_id"]) == 32  # uuid4().hex


def test_bind_request_context_preserves_caller_request_id() -> None:
    bound = bind_request_context(request_id="rid-1")
    assert bound["request_id"] == "rid-1"


def test_bind_request_context_includes_optional_fields() -> None:
    bound = bind_request_context(
        request_id="r1",
        trace_id="t1",
        tenant="mt",
        actor_id="user-42",
        sku="SKU-1",
    )
    assert bound["tenant"] == "mt"
    assert bound["actor_id"] == "user-42"
    assert bound["sku"] == "SKU-1"
    assert bound["trace_id"] == "t1"


def test_bind_request_context_skips_none_extras() -> None:
    bound = bind_request_context(request_id="r1", trace_id="t1", custom_field=None)
    assert "custom_field" not in bound


# -----------------------------------------------------------------------------
# current_trace_id
# -----------------------------------------------------------------------------
def test_current_trace_id_falls_back_to_uuid_when_no_sentry_scope() -> None:
    tid = current_trace_id()
    assert isinstance(tid, str)
    assert len(tid) == 32


def test_emit_breadcrumb_does_not_raise_when_sentry_uninitialized() -> None:
    # Smoke — no Sentry init, no DSN, but call must not raise.
    emit_breadcrumb("test", "hello", foo="bar")


# -----------------------------------------------------------------------------
# Better Stack handler — redact + payload
# -----------------------------------------------------------------------------
def test_redact_replaces_sensitive_keys_in_dict() -> None:
    redacted = _redact({"email": "x@y.com", "password": "p", "sku": "SKU-1"})
    # _redact only redacts keys at this level recursively in nested structures
    # The top-level redaction logic is in _record_to_payload via key match.
    # _redact replaces values for sensitive keys recursively.
    assert redacted["password"] == "***REDACTED***"
    assert redacted["sku"] == "SKU-1"


def test_redact_recurses_into_nested_dicts() -> None:
    redacted = _redact({"meta": {"api_key": "abc", "ok": "yes"}})
    assert redacted["meta"]["api_key"] == "***REDACTED***"
    assert redacted["meta"]["ok"] == "yes"


def test_redact_handles_lists() -> None:
    redacted = _redact([{"token": "x"}, {"sku": "SKU-1"}])
    assert redacted[0]["token"] == "***REDACTED***"
    assert redacted[1]["sku"] == "SKU-1"


def test_record_to_payload_emits_basic_fields() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = _record_to_payload(record)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello world"
    assert "dt" in payload


def test_record_to_payload_redacts_pii_in_extras() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="m",
        args=(),
        exc_info=None,
    )
    record.password = "leaked"  # type: ignore[attr-defined]
    record.sku = "SKU-1"  # type: ignore[attr-defined]
    payload = _record_to_payload(record)
    assert payload["password"] == "***REDACTED***"
    assert payload["sku"] == "SKU-1"


# -----------------------------------------------------------------------------
# BetterStackHandler — buffer / emit / flush — mocked client
# -----------------------------------------------------------------------------
def test_handler_emit_drops_when_token_empty() -> None:
    client = MagicMock()
    handler = BetterStackHandler(token="", client=client)
    record = logging.LogRecord(
        name="app", level=logging.INFO, pathname=__file__, lineno=1,
        msg="m", args=(), exc_info=None,
    )
    handler.emit(record)
    handler.flush()
    client.post.assert_not_called()


def test_handler_emit_buffers_and_flush_sends_batch() -> None:
    client = MagicMock()
    handler = BetterStackHandler(token="tok", client=client)
    for i in range(3):
        record = logging.LogRecord(
            name="app", level=logging.INFO, pathname=__file__, lineno=1,
            msg=f"event-{i}", args=(), exc_info=None,
        )
        handler.emit(record)

    handler.flush()
    client.post.assert_called_once()
    # Headers contain Bearer token
    kwargs = client.post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


def test_handler_default_buffer_size() -> None:
    assert DEFAULT_BUFFER_SIZE == 50


def test_handler_close_does_not_raise_without_start() -> None:
    client = MagicMock()
    handler = BetterStackHandler(token="tok", client=client)
    handler.close()


# -----------------------------------------------------------------------------
# attach_better_stack_handler — env-aware no-op
# -----------------------------------------------------------------------------
def test_attach_better_stack_handler_noop_when_token_missing() -> None:
    with patch("app.core.log_handlers.settings") as fake_settings:
        fake_settings.BETTER_STACK_LOGS_TOKEN = ""
        fake_settings.BETTER_STACK_LOGS_HOST = ""
        result = attach_better_stack_handler()
    assert result is None


def test_attach_better_stack_handler_attaches_when_token_present() -> None:
    with patch("app.core.log_handlers.settings") as fake_settings:
        fake_settings.BETTER_STACK_LOGS_TOKEN = "test-token"
        fake_settings.BETTER_STACK_LOGS_HOST = "https://example.test"
        handler = attach_better_stack_handler()
    assert handler is not None
    try:
        assert handler in logging.getLogger().handlers
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()
