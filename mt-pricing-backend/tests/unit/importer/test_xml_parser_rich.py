from __future__ import annotations

from app.services.importer.xml_parser import parse_xml_stream

_NS = "https://mtme-api/schemas/articulos/v1"

_RICH = f"""<?xml version="1.0" encoding="UTF-8"?>
<catalog xmlns="{_NS}">
  <article>
    <sku>MT-V-038</sku>
    <name_en>Brass Ball Valve DN25</name_en>
    <family>ball_valve</family>
    <specs>
      <materials_body>brass</materials_body>
      <kv>32.5</kv>
      <connections>
        <connection><position>1</position><type>threaded</type><dn>25</dn></connection>
        <connection><position>2</position><type>threaded</type><dn>25</dn></connection>
      </connections>
      <extra>
        <field key="surface_treatment">nickel_plated</field>
        <field key="mesh_microns">500</field>
      </extra>
    </specs>
    <translations>
      <translation lang="es" status="approved">
        <name>Válvula de bola</name>
        <description>Desc ES</description>
      </translation>
      <translation lang="ar"><name>صمام</name></translation>
    </translations>
    <releases>
      <release market_code="UAE">
        <local_name>Ball Valve</local_name>
        <list_price>45.00</list_price>
        <price_currency>AED</price_currency>
      </release>
    </releases>
    <uom_conversions>
      <uom_conversion uom_from="BOX" uom_to="EA" factor="20"/>
    </uom_conversions>
    <bore_dimensions>
      <bore_dimension standard_system="EN" standard_code="EN 1092-1" is_primary="true">
        <bore_mm>25</bore_mm>
      </bore_dimension>
    </bore_dimensions>
  </article>
</catalog>"""


def test_specs_extra_and_connections() -> None:
    row = parse_xml_stream(_RICH.encode("utf-8")).rows[0]
    specs = row.payload["specs"]
    assert specs["materials_body"] == "brass"
    assert specs["kv"] == "32.5"
    assert specs["surface_treatment"] == "nickel_plated"
    assert specs["mesh_microns"] == "500"
    assert specs["connections"] == [
        {"position": 1, "type": "threaded", "dn": "25"},
        {"position": 2, "type": "threaded", "dn": "25"},
    ]


def test_rich_blocks() -> None:
    p = parse_xml_stream(_RICH.encode("utf-8")).rows[0].payload
    assert {
        "lang": "es",
        "status": "approved",
        "name": "Válvula de bola",
        "description": "Desc ES",
    }.items() <= p["_translations"][0].items()
    assert p["_translations"][1]["lang"] == "ar"
    assert p["_releases"][0] == {
        "market_code": "UAE",
        "local_name": "Ball Valve",
        "list_price": "45.00",
        "price_currency": "AED",
    }
    assert p["_uom_conversions"][0] == {"uom_from": "BOX", "uom_to": "EA", "factor": "20"}
    bore = p["_bore_dimensions"][0]
    assert bore["standard_system"] == "EN"
    assert bore["standard_code"] == "EN 1092-1"
    assert bore["is_primary"] is True
    assert bore["bore_mm"] == "25"


def test_manufacturing_method_folds_into_specs() -> None:
    xml = (
        f'<catalog xmlns="{_NS}"><article><sku>MT-V-1</sku>'
        f"<name_en>x</name_en><family>ball_valve</family>"
        f"<manufacturing_method>forged</manufacturing_method>"
        f"<specs><materials_body>brass</materials_body></specs>"
        f"</article></catalog>"
    )
    p = parse_xml_stream(xml.encode("utf-8")).rows[0].payload
    assert p["specs"]["manufacturing_method"] == "forged"
    assert p["specs"]["materials_body"] == "brass"
    assert "manufacturing_method" not in p  # not a top-level scalar
