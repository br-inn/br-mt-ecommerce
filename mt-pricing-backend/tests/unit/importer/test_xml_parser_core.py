from __future__ import annotations

from app.services.importer.xml_parser import parse_xml_stream

_NS = "https://mtme-api/schemas/articulos/v1"

_MINIMAL = f"""<?xml version="1.0" encoding="UTF-8"?>
<catalog xmlns="{_NS}">
  <article>
    <sku>MT-V-038</sku>
    <name_en>Brass Ball Valve DN25</name_en>
    <family>ball_valve</family>
    <material>brass</material>
    <dn>25</dn>
    <pn>40</pn>
    <weight>0.42</weight>
    <weight_unit>kg</weight_unit>
    <dimensions><high_mm>62.5</high_mm><wide_mm>48.0</wide_mm></dimensions>
    <packaging><qty_per_box>20</qty_per_box></packaging>
    <specs><materials_body>brass CW617N</materials_body></specs>
  </article>
</catalog>"""


def test_parse_scalars_and_jsonb() -> None:
    result = parse_xml_stream(_MINIMAL.encode("utf-8"))
    assert result.header_ok is True
    assert result.total_data_rows == 1
    row = result.rows[0]
    assert row.sku == "MT-V-038"
    assert row.errors == []
    p = row.payload
    assert p["name_en"] == "Brass Ball Valve DN25"
    assert p["family"] == "ball_valve"
    assert p["dn"] == "25"
    assert p["pn"] == "40"
    assert p["weight"] == "0.42"
    assert p["dimensions"] == {"high_mm": "62.5", "wide_mm": "48.0"}
    assert p["packaging"] == {"qty_per_box": 20}
    assert p["specs"]["materials_body"] == "brass CW617N"


def test_invalid_dn_marks_row_error_not_file() -> None:
    bad = _MINIMAL.replace("<dn>25</dn>", "<dn>99</dn>")
    result = parse_xml_stream(bad.encode("utf-8"))
    assert result.header_ok is True
    assert result.rows[0].errors
    assert any("dn" in e.lower() for e in result.rows[0].errors)


def test_entity_expansion_attack_is_rejected() -> None:
    """defusedxml debe rechazar DTD/entidades (XXE / billion-laughs)."""
    import pytest

    from app.services.importer.xml_parser import XmlParseError

    evil = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;&lol;">]>'
        f'<catalog xmlns="{_NS}"><article><sku>&lol2;</sku>'
        "<name_en>x</name_en><family>f</family></article></catalog>"
    )
    with pytest.raises(XmlParseError):
        parse_xml_stream(evil.encode("utf-8"))


def test_malformed_xml_raises_file_error() -> None:
    import pytest

    from app.services.importer.xml_parser import XmlParseError

    with pytest.raises(XmlParseError):
        parse_xml_stream(b"<catalog><article>")


def test_wrong_root_raises_file_error() -> None:
    import pytest

    from app.services.importer.xml_parser import XmlParseError

    with pytest.raises(XmlParseError):
        parse_xml_stream(b"<wrong/>")
