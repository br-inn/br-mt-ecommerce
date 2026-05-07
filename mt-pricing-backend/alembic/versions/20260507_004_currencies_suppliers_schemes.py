"""currencies_suppliers_schemes — S2 master data fundacional.

Cubre tres stories del Sprint 2:
- US-1A-03-01 — `currencies` (seed mínimo USD/EUR/AED/SAR) + `suppliers`.
- US-1A-04-01 — `schemes` con `cost_components_template` JSONB seeded.

NO incluye `fx_rates`, `channels`, ni `costs` — esos llegan en S3.

RLS:
- `currencies`: read-all-auth, write admin/TI sólo (read-only en S2).
- `suppliers`: read-all-auth, write comercial+ (replica patrón products).
- `schemes`: read-all-auth, write admin/TI sólo (catálogo cerrado).

Revision ID: 20260507_004
Revises: 20260506_003
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260507_004"
down_revision: str | None = "20260506_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------
# Seeds
# --------------------------------------------------------------------------
# Currencies — orden importa: AED es la base, debe insertarse primero o el
# partial unique index `uq_currencies_one_base` rechaza inserts simultáneos.
_CURRENCIES_SEED: tuple[tuple[str, str, str, int, bool], ...] = (
    # (code, name, symbol, decimals, is_base)
    ("AED", "United Arab Emirates Dirham", "د.إ", 2, True),
    ("USD", "United States Dollar", "$", 2, False),
    ("EUR", "Euro", "€", 2, False),
    ("SAR", "Saudi Riyal", "ر.س", 2, False),
)

# Cost schemes — los 5 templates documentados en sprint2-backlog §US-1A-04-01.
# Estructura JSONB: {"required": [...componentes...]}.
_SCHEMES_SEED: tuple[tuple[str, str, str, list[str]], ...] = (
    (
        "FBA",
        "Amazon FBA",
        "Amazon Fulfillment by Amazon — fees Amazon incluidos",
        ["fob", "freight", "customs", "fba_fees", "payment_fees"],
    ),
    (
        "FBM",
        "Amazon FBM",
        "Amazon Fulfilled by Merchant — fees referrer Amazon",
        ["fob", "freight", "customs", "fbm_fees", "payment_fees"],
    ),
    (
        "DIRECT_B2C",
        "Direct B2C",
        "Venta directa a consumidor final (mtme.ae) con marketing propio",
        ["fob", "freight", "customs", "payment_fees", "marketing"],
    ),
    (
        "DIRECT_B2B",
        "Direct B2B",
        "Venta directa B2B (distribuidores GCC) — sin marketing",
        ["fob", "freight", "customs", "payment_fees"],
    ),
    (
        "MARKETPLACE",
        "Marketplace listed",
        "Marketplaces no-Amazon (Noon, etc.) con fees referrer",
        ["fob", "freight", "customs", "marketplace_fees", "payment_fees", "marketing"],
    ),
)


def upgrade() -> None:
    # ----- currencies -----
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text()),
        sa.Column("decimals", sa.Integer(), nullable=False, server_default=sa.text("2")),
        sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("decimals BETWEEN 0 AND 8", name="ck_currencies_decimals"),
    )
    # Una sola moneda base (partial unique).
    op.execute(
        "CREATE UNIQUE INDEX uq_currencies_one_base ON currencies (is_base) "
        "WHERE is_base = true;"
    )

    # Seed currencies — orden: base primero. Usamos SQL literal con escape
    # de comilla simple en symbol (los nombres de monedas no contienen comillas).
    for code, name, symbol, decimals, is_base in _CURRENCIES_SEED:
        symbol_sql = "NULL" if symbol is None else "'" + symbol.replace("'", "''") + "'"
        op.execute(
            f"INSERT INTO currencies (code, name, symbol, decimals, is_base) "
            f"VALUES ('{code}', '{name.replace(chr(39), chr(39)*2)}', "
            f"        {symbol_sql}, {decimals}, {str(is_base).lower()}) "
            f"ON CONFLICT (code) DO NOTHING;"
        )

    # ----- suppliers -----
    op.create_table(
        "suppliers",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("contact_email", postgresql.CITEXT()),
        sa.Column("contact_phone", sa.Text()),
        sa.Column(
            "contract_currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("lead_time_days", sa.Integer()),
        sa.Column("payment_terms", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    )
    op.create_index(
        "idx_suppliers_active",
        "suppliers",
        ["active"],
        postgresql_where=sa.text("active = true"),
    )
    op.create_index("idx_suppliers_currency", "suppliers", ["contract_currency"])

    # Trigger updated_at — reusa la función creada en migration 001.
    op.execute(
        "CREATE TRIGGER trg_suppliers_updated_at BEFORE UPDATE ON suppliers "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- schemes (cost schemes) -----
    op.create_table(
        "schemes",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "cost_components_template",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint(
            "code IN ('FBA','FBM','DIRECT_B2C','DIRECT_B2B','MARKETPLACE')",
            name="ck_schemes_code",
        ),
    )

    # Seed cost schemes — JSONB inline literal (más simple que jsonb_build_object
    # con bindparams en op.execute). Escapamos las comillas simples del JSON.
    import json

    for code, name, description, components in _SCHEMES_SEED:
        components_json = json.dumps({"required": components})
        # Doble comilla SQL para escapar dentro de literal.
        components_sql = components_json.replace("'", "''")
        desc_sql = description.replace("'", "''") if description else ""
        op.execute(
            f"INSERT INTO schemes (code, name, description, cost_components_template) "
            f"VALUES ('{code}', '{name.replace(chr(39), chr(39)*2)}', "
            f"        '{desc_sql}', '{components_sql}'::jsonb) "
            f"ON CONFLICT (code) DO NOTHING;"
        )

    # ----- RLS policies -----
    # Las políticas RLS dependen del rol `mt_app` y la función `current_role_code()`
    # creados por las migraciones Supabase (`supabase/migrations/20260506_001`,
    # `20260506_003`). En testcontainers Postgres puro, el rol no existe y las
    # policies fallarían — por eso aplicamos sólo si el rol existe (idempotente).
    # Mirror canónico de las policies vive en
    # `supabase/migrations/20260507_005_currencies_suppliers_schemes_rls.sql`.
    op.execute(
        """
        DO $rls$
        DECLARE
            mt_app_exists BOOLEAN;
        BEGIN
            SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') INTO mt_app_exists;
            IF mt_app_exists THEN
                EXECUTE 'ALTER TABLE currencies ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE suppliers  ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE schemes    ENABLE ROW LEVEL SECURITY';

                EXECUTE 'CREATE POLICY currencies_read_all ON currencies '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY currencies_ti_write ON currencies '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY suppliers_read_all ON suppliers '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY suppliers_write_comercial ON suppliers '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''comercial'',''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''comercial'',''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY schemes_read_all ON schemes '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY schemes_ti_write ON schemes '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''ti_integracion'',''admin''))';
            END IF;
        END
        $rls$;
        """
    )


def downgrade() -> None:
    # Orden inverso. Drop policies via DROP TABLE CASCADE.
    op.execute("DROP TABLE IF EXISTS schemes CASCADE;")
    op.execute("DROP TABLE IF EXISTS suppliers CASCADE;")
    op.execute("DROP TABLE IF EXISTS currencies CASCADE;")
