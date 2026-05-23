"""assets_unification — Wave 1 Asset Unification.

Cambios:
- Rename tabla ``product_images`` → ``product_assets``.
- Columnas nuevas: kind, bucket, locale, caption, variants, metadata, revision,
  supersedes_id (self-FK), archived_at, archived_by (FK users).
- Backfill: metadata ← {width, height}; bucket='product-images'; kind='photo'.
- Migración de image_status → absorb en columna status existente.
- Drop de columnas legacy: image_status, role → posición/kind gestionado por kind+position.
- Índices nuevos: (sku, kind, position), status parcial, locale parcial.
- Unique constraint: (bucket, storage_path).
- Backward compat: mantenemos columna ``role`` como TEXT nullable hasta Wave 2 la
  elimine definitivamente, para que los readers legacy no rompan en el periodo
  de transición. Sí la hacemos nullable para flexibilidad.

Slot 030.

Revision ID: 20260508_030
Revises: 20260507_029
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260508_030"
down_revision: str | None = "20260507_029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Rename table.
    op.rename_table("product_images", "product_assets")

    # 2. Rename any existing check constraints and indexes that reference the old table.
    #    Most DBs keep the constraint name independent of table name, but indexes
    #    may be table-scoped. We drop old indexes first, then recreate.
    op.execute("DROP INDEX IF EXISTS idx_images_sku_role")
    op.execute("DROP INDEX IF EXISTS idx_product_images_hash")

    # 3. Drop old check constraints (role is going nullable, image_status being absorbed).
    op.execute("ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS ck_images_status")
    op.execute(
        "ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS ck_product_images_image_status"
    )

    # 4. Add new columns.
    op.add_column(
        "product_assets",
        sa.Column(
            "kind",
            sa.Text,
            nullable=False,
            server_default=sa.text("'photo'"),
        ),
    )
    op.add_column(
        "product_assets",
        sa.Column(
            "bucket",
            sa.Text,
            nullable=False,
            server_default=sa.text("'product-images'"),
        ),
    )
    op.add_column(
        "product_assets",
        sa.Column("locale", sa.Text, nullable=True),
    )
    op.add_column(
        "product_assets",
        sa.Column("caption", sa.Text, nullable=True),
    )
    op.add_column(
        "product_assets",
        sa.Column(
            "variants",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "product_assets",
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "product_assets",
        sa.Column("revision", sa.Text, nullable=True),
    )
    op.add_column(
        "product_assets",
        sa.Column(
            "supersedes_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("product_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "product_assets",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "product_assets",
        sa.Column(
            "archived_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    # position column for ordering within (sku, kind).
    op.add_column(
        "product_assets",
        sa.Column(
            "position",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # 5. Backfill: metadata ← width/height dimensions; bucket; kind.
    op.execute(
        """
        UPDATE product_assets
        SET
            metadata = CASE
                WHEN width IS NOT NULL OR height IS NOT NULL
                THEN jsonb_build_object('width', width, 'height', height)
                ELSE '{}'::jsonb
            END,
            bucket = 'product-images',
            kind   = 'photo'
        """
    )

    # 6. Migrate image_status → status (absorb legacy mirror-pipeline states).
    #    Old image_status values: pending, mirroring, mirrored, failed.
    #    Existing status values: active, archived, broken.
    #    New unified status values: active, archived, broken, pending_upload, processing.
    op.execute(
        """
        UPDATE product_assets
        SET status = CASE
            WHEN image_status = 'pending'   THEN 'pending_upload'
            WHEN image_status = 'mirroring' THEN 'processing'
            WHEN image_status = 'failed'    THEN 'broken'
            ELSE status  -- 'mirrored' → stays as current status (active/archived/broken)
        END
        WHERE image_status != 'mirrored'
        """
    )

    # 7. Drop legacy columns — image_status absorbed above; role replaced by kind+position.
    #    We make role nullable for backward compat during transition (Wave 2 drops it).
    op.alter_column("product_assets", "role", nullable=True)
    op.drop_column("product_assets", "image_status")

    # 8. Add new check constraint for unified status.
    op.execute(
        """
        ALTER TABLE product_assets
        ADD CONSTRAINT ck_assets_status
        CHECK (status IN ('active','archived','broken','pending_upload','processing'))
        """
    )

    # 9. Add check constraint for kind.
    op.execute(
        """
        ALTER TABLE product_assets
        ADD CONSTRAINT ck_assets_kind
        CHECK (kind IN (
            'photo','banner','datasheet_pdf','exploded_3d',
            'section_drawing','dimension_drawing','certificate_pdf',
            'video_link','external_url','mirror_url'
        ))
        """
    )

    # 10. Add unique constraint (bucket, storage_path).
    op.execute(
        """
        ALTER TABLE product_assets
        ADD CONSTRAINT uq_assets_bucket_path
        UNIQUE (bucket, storage_path)
        """
    )

    # 11. New indexes.
    op.create_index(
        "idx_product_assets_sku_kind",
        "product_assets",
        ["sku", "kind", "position"],
    )
    op.execute(
        """
        CREATE INDEX idx_product_assets_status
            ON product_assets (status)
            WHERE status != 'archived'
        """
    )
    op.execute(
        """
        CREATE INDEX idx_product_assets_locale
            ON product_assets (locale)
            WHERE locale IS NOT NULL
        """
    )
    op.create_index(
        "idx_product_assets_hash",
        "product_assets",
        ["hash_sha256"],
    )


def downgrade() -> None:
    # Reverse in the opposite order.
    op.drop_index("idx_product_assets_hash", table_name="product_assets")
    op.execute("DROP INDEX IF EXISTS idx_product_assets_locale")
    op.execute("DROP INDEX IF EXISTS idx_product_assets_status")
    op.drop_index("idx_product_assets_sku_kind", table_name="product_assets")

    op.execute("ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS uq_assets_bucket_path")
    op.execute("ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS ck_assets_kind")
    op.execute("ALTER TABLE product_assets DROP CONSTRAINT IF EXISTS ck_assets_status")

    # Re-add image_status column.
    op.add_column(
        "product_assets",
        sa.Column(
            "image_status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )

    # Reverse status migration.
    op.execute(
        """
        UPDATE product_assets
        SET image_status = CASE
            WHEN status = 'pending_upload' THEN 'pending'
            WHEN status = 'processing'     THEN 'mirroring'
            WHEN status = 'broken'         THEN 'failed'
            ELSE 'mirrored'
        END,
        status = CASE
            WHEN status IN ('pending_upload','processing') THEN 'active'
            ELSE status
        END
        """
    )

    # Restore role as NOT NULL (best-effort, may fail if NULLs exist).
    op.alter_column("product_assets", "role", nullable=False, server_default=sa.text("'main'"))

    # Re-add old check constraints.
    op.execute(
        """
        ALTER TABLE product_assets
        ADD CONSTRAINT ck_images_status
        CHECK (status IN ('active','archived','broken'))
        """
    )
    op.execute(
        """
        ALTER TABLE product_assets
        ADD CONSTRAINT ck_product_images_image_status
        CHECK (image_status IN ('pending','mirroring','mirrored','failed'))
        """
    )

    # Drop new columns.
    op.drop_column("product_assets", "position")
    op.drop_column("product_assets", "archived_by")
    op.drop_column("product_assets", "archived_at")
    op.drop_column("product_assets", "supersedes_id")
    op.drop_column("product_assets", "revision")
    op.drop_column("product_assets", "metadata")
    op.drop_column("product_assets", "variants")
    op.drop_column("product_assets", "caption")
    op.drop_column("product_assets", "locale")
    op.drop_column("product_assets", "bucket")
    op.drop_column("product_assets", "kind")

    # Restore old indexes.
    op.create_index("idx_images_sku_role", "product_assets", ["sku", "role"])
    op.create_index("idx_product_images_hash", "product_assets", ["hash_sha256"])

    # Rename back.
    op.rename_table("product_assets", "product_images")
