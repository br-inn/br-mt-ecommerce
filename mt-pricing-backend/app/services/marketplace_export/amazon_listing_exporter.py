"""Builds Amazon UAE flat-file feed rows from product + marketplace listing data.

All 46 columns of the Amazon UAE PlumbingFixture feed template.
Static values are per the reference Excel "VOLCADO AMAZON".
"""
from __future__ import annotations

import csv
import io
from typing import Any

AMAZON_FEED_HEADERS = [
    "feed_product_type",
    "item_sku",
    "external_product_id",
    "external_product_id_type",
    "brand_name",
    "item_name",
    "manufacturer",
    "part_number",
    "model",
    "country_of_origin",
    "condition_type",
    "product_description",
    "bullet_point1",
    "bullet_point2",
    "bullet_point3",
    "bullet_point4",
    "bullet_point5",
    "generic_keyword",
    "main_image_url",
    "other_image_url1",
    "other_image_url2",
    "other_image_url3",
    "other_image_url4",
    "other_image_url5",
    "other_image_url6",
    "other_image_url7",
    "standard_price",
    "currency",
    "quantity",
    "fulfillment_channel",
    "item_weight",
    "item_weight_unit_of_measure",
    "package_weight",
    "package_weight_unit_of_measure",
    "item_height",
    "item_width",
    "item_length",
    "item_dimensions_unit_of_measure",
    "package_height",
    "package_width",
    "package_length",
    "package_dimensions_unit_of_measure",
    "material_type",
    "connection_type",
    "pressure_rating_unit_of_measure",
    "pressure_rating",
    "min_temperature",
    "max_temperature",
    "temperature_unit_of_measure",
    "size_name",
    "compliance_certifications",
    "compliance_standards",
    "safety_data_sheet_url",
    "hs_code",
    "update_delete",
]

_REQUIRED_FIELDS = [
    ("item_sku", "MISSING_SKU", "SKU is required"),
    ("external_product_id", "MISSING_EAN", "EAN/GTIN is required for Amazon"),
    ("item_name", "MISSING_TITLE", "Listing title is required"),
    ("product_description", "MISSING_DESCRIPTION", "Product description is required"),
    ("standard_price", "MISSING_PRICE", "Price (standard_price) is required"),
]

_WARNING_RULES = [
    ("hs_code", "MISSING_HS_CODE", "HS code missing — required for customs"),
    ("main_image_url", "MISSING_MAIN_IMAGE", "Main image URL missing"),
]


class AmazonListingExporter:
    """Assembles Amazon UAE flat-file rows and validates field completeness."""

    def build_row(self, product: Any, listing: Any | None, channel_listing: Any | None) -> dict[str, Any]:
        """Return a dict with all 46 Amazon feed fields populated."""
        images = sorted(
            [a for a in (getattr(product, "assets", None) or []) if getattr(a, "kind", "") == "image"],
            key=lambda a: getattr(a, "position", 99),
        )
        img_urls = [getattr(img, "public_url", "") or "" for img in images]

        body_materials = [
            m for m in (getattr(product, "materials", None) or [])
            if getattr(m, "component", "") == "body" and getattr(m, "position", 0) == 0
        ]
        material_type = body_materials[0].material if body_materials else ""

        conns = sorted(
            getattr(product, "connections", None) or [],
            key=lambda c: getattr(c, "position", 99),
        )
        connection_type = conns[0].connection_type if conns else ""

        pt = next(
            (t for t in (getattr(product, "tech_tables", None) or [])
             if getattr(t, "kind", "") == "pressure_temperature"),
            None,
        )
        pressure = float(pt.data.get("pn")) if pt and pt.data.get("pn") is not None else ""
        temp_min = float(pt.data.get("temp_min_c")) if pt and pt.data.get("temp_min_c") is not None else ""
        temp_max = float(pt.data.get("temp_max_c")) if pt and pt.data.get("temp_max_c") is not None else ""

        dim_table = next(
            (t for t in (getattr(product, "tech_tables", None) or [])
             if getattr(t, "kind", "") == "dimensions_by_dn"),
            None,
        )
        dim_row: dict[str, Any] = {}
        if dim_table and isinstance(dim_table.data, dict) and dim_table.data.get("rows"):
            dim_row = dim_table.data["rows"][0]

        certs = getattr(product, "certificates", None) or []
        cert_codes = ", ".join(
            c.certification_code for c in certs if getattr(c, "certification_code", None)
        )
        cert_standards = ", ".join(
            c.standard for c in certs if getattr(c, "standard", None)
        )
        cert_url = next(
            (getattr(c, "document_url", "") for c in certs if getattr(c, "document_url", None)),
            "",
        )

        bullets = list(getattr(listing, "bullet_points", None) or []) if listing else []
        extra = dict(getattr(listing, "extra", None) or {}) if listing else {}

        raw_price = extra.get("standard_price", "") if listing else ""
        price = float(raw_price) if raw_price not in ("", None) else ""
        stock = getattr(channel_listing, "stock_qty", "") if channel_listing else ""

        return {
            "feed_product_type": "PlumbingFixture",
            "item_sku": getattr(product, "sku", ""),
            "external_product_id": getattr(product, "gtin", "") or "",
            "external_product_id_type": "EAN",
            "brand_name": "MT Valves And Fittings",
            "item_name": getattr(listing, "listing_title", "") or "" if listing else "",
            "manufacturer": "Business Key, S.L.",
            "part_number": getattr(product, "sku", ""),
            "model": getattr(product, "sku", ""),
            "country_of_origin": getattr(product, "country_of_origin", "ES") or "ES",
            "condition_type": "New",
            "product_description": getattr(listing, "listing_description", "") or "" if listing else "",
            "bullet_point1": bullets[0] if len(bullets) > 0 else "",
            "bullet_point2": bullets[1] if len(bullets) > 1 else "",
            "bullet_point3": bullets[2] if len(bullets) > 2 else "",
            "bullet_point4": bullets[3] if len(bullets) > 3 else "",
            "bullet_point5": bullets[4] if len(bullets) > 4 else "",
            "generic_keyword": getattr(listing, "search_keywords", "") or "" if listing else "",
            "main_image_url": img_urls[0] if img_urls else "",
            "other_image_url1": img_urls[1] if len(img_urls) > 1 else "",
            "other_image_url2": img_urls[2] if len(img_urls) > 2 else "",
            "other_image_url3": img_urls[3] if len(img_urls) > 3 else "",
            "other_image_url4": img_urls[4] if len(img_urls) > 4 else "",
            "other_image_url5": img_urls[5] if len(img_urls) > 5 else "",
            "other_image_url6": img_urls[6] if len(img_urls) > 6 else "",
            "other_image_url7": img_urls[7] if len(img_urls) > 7 else "",
            "standard_price": price,
            "currency": "AED",
            "quantity": stock,
            "fulfillment_channel": extra.get("fulfillment_channel", "DEFAULT"),
            "item_weight": getattr(product, "weight", "") or "",
            "item_weight_unit_of_measure": "KG",
            "package_weight": extra.get("package_weight", ""),
            "package_weight_unit_of_measure": "KG",
            "item_height": dim_row.get("H_mm", ""),
            "item_width": dim_row.get("W_mm", ""),
            "item_length": dim_row.get("L_mm", ""),
            "item_dimensions_unit_of_measure": "CM",
            "package_height": extra.get("pkg_h", ""),
            "package_width": extra.get("pkg_w", ""),
            "package_length": extra.get("pkg_l", ""),
            "package_dimensions_unit_of_measure": "CM",
            "material_type": material_type,
            "connection_type": connection_type,
            "pressure_rating_unit_of_measure": "bar",
            "pressure_rating": pressure,
            "min_temperature": temp_min,
            "max_temperature": temp_max,
            "temperature_unit_of_measure": "Celsius",
            "size_name": getattr(product, "dn", "") or "",
            "compliance_certifications": cert_codes,
            "compliance_standards": cert_standards,
            "safety_data_sheet_url": cert_url,
            "hs_code": getattr(product, "hs_code", "") or "",
            "update_delete": "Update",
        }

    def validate(
        self,
        product: Any,
        listing: Any | None,
        channel_listing: Any | None,
    ) -> tuple[list[dict], list[dict]]:
        """Return (errors, warnings). Errors block export; warnings are informational."""
        row = self.build_row(product, listing, channel_listing)
        errors: list[dict] = []
        warnings: list[dict] = []

        for field, code, message in _REQUIRED_FIELDS:
            val = row.get(field)
            if not val and val != 0:
                errors.append({"field": field, "code": code, "message": message})

        for field, code, message in _WARNING_RULES:
            val = row.get(field)
            if not val:
                warnings.append({"field": field, "code": code, "message": message})

        bullets_filled = sum(
            1 for k in ("bullet_point1", "bullet_point2", "bullet_point3",
                        "bullet_point4", "bullet_point5")
            if row.get(k)
        )
        if bullets_filled < 5:
            warnings.append({
                "field": "bullet_points",
                "code": "INCOMPLETE_BULLETS",
                "message": f"Only {bullets_filled}/5 bullet points filled. Amazon recommends all 5.",
            })

        return errors, warnings

    def export_csv(
        self,
        rows: list[tuple[Any, Any | None, Any | None]],
    ) -> bytes:
        """Build Amazon flat-file CSV bytes from (product, listing, channel_listing) tuples."""
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=AMAZON_FEED_HEADERS,
            extrasaction="ignore",
            lineterminator="\r\n",
        )
        writer.writeheader()
        for product, listing, channel_listing in rows:
            writer.writerow(self.build_row(product, listing, channel_listing))
        return buf.getvalue().encode("utf-8")
