"""match_scorer.py — Scorer determinista de 8 dimensiones para productos industriales.

Migrado desde MT_Pricing_Run_Kit/src/match_scorer_v2.py al backend FastAPI.

Lógica de scoring:
  1. EAN directo         → auto-100 (skip resto)
  2. Alloy code          → +25 pts (CW617N, AISI316, A105…)
  3. Valve type          → +30 pts, VETO si mismatch (cap score ≤30)
  4. Material            → +20 pts, VETO si mismatch
  5. Size DN/inches      → +15 pts
  6. Pressure PN         → +10 pts
  7. End connection      → +5 pts
  8. Brand tier          → +bonus (competitor) / -penalty (dropshipper)

``product_data`` viene del modelo Product de SQLAlchemy vía _product_to_dict().
``amazon_specs`` son specs extraídas del PDP de Amazon (por el extractor o bruto).
"""

from __future__ import annotations

import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Vocabulario de sinónimos — migrado íntegro de match_scorer_v2.py
# ---------------------------------------------------------------------------

VALVE_TYPE_SYNONYMS: dict[str, list[str]] = {
    "ball valve": ["ball valve", "ball-valve", "ball", "esfera", "esférica"],
    "gate valve": ["gate valve", "gate-valve", "gate", "compuerta", "wedge"],
    "check valve": [
        "check valve",
        "non return",
        "non-return",
        "one way",
        "antirretorno",
        "antirretroceso",
        "check",
    ],
    "butterfly valve": ["butterfly valve", "butterfly", "wafer", "lugged"],
    "angle valve": ["angle valve", "angle", "escuadra"],
    "bibcock": ["bibcock", "tap", "garden tap", "spigot"],
    "expansion joint": [
        "expansion joint",
        "compensator",
        "manguito elástico",
        "flexible joint",
        "rubber joint",
    ],
    "strainer": ["strainer", "y-strainer", "filter", "filtro"],
    "globe valve": ["globe valve", "globe", "asiento"],
    "safety valve": ["safety valve", "pressure relief", "válvula de seguridad"],
    "mixer tap": ["mixer tap", "mezclador", "mixer"],
    "click clack": ["click clack", "click-clack", "pop-up waste", "waste"],
}

MATERIAL_SYNONYMS: dict[str, list[str]] = {
    "brass": [
        "brass",
        "latón",
        "cu-zn",
        "cw617n",
        "cw602n",
        "cw724r",
        "cw511l",
        "leaded brass",
        "lead-free brass",
        "dezincification",
    ],
    "stainless_steel": [
        "stainless",
        "stainless steel",
        "acero inox",
        "inoxidable",
        "aisi 304",
        "aisi 316",
        "aisi 420",
        "ss 304",
        "ss 316",
        "ss316",
        "a351",
        "cf8m",
        "cf8",
    ],
    "carbon_steel": [
        "carbon steel",
        "a105",
        "forged steel",
        "lcb",
        "wcb",
        "a216",
        "acero al carbono",
        "acero al carbon",
    ],
    "cast_iron": [
        "cast iron",
        "fundición",
        "ductile iron",
        "en-gjl",
        "en-gjs",
        "gg25",
        "gg-25",
        "ggg40",
    ],
    "rubber_epdm": ["epdm", "rubber"],
    "rubber_nbr": ["nbr", "buna-n", "nitrile"],
    "ptfe": ["ptfe", "teflon"],
    "pvc": ["pvc"],
    "bronze": ["bronze", "bronce"],
    "nickel": ["nickel", "níquel"],
}

END_CONNECTION_SYNONYMS: dict[str, list[str]] = {
    "threaded": [
        "threaded",
        "thread",
        "rosca",
        "roscada",
        "female thread",
        "male thread",
        "bsp",
        "npt",
        "g 1/2",
        "iso 228",
        "din 259",
    ],
    "flanged": [
        "flanged",
        "flange",
        "brida",
        "bridada",
        "pn10/pn16",
        "pn 10",
        "ansi 150",
        "asme b16.5",
        "en 1092",
    ],
    "wafer": ["wafer"],
    "lug": ["lug", "lugged"],
    "weld": ["weld", "soldar", "soldadura", "butt-weld", "socket-weld"],
    "press_fit": ["press-fit", "press fit", "pressfit"],
    "compression": ["compression", "compresión", "cutting ring"],
}

# Tier de competidores/marcas embebido en el scorer (sin fichero externo).
# Se puede enriquecer vía env/DB en sprints futuros.
# Format: {alias_lower: {"brand_canonical": str, "tier": int}}
_COMPETITOR_BRANDS: dict[str, dict[str, Any]] = {
    "pegler": {"brand_canonical": "Pegler", "tier": 1},
    "giacomini": {"brand_canonical": "Giacomini", "tier": 1},
    "apollo": {"brand_canonical": "Apollo", "tier": 1},
    "nibco": {"brand_canonical": "Nibco", "tier": 1},
    "arco": {"brand_canonical": "Arco", "tier": 1},
    "viega": {"brand_canonical": "Viega", "tier": 1},
    "watts": {"brand_canonical": "Watts", "tier": 2},
    "honeywell": {"brand_canonical": "Honeywell", "tier": 2},
    "danfoss": {"brand_canonical": "Danfoss", "tier": 2},
    "kitz": {"brand_canonical": "Kitz", "tier": 2},
    "bonomi": {"brand_canonical": "Bonomi", "tier": 2},
    "vexve": {"brand_canonical": "Vexve", "tier": 3},
    "caleffi": {"brand_canonical": "Caleffi", "tier": 3},
}

_DROPSHIPPERS: list[str] = [
    "doja",
    "generic",
    "no brand",
    "nobrand",
    "unbranded",
]


# ---------------------------------------------------------------------------
# Helpers de normalización
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[\s\-_]+", " ", text.lower()).strip()


def _matches_any(needle: str, synonyms: list[str]) -> bool:
    n = _normalize(needle)
    for s in synonyms:
        if _normalize(s) in n:
            return True
    return False


def _classify_term(text: str, synonym_map: dict[str, list[str]]) -> Optional[str]:
    """Devuelve la clase canónica para un texto libre."""
    if not text:
        return None
    n = _normalize(text)
    for canon, syns in synonym_map.items():
        for s in syns:
            if _normalize(s) in n:
                return canon
    return None


def _extract_size_inches(text: str) -> Optional[str]:
    """Encuentra la primera medida en pulgadas: '1/2"', '1 1/2"', '2"'."""
    if not text:
        return None
    m = re.search(r'(\d+(?:\s+\d+/\d+)?(?:/\d+)?)\s*"', text)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return None


def _extract_dn(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\bDN\s*(\d+)\b", text, re.I)
    if m:
        return int(m.group(1))
    return None


def _extract_pn(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\bPN[ -]?(\d{1,3})\b", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,3})\s*bar", text, re.I)
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Mapeo product_data (backend) → campos que espera el scorer
# ---------------------------------------------------------------------------


def _build_mt_rec(product_data: dict[str, Any]) -> dict[str, Any]:
    """Convierte product_data del backend al formato interno del scorer.

    product_data puede ser:
    - El resultado de MatchService._product_to_dict() (campos top-level)
    - O un dict libre con claves equivalentes

    Retorna un dict con secciones: web, excel, ficha, nombre_en, codigo.
    """
    attrs: dict[str, Any] = product_data.get("specs") or product_data.get("attributes") or {}

    # Nombre y código
    nombre_en = (
        product_data.get("name_en")
        or product_data.get("nombre_en")
        or product_data.get("name")
        or ""
    )
    codigo = product_data.get("sku") or product_data.get("codigo") or ""

    # EAN — puede estar en atributos EAV o en campo directo
    ean = (
        str(attrs.get("ean_individual") or "")
        or str(attrs.get("ean") or "")
        or str(product_data.get("ean") or "")
    )

    # Alloy codes — lista de strings
    alloy_codes: list[str] = []
    raw_alloys = attrs.get("alloy_codes") or attrs.get("alloy") or []
    if isinstance(raw_alloys, list):
        alloy_codes = [str(a) for a in raw_alloys if a]
    elif isinstance(raw_alloys, str) and raw_alloys:
        alloy_codes = [raw_alloys]
    # Fallback: extrae de nombre si hay CW617N, AISI316, etc.
    if not alloy_codes:
        alloy_pattern = re.findall(
            r"\b(CW\d{3}[A-Z]|AISI\s*\d{3}|A\d{3}|cf8m|cf8)\b", nombre_en, re.I
        )
        alloy_codes = list(dict.fromkeys(p.upper() for p in alloy_pattern))

    # Sección web
    web: dict[str, Any] = {
        "category": (
            attrs.get("category")
            or product_data.get("family")
            or product_data.get("subfamily")
            or ""
        ),
        "material": product_data.get("material") or attrs.get("material") or "",
        "size_in": (
            attrs.get("size_in")
            or attrs.get("size_inches")
            or _extract_size_inches(str(product_data.get("dn") or ""))
            or ""
        ),
        "size_dn": str(product_data.get("dn") or attrs.get("dn") or "").replace("DN", ""),
    }

    # Sección excel
    excel: dict[str, Any] = {
        "ean_individual": ean,
        "medidas_clean": (attrs.get("medidas_clean") or attrs.get("size") or str(web["size_in"])),
        "material_intrastat_guess": attrs.get("material_intrastat_guess") or "",
    }

    # Sección ficha
    ficha: dict[str, Any] = {
        "alloy_codes": alloy_codes,
        "pressure_pn": (product_data.get("pn") or attrs.get("pn") or attrs.get("pressure_pn")),
        "end_connection": _build_end_connection_list(product_data, attrs),
        "materials": attrs.get("materials") or {},
    }

    return {
        "nombre_en": nombre_en,
        "codigo": codigo,
        "web": web,
        "excel": excel,
        "ficha": ficha,
    }


def _build_end_connection_list(product_data: dict[str, Any], attrs: dict[str, Any]) -> list[str]:
    """Construye lista canónica de end connections del producto MT."""
    raw = (
        attrs.get("end_connection")
        or attrs.get("connection_type")
        or product_data.get("connection")
        or product_data.get("thread")
        or ""
    )
    if isinstance(raw, list):
        result = []
        for item in raw:
            canon = _classify_term(str(item), END_CONNECTION_SYNONYMS)
            if canon:
                result.append(canon)
        return result
    if isinstance(raw, str) and raw:
        canon = _classify_term(raw, END_CONNECTION_SYNONYMS)
        return [canon] if canon else []
    return []


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------


def score_match(
    product_data: dict[str, Any],
    amazon_specs: dict[str, Any],
    amazon_title: str = "",
) -> tuple[int, dict[str, Any]]:
    """Calcula score 0-100 y breakdown por dimensión.

    Args:
        product_data: datos del producto MT (salida de _product_to_dict() o similar).
        amazon_specs: specs extraídas del PDP de Amazon.
        amazon_title: título de la listing de Amazon (fallback para campos faltantes).

    Returns:
        (score, breakdown) donde breakdown es dict[dim → (matched, pts, max, note)].
        La firma es compatible con la del CLI en match_scorer_v2.py.
        Si los datos son insuficientes → (0, {"reason": "insufficient_data"}).
    """
    # Validación mínima
    if not product_data or not isinstance(product_data, dict):
        return 0, {"reason": "insufficient_data"}

    mt_rec = _build_mt_rec(product_data)
    breakdown: dict[str, Any] = {}
    veto_active = False

    # Blob de texto Amazon para búsquedas fuzzy
    amz_blob = " ".join(
        filter(
            None,
            [
                amazon_title,
                str(amazon_specs.get("title_pdp") or ""),
                str(amazon_specs.get("material_type") or ""),
                str(amazon_specs.get("valve_type") or ""),
                str(amazon_specs.get("specification_met") or ""),
                str(amazon_specs.get("thread_size") or ""),
                str(amazon_specs.get("size") or ""),
                str(amazon_specs.get("thread_type") or ""),
                str(amazon_specs.get("inlet_connection") or ""),
                str(amazon_specs.get("outlet_connection") or ""),
                str(amazon_specs.get("connection_type") or ""),
                str(amazon_specs.get("maximum_pressure") or ""),
                # campos enriquecidos por LLM extractor
                str(amazon_specs.get("material") or ""),
                str(amazon_specs.get("end_connection") or ""),
                str(amazon_specs.get("alloy_code") or ""),
            ],
        )
    )

    web = mt_rec.get("web") or {}
    excel = mt_rec.get("excel") or {}
    ficha = mt_rec.get("ficha") or {}

    # ─── 1) EAN MATCH (auto-100) ───
    mt_ean = (excel.get("ean_individual") or "").strip()
    if mt_ean and mt_ean in amz_blob.replace(" ", ""):
        breakdown["ean_direct"] = (True, 100, 100, f"EAN {mt_ean} encontrado en Amazon spec")
        return 100, breakdown

    # ─── 2) ALLOY CODE ───
    mt_alloys: list[str] = ficha.get("alloy_codes") or []
    spec_met = str(amazon_specs.get("specification_met") or "")
    alloy_search_text = spec_met + " " + amz_blob
    found_alloy = None
    for alloy in mt_alloys:
        if alloy and _normalize(alloy) in _normalize(alloy_search_text):
            found_alloy = alloy
            break
    if mt_alloys:
        if found_alloy:
            breakdown["alloy"] = (True, 25, 25, f"Alloy {found_alloy} matched")
        else:
            breakdown["alloy"] = (False, 0, 25, f"Alloys {mt_alloys} no encontrados en Amazon")

    # ─── 3) VALVE TYPE (VETO si mismatch) ───
    mt_category = str(web.get("category") or "")
    mt_valve_canon = _classify_term(mt_category, VALVE_TYPE_SYNONYMS) or _classify_term(
        mt_rec.get("nombre_en") or "", VALVE_TYPE_SYNONYMS
    )
    amz_valve_raw = str(amazon_specs.get("valve_type") or "") + " " + amazon_title
    amz_valve_canon = _classify_term(amz_valve_raw, VALVE_TYPE_SYNONYMS)

    if mt_valve_canon and amz_valve_canon:
        if mt_valve_canon == amz_valve_canon:
            breakdown["valve_type"] = (True, 30, 30, f"{mt_valve_canon} == {amz_valve_canon}")
        else:
            breakdown["valve_type"] = (
                False,
                0,
                30,
                f"MT={mt_valve_canon} ≠ AMZ={amz_valve_canon}  [VETO]",
            )
            veto_active = True
    elif mt_valve_canon and not amz_valve_canon:
        if _matches_any(amz_blob, VALVE_TYPE_SYNONYMS[mt_valve_canon]):
            breakdown["valve_type"] = (True, 20, 30, f"{mt_valve_canon} encontrado en título")
        else:
            breakdown["valve_type"] = (
                False,
                0,
                30,
                f"{mt_valve_canon} no encontrado en ningún campo",
            )
    else:
        breakdown["valve_type"] = (None, 0, 0, "categoría no clasificable")

    # ─── 4) MATERIAL (VETO si mismatch) ───
    mt_mats: set[str] = set()
    for alloy in mt_alloys:
        c = _classify_term(alloy, MATERIAL_SYNONYMS)
        if c:
            mt_mats.add(c)
    for comp_mats in (ficha.get("materials") or {}).values():
        for m in comp_mats or []:
            c = _classify_term(str(m), MATERIAL_SYNONYMS) if m not in MATERIAL_SYNONYMS else m
            if c:
                mt_mats.add(c)
    if web.get("material"):
        c = _classify_term(str(web["material"]), MATERIAL_SYNONYMS)
        if c:
            mt_mats.add(c)
    if excel.get("material_intrastat_guess"):
        c = _classify_term(str(excel["material_intrastat_guess"]), MATERIAL_SYNONYMS)
        if c:
            mt_mats.add(c)
    mt_mats.discard(None)  # type: ignore[arg-type]

    amz_mat_raw = str(amazon_specs.get("material_type") or "") + " " + amazon_title
    # También usar el campo enriquecido "material" del LLM extractor
    if amazon_specs.get("material"):
        amz_mat_raw += " " + str(amazon_specs["material"])
    amz_mat_canon = _classify_term(amz_mat_raw, MATERIAL_SYNONYMS)

    if mt_mats and amz_mat_canon:
        if amz_mat_canon in mt_mats:
            breakdown["material"] = (True, 20, 20, f"{amz_mat_canon} matched MT material set")
        else:
            breakdown["material"] = (
                False,
                0,
                20,
                f"MT primary mats {mt_mats} ≠ AMZ {amz_mat_canon}  [VETO]",
            )
            veto_active = True
    elif mt_mats and not amz_mat_canon:
        breakdown["material"] = (False, 0, 20, f"MT={mt_mats} pero Amazon no tiene campo material")
    else:
        breakdown["material"] = (None, 0, 0, "no hay material MT para comparar")

    # ─── 5) SIZE (inches O DN) ───
    mt_size_in = str(web.get("size_in") or excel.get("medidas_clean") or "").replace('"', "")
    mt_size_dn = str(web.get("size_dn") or "").replace("DN", "")
    amz_size_in = (
        str(amazon_specs.get("thread_size") or amazon_specs.get("size") or "")
        .replace('"', "")
        .strip()
    )
    # Campo enriquecido del LLM
    if not amz_size_in and amazon_specs.get("size_inches"):
        amz_size_in = str(amazon_specs["size_inches"]).replace('"', "").strip()

    size_match = False
    if mt_size_in and amz_size_in:
        if _normalize(mt_size_in) == _normalize(amz_size_in):
            size_match = True
    if not size_match and mt_size_dn:
        amz_dn_raw = amazon_title + " " + str(amazon_specs.get("size") or "")
        if amazon_specs.get("size_dn"):
            amz_dn_raw += f" DN{amazon_specs['size_dn']}"
        amz_dn = _extract_dn(amz_dn_raw)
        if amz_dn and str(amz_dn) == str(mt_size_dn):
            size_match = True

    mt_size_ref = mt_size_in or mt_size_dn
    if mt_size_ref:
        if size_match:
            breakdown["size"] = (True, 15, 15, f"size matched ({mt_size_ref})")
        else:
            breakdown["size"] = (False, 0, 15, f"MT={mt_size_ref} vs AMZ={amz_size_in}")
    else:
        breakdown["size"] = (None, 0, 0, "no hay size MT para comparar")

    # ─── 6) PRESSURE (PN) ───
    mt_pn_raw = ficha.get("pressure_pn") or _extract_pn(mt_rec.get("nombre_en") or "")
    if mt_pn_raw is None:
        mt_pn = None
    elif isinstance(mt_pn_raw, int):
        mt_pn = mt_pn_raw
    else:
        mt_pn = _extract_pn(str(mt_pn_raw))

    amz_pn_text = (
        str(amazon_specs.get("maximum_pressure") or "")
        + " "
        + str(amazon_specs.get("specification_met") or "")
        + " "
        + amazon_title
    )
    if amazon_specs.get("pressure_pn"):
        amz_pn_text += f" PN{amazon_specs['pressure_pn']}"
    amz_pn = _extract_pn(amz_pn_text)

    if mt_pn and amz_pn:
        if abs(mt_pn - amz_pn) <= 5:
            breakdown["pressure"] = (True, 10, 10, f"PN MT={mt_pn} ≈ AMZ={amz_pn}")
        else:
            breakdown["pressure"] = (False, 0, 10, f"PN MT={mt_pn} ≠ AMZ={amz_pn}")
    else:
        breakdown["pressure"] = (None, 0, 0, "PN no comparable")

    # ─── 7) END CONNECTION ───
    mt_ends: list[str] = ficha.get("end_connection") or []
    amz_end_parts = [
        str(amazon_specs.get("inlet_connection") or ""),
        str(amazon_specs.get("outlet_connection") or ""),
        str(amazon_specs.get("connection_type") or ""),
        str(amazon_specs.get("end_connection") or ""),
        amazon_title,
    ]
    amz_end_canon = _classify_term(" ".join(amz_end_parts), END_CONNECTION_SYNONYMS)

    if mt_ends and amz_end_canon:
        if amz_end_canon in mt_ends:
            breakdown["end_conn"] = (True, 5, 5, f"{amz_end_canon} matched")
        else:
            breakdown["end_conn"] = (False, 0, 5, f"MT={mt_ends} ≠ AMZ={amz_end_canon}")
    else:
        breakdown["end_conn"] = (None, 0, 0, "end conn no comparable")

    # ─── 8) BRAND / COMPETITOR TIER ───
    amz_brand_blob = " ".join(
        [
            str(amazon_specs.get("brand_name") or ""),
            str(amazon_specs.get("manufacturer") or ""),
            str(amazon_specs.get("brand") or ""),
            amazon_title[:80],
        ]
    ).lower()

    matched_competitor: Optional[dict[str, Any]] = None
    matched_dropshipper: Optional[str] = None

    for alias, comp_info in _COMPETITOR_BRANDS.items():
        if alias in amz_brand_blob:
            matched_competitor = comp_info
            break

    if not matched_competitor:
        for ds in _DROPSHIPPERS:
            if ds in amz_brand_blob:
                matched_dropshipper = ds
                break

    if matched_competitor:
        tier = matched_competitor.get("tier", 2)
        bonus = {1: 20, 2: 12, 3: 6}.get(tier, 6)
        breakdown["competitor"] = (
            True,
            bonus,
            20,
            f"{matched_competitor['brand_canonical']} (tier {tier} peer fabricator)",
        )
    elif matched_dropshipper:
        breakdown["competitor"] = (
            False,
            -10,
            20,
            f"{matched_dropshipper} → dropshipper, no es peer  [penalty]",
        )
    else:
        breakdown["competitor"] = (None, 0, 0, "marca desconocida — sin bonus/penalty")

    # ─── Score final ───
    pts = sum(b[1] for b in breakdown.values() if b[0] is not None)
    mx = sum(b[2] for b in breakdown.values() if b[0] is not None)
    if mx == 0:
        score = 0
    else:
        score = int(round(max(0, pts) / mx * 100))
    if veto_active:
        score = min(score, 30)

    return score, breakdown


__all__ = [
    "VALVE_TYPE_SYNONYMS",
    "MATERIAL_SYNONYMS",
    "END_CONNECTION_SYNONYMS",
    "score_match",
]
