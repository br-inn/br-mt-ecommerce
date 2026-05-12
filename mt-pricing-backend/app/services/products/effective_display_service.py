"""Effective display service — Wave 11 Stage 3.

Calcula la unión efectiva de tags y certificaciones para un producto:

- ``tags``: dedupe de ``products.tags`` ∪ ``series.features_tags``.
- ``certifications``: dedupe por ``code`` de ``series.series_certifications`` (defaults
  por serie) ∪ ``products.product_certifications`` (overrides específicos del SKU).

Los datos de la serie se cargan via ``selectinload`` para evitar lazy-load.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.product import Product
from app.db.models.vocabularies import Series, SeriesCertification
from app.services.vocabularies.vocabulary_service import VocabularyDomainError


class EffectiveDisplayService:
    """Compone tags + certifications efectivos (serie defaults + product overrides)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def compute(self, sku: str) -> dict[str, Any]:
        """Devuelve ``{"tags": [...], "certifications": [...]}`` para el SKU.

        Raises:
            VocabularyDomainError(404): si el SKU no existe.
        """
        stmt = select(Product).where(Product.sku == sku)
        result = await self.session.execute(stmt)
        product = result.scalar_one_or_none()
        if product is None:
            raise VocabularyDomainError(
                f"Product '{sku}' not found",
                code="product_not_found",
                status_code=404,
            )

        # Cargar certificaciones desde product_certifications (cert eager)
        # Re-fetch con eager de la cert para evitar lazy-load.
        from app.db.models.vocabularies import ProductCertification

        pc_stmt = (
            select(ProductCertification)
            .where(ProductCertification.product_sku == sku)
            .options(selectinload(ProductCertification.certification))
        )
        pc_rows = (await self.session.execute(pc_stmt)).scalars().all()

        # Cargar series defaults (si aplica)
        series_certs: list[Any] = []
        series_feature_tags: list[str] = []
        if product.series_id is not None:
            s_stmt = (
                select(Series)
                .where(Series.id == product.series_id)
                .options(
                    selectinload(Series.series_certifications).selectinload(
                        SeriesCertification.certification
                    ),
                )
            )
            series = (await self.session.execute(s_stmt)).scalar_one_or_none()
            if series is not None:
                series_feature_tags = list(series.features_tags or [])
                series_certs = [sc.certification for sc in series.series_certifications]

        # ---- Tags: Fase B (mig 065) — products.tags eliminado; sólo series feature_tags ----
        seen_tags: set[str] = set()
        merged_tags: list[str] = []
        for t in series_feature_tags:
            if t and t not in seen_tags:
                seen_tags.add(t)
                merged_tags.append(t)

        # ---- Certifications: dedupe by code (product overrides win, series fills) ----
        seen_codes: set[str] = set()
        merged_certs: list[dict[str, Any]] = []
        # Product-specific first (mayor especificidad)
        for pc in pc_rows:
            cert = pc.certification
            if cert is None or cert.code in seen_codes:
                continue
            seen_codes.add(cert.code)
            merged_certs.append(
                {
                    "id": cert.id,
                    "code": cert.code,
                    "name": cert.name,
                    "issued_by": cert.issued_by,
                    "scope": cert.scope,
                    "logo_url": cert.logo_url,
                }
            )
        # Series defaults complementan
        for cert in series_certs:
            if cert is None or cert.code in seen_codes:
                continue
            seen_codes.add(cert.code)
            merged_certs.append(
                {
                    "id": cert.id,
                    "code": cert.code,
                    "name": cert.name,
                    "issued_by": cert.issued_by,
                    "scope": cert.scope,
                    "logo_url": cert.logo_url,
                }
            )

        return {"tags": merged_tags, "certifications": merged_certs}
