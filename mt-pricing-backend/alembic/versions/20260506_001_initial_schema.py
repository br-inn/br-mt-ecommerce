"""initial_schema

Sprint 1 foundations: extensions, users/roles/permissions, products,
audit_events (particionada), jobs (DatabaseScheduler).

Revision ID: 20260506_001
Revises:
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260506_001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
DATA_QUALITY_VALUES = ("complete", "partial", "blocked", "migrated_demo")
TRANSLATION_STATUS_VALUES = ("pending", "draft", "approved")
JOB_STATUS_VALUES = ("idle", "running", "success", "failure", "cancelled")
JOB_OWNER_VALUES = ("infra", "business")
SCHEDULE_TYPE_VALUES = ("cron", "interval")


def _csv(values: tuple[str, ...]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


# --------------------------------------------------------------------------
# upgrade()
# --------------------------------------------------------------------------
def upgrade() -> None:
    # ----- Extensions -----
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    # vector + pg_uuidv7 son deseables pero opcionales en Sprint 1.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # pg_uuidv7 sólo en Supabase Pro — TODO Sprint 2:
    # op.execute("CREATE EXTENSION IF NOT EXISTS pg_uuidv7;")

    # ----- Función updated_at trigger -----
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END
        $$;
        """
    )

    # ----- roles -----
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "permissions_snapshot",
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
    )
    op.create_index("idx_roles_code", "roles", ["code"])

    # ----- permissions -----
    op.create_table(
        "permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ----- role_permissions (M:N) -----
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ----- users -----
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("full_name", sa.Text()),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("locale", sa.String(2), nullable=False, server_default=sa.text("'es'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="SET NULL")
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
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
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("locale IN ('es','en','ar')", name="ck_users_locale"),
    )
    op.create_index("idx_users_role", "users", ["role_id"])
    op.create_index(
        "idx_users_active",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.execute(
        "CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )
    op.execute(
        "CREATE TRIGGER trg_roles_updated_at BEFORE UPDATE ON roles "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- products -----
    op.create_table(
        "products",
        sa.Column("sku", sa.Text(), primary_key=True),
        sa.Column(
            "internal_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("description_en", sa.Text()),
        sa.Column("marketing_copy_en", sa.Text()),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("subfamily", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("material", sa.Text()),
        sa.Column("dn", sa.Text()),
        sa.Column("pn", sa.Text()),
        sa.Column("connection", sa.Text()),
        sa.Column("brand", sa.Text()),
        sa.Column(
            "specs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "packaging",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("weight", sa.Numeric(12, 4)),
        sa.Column("weight_unit", sa.String(8), server_default=sa.text("'kg'")),
        sa.Column("intrastat_code", sa.Text()),
        sa.Column("erp_name", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("image_origin_url", sa.Text()),
        sa.Column(
            "image_status", sa.String(16), nullable=False, server_default=sa.text("'missing'")
        ),
        sa.Column(
            "data_quality", sa.String(16), nullable=False, server_default=sa.text("'partial'")
        ),
        sa.Column(
            "manual_locked_fields",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # embeddings — tipo TEXT[] como fallback genérico (real Vector(1024) lo
        # activa Sprint 2+ con `pgvector` instalado y ALTER TABLE).
        sa.Column("embedding_text", postgresql.ARRAY(sa.Float())),
        sa.Column("embedding_image", postgresql.ARRAY(sa.Float())),
        sa.Column("embedding_model", sa.Text()),
        sa.Column("embedding_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            f"data_quality IN {_csv(DATA_QUALITY_VALUES)}",
            name="ck_products_data_quality",
        ),
        sa.CheckConstraint(
            "image_status IN ('missing','mirrored','failed')",
            name="ck_products_image_status",
        ),
    )
    op.create_index("idx_products_family", "products", ["family"])
    op.create_index("idx_products_brand", "products", ["brand"])
    op.create_index(
        "idx_products_active", "products", ["active"], postgresql_where=sa.text("active = true")
    )
    op.create_index("idx_products_specs_gin", "products", ["specs"], postgresql_using="gin")
    op.execute("CREATE INDEX idx_products_name_trgm ON products USING gin (name_en gin_trgm_ops);")
    op.execute(
        "CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- product_translations -----
    op.create_table(
        "product_translations",
        sa.Column(
            "sku", sa.Text(), sa.ForeignKey("products.sku", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("lang", sa.String(2), primary_key=True),
        sa.Column("name", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("marketing_copy", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "translated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("translated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
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
        sa.CheckConstraint("lang IN ('es','ar','en')", name="ck_translations_lang"),
        sa.CheckConstraint(
            f"status IN {_csv(TRANSLATION_STATUS_VALUES)}",
            name="ck_translations_status",
        ),
    )
    op.create_index("idx_translations_status", "product_translations", ["lang", "status"])
    op.execute(
        "CREATE TRIGGER trg_product_translations_updated_at BEFORE UPDATE ON product_translations "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- product_images -----
    op.create_table(
        "product_images",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "sku", sa.Text(), sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False, unique=True),
        sa.Column("original_url", sa.Text()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("alt_text", sa.Text()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("bytes_size", sa.BigInteger()),
        sa.Column("mime_type", sa.Text()),
        sa.Column("hash_sha256", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint(
            "status IN ('active','archived','broken')",
            name="ck_images_status",
        ),
    )
    op.create_index("idx_images_sku_role", "product_images", ["sku", "role"])
    op.create_index("idx_product_images_hash", "product_images", ["hash_sha256"])

    # ----- audit_events (PARTITIONED BY RANGE event_at) -----
    # Crear como tabla particionada via op.execute para que postgres acepte
    # PARTITION BY RANGE en el create.
    op.execute(
        """
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
        ) PARTITION BY RANGE (event_at);
        """
    )
    op.execute("CREATE INDEX idx_audit_entity ON audit_events (entity_type, entity_id, event_at);")
    op.execute("CREATE INDEX idx_audit_actor ON audit_events (actor_id, event_at);")
    op.execute("CREATE INDEX idx_audit_action ON audit_events (action, event_at);")
    op.execute("CREATE INDEX idx_audit_request ON audit_events (request_id);")

    # Particiones iniciales: el mes corriente + el siguiente.
    # TODO(Sprint 2): job mensual `ensure_audit_partition` que cree la partición
    # del mes siguiente automáticamente.
    op.execute(
        """
        CREATE TABLE audit_events_2026_05 PARTITION OF audit_events
        FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
        """
    )
    op.execute(
        """
        CREATE TABLE audit_events_2026_06 PARTITION OF audit_events
        FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
        """
    )

    # ----- job_definitions -----
    op.create_table(
        "job_definitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner", sa.String(16), nullable=False, server_default=sa.text("'infra'")),
        sa.Column("schedule_type", sa.String(16), nullable=False),
        sa.Column("cron_expression", sa.Text()),
        sa.Column("interval_seconds", sa.Integer()),
        sa.Column("timezone", sa.Text(), nullable=False, server_default=sa.text("'Asia/Dubai'")),
        sa.Column("queue", sa.Text(), nullable=False, server_default=sa.text("'default'")),
        sa.Column(
            "args",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "kwargs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(16)),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_celery_task_id", sa.Text()),
        sa.Column(
            "edited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True)),
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
        sa.CheckConstraint(f"owner IN {_csv(JOB_OWNER_VALUES)}", name="ck_jobs_owner"),
        sa.CheckConstraint(
            f"schedule_type IN {_csv(SCHEDULE_TYPE_VALUES)}",
            name="ck_jobs_schedule_type",
        ),
        sa.CheckConstraint(
            "(schedule_type='cron' AND cron_expression IS NOT NULL) OR "
            "(schedule_type='interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)",
            name="ck_jobs_schedule_complete",
        ),
        sa.CheckConstraint(
            f"last_status IS NULL OR last_status IN {_csv(JOB_STATUS_VALUES)}",
            name="ck_jobs_last_status",
        ),
    )
    op.create_index(
        "idx_jobs_enabled",
        "job_definitions",
        ["enabled"],
        postgresql_where=sa.text("enabled = true"),
    )
    op.create_index("idx_jobs_next_run", "job_definitions", ["next_run_at"])
    op.execute(
        "CREATE TRIGGER trg_job_definitions_updated_at BEFORE UPDATE ON job_definitions "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ----- job_runs -----
    op.create_table(
        "job_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_code", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("retries", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("celery_task_id", sa.Text()),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error", sa.Text()),
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
        sa.CheckConstraint(f"status IN {_csv(JOB_STATUS_VALUES)}", name="ck_job_runs_status"),
    )
    op.create_index("idx_job_runs_job_started", "job_runs", ["job_id", "started_at"])
    op.create_index(
        "idx_job_runs_running",
        "job_runs",
        ["status"],
        postgresql_where=sa.text("status IN ('idle','running')"),
    )
    op.execute(
        "CREATE TRIGGER trg_job_runs_updated_at BEFORE UPDATE ON job_runs "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ------------------------------------------------------------------
    # Seeds Sprint 1
    # ------------------------------------------------------------------
    # Roles base — alineados con architecture §8.2
    op.execute(
        """
        INSERT INTO roles (code, name, description, is_system) VALUES
            ('comercial','Comercial Canal Online & Marketplaces','CRUD catálogo, propone precios',true),
            ('gerente_comercial','Gerente Comercial','Aprueba excepciones, define reglas',true),
            ('ti_integracion','TI Integración','Configura connectors, gestiona usuarios',true),
            ('admin','Sysadmin','BR Innovation / TI MT inicial',true);
        """
    )
    # Permisos básicos
    op.execute(
        """
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
            ('audit:read','Leer audit log');
        """
    )
    # Asignación role→permission básica
    op.execute(
        """
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
         OR (r.code = 'admin');
        """
    )

    # Job definitions Sprint 1 (placeholders — los servicios concretos los
    # registran en Sprint 2). Sólo el housekeeping de DB.
    op.execute(
        """
        INSERT INTO job_definitions
            (code, task_name, description, owner, schedule_type, cron_expression, queue, enabled)
        VALUES
            ('audit_partitions_ensure',
             'app.workers.tasks.audit.ensure_partitions',
             'Crea partición del mes siguiente para audit_events',
             'infra', 'cron', '0 2 1 * *', 'default', true);
        """
    )

    # TODO(Sprint 2): seed admin user — requiere id real desde Supabase auth.users.


# --------------------------------------------------------------------------
# downgrade()
# --------------------------------------------------------------------------
def downgrade() -> None:
    # Orden inverso. Triggers se borran al droppear la tabla.
    op.execute("DROP TABLE IF EXISTS job_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS job_definitions CASCADE;")

    # audit_events particionada — drop incluye particiones via CASCADE.
    op.execute("DROP TABLE IF EXISTS audit_events CASCADE;")

    op.execute("DROP TABLE IF EXISTS product_images CASCADE;")
    op.execute("DROP TABLE IF EXISTS product_translations CASCADE;")
    op.execute("DROP TABLE IF EXISTS products CASCADE;")

    op.execute("DROP TABLE IF EXISTS role_permissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS permissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS roles CASCADE;")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")
    # Extensions deliberately NOT dropped — pueden ser usadas por otros schemas.
