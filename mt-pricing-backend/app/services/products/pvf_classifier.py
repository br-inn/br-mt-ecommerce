"""PVF rule-based classifier — extrae family/material/dn/pn del `name_en`.

Diseñado contra el catálogo MT (PIM 5085 SKUs). Los nombres siguen patrones
formulaicos PVF (Pipes/Valves/Fittings) tipo:

    "m-f 90° bend galvanised 3/8\""
    "Butterfly valve wafer cast iron disc epdm 6\""
    "Stainless steel pressure gauge dn63 brass bottom 0-100 bar"

El classifier es **pure / determinístico**: dada `name_en`, devuelve
``ClassifyResult`` con campos extraídos + flags de confianza. La lógica de
persistencia y audit la maneja la task Celery (no este módulo).

Cobertura esperada (sobre nombres reales, no placeholders): ~70-85% para
`family`, ~75-90% para `material`, ~80-95% para `dn`. `pn` es raro en el nombre
(~25%) y suele requerir specs adicionales para llenarse — aceptable como NULL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Family — orden importa (más específico primero).
# ---------------------------------------------------------------------------
# Cada entrada es ``(family_code, [regex_patterns...])`` — el primero que
# matchee gana. Las regex se compilan con `re.IGNORECASE` y deben usar word
# boundaries para evitar falsos positivos tipo "nut" → "**t** galvanised".
_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("valve", (
        r"\b(ball|butterfly|gate|globe|check|angle|control|needle|diaphragm|solenoid|stop)\s+valve\b",
        r"\bvalve\b",
    )),
    ("flange", (
        r"\bflange\b",
        r"\bblind\b",
        r"\bstub\s+end\b",
        r"\bwelding\s+(neck|socket)\b",
    )),
    ("gauge", (
        r"\bpressure\s+gauge\b",
        r"\b(thermometer|manometer|gauge)\b",
    )),
    ("actuator", (
        r"\b(actuator|servomotor)\b",
        r"\blevel\s+regulator\b",
    )),
    ("tee", (
        # "T fitting", "F-F-F equal T 18", "Brass female T 15", "reducing T"
        r"\b(equal|reducing|female|male|brass|galvanised|stainless|f-cu)\s+t\b",
        r"\bf-f-f\b",
        r"\bt\s+(fitting|brass|galvanised|stainless)\b",
    )),
    ("elbow", (
        r"\b(90°?|45°?)\s+(elbow|bend)\b",
        r"\belbow\b",
        r"\bbend\b",
        r"\blong\s+radius\b",
    )),
    ("reducer", (
        r"\b(concentric|eccentric)\s+reducer\b",
        r"\breducer\b",
        r"\breducing\s+(coupling|nut|socket)\b",
    )),
    ("press_fitting", (
        r"\bpress\s+fitting\b",
        r"\bmt-press\b",
    )),
    ("coupling", (
        r"\b(double\s+)?coupling\b",
        r"\b(pipe\s+)?socket\b",
    )),
    ("nipple", (r"\bnipple\b",)),
    ("plug", (r"\bplug\b",)),
    ("nut", (
        r"\b(hexagon|lock)\s+nut\b",
        r"\bnut\b",
    )),
    ("adaptor", (
        r"\b(adaptor|adapter|connector)\b",
        r"\btap\s+connector\b",
    )),
    ("pipe", (
        r"\bpe-?xa?\b.*\bpipe\b",
        r"\b(sch\s*40|sch\s*80)\b",
        r"\bpipe\b",
    )),
    ("hardware", (
        r"\bu-bolt\b",
        r"\b(bolt|screw|washer|bracket|hanger)\b",
    )),
    ("hose", (
        r"\bhose\b",
        r"\bflexible\s+connection\b",
    )),
    ("fitting", (
        r"\bfitting\b",
        r"\b(f-cu|fe/pe|pe/pe|pe/f|pe/m|cu-mult|compression)\b",
    )),
)
# Pre-compilamos para evitar overhead en cada call (5085 productos).
_FAMILY_COMPILED: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (code, tuple(re.compile(p, re.IGNORECASE) for p in patterns))
    for code, patterns in _FAMILY_PATTERNS
)


# ---------------------------------------------------------------------------
# Material — case-insensitive substring match.
# ---------------------------------------------------------------------------
_MATERIAL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stainless_steel_316l", ("a-316l", "1.4404", "316l", "iso 316l", "aisi-316l")),
    ("stainless_steel_304", ("a-304l", "304l", "aisi-304", "iso 304")),
    ("stainless_steel", ("stainless steel", "stainless", "aisi-316", "aisi 316")),
    ("brass", ("brass",)),
    ("galvanised_steel", ("galvanised", "galvanized", "zinc plated", "carbon steel")),
    ("cast_iron", ("cast iron", "ductile iron")),
    ("polyamide", ("polyamide", "pa6", "nylon")),
    ("pvc", ("pvc",)),
    ("abs", (" abs ", " abs.", "abs cable")),
    ("epdm", ("epdm",)),
    ("nbr", ("nbr",)),
    ("pe_xa", ("pe-xa", "pex")),
    ("multilayer", ("multilayer", "multi-layer", "mult.")),
    ("polyethylene", ("pe/pe", "pe/f", "pe/m", "polyethylene")),
    ("copper", (" copper", "f-cu", "m-cu")),
)


# ---------------------------------------------------------------------------
# DN extraction — múltiples formatos.
# ---------------------------------------------------------------------------
# 1) `dn<num>` → captura num. Sin trailing `\b` para que `dn16x3/4"` también
#    matchee (los dígitos pueden ir pegados a 'x' o letra de unidad).
_DN_DIRECT_RE = re.compile(r"\bdn\s*0*(\d{1,4})(?!\d)", re.IGNORECASE)
# 2) `ø<num>`   → captura num
_DN_DIAMETER_RE = re.compile(r"ø\s*0*(\d{1,4})", re.IGNORECASE)
# 3) Imperial `<int>"` o `<int> <num>/<num>"` o `<num>/<num>"`
_DN_IMPERIAL_RE = re.compile(r'(\d{1,3}\s+)?(\d{1,3})/(\d{1,3})\s*[”"]')
_DN_IMPERIAL_INT_RE = re.compile(r'\b(\d{1,3})\s*[”"]')

# Imperial → DN (mm) — tabla canónica BS/EN ISO 6708.
_IMPERIAL_TO_DN: dict[str, str] = {
    "1/8":   "6",
    "1/4":   "8",
    "3/8":   "10",
    "1/2":   "15",
    "3/4":   "20",
    "1":     "25",
    "1 1/4": "32",
    "11/4":  "32",
    "1 1/2": "40",
    "11/2":  "40",
    "2":     "50",
    "2 1/2": "65",
    "21/2":  "65",
    "3":     "80",
    "4":     "100",
    "5":     "125",
    "6":     "150",
    "8":     "200",
    "10":    "250",
    "12":    "300",
}


def _imperial_key(whole: str | None, num: str, den: str) -> str:
    """Normaliza un imperial detectado a una clave de _IMPERIAL_TO_DN."""
    whole = (whole or "").strip()
    if whole:
        return f'{whole} {num}/{den}'
    return f'{num}/{den}'


# ---------------------------------------------------------------------------
# PN extraction — `pn<num>` (ej. pn10, pn16, pn30). Si hay rango "pn10/pn16",
# tomamos el más bajo (interpretación conservadora, ratio working pressure).
# ---------------------------------------------------------------------------
_PN_RE = re.compile(r"\bpn\s*0*(\d{1,3})\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ClassifyResult:
    """Output del classifier — None significa "no inferible del nombre"."""

    family: str | None
    material: str | None
    dn: str | None  # mm como string (ej. "50")
    pn: str | None  # bar como string (ej. "16")
    confidence_notes: tuple[str, ...]  # diagnóstico para audit


def _normalize(name: str) -> str:
    """Lowercase + trim. Mantiene comillas/símbolos para detectar imperial."""
    return name.lower().strip()


def _classify_family(text: str) -> str | None:
    for family_code, patterns in _FAMILY_COMPILED:
        for pat in patterns:
            if pat.search(text):
                return family_code
    return None


def _classify_material(text: str) -> str | None:
    for material_code, keywords in _MATERIAL_RULES:
        for kw in keywords:
            if kw in text:
                return material_code
    return None


def _extract_dn(text: str) -> str | None:
    # Prioridad 1: dn<num> explícito.
    m = _DN_DIRECT_RE.search(text)
    if m:
        return str(int(m.group(1)))
    # Prioridad 2: ø<num> (presión MT-press, multicapa).
    m = _DN_DIAMETER_RE.search(text)
    if m:
        return str(int(m.group(1)))
    # Prioridad 3: imperial fraccional `1 1/4"` o `3/8"`.
    m = _DN_IMPERIAL_RE.search(text)
    if m:
        whole, num, den = m.group(1), m.group(2), m.group(3)
        key = _imperial_key(whole, num, den)
        dn = _IMPERIAL_TO_DN.get(key)
        if dn is not None:
            return dn
    # Prioridad 4: imperial entero `2"` → DN50.
    m = _DN_IMPERIAL_INT_RE.search(text)
    if m:
        whole = m.group(1)
        dn = _IMPERIAL_TO_DN.get(whole)
        if dn is not None:
            return dn
    return None


def _extract_pn(text: str) -> str | None:
    matches = _PN_RE.findall(text)
    if not matches:
        return None
    # Si hay múltiples (ej. "pn10/pn16"), tomamos el menor (rating efectivo).
    return str(min(int(m) for m in matches))


def classify(name_en: str) -> ClassifyResult:
    """Clasifica un nombre PVF.

    Returns:
        ClassifyResult con los 4 campos + notas. Cualquier campo puede ser None
        si no se infiere del nombre (caller decide si persistir o dejar como
        está).
    """
    text = _normalize(name_en)
    notes: list[str] = []

    family = _classify_family(text)
    if family is None:
        notes.append("family:no-match")
    material = _classify_material(text)
    if material is None:
        notes.append("material:no-match")
    dn = _extract_dn(text)
    if dn is None:
        notes.append("dn:no-match")
    pn = _extract_pn(text)
    if pn is None:
        notes.append("pn:no-match")

    return ClassifyResult(
        family=family,
        material=material,
        dn=dn,
        pn=pn,
        confidence_notes=tuple(notes),
    )
