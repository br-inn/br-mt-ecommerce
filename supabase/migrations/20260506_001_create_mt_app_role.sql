-- =============================================================================
-- 20260506_001_create_mt_app_role.sql
-- ADR-031 (Supabase + uuidv7) + mt-users-module-design §5.1.6 (RLS)
--
-- Crea el rol Postgres `mt_app` (sin elevar privilegios) que usa el backend
-- FastAPI para CRUD aplicativo. Respeta RLS — políticas concretas en
-- 20260506_003_rls_policies.sql.
--
-- También crea `mt_migrate` para Alembic (DDL) — rol separado para auditar
-- migraciones distintas del tráfico aplicativo.
-- =============================================================================

-- 1. Rol aplicativo (sujeto a RLS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') THEN
        CREATE ROLE mt_app NOLOGIN NOINHERIT;
    END IF;
END
$$;

-- Permite que `authenticator` (rol Supabase del API gateway) asuma `mt_app`.
GRANT mt_app TO authenticator;

-- 2. Rol DDL (Alembic) — sí puede crear/alterar tablas en `public`.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mt_migrate') THEN
        CREATE ROLE mt_migrate NOLOGIN;
    END IF;
END
$$;

-- 3. Privilegios mínimos sobre schema public para mt_app
GRANT USAGE ON SCHEMA public TO mt_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mt_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO mt_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO mt_app;

-- 4. Privilegios DDL para mt_migrate
GRANT ALL ON SCHEMA public TO mt_migrate;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO mt_migrate;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO mt_migrate;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON FUNCTIONS TO mt_migrate;

-- 5. Aplicar privilegios a tablas EXISTENTES (la migración Alembic ya las creó).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mt_app;

-- mt_app NO debe poder bypassear RLS:
ALTER ROLE mt_app NOBYPASSRLS;
ALTER ROLE mt_migrate BYPASSRLS;  -- DDL/seeds requieren bypass

-- 6. Comentarios documentales
COMMENT ON ROLE mt_app IS 'Backend FastAPI runtime role. RLS-restricted. ADR-031.';
COMMENT ON ROLE mt_migrate IS 'Alembic DDL role. BYPASSRLS for migrations & seeds.';
