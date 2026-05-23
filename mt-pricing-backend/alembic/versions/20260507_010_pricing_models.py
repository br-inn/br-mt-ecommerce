"""pricing_models — Wave 2 motor v5.1 ported.

Crea las tablas del dominio pricing:
- channels (5 canales seeded inactive)
- fx_rates (1 FX EUR→AED 4.29 efectivo desde 2026-04-01)
- costs (breakdown JSONB por SKU + scheme)
- prices (state machine: draft|auto_approved|pending_review|approved|rejected|revised|exported)
- exception_rules (5 thresholds default — margin 5%, FX 3%, min margin B2C 8%/B2B 5%)
- price_approval_events (audit FSM)

Refs:
- ADR-006 (workflow excepción)
- ADR-010 (no aprobado no integra)
- ADR-045 (persistencia híbrida)
- _bmad-output/planning-artifacts/sprint0-v51-rules-extraction.md (golden numbers)

RLS:
- channels/fx_rates/exception_rules: read-all-auth, write admin/TI.
- costs/prices: read aplicación-completa, write con auth.uid() (preparado).

NOTA: la migration 20260507_004 ya creó `currencies` y `schemes`. Esta migration
sólo añade columna nueva si fuera necesario (no es).

Revision ID: 20260507_010
Revises: 20260507_009
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507_010"
down_revision: str | None = "20260507_009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------
# Seeds
# --------------------------------------------------------------------------
_CHANNELS_SEED: tuple[tuple[str, str, str, list[str]], ...] = (
    (
        "amazon_uae",
        "Amazon UAE",
        "inactive",
        ["FBA", "FBM"],
    ),
    (
        "noon_uae",
        "Noon UAE",
        "inactive",
        ["MARKETPLACE"],
    ),
    (
        "b2c_direct",
        "B2C directo (mtme.ae)",
        "inactive",
        ["DIRECT_B2C"],
    ),
    (
        "b2b_direct",
        "B2B directo",
        "inactive",
        ["DIRECT_B2B"],
    ),
    (
        "marketplace_listing",
        "Marketplace listing genérico",
        "inactive",
        ["MARKETPLACE"],
    ),
)


# (code, description, channel_code|None, scheme_code|None,
#  margin_threshold_pct, fx_swing_threshold_pct, min_margin_pct)
_EXCEPTION_RULES_SEED: tuple[
    tuple[str, str, str | None, str | None, float | None, float | None, float | None], ...
] = (
    (
        "GLOBAL_MARGIN_DELTA",
        "Pending review si delta margen > 5% vs precio anterior",
        None,
        None,
        5.0,
        None,
        None,
    ),
    (
        "GLOBAL_FX_SWING",
        "Pending review si FX se movió > 3% desde último precio",
        None,
        None,
        None,
        3.0,
        None,
    ),
    (
        "B2C_MIN_MARGIN",
        "Margen mínimo B2C 8%",
        None,
        "DIRECT_B2C",
        None,
        None,
        8.0,
    ),
    (
        "B2B_MIN_MARGIN",
        "Margen mínimo B2B 5%",
        None,
        "DIRECT_B2B",
        None,
        None,
        5.0,
    ),
    (
        "FBA_MIN_MARGIN",
        "Margen mínimo FBA 10%",
        None,
        "FBA",
        None,
        None,
        10.0,
    ),
)


def upgrade() -> None:
    # ----- channels -----
    op.create_table(
        "channels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "state",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'inactive'"),
        ),
        sa.Column(
            "schemes_supported",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "state_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        sa.CheckConstraint(
            "state IN ('inactive','pre_launch','pilot','live','paused','deprecated')",
            name="ck_channels_state",
        ),
    )
    op.create_index("idx_channels_state", "channels", ["state"])
    op.execute(
        "CREATE TRIGGER trg_channels_updated_at BEFORE UPDATE ON channels "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # Seed channels.
    import json

    for code, name, state, schemes in _CHANNELS_SEED:
        schemes_sql = json.dumps(schemes).replace("'", "''")
        op.execute(
            f"INSERT INTO channels (code, name, state, schemes_supported) "
            f"VALUES ('{code}', '{name.replace(chr(39), chr(39) * 2)}', "
            f"        '{state}', '{schemes_sql}'::jsonb) "
            f"ON CONFLICT (code) DO NOTHING;"
        )

    # ----- fx_rates -----
    op.create_table(
        "fx_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "from_currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=True),
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
        sa.CheckConstraint("rate > 0", name="ck_fx_rate_positive"),
    )
    op.create_index("idx_fx_lookup", "fx_rates", ["from_currency", "to_currency", "effective_from"])
    op.create_index(
        "idx_fx_active",
        "fx_rates",
        ["from_currency", "to_currency"],
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_fx_rates_updated_at BEFORE UPDATE ON fx_rates "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # Seed FX EUR→AED 4.29 efectivo 2026-04-01.
    op.execute(
        "INSERT INTO fx_rates (from_currency, to_currency, rate, "
        "       effective_from, source) "
        "VALUES ('EUR', 'AED', 4.29, '2026-04-01 00:00:00+00', 'manual') "
        "ON CONFLICT DO NOTHING;"
    )
    # Inversa
    op.execute(
        "INSERT INTO fx_rates (from_currency, to_currency, rate, "
        "       effective_from, source) "
        "VALUES ('AED', 'EUR', 0.23310023, '2026-04-01 00:00:00+00', 'manual') "
        "ON CONFLICT DO NOTHING;"
    )

    # ----- costs -----
    op.create_table(
        "costs",
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
            "breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("total", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("'AED'"),
        ),
        sa.Column("fx_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        # Audit mixin
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
        sa.CheckConstraint("total >= 0", name="ck_costs_total_nonneg"),
    )
    op.create_index("idx_costs_lookup", "costs", ["product_sku", "scheme_code", "valid_from"])
    op.create_index(
        "idx_costs_active",
        "costs",
        ["product_sku", "scheme_code"],
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_costs_updated_at BEFORE UPDATE ON costs "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- prices -----
    op.create_table(
        "prices",
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
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scheme_code",
            sa.String(32),
            sa.ForeignKey("schemes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("pvp_min", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "margin_pct",
            sa.Numeric(7, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=False,
            server_default=sa.text("'AED'"),
        ),
        sa.Column("rule_applied", sa.String(64), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column(
            "breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "alerts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("fx_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "proposed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        # AuditMixin
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
        sa.CheckConstraint("amount >= 0", name="ck_prices_amount_nonneg"),
        sa.CheckConstraint(
            "status IN ('draft','pending_review','auto_approved','approved','rejected','revised','exported','superseded','migrated')",
            name="ck_prices_status",
        ),
    )
    op.create_index("idx_prices_lookup", "prices", ["product_sku", "channel_id", "scheme_code"])
    op.create_index(
        "idx_prices_pending",
        "prices",
        ["status"],
        postgresql_where=sa.text("status IN ('pending_review','draft')"),
    )
    op.create_index(
        "idx_prices_active",
        "prices",
        ["product_sku", "channel_id", "scheme_code"],
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_prices_updated_at BEFORE UPDATE ON prices "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- exception_rules -----
    op.create_table(
        "exception_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "scheme_code",
            sa.String(32),
            sa.ForeignKey("schemes.code", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("margin_threshold_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("fx_swing_threshold_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("min_margin_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column(
            "active",
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
    )
    op.create_index(
        "idx_exception_rules_active",
        "exception_rules",
        ["active"],
        postgresql_where=sa.text("active = true"),
    )
    op.execute(
        "CREATE TRIGGER trg_exception_rules_updated_at BEFORE UPDATE ON exception_rules "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # Seed exception rules.
    for (
        code,
        description,
        channel_code,
        scheme_code,
        margin_th,
        fx_th,
        min_margin,
    ) in _EXCEPTION_RULES_SEED:
        desc_sql = description.replace("'", "''") if description else ""
        if channel_code:
            channel_id_sql = f"(SELECT id FROM channels WHERE code = '{channel_code}')"
        else:
            channel_id_sql = "NULL"
        scheme_sql = f"'{scheme_code}'" if scheme_code else "NULL"
        margin_sql = f"{margin_th}" if margin_th is not None else "NULL"
        fx_sql = f"{fx_th}" if fx_th is not None else "NULL"
        min_margin_sql = f"{min_margin}" if min_margin is not None else "NULL"
        op.execute(
            f"INSERT INTO exception_rules (code, description, channel_id, "
            f"  scheme_code, margin_threshold_pct, fx_swing_threshold_pct, "
            f"  min_margin_pct) "
            f"VALUES ('{code}', '{desc_sql}', {channel_id_sql}, "
            f"  {scheme_sql}, {margin_sql}, {fx_sql}, {min_margin_sql}) "
            f"ON CONFLICT (code) DO NOTHING;"
        )

    # ----- price_approval_events -----
    op.create_table(
        "price_approval_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "price_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=False),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.CheckConstraint(
            "from_status IN ('draft','pending_review','auto_approved','approved','rejected','revised','exported','superseded','migrated')",
            name="ck_price_approval_events_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('draft','pending_review','auto_approved','approved','rejected','revised','exported','superseded','migrated')",
            name="ck_price_approval_events_to_status",
        ),
    )
    op.create_index(
        "idx_price_approval_events_lookup",
        "price_approval_events",
        ["price_id", "created_at"],
    )

    # ----- Permissions seed (RBAC) -----
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('prices:read', 'Listar/leer prices'),
            ('prices:propose', 'Crear propuesta de precio (motor v5.1)'),
            ('prices:approve', 'Aprobar/rechazar/revisar prices'),
            ('prices:export', 'Marcar prices como exported'),
            ('channels:read', 'Listar canales'),
            ('channels:manage', 'Gestionar estado de canales'),
            ('fx:read', 'Listar FX rates'),
            ('fx:write', 'Crear FX rates manuales')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ----- RLS policies -----
    op.execute(
        """
        DO $rls$
        DECLARE
            mt_app_exists BOOLEAN;
        BEGIN
            SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') INTO mt_app_exists;
            IF mt_app_exists THEN
                EXECUTE 'ALTER TABLE channels             ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE fx_rates             ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE costs                ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE prices               ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE exception_rules      ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE price_approval_events ENABLE ROW LEVEL SECURITY';

                EXECUTE 'CREATE POLICY channels_read_all ON channels '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY channels_admin_write ON channels '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY fx_rates_read_all ON fx_rates '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY fx_rates_ti_write ON fx_rates '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY costs_read_all ON costs '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY costs_comercial_write ON costs '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY prices_read_all ON prices '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY prices_propose_write ON prices '
                     || 'FOR INSERT TO mt_app '
                     || 'WITH CHECK (auth.uid() IS NOT NULL AND current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin''))';
                EXECUTE 'CREATE POLICY prices_update_write ON prices '
                     || 'FOR UPDATE TO mt_app '
                     || 'USING (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY exception_rules_read_all ON exception_rules '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY exception_rules_admin_write ON exception_rules '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''gerente_comercial'',''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''gerente_comercial'',''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY price_approval_events_read_all ON price_approval_events '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY price_approval_events_insert ON price_approval_events '
                     || 'FOR INSERT TO mt_app '
                     || 'WITH CHECK (auth.uid() IS NOT NULL)';
            END IF;
        END
        $rls$;
        """
    )


def downgrade() -> None:
    # Inverse order — drop tablas hijo primero.
    op.execute("DROP TABLE IF EXISTS price_approval_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS exception_rules CASCADE;")
    op.execute("DROP TABLE IF EXISTS prices CASCADE;")
    op.execute("DROP TABLE IF EXISTS costs CASCADE;")
    op.execute("DROP TABLE IF EXISTS fx_rates CASCADE;")
    op.execute("DROP TABLE IF EXISTS channels CASCADE;")

    op.execute(
        """
        DELETE FROM permissions WHERE code IN (
            'prices:read','prices:propose','prices:approve','prices:export',
            'channels:read','channels:manage','fx:read','fx:write'
        );
        """
    )
