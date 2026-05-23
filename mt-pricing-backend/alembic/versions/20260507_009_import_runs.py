"""import_runs — persistencia de runs del importer batch (US-1A-06-01).

Tabla nueva. Soporta el batch importer Celery (PimImporter) y queda lista
para costs/datasheets en sprints siguientes (Fase 1a backlog).

FSM:
    queued → running → completed | completed_with_errors | failed

RLS:
- Lectura: rol `imports:read` aplicativo (gating en API, NO en RLS — el actor
  del Celery worker es service_role).
- Escritura: sólo backend/worker via service_role.

Revision ID: 20260507_009
Revises: 20260507_008
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260507_009"
down_revision: str | None = "20260507_008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("import_type", sa.String(length=16), nullable=False),
        sa.Column("source_filename", sa.Text(), nullable=False),
        sa.Column("source_storage_path", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column(
            "inserted_rows",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_rows",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "skipped_rows",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "error_rows",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_import_runs"),
        sa.ForeignKeyConstraint(
            ["triggered_by"],
            ["users.id"],
            name="fk_import_runs_triggered_by",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "import_type IN ('pim','costs','datasheets')",
            name="ck_import_runs_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','completed_with_errors','failed')",
            name="ck_import_runs_status",
        ),
    )
    op.create_index("idx_import_runs_status", "import_runs", ["status"], unique=False)
    op.create_index(
        "idx_import_runs_type_created",
        "import_runs",
        ["import_type", "created_at"],
        unique=False,
    )

    # Trigger reusa el helper `set_updated_at` instalado en la migration inicial.
    op.execute(
        """
        CREATE TRIGGER set_import_runs_updated_at
            BEFORE UPDATE ON import_runs
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    # Permission code para gating Celery-trigger endpoints (alias de imports:write
    # para mantener simetría con el wizard sincrono).
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('imports:execute', 'Disparar batch imports async (PIM, costs)')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS set_import_runs_updated_at ON import_runs;")
    op.drop_index("idx_import_runs_type_created", table_name="import_runs")
    op.drop_index("idx_import_runs_status", table_name="import_runs")
    op.drop_table("import_runs")
    op.execute("DELETE FROM permissions WHERE code = 'imports:execute';")
