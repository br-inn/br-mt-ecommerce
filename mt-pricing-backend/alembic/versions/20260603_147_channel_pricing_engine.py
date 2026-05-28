"""channel pricing engine: enums, product fields, 7 new tables

Revision ID: 20260603_147
Revises: 20260527_159
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260603_147"
down_revision = "20260527_159"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. PG enum types — MUST be created before any column that uses them ──
    op.execute("CREATE TYPE selling_model AS ENUM ('b2c', 'b2b')")
    op.execute(
        "CREATE TYPE fulfillment_scheme AS ENUM "
        "('canal_full', 'canal_lastmile', 'merchant_managed')"
    )
    op.execute("CREATE TYPE ceiling_basis AS ENUM ('catalog_pvp', 'margin_floor')")

    # ── 2. New columns on existing products table ────────────────────────
    op.add_column("products", sa.Column("pe_eur", sa.Numeric(14, 4), nullable=True))
    op.add_column("products", sa.Column("catalog_pvp_eur", sa.Numeric(14, 4), nullable=True))
    op.add_column("products", sa.Column(
        "units_per_box", sa.Integer(), nullable=False, server_default="1"
    ))
    op.add_column("products", sa.Column(
        "b2c_labeling_aed", sa.Numeric(10, 4), nullable=False, server_default="0"
    ))
    op.add_column("products", sa.Column(
        "ceiling_basis",
        postgresql.ENUM(name="ceiling_basis", create_type=False),
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
            postgresql.ENUM(name="fulfillment_scheme", create_type=False),
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
            postgresql.ENUM(name="fulfillment_scheme", create_type=False),
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
            postgresql.ENUM(name="selling_model", create_type=False),
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
            postgresql.ENUM(name="selling_model", create_type=False),
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
            postgresql.ENUM(name="selling_model", create_type=False),
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

    # ── 10. Lookup indexes ────────────────────────────────────────────────
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
    for col in ["ceiling_basis", "b2c_labeling_aed", "units_per_box",
                "catalog_pvp_eur", "pe_eur"]:
        op.drop_column("products", col)
    op.execute("DROP TYPE IF EXISTS ceiling_basis")
    op.execute("DROP TYPE IF EXISTS fulfillment_scheme")
    op.execute("DROP TYPE IF EXISTS selling_model")
