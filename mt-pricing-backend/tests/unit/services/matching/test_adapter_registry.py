"""Tests del adapter registry / factory (matching + channel_mirror)."""

from __future__ import annotations

import pytest

from app.services.matching.adapter_registry import get_fetcher
from app.services.matching.adapters.amazon_uae_stub import AmazonUaeStubFetcher
from app.services.matching.adapters.noon_uae_stub import NoonUaeStubFetcher
from app.services.channel_mirror.adapter_registry import get_channel_adapter
from app.services.channel_mirror.adapters.amazon_sp_api_stub import AmazonSPApiStub
from app.services.channel_mirror.adapters.noon_api_stub import NoonApiStub

pytestmark = pytest.mark.unit


def test_matching_returns_stub_when_live_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    assert isinstance(get_fetcher("amazon_uae"), AmazonUaeStubFetcher)
    assert isinstance(get_fetcher("noon_uae"), NoonUaeStubFetcher)


def test_matching_returns_real_when_live_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    f1 = get_fetcher("amazon_uae")
    f2 = get_fetcher("noon_uae")
    # importadas lazy, sólo verificamos clase por nombre
    assert f1.__class__.__name__ == "BrightDataAmazonUaeFetcher"
    assert f2.__class__.__name__ == "PlaywrightNoonUaeFetcher"


def test_matching_unknown_channel_raises() -> None:
    with pytest.raises(ValueError):
        get_fetcher("unknown_channel")


def test_channel_mirror_returns_stub_when_live_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    assert isinstance(get_channel_adapter("amazon_uae"), AmazonSPApiStub)
    assert isinstance(get_channel_adapter("noon_uae"), NoonApiStub)


def test_channel_mirror_returns_real_when_live_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    a = get_channel_adapter("amazon_uae")
    n = get_channel_adapter("noon_uae")
    assert a.__class__.__name__ == "AmazonSPApiAdapter"
    assert n.__class__.__name__ == "NoonRealApiAdapter"


def test_channel_mirror_unknown_raises() -> None:
    with pytest.raises(ValueError):
        get_channel_adapter("foo")


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "TRUE", "Yes"])
def test_live_network_truthy_values(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", val)
    assert get_fetcher("amazon_uae").__class__.__name__ == "BrightDataAmazonUaeFetcher"


@pytest.mark.parametrize("val", ["0", "false", "no", "off", "", "garbage"])
def test_live_network_falsy_values(monkeypatch: pytest.MonkeyPatch, val: str) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", val)
    assert isinstance(get_fetcher("amazon_uae"), AmazonUaeStubFetcher)
