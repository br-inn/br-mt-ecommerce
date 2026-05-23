"""taxonomy_registry — Registry polimórfico (E1-hardened, aditivo).

Modernización de taxonomías: del modelo fijo `divisions/series/tiers/materials`
hacia un registry data-driven que permite agregar nuevas dimensiones (mercados,
certificaciones, aplicaciones, etc.) **sin código nuevo** — solo INSERT.

Esta migración es **aditiva**: las tablas `divisions`, `series`, `series_tiers`,
`materials` se mantienen intactas. La sincronización legacy → registry se hará
en migración posterior (ver `_bmad-output/brainstorming/brainstorming-session-2026-05-10-1430.md`).

Tablas creadas:
- ``taxonomy_types`` — registry maestro de tipos de taxonomía
- ``taxonomy_nodes`` — nodos polimórficos (terms) de cualquier tipo
- ``taxonomy_node_parents`` — multi-inheritance (M:N)
- ``taxonomy_node_descendants`` — closure table mantenida por triggers
- ``taxonomy_aliases`` — slug evolution (rename sin romper contratos)
- ``product_taxonomy_links`` — M:N products ↔ nodes con `role`
- ``family_schemas`` — JSON Schema por familia almacenado como dato

Hooks evolutivos (no usar hoy, listos para Fase 2/3):
- `role` en `product_taxonomy_links` → futuro grafo (E2 con Neo4j read-replica).
- `external_mappings` en `taxonomy_types` → marketplaces (Schema.org/Google).
- `superseded_by` → renaming/fusión sin pérdida histórica.

Pre-load: 4 taxonomy_types `is_system=true` (division/series/tier/material)
con slugs canónicos. NO migra data de las tablas legacy — esa migración va en
un PR separado por capas (con vistas SQL emuladoras).

Revision ID: 20260511_049
Revises: 20260509_048
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260511_049"
down_revision: str | None = "20260509_048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Constants — valores permitidos para enums CHECK
# ---------------------------------------------------------------------------
VALUE_KINDS = (
    "enum_closed",  # set fijo de nodos curado por admin (e.g. division)
    "enum_open",  # set abierto de nodos extensible (e.g. material)
    "numeric_with_unit",  # valor numérico + unidad (e.g. pressure_rating)
    "freetext",  # texto libre (e.g. notas)
    "reference_to_other_type",  # FK lógica a otro taxonomy_type
)

LINK_ROLES = (
    "belongs_to",  # producto pertenece al nodo (clasificación)
    "compatible_with",  # producto es compatible con (relación de grafo futuro)
    "replaces",  # producto reemplaza al referido (sucesor)
    "recommends",  # producto recomienda al referido (cross-sell)
)

# Slug pattern: lowercase, comienza con letra, permite a-z 0-9 _
SLUG_REGEX = r"^[a-z][a-z0-9_]*$"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. taxonomy_types — Registry maestro
    # ------------------------------------------------------------------
    op.create_table(
        "taxonomy_types",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                "true = type núcleo (division, series, tier, material). "
                "Edición restringida; renaming sólo vía taxonomy_aliases."
            ),
        ),
        sa.Column(
            "label_i18n",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="i18n labels: {es: ..., en: ..., ar: ...}",
        ),
        sa.Column(
            "is_hierarchical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "depth_max",
            sa.SmallInteger(),
            nullable=True,
            comment="NULL = ilimitado; valida en INSERT/UPDATE de nodes",
        ),
        sa.Column(
            "value_kind",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'enum_open'"),
        ),
        sa.Column(
            "filterable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "ui_layout",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="UI hints: {icon, custom_component, groups, position}",
        ),
        sa.Column(
            "governance_policy",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="{approval_required, allowed_creator_roles, max_nodes}",
        ),
        sa.Column(
            "required_for_products",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "external_mappings",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="{schema_org, google_taxonomy, amazon_aces}",
        ),
        sa.Column(
            "schema_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
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
        sa.UniqueConstraint("slug", name="uq_taxonomy_types_slug"),
        sa.CheckConstraint(
            f"slug ~ '{SLUG_REGEX}'",
            name="ck_taxonomy_types_slug_format",
        ),
        sa.CheckConstraint(
            "value_kind IN (" + ", ".join(f"'{v}'" for v in VALUE_KINDS) + ")",
            name="ck_taxonomy_types_value_kind",
        ),
        sa.CheckConstraint(
            "depth_max IS NULL OR depth_max > 0",
            name="ck_taxonomy_types_depth_max_positive",
        ),
    )
    op.create_index("idx_taxonomy_types_active", "taxonomy_types", ["active"])
    op.create_index(
        "idx_taxonomy_types_filterable",
        "taxonomy_types",
        ["filterable"],
        postgresql_where=sa.text("filterable = true AND active = true"),
    )

    # ------------------------------------------------------------------
    # 2. taxonomy_nodes — Nodos polimórficos
    # ------------------------------------------------------------------
    op.create_table(
        "taxonomy_nodes",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "type_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="RESTRICT"),
            nullable=True,
            comment=(
                "Primary parent (legacy single-parent tree). "
                "Multi-inheritance vive en taxonomy_node_parents."
            ),
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column(
            "labels",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="i18n labels: {es: ..., en: ..., ar: ...}",
        ),
        sa.Column(
            "attributes",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Validado contra family_schemas si aplicable",
        ),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="NULL = vigente; set para deprecar sin eliminar",
        ),
        sa.Column(
            "superseded_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"),
            nullable=True,
            comment="Nodo sucesor tras rename/fusión",
        ),
        sa.Column(
            "node_acl",
            JSONB(),
            nullable=True,
            comment=(
                "ACL granular opcional override del type. {visible_to_roles, editable_by_roles}"
            ),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
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
        sa.UniqueConstraint("type_id", "slug", name="uq_taxonomy_nodes_type_slug"),
        sa.CheckConstraint(
            f"slug ~ '{SLUG_REGEX}'",
            name="ck_taxonomy_nodes_slug_format",
        ),
        sa.CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id",
            name="ck_taxonomy_nodes_no_self_supersede",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_taxonomy_nodes_valid_range",
        ),
    )
    op.create_index("idx_taxonomy_nodes_type", "taxonomy_nodes", ["type_id"])
    op.create_index(
        "idx_taxonomy_nodes_parent",
        "taxonomy_nodes",
        ["parent_id"],
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )
    op.create_index(
        "idx_taxonomy_nodes_active",
        "taxonomy_nodes",
        ["type_id", "active"],
        postgresql_where=sa.text("active = true"),
    )
    op.create_index(
        "idx_taxonomy_nodes_labels_gin",
        "taxonomy_nodes",
        ["labels"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_taxonomy_nodes_attributes_gin",
        "taxonomy_nodes",
        ["attributes"],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # 3. taxonomy_node_parents — Multi-inheritance M:N
    # ------------------------------------------------------------------
    op.create_table(
        "taxonomy_node_parents",
        sa.Column(
            "node_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "parent_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "weight",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "node_id <> parent_id",
            name="ck_taxonomy_node_parents_no_self_loop",
        ),
    )
    op.create_index(
        "idx_taxonomy_node_parents_parent",
        "taxonomy_node_parents",
        ["parent_id"],
    )
    # Solo un primary parent por nodo (partial unique index)
    op.create_index(
        "uq_taxonomy_node_parents_primary",
        "taxonomy_node_parents",
        ["node_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    # ------------------------------------------------------------------
    # 4. taxonomy_node_descendants — Closure table
    # ------------------------------------------------------------------
    op.create_table(
        "taxonomy_node_descendants",
        sa.Column(
            "ancestor_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "descendant_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "depth",
            sa.SmallInteger(),
            nullable=False,
            comment="0 = self; 1 = direct child; N = N-step descendant",
        ),
        sa.CheckConstraint("depth >= 0", name="ck_taxonomy_descendants_depth"),
    )
    op.create_index(
        "idx_taxonomy_descendants_descendant",
        "taxonomy_node_descendants",
        ["descendant_id"],
    )
    op.create_index(
        "idx_taxonomy_descendants_depth",
        "taxonomy_node_descendants",
        ["ancestor_id", "depth"],
    )

    # ------------------------------------------------------------------
    # 5. taxonomy_aliases — Slug evolution
    # ------------------------------------------------------------------
    op.create_table(
        "taxonomy_aliases",
        sa.Column("alias_slug", sa.Text(), nullable=False),
        sa.Column(
            "type_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "canonical_node_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="NULL = alias permanente (e.g. rename); set para alias temporal",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("type_id", "alias_slug", name="pk_taxonomy_aliases"),
        sa.CheckConstraint(
            f"alias_slug ~ '{SLUG_REGEX}'",
            name="ck_taxonomy_aliases_slug_format",
        ),
    )
    op.create_index(
        "idx_taxonomy_aliases_canonical",
        "taxonomy_aliases",
        ["canonical_node_id"],
    )

    # ------------------------------------------------------------------
    # 6. product_taxonomy_links — M:N products ↔ taxonomy_nodes con role
    # ------------------------------------------------------------------
    op.create_table(
        "product_taxonomy_links",
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "node_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("taxonomy_nodes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "role",
            sa.Text(),
            primary_key=True,
            server_default=sa.text("'belongs_to'"),
        ),
        sa.Column(
            "weight",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in LINK_ROLES) + ")",
            name="ck_product_taxonomy_links_role",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_product_taxonomy_links_valid_range",
        ),
    )
    op.create_index(
        "idx_product_taxonomy_links_node",
        "product_taxonomy_links",
        ["node_id"],
    )
    op.create_index(
        "idx_product_taxonomy_links_role",
        "product_taxonomy_links",
        ["role"],
    )
    op.create_index(
        "idx_product_taxonomy_links_current",
        "product_taxonomy_links",
        ["product_sku", "node_id"],
        postgresql_where=sa.text("valid_until IS NULL"),
    )

    # ------------------------------------------------------------------
    # 7. family_schemas — JSON Schema por familia como dato
    # ------------------------------------------------------------------
    op.create_table(
        "family_schemas",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "family_slug",
            sa.Text(),
            nullable=False,
            comment=(
                "Slug de familia (corresponde a families.code o registry futuro). "
                "Sin FK por ahora — evolutivo."
            ),
        ),
        sa.Column(
            "schema_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "json_schema",
            JSONB(),
            nullable=False,
            comment="JSON Schema Draft 2020-12; validado client + server",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "superseded_by",
            PgUUID(as_uuid=True),
            sa.ForeignKey("family_schemas.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.UniqueConstraint(
            "family_slug",
            "schema_version",
            name="uq_family_schemas_slug_version",
        ),
        sa.CheckConstraint(
            f"family_slug ~ '{SLUG_REGEX}'",
            name="ck_family_schemas_slug_format",
        ),
        sa.CheckConstraint(
            "schema_version >= 1",
            name="ck_family_schemas_version_positive",
        ),
    )
    op.create_index(
        "idx_family_schemas_active",
        "family_schemas",
        ["family_slug"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_family_schemas_json_gin",
        "family_schemas",
        ["json_schema"],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # 8. Closure table triggers — mantenimiento automático
    # ------------------------------------------------------------------
    op.execute(
        """
        -- Función helper: recomputa closure para un nodo y sus descendientes.
        -- Idempotente: borra entries previas para el nodo y reinserta.
        CREATE OR REPLACE FUNCTION taxonomy_recompute_closure(target_node UUID)
        RETURNS VOID AS $$
        BEGIN
            -- Borrar entries donde target_node sea descendant
            DELETE FROM taxonomy_node_descendants
            WHERE descendant_id = target_node;

            -- Self-row (depth 0)
            INSERT INTO taxonomy_node_descendants (ancestor_id, descendant_id, depth)
            VALUES (target_node, target_node, 0);

            -- Inferir ancestros transitivos vía taxonomy_node_parents
            -- (cubre tanto parent_id tree-style como multi-inheritance)
            WITH RECURSIVE ancestors AS (
                SELECT parent_id AS ancestor_id, 1 AS depth
                FROM taxonomy_node_parents
                WHERE node_id = target_node
                UNION
                SELECT
                    tnp.parent_id,
                    a.depth + 1
                FROM ancestors a
                JOIN taxonomy_node_parents tnp ON tnp.node_id = a.ancestor_id
                WHERE a.depth < 32  -- safety cap contra ciclos
            )
            INSERT INTO taxonomy_node_descendants (ancestor_id, descendant_id, depth)
            SELECT ancestor_id, target_node, depth
            FROM ancestors
            ON CONFLICT (ancestor_id, descendant_id) DO NOTHING;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        -- Trigger: al insertar/borrar en taxonomy_node_parents, recomputa closure
        -- del nodo afectado y de TODOS sus descendientes (porque al cambiar la
        -- ancestría del nodo, los descendientes heredan nuevos ancestros).
        CREATE OR REPLACE FUNCTION taxonomy_node_parents_closure_trigger()
        RETURNS TRIGGER AS $$
        DECLARE
            affected_node UUID;
            desc_id UUID;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                affected_node := OLD.node_id;
            ELSE
                affected_node := NEW.node_id;
            END IF;

            -- Recompute para el nodo y descendientes existentes
            PERFORM taxonomy_recompute_closure(affected_node);
            FOR desc_id IN
                SELECT descendant_id FROM taxonomy_node_descendants
                WHERE ancestor_id = affected_node AND depth > 0
            LOOP
                PERFORM taxonomy_recompute_closure(desc_id);
            END LOOP;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_taxonomy_node_parents_closure
        AFTER INSERT OR UPDATE OR DELETE ON taxonomy_node_parents
        FOR EACH ROW
        EXECUTE FUNCTION taxonomy_node_parents_closure_trigger();
        """
    )

    op.execute(
        """
        -- Trigger: al insertar un nodo, agregar self-row a closure (depth 0).
        -- Si tiene parent_id directo, también lo registramos como ancestor depth 1.
        CREATE OR REPLACE FUNCTION taxonomy_nodes_closure_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                INSERT INTO taxonomy_node_descendants (ancestor_id, descendant_id, depth)
                VALUES (NEW.id, NEW.id, 0)
                ON CONFLICT DO NOTHING;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_taxonomy_nodes_closure_insert
        AFTER INSERT ON taxonomy_nodes
        FOR EACH ROW
        EXECUTE FUNCTION taxonomy_nodes_closure_trigger();
        """
    )

    # ------------------------------------------------------------------
    # 9. Seed inicial — 4 taxonomy_types is_system=true
    # ------------------------------------------------------------------
    # Estos son los slugs CANÓNICOS del registry. Las tablas legacy
    # (divisions, series, series_tiers, materials) siguen siendo source of
    # truth de DATOS hasta una migración posterior que mueva nodos al registry.
    op.execute(
        """
        INSERT INTO taxonomy_types (
            slug, is_system, label_i18n, is_hierarchical, value_kind,
            filterable, display_order, ui_layout, governance_policy,
            required_for_products, external_mappings, active
        ) VALUES
        (
            'division', true,
            '{"es": "Divisiones", "en": "Divisions", "ar": "الأقسام"}'::jsonb,
            false, 'enum_closed',
            true, 10,
            '{"icon": "layers", "position": 1}'::jsonb,
            '{"approval_required": true, "allowed_creator_roles": ["admin"]}'::jsonb,
            true,
            '{"schema_org": "category"}'::jsonb,
            true
        ),
        (
            'series', true,
            '{"es": "Series", "en": "Series", "ar": "السلسلة"}'::jsonb,
            false, 'enum_open',
            true, 20,
            '{"icon": "sprout", "position": 2}'::jsonb,
            '{"approval_required": true, "allowed_creator_roles": ["admin", "product_manager"]}'::jsonb,
            false,
            '{"schema_org": "category"}'::jsonb,
            true
        ),
        (
            'tier', true,
            '{"es": "Tiers", "en": "Tiers", "ar": "المستويات"}'::jsonb,
            false, 'enum_closed',
            true, 30,
            '{"icon": "award", "position": 3}'::jsonb,
            '{"approval_required": true, "allowed_creator_roles": ["admin"]}'::jsonb,
            false,
            '{}'::jsonb,
            true
        ),
        (
            'material', true,
            '{"es": "Materiales", "en": "Materials", "ar": "المواد"}'::jsonb,
            false, 'enum_open',
            true, 40,
            '{"icon": "atom", "position": 4}'::jsonb,
            '{"approval_required": false, "allowed_creator_roles": ["admin", "product_manager"]}'::jsonb,
            false,
            '{"schema_org": "material"}'::jsonb,
            true
        )
        ON CONFLICT (slug) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Triggers + funciones
    op.execute("DROP TRIGGER IF EXISTS trg_taxonomy_nodes_closure_insert ON taxonomy_nodes;")
    op.execute("DROP FUNCTION IF EXISTS taxonomy_nodes_closure_trigger();")
    op.execute("DROP TRIGGER IF EXISTS trg_taxonomy_node_parents_closure ON taxonomy_node_parents;")
    op.execute("DROP FUNCTION IF EXISTS taxonomy_node_parents_closure_trigger();")
    op.execute("DROP FUNCTION IF EXISTS taxonomy_recompute_closure(UUID);")

    # Tablas en orden reverso de FKs
    op.drop_index("idx_family_schemas_json_gin", table_name="family_schemas")
    op.drop_index("idx_family_schemas_active", table_name="family_schemas")
    op.drop_table("family_schemas")

    op.drop_index(
        "idx_product_taxonomy_links_current",
        table_name="product_taxonomy_links",
    )
    op.drop_index(
        "idx_product_taxonomy_links_role",
        table_name="product_taxonomy_links",
    )
    op.drop_index(
        "idx_product_taxonomy_links_node",
        table_name="product_taxonomy_links",
    )
    op.drop_table("product_taxonomy_links")

    op.drop_index("idx_taxonomy_aliases_canonical", table_name="taxonomy_aliases")
    op.drop_table("taxonomy_aliases")

    op.drop_index(
        "idx_taxonomy_descendants_depth",
        table_name="taxonomy_node_descendants",
    )
    op.drop_index(
        "idx_taxonomy_descendants_descendant",
        table_name="taxonomy_node_descendants",
    )
    op.drop_table("taxonomy_node_descendants")

    op.drop_index(
        "uq_taxonomy_node_parents_primary",
        table_name="taxonomy_node_parents",
    )
    op.drop_index(
        "idx_taxonomy_node_parents_parent",
        table_name="taxonomy_node_parents",
    )
    op.drop_table("taxonomy_node_parents")

    op.drop_index("idx_taxonomy_nodes_attributes_gin", table_name="taxonomy_nodes")
    op.drop_index("idx_taxonomy_nodes_labels_gin", table_name="taxonomy_nodes")
    op.drop_index("idx_taxonomy_nodes_active", table_name="taxonomy_nodes")
    op.drop_index("idx_taxonomy_nodes_parent", table_name="taxonomy_nodes")
    op.drop_index("idx_taxonomy_nodes_type", table_name="taxonomy_nodes")
    op.drop_table("taxonomy_nodes")

    op.drop_index("idx_taxonomy_types_filterable", table_name="taxonomy_types")
    op.drop_index("idx_taxonomy_types_active", table_name="taxonomy_types")
    op.drop_table("taxonomy_types")
