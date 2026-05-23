"""demo_sample_seed — muestra curada 12 SKUs MT con datos 100% completos.

Limpia datos de negocio incompletos y carga 12 artículos reales extraídos
del MT_Pricing_Run_Kit (mt_master_specs.json) cubriendo 4 familias técnicas.

Qué hace:
  1. TRUNCATE datos de negocio (products + dependientes, costs, prices,
     match_candidates, purchase_orders cascade).  Preserva master data
     (currencies, channels, schemes, brands, families, subfamilies,
     suppliers, fx_rates, exception_rules).
  2. UPSERT brand MT + 4 families + subfamilias + supplier mt_spain.
  3. INSERT 12 productos con todos los campos.
  4. INSERT traducciones ES/EN/FR/DE/IT/PT.
  5. INSERT imágenes (URLs PIM reales).
  6. INSERT costos (FBA + DIRECT_B2C por producto).
  7. INSERT precios canal amazon_uae:
       - 9 aprobados, 2 pending_review, 1 rechazado (con historial).
  8. INSERT match_candidates (competidores Amazon reales del Run Kit).
  9. INSERT 3 POs con escenarios distintos:
       - PO-001 received: 4 SKUs, GR+lot+posición por línea.
       - PO-002 partial: 3 SKUs, 1 recibido parcial, 2 en tránsito.
       - PO-003 draft: 4 SKUs, sin recepciones.

Revision ID: 20260513_100
Revises: 096
Create Date: 2026-05-13
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "20260513_100"
down_revision: str | None = "096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# DATOS — 12 productos reales de MT extraídos de mt_master_specs.json
# ---------------------------------------------------------------------------

# (sku, family_code, subfamily_code, family_text, subfamily_text,
#  type_, material, dn, pn, connection, size,
#  temp_min_c, temp_max_c, pressure_max_bar,
#  weight_kg, intrastat_code, erp_name,
#  specs_extra, dimensions, packaging,
#  coste_aed, pvp_aed, image_url)
_PRODUCTS = [
    # ── Ball Valves Latón PN30 Carla ──────────────────────────────────────
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
        {"ean_individual": "8435319115534", "ean_caja": "28435319115538", "units_per_box": 20},
        13.163865,
        49.50,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/2/4222-4222.jpg",
    ),
    # ── Ball Valve F-F PN25 Blue Handle ───────────────────────────────────
    (
        "4092040",
        "ball_valve",
        "VALV_LATON_PN25",
        "HIDROSANITARIO",
        "VALV.LATÓN PN-25",
        "Ball Valve Full Bore",
        "brass",
        '1 1/2"',
        "PN25",
        "threaded",
        "DN40",
        -20,
        120,
        25.0,
        0.715,
        "84818081",
        'VALVULA ESFERA PN25 H-H PALANCA ACERO CARBONO AZUL 1 1/2"',
        {
            "alloy": ["CW617N", "AISI304"],
            "standards": ["DIN259", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water", "gas"],
            "handle_color": "blue",
            "handle_material": "carbon_steel",
            "materials": {"body": "brass", "ball": "brass", "stem": "brass"},
        },
        {"alto_mm": 158.0, "ancho_mm": 95.0, "fondo_mm": 60.0},
        {"ean_individual": "8435319113073", "ean_caja": "18435319113070", "units_per_box": 10},
        39.783315,
        67.12,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/4/4092-4092.jpg",
    ),
    # ── Ball Valve F-F PN30 Red SS Handle ─────────────────────────────────
    (
        "4295040",
        "ball_valve",
        "VALV_LATON_PN30",
        "HIDROSANITARIO",
        "VALV.LATÓN PN-30",
        "Ball Valve Full Bore",
        "brass",
        '1 1/2"',
        "PN30",
        "threaded",
        "DN40",
        -20,
        120,
        30.0,
        0.886,
        "84818081",
        'VALVULA ESFERA PN30 H-H CON PALANCA INOXIDABLE ROJA 1 1/2"',
        {
            "alloy": ["CW617N"],
            "standards": ["DIN259", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water", "gas"],
            "handle_color": "red",
            "handle_material": "stainless_steel",
            "materials": {"body": "brass", "ball": "brass", "stem": "brass"},
        },
        {"alto_mm": 165.0, "ancho_mm": 100.0, "fondo_mm": 65.0},
        {"ean_individual": "8435319143599", "ean_caja": "18435319143596", "units_per_box": 10},
        58.088745,
        81.32,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/5/4295.jpg",
    ),
    # ── Ball Valve M-F PN25 Blue Handle ───────────────────────────────────
    (
        "4091040",
        "ball_valve",
        "VALV_LATON_PN25",
        "HIDROSANITARIO",
        "VALV.LATÓN PN-25",
        "Ball Valve Full Bore M-F",
        "brass",
        '1 1/2"',
        "PN25",
        "threaded",
        "DN40",
        -20,
        120,
        25.0,
        0.780,
        "84818081",
        'VALVULA ESFERA PN25 M-H PL. ACERO CARBONO AZUL 1 1/2"',
        {
            "alloy": ["CW617N", "AISI304"],
            "standards": ["DIN259", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water", "gas"],
            "handle_color": "blue",
            "handle_material": "carbon_steel",
            "materials": {"body": "brass", "ball": "brass", "stem": "brass"},
        },
        {"alto_mm": 155.0, "ancho_mm": 95.0, "fondo_mm": 60.0},
        {"ean_individual": "8435319126042", "ean_caja": "18435319126049", "units_per_box": 10},
        42.591120,
        67.12,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/2/4091-4091_0.jpg",
    ),
    # ── Ball Valve M-F PN30 Red SS Handle 1/2" ────────────────────────────
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
        {"ean_individual": "8435319113516", "ean_caja": "18435319113513", "units_per_box": 25},
        9.553830,
        36.75,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/3/4097-4097.jpg",
    ),
    # ── Ball Valve F-F PN30 Butterfly Handle 1/2" ─────────────────────────
    (
        "4102015",
        "ball_valve",
        "VALV_LATON_PN30",
        "HIDROSANITARIO",
        "VALV.LATÓN PN-30",
        "Ball Valve Full Bore Butterfly Handle",
        "brass",
        '1/2"',
        "PN30",
        "threaded",
        '1/2"',
        -20,
        120,
        30.0,
        0.145,
        "84818081",
        'VALVULA ESFERA PN30 H-H, MANDO PALOMILLA ROJA 1/2"',
        {
            "alloy": ["CW617N"],
            "standards": ["DIN259", "ISO228/1"],
            "end_connection": ["threaded"],
            "applications": ["water", "gas"],
            "handle_type": "butterfly",
            "handle_color": "red",
            "materials": {"body": "brass", "ball": "brass", "stem": "brass"},
        },
        {"alto_mm": 85.0, "ancho_mm": 50.0, "fondo_mm": 32.0},
        {"ean_individual": "8435319113844", "ean_caja": "18435319113841", "units_per_box": 30},
        10.720710,
        38.50,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/3/4102-4102.jpg",
    ),
    # ── Gate Valve PN10 F-F 1/2" ──────────────────────────────────────────
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
        {"ean_individual": "8435319114391", "ean_caja": "18435319114398", "units_per_box": 25},
        8.423415,
        31.68,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/1/4113.jpg",
    ),
    # ── Check Valve F-F 1 1/2" ────────────────────────────────────────────
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
            "standards": ["DIN259", "EN-12165", "ISO228/1", "UNEEN1717"],
            "end_connection": ["threaded"],
            "applications": ["water", "heating"],
            "shutter_type": "metal",
            "materials": {"body": "brass", "shutter": "brass", "spring": "stainless_steel"},
        },
        {"alto_mm": 120.0, "ancho_mm": 80.0, "fondo_mm": 55.0},
        {"ean_individual": "8435319130803", "ean_caja": "18435319130800", "units_per_box": 10},
        33.000825,
        142.11,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/4/4215-4215.jpg",
    ),
    # ── Angle Valve Deco Round Handle 1/2"×3/8" ───────────────────────────
    (
        "440901510",
        "angle_valve",
        "VALV_ESCUADRA_DECO",
        "HIDROSANITARIO",
        'VALV.LATÓN ESC. "DECO"',
        "Angle Valve Deco",
        "brass",
        '1/2"',
        "PN10",
        "compression",
        '1/2"x3/8"',
        None,
        None,
        10.0,
        0.215,
        "84818099",
        'VALVULA ESCUADRA "DECO" MANDO REDONDO 1/2"X3/8"',
        {
            "alloy": ["CW617N"],
            "standards": ["DIN259", "ISO228/1", "UNEEN12165"],
            "end_connection": ["threaded", "compression"],
            "applications": ["water", "sanitary"],
            "materials": {"body": "brass", "handle": "chrome_brass"},
        },
        {"alto_mm": 125.0, "ancho_mm": 55.0, "fondo_mm": 40.0},
        {"ean_individual": "8435319127988", "ean_caja": "18435319127985", "units_per_box": 20},
        11.668800,
        32.99,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/2/4409-4409.jpg",
    ),
    # ── Ball Valve Inox 2pcs Flanged PN40 1 1/2" ──────────────────────────
    (
        "5128040",
        "ball_valve",
        "VALV_INOX_2PCS",
        "INDUSTRIAL",
        "VÁLVULAS INOXIDABLES-ESFERA",
        "Ball Valve SS 2-piece Flanged",
        "stainless_steel",
        '1 1/2"',
        "PN40",
        "flanged",
        "DN40",
        -30,
        180,
        40.0,
        5.930,
        "84818030",
        'VALVULA ESFERA INOX. BOLA A-316 2 PIEZAS PN40 1 1/2"',
        {
            "alloy": ["AISI316", "AISI304", "A351CF8M"],
            "standards": ["ANSI150", "API598", "API607", "ASME16.5", "EN1092", "ISO5211"],
            "end_connection": ["flanged"],
            "applications": ["industrial", "chemical", "oil_gas"],
            "materials": {
                "body": "AISI316",
                "ball": "AISI316",
                "stem": "AISI316",
                "seat": "PTFE",
                "seals": "PTFE",
            },
        },
        {"alto_mm": 310.0, "ancho_mm": 200.0, "fondo_mm": 155.0},
        {"ean_individual": "8435319126318", "ean_caja": "18435319126315", "units_per_box": 2},
        336.316695,
        941.69,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/8/5128-5128.jpg",
    ),
    # ── Ball Valve SS 2pcs Threaded F-F 1 1/2" ────────────────────────────
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
            "standards": ["DIN259", "ISO-7", "ISO228", "ISO5211", "ISO7-1"],
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
        {"ean_individual": "8435319117767", "ean_caja": "18435319117764", "units_per_box": 5},
        88.755810,
        248.52,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/1/0910.jpg",
    ),
    # ── Gate Valve Resilient Wedge Flanged DN50 ───────────────────────────
    (
        "5113050",
        "gate_valve",
        "VALV_COMPUERTA_FUND",
        "INDUSTRIAL",
        "VÁLVULAS FUNDICIÓN-COMPUERTAS",
        "Gate Valve Resilient Wedge",
        "ductile_iron",
        "DN50",
        "PN16",
        "flanged",
        "DN50",
        -10,
        80,
        16.0,
        9.400,
        "84818020",
        "VALVULA COMPUERTA C/BRIDAS, EJE FIJO C. ELASTICO EPDM DN50",
        {
            "alloy": [],
            "standards": ["EN1074-2", "ISO7259", "EN1092", "EN558"],
            "end_connection": ["flanged"],
            "applications": ["water_supply", "fire_protection"],
            "lining": "epoxy",
            "wedge_coating": "EPDM",
            "materials": {
                "body": "ductile_iron",
                "wedge": "ductile_iron+EPDM",
                "stem": "stainless_steel",
                "handwheel": "ductile_iron",
            },
        },
        {"alto_mm": 295.0, "ancho_mm": 195.0, "fondo_mm": 145.0},
        {"ean_individual": "8435319116647", "ean_caja": "18435319116644", "units_per_box": 1},
        177.146970,
        590.50,
        "https://d7rh5s3nxmpy4.cloudfront.net/CMP8164/5/5113-5113.jpg",
    ),
]

# ---------------------------------------------------------------------------
# TRANSLATIONS
# (sku, lang, name, description)
# ---------------------------------------------------------------------------
_TRANSLATIONS = {
    "4222015": {
        "es": (
            'VALVULA ESFERA EMPOTRAR H-H PN30 ROSCAR CARLA 1/2"',
            "Válvula esfera PN30 para empotrar conexión roscada. Latón CW617N. Aplicaciones agua potable.",
        ),
        "en": (
            "F-F PN30 LONG NECK THREADED BALL VALVE 'CARLA' TYPE 1/2\"",
            "Long neck ball valve PN30 threaded ends. Brass CW617N. Drinking water applications.",
        ),
        "fr": (
            'VANNE SPHÉRIQUE PN-30 MOD. "CARLA" ENCASTRABLE F-F 1/2"',
            "Robinet à boisseau sphérique PN30 encastrable à filetage. Laiton CW617N.",
        ),
        "de": (
            'SPÜLVENTIL PN-30 IG/IG "CARLA" 1/2"',
            "Einbau-Kugelventil PN30 Innengewinde. Messing CW617N. Trinkwasseranwendungen.",
        ),
        "it": (
            'VALV. SFERA DA INCASSARE F/F PN30 TIPO "CARLA" 1/2"',
            "Valvola a sfera da incassare PN30 filettata. Ottone CW617N. Acqua potabile.",
        ),
        "pt": (
            'VÁLVULA ESFERA ENCASTRAR F-F PN30 ROSCAR MODELO "CARLA" 1/2"',
            "Válvula de esfera encastrada PN30 roscada. Latão CW617N. Água potável.",
        ),
    },
    "4092040": {
        "es": (
            'VALVULA ESFERA PN25 H-H PALANCA ACERO CARBONO AZUL 1 1/2"',
            "Válvula de esfera PN25 paso total con palanca ergonómica azul de acero al carbono. Latón CW617N.",
        ),
        "en": (
            'F-F BRASS BALL VALVE PN-25 BLUE ERGONOMIC CARBON STEEL HANDLE 1 1/2"',
            "Full bore brass ball valve PN25 with blue ergonomic carbon steel handle. CW617N body.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE LAITON PN25 POIGNÉE BLEUE ERGONOMIQUE 1 1/2"',
            "Robinet à boisseau sphérique laiton alésage total PN25 avec poignée ergonomique bleue.",
        ),
        "de": (
            'KUGELVENTIL MESSING PN25 BLAUE ERGONOMISCHE GRIFF 1 1/2"',
            "Vollbohrungskugelventil Messing PN25 mit blauem ergonomischem Hebelgriff.",
        ),
        "it": (
            'VALVOLA A SFERA OTTONE PN25 MANICO ERGONOMICO BLU 1 1/2"',
            "Valvola a sfera piena passaggio ottone PN25 con manico ergonomico blu in acciaio.",
        ),
        "pt": (
            'VÁLVULA ESFERA LATÃO PN25 MANÍPULO ERGONÓMICO AZUL 1 1/2"',
            "Válvula de esfera latão passagem total PN25 com manípulo ergonómico azul.",
        ),
    },
    "4295040": {
        "es": (
            'VALVULA ESFERA PN30 H-H CON PALANCA INOXIDABLE ROJA 1 1/2"',
            "Válvula de esfera PN30 paso total palanca inoxidable roja. Latón CW617N. Agua y gas.",
        ),
        "en": (
            'F-F BRASS BALL VALVE PN30 FULL BORE RED STAINLESS STEEL HANDLE 1 1/2"',
            "Full bore brass ball valve PN30 with red stainless steel ergonomic handle.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE LAITON PN30 POIGNÉE INOX ROUGE 1 1/2"',
            "Robinet à boisseau sphérique PN30 alésage total avec poignée inox rouge.",
        ),
        "de": (
            'KUGELVENTIL MESSING PN30 ROTER EDELSTAHL HEBELGRIFF 1 1/2"',
            "Vollbohrungskugelventil Messing PN30 mit rotem Edelstahlhebelgriff.",
        ),
        "it": (
            'VALVOLA A SFERA OTTONE PN30 MANICO INOX ROSSO 1 1/2"',
            "Valvola a sfera ottone PN30 piena passaggio con manico ergonomico inox rosso.",
        ),
        "pt": (
            'VÁLVULA ESFERA LATÃO PN30 MANÍPULO INOX VERMELHO 1 1/2"',
            "Válvula de esfera latão PN30 passagem total com manípulo inox vermelho.",
        ),
    },
    "4091040": {
        "es": (
            'VALVULA ESFERA PN25 M-H PL. ACERO CARBONO AZUL 1 1/2"',
            "Válvula de esfera PN25 macho-hembra palanca ergonómica azul acero carbono. Latón CW617N.",
        ),
        "en": (
            'M-F BRASS BALL VALVE PN-25 BLUE ERGONOMIC CARBON STEEL HANDLE 1 1/2"',
            "Male-female full bore brass ball valve PN25 with blue ergonomic carbon steel handle.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE LAITON PN25 MF POIGNÉE BLEUE 1 1/2"',
            "Robinet à boisseau sphérique laiton PN25 mâle-femelle poignée ergonomique bleue.",
        ),
        "de": (
            'MF KUGELVENTIL MESSING PN25 BLAUE ERGONOMISCHE GRIFF 1 1/2"',
            "Außen-Innen Kugelventil Messing PN25 mit blauem ergonomischem Hebelgriff.",
        ),
        "it": (
            'VALVOLA A SFERA OTTONE PN25 MF MANICO BLU 1 1/2"',
            "Valvola a sfera ottone PN25 maschio-femmina con manico ergonomico blu.",
        ),
        "pt": (
            'VÁLVULA ESFERA LATÃO PN25 MF MANÍPULO AZUL 1 1/2"',
            "Válvula de esfera latão PN25 macho-fêmea com manípulo ergonómico azul.",
        ),
    },
    "4097015": {
        "es": (
            'VALVULA ESFERA PN30 M-H PALANCA ERG. INOXIDABLE ROJA 1/2"',
            "Válvula de esfera PN30 macho-hembra con palanca ergonómica inoxidable roja. Latón CW617N.",
        ),
        "en": (
            'M-F BALL VALVE PN-30 WITH STAINLESS STEEL RED HANDLE 1/2"',
            "Male-female brass ball valve PN30 with ergonomic red stainless steel handle.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE LAITON PN30 MF POIGNÉE INOX ROUGE 1/2"',
            "Robinet à boisseau sphérique laiton PN30 mâle-femelle avec poignée inox rouge.",
        ),
        "de": (
            'MF KUGELVENTIL MESSING PN30 ROTER EDELSTAHL GRIFF 1/2"',
            "Außen-Innen Kugelventil Messing PN30 mit rotem Edelstahlhebelgriff.",
        ),
        "it": (
            'VALVOLA A SFERA OTTONE PN30 MF MANICO INOX ROSSO 1/2"',
            "Valvola a sfera ottone PN30 maschio-femmina con manico inox rosso.",
        ),
        "pt": (
            'VÁLVULA ESFERA LATÃO PN30 MF MANÍPULO INOX VERMELHO 1/2"',
            "Válvula de esfera latão PN30 macho-fêmea com manípulo inox vermelho.",
        ),
    },
    "4102015": {
        "es": (
            'VALVULA ESFERA PN30 H-H, MANDO PALOMILLA ROJA 1/2"',
            "Válvula de esfera PN30 paso total con mando palomilla roja. Latón CW617N.",
        ),
        "en": (
            'F-F BRASS BALL VALVE PN-30 FULL BORE WITH RED BUTTERFLY HANDLE 1/2"',
            "Full bore brass ball valve PN30 with red butterfly handle. Ideal for confined spaces.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE LAITON PN30 PAPILLON ROUGE 1/2"',
            "Robinet à boisseau sphérique laiton PN30 plein alésage avec poignée papillon rouge.",
        ),
        "de": (
            'KUGELVENTIL MESSING PN30 ROTES FLÜGELGRIFF 1/2"',
            "Vollbohrungskugelventil Messing PN30 mit rotem Flügelgriff.",
        ),
        "it": (
            'VALVOLA A SFERA OTTONE PN30 FARFALLA ROSSA 1/2"',
            "Valvola a sfera ottone PN30 piena passaggio con leva farfalla rossa.",
        ),
        "pt": (
            'VÁLVULA ESFERA LATÃO PN30 BORBOLETA VERMELHA 1/2"',
            "Válvula de esfera latão PN30 passagem total com manípulo borboleta vermelho.",
        ),
    },
    "4113015": {
        "es": (
            'VALVULA COMPUERTA PN10 PASO STANDAR H-H 1/2"',
            "Válvula de compuerta latón PN10 paso estándar conexión roscada. Agua fría y caliente.",
        ),
        "en": (
            'F-F GATE VALVE PN10 STANDARD FLOW 1/2"',
            "Female-female brass gate valve PN10 standard flow. Threaded connection. Water applications.",
        ),
        "fr": (
            'VANNE-PORTE LAITON PN10 PASSAGE STANDARD FF 1/2"',
            "Vanne-porte laiton PN10 passage standard femelle-femelle filetée.",
        ),
        "de": (
            'ABSPERRSCHIEBER MESSING PN10 STANDARD FF 1/2"',
            "Absperrschieber Messing PN10 Standardbohrung Innengewinde beidseitig.",
        ),
        "it": (
            'VALVOLA A SARACINESCA OTTONE PN10 PASSAGGIO STANDARD FF 1/2"',
            "Valvola a saracinesca ottone PN10 passaggio standard femmina-femmina filettata.",
        ),
        "pt": (
            'VÁLVULA DE GAVETA LATÃO PN10 PASSAGEM STANDARD FF 1/2"',
            "Válvula de gaveta latão PN10 passagem padrão fêmea-fêmea roscada.",
        ),
    },
    "4215040": {
        "es": (
            'VALVULA RETENCION LIGERA OBTURADOR METALICO H-H 1 1/2"',
            "Válvula de retención ligera con obturador metálico conexión roscada. Latón CW617N. PN25.",
        ),
        "en": (
            'F-F NON RETURN VALVE LIGHT TYPE WITH METAL SHUTTER 1 1/2"',
            "Light non-return valve with metal shutter female-female threaded connection. Brass CW617N.",
        ),
        "fr": (
            'CLAPET DE RETENUE LÉGER OBTURATEUR MÉTALLIQUE FF 1 1/2"',
            "Clapet de retenue léger type simple avec obturateur métallique en laiton.",
        ),
        "de": (
            'LEICHTES RÜCKSCHLAGVENTIL METALLSCHEIBE FF 1 1/2"',
            "Leichtes Rückschlagventil mit Metallscheibe Innengewinde. Messing CW617N.",
        ),
        "it": (
            'VALVOLA DI RITEGNO LEGGERA OTTURATORE METALLICO FF 1 1/2"',
            "Valvola di ritegno leggera tipo semplice con otturatore metallico filettata.",
        ),
        "pt": (
            'VÁLVULA DE RETENÇÃO LIGEIRA OBTURADOR METÁLICO FF 1 1/2"',
            "Válvula de retenção ligeira com obturador metálico rosca fêmea-fêmea.",
        ),
    },
    "440901510": {
        "es": (
            'VALVULA ESCUADRA "DECO" MANDO REDONDO 1/2"X3/8"',
            "Válvula escuadra línea Deco con mando redondo cromado. Latón CW617N. Baño y cocina.",
        ),
        "en": (
            'ANGLE VALVE "DECO" ROUND HANDLE 1/2"X3/8"',
            "Deco line angle valve with round chrome handle. Brass CW617N. Bathroom and kitchen.",
        ),
        "fr": (
            'VANNE D\'ANGLE "DECO" POIGNÉE RONDE 1/2"X3/8"',
            "Vanne d'angle ligne Deco avec poignée ronde chromée. Laiton CW617N. Salle de bain.",
        ),
        "de": (
            'ECKVENTIL "DECO" RUNDER GRIFF 1/2"X3/8"',
            "Eckventil Deco-Linie mit rundem verchromtem Griff. Messing CW617N. Bad und Küche.",
        ),
        "it": (
            'VALVOLA ANGOLARE "DECO" MANIGLIA TONDA 1/2"X3/8"',
            "Valvola angolare linea Deco con maniglia tonda cromata. Ottone CW617N. Bagno.",
        ),
        "pt": (
            'VÁLVULA ANGULAR "DECO" MANÍPULO REDONDO 1/2"X3/8"',
            "Válvula angular linha Deco com manípulo redondo cromado. Latão CW617N. WC.",
        ),
    },
    "5128040": {
        "es": (
            'VALVULA ESFERA INOX. BOLA A-316 2 PIEZAS PN40 1 1/2"',
            "Válvula de esfera inoxidable AISI 316 2 piezas bridada PN40. Uso industrial y químico.",
        ),
        "en": (
            'TWO PIECES BALL VALVE S.S. FLANGED END PN40 1 1/2"',
            "Two-piece stainless steel AISI 316 ball valve with flanged ends PN40. Industrial use.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE 2 PIÈCES INOX BRIDES PN40 1 1/2"',
            "Robinet à boisseau sphérique 2 pièces inox AISI 316 brides PN40. Usage industriel.",
        ),
        "de": (
            '2-TEILIGES KUGELVENTIL EDELSTAHL FLANSCH PN40 1 1/2"',
            "2-teiliges Kugelventil Edelstahl AISI316 mit Flanschenden PN40. Industrie.",
        ),
        "it": (
            'VALVOLA A SFERA 2 PEZZI INOX FLANGIATA PN40 1 1/2"',
            "Valvola a sfera 2 pezzi acciaio inox AISI316 con attacchi flangiati PN40.",
        ),
        "pt": (
            'VÁLVULA ESFERA 2 PEÇAS INOX FLANGEADA PN40 1 1/2"',
            "Válvula de esfera 2 peças aço inoxidável AISI316 com extremidades flangeadas PN40.",
        ),
    },
    "0910040": {
        "es": (
            'VALVULA INOX. DE DOS PIEZAS ROSCAR H-H 1 1/2" PALANCA AZUL',
            "Válvula de esfera inoxidable 2 piezas paso total conexión roscada. AISI 316. PN63.",
        ),
        "en": (
            'F-F BALL VALVE STAINLESS STEEL 2 PCS THREADED END FULL BORE 1 1/2"',
            "Two-piece full bore stainless steel ball valve with threaded ends. AISI 316. PN63.",
        ),
        "fr": (
            'ROBINET SPHÉRIQUE INOX 2 PIÈCES FILETAGE PLEIN ALÉSAGE 1 1/2"',
            "Robinet à boisseau sphérique 2 pièces inox AISI316 fileté plein alésage. PN63.",
        ),
        "de": (
            '2-TEILIGES EDELSTAHL KUGELVENTIL GEWINDE VOLLBOHRUNG 1 1/2"',
            "2-teiliges Edelstahl AISI316 Kugelventil mit Innengewinde Vollbohrung. PN63.",
        ),
        "it": (
            'VALVOLA A SFERA INOX 2 PEZZI FILETTATA PIENA PASSAGGIO 1 1/2"',
            "Valvola a sfera 2 pezzi acciaio inox AISI316 filettata piena passaggio. PN63.",
        ),
        "pt": (
            'VÁLVULA ESFERA INOX 2 PEÇAS ROSCADA PASSAGEM TOTAL 1 1/2"',
            "Válvula de esfera 2 peças aço inox AISI316 roscada passagem total. PN63.",
        ),
    },
    "5113050": {
        "es": (
            "VALVULA COMPUERTA C/BRIDAS, EJE FIJO C. ELASTICO EPDM DN50",
            "Válvula de compuerta de fundición dúctil PN16 con cuña elástica EPDM y bridas DN50.",
        ),
        "en": (
            "EPDM RESILIENT WEDGE GATE VALVE, FLANGED ENDS DN 50",
            "Ductile iron gate valve PN16 with EPDM resilient wedge and flanged ends DN50.",
        ),
        "fr": (
            "VANNE-PORTE FONTE DUCTILE SIÈGE ÉLASTOMÈRE EPDM BRIDES DN50",
            "Vanne-porte corps fonte ductile PN16 avec siège élastomère EPDM et brides DN50.",
        ),
        "de": (
            "ABSPERRSCHIEBER DUKTILES GUSSEISEN EPDM KEIL FLANSCH DN50",
            "Absperrschieber aus duktilem Gusseisen PN16 mit EPDM-Weichgummi-Keil und Flanschen.",
        ),
        "it": (
            "SARACINESCA GHISA DUTTILE CUNEO ELASTICO EPDM FLANGIATE DN50",
            "Valvola a saracinesca ghisa duttile PN16 con cuneo elastomero EPDM bridato DN50.",
        ),
        "pt": (
            "VÁLVULA DE GAVETA FERRO FUNDIDO CUNHA ELÁSTICA EPDM FLANGEADA DN50",
            "Válvula de gaveta ferro fundido dúctil PN16 cunha elástica EPDM extremidades flangeadas.",
        ),
    },
}

# ---------------------------------------------------------------------------
# MATCH CANDIDATES — competidores reales del Run Kit (Amazon UAE)
# (sku, asin, title, price_aed, score, kind)
# ---------------------------------------------------------------------------
_COMPETITORS = {
    "4222015": [
        (
            "B0D9JY2KT5",
            "Azonee Ball Valve, 3Pcs 1/2 Inch Brass Mini Ball Valve Shut Off Switch, 1/2 Inch Male x Female NPT Thread",
            45.00,
            95,
            "peer",
        ),
        (
            "B0GS6QP2Z9",
            "TOPINCN Thickened Brass Female Male Threaded Ball Valve Wear-Resistant Shut Off Switch 1/2in 3Pcs",
            60.26,
            95,
            "peer",
        ),
    ],
    "4092040": [
        (
            "B09WXQ4KJZ",
            "Abest 1-1/2 Inch Full Port Ball Valve Brass Heavy Duty Lever Handle 600 WOG",
            61.02,
            55,
            "peer",
        ),
    ],
    "4295040": [
        (
            "B08FHQGCPR",
            "SISCO Full Port Ball Valve 1.5 Inch NPT Brass Red Lever Handle Industrial",
            67.49,
            85,
            "peer",
        ),
    ],
    "4091040": [
        (
            "B09WXQ4KJZ",
            "Abest 1-1/2 Inch Full Port Ball Valve Brass Heavy Duty Lever Handle 600 WOG",
            61.02,
            55,
            "peer",
        ),
    ],
    "4097015": [
        (
            "B0C1NKG8PR",
            "GFHD 1/2 Inch NPT Brass Ball Valve Full Port Red Stainless Steel Handle 200 PSI",
            32.50,
            85,
            "peer",
        ),
    ],
    "4102015": [
        (
            "B08K2LJNK7",
            "Midline Valve 1/2 Inch Ball Valve Butterfly Handle Full Port Lead Free Brass",
            28.90,
            90,
            "peer",
        ),
    ],
    "4113015": [
        (
            "B07K3QMHXV",
            "MUHIZE 1/2 Inch Gate Valve NPT Heavy Duty Forged Brass Renewable Seal",
            35.00,
            90,
            "peer",
        ),
    ],
    "4215040": [
        (
            "B09PQRKGL2",
            "Watts 1.5 Inch Check Valve Water Swing Non Return Full Port Brass Lead Free",
            129.19,
            53,
            "peer",
        ),
    ],
    "440901510": [
        (
            "B0BTPH6KPL",
            "Acorn Controls 1/2 x 3/8 Inch Straight Valve Chrome Compression x OD",
            29.99,
            93,
            "peer",
        ),
    ],
    "5128040": [
        (
            "B07RCW2TMB",
            "Valworx 1-1/2 inch Stainless Steel Ball Valve Flanged Full Port ANSI Class 150",
            123.50,
            85,
            "peer",
        ),
    ],
    "0910040": [
        (
            "B09T64MXBF",
            "VEVOR Stainless Steel Ball Valve 1-1/2 Inch 2-Piece Full Port NPT 1000 WOG",
            154.63,
            98,
            "peer",
        ),
    ],
    "5113050": [
        (
            "B0BKLM7KW2",
            "Nibco T-113 Series Gate Valve Flanged Ends DN50 Ductile Iron PN16 Water",
            245.00,
            73,
            "peer",
        ),
    ],
}

# ---------------------------------------------------------------------------
# PURCHASE ORDER SCENARIOS
# ---------------------------------------------------------------------------

# PO-001: RECEIVED — 4 SKUs, recepción completa procesada
_PO001_LINES = [
    # (sku, qty_ordered, qty_received, unit_price_aed, landed_cost_breakdown)
    (
        "4222015",
        100,
        100,
        13.163865,
        {"fob": 8.56, "freight": 2.37, "customs": 1.45, "fba_fees": 0.78},
    ),
    (
        "4092040",
        50,
        50,
        39.783315,
        {"fob": 25.86, "freight": 7.16, "customs": 4.38, "fba_fees": 2.37},
    ),
    (
        "4097015",
        200,
        200,
        9.553830,
        {"fob": 6.21, "freight": 1.72, "customs": 1.05, "fba_fees": 0.57},
    ),
    (
        "4113015",
        150,
        150,
        8.423415,
        {"fob": 5.48, "freight": 1.52, "customs": 0.93, "fba_fees": 0.50},
    ),
]

# PO-002: PARTIAL — 3 SKUs, 1 recibido parcial (15/30), 2 en tránsito
_PO002_LINES = [
    # (sku, qty_ordered, qty_received, unit_price_aed, landed_cost_breakdown)
    (
        "4295040",
        80,
        0,
        58.088745,
        {"fob": 37.76, "freight": 10.46, "customs": 6.39, "fba_fees": 3.47},
    ),
    (
        "5128040",
        30,
        15,
        336.316695,
        {"fob": 218.61, "freight": 60.54, "customs": 37.02, "fba_fees": 20.16},
    ),
    (
        "0910040",
        60,
        0,
        88.755810,
        {"fob": 57.69, "freight": 15.98, "customs": 9.76, "fba_fees": 5.31},
    ),
]

# PO-003: DRAFT — 4 SKUs, sin recepciones (pendiente de aprobación)
_PO003_LINES = [
    (
        "5113050",
        20,
        0,
        177.146970,
        {"fob": 115.15, "freight": 31.89, "customs": 19.49, "fba_fees": 0.00},
    ),
    (
        "4215040",
        100,
        0,
        33.000825,
        {"fob": 21.45, "freight": 5.94, "customs": 3.63, "fba_fees": 1.97},
    ),
    (
        "440901510",
        200,
        0,
        11.668800,
        {"fob": 7.58, "freight": 2.10, "customs": 1.28, "fba_fees": 0.70},
    ),
    (
        "4102015",
        300,
        0,
        10.720710,
        {"fob": 6.97, "freight": 1.93, "customs": 1.18, "fba_fees": 0.64},
    ),
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _j(obj: object) -> str:
    """Serializa a JSON SQL-safe (escapa comillas simples)."""
    return json.dumps(obj, ensure_ascii=False).replace("'", "''")


def upgrade() -> None:
    bind = op.get_bind()

    # =======================================================================
    # 0. Fix cdc_emit_product — referencias a columnas ya eliminadas (065/066)
    # =======================================================================
    bind.execute(
        text("""
        CREATE OR REPLACE FUNCTION cdc_emit_product()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $fn$
        DECLARE
            v_action    TEXT;
            v_entity_id TEXT;
            v_payload   JSONB;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_action    := 'delete';
                v_entity_id := OLD.sku;
                v_payload   := jsonb_build_object('sku', OLD.sku);
            ELSE
                IF TG_OP = 'INSERT' THEN v_action := 'insert';
                ELSE v_action := 'update';
                END IF;
                v_entity_id := NEW.sku;
                v_payload   := jsonb_build_object(
                    'sku',        NEW.sku,
                    'family',     NEW.family,
                    'subfamily',  NEW.subfamily,
                    'type',       NEW.type,
                    'material',   NEW.material,
                    'dn',         NEW.dn,
                    'pn',         NEW.pn,
                    'connection', NEW.connection,
                    'brand',      NEW.brand
                );
            END IF;
            INSERT INTO cdc_events (entity_type, entity_id, action, payload_jsonb)
            VALUES ('product', v_entity_id, v_action, v_payload);
            PERFORM pg_notify('cdc_events', json_build_object(
                'entity_type', 'product',
                'entity_id',   v_entity_id,
                'action',      v_action
            )::text);
            RETURN COALESCE(NEW, OLD);
        END;
        $fn$
    """)
    )

    # =======================================================================
    # 0b. Extender ck_translations_lang para idiomas europeos MT
    #     (inicial solo era es/ar/en — añadimos fr/de/it/pt)
    # =======================================================================
    bind.execute(
        text("""
        ALTER TABLE product_translations
            DROP CONSTRAINT IF EXISTS ck_translations_lang;
        ALTER TABLE product_translations
            ADD CONSTRAINT ck_translations_lang
            CHECK (lang IN ('es','ar','en','fr','de','it','pt'));
    """)
    )

    # =======================================================================
    # 1. TRUNCATE datos de negocio — orden respeta FKs
    # =======================================================================
    truncate_order = [
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
    ]
    for tbl in truncate_order:
        bind.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))

    # =======================================================================
    # 2. MASTER DATA — brand MT + familias + subfamilias + supplier
    # =======================================================================

    # Brand
    bind.execute(
        text("""
        INSERT INTO brands (code, name, active)
        VALUES ('MT', 'MT Middle East', true)
        ON CONFLICT (code) DO NOTHING
    """)
    )

    # Families
    for fcode, fname, fdesc, fsort in [
        ("ball_valve", "Ball Valves", "Válvulas de esfera latón e inoxidable", 1),
        ("gate_valve", "Gate Valves", "Válvulas de compuerta latón y fundición", 2),
        ("check_valve", "Check Valves", "Válvulas de retención y antiretorno", 3),
        ("angle_valve", "Angle Valves", "Válvulas escuadra para baño y cocina", 4),
    ]:
        bind.execute(
            text("""
            INSERT INTO families (code, name, description, sort_order, active)
            VALUES (:c, :n, :d, :s, true)
            ON CONFLICT (code) DO NOTHING
        """),
            {"c": fcode, "n": fname, "d": fdesc, "s": fsort},
        )

    # Subfamilies
    for fam_code, sub_code, sub_name, sub_sort in [
        ("ball_valve", "VALV_LATON_PN30", "Ball Valves PN30 Brass", 1),
        ("ball_valve", "VALV_LATON_PN25", "Ball Valves PN25 Brass", 2),
        ("ball_valve", "VALV_INOX_2PCS", "Ball Valves SS 2-piece", 3),
        ("gate_valve", "VALV_COMPUERTA_LATON", "Gate Valves Brass", 1),
        ("gate_valve", "VALV_COMPUERTA_FUND", "Gate Valves Cast Iron", 2),
        ("check_valve", "VALV_RETENCION_LATON", "Check Valves Brass", 1),
        ("angle_valve", "VALV_ESCUADRA_DECO", "Angle Valves Deco", 1),
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

    # Supplier
    bind.execute(
        text("""
        INSERT INTO suppliers (code, name, contact_email, contact_phone,
                               contract_currency, lead_time_days, payment_terms, active)
        VALUES ('mt_spain', 'MT Spain S.A.', 'orders@mtspain.net', '+34 93 555 0001',
                'EUR', 21, 'Net 60 días', true)
        ON CONFLICT (code) DO NOTHING
    """)
    )

    # =======================================================================
    # 3. PRODUCTS
    # =======================================================================
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

    # =======================================================================
    # 4. PRODUCT TRANSLATIONS (ES / EN / FR / DE / IT / PT)
    # =======================================================================
    for sku, langs in _TRANSLATIONS.items():
        for lang, (name, desc) in langs.items():
            name_sql = name.replace("'", "''")
            desc_sql = desc.replace("'", "''")
            bind.execute(
                text(f"""
                INSERT INTO product_translations (sku, lang, name, description, status)
                VALUES ('{sku}', '{lang}', '{name_sql}', '{desc_sql}', 'approved')
                ON CONFLICT (sku, lang) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    status = 'approved'
            """)
            )

    # =======================================================================
    # 5. PRODUCT ASSETS (imagen principal — kind='external_url', bucket product-images)
    # =======================================================================
    for sku, *_, image_url in _PRODUCTS:
        if not image_url or image_url == "nan":
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

    # =======================================================================
    # 6. COSTS — FBA y DIRECT_B2C por producto
    # =======================================================================
    for sku, *_, coste_aed, pvp_aed, __ in _PRODUCTS:
        fob = round(coste_aed * 0.65, 4)
        freight = round(coste_aed * 0.15, 4)
        customs = round(coste_aed * 0.12, 4)
        fba_fees = round(coste_aed * 0.08, 4)
        marketing = round(coste_aed * 0.10, 4)

        breakdown_fba = _j(
            {"fob": fob, "freight": freight, "customs": customs, "fba_fees": fba_fees}
        )
        breakdown_b2c = _j(
            {
                "fob": fob,
                "freight": freight,
                "customs": customs,
                "payment_fees": round(coste_aed * 0.02, 4),
                "marketing": marketing,
            }
        )

        bind.execute(
            text(f"""
            INSERT INTO costs
                (sku, scheme_code, supplier_code, breakdown, currency_origin, effective_at)
            VALUES
                ('{sku}', 'FBA', 'mt_spain', '{breakdown_fba}'::jsonb, 'AED',
                 '2026-04-01 00:00:00+00'),
                ('{sku}', 'DIRECT_B2C', 'mt_spain', '{breakdown_b2c}'::jsonb,
                 'AED', '2026-04-01 00:00:00+00')
            ON CONFLICT DO NOTHING
        """)
        )

    # =======================================================================
    # 7. PRICES — canal amazon_uae
    #    • 9 approved  • 2 pending_review (margin < threshold)  • 1 historial rejected
    # =======================================================================
    # Seed bypasses the initial-status trigger (prices_initial_status_trg).
    bind.execute(text("ALTER TABLE prices DISABLE TRIGGER prices_initial_status_trg;"))

    # SKUs con pending_review (margen comprimido — precio muy cercano al costo)
    _PENDING_SKUS = {"4092040", "4295040"}
    # SKU con historial rejected (5113050 — precio rechazado, luego ajustado)
    _REJECTED_SKU = "5113050"

    for sku, *_, coste_aed, pvp_aed, __ in _PRODUCTS:
        margin = round((pvp_aed - coste_aed) / pvp_aed * 100, 4) if pvp_aed > 0 else 0
        breakdown = _j(
            {"cost": coste_aed, "target_pvp": pvp_aed, "margin_pct": margin, "scheme": "FBA"}
        )

        if sku in _PENDING_SKUS:
            status = "pending_review"
        else:
            status = "approved"

        bind.execute(
            text(f"""
            INSERT INTO prices
                (product_sku, channel_id, scheme_code, amount, margin_pct,
                 currency, status, breakdown, valid_from)
            SELECT
                '{sku}',
                c.id,
                'FBA',
                {pvp_aed},
                {margin},
                'AED',
                '{status}',
                '{breakdown}'::jsonb,
                '2026-04-15 00:00:00+00'
            FROM channels c WHERE c.code = 'amazon_uae'
            ON CONFLICT DO NOTHING
        """)
        )

    # Precio rechazado para 5113050 (draft → pending_review → rejected)
    bind.execute(
        text(f"""
        INSERT INTO prices
            (product_sku, channel_id, scheme_code, amount, margin_pct,
             currency, status, breakdown, rejection_reason, valid_from)
        SELECT
            '5113050',
            c.id,
            'FBA',
            450.00,
            23.7736,
            'AED',
            'rejected',
            '{_j({"cost": 177.15, "target_pvp": 450.0, "margin_pct": 23.77, "scheme": "FBA", "note": "Primer intento — precio demasiado bajo para canal FBA"})}'::jsonb,
            'Margen insuficiente para cubrir comisiones FBA y campaña. Precio mínimo requerido: 590 AED.',
            '2026-04-10 00:00:00+00'
        FROM channels c WHERE c.code = 'amazon_uae'
        ON CONFLICT DO NOTHING
    """)
    )

    # Precio aprobado definitivo para 5113050
    bind.execute(
        text(f"""
        INSERT INTO prices
            (product_sku, channel_id, scheme_code, amount, margin_pct,
             currency, status, breakdown, valid_from)
        SELECT
            '5113050',
            c.id,
            'FBA',
            590.50,
            70.0114,
            'AED',
            'approved',
            '{_j({"cost": 177.15, "target_pvp": 590.50, "margin_pct": 70.01, "scheme": "FBA"})}'::jsonb,
            '2026-04-20 00:00:00+00'
        FROM channels c WHERE c.code = 'amazon_uae'
        ON CONFLICT DO NOTHING
    """)
    )

    bind.execute(text("ALTER TABLE prices ENABLE TRIGGER prices_initial_status_trg;"))

    # =======================================================================
    # 8. MATCH CANDIDATES — competidores Amazon reales
    # =======================================================================
    for sku, cands in _COMPETITORS.items():
        for asin, title, price_aed, score, kind in cands:
            title_sql = title.replace("'", "''")
            bind.execute(
                text(f"""
                INSERT INTO match_candidates
                    (product_sku, channel, external_id, title, price_aed, score, kind, status)
                VALUES
                    ('{sku}', 'amazon_uae', '{asin}', '{title_sql}', {price_aed}, {score},
                     '{kind}', 'pending')
                ON CONFLICT (product_sku, channel, external_id) DO NOTHING
            """)
            )

    # =======================================================================
    # 9. PURCHASE ORDERS + LÍNEAS + GOODS RECEIPTS + COST LOTS + POSICIONES
    # =======================================================================

    # — PO-001: RECEIVED ——————————————————————————————————————————————————
    bind.execute(
        text("""
        INSERT INTO purchase_orders
            (po_number, supplier_code, status, currency, notes, confirmed_at)
        VALUES
            ('MT-PO-2026-001', 'mt_spain', 'received', 'EUR',
             'Primera compra muestra — recepción completa Dubai Warehouse',
             '2026-04-10 09:00:00+04')
        ON CONFLICT (po_number) DO NOTHING
    """)
    )

    po1_id = bind.execute(
        text("SELECT id FROM purchase_orders WHERE po_number = 'MT-PO-2026-001'")
    ).scalar()

    fx_id = bind.execute(
        text(
            "SELECT id FROM fx_rates WHERE from_currency='EUR' AND to_currency='AED' "
            "AND effective_to IS NULL ORDER BY effective_from DESC LIMIT 1"
        )
    ).scalar()

    for sku, qty_ord, qty_rec, unit_price, breakdown in _PO001_LINES:
        landed_sql = _j(breakdown)
        # Insert línea
        bind.execute(
            text(f"""
            INSERT INTO purchase_order_lines
                (po_id, sku, scheme_code, qty_ordered, qty_received,
                 unit_price, landed_cost_breakdown)
            VALUES
                ('{po1_id}', '{sku}', 'FBA', {qty_ord}, {qty_rec},
                 {unit_price}, '{landed_sql}'::jsonb)
        """)
        )
        pol_id = bind.execute(
            text(f"SELECT id FROM purchase_order_lines WHERE po_id='{po1_id}' AND sku='{sku}'")
        ).scalar()

        unit_cost_aed = round(unit_price * 4.29, 4)  # EUR→AED al FX 4.29

        # Goods receipt
        actual_breakdown = _j({k: round(v * 4.29, 4) for k, v in breakdown.items()})
        bind.execute(
            text(f"""
            INSERT INTO goods_receipts
                (po_line_id, qty_received, received_at, actual_unit_price,
                 actual_breakdown, map_before, map_after, fx_rate_id, status, processed_at)
            VALUES
                ('{pol_id}', {qty_rec}, '2026-04-25 08:00:00+04', {unit_cost_aed},
                 '{actual_breakdown}'::jsonb,
                 0, {unit_cost_aed},
                 {"NULL" if not fx_id else f"'{fx_id}'"},
                 'processed', '2026-04-25 09:30:00+04')
        """)
        )
        gr_id = bind.execute(
            text(f"SELECT id FROM goods_receipts WHERE po_line_id='{pol_id}' LIMIT 1")
        ).scalar()

        # Cost lot (qty_remaining = qty_original — todo disponible)
        bind.execute(
            text(f"""
            INSERT INTO cost_lots
                (sku, supplier_code, scheme_code, gr_id,
                 qty_original, qty_remaining, unit_cost_aed, effective_at)
            VALUES
                ('{sku}', 'mt_spain', 'FBA', '{gr_id}',
                 {qty_rec}, {qty_rec}, {unit_cost_aed}, '2026-04-25 09:30:00+04')
        """)
        )

        # Inventory position
        bind.execute(
            text(f"""
            INSERT INTO inventory_positions
                (sku, supplier_code, scheme_code, qty_on_hand, map_aed, last_gr_id, last_updated_at)
            VALUES
                ('{sku}', 'mt_spain', 'FBA', {qty_rec}, {unit_cost_aed}, '{gr_id}',
                 '2026-04-25 09:30:00+04')
            ON CONFLICT (sku, supplier_code, scheme_code) DO UPDATE SET
                qty_on_hand = EXCLUDED.qty_on_hand,
                map_aed = EXCLUDED.map_aed,
                last_gr_id = EXCLUDED.last_gr_id,
                last_updated_at = EXCLUDED.last_updated_at
        """)
        )

    # — PO-002: PARTIAL ——————————————————————————————————————————————————
    bind.execute(
        text("""
        INSERT INTO purchase_orders
            (po_number, supplier_code, status, currency, notes, confirmed_at)
        VALUES
            ('MT-PO-2026-002', 'mt_spain', 'partial', 'EUR',
             'Pedido en tránsito — recepción parcial (5128040 recibido 50%)',
             '2026-05-01 10:00:00+04')
        ON CONFLICT (po_number) DO NOTHING
    """)
    )

    po2_id = bind.execute(
        text("SELECT id FROM purchase_orders WHERE po_number = 'MT-PO-2026-002'")
    ).scalar()

    for sku, qty_ord, qty_rec, unit_price, breakdown in _PO002_LINES:
        landed_sql = _j(breakdown)
        bind.execute(
            text(f"""
            INSERT INTO purchase_order_lines
                (po_id, sku, scheme_code, qty_ordered, qty_received,
                 unit_price, landed_cost_breakdown)
            VALUES
                ('{po2_id}', '{sku}', 'FBA', {qty_ord}, {qty_rec},
                 {unit_price}, '{landed_sql}'::jsonb)
        """)
        )

        # Solo 5128040 tiene GR parcial
        if qty_rec > 0:
            pol_id = bind.execute(
                text(f"SELECT id FROM purchase_order_lines WHERE po_id='{po2_id}' AND sku='{sku}'")
            ).scalar()

            unit_cost_aed = round(unit_price * 4.29, 4)
            actual_breakdown = _j({k: round(v * 4.29, 4) for k, v in breakdown.items()})

            bind.execute(
                text(f"""
                INSERT INTO goods_receipts
                    (po_line_id, qty_received, received_at, actual_unit_price,
                     actual_breakdown, map_before, map_after, fx_rate_id, status, processed_at,
                     notes)
                VALUES
                    ('{pol_id}', {qty_rec}, '2026-05-10 11:00:00+04', {unit_cost_aed},
                     '{actual_breakdown}'::jsonb,
                     0, {unit_cost_aed},
                     {"NULL" if not fx_id else f"'{fx_id}'"},
                     'processed', '2026-05-10 12:00:00+04',
                     'Recepción parcial — 15 unidades de 30 pedidas. Resto en tránsito.')
            """)
            )
            gr_id = bind.execute(
                text(f"SELECT id FROM goods_receipts WHERE po_line_id='{pol_id}' LIMIT 1")
            ).scalar()

            bind.execute(
                text(f"""
                INSERT INTO cost_lots
                    (sku, supplier_code, scheme_code, gr_id,
                     qty_original, qty_remaining, unit_cost_aed, effective_at)
                VALUES
                    ('{sku}', 'mt_spain', 'FBA', '{gr_id}',
                     {qty_rec}, {qty_rec}, {unit_cost_aed}, '2026-05-10 12:00:00+04')
            """)
            )

            bind.execute(
                text(f"""
                INSERT INTO inventory_positions
                    (sku, supplier_code, scheme_code, qty_on_hand, map_aed,
                     last_gr_id, last_updated_at)
                VALUES
                    ('{sku}', 'mt_spain', 'FBA', {qty_rec}, {unit_cost_aed},
                     '{gr_id}', '2026-05-10 12:00:00+04')
                ON CONFLICT (sku, supplier_code, scheme_code) DO UPDATE SET
                    qty_on_hand = EXCLUDED.qty_on_hand,
                    map_aed = EXCLUDED.map_aed,
                    last_gr_id = EXCLUDED.last_gr_id,
                    last_updated_at = EXCLUDED.last_updated_at
            """)
            )

    # — PO-003: DRAFT ————————————————————————————————————————————————————
    bind.execute(
        text("""
        INSERT INTO purchase_orders
            (po_number, supplier_code, status, currency, notes)
        VALUES
            ('MT-PO-2026-003', 'mt_spain', 'draft', 'EUR',
             'Reabastecimiento Q2 — pendiente aprobación dirección comercial')
        ON CONFLICT (po_number) DO NOTHING
    """)
    )

    po3_id = bind.execute(
        text("SELECT id FROM purchase_orders WHERE po_number = 'MT-PO-2026-003'")
    ).scalar()

    for sku, qty_ord, qty_rec, unit_price, breakdown in _PO003_LINES:
        landed_sql = _j(breakdown)
        bind.execute(
            text(f"""
            INSERT INTO purchase_order_lines
                (po_id, sku, scheme_code, qty_ordered, qty_received,
                 unit_price, landed_cost_breakdown)
            VALUES
                ('{po3_id}', '{sku}', 'FBA', {qty_ord}, {qty_rec},
                 {unit_price}, '{landed_sql}'::jsonb)
        """)
        )

    print(
        "[mig 100] Demo sample seed completado:\n"
        "  ✓ 12 productos insertados con datos completos\n"
        "  ✓ 72 traducciones (6 idiomas × 12 SKUs)\n"
        "  ✓ 12 imágenes reales del PIM\n"
        "  ✓ 24 registros de costos (FBA + DIRECT_B2C)\n"
        "  ✓ 13 precios (9 approved, 2 pending_review, 1 rejected + 1 aprobado revisado)\n"
        "  ✓ 13 match_candidates (competidores Amazon reales)\n"
        "  ✓ 3 POs: MT-PO-2026-001 received / 002 partial / 003 draft\n"
        "  ✓ 4 goods receipts + cost lots + inventory positions"
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Eliminar los POs de demo (cascada a líneas, GRs, lots, posiciones)
    bind.execute(
        text("""
        DELETE FROM purchase_orders
        WHERE po_number IN ('MT-PO-2026-001', 'MT-PO-2026-002', 'MT-PO-2026-003')
    """)
    )

    # Eliminar productos de demo (cascada a traducciones, assets, costs, prices, candidates)
    demo_skus = [p[0] for p in _PRODUCTS]
    skus_sql = ", ".join(f"'{s}'" for s in demo_skus)
    bind.execute(text(f"DELETE FROM products WHERE sku IN ({skus_sql})"))

    # Limpiar master data si no hay otros productos que la usen
    for fcode in ["ball_valve", "gate_valve", "check_valve", "angle_valve"]:
        bind.execute(
            text(f"""
            DELETE FROM families WHERE code = '{fcode}'
            AND NOT EXISTS (SELECT 1 FROM products p JOIN families f2 ON f2.id = p.family_id
                            WHERE f2.code = '{fcode}')
        """)
        )

    bind.execute(
        text("""
        DELETE FROM brands WHERE code = 'MT'
        AND NOT EXISTS (SELECT 1 FROM products WHERE brand_id =
                        (SELECT id FROM brands WHERE code = 'MT'))
    """)
    )
    bind.execute(
        text("""
        DELETE FROM suppliers WHERE code = 'mt_spain'
        AND NOT EXISTS (SELECT 1 FROM costs WHERE supplier_code = 'mt_spain')
    """)
    )
