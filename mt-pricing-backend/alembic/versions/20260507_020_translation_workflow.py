"""translation_workflow — US-1A-02-05 (Sprint 3).

Cambios:

- Añade columnas a ``product_translations``:
    * ``staleness_reason``  TEXT NULL — etiqueta opcional cuando la traducción
      cae en estado ``stale`` (ej. ``master_en_changed``).
    * ``rejection_reason``  TEXT NULL — motivo cuando un aprobador rechaza
      una traducción ``pending_review``.

- Extiende el CHECK constraint ``ck_translations_status`` para soportar los
  nuevos estados ``pending_review`` + ``stale`` (los enums ``draft|pending|approved``
  preexistentes se mantienen para compatibilidad con datos S1/S2).

- Añade trigger PL/pgSQL ``mark_translations_stale_on_master_edit``:
  AFTER UPDATE OF ``name_en``, ``description_en`` ON ``products`` — marca
  todas las traducciones no-EN del producto cuyo ``status='approved'`` como
  ``status='stale'`` con ``staleness_reason='master_en_changed'``.

NOTA — gestión de slot 020:
- Esta migración está reservada al agente del workflow de traducciones.
- ``down_revision`` apunta a ``20260507_019`` (chain ininterrumpida acordada
  por los agentes A/B/C/D del Sprint 3).
- NO se aplica con ``alembic upgrade head`` automáticamente — staging la
  consume cuando todas las migraciones 017/018/019 están en main.

Revision ID: 20260507_020
Revises: 20260507_019
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_020"
down_revision: str | None = "20260507_019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Lista canónica de estados soportados S3.
_VALID_STATUSES: tuple[str, ...] = (
    "pending",  # legacy S1/S2 — equivalente operacional a draft
    "draft",
    "pending_review",
    "approved",
    "stale",
)


def upgrade() -> None:
    # ----- Columnas nuevas (idempotente — usamos IF NOT EXISTS) -----
    op.execute(
        "ALTER TABLE product_translations "
        "ADD COLUMN IF NOT EXISTS staleness_reason TEXT NULL"
    )
    op.execute(
        "ALTER TABLE product_translations "
        "ADD COLUMN IF NOT EXISTS rejection_reason TEXT NULL"
    )

    # ----- Reemplaza CHECK constraint del estado -----
    # Drop si existe (creado en 20260506_001) y recrea con la nueva lista.
    op.execute(
        "ALTER TABLE product_translations "
        "DROP CONSTRAINT IF EXISTS ck_translations_status"
    )
    statuses_csv = ",".join(f"'{s}'" for s in _VALID_STATUSES)
    op.execute(
        "ALTER TABLE product_translations "
        f"ADD CONSTRAINT ck_translations_status CHECK (status IN ({statuses_csv}))"
    )

    # ----- Índice por (lang, status) para queries de cobertura -----
    # (idx_translations_status ya existe — lo dejamos)

    # ----- Trigger function -----
    op.execute(
        """
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
        $fn$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_translations_stale_on_master_edit "
        "ON products"
    )
    op.execute(
        """
        CREATE TRIGGER trg_translations_stale_on_master_edit
        AFTER UPDATE OF name_en, description_en ON products
        FOR EACH ROW
        EXECUTE FUNCTION mark_translations_stale_on_master_edit();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_translations_stale_on_master_edit "
        "ON products"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS mark_translations_stale_on_master_edit()"
    )
    op.execute(
        "ALTER TABLE product_translations "
        "DROP CONSTRAINT IF EXISTS ck_translations_status"
    )
    op.execute(
        "ALTER TABLE product_translations "
        "ADD CONSTRAINT ck_translations_status "
        "CHECK (status IN ('pending','draft','approved'))"
    )
    op.execute(
        "ALTER TABLE product_translations DROP COLUMN IF EXISTS rejection_reason"
    )
    op.execute(
        "ALTER TABLE product_translations DROP COLUMN IF EXISTS staleness_reason"
    )
