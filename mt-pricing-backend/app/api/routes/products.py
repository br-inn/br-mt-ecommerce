"""Products / ProductTranslations / ProductImages — API v1 routes.

Alineado con `_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml`.

Convenciones (CLAUDE.md / arquitectura):
- Path PK = `sku` (no UUID) — coherente con DDL Wave 1.
- Cursor-based pagination (no offset) — `cursor` opaco = `sku` del último item.
- RBAC vía `Depends(require_permissions("products:read"|"products:write"|"products:delete"))`.
- Audit emission a través de `ProductService` (no en handlers).
- Errores → `ProblemDetails` RFC 7807.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.pagination import decode_sku_cursor, encode_sku_cursor
from app.db.models.user import User
from app.schemas.common import Cursor, Pagination, ProblemDetails
from app.schemas.assets import (
    AssetKind,
    ProductAssetConfirmRequest,
    ProductAssetPatch,
    ProductAssetResponse,
    ProductAssetUploadRequest,
)
from app.schemas.compatibility import (
    CompatibilityKind,
    CompatibleProductSummary,
    ProductCompatibilityCreate,
    ProductCompatibilityReplaceItem,
    ProductCompatibilityResponse,
)
from app.schemas.products import (
    ProductCreate,
    ProductDataQualityPatch,
    ProductDetail,
    ProductImageConfirmRequest,
    ProductImageResponse,
    ProductImageUploadRequest,
    ProductPatch,
    ProductReplace,
    ProductResponse,
    ProductTranslationCreate,
    ProductTranslationPatch,
    ProductTranslationResponse,
)
from app.services.assets import AssetService
from app.services.assets.asset_service import AssetNotFoundError, AssetValidationError
from app.services.compatibility import (
    CompatibilityDomainError,
    CompatibilityService,
)
from app.services.components import ComponentsDomainError, ComponentsService
from app.services.products import ImageService, ProductService
from app.services.products.parent_resolver import ParentResolver, ParentResolverError
from app.services.products.product_service import ProductDomainError
from app.services.specs.specs_registry import SpecsRegistry
from app.services.specs.specs_validator import SpecsValidationError, SpecsValidator

router = APIRouter(prefix="/products", tags=["products"])

# Module-level singleton — loaded once when the module is first imported.
_specs_registry: SpecsRegistry = SpecsRegistry.get_instance()
_specs_validator: SpecsValidator = SpecsValidator(_specs_registry)


# --------------------------------------------------------------------------
# DI factories — keep service stateless; instantiated per request.
# --------------------------------------------------------------------------
def get_product_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductService:
    return ProductService(session, specs_validator=_specs_validator)


def get_image_service() -> ImageService:
    return ImageService()


def get_asset_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AssetService:
    return AssetService(session)


def get_compatibility_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompatibilityService:
    return CompatibilityService(session)


def get_components_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ComponentsService:
    return ComponentsService(session)


def get_parent_resolver(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ParentResolver:
    return ParentResolver(session)


# --------------------------------------------------------------------------
# Error helper — traduce ProductDomainError → ProblemDetails / HTTPException.
# --------------------------------------------------------------------------
def _problem(
    request: Request, status_code: int, code: str, title: str, detail: str | None = None
) -> JSONResponse:
    payload = ProblemDetails(
        type=f"https://mtme-api/errors/{code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        code=code,
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=payload)


def _raise_domain(err: ProductDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _raise_compat(err: CompatibilityDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _raise_components(err: ComponentsDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _raise_parent(err: ParentResolverError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _raise_specs_error(err: SpecsValidationError) -> None:
    """Translate SpecsValidationError → RFC 7807 422 response."""
    raise HTTPException(
        status_code=422,
        detail={
            "code": err.code,
            "title": "specs validation failed",
            "errors": [e.model_dump() for e in err.errors],
        },
    )


# ==========================================================================
# Specs schema endpoint (Wave 9)
# ==========================================================================
@router.get(
    "/specs/schema",
    summary="Obtener JSON Schema de specs para una familia/subfamilia",
    response_model=dict,
)
async def get_specs_schema(
    family: Annotated[str, Query(min_length=1, max_length=64, description="Product family key")],
    subfamily: Annotated[str | None, Query(max_length=64)] = None,
    _user: Annotated[User, Depends(require_permissions("products:read"))] = None,  # type: ignore[assignment]
) -> dict:
    """Return the JSON Schema governing ``specs`` for the requested family/subfamily.

    Fallback chain: ``{family}_{subfamily}`` → ``{family}`` → ``_default``.
    No auth required beyond ``products:read``.
    """
    return _specs_registry.get_schema(family, subfamily)



# ==========================================================================
# Listing / search / CRUD
# ==========================================================================
@router.get(
    "",
    response_model=Pagination[ProductResponse],
    summary="Listar productos con filtros y cursor pagination",
)
async def list_products(
    family: Annotated[str | None, Query()] = None,
    brand: Annotated[str | None, Query()] = None,
    translation_status: Annotated[str | None, Query(pattern=r"^(pending|draft|approved)$")] = None,
    lang: Annotated[str | None, Query(pattern=r"^(es|ar)$")] = None,
    data_quality: Annotated[
        str | None, Query(pattern=r"^(complete|partial|blocked|migrated_demo)$")
    ] = None,
    active: Annotated[bool | None, Query()] = None,
    dn: Annotated[str | None, Query(max_length=8)] = None,
    pn: Annotated[str | None, Query(max_length=8)] = None,
    material: Annotated[str | None, Query(max_length=64)] = None,
    created_after: Annotated[str | None, Query(description="ISO-8601 datetime")] = None,
    created_before: Annotated[str | None, Query(description="ISO-8601 datetime")] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=128, alias="q")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_total: Annotated[bool, Query()] = False,
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
) -> Pagination[ProductResponse]:
    """Listado paginado con filtros. Cursor-based (sku-ordered ASC).

    El cursor expuesto al cliente es ``base64url(json({"sku": "..."}))``.
    Internamente el repositorio recibe el `sku` plano. Cursor inválido → 400.

    US-1A-02-09 — añade filtros avanzados ``dn``, ``pn``, ``material``,
    ``created_after``, ``created_before``, alias de búsqueda full-text ``q``
    (PostgreSQL ``websearch_to_tsquery`` con peso por sku/name/family/brand) y
    flag opcional ``include_total`` para obtener ``total_count`` además del
    cursor.
    """
    from datetime import datetime as _dt

    def _parse_iso(value: str | None, field: str) -> _dt | None:
        if value is None:
            return None
        try:
            # Acepta sufijo Z para UTC.
            return _dt.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_datetime",
                    "title": f"`{field}` no es ISO-8601 válido",
                    "detail": str(exc),
                },
            ) from exc

    sku_cursor = decode_sku_cursor(cursor)
    # `q` (US-1A-02-09 nombre canónico OpenAPI) tiene precedencia sobre `search`
    # (alias retro-compat introducido en S1).
    effective_search = q or search
    rows, next_sku, total = await service.list_products(
        family=family,
        brand=brand,
        translation_status=translation_status,
        translation_lang=lang,
        data_quality=data_quality,
        active=active,
        dn=dn,
        pn=pn,
        material=material,
        created_after=_parse_iso(created_after, "created_after"),
        created_before=_parse_iso(created_before, "created_before"),
        search=effective_search,
        cursor=sku_cursor,
        limit=limit,
        include_total=include_total,
    )
    # Batch fetch de agregados para el listado: translation_status (es/ar) +
    # primary photo URL. Mantiene la lista cursor-based eficiente con N+0
    # round trips: 1 query Products + 1 translations + 1 assets.
    skus = [r.sku for r in rows]
    xlate_map: dict[tuple[str, str], str] = {}
    primary_photo_map: dict[str, str] = {}
    if skus:
        from sqlalchemy import select as _select

        from app.db.models.product import ProductAsset, ProductTranslation

        session = service.session
        xlate_rows = await session.execute(
            _select(
                ProductTranslation.sku,
                ProductTranslation.lang,
                ProductTranslation.status,
            ).where(
                ProductTranslation.sku.in_(skus),
                ProductTranslation.lang.in_(("es", "ar")),
            )
        )
        for sku, lang_code, status_code in xlate_rows.all():
            xlate_map[(sku, lang_code)] = status_code
        # Primary photo (kind='photo', is_primary=true, status='active') for each sku.
        photo_rows = await session.execute(
            _select(
                ProductAsset.sku,
                ProductAsset.variants,
                ProductAsset.bucket,
                ProductAsset.storage_path,
            ).where(
                ProductAsset.sku.in_(skus),
                ProductAsset.kind == "photo",
                ProductAsset.is_primary.is_(True),
                ProductAsset.status == "active",
            )
        )
        from app.core.config import settings as _settings

        sb_url = str(getattr(_settings, "SUPABASE_URL", "") or "").rstrip("/")
        for sku, variants, bucket, storage_path in photo_rows.all():
            # Prefer thumb_400 if present, else original.
            thumb_path = (variants or {}).get("webp_400") or storage_path
            if sb_url and bucket and thumb_path:
                primary_photo_map[sku] = (
                    f"{sb_url}/storage/v1/object/public/{bucket}/{thumb_path}"
                )

    items: list[ProductResponse] = []
    for r in rows:
        item = ProductResponse.model_validate(r)
        item.translation_status_es = xlate_map.get((r.sku, "es"))
        item.translation_status_ar = xlate_map.get((r.sku, "ar"))
        item.primary_image_url = primary_photo_map.get(r.sku)
        items.append(item)
    return Pagination[ProductResponse](
        items=items,
        cursor=Cursor(next=encode_sku_cursor(next_sku)),
        page_size=limit,
        total=total,
    )


@router.get(
    "/search",
    response_model=list[ProductResponse],
    summary="Búsqueda Cmd-K (trigram name_en + sku prefix)",
)
async def search_products(
    q: Annotated[str, Query(min_length=2, max_length=128)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
) -> list[ProductResponse]:
    """Búsqueda full-text simple — Sprint 1 sin pgvector; Sprint 2+ híbrido."""
    rows = await service.search_products(q, limit=limit)
    return [ProductResponse.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=ProductDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto (PIM)",
    responses={
        409: {"model": ProblemDetails, "description": "SKU duplicado"},
    },
)
async def create_product(
    data: ProductCreate,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductDetail:
    """Crea producto canónico + emite audit event."""
    try:
        prod = await service.create_product(data.model_dump(), user)
    except SpecsValidationError as e:
        _raise_specs_error(e)
    except ProductDomainError as e:
        _raise_domain(e)
    # Reload con eager translations/images (vacíos al crear).
    full = await service.get_product_by_id(prod.sku)  # type: ignore[possibly-undefined]
    return ProductDetail.model_validate(full)


@router.get(
    "/{sku}",
    response_model=ProductDetail,
    summary="Obtener producto por SKU (con translations + images)",
    responses={404: {"model": ProblemDetails}},
)
async def get_product(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
) -> ProductDetail:
    try:
        prod = await service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductDetail.model_validate(prod)


@router.patch(
    "/{sku}",
    response_model=ProductDetail,
    summary="Modificar producto (respeta manual_locked_fields)",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Campo bloqueado manualmente"},
    },
)
async def update_product(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductPatch,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductDetail:
    payload = data.model_dump(exclude_unset=True)
    try:
        await service.update_product(sku, payload, user)
        prod = await service.get_product_by_id(sku)
    except SpecsValidationError as e:
        _raise_specs_error(e)
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductDetail.model_validate(prod)  # type: ignore[possibly-undefined]


@router.put(
    "/{sku}",
    response_model=ProductDetail,
    summary="Reemplazar ficha de producto (PUT, optimistic locking via If-Match ETag)",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Campo bloqueado manualmente"},
        412: {
            "model": ProblemDetails,
            "description": "If-Match ETag no coincide con la versión actual",
        },
        422: {"model": ProblemDetails, "description": "Validación o campo inmutable"},
    },
)
async def replace_product(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductReplace,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ProductDetail:
    """Full update — todos los campos editables deben venir en el body.

    Header ``If-Match: W/"<iso8601 updated_at>"`` opcional pero recomendado:
    si se envía y no coincide con el ETag actual del recurso, retorna 412
    Precondition Failed (BR-1a-OPT-LOCK-01).

    El ETag de la versión resultante se devuelve en el header ``ETag``.
    """
    payload = data.model_dump()
    try:
        prod = await service.replace_product(sku, payload, user, if_match=if_match)
        full = await service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    response.headers["ETag"] = service.etag_for(prod)
    return ProductDetail.model_validate(full)


@router.patch(
    "/{sku}/data-quality",
    response_model=ProductDetail,
    summary="Cambiar `data_quality` de un SKU (toggle complete↔partial↔blocked)",
    responses={
        404: {"model": ProblemDetails},
        422: {"model": ProblemDetails, "description": "Transición inválida o falta de completitud"},
    },
)
async def patch_product_data_quality(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductDataQualityPatch,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    response: Response,
) -> ProductDetail:
    """Cambia el flag de calidad. Para promover a `complete`, el producto
    debe tener todos los campos obligatorios poblados (BR-1a-DQ-01)."""
    try:
        prod = await service.patch_data_quality(
            sku, data.data_quality, user, reason=data.reason
        )
        full = await service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    response.headers["ETag"] = service.etag_for(prod)
    return ProductDetail.model_validate(full)


@router.post(
    "/classify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Disparar classifier PVF rule-based en lote",
    responses={
        503: {"model": ProblemDetails, "description": "Celery no disponible"},
    },
)
async def classify_pim_batch(
    user: Annotated[User, Depends(require_permissions("products:write"))],
    only_partial: Annotated[bool, Query(description="Si false revisa todos los productos.")] = True,
    promote_to_complete: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    """Encola la task `mt.products.classify_pim_batch` que extrae
    family/material/dn/pn del `name_en` de cada producto y promueve a
    `complete` los que cumplen los 5 campos requeridos.

    Idempotente: solo modifica campos vacíos o `family='unclassified'`.
    Respeta `manual_locked_fields`. Audit por cada cambio.
    """
    try:
        from app.workers.tasks.products import classify_pim_batch_task

        async_result = classify_pim_batch_task.apply_async(
            args=[str(user.id), only_partial, promote_to_complete],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={
                "code": "classify_celery_unavailable",
                "title": "Celery no respondió.",
            },
        ) from exc

    return {
        "celery_task_id": async_result.id,
        "queued_at": async_result.date_done,
        "params": {
            "only_partial": only_partial,
            "promote_to_complete": promote_to_complete,
        },
    }


@router.delete(
    "/{sku}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Soft-delete producto (active=false + deleted_at=now)",
)
async def delete_product(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[User, Depends(require_permissions("products:delete"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Response:
    try:
        await service.soft_delete_product(sku, user)
    except ProductDomainError as e:
        _raise_domain(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================================================
# Translations
# ==========================================================================
@router.get(
    "/{sku}/translations",
    response_model=list[ProductTranslationResponse],
    summary="Listar traducciones de un producto",
    responses={404: {"model": ProblemDetails}},
)
async def list_translations(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
) -> list[ProductTranslationResponse]:
    try:
        rows = await service.list_translations(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    return [ProductTranslationResponse.model_validate(r) for r in rows]


@router.put(
    "/{sku}/translations/{lang}",
    response_model=ProductTranslationResponse,
    summary="Crear o actualizar traducción (idempotente, lang ∈ {es, ar})",
    responses={404: {"model": ProblemDetails}},
)
async def upsert_translation(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    lang: Annotated[str, Path(pattern=r"^(es|ar)$")],
    data: ProductTranslationCreate,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductTranslationResponse:
    try:
        row, _created = await service.upsert_translation(
            sku, lang, data.model_dump(exclude_unset=True), user
        )
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductTranslationResponse.model_validate(row)


@router.patch(
    "/{sku}/translations/{lang}",
    response_model=ProductTranslationResponse,
    summary="Modificar traducción (parcial)",
    responses={404: {"model": ProblemDetails}},
)
async def patch_translation(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    lang: Annotated[str, Path(pattern=r"^(es|ar)$")],
    data: ProductTranslationPatch,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductTranslationResponse:
    try:
        row = await service.update_translation(
            sku, lang, data.model_dump(exclude_unset=True), user
        )
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductTranslationResponse.model_validate(row)


@router.post(
    "/{sku}/translations/{lang}/approve",
    response_model=ProductTranslationResponse,
    summary="Aprobar traducción (workflow review→approved)",
    responses={404: {"model": ProblemDetails}},
)
async def approve_translation(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    lang: Annotated[str, Path(pattern=r"^(es|ar)$")],
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductTranslationResponse:
    try:
        row = await service.approve_translation(sku, lang, user)
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductTranslationResponse.model_validate(row)


# ==========================================================================
# Images
# ==========================================================================
@router.get(
    "/{sku}/images",
    response_model=list[ProductImageResponse],
    summary="Listar imágenes de un producto",
    responses={404: {"model": ProblemDetails}},
)
async def list_images(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
) -> list[ProductImageResponse]:
    try:
        prod = await service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    return [ProductImageResponse.model_validate(i) for i in prod.images]


@router.post(
    "/{sku}/images/upload-url",
    summary="[DEPRECATED] Solicitar signed URL — use /assets/upload-url",
    responses={404: {"model": ProblemDetails}},
    deprecated=True,
)
async def get_image_upload_url(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    request: ProductImageUploadRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    response: Response,
) -> dict[str, Any]:
    """DEPRECATED — proxy to /assets/upload-url with kind=photo."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'</{sku}/assets/upload-url>; rel="successor-version"'
    try:
        await product_service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    filename = getattr(request, "filename", "image.jpg")
    mime_type = getattr(request, "content_type", "image/jpeg")
    return asset_service.generate_signed_upload_url(
        sku=sku,
        kind="photo",
        filename=filename,
        mime_type=mime_type,
    )


@router.post(
    "/{sku}/images/confirm",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[DEPRECATED] Confirmar upload — use /assets/{asset_id}/confirm",
    responses={404: {"model": ProblemDetails}},
    deprecated=True,
)
async def confirm_image_upload(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    payload: ProductImageConfirmRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    response: Response,
) -> ProductImageResponse:
    """DEPRECATED — proxy to new asset confirm with kind=photo."""
    response.headers["Deprecation"] = "true"
    try:
        await service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    try:
        asset = await asset_service.confirm_upload(
            sku,
            storage_path=payload.storage_path,
            kind="photo",
            mime_type=payload.mime_type,
            bytes_size=payload.bytes_size,
            width=payload.width,
            height=payload.height,
            alt_text=payload.alt_text,
            is_primary=payload.is_primary,
            actor_id=user.id,
        )
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProductImageResponse.model_validate(asset)


@router.post(
    "/{sku}/images/{image_id}/set-primary",
    response_model=ProductImageResponse,
    summary="[DEPRECATED] Marcar imagen como primaria — use /assets/{asset_id}/primary",
    responses={404: {"model": ProblemDetails}},
    deprecated=True,
)
async def set_primary_image(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    image_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    response: Response,
) -> ProductImageResponse:
    """DEPRECATED — proxy to PATCH /assets/{asset_id}/primary."""
    response.headers["Deprecation"] = "true"
    try:
        asset = await asset_service.set_primary(image_id, sku)
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    return ProductImageResponse.model_validate(asset)


@router.delete(
    "/{sku}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="[DEPRECATED] Eliminar imagen — use DELETE /assets/{asset_id}",
    deprecated=True,
)
async def delete_image(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    image_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:delete"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    response: Response,
) -> Response:
    """DEPRECATED — proxy to DELETE /assets/{asset_id}."""
    response.headers["Deprecation"] = "true"
    try:
        await asset_service.delete_hard(image_id, sku)
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================================================
# Assets (Wave 1) — new endpoints
# ==========================================================================
@router.get(
    "/{sku}/assets",
    response_model=list[ProductAssetResponse],
    summary="Listar assets de un producto (filtro opcional por kind)",
    responses={404: {"model": ProblemDetails}},
)
async def list_assets(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: Annotated[AssetKind | None, Query()] = None,
    include_archived: Annotated[bool, Query()] = False,
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
    asset_service: AssetService = Depends(get_asset_service),
) -> list[ProductAssetResponse]:
    try:
        await service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    assets = await asset_service.list_for_product(
        sku, kind=kind.value if kind else None, include_archived=include_archived
    )
    return [ProductAssetResponse.model_validate(a) for a in assets]


@router.post(
    "/{sku}/assets/upload-url",
    summary="Solicitar signed URL para upload directo a Supabase Storage (multi-kind)",
    responses={404: {"model": ProblemDetails}},
)
async def get_asset_upload_url(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    request: ProductAssetUploadRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
) -> dict[str, Any]:
    """Devuelve dict con storage_path, upload_url, token, headers, expires_in, bucket, kind."""
    try:
        await product_service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    try:
        return asset_service.generate_signed_upload_url(
            sku=sku,
            kind=request.kind.value,
            filename=request.filename,
            mime_type=request.mime_type,
        )
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{sku}/assets/{asset_id}/confirm",
    response_model=ProductAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirmar upload exitoso — persiste row en product_assets",
    responses={404: {"model": ProblemDetails}},
)
async def confirm_asset_upload(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    asset_id: UUID,
    payload: ProductAssetConfirmRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
) -> ProductAssetResponse:
    """Frontend flow:
      1. POST /upload-url → { storage_path, upload_url, token }
      2. supabase.storage.from(bucket).uploadToSignedUrl(path, token, file)
      3. POST /assets/{uuid}/confirm → row product_assets created + thumbnails queued.
    """
    try:
        await product_service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    try:
        asset = await asset_service.confirm_upload(
            sku,
            storage_path=payload.storage_path,
            kind=payload.kind.value,
            mime_type=payload.mime_type,
            bytes_size=payload.bytes_size,
            width=payload.width,
            height=payload.height,
            alt_text=payload.alt_text,
            locale=payload.locale,
            caption=payload.caption,
            is_primary=payload.is_primary,
            position=payload.position,
            actor_id=user.id,
        )
    except AssetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Dispatch thumbnails for photo-like kinds.
    if asset.kind in ("photo", "banner", "mirror_url"):
        try:
            from app.workers.thumbnails import generate_thumbnails

            generate_thumbnails.delay(sku, asset.storage_path)
        except Exception:  # noqa: BLE001
            pass

    return ProductAssetResponse.model_validate(asset)


@router.patch(
    "/{sku}/assets/{asset_id}/primary",
    response_model=ProductAssetResponse,
    summary="Marcar asset como primario dentro de su kind",
    responses={404: {"model": ProblemDetails}},
)
async def set_primary_asset(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    asset_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    request: Request,
) -> ProductAssetResponse:
    try:
        asset = await asset_service.set_primary(asset_id, sku)
    except AssetNotFoundError:
        return _problem(request, 404, "asset_not_found", "Asset not found")
    return ProductAssetResponse.model_validate(asset)


@router.patch(
    "/{sku}/assets/{asset_id}/archive",
    response_model=ProductAssetResponse,
    summary="Archivar asset (soft-delete)",
    responses={404: {"model": ProblemDetails}},
)
async def archive_asset(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    asset_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    request: Request,
) -> ProductAssetResponse:
    try:
        asset = await asset_service.archive(asset_id, sku, actor_id=user.id)
    except AssetNotFoundError:
        return _problem(request, 404, "asset_not_found", "Asset not found")
    return ProductAssetResponse.model_validate(asset)


@router.patch(
    "/{sku}/assets/{asset_id}/restore",
    response_model=ProductAssetResponse,
    summary="Restaurar asset archivado",
    responses={404: {"model": ProblemDetails}},
)
async def restore_asset(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    asset_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    request: Request,
) -> ProductAssetResponse:
    try:
        asset = await asset_service.restore(asset_id, sku)
    except AssetNotFoundError:
        return _problem(request, 404, "asset_not_found", "Asset not found")
    return ProductAssetResponse.model_validate(asset)


@router.delete(
    "/{sku}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Eliminar asset permanentemente",
    responses={404: {"model": ProblemDetails}},
)
async def delete_asset(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    asset_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:delete"))],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
) -> Response:
    """Hard delete. Requires `assets:certify` for certificate_pdf kind, else `products:delete`."""
    try:
        await asset_service.delete_hard(asset_id, sku)
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail="Asset not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================================================
# Compatibility — Wave 7 (recambios / accesorios M:N)
# ==========================================================================

def _build_compat_response(row: Any) -> ProductCompatibilityResponse:
    """Construye el schema de respuesta desnormalizando compatible_product."""
    compatible_product: CompatibleProductSummary | None = None
    if row.compatible_with is not None:
        prod = row.compatible_with
        # primary_image_url: primer image con is_primary=True, o None.
        primary_img = next(
            (img.storage_path for img in getattr(prod, "images", []) if img.is_primary),
            None,
        )
        compatible_product = CompatibleProductSummary(
            sku=prod.sku,
            name_en=prod.name_en,
            family=prod.family,
            primary_image_url=primary_img,
        )
    data = {
        "id": row.id,
        "product_sku": row.product_sku,
        "compatible_with_sku": row.compatible_with_sku,
        "kind": row.kind,
        "notes": row.notes,
        "position": row.position,
        "created_at": row.created_at,
        "created_by": row.created_by,
        "compatible_product": compatible_product,
    }
    return ProductCompatibilityResponse.model_validate(data)


@router.get(
    "/{sku}/compatibility",
    response_model=list[ProductCompatibilityResponse],
    summary="Listar compatibilidades outgoing de un producto (recambios, accesorios, etc.)",
    responses={404: {"model": ProblemDetails}},
)
async def list_compatibility(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: Annotated[CompatibilityKind | None, Query()] = None,
    _user: User = Depends(require_permissions("products:read")),
    service: CompatibilityService = Depends(get_compatibility_service),
) -> list[ProductCompatibilityResponse]:
    """Devuelve los enlaces donde `sku` es el producto origen (outgoing).

    Filtra opcionalmente por `kind` (spare_part, accessory, replaces, replaced_by,
    compatible_with).
    """
    try:
        rows = await service.list_for_product(sku, kind=kind.value if kind else None)
    except CompatibilityDomainError as e:
        _raise_compat(e)
    return [_build_compat_response(r) for r in rows]


@router.get(
    "/{sku}/compatibility/inverse",
    response_model=list[ProductCompatibilityResponse],
    summary="Listar compatibilidades incoming (productos que apuntan a este SKU como destino)",
    responses={404: {"model": ProblemDetails}},
)
async def list_compatibility_inverse(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: Annotated[CompatibilityKind | None, Query()] = None,
    _user: User = Depends(require_permissions("products:read")),
    service: CompatibilityService = Depends(get_compatibility_service),
) -> list[ProductCompatibilityResponse]:
    """Devuelve los enlaces donde `sku` es el producto destino (incoming).

    Útil para «¿qué productos tienen este SKU como recambio/accesorio?»
    La respuesta incluye ``compatible_product`` = None (el origen está en ``product``).
    """
    try:
        rows = await service.list_inverse(sku, kind=kind.value if kind else None)
    except CompatibilityDomainError as e:
        _raise_compat(e)
    # Para inverse, product_sku es el origen; no desnormalizamos compatible_with
    # (es el SKU consultado). Devolvemos los datos tal cual.
    return [
        ProductCompatibilityResponse(
            id=r.id,
            product_sku=r.product_sku,
            compatible_with_sku=r.compatible_with_sku,
            kind=r.kind,
            notes=r.notes,
            position=r.position,
            created_at=r.created_at,
            created_by=r.created_by,
            compatible_product=None,
        )
        for r in rows
    ]


@router.post(
    "/{sku}/compatibility",
    response_model=ProductCompatibilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir enlace de compatibilidad (spare_part, accessory, replaces, etc.)",
    responses={
        404: {"model": ProblemDetails, "description": "SKU no encontrado"},
        409: {"model": ProblemDetails, "description": "Enlace duplicado"},
        422: {"model": ProblemDetails, "description": "Self-loop o validación"},
    },
)
async def add_compatibility(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductCompatibilityCreate,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[CompatibilityService, Depends(get_compatibility_service)],
) -> ProductCompatibilityResponse:
    """Crea un enlace ``sku`` → ``kind`` → ``compatible_with_sku``.

    Para ``replaces``/``replaced_by`` también crea automáticamente el inverso.
    """
    try:
        link = await service.add_link(
            sku,
            data.compatible_with_sku,
            data.kind.value,
            notes=data.notes,
            position=data.position,
            actor_id=user.id,
            actor_email=getattr(user, "email", None),
        )
    except CompatibilityDomainError as e:
        _raise_compat(e)
    return _build_compat_response(link)


@router.delete(
    "/{sku}/compatibility/{compatible_with_sku}/{kind}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Eliminar enlace de compatibilidad",
    responses={404: {"model": ProblemDetails}},
)
async def remove_compatibility(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    compatible_with_sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: CompatibilityKind,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[CompatibilityService, Depends(get_compatibility_service)],
) -> Response:
    """Elimina el enlace ``sku`` → ``kind`` → ``compatible_with_sku``.

    Para ``replaces``/``replaced_by`` también elimina el inverso.
    """
    try:
        await service.remove_link(
            sku,
            compatible_with_sku,
            kind.value,
            actor_id=user.id,
            actor_email=getattr(user, "email", None),
        )
    except CompatibilityDomainError as e:
        _raise_compat(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{sku}/compatibility",
    response_model=list[ProductCompatibilityResponse],
    summary="Reemplazar todos los enlaces de compatibilidad de un producto (bulk replace)",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Conflicto de integridad"},
        422: {"model": ProblemDetails, "description": "Self-loop o validación"},
    },
)
async def replace_compatibility(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: list[ProductCompatibilityReplaceItem],
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[CompatibilityService, Depends(get_compatibility_service)],
) -> list[ProductCompatibilityResponse]:
    """Reemplaza TODOS los enlaces outgoing de ``sku`` con la lista del body.

    Body: array de ``{compatible_with_sku, kind, notes?, position?}``.
    Array vacío ``[]`` elimina todas las compatibilidades.
    """
    links = [
        {
            "compatible_with_sku": item.compatible_with_sku,
            "kind": item.kind.value,
            "notes": item.notes,
            "position": item.position,
        }
        for item in data
    ]
    try:
        created = await service.replace_all_for_product(
            sku,
            links,
            actor_id=user.id,
            actor_email=getattr(user, "email", None),
        )
    except CompatibilityDomainError as e:
        _raise_compat(e)
    return [_build_compat_response(r) for r in created]


# ==========================================================================
# Wave 3 — Components (materials + connections)
# ==========================================================================
from app.schemas.components import (  # noqa: E402
    ProductConnectionCreate,
    ProductConnectionPatch,
    ProductConnectionResponse,
    ProductConnectionsReplaceRequest,
    ProductMaterialCreate,
    ProductMaterialPatch,
    ProductMaterialResponse,
    ProductMaterialsReplaceRequest,
)


# ---- Materials -----------------------------------------------------------
@router.get(
    "/{sku}/materials",
    response_model=list[ProductMaterialResponse],
    summary="Listar materiales por componente",
)
async def list_materials(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ComponentsService = Depends(get_components_service),
) -> list[ProductMaterialResponse]:
    try:
        rows = await service.list_materials(sku)
    except ComponentsDomainError as e:
        _raise_components(e)
    return [ProductMaterialResponse.model_validate(r) for r in rows]


@router.post(
    "/{sku}/materials",
    response_model=ProductMaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir/actualizar un material por componente (upsert por PK)",
)
async def upsert_material(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductMaterialCreate,
    _user: User = Depends(require_permissions("products:write")),
    service: ComponentsService = Depends(get_components_service),
) -> ProductMaterialResponse:
    try:
        row = await service.add_material(
            sku,
            component=data.component,
            position=data.position,
            material=data.material,
            observations=data.observations,
        )
    except ComponentsDomainError as e:
        _raise_components(e)
    return ProductMaterialResponse.model_validate(row)


@router.delete(
    "/{sku}/materials/{component}/{position}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un material específico (component+position)",
)
async def delete_material(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    component: Annotated[str, Path(min_length=1, max_length=32)],
    position: Annotated[int, Path(ge=0, le=99)],
    _user: User = Depends(require_permissions("products:write")),
    service: ComponentsService = Depends(get_components_service),
) -> Response:
    try:
        await service.delete_material(sku, component, position)
    except ComponentsDomainError as e:
        _raise_components(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{sku}/materials",
    response_model=list[ProductMaterialResponse],
    summary="Reemplazar TODA la lista de materiales del producto",
)
async def replace_materials(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductMaterialsReplaceRequest,
    _user: User = Depends(require_permissions("products:write")),
    service: ComponentsService = Depends(get_components_service),
) -> list[ProductMaterialResponse]:
    try:
        rows = await service.replace_materials(
            sku,
            [item.model_dump() for item in data.items],
        )
    except ComponentsDomainError as e:
        _raise_components(e)
    return [ProductMaterialResponse.model_validate(r) for r in rows]


# ---- Connections ---------------------------------------------------------
@router.get(
    "/{sku}/connections",
    response_model=list[ProductConnectionResponse],
    summary="Listar conexiones del producto (puertos físicos)",
)
async def list_connections(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    service: ComponentsService = Depends(get_components_service),
) -> list[ProductConnectionResponse]:
    try:
        rows = await service.list_connections(sku)
    except ComponentsDomainError as e:
        _raise_components(e)
    return [ProductConnectionResponse.model_validate(r) for r in rows]


@router.post(
    "/{sku}/connections",
    response_model=ProductConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir/actualizar una conexión (upsert por position)",
)
async def upsert_connection(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductConnectionCreate,
    _user: User = Depends(require_permissions("products:write")),
    service: ComponentsService = Depends(get_components_service),
) -> ProductConnectionResponse:
    try:
        row = await service.add_connection(
            sku,
            position=data.position,
            connection_type=data.connection_type,
            dn=data.dn,
            dn_real=data.dn_real,
            size=data.size,
            threading=data.threading,
            notes=data.notes,
        )
    except ComponentsDomainError as e:
        _raise_components(e)
    return ProductConnectionResponse.model_validate(row)


@router.delete(
    "/{sku}/connections/{position}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una conexión específica (por position)",
)
async def delete_connection(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    position: Annotated[int, Path(ge=1, le=8)],
    _user: User = Depends(require_permissions("products:write")),
    service: ComponentsService = Depends(get_components_service),
) -> Response:
    try:
        await service.delete_connection(sku, position)
    except ComponentsDomainError as e:
        _raise_components(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{sku}/connections",
    response_model=list[ProductConnectionResponse],
    summary="Reemplazar TODA la lista de conexiones del producto",
)
async def replace_connections(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductConnectionsReplaceRequest,
    _user: User = Depends(require_permissions("products:write")),
    service: ComponentsService = Depends(get_components_service),
) -> list[ProductConnectionResponse]:
    try:
        rows = await service.replace_connections(
            sku,
            [item.model_dump() for item in data.items],
        )
    except ComponentsDomainError as e:
        _raise_components(e)
    return [ProductConnectionResponse.model_validate(r) for r in rows]


# ==========================================================================
# Wave 5 — Parent / variant resolution (inheritance with fallback)
# ==========================================================================
@router.get(
    "/{sku}/resolved",
    summary="Devuelve specs+assets+translations resueltos con fallback al padre",
)
async def get_resolved_view(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    resolver: ParentResolver = Depends(get_parent_resolver),
) -> dict[str, Any]:
    """Para variantes, devuelve campos heredados del padre cuando faltan localmente.

    Útil para vistas de detalle: el frontend pinta una badge "heredado de PARENT_SKU"
    cuando ``inherited_from`` no es null.
    """
    specs, specs_inherited = await resolver.resolve_specs(sku)
    assets, assets_inherited = await resolver.resolve_assets(sku)
    translations, tr_inherited = await resolver.resolve_translations(sku)
    return {
        "sku": sku,
        "specs": specs,
        "specs_inherited_from": specs_inherited,
        "assets_count": len(list(assets)),
        "assets_inherited_from": assets_inherited,
        "translations_count": len(list(translations)),
        "translations_inherited_from": tr_inherited,
    }


@router.post(
    "/{sku}/parent",
    summary="Asignar/cambiar el parent_sku de una variante (valida ciclos y profundidad)",
)
async def set_parent(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    parent_sku: Annotated[str | None, Query(max_length=64)] = None,
    user: User = Depends(require_permissions("products:write")),
    service: ProductService = Depends(get_product_service),
    resolver: ParentResolver = Depends(get_parent_resolver),
) -> dict[str, Any]:
    """Asigna ``parent_sku`` a un producto. ``null`` lo desasocia.

    Valida ciclo, existencia del padre, y profundidad máxima 1.
    """
    try:
        await resolver.validate_parent_link(sku, parent_sku)
    except ParentResolverError as e:
        _raise_parent(e)
    # Update product.
    try:
        await service.update_product(sku, {"parent_sku": parent_sku}, user)
    except ProductDomainError as e:
        _raise_domain(e)
    # Sync flags after persistence.
    await resolver.recompute_parent_flags(sku)
    return {"sku": sku, "parent_sku": parent_sku}
