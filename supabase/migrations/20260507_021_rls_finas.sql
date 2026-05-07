-- =============================================================================
-- 20260507_021_rls_finas.sql
-- Mirror Supabase de las RLS finas declaradas en Alembic 20260507_022.
--
-- Sprint 4 (US-1A-07-02): RLS endurecidas para products / costs / prices /
-- audit_events. Roles soportados:
--   * comercial
--   * gerente (alias: gerente_comercial)
--   * ti (alias: ti_integracion, admin)
--   * auditor (NUEVO en S4 — read-only timeline auditoría)
--
-- IMPORTANTE: este archivo se mantiene separado para que Supabase Studio /
-- supabase CLI puedan re-aplicar las policies sin pasar por Alembic
-- (rehidratación de branch staging). DDL de tablas vive en Alembic.
--
-- Helper resolve_user_role(): lee `app.user_role` (set por backend) con
-- fallback a `request.jwt.claims->>role` (Supabase JWT). Defense-in-depth.
-- =============================================================================

-- 0. Sanity check
DO $$
BEGIN
    IF to_regclass('public.products') IS NULL THEN
        RAISE EXCEPTION 'Tabla products no existe — corre Alembic primero.';
    END IF;
    IF to_regclass('public.costs') IS NULL THEN
        RAISE EXCEPTION 'Tabla costs no existe — corre Alembic 20260507_018 primero.';
    END IF;
    IF to_regclass('public.prices') IS NULL THEN
        RAISE EXCEPTION 'Tabla prices no existe — corre Alembic 20260507_010 primero.';
    END IF;
    IF to_regclass('public.audit_events') IS NULL THEN
        RAISE EXCEPTION 'Tabla audit_events no existe — corre Alembic 20260506_001 primero.';
    END IF;
END
$$;

-- =============================================================================
-- helper resolve_user_role()
-- =============================================================================
CREATE OR REPLACE FUNCTION resolve_user_role() RETURNS TEXT
LANGUAGE plpgsql STABLE AS $fn$
DECLARE
    r TEXT;
BEGIN
    BEGIN
        r := NULLIF(current_setting('app.user_role', true), '');
    EXCEPTION WHEN OTHERS THEN
        r := NULL;
    END;
    IF r IS NOT NULL THEN
        RETURN r;
    END IF;
    BEGIN
        r := current_setting('request.jwt.claims', true)::json->>'role';
    EXCEPTION WHEN OTHERS THEN
        r := NULL;
    END;
    RETURN NULLIF(r, '');
END;
$fn$;

-- =============================================================================
-- PRODUCTS
-- =============================================================================
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS products_read_all ON products;
DROP POLICY IF EXISTS products_write_comercial ON products;
DROP POLICY IF EXISTS products_finas_read ON products;
DROP POLICY IF EXISTS products_finas_write_comercial ON products;
DROP POLICY IF EXISTS products_finas_update_comercial ON products;
DROP POLICY IF EXISTS products_finas_delete_ti ON products;

CREATE POLICY products_finas_read ON products
    FOR SELECT TO mt_app
    USING (resolve_user_role() IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

CREATE POLICY products_finas_write_comercial ON products
    FOR INSERT TO mt_app
    WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));

CREATE POLICY products_finas_update_comercial ON products
    FOR UPDATE TO mt_app
    USING (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'))
    WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));

CREATE POLICY products_finas_delete_ti ON products
    FOR DELETE TO mt_app
    USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

-- =============================================================================
-- COSTS
-- =============================================================================
ALTER TABLE costs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS costs_read_all ON costs;
DROP POLICY IF EXISTS costs_write_comercial ON costs;
DROP POLICY IF EXISTS costs_finas_read ON costs;
DROP POLICY IF EXISTS costs_finas_insert_comercial ON costs;
DROP POLICY IF EXISTS costs_finas_update_gerente ON costs;
DROP POLICY IF EXISTS costs_finas_delete_ti ON costs;

CREATE POLICY costs_finas_read ON costs
    FOR SELECT TO mt_app
    USING (resolve_user_role() IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

CREATE POLICY costs_finas_insert_comercial ON costs
    FOR INSERT TO mt_app
    WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));

CREATE POLICY costs_finas_update_gerente ON costs
    FOR UPDATE TO mt_app
    USING (resolve_user_role() IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'))
    WITH CHECK (resolve_user_role() IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'));

CREATE POLICY costs_finas_delete_ti ON costs
    FOR DELETE TO mt_app
    USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

-- =============================================================================
-- PRICES
-- =============================================================================
ALTER TABLE prices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS prices_read_all ON prices;
DROP POLICY IF EXISTS prices_finas_read ON prices;
DROP POLICY IF EXISTS prices_finas_insert_comercial ON prices;
DROP POLICY IF EXISTS prices_finas_update_gerente ON prices;
DROP POLICY IF EXISTS prices_finas_update_comercial_draft ON prices;
DROP POLICY IF EXISTS prices_finas_delete_ti ON prices;

CREATE POLICY prices_finas_read ON prices
    FOR SELECT TO mt_app
    USING (resolve_user_role() IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

-- Comercial sólo puede INSERT con status='draft'.
CREATE POLICY prices_finas_insert_comercial ON prices
    FOR INSERT TO mt_app
    WITH CHECK (
        resolve_user_role() IN ('comercial','ti','ti_integracion','admin')
        AND (
            resolve_user_role() IN ('ti','ti_integracion','admin')
            OR status = 'draft'
        )
    );

-- Gerente / TI: UPDATE libre.
CREATE POLICY prices_finas_update_gerente ON prices
    FOR UPDATE TO mt_app
    USING (resolve_user_role() IN ('gerente','gerente_comercial','ti','ti_integracion','admin'))
    WITH CHECK (resolve_user_role() IN
        ('gerente','gerente_comercial','ti','ti_integracion','admin'));

-- Comercial sólo UPDATE si status sigue en draft.
CREATE POLICY prices_finas_update_comercial_draft ON prices
    FOR UPDATE TO mt_app
    USING (resolve_user_role() = 'comercial' AND status = 'draft')
    WITH CHECK (resolve_user_role() = 'comercial' AND status = 'draft');

CREATE POLICY prices_finas_delete_ti ON prices
    FOR DELETE TO mt_app
    USING (resolve_user_role() IN ('ti','ti_integracion','admin'));

-- =============================================================================
-- AUDIT_EVENTS — append-only enforcement
-- =============================================================================
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_events_read ON audit_events;
DROP POLICY IF EXISTS audit_events_insert ON audit_events;
DROP POLICY IF EXISTS audit_events_finas_read ON audit_events;
DROP POLICY IF EXISTS audit_events_finas_insert ON audit_events;

-- Comercial NO lee audit log.
CREATE POLICY audit_events_finas_read ON audit_events
    FOR SELECT TO mt_app
    USING (resolve_user_role() IN
        ('gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

-- Insert: cualquier rol autenticado puede registrar.
CREATE POLICY audit_events_finas_insert ON audit_events
    FOR INSERT TO mt_app
    WITH CHECK (resolve_user_role() IN
        ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));

-- Append-only: BEFORE UPDATE OR DELETE → raise.
CREATE OR REPLACE FUNCTION audit_events_forbid_mutation()
RETURNS TRIGGER AS $fn$
BEGIN
    RAISE EXCEPTION
      'forbidden_audit_mutation: audit_events es append-only.'
      USING ERRCODE = 'insufficient_privilege';
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_events_immutable_trg ON audit_events;
CREATE TRIGGER audit_events_immutable_trg
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION audit_events_forbid_mutation();
