"""fefo_replenishment_abc_kpis — US-ERP-02-05/06/07/08.

Tablas nuevas:
  - expiry_alert_thresholds   (US-ERP-02-05 — threshold por producto)
  - inventory_alerts          (US-ERP-02-05 — alertas LOT_EXPIRY_WARNING)
  - replenishment_params      (US-ERP-02-06 — ROP/safety-stock)
  - product_abc_classifications (US-ERP-02-07)
  - cycle_count_schedules     (US-ERP-02-07)

JobDefinition seeds:
  - lot_expiry_check          cron 0 6 * * *
  - rop_daily_check           cron 0 7 * * *
  - abc_monthly_classification cron 0 2 1 * *

Revision ID: 20260522_110
Revises: 20260517_109
Create Date: 2026-05-22
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "20260522_110"
down_revision: str = "20260517_109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # US-ERP-02-05: expiry alert thresholds
    # ------------------------------------------------------------------
    op.create_table(
        "expiry_alert_thresholds",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_sku", sa.Text, sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("threshold_days", sa.Integer, nullable=False, server_default=sa.text("30")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_eat_sku", "expiry_alert_thresholds", ["product_sku"])

    # ------------------------------------------------------------------
    # US-ERP-02-05: inventory alerts
    # ------------------------------------------------------------------
    op.create_table(
        "inventory_alerts",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("alert_type", sa.Text, nullable=False),
        sa.Column("product_sku", sa.Text, sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_lots.id", ondelete="CASCADE"), nullable=True),
        sa.Column("warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("severity", sa.Text, nullable=False, server_default=sa.text("'warning'")),
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("alert_type IN ('LOT_EXPIRY_WARNING','STOCKOUT','ROP_BREACH')", name="ck_inv_alert_type"),
        sa.CheckConstraint("severity IN ('info','warning','critical')", name="ck_inv_alert_severity"),
    )
    op.create_index("idx_inv_alerts_sku", "inventory_alerts", ["product_sku"])
    op.create_index("idx_inv_alerts_type", "inventory_alerts", ["alert_type"])
    op.create_index("idx_inv_alerts_unresolved", "inventory_alerts", ["resolved_at"],
                    postgresql_where=sa.text("resolved_at IS NULL"))

    # ------------------------------------------------------------------
    # US-ERP-02-06: replenishment_params
    # ------------------------------------------------------------------
    op.create_table(
        "replenishment_params",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_sku", sa.Text, sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reorder_point", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("safety_stock", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("reorder_qty", sa.Numeric(12, 3), nullable=False, server_default=sa.text("1")),
        sa.Column("lead_time_days", sa.Integer, nullable=False, server_default=sa.text("7")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("product_sku", "warehouse_id", name="uq_replenishment_params_sku_wh"),
        sa.CheckConstraint("reorder_point >= 0", name="ck_rp_reorder_point_nonneg"),
        sa.CheckConstraint("safety_stock >= 0", name="ck_rp_safety_stock_nonneg"),
        sa.CheckConstraint("reorder_qty > 0", name="ck_rp_reorder_qty_pos"),
        sa.CheckConstraint("lead_time_days >= 0", name="ck_rp_lead_time_nonneg"),
    )
    op.create_index("idx_rp_sku", "replenishment_params", ["product_sku"])
    op.create_index("idx_rp_warehouse", "replenishment_params", ["warehouse_id"])
    op.create_index("idx_rp_active", "replenishment_params", ["is_active"],
                    postgresql_where=sa.text("is_active = true"))

    # ------------------------------------------------------------------
    # US-ERP-02-07: product_abc_classifications
    # ------------------------------------------------------------------
    op.create_table(
        "product_abc_classifications",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_sku", sa.Text, sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("abc_class", sa.Text, nullable=False),
        sa.Column("annual_consumption_value", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("pct_of_total", sa.Numeric(7, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("product_sku", "warehouse_id", name="uq_abc_sku_wh"),
        sa.CheckConstraint("abc_class IN ('A','B','C')", name="ck_abc_class"),
        sa.CheckConstraint("annual_consumption_value >= 0", name="ck_abc_value_nonneg"),
        sa.CheckConstraint("pct_of_total >= 0 AND pct_of_total <= 100", name="ck_abc_pct_range"),
    )
    op.create_index("idx_abc_sku", "product_abc_classifications", ["product_sku"])
    op.create_index("idx_abc_warehouse", "product_abc_classifications", ["warehouse_id"])
    op.create_index("idx_abc_class", "product_abc_classifications", ["abc_class"])

    # ------------------------------------------------------------------
    # US-ERP-02-07: cycle_count_schedules
    # ------------------------------------------------------------------
    op.create_table(
        "cycle_count_schedules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("warehouse_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("abc_class", sa.Text, nullable=False),
        sa.Column("frequency_days", sa.Integer, nullable=False),
        sa.Column("next_count_date", sa.Date, nullable=True),
        sa.Column("last_count_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("abc_class IN ('A','B','C')", name="ck_ccs_abc_class"),
        sa.CheckConstraint("frequency_days > 0", name="ck_ccs_frequency_pos"),
    )
    op.create_index("idx_ccs_warehouse", "cycle_count_schedules", ["warehouse_id"])
    op.create_index("idx_ccs_active", "cycle_count_schedules", ["is_active"],
                    postgresql_where=sa.text("is_active = true"))

    # ------------------------------------------------------------------
    # JobDefinition seeds — US-ERP-02-05/06/07
    # ------------------------------------------------------------------
    op.execute(sa.text("""
        INSERT INTO job_definitions (id, code, task_name, description, owner, schedule_type, cron_expression, enabled, created_at, updated_at)
        VALUES
          (gen_random_uuid(), 'lot_expiry_check',
           'mt.inventory.check_lot_expiry_warnings',
           'Detectar lotes próximos a vencer y crear alertas LOT_EXPIRY_WARNING',
           'business', 'cron', '0 6 * * *', true, now(), now()),
          (gen_random_uuid(), 'rop_daily_check',
           'mt.inventory.run_rop_check',
           'ROP diario: crear PurchaseRequisitions automáticas cuando qty <= reorder_point',
           'business', 'cron', '0 7 * * *', true, now(), now()),
          (gen_random_uuid(), 'abc_monthly_classification',
           'mt.inventory.run_abc_classification',
           'Clasificación ABC mensual por valor de consumo anual',
           'business', 'cron', '0 2 1 * *', true, now(), now())
        ON CONFLICT (code) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM job_definitions WHERE code IN "
            "('lot_expiry_check','rop_daily_check','abc_monthly_classification')"
        )
    )
    op.drop_table("cycle_count_schedules")
    op.drop_table("product_abc_classifications")
    op.drop_table("replenishment_params")
    op.drop_table("inventory_alerts")
    op.drop_table("expiry_alert_thresholds")
