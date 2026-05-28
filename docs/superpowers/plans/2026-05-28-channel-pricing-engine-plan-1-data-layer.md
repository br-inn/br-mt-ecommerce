# Channel Pricing Engine — Plan 1: Data Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear la capa de datos completa del motor de precios multi-canal: 3 enums PG, 5 campos en `products`, 7 tablas nuevas, modelos ORM, schemas Pydantic y seed data inicial para Amazon UAE y Noon UAE.

**Architecture:** Migración Alembic única (147) que crea enums primero y luego tablas con FKs. Modelos SQLAlchemy en un fichero nuevo `channel_pricing.py`. Pydantic schemas separados por responsabilidad. Seed data via script ejecutable una sola vez.

**Tech Stack:** SQLAlchemy 2.0 async · Alembic · Pydantic v2 · asyncpg · pytest-asyncio · uv

**Spec de referencia:** `docs/superpowers/specs/2026-05-28-channel-pricing-engine-design.md`

---

## Estructura de ficheros

```
mt-pricing-backend/
├── alembic/versions/
│   └── 20260603_147_channel_pricing_engine.py   ← CREAR
├── app/
│   ├── models/
│   │   ├── enums.py                              ← MODIFICAR (añadir 3 enums)
│   │   ├── product.py                            ← MODIFICAR (5 columnas)
│   │   └── channel_pricing.py                   ← CREAR (7 modelos ORM)
│   └── schemas/
│       └── channel_pricing.py                   ← CREAR (schemas Pydantic)
├── app/scripts/
│   └── seed_channel_pricing.py                  ← CREAR (seed data)
└── tests/
    └── models/
        └── test_channel_pricing_models.py        ← CREAR
```

---

## Task 1: Enums en `app/models/enums.py`

**Files:**
- Modify: `app/models/enums.py`

Añadir los 3 nuevos enums al final del fichero existente, usando `create_type=False` (patrón del proyecto — el tipo PG se crea en la migración, no aquí).

- [ ] **1.1 Leer el fichero actual**

```bash
# Verificar el patrón existente antes de editar
grep -n "create_type" app/models/enums.py | head -5
```

Busca líneas como `sa.Enum(..., name="...", create_type=False)` — ese es el patrón a seguir.

- [ ] **1.2 Añadir los 3 enums nuevos al final de `app/models/enums.py`**

```python
# ── Channel Pricing Engine ─────────────────────────────────────────────
import enum as _enum


class SellingModel(str, _enum.Enum):
    """B2C = por unidad (Amazon/Noon). B2B = por caja (clientes directos)."""
    b2c = "b2c"
    b2b = "b2b"


class FulfillmentScheme(str, _enum.Enum):
    """Categoría genérica de fulfillment independiente del canal.
    
    canal_full      → FBA (Amazon) / FBN (Noon): canal almacena y envía.
    canal_lastmile  → Easy Ship: MT almacena, canal recoge y envía.
    merchant_managed → Self-Ship / FBM: MT almacena y envía.
    """
    canal_full       = "canal_full"
    canal_lastmile   = "canal_lastmile"
    merchant_managed = "merchant_managed"


class CeilingBasis(str, _enum.Enum):
    """Cómo se calcula el precio techo por producto.
    
    catalog_pvp  → techo = catalog_pvp_eur × fx + costes UAE (normal).
    margin_floor → techo calculado como margen mínimo garantizado
                   (para productos sin PVP en catálogo MT, ej. fondo de cuba).
    """
    catalog_pvp  = "catalog_pvp"
    margin_floor = "margin_floor"
```

- [ ] **1.3 Verificar que los imports no colisionan**

```bash
cd mt-pricing-backend && uv run python -c "from app.models.enums import SellingModel, FulfillmentScheme, CeilingBasis; print('OK')"
```

Esperado: `OK`

- [ ] **1.4 Commit**

```bash
git add app/models/enums.py
git commit -m "feat(pricing): add SellingModel, FulfillmentScheme, CeilingBasis enums"
```

---

## Task 2: Migración Alembic 147

**Files:**
- Create: `alembic/versions/20260603_147_channel_pricing_engine.py`

- [ ] **2.1 Verificar el HEAD actual**

```bash
cd mt-pricing-backend && uv run alembic current
```

Esperado: alguna revisión que termina con `(head)`. Apunta su ID — lo usarás en `Revises`.

- [ ] **2.2 Crear el fichero de migración**

Remplaza `<CURRENT_HEAD>` con el ID del paso anterior.

```python
# alembic/versions/20260603_147_channel_pricing_engine.py
"""channel pricing engine: enums, product fields, 7 new tables

Revision ID: 20260603_147
Revises: <CURRENT_HEAD>
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260603_147"
down_revision = "<CURRENT_HEAD>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Tipos PG — OBLIGATORIO antes de cualquier columna que los use ──
    op.execute("CREATE TYPE selling_model AS ENUM ('b2c', 'b2b')")
    op.execute(
        "CREATE TYPE fulfillment_scheme AS ENUM "
        "('canal_full', 'canal_lastmile', 'merchant_managed')"
    )
    op.execute("CREATE TYPE ceiling_basis AS ENUM ('catalog_pvp', 'margin_floor')")

    # ── 2. Campos nuevos en products ────────────────────────────────────
    op.add_column("products", sa.Column("pe_eur", sa.Numeric(14, 4), nullable=True))
    op.add_column("products", sa.Column("catalog_pvp_eur", sa.Numeric(14, 4), nullable=True))
    op.add_column("products", sa.Column("units_per_box", sa.Integer(), server_default="1"))
    op.add_column("products", sa.Column(
        "b2c_labeling_aed", sa.Numeric(10, 4), nullable=False, server_default="0"
    ))
    op.add_column("products", sa.Column(
        "ceiling_basis",
        sa.Enum("catalog_pvp", "margin_floor", name="ceiling_basis", create_type=False),
        nullable=False, server_default="catalog_pvp",
    ))

    # ── 3. trade_route_params ────────────────────────────────────────────
    op.create_table(
        "trade_route_params",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("route_code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("fx_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("fx_buffer_pct", sa.Numeric(5, 2), nullable=False, server_default="2"),
        sa.Column("freight_rate_per_kg", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("freight_min_aed", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("import_tariff_pct", sa.Numeric(5, 2), nullable=False, server_default="4.14"),
        sa.Column("local_warehouse_pct", sa.Numeric(5, 2), nullable=False, server_default="2"),
        sa.Column("handling_pct", sa.Numeric(5, 2), nullable=False, server_default="1.5"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text()),
        sa.UniqueConstraint("route_code", name="uq_trade_route_params_code"),
    )

    # ── 4. channel_fee_params ────────────────────────────────────────────
    op.create_table(
        "channel_fee_params",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mt_discount_pct", sa.Numeric(5, 2), nullable=False, server_default="15"),
        sa.Column("commission_pct", sa.Numeric(5, 2), nullable=False, server_default="11"),
        sa.Column("vat_pct", sa.Numeric(5, 2), nullable=False, server_default="5"),
        sa.Column("advertising_pct", sa.Numeric(5, 2), nullable=False, server_default="8"),
        sa.Column("returns_pct", sa.Numeric(5, 2), nullable=False, server_default="2"),
        sa.Column("storage_multiplier", sa.Numeric(6, 4), nullable=False, server_default="1.0"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text()),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"],
                                name="fk_channel_fee_params_channel"),
        sa.ForeignKeyConstraint(["route_id"], ["trade_route_params.id"],
                                name="fk_channel_fee_params_route"),
        sa.UniqueConstraint("channel_id", name="uq_channel_fee_params_channel"),
    )

    # ── 5. channel_scheme_params ─────────────────────────────────────────
    op.create_table(
        "channel_scheme_params",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "fulfillment_scheme",
            sa.Enum("canal_full", "canal_lastmile", "merchant_managed",
                    name="fulfillment_scheme", create_type=False),
            nullable=False,
        ),
        sa.Column("scheme_label", sa.Text(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("flat_supplement_aed", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("pct_surcharge", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("max_weight_kg", sa.Numeric(8, 2)),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"],
                                name="fk_channel_scheme_params_channel"),
        sa.UniqueConstraint("channel_id", "fulfillment_scheme",
                            name="uq_channel_scheme_params"),
    )

    # ── 6. channel_product_logistics ─────────────────────────────────────
    op.create_table(
        "channel_product_logistics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_sku", sa.Text(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inbound_fee_aed", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("storage_fee_aed", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("fulfillment_fee_aed", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column(
            "default_scheme",
            sa.Enum("canal_full", "canal_lastmile", "merchant_managed",
                    name="fulfillment_scheme", create_type=False),
            nullable=False, server_default="canal_full",
        ),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text()),
        sa.ForeignKeyConstraint(["product_sku"], ["products.sku"], ondelete="CASCADE",
                                name="fk_channel_product_logistics_sku"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"],
                                name="fk_channel_product_logistics_channel"),
        sa.UniqueConstraint("product_sku", "channel_id",
                            name="uq_channel_product_logistics"),
    )

    # ── 7. channel_margin_targets ─────────────────────────────────────────
    op.create_table(
        "channel_margin_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "selling_model",
            sa.Enum("b2c", "b2b", name="selling_model", create_type=False),
            nullable=False, server_default="b2c",
        ),
        sa.Column("margin_target_pct", sa.Numeric(5, 2), nullable=False, server_default="12"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text()),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"],
                                name="fk_channel_margin_targets_channel"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"],
                                name="fk_channel_margin_targets_family"),
        sa.UniqueConstraint("channel_id", "family_id", "selling_model",
                            name="uq_channel_margin_targets"),
    )

    # ── 8. channel_margin_overrides ───────────────────────────────────────
    op.create_table(
        "channel_margin_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_sku", sa.Text(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "selling_model",
            sa.Enum("b2c", "b2b", name="selling_model", create_type=False),
            nullable=False, server_default="b2c",
        ),
        sa.Column("margin_override_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text()),
        sa.ForeignKeyConstraint(["product_sku"], ["products.sku"], ondelete="CASCADE",
                                name="fk_channel_margin_overrides_sku"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"],
                                name="fk_channel_margin_overrides_channel"),
        sa.UniqueConstraint("product_sku", "channel_id", "selling_model",
                            name="uq_channel_margin_overrides"),
    )

    # ── 9. pricing_scenarios ──────────────────────────────────────────────
    op.create_table(
        "pricing_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "selling_model",
            sa.Enum("b2c", "b2b", name="selling_model", create_type=False),
            nullable=False, server_default="b2c",
        ),
        sa.Column("slot", sa.CHAR(1), nullable=False),
        sa.Column("label", sa.Text()),
        sa.Column("config_jsonb", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("snapshot_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text()),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"],
                                name="fk_pricing_scenarios_channel"),
        sa.CheckConstraint("slot IN ('A','B')", name="ck_pricing_scenarios_slot"),
        sa.UniqueConstraint("channel_id", "selling_model", "slot",
                            name="uq_pricing_scenarios_slot"),
    )

    # ── 10. Índices de lookup ─────────────────────────────────────────────
    op.create_index("idx_channel_fee_params_channel",
                    "channel_fee_params", ["channel_id"])
    op.create_index("idx_channel_scheme_params_lookup",
                    "channel_scheme_params", ["channel_id", "fulfillment_scheme"])
    op.create_index("idx_channel_product_logistics_sku_ch",
                    "channel_product_logistics", ["product_sku", "channel_id"])
    op.create_index("idx_channel_product_logistics_channel",
                    "channel_product_logistics", ["channel_id"])
    op.create_index("idx_channel_margin_targets_lookup",
                    "channel_margin_targets", ["channel_id", "family_id", "selling_model"])
    op.create_index("idx_channel_margin_overrides_sku",
                    "channel_margin_overrides", ["product_sku", "channel_id", "selling_model"])
    op.create_index("idx_pricing_scenarios_lookup",
                    "pricing_scenarios", ["channel_id", "selling_model"])


def downgrade() -> None:
    # Índices
    for idx in [
        "idx_pricing_scenarios_lookup",
        "idx_channel_margin_overrides_sku",
        "idx_channel_margin_targets_lookup",
        "idx_channel_product_logistics_channel",
        "idx_channel_product_logistics_sku_ch",
        "idx_channel_scheme_params_lookup",
        "idx_channel_fee_params_channel",
    ]:
        op.drop_index(idx)
    # Tablas (orden inverso por dependencias FK)
    for tbl in [
        "pricing_scenarios",
        "channel_margin_overrides",
        "channel_margin_targets",
        "channel_product_logistics",
        "channel_scheme_params",
        "channel_fee_params",
        "trade_route_params",
    ]:
        op.drop_table(tbl)
    # Columnas en products (orden inverso)
    for col in ["ceiling_basis", "b2c_labeling_aed", "units_per_box",
                "catalog_pvp_eur", "pe_eur"]:
        op.drop_column("products", col)
    # Tipos PG (orden inverso — ceiling_basis primero porque solo lo usa products)
    op.execute("DROP TYPE IF EXISTS ceiling_basis")
    op.execute("DROP TYPE IF EXISTS fulfillment_scheme")
    op.execute("DROP TYPE IF EXISTS selling_model")
```

- [ ] **2.3 Ejecutar la migración**

```bash
cd mt-pricing-backend && uv run alembic upgrade head
```

Esperado: `Running upgrade <prev> -> 20260603_147, channel pricing engine: enums, product fields, 7 new tables`

Si falla con `DatatypeMismatch` en los enums, verifica que el bloque `op.execute("CREATE TYPE ...")` está antes de cualquier `op.add_column` o `op.create_table` que use ese tipo.

- [ ] **2.4 Verificar que la migración es reversible**

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Ambos deben completarse sin error.

- [ ] **2.5 Commit**

```bash
git add alembic/versions/20260603_147_channel_pricing_engine.py
git commit -m "feat(pricing): migration 147 — channel pricing engine tables and enums"
```

---

## Task 3: Modelos ORM en `app/models/channel_pricing.py`

**Files:**
- Create: `app/models/channel_pricing.py`
- Modify: `app/models/__init__.py` (exportar los nuevos modelos)
- Modify: `app/models/product.py` (añadir 5 columnas)

- [ ] **3.1 Añadir los 5 campos nuevos al modelo Product**

En `app/models/product.py`, dentro de la clase `Product`, añadir después de los campos existentes de peso/dimensiones:

```python
# ── Channel Pricing Engine ────────────────────────────────────────────
pe_eur: Mapped[Optional[Decimal]] = mapped_column(
    Numeric(14, 4), nullable=True, comment="Precio compra MT España por unidad (EUR)"
)
catalog_pvp_eur: Mapped[Optional[Decimal]] = mapped_column(
    Numeric(14, 4), nullable=True, comment="PVP catálogo MT por unidad (EUR) — base del techo"
)
units_per_box: Mapped[int] = mapped_column(
    Integer, nullable=False, server_default="1",
    comment="Unidades por caja (MOQ MT). Para B2C divide el flete."
)
b2c_labeling_aed: Mapped[Decimal] = mapped_column(
    Numeric(10, 4), nullable=False, server_default="0",
    comment="Coste etiquetado/prep por unidad para canales B2C (AED)"
)
ceiling_basis: Mapped[CeilingBasis] = mapped_column(
    Enum(CeilingBasis, name="ceiling_basis", create_type=False),
    nullable=False, server_default="catalog_pvp",
)
```

Asegúrate de importar `CeilingBasis` desde `app.models.enums` al inicio del fichero.

- [ ] **3.2 Verificar que el modelo Product importa bien**

```bash
uv run python -c "from app.models.product import Product; print(Product.__table__.columns.keys())" 2>&1 | tail -5
```

Esperado: lista que incluye `pe_eur`, `catalog_pvp_eur`, `units_per_box`, `b2c_labeling_aed`, `ceiling_basis`.

- [ ] **3.3 Crear `app/models/channel_pricing.py`**

```python
# app/models/channel_pricing.py
"""ORM models for the channel pricing engine.

Seven tables that together support multi-channel, multi-selling-model
price calculation: route params → channel fees → scheme configs →
product logistics → margin targets/overrides → scenarios.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy import Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import FulfillmentScheme, SellingModel


class TradeRouteParams(Base):
    """Cost parameters for a physical trade route (e.g. Spain → UAE).

    Shared by all channels that use the same route. Amazon UAE and Noon UAE
    both use route_code='es_to_uae'.
    """

    __tablename__ = "trade_route_params"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    route_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    fx_buffer_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="2"
    )
    freight_rate_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0",
        comment="EUR/kg. 0 = placeholder until 3PL quote received."
    )
    freight_min_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default="0",
        comment="Minimum freight charge per shipment in AED."
    )
    import_tariff_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="4.14"
    )
    local_warehouse_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="2"
    )
    handling_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="1.5"
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text)


class ChannelFeeParams(Base):
    """Marketplace commissions and financial parameters per channel.

    One row per channel. Links to the trade route used to reach that channel.
    mt_discount_pct is the commercial discount MT Spain gives us as distributor.
    """

    __tablename__ = "channel_fee_params"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT", name="fk_channel_fee_params_channel"),
        nullable=False, unique=True,
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trade_route_params.id", ondelete="RESTRICT",
                   name="fk_channel_fee_params_route"),
        nullable=False,
    )
    mt_discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="15"
    )
    commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="11"
    )
    vat_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="5"
    )
    advertising_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="8"
    )
    returns_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="2"
    )
    storage_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="1.0",
        comment="Multiplier on storage_fee_aed. 1.0 = full rate (100% in UI)."
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text)


class ChannelSchemeParams(Base):
    """Fulfillment scheme configuration per channel.

    One row per (channel, scheme). Defines which schemes are available and
    their cost supplements relative to the base fulfillment_fee_aed.
    """

    __tablename__ = "channel_scheme_params"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT",
                   name="fk_channel_scheme_params_channel"),
        nullable=False,
    )
    fulfillment_scheme: Mapped[FulfillmentScheme] = mapped_column(
        Enum(FulfillmentScheme, name="fulfillment_scheme", create_type=False),
        nullable=False,
    )
    scheme_label: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Human-readable label: FBA, Easy Ship, Self-Ship, FBN, FBM, etc."
    )
    is_available: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="true"
    )
    flat_supplement_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default="0",
        comment="Fixed AED surcharge added on top of fulfillment_fee (e.g. Easy Ship: 6 AED)."
    )
    pct_surcharge: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0",
        comment="% surcharge on (fulfillment_fee + flat_supplement). Self-Ship: 15%."
    )
    max_weight_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 2),
        comment="NULL = no weight limit. FBA Amazon = 25 kg."
    )

    __table_args__ = (
        sa.UniqueConstraint("channel_id", "fulfillment_scheme",
                            name="uq_channel_scheme_params"),
    )


class ChannelProductLogistics(Base):
    """Per-SKU fulfillment fees for a specific channel.

    Populated by importing the channel's logistics data (FBA rate card for
    Amazon, FBN rate card for Noon). One row per (product_sku, channel).
    """

    __tablename__ = "channel_product_logistics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE",
                   name="fk_channel_product_logistics_sku"),
        nullable=False,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT",
                   name="fk_channel_product_logistics_channel"),
        nullable=False,
    )
    inbound_fee_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0",
        comment="Amazon: fba_env. Noon: inbound fee to FBN warehouse."
    )
    storage_fee_aed: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="0",
        comment="Per-unit storage fee. Multiplied by storage_multiplier from channel_fee_params."
    )
    fulfillment_fee_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default="0",
        comment="Pick-pack-ship fee. Also base for Easy Ship and Self-Ship formulas."
    )
    default_scheme: Mapped[FulfillmentScheme] = mapped_column(
        Enum(FulfillmentScheme, name="fulfillment_scheme", create_type=False),
        nullable=False, server_default="canal_full",
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        sa.UniqueConstraint("product_sku", "channel_id",
                            name="uq_channel_product_logistics"),
    )


class ChannelMarginTarget(Base):
    """Target margin per channel × product family × selling model.

    The engine uses this as the default margin when no per-product override
    exists. family_id FK → families.id (vocabulary table).
    """

    __tablename__ = "channel_margin_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT",
                   name="fk_channel_margin_targets_channel"),
        nullable=False,
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="RESTRICT",
                   name="fk_channel_margin_targets_family"),
        nullable=False,
    )
    selling_model: Mapped[SellingModel] = mapped_column(
        Enum(SellingModel, name="selling_model", create_type=False),
        nullable=False, server_default="b2c",
    )
    margin_target_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="12"
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        sa.UniqueConstraint("channel_id", "family_id", "selling_model",
                            name="uq_channel_margin_targets"),
    )


class ChannelMarginOverride(Base):
    """Per-product margin override for a specific channel and selling model.

    Takes precedence over ChannelMarginTarget for the same (sku, channel,
    selling_model) combination. Deleted in bulk when the family margin changes.
    """

    __tablename__ = "channel_margin_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE",
                   name="fk_channel_margin_overrides_sku"),
        nullable=False,
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT",
                   name="fk_channel_margin_overrides_channel"),
        nullable=False,
    )
    selling_model: Mapped[SellingModel] = mapped_column(
        Enum(SellingModel, name="selling_model", create_type=False),
        nullable=False, server_default="b2c",
    )
    margin_override_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        sa.UniqueConstraint("product_sku", "channel_id", "selling_model",
                            name="uq_channel_margin_overrides"),
    )


class PricingScenario(Base):
    """A/B scenario snapshot for a channel + selling model combination.

    config_jsonb stores a complete snapshot of: route params, channel fees,
    family margin targets, and product overrides at the time of saving.
    Only 2 slots (A and B) per (channel, selling_model).
    """

    __tablename__ = "pricing_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="RESTRICT",
                   name="fk_pricing_scenarios_channel"),
        nullable=False,
    )
    selling_model: Mapped[SellingModel] = mapped_column(
        Enum(SellingModel, name="selling_model", create_type=False),
        nullable=False, server_default="b2c",
    )
    slot: Mapped[str] = mapped_column(sa.CHAR(1), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(Text)
    config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    snapshot_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        sa.CheckConstraint("slot IN ('A','B')", name="ck_pricing_scenarios_slot"),
        sa.UniqueConstraint("channel_id", "selling_model", "slot",
                            name="uq_pricing_scenarios_slot"),
    )
```

- [ ] **3.4 Exportar los nuevos modelos en `app/models/__init__.py`**

Añadir al final de las importaciones existentes:

```python
from app.models.channel_pricing import (  # noqa: F401
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelProductLogistics,
    ChannelSchemeParams,
    PricingScenario,
    TradeRouteParams,
)
```

- [ ] **3.5 Verificar que todos los modelos importan sin error**

```bash
uv run python -c "
from app.models.channel_pricing import (
    TradeRouteParams, ChannelFeeParams, ChannelSchemeParams,
    ChannelProductLogistics, ChannelMarginTarget,
    ChannelMarginOverride, PricingScenario,
)
print('All models OK')
"
```

Esperado: `All models OK`

- [ ] **3.6 Verificar que `alembic check` no detecta drift**

```bash
uv run alembic check
```

Esperado: `No new upgrade operations detected.`

Si sale drift, hay un campo en el modelo ORM que no tiene su columna en la migración (o viceversa). Corregir el fichero que difiere.

- [ ] **3.7 Commit**

```bash
git add app/models/enums.py app/models/product.py app/models/channel_pricing.py app/models/__init__.py
git commit -m "feat(pricing): ORM models for channel pricing engine (7 tables)"
```

---

## Task 4: Schemas Pydantic en `app/schemas/channel_pricing.py`

**Files:**
- Create: `app/schemas/channel_pricing.py`

- [ ] **4.1 Crear el fichero de schemas**

```python
# app/schemas/channel_pricing.py
"""Pydantic schemas for the channel pricing engine API."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import CeilingBasis, FulfillmentScheme, SellingModel


# ── Trade Route Params ────────────────────────────────────────────────

class TradeRouteParamsRead(BaseModel):
    id: uuid.UUID
    route_code: str
    description: Optional[str]
    fx_rate: Decimal
    fx_buffer_pct: Decimal
    freight_rate_per_kg: Decimal
    freight_min_aed: Decimal
    import_tariff_pct: Decimal
    local_warehouse_pct: Decimal
    handling_pct: Decimal

    model_config = {"from_attributes": True}


class TradeRouteParamsUpdate(BaseModel):
    fx_rate: Optional[Decimal] = None
    fx_buffer_pct: Optional[Decimal] = None
    freight_rate_per_kg: Optional[Decimal] = Field(None, ge=0)
    freight_min_aed: Optional[Decimal] = Field(None, ge=0)
    import_tariff_pct: Optional[Decimal] = Field(None, ge=0, le=50)
    local_warehouse_pct: Optional[Decimal] = Field(None, ge=0, le=20)
    handling_pct: Optional[Decimal] = Field(None, ge=0, le=20)


# ── Channel Fee Params ────────────────────────────────────────────────

class ChannelFeeParamsRead(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    route_id: uuid.UUID
    mt_discount_pct: Decimal
    commission_pct: Decimal
    vat_pct: Decimal
    advertising_pct: Decimal
    returns_pct: Decimal
    storage_multiplier: Decimal
    total_fees_pct: Decimal  # computed: commission + vat + advertising + returns

    model_config = {"from_attributes": True}


class ChannelFeeParamsUpdate(BaseModel):
    mt_discount_pct: Optional[Decimal] = Field(None, ge=0, le=50)
    commission_pct: Optional[Decimal] = Field(None, ge=0, le=30)
    vat_pct: Optional[Decimal] = Field(None, ge=0, le=30)
    advertising_pct: Optional[Decimal] = Field(None, ge=0, le=30)
    returns_pct: Optional[Decimal] = Field(None, ge=0, le=15)
    storage_multiplier: Optional[Decimal] = Field(None, ge=0, le=5)


# ── Channel Scheme Params ─────────────────────────────────────────────

class ChannelSchemeParamsRead(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    fulfillment_scheme: FulfillmentScheme
    scheme_label: str
    is_available: bool
    flat_supplement_aed: Decimal
    pct_surcharge: Decimal
    max_weight_kg: Optional[Decimal]

    model_config = {"from_attributes": True}


# ── Channel Product Logistics ─────────────────────────────────────────

class ChannelProductLogisticsRead(BaseModel):
    product_sku: str
    channel_id: uuid.UUID
    inbound_fee_aed: Decimal
    storage_fee_aed: Decimal
    fulfillment_fee_aed: Decimal
    default_scheme: FulfillmentScheme

    model_config = {"from_attributes": True}


class ChannelProductLogisticsUpsert(BaseModel):
    product_sku: str
    inbound_fee_aed: Decimal = Field(ge=0)
    storage_fee_aed: Decimal = Field(ge=0)
    fulfillment_fee_aed: Decimal = Field(ge=0)
    default_scheme: FulfillmentScheme = FulfillmentScheme.canal_full


# ── Margin Targets ────────────────────────────────────────────────────

class MarginTargetRead(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    family_id: uuid.UUID
    family_name: str  # joined from families table
    selling_model: SellingModel
    margin_target_pct: Decimal

    model_config = {"from_attributes": True}


class MarginTargetUpsert(BaseModel):
    family_id: uuid.UUID
    selling_model: SellingModel = SellingModel.b2c
    margin_target_pct: Decimal = Field(ge=-10, le=80)


# ── Margin Overrides ──────────────────────────────────────────────────

class MarginOverrideRead(BaseModel):
    product_sku: str
    channel_id: uuid.UUID
    selling_model: SellingModel
    margin_override_pct: Decimal
    reason: Optional[str]

    model_config = {"from_attributes": True}


class MarginOverrideUpsert(BaseModel):
    margin_override_pct: Decimal = Field(ge=-10, le=80)
    selling_model: SellingModel = SellingModel.b2c
    reason: Optional[str] = None


# ── Catalog Import ────────────────────────────────────────────────────

class CatalogImportRow(BaseModel):
    sku: str
    pe_eur: Decimal = Field(gt=0)
    catalog_pvp_eur: Decimal = Field(gt=0)
    units_per_box: int = Field(ge=1)
    weight_kg: Optional[Decimal] = Field(None, gt=0)
    ceiling_basis: CeilingBasis = CeilingBasis.catalog_pvp


class CatalogImportResult(BaseModel):
    total_rows: int
    upserted: int
    errors: list[dict]  # [{row, sku, error}]
    ceiling_preview: list[dict]  # [{sku, ceiling_b2c_aed, ceiling_b2b_aed}]


class LogisticsImportRow(BaseModel):
    sku: str
    inbound_fee_aed: Decimal = Field(ge=0)
    storage_fee_aed: Decimal = Field(ge=0)
    fulfillment_fee_aed: Decimal = Field(ge=0)
    default_scheme: FulfillmentScheme = FulfillmentScheme.canal_full


# ── Scenarios ─────────────────────────────────────────────────────────

class ScenarioRead(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    selling_model: SellingModel
    slot: str
    label: Optional[str]
    snapshot_at: str

    model_config = {"from_attributes": True}
```

- [ ] **4.2 Verificar que los schemas importan sin error**

```bash
uv run python -c "from app.schemas.channel_pricing import TradeRouteParamsRead, CatalogImportRow; print('Schemas OK')"
```

Esperado: `Schemas OK`

- [ ] **4.3 Commit**

```bash
git add app/schemas/channel_pricing.py
git commit -m "feat(pricing): Pydantic schemas for channel pricing engine API"
```

---

## Task 5: Seed data — Amazon UAE y Noon UAE

**Files:**
- Create: `app/scripts/seed_channel_pricing.py`

Este script se ejecuta una sola vez contra la DB. Inserta los datos iniciales con los valores del Pricing Desk original.

- [ ] **5.1 Crear el script de seed**

```python
# app/scripts/seed_channel_pricing.py
"""Seed initial channel pricing data for Amazon UAE and Noon UAE.

Run once: uv run python -m app.scripts.seed_channel_pricing
Idempotent: uses INSERT ... ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session_ctx


ROUTE_CODE = "es_to_uae"

# Default values from original Pricing Desk (MT_Amazon_UAE_App_Pricing_Desk)
ROUTE_DEFAULTS = {
    "route_code": ROUTE_CODE,
    "description": "Spain (MT España) → UAE (Dubai warehouse)",
    "fx_rate": "4.28",
    "fx_buffer_pct": "2",
    "freight_rate_per_kg": "0",   # placeholder — pending 3PL quote
    "freight_min_aed": "0",
    "import_tariff_pct": "4.14",
    "local_warehouse_pct": "2",
    "handling_pct": "1.5",
}

# channel_code → fee params
CHANNEL_FEES = {
    "amazon_uae": {
        "mt_discount_pct": "15",
        "commission_pct": "11",    # referral — verify in Seller Central (may be 15%)
        "vat_pct": "5",
        "advertising_pct": "8",
        "returns_pct": "2",
        "storage_multiplier": "1.0",
    },
    "noon_uae": {
        "mt_discount_pct": "15",
        "commission_pct": "10",    # Noon default — confirm with Noon account manager
        "vat_pct": "5",
        "advertising_pct": "5",
        "returns_pct": "2",
        "storage_multiplier": "1.0",
    },
}

# channel_code → list of scheme configs
CHANNEL_SCHEMES = {
    "amazon_uae": [
        {
            "fulfillment_scheme": "canal_full",
            "scheme_label": "FBA",
            "is_available": True,
            "flat_supplement_aed": "0",
            "pct_surcharge": "0",
            "max_weight_kg": "25",   # Amazon FBA limit
        },
        {
            "fulfillment_scheme": "canal_lastmile",
            "scheme_label": "Easy Ship",
            "is_available": True,
            "flat_supplement_aed": "6",  # Amazon picks up, adds 6 AED
            "pct_surcharge": "0",
            "max_weight_kg": None,
        },
        {
            "fulfillment_scheme": "merchant_managed",
            "scheme_label": "Self-Ship",
            "is_available": True,
            "flat_supplement_aed": "0",
            "pct_surcharge": "15",  # own courier ~15% more than Easy Ship
            "max_weight_kg": None,
        },
    ],
    "noon_uae": [
        {
            "fulfillment_scheme": "canal_full",
            "scheme_label": "FBN",
            "is_available": True,
            "flat_supplement_aed": "0",
            "pct_surcharge": "0",
            "max_weight_kg": None,
        },
        {
            "fulfillment_scheme": "merchant_managed",
            "scheme_label": "FBM",
            "is_available": True,
            "flat_supplement_aed": "0",
            "pct_surcharge": "0",
            "max_weight_kg": None,
        },
    ],
}

# Family name → margin_target_pct for b2c (from Pricing Desk defaults)
FAMILY_MARGINS_B2C = {
    "VÁLVULAS INOX 3 PIEZAS (FONDO DE CUBA)": 12,
    "VÁLVULAS DE LATÓN": 12,
    "MANGUITOS ELÁSTICOS": 0,
    "VÁLVULAS INOXIDABLES": 40,
    "VÁLVULAS DE FUNDICIÓN": 25,
}


async def seed(session: AsyncSession) -> None:
    # 1. Insert trade route
    await session.execute(text("""
        INSERT INTO trade_route_params
            (route_code, description, fx_rate, fx_buffer_pct,
             freight_rate_per_kg, freight_min_aed,
             import_tariff_pct, local_warehouse_pct, handling_pct)
        VALUES
            (:route_code, :description, :fx_rate, :fx_buffer_pct,
             :freight_rate_per_kg, :freight_min_aed,
             :import_tariff_pct, :local_warehouse_pct, :handling_pct)
        ON CONFLICT (route_code) DO NOTHING
    """), ROUTE_DEFAULTS)
    await session.flush()

    route_id = (await session.execute(
        text("SELECT id FROM trade_route_params WHERE route_code = :code"),
        {"code": ROUTE_CODE},
    )).scalar_one()

    for channel_code, fee_params in CHANNEL_FEES.items():
        # 2. Get channel id
        channel_id = (await session.execute(
            text("SELECT id FROM channels WHERE code = :code"),
            {"code": channel_code},
        )).scalar_one_or_none()

        if channel_id is None:
            print(f"  SKIP {channel_code} — channel not found in DB")
            continue

        # 3. Insert fee params
        await session.execute(text("""
            INSERT INTO channel_fee_params
                (channel_id, route_id, mt_discount_pct, commission_pct,
                 vat_pct, advertising_pct, returns_pct, storage_multiplier)
            VALUES
                (:channel_id, :route_id, :mt_discount_pct, :commission_pct,
                 :vat_pct, :advertising_pct, :returns_pct, :storage_multiplier)
            ON CONFLICT (channel_id) DO NOTHING
        """), {"channel_id": channel_id, "route_id": route_id, **fee_params})

        # 4. Insert scheme params
        for scheme in CHANNEL_SCHEMES.get(channel_code, []):
            await session.execute(text("""
                INSERT INTO channel_scheme_params
                    (channel_id, fulfillment_scheme, scheme_label, is_available,
                     flat_supplement_aed, pct_surcharge, max_weight_kg)
                VALUES
                    (:channel_id, :fulfillment_scheme, :scheme_label, :is_available,
                     :flat_supplement_aed, :pct_surcharge, :max_weight_kg)
                ON CONFLICT (channel_id, fulfillment_scheme) DO NOTHING
            """), {"channel_id": channel_id, **scheme})

        # 5. Insert family margin targets (b2c)
        for family_name, margin in FAMILY_MARGINS_B2C.items():
            family_id = (await session.execute(
                text("SELECT id FROM families WHERE name = :name"),
                {"name": family_name},
            )).scalar_one_or_none()

            if family_id is None:
                print(f"  SKIP family '{family_name}' — not found in families table")
                continue

            await session.execute(text("""
                INSERT INTO channel_margin_targets
                    (channel_id, family_id, selling_model, margin_target_pct)
                VALUES
                    (:channel_id, :family_id, 'b2c', :margin_pct)
                ON CONFLICT (channel_id, family_id, selling_model) DO NOTHING
            """), {"channel_id": channel_id, "family_id": family_id,
                   "margin_pct": margin})

        print(f"  Seeded {channel_code}")

    await session.commit()
    print("Seed complete.")


async def main() -> None:
    async with get_async_session_ctx() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **5.2 Ejecutar el seed**

```bash
cd mt-pricing-backend && uv run python -m app.scripts.seed_channel_pricing
```

Esperado:
```
  Seeded amazon_uae
  Seeded noon_uae
Seed complete.
```

Si sale `SKIP family '...' — not found in families table`, significa que los nombres de familia en el seed no coinciden con los de la tabla `families`. Ejecuta:
```sql
SELECT name FROM families ORDER BY name;
```
y ajusta `FAMILY_MARGINS_B2C` con los nombres exactos del vocabulario.

- [ ] **5.3 Verificar el seed**

```bash
uv run python -c "
import asyncio
from app.db.session import get_async_session_ctx
from sqlalchemy import text

async def check():
    async with get_async_session_ctx() as s:
        r = await s.execute(text('SELECT route_code FROM trade_route_params'))
        print('Routes:', r.scalars().all())
        f = await s.execute(text('SELECT COUNT(*) FROM channel_fee_params'))
        print('Fee params rows:', f.scalar())
        sc = await s.execute(text('SELECT COUNT(*) FROM channel_scheme_params'))
        print('Scheme rows:', sc.scalar())
        mt = await s.execute(text('SELECT COUNT(*) FROM channel_margin_targets'))
        print('Margin targets:', mt.scalar())

asyncio.run(check())
"
```

Esperado:
```
Routes: ['es_to_uae']
Fee params rows: 2
Scheme rows: 5
Margin targets: 10   (5 familias × 2 canales)
```

- [ ] **5.4 Commit**

```bash
git add app/scripts/seed_channel_pricing.py
git commit -m "feat(pricing): seed data — Amazon UAE and Noon UAE initial params"
```

---

## Task 6: Tests de integración del modelo

**Files:**
- Create: `tests/models/test_channel_pricing_models.py`

- [ ] **6.1 Escribir los tests**

```python
# tests/models/test_channel_pricing_models.py
"""Integration tests for channel pricing ORM models.

These tests hit a real DB (the test database configured in conftest).
They verify: FK constraints, UNIQUE constraints, cascade deletes.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel_pricing import (
    ChannelFeeParams,
    ChannelMarginOverride,
    ChannelMarginTarget,
    ChannelProductLogistics,
    ChannelSchemeParams,
    TradeRouteParams,
)
from app.models.enums import FulfillmentScheme, SellingModel


@pytest.mark.asyncio
async def test_trade_route_params_unique_route_code(db_session: AsyncSession):
    """Two rows with the same route_code must raise IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    route = TradeRouteParams(
        route_code="test_route",
        fx_rate="4.28",
        fx_buffer_pct="2",
        freight_rate_per_kg="0",
        freight_min_aed="0",
        import_tariff_pct="4.14",
        local_warehouse_pct="2",
        handling_pct="1.5",
    )
    db_session.add(route)
    await db_session.flush()

    duplicate = TradeRouteParams(
        route_code="test_route",  # same code
        fx_rate="4.30",
        fx_buffer_pct="2",
        freight_rate_per_kg="0",
        freight_min_aed="0",
        import_tariff_pct="4.14",
        local_warehouse_pct="2",
        handling_pct="1.5",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_channel_scheme_params_unique_channel_scheme(
    db_session: AsyncSession, amazon_uae_channel_id
):
    """Cannot insert two rows with same (channel_id, fulfillment_scheme)."""
    from sqlalchemy.exc import IntegrityError

    s1 = ChannelSchemeParams(
        channel_id=amazon_uae_channel_id,
        fulfillment_scheme=FulfillmentScheme.canal_full,
        scheme_label="FBA",
        is_available=True,
        flat_supplement_aed="0",
        pct_surcharge="0",
    )
    db_session.add(s1)
    await db_session.flush()

    s2 = ChannelSchemeParams(
        channel_id=amazon_uae_channel_id,
        fulfillment_scheme=FulfillmentScheme.canal_full,  # duplicate
        scheme_label="FBA2",
        is_available=True,
        flat_supplement_aed="0",
        pct_surcharge="0",
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_channel_margin_override_cascade_delete(
    db_session: AsyncSession, amazon_uae_channel_id, seeded_product_sku: str
):
    """Deleting the product cascades to its margin overrides."""
    from sqlalchemy import delete
    from app.models.product import Product

    override = ChannelMarginOverride(
        product_sku=seeded_product_sku,
        channel_id=amazon_uae_channel_id,
        selling_model=SellingModel.b2c,
        margin_override_pct="20",
    )
    db_session.add(override)
    await db_session.flush()

    # Delete the product
    await db_session.execute(
        delete(Product).where(Product.sku == seeded_product_sku)
    )
    await db_session.flush()

    # Override must be gone
    result = await db_session.execute(
        select(ChannelMarginOverride).where(
            ChannelMarginOverride.product_sku == seeded_product_sku
        )
    )
    assert result.scalars().first() is None
```

- [ ] **6.2 Ejecutar los tests**

```bash
cd mt-pricing-backend && uv run pytest tests/models/test_channel_pricing_models.py -v
```

Esperado: todos en PASS. Si falla con `fixture 'amazon_uae_channel_id' not found`, añade la fixture al `conftest.py` del proyecto:

```python
# En tests/conftest.py — añadir si no existe
@pytest.fixture
async def amazon_uae_channel_id(db_session: AsyncSession):
    from sqlalchemy import select
    from app.models.channels import Channel
    result = await db_session.execute(
        select(Channel.id).where(Channel.code == "amazon_uae")
    )
    return result.scalar_one()
```

- [ ] **6.3 Commit**

```bash
git add tests/models/test_channel_pricing_models.py
git commit -m "test(pricing): integration tests for channel pricing ORM models"
```

---

## Verificación final del Plan 1

```bash
cd mt-pricing-backend

# 1. Migración HEAD limpio
uv run alembic check

# 2. Todos los modelos importan
uv run python -c "from app.models import TradeRouteParams, ChannelFeeParams, ChannelSchemeParams, ChannelProductLogistics, ChannelMarginTarget, ChannelMarginOverride, PricingScenario; print('OK')"

# 3. Tests pasan
uv run pytest tests/models/test_channel_pricing_models.py -v

# 4. Ruff y mypy sin errores en los ficheros nuevos
uv run ruff check app/models/channel_pricing.py app/schemas/channel_pricing.py app/scripts/seed_channel_pricing.py
```

---

**Continuar con:** `docs/superpowers/plans/2026-05-28-channel-pricing-engine-plan-2-engine-api.md`
