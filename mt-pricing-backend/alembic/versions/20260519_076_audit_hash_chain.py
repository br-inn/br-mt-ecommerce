"""audit_hash_chain — hash chain tamper-evident en audit_events (R-005 / ADR-076).

Agrega:
- Tabla ``audit_hash_state`` (singleton, fila única): persiste el último hash
  del chain para evitar un full-scan de la partición al insertar.
- Tabla ``audit_chain_signatures``: firma HMAC-SHA256 diaria del último hash
  (generada por el job ``audit.nightly_integrity_check``).
- Función PL/pgSQL ``compute_audit_hash()``: calcula y encadena hashes via
  ``sha256()`` de Postgres (disponible desde PG 11).
- Trigger ``trg_audit_hash_before_insert`` BEFORE INSERT sobre ``audit_events``.
- REVOKE UPDATE/DELETE sobre ``audit_events`` desde ``mt_app`` (append-only).

Revision ID: 076
Revises: 075
Create Date: 2026-05-19
"""

from __future__ import annotations

from alembic import op

revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Tabla singleton — estado del chain (evita scan de partición)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_hash_state (
            id          INTEGER PRIMARY KEY DEFAULT 1,
            last_event_id BIGINT,
            last_hash   VARCHAR(64) NOT NULL DEFAULT '',
            updated_at  TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT audit_hash_state_singleton CHECK (id = 1)
        );
        """
    )
    op.execute(
        """
        INSERT INTO audit_hash_state (id, last_hash)
        VALUES (1, '')
        ON CONFLICT (id) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 2. Tabla de firmas diarias
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_chain_signatures (
            id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            signed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            range_start    TIMESTAMPTZ NOT NULL,
            range_end      TIMESTAMPTZ NOT NULL,
            last_hash      VARCHAR(64) NOT NULL,
            signature      TEXT        NOT NULL,
            rows_verified  INTEGER     NOT NULL,
            tampered_count INTEGER     NOT NULL DEFAULT 0,
            passed         BOOLEAN     NOT NULL
        );
        """
    )

    # ------------------------------------------------------------------
    # 3. Función PL/pgSQL que calcula el hash chain
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION compute_audit_hash() RETURNS TRIGGER AS $$
        DECLARE
            prev_h    TEXT;
            row_data  TEXT;
        BEGIN
            -- Lock la fila única para serializar inserts concurrentes
            SELECT last_hash INTO prev_h
            FROM audit_hash_state WHERE id = 1 FOR UPDATE;

            row_data := COALESCE(NEW.id::TEXT, '')          ||
                        COALESCE(NEW.event_at::TEXT, '')     ||
                        COALESCE(NEW.actor_id::TEXT, '')     ||
                        COALESCE(NEW.entity_type, '')        ||
                        COALESCE(NEW.entity_id, '')          ||
                        COALESCE(NEW.action, '')             ||
                        COALESCE(NEW.payload_diff::TEXT, '{}') ||
                        COALESCE(prev_h, '');

            NEW.prev_hash    := COALESCE(prev_h, '');
            NEW.current_hash := encode(sha256(row_data::bytea), 'hex');

            UPDATE audit_hash_state
            SET last_event_id = NEW.id,
                last_hash     = NEW.current_hash,
                updated_at    = now()
            WHERE id = 1;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
    )

    # ------------------------------------------------------------------
    # 4. Trigger BEFORE INSERT sobre la tabla particionada
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TRIGGER trg_audit_hash_before_insert
            BEFORE INSERT ON audit_events
            FOR EACH ROW EXECUTE FUNCTION compute_audit_hash();
        """
    )

    # ------------------------------------------------------------------
    # 5. REVOKE UPDATE/DELETE — append-only enforcement
    #    Envuelto en DO/EXCEPTION por si mt_app no existe en dev local.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            REVOKE UPDATE, DELETE ON audit_events FROM mt_app;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC;
        """
    )


def downgrade() -> None:
    # Restaurar permisos antes de destruir objetos
    op.execute(
        """
        DO $$ BEGIN
            GRANT UPDATE, DELETE ON audit_events TO mt_app;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        GRANT UPDATE, DELETE ON audit_events TO PUBLIC;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_audit_hash_before_insert ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS compute_audit_hash();")
    op.execute("DROP TABLE IF EXISTS audit_chain_signatures;")
    op.execute("DROP TABLE IF EXISTS audit_hash_state;")
