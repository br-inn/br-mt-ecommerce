# Channel Pricing Engine — Plan 2: Motor + API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el motor de cálculo puro (`PricingEngine`), el cargador de parámetros (`ParameterLoader`), el optimizador de canal, los 18 endpoints de la API, y el proceso de importación del catálogo desde Excel.

**Architecture:** `PricingEngine` es una función pura Python sin I/O — recibe dataclasses, devuelve `PriceResult`. `ParameterLoader` hace una sola query JOIN por request y pasa los datos al engine. La API FastAPI consume el engine a través del loader. Los endpoints de importación usan `openpyxl` para parsear el Excel de MT.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · openpyxl · pytest-asyncio · httpx (test client)

**Prerequisito:** Plan 1 completado y migración 147 aplicada.

**Spec de referencia:** `docs/superpowers/specs/2026-05-28-channel-pricing-engine-design.md`

---

## Estructura de ficheros

```
mt-pricing-backend/
├── app/
│   ├── services/
│   │   └── pricing/
│   │       ├── __init__.py          ← CREAR (vacío)
│   │       ├── schemas.py           ← CREAR (dataclasses del motor)
│   │       ├── engine.py            ← CREAR (PricingEngine, función pura)
│   │       ├── loader.py            ← CREAR (ParameterLoader, async DB)
│   │       └── optimizer.py         ← CREAR (ChannelOptimizer)
│   └── api/
│       └── routes/
│           ├── channel_pricing.py   ← CREAR (todos los endpoints)
│           └── __init__.py          ← MODIFICAR (registrar router)
└── tests/
    ├── services/
    │   └── pricing/
    │       ├── test_engine.py        ← CREAR
    │       └── test_optimizer.py     ← CREAR
    └── api/
        └── test_channel_pricing.py   ← CREAR
```

---

## Task 1: Dataclasses del motor (`app/services/pricing/schemas.py`)

**Files:**
- Create: `app/services/pricing/__init__.py`
- Create: `app/services/pricing/schemas.py`

- [ ] **1.1 Crear `__init__.py` vacío**

```bash
mkdir -p mt-pricing-backend/app/services/pricing
touch mt-pricing-backend/app/services/pricing/__init__.py
```

- [ ] **1.2 Crear `app/services/pricing/schemas.py`**

```python
# app/services/pricing/schemas.py
"""Immutable dataclasses used by PricingEngine.

These are NOT ORM models — they carry the exact data the engine needs
without touching the database. ParameterLoader builds them from DB rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.models.enums import CeilingBasis, FulfillmentScheme, SellingModel


@dataclass(frozen=True)
class RouteParams:
    """Trade route cost parameters (Layer 2 + 3 of cost stack)."""
    fx_rate: Decimal
    fx_buffer_pct: Decimal
    freight_rate_per_kg: Decimal
    freight_min_aed: Decimal
    import_tariff_pct: Decimal
    local_warehouse_pct: Decimal
    handling_pct: Decimal


@dataclass(frozen=True)
class ChannelFees:
    """Channel-level financial parameters (Layer 1 + 5 of cost stack)."""
    mt_discount_pct: Decimal
    commission_pct: Decimal
    vat_pct: Decimal
    advertising_pct: Decimal
    returns_pct: Decimal
    storage_multiplier: Decimal

    @property
    def total_fees_frac(self) -> Decimal:
        """Sum of all marketplace fees as a fraction (0..1)."""
        return (self.commission_pct + self.vat_pct
                + self.advertising_pct + self.returns_pct) / Decimal("100")


@dataclass(frozen=True)
class SchemeConfig:
    """Fulfillment scheme configuration for one (channel, scheme) pair."""
    fulfillment_scheme: FulfillmentScheme
    scheme_label: str
    is_available: bool
    flat_supplement_aed: Decimal
    pct_surcharge: Decimal
    max_weight_kg: Optional[Decimal]  # None = no limit


@dataclass(frozen=True)
class ProductLogistics:
    """Per-SKU fulfillment fees for a specific channel (Layer 4)."""
    inbound_fee_aed: Decimal
    storage_fee_aed: Decimal
    fulfillment_fee_aed: Decimal
    default_scheme: FulfillmentScheme


@dataclass(frozen=True)
class ProductPricingData:
    """All product-level data needed for price calculation."""
    sku: str
    family_id: str
    pe_eur: Decimal             # purchase price from MT Spain per unit
    catalog_pvp_eur: Decimal    # MT catalog PVP per unit (ceiling reference)
    units_per_box: int
    weight_kg: Decimal
    b2c_labeling_aed: Decimal
    ceiling_basis: CeilingBasis
    logistics: ProductLogistics


@dataclass(frozen=True)
class CostBreakdown:
    """Detailed cost breakdown — stored in prices.breakdown JSONB."""
    net_eur: Decimal
    fx_applied: Decimal
    aed_before_freight: Decimal
    freight_aed: Decimal
    landed_aed: Decimal
    labeling_aed: Decimal       # 0 for B2B
    channel_logistics_aed: Decimal
    cost_op_aed: Decimal
    fees_frac: Decimal
    scheme: str

    def to_dict(self) -> dict:
        return {k: str(v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class PriceResult:
    """Output of PricingEngine.compute_*. All amounts in AED."""
    sku: str
    selling_model: SellingModel
    fulfillment_scheme: FulfillmentScheme
    scheme_label: str
    margin_pct: Decimal
    cost_op_aed: Decimal
    selling_price_aed: Decimal
    ceiling_aed: Decimal
    benefit_per_unit_aed: Decimal
    roi_pct: Decimal
    margin_to_ceiling_pct: Decimal
    is_publishable: bool          # selling_price <= ceiling
    signal: str                   # PÉRDIDA / FRÁGIL / FINO / ÓPTIMO / EXCELENTE
    breakdown: CostBreakdown

    @classmethod
    def infeasible(
        cls,
        sku: str,
        selling_model: SellingModel,
        scheme: SchemeConfig,
        cost_op: Decimal,
        margin_pct: Decimal,
    ) -> "PriceResult":
        """Returned when (1 - fees - margin) <= 0 — price is mathematically impossible."""
        zero = Decimal("0")
        return cls(
            sku=sku,
            selling_model=selling_model,
            fulfillment_scheme=scheme.fulfillment_scheme,
            scheme_label=scheme.scheme_label,
            margin_pct=margin_pct,
            cost_op_aed=cost_op,
            selling_price_aed=Decimal("Infinity"),
            ceiling_aed=zero,
            benefit_per_unit_aed=-cost_op,
            roi_pct=Decimal("-100"),
            margin_to_ceiling_pct=Decimal("-100"),
            is_publishable=False,
            signal="PÉRDIDA",
            breakdown=CostBreakdown(
                net_eur=zero, fx_applied=zero, aed_before_freight=zero,
                freight_aed=zero, landed_aed=cost_op, labeling_aed=zero,
                channel_logistics_aed=zero, cost_op_aed=cost_op,
                fees_frac=zero, scheme=scheme.scheme_label,
            ),
        )
```

- [ ] **1.3 Verificar importación**

```bash
cd mt-pricing-backend && uv run python -c "from app.services.pricing.schemas import PriceResult, ProductPricingData; print('OK')"
```

- [ ] **1.4 Commit**

```bash
git add app/services/pricing/__init__.py app/services/pricing/schemas.py
git commit -m "feat(pricing): engine dataclasses — PriceResult, ProductPricingData, RouteParams"
```

---

## Task 2: Motor puro (`app/services/pricing/engine.py`) — TDD

**Files:**
- Create: `app/services/pricing/engine.py`
- Create: `tests/services/pricing/test_engine.py`

- [ ] **2.1 Escribir los tests primero**

```python
# tests/services/pricing/test_engine.py
"""Unit tests for PricingEngine — pure function, no DB required."""
from decimal import Decimal

import pytest

from app.models.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.services.pricing.engine import PricingEngine
from app.services.pricing.schemas import (
    ChannelFees,
    ProductLogistics,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def route() -> RouteParams:
    return RouteParams(
        fx_rate=Decimal("4.28"),
        fx_buffer_pct=Decimal("2"),
        freight_rate_per_kg=Decimal("0"),
        freight_min_aed=Decimal("0"),
        import_tariff_pct=Decimal("4.14"),
        local_warehouse_pct=Decimal("2"),
        handling_pct=Decimal("1.5"),
    )


@pytest.fixture
def fees() -> ChannelFees:
    return ChannelFees(
        mt_discount_pct=Decimal("15"),
        commission_pct=Decimal("11"),
        vat_pct=Decimal("5"),
        advertising_pct=Decimal("8"),
        returns_pct=Decimal("2"),
        storage_multiplier=Decimal("1.0"),
    )


@pytest.fixture
def fba_scheme() -> SchemeConfig:
    return SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.canal_full,
        scheme_label="FBA",
        is_available=True,
        flat_supplement_aed=Decimal("0"),
        pct_surcharge=Decimal("0"),
        max_weight_kg=Decimal("25"),
    )


@pytest.fixture
def easy_ship_scheme() -> SchemeConfig:
    return SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.canal_lastmile,
        scheme_label="Easy Ship",
        is_available=True,
        flat_supplement_aed=Decimal("6"),
        pct_surcharge=Decimal("0"),
        max_weight_kg=None,
    )


@pytest.fixture
def self_ship_scheme() -> SchemeConfig:
    return SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.merchant_managed,
        scheme_label="Self-Ship",
        is_available=True,
        flat_supplement_aed=Decimal("0"),
        pct_surcharge=Decimal("15"),
        max_weight_kg=None,
    )


@pytest.fixture
def brass_valve_logistics() -> ProductLogistics:
    """SKU 4222015 — F-F PN30 LONG NECK BALL VALVE 1/2" (from Pricing Desk)."""
    return ProductLogistics(
        inbound_fee_aed=Decimal("1.5"),
        storage_fee_aed=Decimal("0.028"),
        fulfillment_fee_aed=Decimal("7.2"),
        default_scheme=FulfillmentScheme.canal_full,
    )


@pytest.fixture
def brass_valve(brass_valve_logistics) -> ProductPricingData:
    return ProductPricingData(
        sku="4222015",
        family_id="dummy-family-uuid",
        pe_eur=Decimal("3.07"),
        catalog_pvp_eur=Decimal("9.77"),  # v=41.82 AED / 4.28 ≈ 9.77 EUR
        units_per_box=1,
        weight_kg=Decimal("0.21"),
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.catalog_pvp,
        logistics=brass_valve_logistics,
    )


# ── Tests ─────────────────────────────────────────────────────────────

def test_fees_frac(fees):
    """Total fees fraction = (11+5+8+2)/100 = 0.26."""
    assert fees.total_fees_frac == Decimal("0.26")


def test_compute_b2c_margin_12_fba(brass_valve, route, fees, fba_scheme):
    """Regression: brass valve at 12% margin FBA must be publishable."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))

    assert result.sku == "4222015"
    assert result.selling_model == SellingModel.b2c
    assert result.fulfillment_scheme == FulfillmentScheme.canal_full
    assert result.margin_pct == Decimal("12")
    assert result.is_publishable is True
    assert result.signal in ("FINO", "ÓPTIMO", "EXCELENTE", "FRÁGIL")
    # selling price must be between cost and ceiling
    assert result.cost_op_aed < result.selling_price_aed <= result.ceiling_aed


def test_compute_b2c_cost_op_breakdown(brass_valve, route, fees, fba_scheme):
    """FBA cost = landed + inbound + storage×multiplier + fulfillment."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    bd = result.breakdown

    # landed = (pe × (1-discount) × fx × (1+buffer)) × (1 + tariff + wh + handling)
    net_eur = Decimal("3.07") * Decimal("0.85")
    fx_adj = Decimal("4.28") * Decimal("1.02")
    aed = net_eur * fx_adj
    landed = aed * (Decimal("1") + Decimal("0.0414") + Decimal("0.02") + Decimal("0.015"))
    channel_logistics = (
        Decimal("1.5")          # inbound
        + Decimal("0.028") * Decimal("1.0")  # storage × multiplier
        + Decimal("7.2")        # fulfillment
    )
    expected_cost_op = landed + channel_logistics

    assert abs(result.cost_op_aed - expected_cost_op) < Decimal("0.01")


def test_compute_b2c_easy_ship_higher_cost(brass_valve, route, fees,
                                            fba_scheme, easy_ship_scheme):
    """Easy Ship cost > FBA cost for this product (no inbound+storage, but +6 AED)."""
    r_fba = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    r_es = PricingEngine.compute_b2c(brass_valve, route, fees, easy_ship_scheme, Decimal("12"))

    # Easy Ship = fulfillment + 6 AED (no inbound, no storage)
    # FBA = inbound + storage + fulfillment ≈ 1.5 + 0.028 + 7.2 = 8.73
    # Easy Ship = 7.2 + 6 = 13.2 → more expensive
    assert r_es.cost_op_aed > r_fba.cost_op_aed


def test_compute_b2c_negative_margin_signal(brass_valve, route, fees, fba_scheme):
    """Margin -5% → signal PÉRDIDA, is_publishable may be false."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("-5"))
    assert result.signal == "PÉRDIDA"


def test_compute_b2c_high_margin_signal(brass_valve, route, fees, fba_scheme):
    """Margin 30% → signal EXCELENTE."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("30"))
    assert result.signal == "EXCELENTE"


def test_compute_b2c_infeasible_when_fees_exceed_100(brass_valve, route, fba_scheme):
    """margin_pct=80 makes (1 - fees - margin) <= 0 → infeasible result."""
    very_high_fees = ChannelFees(
        mt_discount_pct=Decimal("15"),
        commission_pct=Decimal("50"),
        vat_pct=Decimal("5"),
        advertising_pct=Decimal("8"),
        returns_pct=Decimal("2"),
        storage_multiplier=Decimal("1.0"),
    )
    result = PricingEngine.compute_b2c(brass_valve, route, very_high_fees,
                                        fba_scheme, Decimal("80"))
    assert result.is_publishable is False
    assert result.signal == "PÉRDIDA"


def test_compute_b2b_uses_box_quantity(brass_valve, route, fees, fba_scheme):
    """B2B uses units_per_box for quantity — cost is N times B2C single-unit cost."""
    # Create a product with units_per_box=10
    from dataclasses import replace
    product_box = replace(brass_valve, units_per_box=10)

    result_b2b = PricingEngine.compute_b2b(product_box, route, fees, fba_scheme, Decimal("12"))

    # B2B cost ≈ B2C cost × 10 (minus labeling, which B2B doesn't have)
    result_b2c = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("12"))
    assert result_b2b.cost_op_aed > result_b2c.cost_op_aed
    assert result_b2b.selling_model == SellingModel.b2b


def test_fba_weight_limit_respected(route, fees):
    """Product >25kg must return infeasible for canal_full (FBA weight limit)."""
    heavy_logistics = ProductLogistics(
        inbound_fee_aed=Decimal("5"),
        storage_fee_aed=Decimal("3"),
        fulfillment_fee_aed=Decimal("19.5"),
        default_scheme=FulfillmentScheme.canal_full,
    )
    heavy_product = ProductPricingData(
        sku="HEAVY001",
        family_id="dummy",
        pe_eur=Decimal("200"),
        catalog_pvp_eur=Decimal("2000"),
        units_per_box=1,
        weight_kg=Decimal("30"),  # > 25 kg
        b2c_labeling_aed=Decimal("0"),
        ceiling_basis=CeilingBasis.catalog_pvp,
        logistics=heavy_logistics,
    )
    fba_scheme = SchemeConfig(
        fulfillment_scheme=FulfillmentScheme.canal_full,
        scheme_label="FBA",
        is_available=True,
        flat_supplement_aed=Decimal("0"),
        pct_surcharge=Decimal("0"),
        max_weight_kg=Decimal("25"),  # limit
    )
    result = PricingEngine.compute_b2c(heavy_product, route, fees, fba_scheme, Decimal("15"))
    assert result.is_publishable is False


def test_ceiling_catalog_pvp(brass_valve, route, fees, fba_scheme):
    """Ceiling = catalog_pvp_eur × fx_rate × (1 + tariff + wh + handling)."""
    result = PricingEngine.compute_b2c(brass_valve, route, fees, fba_scheme, Decimal("0"))
    # ceiling_b2c ≈ 9.77 EUR × 4.28 × 1.0764 ≈ 45.0 AED
    assert Decimal("40") < result.ceiling_aed < Decimal("50")
```

- [ ] **2.2 Ejecutar los tests — verificar que fallan**

```bash
cd mt-pricing-backend && uv run pytest tests/services/pricing/test_engine.py -v 2>&1 | head -20
```

Esperado: todos en `ERROR` o `FAILED` con `ModuleNotFoundError: No module named 'app.services.pricing.engine'`

- [ ] **2.3 Crear `app/services/pricing/engine.py`**

```python
# app/services/pricing/engine.py
"""PricingEngine — pure function, no I/O.

All inputs arrive as frozen dataclasses. All outputs are PriceResult.
No database access, no side effects, fully unit-testable.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.models.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.services.pricing.schemas import (
    ChannelFees,
    CostBreakdown,
    PriceResult,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)


class PricingEngine:
    """Static methods only — instantiation not needed."""

    @staticmethod
    def compute_b2c(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        scheme: SchemeConfig,
        margin_pct: Decimal,
    ) -> PriceResult:
        """Calculate selling price for one unit on a B2C marketplace channel."""
        # Weight limit check (e.g. FBA: no products > 25 kg)
        if (
            scheme.max_weight_kg is not None
            and product.weight_kg > scheme.max_weight_kg
        ):
            cost_op = PricingEngine._landed_b2c(product, route, fees) + Decimal("0")
            return PriceResult.infeasible(
                product.sku, SellingModel.b2c, scheme, cost_op, margin_pct
            )

        landed = PricingEngine._landed_b2c(product, route, fees)
        freight = PricingEngine._freight_per_unit(product, route)
        labeling = product.b2c_labeling_aed
        channel_logistics = PricingEngine._logistics_cost(product.logistics, scheme, fees)
        cost_op = landed + labeling + channel_logistics

        result = PricingEngine._build_result(
            sku=product.sku,
            selling_model=SellingModel.b2c,
            scheme=scheme,
            margin_pct=margin_pct,
            cost_op=cost_op,
            fees=fees,
            ceiling=PricingEngine._ceiling_b2c(product, route),
            breakdown=CostBreakdown(
                net_eur=product.pe_eur * (1 - fees.mt_discount_pct / 100),
                fx_applied=route.fx_rate * (1 + route.fx_buffer_pct / 100),
                aed_before_freight=product.pe_eur
                    * (1 - fees.mt_discount_pct / 100)
                    * route.fx_rate * (1 + route.fx_buffer_pct / 100),
                freight_aed=freight,
                landed_aed=landed,
                labeling_aed=labeling,
                channel_logistics_aed=channel_logistics,
                cost_op_aed=cost_op,
                fees_frac=fees.total_fees_frac,
                scheme=scheme.scheme_label,
            ),
        )
        return result

    @staticmethod
    def compute_b2b(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        scheme: SchemeConfig,
        margin_pct: Decimal,
    ) -> PriceResult:
        """Calculate selling price for one box on a B2B channel."""
        n = Decimal(str(product.units_per_box))
        landed = PricingEngine._landed_b2b(product, route, fees)
        freight = PricingEngine._freight_per_box(product, route)
        # B2B: no per-unit labeling cost — MT ships in original boxes
        channel_logistics = PricingEngine._logistics_cost(product.logistics, scheme, fees) * n
        cost_op = landed + channel_logistics

        return PricingEngine._build_result(
            sku=product.sku,
            selling_model=SellingModel.b2b,
            scheme=scheme,
            margin_pct=margin_pct,
            cost_op=cost_op,
            fees=fees,
            ceiling=PricingEngine._ceiling_b2b(product, route),
            breakdown=CostBreakdown(
                net_eur=product.pe_eur * n * (1 - fees.mt_discount_pct / 100),
                fx_applied=route.fx_rate * (1 + route.fx_buffer_pct / 100),
                aed_before_freight=product.pe_eur * n
                    * (1 - fees.mt_discount_pct / 100)
                    * route.fx_rate * (1 + route.fx_buffer_pct / 100),
                freight_aed=freight,
                landed_aed=landed,
                labeling_aed=Decimal("0"),
                channel_logistics_aed=channel_logistics,
                cost_op_aed=cost_op,
                fees_frac=fees.total_fees_frac,
                scheme=scheme.scheme_label,
            ),
        )

    # ── Private helpers ────────────────────────────────────────────────

    @staticmethod
    def _freight_per_unit(product: ProductPricingData, route: RouteParams) -> Decimal:
        """Freight cost per unit in AED. Splits shipment minimum across box units."""
        units = max(product.units_per_box, 1)
        per_kg = route.freight_rate_per_kg * product.weight_kg * route.fx_rate
        per_min = route.freight_min_aed / Decimal(str(units))
        return max(per_min, per_kg)

    @staticmethod
    def _freight_per_box(product: ProductPricingData, route: RouteParams) -> Decimal:
        """Freight cost per box in AED."""
        n = Decimal(str(product.units_per_box))
        per_kg = route.freight_rate_per_kg * product.weight_kg * n * route.fx_rate
        return max(route.freight_min_aed, per_kg)

    @staticmethod
    def _import_factor(route: RouteParams) -> Decimal:
        return (
            Decimal("1")
            + route.import_tariff_pct / 100
            + route.local_warehouse_pct / 100
            + route.handling_pct / 100
        )

    @staticmethod
    def _landed_b2c(
        product: ProductPricingData, route: RouteParams, fees: ChannelFees
    ) -> Decimal:
        """Cost of one unit landed in Dubai warehouse (layers 1-3)."""
        net_eur = product.pe_eur * (1 - fees.mt_discount_pct / 100)
        fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
        aed = net_eur * fx
        freight = PricingEngine._freight_per_unit(product, route)
        return (aed + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _landed_b2b(
        product: ProductPricingData, route: RouteParams, fees: ChannelFees
    ) -> Decimal:
        """Cost of one box landed in Dubai warehouse (layers 1-3)."""
        n = Decimal(str(product.units_per_box))
        net_eur_box = product.pe_eur * n * (1 - fees.mt_discount_pct / 100)
        fx = route.fx_rate * (1 + route.fx_buffer_pct / 100)
        aed_box = net_eur_box * fx
        freight = PricingEngine._freight_per_box(product, route)
        return (aed_box + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _logistics_cost(
        logistics: "ProductLogistics",  # noqa: F821
        scheme: SchemeConfig,
        fees: ChannelFees,
    ) -> Decimal:
        """Channel logistics cost per unit for the given fulfillment scheme."""
        ff = logistics.fulfillment_fee_aed
        if scheme.fulfillment_scheme == FulfillmentScheme.canal_full:
            return (
                logistics.inbound_fee_aed
                + logistics.storage_fee_aed * fees.storage_multiplier
                + ff
            )
        elif scheme.fulfillment_scheme == FulfillmentScheme.canal_lastmile:
            return ff + scheme.flat_supplement_aed
        else:  # merchant_managed
            return (ff + scheme.flat_supplement_aed) * (
                1 + scheme.pct_surcharge / 100
            )

    @staticmethod
    def _ceiling_b2c(product: ProductPricingData, route: RouteParams) -> Decimal:
        if product.ceiling_basis == CeilingBasis.margin_floor:
            # No PVP in MT catalog — use a fixed 35% margin floor as ceiling proxy
            return Decimal("Infinity")  # Optimizer will handle this differently
        pvp_aed = product.catalog_pvp_eur * route.fx_rate
        freight = PricingEngine._freight_per_unit_no_buffer(product, route)
        return (pvp_aed + freight) * PricingEngine._import_factor(route) + product.b2c_labeling_aed

    @staticmethod
    def _ceiling_b2b(product: ProductPricingData, route: RouteParams) -> Decimal:
        if product.ceiling_basis == CeilingBasis.margin_floor:
            return Decimal("Infinity")
        n = Decimal(str(product.units_per_box))
        pvp_aed_box = product.catalog_pvp_eur * n * route.fx_rate
        freight = PricingEngine._freight_per_box_no_buffer(product, route)
        return (pvp_aed_box + freight) * PricingEngine._import_factor(route)

    @staticmethod
    def _freight_per_unit_no_buffer(
        product: ProductPricingData, route: RouteParams
    ) -> Decimal:
        """Freight for ceiling calc — uses raw fx_rate, no buffer (buyer reference price)."""
        units = max(product.units_per_box, 1)
        per_kg = route.freight_rate_per_kg * product.weight_kg * route.fx_rate
        per_min = route.freight_min_aed / Decimal(str(units))
        return max(per_min, per_kg)

    @staticmethod
    def _freight_per_box_no_buffer(
        product: ProductPricingData, route: RouteParams
    ) -> Decimal:
        n = Decimal(str(product.units_per_box))
        per_kg = route.freight_rate_per_kg * product.weight_kg * n * route.fx_rate
        return max(route.freight_min_aed, per_kg)

    @staticmethod
    def _signal(margin_pct: Decimal) -> str:
        if margin_pct < 0:
            return "PÉRDIDA"
        if margin_pct < Decimal("5"):
            return "FRÁGIL"
        if margin_pct < Decimal("15"):
            return "FINO"
        if margin_pct <= Decimal("25"):
            return "ÓPTIMO"
        return "EXCELENTE"

    @staticmethod
    def _build_result(
        sku: str,
        selling_model: SellingModel,
        scheme: SchemeConfig,
        margin_pct: Decimal,
        cost_op: Decimal,
        fees: ChannelFees,
        ceiling: Decimal,
        breakdown: CostBreakdown,
    ) -> PriceResult:
        k = Decimal("1") - fees.total_fees_frac - margin_pct / 100
        if k <= Decimal("0"):
            return PriceResult.infeasible(sku, selling_model, scheme, cost_op, margin_pct)

        price = (cost_op / k).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        benefit = price * (Decimal("1") - fees.total_fees_frac) - cost_op
        roi = (benefit / cost_op * 100) if cost_op > 0 else Decimal("0")
        publishable = price <= ceiling if ceiling != Decimal("Infinity") else True
        margin_to_ceil = (
            (ceiling - price) / ceiling * 100
            if ceiling not in (Decimal("0"), Decimal("Infinity"))
            else Decimal("0")
        )

        return PriceResult(
            sku=sku,
            selling_model=selling_model,
            fulfillment_scheme=scheme.fulfillment_scheme,
            scheme_label=scheme.scheme_label,
            margin_pct=margin_pct,
            cost_op_aed=cost_op.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            selling_price_aed=price,
            ceiling_aed=ceiling.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if ceiling != Decimal("Infinity") else ceiling,
            benefit_per_unit_aed=benefit.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            roi_pct=roi.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
            margin_to_ceiling_pct=margin_to_ceil.quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            ),
            is_publishable=publishable,
            signal=PricingEngine._signal(margin_pct),
            breakdown=breakdown,
        )
```

- [ ] **2.4 Ejecutar los tests — verificar que pasan**

```bash
uv run pytest tests/services/pricing/test_engine.py -v
```

Esperado: todos en PASS. Si hay un fallo en `test_compute_b2c_cost_op_breakdown`, verifica que los valores de los fixtures de `route` y `fees` coinciden exactamente con los de la prueba de regresión.

- [ ] **2.5 Commit**

```bash
git add app/services/pricing/engine.py tests/services/pricing/test_engine.py
git commit -m "feat(pricing): PricingEngine pure function with TDD (B2C + B2B formulas)"
```

---

## Task 3: ParameterLoader (`app/services/pricing/loader.py`)

**Files:**
- Create: `app/services/pricing/loader.py`

Lee todos los parámetros necesarios para calcular el precio de un catálogo en **una sola query JOIN** por request. Nunca hace queries dentro del engine.

- [ ] **3.1 Crear `app/services/pricing/loader.py`**

```python
# app/services/pricing/loader.py
"""ParameterLoader — loads all pricing params in one JOIN query per request.

Never call this inside a loop. Load once per API request, pass the result
to PricingEngine for every product in the catalog.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelProductLogistics,
    ChannelSchemeParams,
    TradeRouteParams,
)
from app.models.enums import FulfillmentScheme, SellingModel
from app.models.product import Product
from app.services.pricing.schemas import (
    ChannelFees,
    ProductLogistics,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)


class ParameterLoader:
    """Loads all pricing parameters for a channel in one pass."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def load_route_and_fees(
        self, channel_id: uuid.UUID
    ) -> tuple[RouteParams, ChannelFees, list[SchemeConfig]]:
        """Load trade route + channel fees + available schemes for a channel."""
        fee_row = (
            await self._session.execute(
                select(ChannelFeeParams)
                .where(ChannelFeeParams.channel_id == channel_id)
                .options(joinedload(ChannelFeeParams.route))  # type: ignore[attr-defined]
            )
        ).scalars().first()

        if fee_row is None:
            raise ValueError(
                f"No channel_fee_params found for channel_id={channel_id}. "
                "Run seed_channel_pricing.py first."
            )

        route_row: TradeRouteParams = fee_row.route  # type: ignore[attr-defined]

        route = RouteParams(
            fx_rate=route_row.fx_rate,
            fx_buffer_pct=route_row.fx_buffer_pct,
            freight_rate_per_kg=route_row.freight_rate_per_kg,
            freight_min_aed=route_row.freight_min_aed,
            import_tariff_pct=route_row.import_tariff_pct,
            local_warehouse_pct=route_row.local_warehouse_pct,
            handling_pct=route_row.handling_pct,
        )
        fees = ChannelFees(
            mt_discount_pct=fee_row.mt_discount_pct,
            commission_pct=fee_row.commission_pct,
            vat_pct=fee_row.vat_pct,
            advertising_pct=fee_row.advertising_pct,
            returns_pct=fee_row.returns_pct,
            storage_multiplier=fee_row.storage_multiplier,
        )

        scheme_rows = (
            await self._session.execute(
                select(ChannelSchemeParams)
                .where(
                    ChannelSchemeParams.channel_id == channel_id,
                    ChannelSchemeParams.is_available.is_(True),
                )
            )
        ).scalars().all()

        schemes = [
            SchemeConfig(
                fulfillment_scheme=s.fulfillment_scheme,
                scheme_label=s.scheme_label,
                is_available=s.is_available,
                flat_supplement_aed=s.flat_supplement_aed,
                pct_surcharge=s.pct_surcharge,
                max_weight_kg=s.max_weight_kg,
            )
            for s in scheme_rows
        ]
        return route, fees, schemes

    async def load_product_data(
        self,
        channel_id: uuid.UUID,
        skus: Optional[list[str]] = None,
    ) -> list[ProductPricingData]:
        """Load all products with their channel logistics.

        If skus is None, loads the full catalog.
        """
        q = (
            select(Product, ChannelProductLogistics)
            .join(
                ChannelProductLogistics,
                (ChannelProductLogistics.product_sku == Product.sku)
                & (ChannelProductLogistics.channel_id == channel_id),
                isouter=True,  # left join — products without logistics still appear
            )
            .where(Product.lifecycle_status == "active")
        )
        if skus:
            q = q.where(Product.sku.in_(skus))

        rows = (await self._session.execute(q)).all()

        result = []
        for product, logistics_row in rows:
            if logistics_row is None:
                # Product has no logistics data for this channel — skip
                continue
            logistics = ProductLogistics(
                inbound_fee_aed=logistics_row.inbound_fee_aed,
                storage_fee_aed=logistics_row.storage_fee_aed,
                fulfillment_fee_aed=logistics_row.fulfillment_fee_aed,
                default_scheme=logistics_row.default_scheme,
            )
            result.append(
                ProductPricingData(
                    sku=product.sku,
                    family_id=str(product.family_id),
                    pe_eur=product.pe_eur or Decimal("0"),
                    catalog_pvp_eur=product.catalog_pvp_eur or Decimal("0"),
                    units_per_box=product.units_per_box or 1,
                    weight_kg=product.weight or Decimal("0"),
                    b2c_labeling_aed=product.b2c_labeling_aed or Decimal("0"),
                    ceiling_basis=product.ceiling_basis,
                    logistics=logistics,
                )
            )
        return result

    async def load_effective_margins(
        self,
        channel_id: uuid.UUID,
        selling_model: SellingModel,
        skus: list[str],
    ) -> dict[str, Decimal]:
        """Return {sku: effective_margin_pct} for the given skus.

        Priority: product override > family target > default 12%.
        """
        # 1. Load family targets for this channel+selling_model
        target_rows = (
            await self._session.execute(
                select(ChannelMarginTarget)
                .where(
                    ChannelMarginTarget.channel_id == channel_id,
                    ChannelMarginTarget.selling_model == selling_model,
                )
            )
        ).scalars().all()
        family_targets: dict[str, Decimal] = {
            str(r.family_id): r.margin_target_pct for r in target_rows
        }

        # 2. Load product overrides
        override_rows = (
            await self._session.execute(
                select(ChannelMarginOverride)
                .where(
                    ChannelMarginOverride.channel_id == channel_id,
                    ChannelMarginOverride.selling_model == selling_model,
                    ChannelMarginOverride.product_sku.in_(skus),
                )
            )
        ).scalars().all()
        overrides: dict[str, Decimal] = {
            r.product_sku: r.margin_override_pct for r in override_rows
        }

        # 3. Load products to get family_id
        product_rows = (
            await self._session.execute(
                select(Product.sku, Product.family_id).where(Product.sku.in_(skus))
            )
        ).all()

        result: dict[str, Decimal] = {}
        for sku, family_id in product_rows:
            if sku in overrides:
                result[sku] = overrides[sku]
            elif str(family_id) in family_targets:
                result[sku] = family_targets[str(family_id)]
            else:
                result[sku] = Decimal("12")  # global default

        return result
```

- [ ] **3.2 Añadir la relación ORM faltante en ChannelFeeParams**

El loader hace `joinedload(ChannelFeeParams.route)`. Para que funcione, hay que declarar la relación en el modelo. Añadir al final de `ChannelFeeParams` en `app/models/channel_pricing.py`:

```python
from sqlalchemy.orm import relationship

# Dentro de la clase ChannelFeeParams, después de updated_by:
route: Mapped["TradeRouteParams"] = relationship(
    "TradeRouteParams", foreign_keys=[route_id], lazy="raise"
)
```

- [ ] **3.3 Verificar que el loader importa sin error**

```bash
uv run python -c "from app.services.pricing.loader import ParameterLoader; print('OK')"
```

- [ ] **3.4 Commit**

```bash
git add app/services/pricing/loader.py app/models/channel_pricing.py
git commit -m "feat(pricing): ParameterLoader — single-query param loading for engine"
```

---

## Task 4: ChannelOptimizer (`app/services/pricing/optimizer.py`)

**Files:**
- Create: `app/services/pricing/optimizer.py`
- Create: `tests/services/pricing/test_optimizer.py`

- [ ] **4.1 Escribir tests del optimizador**

```python
# tests/services/pricing/test_optimizer.py
from decimal import Decimal
import pytest
from app.models.enums import CeilingBasis, FulfillmentScheme, SellingModel
from app.services.pricing.engine import PricingEngine
from app.services.pricing.optimizer import ChannelOptimizer
from app.services.pricing.schemas import (
    ChannelFees, ProductLogistics, ProductPricingData, RouteParams, SchemeConfig,
)


@pytest.fixture
def standard_route():
    return RouteParams(
        fx_rate=Decimal("4.28"), fx_buffer_pct=Decimal("2"),
        freight_rate_per_kg=Decimal("0"), freight_min_aed=Decimal("0"),
        import_tariff_pct=Decimal("4.14"), local_warehouse_pct=Decimal("2"),
        handling_pct=Decimal("1.5"),
    )


@pytest.fixture
def standard_fees():
    return ChannelFees(
        mt_discount_pct=Decimal("15"), commission_pct=Decimal("11"),
        vat_pct=Decimal("5"), advertising_pct=Decimal("8"),
        returns_pct=Decimal("2"), storage_multiplier=Decimal("1.0"),
    )


@pytest.fixture
def all_schemes():
    return [
        SchemeConfig(FulfillmentScheme.canal_full, "FBA", True, Decimal("0"), Decimal("0"), Decimal("25")),
        SchemeConfig(FulfillmentScheme.canal_lastmile, "Easy Ship", True, Decimal("6"), Decimal("0"), None),
        SchemeConfig(FulfillmentScheme.merchant_managed, "Self-Ship", True, Decimal("0"), Decimal("15"), None),
    ]


@pytest.fixture
def standard_product():
    return ProductPricingData(
        sku="TEST001", family_id="fam1",
        pe_eur=Decimal("3.07"), catalog_pvp_eur=Decimal("9.77"),
        units_per_box=1, weight_kg=Decimal("0.21"),
        b2c_labeling_aed=Decimal("0"), ceiling_basis=CeilingBasis.catalog_pvp,
        logistics=ProductLogistics(
            inbound_fee_aed=Decimal("1.5"), storage_fee_aed=Decimal("0.028"),
            fulfillment_fee_aed=Decimal("7.2"),
            default_scheme=FulfillmentScheme.canal_full,
        ),
    )


def test_optimize_finds_best_publishable_scheme(standard_product, standard_route, standard_fees, all_schemes):
    """optimal_scheme returns the publishable scheme with best benefit/unit."""
    result = ChannelOptimizer.best_scheme_b2c(
        standard_product, standard_route, standard_fees, all_schemes, Decimal("12")
    )
    assert result is not None
    assert result.is_publishable


def test_optimize_full_catalog_returns_one_result_per_sku(
    standard_product, standard_route, standard_fees, all_schemes
):
    results = ChannelOptimizer.optimize_catalog_b2c(
        [standard_product], standard_route, standard_fees, all_schemes,
        margins={"TEST001": Decimal("12")},
    )
    assert len(results) == 1
    assert results[0].sku == "TEST001"
```

- [ ] **4.2 Crear `app/services/pricing/optimizer.py`**

```python
# app/services/pricing/optimizer.py
"""ChannelOptimizer — tries all available schemes and picks the best.

Best = highest benefit_per_unit_aed among schemes where is_publishable=True.
If no scheme is publishable, returns the one with the best (least negative) result.
Tie-breaking order: canal_full > canal_lastmile > merchant_managed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.models.enums import FulfillmentScheme, SellingModel
from app.services.pricing.engine import PricingEngine
from app.services.pricing.schemas import (
    ChannelFees,
    PriceResult,
    ProductPricingData,
    RouteParams,
    SchemeConfig,
)

# Tiebreaker priority (lower index = higher priority)
_SCHEME_PRIORITY = [
    FulfillmentScheme.canal_full,
    FulfillmentScheme.canal_lastmile,
    FulfillmentScheme.merchant_managed,
]


class ChannelOptimizer:

    @staticmethod
    def best_scheme_b2c(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margin_pct: Decimal,
    ) -> Optional[PriceResult]:
        """Return the best PriceResult for all available schemes at a given margin."""
        candidates = [
            PricingEngine.compute_b2c(product, route, fees, scheme, margin_pct)
            for scheme in schemes
            if scheme.is_available
        ]
        if not candidates:
            return None
        return _pick_best(candidates)

    @staticmethod
    def optimal_margin_b2c(
        product: ProductPricingData,
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margin_step: Decimal = Decimal("1"),
    ) -> Optional[PriceResult]:
        """Find the maximum margin under ceiling across all schemes.

        Iterates margin from 80% down to -10% in margin_step increments.
        Returns the best (scheme, margin) combination that stays under the ceiling.
        """
        best: Optional[PriceResult] = None
        margin = Decimal("80")
        floor = Decimal("-10")

        while margin >= floor:
            candidate = ChannelOptimizer.best_scheme_b2c(
                product, route, fees, schemes, margin
            )
            if candidate and candidate.is_publishable:
                if best is None or candidate.benefit_per_unit_aed > best.benefit_per_unit_aed:
                    best = candidate
                break  # Found the max publishable margin — stop
            margin -= margin_step

        return best

    @staticmethod
    def optimize_catalog_b2c(
        products: list[ProductPricingData],
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
        margins: dict[str, Decimal],
    ) -> list[PriceResult]:
        """Compute best scheme for each product at its effective margin.

        margins: {sku: effective_margin_pct} from ParameterLoader.load_effective_margins
        """
        results = []
        for product in products:
            margin = margins.get(product.sku, Decimal("12"))
            result = ChannelOptimizer.best_scheme_b2c(
                product, route, fees, schemes, margin
            )
            if result:
                results.append(result)
        return results

    @staticmethod
    def full_optimize_catalog_b2c(
        products: list[ProductPricingData],
        route: RouteParams,
        fees: ChannelFees,
        schemes: list[SchemeConfig],
    ) -> list[PriceResult]:
        """For each product, find the scheme+margin that maximizes benefit under ceiling."""
        results = []
        for product in products:
            result = ChannelOptimizer.optimal_margin_b2c(product, route, fees, schemes)
            if result:
                results.append(result)
        return results


def _pick_best(candidates: list[PriceResult]) -> PriceResult:
    publishable = [r for r in candidates if r.is_publishable]
    pool = publishable if publishable else candidates
    return max(
        pool,
        key=lambda r: (
            r.benefit_per_unit_aed,
            -_SCHEME_PRIORITY.index(r.fulfillment_scheme)
            if r.fulfillment_scheme in _SCHEME_PRIORITY
            else -99,
        ),
    )
```

- [ ] **4.3 Ejecutar todos los tests de servicios**

```bash
uv run pytest tests/services/pricing/ -v
```

Esperado: todos en PASS.

- [ ] **4.4 Commit**

```bash
git add app/services/pricing/optimizer.py tests/services/pricing/test_optimizer.py
git commit -m "feat(pricing): ChannelOptimizer — best scheme + full catalog optimization"
```

---

## Task 5: API Router — Configuración y Parámetros

**Files:**
- Create: `app/api/routes/channel_pricing.py` (primera parte)
- Modify: `app/api/routes/__init__.py` (registrar router)

- [ ] **5.1 Crear el router y los endpoints de configuración**

```python
# app/api/routes/channel_pricing.py
"""Channel Pricing Engine API endpoints.

All paths are prefixed with /pricing/{channel_code} by the main router.
channel_code is resolved to channel_id on entry via _get_channel_id().
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db  # adjust to your actual dep path
from app.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelSchemeParams,
    TradeRouteParams,
)
from app.models.channels import Channel
from app.schemas.channel_pricing import (
    ChannelFeeParamsRead,
    ChannelFeeParamsUpdate,
    ChannelSchemeParamsRead,
    MarginOverrideRead,
    MarginOverrideUpsert,
    MarginTargetRead,
    MarginTargetUpsert,
    TradeRouteParamsRead,
    TradeRouteParamsUpdate,
)

router = APIRouter(prefix="/pricing/{channel_code}", tags=["pricing"])


async def _get_channel_id(
    channel_code: str, db: AsyncSession = Depends(get_db)
) -> uuid.UUID:
    """Resolve channel_code → channel.id. Raises 404 if not found."""
    row = (
        await db.execute(select(Channel.id).where(Channel.code == channel_code))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_code}' not found")
    return row


# ── Route Params ──────────────────────────────────────────────────────

@router.get("/params", response_model=dict)
async def get_params(
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Return route + fee + scheme params for this channel."""
    fee_row = (
        await db.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    if fee_row is None:
        raise HTTPException(404, "Channel fee params not configured")

    route_row = (
        await db.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first()

    scheme_rows = (
        await db.execute(
            select(ChannelSchemeParams).where(
                ChannelSchemeParams.channel_id == channel_id
            )
        )
    ).scalars().all()

    return {
        "route": TradeRouteParamsRead.model_validate(route_row),
        "fees": {
            **ChannelFeeParamsRead.model_validate(fee_row).model_dump(),
            "total_fees_pct": float(
                fee_row.commission_pct + fee_row.vat_pct
                + fee_row.advertising_pct + fee_row.returns_pct
            ),
        },
        "schemes": [ChannelSchemeParamsRead.model_validate(s) for s in scheme_rows],
    }


@router.patch("/route-params", response_model=TradeRouteParamsRead)
async def update_route_params(
    body: TradeRouteParamsUpdate,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Update trade route parameters. Changes affect all channels on this route."""
    fee_row = (
        await db.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    if fee_row is None:
        raise HTTPException(404, "Channel not configured")

    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if values:
        await db.execute(
            update(TradeRouteParams)
            .where(TradeRouteParams.id == fee_row.route_id)
            .values(**values)
        )
        await db.commit()

    route = (
        await db.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first()
    return TradeRouteParamsRead.model_validate(route)


@router.patch("/fee-params", response_model=ChannelFeeParamsRead)
async def update_fee_params(
    body: ChannelFeeParamsUpdate,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Update channel-specific fee parameters."""
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if values:
        await db.execute(
            update(ChannelFeeParams)
            .where(ChannelFeeParams.channel_id == channel_id)
            .values(**values)
        )
        await db.commit()

    row = (
        await db.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    return ChannelFeeParamsRead.model_validate(row)


# ── Margin Targets ────────────────────────────────────────────────────

@router.get("/margin-targets", response_model=list[MarginTargetRead])
async def list_margin_targets(
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    from app.models.vocabulary import Family  # adjust import path
    rows = (
        await db.execute(
            select(ChannelMarginTarget, Family.name)
            .join(Family, Family.id == ChannelMarginTarget.family_id)
            .where(ChannelMarginTarget.channel_id == channel_id)
            .order_by(Family.name)
        )
    ).all()
    return [
        MarginTargetRead(
            id=r.ChannelMarginTarget.id,
            channel_id=r.ChannelMarginTarget.channel_id,
            family_id=r.ChannelMarginTarget.family_id,
            family_name=r.name,
            selling_model=r.ChannelMarginTarget.selling_model,
            margin_target_pct=r.ChannelMarginTarget.margin_target_pct,
        )
        for r in rows
    ]


@router.put("/margin-targets", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_margin_target(
    body: MarginTargetUpsert,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Upsert margin target. Clears all product overrides for this family+selling_model."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    await db.execute(
        pg_insert(ChannelMarginTarget)
        .values(
            channel_id=channel_id,
            family_id=body.family_id,
            selling_model=body.selling_model,
            margin_target_pct=body.margin_target_pct,
        )
        .on_conflict_do_update(
            constraint="uq_channel_margin_targets",
            set_={"margin_target_pct": body.margin_target_pct},
        )
    )
    # Clear overrides for this family when family margin changes (Pricing Desk behavior)
    from sqlalchemy import delete
    from app.models.product import Product
    await db.execute(
        delete(ChannelMarginOverride)
        .where(
            ChannelMarginOverride.channel_id == channel_id,
            ChannelMarginOverride.selling_model == body.selling_model,
            ChannelMarginOverride.product_sku.in_(
                select(Product.sku).where(Product.family_id == body.family_id)
            ),
        )
    )
    await db.commit()


# ── Margin Overrides ──────────────────────────────────────────────────

@router.put("/margin-overrides/{sku}", response_model=MarginOverrideRead)
async def upsert_margin_override(
    sku: str,
    body: MarginOverrideUpsert,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    await db.execute(
        pg_insert(ChannelMarginOverride)
        .values(
            product_sku=sku,
            channel_id=channel_id,
            selling_model=body.selling_model,
            margin_override_pct=body.margin_override_pct,
            reason=body.reason,
        )
        .on_conflict_do_update(
            constraint="uq_channel_margin_overrides",
            set_={
                "margin_override_pct": body.margin_override_pct,
                "reason": body.reason,
            },
        )
    )
    await db.commit()
    row = (
        await db.execute(
            select(ChannelMarginOverride).where(
                ChannelMarginOverride.product_sku == sku,
                ChannelMarginOverride.channel_id == channel_id,
                ChannelMarginOverride.selling_model == body.selling_model,
            )
        )
    ).scalars().first()
    return MarginOverrideRead.model_validate(row)


@router.delete("/margin-overrides/{sku}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_margin_override(
    sku: str,
    selling_model: str = "b2c",
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import delete
    await db.execute(
        delete(ChannelMarginOverride).where(
            ChannelMarginOverride.product_sku == sku,
            ChannelMarginOverride.channel_id == channel_id,
            ChannelMarginOverride.selling_model == selling_model,
        )
    )
    await db.commit()
```

- [ ] **5.2 Registrar el router en la aplicación**

En `app/api/routes/__init__.py` o donde se registren los routers (verifica el patrón del proyecto con `grep -r "include_router" app/`):

```python
from app.api.routes.channel_pricing import router as channel_pricing_router

# Añadir junto a los demás include_router:
app.include_router(channel_pricing_router)
# O si se usa un router agregador:
api_router.include_router(channel_pricing_router)
```

- [ ] **5.3 Verificar que la app arranca sin errores de importación**

```bash
uv run python -c "from app.main import app; print('App imports OK')"
```

- [ ] **5.4 Commit**

```bash
git add app/api/routes/channel_pricing.py app/api/routes/__init__.py
git commit -m "feat(pricing): configuration and margin endpoints (route-params, fee-params, margin-targets, overrides)"
```

---

## Task 6: API Router — Cálculo, Catálogo y Optimización

**Files:**
- Modify: `app/api/routes/channel_pricing.py` (añadir endpoints de cálculo)

- [ ] **6.1 Añadir los endpoints de cálculo al router**

Añadir al final de `app/api/routes/channel_pricing.py`:

```python
# ── Cálculo ───────────────────────────────────────────────────────────

from app.models.enums import FulfillmentScheme as FulfillmentSchemeEnum, SellingModel
from app.services.pricing.engine import PricingEngine
from app.services.pricing.loader import ParameterLoader
from app.services.pricing.optimizer import ChannelOptimizer


def _price_result_to_dict(r) -> dict:
    return {
        "sku": r.sku,
        "selling_model": r.selling_model.value,
        "fulfillment_scheme": r.fulfillment_scheme.value,
        "scheme_label": r.scheme_label,
        "margin_pct": float(r.margin_pct),
        "cost_op_aed": float(r.cost_op_aed),
        "selling_price_aed": float(r.selling_price_aed)
            if r.selling_price_aed != Decimal("Infinity") else None,
        "ceiling_aed": float(r.ceiling_aed)
            if r.ceiling_aed not in (Decimal("Infinity"), Decimal("0")) else None,
        "benefit_per_unit_aed": float(r.benefit_per_unit_aed),
        "roi_pct": float(r.roi_pct),
        "margin_to_ceiling_pct": float(r.margin_to_ceiling_pct),
        "is_publishable": r.is_publishable,
        "signal": r.signal,
    }


@router.get("/product/{sku}")
async def get_product_price(
    sku: str,
    selling_model: str = "b2c",
    margin_pct: Optional[float] = None,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Calculate price for one SKU. Returns B2C and B2B results."""
    loader = ParameterLoader(db)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id, skus=[sku])
    if not products:
        raise HTTPException(404, f"SKU '{sku}' not found or has no logistics data")

    product = products[0]
    sm = SellingModel(selling_model)

    effective_margins = await loader.load_effective_margins(channel_id, sm, [sku])
    m = Decimal(str(margin_pct)) if margin_pct is not None else effective_margins.get(sku, Decimal("12"))

    compute = PricingEngine.compute_b2c if sm == SellingModel.b2c else PricingEngine.compute_b2b
    results = [compute(product, route, fees, s, m) for s in schemes if s.is_available]
    best = ChannelOptimizer.best_scheme_b2c(product, route, fees, schemes, m)

    return {
        "sku": sku,
        "effective_margin_pct": float(m),
        "best_scheme": _price_result_to_dict(best) if best else None,
        "all_schemes": [_price_result_to_dict(r) for r in results],
    }


@router.get("/catalog")
async def get_catalog_summary(
    selling_model: str = "b2c",
    family: Optional[str] = None,
    signal: Optional[str] = None,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Return price analysis for the full catalog."""
    loader = ParameterLoader(db)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)
    sm = SellingModel(selling_model)
    skus = [p.sku for p in products]
    margins = await loader.load_effective_margins(channel_id, sm, skus)

    results = ChannelOptimizer.optimize_catalog_b2c(products, route, fees, schemes, margins)

    # Filters
    if signal:
        results = [r for r in results if r.signal == signal.upper()]

    rows = [_price_result_to_dict(r) for r in results]
    publishable = sum(1 for r in results if r.is_publishable)
    in_loss = sum(1 for r in results if r.signal == "PÉRDIDA")

    return {
        "semaforo": {
            "total": len(results),
            "publishable": publishable,
            "blocked": len(results) - publishable,
            "in_loss": in_loss,
            "by_scheme": {
                scheme.value: sum(1 for r in results if r.fulfillment_scheme == scheme)
                for scheme in FulfillmentSchemeEnum
            },
        },
        "rows": rows,
    }


@router.post("/optimize")
async def optimize_catalog(
    selling_model: str = "b2c",
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Find optimal scheme+margin for every product. Does NOT persist changes."""
    loader = ParameterLoader(db)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)

    sm = SellingModel(selling_model)
    results = ChannelOptimizer.full_optimize_catalog_b2c(products, route, fees, schemes)
    return {"results": [_price_result_to_dict(r) for r in results]}


@router.post("/optimize/apply", status_code=status.HTTP_204_NO_CONTENT)
async def apply_optimization(
    selling_model: str = "b2c",
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Persist optimal margins as product overrides."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    loader = ParameterLoader(db)
    route, fees, schemes = await loader.load_route_and_fees(channel_id)
    products = await loader.load_product_data(channel_id)
    sm = SellingModel(selling_model)
    results = ChannelOptimizer.full_optimize_catalog_b2c(products, route, fees, schemes)

    for r in results:
        await db.execute(
            pg_insert(ChannelMarginOverride)
            .values(
                product_sku=r.sku,
                channel_id=channel_id,
                selling_model=sm,
                margin_override_pct=r.margin_pct,
                reason="auto-optimized",
            )
            .on_conflict_do_update(
                constraint="uq_channel_margin_overrides",
                set_={"margin_override_pct": r.margin_pct, "reason": "auto-optimized"},
            )
        )
    await db.commit()
```

- [ ] **6.2 Verificar que la app arranca**

```bash
uv run python -c "from app.main import app; print('OK')"
```

- [ ] **6.3 Test smoke de los endpoints con el cliente de prueba**

```bash
uv run pytest tests/api/test_channel_pricing.py -v -k "test_catalog_returns_200" 2>&1 | tail -10
```

(Los tests se crean en Task 8.)

- [ ] **6.4 Commit**

```bash
git add app/api/routes/channel_pricing.py
git commit -m "feat(pricing): catalog and optimization endpoints (product, catalog, optimize)"
```

---

## Task 7: Importación del catálogo desde Excel

**Files:**
- Modify: `app/api/routes/channel_pricing.py` (añadir endpoints de importación)

- [ ] **7.1 Añadir dependencia openpyxl**

```bash
cd mt-pricing-backend && uv add openpyxl
```

- [ ] **7.2 Añadir los endpoints de importación**

Añadir al final de `app/api/routes/channel_pricing.py`:

```python
# ── Importación de catálogo ───────────────────────────────────────────

import io
from fastapi import UploadFile, File
import openpyxl
from app.models.enums import CeilingBasis
from app.schemas.channel_pricing import CatalogImportResult, LogisticsImportRow
from app.services.pricing.engine import PricingEngine as _Engine
from app.services.pricing.schemas import RouteParams as _RouteParams


@router.post("/catalog/import", response_model=CatalogImportResult)
async def import_catalog(
    file: UploadFile = File(...),
    confirm: bool = False,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Import MT catalog Excel.

    Required columns: sku, pe_eur, pvp_eur, uds_caja, peso_kg.
    Optional: ceiling_basis (default: catalog_pvp).
    
    Pass ?confirm=true to actually save. Without confirm, returns a preview
    of the calculated ceiling prices without writing anything.
    """
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active

    headers = [str(cell.value).strip().lower() for cell in next(ws.iter_rows(max_row=1))]
    required = {"sku", "pe_eur", "pvp_eur", "uds_caja", "peso_kg"}
    missing = required - set(headers)
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}")

    idx = {h: i for i, h in enumerate(headers)}
    errors = []
    valid_rows = []

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        def cell(col: str):
            return row[idx[col]] if col in idx else None

        sku = str(cell("sku") or "").strip()
        if not sku:
            continue
        try:
            pe = Decimal(str(cell("pe_eur")))
            pvp = Decimal(str(cell("pvp_eur")))
            uds = int(cell("uds_caja") or 1)
            peso = Decimal(str(cell("peso_kg") or 0))
            cb_raw = str(cell("ceiling_basis") or "catalog_pvp").strip()
            cb = CeilingBasis(cb_raw) if cb_raw in CeilingBasis._value2member_map_ else CeilingBasis.catalog_pvp

            if pe <= 0:
                raise ValueError("pe_eur must be > 0")
            if pvp <= 0:
                raise ValueError("pvp_eur must be > 0")
            if uds < 1:
                raise ValueError("uds_caja must be >= 1")

            valid_rows.append({
                "sku": sku, "pe_eur": pe, "catalog_pvp_eur": pvp,
                "units_per_box": uds, "weight": peso, "ceiling_basis": cb,
            })
        except Exception as e:
            errors.append({"row": row_num, "sku": sku, "error": str(e)})

    # Compute ceiling preview using current route params
    loader = ParameterLoader(db)
    fee_row = (
        await db.execute(
            select(ChannelFeeParams).where(ChannelFeeParams.channel_id == channel_id)
        )
    ).scalars().first()
    route_row = (
        await db.execute(
            select(TradeRouteParams).where(TradeRouteParams.id == fee_row.route_id)
        )
    ).scalars().first() if fee_row else None

    ceiling_preview = []
    if route_row:
        from app.services.pricing.schemas import (
            ProductLogistics, ProductPricingData, RouteParams as RP,
        )
        route_dc = RP(
            fx_rate=route_row.fx_rate, fx_buffer_pct=route_row.fx_buffer_pct,
            freight_rate_per_kg=route_row.freight_rate_per_kg,
            freight_min_aed=route_row.freight_min_aed,
            import_tariff_pct=route_row.import_tariff_pct,
            local_warehouse_pct=route_row.local_warehouse_pct,
            handling_pct=route_row.handling_pct,
        )
        from app.services.pricing.engine import PricingEngine
        for r in valid_rows[:20]:  # preview first 20 only
            dummy_logistics = ProductLogistics(
                inbound_fee_aed=Decimal("0"), storage_fee_aed=Decimal("0"),
                fulfillment_fee_aed=Decimal("0"),
                default_scheme=FulfillmentSchemeEnum.canal_full,
            )
            dummy_product = ProductPricingData(
                sku=r["sku"], family_id="preview",
                pe_eur=r["pe_eur"], catalog_pvp_eur=r["catalog_pvp_eur"],
                units_per_box=r["units_per_box"], weight_kg=r.get("weight", Decimal("0")),
                b2c_labeling_aed=Decimal("0"), ceiling_basis=r["ceiling_basis"],
                logistics=dummy_logistics,
            )
            c_b2c = PricingEngine._ceiling_b2c(dummy_product, route_dc)
            c_b2b = PricingEngine._ceiling_b2b(dummy_product, route_dc)
            ceiling_preview.append({
                "sku": r["sku"],
                "ceiling_b2c_aed": float(c_b2c) if c_b2c != Decimal("Infinity") else None,
                "ceiling_b2b_aed": float(c_b2b) if c_b2b != Decimal("Infinity") else None,
            })

    upserted = 0
    if confirm:
        from sqlalchemy import update as sa_update
        for r in valid_rows:
            result = await db.execute(
                sa_update(Product)
                .where(Product.sku == r["sku"])
                .values(
                    pe_eur=r["pe_eur"],
                    catalog_pvp_eur=r["catalog_pvp_eur"],
                    units_per_box=r["units_per_box"],
                    weight=r.get("weight") or Product.weight,
                    ceiling_basis=r["ceiling_basis"],
                )
            )
            if result.rowcount > 0:
                upserted += 1
            else:
                errors.append({"row": None, "sku": r["sku"], "error": "SKU not found in products table"})
        await db.commit()

    return CatalogImportResult(
        total_rows=len(valid_rows) + len(errors),
        upserted=upserted,
        errors=errors,
        ceiling_preview=ceiling_preview,
    )


@router.post("/logistics/import", status_code=status.HTTP_200_OK)
async def import_logistics(
    file: UploadFile = File(...),
    confirm: bool = False,
    channel_id: uuid.UUID = Depends(_get_channel_id),
    db: AsyncSession = Depends(get_db),
):
    """Import logistics fees Excel (inbound_fee, storage_fee, fulfillment_fee per SKU)."""
    from app.models.channel_pricing import ChannelProductLogistics
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    headers = [str(cell.value).strip().lower() for cell in next(ws.iter_rows(max_row=1))]
    required = {"sku", "inbound_fee_aed", "storage_fee_aed", "fulfillment_fee_aed"}
    missing = required - set(headers)
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")

    idx = {h: i for i, h in enumerate(headers)}
    errors = []
    upserted = 0

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        def cell(col):
            return row[idx[col]] if col in idx else None

        sku = str(cell("sku") or "").strip()
        if not sku:
            continue
        try:
            values = {
                "product_sku": sku,
                "channel_id": channel_id,
                "inbound_fee_aed": Decimal(str(cell("inbound_fee_aed") or 0)),
                "storage_fee_aed": Decimal(str(cell("storage_fee_aed") or 0)),
                "fulfillment_fee_aed": Decimal(str(cell("fulfillment_fee_aed") or 0)),
                "default_scheme": str(cell("default_scheme") or "canal_full"),
            }
            if confirm:
                await db.execute(
                    pg_insert(ChannelProductLogistics)
                    .values(**values)
                    .on_conflict_do_update(
                        constraint="uq_channel_product_logistics",
                        set_={k: v for k, v in values.items()
                              if k not in ("product_sku", "channel_id")},
                    )
                )
                upserted += 1
        except Exception as e:
            errors.append({"row": row_num, "sku": sku, "error": str(e)})

    if confirm:
        await db.commit()

    return {"total_rows": row_num - 1, "upserted": upserted, "errors": errors}
```

- [ ] **7.3 Commit**

```bash
git add app/api/routes/channel_pricing.py
git commit -m "feat(pricing): catalog and logistics import endpoints (Excel upload)"
```

---

## Task 8: Tests de integración de la API

**Files:**
- Create: `tests/api/test_channel_pricing.py`

- [ ] **8.1 Crear los tests**

```python
# tests/api/test_channel_pricing.py
"""API integration tests for the channel pricing engine.

These tests use the FastAPI test client against a real test database
that has the seed data from seed_channel_pricing.py applied.
"""
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_get_params_amazon_uae(async_client: AsyncClient):
    """GET /pricing/amazon_uae/params returns route + fees + schemes."""
    resp = await async_client.get("/pricing/amazon_uae/params")
    assert resp.status_code == 200
    data = resp.json()
    assert "route" in data
    assert "fees" in data
    assert "schemes" in data
    assert data["fees"]["vat_pct"] == 5.0
    assert len(data["schemes"]) == 3  # FBA, Easy Ship, Self-Ship


@pytest.mark.asyncio
async def test_get_params_unknown_channel(async_client: AsyncClient):
    """GET /pricing/nonexistent/params returns 404."""
    resp = await async_client.get("/pricing/nonexistent_channel/params")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catalog_returns_200_with_semaforo(async_client: AsyncClient):
    """GET /pricing/amazon_uae/catalog returns semaforo summary."""
    resp = await async_client.get("/pricing/amazon_uae/catalog?selling_model=b2c")
    assert resp.status_code == 200
    data = resp.json()
    assert "semaforo" in data
    assert "rows" in data
    s = data["semaforo"]
    assert s["total"] == s["publishable"] + s["blocked"]


@pytest.mark.asyncio
async def test_margin_target_upsert_clears_overrides(
    async_client: AsyncClient, seeded_family_id: str, seeded_product_sku: str
):
    """PUT margin-targets should clear overrides for that family."""
    # Set override first
    await async_client.put(
        f"/pricing/amazon_uae/margin-overrides/{seeded_product_sku}",
        json={"margin_override_pct": 25, "selling_model": "b2c"},
    )
    # Update family margin — should delete the override
    resp = await async_client.put(
        "/pricing/amazon_uae/margin-targets",
        json={"family_id": seeded_family_id, "selling_model": "b2c",
              "margin_target_pct": 20},
    )
    assert resp.status_code == 204
    # Check override is gone
    catalog = await async_client.get(
        f"/pricing/amazon_uae/product/{seeded_product_sku}?selling_model=b2c"
    )
    assert catalog.json()["effective_margin_pct"] == 20.0


@pytest.mark.asyncio
async def test_patch_route_params_fx_rate(async_client: AsyncClient):
    """PATCH route-params updates fx_rate and it's reflected in GET /params."""
    resp = await async_client.patch(
        "/pricing/amazon_uae/route-params",
        json={"fx_rate": 4.30},
    )
    assert resp.status_code == 200
    assert float(resp.json()["fx_rate"]) == pytest.approx(4.30, abs=0.001)
```

- [ ] **8.2 Ejecutar los tests**

```bash
uv run pytest tests/api/test_channel_pricing.py -v
```

Si falla con `fixture 'async_client' not found`, verifica el `conftest.py` del proyecto para el cliente HTTP de prueba. El patrón habitual en proyectos FastAPI+asyncpg es:

```python
# En tests/conftest.py
@pytest.fixture
async def async_client(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

- [ ] **8.3 Commit**

```bash
git add tests/api/test_channel_pricing.py
git commit -m "test(pricing): API integration tests for channel pricing endpoints"
```

---

## Task 9: Verificación final y OpenAPI sync

- [ ] **9.1 Ejecutar suite completa**

```bash
cd mt-pricing-backend
uv run pytest tests/services/pricing/ tests/api/test_channel_pricing.py tests/models/test_channel_pricing_models.py -v --tb=short
```

Esperado: todos en PASS, cobertura engine ≥ 90%.

- [ ] **9.2 Ruff check sobre todos los ficheros nuevos**

```bash
uv run ruff check app/services/pricing/ app/api/routes/channel_pricing.py app/models/channel_pricing.py app/schemas/channel_pricing.py
uv run ruff format --check app/services/pricing/ app/api/routes/channel_pricing.py
```

Si hay errores, corregirlos con `uv run ruff check --fix`.

- [ ] **9.3 Regenerar el spec OpenAPI**

El proyecto requiere sincronizar el spec cuando cambian rutas o schemas (ver CLAUDE.md):

```bash
uv run python -m app.scripts.export_openapi
git add _bmad-output/planning-artifacts/mt-api-contract-openapi.json
git commit -m "chore(openapi): sync spec after channel pricing engine endpoints"
```

- [ ] **9.4 Commit final de cierre del plan**

```bash
git commit --allow-empty -m "feat(pricing): channel pricing engine complete — plan 2 done"
```

---

## Checklist de cobertura del spec

| Req spec | Task | Estado |
|---|---|---|
| 3 enums PG nuevos | Task 1 (Plan 1) | ✅ |
| 5 campos en products | Task 2 (Plan 1) | ✅ |
| 7 tablas nuevas | Task 2 (Plan 1) | ✅ |
| Seed Amazon UAE + Noon UAE | Task 5 (Plan 1) | ✅ |
| PricingEngine B2C + B2B | Task 2 | ✅ |
| `_logistics_cost` 3 esquemas | Task 2 | ✅ |
| Ceiling B2C + B2B | Task 2 | ✅ |
| ParameterLoader single-query | Task 3 | ✅ |
| ChannelOptimizer | Task 4 | ✅ |
| GET /params + PATCH route/fee | Task 5 | ✅ |
| PUT margin-targets + overrides | Task 5 | ✅ |
| GET /catalog con semáforo | Task 6 | ✅ |
| POST /optimize + /apply | Task 6 | ✅ |
| POST /catalog/import (Excel) | Task 7 | ✅ |
| POST /logistics/import | Task 7 | ✅ |
| OpenAPI sync | Task 9 | ✅ |
| Frontend Pricing Desk | — | 📋 Plan 3 |
| Flujo aprobación precios | — | 📋 Plan 3 |
