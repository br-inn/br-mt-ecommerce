"""certificates + certificate_scopes"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_127"
down_revision = "20260529_126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", sa.UUID(), nullable=True),
        sa.Column("certification_id", sa.UUID(), nullable=True),
        sa.Column("cert_number", sa.Text(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'valid'"), nullable=False),
        sa.Column("signatory_name", sa.Text(), nullable=True),
        sa.Column("signatory_role", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('valid','expiring_soon','critical','expired','renewing')",
            name="ck_certificate_status",
        ),
        sa.ForeignKeyConstraint(["model_id"], ["product_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["certification_id"], ["certifications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_certificates_model", "certificates", ["model_id"])
    op.create_index("idx_certificates_status", "certificates", ["status"])
    op.create_index("idx_certificates_expires", "certificates", ["expires_at"])
    op.create_index("idx_certificates_certification", "certificates", ["certification_id"])

    op.create_table(
        "certificate_scopes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("certificate_id", sa.UUID(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("dn_min", sa.Integer(), nullable=True),
        sa.Column("dn_max", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "dn_min IS NULL OR dn_max IS NULL OR dn_max >= dn_min",
            name="ck_cert_scope_dn",
        ),
        sa.ForeignKeyConstraint(["certificate_id"], ["certificates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cert_scopes_cert", "certificate_scopes", ["certificate_id"])
    op.create_index("idx_cert_scopes_sku", "certificate_scopes", ["sku"])


def downgrade() -> None:
    op.drop_table("certificate_scopes")
    op.drop_table("certificates")
