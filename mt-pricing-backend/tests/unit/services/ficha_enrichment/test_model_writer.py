"""Unit tests for model_writer — pure logic, no DB."""

from app.schemas.ficha_enrich import (
    ExtractedDimensionRow,
    ExtractedScalars,
    ExtractedSpecs,
    FichaExtractionResult,
)
from app.services.ficha_enrichment.model_writer import (
    _build_dimensions_dict,
    write_pt_curves_data,
)


def _make_result(**kwargs):
    return FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        **kwargs,
    )


def test_build_dimensions_dict():
    row = ExtractedDimensionRow(
        dn_label="DN15",
        values={"L_mm": 57.0, "H_mm": 72.0},
    )
    result = _build_dimensions_dict(row)
    assert result == {"L_mm": 57.0, "H_mm": 72.0}


def test_build_dimensions_dict_with_secondary():
    row = ExtractedDimensionRow(
        dn_label='1/2"',
        dn_secondary_label='3/8"',
        values={"A_mm": 24.0},
    )
    result = _build_dimensions_dict(row)
    assert result == {"A_mm": 24.0}


def test_write_pt_curves_data_empty():
    result = _make_result()
    tables = write_pt_curves_data(result)
    assert tables == []


def test_write_pt_curves_data_single():
    result = _make_result(
        pt_curve_points=[
            {"temperature_c": 20, "pressure_max_bar": 30},
            {"temperature_c": 120, "pressure_max_bar": 20},
        ]
    )
    tables = write_pt_curves_data(result)
    assert len(tables) == 1
    assert tables[0]["kind"] == "pt_curve"
    assert tables[0]["gasket_material"] is None
    assert len(tables[0]["data"]) == 2
