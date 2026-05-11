"""Repository layer — registry polimórfico de taxonomías (mig. 049/050).

CRUD + queries especializadas sobre el registry. NO commitea (caller
responsable). Provee:

- ``TaxonomyTypeRepository``: CRUD sobre tipos + listado del registry
- ``TaxonomyNodeRepository``: CRUD sobre nodos + queries jerárquicas vía
  closure table + alias resolution
- ``ProductTaxonomyLinkRepository``: M:N links con role + queries por sku/node

Convención: las funciones que aceptan ``slug`` resuelven aliases vía
``TaxonomyAlias`` antes de buscar; las que aceptan ``id`` van directo.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.taxonomy_registry import (
    FamilySchema,
    ProductTaxonomyLink,
    TaxonomyAlias,
    TaxonomyNode,
    TaxonomyNodeDescendant,
    TaxonomyNodeParent,
    TaxonomyType,
)


# ---------------------------------------------------------------------------
# TaxonomyType
# ---------------------------------------------------------------------------


class TaxonomyTypeRepository:
    """CRUD + queries sobre ``taxonomy_types``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, type_id: UUID) -> TaxonomyType | None:
        stmt = select(TaxonomyType).where(TaxonomyType.id == type_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(
        self, slug: str, *, resolve_aliases: bool = True
    ) -> TaxonomyType | None:
        """Resuelve por slug; opcionalmente sigue aliases de TaxonomyAlias.

        Para tipos: los aliases viven a nivel de TaxonomyAlias (que apunta
        a nodes, no a types). Para types, el slug es canónico — alias
        resolution aquí es no-op en versión actual; flag preservado para
        evolución (e.g. si agregamos type-level aliases en futuro).
        """
        _ = resolve_aliases  # placeholder; ver docstring
        stmt = select(TaxonomyType).where(TaxonomyType.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_registry(
        self,
        *,
        active_only: bool = True,
        filterable_only: bool = False,
    ) -> Sequence[TaxonomyType]:
        """Lista tipos para construir el sidebar / registro."""
        stmt = select(TaxonomyType).order_by(
            TaxonomyType.display_order, TaxonomyType.slug
        )
        if active_only:
            stmt = stmt.where(TaxonomyType.active.is_(True))
        if filterable_only:
            stmt = stmt.where(TaxonomyType.filterable.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **fields: Any) -> TaxonomyType:
        instance = TaxonomyType(**fields)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(
        self, slug: str, **fields: Any
    ) -> TaxonomyType | None:
        instance = await self.get_by_slug(slug, resolve_aliases=False)
        if instance is None:
            return None
        if instance.is_system:
            # Restricción de la capa repo, NO de DB. Evita rename accidental
            # de slug; otros campos sí editables vía governance.
            disallowed = {"slug", "value_kind"}
            blocked = disallowed & fields.keys()
            if blocked:
                msg = (
                    f"No se pueden modificar campos {sorted(blocked)} en "
                    f"is_system=true type '{slug}'. Usar TaxonomyAlias para rename."
                )
                raise ValueError(msg)
        for key, value in fields.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def soft_delete(self, slug: str) -> bool:
        """Marca active=false. Devuelve True si encontró el tipo."""
        instance = await self.get_by_slug(slug, resolve_aliases=False)
        if instance is None:
            return False
        if instance.is_system:
            msg = f"No se puede borrar is_system type '{slug}'"
            raise ValueError(msg)
        instance.active = False
        await self.session.flush()
        return True


# ---------------------------------------------------------------------------
# TaxonomyNode
# ---------------------------------------------------------------------------


class TaxonomyNodeRepository:
    """CRUD + queries jerárquicas sobre ``taxonomy_nodes``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, node_id: UUID) -> TaxonomyNode | None:
        stmt = select(TaxonomyNode).where(TaxonomyNode.id == node_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def resolve_slug(
        self, type_id: UUID, slug: str
    ) -> TaxonomyNode | None:
        """Resuelve slug → node siguiendo TaxonomyAlias si no encuentra directo."""
        # 1. Match directo
        stmt = select(TaxonomyNode).where(
            and_(
                TaxonomyNode.type_id == type_id,
                TaxonomyNode.slug == slug,
            )
        )
        node = (await self.session.execute(stmt)).scalar_one_or_none()
        if node is not None:
            return node

        # 2. Buscar como alias
        alias_stmt = select(TaxonomyAlias).where(
            and_(
                TaxonomyAlias.type_id == type_id,
                TaxonomyAlias.alias_slug == slug,
                or_(
                    TaxonomyAlias.valid_until.is_(None),
                    TaxonomyAlias.valid_until > func.now(),
                ),
            )
        )
        alias = (await self.session.execute(alias_stmt)).scalar_one_or_none()
        if alias is None:
            return None

        # 3. Devolver el nodo canónico apuntado por el alias
        return await self.get_by_id(alias.canonical_node_id)

    async def list_by_type(
        self,
        type_id: UUID,
        *,
        active_only: bool = True,
        include_deprecated: bool = False,
    ) -> Sequence[TaxonomyNode]:
        """Lista nodos de un type, ordenado por display_order."""
        stmt = (
            select(TaxonomyNode)
            .where(TaxonomyNode.type_id == type_id)
            .order_by(TaxonomyNode.display_order, TaxonomyNode.slug)
        )
        if active_only:
            stmt = stmt.where(TaxonomyNode.active.is_(True))
        if not include_deprecated:
            stmt = stmt.where(TaxonomyNode.valid_until.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        *,
        type_id: UUID,
        slug: str,
        parent_id: UUID | None = None,
        additional_parents: Sequence[UUID] = (),
        **fields: Any,
    ) -> TaxonomyNode:
        instance = TaxonomyNode(
            type_id=type_id,
            slug=slug,
            parent_id=parent_id,
            **fields,
        )
        self.session.add(instance)
        await self.session.flush()

        # Registrar parent primario en taxonomy_node_parents si parent_id existe
        if parent_id is not None:
            self.session.add(
                TaxonomyNodeParent(
                    node_id=instance.id,
                    parent_id=parent_id,
                    is_primary=True,
                )
            )

        # Parents adicionales (multi-inheritance) — no primary
        for p in additional_parents:
            if p == parent_id:
                continue
            self.session.add(
                TaxonomyNodeParent(
                    node_id=instance.id,
                    parent_id=p,
                    is_primary=False,
                )
            )

        await self.session.flush()
        return instance

    async def update(
        self, node_id: UUID, **fields: Any
    ) -> TaxonomyNode | None:
        instance = await self.get_by_id(node_id)
        if instance is None:
            return None
        for key, value in fields.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def soft_delete(self, node_id: UUID) -> bool:
        """Deprecación con ``valid_until = clock_timestamp()`` + active=false.

        Server-side ``clock_timestamp()`` evita el CHECK ``valid_until > valid_from``
        en escenarios donde Python ``datetime.now()`` queda por detrás del server
        clock (testcontainers tienen clock skew respecto al host).
        """
        instance = await self.get_by_id(node_id)
        if instance is None:
            return False
        stmt = (
            update(TaxonomyNode)
            .where(TaxonomyNode.id == node_id)
            .values(valid_until=func.clock_timestamp(), active=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        await self.session.refresh(instance)
        return True

    async def get_descendants(
        self, ancestor_id: UUID, *, max_depth: int | None = None
    ) -> Sequence[TaxonomyNode]:
        """Lista descendientes (excluyendo self) vía closure table — O(1)."""
        stmt = (
            select(TaxonomyNode)
            .join(
                TaxonomyNodeDescendant,
                TaxonomyNodeDescendant.descendant_id == TaxonomyNode.id,
            )
            .where(
                and_(
                    TaxonomyNodeDescendant.ancestor_id == ancestor_id,
                    TaxonomyNodeDescendant.depth > 0,
                )
            )
            .order_by(TaxonomyNodeDescendant.depth, TaxonomyNode.display_order)
        )
        if max_depth is not None:
            stmt = stmt.where(TaxonomyNodeDescendant.depth <= max_depth)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_ancestors(
        self, descendant_id: UUID
    ) -> Sequence[TaxonomyNode]:
        """Lista ancestros (excluyendo self) vía closure table."""
        stmt = (
            select(TaxonomyNode)
            .join(
                TaxonomyNodeDescendant,
                TaxonomyNodeDescendant.ancestor_id == TaxonomyNode.id,
            )
            .where(
                and_(
                    TaxonomyNodeDescendant.descendant_id == descendant_id,
                    TaxonomyNodeDescendant.depth > 0,
                )
            )
            .order_by(TaxonomyNodeDescendant.depth.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_alias(
        self,
        *,
        type_id: UUID,
        alias_slug: str,
        canonical_node_id: UUID,
        valid_until: datetime | None = None,
    ) -> TaxonomyAlias:
        """Crear alias para evolución de slug sin romper contratos."""
        alias = TaxonomyAlias(
            type_id=type_id,
            alias_slug=alias_slug,
            canonical_node_id=canonical_node_id,
            valid_until=valid_until,
        )
        self.session.add(alias)
        await self.session.flush()
        return alias


# ---------------------------------------------------------------------------
# ProductTaxonomyLink
# ---------------------------------------------------------------------------


class ProductTaxonomyLinkRepository:
    """M:N entre products y taxonomy_nodes con campo role."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_product(
        self,
        product_sku: str,
        *,
        role: str | None = None,
        type_slug: str | None = None,
        current_only: bool = True,
    ) -> Sequence[ProductTaxonomyLink]:
        """Lista links de un producto con filtros opcionales."""
        stmt = select(ProductTaxonomyLink).where(
            ProductTaxonomyLink.product_sku == product_sku
        )
        if role is not None:
            stmt = stmt.where(ProductTaxonomyLink.role == role)
        if current_only:
            stmt = stmt.where(ProductTaxonomyLink.valid_until.is_(None))
        if type_slug is not None:
            stmt = (
                stmt.join(
                    TaxonomyNode, TaxonomyNode.id == ProductTaxonomyLink.node_id
                )
                .join(
                    TaxonomyType, TaxonomyType.id == TaxonomyNode.type_id
                )
                .where(TaxonomyType.slug == type_slug)
            )
        stmt = stmt.order_by(
            ProductTaxonomyLink.role, ProductTaxonomyLink.weight.desc()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_node(
        self,
        node_id: UUID,
        *,
        role: str | None = None,
        current_only: bool = True,
    ) -> Sequence[ProductTaxonomyLink]:
        stmt = select(ProductTaxonomyLink).where(
            ProductTaxonomyLink.node_id == node_id
        )
        if role is not None:
            stmt = stmt.where(ProductTaxonomyLink.role == role)
        if current_only:
            stmt = stmt.where(ProductTaxonomyLink.valid_until.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def link(
        self,
        *,
        product_sku: str,
        node_id: UUID,
        role: str = "belongs_to",
        weight: int = 0,
        created_by: UUID | None = None,
    ) -> ProductTaxonomyLink:
        """Crear link. Idempotente por (sku, node_id, role).

        Verifica existencia ANTES de INSERT para evitar IntegrityError +
        rollback (que volaría la transacción completa del caller).
        """
        # Check first — idempotency sin tocar la transacción
        stmt = select(ProductTaxonomyLink).where(
            and_(
                ProductTaxonomyLink.product_sku == product_sku,
                ProductTaxonomyLink.node_id == node_id,
                ProductTaxonomyLink.role == role,
            )
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        instance = ProductTaxonomyLink(
            product_sku=product_sku,
            node_id=node_id,
            role=role,
            weight=weight,
            created_by=created_by,
        )
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def unlink(
        self,
        *,
        product_sku: str,
        node_id: UUID,
        role: str = "belongs_to",
        soft: bool = True,
    ) -> bool:
        """Borra o sets valid_until = clock_timestamp() (soft).

        Usamos ``clock_timestamp()`` (wall clock server-side) en vez de Python
        ``datetime.now()`` porque:
        1. ``valid_from`` se setea con server ``now()`` (transaction-start);
           ``clock_timestamp()`` siempre es ≥ ``now()`` dentro de una transacción,
           garantizando el CHECK constraint ``valid_until > valid_from``.
        2. Evita skew entre clock del container Postgres y clock del host
           (testcontainers).
        """
        if soft:
            stmt = (
                update(ProductTaxonomyLink)
                .where(
                    and_(
                        ProductTaxonomyLink.product_sku == product_sku,
                        ProductTaxonomyLink.node_id == node_id,
                        ProductTaxonomyLink.role == role,
                        ProductTaxonomyLink.valid_until.is_(None),
                    )
                )
                .values(valid_until=func.clock_timestamp())
            )
        else:
            stmt = delete(ProductTaxonomyLink).where(
                and_(
                    ProductTaxonomyLink.product_sku == product_sku,
                    ProductTaxonomyLink.node_id == node_id,
                    ProductTaxonomyLink.role == role,
                )
            )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def list_products_in_subtree(
        self,
        ancestor_node_id: UUID,
        *,
        role: str = "belongs_to",
    ) -> Sequence[str]:
        """SKUs vinculados a ancestor_node o cualquiera de sus descendientes.

        Usa closure table → query O(1) en lugar de CTE recursivo.
        """
        stmt = (
            select(ProductTaxonomyLink.product_sku)
            .join(
                TaxonomyNodeDescendant,
                TaxonomyNodeDescendant.descendant_id == ProductTaxonomyLink.node_id,
            )
            .where(
                and_(
                    TaxonomyNodeDescendant.ancestor_id == ancestor_node_id,
                    ProductTaxonomyLink.role == role,
                    ProductTaxonomyLink.valid_until.is_(None),
                )
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]


# ---------------------------------------------------------------------------
# FamilySchema
# ---------------------------------------------------------------------------


class FamilySchemaRepository:
    """JSON Schemas por familia (versionados, almacenados como dato)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, family_slug: str) -> FamilySchema | None:
        stmt = (
            select(FamilySchema)
            .where(
                and_(
                    FamilySchema.family_slug == family_slug,
                    FamilySchema.is_active.is_(True),
                )
            )
            .order_by(FamilySchema.schema_version.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_versions(self, family_slug: str) -> Sequence[FamilySchema]:
        stmt = (
            select(FamilySchema)
            .where(FamilySchema.family_slug == family_slug)
            .order_by(FamilySchema.schema_version.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        *,
        family_slug: str,
        json_schema: dict[str, Any],
        description: str | None = None,
    ) -> FamilySchema:
        """Crea una nueva versión, marca anterior como inactiva."""
        # Buscar versión actual para incrementar y deprecar
        current = await self.get_active(family_slug)
        new_version = (current.schema_version + 1) if current else 1

        new_schema = FamilySchema(
            family_slug=family_slug,
            schema_version=new_version,
            json_schema=json_schema,
            description=description,
            is_active=True,
        )
        self.session.add(new_schema)
        await self.session.flush()

        # Deprecar la versión anterior — superseded_by apunta a la nueva
        if current is not None:
            current.is_active = False
            current.superseded_by = new_schema.id
            await self.session.flush()

        return new_schema
