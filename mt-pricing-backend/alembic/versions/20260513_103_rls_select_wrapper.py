"""rls_select_wrapper — re-crea policies RLS con (SELECT resolve_user_role()).

Las policies RLS de las migs. 003/021/022 llaman a resolve_user_role() sin
wrapper SELECT. Postgres puede evaluar la función por cada fila del plan de
ejecución. Con (SELECT resolve_user_role()), el planner crea un "init plan"
que evalúa la función una sola vez y cachea el resultado — 5-10x más rápido
en tablas con muchas filas.

Lo mismo aplica a current_user_id() y current_role_code() en la mig. 003.

Ref: security-rls-performance best practice (Supabase Postgres).

Revision ID: 20260513_103
Revises: 20260513_102
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260513_103"
down_revision: str = "20260513_102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        -- ======================================================
        -- PRODUCTS (mig. 021)
        -- ======================================================
        DROP POLICY IF EXISTS products_finas_read              ON products;
        DROP POLICY IF EXISTS products_finas_write_comercial   ON products;
        DROP POLICY IF EXISTS products_finas_update_comercial  ON products;
        DROP POLICY IF EXISTS products_finas_delete_ti         ON products;

        CREATE POLICY products_finas_read ON products FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY products_finas_write_comercial ON products FOR INSERT TO mt_app
            WITH CHECK ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'));

        CREATE POLICY products_finas_update_comercial ON products FOR UPDATE TO mt_app
            USING  ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'))
            WITH CHECK ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'));

        CREATE POLICY products_finas_delete_ti ON products FOR DELETE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('ti','ti_integracion','admin'));

        -- ======================================================
        -- COSTS (mig. 021)
        -- ======================================================
        DROP POLICY IF EXISTS costs_finas_read               ON costs;
        DROP POLICY IF EXISTS costs_finas_insert_comercial   ON costs;
        DROP POLICY IF EXISTS costs_finas_update_gerente     ON costs;
        DROP POLICY IF EXISTS costs_finas_delete_ti          ON costs;

        CREATE POLICY costs_finas_read ON costs FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY costs_finas_insert_comercial ON costs FOR INSERT TO mt_app
            WITH CHECK ((SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin'));

        CREATE POLICY costs_finas_update_gerente ON costs FOR UPDATE TO mt_app
            USING  ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'));

        CREATE POLICY costs_finas_delete_ti ON costs FOR DELETE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('ti','ti_integracion','admin'));

        -- ======================================================
        -- PRICES (mig. 021)
        -- ======================================================
        DROP POLICY IF EXISTS prices_finas_read                   ON prices;
        DROP POLICY IF EXISTS prices_finas_insert_comercial       ON prices;
        DROP POLICY IF EXISTS prices_finas_update_gerente         ON prices;
        DROP POLICY IF EXISTS prices_finas_update_comercial_draft ON prices;
        DROP POLICY IF EXISTS prices_finas_delete_ti              ON prices;

        CREATE POLICY prices_finas_read ON prices FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY prices_finas_insert_comercial ON prices FOR INSERT TO mt_app
            WITH CHECK (
                (SELECT resolve_user_role()) IN ('comercial','ti','ti_integracion','admin')
                AND (
                    (SELECT resolve_user_role()) IN ('ti','ti_integracion','admin')
                    OR status = 'draft'
                )
            );

        CREATE POLICY prices_finas_update_gerente ON prices FOR UPDATE TO mt_app
            USING  ((SELECT resolve_user_role()) IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK ((SELECT resolve_user_role()) IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin'));

        CREATE POLICY prices_finas_update_comercial_draft ON prices FOR UPDATE TO mt_app
            USING  ((SELECT resolve_user_role()) = 'comercial' AND status = 'draft')
            WITH CHECK ((SELECT resolve_user_role()) = 'comercial' AND status = 'draft');

        CREATE POLICY prices_finas_delete_ti ON prices FOR DELETE TO mt_app
            USING ((SELECT resolve_user_role()) IN ('ti','ti_integracion','admin'));

        -- ======================================================
        -- AUDIT_EVENTS (mig. 021)
        -- ======================================================
        DROP POLICY IF EXISTS audit_events_finas_read   ON audit_events;
        DROP POLICY IF EXISTS audit_events_finas_insert ON audit_events;

        CREATE POLICY audit_events_finas_read ON audit_events FOR SELECT TO mt_app
            USING ((SELECT resolve_user_role()) IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        CREATE POLICY audit_events_finas_insert ON audit_events FOR INSERT TO mt_app
            WITH CHECK ((SELECT resolve_user_role()) IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        -- USERS: current_user_id() es función Supabase-only (mig. 003 SQL).
        -- Su re-creación con wrapper va exclusivamente en
        -- supabase/migrations/20260513_103_rls_select_wrapper.sql.
    """)


def downgrade() -> None:
    # Restaurar sin wrapper (estado pre-mig 103).
    op.execute("""
        DROP POLICY IF EXISTS products_finas_read              ON products;
        DROP POLICY IF EXISTS products_finas_write_comercial   ON products;
        DROP POLICY IF EXISTS products_finas_update_comercial  ON products;
        DROP POLICY IF EXISTS products_finas_delete_ti         ON products;

        CREATE POLICY products_finas_read ON products FOR SELECT TO mt_app
            USING (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));
        CREATE POLICY products_finas_write_comercial ON products FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));
        CREATE POLICY products_finas_update_comercial ON products FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));
        CREATE POLICY products_finas_delete_ti ON products FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

        DROP POLICY IF EXISTS costs_finas_read               ON costs;
        DROP POLICY IF EXISTS costs_finas_insert_comercial   ON costs;
        DROP POLICY IF EXISTS costs_finas_update_gerente     ON costs;
        DROP POLICY IF EXISTS costs_finas_delete_ti          ON costs;

        CREATE POLICY costs_finas_read ON costs FOR SELECT TO mt_app
            USING (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));
        CREATE POLICY costs_finas_insert_comercial ON costs FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));
        CREATE POLICY costs_finas_update_gerente ON costs FOR UPDATE TO mt_app
            USING (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'));
        CREATE POLICY costs_finas_delete_ti ON costs FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

        DROP POLICY IF EXISTS prices_finas_read                   ON prices;
        DROP POLICY IF EXISTS prices_finas_insert_comercial       ON prices;
        DROP POLICY IF EXISTS prices_finas_update_gerente         ON prices;
        DROP POLICY IF EXISTS prices_finas_update_comercial_draft ON prices;
        DROP POLICY IF EXISTS prices_finas_delete_ti              ON prices;

        CREATE POLICY prices_finas_read ON prices FOR SELECT TO mt_app
            USING (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));
        CREATE POLICY prices_finas_insert_comercial ON prices FOR INSERT TO mt_app
            WITH CHECK (
                resolve_user_role() IN ('comercial','ti','ti_integracion','admin')
                AND (resolve_user_role() IN ('ti','ti_integracion','admin') OR status = 'draft')
            );
        CREATE POLICY prices_finas_update_gerente ON prices FOR UPDATE TO mt_app
            USING (resolve_user_role() IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin'));
        CREATE POLICY prices_finas_update_comercial_draft ON prices FOR UPDATE TO mt_app
            USING (resolve_user_role() = 'comercial' AND status = 'draft')
            WITH CHECK (resolve_user_role() = 'comercial' AND status = 'draft');
        CREATE POLICY prices_finas_delete_ti ON prices FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

        DROP POLICY IF EXISTS audit_events_finas_read   ON audit_events;
        DROP POLICY IF EXISTS audit_events_finas_insert ON audit_events;

        CREATE POLICY audit_events_finas_read ON audit_events FOR SELECT TO mt_app
            USING (resolve_user_role() IN
                ('gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));
        CREATE POLICY audit_events_finas_insert ON audit_events FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN
                ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

        -- USERS: mantenido en supabase/migrations (current_user_id Supabase-only).
    """)
