"""vocabularios M:N — certifications, applications + junction tables.

Cambios:
- Tabla ``certifications``: catálogo curado de certificaciones de producto.
- Tabla ``applications``: catálogo curado de aplicaciones/usos de producto.
- Tabla ``product_certifications``: M:N junction products ↔ certifications.
- Tabla ``product_applications``: M:N junction products ↔ applications.
- Seed: 12 certifications + 8 applications estándar de la industria.

Wave 4 — vocabularios (rama paralela a Wave 1; merge migration pendiente).

Revision ID: 20260508_033
Revises: 20260507_029
Create Date: 2026-05-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260508_033"
down_revision: str | None = "20260507_029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
CERTIFICATIONS = [
    ("CE", "CE Marking", "European Commission", "European conformity"),
    ("WRAS", "WRAS Approved", "WRAS", "UK drinking water"),
    ("NSF", "NSF/ANSI 61", "NSF International", "Drinking water — health effects"),
    ("KIWA", "KIWA Approval", "KIWA Nederland", "Drinking water — Netherlands"),
    ("ACS", "ACS Sanitaire", "ANSES France", "Drinking water — France"),
    ("ATEX", "ATEX", "EU Directive 2014/34/EU", "Explosive atmospheres"),
    ("FM", "FM Approved", "FM Approvals", "Fire protection"),
    ("UL", "UL Listed", "UL LLC", "North America safety"),
    ("CSA", "CSA Group", "Canadian Standards Association", "Canadian safety"),
    ("ROHS", "RoHS", "EU Directive 2011/65/EU", "Hazardous substances restriction"),
    ("REACH", "REACH", "EU Regulation 1907/2006", "Chemical substances"),
    ("ISO9001", "ISO 9001:2015", "ISO", "Quality management systems"),
]

APPLICATIONS = [
    ("water", "Water", "Drinking water and general water systems"),
    ("gas", "Gas", "Natural gas, LPG, and combustion gas systems"),
    ("oil", "Oil", "Oil-based fluids, fuel oils, lubricants"),
    ("food", "Food & Beverage", "Food-contact applications, beverage processing"),
    ("hvac", "HVAC", "Heating, ventilation, air conditioning"),
    ("fire-fighting", "Fire Fighting", "Sprinkler and fire suppression systems"),
    ("irrigation", "Irrigation", "Agricultural and landscape irrigation"),
    ("industrial", "Industrial", "General industrial process fluids"),
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # certifications
    # ------------------------------------------------------------------
    op.create_table(
        "certifications",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("issued_by", sa.Text, nullable=True),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column(
            "active",
            sa.Boolean,
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
        sa.UniqueConstraint("code", name="uq_certifications_code"),
    )

    # ------------------------------------------------------------------
    # applications
    # ------------------------------------------------------------------
    op.create_table(
        "applications",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "active",
            sa.Boolean,
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
        sa.UniqueConstraint("code", name="uq_applications_code"),
    )

    # ------------------------------------------------------------------
    # product_certifications  (junction)
    # ------------------------------------------------------------------
    op.create_table(
        "product_certifications",
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "certification_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("certifications.id", ondelete="RESTRICT"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "certificate_pdf_asset_id",
            PgUUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("obtained_at", sa.Date, nullable=True),
        sa.Column("expires_at", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_product_certifications_cert",
        "product_certifications",
        ["certification_id"],
    )

    # ------------------------------------------------------------------
    # product_applications  (junction)
    # ------------------------------------------------------------------
    op.create_table(
        "product_applications",
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "application_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="RESTRICT"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "position",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_product_applications_app",
        "product_applications",
        ["application_id"],
    )
    op.execute(
        """
        CREATE INDEX idx_product_applications_primary
            ON product_applications (product_sku)
            WHERE is_primary = true;
        """
    )

    # ------------------------------------------------------------------
    # Seed: certifications
    # ------------------------------------------------------------------
    certifications_table = sa.table(
        "certifications",
        sa.column("code", sa.Text),
        sa.column("name", sa.Text),
        sa.column("issued_by", sa.Text),
        sa.column("scope", sa.Text),
    )
    op.bulk_insert(
        certifications_table,
        [
            {"code": code, "name": name, "issued_by": issued_by, "scope": scope}
            for code, name, issued_by, scope in CERTIFICATIONS
        ],
    )

    # ------------------------------------------------------------------
    # Seed: applications
    # ------------------------------------------------------------------
    applications_table = sa.table(
        "applications",
        sa.column("code", sa.Text),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        applications_table,
        [
            {"code": code, "name": name, "description": description}
            for code, name, description in APPLICATIONS
        ],
    )

    # ------------------------------------------------------------------
    # Permission seed: admin:vocabularies
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('admin:vocabularies', 'Gestionar vocabularios curados (certifications, applications)')
        ON CONFLICT (code) DO NOTHING;
        """
    )
    # Assign to ti_integracion and admin roles
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.code IN ('ti_integracion', 'admin')
          AND p.code = 'admin:vocabularies'
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    # Remove admin:vocabularies permission links + permission
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE code = 'admin:vocabularies'
        );
        DELETE FROM permissions WHERE code = 'admin:vocabularies';
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_product_applications_primary")
    op.drop_index("idx_product_applications_app", table_name="product_applications")
    op.drop_table("product_applications")

    op.drop_index("idx_product_certifications_cert", table_name="product_certifications")
    op.drop_table("product_certifications")

    op.drop_table("applications")
    op.drop_table("certifications")
