"""Tests del MirrorService usando fakes in-memory (no DB).

Cubre:
- ``sync()``: pull → diff → persist + log (2 events: pull + diff).
- ``compute_diff()``: lectura barata desde snapshots persistidos.
- ``publish()``: empuja → log push event.
- Errores: canal desconocido, sku sin canonical, sku sin listing previo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.services.channel_mirror.mirror_service import (
    CanonicalNotFoundError,
    MirrorService,
    UnknownChannelError,
)
from app.services.channel_mirror.ports import LiveListing, PublishResult

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes in-memory (sin SQLAlchemy)
# ---------------------------------------------------------------------------
class _FakeListing:
    def __init__(self, **kwargs: Any) -> None:
        self.id = kwargs.get("id", uuid4())
        self.channel_code = kwargs["channel_code"]
        self.product_sku = kwargs["product_sku"]
        self.external_id = kwargs.get("external_id", "")
        self.canonical_snapshot_jsonb = kwargs.get("canonical_snapshot", {})
        self.live_snapshot_jsonb = kwargs.get("live_snapshot", {})
        self.diff_summary = kwargs.get("diff_summary", {})
        self.buybox_state = kwargs.get("buybox_state", "none")
        self.buybox_pct_7d = kwargs.get("buybox_pct_7d")
        self.stock_qty = kwargs.get("stock_qty")
        self.rating = kwargs.get("rating")
        self.reviews_count = kwargs.get("reviews_count")
        self.last_sync_at = kwargs.get("last_sync_at")


class _FakeListingsRepo:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], _FakeListing] = {}

    async def get_by_channel_sku(self, channel_code: str, sku: str) -> _FakeListing | None:
        return self.store.get((channel_code, sku))

    async def upsert(self, **kwargs: Any) -> _FakeListing:
        key = (kwargs["channel_code"], kwargs["product_sku"])
        existing = self.store.get(key)
        if existing is None:
            obj = _FakeListing(**kwargs)
            self.store[key] = obj
            return obj
        for k, v in kwargs.items():
            if k == "canonical_snapshot":
                existing.canonical_snapshot_jsonb = v
            elif k == "live_snapshot":
                existing.live_snapshot_jsonb = v
            else:
                setattr(existing, k, v)
        return existing


class _FakeEventsRepo:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def log(self, **kwargs: Any) -> None:
        self.events.append(kwargs)
        return None


class _FakeAdapter:
    def __init__(
        self,
        channel_code: str,
        listing: LiveListing,
        publish_result: PublishResult | None = None,
    ) -> None:
        self.channel_code = channel_code
        self._listing = listing
        self._publish_result = publish_result or PublishResult(
            ok=True, submission_id="fake_sub", accepted_fields=[]
        )
        self.pull_calls: int = 0
        self.push_calls: int = 0
        self.last_push_payload: dict[str, Any] | None = None

    async def pull_listing(self, sku: str, external_id: str | None = None) -> LiveListing:
        self.pull_calls += 1
        return self._listing

    async def push_diff(
        self,
        sku: str,
        external_id: str | None,
        diff_payload: dict[str, Any],
    ) -> PublishResult:
        self.push_calls += 1
        self.last_push_payload = dict(diff_payload)
        return self._publish_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_canonical_loader(canonical_db: dict[str, dict[str, Any]]) -> Any:
    async def _loader(sku: str) -> dict[str, Any]:
        return canonical_db.get(sku, {})

    return _loader


def _make_service(
    *,
    canonical_db: dict[str, dict[str, Any]],
    adapters: dict[str, _FakeAdapter] | None = None,
) -> tuple[MirrorService, _FakeListingsRepo, _FakeEventsRepo]:
    listings_repo = _FakeListingsRepo()
    events_repo = _FakeEventsRepo()
    if adapters is None:
        adapters = {}
    service = MirrorService(
        listings_repo=listings_repo,  # type: ignore[arg-type]
        events_repo=events_repo,  # type: ignore[arg-type]
        adapters=adapters,  # type: ignore[arg-type]
        canonical_loader=_make_canonical_loader(canonical_db),
    )
    return service, listings_repo, events_repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_sync_persists_listing_and_logs_two_events() -> None:
    canonical = {"brand": "Genebre", "DN": "25 mm", "title_ar": "كروي"}
    live_listing = LiveListing(
        channel_code="amazon_uae",
        external_id="B0CXR4M7Z9",
        sku="MTV-1004",
        fields={"brand": "Genebre", "DN": "25 mm", "title_ar": ""},
        buybox_state="own",
        buybox_pct_7d=0.87,
        stock_qty=312,
        rating=4.6,
        reviews_count=184,
        fetched_at=datetime.now(tz=UTC),
    )
    adapter = _FakeAdapter("amazon_uae", live_listing)
    service, listings_repo, events_repo = _make_service(
        canonical_db={"MTV-1004": canonical},
        adapters={"amazon_uae": adapter},
    )

    outcome = await service.sync("amazon_uae", "MTV-1004")

    # adapter.pull_listing called once
    assert adapter.pull_calls == 1
    # listing persisted
    listing = await listings_repo.get_by_channel_sku("amazon_uae", "MTV-1004")
    assert listing is not None
    assert listing.external_id == "B0CXR4M7Z9"
    assert listing.buybox_state == "own"
    # 2 events: pull + diff
    types = [e["event_type"] for e in events_repo.events]
    assert types == ["pull", "diff"]
    # outcome carries diffs
    assert outcome.summary["match"] == 2
    assert outcome.summary["missing"] == 1
    assert outcome.summary["drift"] == 0
    assert outcome.summary["queued"] == 0


async def test_sync_unknown_channel_raises() -> None:
    service, _, _ = _make_service(
        canonical_db={"MTV-1004": {"brand": "x"}},
        adapters={},
    )
    with pytest.raises(UnknownChannelError):
        await service.sync("unknown_channel", "MTV-1004")


async def test_sync_canonical_missing_raises() -> None:
    live_listing = LiveListing(
        channel_code="amazon_uae",
        external_id="B0CXR4M7Z9",
        sku="UNKNOWN-SKU",
        fields={},
    )
    adapter = _FakeAdapter("amazon_uae", live_listing)
    service, _, _ = _make_service(
        canonical_db={},  # nada
        adapters={"amazon_uae": adapter},
    )
    with pytest.raises(CanonicalNotFoundError):
        await service.sync("amazon_uae", "UNKNOWN-SKU")


async def test_compute_diff_uses_snapshots_no_pull() -> None:
    canonical = {"brand": "Genebre", "material": "Brass CW617N"}
    live_listing = LiveListing(
        channel_code="amazon_uae",
        external_id="B0CXR4M7Z9",
        sku="MTV-1004",
        fields={"brand": "Genebre", "material": "Brass"},
    )
    adapter = _FakeAdapter("amazon_uae", live_listing)
    service, _, _ = _make_service(
        canonical_db={"MTV-1004": canonical},
        adapters={"amazon_uae": adapter},
    )

    # prime: do an initial sync
    await service.sync("amazon_uae", "MTV-1004")
    assert adapter.pull_calls == 1

    # now compute_diff should NOT call pull again
    diffs, summary = await service.compute_diff("amazon_uae", "MTV-1004")
    assert adapter.pull_calls == 1
    assert summary["drift"] == 1
    assert summary["match"] == 1


async def test_compute_diff_no_listing_raises() -> None:
    service, _, _ = _make_service(
        canonical_db={"MTV-1004": {"brand": "x"}},
        adapters={},
    )
    with pytest.raises(CanonicalNotFoundError):
        await service.compute_diff("amazon_uae", "MTV-1004")


async def test_publish_logs_push_event_and_calls_adapter() -> None:
    canonical = {"brand": "Genebre", "material": "Brass CW617N"}
    live_listing = LiveListing(
        channel_code="amazon_uae",
        external_id="B0CXR4M7Z9",
        sku="MTV-1004",
        fields={"brand": "Genebre", "material": "Brass"},
    )
    adapter = _FakeAdapter(
        "amazon_uae",
        live_listing,
        publish_result=PublishResult(
            ok=True,
            submission_id="sub_xyz",
            accepted_fields=["material"],
            rejected_fields=[],
            message="stub",
        ),
    )
    service, _, events_repo = _make_service(
        canonical_db={"MTV-1004": canonical},
        adapters={"amazon_uae": adapter},
    )
    await service.sync("amazon_uae", "MTV-1004")

    result = await service.publish("amazon_uae", "MTV-1004", fields=["material"])
    assert result.ok is True
    assert result.submission_id == "sub_xyz"
    assert adapter.push_calls == 1
    assert adapter.last_push_payload == {"material": "Brass CW617N"}

    push_events = [e for e in events_repo.events if e["event_type"] == "push"]
    assert len(push_events) == 1
    assert push_events[0]["ok"] is True


async def test_publish_no_prior_listing_raises() -> None:
    canonical = {"brand": "x"}
    adapter = _FakeAdapter(
        "amazon_uae",
        LiveListing(channel_code="amazon_uae", external_id="", sku="X", fields={}),
    )
    service, _, _ = _make_service(
        canonical_db={"X": canonical},
        adapters={"amazon_uae": adapter},
    )
    with pytest.raises(CanonicalNotFoundError):
        await service.publish("amazon_uae", "X")


async def test_publish_default_pushes_full_canonical() -> None:
    canonical = {"a": "1", "b": "2"}
    live_listing = LiveListing(
        channel_code="amazon_uae",
        external_id="B0CXR4M7Z9",
        sku="MTV-1004",
        fields={"a": "1"},
    )
    adapter = _FakeAdapter("amazon_uae", live_listing)
    service, _, _ = _make_service(
        canonical_db={"MTV-1004": canonical},
        adapters={"amazon_uae": adapter},
    )
    await service.sync("amazon_uae", "MTV-1004")
    await service.publish("amazon_uae", "MTV-1004")  # fields=None
    assert adapter.last_push_payload == canonical


async def test_amazon_stub_pull_returns_canned_for_mtv1004() -> None:
    from app.services.channel_mirror.adapters import AmazonSPApiStub

    adapter = AmazonSPApiStub()
    listing = await adapter.pull_listing("MTV-1004")
    assert listing.external_id == "B0CXR4M7Z9"
    assert listing.buybox_state == "own"
    assert "title_en" in listing.fields


async def test_amazon_stub_pull_unknown_sku_returns_empty() -> None:
    from app.services.channel_mirror.adapters import AmazonSPApiStub

    adapter = AmazonSPApiStub()
    listing = await adapter.pull_listing("UNKNOWN-SKU")
    assert listing.external_id == ""
    assert listing.fields == {}


async def test_noon_stub_pull_returns_canned_for_mtv1004() -> None:
    from app.services.channel_mirror.adapters import NoonApiStub

    adapter = NoonApiStub()
    listing = await adapter.pull_listing("MTV-1004")
    assert listing.external_id == "N0ON-MTV1004"
    assert listing.buybox_state == "competitor"
