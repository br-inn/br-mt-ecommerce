-- =============================================================================
-- 20260513_103_rls_select_wrapper.sql
-- Re-crea las policies RLS con (SELECT resolve_user_role()) para que el
-- planner evalúe la función una sola vez (init plan) en lugar de por cada fila.
--
-- Impacto: 5-10x más rápido en tablas con muchas filas.
-- Ref: security-rls-performance best practice.
-- Mirror de: alembic/versions/20260513_103_rls_select_wrapper.py
-- =============================================================================

-- PRODUCTS
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

-- COSTS
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

-- PRICES
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

-- AUDIT_EVENTS
DROP POLICY IF EXISTS audit_events_finas_read   ON audit_events;
DROP POLICY IF EXISTS audit_events_finas_insert ON audit_events;

CREATE POLICY audit_events_finas_read ON audit_events FOR SELECT TO mt_app
    USING ((SELECT resolve_user_role()) IN
        ('gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

CREATE POLICY audit_events_finas_insert ON audit_events FOR INSERT TO mt_app
    WITH CHECK ((SELECT resolve_user_role()) IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

-- USERS — current_user_id() + current_role_code()
DROP POLICY IF EXISTS users_self_read    ON users;
DROP POLICY IF EXISTS users_manager_read ON users;
DROP POLICY IF EXISTS users_ti_full      ON users;

CREATE POLICY users_self_read ON users FOR SELECT TO mt_app
    USING (id = (SELECT current_user_id()));

CREATE POLICY users_manager_read ON users FOR SELECT TO mt_app
    USING ((SELECT current_role_code()) IN ('gerente_comercial','ti_integracion','admin'));

CREATE POLICY users_ti_full ON users FOR ALL TO mt_app
    USING ((SELECT current_role_code()) IN ('ti_integracion','admin'))
    WITH CHECK ((SELECT current_role_code()) IN ('ti_integracion','admin'));
