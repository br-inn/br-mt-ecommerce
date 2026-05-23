"""taxonomy_profiles table with seed from taxonomy_rules.py

Revision ID: 20260517_137
Revises: 20260602_136
Create Date: 2026-05-17
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260517_137"
down_revision = "20260602_136"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Weight profiles (mirrors hardcoded taxonomy_rules.py)
# ---------------------------------------------------------------------------
_VALVE_W = {
    "material": 0.17,
    "pn": 0.11,
    "dn": 0.17,
    "product_type": 0.11,
    "thread_standard": 0.14,
    "ways": 0.05,
    "norma": 0.04,
    "brand_tier": 0.07,
    "delivery": 0.06,
    "data_completeness": 0.08,
}
_STRAINER_W = {
    "material": 0.18,
    "pn": 0.11,
    "dn": 0.18,
    "product_type": 0.14,
    "thread_standard": 0.14,
    "ways": 0.00,
    "norma": 0.05,
    "brand_tier": 0.07,
    "delivery": 0.05,
    "data_completeness": 0.08,
}
_GAUGE_W = {
    "material": 0.18,
    "pn": 0.19,
    "dn": 0.09,
    "product_type": 0.18,
    "thread_standard": 0.09,
    "ways": 0.00,
    "norma": 0.05,
    "brand_tier": 0.07,
    "delivery": 0.07,
    "data_completeness": 0.08,
}
_DEFAULT_W = {
    "material": 0.18,
    "pn": 0.14,
    "dn": 0.00,
    "product_type": 0.00,
    "thread_standard": 0.14,
    "ways": 0.00,
    "norma": 0.14,
    "brand_tier": 0.18,
    "delivery": 0.14,
    "data_completeness": 0.08,
}

# ---------------------------------------------------------------------------
# Hard blocker profiles
# ---------------------------------------------------------------------------
_FULL_VALVE_B = [
    "dn_mismatch",
    "material_mismatch",
    "mini_mismatch",
    "pn_below_sku_requirement",
    "pn_too_far_above",
    "product_type_mismatch",
    "ways_mismatch",
]
_BASE_VALVE_B = [
    "dn_mismatch",
    "material_mismatch",
    "pn_below_sku_requirement",
    "pn_too_far_above",
    "product_type_mismatch",
    "ways_mismatch",
]
_GAUGE_B = [
    "product_type_mismatch",
    "pn_below_sku_requirement",
    "pn_too_far_above",
]
_DEFAULT_B = [
    "pn_below_sku_requirement",
    "thread_mismatch",
    "material_mismatch",
]

# ---------------------------------------------------------------------------
# Seed rows: (family, weights, hard_blockers, description)
# ---------------------------------------------------------------------------
SEED = [
    ("ball_valve", _VALVE_W, _FULL_VALVE_B, "Válvulas de bola"),
    ("valves_ball", _VALVE_W, _FULL_VALVE_B, "Válvulas de bola (alias)"),
    ("HIDROSANITARIO", _VALVE_W, _FULL_VALVE_B, "Hidrosanitario"),
    ("gate_valve", _VALVE_W, _BASE_VALVE_B, "Válvulas de compuerta"),
    ("globe_valve", _VALVE_W, _BASE_VALVE_B, "Válvulas de globo"),
    ("check_valve", _VALVE_W, _BASE_VALVE_B, "Válvulas de retención"),
    ("butterfly_valve", _VALVE_W, _BASE_VALVE_B, "Válvulas de mariposa"),
    ("strainer", _STRAINER_W, _BASE_VALVE_B, "Filtros strainer"),
    ("FILTROS", _STRAINER_W, _BASE_VALVE_B, "Filtros"),
    ("pressure_gauge", _GAUGE_W, _GAUGE_B, "Manómetros"),
    ("MANOMETROS", _GAUGE_W, _GAUGE_B, "Manómetros (alias)"),
    ("_default", _DEFAULT_W, _DEFAULT_B, "Perfil por defecto"),
]


def upgrade() -> None:
    op.create_table(
        "taxonomy_profiles",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("weights", JSONB(), nullable=False),
        sa.Column(
            "hard_blockers",
            ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
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
        sa.UniqueConstraint("family", name="uq_taxonomy_profiles_family"),
        sa.CheckConstraint("family != ''", name="ck_taxonomy_profiles_family_nonempty"),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "taxonomy_profiles",
            sa.column("id", sa.UUID()),
            sa.column("family", sa.Text()),
            sa.column("weights", JSONB()),
            sa.column("hard_blockers", ARRAY(sa.Text())),
            sa.column("description", sa.Text()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "family": f,
                "weights": w,
                "hard_blockers": b,
                "description": d,
                "created_at": now,
                "updated_at": now,
            }
            for f, w, b, d in SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("taxonomy_profiles")
