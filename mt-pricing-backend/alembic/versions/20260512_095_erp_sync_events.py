"""erp_sync_events — outbox pattern para eventos ERP salientes (US-INV-01-07).

Crea la tabla ``erp_sync_events`` que actúa como transactional outbox:
cada fila representa un evento a enviar al ERP externo (SAP, Odoo, etc.).
La Celery task ``mt.erp.push_erp_event`` la procesa de forma asíncrona.

Índices:
- ``idx_erp_sync_pending``: partial WHERE ``status = 'pending'`` — acelera
  el polling de la task worker.
- ``idx_erp_sync_entity``: ``(entity_id, event_type)`` — auditoría y dedup.

Revision ID: 095
Revises: 094
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "095"
down_revision = "094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "erp_sync_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "adapter",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'noop'"),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_ref", sa.String(256), nullable=True),
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
            "status IN ('pending','delivered','failed','skipped')",
            name="ck_erp_sync_status",
        ),
    )

    # Partial index — sólo filas pendientes de envío
    op.create_index(
        "idx_erp_sync_pending",
        "erp_sync_events",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Compuesto — auditoría por entidad + tipo
    op.create_index(
        "idx_erp_sync_entity",
        "erp_sync_events",
        ["entity_id", "event_type"],
    )

    # Trigger updated_at automático
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_erp_sync_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_erp_sync_updated_at
            BEFORE UPDATE ON erp_sync_events
            FOR EACH ROW EXECUTE FUNCTION set_erp_sync_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_erp_sync_updated_at ON erp_sync_events;")
    op.execute("DROP FUNCTION IF EXISTS set_erp_sync_updated_at();")
    op.drop_index("idx_erp_sync_entity", table_name="erp_sync_events")
    op.drop_index("idx_erp_sync_pending", table_name="erp_sync_events")
    op.drop_table("erp_sync_events")
