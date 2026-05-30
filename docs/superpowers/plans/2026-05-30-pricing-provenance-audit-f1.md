# Pricing Desk F1 — Provenance + Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the provenance + audit base to the Channel Pricing Engine: a non-destructive Alembic migration (provenance columns, `source_observations`, `source_health`, `pricing_scenarios` extension) plus code wiring so every Desk mutation records who/when/source and emits an `audit_events` row.

**Architecture:** One Alembic revision off HEAD `20260603_147` (created/reviewed by the `db-migrator`/`migration-reviewer` agents). New ORM models + columns. A small `provenance.py` helper (`stamp`, `emit_audit`, `record_observation`) that wraps the existing `AuditRepository.record` (hash-chained `audit_events`). The 6 mutation routes in `channel_pricing.py` call the helper, threading the authenticated `User`.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 async, Alembic, FastAPI, pytest (Postgres). Backend `mt-pricing-backend/`. Spec: `docs/superpowers/specs/2026-05-30-pricing-provenance-audit-f1-design.md`.

**Run tests (Docker; uv fails locally):** code is live-mounted in container `mt-backend` at `/app`:
`docker exec mt-backend sh -c "cd /app && python -m pytest <path> -o addopts='' -q"`

**Resolved facts (from research):**
- Audit emitter to reuse: `AuditRepository(session).record(entity_type, entity_id, action, actor_id=, actor_role=, before=, after=, reason=)` in `app/repositories/audit.py` (sanitizes Decimal/UUID/datetime, flushes, hash-chain trigger fires).
- `channel_pricing.py` routes already receive the user: `_user: Annotated[User, Depends(require_permissions("prices:..."))]` → use `_user.id`. `propose_prices_selected` currently passes `proposed_by=None` and has NO user dep — add one.
- All `updated_by`/`created_by` columns are 100% NULL today → `TEXT→uuid` is a trivial type change, no backfill.
- Tables: `trade_route_params`, `channel_fee_params`, `channel_margin_targets`, `channel_product_logistics` have `updated_at`+`updated_by TEXT`. `channel_margin_overrides` has `created_at`+`created_by TEXT` (no `updated_by`). `pricing_scenarios` has `snapshot_at`+`created_by TEXT`.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `mt-pricing-backend/alembic/versions/2026MMDD_148_pricing_provenance_audit.py` | Migration | **new** (db-migrator) |
| `mt-pricing-backend/app/db/models/channel_pricing.py` | Channel config models | **modify** — add provenance cols + `updated_by/created_by` uuid; `PricingScenario` `kind`/`retention_until` |
| `mt-pricing-backend/app/db/models/provenance.py` | New ORM | **new** — `SourceObservation`, `SourceHealth` |
| `mt-pricing-backend/app/db/models/__init__.py` | model registry | **modify** — export new models |
| `mt-pricing-backend/app/db/enums.py` | enums | **modify** — `SourceOp`, `SnapshotKind` Python enums |
| `mt-pricing-backend/app/services/pricing/provenance.py` | helper | **new** — `stamp`, `emit_audit`, `record_observation` |
| `mt-pricing-backend/app/api/routes/channel_pricing.py` | routes | **modify** — wire provenance/audit/actor on 6 mutations |
| tests under `tests/db/`, `tests/services/pricing/`, `tests/api/` | tests | **new/modify** |

---

## Task 1: Migration (DDL) — via db-migrator + migration-reviewer

**Files:** Create `mt-pricing-backend/alembic/versions/2026MMDD_148_pricing_provenance_audit.py`

- [ ] **Step 1: Create the migration with the `db-migrator` agent**

Dispatch the `db-migrator` agent with this exact DDL (from spec §3), down_revision = `20260603_147`, naming `2026MMDD_148_pricing_provenance_audit`:

1. **Enums** (`public.*`): `source_op` = `(compras_po, importacion_dua, tesoreria_fx, master_canal, vendor_price_list, settlement_amazon, settlement_noon, contabilidad_analitica, master_fiscal, marketing_budget, postventa_rma, master_comercial, decision_local, manual)`; `snapshot_kind` = `(manual_a, manual_b, auto_pre_optimization, auto_pre_import, auto_pre_bulk_margin_change, auto_pre_sync_param)`. Create with `sa.Enum(..., name=..., create_type=True)` in `upgrade`; drop in `downgrade`.
2. **Provenance columns** on `trade_route_params`, `channel_fee_params`, `channel_margin_targets`, `channel_margin_overrides`, `channel_product_logistics`:
   `source_op source_op NOT NULL DEFAULT 'manual'`, `source_ref TEXT`, `observed_at timestamptz`, `valid_until timestamptz`, `override_by uuid REFERENCES users(id) ON DELETE SET NULL`, `override_reason TEXT`. Add `created_at timestamptz NOT NULL DEFAULT now()` + `created_by uuid REFERENCES users(id) ON DELETE SET NULL` where the table lacks them. CHECK `(override_by IS NULL OR override_reason IS NOT NULL)` named `ck_<table>_override_reason`.
3. **`updated_by`/`created_by` TEXT→uuid** (all NULL → safe): for the 4 tables with `updated_by TEXT` use `ALTER COLUMN updated_by TYPE uuid USING updated_by::uuid` + add FK to `users(id)`. For `channel_margin_overrides` and `pricing_scenarios`, same for `created_by TEXT→uuid`.
4. **`source_observations`** and **`source_health`** tables exactly per spec §3.3 / §3.4 (indexes included).
5. **Seed `source_health`**: one row per `source_op` value with `freshness_sla_minutes`: `tesoreria_fx`=1440, `master_canal`=1440, `vendor_price_list`=129600, `compras_po`=129600, `importacion_dua`=129600, `settlement_amazon`/`settlement_noon`=86400, `contabilidad_analitica`=86400, `master_fiscal`=525600, `marketing_budget`=86400, `postventa_rma`=129600, `master_comercial`=129600, `decision_local`=525600, `manual`=525600.
6. **`pricing_scenarios`**: add `kind snapshot_kind NOT NULL DEFAULT 'manual_a'`, `retention_until timestamptz`; backfill `kind = 'manual_a'` where `slot='A'`, `'manual_b'` where `slot='B'`; drop UNIQUE `(channel_id, selling_model, slot)` and create partial unique `uq_pricing_scenarios_manual (channel_id, selling_model, slot) WHERE kind IN ('manual_a','manual_b')`; add `idx_pricing_scenarios_retention (retention_until) WHERE retention_until IS NOT NULL`.

`downgrade` must reverse everything (drop columns/tables/indexes, revert `updated_by`/`created_by` to TEXT, restore the original UNIQUE, drop enums).

- [ ] **Step 2: Apply + verify upgrade/downgrade**

Run: `docker exec mt-backend sh -c "cd /app && alembic upgrade head && alembic downgrade -1 && alembic upgrade head"`
Expected: clean up→down→up (no errors). Confirm new tables: `docker exec mt-backend sh -c "cd /app && python -c \"import asyncio,os;from sqlalchemy import text;from app.db import make_engine;asyncio.run((lambda: None)())\""` — or simpler, a model test in Task 2.

- [ ] **Step 3: Review with `migration-reviewer` agent**

Dispatch `migration-reviewer` on the new migration file. Fix any findings (enum `create_type`, index coverage, reversibility, the `public.*` split). Re-review until clean.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/alembic/versions/2026MMDD_148_pricing_provenance_audit.py
git commit -m "feat(db): F1 migration — provenance columns, source_observations, source_health"
```

---

## Task 2: ORM models

**Files:**
- Modify: `mt-pricing-backend/app/db/enums.py`, `app/db/models/channel_pricing.py`, `app/db/models/__init__.py`
- Create: `mt-pricing-backend/app/db/models/provenance.py`
- Test: `mt-pricing-backend/tests/db/test_provenance_models.py`

- [ ] **Step 1: Write the failing test**

`tests/db/test_provenance_models.py`:
```python
"""Provenance/audit model + migration smoke (F1)."""
from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_source_health_seeded_one_row_per_source_op(db_session: AsyncSession):
    from app.db.enums import SourceOp

    n = (await db_session.execute(text("select count(*) from source_health"))).scalar_one()
    assert n == len(list(SourceOp))


async def test_source_observation_roundtrip(db_session: AsyncSession):
    from app.db.models.provenance import SourceObservation
    from app.db.enums import SourceOp
    from datetime import datetime, UTC

    obs = SourceObservation(
        source_op=SourceOp.VENDOR_PRICE_LIST.value,
        target_table="products",
        target_field="pe_eur",
        sku=None,
        value_numeric=Decimal("1.05"),
        source_ref="vendor_product_conditions:abc@2026-05-01",
        observed_at=datetime.now(UTC),
    )
    db_session.add(obs)
    await db_session.flush()
    assert obs.id is not None


async def test_channel_fee_params_has_provenance_columns(db_session: AsyncSession):
    cols = (await db_session.execute(text(
        "select column_name from information_schema.columns "
        "where table_name='channel_fee_params'"
    ))).scalars().all()
    assert {"source_op", "observed_at", "override_by", "override_reason"} <= set(cols)
```

- [ ] **Step 2: Run — expect FAIL** (no `SourceOp` enum / `provenance` model)

Run: `docker exec mt-backend sh -c "cd /app && python -m pytest tests/db/test_provenance_models.py -o addopts='' -q"`

- [ ] **Step 3: Implement**

(a) `app/db/enums.py` — add:
```python
import enum


class SourceOp(str, enum.Enum):
    COMPRAS_PO = "compras_po"
    IMPORTACION_DUA = "importacion_dua"
    TESORERIA_FX = "tesoreria_fx"
    MASTER_CANAL = "master_canal"
    VENDOR_PRICE_LIST = "vendor_price_list"
    SETTLEMENT_AMAZON = "settlement_amazon"
    SETTLEMENT_NOON = "settlement_noon"
    CONTABILIDAD_ANALITICA = "contabilidad_analitica"
    MASTER_FISCAL = "master_fiscal"
    MARKETING_BUDGET = "marketing_budget"
    POSTVENTA_RMA = "postventa_rma"
    MASTER_COMERCIAL = "master_comercial"
    DECISION_LOCAL = "decision_local"
    MANUAL = "manual"


class SnapshotKind(str, enum.Enum):
    MANUAL_A = "manual_a"
    MANUAL_B = "manual_b"
    AUTO_PRE_OPTIMIZATION = "auto_pre_optimization"
    AUTO_PRE_IMPORT = "auto_pre_import"
    AUTO_PRE_BULK_MARGIN_CHANGE = "auto_pre_bulk_margin_change"
    AUTO_PRE_SYNC_PARAM = "auto_pre_sync_param"
```
(Match the existing enum style in `enums.py` — if it uses a shared base, follow it.)

(b) `app/db/models/provenance.py` — new models `SourceObservation` and `SourceHealth` mirroring the migration columns (use `PG_ENUM("...", name="source_op", create_type=False)` for `source_op`, `UUID_PG`, `Numeric(18,8)`, `JSONB` not needed). Follow the column/type/index definitions from spec §3.3/§3.4 and the patterns in `channel_pricing.py`.

(c) `app/db/models/channel_pricing.py` — add to the 5 config model classes: `source_op` (`PG_ENUM(..., name="source_op", create_type=False)`), `source_ref: Mapped[str|None]`, `observed_at`, `valid_until`, `override_by` (UUID_PG FK), `override_reason`, and change `updated_by`/`created_by` to `Mapped[UUID|None]` (UUID_PG FK). Add `created_at`/`created_by` to classes lacking them. Extend `PricingScenario` with `kind` (`PG_ENUM(..., name="snapshot_kind", create_type=False)`) and `retention_until`.

(d) `app/db/models/__init__.py` — import + add `SourceObservation`, `SourceHealth` to `__all__`.

- [ ] **Step 4: Run — expect PASS** (3 passed)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/db/enums.py mt-pricing-backend/app/db/models/provenance.py mt-pricing-backend/app/db/models/channel_pricing.py mt-pricing-backend/app/db/models/__init__.py mt-pricing-backend/tests/db/test_provenance_models.py
git commit -m "feat(db): F1 ORM — SourceObservation/SourceHealth + provenance columns"
```

---

## Task 3: provenance helper

**Files:**
- Create: `mt-pricing-backend/app/services/pricing/provenance.py`
- Test: `mt-pricing-backend/tests/services/pricing/test_provenance_helper.py`

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal
from uuid import uuid4

from app.services.pricing.provenance import stamp


def test_stamp_adds_actor_source_and_observed_at():
    actor = uuid4()
    out = stamp({"fx_rate": Decimal("4.28")}, actor_id=actor, source_op="decision_local",
                updated_field="updated_by")
    assert out["fx_rate"] == Decimal("4.28")
    assert out["updated_by"] == actor
    assert out["source_op"] == "decision_local"
    assert out["observed_at"] is not None


def test_stamp_created_field_variant():
    actor = uuid4()
    out = stamp({"margin_override_pct": Decimal("12")}, actor_id=actor,
                source_op="decision_local", updated_field="created_by")
    assert out["created_by"] == actor
```

- [ ] **Step 2: Run — expect FAIL** (ModuleNotFoundError)

- [ ] **Step 3: Implement** `app/services/pricing/provenance.py`:
```python
"""Provenance + audit helpers for Channel Pricing mutations (F1)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditRepository


def stamp(
    values: dict[str, Any],
    *,
    actor_id: UUID | None,
    source_op: str = "manual",
    source_ref: str | None = None,
    observed_at: datetime | None = None,
    updated_field: str = "updated_by",
) -> dict[str, Any]:
    """Return `values` augmented with provenance fields for an UPDATE/upsert."""
    out = dict(values)
    out[updated_field] = actor_id
    out["source_op"] = source_op
    out["observed_at"] = observed_at or datetime.now(UTC)
    if source_ref is not None:
        out["source_ref"] = source_ref
    return out


async def emit_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: UUID | None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> None:
    """Write one audit_events row (hash-chained) reusing AuditRepository."""
    await AuditRepository(session).record(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_role=None if actor_id else "system",
        before=before,
        after=after,
        reason=reason,
    )


async def record_observation(
    session: AsyncSession,
    *,
    source_op: str,
    target_table: str,
    target_field: str,
    value: Any,
    sku: str | None = None,
    channel_id: UUID | None = None,
    source_ref: str | None = None,
    observed_at: datetime | None = None,
) -> None:
    """Append a field-level observation to source_observations."""
    from decimal import Decimal

    from app.db.models.provenance import SourceObservation

    is_num = isinstance(value, (int, float, Decimal))
    session.add(
        SourceObservation(
            source_op=source_op,
            target_table=target_table,
            target_field=target_field,
            sku=sku,
            channel_id=channel_id,
            value_numeric=Decimal(str(value)) if is_num else None,
            value_text=None if is_num else (str(value) if value is not None else None),
            source_ref=source_ref,
            observed_at=observed_at or datetime.now(UTC),
        )
    )
    await session.flush()
```

- [ ] **Step 4: Run — expect PASS** (2 passed). `emit_audit`/`record_observation` are covered by Task 4 integration tests.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/pricing/provenance.py mt-pricing-backend/tests/services/pricing/test_provenance_helper.py
git commit -m "feat(pricing): provenance helper (stamp/emit_audit/record_observation)"
```

---

## Task 4: Wire routes (provenance + audit + actor)

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/channel_pricing.py`
- Test: `mt-pricing-backend/tests/api/test_channel_pricing_provenance.py`

- [ ] **Step 1: Write the failing integration test**

`tests/api/test_channel_pricing_provenance.py` — using the existing app test client + auth fixtures (read `tests/api/test_channel_pricing.py` for the client/auth fixture pattern and reuse it). Assert:
```python
# pseudocode skeleton — adapt to the repo's api test fixtures (authenticated client)
async def test_patch_route_params_stamps_provenance_and_audit(authed_client, seeded_channel, db_session):
    r = await authed_client.patch(f"/api/v1/pricing/{seeded_channel.code}/route-params",
                                  json={"fx_rate": "4.30"})
    assert r.status_code == 200
    # provenance stamped
    row = (await db_session.execute(text(
        "select source_op, updated_by, observed_at from trade_route_params limit 1"))).one()
    assert row.source_op == "decision_local" and row.updated_by is not None and row.observed_at is not None
    # audit emitted
    n = (await db_session.execute(text(
        "select count(*) from audit_events where entity_type='pricing_param' and action='update'"))).scalar_one()
    assert n >= 1
```
Add a second test for `propose-selected` asserting the created `prices` row has `proposed_by` non-NULL and an `audit_events` row with `entity_type='price_proposal'`.

> The exact authenticated-client fixture and how to seed a channel must follow `tests/api/test_channel_pricing.py`. If api tests there use a synchronous TestClient with a permission-bearing user, mirror it.

- [ ] **Step 2: Run — expect FAIL** (provenance not stamped / audit not emitted)

- [ ] **Step 3: Implement the wiring** in `channel_pricing.py`. For each mutation, after resolving `channel_id` and BEFORE/around the write, use the helper. Concrete edits:

`update_route_params` / `update_fee_params`: thread `_user` (already a param), and change the UPDATE values:
```python
from app.services.pricing.provenance import emit_audit, stamp
# inside update_route_params, after computing `values = body.model_dump(exclude_unset=True)`:
if values:
    before = TradeRouteParamsRead.model_validate(route_row).model_dump(mode="json")  # load row first
    values = stamp(values, actor_id=_user.id, source_op="decision_local", updated_field="updated_by")
    await session.execute(update(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id).values(**values))
    await emit_audit(session, entity_type="pricing_param", entity_id=str(fee_row.route_id),
                     action="update", actor_id=_user.id, before=before, after=values)
    await session.commit()
```
Apply the same shape to `update_fee_params` (`entity_id=str(channel fee row id)`).

`upsert_margin_target`: add `source_op`/`updated_by` to the pg_insert values via `stamp(...)`; before deleting family overrides, capture them as `before` and `emit_audit(entity_type="margin_target", action="update", before=<deleted overrides>, after=<target>)`.

`upsert_margin_override`: `stamp(..., updated_field="created_by")`; if `body.reason` indicates an override of an automatic value, also set `override_by=_user.id`, `override_reason=body.reason`; `emit_audit(entity_type="margin_override", action="update", ...)`.

`apply_optimization`: before persisting overrides, `emit_audit(entity_type="optimization", entity_id=channel_code, action="optimize_apply", actor_id=_user.id, after={"count": len(results)})`; set `source_op="decision_local"`, `created_by=_user.id` on the upserted overrides.

`import_catalog` / `import_logistics`: on confirm, `emit_audit(entity_type="catalog_import", action="import", actor_id=_user.id, after={"upserted": upserted})`; for each upserted product field, `record_observation(source_op="master_canal", target_table="products", target_field="catalog_pvp_eur"/"pe_eur", value=..., sku=..., source_ref=file.filename)`.

`propose_prices_selected`: add `_user: Annotated[User, Depends(require_permissions("prices:propose"))]` param; pass `proposed_by=_user.id` to `proposer.propose(...)`; after, `emit_audit(entity_type="price_proposal", entity_id=channel_code, action="propose", actor_id=_user.id, after={"skus": body.skus})`.

(`stamp` for pg_insert upserts: merge the provenance keys into the `.values(...)` dict and the `on_conflict_do_update set_`.)

- [ ] **Step 4: Run — expect PASS**

Run the new test + the existing `tests/api/test_channel_pricing.py` (regression):
`docker exec mt-backend sh -c "cd /app && python -m pytest tests/api/test_channel_pricing.py tests/api/test_channel_pricing_provenance.py -o addopts='' -q"`

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/api/routes/channel_pricing.py mt-pricing-backend/tests/api/test_channel_pricing_provenance.py
git commit -m "feat(pricing): wire provenance + audit + actor into Desk mutations (F1)"
```

---

## Task 5: Regression + lint + typecheck + OpenAPI

- [ ] **Step 1:** Full pricing/db suites
`docker exec mt-backend sh -c "cd /app && python -m pytest tests/db/test_provenance_models.py tests/services/pricing/ tests/api/test_channel_pricing.py tests/api/test_channel_pricing_provenance.py -o addopts='' -q"` → PASS
- [ ] **Step 2:** `docker exec mt-backend sh -c "cd /app && ruff check <changed files> && ruff format <changed files> && mypy app/services/pricing/provenance.py app/db/models/provenance.py"` → clean
- [ ] **Step 3:** OpenAPI: F1 changes no route signatures/response schemas (only behavior + DB). Confirm no drift; if `propose_prices_selected` signature changed (added a dep param — deps don't affect the schema), regenerate to be safe: run the container export → sync root spec + `lib/api/types.ts` (per the repo's `openapi-gen.sh`). Commit if changed.
- [ ] **Step 4:** Commit any format/openapi changes.

---

## Self-Review

**Spec coverage:** §3.1 enums → Task 1/2. §3.2 provenance cols → Task 1/2. §3.3 source_observations → Task 1/2/3. §3.4 source_health + seed → Task 1 (seed) + Task 2 (seed test). §3.5 pricing_scenarios → Task 1/2. §4.1 helper → Task 3. §4.2 route wiring → Task 4. §4.3 PIR connection → `record_observation(source_op='vendor_price_list', ...)` available (wired where PIR-derived cost is recorded; F0.5 ingest is the caller — noted as follow-up since F0.5 already merged, a small follow-up wires it). Testing §6 → Tasks 2/4/5.

**Gap noted:** the PIR→observation wiring lives in the F0.5 invoice-ingest path (already merged). F1 provides `source_op='vendor_price_list'` + `record_observation`; a 1-line follow-up in `invoice_ingest_service` to emit the observation is **in scope of Task 4** if that file is touched, else a fast follow-up. Added explicitly to Task 4 scope.

**Placeholder scan:** Task 4 test is a skeleton tied to the repo's api-test fixtures (the implementer reads `test_channel_pricing.py` to mirror the authenticated client) — not a placeholder for logic, but the fixture wiring is repo-specific. All code steps have concrete code.

**Type consistency:** `stamp(updated_field=...)` used consistently; `emit_audit`/`record_observation` signatures match Task 3 ↔ Task 4 calls; `SourceOp`/`SnapshotKind` values match migration enums.

**Known follow-ups:** `GET /sources/health` + `/freshness` endpoints and lineage drawers (F4); jobs populating `source_health` (F2/F3/F6); audit on `vendor_product_conditions` (proveedores module).
