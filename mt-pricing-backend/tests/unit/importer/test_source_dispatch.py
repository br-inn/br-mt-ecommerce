from __future__ import annotations

import pytest

from app.services.importer.source_dispatch import is_xml_filename, parse_source

_NS = "https://mtme-api/schemas/articulos/v1"
_XML = (
    f'<catalog xmlns="{_NS}"><article><sku>MT-V-1</sku>'
    f"<name_en>X</name_en><family>ball_valve</family></article></catalog>"
)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("articulos.xml", True),
        ("ART.XML", True),
        ("PIM completo.xlsx", False),
        ("data.csv", False),
    ],
)
def test_is_xml_filename(name: str, expected: bool) -> None:
    assert is_xml_filename(name) is expected


def test_parse_source_routes_xml() -> None:
    result = parse_source(_XML.encode("utf-8"), "articulos.xml")
    assert result.total_data_rows == 1
    assert result.rows[0].sku == "MT-V-1"
