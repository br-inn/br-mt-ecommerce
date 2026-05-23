"""Fase 2 — EAV typed attribute system (PDF §8 alignment).

Crea el modelo Entity-Attribute-Value tipado para atributos dinámicos por
familia, alineado con la propuesta del PDF v1.0 §8 (Modelo de atributos
dinámicos por familia).

Tablas creadas:

1. ``attribute_definitions`` — catálogo central de atributos disponibles.
   Cada atributo tiene un ``data_type`` que determina qué columna de
   ``attribute_values`` debe poblarse (number/integer/text/bool/enum/
   range/dimension).

2. ``attribute_options`` — opciones discretas para atributos tipo enum
   (e.g. material_body → ss316, ss304, brass…).

3. ``family_attributes`` — plantilla por familia: qué atributos aplican a
   qué familia, en qué grupo visual y orden, si son requeridos, default
   value y reglas de validación opcionales en JSONB.

4. ``attribute_values`` — valores reales asignados a productos o
   variantes (owner_type/owner_id polimórfico). Una sola fila por
   (owner, attribute, language) con el campo tipado correspondiente
   poblado; CHECK constraint garantiza que al menos una columna de valor
   está rellena.

Notas:
- ``owner_id`` es TEXT porque ``products.sku`` es TEXT PK. Para variantes
  el sku también es TEXT.
- ``language`` CHAR(2) para soportar i18n via filas separadas (decisión
  "todo en inglés" — identifiers en inglés, content traducible).
- ``specs`` JSONB en ``products`` NO se elimina — se mantiene como
  escape hatch para metadatos opacos (decisión §5.7 comparativa).

Revision ID: 20260514_054
Revises: 20260513_053
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260514_054"
down_revision: str | None = "20260513_053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. attribute_definitions — catálogo central
    # ------------------------------------------------------------------
    op.create_table(
        "attribute_definitions",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column(
            "is_filterable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_seo_relevant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "scope",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'product'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_attribute_definitions_code"),
        sa.CheckConstraint(
            "data_type IN ('number','integer','text','bool','enum','range','dimension')",
            name="ck_attribute_definitions_data_type",
        ),
        sa.CheckConstraint(
            "scope IN ('product','variant','both')",
            name="ck_attribute_definitions_scope",
        ),
    )

    # ------------------------------------------------------------------
    # 2. attribute_options — opciones para enums
    # ------------------------------------------------------------------
    op.create_table(
        "attribute_options",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "attribute_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint("attribute_id", "code", name="uq_attribute_options_attr_code"),
    )
    op.create_index(
        "ix_attribute_options_attribute",
        "attribute_options",
        ["attribute_id"],
    )

    # ------------------------------------------------------------------
    # 3. family_attributes — plantilla por familia
    # ------------------------------------------------------------------
    op.create_table(
        "family_attributes",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "family_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attribute_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("group_code", sa.Text(), nullable=False),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("validation_rule", JSONB(), nullable=True),
        sa.UniqueConstraint("family_id", "attribute_id", name="uq_family_attributes_family_attr"),
    )
    op.create_index("ix_fa_family", "family_attributes", ["family_id"])
    op.create_index("ix_fa_attribute", "family_attributes", ["attribute_id"])

    # ------------------------------------------------------------------
    # 4. attribute_values — valores reales
    # ------------------------------------------------------------------
    op.create_table(
        "attribute_values",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("owner_type", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column(
            "attribute_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("value_number", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column(
            "value_enum_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("attribute_options.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("value_min", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_max", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("language", sa.CHAR(2), nullable=True),
        sa.UniqueConstraint(
            "owner_type",
            "owner_id",
            "attribute_id",
            "language",
            name="uq_attribute_values_owner_attr_lang",
        ),
        sa.CheckConstraint(
            "owner_type IN ('product','variant')",
            name="ck_attribute_values_owner_type",
        ),
        sa.CheckConstraint(
            "("
            "(value_number IS NOT NULL)::int + "
            "(value_text IS NOT NULL)::int + "
            "(value_bool IS NOT NULL)::int + "
            "(value_enum_id IS NOT NULL)::int + "
            "((value_min IS NOT NULL) OR (value_max IS NOT NULL))::int"
            ") >= 1",
            name="ck_attribute_values_at_least_one_value",
        ),
    )
    op.create_index("ix_av_owner", "attribute_values", ["owner_type", "owner_id"])
    op.create_index("ix_av_attribute", "attribute_values", ["attribute_id"])
    # Partial index: queries de filtrado numérico por atributo (e.g. dn<=50)
    op.execute(
        "CREATE INDEX ix_av_attr_number "
        "ON attribute_values(attribute_id, value_number) "
        "WHERE value_number IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_av_attr_number")
    op.drop_index("ix_av_attribute", table_name="attribute_values")
    op.drop_index("ix_av_owner", table_name="attribute_values")
    op.drop_table("attribute_values")

    op.drop_index("ix_fa_attribute", table_name="family_attributes")
    op.drop_index("ix_fa_family", table_name="family_attributes")
    op.drop_table("family_attributes")

    op.drop_index("ix_attribute_options_attribute", table_name="attribute_options")
    op.drop_table("attribute_options")

    op.drop_table("attribute_definitions")
