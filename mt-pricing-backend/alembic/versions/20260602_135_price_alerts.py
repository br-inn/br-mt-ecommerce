"""price_alerts + scraper_heartbeat job seed (US-SCR-04-05).

Revision ID: 20260602_135
Revises: 20260601_134
Create Date: 2026-06-02

Tablas:
- ``price_alerts`` — alertas de variación de precio detectadas por price_monitor_task.
  Incluye canal pg_notify ``price_alert`` al INSERT.
- job_definitions seed para ``send_price_alert_emails`` (cada 5 min) y
  ``scraper_heartbeat`` (cada 26h).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260602_135"
down_revision = "20260601_134"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # price_alerts — registra cada disparo de alerta de precio
    # ------------------------------------------------------------------
    op.create_table(
        "price_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("match_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column(
            "alert_type",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'price_variation'"),
        ),
        sa.Column("threshold_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("prev_price_aed", sa.Numeric(14, 4), nullable=True),
        sa.Column("current_price_aed", sa.Numeric(14, 4), nullable=True),
        sa.Column("variation_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "channel",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'email'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_price_alerts_triggered_at",
        "price_alerts",
        ["triggered_at"],
        postgresql_using="brin",
    )
    op.create_index(
        "ix_price_alerts_notified_at",
        "price_alerts",
        ["notified_at"],
        postgresql_where=sa.text("notified_at IS NULL"),
    )
    op.create_index(
        "ix_price_alerts_match_id",
        "price_alerts",
        ["match_id"],
    )

    # ------------------------------------------------------------------
    # pg_notify trigger — emite notificación en canal price_alert al INSERT
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_price_alert()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify(
                'price_alert',
                json_build_object(
                    'id',          NEW.id,
                    'sku',         NEW.sku,
                    'marketplace', NEW.marketplace,
                    'alert_type',  NEW.alert_type,
                    'variation_pct', NEW.variation_pct
                )::text
            );
            RETURN NEW;
        END;
        $$
    """)

    op.execute("""
        CREATE TRIGGER trg_price_alert_notify
        AFTER INSERT ON price_alerts
        FOR EACH ROW EXECUTE FUNCTION notify_price_alert()
    """)

    # ------------------------------------------------------------------
    # job_definitions seed — send_price_alert_emails + scraper_heartbeat
    # ------------------------------------------------------------------
    op.execute("""
        INSERT INTO job_definitions (code, task_name, description, owner, schedule_type, cron_expression, enabled)
        VALUES
        (
            'send_price_alert_emails',
            'mt.scraper.send_price_alert_emails',
            'Envía emails via SendGrid para alertas de precio sin notificar (notified_at IS NULL).',
            'infra',
            'cron',
            '*/5 * * * *',
            true
        ),
        (
            'scraper_heartbeat',
            'mt.scraper.scraper_heartbeat',
            'Heartbeat del scraper — actualiza last_run_at en job_definitions cada 26h.',
            'infra',
            'cron',
            '0 */26 * * *',
            true
        )
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute(
        "DELETE FROM job_definitions WHERE code IN ('send_price_alert_emails', 'scraper_heartbeat')"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_price_alert_notify ON price_alerts")
    op.execute("DROP FUNCTION IF EXISTS notify_price_alert()")
    op.drop_index("ix_price_alerts_match_id", table_name="price_alerts")
    op.drop_index("ix_price_alerts_notified_at", table_name="price_alerts")
    op.drop_index("ix_price_alerts_triggered_at", table_name="price_alerts")
    op.drop_table("price_alerts")
