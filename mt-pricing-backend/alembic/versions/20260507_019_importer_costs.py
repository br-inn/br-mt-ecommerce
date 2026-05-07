"""importer_costs + material_compatibilities (US-1A-06-02 / US-1A-06-03).

Cambios:
- Crea tabla ``material_compatibilities`` (US-1A-06-03).
- Extiende ``import_runs`` para soportar ``import_type='materials'`` y añade
  columna ``orphans`` JSONB (US-1A-06-02 — preview costs requiere reportar
  huérfanos por categoría).
- Permission ``imports:write`` ya existe (seeded en ``20260507_009``); aquí
  reusamos.

Decisión sobre ``import_runs.kind``:
- La tabla ``import_runs`` ya existía con un CHECK constraint que aceptaba
  ``('pim','costs','datasheets')``. **Reutilizamos** la columna existente
  ``import_type`` y AMPLIAMOS el CHECK para añadir ``'materials'``. NO se
  introduce un enum PG (el column es VARCHAR + CHECK), por lo que no hay
  ALTER TYPE — sólo DROP/CREATE del CHECK constraint.

NO se aplica en este sprint: ``alembic upgrade head`` se difiere hasta el
merge de Sprint 3.

Revision ID: 20260507_019
Revises: 20260507_018
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507_019"
down_revision: str | None = "20260507_018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- material_compatibilities ----------------------------------------
    op.create_table(
        "material_compatibilities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("producto_descriptor", sa.Text(), nullable=False),
        sa.Column("temperatura_c", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "compatibilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.UniqueConstraint(
            "producto_descriptor",
            "temperatura_c",
            name="uq_material_compatibilities_descriptor_temp",
        ),
    )
    op.create_index(
        "idx_material_compatibilities_descriptor",
        "material_compatibilities",
        ["producto_descriptor"],
    )
    op.execute(
        "CREATE TRIGGER trg_material_compatibilities_updated_at "
        "BEFORE UPDATE ON material_compatibilities "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ---- import_runs: ampliar CHECK + añadir columna orphans ------------
    op.execute("ALTER TABLE import_runs DROP CONSTRAINT IF EXISTS ck_import_runs_type;")
    op.create_check_constraint(
        "ck_import_runs_type",
        "import_runs",
        "import_type IN ('pim','costs','datasheets','materials')",
    )
    op.add_column(
        "import_runs",
        sa.Column(
            "orphans",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("import_runs", "orphans")
    op.execute("ALTER TABLE import_runs DROP CONSTRAINT IF EXISTS ck_import_runs_type;")
    op.create_check_constraint(
        "ck_import_runs_type",
        "import_runs",
        "import_type IN ('pim','costs','datasheets')",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_material_compatibilities_updated_at "
        "ON material_compatibilities;"
    )
    op.drop_index(
        "idx_material_compatibilities_descriptor",
        table_name="material_compatibilities",
    )
    op.drop_table("material_compatibilities")
