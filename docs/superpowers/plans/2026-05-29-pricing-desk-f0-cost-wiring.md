# Pricing Desk F0 — Cost Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Pricing Desk use the **real landed cost** computed from goods receipts (`inventory_positions.map_aed`) when it exists, instead of always deriving cost from the manual `products.pe_eur`.

**Architecture:** The MAP subsystem (`goods_receipts → MAPService → inventory_positions.map_aed`) already computes the real landed-in-Dubai cost per SKU. The pricing engine's `_landed_b2c/_landed_b2b` currently derive that landed cost from `pe_eur` (discount→FX→freight→import). We add an optional **`landed_cost_aed` override** to `ProductPricingData`; when present the engine uses it as the landed value (layers 1‑3) and still adds channel logistics + margin + fees (layers 4‑5) on top. `ParameterLoader` populates the override from `inventory_positions` (per‑SKU; landed cost is supplier/route‑level, not channel‑scheme‑level). When no receipt exists, behaviour is unchanged (fallback to `pe_eur`).

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 async, FastAPI, pytest (unit + integration with Postgres container). Backend: `mt-pricing-backend/`.

**Scope:** This is **F0 only** (the keystone). F0.5 (invoice → goods receipt ingestion) and F1+ (provenance/audit, FX auto, etc.) are separate plans — see `docs/architecture/pricing-desk/07-implementation-plan.md`. F0 makes the wiring work and is testable on its own (seeded inventory position in tests); it becomes valuable in production once F0.5 feeds real receipts.

**Design decisions (locked):**
- Landed cost is resolved **per SKU**, scheme‑agnostic: landed‑to‑warehouse cost (layers 1‑3) does not depend on the channel fulfilment scheme (which only affects layer 4). If a SKU has multiple `inventory_positions` (multi‑supplier), pick the row with the **highest `qty_on_hand`** and non‑null `map_aed` (the dominant lot). Multi‑supplier blending is out of scope for F0.
- `landed_cost_aed` is a **per‑unit** AED cost. B2C landed = `landed_cost_aed`; B2B landed = `landed_cost_aed × units_per_box`.
- Provenance **display** (badges, `source_op` in the API) is **F1**, not F0. F0 only wires the value. The override carries no source string yet.
- `breakdown.landed_aed` reflects the override automatically (it is the `landed` variable). `breakdown.net_eur`/`aed_before_freight` keep showing the `pe_eur`‑derived estimate in F0 — refined in F1/lineage. Acceptable.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `mt-pricing-backend/app/services/pricing/schemas.py` | Engine input dataclasses | Add optional `landed_cost_aed` to `ProductPricingData` |
| `mt-pricing-backend/app/services/pricing/engine.py` | Pure cost computation | `_landed_b2c`/`_landed_b2b` honour the override |
| `mt-pricing-backend/app/services/pricing/loader.py` | DB → dataclasses | Populate `landed_cost_aed` from `inventory_positions` |
| `mt-pricing-backend/tests/services/pricing/test_engine.py` | Engine unit tests | Add override tests + regression |
| `mt-pricing-backend/tests/services/pricing/test_loader_cost.py` (new) | Loader integration test | Seed product + inventory_position, assert override populated |

---

## Task 1: Add `landed_cost_aed` override to `ProductPricingData`

**Files:**
- Modify: `mt-pricing-backend/app/services/pricing/schemas.py:71-89`
- Test: `mt-pricing-backend/tests/services/pricing/test_engine.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/services/pricing/test_engine.py`:

```python
def test_product_pricing_data_accepts_landed_cost_override():
    from app.services.pricing.schemas import ProductLogistics, ProductPricingData
    from app.db.enums import CeilingBasis, FulfillmentScheme

    p = ProductPricingData(
        sku="TEST1",
        family_id="fam-1",
        pe_eur=Decimal("10"),
        catalog_pvp_eur=Decimal("40"),
        units_per_box=10,
        weight_kg=Decimal("0.5"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=ProductLogistics(
            inbound_fee_aed=Decimal("0"),
            storage_fee_aed=Decimal("0"),
            fulfillment_fee_aed=Decimal("0"),
            default_scheme=FulfillmentScheme.CANAL_FULL,
        ),
        landed_cost_aed=Decimal("47.5"),
    )
    assert p.landed_cost_aed == Decimal("47.5")


def test_product_pricing_data_landed_cost_defaults_none():
    from app.services.pricing.schemas import ProductLogistics, ProductPricingData
    from app.db.enums import CeilingBasis, FulfillmentScheme

    p = ProductPricingData(
        sku="TEST2",
        family_id="fam-1",
        pe_eur=Decimal("10"),
        catalog_pvp_eur=Decimal("40"),
        units_per_box=1,
        weight_kg=Decimal("0"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=ProductLogistics(
            inbound_fee_aed=Decimal("0"),
            storage_fee_aed=Decimal("0"),
            fulfillment_fee_aed=Decimal("0"),
            default_scheme=FulfillmentScheme.CANAL_FULL,
        ),
    )
    assert p.landed_cost_aed is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/test_engine.py::test_product_pricing_data_accepts_landed_cost_override -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'landed_cost_aed'`

- [ ] **Step 3: Write minimal implementation**

In `schemas.py`, add the field to `ProductPricingData` (after `logistics`, keep it last so positional construction elsewhere is unaffected):

```python
@dataclass(frozen=True)
class ProductPricingData:
    """All product-level data needed for price calculation."""

    sku: str
    family_id: str
    pe_eur: Decimal
    catalog_pvp_eur: Decimal
    units_per_box: int
    weight_kg: Decimal
    b2c_labeling_aed: Decimal
    ceiling_basis: CeilingBasis
    logistics: ProductLogistics
    # Real landed cost per unit in AED from goods receipts (MAP). When set,
    # the engine uses it as layers 1-3 instead of deriving from pe_eur. F0.
    landed_cost_aed: Optional[Decimal] = None

    def __post_init__(self) -> None:
        if self.units_per_box < 1:
            raise ValueError(
                f"units_per_box must be >= 1, got {self.units_per_box} for sku={self.sku}"
            )
```

`Optional` is already imported in `schemas.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/test_engine.py::test_product_pricing_data_accepts_landed_cost_override tests/services/pricing/test_engine.py::test_product_pricing_data_landed_cost_defaults_none -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/pricing/schemas.py mt-pricing-backend/tests/services/pricing/test_engine.py
git commit -m "feat(pricing): add optional landed_cost_aed override to ProductPricingData"
```

---

## Task 2: Engine honours `landed_cost_aed` in `_landed_b2c` / `_landed_b2b`

**Files:**
- Modify: `mt-pricing-backend/app/services/pricing/engine.py:142-159`
- Test: `mt-pricing-backend/tests/services/pricing/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/services/pricing/test_engine.py` (reuse existing `route`, `fees`, `fba_scheme`, `brass_valve_logistics` fixtures):

```python
def _product_with(landed, logistics, **kw):
    from app.services.pricing.schemas import ProductPricingData
    from app.db.enums import CeilingBasis
    base = dict(
        sku="OVR1", family_id="fam-1", pe_eur=Decimal("10"),
        catalog_pvp_eur=Decimal("40"), units_per_box=10, weight_kg=Decimal("0.5"),
        b2c_labeling_aed=Decimal("0"), ceiling_basis=CeilingBasis.CATALOG_PVP,
        logistics=logistics, landed_cost_aed=landed,
    )
    base.update(kw)
    return ProductPricingData(**base)


def test_b2c_uses_landed_override_when_present(route, fees, fba_scheme, brass_valve_logistics):
    product = _product_with(Decimal("47.5"), brass_valve_logistics)
    r = PricingEngine.compute_b2c(product, route, fees, fba_scheme, Decimal("12"))
    # cost_op = landed(47.5) + labeling(0) + channel_logistics
    expected_logistics = PricingEngine._logistics_cost(brass_valve_logistics, fba_scheme, fees)
    assert r.breakdown.landed_aed == Decimal("47.5")
    assert r.cost_op_aed == (Decimal("47.5") + expected_logistics).quantize(Decimal("0.0001"))


def test_b2b_scales_landed_override_by_units_per_box(route, fees, fba_scheme, brass_valve_logistics):
    product = _product_with(Decimal("47.5"), brass_valve_logistics, units_per_box=10)
    r = PricingEngine.compute_b2b(product, route, fees, fba_scheme, Decimal("12"))
    # B2B landed = 47.5 * 10 = 475
    assert r.breakdown.landed_aed == Decimal("475.0")


def test_landed_override_none_keeps_pe_eur_derivation(route, fees, fba_scheme, brass_valve_logistics):
    """Regression: no override → engine derives landed from pe_eur exactly as before."""
    product = _product_with(None, brass_valve_logistics)
    r = PricingEngine.compute_b2c(product, route, fees, fba_scheme, Decimal("12"))
    expected_landed = PricingEngine._landed_b2c(product, route, fees)
    assert r.breakdown.landed_aed == expected_landed
    assert r.breakdown.landed_aed != Decimal("47.5")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/test_engine.py::test_b2c_uses_landed_override_when_present -v`
Expected: FAIL (override ignored → `landed_aed` is the pe_eur-derived value, not 47.5)

- [ ] **Step 3: Write minimal implementation**

In `engine.py`, modify the two private helpers to return the override first:

```python
    @staticmethod
    def _landed_b2c(product: ProductPricingData, route: RouteParams, fees: ChannelFees) -> Decimal:
        """Cost of one unit landed in Dubai warehouse (layers 1-3)."""
        if product.landed_cost_aed is not None:
            return product.landed_cost_aed
        net_eur = product.pe_eur * (1 - fees.mt_discount_pct / 100)
        fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
        aed = net_eur * fx
        freight = PricingEngine._freight_per_unit(product, route)
        return (aed + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _landed_b2b(product: ProductPricingData, route: RouteParams, fees: ChannelFees) -> Decimal:
        """Cost of one box landed in Dubai warehouse (layers 1-3)."""
        n = Decimal(str(product.units_per_box))
        if product.landed_cost_aed is not None:
            return product.landed_cost_aed * n
        net_eur_box = product.pe_eur * n * (1 - fees.mt_discount_pct / 100)
        fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
        aed_box = net_eur_box * fx
        freight = PricingEngine._freight_per_box(product, route)
        return (aed_box + freight) * PricingEngine._import_factor(route)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/test_engine.py -v`
Expected: PASS (all engine tests, including the 3 new + existing regression suite green)

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/pricing/engine.py mt-pricing-backend/tests/services/pricing/test_engine.py
git commit -m "feat(pricing): engine uses real landed_cost_aed override when present"
```

---

## Task 3: `ParameterLoader` populates `landed_cost_aed` from `inventory_positions`

**Files:**
- Modify: `mt-pricing-backend/app/services/pricing/loader.py:106-161`
- Test: `mt-pricing-backend/tests/services/pricing/test_loader_cost.py` (new)

- [ ] **Step 1: Write the failing integration test**

Create `mt-pricing-backend/tests/services/pricing/test_loader_cost.py`:

```python
"""Integration test: ParameterLoader populates landed_cost_aed from inventory_positions."""
from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def _seed_product_and_channel(db_session: AsyncSession, sku: str, channel_code: str):
    from app.db.models.channels import Channel
    from app.db.models.product import Product
    from app.db.models.channel_pricing import (
        ChannelFeeParams, ChannelProductLogistics, TradeRouteParams,
    )

    ch = Channel(code=channel_code, name=channel_code)
    db_session.add(ch)
    await db_session.flush()

    route = TradeRouteParams(route_code=f"r-{channel_code}", fx_rate=Decimal("4.28"))
    db_session.add(route)
    await db_session.flush()
    db_session.add(ChannelFeeParams(channel_id=ch.id, route_id=route.id))

    db_session.add(Product(
        sku=sku, name="Test", family_id=None,
        pe_eur=Decimal("10"), catalog_pvp_eur=Decimal("40"),
        units_per_box=10, weight=Decimal("0.5"), active=True,
        ceiling_basis="catalog_pvp",
    ))
    await db_session.flush()
    db_session.add(ChannelProductLogistics(
        product_sku=sku, channel_id=ch.id,
        inbound_fee_aed=Decimal("0"), storage_fee_aed=Decimal("0"),
        fulfillment_fee_aed=Decimal("0"), default_scheme="canal_full",
    ))
    await db_session.flush()
    return ch.id


async def test_loader_sets_landed_cost_from_inventory_position(db_session: AsyncSession):
    from app.db.models.inventory import InventoryPosition
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_product_and_channel(db_session, "COSTSKU1", "ch_cost1")
    db_session.add(InventoryPosition(
        sku="COSTSKU1", supplier_code="MT", scheme_code="DIRECT_B2C",
        qty_on_hand=Decimal("100"), map_aed=Decimal("47.5"),
    ))
    await db_session.flush()

    loader = ParameterLoader(db_session)
    products = await loader.load_product_data(channel_id, skus=["COSTSKU1"])

    assert len(products) == 1
    assert products[0].landed_cost_aed == Decimal("47.5")


async def test_loader_landed_cost_none_when_no_position(db_session: AsyncSession):
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_product_and_channel(db_session, "COSTSKU2", "ch_cost2")

    loader = ParameterLoader(db_session)
    products = await loader.load_product_data(channel_id, skus=["COSTSKU2"])

    assert len(products) == 1
    assert products[0].landed_cost_aed is None


async def test_loader_picks_highest_qty_position(db_session: AsyncSession):
    from app.db.models.inventory import InventoryPosition
    from app.services.pricing.loader import ParameterLoader

    channel_id = await _seed_product_and_channel(db_session, "COSTSKU3", "ch_cost3")
    db_session.add(InventoryPosition(
        sku="COSTSKU3", supplier_code="MT", scheme_code="DIRECT_B2C",
        qty_on_hand=Decimal("10"), map_aed=Decimal("50"),
    ))
    db_session.add(InventoryPosition(
        sku="COSTSKU3", supplier_code="ALT", scheme_code="DIRECT_B2C",
        qty_on_hand=Decimal("200"), map_aed=Decimal("45"),
    ))
    await db_session.flush()

    loader = ParameterLoader(db_session)
    products = await loader.load_product_data(channel_id, skus=["COSTSKU3"])
    assert products[0].landed_cost_aed == Decimal("45")  # dominant lot (qty 200)
```

> Note: if `scheme_code='DIRECT_B2C'` is not in the seeded `schemes` table, use a scheme code that the
> migrations seed (check `schemes` rows) or insert a `Scheme` row in the helper. Adjust the literal to a
> valid `schemes.code` if the FK fails.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/test_loader_cost.py::test_loader_sets_landed_cost_from_inventory_position -v`
Expected: FAIL with `AssertionError` (landed_cost_aed is None — loader doesn't read inventory_positions yet)

- [ ] **Step 3: Write minimal implementation**

In `loader.py`, modify `load_product_data` to fetch positions and populate the override. Add the import at top:

```python
from app.db.models.inventory import InventoryPosition
```

Replace the body of `load_product_data` (after building `rows`) so it resolves the dominant landed cost per SKU:

```python
        rows = (await self._session.execute(q)).all()

        # Resolve real landed cost per SKU from inventory_positions (dominant lot:
        # highest qty_on_hand with non-null map_aed). Scheme/supplier-agnostic — landed
        # cost (layers 1-3) is route-level, not channel-scheme-level. F0.
        sku_list = [p.sku for p, _ in rows]
        landed_by_sku: dict[str, Decimal] = {}
        if sku_list:
            pos_rows = (
                await self._session.execute(
                    select(
                        InventoryPosition.sku,
                        InventoryPosition.map_aed,
                        InventoryPosition.qty_on_hand,
                    ).where(
                        InventoryPosition.sku.in_(sku_list),
                        InventoryPosition.map_aed.is_not(None),
                    )
                )
            ).all()
            best_qty: dict[str, Decimal] = {}
            for sku, map_aed, qty in pos_rows:
                if sku not in best_qty or qty > best_qty[sku]:
                    best_qty[sku] = qty
                    landed_by_sku[sku] = map_aed

        result = []
        for product, logistics_row in rows:
            if logistics_row is None or product.pe_eur is None or product.catalog_pvp_eur is None:
                continue

            logistics = ProductLogistics(
                inbound_fee_aed=logistics_row.inbound_fee_aed,
                storage_fee_aed=logistics_row.storage_fee_aed,
                fulfillment_fee_aed=logistics_row.fulfillment_fee_aed,
                default_scheme=FulfillmentScheme(logistics_row.default_scheme),
            )

            cb = product.ceiling_basis
            if isinstance(cb, str):
                cb = CeilingBasis(cb)

            result.append(
                ProductPricingData(
                    sku=product.sku,
                    family_id=str(product.family_id),
                    pe_eur=product.pe_eur,
                    catalog_pvp_eur=product.catalog_pvp_eur,
                    units_per_box=product.units_per_box or 1,
                    weight_kg=product.weight or Decimal("0"),
                    b2c_labeling_aed=product.b2c_labeling_aed or Decimal("0"),
                    ceiling_basis=cb,
                    logistics=logistics,
                    landed_cost_aed=landed_by_sku.get(product.sku),
                )
            )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/test_loader_cost.py -v`
Expected: PASS (3 passed). If a FK error on `scheme_code` appears, adjust the seed scheme code per the note in Step 1.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-backend/app/services/pricing/loader.py mt-pricing-backend/tests/services/pricing/test_loader_cost.py
git commit -m "feat(pricing): loader resolves real landed cost from inventory_positions"
```

---

## Task 4: Full regression + lint + typecheck

**Files:** none (verification only)

- [ ] **Step 1: Run the full pricing test suite**

Run: `cd mt-pricing-backend && uv run pytest tests/services/pricing/ tests/unit/test_pricing_engine.py tests/api/test_channel_pricing.py -v`
Expected: PASS (no regressions in existing engine/optimizer/api tests)

- [ ] **Step 2: Lint + typecheck**

Run: `cd mt-pricing-backend && uv run ruff check app/services/pricing/ && uv run ruff format --check app/services/pricing/ && uv run mypy app/services/pricing/`
Expected: clean (fix any issues, re-run)

- [ ] **Step 3: OpenAPI drift check (only if routes/schemas changed)**

F0 does not change `app/api/routes/` or `app/schemas/` → no OpenAPI regeneration needed. Confirm:
Run: `git diff --name-only main...HEAD | grep -E "app/api/routes/|app/schemas/" || echo "no api/schema changes"`
Expected: `no api/schema changes`

- [ ] **Step 4: Commit (if lint/format applied changes)**

```bash
git add -A && git commit -m "style(pricing): ruff format for cost-wiring" || echo "nothing to format"
```

---

## Self-Review

**Spec coverage (vs doc 09 Hueco A):**
- "Motor lee coste de `inventory_positions.map_aed`/`costs` con fallback" → Tasks 2 + 3 ✅ (uses `inventory_positions.map_aed`; `costs.scheme_landed_aed` is the same value written by MAPService — using `inventory_positions` is the per‑SKU read).
- "Híbrido A3: real si hay recepción, fallback a pe_eur/estimación" → Task 2 fallback + Task 3 `None` when no position ✅.
- "Resto del motor sin cambios" → only `_landed_b2c/_landed_b2b` touched; margin/ceiling/fees untouched ✅.
- Acceptance "SKU con goods receipt muestra coste landed real" → Task 3 integration test ✅.
- Acceptance "SKU sin recepción cae al fallback" → `test_loader_landed_cost_none_when_no_position` + `test_landed_override_none_keeps_pe_eur_derivation` ✅.
- Acceptance "coste expone source_op" → **deferred to F1** (documented in Design decisions) — not in F0.

**Placeholder scan:** none — all steps have concrete code/commands.

**Type consistency:** `landed_cost_aed: Optional[Decimal]` used identically in schemas (Task 1), engine reads `product.landed_cost_aed` (Task 2), loader sets `landed_cost_aed=...` (Task 3). `InventoryPosition.map_aed` is `Numeric(18,4)` → Decimal, matches. ✅

**Known follow-ups (out of F0 scope):** provenance/source display (F1); multi‑supplier cost blending; cost↔channel‑scheme mapping if landed cost ever needs to vary by scheme; populating `breakdown.net_eur` consistently when override is used.
