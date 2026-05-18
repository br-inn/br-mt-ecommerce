"""Writes extracted ficha data to product_models and related tables."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.certificates import Certificate
from app.db.models.product_models import (
    ModelDimensionRow,
    ModelFlowData,
    ModelTechTable,
    ProductModel,
)
from app.db.models.product import Product
from app.schemas.ficha_enrich import (
    ExtractedDimensionRow,
    FichaExtractionResult,
)
from app.services.ficha_enrichment.series_resolver import dn_label_to_int

logger = logging.getLogger(__name__)


def _build_dimensions_dict(row: ExtractedDimensionRow) -> dict[str, Any]:
    return dict(row.values)


def write_pt_curves_data(extraction: FichaExtractionResult) -> list[dict[str, Any]]:
    """Returns list of dicts {kind, gasket_material, data} for ModelTechTable creation."""
    if not extraction.pt_curve_points:
        return []
    return [{"kind": "pt_curve", "gasket_material": None, "data": extraction.pt_curve_points}]


async def upsert_model(
    session: AsyncSession,
    series_prefix: str,
    variant_series: str | None = None,
) -> ProductModel:
    """Find or create ProductModel for series_prefix. Links variant if provided."""
    result = await session.execute(
        select(ProductModel).where(ProductModel.code == series_prefix)
    )
    model = result.scalar_one_or_none()
    if model is None:
        model = ProductModel(code=series_prefix)
        session.add(model)
        await session.flush()

    if variant_series:
        v_result = await session.execute(
            select(ProductModel).where(ProductModel.code == variant_series)
        )
        variant = v_result.scalar_one_or_none()
        if variant is None:
            variant = ProductModel(code=variant_series, variant_of_id=model.id)
            session.add(variant)
            await session.flush()
        elif variant.variant_of_id is None:
            variant.variant_of_id = model.id

    return model


async def write_dimension_rows(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    for row in extraction.dimensions:
        dn = dn_label_to_int(row.dn_label)
        if dn is None:
            logger.warning("model_writer: cannot parse DN from '%s'", row.dn_label)
            continue
        dn_sec = dn_label_to_int(row.dn_secondary_label) if row.dn_secondary_label else None

        existing = await session.execute(
            select(ModelDimensionRow).where(
                ModelDimensionRow.model_id == model.id,
                ModelDimensionRow.dn_mm == dn,
                ModelDimensionRow.dn_secondary_mm == dn_sec,
            )
        )
        dim_row = existing.scalar_one_or_none()
        if dim_row is None:
            dim_row = ModelDimensionRow(
                model_id=model.id,
                dn_mm=dn,
                dn_secondary_mm=dn_sec,
                dimensions=_build_dimensions_dict(row),
                source="ficha_enrichment",
            )
            session.add(dim_row)
        else:
            dim_row.dimensions = _build_dimensions_dict(row)


async def write_flow_data_rows(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    for fd in extraction.flow_data:
        dn = dn_label_to_int(fd.dn_label)
        if dn is None:
            continue
        existing = await session.execute(
            select(ModelFlowData).where(
                ModelFlowData.model_id == model.id,
                ModelFlowData.dn_mm == dn,
                ModelFlowData.mesh_mm == fd.mesh_mm,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = ModelFlowData(
                model_id=model.id,
                dn_mm=dn,
                kv=fd.kv,
                cv=fd.cv,
                mesh_mm=fd.mesh_mm,
            )
            session.add(row)
        else:
            row.kv = fd.kv
            row.cv = fd.cv


async def write_model_tech_tables(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    for table_data in write_pt_curves_data(extraction):
        existing = await session.execute(
            select(ModelTechTable).where(
                ModelTechTable.model_id == model.id,
                ModelTechTable.kind == table_data["kind"],
                ModelTechTable.gasket_material == table_data["gasket_material"],
            )
        )
        tt = existing.scalar_one_or_none()
        if tt is None:
            tt = ModelTechTable(
                model_id=model.id,
                kind=table_data["kind"],
                gasket_material=table_data["gasket_material"],
                data=table_data["data"],
                source="ficha_enrichment",
            )
            session.add(tt)
        else:
            tt.data = table_data["data"]


async def write_certificates(
    session: AsyncSession,
    model: ProductModel,
    extraction: FichaExtractionResult,
) -> None:
    for cert_data in extraction.certificates:
        if not cert_data.cert_number:
            continue
        existing = await session.execute(
            select(Certificate).where(
                Certificate.model_id == model.id,
                Certificate.cert_number == cert_data.cert_number,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        def _parse_date(s: str | None) -> date | None:
            if not s:
                return None
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                return None

        cert = Certificate(
            model_id=model.id,
            cert_number=cert_data.cert_number,
            issuer=cert_data.issuer,
            issued_at=_parse_date(cert_data.issued_at),
            expires_at=_parse_date(cert_data.expires_at),
            signatory_name=cert_data.signatory_name,
            signatory_role=cert_data.signatory_role,
            status="valid",
        )
        session.add(cert)


async def link_products_to_model(
    session: AsyncSession,
    model: ProductModel,
    series_prefix: str,
) -> None:
    await session.execute(
        update(Product)
        .where(
            Product.sku.like(f"{series_prefix}%"),
            Product.model_id.is_(None),
        )
        .values(model_id=model.id)
    )


async def write_model_data(
    session: AsyncSession,
    series_prefix: str,
    extraction: FichaExtractionResult,
    variant_series: str | None = None,
) -> ProductModel:
    """Orchestrates all model-level writes for one series."""
    model = await upsert_model(session, series_prefix, variant_series)
    await write_dimension_rows(session, model, extraction)
    await write_flow_data_rows(session, model, extraction)
    await write_model_tech_tables(session, model, extraction)
    await write_certificates(session, model, extraction)
    await link_products_to_model(session, model, series_prefix)
    return model


__all__ = [
    "write_model_data",
    "upsert_model",
    "write_dimension_rows",
    "write_flow_data_rows",
    "write_model_tech_tables",
    "write_certificates",
    "link_products_to_model",
    "_build_dimensions_dict",
    "write_pt_curves_data",
]
