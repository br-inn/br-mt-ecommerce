"""costs_engine — US-1A-04-02 motor de costes con FX as-of trigger.

Reemplaza la tabla `costs` antigua (creada en `20260507_010_pricing_models`)
por el schema nuevo del Sprint 3:

- ``id`` UUID PK
- ``sku`` FK products.sku (CASCADE)
- ``scheme_code`` FK schemes.code (RESTRICT)
- ``supplier_code`` FK suppliers.code (SET NULL, opcional)
- ``currency_origin`` FK currencies.code (RESTRICT, default 'AED')
- ``fx_rate_id`` FK fx_rates.id (SET NULL, autopoblado por trigger)
- ``breakdown`` JSONB
- ``scheme_landed_aed`` NUMERIC(14,4) (calculado por trigger AFTER)
- ``effective_at`` TIMESTAMPTZ NOT NULL
- ``status`` String(16) ∈ {active, superseded}
- ``fx_inferred`` BOOL default false
- ``version`` INT default 1
- AuditMixin (created_by, updated_by) + TimestampMixin

Triggers:
- ``costs_stamp_fx_trg BEFORE INSERT OR UPDATE``: si fx_rate_id NULL y
  currency_origin != 'AED', llama a ``fx_rate_at(currency_origin, 'AED',
  effective_at)`` (creada por la migración FX engine 20260507_017).
  Si no encuentra rate → RAISE EXCEPTION con 'fx_rate_not_found_at_effective_at'.
  Si currency_origin = 'AED' → fx_rate_id permanece NULL (rate identidad).
  Si fx_rate_id ya viene explícito → respeta (importer reusa).
- ``costs_compute_landed_aed_trg AFTER INSERT OR UPDATE OF breakdown,
  fx_rate_id``: suma breakdown × FX → scheme_landed_aed.

UNIQUE parcial: sólo 1 row 'active' por (sku, scheme_code, supplier_code).

DEPENDE de ``20260507_017_fx_engine`` que crea ``fx_rate_at(text, text, timestamptz)``.

Revision ID: 20260507_018
Revises: 20260507_017
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260507_018"
down_revision: str | None = "20260507_017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ===========================================================================
# Triggers — código PL/pgSQL en strings literales (uso `op.execute`).
# ===========================================================================

# Convención de claves del breakdown JSONB (reflected in PL/pgSQL):
#   *_aed   → no convierten (importes ya en AED)
#   *_<currency_origin lower>  → convierten via FX (rate)
#   *_pct   → porcentaje sobre el subtotal de los demás componentes
TRG_STAMP_FX = """
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

TRG_COMPUTE_LANDED = """
CREATE OR REPLACE FUNCTION costs_compute_landed_aed() RETURNS trigger AS $body$
DECLARE
    v_rate numeric(18,8) := 1;
    v_subtotal numeric(20,8) := 0;
    v_pct_total numeric(20,8) := 0;
    k text;
    v_raw text;
    v numeric(20,8);
    v_lower text;
    v_origin_suffix text;
BEGIN
    -- Resolve FX rate. NULL fx_rate_id (currency = AED) → rate=1.
    IF NEW.fx_rate_id IS NOT NULL THEN
        SELECT rate INTO v_rate FROM fx_rates WHERE id = NEW.fx_rate_id;
        IF v_rate IS NULL THEN
            v_rate := 1;
        END IF;
    END IF;

    v_origin_suffix := '_' || lower(NEW.currency_origin);

    -- Iterar pares clave-valor del JSONB.
    FOR k, v_raw IN SELECT * FROM jsonb_each_text(COALESCE(NEW.breakdown, '{}'::jsonb))
    LOOP
        -- Skip si el valor no es numérico parseable.
        BEGIN
            v := v_raw::numeric;
        EXCEPTION WHEN others THEN
            CONTINUE;
        END;

        v_lower := lower(k);

        IF v_lower LIKE '%\\_pct' ESCAPE '\\' THEN
            -- Porcentaje → acumula y se aplica al final.
            v_pct_total := v_pct_total + v;
        ELSIF v_lower LIKE '%\\_aed' ESCAPE '\\' THEN
            -- Importe ya en AED.
            v_subtotal := v_subtotal + v;
        ELSIF v_lower LIKE ('%' || v_origin_suffix) THEN
            -- Importe en moneda origen → convierte.
            v_subtotal := v_subtotal + (v * v_rate);
        ELSE
            -- Default: asume currency_origin si no es AED, AED si sí.
            IF NEW.currency_origin = 'AED' THEN
                v_subtotal := v_subtotal + v;
            ELSE
                v_subtotal := v_subtotal + (v * v_rate);
            END IF;
        END IF;
    END LOOP;

    -- Aplica % sobre el subtotal acumulado.
    IF v_pct_total <> 0 THEN
        v_subtotal := v_subtotal + (v_subtotal * v_pct_total / 100);
    END IF;

    -- AFTER trigger → write via UPDATE (no se puede mutar NEW).
    UPDATE costs
       SET scheme_landed_aed = round(v_subtotal, 4)
     WHERE id = NEW.id
       AND (scheme_landed_aed IS DISTINCT FROM round(v_subtotal, 4));

    RETURN NULL;
END;
$body$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # 0) Drop old `costs` table if present (created in 20260507_010 with the
    # legacy schema — `product_sku`, `total`, `valid_from/to`, etc.). Safe to
    # drop because S3 is the first sprint that *actually* writes costs.
    op.execute("DROP TABLE IF EXISTS costs CASCADE;")

    # 1) Recreate with new schema.
    op.create_table(
        "costs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scheme_code",
            sa.String(32),
            sa.ForeignKey("schemes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "supplier_code",
            sa.Text(),
            sa.ForeignKey("suppliers.code", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "currency_origin",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("'AED'"),
        ),
        sa.Column(
            "fx_rate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fx_rates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("scheme_landed_aed", sa.Numeric(14, 4), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "fx_inferred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        # Audit + Timestamps
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.CheckConstraint("status IN ('active','superseded')", name="ck_costs_status"),
        sa.CheckConstraint("version >= 1", name="ck_costs_version_pos"),
        sa.CheckConstraint(
            "scheme_landed_aed IS NULL OR scheme_landed_aed >= 0",
            name="ck_costs_landed_nonneg",
        ),
    )

    # Indexes
    op.create_index("idx_costs_sku_scheme", "costs", ["sku", "scheme_code"])
    op.create_index("idx_costs_effective_at", "costs", ["effective_at"])

    # UNIQUE parcial — sólo 1 'active' por (sku, scheme_code, COALESCE(supplier_code, '')).
    # supplier_code puede ser NULL: usamos COALESCE para que NULL cuente como
    # un único valor canónico (de lo contrario PG trataría cada NULL como
    # distinto y permitiría duplicados).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_costs_active_combo
        ON costs (sku, scheme_code, COALESCE(supplier_code, ''))
        WHERE status = 'active';
        """
    )

    # updated_at trigger (reusa función set_updated_at del initial_schema).
    op.execute(
        "CREATE TRIGGER trg_costs_updated_at BEFORE UPDATE ON costs "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # 2) Triggers FX + landed.
    op.execute(TRG_STAMP_FX)
    op.execute(TRG_COMPUTE_LANDED)

    op.execute(
        """
        DROP TRIGGER IF EXISTS costs_stamp_fx_trg ON costs;
        CREATE TRIGGER costs_stamp_fx_trg
            BEFORE INSERT OR UPDATE ON costs
            FOR EACH ROW EXECUTE FUNCTION costs_stamp_fx();
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS costs_compute_landed_aed_trg ON costs;
        CREATE TRIGGER costs_compute_landed_aed_trg
            AFTER INSERT OR UPDATE OF breakdown, fx_rate_id, currency_origin ON costs
            FOR EACH ROW EXECUTE FUNCTION costs_compute_landed_aed();
        """
    )

    # 3) RLS — recreate policies (drop in step 0 también las eliminó).
    op.execute(
        """
        DO $rls$
        DECLARE
            mt_app_exists BOOLEAN;
        BEGIN
            SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') INTO mt_app_exists;
            IF mt_app_exists THEN
                EXECUTE 'ALTER TABLE costs ENABLE ROW LEVEL SECURITY';
                EXECUTE 'CREATE POLICY costs_read_all ON costs '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY costs_comercial_write ON costs '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin''))';
            END IF;
        END
        $rls$;
        """
    )


def downgrade() -> None:
    # Drop triggers + table.
    op.execute("DROP TRIGGER IF EXISTS costs_compute_landed_aed_trg ON costs;")
    op.execute("DROP TRIGGER IF EXISTS costs_stamp_fx_trg ON costs;")
    op.execute("DROP FUNCTION IF EXISTS costs_compute_landed_aed();")
    op.execute("DROP FUNCTION IF EXISTS costs_stamp_fx();")
    op.execute("DROP TABLE IF EXISTS costs CASCADE;")

    # NOTE: no recreamos la tabla legacy — el sprint 3 es el primero que
    # realmente persiste costs, así que no hay datos que migrar al volver atrás.
