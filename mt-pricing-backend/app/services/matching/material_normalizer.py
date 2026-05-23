"""MaterialNormalizer — homologación de materiales para el matching pipeline.

Mapea aliases de industria a un nombre canónico, permitiendo comparar
"SS316", "AISI 316", "1.4404" e "inox 316" como equivalentes.

Uso en scoring (síncrono, sin IO):
    normalizer = MaterialNormalizer.from_static()
    normalizer.canonical("SS316")           # → "stainless_steel_316"
    normalizer.same_canonical("SS316", "AISI 316")   # → True
    normalizer.same_family("ss316", "ss304")         # → True  (ambos "stainless")
    normalizer.same_family("brass", "stainless_steel_316")  # → False

Uso con DB (async, para cargar aliases extendidos del usuario):
    normalizer = await MaterialNormalizer.from_db(session)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Seed estático — aliases canónicos de la industria de válvulas industriales.
# Mismo dataset que la migración 20260514_107 — usado como fallback cuando
# la DB no está disponible o en tests.
# ---------------------------------------------------------------------------

# (canonical_name, display_name, material_class, [aliases...])
_STATIC_GROUPS: list[tuple[str, str, str, list[str]]] = [
    # ── Metales ──────────────────────────────────────────────────────────────
    (
        "brass",
        "Brass / Latón",
        "metal",
        [
            "brass",
            "laton",
            "latón",
            "latten",
            "messing",
            "yellow brass",
            "naval brass",
            "cuzn",
        ],
    ),
    (
        "brass_cw617n",
        "Brass CW617N (DZR)",
        "metal",
        [
            "cw617n",
            "brass cw617n",
            "dezincification resistant brass",
            "dzr brass",
            "dzr",
            "cr brass",
        ],
    ),
    (
        "brass_cw602n",
        "Brass CW602N",
        "metal",
        [
            "cw602n",
            "brass cw602n",
        ],
    ),
    (
        "brass_cw628n",
        "Brass CW628N",
        "metal",
        [
            "cw628n",
            "brass cw628n",
        ],
    ),
    (
        "bronze",
        "Bronze / Bronce",
        "metal",
        [
            "bronze",
            "gunmetal",
            "lg2",
            "cc491k",
            "bronce",
            "laiton rouge",
            "red brass",
        ],
    ),
    (
        "stainless_steel_316",
        "Stainless Steel 316",
        "metal",
        [
            "ss316",
            "316ss",
            "aisi 316",
            "316l",
            "316",
            "1.4404",
            "1.4401",
            "stainless 316",
            "stainless steel 316",
            "inox 316",
            "inox316",
            "acero inox 316",
            "acero inoxidable 316",
        ],
    ),
    (
        "stainless_steel_304",
        "Stainless Steel 304",
        "metal",
        [
            "ss304",
            "304ss",
            "aisi 304",
            "304l",
            "304",
            "1.4301",
            "1.4307",
            "stainless 304",
            "stainless steel 304",
            "inox 304",
            "inox304",
            "acero inox 304",
        ],
    ),
    (
        "stainless_steel_316l",
        "Stainless Steel 316L",
        "metal",
        [
            "ss316l",
            "316l",
            "1.4404",
            "aisi 316l",
        ],
    ),
    (
        "cast_iron",
        "Cast Iron / Fundición Gris",
        "metal",
        [
            "cast iron",
            "grey iron",
            "gray iron",
            "gg25",
            "en-gjl-250",
            "en gjl 250",
            "gjl-250",
            "hierro fundido",
            "fonte grise",
            "cast_iron",
        ],
    ),
    (
        "ductile_iron",
        "Ductile Iron / Fundición Dúctil",
        "metal",
        [
            "ductile iron",
            "nodular iron",
            "sg iron",
            "ggg50",
            "ggg40",
            "ggg-50",
            "ggg-40",
            "en-gjs-500",
            "en gjs 500",
            "gjs-500",
            "spheroidal graphite iron",
            "hierro dúctil",
            "hierro nodular",
            "fonte ductile",
        ],
    ),
    (
        "carbon_steel",
        "Carbon Steel / Acero Carbono",
        "metal",
        [
            "carbon steel",
            "cs",
            "a216 wcb",
            "wcb",
            "a105",
            "a216",
            "acero carbono",
            "acier carbone",
        ],
    ),
    (
        "zamak",
        "Zamak / Zinc Alloy",
        "metal",
        [
            "zamak",
            "zamac",
            "zinc alloy",
            "die cast zinc",
            "zinc die cast",
            "zn alloy",
        ],
    ),
    (
        "aluminium",
        "Aluminium / Aluminio",
        "metal",
        [
            "aluminium",
            "aluminum",
            "aluminio",
            "al",
            "6061",
            "6063",
        ],
    ),
    # ── Polímeros ────────────────────────────────────────────────────────────
    (
        "ptfe",
        "PTFE / Teflon",
        "polymer",
        [
            "ptfe",
            "tfe",
            "teflon",
            "polytetrafluoroethylene",
            "teflón",
        ],
    ),
    (
        "rptfe",
        "Reinforced PTFE",
        "polymer",
        [
            "rptfe",
            "reinforced ptfe",
            "glass-filled ptfe",
            "filled ptfe",
            "modified ptfe",
            "carbon-filled ptfe",
        ],
    ),
    (
        "pvc",
        "PVC",
        "polymer",
        [
            "pvc",
            "upvc",
            "u-pvc",
            "rigid pvc",
            "pvc-u",
            "polyvinyl chloride",
        ],
    ),
    (
        "cpvc",
        "CPVC",
        "polymer",
        [
            "cpvc",
            "chlorinated pvc",
            "chlorinated polyvinyl chloride",
            "pvc-c",
        ],
    ),
    (
        "pp",
        "Polypropylene / Polipropileno",
        "polymer",
        [
            "pp",
            "polypropylene",
            "polipropileno",
            "pp-h",
            "pp-r",
            "ppr",
        ],
    ),
    (
        "pvdf",
        "PVDF / Kynar",
        "polymer",
        [
            "pvdf",
            "kynar",
            "polyvinylidene fluoride",
            "pvf2",
        ],
    ),
    (
        "peek",
        "PEEK",
        "polymer",
        [
            "peek",
            "polyether ether ketone",
        ],
    ),
    (
        "pa",
        "Polyamide / Nylon",
        "polymer",
        [
            "pa",
            "nylon",
            "polyamide",
            "pa6",
            "pa66",
            "nylon 6",
            "nylon 66",
        ],
    ),
    # ── Elastómeros ──────────────────────────────────────────────────────────
    (
        "nbr",
        "NBR / Nitrile",
        "elastomer",
        [
            "nbr",
            "nitrile",
            "buna-n",
            "buna n",
            "nitrile rubber",
            "acrylonitrile butadiene",
            "caucho nitrilo",
        ],
    ),
    (
        "epdm",
        "EPDM",
        "elastomer",
        [
            "epdm",
            "epdm rubber",
            "ethylene propylene",
            "ep rubber",
            "ethylene propylene diene monomer",
        ],
    ),
    (
        "viton",
        "Viton / FKM",
        "elastomer",
        [
            "viton",
            "fkm",
            "fpm",
            "fluorocarbon rubber",
            "fluoroelastomer",
            "fluoro rubber",
        ],
    ),
    (
        "neoprene",
        "Neoprene / CR",
        "elastomer",
        [
            "neoprene",
            "cr",
            "chloroprene rubber",
            "chloroprene",
            "polychloroprene",
        ],
    ),
    (
        "silicone",
        "Silicone / Silicona",
        "elastomer",
        [
            "silicone",
            "silicona",
            "vmq",
            "silicon rubber",
        ],
    ),
]


def _build_static_map() -> dict[str, str]:
    """Construye alias_lower → canonical_name desde los datos estáticos."""
    m: dict[str, str] = {}
    for canonical, _display, _cls, aliases in _STATIC_GROUPS:
        for alias in aliases:
            key = alias.lower().strip()
            m[key] = canonical
    return m


_STATIC_MAP: dict[str, str] = _build_static_map()

# Familia = primer token antes de "_" (ej. "stainless" para ss316 y ss304)
_FAMILY_RE = re.compile(r"^([a-z]+)")


def _family(canonical: str) -> str:
    m = _FAMILY_RE.match(canonical)
    return m.group(1) if m else canonical


class MaterialNormalizer:
    """Normaliza strings de material a un canonical_name."""

    def __init__(self, alias_map: dict[str, str]) -> None:
        self._map = alias_map

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def from_static(cls) -> "MaterialNormalizer":
        """Instancia rápida desde el mapa estático (sin IO)."""
        return cls(dict(_STATIC_MAP))

    @classmethod
    async def from_db(cls, session: "AsyncSession") -> "MaterialNormalizer":
        """Carga alias desde DB, fusionando con el mapa estático.

        Los alias de DB sobreescriben el estático cuando hay conflicto,
        permitiendo que el usuario extienda o corrija la homologación sin
        redeploy.
        """
        from sqlalchemy import select

        from app.db.models.material_alias import MaterialAlias

        rows = (await session.execute(select(MaterialAlias))).scalars().all()
        merged = dict(_STATIC_MAP)
        for row in rows:
            merged[row.alias_lower] = row.canonical_name
        return cls(merged)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def canonical(self, text: str | None) -> str | None:
        """Devuelve canonical_name o el propio texto normalizado si no hay alias."""
        if not text:
            return None
        key = text.lower().strip()
        return self._map.get(key, key)

    def same_canonical(self, a: str | None, b: str | None) -> bool:
        """True si ambos materiales tienen el mismo canonical_name."""
        ca, cb = self.canonical(a), self.canonical(b)
        return bool(ca and cb and ca == cb)

    def same_family(self, a: str | None, b: str | None) -> bool:
        """True si ambos materiales pertenecen a la misma familia.

        Ejemplos:
          same_family("brass", "brass_cw617n")    → True  (ambos "brass")
          same_family("ss316", "ss304")            → True  (ambos "stainless")
          same_family("brass", "stainless_steel_316") → False
        """
        ca, cb = self.canonical(a), self.canonical(b)
        if not ca or not cb:
            return False
        return _family(ca) == _family(cb)


# Singleton estático listo para usar en contextos síncronos (scoring puro).
STATIC_NORMALIZER: MaterialNormalizer = MaterialNormalizer.from_static()
