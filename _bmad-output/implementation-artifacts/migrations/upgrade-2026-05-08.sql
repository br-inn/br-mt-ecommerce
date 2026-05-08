BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20260506_001

CREATE EXTENSION IF NOT EXISTS pgcrypto;;

CREATE EXTENSION IF NOT EXISTS pg_trgm;;

CREATE EXTENSION IF NOT EXISTS citext;;

CREATE EXTENSION IF NOT EXISTS vector;;

CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END
        $$;;

CREATE TABLE roles (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code TEXT NOT NULL, 
    name TEXT NOT NULL, 
    description TEXT, 
    is_system BOOLEAN DEFAULT true NOT NULL, 
    permissions_snapshot JSONB DEFAULT '[]'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE INDEX idx_roles_code ON roles (code);

CREATE TABLE permissions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code TEXT NOT NULL, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL, 
    permission_id UUID NOT NULL, 
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (role_id, permission_id), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
    FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE users (
    id UUID NOT NULL, 
    email CITEXT NOT NULL, 
    full_name TEXT, 
    avatar_url TEXT, 
    locale VARCHAR(2) DEFAULT 'es' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    role_id UUID, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    failed_logins INTEGER DEFAULT 0 NOT NULL, 
    locked_until TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_by UUID, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_users_locale CHECK (locale IN ('es','en','ar')), 
    UNIQUE (email), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_users_role ON users (role_id);

CREATE INDEX idx_users_active ON users (is_active) WHERE is_active = true;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TRIGGER trg_roles_updated_at BEFORE UPDATE ON roles FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE products (
    sku TEXT NOT NULL, 
    internal_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    name_en TEXT NOT NULL, 
    description_en TEXT, 
    marketing_copy_en TEXT, 
    family TEXT NOT NULL, 
    subfamily TEXT, 
    type TEXT, 
    material TEXT, 
    dn TEXT, 
    pn TEXT, 
    connection TEXT, 
    brand TEXT, 
    specs JSONB DEFAULT '{}'::jsonb NOT NULL, 
    dimensions JSONB DEFAULT '{}'::jsonb NOT NULL, 
    packaging JSONB DEFAULT '{}'::jsonb NOT NULL, 
    weight NUMERIC(12, 4), 
    weight_unit VARCHAR(8) DEFAULT 'kg', 
    intrastat_code TEXT, 
    erp_name TEXT, 
    image_url TEXT, 
    image_origin_url TEXT, 
    image_status VARCHAR(16) DEFAULT 'missing' NOT NULL, 
    data_quality VARCHAR(16) DEFAULT 'partial' NOT NULL, 
    manual_locked_fields TEXT[] DEFAULT '{}'::text[] NOT NULL, 
    active BOOLEAN DEFAULT true NOT NULL, 
    embedding_text FLOAT[], 
    embedding_image FLOAT[], 
    embedding_model TEXT, 
    embedding_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_by UUID, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_by UUID, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (sku), 
    CONSTRAINT ck_products_data_quality CHECK (data_quality IN ('complete','partial','blocked','migrated_demo')), 
    CONSTRAINT ck_products_image_status CHECK (image_status IN ('missing','mirrored','failed')), 
    UNIQUE (internal_id), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_products_family ON products (family);

CREATE INDEX idx_products_brand ON products (brand);

CREATE INDEX idx_products_active ON products (active) WHERE active = true;

CREATE INDEX idx_products_specs_gin ON products USING gin (specs);

CREATE INDEX idx_products_name_trgm ON products USING gin (name_en gin_trgm_ops);;

CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE product_translations (
    sku TEXT NOT NULL, 
    lang VARCHAR(2) NOT NULL, 
    name TEXT, 
    description TEXT, 
    marketing_copy TEXT, 
    status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
    translated_by UUID, 
    translated_at TIMESTAMP WITH TIME ZONE, 
    reviewed_by UUID, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (sku, lang), 
    CONSTRAINT ck_translations_lang CHECK (lang IN ('es','ar','en')), 
    CONSTRAINT ck_translations_status CHECK (status IN ('pending','draft','approved')), 
    FOREIGN KEY(sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(translated_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_translations_status ON product_translations (lang, status);

CREATE TRIGGER trg_product_translations_updated_at BEFORE UPDATE ON product_translations FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE product_images (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    sku TEXT NOT NULL, 
    role TEXT NOT NULL, 
    storage_path TEXT NOT NULL, 
    original_url TEXT, 
    is_primary BOOLEAN DEFAULT false NOT NULL, 
    alt_text TEXT, 
    width INTEGER, 
    height INTEGER, 
    bytes_size BIGINT, 
    mime_type TEXT, 
    hash_sha256 TEXT, 
    status VARCHAR(16) DEFAULT 'active' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_by UUID, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_images_status CHECK (status IN ('active','archived','broken')), 
    FOREIGN KEY(sku) REFERENCES products (sku) ON DELETE CASCADE, 
    UNIQUE (storage_path), 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_images_sku_role ON product_images (sku, role);

CREATE INDEX idx_product_images_hash ON product_images (hash_sha256);

CREATE TABLE audit_events (
            id            BIGSERIAL,
            event_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            actor_id      UUID REFERENCES users(id) ON DELETE SET NULL,
            actor_email   TEXT,
            actor_role    TEXT,
            entity_type   TEXT NOT NULL,
            entity_id     TEXT NOT NULL,
            action        TEXT NOT NULL,
            before        JSONB,
            after         JSONB,
            payload_diff  JSONB NOT NULL DEFAULT '{}'::jsonb,
            reason        TEXT,
            prev_hash     VARCHAR(64),
            current_hash  VARCHAR(64),
            request_id    TEXT,
            ip_address    INET,
            user_agent    TEXT,
            CONSTRAINT pk_audit_events PRIMARY KEY (id, event_at)
        ) PARTITION BY RANGE (event_at);;

CREATE INDEX idx_audit_entity ON audit_events (entity_type, entity_id, event_at);;

CREATE INDEX idx_audit_actor ON audit_events (actor_id, event_at);;

CREATE INDEX idx_audit_action ON audit_events (action, event_at);;

CREATE INDEX idx_audit_request ON audit_events (request_id);;

CREATE TABLE audit_events_2026_05 PARTITION OF audit_events
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');;

CREATE TABLE audit_events_2026_06 PARTITION OF audit_events
        FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');;

CREATE TABLE job_definitions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code TEXT NOT NULL, 
    task_name TEXT NOT NULL, 
    description TEXT, 
    owner VARCHAR(16) DEFAULT 'infra' NOT NULL, 
    schedule_type VARCHAR(16) NOT NULL, 
    cron_expression TEXT, 
    interval_seconds INTEGER, 
    timezone TEXT DEFAULT 'Asia/Dubai' NOT NULL, 
    queue TEXT DEFAULT 'default' NOT NULL, 
    args JSONB DEFAULT '[]'::jsonb NOT NULL, 
    kwargs JSONB DEFAULT '{}'::jsonb NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    last_run_at TIMESTAMP WITH TIME ZONE, 
    next_run_at TIMESTAMP WITH TIME ZONE, 
    last_status VARCHAR(16), 
    last_error TEXT, 
    last_celery_task_id TEXT, 
    edited_by UUID, 
    edited_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_jobs_owner CHECK (owner IN ('infra','business')), 
    CONSTRAINT ck_jobs_schedule_type CHECK (schedule_type IN ('cron','interval')), 
    CONSTRAINT ck_jobs_schedule_complete CHECK ((schedule_type='cron' AND cron_expression IS NOT NULL) OR (schedule_type='interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)), 
    CONSTRAINT ck_jobs_last_status CHECK (last_status IS NULL OR last_status IN ('idle','running','success','failure','cancelled')), 
    UNIQUE (code), 
    FOREIGN KEY(edited_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_jobs_enabled ON job_definitions (enabled) WHERE enabled = true;

CREATE INDEX idx_jobs_next_run ON job_definitions (next_run_at);

CREATE TRIGGER trg_job_definitions_updated_at BEFORE UPDATE ON job_definitions FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE job_runs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    job_id UUID NOT NULL, 
    job_code TEXT NOT NULL, 
    status VARCHAR(16) DEFAULT 'idle' NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    retries INTEGER DEFAULT 0 NOT NULL, 
    celery_task_id TEXT, 
    result JSONB, 
    error TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_job_runs_status CHECK (status IN ('idle','running','success','failure','cancelled')), 
    FOREIGN KEY(job_id) REFERENCES job_definitions (id) ON DELETE CASCADE
);

CREATE INDEX idx_job_runs_job_started ON job_runs (job_id, started_at);

CREATE INDEX idx_job_runs_running ON job_runs (status) WHERE status IN ('idle','running');

CREATE TRIGGER trg_job_runs_updated_at BEFORE UPDATE ON job_runs FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

INSERT INTO roles (code, name, description, is_system) VALUES
            ('comercial','Comercial Canal Online & Marketplaces','CRUD catálogo, propone precios',true),
            ('gerente_comercial','Gerente Comercial','Aprueba excepciones, define reglas',true),
            ('ti_integracion','TI Integración','Configura connectors, gestiona usuarios',true),
            ('admin','Sysadmin','BR Innovation / TI MT inicial',true);;

INSERT INTO permissions (code, description) VALUES
            ('products:read','Leer catálogo'),
            ('products:write','Editar catálogo'),
            ('prices:read','Leer precios'),
            ('prices:propose','Proponer precios'),
            ('prices:approve','Aprobar precios'),
            ('costs:read','Leer costes'),
            ('costs:write','Editar costes'),
            ('rules:read','Leer reglas'),
            ('rules:write','Editar reglas'),
            ('users:read','Leer usuarios'),
            ('users:write','Crear/editar usuarios'),
            ('jobs:read','Leer jobs'),
            ('jobs:write','Editar jobs'),
            ('audit:read','Leer audit log');;

WITH r AS (SELECT id, code FROM roles), p AS (SELECT id, code FROM permissions)
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM r CROSS JOIN p
        WHERE
            (r.code = 'comercial' AND p.code IN (
                'products:read','products:write','prices:read','prices:propose',
                'costs:read','rules:read'))
         OR (r.code = 'gerente_comercial' AND p.code IN (
                'products:read','prices:read','prices:approve','costs:read',
                'rules:read','rules:write','audit:read'))
         OR (r.code = 'ti_integracion' AND p.code IN (
                'products:read','prices:read','costs:read','users:read','users:write',
                'jobs:read','jobs:write','audit:read'))
         OR (r.code = 'admin');;

INSERT INTO job_definitions
            (code, task_name, description, owner, schedule_type, cron_expression, queue, enabled)
        VALUES
            ('audit_partitions_ensure',
             'app.workers.tasks.audit.ensure_partitions',
             'Crea partición del mes siguiente para audit_events',
             'infra', 'cron', '0 2 1 * *', 'default', true);;

INSERT INTO alembic_version (version_num) VALUES ('20260506_001') RETURNING alembic_version.version_num;

-- Running upgrade 20260506_001 -> 20260506_002

INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__imports',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue imports (ADR-048)',
                 'infra', 'interval', 30, 'imports', true,
                 '[]'::jsonb, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING;;

INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__pricing',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue pricing (ADR-048)',
                 'infra', 'interval', 30, 'pricing', true,
                 '[]'::jsonb, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING;;

INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__images',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue images (ADR-048)',
                 'infra', 'interval', 30, 'images', true,
                 '[]'::jsonb, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING;;

INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__comparator',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue comparator (ADR-048)',
                 'infra', 'interval', 30, 'comparator', true,
                 '[]'::jsonb, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING;;

INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__notifications',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue notifications (ADR-048)',
                 'infra', 'interval', 30, 'notifications', true,
                 '[]'::jsonb, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING;;

INSERT INTO job_definitions
                (code, task_name, description, owner,
                 schedule_type, interval_seconds, queue, enabled,
                 args, kwargs)
            VALUES
                ('worker_heartbeat__audit',
                 'mt.system.publish_heartbeat',
                 'Publica heartbeat del worker en queue audit (ADR-048)',
                 'infra', 'interval', 30, 'audit', true,
                 '[]'::jsonb, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING;;

UPDATE alembic_version SET version_num='20260506_002' WHERE alembic_version.version_num = '20260506_001';

-- Running upgrade 20260506_002 -> 20260506_003

ALTER TABLE products
        ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(sku, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(name_en, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description_en, '')), 'C') ||
            setweight(to_tsvector('simple', coalesce(family, '') || ' ' || coalesce(brand, '')), 'D')
        ) STORED;;

CREATE INDEX idx_products_search_tsv ON products USING gin (search_tsv);;

UPDATE alembic_version SET version_num='20260506_003' WHERE alembic_version.version_num = '20260506_002';

-- Running upgrade 20260506_003 -> 20260507_004

CREATE TABLE currencies (
    code VARCHAR(3) NOT NULL, 
    name TEXT NOT NULL, 
    symbol TEXT, 
    decimals INTEGER DEFAULT 2 NOT NULL, 
    is_base BOOLEAN DEFAULT false NOT NULL, 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (code), 
    CONSTRAINT ck_currencies_decimals CHECK (decimals BETWEEN 0 AND 8)
);

CREATE UNIQUE INDEX uq_currencies_one_base ON currencies (is_base) WHERE is_base = true;;

INSERT INTO currencies (code, name, symbol, decimals, is_base) VALUES ('AED', 'United Arab Emirates Dirham',         'د.إ', 2, true) ON CONFLICT (code) DO NOTHING;;

INSERT INTO currencies (code, name, symbol, decimals, is_base) VALUES ('USD', 'United States Dollar',         '$', 2, false) ON CONFLICT (code) DO NOTHING;;

INSERT INTO currencies (code, name, symbol, decimals, is_base) VALUES ('EUR', 'Euro',         '€', 2, false) ON CONFLICT (code) DO NOTHING;;

INSERT INTO currencies (code, name, symbol, decimals, is_base) VALUES ('SAR', 'Saudi Riyal',         'ر.س', 2, false) ON CONFLICT (code) DO NOTHING;;

CREATE TABLE suppliers (
    code TEXT NOT NULL, 
    name TEXT NOT NULL, 
    contact_email CITEXT, 
    contact_phone TEXT, 
    contract_currency VARCHAR(3) NOT NULL, 
    lead_time_days INTEGER, 
    payment_terms TEXT, 
    notes TEXT, 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (code), 
    FOREIGN KEY(contract_currency) REFERENCES currencies (code) ON DELETE RESTRICT
);

CREATE INDEX idx_suppliers_active ON suppliers (active) WHERE active = true;

CREATE INDEX idx_suppliers_currency ON suppliers (contract_currency);

CREATE TRIGGER trg_suppliers_updated_at BEFORE UPDATE ON suppliers FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE schemes (
    code VARCHAR(32) NOT NULL, 
    name TEXT NOT NULL, 
    description TEXT, 
    cost_components_template JSONB DEFAULT '{}'::jsonb NOT NULL, 
    active BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (code), 
    CONSTRAINT ck_schemes_code CHECK (code IN ('FBA','FBM','DIRECT_B2C','DIRECT_B2B','MARKETPLACE'))
);

INSERT INTO schemes (code, name, description, cost_components_template) VALUES ('FBA', 'Amazon FBA',         'Amazon Fulfillment by Amazon — fees Amazon incluidos', '{"required": ["fob", "freight", "customs", "fba_fees", "payment_fees"]}'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO schemes (code, name, description, cost_components_template) VALUES ('FBM', 'Amazon FBM',         'Amazon Fulfilled by Merchant — fees referrer Amazon', '{"required": ["fob", "freight", "customs", "fbm_fees", "payment_fees"]}'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO schemes (code, name, description, cost_components_template) VALUES ('DIRECT_B2C', 'Direct B2C',         'Venta directa a consumidor final (mtme.ae) con marketing propio', '{"required": ["fob", "freight", "customs", "payment_fees", "marketing"]}'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO schemes (code, name, description, cost_components_template) VALUES ('DIRECT_B2B', 'Direct B2B',         'Venta directa B2B (distribuidores GCC) — sin marketing', '{"required": ["fob", "freight", "customs", "payment_fees"]}'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO schemes (code, name, description, cost_components_template) VALUES ('MARKETPLACE', 'Marketplace listed',         'Marketplaces no-Amazon (Noon, etc.) con fees referrer', '{"required": ["fob", "freight", "customs", "marketplace_fees", "payment_fees", "marketing"]}'::jsonb) ON CONFLICT (code) DO NOTHING;;

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
        $rls$;;

UPDATE alembic_version SET version_num='20260507_004' WHERE alembic_version.version_num = '20260506_003';

-- Running upgrade 20260507_004 -> 20260507_005

CREATE OR REPLACE FUNCTION raise_use_soft_delete()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'DELETE físico bloqueado por compliance VAT UAE (NFR-35). '
                'Use UPDATE para set active=false (soft-deactivate).'
                USING ERRCODE = 'P0001';
        END
        $$;;

COMMENT ON FUNCTION raise_use_soft_delete() IS
            'Bloquea DELETE físico en tablas con audit trail VAT-compliant. '
            'Aplicar via BEFORE DELETE trigger row-level.';;

DROP TRIGGER IF EXISTS trg_products_no_hard_delete ON products;
        CREATE TRIGGER trg_products_no_hard_delete
            BEFORE DELETE ON products
            FOR EACH ROW
            EXECUTE FUNCTION raise_use_soft_delete();;

UPDATE alembic_version SET version_num='20260507_005' WHERE alembic_version.version_num = '20260507_004';

-- Running upgrade 20260507_005 -> 20260507_006

UPDATE job_definitions
           SET task_name = 'mt.audit.ensure_partitions',
               kwargs    = jsonb_build_object('months_ahead', 2),
               description = 'Crea particiones de audit_events para los próximos 2 meses si no existen (idempotente)',
               cron_expression = '0 2 * * *',
               queue = 'audit'
         WHERE code = 'audit_partitions_ensure';;

UPDATE alembic_version SET version_num='20260507_006' WHERE alembic_version.version_num = '20260507_005';

-- Running upgrade 20260507_006 -> 20260507_007

ALTER TABLE product_images ADD COLUMN image_status VARCHAR(16) DEFAULT 'pending' NOT NULL;

ALTER TABLE product_images ADD CONSTRAINT ck_product_images_image_status CHECK (image_status IN ('pending','mirroring','mirrored','failed'));

CREATE INDEX IF NOT EXISTS ix_product_images_image_status_active
            ON product_images (image_status)
         WHERE image_status IN ('pending','mirroring');;

UPDATE alembic_version SET version_num='20260507_007' WHERE alembic_version.version_num = '20260507_006';

-- Running upgrade 20260507_007 -> 20260507_008

CREATE INDEX IF NOT EXISTS ix_products_fts_gin ON products USING GIN (
            (
                setweight(to_tsvector('simple', coalesce(sku, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(name_en, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(family, '')), 'C') ||
                setweight(to_tsvector('simple', coalesce(brand, '')), 'D')
            )
        );;

UPDATE alembic_version SET version_num='20260507_008' WHERE alembic_version.version_num = '20260507_007';

-- Running upgrade 20260507_008 -> 20260507_009

CREATE TABLE import_runs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    import_type VARCHAR(16) NOT NULL, 
    source_filename TEXT NOT NULL, 
    source_storage_path TEXT, 
    status VARCHAR(32) DEFAULT 'queued' NOT NULL, 
    total_rows INTEGER, 
    inserted_rows INTEGER DEFAULT 0 NOT NULL, 
    updated_rows INTEGER DEFAULT 0 NOT NULL, 
    skipped_rows INTEGER DEFAULT 0 NOT NULL, 
    error_rows INTEGER DEFAULT 0 NOT NULL, 
    errors JSONB DEFAULT '[]'::jsonb NOT NULL, 
    summary JSONB DEFAULT '{}'::jsonb NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    triggered_by UUID, 
    celery_task_id TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_import_runs PRIMARY KEY (id), 
    CONSTRAINT fk_import_runs_triggered_by FOREIGN KEY(triggered_by) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT ck_import_runs_type CHECK (import_type IN ('pim','costs','datasheets')), 
    CONSTRAINT ck_import_runs_status CHECK (status IN ('queued','running','completed','completed_with_errors','failed'))
);

CREATE INDEX idx_import_runs_status ON import_runs (status);

CREATE INDEX idx_import_runs_type_created ON import_runs (import_type, created_at);

CREATE TRIGGER set_import_runs_updated_at
            BEFORE UPDATE ON import_runs
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

INSERT INTO permissions (code, description)
        VALUES ('imports:execute', 'Disparar batch imports async (PIM, costs)')
        ON CONFLICT (code) DO NOTHING;;

UPDATE alembic_version SET version_num='20260507_009' WHERE alembic_version.version_num = '20260507_008';

-- Running upgrade 20260507_009 -> 20260507_010

CREATE TABLE channels (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code VARCHAR(64) NOT NULL, 
    name TEXT NOT NULL, 
    state VARCHAR(32) DEFAULT 'inactive' NOT NULL, 
    schemes_supported JSONB DEFAULT '[]'::jsonb NOT NULL, 
    state_history JSONB DEFAULT '[]'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_channels_state CHECK (state IN ('inactive','pre_launch','pilot','live','paused','deprecated')), 
    UNIQUE (code)
);

CREATE INDEX idx_channels_state ON channels (state);

CREATE TRIGGER trg_channels_updated_at BEFORE UPDATE ON channels FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

INSERT INTO channels (code, name, state, schemes_supported) VALUES ('amazon_uae', 'Amazon UAE',         'inactive', '["FBA", "FBM"]'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO channels (code, name, state, schemes_supported) VALUES ('noon_uae', 'Noon UAE',         'inactive', '["MARKETPLACE"]'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO channels (code, name, state, schemes_supported) VALUES ('b2c_direct', 'B2C directo (mtme.ae)',         'inactive', '["DIRECT_B2C"]'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO channels (code, name, state, schemes_supported) VALUES ('b2b_direct', 'B2B directo',         'inactive', '["DIRECT_B2B"]'::jsonb) ON CONFLICT (code) DO NOTHING;;

INSERT INTO channels (code, name, state, schemes_supported) VALUES ('marketplace_listing', 'Marketplace listing genérico',         'inactive', '["MARKETPLACE"]'::jsonb) ON CONFLICT (code) DO NOTHING;;

CREATE TABLE fx_rates (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    from_currency VARCHAR(3) NOT NULL, 
    to_currency VARCHAR(3) NOT NULL, 
    rate NUMERIC(18, 8) NOT NULL, 
    effective_from TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    effective_to TIMESTAMP WITH TIME ZONE, 
    source VARCHAR(32), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_fx_rate_positive CHECK (rate > 0), 
    FOREIGN KEY(from_currency) REFERENCES currencies (code) ON DELETE RESTRICT, 
    FOREIGN KEY(to_currency) REFERENCES currencies (code) ON DELETE RESTRICT
);

CREATE INDEX idx_fx_lookup ON fx_rates (from_currency, to_currency, effective_from);

CREATE INDEX idx_fx_active ON fx_rates (from_currency, to_currency) WHERE effective_to IS NULL;

CREATE TRIGGER trg_fx_rates_updated_at BEFORE UPDATE ON fx_rates FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

INSERT INTO fx_rates (from_currency, to_currency, rate,        effective_from, source) VALUES ('EUR', 'AED', 4.29, '2026-04-01 00:00:00+00', 'manual') ON CONFLICT DO NOTHING;;

INSERT INTO fx_rates (from_currency, to_currency, rate,        effective_from, source) VALUES ('AED', 'EUR', 0.23310023, '2026-04-01 00:00:00+00', 'manual') ON CONFLICT DO NOTHING;;

CREATE TABLE costs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    product_sku TEXT NOT NULL, 
    scheme_code VARCHAR(32) NOT NULL, 
    supplier_code TEXT, 
    breakdown JSONB DEFAULT '{}'::jsonb NOT NULL, 
    total NUMERIC(18, 4) NOT NULL, 
    currency VARCHAR(3) DEFAULT 'AED' NOT NULL, 
    fx_at TIMESTAMP WITH TIME ZONE, 
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    valid_to TIMESTAMP WITH TIME ZONE, 
    created_by UUID, 
    updated_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_costs_total_nonneg CHECK (total >= 0), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(scheme_code) REFERENCES schemes (code) ON DELETE RESTRICT, 
    FOREIGN KEY(supplier_code) REFERENCES suppliers (code) ON DELETE SET NULL, 
    FOREIGN KEY(currency) REFERENCES currencies (code) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_costs_lookup ON costs (product_sku, scheme_code, valid_from);

CREATE INDEX idx_costs_active ON costs (product_sku, scheme_code) WHERE valid_to IS NULL;

CREATE TRIGGER trg_costs_updated_at BEFORE UPDATE ON costs FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE prices (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    product_sku TEXT NOT NULL, 
    channel_id UUID NOT NULL, 
    scheme_code VARCHAR(32) NOT NULL, 
    amount NUMERIC(18, 4) NOT NULL, 
    pvp_min NUMERIC(18, 4), 
    margin_pct NUMERIC(7, 4) DEFAULT 0 NOT NULL, 
    currency VARCHAR(3) DEFAULT 'AED' NOT NULL, 
    rule_applied VARCHAR(64), 
    formula TEXT, 
    breakdown JSONB DEFAULT '{}'::jsonb NOT NULL, 
    alerts JSONB DEFAULT '[]'::jsonb NOT NULL, 
    fx_at TIMESTAMP WITH TIME ZONE, 
    status VARCHAR(32) DEFAULT 'draft' NOT NULL, 
    proposed_by UUID, 
    approved_by UUID, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    rejection_reason TEXT, 
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    valid_to TIMESTAMP WITH TIME ZONE, 
    created_by UUID, 
    updated_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_prices_amount_nonneg CHECK (amount >= 0), 
    CONSTRAINT ck_prices_status CHECK (status IN ('draft','pending_review','auto_approved','approved','rejected','revised','exported','superseded','migrated')), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE RESTRICT, 
    FOREIGN KEY(scheme_code) REFERENCES schemes (code) ON DELETE RESTRICT, 
    FOREIGN KEY(currency) REFERENCES currencies (code) ON DELETE RESTRICT, 
    FOREIGN KEY(proposed_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_prices_lookup ON prices (product_sku, channel_id, scheme_code);

CREATE INDEX idx_prices_pending ON prices (status) WHERE status IN ('pending_review','draft');

CREATE INDEX idx_prices_active ON prices (product_sku, channel_id, scheme_code) WHERE valid_to IS NULL;

CREATE TRIGGER trg_prices_updated_at BEFORE UPDATE ON prices FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE exception_rules (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code VARCHAR(64) NOT NULL, 
    description TEXT, 
    channel_id UUID, 
    scheme_code VARCHAR(32), 
    margin_threshold_pct NUMERIC(7, 4), 
    fx_swing_threshold_pct NUMERIC(7, 4), 
    min_margin_pct NUMERIC(7, 4), 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code), 
    FOREIGN KEY(channel_id) REFERENCES channels (id) ON DELETE CASCADE, 
    FOREIGN KEY(scheme_code) REFERENCES schemes (code) ON DELETE CASCADE
);

CREATE INDEX idx_exception_rules_active ON exception_rules (active) WHERE active = true;

CREATE TRIGGER trg_exception_rules_updated_at BEFORE UPDATE ON exception_rules FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

INSERT INTO exception_rules (code, description, channel_id,   scheme_code, margin_threshold_pct, fx_swing_threshold_pct,   min_margin_pct) VALUES ('GLOBAL_MARGIN_DELTA', 'Pending review si delta margen > 5% vs precio anterior', NULL,   NULL, 5.0, NULL, NULL) ON CONFLICT (code) DO NOTHING;;

INSERT INTO exception_rules (code, description, channel_id,   scheme_code, margin_threshold_pct, fx_swing_threshold_pct,   min_margin_pct) VALUES ('GLOBAL_FX_SWING', 'Pending review si FX se movió > 3% desde último precio', NULL,   NULL, NULL, 3.0, NULL) ON CONFLICT (code) DO NOTHING;;

INSERT INTO exception_rules (code, description, channel_id,   scheme_code, margin_threshold_pct, fx_swing_threshold_pct,   min_margin_pct) VALUES ('B2C_MIN_MARGIN', 'Margen mínimo B2C 8%', NULL,   'DIRECT_B2C', NULL, NULL, 8.0) ON CONFLICT (code) DO NOTHING;;

INSERT INTO exception_rules (code, description, channel_id,   scheme_code, margin_threshold_pct, fx_swing_threshold_pct,   min_margin_pct) VALUES ('B2B_MIN_MARGIN', 'Margen mínimo B2B 5%', NULL,   'DIRECT_B2B', NULL, NULL, 5.0) ON CONFLICT (code) DO NOTHING;;

INSERT INTO exception_rules (code, description, channel_id,   scheme_code, margin_threshold_pct, fx_swing_threshold_pct,   min_margin_pct) VALUES ('FBA_MIN_MARGIN', 'Margen mínimo FBA 10%', NULL,   'FBA', NULL, NULL, 10.0) ON CONFLICT (code) DO NOTHING;;

CREATE TABLE price_approval_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    price_id UUID NOT NULL, 
    actor_id UUID NOT NULL, 
    from_status VARCHAR(32) NOT NULL, 
    to_status VARCHAR(32) NOT NULL, 
    reason TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_price_approval_events_from_status CHECK (from_status IN ('draft','pending_review','auto_approved','approved','rejected','revised','exported','superseded','migrated')), 
    CONSTRAINT ck_price_approval_events_to_status CHECK (to_status IN ('draft','pending_review','auto_approved','approved','rejected','revised','exported','superseded','migrated')), 
    FOREIGN KEY(price_id) REFERENCES prices (id) ON DELETE CASCADE, 
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX idx_price_approval_events_lookup ON price_approval_events (price_id, created_at);

INSERT INTO permissions (code, description) VALUES
            ('prices:read', 'Listar/leer prices'),
            ('prices:propose', 'Crear propuesta de precio (motor v5.1)'),
            ('prices:approve', 'Aprobar/rechazar/revisar prices'),
            ('prices:export', 'Marcar prices como exported'),
            ('channels:read', 'Listar canales'),
            ('channels:manage', 'Gestionar estado de canales'),
            ('fx:read', 'Listar FX rates'),
            ('fx:write', 'Crear FX rates manuales')
        ON CONFLICT (code) DO NOTHING;;

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
        $rls$;;

UPDATE alembic_version SET version_num='20260507_010' WHERE alembic_version.version_num = '20260507_009';

-- Running upgrade 20260507_010 -> 20260507_011

INSERT INTO permissions (code, description) VALUES
            ('suppliers:read',  'Listar/leer proveedores'),
            ('suppliers:write', 'Crear/editar proveedores')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'comercial'        AND p.code IN ('suppliers:read'))
         OR (r.code = 'gerente_comercial' AND p.code IN ('suppliers:read'))
         OR (r.code = 'ti_integracion'   AND p.code IN ('suppliers:read','suppliers:write'))
         OR (r.code = 'admin'            AND p.code IN ('suppliers:read','suppliers:write'))
        ON CONFLICT DO NOTHING;;

UPDATE alembic_version SET version_num='20260507_011' WHERE alembic_version.version_num = '20260507_010';

-- Running upgrade 20260507_011 -> 20260507_012

INSERT INTO permissions (code, description) VALUES
            ('jobs:read',  'Listar/leer job_definitions y JobRuns'),
            ('jobs:write', 'Crear/editar job_definitions (cron, args, enabled)'),
            ('jobs:run',   'Disparar ejecuciones ad-hoc (run-now)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'gerente_comercial' AND p.code IN ('jobs:read'))
         OR (r.code = 'ti_integracion'   AND p.code IN ('jobs:read','jobs:write','jobs:run'))
         OR (r.code = 'admin'            AND p.code IN ('jobs:read','jobs:write','jobs:run'))
        ON CONFLICT DO NOTHING;;

UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('gerente_comercial', 'ti_integracion', 'admin');;

UPDATE alembic_version SET version_num='20260507_012' WHERE alembic_version.version_num = '20260507_011';

-- Running upgrade 20260507_012 -> 20260507_013

CREATE TABLE IF NOT EXISTS public.force_logout_events (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            reason      TEXT        NOT NULL,
            actor_id    UUID        REFERENCES public.users(id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );;

CREATE INDEX IF NOT EXISTS ix_force_logout_user_created
            ON public.force_logout_events (user_id, created_at DESC);;

DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                ALTER PUBLICATION supabase_realtime ADD TABLE public.force_logout_events;
            END IF;
        EXCEPTION
            WHEN duplicate_object THEN
                -- Tabla ya en la publication, ignorar.
                NULL;
        END $$;;

ALTER TABLE public.force_logout_events ENABLE ROW LEVEL SECURITY;;

DROP POLICY IF EXISTS users_read_own_logout_events ON public.force_logout_events;
        CREATE POLICY users_read_own_logout_events
            ON public.force_logout_events
            FOR SELECT
            USING (user_id::text = COALESCE(auth.uid()::text, ''));;

DROP POLICY IF EXISTS service_role_inserts_logout_events ON public.force_logout_events;
        CREATE POLICY service_role_inserts_logout_events
            ON public.force_logout_events
            FOR INSERT
            TO service_role
            WITH CHECK (true);;

INSERT INTO job_definitions
            (code, task_name, description, owner,
             schedule_type, cron_expression, queue, enabled,
             args, kwargs)
        VALUES
            ('cleanup_force_logout_events',
             'mt.audit.cleanup_force_logout_events',
             'Borra force_logout_events > 24h (ADR-032 cleanup)',
             'infra', 'cron', '0 3 * * *', 'audit', true,
             '[]'::jsonb, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING;;

UPDATE public.job_definitions
        SET next_run_at = now()
        WHERE next_run_at IS NULL AND enabled = true;;

UPDATE alembic_version SET version_num='20260507_013' WHERE alembic_version.version_num = '20260507_012';

-- Running upgrade 20260507_013 -> 20260507_014

INSERT INTO permissions (code, description) VALUES
            ('audit:read', 'Leer audit_events (timeline producto/usuario/job/role)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'gerente_comercial' AND p.code = 'audit:read')
         OR (r.code = 'ti_integracion'    AND p.code = 'audit:read')
         OR (r.code = 'admin'             AND p.code = 'audit:read')
        ON CONFLICT DO NOTHING;;

UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('gerente_comercial', 'ti_integracion', 'admin');;

UPDATE alembic_version SET version_num='20260507_014' WHERE alembic_version.version_num = '20260507_013';

-- Running upgrade 20260507_014 -> 20260507_015

CREATE TABLE channel_listings (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    product_sku TEXT NOT NULL, 
    channel_code VARCHAR(64) NOT NULL, 
    external_id TEXT DEFAULT '' NOT NULL, 
    buybox_state VARCHAR(16) DEFAULT 'none' NOT NULL, 
    buybox_pct_7d NUMERIC(5, 4), 
    stock_qty INTEGER, 
    rating NUMERIC(3, 2), 
    reviews_count INTEGER, 
    last_sync_at TIMESTAMP WITH TIME ZONE, 
    canonical_snapshot_jsonb JSONB DEFAULT '{}'::jsonb NOT NULL, 
    live_snapshot_jsonb JSONB DEFAULT '{}'::jsonb NOT NULL, 
    diff_summary JSONB DEFAULT '{}'::jsonb NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_channel_listings_channel_external UNIQUE (channel_code, external_id), 
    CONSTRAINT uq_channel_listings_channel_sku UNIQUE (channel_code, product_sku), 
    CONSTRAINT ck_channel_listings_buybox_state CHECK (buybox_state IN ('own','competitor','none')), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE
);

CREATE INDEX idx_channel_listings_lookup ON channel_listings (channel_code, product_sku);

CREATE INDEX idx_channel_listings_last_sync ON channel_listings (channel_code, last_sync_at);

CREATE INDEX ix_channel_listings_product_sku ON channel_listings (product_sku);

CREATE INDEX ix_channel_listings_channel_code ON channel_listings (channel_code);

CREATE TRIGGER trg_channel_listings_updated_at BEFORE UPDATE ON channel_listings FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE TABLE channel_sync_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    channel_code VARCHAR(64) NOT NULL, 
    product_sku TEXT, 
    event_type VARCHAR(16) NOT NULL, 
    ok BOOLEAN DEFAULT true NOT NULL, 
    summary TEXT, 
    payload_jsonb JSONB DEFAULT '{}'::jsonb NOT NULL, 
    duration_ms INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_channel_sync_events_event_type CHECK (event_type IN ('pull','push','diff')), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE SET NULL
);

CREATE INDEX idx_channel_sync_events_recent ON channel_sync_events (channel_code, created_at);

CREATE INDEX ix_channel_sync_events_channel_code ON channel_sync_events (channel_code);

CREATE INDEX ix_channel_sync_events_product_sku ON channel_sync_events (product_sku);

DO $rls$
        DECLARE
            mt_app_exists BOOLEAN;
        BEGIN
            SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') INTO mt_app_exists;
            IF mt_app_exists THEN
                EXECUTE 'ALTER TABLE channel_listings     ENABLE ROW LEVEL SECURITY';
                EXECUTE 'ALTER TABLE channel_sync_events  ENABLE ROW LEVEL SECURITY';

                EXECUTE 'CREATE POLICY channel_listings_read_all ON channel_listings '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY channel_listings_ti_write ON channel_listings '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''ti_integracion'',''admin''))';

                EXECUTE 'CREATE POLICY channel_sync_events_read_all ON channel_sync_events '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY channel_sync_events_insert ON channel_sync_events '
                     || 'FOR INSERT TO mt_app '
                     || 'WITH CHECK (auth.uid() IS NOT NULL)';
            END IF;
        END
        $rls$;;

UPDATE alembic_version SET version_num='20260507_015' WHERE alembic_version.version_num = '20260507_014';

-- Running upgrade 20260507_015 -> 20260507_016

CREATE TABLE match_candidates (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    product_sku TEXT NOT NULL, 
    channel VARCHAR(32) NOT NULL, 
    external_id TEXT NOT NULL, 
    brand TEXT, 
    title TEXT NOT NULL, 
    price_aed NUMERIC(18, 4), 
    delivery_text TEXT, 
    specs_jsonb JSONB DEFAULT '{}'::jsonb NOT NULL, 
    kind VARCHAR(16) DEFAULT 'unknown' NOT NULL, 
    score INTEGER DEFAULT 0 NOT NULL, 
    status VARCHAR(16) DEFAULT 'pending' NOT NULL, 
    validated_by UUID, 
    validated_at TIMESTAMP WITH TIME ZONE, 
    discarded_reason TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_match_candidates_channel CHECK (channel IN ('amazon_uae','noon_uae')), 
    CONSTRAINT ck_match_candidates_kind CHECK (kind IN ('peer','drop','unknown')), 
    CONSTRAINT ck_match_candidates_status CHECK (status IN ('pending','validated','discarded')), 
    CONSTRAINT ck_match_candidates_score CHECK (score >= 0 AND score <= 100), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(validated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_match_candidates_sku_status ON match_candidates (product_sku, status);

CREATE UNIQUE INDEX idx_match_candidates_unique_external ON match_candidates (product_sku, channel, external_id);

CREATE TRIGGER trg_match_candidates_updated_at BEFORE UPDATE ON match_candidates FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

UPDATE alembic_version SET version_num='20260507_016' WHERE alembic_version.version_num = '20260507_015';

-- Running upgrade 20260507_016 -> 20260507_017

ALTER TABLE fx_rates
            ADD COLUMN IF NOT EXISTS created_by UUID
            REFERENCES users(id) ON DELETE SET NULL;;

ALTER TABLE fx_rates DROP CONSTRAINT IF EXISTS ck_fx_rates_source;;

ALTER TABLE fx_rates
            ADD CONSTRAINT ck_fx_rates_source
            CHECK (source IS NULL OR source IN
                ('manual','cbuae','ecb','imported','identity'));;

DROP INDEX IF EXISTS idx_fx_lookup_desc;;

CREATE INDEX idx_fx_lookup_desc
            ON fx_rates (from_currency, to_currency, effective_from DESC);;

CREATE OR REPLACE FUNCTION fx_rates_close_previous() RETURNS TRIGGER
LANGUAGE plpgsql AS $fx$
DECLARE
    prev_id UUID;
    prev_effective_from TIMESTAMPTZ;
    prev_effective_to   TIMESTAMPTZ;
    allow_retro TEXT;
BEGIN
    -- 0. Identity case: AED→AED, EUR→EUR, etc. Force rate=1.
    IF NEW.from_currency = NEW.to_currency THEN
        NEW.rate := 1;
    END IF;

    -- 1. rate > 0 (defensa, además del CHECK constraint).
    IF NEW.rate IS NULL OR NEW.rate <= 0 THEN
        RAISE EXCEPTION USING
            ERRCODE = 'P0001',
            MESSAGE = 'fx_rate_must_be_positive';
    END IF;

    -- 2. Buscar último vigente para el mismo par (effective_to IS NULL).
    SELECT id, effective_from, effective_to
      INTO prev_id, prev_effective_from, prev_effective_to
      FROM fx_rates
     WHERE from_currency = NEW.from_currency
       AND to_currency   = NEW.to_currency
       AND effective_to IS NULL
     ORDER BY effective_from DESC
     LIMIT 1
     FOR UPDATE;

    IF FOUND THEN
        -- 2.a Mismo timestamp → bloqueo (no permitimos dos rates iniciando
        --     en el mismo instante para el mismo par).
        IF prev_effective_from = NEW.effective_from THEN
            RAISE EXCEPTION USING
                ERRCODE = 'P0001',
                MESSAGE = 'fx_same_effective_from';
        END IF;

        -- 2.b Retroactivo → bloqueo salvo flag explícito.
        IF prev_effective_from > NEW.effective_from THEN
            BEGIN
                allow_retro := current_setting('fx.allow_retroactive', true);
            EXCEPTION WHEN OTHERS THEN
                allow_retro := NULL;
            END;
            IF allow_retro IS NULL OR lower(allow_retro) <> 'true' THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'P0001',
                    MESSAGE = 'fx_retroactive_not_allowed';
            END IF;
            -- Retroactivo permitido: cerramos igual el previo con effective_to
            -- = NEW.effective_from. Esto crea un solapamiento en el histórico
            -- (vigente antes < NEW < cierre del previo) pero la función
            -- fx_rate_at sigue siendo determinista porque escoge effective_from
            -- DESC LIMIT 1.
        END IF;

        -- 2.c Caso normal: cerramos el previo.
        UPDATE fx_rates
           SET effective_to = NEW.effective_from
         WHERE id = prev_id;
    END IF;

    -- NEW siempre se inserta con effective_to NULL.
    NEW.effective_to := NULL;

    RETURN NEW;
END;
$fx$;;

DROP TRIGGER IF EXISTS fx_rates_close_previous_trg ON fx_rates;
CREATE TRIGGER fx_rates_close_previous_trg
BEFORE INSERT ON fx_rates
FOR EACH ROW
EXECUTE FUNCTION fx_rates_close_previous();;

CREATE OR REPLACE FUNCTION fx_rate_at(
    p_from_code TEXT,
    p_to_code   TEXT,
    p_at        TIMESTAMPTZ
) RETURNS UUID
LANGUAGE sql STABLE AS $fxat$
    SELECT id
      FROM fx_rates
     WHERE from_currency = p_from_code
       AND to_currency   = p_to_code
       AND effective_from <= p_at
       AND (effective_to IS NULL OR effective_to > p_at)
     ORDER BY effective_from DESC
     LIMIT 1;
$fxat$;;

INSERT INTO fx_rates (from_currency, to_currency, rate, effective_from, source)
        SELECT 'AED','AED',1,'2026-04-01 00:00:00+00','identity'
         WHERE NOT EXISTS (
            SELECT 1 FROM fx_rates
             WHERE from_currency='AED' AND to_currency='AED'
         );;

INSERT INTO permissions (code, description) VALUES
            ('currencies:manage', 'Activar/desactivar currencies seed (TI/admin)'),
            ('fx:manage',         'Crear y administrar tasas FX (TI/admin)'),
            ('fx:read',           'Leer currencies y FX rates (todos)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
          FROM roles r CROSS JOIN permissions p
         WHERE
             (r.code = 'comercial'         AND p.code IN ('fx:read'))
          OR (r.code = 'gerente_comercial' AND p.code IN ('fx:read'))
          OR (r.code = 'ti_integracion'    AND p.code IN ('fx:read','fx:manage','currencies:manage'))
          OR (r.code = 'admin'             AND p.code IN ('fx:read','fx:manage','currencies:manage'))
        ON CONFLICT DO NOTHING;;

UPDATE alembic_version SET version_num='20260507_017' WHERE alembic_version.version_num = '20260507_016';

-- Running upgrade 20260507_017 -> 20260507_018

DROP TABLE IF EXISTS costs CASCADE;;

CREATE TABLE costs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    sku TEXT NOT NULL, 
    scheme_code VARCHAR(32) NOT NULL, 
    supplier_code TEXT, 
    currency_origin VARCHAR(3) DEFAULT 'AED' NOT NULL, 
    fx_rate_id UUID, 
    breakdown JSONB DEFAULT '{}'::jsonb NOT NULL, 
    scheme_landed_aed NUMERIC(14, 4), 
    effective_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(16) DEFAULT 'active' NOT NULL, 
    fx_inferred BOOLEAN DEFAULT false NOT NULL, 
    version INTEGER DEFAULT 1 NOT NULL, 
    created_by UUID, 
    updated_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_costs_status CHECK (status IN ('active','superseded')), 
    CONSTRAINT ck_costs_version_pos CHECK (version >= 1), 
    CONSTRAINT ck_costs_landed_nonneg CHECK (scheme_landed_aed IS NULL OR scheme_landed_aed >= 0), 
    FOREIGN KEY(sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(scheme_code) REFERENCES schemes (code) ON DELETE RESTRICT, 
    FOREIGN KEY(supplier_code) REFERENCES suppliers (code) ON DELETE SET NULL, 
    FOREIGN KEY(currency_origin) REFERENCES currencies (code) ON DELETE RESTRICT, 
    FOREIGN KEY(fx_rate_id) REFERENCES fx_rates (id) ON DELETE SET NULL, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_costs_sku_scheme ON costs (sku, scheme_code);

CREATE INDEX idx_costs_effective_at ON costs (effective_at);

CREATE UNIQUE INDEX uq_costs_active_combo
        ON costs (sku, scheme_code, COALESCE(supplier_code, ''))
        WHERE status = 'active';;

CREATE TRIGGER trg_costs_updated_at BEFORE UPDATE ON costs FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

CREATE OR REPLACE FUNCTION costs_stamp_fx() RETURNS trigger AS $body$
DECLARE
    v_fx_id uuid;
BEGIN
    -- Si fx_rate_id viene explícito (importer reusa) → respetar y NO sobrescribir.
    IF NEW.fx_rate_id IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Si la moneda origen es AED, no hace falta FX (rate identidad implícita).
    IF NEW.currency_origin = 'AED' THEN
        NEW.fx_rate_id := NULL;
        RETURN NEW;
    END IF;

    -- Buscar el FX vigente a effective_at vía función fx_rate_at (US-1A-05-02).
    -- Si no existe → fail con código semántico.
    BEGIN
        SELECT fx_rate_at(NEW.currency_origin, 'AED', NEW.effective_at) INTO v_fx_id;
    EXCEPTION
        WHEN undefined_function THEN
            -- Fallback (test envs sin la función) — busca directo en fx_rates.
            v_fx_id := NULL;
    END;

    IF v_fx_id IS NULL THEN
        SELECT id INTO v_fx_id
        FROM fx_rates
        WHERE from_currency = NEW.currency_origin
          AND to_currency = 'AED'
          AND effective_from <= NEW.effective_at
          AND (effective_to IS NULL OR effective_to > NEW.effective_at)
        ORDER BY effective_from DESC
        LIMIT 1;
    END IF;

    IF v_fx_id IS NULL THEN
        RAISE EXCEPTION 'fx_rate_not_found_at_effective_at: % -> AED at %',
            NEW.currency_origin, NEW.effective_at
            USING ERRCODE = 'P0001';
    END IF;

    NEW.fx_rate_id := v_fx_id;
    RETURN NEW;
END;
$body$ LANGUAGE plpgsql;;

CREATE OR REPLACE FUNCTION costs_compute_landed_aed() RETURNS trigger AS $body$
DECLARE
    v_rate numeric(18,8) := 1;
    v_subtotal numeric(20,8) := 0;
    v_pct_total numeric(20,8) := 0;
    k text;
    v_raw text;
    v numeric(20,8);
    v_lower text;
    v_origin_suffix text;
BEGIN
    -- Resolve FX rate. NULL fx_rate_id (currency = AED) → rate=1.
    IF NEW.fx_rate_id IS NOT NULL THEN
        SELECT rate INTO v_rate FROM fx_rates WHERE id = NEW.fx_rate_id;
        IF v_rate IS NULL THEN
            v_rate := 1;
        END IF;
    END IF;

    v_origin_suffix := '_' || lower(NEW.currency_origin);

    -- Iterar pares clave-valor del JSONB.
    FOR k, v_raw IN SELECT * FROM jsonb_each_text(COALESCE(NEW.breakdown, '{}'::jsonb))
    LOOP
        -- Skip si el valor no es numérico parseable.
        BEGIN
            v := v_raw::numeric;
        EXCEPTION WHEN others THEN
            CONTINUE;
        END;

        v_lower := lower(k);

        IF v_lower LIKE '%\_pct' ESCAPE '\' THEN
            -- Porcentaje → acumula y se aplica al final.
            v_pct_total := v_pct_total + v;
        ELSIF v_lower LIKE '%\_aed' ESCAPE '\' THEN
            -- Importe ya en AED.
            v_subtotal := v_subtotal + v;
        ELSIF v_lower LIKE ('%' || v_origin_suffix) THEN
            -- Importe en moneda origen → convierte.
            v_subtotal := v_subtotal + (v * v_rate);
        ELSE
            -- Default: asume currency_origin si no es AED, AED si sí.
            IF NEW.currency_origin = 'AED' THEN
                v_subtotal := v_subtotal + v;
            ELSE
                v_subtotal := v_subtotal + (v * v_rate);
            END IF;
        END IF;
    END LOOP;

    -- Aplica % sobre el subtotal acumulado.
    IF v_pct_total <> 0 THEN
        v_subtotal := v_subtotal + (v_subtotal * v_pct_total / 100);
    END IF;

    -- AFTER trigger → write via UPDATE (no se puede mutar NEW).
    UPDATE costs
       SET scheme_landed_aed = round(v_subtotal, 4)
     WHERE id = NEW.id
       AND (scheme_landed_aed IS DISTINCT FROM round(v_subtotal, 4));

    RETURN NULL;
END;
$body$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS costs_stamp_fx_trg ON costs;
        CREATE TRIGGER costs_stamp_fx_trg
            BEFORE INSERT OR UPDATE ON costs
            FOR EACH ROW EXECUTE FUNCTION costs_stamp_fx();;

DROP TRIGGER IF EXISTS costs_compute_landed_aed_trg ON costs;
        CREATE TRIGGER costs_compute_landed_aed_trg
            AFTER INSERT OR UPDATE OF breakdown, fx_rate_id, currency_origin ON costs
            FOR EACH ROW EXECUTE FUNCTION costs_compute_landed_aed();;

DO $rls$
        DECLARE
            mt_app_exists BOOLEAN;
        BEGIN
            SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') INTO mt_app_exists;
            IF mt_app_exists THEN
                EXECUTE 'ALTER TABLE costs ENABLE ROW LEVEL SECURITY';
                EXECUTE 'CREATE POLICY costs_read_all ON costs '
                     || 'FOR SELECT TO mt_app USING (true)';
                EXECUTE 'CREATE POLICY costs_comercial_write ON costs '
                     || 'FOR ALL TO mt_app '
                     || 'USING (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin'')) '
                     || 'WITH CHECK (current_role_code() IN (''comercial'',''gerente_comercial'',''ti_integracion'',''admin''))';
            END IF;
        END
        $rls$;;

UPDATE alembic_version SET version_num='20260507_018' WHERE alembic_version.version_num = '20260507_017';

-- Running upgrade 20260507_018 -> 20260507_019

CREATE TABLE material_compatibilities (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    producto_descriptor TEXT NOT NULL, 
    temperatura_c NUMERIC(10, 2) NOT NULL, 
    compatibilities JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_material_compatibilities_descriptor_temp UNIQUE (producto_descriptor, temperatura_c)
);

CREATE INDEX idx_material_compatibilities_descriptor ON material_compatibilities (producto_descriptor);

CREATE TRIGGER trg_material_compatibilities_updated_at BEFORE UPDATE ON material_compatibilities FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

ALTER TABLE import_runs DROP CONSTRAINT IF EXISTS ck_import_runs_type;;

ALTER TABLE import_runs ADD CONSTRAINT ck_import_runs_type CHECK (import_type IN ('pim','costs','datasheets','materials'));

ALTER TABLE import_runs ADD COLUMN orphans JSONB DEFAULT '{}'::jsonb NOT NULL;

UPDATE alembic_version SET version_num='20260507_019' WHERE alembic_version.version_num = '20260507_018';

-- Running upgrade 20260507_019 -> 20260507_020

ALTER TABLE product_translations ADD COLUMN IF NOT EXISTS staleness_reason TEXT NULL;

ALTER TABLE product_translations ADD COLUMN IF NOT EXISTS rejection_reason TEXT NULL;

ALTER TABLE product_translations DROP CONSTRAINT IF EXISTS ck_translations_status;

ALTER TABLE product_translations ADD CONSTRAINT ck_translations_status CHECK (status IN ('pending','draft','pending_review','approved','stale'));

CREATE OR REPLACE FUNCTION mark_translations_stale_on_master_edit()
        RETURNS TRIGGER AS $fn$
        BEGIN
            IF (NEW.name_en IS DISTINCT FROM OLD.name_en)
               OR (NEW.description_en IS DISTINCT FROM OLD.description_en) THEN
                UPDATE product_translations
                   SET status = 'stale',
                       staleness_reason = 'master_en_changed',
                       updated_at = now()
                 WHERE sku = NEW.sku
                   AND lang <> 'en'
                   AND status = 'approved';
            END IF;
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS trg_translations_stale_on_master_edit ON products;

CREATE TRIGGER trg_translations_stale_on_master_edit
        AFTER UPDATE OF name_en, description_en ON products
        FOR EACH ROW
        EXECUTE FUNCTION mark_translations_stale_on_master_edit();;

UPDATE alembic_version SET version_num='20260507_020' WHERE alembic_version.version_num = '20260507_019';

-- Running upgrade 20260507_020 -> 20260507_021

CREATE TABLE IF NOT EXISTS price_state_transitions (
            from_status TEXT NOT NULL,
            to_status   TEXT NOT NULL,
            PRIMARY KEY (from_status, to_status)
        );

DELETE FROM price_state_transitions;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('draft', 'auto_approved') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('draft', 'pending_review') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('draft', 'rejected') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('auto_approved', 'approved') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('auto_approved', 'exported') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('auto_approved', 'revised') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('pending_review', 'approved') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('pending_review', 'rejected') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('pending_review', 'revised') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('approved', 'exported') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('approved', 'revised') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('rejected', 'draft') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('revised', 'pending_review') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('revised', 'rejected') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('migrated', 'approved') ON CONFLICT DO NOTHING;

INSERT INTO price_state_transitions (from_status, to_status) VALUES ('migrated', 'rejected') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS pricing_golden_tiers (
            name          TEXT PRIMARY KEY,
            upper_bound   NUMERIC(18, 4) NOT NULL,
            endings       TEXT NOT NULL,
            modulus       NUMERIC(18, 4) NULL,
            tolerance     NUMERIC(18, 4) NOT NULL,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );

DELETE FROM pricing_golden_tiers;

INSERT INTO pricing_golden_tiers
            (name, upper_bound, endings, modulus, tolerance)
            VALUES ('tier_1_small', '10.00'::numeric, '0.49,0.99',
                    NULL, '0.30'::numeric);

INSERT INTO pricing_golden_tiers
            (name, upper_bound, endings, modulus, tolerance)
            VALUES ('tier_2_medium', '100.00'::numeric, '0.95,0.99',
                    NULL, '0.30'::numeric);

INSERT INTO pricing_golden_tiers
            (name, upper_bound, endings, modulus, tolerance)
            VALUES ('tier_3_large', '1000.00'::numeric, '0.95,0.99',
                    '5.00'::numeric, '0.50'::numeric);

INSERT INTO pricing_golden_tiers
            (name, upper_bound, endings, modulus, tolerance)
            VALUES ('tier_4_xlarge', '999999999.00'::numeric, '0.99',
                    '10.00'::numeric, '2.00'::numeric);

CREATE UNIQUE INDEX IF NOT EXISTS uq_prices_one_approved_active
        ON prices (product_sku, channel_id, scheme_code)
        WHERE status = 'approved' AND valid_to IS NULL;

CREATE OR REPLACE FUNCTION prices_check_initial_status()
        RETURNS TRIGGER AS $fn$
        BEGIN
            IF NEW.status NOT IN ('draft','auto_approved') THEN
                RAISE EXCEPTION
                  'invalid_initial_status: estado inicial % no permitido. '
                  'Sólo draft o auto_approved.', NEW.status
                  USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS prices_initial_status_trg ON prices;

CREATE TRIGGER prices_initial_status_trg
        BEFORE INSERT ON prices
        FOR EACH ROW
        EXECUTE FUNCTION prices_check_initial_status();;

CREATE OR REPLACE FUNCTION prices_validate_transition()
        RETURNS TRIGGER AS $fn$
        BEGIN
            -- Permitir UPDATEs que NO cambien el status (e.g. update breakdown).
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;
            -- Validar la transición contra la tabla canónica.
            PERFORM 1
              FROM price_state_transitions
             WHERE from_status = OLD.status AND to_status = NEW.status;
            IF NOT FOUND THEN
                RAISE EXCEPTION
                  'invalid_transition: % → % no permitida.',
                  OLD.status, NEW.status
                  USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS prices_state_machine_trg ON prices;

CREATE TRIGGER prices_state_machine_trg
        BEFORE UPDATE ON prices
        FOR EACH ROW
        EXECUTE FUNCTION prices_validate_transition();;

UPDATE alembic_version SET version_num='20260507_021' WHERE alembic_version.version_num = '20260507_020';

-- Running upgrade 20260507_021 -> 20260507_022

DO $do$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mt_app') THEN
                CREATE ROLE mt_app NOLOGIN;
            END IF;
        END
        $do$;;

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
        $fn$;;

ALTER TABLE products ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS products_read_all ON products;

DROP POLICY IF EXISTS products_write_comercial ON products;

DROP POLICY IF EXISTS products_finas_read ON products;

DROP POLICY IF EXISTS products_finas_write_comercial ON products;

DROP POLICY IF EXISTS products_finas_write_ti ON products;

CREATE POLICY products_finas_read ON products
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));;

CREATE POLICY products_finas_write_comercial ON products
            FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));;

CREATE POLICY products_finas_update_comercial ON products
            FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));;

CREATE POLICY products_finas_delete_ti ON products
            FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));;

ALTER TABLE costs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS costs_read_all ON costs;

DROP POLICY IF EXISTS costs_write_comercial ON costs;

DROP POLICY IF EXISTS costs_finas_read ON costs;

DROP POLICY IF EXISTS costs_finas_insert_comercial ON costs;

DROP POLICY IF EXISTS costs_finas_update_gerente ON costs;

DROP POLICY IF EXISTS costs_finas_full_ti ON costs;

CREATE POLICY costs_finas_read ON costs
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));;

CREATE POLICY costs_finas_insert_comercial ON costs
            FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ('comercial','ti','ti_integracion','admin'));;

CREATE POLICY costs_finas_update_gerente ON costs
            FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin'));;

CREATE POLICY costs_finas_delete_ti ON costs
            FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));;

ALTER TABLE prices ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS prices_read_all ON prices;

DROP POLICY IF EXISTS prices_finas_read ON prices;

DROP POLICY IF EXISTS prices_finas_insert_comercial ON prices;

DROP POLICY IF EXISTS prices_finas_update_gerente ON prices;

DROP POLICY IF EXISTS prices_finas_full_ti ON prices;

CREATE POLICY prices_finas_read ON prices
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));;

CREATE POLICY prices_finas_insert_comercial ON prices
            FOR INSERT TO mt_app
            WITH CHECK (
                resolve_user_role() IN ('comercial','ti','ti_integracion','admin')
                AND (
                    resolve_user_role() IN ('ti','ti_integracion','admin')
                    OR status = 'draft'
                )
            );;

CREATE POLICY prices_finas_update_gerente ON prices
            FOR UPDATE TO mt_app
            USING (resolve_user_role() IN ('gerente','gerente_comercial','ti','ti_integracion','admin'))
            WITH CHECK (resolve_user_role() IN ('gerente','gerente_comercial','ti','ti_integracion','admin'));;

CREATE POLICY prices_finas_update_comercial_draft ON prices
            FOR UPDATE TO mt_app
            USING (
                resolve_user_role() IN ('comercial')
                AND status = 'draft'
            )
            WITH CHECK (
                resolve_user_role() IN ('comercial')
                AND status = 'draft'
            );;

CREATE POLICY prices_finas_delete_ti ON prices
            FOR DELETE TO mt_app
            USING (resolve_user_role() IN ('ti','ti_integracion','admin'));;

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_events_read ON audit_events;

DROP POLICY IF EXISTS audit_events_insert ON audit_events;

DROP POLICY IF EXISTS audit_events_finas_read ON audit_events;

DROP POLICY IF EXISTS audit_events_finas_insert ON audit_events;

CREATE POLICY audit_events_finas_read ON audit_events
            FOR SELECT TO mt_app
            USING (resolve_user_role() IN ('gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));;

CREATE POLICY audit_events_finas_insert ON audit_events
            FOR INSERT TO mt_app
            WITH CHECK (resolve_user_role() IN ('comercial','gerente','gerente_comercial','ti','ti_integracion','admin','auditor'));;

CREATE OR REPLACE FUNCTION audit_events_forbid_mutation()
        RETURNS TRIGGER AS $fn$
        BEGIN
            RAISE EXCEPTION
              'forbidden_audit_mutation: audit_events es append-only.'
              USING ERRCODE = 'insufficient_privilege';
        END;
        $fn$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS audit_events_immutable_trg ON audit_events;

CREATE TRIGGER audit_events_immutable_trg
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION audit_events_forbid_mutation();;

UPDATE alembic_version SET version_num='20260507_022' WHERE alembic_version.version_num = '20260507_021';

-- Running upgrade 20260507_022 -> 20260507_023

CREATE TABLE product_datasheets (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    kind VARCHAR(32) NOT NULL, 
    storage_path TEXT NOT NULL, 
    original_filename TEXT NOT NULL, 
    file_size_bytes INTEGER DEFAULT 0 NOT NULL, 
    sku_list JSONB DEFAULT '[]'::jsonb NOT NULL, 
    specs_extracted JSONB DEFAULT '{}'::jsonb NOT NULL, 
    import_run_id UUID, 
    uploaded_by UUID, 
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_product_datasheets_kind CHECK (kind IN ('ficha_tecnica','compliance','manual')), 
    CONSTRAINT uq_product_datasheets_storage_path UNIQUE (storage_path), 
    FOREIGN KEY(import_run_id) REFERENCES import_runs (id) ON DELETE SET NULL, 
    FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_product_datasheets_kind ON product_datasheets (kind);

CREATE TRIGGER trg_product_datasheets_updated_at BEFORE UPDATE ON product_datasheets FOR EACH ROW EXECUTE FUNCTION set_updated_at();;

ALTER TABLE import_runs DROP CONSTRAINT IF EXISTS ck_import_runs_type;;

ALTER TABLE import_runs ADD CONSTRAINT ck_import_runs_type CHECK (import_type IN ('pim','costs','datasheets','materials'));

UPDATE alembic_version SET version_num='20260507_023' WHERE alembic_version.version_num = '20260507_022';

-- Running upgrade 20260507_023 -> 20260507_024

ALTER TABLE match_candidates ADD COLUMN raw_payload_jsonb JSONB;

ALTER TABLE match_candidates ADD COLUMN fetched_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE match_candidates ADD COLUMN calibrated_score NUMERIC(5, 4);

ALTER TABLE match_candidates ADD COLUMN vlm_verdict TEXT;

ALTER TABLE match_candidates ADD COLUMN vlm_reasoning TEXT;

ALTER TABLE match_candidates ADD COLUMN pipeline_version TEXT;

ALTER TABLE match_candidates ADD COLUMN calibrator_version TEXT;

ALTER TABLE match_candidates ADD CONSTRAINT ck_match_candidates_vlm_verdict CHECK (vlm_verdict IS NULL OR vlm_verdict IN ('match','drift','reject','uncertain'));

ALTER TABLE match_candidates ADD CONSTRAINT ck_match_candidates_calibrated_score_range CHECK (calibrated_score IS NULL OR (calibrated_score >= 0 AND calibrated_score <= 1));

CREATE INDEX idx_match_candidates_calibrated ON match_candidates (product_sku, calibrated_score) WHERE calibrated_score IS NOT NULL;

UPDATE alembic_version SET version_num='20260507_024' WHERE alembic_version.version_num = '20260507_023';

-- Running upgrade 20260507_024 -> 20260507_025

CREATE TABLE cdc_events (
    id BIGSERIAL NOT NULL, 
    entity_type TEXT NOT NULL, 
    entity_id TEXT NOT NULL, 
    action TEXT NOT NULL, 
    payload_jsonb JSONB DEFAULT '{}'::jsonb NOT NULL, 
    status TEXT DEFAULT 'pending' NOT NULL, 
    attempts INTEGER DEFAULT 0 NOT NULL, 
    last_error TEXT, 
    processed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_cdc_events_action CHECK (action IN ('insert','update','delete')), 
    CONSTRAINT ck_cdc_events_status CHECK (status IN ('pending','processed','failed','dead_letter')), 
    CONSTRAINT ck_cdc_events_attempts_nonneg CHECK (attempts >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cdc_events_pending
            ON cdc_events (id)
            WHERE status = 'pending';;

CREATE INDEX IF NOT EXISTS idx_cdc_events_entity
            ON cdc_events (entity_type, entity_id);;

CREATE OR REPLACE FUNCTION cdc_emit_product()
        RETURNS TRIGGER AS $fn$
        DECLARE
            v_action TEXT;
            v_entity_id TEXT;
            v_payload JSONB;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_action := 'delete';
                v_entity_id := OLD.sku;
                v_payload := jsonb_build_object('sku', OLD.sku);
            ELSE
                IF TG_OP = 'INSERT' THEN
                    v_action := 'insert';
                ELSE
                    v_action := 'update';
                END IF;
                v_entity_id := NEW.sku;
                v_payload := jsonb_build_object(
                    'sku', NEW.sku,
                    'name_en', NEW.name_en,
                    'family', NEW.family,
                    'subfamily', NEW.subfamily,
                    'type', NEW.type,
                    'material', NEW.material,
                    'dn', NEW.dn,
                    'pn', NEW.pn,
                    'connection', NEW.connection,
                    'brand', NEW.brand,
                    'active', NEW.active
                );
            END IF;

            INSERT INTO cdc_events (entity_type, entity_id, action, payload_jsonb)
            VALUES ('product', v_entity_id, v_action, v_payload);

            -- LISTEN/NOTIFY hint para suscriptores futuros (Fase 2+,
            -- Supabase Realtime / Debezium consumirá vía WAL).
            PERFORM pg_notify('cdc_events', json_build_object(
                'entity_type', 'product',
                'entity_id', v_entity_id,
                'action', v_action
            )::text);

            RETURN COALESCE(NEW, OLD);
        END;
        $fn$ LANGUAGE plpgsql;;

DROP TRIGGER IF EXISTS trg_cdc_emit_product ON products;

CREATE TRIGGER trg_cdc_emit_product
            AFTER INSERT OR UPDATE OR DELETE ON products
            FOR EACH ROW
            EXECUTE FUNCTION cdc_emit_product();;

INSERT INTO permissions (code, description) VALUES
            ('graphrag:admin', 'Administrar GraphRAG (replay CDC, ver health avanzado)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE p.code = 'graphrag:admin'
          AND r.code IN ('ti_integracion', 'admin')
        ON CONFLICT DO NOTHING;;

UPDATE alembic_version SET version_num='20260507_025' WHERE alembic_version.version_num = '20260507_024';

-- Running upgrade 20260507_025 -> 20260507_026

INSERT INTO permissions (code, description) VALUES
            ('matches:read',           'Listar/ver match candidates'),
            ('matches:write',          'Refresh/validate/discard match candidates'),
            ('prices:override_review', 'Disparar review/override sobre prices (counter-proposals, what-if)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO permissions (code, description) VALUES
            ('channels:read',   'Listar canales'),
            ('channels:manage', 'Gestionar estado de canales'),
            ('graphrag:admin',  'Administrar GraphRAG (replay CDC, ver health avanzado)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO roles (code, name, description, is_system) VALUES
            ('auditor', 'Auditor', 'Acceso read-only — auditorías internas/externas', true)
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'comercial'         AND p.code IN ('matches:read', 'matches:write'))
         OR (r.code = 'gerente_comercial' AND p.code IN ('matches:write', 'channels:manage', 'prices:override_review'))
         OR (r.code = 'ti_integracion'    AND p.code IN ('channels:manage', 'graphrag:admin'))
         OR (r.code = 'auditor'           AND p.code IN ('matches:read', 'channels:read'))
         OR (r.code = 'admin'             AND p.code IN (
                'matches:read', 'matches:write',
                'channels:read', 'channels:manage',
                'prices:override_review', 'graphrag:admin'
            ))
        ON CONFLICT DO NOTHING;;

UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('comercial', 'gerente_comercial', 'ti_integracion', 'auditor', 'admin');;

UPDATE alembic_version SET version_num='20260507_026' WHERE alembic_version.version_num = '20260507_025';

-- Running upgrade 20260507_026 -> 20260507_027

CREATE TABLE feature_flags (
    key TEXT NOT NULL, 
    value_jsonb JSONB DEFAULT '{"enabled": false}'::jsonb NOT NULL, 
    updated_by UUID, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (key), 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('MT_LIVE_NETWORK_AMAZON_UAE', '{"enabled": false}'::jsonb)
            ON CONFLICT (key) DO NOTHING;;

INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('MT_LIVE_NETWORK_NOON_UAE', '{"enabled": false}'::jsonb)
            ON CONFLICT (key) DO NOTHING;;

INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('MT_LIVE_NETWORK_SP_API', '{"enabled": false}'::jsonb)
            ON CONFLICT (key) DO NOTHING;;

INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('MT_LIVE_NETWORK_NOON_API', '{"enabled": false}'::jsonb)
            ON CONFLICT (key) DO NOTHING;;

INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('MT_LIVE_NETWORK_VLM_JUDGE', '{"enabled": false}'::jsonb)
            ON CONFLICT (key) DO NOTHING;;

INSERT INTO feature_flags (key, value_jsonb)
            VALUES ('KILL_SWITCH', '{"enabled": false}'::jsonb)
            ON CONFLICT (key) DO NOTHING;;

INSERT INTO permissions (code, description) VALUES
            ('flags:manage',
             'Listar y togglear feature flags (excluye kill-switch)'),
            ('kill-switch:execute',
             'Engage / disengage global kill-switch (corta toda la red real)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE
            (r.code = 'ti_integracion' AND p.code IN ('flags:manage', 'kill-switch:execute'))
         OR (r.code = 'admin'          AND p.code IN ('flags:manage', 'kill-switch:execute'))
        ON CONFLICT DO NOTHING;;

UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('ti_integracion', 'admin');;

UPDATE alembic_version SET version_num='20260507_027' WHERE alembic_version.version_num = '20260507_026';

-- Running upgrade 20260507_027 -> 20260507_028

CREATE TABLE golden_labels (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    sku TEXT NOT NULL, 
    candidate_id UUID NOT NULL, 
    label INTEGER NOT NULL, 
    score NUMERIC(5, 4) NOT NULL, 
    judged_by UUID, 
    judged_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    notes TEXT, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_golden_labels_label_binary CHECK (label IN (0, 1)), 
    CONSTRAINT ck_golden_labels_score_range CHECK (score >= 0 AND score <= 1), 
    CONSTRAINT uq_golden_labels_sku_candidate UNIQUE (sku, candidate_id), 
    FOREIGN KEY(sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(candidate_id) REFERENCES match_candidates (id) ON DELETE CASCADE, 
    FOREIGN KEY(judged_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_golden_labels_sku ON golden_labels (sku);

CREATE INDEX idx_golden_labels_judged_at ON golden_labels (judged_at);

CREATE TABLE calibrator_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    version TEXT NOT NULL, 
    model_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    trained_on_count INTEGER DEFAULT 0 NOT NULL, 
    brier_score NUMERIC(7, 6), 
    ece NUMERIC(7, 6), 
    is_active BOOLEAN DEFAULT false NOT NULL, 
    trained_by UUID, 
    trained_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    promoted_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_calibrator_versions_count_nonneg CHECK (trained_on_count >= 0), 
    UNIQUE (version), 
    FOREIGN KEY(trained_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_calibrator_versions_active
            ON calibrator_versions ((is_active))
            WHERE is_active = true;;

INSERT INTO permissions (code, description) VALUES
            ('calibrator:train',
             'Entrenar y promover versiones del IsotonicCalibrator')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE p.code = 'calibrator:train'
          AND r.code IN ('ti_integracion', 'admin')
        ON CONFLICT DO NOTHING;;

UPDATE roles r
        SET permissions_snapshot = COALESCE(
            (
                SELECT jsonb_agg(p.code ORDER BY p.code)
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = r.id
            ),
            '[]'::jsonb
        )
        WHERE r.code IN ('ti_integracion', 'admin');;

UPDATE alembic_version SET version_num='20260507_028' WHERE alembic_version.version_num = '20260507_027';

-- Running upgrade 20260507_028 -> 20260507_029

CREATE TABLE notifications (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    recipient_user_id UUID NOT NULL, 
    kind TEXT NOT NULL, 
    payload JSONB DEFAULT '{}'::jsonb NOT NULL, 
    seen_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX idx_notifications_inbox ON notifications (recipient_user_id, created_at DESC);

CREATE INDEX idx_notifications_kind ON notifications (kind);

ALTER TABLE prices ADD COLUMN escalated BOOLEAN DEFAULT false NOT NULL;

ALTER TABLE prices ADD COLUMN escalated_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_prices_escalated
            ON prices (escalated_at)
            WHERE escalated = true;;

ALTER TABLE users ADD COLUMN delegate_user_id UUID;

ALTER TABLE users ADD FOREIGN KEY(delegate_user_id) REFERENCES users (id) ON DELETE SET NULL;

CREATE INDEX idx_users_delegate ON users (delegate_user_id);

UPDATE alembic_version SET version_num='20260507_029' WHERE alembic_version.version_num = '20260507_028';

-- Running upgrade 20260507_029 -> 20260508_035

CREATE TYPE compatibility_kind AS ENUM (
            'spare_part',
            'accessory',
            'replaces',
            'replaced_by',
            'compatible_with'
        );

CREATE TYPE compatibility_kind AS ENUM ('spare_part', 'accessory', 'replaces', 'replaced_by', 'compatible_with');

CREATE TABLE product_compatibility (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    product_sku TEXT NOT NULL, 
    compatible_with_sku TEXT NOT NULL, 
    kind compatibility_kind NOT NULL, 
    notes TEXT, 
    position SMALLINT DEFAULT 0 NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_by UUID, 
    PRIMARY KEY (id), 
    CONSTRAINT chk_no_self_compatibility CHECK (product_sku <> compatible_with_sku), 
    CONSTRAINT uq_product_compatibility UNIQUE (product_sku, compatible_with_sku, kind), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(compatible_with_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX idx_product_compatibility_sku ON product_compatibility (product_sku);

CREATE INDEX idx_product_compatibility_with ON product_compatibility (compatible_with_sku);

CREATE INDEX idx_product_compatibility_kind ON product_compatibility (kind);

UPDATE alembic_version SET version_num='20260508_035' WHERE alembic_version.version_num = '20260507_029';

-- Running upgrade 20260507_029 -> 20260508_033

CREATE TABLE certifications (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code TEXT NOT NULL, 
    name TEXT NOT NULL, 
    issued_by TEXT, 
    scope TEXT, 
    logo_url TEXT, 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_certifications_code UNIQUE (code)
);

CREATE TABLE applications (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    code TEXT NOT NULL, 
    name TEXT NOT NULL, 
    description TEXT, 
    active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_applications_code UNIQUE (code)
);

CREATE TABLE product_certifications (
    product_sku TEXT NOT NULL, 
    certification_id UUID NOT NULL, 
    certificate_pdf_asset_id UUID, 
    obtained_at DATE, 
    expires_at DATE, 
    notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (product_sku, certification_id), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(certification_id) REFERENCES certifications (id) ON DELETE RESTRICT
);

CREATE INDEX idx_product_certifications_cert ON product_certifications (certification_id);

CREATE TABLE product_applications (
    product_sku TEXT NOT NULL, 
    application_id UUID NOT NULL, 
    is_primary BOOLEAN DEFAULT false NOT NULL, 
    position SMALLINT DEFAULT 0 NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (product_sku, application_id), 
    FOREIGN KEY(product_sku) REFERENCES products (sku) ON DELETE CASCADE, 
    FOREIGN KEY(application_id) REFERENCES applications (id) ON DELETE RESTRICT
);

CREATE INDEX idx_product_applications_app ON product_applications (application_id);

CREATE INDEX idx_product_applications_primary
            ON product_applications (product_sku)
            WHERE is_primary = true;;

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('CE', 'CE Marking', 'European Commission', 'European conformity');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('WRAS', 'WRAS Approved', 'WRAS', 'UK drinking water');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('NSF', 'NSF/ANSI 61', 'NSF International', 'Drinking water — health effects');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('KIWA', 'KIWA Approval', 'KIWA Nederland', 'Drinking water — Netherlands');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('ACS', 'ACS Sanitaire', 'ANSES France', 'Drinking water — France');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('ATEX', 'ATEX', 'EU Directive 2014/34/EU', 'Explosive atmospheres');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('FM', 'FM Approved', 'FM Approvals', 'Fire protection');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('UL', 'UL Listed', 'UL LLC', 'North America safety');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('CSA', 'CSA Group', 'Canadian Standards Association', 'Canadian safety');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('ROHS', 'RoHS', 'EU Directive 2011/65/EU', 'Hazardous substances restriction');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('REACH', 'REACH', 'EU Regulation 1907/2006', 'Chemical substances');

INSERT INTO certifications (code, name, issued_by, scope) VALUES ('ISO9001', 'ISO 9001:2015', 'ISO', 'Quality management systems');

INSERT INTO applications (code, name, description) VALUES ('water', 'Water', 'Drinking water and general water systems');

INSERT INTO applications (code, name, description) VALUES ('gas', 'Gas', 'Natural gas, LPG, and combustion gas systems');

INSERT INTO applications (code, name, description) VALUES ('oil', 'Oil', 'Oil-based fluids, fuel oils, lubricants');

INSERT INTO applications (code, name, description) VALUES ('food', 'Food & Beverage', 'Food-contact applications, beverage processing');

INSERT INTO applications (code, name, description) VALUES ('hvac', 'HVAC', 'Heating, ventilation, air conditioning');

INSERT INTO applications (code, name, description) VALUES ('fire-fighting', 'Fire Fighting', 'Sprinkler and fire suppression systems');

INSERT INTO applications (code, name, description) VALUES ('irrigation', 'Irrigation', 'Agricultural and landscape irrigation');

INSERT INTO applications (code, name, description) VALUES ('industrial', 'Industrial', 'General industrial process fluids');

INSERT INTO permissions (code, description)
        VALUES ('admin:vocabularies', 'Gestionar vocabularios curados (certifications, applications)')
        ON CONFLICT (code) DO NOTHING;;

INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.code IN ('ti_integracion', 'admin')
          AND p.code = 'admin:vocabularies'
        ON CONFLICT DO NOTHING;;

INSERT INTO alembic_version (version_num) VALUES ('20260508_033') RETURNING alembic_version.version_num;

-- Running upgrade 20260507_029 -> 20260508_030

ALTER TABLE product_images RENAME TO product_assets;

DROP INDEX IF EXISTS idx_images_sku_role;

DROP INDEX IF EXISTS idx_product_images_hash;

ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS ck_images_status;

ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS ck_product_images_image_status;

ALTER TABLE product_assets ADD COLUMN kind TEXT DEFAULT 'photo' NOT NULL;

ALTER TABLE product_assets ADD COLUMN bucket TEXT DEFAULT 'product-images' NOT NULL;

ALTER TABLE product_assets ADD COLUMN locale TEXT;

ALTER TABLE product_assets ADD COLUMN caption TEXT;

ALTER TABLE product_assets ADD COLUMN variants JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE product_assets ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb NOT NULL;

ALTER TABLE product_assets ADD COLUMN revision TEXT;

ALTER TABLE product_assets ADD COLUMN supersedes_id UUID;

ALTER TABLE product_assets ADD FOREIGN KEY(supersedes_id) REFERENCES product_assets (id) ON DELETE SET NULL;

ALTER TABLE product_assets ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE product_assets ADD COLUMN archived_by UUID;

ALTER TABLE product_assets ADD FOREIGN KEY(archived_by) REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE product_assets ADD COLUMN position INTEGER DEFAULT 0 NOT NULL;

UPDATE product_assets
        SET
            metadata = CASE
                WHEN width IS NOT NULL OR height IS NOT NULL
                THEN jsonb_build_object('width', width, 'height', height)
                ELSE '{}'::jsonb
            END,
            bucket = 'product-images',
            kind   = 'photo';

UPDATE product_assets
        SET status = CASE
            WHEN image_status = 'pending'   THEN 'pending_upload'
            WHEN image_status = 'mirroring' THEN 'processing'
            WHEN image_status = 'failed'    THEN 'broken'
            ELSE status  -- 'mirrored' → stays as current status (active/archived/broken)
        END
        WHERE image_status != 'mirrored';

ALTER TABLE product_assets ALTER COLUMN role DROP NOT NULL;

ALTER TABLE product_assets DROP COLUMN image_status;

ALTER TABLE product_assets
        ADD CONSTRAINT ck_assets_status
        CHECK (status IN ('active','archived','broken','pending_upload','processing'));

ALTER TABLE product_assets
        ADD CONSTRAINT ck_assets_kind
        CHECK (kind IN (
            'photo','banner','datasheet_pdf','exploded_3d',
            'section_drawing','dimension_drawing','certificate_pdf',
            'video_link','external_url','mirror_url'
        ));

ALTER TABLE product_assets
        ADD CONSTRAINT uq_assets_bucket_path
        UNIQUE (bucket, storage_path);

CREATE INDEX idx_product_assets_sku_kind ON product_assets (sku, kind, position);

CREATE INDEX idx_product_assets_status
            ON product_assets (status)
            WHERE status != 'archived';

CREATE INDEX idx_product_assets_locale
            ON product_assets (locale)
            WHERE locale IS NOT NULL;

CREATE INDEX idx_product_assets_hash ON product_assets (hash_sha256);

INSERT INTO alembic_version (version_num) VALUES ('20260508_030') RETURNING alembic_version.version_num;

-- Running upgrade 20260508_030, 20260508_033, 20260508_035 -> 80af479d704d

DELETE FROM alembic_version WHERE alembic_version.version_num = '20260508_030';

DELETE FROM alembic_version WHERE alembic_version.version_num = '20260508_033';

UPDATE alembic_version SET version_num='80af479d704d' WHERE alembic_version.version_num = '20260508_035';

COMMIT;

