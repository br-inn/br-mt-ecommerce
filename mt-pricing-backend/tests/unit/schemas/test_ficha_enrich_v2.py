"""Tests for extended ficha_enrich schemas."""
from app.schemas.ficha_enrich import (
    ExtractedMaterial,
    ExtractedDimensionRow,
    ExtractedCertificate,
    ExtractedFlowData,
    FichaExtractionResult,
    ExtractedScalars,
    ExtractedSpecs,
)


def test_extracted_material_has_grade():
    m = ExtractedMaterial(
        component="body",
        material="gunmetal",
        material_grade="EN-GJL-250",
        material_standard="UNE-EN-12165",
        surface_treatment="None",
    )
    assert m.material_grade == "EN-GJL-250"
    assert m.surface_treatment == "None"


def test_extracted_dimension_row_has_secondary():
    row = ExtractedDimensionRow(
        dn_label='1/2"',
        dn_secondary_label='3/8"',
        values={"A_mm": 24},
    )
    assert row.dn_secondary_label == '3/8"'


def test_extracted_certificate():
    cert = ExtractedCertificate(
        certification_code="ACS",
        cert_number="23 ACC LY 482",
        issuer="Carso",
        expires_at="2028-07-11",
    )
    assert cert.certification_code == "ACS"
    assert cert.cert_number == "23 ACC LY 482"


def test_extracted_flow_data():
    fd = ExtractedFlowData(dn_label='1"', kv=18.5, mesh_mm=1.8)
    assert fd.kv == 18.5
    assert fd.mesh_mm == 1.8


def test_ficha_extraction_result_has_certs_and_flow():
    result = FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        certificates=[
            ExtractedCertificate(certification_code="WRAS", cert_number="240908012")
        ],
        flow_data=[
            ExtractedFlowData(dn_label='1"', kv=18.5)
        ],
    )
    assert len(result.certificates) == 1
    assert result.certificates[0].certification_code == "WRAS"
    assert len(result.flow_data) == 1
