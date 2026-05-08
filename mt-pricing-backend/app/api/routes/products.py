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
from app.services.products import ImageService, ProductService
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
    return Pagination[ProductResponse](
        items=[ProductResponse.model_validate(r) for r in rows],
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
    summary="Solicitar signed URL para upload directo a Supabase Storage",
    responses={404: {"model": ProblemDetails}},
)
async def get_image_upload_url(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    request: ProductImageUploadRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    image_service: Annotated[ImageService, Depends(get_image_service)],
) -> dict[str, Any]:
    """Devuelve dict con `storage_path`, `upload_url`, `headers`, `expires_in`."""
    try:
        # Verifica que el producto existe (no upload a sku inválido).
        await product_service.get_product_by_id(sku)
    except ProductDomainError as e:
        _raise_domain(e)
    return image_service.generate_signed_upload_url(
        sku=sku,
        filename=request.filename,
        content_type=request.content_type,
    )


@router.post(
    "/{sku}/images/confirm",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirmar upload exitoso a Storage — crea row en product_images",
    responses={404: {"model": ProblemDetails}},
)
async def confirm_image_upload(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    payload: ProductImageConfirmRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductImageResponse:
    """Endpoint de confirmación tras PUT directo a Supabase Storage.

    Frontend flow:
        1. POST /upload-url → { storage_path, upload_url, token }
        2. supabase.storage.from(bucket).uploadToSignedUrl(path, token, file)
        3. POST /confirm → row product_images creada + thumbnails dispatch.
    """
    try:
        img = await service.confirm_image_upload(
            sku,
            storage_path=payload.storage_path,
            mime_type=payload.mime_type,
            bytes_size=payload.bytes_size,
            width=payload.width,
            height=payload.height,
            alt_text=payload.alt_text,
            is_primary=payload.is_primary,
            role=payload.role,
            actor=user,
        )
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductImageResponse.model_validate(img)


@router.post(
    "/{sku}/images/{image_id}/set-primary",
    response_model=ProductImageResponse,
    summary="Marcar imagen como primaria (resto pasa a is_primary=false)",
    responses={404: {"model": ProblemDetails}},
)
async def set_primary_image(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    image_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> ProductImageResponse:
    try:
        img = await service.set_primary_image(sku, image_id, user)
    except ProductDomainError as e:
        _raise_domain(e)
    return ProductImageResponse.model_validate(img)


@router.delete(
    "/{sku}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
    summary="Eliminar imagen del producto",
)
async def delete_image(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    image_id: UUID,
    user: Annotated[User, Depends(require_permissions("products:delete"))],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> Response:
    try:
        await service.delete_image(sku, image_id, user)
    except ProductDomainError as e:
        _raise_domain(e)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
