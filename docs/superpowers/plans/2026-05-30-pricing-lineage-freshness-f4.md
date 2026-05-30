# Pricing Desk F4 — Lineage + Freshness + Source Health (API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) tracking.

**Goal:** Expose F1's provenance via 5 read endpoints under `/pricing/{channel_code}`: `sources/health`, `freshness`, `lineage/{sku}/{field}`, `parameters/{key}/audit`, `products/{sku}/card`.

**Architecture:** A read-only service `provenance_query.py` assembles responses from F1's tables (`source_health`, `source_observations`, `audit_events`) + existing ones (`products`, `product_marketplace_listings`, `prices`, `price_approval_events`) + `ParameterLoader`/`PricingEngine` (for lineage breakdown). Thin handlers in `channel_pricing.py`. No migration. Branch is stacked on F1 (`feat/pricing-desk-provenance-audit`).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic v2, pytest. Backend `mt-pricing-backend/`. Spec: `docs/superpowers/specs/2026-05-30-pricing-lineage-freshness-f4-design.md`.

**Run tests (Docker; DB at alembic head `20260603_149`):**
`docker exec mt-backend sh -c "cd /app && python -m pytest <path> -o addopts='' -q"`

**Resolved facts (research):**
- `SourceHealth` cols: `source_op` (PK), `last_sync_attempt_at`, `last_sync_success_at`, `last_error`, `freshness_sla_minutes`, `rows_last_sync`, `updated_at`. 14 rows seeded (one per `source_op`), all `last_sync_success_at` NULL today.
- `SourceObservation` cols: `source_op, target_table, target_id, sku, channel_id, target_field, value_numeric, value_text, source_ref, observed_at, ingested_at, correlation_id`.
- `AuditRepository(session).list_for_entity(entity_type, entity_id, *, since=None, limit=100)` returns `Sequence[AuditEvent]` (cols incl. `actor_id, action, before, after, reason, event_at`).
- **F1 audit entity mapping** (in `channel_pricing.py`): `pricing_param`→entity_id `route_id` (route-params) or fee row id (fee-params); `margin_target`→`str(family_id)`; `margin_override`→`f"{channel_code}:{sku}"`; `optimization`/`price_proposal`/`catalog_import`→`channel_code`.
- `product_marketplace_listings` cols: `product_sku, marketplace, status, listing_title, listing_description, bullet_points, search_keywords, ai_generated_at, created_at, updated_at` (no channel_id, no price; key by `product_sku`+`marketplace`).
- `prices` cols (read for proposals): `product_sku, channel_id, scheme_code, amount, status, proposed_by, approved_by, created_at`. `price_approval_events`: `price_id, actor_id, from_status, to_status, reason, created_at`.
- `ParameterLoader(session).load_route_and_fees(channel_id)` + `load_product_data(channel_id, skus=[sku])` + `load_effective_margins(...)`; `PricingEngine.compute_b2c(product, route, fees, scheme, margin)` → `PriceResult` with `.breakdown` (CostBreakdown: `net_eur, fx_applied, aed_before_freight, freight_aed, landed_aed, labeling_aed, channel_logistics_aed, cost_op_aed, fees_frac, scheme`).
- `_resolve_channel_id(channel_code, session)` helper exists in `channel_pricing.py`.

---

## File Structure
| File | Responsibility | Change |
|------|----------------|--------|
| `mt-pricing-backend/app/schemas/provenance_query.py` | Pydantic responses | **new** |
| `mt-pricing-backend/app/services/pricing/provenance_query.py` | read-only assembly | **new** |
| `mt-pricing-backend/app/api/routes/channel_pricing.py` | 5 GET handlers | **modify** |
| `_bmad-output/.../mt-api-contract-openapi.json` + `mt-pricing-frontend/lib/api/types.ts` | regen | **modify** |
| tests under `tests/services/pricing/`, `tests/api/` | tests | **new** |

---

## Task 1: Schemas + service (with pure-logic unit tests)

**Files:**
- Create `mt-pricing-backend/app/schemas/provenance_query.py`, `mt-pricing-backend/app/services/pricing/provenance_query.py`
- Test `mt-pricing-backend/tests/services/pricing/test_provenance_query_logic.py`

- [ ] **Step 1: failing unit test** (pure helpers — `is_healthy`, `is_stale`):
```python
from datetime import UTC, datetime, timedelta

from app.services.pricing.provenance_query import compute_is_healthy, compute_is_stale


def test_is_healthy_false_when_never_synced():
    assert compute_is_healthy(None, 1440, now=datetime.now(UTC)) is False


def test_is_healthy_true_within_sla():
    now = datetime.now(UTC)
    assert compute_is_healthy(now - timedelta(minutes=10), 1440, now=now) is True


def test_is_healthy_false_past_sla():
    now = datetime.now(UTC)
    assert compute_is_healthy(now - timedelta(minutes=2000), 1440, now=now) is False


def test_is_stale_true_when_valid_until_past():
    now = datetime.now(UTC)
    assert compute_is_stale(now - timedelta(days=1), now - timedelta(hours=1), now=now) is True


def test_is_stale_true_when_no_observed_at():
    assert compute_is_stale(None, None, now=datetime.now(UTC)) is True


def test_is_stale_false_when_valid():
    now = datetime.now(UTC)
    assert compute_is_stale(now - timedelta(hours=1), now + timedelta(days=1), now=now) is False
```

- [ ] **Step 2: run → FAIL** (ModuleNotFoundError).

- [ ] **Step 3: implement schemas** `app/schemas/provenance_query.py` (Pydantic v2 `BaseModel`):
```python
"""Read responses for F4 lineage/freshness/health endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SourceHealthItem(BaseModel):
    source_op: str
    last_sync_attempt_at: datetime | None = None
    last_sync_success_at: datetime | None = None
    last_error: str | None = None
    freshness_sla_minutes: int
    age_minutes: int | None = None
    is_healthy: bool


class SourceHealthResponse(BaseModel):
    sources: list[SourceHealthItem] = []
    blocking: list[str] = []


class FreshnessItem(BaseModel):
    scope: str            # 'param' | 'sku'
    key: str
    source_op: str
    observed_at: datetime | None = None
    valid_until: datetime | None = None
    is_stale: bool


class FreshnessResponse(BaseModel):
    items: list[FreshnessItem] = []


class LineageComponent(BaseModel):
    key: str
    value: Decimal
    source_op: str | None = None
    source_ref: str | None = None
    observed_at: datetime | None = None
    is_stale: bool = False


class LineageLayer(BaseModel):
    layer: int
    label: str
    amount_aed: Decimal
    components: list[LineageComponent] = []


class LineageResponse(BaseModel):
    sku: str
    field: str
    total_aed: Decimal
    layers: list[LineageLayer] = []


class AuditEntry(BaseModel):
    actor_id: str | None = None
    action: str
    before: dict | None = None
    after: dict | None = None
    reason: str | None = None
    event_at: datetime


class ParameterAuditResponse(BaseModel):
    key: str
    entity_type: str
    entity_id: str
    entries: list[AuditEntry] = []


class ProductCardResponse(BaseModel):
    sku: str
    master: dict
    price_history: list[dict] = []
    listing: dict | None = None
    proposals: list[dict] = []
```

- [ ] **Step 4: implement service** `app/services/pricing/provenance_query.py`. Start with the pure helpers (make Step-1 test pass) and the DB functions (covered by Task 2 integration tests):
```python
"""Read-only assembly for F4 lineage/freshness/health/card endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provenance import SourceHealth, SourceObservation

_CRITICAL = {"tesoreria_fx", "master_canal", "vendor_price_list"}


def compute_is_healthy(last_success, sla_minutes: int, *, now: datetime) -> bool:
    if last_success is None:
        return False
    return (now - last_success).total_seconds() / 60.0 < sla_minutes


def compute_is_stale(observed_at, valid_until, *, now: datetime) -> bool:
    if observed_at is None:
        return True
    if valid_until is not None and now > valid_until:
        return True
    return False


async def sources_health(session: AsyncSession) -> dict:
    now = datetime.now(UTC)
    rows = (await session.execute(select(SourceHealth))).scalars().all()
    items, blocking = [], []
    for r in rows:
        healthy = compute_is_healthy(r.last_sync_success_at, r.freshness_sla_minutes, now=now)
        age = (
            int((now - r.last_sync_success_at).total_seconds() / 60)
            if r.last_sync_success_at
            else None
        )
        items.append({
            "source_op": r.source_op, "last_sync_attempt_at": r.last_sync_attempt_at,
            "last_sync_success_at": r.last_sync_success_at, "last_error": r.last_error,
            "freshness_sla_minutes": r.freshness_sla_minutes, "age_minutes": age,
            "is_healthy": healthy,
        })
        if not healthy and r.source_op in _CRITICAL:
            blocking.append(r.source_op)
    return {"sources": items, "blocking": blocking}
```
(Implement `freshness`, `lineage`, `parameter_audit`, `product_card` as further functions — Task 2 specifies their exact behavior and tests. Keep each focused.)

- [ ] **Step 5: run → PASS** (6 passed). ruff + commit:
`git add app/schemas/provenance_query.py app/services/pricing/provenance_query.py tests/services/pricing/test_provenance_query_logic.py`
commit `feat(pricing): F4 schemas + provenance_query helpers (health/staleness)`.

---

## Task 2: The 5 read endpoints + integration tests

**Files:** Modify `app/api/routes/channel_pricing.py`; extend `app/services/pricing/provenance_query.py`; Test `mt-pricing-backend/tests/api/test_provenance_query_api.py`.

- [ ] **Step 1: failing integration test** `tests/api/test_provenance_query_api.py`. MIRROR the authed-client + channel seed from `tests/api/test_channel_pricing.py`. Assert:
  - `GET /pricing/{ch}/sources/health` → 200; `len(sources)==14`; every `is_healthy==False`; `blocking` contains `tesoreria_fx`,`master_canal`,`vendor_price_list`.
  - `GET /pricing/{ch}/freshness?selling_model=b2c` → 200; returns items with `is_stale` booleans.
  - `GET /pricing/{ch}/lineage/{sku}/cost` for a seeded SKU with logistics → 200; `total_aed>0`; `layers` non-empty. For unknown SKU → 404.
  - `GET /pricing/{ch}/parameters/route/audit` after a route-params PATCH (seed one audit_event or call the PATCH route) → entries non-empty with `action='update'`.
  - `GET /pricing/{ch}/products/{sku}/card` → 200; `master` populated; `listing` null and `proposals` [] when none; never 500.

- [ ] **Step 2: run → FAIL** (404 routes not found).

- [ ] **Step 3: implement** the remaining service functions + the 5 handlers.

Service (`provenance_query.py`) — add:
- `async def freshness(session, channel_id, selling_model)`: read the 5 config tables' rows for the channel (via existing models), emit a `FreshnessItem`-shaped dict per row using `compute_is_stale(observed_at, valid_until)`; key = table name + id. (Keep it to the param scope; SKU scope optional from `source_observations` if cheap.)
- `async def lineage(session, channel_id, sku, field, selling_model)`: use `ParameterLoader` + `PricingEngine.compute_b2c` (like `get_product_price`) to get a `PriceResult`; build layers from `result.breakdown` — for `field=='cost'`: layer1 "Compra MT" (net_eur, source from `pe_eur` observation/config), layer2 "Ruta" (fx_applied/freight_aed; source_op from `trade_route_params`), layer3 import (landed_aed), layer4 "Logística canal" (channel_logistics_aed), total = cost_op_aed; for `field=='ceiling'`: ceiling components (catalog_pvp_eur×fx + freight + import). Attach `source_op`/`source_ref`/`observed_at` from the config rows + `source_observations` for `pe_eur`/`catalog_pvp_eur`. Raise 404 (ValueError) if no product/logistics.
- `async def parameter_audit(session, channel_id, channel_code, key)`: resolve `(entity_type, entity_id)` from `key`: `"route"`→(`pricing_param`, route_id of the channel's fee row), `"fees"`→(`pricing_param`, fee row id), `"margin:<family_id>"`→(`margin_target`, family_id), `"override:<sku>"`→(`margin_override`, f"{channel_code}:{sku}"), `"optimization"`/`"import"`/`"proposal"`→(that entity_type, channel_code). Then `AuditRepository(session).list_for_entity(entity_type, entity_id)`.
- `async def product_card(session, channel_id, channel_code, sku)`: master from `products`; price_history from `source_observations` where sku=sku and target_field in ('pe_eur','catalog_pvp_eur') order observed_at desc limit 20; listing from `product_marketplace_listings` where product_sku=sku and marketplace=channel_code (or mapped) → first or None; proposals from `prices` where product_sku=sku and channel_id=channel_id order created_at desc limit 20 (+ optionally last approval events). Tolerate missing → null/[].

Handlers in `channel_pricing.py` (each `@router.get(...)`, `dependencies=[Depends(require_permissions("prices:read"))]`, `response_model=...`):
```python
@router.get("/sources/health", response_model=SourceHealthResponse, operation_id="sourcesHealth",
            dependencies=[Depends(require_permissions("prices:read"))])
async def get_sources_health(channel_code: str,
        session: Annotated[AsyncSession, Depends(get_db_session)]) -> SourceHealthResponse:
    await _resolve_channel_id(channel_code, session)
    return SourceHealthResponse(**await provenance_query.sources_health(session))
```
(Analogous for the other 4; lineage/card resolve `channel_id` first and map `ValueError`→`HTTPException(404)`.)

- [ ] **Step 4: run → PASS** (new test + `tests/api/test_channel_pricing.py` regression).

- [ ] **Step 5: ruff + commit** `feat(pricing): F4 read endpoints (health/freshness/lineage/audit/card)`.

---

## Task 3: OpenAPI regen + regression + lint/typecheck

- [ ] **Step 1:** Regenerate spec (F4 adds endpoints): `docker exec mt-backend sh -c "cd /app && python -m app.scripts.export_openapi --out /tmp/f4.json"`; `docker cp mt-backend:/tmp/f4.json` → BOTH `_bmad-output/planning-artifacts/mt-api-contract-openapi.json` and `mt-pricing-backend/_bmad-output/planning-artifacts/mt-api-contract-openapi.json`; then `npx --yes openapi-typescript@7.13.0 _bmad-output/planning-artifacts/mt-api-contract-openapi.json -o mt-pricing-frontend/lib/api/types.ts`. Confirm the new operationIds (`sourcesHealth`, etc.) appear.
- [ ] **Step 2:** Full suite: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/services/pricing/ tests/api/test_channel_pricing.py tests/api/test_provenance_query_api.py -o addopts='' -q"` → PASS.
- [ ] **Step 3:** `ruff check` + `ruff format` + `mypy app/services/pricing/provenance_query.py app/schemas/provenance_query.py` → clean.
- [ ] **Step 4:** Commit `feat(pricing): regenerate OpenAPI + types for F4 endpoints` (spec + types.ts).

---

## Self-Review
- Spec §4.1–4.5 → Tasks 1 (schemas+health) + 2 (4 endpoints). §5 errors → 404 mapping in Task 2. §6 tests → Tasks 1/2/3. §OpenAPI → Task 3.
- Placeholder scan: handlers/service have concrete code; the per-table freshness/lineage assembly references exact models/columns from "Resolved facts" — implementer reads them. Audit `key` mapping fully specified.
- Type consistency: `compute_is_healthy`/`compute_is_stale` signatures match tests; response models match service dict keys.
- Known follow-ups: frontend drawers (UI cycle); jobs populating `source_health` (F2/F3/F6); SKU-scope freshness can extend later.
