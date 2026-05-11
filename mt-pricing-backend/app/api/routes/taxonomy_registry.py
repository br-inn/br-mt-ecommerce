"""Taxonomy Registry API — endpoints genéricos data-driven.

Reemplaza la necesidad de tener un endpoint por taxonomía. Agregar una
dimensión nueva (mercados, certificaciones, aplicaciones, etc.) = INSERT
en ``taxonomy_types`` + nodos vía POST genérico. Cero código nuevo en
backend/frontend al crecer.

Endpoints públicos (auth: ``products:read``):
- ``GET /taxonomies/registry`` → lista de tipos para construir sidebar
- ``GET /taxonomies/{type_slug}`` → metadatos de un tipo
- ``GET /taxonomies/{type_slug}/nodes`` → lista nodos del tipo
- ``GET /taxonomies/{type_slug}/nodes/{node_slug}`` → nodo individual
- ``GET /taxonomies/{type_slug}/nodes/{node_slug}/descendants`` → vía closure
- ``GET /products/{sku}/taxonomies`` → todas las taxonomías linkeadas

Endpoints admin (auth: ``admin:taxonomy``):
- ``POST /admin/taxonomies/types`` → crear nuevo tipo
- ``PATCH /admin/taxonomies/types/{type_slug}`` → editar tipo (no slug)
- ``DELETE /admin/taxonomies/types/{type_slug}`` → soft-delete (active=false)
- ``POST /admin/taxonomies/{type_slug}/nodes`` → crear nodo
- ``PATCH /admin/taxonomies/{type_slug}/nodes/{node_slug}`` → editar nodo
- ``DELETE /admin/taxonomies/{type_slug}/nodes/{node_slug}`` → soft-delete
- ``POST /admin/products/{sku}/taxonomies`` → link producto↔nodo con role
- ``DELETE /admin/products/{sku}/taxonomies/{node_id}`` → unlink (soft)
- ``POST /admin/taxonomies/{type_slug}/aliases`` → crear alias

Reads no requieren resolver alias del type (slugs son canónicos a nivel type);
sí resuelven alias a nivel node (vía ``TaxonomyAlias``).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.repositories.taxonomy import (
    FamilySchemaRepository,
    ProductTaxonomyLinkRepository,
    TaxonomyNodeRepository,
    TaxonomyTypeRepository,
)
from app.schemas.common import ProblemDetails
from app.schemas.taxonomy_registry import (
    FamilySchemaCreate,
    FamilySchemaRead,
    ProductTaxonomyLinkCreate,
    ProductTaxonomyLinkRead,
    TaxonomyAliasCreate,
    TaxonomyAliasRead,
    TaxonomyNodeCreate,
    TaxonomyNodeRead,
    TaxonomyNodeUpdate,
    TaxonomyTypeCreate,
    TaxonomyTypeRead,
    TaxonomyTypeUpdate,
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Lecturas públicas — montadas directamente bajo /api/v1
registry_router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])
products_taxonomies_router = APIRouter(tags=["taxonomies:product-links"])

# Admin — mutaciones del registry
admin_registry_router = APIRouter(
    prefix="/admin/taxonomies", tags=["admin:taxonomy-registry"]
)
admin_products_taxonomies_router = APIRouter(
    prefix="/admin/products", tags=["admin:taxonomy-registry"]
)
admin_family_schemas_router = APIRouter(
    prefix="/admin/family-schemas", tags=["admin:taxonomy-registry"]
)


# ---------------------------------------------------------------------------
# Helpers — error responses
# ---------------------------------------------------------------------------


def _problem_response(
    *,
    status_code: int,
    title: str,
    detail: str | None = None,
    code: str | None = None,
) -> JSONResponse:
    body = ProblemDetails(
        title=title,
        status=status_code,
        detail=detail,
        code=code,
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=body)


def _http_not_found(resource: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "title": "Not found",
            "type": "about:blank",
            "status": 404,
            "detail": f"{resource} '{identifier}' no encontrado",
        },
    )


def _node_to_read(node: object, type_slug: str | None) -> TaxonomyNodeRead:
    """Hidrata TaxonomyNodeRead con el type_slug enriquecido."""
    data = TaxonomyNodeRead.model_validate(node)
    if type_slug is not None:
        data.type_slug = type_slug
    return data


# ---------------------------------------------------------------------------
# Lecturas — registry y tipos
# ---------------------------------------------------------------------------


@registry_router.get(
    "/registry",
    response_model=list[TaxonomyTypeRead],
    summary="Listar todos los tipos de taxonomía registrados (sidebar source)",
    dependencies=[Depends(require_permissions("products:read"))],
)
async def list_registry(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    filterable_only: Annotated[
        bool,
        Query(description="Solo tipos marcados filterable=true"),
    ] = False,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[TaxonomyTypeRead]:
    repo = TaxonomyTypeRepository(session)
    types = await repo.list_registry(
        active_only=not include_inactive, filterable_only=filterable_only
    )
    return [TaxonomyTypeRead.model_validate(t) for t in types]


@registry_router.get(
    "/{type_slug}",
    response_model=TaxonomyTypeRead,
    summary="Metadatos de un tipo de taxonomía",
    dependencies=[Depends(require_permissions("products:read"))],
)
async def get_type(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyTypeRead:
    repo = TaxonomyTypeRepository(session)
    instance = await repo.get_by_slug(type_slug)
    if instance is None:
        raise _http_not_found("TaxonomyType", type_slug)
    return TaxonomyTypeRead.model_validate(instance)


# ---------------------------------------------------------------------------
# Lecturas — nodes
# ---------------------------------------------------------------------------


@registry_router.get(
    "/{type_slug}/nodes",
    response_model=list[TaxonomyNodeRead],
    summary="Listar nodos de un tipo (terms)",
    dependencies=[Depends(require_permissions("products:read"))],
)
async def list_nodes(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    include_inactive: Annotated[bool, Query()] = False,
    include_deprecated: Annotated[bool, Query()] = False,
) -> list[TaxonomyNodeRead]:
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    nodes = await node_repo.list_by_type(
        t.id,
        active_only=not include_inactive,
        include_deprecated=include_deprecated,
    )
    return [_node_to_read(n, t.slug) for n in nodes]


@registry_router.get(
    "/{type_slug}/nodes/{node_slug}",
    response_model=TaxonomyNodeRead,
    summary="Obtener un nodo (resuelve aliases)",
    dependencies=[Depends(require_permissions("products:read"))],
)
async def get_node(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    node_slug: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyNodeRead:
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    node = await node_repo.resolve_slug(t.id, node_slug)
    if node is None:
        raise _http_not_found("TaxonomyNode", node_slug)
    return _node_to_read(node, t.slug)


@registry_router.get(
    "/{type_slug}/nodes/{node_slug}/descendants",
    response_model=list[TaxonomyNodeRead],
    summary="Descendientes de un nodo vía closure table (O(1))",
    dependencies=[Depends(require_permissions("products:read"))],
)
async def list_descendants(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    node_slug: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    max_depth: Annotated[int | None, Query(ge=1, le=32)] = None,
) -> list[TaxonomyNodeRead]:
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    node = await node_repo.resolve_slug(t.id, node_slug)
    if node is None:
        raise _http_not_found("TaxonomyNode", node_slug)
    descendants = await node_repo.get_descendants(node.id, max_depth=max_depth)
    return [_node_to_read(n, t.slug) for n in descendants]


# ---------------------------------------------------------------------------
# Lecturas — product taxonomy links
# ---------------------------------------------------------------------------


@products_taxonomies_router.get(
    "/products/{sku}/taxonomies",
    response_model=list[ProductTaxonomyLinkRead],
    summary="Listar todas las taxonomías linkeadas a un producto",
    dependencies=[Depends(require_permissions("products:read"))],
)
async def list_product_taxonomies(
    sku: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    role: Annotated[
        str | None, Query(description="belongs_to | compatible_with | replaces | recommends")
    ] = None,
    type_slug: Annotated[
        str | None,
        Query(description="Filtrar por slug de taxonomy_type"),
    ] = None,
    include_historic: Annotated[bool, Query()] = False,
) -> list[ProductTaxonomyLinkRead]:
    repo = ProductTaxonomyLinkRepository(session)
    links = await repo.list_for_product(
        sku,
        role=role,
        type_slug=type_slug,
        current_only=not include_historic,
    )
    return [ProductTaxonomyLinkRead.model_validate(link) for link in links]


# ---------------------------------------------------------------------------
# Admin — TaxonomyType CRUD
# ---------------------------------------------------------------------------


@admin_registry_router.post(
    "/types",
    response_model=TaxonomyTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo tipo de taxonomía (zero-code growth para nuevas dimensiones)",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def create_type(
    payload: TaxonomyTypeCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyTypeRead:
    repo = TaxonomyTypeRepository(session)
    existing = await repo.get_by_slug(payload.slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"TaxonomyType '{payload.slug}' ya existe",
        )
    instance = await repo.create(**payload.model_dump())
    return TaxonomyTypeRead.model_validate(instance)


@admin_registry_router.patch(
    "/types/{type_slug}",
    response_model=TaxonomyTypeRead,
    summary="Editar tipo (slug no editable; usar aliases)",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def update_type(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    payload: TaxonomyTypeUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyTypeRead:
    repo = TaxonomyTypeRepository(session)
    fields = payload.model_dump(exclude_unset=True)
    try:
        instance = await repo.update(type_slug, **fields)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    if instance is None:
        raise _http_not_found("TaxonomyType", type_slug)
    return TaxonomyTypeRead.model_validate(instance)


@admin_registry_router.delete(
    "/types/{type_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete (active=false) — bloqueado para is_system",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def delete_type(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    repo = TaxonomyTypeRepository(session)
    try:
        ok = await repo.soft_delete(type_slug)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    if not ok:
        raise _http_not_found("TaxonomyType", type_slug)


# ---------------------------------------------------------------------------
# Admin — TaxonomyNode CRUD
# ---------------------------------------------------------------------------


@admin_registry_router.post(
    "/{type_slug}/nodes",
    response_model=TaxonomyNodeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nodo dentro de un tipo (M:N parents soportado)",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def create_node(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    payload: TaxonomyNodeCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyNodeRead:
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    if not t.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"TaxonomyType '{type_slug}' está inactivo",
        )
    # Verificar duplicado dentro del type
    existing = await node_repo.resolve_slug(t.id, payload.slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Node '{payload.slug}' ya existe en type '{type_slug}'",
        )
    instance = await node_repo.create(
        type_id=t.id,
        slug=payload.slug,
        parent_id=payload.parent_id,
        additional_parents=payload.additional_parents,
        labels=payload.labels,
        attributes=payload.attributes,
        display_order=payload.display_order,
        node_acl=payload.node_acl,
        active=payload.active,
    )
    return _node_to_read(instance, t.slug)


@admin_registry_router.patch(
    "/{type_slug}/nodes/{node_slug}",
    response_model=TaxonomyNodeRead,
    summary="Editar nodo (slug no editable; usar aliases)",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def update_node(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    node_slug: Annotated[str, Path(min_length=1, max_length=128)],
    payload: TaxonomyNodeUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyNodeRead:
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    node = await node_repo.resolve_slug(t.id, node_slug)
    if node is None:
        raise _http_not_found("TaxonomyNode", node_slug)
    fields = payload.model_dump(exclude_unset=True)
    updated = await node_repo.update(node.id, **fields)
    return _node_to_read(updated, t.slug)


@admin_registry_router.delete(
    "/{type_slug}/nodes/{node_slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete con valid_until=now()",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def delete_node(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    node_slug: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    node = await node_repo.resolve_slug(t.id, node_slug)
    if node is None:
        raise _http_not_found("TaxonomyNode", node_slug)
    await node_repo.soft_delete(node.id)


# ---------------------------------------------------------------------------
# Admin — TaxonomyAlias
# ---------------------------------------------------------------------------


@admin_registry_router.post(
    "/{type_slug}/aliases",
    response_model=TaxonomyAliasRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear alias para evolución de slug sin romper contratos externos",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def create_alias(
    type_slug: Annotated[str, Path(min_length=1, max_length=64)],
    payload: TaxonomyAliasCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaxonomyAliasRead:
    type_repo = TaxonomyTypeRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    t = await type_repo.get_by_slug(type_slug)
    if t is None:
        raise _http_not_found("TaxonomyType", type_slug)
    canonical = await node_repo.get_by_id(payload.canonical_node_id)
    if canonical is None or canonical.type_id != t.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="canonical_node_id no pertenece al type indicado",
        )
    alias = await node_repo.add_alias(
        type_id=t.id,
        alias_slug=payload.alias_slug,
        canonical_node_id=payload.canonical_node_id,
        valid_until=payload.valid_until,
    )
    return TaxonomyAliasRead.model_validate(alias)


# ---------------------------------------------------------------------------
# Admin — Product taxonomy links
# ---------------------------------------------------------------------------


@admin_products_taxonomies_router.post(
    "/{sku}/taxonomies",
    response_model=ProductTaxonomyLinkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Linkear producto a un nodo con role específico",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def link_product_to_node(
    sku: Annotated[str, Path(min_length=1, max_length=128)],
    payload: ProductTaxonomyLinkCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductTaxonomyLinkRead:
    link_repo = ProductTaxonomyLinkRepository(session)
    node_repo = TaxonomyNodeRepository(session)
    node = await node_repo.get_by_id(payload.node_id)
    if node is None:
        raise _http_not_found("TaxonomyNode", str(payload.node_id))
    link = await link_repo.link(
        product_sku=sku,
        node_id=payload.node_id,
        role=payload.role,
        weight=payload.weight,
    )
    return ProductTaxonomyLinkRead.model_validate(link)


@admin_products_taxonomies_router.delete(
    "/{sku}/taxonomies/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink (soft = set valid_until)",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def unlink_product_from_node(
    sku: Annotated[str, Path(min_length=1, max_length=128)],
    node_id: Annotated[UUID, Path()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    role: Annotated[str, Query()] = "belongs_to",
):
    repo = ProductTaxonomyLinkRepository(session)
    ok = await repo.unlink(
        product_sku=sku, node_id=node_id, role=role, soft=True
    )
    if not ok:
        raise _http_not_found(
            "ProductTaxonomyLink", f"{sku}/{node_id}/{role}"
        )


# ---------------------------------------------------------------------------
# Admin — Family schemas (JSON Schema versionado por familia)
# ---------------------------------------------------------------------------


@admin_family_schemas_router.get(
    "/{family_slug}",
    response_model=FamilySchemaRead,
    summary="Schema activo de una familia",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def get_family_schema(
    family_slug: Annotated[str, Path(min_length=1, max_length=64)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FamilySchemaRead:
    repo = FamilySchemaRepository(session)
    instance = await repo.get_active(family_slug)
    if instance is None:
        raise _http_not_found("FamilySchema", family_slug)
    return FamilySchemaRead.model_validate(instance)


@admin_family_schemas_router.post(
    "",
    response_model=FamilySchemaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva versión de schema para una familia",
    dependencies=[Depends(require_permissions("admin:taxonomy"))],
)
async def create_family_schema(
    payload: FamilySchemaCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FamilySchemaRead:
    repo = FamilySchemaRepository(session)
    instance = await repo.create(
        family_slug=payload.family_slug,
        json_schema=payload.json_schema,
        description=payload.description,
    )
    return FamilySchemaRead.model_validate(instance)
