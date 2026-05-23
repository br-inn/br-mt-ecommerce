"""comparator_config — scalar config table with seed

Revision ID: 20260517_138
Revises: 20260517_137
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from datetime import datetime, timezone

revision = "20260517_138"
down_revision = "20260517_137"
branch_labels = None
depends_on = None

SEED = [
    ("peer_threshold", 70, "Score mínimo para clasificar candidato como peer"),
    ("drop_threshold", 40, "Score mínimo para clasificar candidato como drop"),
    ("g1_median_multiplier", 1.10, "Multiplicador sobre mediana peer-group para precio G1"),
    (
        "g2_multipliers",
        {"default": 2.5, "stainless": 3.0, "cast_iron": 2.0},
        "Multiplicadores G2 por subtipo material",
    ),
    ("hitl_value_threshold_aed", 1000, "Valor mínimo AED para encolar en HITL"),
]


def upgrade() -> None:
    op.create_table(
        "comparator_config",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_comparator_config_key"),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "comparator_config",
            sa.column("id", sa.UUID()),
            sa.column("key", sa.Text()),
            sa.column("value", JSONB()),
            sa.column("description", sa.Text()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "key": k,
                "value": v,
                "description": d,
                "created_at": now,
                "updated_at": now,
            }
            for k, v, d in SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("comparator_config")
