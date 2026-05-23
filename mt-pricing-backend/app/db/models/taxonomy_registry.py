"""ORM models — registry polimórfico de taxonomías (E1-hardened).

Modelo data-driven: agregar nuevas dimensiones (mercados, certificaciones,
aplicaciones, etc.) no requiere nuevas tablas ni código — solo INSERT en
``taxonomy_types`` y ``taxonomy_nodes``.

Coexiste con las tablas legacy (``divisions``, ``series``, ``series_tiers``,
``materials`` en ``vocabularies.py``) durante la transición. La migración
de datos legacy → registry se hará en migración posterior.

Referencia: ``_bmad-output/brainstorming/brainstorming-session-2026-05-10-1430.md``
(Enfoque 1 — Registry Polimórfico Postgres).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


# ---------------------------------------------------------------------------
# Constants — espejo de los CHECK constraints en la migración 049
# ---------------------------------------------------------------------------

VALUE_KINDS: tuple[str, ...] = (
    "enum_closed",
    "enum_open",
    "numeric_with_unit",
    "freetext",
    "reference_to_other_type",
)

LINK_ROLES: tuple[str, ...] = (
    "belongs_to",
    "compatible_with",
    "replaces",
    "recommends",
)

# Slugs canónicos pre-cargados (is_system=true). Importar desde aquí para
# evitar string-literals dispersos en el código que consume el registry.
SYSTEM_TYPE_SLUGS: tuple[str, ...] = (
    "division",
    "series",
    "tier",
    "material",
)


# ---------------------------------------------------------------------------
# TaxonomyType — registry maestro
# ---------------------------------------------------------------------------


class TaxonomyType(UuidPkMixin, Base):
    """Registro de un tipo de taxonomía.

    Agregar un nuevo "Divisiones / Series / Tiers" del sidebar = INSERT aquí.
    Los tipos ``is_system=true`` están protegidos contra rename/delete; usar
    ``TaxonomyAlias`` para evolución de slug.
    """

    __tablename__ = "taxonomy_types"

    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    label_i18n: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_hierarchical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    depth_max: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    value_kind: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'enum_open'")
    )
    filterable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ui_layout: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    governance_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    required_for_products: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    external_mappings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    nodes: Mapped[list["TaxonomyNode"]] = relationship(
        back_populates="type",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    aliases: Mapped[list["TaxonomyAlias"]] = relationship(
        back_populates="type",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_taxonomy_types_slug"),
        CheckConstraint(
            "slug ~ '^[a-z][a-z0-9_]*$'",
            name="ck_taxonomy_types_slug_format",
        ),
        CheckConstraint(
            "value_kind IN (" + ", ".join(f"'{v}'" for v in VALUE_KINDS) + ")",
            name="ck_taxonomy_types_value_kind",
        ),
        CheckConstraint(
            "depth_max IS NULL OR depth_max > 0",
            name="ck_taxonomy_types_depth_max_positive",
        ),
        Index("idx_taxonomy_types_active", "active"),
        Index(
            "idx_taxonomy_types_filterable",
            "filterable",
            postgresql_where=text("filterable = true AND active = true"),
        ),
    )


# ---------------------------------------------------------------------------
# TaxonomyNode — nodos polimórficos
# ---------------------------------------------------------------------------


class TaxonomyNode(UuidPkMixin, Base):
    """Nodo (término/instancia) de cualquier ``TaxonomyType``.

    ``parent_id`` es el padre primario para queries tree-style. Multi-inheritance
    real vive en ``TaxonomyNodeParent`` (M:N). La closure table
    ``taxonomy_node_descendants`` se mantiene por triggers en la BD.
    """

    __tablename__ = "taxonomy_nodes"

    type_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    labels: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_acl: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    type: Mapped[TaxonomyType] = relationship(back_populates="nodes")
    parent: Mapped["TaxonomyNode | None"] = relationship(
        remote_side="TaxonomyNode.id",
        foreign_keys=[parent_id],
    )
    successor: Mapped["TaxonomyNode | None"] = relationship(
        remote_side="TaxonomyNode.id",
        foreign_keys=[superseded_by],
    )

    __table_args__ = (
        UniqueConstraint("type_id", "slug", name="uq_taxonomy_nodes_type_slug"),
        CheckConstraint(
            "slug ~ '^[a-z][a-z0-9_]*$'",
            name="ck_taxonomy_nodes_slug_format",
        ),
        CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id",
            name="ck_taxonomy_nodes_no_self_supersede",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_taxonomy_nodes_valid_range",
        ),
        Index("idx_taxonomy_nodes_type", "type_id"),
        Index(
            "idx_taxonomy_nodes_parent",
            "parent_id",
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
        Index(
            "idx_taxonomy_nodes_active",
            "type_id",
            "active",
            postgresql_where=text("active = true"),
        ),
        Index(
            "idx_taxonomy_nodes_labels_gin",
            "labels",
            postgresql_using="gin",
        ),
        Index(
            "idx_taxonomy_nodes_attributes_gin",
            "attributes",
            postgresql_using="gin",
        ),
    )


# ---------------------------------------------------------------------------
# TaxonomyNodeParent — multi-inheritance M:N
# ---------------------------------------------------------------------------


class TaxonomyNodeParent(Base):
    """Multi-inheritance: un nodo puede tener N padres (idea 20 — SNOMED-style).

    Las inserciones/borrados aquí disparan el trigger
    ``taxonomy_node_parents_closure_trigger`` que mantiene la closure table.
    """

    __tablename__ = "taxonomy_node_parents"

    node_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    parent_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    weight: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "node_id <> parent_id",
            name="ck_taxonomy_node_parents_no_self_loop",
        ),
        Index("idx_taxonomy_node_parents_parent", "parent_id"),
        Index(
            "uq_taxonomy_node_parents_primary",
            "node_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
    )


# ---------------------------------------------------------------------------
# TaxonomyNodeDescendant — closure table (read-only, mantenida por triggers)
# ---------------------------------------------------------------------------


class TaxonomyNodeDescendant(Base):
    """Closure table — NO escribir directamente desde aplicación.

    Mantenida por triggers ``taxonomy_node_parents_closure_trigger`` y
    ``taxonomy_nodes_closure_trigger``. Permite queries jerárquicas O(1)
    en lugar de CTEs recursivos.
    """

    __tablename__ = "taxonomy_node_descendants"

    ancestor_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    descendant_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("depth >= 0", name="ck_taxonomy_descendants_depth"),
        Index("idx_taxonomy_descendants_descendant", "descendant_id"),
        Index("idx_taxonomy_descendants_depth", "ancestor_id", "depth"),
    )


# ---------------------------------------------------------------------------
# TaxonomyAlias — slug evolution (rename sin romper contratos)
# ---------------------------------------------------------------------------


class TaxonomyAlias(Base):
    """Alias de slug para evolución de taxonomías sin romper código externo.

    Caso de uso: renombrar internamente ``division`` → ``business_line`` sin
    obligar al ERP a cambiar su integración. INSERT en ``taxonomy_aliases``
    con ``alias_slug='division'`` apuntando al nodo canónico.
    """

    __tablename__ = "taxonomy_aliases"

    alias_slug: Mapped[str] = mapped_column(Text, nullable=False)
    type_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_node_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    type: Mapped[TaxonomyType] = relationship(back_populates="aliases")

    __table_args__ = (
        PrimaryKeyConstraint("type_id", "alias_slug", name="pk_taxonomy_aliases"),
        CheckConstraint(
            "alias_slug ~ '^[a-z][a-z0-9_]*$'",
            name="ck_taxonomy_aliases_slug_format",
        ),
        Index("idx_taxonomy_aliases_canonical", "canonical_node_id"),
    )


# ---------------------------------------------------------------------------
# ProductTaxonomyLink — M:N products ↔ taxonomy_nodes con role
# ---------------------------------------------------------------------------


class ProductTaxonomyLink(Base):
    """Link tipado entre producto y nodo de taxonomía.

    El campo ``role`` permite el mismo (product, node) bajo distintos rolfes:
    ``belongs_to`` (clasificación), ``compatible_with`` (relación), etc.
    PK incluye ``role`` para permitir múltiples roles por par.
    """

    __tablename__ = "product_taxonomy_links"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
    )
    node_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("taxonomy_nodes.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(Text, primary_key=True, server_default=text("'belongs_to'"))
    weight: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in LINK_ROLES) + ")",
            name="ck_product_taxonomy_links_role",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_product_taxonomy_links_valid_range",
        ),
        Index("idx_product_taxonomy_links_node", "node_id"),
        Index("idx_product_taxonomy_links_role", "role"),
        Index(
            "idx_product_taxonomy_links_current",
            "product_sku",
            "node_id",
            postgresql_where=text("valid_until IS NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# FamilySchema — JSON Schema por familia como dato
# ---------------------------------------------------------------------------


class FamilySchema(UuidPkMixin, Base):
    """JSON Schema versionado por familia (substitución futura de ``specs/*.json``).

    Permite editar schema sin redeploy. El validador genérico (Pydantic +
    jsonschema) consume ``json_schema`` para validar ``products.specs``.
    """

    __tablename__ = "family_schemas"

    family_slug: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    json_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("family_schemas.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "family_slug",
            "schema_version",
            name="uq_family_schemas_slug_version",
        ),
        CheckConstraint(
            "family_slug ~ '^[a-z][a-z0-9_]*$'",
            name="ck_family_schemas_slug_format",
        ),
        CheckConstraint(
            "schema_version >= 1",
            name="ck_family_schemas_version_positive",
        ),
        Index(
            "idx_family_schemas_active",
            "family_slug",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_family_schemas_json_gin",
            "json_schema",
            postgresql_using="gin",
        ),
    )
