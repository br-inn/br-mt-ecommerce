-- =============================================================================
-- 20260507_005_currencies_suppliers_schemes_rls.sql
--
-- Mirror Supabase de las RLS policies para `currencies`, `suppliers`, `schemes`
-- creadas en Alembic 20260507_004. Mantenemos este archivo separado para que
-- Supabase Studio / supabase CLI puedan re-aplicar las policies sin pasar por
-- Alembic (útil cuando se rehidrata un branch staging).
--
-- DDL de tablas + seeds vive en Alembic — esta migración asume que las tablas
-- ya existen. Si no, falla noisy con error claro.
--
-- US-1A-03-01 (currencies + suppliers), US-1A-04-01 (schemes).
-- =============================================================================

-- 0. Sanity check: las tablas deben existir antes de habilitar RLS.
DO $$
BEGIN
    IF to_regclass('public.currencies') IS NULL THEN
        RAISE EXCEPTION 'Tabla currencies no existe — corre Alembic 20260507_004 primero.';
    END IF;
    IF to_regclass('public.suppliers') IS NULL THEN
        RAISE EXCEPTION 'Tabla suppliers no existe — corre Alembic 20260507_004 primero.';
    END IF;
    IF to_regclass('public.schemes') IS NULL THEN
        RAISE EXCEPTION 'Tabla schemes no existe — corre Alembic 20260507_004 primero.';
    END IF;
END
$$;

-- =============================================================================
-- CURRENCIES — read-all-auth, write admin/TI sólo (catálogo cerrado en S2).
-- =============================================================================
ALTER TABLE currencies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS currencies_read_all ON currencies;
CREATE POLICY currencies_read_all ON currencies
    FOR SELECT TO mt_app USING (true);

DROP POLICY IF EXISTS currencies_ti_write ON currencies;
CREATE POLICY currencies_ti_write ON currencies
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));

-- =============================================================================
-- SUPPLIERS — read-all-auth, write comercial+ (replica patrón products).
-- =============================================================================
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS suppliers_read_all ON suppliers;
CREATE POLICY suppliers_read_all ON suppliers
    FOR SELECT TO mt_app USING (true);

DROP POLICY IF EXISTS suppliers_write_comercial ON suppliers;
CREATE POLICY suppliers_write_comercial ON suppliers
    FOR ALL TO mt_app
    USING (current_role_code() IN ('comercial','ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('comercial','ti_integracion','admin'));

-- =============================================================================
-- SCHEMES — read-all-auth, write admin/TI sólo (5 schemes inmutables seeded).
-- =============================================================================
ALTER TABLE schemes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS schemes_read_all ON schemes;
CREATE POLICY schemes_read_all ON schemes
    FOR SELECT TO mt_app USING (true);

DROP POLICY IF EXISTS schemes_ti_write ON schemes;
CREATE POLICY schemes_ti_write ON schemes
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));
