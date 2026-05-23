"""Compara campos extraídos del PDF con los valores actuales del producto en DB."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.db.models.product import Product
from app.schemas.ficha_enrich import FichaExtractionResult, FieldDiff

_SCALAR_FIELD_MAP: dict[str, str] = {
    "family": "family",
    "subfamily": "subfamily",
    "type": "type",
    "material": "material",
    "dn": "dn",
    "pn": "pn",
    "connection": "connection",
    "brand": "brand",
    "weight": "weight",
    "weight_unit": "weight_unit",
    "temp_min_c": "temp_min_c",
    "temp_max_c": "temp_max_c",
    "pressure_max_bar": "pressure_max_bar",
    "size": "size",
}


class FichaEnrichmentDiffer:
    """Genera lista de FieldDiff comparando extracción vs. Product ORM."""

    def compute(self, product: Product, extraction: FichaExtractionResult) -> list[FieldDiff]:
        diffs: list[FieldDiff] = []
        scalars_dict = extraction.scalars.model_dump(exclude_none=True)

        for extracted_field, model_attr in _SCALAR_FIELD_MAP.items():
            if extracted_field not in scalars_dict:
                continue
            extracted_val = scalars_dict[extracted_field]
            current_val = getattr(product, model_attr, None)
            if isinstance(current_val, Decimal):
                current_val = float(current_val)
            has_change = _values_differ(current_val, extracted_val)
            diffs.append(
                FieldDiff(
                    field_name=extracted_field,
                    current_value=current_val,
                    extracted_value=extracted_val,
                    has_change=has_change,
                )
            )

        # specs JSONB diff — como bloque
        specs_extracted = _specs_to_dict(extraction)
        if specs_extracted:
            current_specs = dict(product.specs or {})
            merged = {**current_specs, **specs_extracted}
            has_change = any(
                _values_differ(current_specs.get(k), v) for k, v in specs_extracted.items()
            )
            diffs.append(
                FieldDiff(
                    field_name="specs",
                    current_value=current_specs,
                    extracted_value=merged,
                    has_change=has_change,
                )
            )

        # materials — como bloque
        if extraction.materials:
            diffs.append(
                FieldDiff(
                    field_name="materials",
                    current_value=None,
                    extracted_value=[m.model_dump() for m in extraction.materials],
                    has_change=True,
                )
            )

        # dimensions — como bloque
        if extraction.dimensions:
            diffs.append(
                FieldDiff(
                    field_name="dimensions_by_dn",
                    current_value=None,
                    extracted_value=[d.model_dump() for d in extraction.dimensions],
                    has_change=True,
                )
            )

        # translations — como bloque
        if extraction.translations:
            diffs.append(
                FieldDiff(
                    field_name="translations",
                    current_value=None,
                    extracted_value=[t.model_dump() for t in extraction.translations],
                    has_change=True,
                )
            )

        # pt_curve_points — como bloque
        if extraction.pt_curve_points:
            diffs.append(
                FieldDiff(
                    field_name="pt_curve_points",
                    current_value=None,
                    extracted_value=extraction.pt_curve_points,
                    has_change=True,
                )
            )

        # extracted_assets — como bloque
        if extraction.extracted_assets:
            diffs.append(
                FieldDiff(
                    field_name="assets",
                    current_value=None,
                    extracted_value=[a.model_dump() for a in extraction.extracted_assets],
                    has_change=True,
                )
            )

        return diffs

    def compute_batch(
        self,
        products: list,  # list[Product]
        extraction: FichaExtractionResult,
    ) -> list:  # list[SkuDiffResult]
        from app.schemas.ficha_enrich import SkuDiffResult

        return [SkuDiffResult(sku=p.sku, diffs=self.compute(p, extraction)) for p in products]


def _values_differ(current: Any, extracted: Any) -> bool:
    if current is None and extracted is None:
        return False
    if current is None or extracted is None:
        return True
    if isinstance(current, (float, int)) or isinstance(extracted, (float, int)):
        try:
            return abs(float(current) - float(extracted)) > 0.001
        except (TypeError, ValueError):
            pass
    return str(current).strip() != str(extracted).strip()


def _specs_to_dict(extraction: FichaExtractionResult) -> dict[str, Any]:
    out: dict[str, Any] = {}
    s = extraction.specs
    if s.seat_material:
        out["seat_material"] = s.seat_material
    if s.seal_material:
        out["seal_material"] = s.seal_material
    if s.stem_material:
        out["stem_material"] = s.stem_material
    if s.standards:
        out["standards"] = s.standards
    if s.certifications:
        out["certifications"] = s.certifications
    if s.no_frost is not None:
        out["no_frost"] = s.no_frost
    if s.actuation_type:
        out["actuation_type"] = s.actuation_type
    if s.bore_type:
        out["bore_type"] = s.bore_type
    if s.end_connection_gender:
        out["end_connection_gender"] = s.end_connection_gender
    if s.inlet_connection:
        out["inlet_connection"] = s.inlet_connection
    if s.outlet_connection:
        out["outlet_connection"] = s.outlet_connection
    if s.extra:
        out.update(s.extra)
    return out


__all__ = ["FichaEnrichmentDiffer", "_specs_to_dict"]
