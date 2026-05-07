"""channel_listings + channel_sync_events — Sprint 3 Channel Mirror.

Crea las tablas que persisten el estado del mirror MT canonical ↔ canales
externos (Amazon UAE, Noon UAE) y el log append-only de eventos sync
(pull / push / diff).

Refs:
- US Sprint 3 Channel Mirror foundation.
- mt-pricing-frontend/app/(app)/canales/amazon-uae/page.tsx (mockup que
  define el contrato de campos).

Revision ID: 20260507_015
Revises: 20260507_014
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507_015"
down_revision: str | None = "20260507_014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- channel_listings -----
    op.create_table(
        "channel_listings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_code", sa.String(64), nullable=False),
        sa.Column(
            "external_id",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "buybox_state",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column("buybox_pct_7d", sa.Numeric(5, 4), nullable=True),
        sa.Column("stock_qty", sa.Integer(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("reviews_count", sa.Integer(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "canonical_snapshot_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "live_snapshot_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "diff_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "channel_code", "external_id", name="uq_channel_listings_channel_external"
        ),
        sa.UniqueConstraint(
            "channel_code", "product_sku", name="uq_channel_listings_channel_sku"
        ),
        sa.CheckConstraint(
            "buybox_state IN ('own','competitor','none')",
            name="ck_channel_listings_buybox_state",
        ),
    )
    op.create_index(
        "idx_channel_listings_lookup",
        "channel_listings",
        ["channel_code", "product_sku"],
    )
    op.create_index(
        "idx_channel_listings_last_sync",
        "channel_listings",
        ["channel_code", "last_sync_at"],
    )
    op.create_index(
        "ix_channel_listings_product_sku", "channel_listings", ["product_sku"]
    )
    op.create_index(
        "ix_channel_listings_channel_code", "channel_listings", ["channel_code"]
    )
    op.execute(
        "CREATE TRIGGER trg_channel_listings_updated_at "
        "BEFORE UPDATE ON channel_listings "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- channel_sync_events -----
    op.create_table(
        "channel_sync_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("channel_code", sa.String(64), nullable=False),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column(
            "ok",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "payload_jsonb",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "event_type IN ('pull','push','diff')",
            name="ck_channel_sync_events_event_type",
        ),
    )
    op.create_index(
        "idx_channel_sync_events_recent",
        "channel_sync_events",
        ["channel_code", "created_at"],
    )
    op.create_index(
        "ix_channel_sync_events_channel_code",
        "channel_sync_events",
        ["channel_code"],
    )
    op.create_index(
        "ix_channel_sync_events_product_sku",
        "channel_sync_events",
        ["product_sku"],
    )

    # ----- RLS policies (idempotente — solo si rol mt_app existe) -----
    op.execute(
        """
        DO $rls$
        DECLARE
            mt_app_exists BOOLEAN;
        BEGIN
            SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') INTO mt_app_exists;
            IF mt_app_exists THEN
                EXECUTE 'ALTER TABLE channel_listings     ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE channel_sync_events  ENABLE ROW LEVEL SECURITY';

                EXECUTE 'CREATE POLICY channel_listings_read_all ON channel_listings '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY channel_listings_ti_write ON channel_listings '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY channel_sync_events_read_all ON channel_sync_events '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY channel_sync_events_insert ON channel_sync_events '
                     || 'FOR INSERT TO mt_app '
                     || 'WITH CHECK (auth.uid() IS NOT NULL)';
            END IF;
        END
        $rls$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS channel_sync_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS channel_listings CASCADE;")
