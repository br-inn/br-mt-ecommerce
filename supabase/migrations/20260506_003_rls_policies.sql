-- =============================================================================
-- 20260506_003_rls_policies.sql
-- RLS básicas Sprint 1 (ver mt-users-module-design §5.1.6 + matriz PRD).
--
-- Estrategia (defensa en profundidad, ADR-049):
--   - Cada tabla con datos sensibles tiene RLS ENABLE.
--   - El JWT de Supabase (auth.jwt()) trae `role` (code) y `sub` (user.id).
--   - El backend FastAPI puede asumir mt_app (sujeto a RLS); las tasks
--     Celery con bypass usan service_role explícito.
-- =============================================================================

-- ---------- helper: leer rol del JWT ----------
CREATE OR REPLACE FUNCTION current_role_code() RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('request.jwt.claims', true)::json->>'role','');
$$;

CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('request.jwt.claims', true)::json->>'sub','')::uuid;
$$;

-- =============================================================================
-- USERS
-- =============================================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Cada usuario puede leer SU perfil
CREATE POLICY users_self_read ON users
    FOR SELECT TO mt_app
    USING (id = current_user_id());

-- Gerente comercial puede leer todos los perfiles (read-only)
CREATE POLICY users_manager_read ON users
    FOR SELECT TO mt_app
    USING (current_role_code() IN ('gerente_comercial','ti_integracion','admin'));

-- TI Integración + admin: full CRUD
CREATE POLICY users_ti_full ON users
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));

-- =============================================================================
-- ROLES + PERMISSIONS + ROLE_PERMISSIONS
-- =============================================================================
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;

-- Lectura: cualquier usuario autenticado (catálogo de roles es público interno)
CREATE POLICY roles_read_all ON roles
    FOR SELECT TO mt_app USING (true);
CREATE POLICY permissions_read_all ON permissions
    FOR SELECT TO mt_app USING (true);
CREATE POLICY role_permissions_read_all ON role_permissions
    FOR SELECT TO mt_app USING (true);

-- Escritura: sólo TI/admin
CREATE POLICY roles_ti_write ON roles
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));

CREATE POLICY permissions_ti_write ON permissions
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));

CREATE POLICY role_permissions_ti_write ON role_permissions
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));

-- =============================================================================
-- PRODUCTS + product_translations + product_images
-- =============================================================================
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_translations ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_images ENABLE ROW LEVEL SECURITY;

-- Read: todos los roles autenticados
CREATE POLICY products_read_all ON products FOR SELECT TO mt_app USING (true);
CREATE POLICY product_translations_read_all ON product_translations FOR SELECT TO mt_app USING (true);
CREATE POLICY product_images_read_all ON product_images FOR SELECT TO mt_app USING (true);

-- Write: comercial + TI/admin
CREATE POLICY products_write_comercial ON products
    FOR ALL TO mt_app
    USING (current_role_code() IN ('comercial','ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('comercial','ti_integracion','admin'));

CREATE POLICY product_translations_write_comercial ON product_translations
    FOR ALL TO mt_app
    USING (current_role_code() IN ('comercial','ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('comercial','ti_integracion','admin'));

CREATE POLICY product_images_write_comercial ON product_images
    FOR ALL TO mt_app
    USING (current_role_code() IN ('comercial','ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('comercial','ti_integracion','admin'));

-- =============================================================================
-- AUDIT_EVENTS — append-only via trigger; RLS sólo controla lectura.
-- =============================================================================
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

-- Lectura: gerente, TI, admin. Comercial NO ve audit log.
CREATE POLICY audit_events_read ON audit_events
    FOR SELECT TO mt_app
    USING (current_role_code() IN ('gerente_comercial','ti_integracion','admin'));

-- INSERT: cualquier rol autenticado puede registrar evento (lo dispara la app).
CREATE POLICY audit_events_insert ON audit_events
    FOR INSERT TO mt_app
    WITH CHECK (true);

-- =============================================================================
-- JOB_DEFINITIONS + JOB_RUNS
-- =============================================================================
ALTER TABLE job_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY job_definitions_read ON job_definitions
    FOR SELECT TO mt_app
    USING (current_role_code() IN ('gerente_comercial','ti_integracion','admin'));

CREATE POLICY job_definitions_write ON job_definitions
    FOR ALL TO mt_app
    USING (current_role_code() IN ('ti_integracion','admin'))
    WITH CHECK (current_role_code() IN ('ti_integracion','admin'));

CREATE POLICY job_runs_read ON job_runs
    FOR SELECT TO mt_app
    USING (current_role_code() IN ('gerente_comercial','ti_integracion','admin'));

-- job_runs INSERT lo hace exclusivamente el scheduler (service_role bypass RLS).
-- No creamos política INSERT para mt_app — bloqueado por RLS.
