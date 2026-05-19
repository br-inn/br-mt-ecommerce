"""Unit tests for AmazonListingExporter — no DB, pure mock."""
import csv
import io
from unittest.mock import MagicMock

import pytest

from app.services.marketplace_export.amazon_listing_exporter import (
    AMAZON_FEED_HEADERS,
    AmazonListingExporter,
)


def _make_product(
    sku="4097015",
    gtin="8435319115534",
    weight=0.35,
    dn='1/2"',
    hs_code="84818099",
    country_of_origin="ES",
    material="Brass CW617N",
    connection_type="Threaded BSP",
    pressure=30.0,
    temp_min=-20.0,
    temp_max=120.0,
):
    p = MagicMock()
    p.sku = sku
    p.gtin = gtin
    p.weight = weight
    p.dn = dn
    p.hs_code = hs_code
    p.country_of_origin = country_of_origin

    mat = MagicMock()
    mat.component = "body"
    mat.position = 0
    mat.material = material
    p.materials = [mat]

    conn = MagicMock()
    conn.position = 1
    conn.connection_type = connection_type
    p.connections = [conn]

    pt_table = MagicMock()
    pt_table.kind = "pressure_temperature"
    pt_table.data = {"pn": pressure, "temp_min_c": temp_min, "temp_max_c": temp_max}
    p.tech_tables = [pt_table]

    img1 = MagicMock()
    img1.kind = "image"
    img1.position = 0
    img1.public_url = "https://cdn.example.com/img1.jpg"
    p.assets = [img1]

    p.certificates = []
    return p


def _make_listing(
    listing_title="MT Valves Ball Valve 1/2 Brass PN30",
    listing_description="Long neck ball valve PN30 threaded ends...",
    bullet_points=None,
    search_keywords="ball valve brass 1/2 PN30",
    extra=None,
):
    if bullet_points is None:
        bullet_points = [
            "PN30 rated ball valve",
            "Brass CW617N body",
            "BSP threaded ends",
            "Temperature range -20°C to 120°C",
            "CE certified",
        ]
    lst = MagicMock()
    lst.listing_title = listing_title
    lst.listing_description = listing_description
    lst.bullet_points = bullet_points
    lst.search_keywords = search_keywords
    lst.extra = extra if extra is not None else {"standard_price": 45.00}
    return lst


def _make_channel_listing(stock=10):
    cl = MagicMock()
    cl.channel_code = "amazon_uae"
    cl.stock_qty = stock
    return cl


class TestBuildRow:
    def test_static_fields_are_correct(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), _make_listing(), _make_channel_listing())
        assert row["feed_product_type"] == "PlumbingFixture"
        assert row["brand_name"] == "MT Valves And Fittings"
        assert row["manufacturer"] == "Business Key, S.L."
        assert row["condition_type"] == "New"
        assert row["external_product_id_type"] == "EAN"
        assert row["currency"] == "AED"
        assert row["item_weight_unit_of_measure"] == "KG"
        assert row["item_dimensions_unit_of_measure"] == "CM"
        assert row["pressure_rating_unit_of_measure"] == "bar"
        assert row["temperature_unit_of_measure"] == "Celsius"
        assert row["update_delete"] == "Update"

    def test_product_fields_mapped(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), _make_listing(), _make_channel_listing())
        assert row["item_sku"] == "4097015"
        assert row["external_product_id"] == "8435319115534"
        assert row["country_of_origin"] == "ES"
        assert row["item_weight"] == 0.35
        assert row["size_name"] == '1/2"'
        assert row["hs_code"] == "84818099"

    def test_listing_content_mapped(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), _make_listing(), _make_channel_listing())
        assert row["item_name"] == "MT Valves Ball Valve 1/2 Brass PN30"
        assert row["bullet_point1"] == "PN30 rated ball valve"
        assert row["bullet_point2"] == "Brass CW617N body"
        assert row["generic_keyword"] == "ball valve brass 1/2 PN30"

    def test_price_from_listing_extra_and_stock_from_channel_listing(self):
        exporter = AmazonListingExporter()
        listing = _make_listing(extra={"standard_price": 55.5})
        row = exporter.build_row(_make_product(), listing, _make_channel_listing(stock=7))
        assert row["standard_price"] == 55.5
        assert row["quantity"] == 7

    def test_no_price_in_extra_returns_empty(self):
        exporter = AmazonListingExporter()
        listing = _make_listing(extra={})
        row = exporter.build_row(_make_product(), listing, _make_channel_listing())
        assert row["standard_price"] == ""

    def test_material_from_body_component(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), _make_listing(), _make_channel_listing())
        assert row["material_type"] == "Brass CW617N"

    def test_pressure_temperature_from_tech_tables(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), _make_listing(), _make_channel_listing())
        assert row["pressure_rating"] == 30.0
        assert row["min_temperature"] == -20.0
        assert row["max_temperature"] == 120.0

    def test_main_image_url_from_assets(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), _make_listing(), _make_channel_listing())
        assert row["main_image_url"] == "https://cdn.example.com/img1.jpg"

    def test_missing_listing_returns_empty_content_fields(self):
        exporter = AmazonListingExporter()
        row = exporter.build_row(_make_product(), None, _make_channel_listing())
        assert row["item_name"] == ""
        assert row["bullet_point1"] == ""


class TestValidate:
    def test_complete_product_has_no_errors(self):
        exporter = AmazonListingExporter()
        errors, warnings = exporter.validate(_make_product(), _make_listing(), _make_channel_listing())
        assert errors == []

    def test_missing_gtin_is_error(self):
        exporter = AmazonListingExporter()
        p = _make_product(gtin=None)
        errors, _ = exporter.validate(p, _make_listing(), _make_channel_listing())
        codes = [e["code"] for e in errors]
        assert "MISSING_EAN" in codes

    def test_missing_listing_title_is_error(self):
        exporter = AmazonListingExporter()
        lst = _make_listing(listing_title=None)
        errors, _ = exporter.validate(_make_product(), lst, _make_channel_listing())
        codes = [e["code"] for e in errors]
        assert "MISSING_TITLE" in codes

    def test_missing_price_is_error_when_not_in_extra(self):
        exporter = AmazonListingExporter()
        listing = _make_listing(extra={})
        errors, _ = exporter.validate(_make_product(), listing, _make_channel_listing())
        codes = [e["code"] for e in errors]
        assert "MISSING_PRICE" in codes

    def test_missing_price_is_error_when_no_listing(self):
        exporter = AmazonListingExporter()
        errors, _ = exporter.validate(_make_product(), None, _make_channel_listing())
        codes = [e["code"] for e in errors]
        assert "MISSING_PRICE" in codes

    def test_missing_hs_code_is_warning(self):
        exporter = AmazonListingExporter()
        p = _make_product(hs_code=None)
        _, warnings = exporter.validate(p, _make_listing(), _make_channel_listing())
        codes = [w["code"] for w in warnings]
        assert "MISSING_HS_CODE" in codes

    def test_fewer_than_five_bullets_is_warning(self):
        exporter = AmazonListingExporter()
        lst = _make_listing(bullet_points=["Only one bullet"])
        _, warnings = exporter.validate(_make_product(), lst, _make_channel_listing())
        codes = [w["code"] for w in warnings]
        assert "INCOMPLETE_BULLETS" in codes


class TestExportCsv:
    def test_csv_has_correct_headers(self):
        exporter = AmazonListingExporter()
        rows = [(_make_product(), _make_listing(), _make_channel_listing())]
        csv_bytes = exporter.export_csv(rows)
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
        assert list(reader.fieldnames) == AMAZON_FEED_HEADERS

    def test_csv_has_one_data_row(self):
        exporter = AmazonListingExporter()
        rows = [(_make_product(), _make_listing(), _make_channel_listing())]
        csv_bytes = exporter.export_csv(rows)
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
        data_rows = list(reader)
        assert len(data_rows) == 1
        assert data_rows[0]["item_sku"] == "4097015"
