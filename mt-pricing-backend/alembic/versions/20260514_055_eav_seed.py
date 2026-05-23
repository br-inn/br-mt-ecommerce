"""Fase 2 — EAV seed catálogo inicial (subset PDF §8.1).

Inserta el catálogo de attribute_definitions del Sprint 1 EAV — subset
quirúrgico de los ~35 atributos del PDF §8.1. Los demás se añaden
iterativamente en sprints posteriores.

Atributos seedeados (18 total):

Numéricos (12):
- temp_min, temp_max (°C, scope=product)
- pressure_max (bar, scope=both)
- dn_nominal (mm, integer, scope=variant)
- weight (kg, scope=variant) — coexiste con products.weight escalar
- pkg_width, pkg_height, pkg_depth (mm, scope=variant)
- dim_L, dim_H, dim_W, dim_H1 (mm, scope=variant)
- torque (Nm, scope=variant)
- kv (no unit, scope=variant)

Enums (6) — con sus options:
- manufacturing_method (8 options)
- material_body (7 options)
- material_seal (5 options)
- actuation_type (5 options)
- iso5211_flange (8 options)
- connection_type (7 options)

Revision ID: 20260514_055
Revises: 20260514_054
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260514_055"
down_revision: str | None = "20260514_054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Attribute definitions — (code, label_en, data_type, unit, scope,
#                          is_filterable, is_seo_relevant, description_en)
# ---------------------------------------------------------------------------
_NUMERIC_ATTRS: list[tuple[str, str, str, str | None, str, bool, bool, str | None]] = [
    (
        "temp_min",
        "Minimum temperature",
        "number",
        "C",
        "product",
        True,
        True,
        "Nominal minimum service temperature.",
    ),
    (
        "temp_max",
        "Maximum temperature",
        "number",
        "C",
        "product",
        True,
        True,
        "Nominal maximum service temperature.",
    ),
    (
        "pressure_max",
        "Maximum pressure",
        "number",
        "bar",
        "both",
        True,
        True,
        "Maximum service pressure at reference temperature.",
    ),
    (
        "dn_nominal",
        "Nominal diameter (DN)",
        "integer",
        "mm",
        "variant",
        True,
        True,
        "Nominal diameter according to ISO 6708.",
    ),
    (
        "weight",
        "Weight",
        "number",
        "kg",
        "variant",
        False,
        False,
        "Product or variant weight; coexists with products.weight scalar.",
    ),
    ("pkg_width", "Package width", "number", "mm", "variant", False, False, "Outer package width."),
    (
        "pkg_height",
        "Package height",
        "number",
        "mm",
        "variant",
        False,
        False,
        "Outer package height.",
    ),
    ("pkg_depth", "Package depth", "number", "mm", "variant", False, False, "Outer package depth."),
    (
        "dim_L",
        "Dimension L (length)",
        "number",
        "mm",
        "variant",
        False,
        False,
        "Face-to-face / overall length.",
    ),
    (
        "dim_H",
        "Dimension H (height)",
        "number",
        "mm",
        "variant",
        False,
        False,
        "Overall height (centerline to top).",
    ),
    ("dim_W", "Dimension W (width)", "number", "mm", "variant", False, False, "Overall width."),
    (
        "dim_H1",
        "Dimension H1 (auxiliary height)",
        "number",
        "mm",
        "variant",
        False,
        False,
        "Auxiliary height — e.g. from centerline to handle base.",
    ),
    (
        "torque",
        "Operating torque",
        "number",
        "Nm",
        "variant",
        False,
        False,
        "Maximum operating torque under nominal conditions.",
    ),
    (
        "kv",
        "Flow coefficient Kv",
        "number",
        None,
        "variant",
        False,
        False,
        "Flow coefficient Kv in m3/h at 1 bar differential.",
    ),
]
# Note: the list above has 14 items not 12. The spec mentions 12 numeric, but
# weight is "Note: already in products.weight, but allow override via EAV"
# and torque/kv are also listed; the prompt's count is approximate. Seed all 14.


_ENUM_ATTRS: list[tuple[str, str, str, bool, bool, str | None]] = [
    # (code, label_en, scope, is_filterable, is_seo_relevant, description_en)
    (
        "manufacturing_method",
        "Manufacturing method",
        "product",
        True,
        True,
        "Primary manufacturing process used to produce the body.",
    ),
    ("material_body", "Body material", "product", True, True, "Material grade of the main body."),
    (
        "material_seal",
        "Seal material",
        "product",
        True,
        True,
        "Material of the primary sealing element.",
    ),
    (
        "actuation_type",
        "Actuation type",
        "product",
        True,
        True,
        "How the device is actuated (manual, motorized, pneumatic…).",
    ),
    (
        "iso5211_flange",
        "ISO 5211 mounting flange",
        "product",
        True,
        True,
        "Standard mounting flange code per ISO 5211.",
    ),
    (
        "connection_type",
        "Connection type",
        "product",
        True,
        True,
        "End connection type (thread, flange, weld…).",
    ),
]


_ENUM_OPTIONS: dict[str, list[tuple[str, str]]] = {
    # attribute_code -> [(option_code, option_label_en), ...]
    "manufacturing_method": [
        ("forged", "Forged"),
        ("cast", "Cast"),
        ("machined", "Machined"),
        ("welded", "Welded"),
        ("molded", "Molded"),
        ("extruded", "Extruded"),
        ("stamped", "Stamped"),
        ("sintered", "Sintered"),
    ],
    "material_body": [
        ("ss316", "Stainless steel 316"),
        ("ss304", "Stainless steel 304"),
        ("brass", "Brass"),
        ("ductile_iron", "Ductile iron"),
        ("carbon_steel", "Carbon steel"),
        ("pvc", "PVC"),
        ("ppgf", "Polypropylene with glass fiber (PP-GF)"),
    ],
    "material_seal": [
        ("epdm", "EPDM"),
        ("nbr", "NBR"),
        ("viton", "Viton (FKM)"),
        ("ptfe", "PTFE"),
        ("hnbr", "HNBR"),
    ],
    "actuation_type": [
        ("free_shaft", "Free shaft"),
        ("handle", "Manual handle"),
        ("gearbox", "Gearbox"),
        ("motorized", "Electric motorized"),
        ("pneumatic", "Pneumatic"),
    ],
    "iso5211_flange": [
        ("F03", "F03"),
        ("F04", "F04"),
        ("F05", "F05"),
        ("F07", "F07"),
        ("F10", "F10"),
        ("F12", "F12"),
        ("F14", "F14"),
        ("F16", "F16"),
    ],
    "connection_type": [
        ("bsp_thread", "BSP thread"),
        ("npt_thread", "NPT thread"),
        ("flange_pn10", "Flange PN10"),
        ("flange_pn16", "Flange PN16"),
        ("flange_ansi150", "Flange ANSI 150"),
        ("weld_socket", "Socket weld"),
        ("weld_butt", "Butt weld"),
    ],
}


def _quote(value: str | None) -> str:
    """Quote a SQL literal — None → NULL; else escape single quotes."""
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Numeric / integer attributes
    # ------------------------------------------------------------------
    for code, label, dtype, unit, scope, is_filt, is_seo, desc in _NUMERIC_ATTRS:
        op.execute(
            f"""
            INSERT INTO attribute_definitions
                (code, label_en, data_type, unit, scope,
                 is_filterable, is_seo_relevant, description_en)
            VALUES (
                {_quote(code)},
                {_quote(label)},
                {_quote(dtype)},
                {_quote(unit)},
                {_quote(scope)},
                {"true" if is_filt else "false"},
                {"true" if is_seo else "false"},
                {_quote(desc)}
            )
            ON CONFLICT (code) DO NOTHING;
            """
        )

    # ------------------------------------------------------------------
    # 2. Enum attributes (definitions)
    # ------------------------------------------------------------------
    for code, label, scope, is_filt, is_seo, desc in _ENUM_ATTRS:
        op.execute(
            f"""
            INSERT INTO attribute_definitions
                (code, label_en, data_type, unit, scope,
                 is_filterable, is_seo_relevant, description_en)
            VALUES (
                {_quote(code)},
                {_quote(label)},
                'enum',
                NULL,
                {_quote(scope)},
                {"true" if is_filt else "false"},
                {"true" if is_seo else "false"},
                {_quote(desc)}
            )
            ON CONFLICT (code) DO NOTHING;
            """
        )

    # ------------------------------------------------------------------
    # 3. Enum options
    # ------------------------------------------------------------------
    for attr_code, opts in _ENUM_OPTIONS.items():
        for idx, (opt_code, opt_label) in enumerate(opts):
            op.execute(
                f"""
                INSERT INTO attribute_options
                    (attribute_id, code, label_en, order_index)
                SELECT
                    ad.id, {_quote(opt_code)}, {_quote(opt_label)}, {idx}
                FROM attribute_definitions ad
                WHERE ad.code = {_quote(attr_code)}
                ON CONFLICT (attribute_id, code) DO NOTHING;
                """
            )


def downgrade() -> None:
    # Remove options first (CASCADE would handle it, but explicit is safer).
    for attr_code in _ENUM_OPTIONS:
        op.execute(
            f"""
            DELETE FROM attribute_options
            WHERE attribute_id IN (
                SELECT id FROM attribute_definitions WHERE code = {_quote(attr_code)}
            );
            """
        )
    # Remove definitions.
    all_codes = [a[0] for a in _NUMERIC_ATTRS] + [e[0] for e in _ENUM_ATTRS]
    quoted = ",".join(_quote(c) for c in all_codes)
    op.execute(f"DELETE FROM attribute_definitions WHERE code IN ({quoted});")
