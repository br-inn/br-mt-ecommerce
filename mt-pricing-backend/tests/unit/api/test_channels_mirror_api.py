"""Tests del router channels_mirror — usa una FastAPI app aislada con
dependency overrides. NO requiere DB ni Redis.

Cubre los 5 endpoints definidos en
``app/api/routes/channels_mirror.py`` validando shape de respuesta y
manejo de errores 400/404.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

# Force test env BEFORE any app.* import (auth deps lee settings en import time).
os.environ.setdefault("ENV", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("ENABLE_DOCS", "false")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

from datetime import UTC

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes (mismo enfoque que test_mirror_service)
# ---------------------------------------------------------------------------
class _FakeListing:
    def __init__(self, **kwargs: Any) -> None:
        from datetime import datetime

        self.id: UUID = kwargs.get("id", uuid4())
        self.product_sku: str = kwargs["product_sku"]
        self.channel_code: str = kwargs["channel_code"]
        self.external_id: str = kwargs.get("external_id", "")
        self.buybox_state: str = kwargs.get("buybox_state", "none")
        self.buybox_pct_7d = kwargs.get("buybox_pct_7d")
        self.stock_qty = kwargs.get("stock_qty")
        self.rating = kwargs.get("rating")
        self.reviews_count = kwargs.get("reviews_count")
        self.last_sync_at = kwargs.get("last_sync_at")
        self.canonical_snapshot_jsonb = kwargs.get("canonical_snapshot", {})
        self.live_snapshot_jsonb = kwargs.get("live_snapshot", {})
        self.diff_summary = kwargs.get("diff_summary", {})
        self.is_active: bool = kwargs.get("is_active", True)
        self.created_at = kwargs.get("created_at", datetime.now(tz=UTC))
        self.updated_at = kwargs.get("updated_at", datetime.now(tz=UTC))


class _FakeEvent:
    def __init__(self, **kwargs: Any) -> None:
        from datetime import datetime

        self.id: UUID = kwargs.get("id", uuid4())
        self.channel_code: str = kwargs["channel_code"]
        self.product_sku = kwargs.get("product_sku")
        self.event_type: str = kwargs["event_type"]
        self.ok: bool = kwargs.get("ok", True)
        self.summary = kwargs.get("summary")
        self.payload_jsonb = kwargs.get("payload", {})
        self.duration_ms = kwargs.get("duration_ms")
        self.created_at = kwargs.get("created_at", datetime.now(tz=UTC))
        self.updated_at = kwargs.get("updated_at", datetime.now(tz=UTC))


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

    async def list_by_channel(
        self,
        channel_code: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        diff_status: str | None = None,
    ) -> tuple[list[_FakeListing], str | None]:
        rows = sorted(
            (v for k, v in self.store.items() if k[0] == channel_code),
            key=lambda r: r.product_sku,
        )
        if cursor:
            rows = [r for r in rows if r.product_sku > cursor]
        return rows[:limit], None


class _FakeEventsRepo:
    def __init__(self) -> None:
        self.events: list[_FakeEvent] = []

    async def log(self, **kwargs: Any) -> _FakeEvent:
        evt = _FakeEvent(**kwargs)
        self.events.append(evt)
        return evt

    async def recent(self, channel_code: str, *, limit: int = 50) -> list[_FakeEvent]:
        rows = [e for e in self.events if e.channel_code == channel_code]
        rows.sort(key=lambda e: e.created_at, reverse=True)
        return rows[:limit]


# ---------------------------------------------------------------------------
# App fixture: FastAPI aislada con router + dependency overrides
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def app_client() -> AsyncIterator[tuple[AsyncClient, dict[str, Any]]]:
    from app.api.deps import get_db_session
    from app.api.routes.channels_mirror import (
        get_channel_adapters,
        get_mirror_service,
    )
    from app.api.routes.channels_mirror import (
        router as mirror_router,
    )
    from app.db.models.user import User
    from app.services.channel_mirror.mirror_service import MirrorService

    # Build app
    app = FastAPI()
    app.include_router(mirror_router, prefix="/api/v1")

    # Shared fakes & state
    listings_repo = _FakeListingsRepo()
    events_repo = _FakeEventsRepo()
    canonical_db: dict[str, dict[str, Any]] = {
        "MTV-1004": {
            "title_en": "Ball valve PN16, DN25, brass CW617N",
            "title_ar": "صمام كروي PN16, مقاس DN25, نحاس CW617N",
            "brand": "Genebre",
            "material": "Brass CW617N",
            "DN": "25 mm",
            "PN": "16 bar",
            "HS_code": "8481.80.81",
            "weight": "0,38 kg",
        }
    }

    async def _fake_canonical_loader(sku: str) -> dict[str, Any]:
        return canonical_db.get(sku, {})

    # Override get_db_session — devuelve un async context que no toca DB.
    async def _fake_session() -> AsyncIterator[Any]:
        yield None

    # Override require_permissions(...) → fake user con todos los permisos
    # del módulo Channel Mirror (channels:read + channels:manage).
    from app.db.models.user import Role

    async def _fake_user() -> User:
        role = Role(  # type: ignore[call-arg]
            id=uuid4(),
            code="ti_integracion",
            name="ti_integracion",
            permissions_snapshot=["channels:read", "channels:manage"],
        )
        u = User(  # type: ignore[call-arg]
            id=uuid4(), email="t@t", full_name="T", locale="es", is_active=True
        )
        u.role = role
        return u

    # Override the route's DI factories directly (more focused than touching
    # require_permissions internals).
    app.dependency_overrides[get_db_session] = _fake_session

    # require_permissions returns a Callable; we monkey-patch each call site
    # at the *factory* level — easiest approach: override the produced
    # dependency by overriding `get_current_user`. But require_permissions
    # builds an inner _check that depends on get_current_user. Override it.
    from app.api import deps as _deps

    async def _fake_current_user() -> User:
        return await _fake_user()

    app.dependency_overrides[_deps.get_current_user] = _fake_current_user

    # Provide a fake adapter set + service via override.
    from app.services.channel_mirror.ports import LiveListing, PublishResult

    class _FakeAdapter:
        channel_code = "amazon_uae"

        async def pull_listing(self, sku: str, external_id: str | None = None) -> LiveListing:
            from datetime import datetime

            if sku == "MTV-1004":
                return LiveListing(
                    channel_code="amazon_uae",
                    external_id="B0CXR4M7Z9",
                    sku=sku,
                    fields={
                        "title_en": "Ball Valve PN16 DN25 Brass — MT",
                        "title_ar": "",
                        "brand": "Genebre",
                        "material": "Brass",
                        "DN": "25 mm",
                        "PN": "16 bar",
                        "HS_code": "8481.80.81",
                        "weight": "0,38 kg",
                    },
                    buybox_state="own",
                    buybox_pct_7d=0.87,
                    stock_qty=312,
                    rating=4.6,
                    reviews_count=184,
                    fetched_at=datetime.now(tz=UTC),
                )
            return LiveListing(
                channel_code="amazon_uae",
                external_id="",
                sku=sku,
                fields={},
            )

        async def push_diff(
            self,
            sku: str,
            external_id: str | None,
            diff_payload: dict[str, Any],
        ) -> PublishResult:
            return PublishResult(
                ok=True,
                submission_id=f"stub_{sku}",
                accepted_fields=list(diff_payload.keys()),
                rejected_fields=[],
                message="ok",
            )

    fake_adapter = _FakeAdapter()
    fake_adapters = {"amazon_uae": fake_adapter}

    def _override_get_adapters() -> dict[str, Any]:
        return fake_adapters

    def _override_get_mirror_service() -> MirrorService:
        return MirrorService(
            listings_repo=listings_repo,  # type: ignore[arg-type]
            events_repo=events_repo,  # type: ignore[arg-type]
            adapters=fake_adapters,  # type: ignore[arg-type]
            canonical_loader=_fake_canonical_loader,
        )

    # Also override the listing/event repos that the route constructs
    # directly from the session — ours need to be the same instance.
    # Easiest: override the repo classes via monkey-patch on the module.
    import app.api.routes.channels_mirror as routes_mod

    original_listings_cls = routes_mod.ChannelListingRepository
    original_events_cls = routes_mod.ChannelSyncEventRepository

    routes_mod.ChannelListingRepository = lambda _session: listings_repo  # type: ignore[assignment]
    routes_mod.ChannelSyncEventRepository = lambda _session: events_repo  # type: ignore[assignment]

    app.dependency_overrides[get_channel_adapters] = _override_get_adapters
    app.dependency_overrides[get_mirror_service] = _override_get_mirror_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        try:
            yield (
                client,
                {
                    "listings": listings_repo,
                    "events": events_repo,
                    "canonical": canonical_db,
                },
            )
        finally:
            routes_mod.ChannelListingRepository = original_listings_cls  # type: ignore[assignment]
            routes_mod.ChannelSyncEventRepository = original_events_cls  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_sync_endpoint_persists_and_returns_diff(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, state = app_client
    resp = await client.post("/api/v1/channels/amazon_uae/MTV-1004/sync")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["channel_code"] == "amazon_uae"
    assert body["sku"] == "MTV-1004"
    assert body["external_id"] == "B0CXR4M7Z9"
    assert isinstance(body["diffs"], list)
    assert body["summary"]["match"] >= 1
    assert body["summary"]["drift"] >= 1
    assert body["summary"]["missing"] >= 1
    # listing persisted
    assert ("amazon_uae", "MTV-1004") in state["listings"].store


async def test_diff_endpoint_returns_404_without_prior_sync(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    resp = await client.get("/api/v1/channels/amazon_uae/MTV-1004/diff")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["code"] == "listing_not_found"


async def test_diff_endpoint_returns_diff_after_sync(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    await client.post("/api/v1/channels/amazon_uae/MTV-1004/sync")
    resp = await client.get("/api/v1/channels/amazon_uae/MTV-1004/diff")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    fields = {d["field"]: d["status"] for d in body["diffs"]}
    assert fields["material"] == "drift"
    assert fields["title_ar"] == "missing"
    assert fields["DN"] == "match"


async def test_listings_endpoint_paginated(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    await client.post("/api/v1/channels/amazon_uae/MTV-1004/sync")
    resp = await client.get("/api/v1/channels/amazon_uae/listings?limit=10")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["page_size"] == 10
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["product_sku"] == "MTV-1004"
    assert item["external_id"] == "B0CXR4M7Z9"
    assert item["buybox_state"] == "own"


async def test_publish_endpoint_returns_publish_result(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, state = app_client
    await client.post("/api/v1/channels/amazon_uae/MTV-1004/sync")
    resp = await client.post(
        "/api/v1/channels/amazon_uae/MTV-1004/publish",
        json={"fields": ["material"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["accepted_fields"] == ["material"]
    # push event logged
    push_events = [e for e in state["events"].events if e.event_type == "push"]
    assert len(push_events) == 1


async def test_publish_endpoint_404_without_listing(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    resp = await client.post("/api/v1/channels/amazon_uae/MTV-1004/publish", json={})
    assert resp.status_code == 404


async def test_sync_log_endpoint_returns_recent_events(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    await client.post("/api/v1/channels/amazon_uae/MTV-1004/sync")
    await client.post("/api/v1/channels/amazon_uae/MTV-1004/publish", json={})
    resp = await client.get("/api/v1/channels/amazon_uae/sync-log?limit=10")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    types = [r["event_type"] for r in rows]
    # at least pull, diff, push
    assert "pull" in types
    assert "diff" in types
    assert "push" in types


async def test_sync_unknown_channel_returns_400(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    resp = await client.post("/api/v1/channels/unknown_chan/MTV-1004/sync")
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["code"] == "invalid_channel"


async def test_sync_unknown_sku_returns_404(
    app_client: tuple[AsyncClient, dict[str, Any]],
) -> None:
    client, _ = app_client
    resp = await client.post("/api/v1/channels/amazon_uae/UNKNOWN-SKU/sync")
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["code"] == "listing_not_found"
