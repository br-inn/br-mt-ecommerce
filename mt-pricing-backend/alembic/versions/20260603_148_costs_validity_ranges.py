"""costs: vigencia por rangos valid_from/valid_to + exclusion GiST.

Extiende la tabla ``costs`` (Enfoque 1 del diseño de vigencia por rangos):

1. ``CREATE EXTENSION IF NOT EXISTS btree_gist`` (necesaria para combinar
   igualdad de ``text`` con solape de ``daterange`` en una constraint EXCLUDE).
2. Añade ``valid_from DATE`` (nullable temporal) y ``valid_to DATE NULL``.
3. Backfill ``valid_from = effective_at::date``.
4. Encadena ``valid_to = (siguiente valid_from) - 1 día`` por clave
   ``(sku, scheme_code, coalesce(supplier_code, ''))`` ordenado por
   ``(valid_from, version)``; la última fila de cada clave queda abierta
   (``valid_to = NULL``).
5. ``valid_from SET NOT NULL``.
6. Dropea el índice unique parcial ``idx_costs_active_unique_lookup`` (era
   ``WHERE status = 'active'``) y añade la exclusión ``ex_costs_no_overlap``.
7. Recrea ``costs_stamp_fx()`` anclando en ``NEW.valid_from`` (en vez de
   ``NEW.effective_at``). El resto del cuerpo es idéntico a la migración 018.
   El trigger ``costs_compute_landed_aed`` NO se toca.
8. Dropea ``status`` (+ check ``ck_costs_status``) y ``effective_at``.

``downgrade()`` es reversible: re-añade ``effective_at`` (= valid_from::tstz)
y ``status`` (active si vigente hoy, si no superseded), restaura
``ck_costs_status`` + el índice unique parcial, restaura ``costs_stamp_fx``
sobre ``effective_at`` y dropea ``valid_to``/``valid_from`` + la exclusión.
La extensión ``btree_gist`` se deja instalada.

Revision ID: 20260603_148
Revises: 20260603_147
Create Date: 2026-05-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260603_148"
down_revision: str | None = "20260603_147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ===========================================================================
# Triggers — costs_stamp_fx() replicado de 20260507_018_costs_engine.py.
# UPGRADE: ancla en NEW.valid_from (DATE → ::timestamptz). DOWNGRADE: ancla
# en NEW.effective_at (TIMESTAMPTZ). Todo lo demás es idéntico al original.
# ===========================================================================

TRG_STAMP_FX_VALID_FROM = """
CREATE OR REPLACE FUNCTION costs_stamp_fx() RETURNS trigger AS $body$
DECLARE
    v_fx_id uuid;
BEGIN
    -- Si fx_rate_id viene explícito (importer reusa) → respetar y NO sobrescribir.
    IF NEW.fx_rate_id IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Si la moneda origen es AED, no hace falta FX (rate identidad implícita).
    IF NEW.currency_origin = 'AED' THEN
        NEW.fx_rate_id := NULL;
        RETURN NEW;
    END IF;

    -- Buscar el FX vigente a valid_from vía función fx_rate_at (US-1A-05-02).
    -- Si no existe → fail con código semántico.
    BEGIN
        SELECT fx_rate_at(NEW.currency_origin, 'AED', NEW.valid_from::timestamptz)
            INTO v_fx_id;
    EXCEPTION
        WHEN undefined_function THEN
            -- Fallback (test envs sin la función) — busca directo en fx_rates.
            v_fx_id := NULL;
    END;

    IF v_fx_id IS NULL THEN
        SELECT id INTO v_fx_id
        FROM fx_rates
        WHERE from_currency = NEW.currency_origin
          AND to_currency = 'AED'
          AND effective_from <= NEW.valid_from::timestamptz
          AND (effective_to IS NULL OR effective_to > NEW.valid_from::timestamptz)
        ORDER BY effective_from DESC
        LIMIT 1;
    END IF;

    IF v_fx_id IS NULL THEN
        RAISE EXCEPTION 'fx_rate_not_found_at_effective_at: % -> AED at %',
            NEW.currency_origin, NEW.valid_from
            USING ERRCODE = 'P0001';
    END IF;

    NEW.fx_rate_id := v_fx_id;
    RETURN NEW;
END;
$body$ LANGUAGE plpgsql;
"""

# Versión original (downgrade) — anclada en NEW.effective_at, copiada literal
# de 20260507_018_costs_engine.py (TRG_STAMP_FX).
TRG_STAMP_FX_EFFECTIVE_AT = """
CREATE OR REPLACE FUNCTION costs_stamp_fx() RETURNS trigger AS $body$
DECLARE
    v_fx_id uuid;
BEGIN
    -- Si fx_rate_id viene explícito (importer reusa) → respetar y NO sobrescribir.
    IF NEW.fx_rate_id IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Si la moneda origen es AED, no hace falta FX (rate identidad implícita).
    IF NEW.currency_origin = 'AED' THEN
        NEW.fx_rate_id := NULL;
        RETURN NEW;
    END IF;

    -- Buscar el FX vigente a effective_at vía función fx_rate_at (US-1A-05-02).
    -- Si no existe → fail con código semántico.
    BEGIN
        SELECT fx_rate_at(NEW.currency_origin, 'AED', NEW.effective_at) INTO v_fx_id;
    EXCEPTION
        WHEN undefined_function THEN
            -- Fallback (test envs sin la función) — busca directo en fx_rates.
            v_fx_id := NULL;
    END;

    IF v_fx_id IS NULL THEN
        SELECT id INTO v_fx_id
        FROM fx_rates
        WHERE from_currency = NEW.currency_origin
          AND to_currency = 'AED'
          AND effective_from <= NEW.effective_at
          AND (effective_to IS NULL OR effective_to > NEW.effective_at)
        ORDER BY effective_from DESC
        LIMIT 1;
    END IF;

    IF v_fx_id IS NULL THEN
        RAISE EXCEPTION 'fx_rate_not_found_at_effective_at: % -> AED at %',
            NEW.currency_origin, NEW.effective_at
            USING ERRCODE = 'P0001';
    END IF;

    NEW.fx_rate_id := v_fx_id;
    RETURN NEW;
END;
$body$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # 1) Extensión requerida por la constraint EXCLUDE (text WITH = + daterange).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 2) Columnas (valid_from nullable temporalmente para poder backfillear).
    op.add_column("costs", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("costs", sa.Column("valid_to", sa.Date(), nullable=True))

    # 3) Backfill: valid_from = effective_at::date.
    op.execute("UPDATE costs SET valid_from = effective_at::date")

    # 4) Encadenar valid_to = (siguiente valid_from del mismo key) - 1 día.
    #    La última fila de cada clave queda con valid_to = NULL (abierta).
    op.execute(
        """
        WITH ordered AS (
          SELECT
            id,
            lead(valid_from) OVER (
              PARTITION BY sku, scheme_code, coalesce(supplier_code, '')
              ORDER BY valid_from, version
            ) AS next_from
          FROM costs
        )
        UPDATE costs c
           SET valid_to = (o.next_from - INTERVAL '1 day')::date
          FROM ordered o
         WHERE c.id = o.id
           AND o.next_from IS NOT NULL
        """
    )

    # 5) valid_from NOT NULL.
    op.alter_column("costs", "valid_from", nullable=False)

    # 6) Quitar el índice unique parcial viejo y añadir la exclusión de no-solape.
    op.execute("DROP INDEX IF EXISTS idx_costs_active_unique_lookup")
    op.execute(
        """
        ALTER TABLE costs ADD CONSTRAINT ex_costs_no_overlap
        EXCLUDE USING gist (
          sku WITH =,
          scheme_code WITH =,
          coalesce(supplier_code, '') WITH =,
          daterange(valid_from, valid_to, '[]') WITH &&
        )
        """
    )

    # 7) Recrear costs_stamp_fx() anclando en NEW.valid_from.
    op.execute(TRG_STAMP_FX_VALID_FROM)

    # 8) Dropear status (+ check) y effective_at.
    op.execute("ALTER TABLE costs DROP CONSTRAINT IF EXISTS ck_costs_status")
    op.execute("DROP INDEX IF EXISTS idx_costs_effective_at")
    op.drop_column("costs", "status")
    op.drop_column("costs", "effective_at")


def downgrade() -> None:
    # 1) Re-añadir effective_at y status (nullable temporal para backfill).
    op.add_column(
        "costs",
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("costs", sa.Column("status", sa.String(16), nullable=True))

    # 2) Backfill effective_at = valid_from::timestamptz.
    op.execute("UPDATE costs SET effective_at = valid_from::timestamptz")

    # 3) Backfill status: 'active' si la fila está vigente hoy (rango abierto o
    #    current_date dentro de [valid_from, valid_to]); si no, 'superseded'.
    op.execute(
        """
        UPDATE costs SET status = CASE
          WHEN valid_to IS NULL OR current_date BETWEEN valid_from AND valid_to
          THEN 'active'
          ELSE 'superseded'
        END
        """
    )

    # 4) NOT NULL + restaurar check constraint.
    op.alter_column("costs", "effective_at", nullable=False)
    op.alter_column("costs", "status", nullable=False)
    op.execute(
        "ALTER TABLE costs ADD CONSTRAINT ck_costs_status CHECK (status IN ('active','superseded'))"
    )

    # 5) Dropear la exclusión y restaurar el índice parcial original.
    #    En el head actual (migración 157) este índice NO es unique e indexa
    #    las columnas crudas (sin COALESCE) con WHERE status = 'active'.
    op.execute("ALTER TABLE costs DROP CONSTRAINT IF EXISTS ex_costs_no_overlap")
    op.create_index(
        "idx_costs_active_unique_lookup",
        "costs",
        ["sku", "scheme_code", "supplier_code"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("idx_costs_effective_at", "costs", ["effective_at"])

    # 6) Restaurar costs_stamp_fx() anclado en NEW.effective_at.
    op.execute(TRG_STAMP_FX_EFFECTIVE_AT)

    # 7) Dropear las columnas de rangos. (La extensión btree_gist se deja.)
    op.drop_column("costs", "valid_to")
    op.drop_column("costs", "valid_from")
