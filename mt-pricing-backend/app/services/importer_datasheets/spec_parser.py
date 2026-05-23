"""Spec parser — extrae specs técnicas (DN, PN, material, seal) del texto
extraído de un datasheet PDF y deduce el SKU/kind a partir del nombre del
archivo.

Naming convention (Sprint 4 / US-1A-06-04):
- ``MTFT_{sku_suffix}.pdf``  → ficha técnica.
- ``MTCE_{sku_suffix}.pdf``  → compliance (CE).
- ``MTMAN_{sku_suffix}.pdf`` → manual.
- ``MTFT_5114-5115-5116.pdf`` → multi-SKU (separadores ``-``).

``sku_suffix`` se mapea contra ``Product.sku`` con el prefix corto
``MT-V-{suffix}`` (convención BR→MT, ver _bmad-output PRD §3). Si no resuelve
el SKU exacto, se reporta como ``orphan_files``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Filename
# ---------------------------------------------------------------------------
_FILENAME_RE = re.compile(
    r"^(?P<prefix>MTFT|MTCE|MTMAN)_(?P<suffix>[0-9][0-9A-Za-z\-]*)\.pdf$",
    re.IGNORECASE,
)


_PREFIX_TO_KIND = {
    "MTFT": "ficha_tecnica",
    "MTCE": "compliance",
    "MTMAN": "manual",
}


@dataclass(slots=True)
class FilenameParseResult:
    ok: bool
    kind: str | None = None
    sku_suffixes: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "sku_suffixes": list(self.sku_suffixes),
            "error": self.error,
        }


def parse_datasheet_filename(filename: str) -> FilenameParseResult:
    """Parsea el filename del datasheet → kind + lista de SKU suffixes.

    Reglas:
    - Match ``MTFT_5114.pdf``, ``MTCE_5114.pdf``, ``MTMAN_5114-5115.pdf``.
    - Suffixes separados por ``-``. Cada uno debe ser numérico (longitud
      arbitraria, soporta letras finales tipo ``5114B``).
    - Filename inválido → ``ok=False`` con razón.
    """
    base = filename.strip()
    # Soportamos paths Windows / Unix
    base = base.replace("\\", "/").rsplit("/", 1)[-1]
    m = _FILENAME_RE.match(base)
    if not m:
        return FilenameParseResult(
            ok=False,
            error=f"filename '{filename}' no respeta MT(FT|CE|MAN)_<suffix>.pdf",
        )

    prefix = m.group("prefix").upper()
    suffix_blob = m.group("suffix")
    parts = [p for p in suffix_blob.split("-") if p]
    if not parts:
        return FilenameParseResult(ok=False, error="suffix vacío tras parseo")

    return FilenameParseResult(
        ok=True,
        kind=_PREFIX_TO_KIND[prefix],
        sku_suffixes=parts,
    )


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class DatasheetSpecs:
    dn: str | None = None
    pn: str | None = None
    material: str | None = None
    seal: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.dn:
            out["dn"] = self.dn
        if self.pn:
            out["pn"] = self.pn
        if self.material:
            out["material"] = self.material
        if self.seal:
            out["seal"] = self.seal
        if self.extra:
            out["extra"] = dict(self.extra)
        return out

    @property
    def is_empty(self) -> bool:
        return not (self.dn or self.pn or self.material or self.seal)


_DN_RE = re.compile(r"\bDN\s*[:=]?\s*(\d{1,4})\b", re.IGNORECASE)
# PN debe ir seguido de un dígito; "PNCANONICAL" o "PN " no valen.
_PN_RE = re.compile(r"\bPN\s*[:=]?\s*(\d{1,4})\b")
_MATERIAL_RE = re.compile(r"\b(?:material|body)\s*[:=]?\s*([A-Za-z0-9 \-_/+]{2,32})", re.IGNORECASE)
_SEAL_RE = re.compile(
    r"\b(?:seal(?:ing)?|junta)\s*[:=]?\s*([A-Za-z0-9 \-_/+]{2,32})", re.IGNORECASE
)

_KNOWN_MATERIALS = {
    # Códigos específicos primero para que tengan prioridad sobre los genéricos.
    "cw617n": "brass_cw617n",
    "ss316": "ss316",
    "ss304": "ss304",
    "stainless steel": "stainless_steel",
    "cast iron": "cast_iron",
    "ductile iron": "ductile_iron",
    "carbon steel": "carbon_steel",
    "bronze": "bronze",
    "brass": "brass",
    "pvc": "pvc",
}

_KNOWN_SEALS = {
    "epdm": "epdm",
    "nbr": "nbr",
    "viton": "viton",
    "fkm": "fkm",
    "ptfe": "ptfe",
    "silicone": "silicone",
}


def _normalize(value: str) -> str:
    return value.strip().rstrip(".,;").strip()


def _detect_material(text: str) -> str | None:
    t = text.lower()
    for needle, canonical in _KNOWN_MATERIALS.items():
        if needle in t:
            return canonical
    m = _MATERIAL_RE.search(text)
    if m:
        candidate = _normalize(m.group(1))
        if candidate:
            return candidate
    return None


def _detect_seal(text: str) -> str | None:
    t = text.lower()
    for needle, canonical in _KNOWN_SEALS.items():
        if needle in t:
            return canonical
    m = _SEAL_RE.search(text)
    if m:
        candidate = _normalize(m.group(1))
        if candidate:
            return candidate
    return None


def parse_specs_from_text(text: str) -> DatasheetSpecs:
    """Aplica regex a un blob de texto extraído del PDF.

    Tolerante a ruido (whitespace, mayúsculas, separadores ``:`` o ``=``).
    Si no detecta nada, retorna un :class:`DatasheetSpecs` con ``is_empty``.
    """
    if not text:
        return DatasheetSpecs()

    dn_m = _DN_RE.search(text)
    pn_m = _PN_RE.search(text)
    material = _detect_material(text)
    seal = _detect_seal(text)

    return DatasheetSpecs(
        dn=f"DN{dn_m.group(1)}" if dn_m else None,
        pn=f"PN{pn_m.group(1)}" if pn_m else None,
        material=material,
        seal=seal,
    )


__all__ = [
    "DatasheetSpecs",
    "FilenameParseResult",
    "parse_datasheet_filename",
    "parse_specs_from_text",
]
