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
    """
    Sube el PDF a Supabase Storage, crea Document (type=ficha_tecnica) y
    asset_links para cada SKU de la serie. Devuelve el document_id (UUID str) o None.
    """
    if not skus or not pdf_bytes:
        return None

    # Verificar qué SKUs existen (ProductAsset.sku es FK NOT NULL)
    result = await session.execute(
        select(Product.sku).where(Product.sku.in_(skus))
    )
    existing_skus = [row[0] for row in result.fetchall()]
    if not existing_skus:
        logger.warning("document_saver: ningún SKU de la serie existe en DB, omitiendo document save")
        return None

    anchor_sku = existing_skus[0]

    try:
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not supabase_key:
            logger.warning("document_saver: Supabase credentials no configuradas, omitiendo")
            return None

        from supabase import create_client  # noqa: PLC0415
        client = create_client(supabase_url, supabase_key)
        storage_path = f"{_PDF_PATH_PREFIX}/{filename}"

        client.storage.from_(_PDF_BUCKET).upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )

    except Exception as exc:
        logger.warning("document_saver: upload a Supabase Storage falló: %s", exc)
        return None

    try:
        storage_path = f"{_PDF_PATH_PREFIX}/{filename}"

        asset = ProductAsset(
            sku=anchor_sku,
            kind="datasheet_pdf",
            bucket=_PDF_BUCKET,
            storage_path=storage_path,
            mime_type="application/pdf",
        )
        session.add(asset)
        await session.flush()

        code = f"MTFT_{series}"
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

        for sku in existing_skus:
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
