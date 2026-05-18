"""Marketplace Listings — validate, export CSV, CRUD, AI generate.

Endpoints:
  GET  /marketplace-listings/{marketplace}/validate  → AmazonValidationReport
  GET  /marketplace-listings/{marketplace}/export    → StreamingResponse (CSV)
  GET  /marketplace-listings/{sku}/{marketplace}     → MarketplaceListingRead
  PUT  /marketplace-listings/{sku}/{marketplace}     → MarketplaceListingRead
  POST /marketplace-listings/{sku}/{marketplace}/generate → MarketplaceListingRead

Route order: fixed-segment routes (/{marketplace}/validate, /{marketplace}/export)
MUST precede variable-segment routes (/{sku}/{marketplace}) to avoid FastAPI
treating "validate"/"export" as a SKU value.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session, require_permissions
from app.db.models.channel_listing import ChannelListing
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.product import Product
from app.db.models.user import User
from app.schemas.marketplace_listing import (
    AmazonFieldError,
    AmazonListingValidation,
    AmazonValidationReport,
    GenerateListingRequest,
    MarketplaceListingRead,
    MarketplaceListingUpsert,
)
from app.services.marketplace_export.amazon_listing_exporter import AmazonListingExporter
from app.services.marketplace_export.listing_generator import AmazonListingGenerator

log = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace-listings", tags=["marketplace-listings"])

# Module-level singletons — instantiated once at import time.
_EXPORTER = AmazonListingExporter()
_GENERATOR = AmazonListingGenerator()

_SUPPORTED_MARKETPLACES = {"amazon_uae"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_amazon_uae(marketplace: str) -> None:
    if marketplace not in _SUPPORTED_MARKETPLACES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_MARKETPLACE",
                "message": f"Marketplace '{marketplace}' is not supported. "
                           f"Supported: {sorted(_SUPPORTED_MARKETPLACES)}",
            },
        )


async def _load_active_products(session: AsyncSession) -> list[Product]:
    """Return all active products with eager-loaded relationships needed by the exporter."""
    result = await session.execute(
        select(Product)
        .where(Product.lifecycle_status == "active")
        .options(
            selectinload(Product.materials),
            selectinload(Product.connections),
            selectinload(Product.tech_tables),
            selectinload(Product.assets),
            selectinload(Product.translations),
        )
    )
    return list(result.scalars().all())


async def _load_mp_listings(
    session: AsyncSession, marketplace: str
) -> dict[str, MarketplaceListing]:
    """Return {product_sku: MarketplaceListing} for the given marketplace."""
    result = await session.execute(
        select(MarketplaceListing).where(MarketplaceListing.marketplace == marketplace)
    )
    return {r.product_sku: r for r in result.scalars().all()}


async def _load_channel_listings(
    session: AsyncSession, marketplace: str
) -> dict[str, ChannelListing]:
    """Return {product_sku: ChannelListing} for channel_code == marketplace."""
    result = await session.execute(
        select(ChannelListing).where(ChannelListing.channel_code == marketplace)
    )
    return {r.product_sku: r for r in result.scalars().all()}


def _build_product_context(product: Product) -> dict:
    """Build the product context dict for the AI listing generator.

    All data comes from the already-loaded product ORM object and its
    eagerly loaded relationships (materials, connections, tech_tables,
    translations, product_certifications).
    """
    body_material = next(
        (
            m for m in (product.materials or [])
            if getattr(m, "component", None) == "body" and getattr(m, "position", 0) == 0
        ),
        None,
    )
    first_conn = next(
        iter(sorted(product.connections or [], key=lambda c: getattr(c, "position", 99))),
        None,
    )
    pt = next(
        (t for t in (product.tech_tables or []) if getattr(t, "kind", "") == "pressure_temperature"),
        None,
    )
    description_en: str = ""
    for t in (product.translations or []):
        if getattr(t, "lang", None) == "en":
            description_en = getattr(t, "description", "") or ""
            break

    # Gather certifications from product_certifications M:N relationship
    certs = getattr(product, "product_certifications", None) or []
    cert_codes = [
        getattr(c, "certification_code", None) or getattr(c, "code", None)
        for c in certs
        if getattr(c, "certification_code", None) or getattr(c, "code", None)
    ]

    return {
        "sku": product.sku,
        "family": product.family,
        "dn": product.dn or "",
        "material": getattr(body_material, "material", None) or product.material or "",
        "connection_type": getattr(first_conn, "connection_type", None) or product.connection or "",
        "pressure_rating": (
            float(pt.data.get("pn")) if pt and isinstance(pt.data, dict) and pt.data.get("pn") is not None else ""
        ),
        "temp_min": (
            float(pt.data.get("temp_min_c")) if pt and isinstance(pt.data, dict) and pt.data.get("temp_min_c") is not None else ""
        ),
        "temp_max": (
            float(pt.data.get("temp_max_c")) if pt and isinstance(pt.data, dict) and pt.data.get("temp_max_c") is not None else ""
        ),
        "certifications": cert_codes,
        "description_en": description_en,
    }


# ---------------------------------------------------------------------------
# 1. GET /{marketplace}/validate
# ---------------------------------------------------------------------------

@router.get(
    "/{marketplace}/validate",
    response_model=AmazonValidationReport,
    operation_id="marketplaceListingsValidate",
)
async def validate_marketplace_listings(
    marketplace: str,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AmazonValidationReport:
    """Validate all active products for export to the given marketplace."""
    _require_amazon_uae(marketplace)

    products = await _load_active_products(session)
    mp_listings = await _load_mp_listings(session, marketplace)
    channel_listings = await _load_channel_listings(session, marketplace)

    validations: list[AmazonListingValidation] = []
    ready_count = 0
    error_count = 0
    draft_count = 0

    for product in products:
        mp_listing = mp_listings.get(product.sku)
        channel_listing = channel_listings.get(product.sku)

        raw_errors, raw_warnings = _EXPORTER.validate(product, mp_listing, channel_listing)

        errors = [AmazonFieldError(**e) for e in raw_errors]
        warnings = [AmazonFieldError(**w) for w in raw_warnings]
        is_ready = len(errors) == 0

        if is_ready:
            ready_count += 1
        else:
            error_count += 1

        # Count as draft if no mp_listing or mp_listing.status == "draft"
        if mp_listing is None or mp_listing.status == "draft":
            draft_count += 1

        validations.append(
            AmazonListingValidation(
                sku=product.sku,
                is_ready=is_ready,
                errors=errors,
                warnings=warnings,
            )
        )

    return AmazonValidationReport(
        total_skus=len(products),
        ready_count=ready_count,
        draft_count=draft_count,
        error_count=error_count,
        listings=validations,
    )


# ---------------------------------------------------------------------------
# 2. GET /{marketplace}/export
# ---------------------------------------------------------------------------

@router.get(
    "/{marketplace}/export",
    operation_id="marketplaceListingsExport",
)
async def export_marketplace_listings(
    marketplace: str,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    only_ready: bool = Query(True, description="Skip SKUs that have validation errors."),
    skus: str | None = Query(None, description="Comma-separated list of SKUs to export. If omitted, all active products are exported."),
) -> StreamingResponse:
    """Export active products to an Amazon flat-file CSV feed.

    Pass `skus` to restrict the export to a specific subset (comma-separated).
    When `skus` is provided `only_ready` defaults to False since the caller made
    an explicit selection.
    """
    _require_amazon_uae(marketplace)

    sku_filter: set[str] | None = None
    if skus:
        sku_filter = {s.strip() for s in skus.split(",") if s.strip()}
        # Explicit selection — honour only_ready as passed, but caller typically sends false
    if sku_filter is not None and only_ready:
        only_ready = False  # respect explicit selection over the default

    products = await _load_active_products(session)
    if sku_filter is not None:
        products = [p for p in products if p.sku in sku_filter]

    mp_listings = await _load_mp_listings(session, marketplace)
    channel_listings = await _load_channel_listings(session, marketplace)

    rows: list[tuple] = []
    skipped = 0

    for product in products:
        mp_listing = mp_listings.get(product.sku)
        channel_listing = channel_listings.get(product.sku)

        if only_ready:
            errors, _ = _EXPORTER.validate(product, mp_listing, channel_listing)
            if errors:
                skipped += 1
                continue

        rows.append((product, mp_listing, channel_listing))

    csv_bytes = _EXPORTER.export_csv(rows)

    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    filename = f"AMAZON_UAE_{date_str}.csv"

    return StreamingResponse(
        content=io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Rows-Exported": str(len(rows)),
            "X-Rows-Skipped": str(skipped),
        },
    )


# ---------------------------------------------------------------------------
# 3. GET /{sku}/{marketplace}
# ---------------------------------------------------------------------------

@router.get(
    "/{sku}/{marketplace}",
    response_model=MarketplaceListingRead,
    operation_id="marketplaceListingsGetOne",
)
async def get_marketplace_listing(
    sku: str,
    marketplace: str,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketplaceListingRead:
    """Get a single marketplace listing by SKU and marketplace."""
    result = await session.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.product_sku == sku,
            MarketplaceListing.marketplace == marketplace,
        )
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "LISTING_NOT_FOUND",
                "message": f"No marketplace listing for SKU '{sku}' on '{marketplace}'.",
            },
        )
    return MarketplaceListingRead.model_validate(listing)


# ---------------------------------------------------------------------------
# 4. PUT /{sku}/{marketplace}
# ---------------------------------------------------------------------------

@router.put(
    "/{sku}/{marketplace}",
    response_model=MarketplaceListingRead,
    operation_id="marketplaceListingsUpsert",
)
async def upsert_marketplace_listing(
    sku: str,
    marketplace: str,
    body: MarketplaceListingUpsert,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketplaceListingRead:
    """Create or update a marketplace listing for a SKU."""
    result = await session.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.product_sku == sku,
            MarketplaceListing.marketplace == marketplace,
        )
    )
    listing = result.scalar_one_or_none()
    now = datetime.now(tz=timezone.utc)

    if listing is None:
        listing = MarketplaceListing(
            product_sku=sku,
            marketplace=marketplace,
            status=body.status,
            listing_title=body.listing_title,
            listing_description=body.listing_description,
            bullet_points=body.bullet_points,
            search_keywords=body.search_keywords,
            extra=body.extra,
            updated_at=now,
        )
        session.add(listing)
    else:
        listing.status = body.status
        listing.listing_title = body.listing_title
        listing.listing_description = body.listing_description
        listing.bullet_points = body.bullet_points
        listing.search_keywords = body.search_keywords
        listing.extra = body.extra
        listing.updated_at = now

    await session.flush()
    await session.refresh(listing)
    return MarketplaceListingRead.model_validate(listing)


# ---------------------------------------------------------------------------
# 5. POST /{sku}/{marketplace}/generate
# ---------------------------------------------------------------------------

@router.post(
    "/{sku}/{marketplace}/generate",
    response_model=MarketplaceListingRead,
    operation_id="marketplaceListingsGenerate",
)
async def generate_marketplace_listing(
    sku: str,
    marketplace: str,
    body: GenerateListingRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketplaceListingRead:
    """Generate Amazon listing content using AI (Claude).

    Returns 409 if the listing already has content and overwrite=False.
    """
    # Load existing listing (if any)
    result = await session.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.product_sku == sku,
            MarketplaceListing.marketplace == marketplace,
        )
    )
    listing = result.scalar_one_or_none()

    # 409 guard — listing already has content and overwrite not requested
    if listing is not None and listing.listing_title and not body.overwrite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "LISTING_ALREADY_EXISTS",
                "message": (
                    f"Listing for SKU '{sku}' on '{marketplace}' already has content. "
                    "Pass overwrite=true to regenerate."
                ),
            },
        )

    # Load the product with relationships needed to build context
    prod_result = await session.execute(
        select(Product)
        .where(Product.sku == sku)
        .options(
            selectinload(Product.materials),
            selectinload(Product.connections),
            selectinload(Product.tech_tables),
            selectinload(Product.assets),
            selectinload(Product.translations),
        )
    )
    product = prod_result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product '{sku}' not found."},
        )

    # Build product context for the generator
    product_context = _build_product_context(product)

    # Call AI generator
    try:
        generated = await _GENERATOR.generate(product_context)
    except Exception as exc:
        log.exception("AI listing generation failed for SKU %s: %s", sku, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "GENERATION_FAILED",
                "message": f"AI generation failed: {exc}",
            },
        ) from exc

    now = datetime.now(tz=timezone.utc)

    if listing is None:
        listing = MarketplaceListing(
            product_sku=sku,
            marketplace=marketplace,
            status="draft",
            listing_title=generated.listing_title,
            listing_description=generated.listing_description,
            bullet_points=generated.bullet_points,
            search_keywords=generated.search_keywords,
            ai_generated_at=now,
            ai_model=generated.ai_model,
            updated_at=now,
        )
        session.add(listing)
    else:
        listing.status = "draft"
        listing.listing_title = generated.listing_title
        listing.listing_description = generated.listing_description
        listing.bullet_points = generated.bullet_points
        listing.search_keywords = generated.search_keywords
        listing.ai_generated_at = now
        listing.ai_model = generated.ai_model
        listing.updated_at = now

    await session.flush()
    await session.refresh(listing)
    return MarketplaceListingRead.model_validate(listing)
