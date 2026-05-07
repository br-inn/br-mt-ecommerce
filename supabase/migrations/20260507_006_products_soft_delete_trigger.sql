-- =============================================================================
-- 20260507_006_products_soft_delete_trigger.sql
--
-- Mirror Supabase del trigger soft-delete creado por Alembic 20260507_005.
-- Bloquea DELETE físico en `products` para cumplir VAT UAE 7-año retention
-- (BR-1a-07, NFR-35).
--
-- Aplicable también a `costs`, `prices`, `suppliers` en sus respectivos sprints.
--
-- US-1A-02-10.
-- =============================================================================

-- 0. Sanity check.
DO $$
BEGIN
    IF to_regclass('public.products') IS NULL THEN
        RAISE EXCEPTION 'Tabla products no existe — corre Alembic primero.';
    END IF;
END
$$;

-- 1. Función reusable.
CREATE OR REPLACE FUNCTION raise_use_soft_delete()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'DELETE físico bloqueado por compliance VAT UAE (NFR-35). '
        'Use UPDATE para set active=false (soft-deactivate).'
        USING ERRCODE = 'P0001';
END
$$;

COMMENT ON FUNCTION raise_use_soft_delete() IS
    'Bloquea DELETE físico en tablas con audit trail VAT-compliant. '
    'Aplicar via BEFORE DELETE trigger row-level. US-1A-02-10.';

-- 2. Trigger sobre products.
DROP TRIGGER IF EXISTS trg_products_no_hard_delete ON products;
CREATE TRIGGER trg_products_no_hard_delete
    BEFORE DELETE ON products
    FOR EACH ROW
    EXECUTE FUNCTION raise_use_soft_delete();
