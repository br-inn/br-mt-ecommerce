"""Stub the anthropic package so tests run without the SDK installed."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


def _ensure_anthropic_stub() -> None:
    """Insert a minimal anthropic stub into sys.modules if the real package is absent."""
    if "anthropic" not in sys.modules:
        stub = MagicMock()
        stub.AsyncAnthropic = MagicMock
        sys.modules["anthropic"] = stub


# Run at import time so the stub is present before any test module is collected.
_ensure_anthropic_stub()
