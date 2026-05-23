# mt-pricing-backend/app/services/ficha_enrichment/document_saver.py
"""Guarda el PDF de la ficha técnica como Document controlado + asset_links a los SKUs."""

from __future__ import annotations

import logging
import os
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.asset_links import AssetLink
from app.db.models.documents import Document
from app.db.models.product import Product, ProductAsset

logger = logging.getLogger(__name__)

_PDF_BUCKET = "product-datasheets"
_PDF_PATH_PREFIX = "fichas"


async def save_ficha_document(
    session: AsyncSession,
    pdf_bytes: bytes,
    filename: str,
    series: str,
    skus: list[str],
) -> str | None:
    """Crea Document (type=ficha_tecnica) y asset_links para cada SKU de la serie.

    Si `pdf_bytes` no está vacío, sube el binario a Supabase Storage antes de
    crear los registros. Si está vacío (e.g. re-apply sin re-envío del PDF),
    los registros de metadatos se crean igualmente apuntando al storage_path
    esperado — el binario puede subirse manualmente después.
    """
    if not skus:
        return None

    # Verificar qué SKUs existen (ProductAsset.sku es FK NOT NULL)
    result = await session.execute(select(Product.sku).where(Product.sku.in_(skus)))
    existing_skus = [row[0] for row in result.fetchall()]
    if not existing_skus:
        logger.warning(
            "document_saver: ningún SKU de la serie existe en DB, omitiendo document save"
        )
        return None

    anchor_sku = existing_skus[0]
    storage_path = f"{_PDF_PATH_PREFIX}/{filename}"

    # Subir binario solo si se proporcionaron bytes
    if pdf_bytes:
        try:
            supabase_url = os.environ.get("SUPABASE_URL", "")
            supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
            if supabase_url and supabase_key:
                from supabase import create_client

                client = create_client(supabase_url, supabase_key)
                client.storage.from_(_PDF_BUCKET).upload(
                    path=storage_path,
                    file=pdf_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
        except Exception as exc:
            logger.warning("document_saver: upload a Supabase Storage falló: %s", exc)

    try:
        # Evitar duplicados: si ya existe un asset con este storage_path, reusar
        from sqlalchemy import select as _sel

        existing_asset_r = await session.execute(
            _sel(ProductAsset).where(
                ProductAsset.bucket == _PDF_BUCKET,
                ProductAsset.storage_path == storage_path,
            )
        )
        existing_asset = existing_asset_r.scalar_one_or_none()

        if existing_asset is None:
            asset = ProductAsset(
                sku=anchor_sku,
                kind="datasheet_pdf",
                bucket=_PDF_BUCKET,
                storage_path=storage_path,
                mime_type="application/pdf",
            )
            session.add(asset)
            await session.flush()
        else:
            asset = existing_asset

        code = f"MTFT_{series}"
        existing_doc_r = await session.execute(
            _sel(Document).where(
                Document.code == code,
                Document.version == "1",
                Document.language == "es",
            )
        )
        existing_doc = existing_doc_r.scalar_one_or_none()

        if existing_doc is None:
            doc = Document(
                type="ficha_tecnica",
                code=code,
                version="1",
                language="es",
                asset_id=asset.id,
                issued_at=date.today(),
            )
            session.add(doc)
            await session.flush()
        else:
            doc = existing_doc

        # Crear asset_links solo para SKUs que no los tengan ya
        for sku in existing_skus:
            existing_link_r = await session.execute(
                _sel(AssetLink).where(
                    AssetLink.asset_id == asset.id,
                    AssetLink.owner_type == "product",
                    AssetLink.owner_id == sku,
                    AssetLink.role == "ficha_pdf",
                )
            )
            if existing_link_r.scalar_one_or_none() is None:
                link = AssetLink(
                    asset_id=asset.id,
                    owner_type="product",
                    owner_id=sku,
                    role="ficha_pdf",
                )
                session.add(link)

        await session.flush()
        return str(doc.id)

    except Exception as exc:
        logger.warning("document_saver: error creando Document/AssetLink: %s", exc)
        return None


__all__ = ["save_ficha_document"]
