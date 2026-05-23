"""price_history_raw + price_daily_stats + competitor_brands.monitoring_active (US-SCR-04-01/03).

Revision ID: 20260601_134
Revises: 20260531_133
Create Date: 2026-06-01

Tablas:
- ``price_history_raw`` — historial de precios scrapeados por (match_id, marketplace).
  Particionada por rango en ``scraped_at::date`` (fallback si no hay TimescaleDB).
- ``price_daily_stats`` — vista materializada con estadísticas diarias por dominio.
- ALTER competitor_brands ADD COLUMN monitoring_active BOOLEAN (US-SCR-04-03).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260601_134"
down_revision = "20260531_133"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # price_history_raw — tabla particionada por RANGE(scraped_at)
    # Usa particionamiento nativo PG (fallback si no hay TimescaleDB)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS price_history_raw (
            id          UUID        NOT NULL DEFAULT gen_random_uuid(),
            match_id    UUID        REFERENCES match_candidates(id) ON DELETE SET NULL,
            marketplace VARCHAR(32) NOT NULL,
            price_aed   NUMERIC(14,4) NOT NULL,
            currency    VARCHAR(3)  NOT NULL DEFAULT 'AED',
            scraped_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            sku         TEXT,
            source_url  TEXT,
            raw_payload JSONB       NOT NULL DEFAULT '{}'::jsonb
        ) PARTITION BY RANGE (scraped_at)
    """)

    # Partición por defecto que captura todo el rango 2026 en adelante
    op.execute("""
        CREATE TABLE IF NOT EXISTS price_history_raw_2026
            PARTITION OF price_history_raw
            FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')
    """)

    # Partición 2027 para que las filas futuras no queden en vacío
    op.execute("""
        CREATE TABLE IF NOT EXISTS price_history_raw_2027
            PARTITION OF price_history_raw
            FOR VALUES FROM ('2027-01-01') TO ('2028-01-01')
    """)

    # Índices temporales (creados en la tabla padre — propagan a particiones)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_price_history_raw_scraped_at
            ON price_history_raw (scraped_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_price_history_raw_match_marketplace
            ON price_history_raw (match_id, marketplace, scraped_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_price_history_raw_sku
            ON price_history_raw (sku, scraped_at DESC)
        WHERE sku IS NOT NULL
    """)

    # ------------------------------------------------------------------
    # price_daily_stats — vista materializada con min/max/avg/close diario
    # ------------------------------------------------------------------
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS price_daily_stats AS
        SELECT
            match_id,
            marketplace,
            DATE(scraped_at AT TIME ZONE 'UTC') AS stat_date,
            COUNT(*)                            AS sample_count,
            MIN(price_aed)                      AS price_min,
            MAX(price_aed)                      AS price_max,
            ROUND(AVG(price_aed), 4)            AS price_avg,
            -- close = último precio del día (mayor scraped_at)
            (
                ARRAY_AGG(price_aed ORDER BY scraped_at DESC)
            )[1]                                AS price_close,
            MIN(scraped_at)                     AS first_scraped_at,
            MAX(scraped_at)                     AS last_scraped_at
        FROM price_history_raw
        GROUP BY match_id, marketplace, DATE(scraped_at AT TIME ZONE 'UTC')
        WITH NO DATA
    """)

    # Índices en la vista materializada
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uix_price_daily_stats_key
            ON price_daily_stats (match_id, marketplace, stat_date)
        WHERE match_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_price_daily_stats_date
            ON price_daily_stats (stat_date DESC)
    """)

    # ------------------------------------------------------------------
    # competitor_brands.monitoring_active — US-SCR-04-03
    # ------------------------------------------------------------------
    op.add_column(
        "competitor_brands",
        sa.Column(
            "monitoring_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ------------------------------------------------------------------
    # job_definitions seed — refresh_price_daily_stats (cada hora)
    # ------------------------------------------------------------------
    op.execute("""
        INSERT INTO job_definitions (code, task_name, description, owner, schedule_type, cron_expression, enabled)
        VALUES (
            'refresh_price_daily_stats',
            'mt.scraper.refresh_price_daily_stats',
            'Refresca la vista materializada price_daily_stats con datos de la última hora.',
            'infra',
            'cron',
            '0 * * * *',
            true
        )
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'refresh_price_daily_stats'")
    op.drop_column("competitor_brands", "monitoring_active")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS price_daily_stats")
    op.execute("DROP TABLE IF EXISTS price_history_raw_2027")
    op.execute("DROP TABLE IF EXISTS price_history_raw_2026")
    op.execute("DROP TABLE IF EXISTS price_history_raw")
