"""graphrag_scaffold — US-RND-01-11 (Sprint 4).

Crea el outbox de CDC para la propagación Postgres → graph store y siembra
el permiso administrativo del endpoint `/api/v1/graphrag/replay`.

Cambios:

- Tabla ``cdc_events`` (BIGSERIAL, action+status checks, índice parcial
  ``status='pending'``) — outbox pattern para CDC.
- Trigger PL/pgSQL ``cdc_emit_product`` AFTER INSERT/UPDATE/DELETE en
  ``products`` que escribe a ``cdc_events`` con ``entity_type='product'``.
- Permiso ``graphrag:admin`` + asignación a roles ``ti_integracion`` y
  ``admin`` (role mismatch en migration 011 conserva el nomenclátor).
- TODO comentados para triggers en ``suppliers``, ``costs``,
  ``match_candidates`` — quedan diferidos hasta que el scaffold haya
  sido validado E2E (ver Fase 2 ADR-041).

Slot:
- Esta migración está reservada al agente E del Sprint 4.
- ``down_revision = '20260507_024'``: asume que las migraciones 021-024
  (en flight con otros agentes) ya están en main al rebasar. Si todavía
  no están al hacer ``alembic upgrade head``, ajustar localmente.

Revision ID: 20260507_025
Revises: 20260507_024
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260507_025"
down_revision: str | None = "20260507_024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- Tabla cdc_events --------------------------------------------------
    op.create_table(
        "cdc_events",
        sa.Column(
            "id",
            sa.BigInteger,
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column(
            "payload_jsonb",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('insert','update','delete')",
            name="ck_cdc_events_action",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processed','failed','dead_letter')",
            name="ck_cdc_events_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_cdc_events_attempts_nonneg"),
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cdc_events_pending
            ON cdc_events (id)
            WHERE status = 'pending';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cdc_events_entity
            ON cdc_events (entity_type, entity_id);
        """
    )

    # ----- Trigger function (productos) -------------------------------------
    # Construye el payload_jsonb con un subset de columnas (no enviamos
    # blobs como embeddings ni `specs` enteras — Fase 1 mínima).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cdc_emit_product()
        RETURNS TRIGGER AS $fn$
        DECLARE
            v_action TEXT;
            v_entity_id TEXT;
            v_payload JSONB;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_action := 'delete';
                v_entity_id := OLD.sku;
                v_payload := jsonb_build_object('sku', OLD.sku);
            ELSE
                IF TG_OP = 'INSERT' THEN
                    v_action := 'insert';
                ELSE
                    v_action := 'update';
                END IF;
                v_entity_id := NEW.sku;
                v_payload := jsonb_build_object(
                    'sku', NEW.sku,
                    'name_en', NEW.name_en,
                    'family', NEW.family,
                    'subfamily', NEW.subfamily,
                    'type', NEW.type,
                    'material', NEW.material,
                    'dn', NEW.dn,
                    'pn', NEW.pn,
                    'connection', NEW.connection,
                    'brand', NEW.brand,
                    'active', NEW.active
                );
            END IF;

            INSERT INTO cdc_events (entity_type, entity_id, action, payload_jsonb)
            VALUES ('product', v_entity_id, v_action, v_payload);

            -- LISTEN/NOTIFY hint para suscriptores futuros (Fase 2+,
            -- Supabase Realtime / Debezium consumirá vía WAL).
            PERFORM pg_notify('cdc_events', json_build_object(
                'entity_type', 'product',
                'entity_id', v_entity_id,
                'action', v_action
            )::text);

            RETURN COALESCE(NEW, OLD);
        END;
        $fn$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_cdc_emit_product ON products")
    op.execute(
        """
        CREATE TRIGGER trg_cdc_emit_product
            AFTER INSERT OR UPDATE OR DELETE ON products
            FOR EACH ROW
            EXECUTE FUNCTION cdc_emit_product();
        """
    )

    # ----- TODO Fase 2: triggers análogos ------------------------------------
    # NB (Fase 2 / US-RND-01-11 follow-up): replicar el patrón para:
    #   - suppliers          → entity_type='supplier'   (PK code)
    #   - costs              → entity_type='cost'        (PK id)
    #   - match_candidates   → entity_type='match_candidate' (PK id)
    # Cada trigger emite un payload JSONB mínimo (no incluye breakdown
    # ni specs blob). Documentar en ADR-041 la lista canónica de campos.

    # ----- Permiso graphrag:admin (seed RBAC) --------------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('graphrag:admin', 'Administrar GraphRAG (replay CDC, ver health avanzado)')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE p.code = 'graphrag:admin'
          AND r.code IN ('ti_integracion', 'admin')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE code = 'graphrag:admin'
        );
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'graphrag:admin'")

    op.execute("DROP TRIGGER IF EXISTS trg_cdc_emit_product ON products")
    op.execute("DROP FUNCTION IF EXISTS cdc_emit_product()")

    op.execute("DROP INDEX IF EXISTS idx_cdc_events_entity")
    op.execute("DROP INDEX IF EXISTS idx_cdc_events_pending")
    op.drop_table("cdc_events")
