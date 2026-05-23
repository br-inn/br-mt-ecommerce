"""pricing_engine_v51 — US-1B-01-02 + US-1B-01-03 (Sprint 4).

Cambios DDL:

- ``prices``:
    * Refuerza CHECK constraint del INSERT inicial: sólo ``draft`` o
      ``auto_approved`` válidos como estados iniciales (trigger
      ``prices_initial_status_trg`` BEFORE INSERT).
    * Añade trigger ``prices_state_machine_trg`` BEFORE UPDATE — valida
      transiciones contra la tabla ``price_state_transitions`` (mantiene
      el contrato canónico SQL aún si el cliente no pasa por el FSM
      Python).
    * Añade UNIQUE parcial: 1 sola fila ``approved`` por (sku, channel_id,
      scheme_code).

- ``price_state_transitions`` (NUEVA):
    * Tabla declarativa de transiciones legales — duplica el contrato del
      ``app.services.pricing.state_machine.ALLOWED_TRANSITIONS`` para
      enforcement BD-side.

- ``pricing_golden_tiers`` (NUEVA):
    * Configuración de tiers de bundling psicológico v5.1 (firmados por
      Paula). Permite al motor leer rules sin recompilar — soporta
      override en runtime.

NOTA — slot 021 reservado al backend pricing engine v51 agente.
``down_revision="20260507_020"`` para mantener cadena monotónica con la
migración de translation_workflow.

Revision ID: 20260507_021
Revises: 20260507_020
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260507_021"
down_revision: str | None = "20260507_020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Lista canónica de transitions legales — refleja
# `app.services.pricing.state_machine.ALLOWED_TRANSITIONS`.
_TRANSITIONS: tuple[tuple[str, str], ...] = (
    ("draft", "auto_approved"),
    ("draft", "pending_review"),
    ("draft", "rejected"),
    ("auto_approved", "approved"),
    ("auto_approved", "exported"),
    ("auto_approved", "revised"),
    ("pending_review", "approved"),
    ("pending_review", "rejected"),
    ("pending_review", "revised"),
    ("approved", "exported"),
    ("approved", "revised"),
    ("rejected", "draft"),
    ("revised", "pending_review"),
    ("revised", "rejected"),
    ("migrated", "approved"),
    ("migrated", "rejected"),
)

_VALID_INITIAL_STATUSES: tuple[str, ...] = ("draft", "auto_approved")

_GOLDEN_TIERS = (
    # name, upper_bound_aed, endings_csv, modulus, tolerance
    ("tier_1_small", "10.00", "0.49,0.99", None, "0.30"),
    ("tier_2_medium", "100.00", "0.95,0.99", None, "0.30"),
    ("tier_3_large", "1000.00", "0.95,0.99", "5.00", "0.50"),
    ("tier_4_xlarge", "999999999.00", "0.99", "10.00", "2.00"),
)


def upgrade() -> None:
    # ---------- price_state_transitions ----------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS price_state_transitions (
            from_status TEXT NOT NULL,
            to_status   TEXT NOT NULL,
            PRIMARY KEY (from_status, to_status)
        )
        """
    )
    # Re-seed defensive: vaciamos y re-insertamos la lista canónica.
    op.execute("DELETE FROM price_state_transitions")
    for f, t in _TRANSITIONS:
        op.execute(
            sa.text(
                "INSERT INTO price_state_transitions (from_status, to_status) "
                "VALUES (:f, :t) ON CONFLICT DO NOTHING"
            ).bindparams(f=f, t=t)
        )

    # ---------- pricing_golden_tiers ----------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_golden_tiers (
            name          TEXT PRIMARY KEY,
            upper_bound   NUMERIC(18, 4) NOT NULL,
            endings       TEXT NOT NULL,
            modulus       NUMERIC(18, 4) NULL,
            tolerance     NUMERIC(18, 4) NOT NULL,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("DELETE FROM pricing_golden_tiers")
    for name, ub, endings, modulus, tol in _GOLDEN_TIERS:
        # Cast literales a NUMERIC explícitamente — psycopg pasa todo como
        # texto y el server requiere cast cuando el destino es NUMERIC.
        modulus_sql = f"'{modulus}'::numeric" if modulus is not None else "NULL"
        op.execute(
            f"""
            INSERT INTO pricing_golden_tiers
            (name, upper_bound, endings, modulus, tolerance)
            VALUES ('{name}', '{ub}'::numeric, '{endings}',
                    {modulus_sql}, '{tol}'::numeric)
            """
        )

    # ---------- UNIQUE parcial sobre prices (1 active approved/sku/channel/scheme) ----------
    # El índice se omite si ya existe (idempotente).
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_prices_one_approved_active
        ON prices (product_sku, channel_id, scheme_code)
        WHERE status = 'approved' AND valid_to IS NULL
        """
    )

    # ---------- Trigger: prices_initial_status_trg (BEFORE INSERT) ----------
    initial_csv = ",".join(f"'{s}'" for s in _VALID_INITIAL_STATUSES)
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prices_check_initial_status()
        RETURNS TRIGGER AS $fn$
        BEGIN
            IF NEW.status NOT IN ({initial_csv}) THEN
                RAISE EXCEPTION
                  'invalid_initial_status: estado inicial % no permitido. '
                  'Sólo draft o auto_approved.', NEW.status
                  USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS prices_initial_status_trg ON prices")
    op.execute(
        """
        CREATE TRIGGER prices_initial_status_trg
        BEFORE INSERT ON prices
        FOR EACH ROW
        EXECUTE FUNCTION prices_check_initial_status();
        """
    )

    # ---------- Trigger: prices_state_machine_trg (BEFORE UPDATE) ----------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prices_validate_transition()
        RETURNS TRIGGER AS $fn$
        BEGIN
            -- Permitir UPDATEs que NO cambien el status (e.g. update breakdown).
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;
            -- Validar la transición contra la tabla canónica.
            PERFORM 1
              FROM price_state_transitions
             WHERE from_status = OLD.status AND to_status = NEW.status;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                  'invalid_transition: % → % no permitida.',
                  OLD.status, NEW.status
                  USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS prices_state_machine_trg ON prices")
    op.execute(
        """
        CREATE TRIGGER prices_state_machine_trg
        BEFORE UPDATE ON prices
        FOR EACH ROW
        EXECUTE FUNCTION prices_validate_transition();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prices_state_machine_trg ON prices")
    op.execute("DROP FUNCTION IF EXISTS prices_validate_transition()")
    op.execute("DROP TRIGGER IF EXISTS prices_initial_status_trg ON prices")
    op.execute("DROP FUNCTION IF EXISTS prices_check_initial_status()")
    op.execute("DROP INDEX IF EXISTS uq_prices_one_approved_active")
    op.execute("DROP TABLE IF EXISTS pricing_golden_tiers")
    op.execute("DROP TABLE IF EXISTS price_state_transitions")
