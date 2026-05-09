"""Stage 4a — promote products.brand_id + family_id to NOT NULL.

Cobertura verificada (2026-05-09): 100% de los 5085 productos tienen brand_id
y family_id no-NULL tras mig. 042 (Stage 1 Opción C). Promover a NOT NULL
elimina la posibilidad de inserciones futuras sin estas FKs y permite que
queries / facets se simplifiquen al asumir presencia.

Diferido a Stage 4b: subfamily_id, type_id, material_id, series_id (cobertura
parcial — esperan classifier ML / clasificación masiva).

NUNCA promover (decisión arquitectónica): display_pair_sku (excepción),
series_id (opt-in marketing).

Defensive backfill antes de SET NOT NULL — falla la migración (con error
explícito) si quedasen NULLs después de mig. 042. Esto protege al operador
de cualquier producto creado entre 042 y 048 sin FK.

Revision ID: 20260509_048
Revises: 20260509_047
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_048"
down_revision: str | None = "20260509_047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Defensive: si por algún motivo quedan productos sin brand_id o
    # family_id (creados después de mig. 042 sin Stage 1 sync), intentar
    # backfill como en mig. 042 antes de SET NOT NULL.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE products p
        SET brand_id = b.id
        FROM brands b
        WHERE p.brand_id IS NULL
          AND p.brand IS NOT NULL
          AND lower(p.brand) = b.code;
        """
    )
    op.execute(
        """
        UPDATE products p
        SET family_id = f.id
        FROM families f
        WHERE p.family_id IS NULL
          AND p.family IS NOT NULL
          AND lower(p.family) = f.code;
        """
    )

    # ------------------------------------------------------------------
    # Hard-fail si quedan NULLs (productos sin brand/family TEXT que
    # tampoco tienen FK). Mejor abortar que dejar la BD en un estado
    # incoherente con el ORM que ahora declarará NOT NULL.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE
            null_brand_count INTEGER;
            null_family_count INTEGER;
        BEGIN
            SELECT count(*) INTO null_brand_count FROM products WHERE brand_id IS NULL;
            SELECT count(*) INTO null_family_count FROM products WHERE family_id IS NULL;
            IF null_brand_count > 0 THEN
                RAISE EXCEPTION 'Mig 048 abortada: % productos sin brand_id', null_brand_count;
            END IF;
            IF null_family_count > 0 THEN
                RAISE EXCEPTION 'Mig 048 abortada: % productos sin family_id', null_family_count;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # Promover a NOT NULL.
    # ------------------------------------------------------------------
    op.alter_column("products", "brand_id", nullable=False)
    op.alter_column("products", "family_id", nullable=False)


def downgrade() -> None:
    op.alter_column("products", "family_id", nullable=True)
    op.alter_column("products", "brand_id", nullable=True)
