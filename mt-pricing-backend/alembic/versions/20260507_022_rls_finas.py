"""rls_finas — US-1A-07-02 (Sprint 4) RLS finas products/costs/prices/audit_events.

Cambios:

- Activa RLS endurecida sobre tablas previamente protegidas con políticas
  amplias (S1/S2):
    * ``products`` — SELECT all auth, write comercial+; ya estaba pero se
      refuerza eliminando políticas obsoletas.
    * ``costs`` — comercial INSERT/UPDATE; gerente UPDATE; ti full; auditor
      read-only.
    * ``prices`` — comercial INSERT (status=draft only); gerente UPDATE
      transition; ti full; auditor read-only.
    * ``audit_events`` — append-only via service; gerente/ti/auditor SELECT;
      comercial denied; UPDATE/DELETE denied (trigger BEFORE
      UPDATE OR DELETE raises 'forbidden_audit_mutation').

Roles aplicativos (codes):
- ``comercial``
- ``gerente`` (alias backward-compat: ``gerente_comercial``)
- ``ti`` (alias: ``ti_integracion``)
- ``auditor`` (NUEVO en S4 — read-only sobre todas las tablas auditables)

Implementación: política PL/pgSQL ``CURRENT_SETTING('app.user_role')`` con
fallback a ``current_role_code()`` (helper S1) — este último lee
``request.jwt.claims->>role`` y soporta el JWT de Supabase.

Append-only audit_events: trigger ``audit_events_immutable_trg`` BEFORE
UPDATE OR DELETE raises ``forbidden_audit_mutation``.

NOTA — slot 022 reservado al RLS finas agente. ``down_revision="20260507_021"``.

Revision ID: 20260507_022
Revises: 20260507_021
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260507_022"
down_revision: str | None = "20260507_021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Roles privilegiados — pueden hacer la operación principal.
# Nota: usamos los aliases legacy + nuevos para tolerancia.
_R_COMERCIAL = ("comercial",)
_R_GERENTE = ("gerente", "gerente_comercial")
_R_TI = ("ti", "ti_integracion", "admin")
_R_AUDITOR = ("auditor",)


def _csv(*roles: tuple[str, ...]) -> str:
    flat = []
    for r in roles:
        flat.extend(r)
    return ",".join(f"'{r}'" for r in flat)


def upgrade() -> None:
    # ---------- ensure mt_app role exists (supabase-side seed normally) ----------
    # En entornos donde supabase/migrations/20260506_001_create_mt_app_role.sql
    # no se aplicó (DB local de dev sin Supabase CLI run), creamos el rol
    # defensivamente para que las CREATE POLICY ... TO mt_app no fallen.
    op.execute(
        """
        DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') THEN
                CREATE ROLE mt_app NOLOGIN;
            END IF;
        END
        $do$;
        """
    )
    # ---------- helper resolve_user_role() — defense-in-depth ----------
    # Lee primero `app.user_role` (set por backend FastAPI explícitamente),
    # con fallback a `current_role_code()` (JWT claims).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION resolve_user_role() RETURNS TEXT
        LANGUAGE plpgsql STABLE AS $fn$
        DECLARE
            r TEXT;
        BEGIN
            -- 1. app.user_role explícito (backend lo setea per-request).
            BEGIN
                r := NULLIF(current_setting('app.user_role', true), '');
            EXCEPTION WHEN OTHERS THEN
                r := NULL;
            END;
            IF r IS NOT NULL THEN
                RETURN r;
            END IF;
            -- 2. JWT claims (Supabase).
            BEGIN
                r := current_setting('request.jwt.claims', true)::json->>'role';
            EXCEPTION WHEN OTHERS THEN
                r := NULL;
            END;
            RETURN NULLIF(r, '');
        END;
        $fn$;
        """
    )

    # ============================================================
    # PRODUCTS — endurecer (drop policies amplias previas y reseed).
    # ============================================================
    op.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY")
    for pol in (
        "products_read_all",
        "products_write_comercial",
        "products_finas_read",
        "products_finas_write_comercial",
        "products_finas_write_ti",
    ):
        op.execute(f"DROP POLICY IF EXISTS {pol} ON products")
    op.execute(
        f"""
        CREATE POLICY products_finas_read ON products
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_GERENTE, _R_TI, _R_AUDITOR)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY products_finas_write_comercial ON products
            FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_TI)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY products_finas_update_comercial ON products
            FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_TI)}))
            WITH CHECK (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_TI)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY products_finas_delete_ti ON products
            FOR DELETE TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_TI)}));
        """
    )

    # ============================================================
    # COSTS
    # ============================================================
    op.execute("ALTER TABLE costs ENABLE ROW LEVEL SECURITY")
    for pol in (
        "costs_read_all",
        "costs_write_comercial",
        "costs_finas_read",
        "costs_finas_insert_comercial",
        "costs_finas_update_gerente",
        "costs_finas_full_ti",
    ):
        op.execute(f"DROP POLICY IF EXISTS {pol} ON costs")
    op.execute(
        f"""
        CREATE POLICY costs_finas_read ON costs
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_GERENTE, _R_TI, _R_AUDITOR)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY costs_finas_insert_comercial ON costs
            FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_TI)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY costs_finas_update_gerente ON costs
            FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_GERENTE, _R_TI)}))
            WITH CHECK (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_GERENTE, _R_TI)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY costs_finas_delete_ti ON costs
            FOR DELETE TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_TI)}));
        """
    )

    # ============================================================
    # PRICES
    # ============================================================
    op.execute("ALTER TABLE prices ENABLE ROW LEVEL SECURITY")
    for pol in (
        "prices_read_all",
        "prices_finas_read",
        "prices_finas_insert_comercial",
        "prices_finas_update_gerente",
        "prices_finas_full_ti",
    ):
        op.execute(f"DROP POLICY IF EXISTS {pol} ON prices")
    op.execute(
        f"""
        CREATE POLICY prices_finas_read ON prices
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_GERENTE, _R_TI, _R_AUDITOR)}));
        """
    )
    # Comercial sólo puede INSERT con status='draft'.
    op.execute(
        f"""
        CREATE POLICY prices_finas_insert_comercial ON prices
            FOR INSERT TO mt_app
            WITH CHECK (
                resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_TI)})
                AND (
                    resolve_user_role() IN ({_csv(_R_TI)})
                    OR status = 'draft'
                )
            );
        """
    )
    # Gerente puede UPDATE para aprobaciones; comercial sólo si status sigue en draft.
    op.execute(
        f"""
        CREATE POLICY prices_finas_update_gerente ON prices
            FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_GERENTE, _R_TI)}))
            WITH CHECK (resolve_user_role() IN ({_csv(_R_GERENTE, _R_TI)}));
        """
    )
    op.execute(
        f"""
        CREATE POLICY prices_finas_update_comercial_draft ON prices
            FOR UPDATE TO mt_app
            USING (
                resolve_user_role() IN ({_csv(_R_COMERCIAL)})
                AND status = 'draft'
            )
            WITH CHECK (
                resolve_user_role() IN ({_csv(_R_COMERCIAL)})
                AND status = 'draft'
            );
        """
    )
    op.execute(
        f"""
        CREATE POLICY prices_finas_delete_ti ON prices
            FOR DELETE TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_TI)}));
        """
    )

    # ============================================================
    # AUDIT_EVENTS
    # ============================================================
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    for pol in (
        "audit_events_read",
        "audit_events_insert",
        "audit_events_finas_read",
        "audit_events_finas_insert",
    ):
        op.execute(f"DROP POLICY IF EXISTS {pol} ON audit_events")
    # Lectura: gerente, ti, auditor. Comercial NO ve audit log.
    op.execute(
        f"""
        CREATE POLICY audit_events_finas_read ON audit_events
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ({_csv(_R_GERENTE, _R_TI, _R_AUDITOR)}));
        """
    )
    # Append: cualquier rol autenticado puede INSERT (los servicios escriben).
    op.execute(
        f"""
        CREATE POLICY audit_events_finas_insert ON audit_events
            FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ({_csv(_R_COMERCIAL, _R_GERENTE, _R_TI, _R_AUDITOR)}));
        """
    )

    # Append-only: trigger raise on UPDATE/DELETE (defense-in-depth, NFR-34).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_forbid_mutation()
        RETURNS TRIGGER AS $fn$
        BEGIN
            RAISE EXCEPTION
              'forbidden_audit_mutation: audit_events es append-only.'
              USING ERRCODE = 'insufficient_privilege';
        END;
        $fn$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS audit_events_immutable_trg ON audit_events"
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_immutable_trg
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION audit_events_forbid_mutation();
        """
    )


def downgrade() -> None:
    # Drop triggers + functions
    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable_trg ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_forbid_mutation()")

    # Drop policies finas (idempotent)
    for table, pols in (
        (
            "products",
            (
                "products_finas_read",
                "products_finas_write_comercial",
                "products_finas_update_comercial",
                "products_finas_delete_ti",
            ),
        ),
        (
            "costs",
            (
                "costs_finas_read",
                "costs_finas_insert_comercial",
                "costs_finas_update_gerente",
                "costs_finas_delete_ti",
            ),
        ),
        (
            "prices",
            (
                "prices_finas_read",
                "prices_finas_insert_comercial",
                "prices_finas_update_gerente",
                "prices_finas_update_comercial_draft",
                "prices_finas_delete_ti",
            ),
        ),
        (
            "audit_events",
            (
                "audit_events_finas_read",
                "audit_events_finas_insert",
            ),
        ),
    ):
        for pol in pols:
            op.execute(f"DROP POLICY IF EXISTS {pol} ON {table}")

    op.execute("DROP FUNCTION IF EXISTS resolve_user_role()")
