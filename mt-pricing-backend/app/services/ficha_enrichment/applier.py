"""Aplica los campos extraídos de una ficha técnica al producto en DB."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import delete as _sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.ficha_enrich import FichaEnrichApplyRequest, SkuApplyResult
from app.services.ficha_enrichment.differ import _specs_to_dict

logger = logging.getLogger(__name__)

_PATCHABLE_SCALAR_FIELDS = {
    "family",
    "subfamily",
    "type",
    "material",
    "dn",
    "pn",
    "connection",
    "brand",
    "weight",
    "weight_unit",
    "temp_min_c",
    "temp_max_c",
    "pressure_max_bar",
}


class FichaEnrichmentApplier:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply(
        self,
        sku: str,
        request: FichaEnrichApplyRequest,
        actor: Any,  # User ORM object — has .id
        pdf_bytes: bytes | None = None,
    ) -> SkuApplyResult:
        applied: list[str] = []
        skipped: list[str] = []
        warnings: list[str] = []

        product = await self._load_product(sku)
        if product is None:
            warnings.append(f"product_not_found: {sku}")
            return SkuApplyResult(
                sku=sku,
                applied_fields=[],
                skipped_fields=[],
                warnings=warnings,
            )

        # --- scalars ---
        if request.apply_scalars:
            scalars_dict = request.extraction.scalars.model_dump(exclude_none=True)
            allowed = (
                set(request.selected_scalar_fields)
                if request.selected_scalar_fields
                else _PATCHABLE_SCALAR_FIELDS
            )
            for field, value in scalars_dict.items():
                if field not in _PATCHABLE_SCALAR_FIELDS:
                    continue
                if field not in allowed:
                    skipped.append(field)
                    continue
                locked = getattr(product, "manual_locked_fields", []) or []
                if field in locked:
                    skipped.append(f"{field}(locked)")
                    continue
                try:
                    setattr(product, field, value)
                    applied.append(field)
                except Exception as exc:
                    warnings.append(f"{field}: {exc}")

        # Derive size from dn — always single canonical value per SKU.
        # If dn was not set by scalar extraction, fall back to the last 3 digits
        # of the SKU (SKU format: SSSS + DN zero-padded to 3 digits, e.g. 4097015 → DN15).
        if request.apply_scalars:
            from app.services.ficha_enrichment.series_resolver import dn_to_size

            effective_dn = product.dn
            if not effective_dn:
                try:
                    effective_dn = int(sku[-3:]) or None
                    if effective_dn:
                        product.dn = str(effective_dn)  # DB column is VARCHAR
                        applied.append("dn")
                except (ValueError, IndexError):
                    pass
            if effective_dn:
                derived = dn_to_size(effective_dn)
                if derived:
                    product.size = derived
                    if "size" not in applied:
                        applied.append("size")

        # --- specs JSONB merge ---
        if request.apply_specs:
            specs_patch = _specs_to_dict(request.extraction)
            if specs_patch:
                merged = {**(product.specs or {}), **specs_patch}
                product.specs = merged
                applied.append("specs")

        await self._session.flush()

        # --- materials ---
        if request.apply_materials and request.extraction.materials:
            try:
                async with self._session.begin_nested():
                    await self._replace_materials(sku, request.extraction.materials)
                applied.append("materials")
            except Exception as exc:
                logger.warning("materials apply failed sku=%s err=%s", sku, exc)
                warnings.append(f"materials: {exc}")

        # --- dimensions tech-table ---
        if request.apply_dimensions and request.extraction.dimensions:
            try:
                async with self._session.begin_nested():
                    await self._upsert_dimensions_table(sku, request.extraction.dimensions)
                applied.append("dimensions_by_dn")
            except Exception as exc:
                logger.warning("dimensions apply failed sku=%s err=%s", sku, exc)
                warnings.append(f"dimensions_by_dn: {exc}")

        # --- translations ---
        if request.apply_translations and request.extraction.translations:
            try:
                async with self._session.begin_nested():
                    await self._upsert_translations(sku, request.extraction.translations, actor)
                applied.append("translations")
            except Exception as exc:
                logger.warning("translations apply failed sku=%s err=%s", sku, exc)
                warnings.append(f"translations: {exc}")

        # --- P/T curve ---
        if request.apply_pt_curve and request.extraction.pt_curve_points:
            try:
                async with self._session.begin_nested():
                    await self._upsert_pt_curve(sku, request.extraction.pt_curve_points)
                applied.append(f"pt_curve({len(request.extraction.pt_curve_points)} pts)")
            except Exception as exc:
                logger.warning("pt_curve apply failed sku=%s err=%s", sku, exc)
                warnings.append(f"pt_curve: {exc}")

        # --- assets (PNG pages) ---
        if request.apply_assets and request.extraction.extracted_assets and pdf_bytes:
            try:
                uploaded = await self._upload_page_assets(
                    sku, pdf_bytes, request.extraction.extracted_assets, actor
                )
                if uploaded:
                    applied.append(f"assets({len(uploaded)})")
            except Exception as exc:
                logger.warning("assets apply failed sku=%s err=%s", sku, exc)
                warnings.append(f"assets: {exc}")

        return SkuApplyResult(
            sku=sku,
            applied_fields=applied,
            skipped_fields=skipped,
            warnings=warnings,
        )

    async def _load_product(self, sku: str) -> Any:
        from app.db.models.product import Product  # noqa: I001
        from sqlalchemy.orm import raiseload

        result = await self._session.execute(
            select(Product).where(Product.sku == sku).options(raiseload("*"))
        )
        return result.scalar_one_or_none()

    _VALID_COMPONENT_KINDS = frozenset(
        {
            "body",
            "closure",
            "seat",
            "gasket",
            "screen",
            "actuator_housing",
            "stem",
            "handle",
            # Extended component kinds (migration 20260527_159)
            "nut",
            "packing",
            "bonnet",
            "insert",
            "spring",
            "washer",
            "o_ring",
            "cap",
            "other",
        }
    )

    async def _replace_materials(self, sku: str, materials: list[Any]) -> None:
        # ProductMaterial in components.py — PK: (product_sku, component, position)
        # Columns: product_sku, component, position, material, observations
        from app.db.models.components import ProductMaterial

        await self._session.execute(
            _sa_delete(ProductMaterial).where(ProductMaterial.product_sku == sku)
        )
        # Product.materials uses lazy="selectin", so _load_product already populated
        # the identity map with these rows. Core DELETE removes them from DB but not
        # from the map — expunge them so subsequent session.add() doesn't conflict.
        stale = [
            obj
            for obj in self._session.identity_map.values()
            if isinstance(obj, ProductMaterial) and obj.product_sku == sku
        ]
        for obj in stale:
            self._session.expunge(obj)

        # Deduplicate by (component, position) — LLM sometimes returns duplicates
        seen: dict[tuple[str, int], Any] = {}
        for m in materials:
            component = m.component if m.component in self._VALID_COMPONENT_KINDS else "other"
            seen[(component, m.position)] = m
        for (component, position), m in seen.items():
            self._session.add(
                ProductMaterial(
                    product_sku=sku,
                    component=component,
                    position=position,
                    material=m.material,
                    observations=m.observations,
                    material_grade=getattr(m, "material_grade", None),
                    material_standard=getattr(m, "material_standard", None),
                    surface_treatment=getattr(m, "surface_treatment", None),
                )
            )
        await self._session.flush()

    async def _upsert_dimensions_table(self, sku: str, dimensions: list[Any]) -> None:
        from app.db.models.tech_tables import ProductTechTable

        data_payload: dict[str, Any] = {
            "rows": [{"dn_label": d.dn_label, "values": d.flat_values()} for d in dimensions]
        }
        existing = (
            await self._session.execute(
                select(ProductTechTable).where(
                    ProductTechTable.product_sku == sku,
                    ProductTechTable.kind == "dimensions_by_dn",
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.data = data_payload
            existing.source = "imported_pdf"
        else:
            self._session.add(
                ProductTechTable(
                    product_sku=sku,
                    kind="dimensions_by_dn",
                    source="imported_pdf",
                    data=data_payload,
                )
            )
        await self._session.flush()

    async def _upsert_translations(self, sku: str, translations: list[Any], actor: Any) -> None:
        # ProductTranslation columns: sku, lang, name, description, marketing_copy,
        # status, translated_by (UUID FK to users.id), translated_at, etc.
        from app.db.models.product import ProductTranslation

        existing_map = {
            row.lang: row
            for row in (
                await self._session.execute(
                    select(ProductTranslation).where(ProductTranslation.sku == sku)
                )
            )
            .scalars()
            .all()
        }
        for t in translations:
            if not t.name and not t.description:
                continue
            existing = existing_map.get(t.lang)
            if existing:
                if t.name:
                    existing.name = t.name
                if t.description:
                    existing.description = t.description
            else:
                self._session.add(
                    ProductTranslation(
                        sku=sku,
                        lang=t.lang,
                        name=t.name or "",
                        description=t.description,
                        status="draft",
                        translated_by=actor.id,
                    )
                )
        await self._session.flush()

    async def _upsert_pt_curve(self, sku: str, points: list[dict[str, float]]) -> None:
        # PressureTemperaturePoint columns: product_sku, temperature_c,
        # pressure_max_bar, order_index (also: series_variant_code, condition_en)
        from app.db.models.dimensions import PressureTemperaturePoint

        existing = (
            (
                await self._session.execute(
                    select(PressureTemperaturePoint).where(
                        PressureTemperaturePoint.product_sku == sku
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in existing:
            await self._session.delete(row)
        await self._session.flush()
        for order, pt in enumerate(points):
            self._session.add(
                PressureTemperaturePoint(
                    product_sku=sku,
                    temperature_c=pt["temperature_c"],
                    pressure_max_bar=pt["pressure_max_bar"],
                    order_index=order,
                )
            )
        await self._session.flush()

    async def _upload_page_assets(
        self,
        sku: str,
        pdf_bytes: bytes,
        assets: list[Any],
        actor: Any,
    ) -> list[str]:
        # ProductAsset columns: sku, kind, bucket, storage_path, mime_type,
        # bytes_size, hash_sha256, caption, status, created_by (UUID)
        # kind CHECK: photo|banner|datasheet_pdf|exploded_3d|section_drawing|
        #             dimension_drawing|certificate_pdf|video_link|external_url|mirror_url
        from app.db.models.product import ProductAsset
        from app.services.importer_datasheets.vision_extractor import _render_pdf_pages

        pngs = _render_pdf_pages(pdf_bytes, max_pages=20, resolution=150)
        uploaded: list[str] = []

        for asset_meta in assets:
            idx = asset_meta.page_index
            if idx >= len(pngs):
                continue
            png = pngs[idx]
            sha = hashlib.sha256(png).hexdigest()[:16]
            storage_path = f"datasheets/{sku}/{asset_meta.asset_kind}_p{idx}_{sha}.png"

            try:
                from supabase import create_client

                from app.core.config import settings

                sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                sb.storage.from_("product-images").upload(
                    path=storage_path,
                    file=png,
                    file_options={"content-type": "image/png", "upsert": "true"},
                )
            except Exception as exc:
                logger.warning("asset_upload failed path=%s err=%s", storage_path, exc)
                continue

            try:
                row = ProductAsset(
                    sku=sku,
                    kind=asset_meta.asset_kind,
                    bucket="product-images",
                    storage_path=storage_path,
                    mime_type="image/png",
                    bytes_size=len(png),
                    hash_sha256=hashlib.sha256(png).hexdigest(),
                    caption=asset_meta.description or None,
                    status="active",
                    created_by=actor.id,
                )
                self._session.add(row)
                uploaded.append(storage_path)
            except Exception as exc:
                logger.warning("ProductAsset create failed: %s", exc)

        await self._session.flush()
        return uploaded


__all__ = ["FichaEnrichmentApplier"]
