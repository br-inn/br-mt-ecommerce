"""scraper_job_definition — seed job_definitions para scraping semanal Amazon UAE.

Data-only migration: registra ``weekly_amazon_uae_scrape`` en ``job_definitions``
para que DatabaseScheduler dispare ``mt.scraper.scrape_batch`` cada lunes a
las 02:00 Asia/Dubai (queue ``comparator``).

El job se crea con ``enabled = false`` — se activa explícitamente togglando
el feature flag ``live_scraper_amazon_uae`` desde el panel de admin.

ADR-046 (DatabaseScheduler — beat config).
EP-SCR-01 (Scraper Amazon UAE).

Revision ID: 20260513_111
Revises: 20260528_120
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_111"
down_revision: str | None = "20260528_120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_CODE = "weekly_amazon_uae_scrape"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO job_definitions
            (code, task_name, description, owner,
             schedule_type, cron_expression, timezone, queue,
             enabled, args, kwargs)
        VALUES
            ('{_JOB_CODE}',
             'mt.scraper.scrape_batch',
             'Scraping semanal de todos los productos activos en Amazon UAE (EP-SCR-01)',
             'business',
             'cron',
             '0 2 * * 1',
             'Asia/Dubai',
             'comparator',
             false,
             '[]'::jsonb,
             '{{"force": false}}'::jsonb)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM job_definitions WHERE code = '{_JOB_CODE}';")
