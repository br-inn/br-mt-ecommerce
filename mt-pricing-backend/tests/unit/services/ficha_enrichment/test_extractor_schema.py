"""Verify _TOOL_SCHEMA contains required new fields (no API call)."""

from app.services.ficha_enrichment.extractor import _TOOL_SCHEMA


def test_materials_has_grade_fields():
    materials_items = _TOOL_SCHEMA["input_schema"]["properties"]["materials"]["items"]
    props = materials_items["properties"]
    assert "material_grade" in props
    assert "material_standard" in props
    assert "surface_treatment" in props


def test_dimensions_has_secondary_dn():
    dim_items = _TOOL_SCHEMA["input_schema"]["properties"]["dimensions"]["items"]
    props = dim_items["properties"]
    assert "dn_secondary_label" in props


def test_certificates_field_exists():
    props = _TOOL_SCHEMA["input_schema"]["properties"]
    assert "certificates" in props
    cert_items = props["certificates"]["items"]["properties"]
    assert "certification_code" in cert_items
    assert "cert_number" in cert_items
    assert "expires_at" in cert_items


def test_flow_data_field_exists():
    props = _TOOL_SCHEMA["input_schema"]["properties"]
    assert "flow_data" in props
    fd_items = props["flow_data"]["items"]["properties"]
    assert "dn_label" in fd_items
    assert "kv" in fd_items
    assert "mesh_mm" in fd_items
