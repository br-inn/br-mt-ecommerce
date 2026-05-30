"""F1 provenance + audit: provenance columns, source_observations, source_health

Revision ID: 20260603_148
Revises: 20260603_147
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260603_148"
down_revision = "20260603_147"
branch_labels = None
depends_on = None

# Tables receiving the full provenance column set. The first 4 only have
# updated_at/updated_by today; channel_margin_overrides has created_at/created_by.
_PROVENANCE_TABLES = (
    "trade_route_params",
    "channel_fee_params",
    "channel_margin_targets",
    "channel_product_logistics",
    "channel_margin_overrides",
)

# The 4 tables that only have updated_* and therefore also need created_*.
_NEEDS_CREATED = (
    "trade_route_params",
    "channel_fee_params",
    "channel_margin_targets",
    "channel_product_logistics",
)

# TEXT -> uuid conversions: (table, column).
_UUID_CONVERSIONS = (
    ("trade_route_params", "updated_by"),
    ("channel_fee_params", "updated_by"),
    ("channel_margin_targets", "updated_by"),
    ("channel_product_logistics", "updated_by"),
    ("channel_margin_overrides", "created_by"),
    ("pricing_scenarios", "created_by"),
)

_SOURCE_OP_VALUES = (
    "compras_po",
    "importacion_dua",
    "tesoreria_fx",
    "master_canal",
    "vendor_price_list",
    "settlement_amazon",
    "settlement_noon",
    "contabilidad_analitica",
    "master_fiscal",
    "marketing_budget",
    "postventa_rma",
    "master_comercial",
    "decision_local",
    "manual",
)

_SNAPSHOT_KIND_VALUES = (
    "manual_a",
    "manual_b",
    "auto_pre_optimization",
    "auto_pre_import",
    "auto_pre_bulk_margin_change",
    "auto_pre_sync_param",
)

# source_op -> freshness SLA in minutes for the seeded source_health rows.
_SLA_MINUTES = {
    "tesoreria_fx": 1440,
    "master_canal": 1440,
    "vendor_price_list": 129600,
    "compras_po": 129600,
    "importacion_dua": 129600,
    "settlement_amazon": 86400,
    "settlement_noon": 86400,
    "contabilidad_analitica": 86400,
    "master_fiscal": 525600,
    "marketing_budget": 86400,
    "postventa_rma": 129600,
    "master_comercial": 129600,
    "decision_local": 525600,
    "manual": 525600,
}


def upgrade() -> None:
    # ── 1. PG enum types ─────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE source_op AS ENUM (" + ", ".join(f"'{v}'" for v in _SOURCE_OP_VALUES) + ")"
    )
    op.execute(
        "CREATE TYPE snapshot_kind AS ENUM ("
        + ", ".join(f"'{v}'" for v in _SNAPSHOT_KIND_VALUES)
        + ")"
    )

    # ── 2. Provenance columns on the 5 tables ────────────────────────────
    for tbl in _PROVENANCE_TABLES:
        op.add_column(
            tbl,
            sa.Column(
                "source_op",
                postgresql.ENUM(name="source_op", create_type=False),
                nullable=False,
                server_default="manual",
            ),
        )
        op.add_column(tbl, sa.Column("source_ref", sa.Text(), nullable=True))
        op.add_column(tbl, sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=True))
        op.add_column(tbl, sa.Column("valid_until", sa.TIMESTAMP(timezone=True), nullable=True))
        op.add_column(tbl, sa.Column("override_by", postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column(tbl, sa.Column("override_reason", sa.Text(), nullable=True))
        op.create_foreign_key(
            f"fk_{tbl}_override_by",
            tbl,
            "users",
            ["override_by"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_check_constraint(
            f"ck_{tbl}_override_reason",
            tbl,
            "override_by IS NULL OR override_reason IS NOT NULL",
        )

    # ── 2b. created_* for the 4 tables that only have updated_* ──────────
    for tbl in _NEEDS_CREATED:
        op.add_column(
            tbl,
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.add_column(tbl, sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{tbl}_created_by",
            tbl,
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )

    # ── 3. TEXT -> uuid conversions (all values are 100% NULL) ───────────
    for tbl, col in _UUID_CONVERSIONS:
        op.execute(f"ALTER TABLE {tbl} ALTER COLUMN {col} TYPE uuid USING {col}::uuid")
        op.create_foreign_key(
            f"fk_{tbl}_{col}",
            tbl,
            "users",
            [col],
            ["id"],
            ondelete="SET NULL",
        )

    # ── 4. source_observations ───────────────────────────────────────────
    op.create_table(
        "source_observations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_op",
            postgresql.ENUM(name="source_op", create_type=False),
            nullable=False,
        ),
        sa.Column("target_table", sa.Text(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_field", sa.Text(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("value_numeric", sa.Numeric(18, 8), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["channels.id"], name="fk_source_observations_channel"
        ),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"], name="fk_source_observations_sku"),
    )
    op.create_index(
        "idx_source_obs_lookup",
        "source_observations",
        ["target_table", "target_field", "sku", sa.text("observed_at DESC")],
    )
    op.create_index(
        "idx_source_obs_channel",
        "source_observations",
        ["channel_id", "source_op", sa.text("observed_at DESC")],
    )

    # ── 5. source_health (+ seed one row per source_op) ──────────────────
    op.create_table(
        "source_health",
        sa.Column(
            "source_op",
            postgresql.ENUM(name="source_op", create_type=False),
            primary_key=True,
        ),
        sa.Column("last_sync_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_sync_success_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "freshness_sla_minutes",
            sa.Integer(),
            nullable=False,
            server_default="1440",
        ),
        sa.Column("rows_last_sync", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    values = ", ".join(f"('{op_name}', {_SLA_MINUTES[op_name]})" for op_name in _SOURCE_OP_VALUES)
    op.execute("INSERT INTO source_health (source_op, freshness_sla_minutes) VALUES " + values)

    # ── 6. pricing_scenarios extension ───────────────────────────────────
    op.add_column(
        "pricing_scenarios",
        sa.Column(
            "kind",
            postgresql.ENUM(name="snapshot_kind", create_type=False),
            nullable=False,
            server_default="manual_a",
        ),
    )
    op.add_column(
        "pricing_scenarios",
        sa.Column("retention_until", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute("UPDATE pricing_scenarios SET kind = 'manual_a' WHERE slot = 'A'")
    op.execute("UPDATE pricing_scenarios SET kind = 'manual_b' WHERE slot = 'B'")

    op.drop_constraint("uq_pricing_scenarios_slot", "pricing_scenarios", type_="unique")
    op.create_index(
        "uq_pricing_scenarios_manual",
        "pricing_scenarios",
        ["channel_id", "selling_model", "slot"],
        unique=True,
        postgresql_where=sa.text("kind IN ('manual_a','manual_b')"),
    )
    op.create_index(
        "idx_pricing_scenarios_retention",
        "pricing_scenarios",
        ["retention_until"],
        postgresql_where=sa.text("retention_until IS NOT NULL"),
    )


def downgrade() -> None:
    # ── 6. pricing_scenarios extension ───────────────────────────────────
    op.drop_index("idx_pricing_scenarios_retention", "pricing_scenarios")
    op.drop_index("uq_pricing_scenarios_manual", "pricing_scenarios")
    op.create_unique_constraint(
        "uq_pricing_scenarios_slot",
        "pricing_scenarios",
        ["channel_id", "selling_model", "slot"],
    )
    op.drop_column("pricing_scenarios", "retention_until")
    op.drop_column("pricing_scenarios", "kind")

    # ── 5. source_health ─────────────────────────────────────────────────
    op.drop_table("source_health")

    # ── 4. source_observations ───────────────────────────────────────────
    op.drop_index("idx_source_obs_channel", "source_observations")
    op.drop_index("idx_source_obs_lookup", "source_observations")
    op.drop_table("source_observations")

    # ── 3. uuid -> TEXT conversions ──────────────────────────────────────
    for tbl, col in _UUID_CONVERSIONS:
        op.drop_constraint(f"fk_{tbl}_{col}", tbl, type_="foreignkey")
        op.execute(f"ALTER TABLE {tbl} ALTER COLUMN {col} TYPE text USING {col}::text")

    # ── 2b. created_* on the 4 tables ────────────────────────────────────
    for tbl in _NEEDS_CREATED:
        op.drop_constraint(f"fk_{tbl}_created_by", tbl, type_="foreignkey")
        op.drop_column(tbl, "created_by")
        op.drop_column(tbl, "created_at")

    # ── 2. Provenance columns on the 5 tables ────────────────────────────
    for tbl in _PROVENANCE_TABLES:
        op.drop_constraint(f"ck_{tbl}_override_reason", tbl, type_="check")
        op.drop_constraint(f"fk_{tbl}_override_by", tbl, type_="foreignkey")
        op.drop_column(tbl, "override_reason")
        op.drop_column(tbl, "override_by")
        op.drop_column(tbl, "valid_until")
        op.drop_column(tbl, "observed_at")
        op.drop_column(tbl, "source_ref")
        op.drop_column(tbl, "source_op")

    # ── 1. enums last ─────────────────────────────────────────────────────
    op.execute("DROP TYPE IF EXISTS snapshot_kind")
    op.execute("DROP TYPE IF EXISTS source_op")
