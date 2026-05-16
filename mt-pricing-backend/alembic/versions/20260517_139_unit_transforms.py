"""unit_transforms — conversion table with seed

Revision ID: 20260517_139
Revises: 20260517_138
Create Date: 2026-05-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import uuid
from datetime import datetime, timezone

revision = "20260517_139"
down_revision = "20260517_138"
branch_labels = None
depends_on = None

DN_TO_NPS = {
    "6": '1/8"', "8": '1/4"', "10": '3/8"', "15": '1/2"', "20": '3/4"',
    "25": '1"', "32": '1¼"', "40": '1½"', "50": '2"', "65": '2½"',
    "80": '3"', "100": '4"', "125": '5"', "150": '6"', "200": '8"',
    "250": '10"', "300": '12"',
}

SEED = [
    ("numeric", "PSI", "PN", "floor({value} / 14.5038)", None, "PSI/WOG a PN (presión nominal bar)"),
    ("numeric", "WOG", "PN", "floor({value} / 14.5038)", None, "WOG a PN — misma escala que PSI"),
    ("lookup", "DN_metric", "NPS_inches", None, DN_TO_NPS, "Diámetro nominal métrico a NPS pulgadas"),
    ("nominal", "DN50", "NPS_2in", None, {"DN50": '2"', "DN65": '2.5"', "DN80": '3"'}, "Equivalencias nominales DN frecuentes"),
]


def upgrade() -> None:
    op.create_table(
        "unit_transforms",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("transform_type", sa.Text(), nullable=False),
        sa.Column("from_unit", sa.Text(), nullable=False),
        sa.Column("to_unit", sa.Text(), nullable=False),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("lookup_table", JSONB(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("transform_type IN ('numeric','lookup','nominal')", name="ck_unit_transforms_type"),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "unit_transforms",
            sa.column("id", sa.UUID()),
            sa.column("transform_type", sa.Text()),
            sa.column("from_unit", sa.Text()),
            sa.column("to_unit", sa.Text()),
            sa.column("formula", sa.Text()),
            sa.column("lookup_table", JSONB()),
            sa.column("description", sa.Text()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "transform_type": tt,
                "from_unit": fu,
                "to_unit": tu,
                "formula": fo,
                "lookup_table": lt,
                "description": d,
                "created_at": now,
                "updated_at": now,
            }
            for tt, fu, tu, fo, lt, d in SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("unit_transforms")
