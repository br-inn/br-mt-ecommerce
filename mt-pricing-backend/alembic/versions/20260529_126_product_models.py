"""product_models + model_dimension_rows + model_flow_data + model_tech_tables"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260529_126"
down_revision = "20260528_125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_models",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("series_id", sa.UUID(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("color_label", sa.String(32), nullable=True),
        sa.Column("connection_type", sa.String(32), nullable=True),
        sa.Column("thread_standard", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("variant_of_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_of_id"], ["product_models.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("idx_product_models_series", "product_models", ["series_id"])
    op.create_index("idx_product_models_variant_of", "product_models", ["variant_of_id"])
    op.create_index("idx_product_models_active", "product_models", ["active"])

    op.create_table(
        "model_dimension_rows",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("dn_mm", sa.Integer(), nullable=False),
        sa.Column("dn_secondary_mm", sa.Integer(), nullable=True),
        sa.Column(
            "dimensions", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("source", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "dn_mm", "dn_secondary_mm", name="uq_model_dim_rows"),
    )
    op.create_index("idx_model_dim_rows_model", "model_dimension_rows", ["model_id"])
    op.create_index("idx_model_dim_rows_dn", "model_dimension_rows", ["dn_mm"])

    op.create_table(
        "model_flow_data",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("dn_mm", sa.Integer(), nullable=False),
        sa.Column("kv", sa.Numeric(10, 3), nullable=True),
        sa.Column("cv", sa.Numeric(10, 3), nullable=True),
        sa.Column("mesh_mm", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "dn_mm", "mesh_mm", name="uq_model_flow"),
    )
    op.create_index("idx_model_flow_model", "model_flow_data", ["model_id"])

    op.create_table(
        "model_tech_tables",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("gasket_material", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Text(), server_default=sa.text("'v1'"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'manual'"), nullable=False),
        sa.Column(
            "data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "kind", "gasket_material", name="uq_model_tech_table"),
    )
    op.create_index("idx_model_tech_tables_model", "model_tech_tables", ["model_id"])
    op.create_index("idx_model_tech_tables_kind", "model_tech_tables", ["kind"])


def downgrade() -> None:
    op.drop_table("model_tech_tables")
    op.drop_table("model_flow_data")
    op.drop_table("model_dimension_rows")
    op.drop_table("product_models")
