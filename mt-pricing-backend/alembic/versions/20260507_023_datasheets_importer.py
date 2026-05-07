"""datasheets_importer — Sprint 4 / US-1A-06-04.

Cambios:

- Crea tabla ``product_datasheets`` (PDF asociado a uno o más SKUs).
- ``import_runs.import_type`` ya soporta ``'datasheets'`` desde la migración
  019 (CHECK extendido). Aquí lo **garantizamos idempotente** por si esta
  migración se aplica antes que la 019 en algún hotfix path: dropea y
  recrea el CHECK con todos los kinds vigentes.

Slot 023 preasignado al agente Backend Engineer Sprint 4. Slots 021/022
están reservados para US-1A-07-02 (RLS finas) y US-1A-07-03 (audit
triggers); este migration los **respeta** apuntando ``down_revision`` a
``20260507_022``. Cuando 021/022 aterrizen, el chain queda 020 → 021 → 022
→ 023.

NO se aplica con ``alembic upgrade head`` automáticamente — el agente
Backend reporta el patch y el orquestador del sprint decide cuándo.

Revision ID: 20260507_023
Revises: 20260507_022
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507_023"
down_revision: str | None = "20260507_022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- product_datasheets ---------------------------------------------
    op.create_table(
        "product_datasheets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column(
            "file_size_bytes", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "sku_list",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "specs_extracted",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "import_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
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
        sa.CheckConstraint(
            "kind IN ('ficha_tecnica','compliance','manual')",
            name="ck_product_datasheets_kind",
        ),
        sa.UniqueConstraint("storage_path", name="uq_product_datasheets_storage_path"),
    )
    op.create_index(
        "idx_product_datasheets_kind", "product_datasheets", ["kind"]
    )
    op.execute(
        "CREATE TRIGGER trg_product_datasheets_updated_at "
        "BEFORE UPDATE ON product_datasheets "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )

    # ---- import_runs.kind: garantía idempotente -------------------------
    op.execute("ALTER TABLE import_runs DROP CONSTRAINT IF EXISTS ck_import_runs_type;")
    op.create_check_constraint(
        "ck_import_runs_type",
        "import_runs",
        "import_type IN ('pim','costs','datasheets','materials')",
    )


def downgrade() -> None:
    # Revierte sólo la tabla nueva. El CHECK de import_runs.import_type
    # se queda con todos los kinds (lo gestiona la 019 al hacer downgrade).
    op.execute(
        "DROP TRIGGER IF EXISTS trg_product_datasheets_updated_at "
        "ON product_datasheets;"
    )
    op.drop_index("idx_product_datasheets_kind", table_name="product_datasheets")
    op.drop_table("product_datasheets")
