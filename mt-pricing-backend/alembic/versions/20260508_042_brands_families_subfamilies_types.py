"""Stage 1 Opción C — brands + families + subfamilies + product_types + FKs.

**ORIGEN DE ESTA MIGRACIÓN:** las migraciones 042 y 043 estaban ausentes del
repo (gap en la numeración entre 041 y 044). Sin embargo, mig. 048 promueve
``products.brand_id`` y ``products.family_id`` a NOT NULL — implicando que
una mig. 042/043 las creó en algún momento, pero ese archivo no fue
committeado. Los ORM models en ``app/db/models/vocabularies.py`` los
declaran (Brand/Family/Subfamily/ProductType) → schema reconstituido aquí
desde los models, como stub para reparar el chain de alembic.

Reconstituye:
- ``brands`` (code, name, logo_url, website_url, active, timestamps)
- ``families`` (code, name, description, sort_order, active, timestamps)
- ``subfamilies`` (family_id FK→families, code, name, ...) — UNIQUE(family_id, code)
- ``product_types`` (subfamily_id FK→subfamilies, code, name, ...) — UNIQUE(subfamily_id, code)
- ``products.brand_id`` FK→brands (nullable inicialmente; mig 048 promueve a NOT NULL)
- ``products.family_id`` FK→families (idem)
- ``products.subfamily_id`` FK→subfamilies (queda nullable indefinidamente)
- ``products.type_id`` FK→product_types (idem)

Seed: 1 brand_default y 1 family_default para satisfacer cobertura inicial.
La data real venía de Stage 1 backfill que no podemos reproducir aquí; el
ORM expects 100% coverage tras mig. 048 (productos sin brand/family abortan
la migración). Para entornos de test desde cero (testcontainers) seedeamos
2 filas mínimas; en producción ese backfill ya está hecho.

Revision ID: 20260508_042
Revises: 20260508_041
Create Date: 2026-05-11 (stub reconstituido)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260508_042"
down_revision: str | None = "20260508_041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_taxonomy_table(name: str, *, has_parent_fk: tuple[str, str] | None = None) -> None:
    """Crea tabla taxonomy con shape estándar (code, name, description, sort_order, active, timestamps).

    has_parent_fk: tupla (col_name, parent_table) si la tabla cuelga de otra.
    """
    cols = [
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
    ]
    if has_parent_fk is not None:
        col_name, parent_table = has_parent_fk
        cols.append(
            sa.Column(
                col_name,
                PgUUID(as_uuid=True),
                sa.ForeignKey(f"{parent_table}.id", ondelete="RESTRICT"),
                nullable=False,
            )
        )
    cols.extend(
        [
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "sort_order",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
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
        ]
    )

    if has_parent_fk is None:
        # Tabla top-level: code UNIQUE global
        op.create_table(name, *cols, sa.UniqueConstraint("code", name=f"uq_{name}_code"))
    else:
        # Tabla anidada: code UNIQUE dentro del parent
        col_name = has_parent_fk[0]
        op.create_table(
            name,
            *cols,
            sa.UniqueConstraint(col_name, "code", name=f"uq_{name}_{col_name[:-3]}_code"),
        )
        op.create_index(f"idx_{name}_{col_name[:-3]}", name, [col_name])
    op.create_index(f"idx_{name}_active", name, ["active"])


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. brands (taxonomía orthogonal — no jerárquica)
    # ------------------------------------------------------------------
    op.create_table(
        "brands",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.UniqueConstraint("code", name="uq_brands_code"),
    )
    op.create_index("idx_brands_active", "brands", ["active"])

    # ------------------------------------------------------------------
    # 2-4. families → subfamilies → product_types (jerarquía top-down)
    # ------------------------------------------------------------------
    _create_taxonomy_table("families")
    _create_taxonomy_table("subfamilies", has_parent_fk=("family_id", "families"))
    _create_taxonomy_table("product_types", has_parent_fk=("subfamily_id", "subfamilies"))

    # ------------------------------------------------------------------
    # 5. Agregar FK columns a products (nullable; mig 048 promueve a NOT NULL
    #    brand_id + family_id; subfamily_id y type_id se quedan nullable)
    # ------------------------------------------------------------------
    op.add_column(
        "products",
        sa.Column(
            "brand_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "family_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "subfamily_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("subfamilies.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "type_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("product_types.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 6. Seed mínimo — un brand y una family default para que la mig 048
    #    de NOT NULL no aborte en entornos de test desde cero. En prod,
    #    el backfill ya está hecho con data real (no se ejecuta aquí).
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO brands (code, name) VALUES ('default', 'Default Brand')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO families (code, name) VALUES ('default', 'Default Family')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # Backfill products.brand_id / family_id con los defaults para satisfacer
    # mig 048 NOT NULL en entornos sin data legacy.
    op.execute(
        """
        UPDATE products
        SET brand_id = (SELECT id FROM brands WHERE code = 'default' LIMIT 1)
        WHERE brand_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE products
        SET family_id = (SELECT id FROM families WHERE code = 'default' LIMIT 1)
        WHERE family_id IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_column("products", "type_id")
    op.drop_column("products", "subfamily_id")
    op.drop_column("products", "family_id")
    op.drop_column("products", "brand_id")

    op.drop_index("idx_product_types_active", table_name="product_types")
    op.drop_index("idx_product_types_subfamily", table_name="product_types")
    op.drop_table("product_types")

    op.drop_index("idx_subfamilies_active", table_name="subfamilies")
    op.drop_index("idx_subfamilies_family", table_name="subfamilies")
    op.drop_table("subfamilies")

    op.drop_index("idx_families_active", table_name="families")
    op.drop_table("families")

    op.drop_index("idx_brands_active", table_name="brands")
    op.drop_table("brands")
