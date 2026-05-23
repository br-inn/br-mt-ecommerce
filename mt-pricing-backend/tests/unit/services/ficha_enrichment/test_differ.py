from unittest.mock import MagicMock

from app.schemas.ficha_enrich import (
    ExtractedAsset,
    ExtractedMaterial,
    ExtractedScalars,
    ExtractedSpecs,
    FichaExtractionResult,
)
from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer


def _make_product(**kwargs):
    p = MagicMock()
    p.family = "válvulas"
    p.pn = None
    p.temp_min_c = None
    p.temp_max_c = None
    p.material = None
    p.connection = None
    p.brand = None
    p.specs = {}
    p.size = None
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


def test_differ_detects_new_fields():
    product = _make_product()
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(pn="30", temp_min_c=-20, temp_max_c=120),
        specs=ExtractedSpecs(),
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    pn_diff = next(d for d in diffs if d.field_name == "pn")
    assert pn_diff.has_change is True
    assert pn_diff.current_value is None
    assert pn_diff.extracted_value == "30"


def test_differ_no_change_when_same():
    product = _make_product(pn="30")
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(pn="30"),
        specs=ExtractedSpecs(),
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    pn_diff = next(d for d in diffs if d.field_name == "pn")
    assert pn_diff.has_change is False


def test_differ_materials_block():
    product = _make_product()
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        materials=[ExtractedMaterial(component="body", material="brass_cw617n")],
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    mat_diff = next(d for d in diffs if d.field_name == "materials")
    assert mat_diff.has_change is True
    assert mat_diff.extracted_value[0]["component"] == "body"


def test_differ_specs_merged():
    product = _make_product()
    product.specs = {"seat_material": "ptfe"}
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(seal_material="nbr"),
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    specs_diff = next(d for d in diffs if d.field_name == "specs")
    assert specs_diff.has_change is True
    assert specs_diff.extracted_value.get("seal_material") == "nbr"


def test_differ_pt_curve_block():
    product = _make_product()
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        pt_curve_points=[{"temperature_c": 20.0, "pressure_max_bar": 30.0}],
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    pt_diff = next(d for d in diffs if d.field_name == "pt_curve_points")
    assert pt_diff.has_change is True
    assert len(pt_diff.extracted_value) == 1


def test_differ_assets_block():
    product = _make_product()
    extraction = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        extracted_assets=[ExtractedAsset(page_index=1, asset_kind="dimension_drawing")],
        confidence=0.9,
    )
    differ = FichaEnrichmentDiffer()
    diffs = differ.compute(product, extraction)
    asset_diff = next(d for d in diffs if d.field_name == "assets")
    assert asset_diff.has_change is True
