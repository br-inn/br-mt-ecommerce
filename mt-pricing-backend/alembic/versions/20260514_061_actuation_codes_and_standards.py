"""Fase 3 — Tablas técnicas: actuation_codes + standards (PDF §9).

Crea las tablas catálogo:

1. ``actuation_codes`` — códigos de actuación canónicos (free shaft, handle,
   gearbox/MR, motorized/motor, pneumatic/pneu). Referenciado por
   ``dimension_rows.actuation_code_id`` (mig. 062).

2. ``standards`` — normas / estándares (ASTM, EN, ISO, …) con edición + URL
   de referencia. Se popula vía importer; seed inicial vacío. Si la tabla
   ``material_components`` existe (creada por taxonomy), se añade
   ``standard_id`` FK nullable.

Resuelve DUP-05 (actuación duplicado en valve_ball / butterfly specs) y
DUP-06 (standards duplicado entre certifications y schemas JSON spec).

Revision ID: 20260514_061
Revises: 20260514_060
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260514_061"
down_revision: str | None = "20260514_060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. actuation_codes — catálogo canónico
    # ------------------------------------------------------------------
    op.create_table(
        "actuation_codes",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_actuation_codes_code"),
        sa.CheckConstraint(
            "type IN ('free_shaft','handle','gearbox','motorized','pneumatic')",
            name="ck_actuation_codes_type",
        ),
    )

    # Seed inicial — 5 códigos canónicos.
    op.execute(
        """
        INSERT INTO actuation_codes (code, name_en, type)
        VALUES
            ('free',   'Free shaft',  'free_shaft'),
            ('handle', 'Handle',      'handle'),
            ('MR',     'Gearbox',     'gearbox'),
            ('motor',  'Motorized',   'motorized'),
            ('pneu',   'Pneumatic',   'pneumatic')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # 2. standards — catálogo de normas (seed vacío)
    # ------------------------------------------------------------------
    op.create_table(
        "standards",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "edition",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("title_en", sa.Text(), nullable=False),
        sa.Column("reference_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", "edition", name="uq_standards_code_edition"),
    )

    # ------------------------------------------------------------------
    # 3. material_components.standard_id (si la tabla existe)
    # ------------------------------------------------------------------
    inspector = inspect(bind)
    if "material_components" in inspector.get_table_names():
        op.add_column(
            "material_components",
            sa.Column(
                "standard_id",
                PgUUID(as_uuid=True),
                sa.ForeignKey("standards.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    else:
        # Defensive log — material_components no aún creado por taxonomy.
        print(
            "[mig 061] material_components no existe — skip añadir standard_id. "
            "Si la tabla se crea más tarde, añadir la columna manualmente o "
            "en una migración follow-up."
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "material_components" in inspector.get_table_names():
        cols = [c["name"] for c in inspector.get_columns("material_components")]
        if "standard_id" in cols:
            op.drop_column("material_components", "standard_id")

    op.drop_table("standards")
    op.drop_table("actuation_codes")
