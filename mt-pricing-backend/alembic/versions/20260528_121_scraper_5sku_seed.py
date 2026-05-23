"""scraper_5sku_seed — limpia datos de negocio y carga 5 SKUs para pruebas de scraper real.

Selección: diversidad de tipo de válvula y material para validar el pipeline
CurlCffi → Amazon UAE → scoring con datos reales.

SKUs:
  4222015 — Ball Valve Long Neck brass 1/2" PN30 threaded  (confirmado en amazon.ae)
  4097015 — Ball Valve M-F brass 1/2" PN30 threaded
  4113015 — Gate Valve brass 1/2" PN10 threaded
  4215040 — Check Valve brass 1-1/2" PN25 threaded
  0910040 — Ball Valve SS316 2-piece 1-1/2" PN63 threaded

Revision ID: 20260528_121
Revises: 20260528_120, 20260513_111
Create Date: 2026-05-28
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "20260528_121"
down_revision: tuple[str, ...] = ("20260528_120", "20260513_111")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _j(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("'", "''")


_PRODUCTS = [
    # (sku, fam_code, sub_code, fam_text, sub_text,
    #  type_, material, dn, pn, connection, size,
    #  temp_min, temp_max, pressure_bar,
    #  weight, intrastat, erp_name,
    #  specs_extra, dimensions, packaging,
    #  coste_aed, pvp_aed, image_url)
    (
        "4222015",
        "ball_valve",
        "VALV_LATON_PN30",
        "HIDROSANITARIO",
        "VALV.LATÓN CARLAS+EMPOTRAR",
        "Ball Valve Long Neck",
        "brass",
        '1/2"',
        "PN30",
        "threaded",
        '1/2"',
        -20,
        120,
        30.0,
        0.21,
        "84818081",
        'VALVULA ESFERA EMPOTRAR H-H PN30 ROSCAR CARLA 1/2"',
        {
            "alloy": ["CW617N"],
            "standards": ["ISO228/1", "UNEEN12165"],
            "end_connection": ["threaded"],
            "applications": ["drinking_water"],
            "materials": {"body": "brass", "ball": "brass", "stem": "brass"},
        },
        {"alto_mm": 91.5, "ancho_mm": 50.0, "fondo_mm": 30.0},
        {"ean_individual": "8435319115534", "units_per_box": 20},
        13.163865,
        49.50,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/2/4222-4222.jpg",
    ),
    (
        "4097015",
        "ball_valve",
        "VALV_LATON_PN30",
        "HIDROSANITARIO",
        "VALV.LATÓN PN-30",
        "Ball Valve M-F PN30",
        "brass",
        '1/2"',
        "PN30",
        "threaded",
        '1/2"',
        -20,
        120,
        30.0,
        0.181,
        "84818081",
        'VALVULA ESFERA PN30 M-H PALANCA ERG. INOXIDABLE ROJA 1/2"',
        {
            "alloy": ["CW617N"],
            "standards": ["DIN259", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water", "gas"],
            "handle_color": "red",
            "handle_material": "stainless_steel",
            "materials": {"body": "brass", "ball": "brass", "stem": "brass"},
        },
        {"alto_mm": 95.0, "ancho_mm": 55.0, "fondo_mm": 35.0},
        {"ean_individual": "8435319113516", "units_per_box": 25},
        9.553830,
        36.75,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/3/4097-4097.jpg",
    ),
    (
        "4113015",
        "gate_valve",
        "VALV_COMPUERTA_LATON",
        "HIDROSANITARIO",
        "VALV.LATÓN COMPUERTA",
        "Gate Valve PN10",
        "brass",
        '1/2"',
        "PN10",
        "threaded",
        '1/2"',
        0,
        120,
        20.0,
        0.180,
        "84818020",
        'VALVULA COMPUERTA PN10 PASO STANDAR H-H 1/2"',
        {
            "alloy": ["CW617N"],
            "standards": ["DIN259", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water"],
            "materials": {"body": "brass", "gate": "brass", "stem": "brass"},
        },
        {"alto_mm": 110.0, "ancho_mm": 45.0, "fondo_mm": 35.0},
        {"ean_individual": "8435319114391", "units_per_box": 25},
        8.423415,
        31.68,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/1/4113.jpg",
    ),
    (
        "4215040",
        "check_valve",
        "VALV_RETENCION_LATON",
        "HIDROSANITARIO",
        "VALV.LATÓN RETENCIÓN",
        "Check Valve Light Type",
        "brass",
        '1 1/2"',
        "PN25",
        "threaded",
        "DN40",
        -20,
        100,
        25.0,
        0.565,
        "84818099",
        'VALVULA RETENCION LIGERA OBTURADOR METALICO H-H 1 1/2"',
        {
            "alloy": ["CW617N"],
            "standards": ["DIN259", "EN-12165", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water", "heating"],
            "shutter_type": "metal",
            "materials": {"body": "brass", "shutter": "brass", "spring": "stainless_steel"},
        },
        {"alto_mm": 120.0, "ancho_mm": 80.0, "fondo_mm": 55.0},
        {"ean_individual": "8435319130803", "units_per_box": 10},
        33.000825,
        142.11,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/4/4215-4215.jpg",
    ),
    (
        "0910040",
        "ball_valve",
        "VALV_INOX_2PCS",
        "INDUSTRIAL",
        "VÁLVULAS INOXIDABLES-2 PIEZAS",
        "Ball Valve SS 2-piece Threaded",
        "stainless_steel",
        '1 1/2"',
        "PN63",
        "threaded",
        "DN40",
        -20,
        180,
        63.0,
        1.200,
        "84818030",
        'VALVULA INOX. DE DOS PIEZAS ROSCAR H-H 11/2" PALANCA AZUL',
        {
            "alloy": ["AISI316", "AISI304"],
            "standards": ["DIN259", "ISO228", "ISO5211"],
            "end_connection": ["threaded"],
            "applications": ["industrial", "water", "air"],
            "handle_color": "blue",
            "materials": {
                "body": "AISI316",
                "ball": "AISI316",
                "stem": "AISI304",
                "seat": "PTFE",
                "seals": "PTFE",
            },
        },
        {"alto_mm": 180.0, "ancho_mm": 120.0, "fondo_mm": 85.0},
        {"ean_individual": "8435319117767", "units_per_box": 5},
        88.755810,
        248.52,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/1/0910.jpg",
    ),
]

_TRANSLATIONS = {
    "4222015": {
        "es": (
            'VALVULA ESFERA EMPOTRAR H-H PN30 ROSCAR CARLA 1/2"',
            "Válvula esfera PN30 para empotrar conexión roscada. Latón CW617N.",
        ),
        "en": (
            'F-F PN30 LONG NECK THREADED BALL VALVE 1/2"',
            "Long neck ball valve PN30 threaded ends. Brass CW617N. Drinking water.",
        ),
    },
    "4097015": {
        "es": (
            'VALVULA ESFERA PN30 M-H PALANCA INOXIDABLE ROJA 1/2"',
            "Válvula esfera PN30 macho-hembra con palanca roja inoxidable. Latón CW617N.",
        ),
        "en": (
            'M-F PN30 BRASS BALL VALVE RED SS HANDLE 1/2"',
            "Male-female brass ball valve PN30 with red stainless steel ergonomic handle.",
        ),
    },
    "4113015": {
        "es": (
            'VALVULA COMPUERTA PN10 PASO STANDAR H-H 1/2"',
            "Válvula de compuerta PN10 paso estándar hembra-hembra. Latón CW617N.",
        ),
        "en": (
            'F-F BRASS GATE VALVE PN10 STANDARD BORE 1/2"',
            "Female-female brass gate valve PN10 standard bore. Brass CW617N.",
        ),
    },
    "4215040": {
        "es": (
            'VALVULA RETENCION LIGERA OBTURADOR METALICO H-H 1 1/2"',
            "Válvula de retención ligera con obturador metálico PN25. Latón CW617N.",
        ),
        "en": (
            'F-F BRASS CHECK VALVE LIGHT TYPE METAL SHUTTER 1 1/2"',
            "Light type brass check valve with metal shutter. PN25 threaded ends.",
        ),
    },
    "0910040": {
        "es": (
            'VALVULA INOX. 2 PIEZAS ROSCAR H-H 1 1/2" PALANCA AZUL',
            "Válvula esfera inoxidable 2 piezas PN63 con palanca azul. AISI316.",
        ),
        "en": (
            'SS316 2-PIECE BALL VALVE F-F THREADED PN63 1 1/2" BLUE HANDLE',
            "Stainless steel AISI316 2-piece ball valve PN63 threaded. Blue handle.",
        ),
    },
}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1) TRUNCATE datos de negocio (respeta FK order) ──────────────────────
    for tbl in [
        "inventory_positions",
        "cost_lots",
        "goods_receipts",
        "purchase_order_lines",
        "purchase_orders",
        "match_candidates",
        "price_approval_events",
        "prices",
        "costs",
        "asset_links",
        "product_assets",
        "product_translations",
        "products",
    ]:
        bind.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))

    # ── 2) Master data ────────────────────────────────────────────────────────
    bind.execute(
        text("""
        INSERT INTO brands (code, name, active)
        VALUES ('MT', 'MT Middle East', true)
        ON CONFLICT (code) DO NOTHING
    """)
    )

    bind.execute(
        text("""
        INSERT INTO suppliers (code, name, contact_email, contact_phone,
                               contract_currency, lead_time_days, payment_terms, active)
        VALUES ('mt_spain', 'MT Spain S.A.', 'orders@mtspain.net', '+34 93 555 0001',
                'EUR', 21, 'Net 60 días', true)
        ON CONFLICT (code) DO NOTHING
    """)
    )

    for fcode, fname, fdesc, fsort in [
        ("ball_valve", "Ball Valves", "Válvulas de esfera latón e inoxidable", 1),
        ("gate_valve", "Gate Valves", "Válvulas de compuerta latón y fundición", 2),
        ("check_valve", "Check Valves", "Válvulas de retención y antiretorno", 3),
    ]:
        bind.execute(
            text("""
            INSERT INTO families (code, name, description, sort_order, active)
            VALUES (:c, :n, :d, :s, true)
            ON CONFLICT (code) DO NOTHING
        """),
            {"c": fcode, "n": fname, "d": fdesc, "s": fsort},
        )

    for fam_code, sub_code, sub_name, sub_sort in [
        ("ball_valve", "VALV_LATON_PN30", "Ball Valves PN30 Brass", 1),
        ("ball_valve", "VALV_INOX_2PCS", "Ball Valves SS 2-piece", 3),
        ("gate_valve", "VALV_COMPUERTA_LATON", "Gate Valves Brass", 1),
        ("check_valve", "VALV_RETENCION_LATON", "Check Valves Brass", 1),
    ]:
        bind.execute(
            text("""
            INSERT INTO subfamilies (family_id, code, name, sort_order, active)
            SELECT f.id, :sc, :sn, :ss, true
            FROM families f WHERE f.code = :fc
            ON CONFLICT (family_id, code) DO NOTHING
        """),
            {"fc": fam_code, "sc": sub_code, "sn": sub_name, "ss": sub_sort},
        )

    # ── 3) Productos ──────────────────────────────────────────────────────────
    for (
        sku,
        fam_code,
        sub_code,
        fam_text,
        sub_text,
        type_,
        material,
        dn,
        pn,
        connection,
        size,
        temp_min,
        temp_max,
        pressure_bar,
        weight,
        intrastat,
        erp_name,
        specs_extra,
        dimensions,
        packaging,
        coste_aed,
        pvp_aed,
        image_url,
    ) in _PRODUCTS:
        temp_min_sql = "NULL" if temp_min is None else str(temp_min)
        temp_max_sql = "NULL" if temp_max is None else str(temp_max)

        bind.execute(
            text(f"""
            INSERT INTO products (
                sku, family, subfamily, type, material, dn, pn, connection, brand,
                specs, dimensions, packaging,
                weight, weight_unit, intrastat_code, erp_name,
                size, temp_min_c, temp_max_c, pressure_max_bar,
                data_quality, lifecycle_status,
                brand_id, family_id, subfamily_id
            )
            SELECT
                '{sku}',
                '{fam_text}',
                '{sub_text.replace(chr(39), chr(39) * 2)}',
                '{type_.replace(chr(39), chr(39) * 2)}',
                '{material}',
                '{dn.replace(chr(39), chr(39) * 2)}',
                '{pn}',
                '{connection}',
                'MT',
                '{_j(specs_extra)}'::jsonb,
                '{_j(dimensions)}'::jsonb,
                '{_j(packaging)}'::jsonb,
                {weight}, 'kg',
                '{intrastat}',
                '{erp_name.replace(chr(39), chr(39) * 2)}',
                '{size.replace(chr(39), chr(39) * 2)}',
                {temp_min_sql}, {temp_max_sql}, {pressure_bar},
                'complete', 'active',
                b.id, f.id, s.id
            FROM brands b
            JOIN families f ON f.code = '{fam_code}'
            LEFT JOIN subfamilies s ON s.family_id = f.id AND s.code = '{sub_code}'
            WHERE b.code = 'MT'
            ON CONFLICT (sku) DO NOTHING
        """)
        )

    # ── 4) Traducciones ES + EN ───────────────────────────────────────────────
    for sku, langs in _TRANSLATIONS.items():
        for lang, (name, desc) in langs.items():
            bind.execute(
                text(f"""
                INSERT INTO product_translations (sku, lang, name, description, status)
                VALUES ('{sku}', '{lang}',
                        '{name.replace(chr(39), chr(39) * 2)}',
                        '{desc.replace(chr(39), chr(39) * 2)}',
                        'approved')
                ON CONFLICT (sku, lang) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    status = 'approved'
            """)
            )

    # ── 5) Assets (imagen principal) ─────────────────────────────────────────
    for sku, *_, image_url in _PRODUCTS:
        if not image_url:
            continue
        ext = image_url.rsplit(".", 1)[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        bind.execute(
            text(f"""
            INSERT INTO product_assets
                (sku, kind, bucket, storage_path, original_url, position, alt_text, mime_type)
            VALUES
                ('{sku}', 'external_url', 'product-images', '{image_url}', '{image_url}', 0,
                 (SELECT name FROM product_translations
                  WHERE sku='{sku}' AND lang='en' LIMIT 1),
                 '{mime}')
            ON CONFLICT (bucket, storage_path) DO NOTHING
        """)
        )

    # ── 6) Costos FBA + DIRECT_B2C ───────────────────────────────────────────
    for sku, *_, coste_aed, pvp_aed, __ in _PRODUCTS:
        fob = round(coste_aed * 0.65, 4)
        freight = round(coste_aed * 0.15, 4)
        customs = round(coste_aed * 0.12, 4)
        fba_fees = round(coste_aed * 0.08, 4)
        mkt = round(coste_aed * 0.10, 4)

        bd_fba = _j({"fob": fob, "freight": freight, "customs": customs, "fba_fees": fba_fees})
        bd_b2c = _j(
            {
                "fob": fob,
                "freight": freight,
                "customs": customs,
                "payment_fees": round(coste_aed * 0.02, 4),
                "marketing": mkt,
            }
        )

        bind.execute(
            text(f"""
            INSERT INTO costs
                (sku, scheme_code, supplier_code, breakdown, currency_origin, effective_at)
            VALUES
                ('{sku}', 'FBA',       'mt_spain', '{bd_fba}'::jsonb, 'AED', '2026-04-01 00:00:00+00'),
                ('{sku}', 'DIRECT_B2C','mt_spain', '{bd_b2c}'::jsonb, 'AED', '2026-04-01 00:00:00+00')
            ON CONFLICT DO NOTHING
        """)
        )

    # ── 7) Precios amazon_uae (pending_review — el scraper los validará) ──────
    bind.execute(text("ALTER TABLE prices DISABLE TRIGGER prices_initial_status_trg;"))

    for sku, *_, coste_aed, pvp_aed, __ in _PRODUCTS:
        margin = round((pvp_aed - coste_aed) / pvp_aed * 100, 4) if pvp_aed > 0 else 0
        bd = _j({"cost": coste_aed, "target_pvp": pvp_aed, "margin_pct": margin, "scheme": "FBA"})
        bind.execute(
            text(f"""
            INSERT INTO prices
                (product_sku, channel_id, scheme_code, amount, margin_pct,
                 currency, status, breakdown, valid_from)
            SELECT
                '{sku}', c.id, 'FBA', {pvp_aed}, {margin},
                'AED', 'pending_review', '{bd}'::jsonb, '2026-05-28 00:00:00+00'
            FROM channels c WHERE c.code = 'amazon_uae'
            ON CONFLICT DO NOTHING
        """)
        )

    bind.execute(text("ALTER TABLE prices ENABLE TRIGGER prices_initial_status_trg;"))


def downgrade() -> None:
    bind = op.get_bind()
    skus = [r[0] for r in _PRODUCTS]
    placeholders = ", ".join(f"'{s}'" for s in skus)
    bind.execute(text(f"DELETE FROM products WHERE sku IN ({placeholders})"))
