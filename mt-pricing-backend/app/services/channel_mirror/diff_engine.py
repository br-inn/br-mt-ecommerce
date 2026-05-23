"""Pure diff engine — canonical (MT) vs live (Amazon UAE / Noon UAE).

Devuelve ``list[FieldDiff]`` con el estado de cada campo:

- ``match``    : valor MT == valor canal (string-normalized).
- ``drift``    : ambos tienen valor pero distintos.
- ``missing``  : MT tiene valor pero el canal no lo expone (vacío/None).
- ``queued``   : MT tiene valor y existe un push pendiente (o el canal lo
  marcó como pendiente de procesar). El caller (``MirrorService``) decide
  cuándo upgrade un ``missing`` a ``queued``.

Soporta lang AR — los campos cuyo nombre acaba en ``_ar`` se interpretan
como traducciones árabe (RTL); el comparator los trata exactamente igual,
pero el shape resultante incluye ``lang='ar'`` para que el frontend pinte
con la fuente RTL correcta.

Esta función es PURA — no toca DB, no hace IO. Toda la persistencia vive
en ``MirrorService``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Status canonical (alineado con frontend `MirrorStatus` en
# mt-pricing-frontend/app/(app)/canales/amazon-uae/page.tsx).
DiffStatus = Literal["match", "drift", "missing", "queued"]

DIFF_STATUS_MATCH: DiffStatus = "match"
DIFF_STATUS_DRIFT: DiffStatus = "drift"
DIFF_STATUS_MISSING: DiffStatus = "missing"
DIFF_STATUS_QUEUED: DiffStatus = "queued"


@dataclass(frozen=True)
class FieldDiff:
    """Diferencia de un campo individual MT canonical vs canal externo."""

    field: str
    mt: Any
    live: Any
    status: DiffStatus
    lang: str | None = None  # 'ar' si el field termina en _ar; None si no aplica.
    mono: bool = False  # hint UI: campo monoespaciado (códigos, dimensiones).
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Campos que el frontend marca como mono (ver MIRROR_ROWS).
_MONO_FIELDS: frozenset[str] = frozenset(
    {
        "HS_code",
        "DN",
        "PN",
        "weight",
        "price_aed",
        "image_main",
        "image_4 (AR)",
    }
)


def _normalize(value: Any) -> str:
    """Normaliza valores para comparación de igualdad permisiva.

    - ``None`` y ``""`` → ``""``.
    - Strings: strip + collapse whitespace + casefold (para tolerar
      variaciones de mayúsculas / espacios duplicados que Amazon SP-API
      a veces inyecta en feed XML).
    - Otros tipos: ``str(value)``.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        # collapse whitespace
        return " ".join(value.split()).casefold()
    return str(value).casefold()


def _is_empty(value: Any) -> bool:
    """``True`` si el valor canal es vacío (no presente o string vacío)."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _detect_lang(field_name: str) -> str | None:
    """``ar`` si el field acaba en ``_ar`` o contiene ``(AR)``."""
    lname = field_name.lower()
    if lname.endswith("_ar") or "(ar)" in lname:
        return "ar"
    return None


def canonical_vs_live(
    canonical: dict[str, Any],
    live: dict[str, Any],
    *,
    queued_fields: set[str] | None = None,
    fields_order: list[str] | None = None,
) -> list[FieldDiff]:
    """Diff field-by-field MT canonical vs canal externo.

    Args:
        canonical: dict ``{field_name: value}`` desde el snapshot MT.
        live: dict ``{field_name: value}`` desde el canal (vacío si listing
            inexistente — todos los campos quedarán como ``missing``).
        queued_fields: subset de fields que tienen un push pendiente; el
            engine los marca como ``queued`` aunque también sean
            ``missing`` o ``drift``.
        fields_order: si se pasa, el resultado respeta este orden y solo
            incluye estos campos. Si es ``None``, el engine devuelve la
            unión ordenada de keys (canonical primero, luego canal-only).

    Returns:
        Lista de ``FieldDiff`` en orden estable.
    """
    queued = queued_fields or set()

    if fields_order is None:
        # Unión preservando orden: canonical primero, luego live-only.
        seen: set[str] = set()
        ordered: list[str] = []
        for name in canonical:
            if name not in seen:
                ordered.append(name)
                seen.add(name)
        for name in live:
            if name not in seen:
                ordered.append(name)
                seen.add(name)
        fields_order = ordered

    diffs: list[FieldDiff] = []
    for name in fields_order:
        mt_value = canonical.get(name)
        live_value = live.get(name)

        if name in queued:
            status: DiffStatus = DIFF_STATUS_QUEUED
        elif _is_empty(live_value) and not _is_empty(mt_value):
            status = DIFF_STATUS_MISSING
        elif _is_empty(mt_value) and _is_empty(live_value):
            # Ambos vacíos → consideramos match neutral (no hay drift posible).
            status = DIFF_STATUS_MATCH
        elif _normalize(mt_value) == _normalize(live_value):
            status = DIFF_STATUS_MATCH
        else:
            status = DIFF_STATUS_DRIFT

        diffs.append(
            FieldDiff(
                field=name,
                mt=mt_value if mt_value is not None else "",
                live=live_value if live_value is not None else "",
                status=status,
                lang=_detect_lang(name),
                mono=name in _MONO_FIELDS,
            )
        )
    return diffs


def summarize(diffs: list[FieldDiff]) -> dict[str, int]:
    """Cuenta totales por status — útil para banner del frontend."""
    counts = {
        DIFF_STATUS_MATCH: 0,
        DIFF_STATUS_DRIFT: 0,
        DIFF_STATUS_MISSING: 0,
        DIFF_STATUS_QUEUED: 0,
    }
    for d in diffs:
        counts[d.status] += 1
    return counts
