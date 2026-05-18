"""material_aliases — tabla de homologación de materiales para el matching pipeline.

Revision ID: 20260514_107
Revises: 20260514_106
Create Date: 2026-05-14
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "20260514_107"
down_revision = "20260514_106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_aliases",
        sa.Column("id", sa.Text(), nullable=False, primary_key=True),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("material_class", sa.String(16), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("alias_lower", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("canonical_name", "alias_lower", name="uq_material_alias_canonical_alias"),
    )
    op.create_index("idx_material_aliases_alias_lower", "material_aliases", ["alias_lower"])
    op.create_index("idx_material_aliases_canonical", "material_aliases", ["canonical_name"])

    _seed()


def downgrade() -> None:
    op.drop_index("idx_material_aliases_canonical")
    op.drop_index("idx_material_aliases_alias_lower")
    op.drop_table("material_aliases")


# ---------------------------------------------------------------------------
# Seed — mismos grupos que material_normalizer._STATIC_GROUPS
# ---------------------------------------------------------------------------
_SEED: list[tuple[str, str, str, list[str]]] = [
    ("brass", "Brass / Latón", "metal", [
        "brass", "laton", "latón", "latten", "messing", "yellow brass",
        "naval brass", "cuzn",
    ]),
    ("brass_cw617n", "Brass CW617N (DZR)", "metal", [
        "cw617n", "brass cw617n", "dezincification resistant brass",
        "dzr brass", "dzr", "cr brass",
    ]),
    ("brass_cw602n", "Brass CW602N", "metal", [
        "cw602n", "brass cw602n",
    ]),
    ("brass_cw628n", "Brass CW628N", "metal", [
        "cw628n", "brass cw628n",
    ]),
    ("bronze", "Bronze / Bronce", "metal", [
        "bronze", "gunmetal", "lg2", "cc491k", "bronce", "laiton rouge",
        "red brass",
    ]),
    ("stainless_steel_316", "Stainless Steel 316", "metal", [
        "ss316", "316ss", "aisi 316", "316l", "316", "1.4404", "1.4401",
        "stainless 316", "stainless steel 316", "inox 316", "inox316",
        "acero inox 316", "acero inoxidable 316",
    ]),
    ("stainless_steel_304", "Stainless Steel 304", "metal", [
        "ss304", "304ss", "aisi 304", "304l", "304", "1.4301", "1.4307",
        "stainless 304", "stainless steel 304", "inox 304", "inox304",
        "acero inox 304",
    ]),
    ("cast_iron", "Cast Iron / Fundición Gris", "metal", [
        "cast iron", "grey iron", "gray iron", "gg25", "en-gjl-250",
        "en gjl 250", "gjl-250", "hierro fundido", "fonte grise", "cast_iron",
    ]),
    ("ductile_iron", "Ductile Iron / Fundición Dúctil", "metal", [
        "ductile iron", "nodular iron", "sg iron", "ggg50", "ggg40",
        "ggg-50", "ggg-40", "en-gjs-500", "en gjs 500", "gjs-500",
        "spheroidal graphite iron", "hierro dúctil", "hierro nodular",
    ]),
    ("carbon_steel", "Carbon Steel / Acero Carbono", "metal", [
        "carbon steel", "cs", "a216 wcb", "wcb", "a105", "a216",
        "acero carbono",
    ]),
    ("zamak", "Zamak / Zinc Alloy", "metal", [
        "zamak", "zamac", "zinc alloy", "die cast zinc", "zinc die cast",
    ]),
    ("aluminium", "Aluminium / Aluminio", "metal", [
        "aluminium", "aluminum", "aluminio", "al", "6061", "6063",
    ]),
    ("ptfe", "PTFE / Teflon", "polymer", [
        "ptfe", "tfe", "teflon", "polytetrafluoroethylene", "teflón",
    ]),
    ("rptfe", "Reinforced PTFE", "polymer", [
        "rptfe", "reinforced ptfe", "glass-filled ptfe", "filled ptfe",
        "modified ptfe", "carbon-filled ptfe",
    ]),
    ("pvc", "PVC", "polymer", [
        "pvc", "upvc", "u-pvc", "rigid pvc", "pvc-u", "polyvinyl chloride",
    ]),
    ("cpvc", "CPVC", "polymer", [
        "cpvc", "chlorinated pvc", "chlorinated polyvinyl chloride", "pvc-c",
    ]),
    ("pp", "Polypropylene / Polipropileno", "polymer", [
        "pp", "polypropylene", "polipropileno", "pp-h", "pp-r", "ppr",
    ]),
    ("pvdf", "PVDF / Kynar", "polymer", [
        "pvdf", "kynar", "polyvinylidene fluoride", "pvf2",
    ]),
    ("peek", "PEEK", "polymer", [
        "peek", "polyether ether ketone",
    ]),
    ("pa", "Polyamide / Nylon", "polymer", [
        "pa", "nylon", "polyamide", "pa6", "pa66", "nylon 6", "nylon 66",
    ]),
    ("nbr", "NBR / Nitrile", "elastomer", [
        "nbr", "nitrile", "buna-n", "buna n", "nitrile rubber",
        "acrylonitrile butadiene", "caucho nitrilo",
    ]),
    ("epdm", "EPDM", "elastomer", [
        "epdm", "epdm rubber", "ethylene propylene", "ep rubber",
        "ethylene propylene diene monomer",
    ]),
    ("viton", "Viton / FKM", "elastomer", [
        "viton", "fkm", "fpm", "fluorocarbon rubber", "fluoroelastomer",
    ]),
    ("neoprene", "Neoprene / CR", "elastomer", [
        "neoprene", "cr", "chloroprene rubber", "chloroprene",
    ]),
    ("silicone", "Silicone / Silicona", "elastomer", [
        "silicone", "silicona", "vmq", "silicon rubber",
    ]),
]


def _seed() -> None:
    conn = op.get_bind()
    rows = []
    for canonical, display, cls_, aliases in _SEED:
        for alias in aliases:
            rows.append({
                "id": str(uuid.uuid4()),
                "canonical_name": canonical,
                "display_name": display,
                "material_class": cls_,
                "alias": alias,
                "alias_lower": alias.lower().strip(),
                "source": "industry_standard",
            })
    if rows:
        conn.execute(sa.text(
            "INSERT INTO material_aliases "
            "(id, canonical_name, display_name, material_class, alias, alias_lower, source) "
            "VALUES (:id, :canonical_name, :display_name, :material_class, :alias, :alias_lower, :source) "
            "ON CONFLICT (canonical_name, alias_lower) DO NOTHING"
        ), rows)
