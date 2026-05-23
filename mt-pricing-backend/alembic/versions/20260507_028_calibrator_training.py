"""calibrator_training — US-1A-09-07 (Sprint 5).

Crea las tablas ``golden_labels`` (feedback humano) + ``calibrator_versions``
(modelos isotonic versionados, JSON only) y registra el permiso
``calibrator:train``.

Cambios:
- Tabla ``golden_labels``:
    * id UUID PK (gen_random_uuid)
    * sku TEXT NOT NULL FK→products
    * candidate_id UUID NOT NULL FK→match_candidates
    * label INT NOT NULL ∈ {0, 1}
    * score NUMERIC(5,4) NOT NULL ∈ [0,1]
    * judged_by UUID NULL FK→users (SET NULL)
    * judged_at TIMESTAMPTZ DEFAULT now()
    * notes TEXT NULL
    * UNIQUE (sku, candidate_id) — last-write-wins via UPSERT.
- Tabla ``calibrator_versions``:
    * id UUID PK
    * version TEXT NOT NULL UNIQUE
    * model_json JSONB NOT NULL — IsotonicCalibrator.serialize() output
    * trained_on_count INT NOT NULL
    * brier_score NUMERIC(7,6) NULL — métrica al guardar
    * ece NUMERIC(7,6) NULL
    * is_active BOOL DEFAULT false (UNIQUE PARTIAL: solo uno true)
    * trained_by UUID NULL, trained_at TIMESTAMPTZ DEFAULT now()
    * promoted_at TIMESTAMPTZ NULL
- Permiso ``calibrator:train`` (read active + train + promote) asignado
  a roles ``ti_integracion`` y ``admin``.

Slot 028:
- ``down_revision='20260507_027'``.

Revision ID: 20260507_028
Revises: 20260507_027
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "20260507_028"
down_revision: str | None = "20260507_027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- Tabla golden_labels ----------------------------------------------
    op.create_table(
        "golden_labels",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("match_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.Integer, nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "judged_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "judged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.CheckConstraint("label IN (0, 1)", name="ck_golden_labels_label_binary"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_golden_labels_score_range"),
        sa.UniqueConstraint("sku", "candidate_id", name="uq_golden_labels_sku_candidate"),
    )
    op.create_index("idx_golden_labels_sku", "golden_labels", ["sku"])
    op.create_index("idx_golden_labels_judged_at", "golden_labels", ["judged_at"])

    # ----- Tabla calibrator_versions ----------------------------------------
    op.create_table(
        "calibrator_versions",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("version", sa.Text, nullable=False, unique=True),
        sa.Column(
            "model_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "trained_on_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("brier_score", sa.Numeric(7, 6), nullable=True),
        sa.Column("ece", sa.Numeric(7, 6), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "trained_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "trained_on_count >= 0",
            name="ck_calibrator_versions_count_nonneg",
        ),
    )
    # Single active calibrator garantizado via UNIQUE PARTIAL.
    op.execute(
        """
        CREATE UNIQUE INDEX idx_calibrator_versions_active
            ON calibrator_versions ((is_active))
            WHERE is_active = true;
        """
    )

    # ----- Permiso calibrator:train -----------------------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
            ('calibrator:train',
             'Entrenar y promover versiones del IsotonicCalibrator')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE p.code = 'calibrator:train'
          AND r.code IN ('ti_integracion', 'admin')
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
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
        WHERE r.code IN ('ti_integracion', 'admin');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE code = 'calibrator:train'
        );
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'calibrator:train'")
    op.execute(
        """
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
        WHERE r.code IN ('ti_integracion', 'admin');
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_calibrator_versions_active")
    op.drop_table("calibrator_versions")
    op.drop_index("idx_golden_labels_judged_at", table_name="golden_labels")
    op.drop_index("idx_golden_labels_sku", table_name="golden_labels")
    op.drop_table("golden_labels")
