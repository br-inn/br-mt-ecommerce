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
    BoreDimensionRead,
    ProductCreate,
    ProductDataQualityPatch,
    ProductDetail,
    ProductImageConfirmRequest,
    ProductImageResponse,
    ProductImageUploadRequest,
    ProductMini,
    ProductPatch,
    ProductReleasePatch,
    ProductReleaseCreate,
    ProductReleaseResponse,
    ProductReplace,
    ProductResponse,
    ProductTranslationCreate,
    ProductTranslationPatch,
    ProductTranslationResponse,
    ProductUomConversionCreate,
    ProductUomConversionResponse,
)
from app.schemas.facets import FacetsResponse
from app.schemas.product_models import (
    CertificateResponse,
    ModelFlowDataResponse,
    ProductModelResponse,
)
from app.schemas.vocabularies import MaterialResponse, SeriesResponse
from app.services.assets import AssetService
from app.services.assets.asset_service import AssetNotFoundError, AssetValidationError
from app.services.compatibility import (
    CompatibilityDomainError,
    CompatibilityService,
)
from app.services.components import ComponentsDomainError, ComponentsService
from app.repositories.product import ProductBoreDimensionRepository
from app.services.products import ImageService, ProductService
from app.services.products.facets_service import ProductFilters, compute_facets
from app.services.products.parent_resolver import ParentResolver, ParentResolverError
from app.services.products.product_service import ProductDomainError
from app.services.specs.specs_registry import SpecsRegistry
from app.services.specs.specs_validator import SpecsValidationError, SpecsValidator
from pydantic import BaseModel

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


def get_bore_dimension_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductBoreDimensionRepository:
    return ProductBoreDimensionRepository(session)


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


# --------------------------------------------------------------------------
# Stage 3 (Wave 11) — detail enrichment helper
# --------------------------------------------------------------------------
async def _build_product_detail(
    prod: Any, session: AsyncSession
) -> ProductDetail:
    """Construye ``ProductDetail`` enriquecido con series/material/display_pair
    (Stage 3) y ``division_codes`` derivado de ``product_divisions``.

    Notas:
    - ``Product.series`` y ``Product.material`` son columnas TEXT (Wave 2/1).
      No se solapan con relaciones SQLAlchemy en el modelo, así que cargamos
      los vocabularios de Stage 3 con queries directas usando ``series_id`` y
      ``material_id``.
    - ``display_pair`` se resuelve por ``display_pair_sku`` self-FK.
    """
    from sqlalchemy import select as _select

    from app.db.models.product import Product as _ProdModel
    from app.db.models.vocabularies import Material, Series

    base = ProductResponse.model_validate(prod).model_dump()
    # division_codes desde product_divisions eager-loaded.
    base["division_codes"] = [
        pd.division.code
        for pd in (prod.product_divisions or [])
        if pd.division is not None
    ]

    photo_assets = [i for i in prod.assets if i.kind == "photo"]
    primary_image_url = next(
        (i.original_url for i in photo_assets if i.is_primary),
        next((i.original_url for i in photo_assets), None),
    )

    detail_data: dict[str, Any] = {
        **base,
        "translations": [
            ProductTranslationResponse.model_validate(t) for t in prod.translations
        ],
        "images": [ProductImageResponse.model_validate(i) for i in photo_assets],
        "primary_image_url": primary_image_url,
        "series_detail": None,
        "material_detail": None,
        "display_pair": None,
        "model_detail": None,
    }

    # Cargar Series si tenemos series_id.
    if getattr(prod, "series_id", None):
        srow = (
            await session.execute(
                _select(Series).where(Series.id == prod.series_id)
            )
        ).scalar_one_or_none()
        if srow is not None:
            detail_data["series_detail"] = SeriesResponse.model_validate(srow)

    if getattr(prod, "material_id", None):
        mrow = (
            await session.execute(
                _select(Material).where(Material.id == prod.material_id)
            )
        ).scalar_one_or_none()
        if mrow is not None:
            detail_data["material_detail"] = MaterialResponse.model_validate(mrow)

    if getattr(prod, "display_pair_sku", None):
        prow = (
            await session.execute(
                _select(_ProdModel).where(_ProdModel.sku == prod.display_pair_sku)
            )
        ).scalar_one_or_none()
        if prow is not None:
            detail_data["display_pair"] = ProductMini(
                sku=prow.sku,
                name_en=prow.name_en,
                # `image_url` dropeado en mig 053; primary image se resuelve vía
                # ProductAsset (kind='photo', is_primary=true) en el listado.
                primary_image_url=None,
            )

    if prod.model is not None:
        detail_data["model_detail"] = ProductModelResponse.model_validate(prod.model)

    return ProductDetail.model_validate(detail_data)


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
# Export
# ==========================================================================
@router.get(
    "/export",
    summary="Exportar catálogo a CSV",
    response_class=Response,
)
async def export_products_csv(
    family: Annotated[str | None, Query()] = None,
    subfamily: Annotated[str | None, Query(max_length=64)] = None,
    type: Annotated[  # noqa: A002
        str | None, Query(max_length=64, alias="type")
    ] = None,
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
    division: Annotated[str | None, Query(max_length=64, description="division.code o slug")] = None,
    series_id: Annotated[
        str | None,
        Query(max_length=64, description="series.id (UUID) o slug del registry"),
    ] = None,
    material_id: Annotated[
        str | None,
        Query(max_length=64, description="materials.id (UUID) o slug del registry"),
    ] = None,
    tier_code: Annotated[str | None, Query(max_length=32, description="series_tiers.code")] = None,
    _user: User = Depends(require_permissions("products:read")),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Exporta el catálogo filtrado como CSV (máx. 10 000 filas).

    Acepta los mismos filtros que ``GET /products``. No devuelve paginación:
    retorna hasta 10 000 registros ordenados por SKU ASC.
    """
    import csv
    import io
    from datetime import datetime as _dt

    def _parse_iso(value: str | None, field: str) -> _dt | None:
        if value is None:
            return None
        try:
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

    rows, _next_sku, _total = await service.list_products(
        family=family,
        subfamily=subfamily,
        type_=type,
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
        search=q,
        cursor=None,
        limit=10_000,
        include_total=False,
        division_code=division,
        series_id=series_id,
        material_id=material_id,
        tier_code=tier_code,
    )

    _EXPORT_FIELDS = [
        "sku", "name_en", "family", "subfamily", "type", "brand",
        "material", "dn", "pn", "lifecycle_status", "data_quality",
        "created_at", "updated_at",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for p in rows:
        writer.writerow({
            "sku": p.sku,
            "name_en": p.name_en or "",
            "family": p.family or "",
            "subfamily": p.subfamily or "",
            "type": getattr(p, "type", None) or "",
            "brand": p.brand or "",
            "material": p.material or "",
            "dn": p.dn or "",
            "pn": p.pn or "",
            "lifecycle_status": p.lifecycle_status or "",
            "data_quality": p.data_quality or "",
            "created_at": str(p.created_at or ""),
            "updated_at": str(p.updated_at or ""),
        })

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="products-export.csv"',
            "Cache-Control": "no-store",
        },
    )


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
    subfamily: Annotated[str | None, Query(max_length=64)] = None,
    type: Annotated[  # noqa: A002 — query param name
        str | None, Query(max_length=64, alias="type")
    ] = None,
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
    # Stage 3 (Wave 11) — division/series/material/tier filters.
    # series_id/material_id aceptan UUID (legacy contract) o SLUG del registry
    # (mig 050+). El repo resuelve slug→UUID via tabla legacy code lookup.
    division: Annotated[str | None, Query(max_length=64, description="division.code o slug")] = None,
    series_id: Annotated[
        str | None,
        Query(max_length=64, description="series.id (UUID) o slug del registry"),
    ] = None,
    material_id: Annotated[
        str | None,
        Query(max_length=64, description="materials.id (UUID) o slug del registry"),
    ] = None,
    tier_code: Annotated[str | None, Query(max_length=32, description="series_tiers.code")] = None,
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
        subfamily=subfamily,
        type_=type,
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
        # Stage 3 (Wave 11)
        division_code=division,
        series_id=series_id,
        material_id=material_id,
        tier_code=tier_code,
    )
    # Batch fetch de agregados para el listado: translation_status (es/ar) +
    # primary photo URL. Mantiene la lista cursor-based eficiente con N+0
    # round trips: 1 query Products + 1 translations + 1 assets.
    skus = [r.sku for r in rows]
    xlate_map: dict[tuple[str, str], str] = {}
    primary_photo_map: dict[str, str] = {}
    division_codes_map: dict[str, list[str]] = {}
    # Build translation status from already selectin-loaded translations (no extra roundtrip).
    for r in rows:
        for t in r.translations or []:
            if t.lang in ("es", "ar"):
                xlate_map[(r.sku, t.lang)] = t.status
    if skus:
        from sqlalchemy import select as _select

        from app.db.models.product import ProductAsset
        from app.db.models.vocabularies import Division, ProductDivision

        session = service.session
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
        # Stage 3 — division_codes batch fetch (M:N).
        div_rows = await session.execute(
            _select(ProductDivision.product_sku, Division.code)
            .join(Division, Division.id == ProductDivision.division_id)
            .where(ProductDivision.product_sku.in_(skus))
        )
        for sku, code in div_rows.all():
            division_codes_map.setdefault(sku, []).append(code)

    items: list[ProductResponse] = []
    for r in rows:
        item = ProductResponse.model_validate(r)
        item.translation_status_es = xlate_map.get((r.sku, "es"))
        item.translation_status_ar = xlate_map.get((r.sku, "ar"))
        item.primary_image_url = primary_photo_map.get(r.sku)
        item.division_codes = division_codes_map.get(r.sku, [])
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
    return await _build_product_detail(full, service.session)


@router.get(
    "/facets",
    response_model=FacetsResponse,
    summary="Counts por dimensión con refinements non-destructivos (Algolia-style)",
)
async def get_facets(
    family: Annotated[str | None, Query()] = None,
    subfamily: Annotated[str | None, Query(max_length=64)] = None,
    type: Annotated[  # noqa: A002
        str | None, Query(max_length=64, alias="type")
    ] = None,
    brand: Annotated[str | None, Query()] = None,
    material: Annotated[str | None, Query()] = None,
    dn: Annotated[str | None, Query(max_length=8)] = None,
    pn: Annotated[str | None, Query(max_length=8)] = None,
    data_quality: Annotated[str | None, Query()] = None,
    active: Annotated[bool | None, Query()] = None,
    has_image: Annotated[bool | None, Query()] = None,
    lifecycle_status: Annotated[str | None, Query()] = None,
    translation_status: Annotated[
        str | None, Query(pattern=r"^(pending|draft|approved)$")
    ] = None,
    translation_lang: Annotated[str | None, Query(pattern=r"^(es|ar)$")] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    # Stage 3 (Wave 11) — series_id/material_id aceptan UUID o slug del registry.
    division: Annotated[str | None, Query(max_length=64)] = None,
    series_id: Annotated[str | None, Query(max_length=64)] = None,
    material_id: Annotated[str | None, Query(max_length=64)] = None,
    tier_code: Annotated[str | None, Query(max_length=32)] = None,
    _user: User = Depends(require_permissions("products:read")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> FacetsResponse:
    """Devuelve counts por dimensión aplicando todos los filtros activos
    EXCEPTO el de la propia dimensión (refinement no destructivo).

    Performance objetivo: p95 <200ms con índices migration 041 y 5K-50K rows.
    """
    filters = ProductFilters(
        family=family,
        subfamily=subfamily,
        type_=type,
        brand=brand,
        material=material,
        dn=dn,
        pn=pn,
        data_quality=data_quality,
        active=active,
        has_image=has_image,
        lifecycle_status=lifecycle_status,
        translation_status=translation_status,
        translation_lang=translation_lang,
        search=q,
        # Stage 3 (Wave 11)
        division_code=division,
        series_id=series_id,
        material_id=material_id,
        tier_code=tier_code,
    )
    return await compute_facets(session, filters)


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
    return await _build_product_detail(prod, service.session)


@router.get(
    "/{sku}/certificates",
    response_model=list[CertificateResponse],
    summary="Certificados del modelo al que pertenece el SKU",
)
async def get_product_certificates(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CertificateResponse]:
    from sqlalchemy import select as _select
    from app.db.models.certificates import Certificate
    from app.db.models.product import Product as _Prod

    model_id_subq = _select(_Prod.model_id).where(_Prod.sku == sku).scalar_subquery()
    certs = (
        await session.execute(
            _select(Certificate)
            .where(Certificate.model_id == model_id_subq)
            .order_by(Certificate.expires_at.nulls_last(), Certificate.cert_number)
        )
    ).scalars().all()
    return [CertificateResponse.model_validate(c) for c in certs]


@router.get(
    "/{sku}/flow-data",
    response_model=list[ModelFlowDataResponse],
    summary="Coeficientes de flujo Kv/Cv del modelo del SKU",
)
async def get_product_flow_data(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ModelFlowDataResponse]:
    from sqlalchemy import select as _select
    from app.db.models.product_models import ModelFlowData
    from app.db.models.product import Product as _Prod

    model_id_subq = _select(_Prod.model_id).where(_Prod.sku == sku).scalar_subquery()
    rows = (
        await session.execute(
            _select(ModelFlowData)
            .where(ModelFlowData.model_id == model_id_subq)
            .order_by(ModelFlowData.dn_mm)
        )
    ).scalars().all()
    return [ModelFlowDataResponse.model_validate(r) for r in rows]


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
    return await _build_product_detail(prod, service.session)  # type: ignore[possibly-undefined]


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
    return await _build_product_detail(full, service.session)


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
    return await _build_product_detail(full, service.session)


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

    # Hook: reverse image search CLIP indexing (US-RND-01-09).
    # Sólo activo si feature flag reverse_image_search está ON.
    if asset.kind in ("photo", "banner", "mirror_url") and asset.storage_path:
        try:
            from app.services.feature_flags.flag_service import is_reverse_image_search_enabled
            from app.services.image_search.clip_service import get_image_backend

            _db_session = product_service.session  # reuse existing session
            if await is_reverse_image_search_enabled(_db_session):
                _backend = get_image_backend()
                await _backend.index_image(str(sku), asset.storage_path)
        except Exception:  # noqa: BLE001
            # Non-blocking — indexing failure must not break the upload response.
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
    Fase 5 — admite ``owner_type``, ``dn_min``, ``dn_max`` para spare parts.
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
            owner_type=data.owner_type.value,
            dn_min=data.dn_min,
            dn_max=data.dn_max,
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
            "owner_type": item.owner_type.value,
            "dn_min": item.dn_min,
            "dn_max": item.dn_max,
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
    response_model=None,
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
    response_model=None,
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


# ==========================================================================
# Wave 6 — Tech tables (read + manual upsert; importer-driven for PDFs)
# ==========================================================================
from sqlalchemy import select as _sa_select  # noqa: E402

from app.db.models.tech_tables import ProductTechTable  # noqa: E402
from app.schemas.tech_tables import (  # noqa: E402
    ProductTechTableCreate,
    ProductTechTablePatch,
    ProductTechTableResponse,
)


@router.get(
    "/{sku}/tech-tables",
    response_model=list[ProductTechTableResponse],
    summary="Listar tablas técnicas (matrix, dimensions, pressure-temperature)",
)
async def list_tech_tables(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: Annotated[str | None, Query(max_length=32)] = None,
    _user: User = Depends(require_permissions("products:read")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> list[ProductTechTableResponse]:
    stmt = _sa_select(ProductTechTable).where(ProductTechTable.product_sku == sku)
    if kind:
        stmt = stmt.where(ProductTechTable.kind == kind)
    stmt = stmt.order_by(ProductTechTable.kind)
    rows = (await session.execute(stmt)).scalars().all()
    return [ProductTechTableResponse.model_validate(r) for r in rows]


@router.put(
    "/{sku}/tech-tables/{kind}",
    response_model=ProductTechTableResponse,
    summary="Crear/actualizar la tabla técnica de un kind (upsert por (sku,kind))",
)
async def upsert_tech_table(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: Annotated[str, Path(pattern=r"^(materials_matrix|dimensions_by_dn|pressure_temperature)$")],
    data: ProductTechTableCreate,
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ProductTechTableResponse:
    if data.kind != kind:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "kind_mismatch",
                "title": f"path kind={kind!r} does not match body kind={data.kind!r}",
            },
        )
    existing = (
        await session.execute(
            _sa_select(ProductTechTable).where(
                ProductTechTable.product_sku == sku,
                ProductTechTable.kind == kind,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.schema_version = data.schema_version
        existing.source = data.source
        existing.data = data.data
        existing.source_asset_id = data.source_asset_id
        existing.notes = data.notes
        await session.flush()
        return ProductTechTableResponse.model_validate(existing)
    row = ProductTechTable(
        product_sku=sku,
        kind=kind,
        schema_version=data.schema_version,
        source=data.source,
        data=data.data,
        source_asset_id=data.source_asset_id,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    return ProductTechTableResponse.model_validate(row)


@router.delete(
    "/{sku}/tech-tables/{kind}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar una tabla técnica de un kind",
)
async def delete_tech_table(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    kind: Annotated[str, Path(pattern=r"^(materials_matrix|dimensions_by_dn|pressure_temperature)$")],
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> Response:
    existing = (
        await session.execute(
            _sa_select(ProductTechTable).where(
                ProductTechTable.product_sku == sku,
                ProductTechTable.kind == kind,
            )
        )
    ).scalar_one_or_none()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "tech_table_not_found",
                "title": f"tech-table kind={kind!r} not found for sku={sku!r}",
            },
        )
    await session.delete(existing)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# M1-01 — Product Releases (por mercado)
# =============================================================================
from sqlalchemy import select as _sa_select2  # noqa: E402
from app.db.models.product import ProductRelease, ProductUomConversion  # noqa: E402


def _assert_product_exists(product: Any, sku: str) -> None:
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "product_not_found", "title": f"Product {sku!r} not found"},
        )


@router.get(
    "/{sku}/releases",
    response_model=list[ProductReleaseResponse],
    summary="Listar releases de un producto por mercado (M1-01)",
)
async def list_releases(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> list[ProductRelease]:
    rows = (
        await session.execute(
            _sa_select2(ProductRelease).where(ProductRelease.product_sku == sku)
        )
    ).scalars().all()
    return list(rows)


@router.post(
    "/{sku}/releases",
    response_model=ProductReleaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear release de un producto para un mercado (M1-01)",
)
async def create_release(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductReleaseCreate,
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ProductRelease:
    from sqlalchemy import select as _sel
    product = (
        await session.execute(_sel(Product).where(Product.sku == sku))
    ).scalar_one_or_none()
    _assert_product_exists(product, sku)

    existing = (
        await session.execute(
            _sa_select2(ProductRelease).where(
                ProductRelease.product_sku == sku,
                ProductRelease.market_code == data.market_code,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "release_exists",
                "title": f"Release for market {data.market_code!r} already exists for sku={sku!r}",
            },
        )

    release = ProductRelease(
        product_sku=sku,
        created_by=_user.id,
        **data.model_dump(),
    )
    session.add(release)
    await session.flush()
    await session.refresh(release)
    return release


@router.patch(
    "/{sku}/releases/{market_code}",
    response_model=ProductReleaseResponse,
    summary="Actualizar datos de un release por mercado (M1-01)",
)
async def patch_release(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    market_code: Annotated[str, Path(min_length=2, max_length=10)],
    data: ProductReleasePatch,
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ProductRelease:
    release = (
        await session.execute(
            _sa_select2(ProductRelease).where(
                ProductRelease.product_sku == sku,
                ProductRelease.market_code == market_code.upper(),
            )
        )
    ).scalar_one_or_none()
    if not release:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "release_not_found",
                "title": f"Release for market {market_code!r} not found for sku={sku!r}",
            },
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(release, field, value)
    await session.flush()
    await session.refresh(release)
    return release


@router.post(
    "/{sku}/releases/{market_code}/activate",
    response_model=ProductReleaseResponse,
    summary="Activar release de un producto en un mercado (M1-01)",
)
async def activate_release(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    market_code: Annotated[str, Path(min_length=2, max_length=10)],
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ProductRelease:
    from datetime import datetime, timezone

    release = (
        await session.execute(
            _sa_select2(ProductRelease).where(
                ProductRelease.product_sku == sku,
                ProductRelease.market_code == market_code.upper(),
            )
        )
    ).scalar_one_or_none()
    if not release:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "release_not_found",
                "title": f"Release for market {market_code!r} not found for sku={sku!r}",
            },
        )
    release.is_active = True
    release.status = "active"
    release.released_at = datetime.now(timezone.utc)
    release.released_by = _user.id
    await session.flush()
    await session.refresh(release)
    return release


@router.post(
    "/{sku}/releases/{market_code}/deactivate",
    response_model=ProductReleaseResponse,
    summary="Desactivar release de un producto en un mercado (M1-01)",
)
async def deactivate_release(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    market_code: Annotated[str, Path(min_length=2, max_length=10)],
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ProductRelease:
    release = (
        await session.execute(
            _sa_select2(ProductRelease).where(
                ProductRelease.product_sku == sku,
                ProductRelease.market_code == market_code.upper(),
            )
        )
    ).scalar_one_or_none()
    if not release:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "release_not_found",
                "title": f"Release for market {market_code!r} not found for sku={sku!r}",
            },
        )
    release.is_active = False
    release.status = "suspended"
    await session.flush()
    await session.refresh(release)
    return release


# =============================================================================
# M1-04 — Product UoM Conversions
# =============================================================================


@router.get(
    "/{sku}/uom-conversions",
    response_model=list[ProductUomConversionResponse],
    summary="Listar conversiones UoM de un producto (M1-04)",
)
async def list_uom_conversions(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: User = Depends(require_permissions("products:read")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> list[ProductUomConversion]:
    rows = (
        await session.execute(
            _sa_select2(ProductUomConversion).where(
                ProductUomConversion.product_sku == sku
            )
        )
    ).scalars().all()
    return list(rows)


@router.post(
    "/{sku}/uom-conversions",
    response_model=ProductUomConversionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agregar conversión UoM a un producto (M1-04)",
)
async def create_uom_conversion(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    data: ProductUomConversionCreate,
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ProductUomConversion:
    from sqlalchemy import select as _sel2
    product = (
        await session.execute(_sel2(Product).where(Product.sku == sku))
    ).scalar_one_or_none()
    _assert_product_exists(product, sku)

    existing = (
        await session.execute(
            _sa_select2(ProductUomConversion).where(
                ProductUomConversion.product_sku == sku,
                ProductUomConversion.uom_from == data.uom_from,
                ProductUomConversion.uom_to == data.uom_to,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "uom_conversion_exists",
                "title": f"Conversion {data.uom_from}→{data.uom_to} already exists for sku={sku!r}",
            },
        )

    row = ProductUomConversion(product_sku=sku, **data.model_dump())
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


@router.delete(
    "/{sku}/uom-conversions/{uom_from}/{uom_to}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Eliminar conversión UoM de un producto (M1-04)",
)
async def delete_uom_conversion(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    uom_from: Annotated[str, Path(min_length=1, max_length=10)],
    uom_to: Annotated[str, Path(min_length=1, max_length=10)],
    _user: User = Depends(require_permissions("products:write")),
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> Response:
    row = (
        await session.execute(
            _sa_select2(ProductUomConversion).where(
                ProductUomConversion.product_sku == sku,
                ProductUomConversion.uom_from == uom_from,
                ProductUomConversion.uom_to == uom_to,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "uom_conversion_not_found",
                "title": f"Conversion {uom_from}→{uom_to} not found for sku={sku!r}",
            },
        )
    await session.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================================================
# Bore Dimensions — mig 099 — dimensiones por norma
# ==========================================================================
@router.get(
    "/{sku}/bore-dimensions",
    response_model=list[BoreDimensionRead],
    summary="Listar dimensiones por norma de un producto (EN 558, ASME B16.10, etc.)",
    responses={404: {"model": ProblemDetails}},
)
async def list_bore_dimensions(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    repo: Annotated[ProductBoreDimensionRepository, Depends(get_bore_dimension_repo)],
    service: Annotated[ProductService, Depends(get_product_service)],
) -> list[BoreDimensionRead]:
    prod = await service.get_product_by_id(sku)
    if prod is None:
        raise HTTPException(status_code=404, detail={"code": "product_not_found", "title": f"SKU {sku!r} no encontrado"})
    rows = await repo.list_for_sku(sku)
    return [BoreDimensionRead.model_validate(r) for r in rows]


# ==========================================================================
# Datasheets — fichas técnicas y documentos asociados a un SKU
# ==========================================================================
class _DatasheetSummary(BaseModel):
    id: str
    kind: str
    storage_path: str
    signed_url: str
    signed_url_expires_at: str
    original_filename: str
    file_size_bytes: int | None = None
    page_count: int | None = None
    uploaded_at: str
    uploaded_by: str | None = None


@router.get(
    "/{sku}/datasheets",
    response_model=list[_DatasheetSummary],
    summary="Listar datasheets asociados a un SKU via asset_links (role=ficha_pdf)",
    responses={404: {"model": ProblemDetails}},
)
async def list_datasheets(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[_DatasheetSummary]:
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415
    from posixpath import basename  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415

    from app.db.models.asset_links import AssetLink  # noqa: PLC0415
    from app.db.models.documents import Document  # noqa: PLC0415
    from app.db.models.product import ProductAsset  # noqa: PLC0415
    from app.services.storage import create_signed_url  # noqa: PLC0415

    links_result = await session.execute(
        select(AssetLink).where(
            AssetLink.owner_type == "product",
            AssetLink.owner_id == sku,
            AssetLink.role == "ficha_pdf",
        )
    )
    links = links_result.scalars().all()
    if not links:
        return []

    asset_ids = [lnk.asset_id for lnk in links]

    assets_result = await session.execute(
        select(ProductAsset).where(ProductAsset.id.in_(asset_ids))
    )
    assets_by_id = {a.id: a for a in assets_result.scalars().all()}

    docs_result = await session.execute(
        select(Document).where(Document.asset_id.in_(asset_ids))
    )
    docs_by_asset_id = {d.asset_id: d for d in docs_result.scalars().all()}

    _TTL = 3600
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=_TTL)).isoformat()

    summaries: list[_DatasheetSummary] = []
    for asset_id in asset_ids:
        asset = assets_by_id.get(asset_id)
        if asset is None:
            continue
        doc = docs_by_asset_id.get(asset_id)

        raw_type = doc.type if doc else "ficha_tecnica"
        if raw_type == "manual":
            kind = "manual"
        elif raw_type == "ficha_tecnica":
            kind = "ficha_tecnica"
        else:
            kind = "compliance"

        try:
            signed = create_signed_url(asset.storage_path, ttl_seconds=_TTL, bucket=asset.bucket)
            signed_url = signed["signed_url"]
        except Exception:
            signed_url = ""

        summaries.append(
            _DatasheetSummary(
                id=str(doc.id) if doc else str(asset.id),
                kind=kind,
                storage_path=asset.storage_path,
                signed_url=signed_url,
                signed_url_expires_at=expires_at,
                original_filename=basename(asset.storage_path),
                file_size_bytes=asset.bytes_size,
                page_count=(asset.asset_meta or {}).get("page_count"),
                uploaded_at=asset.created_at.isoformat(),
                uploaded_by=None,
            )
        )

    return summaries
