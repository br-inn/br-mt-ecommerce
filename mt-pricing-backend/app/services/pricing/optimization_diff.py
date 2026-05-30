"""Diff puro de dos corridas de optimización (F8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_DETAIL_CAP = 200


@dataclass
class DiffSummary:
    skus_scheme_changed: int = 0
    skus_signal_changed: int = 0
    detail: list[dict[str, Any]] = field(default_factory=list)


def _scheme(r: Any) -> str:
    s = r.fulfillment_scheme
    return s.value if hasattr(s, "value") else str(s)


def diff_results(old: list[Any], new: list[Any]) -> DiffSummary:
    """Compara por SKU el fulfillment_scheme y la signal entre dos corridas."""
    old_by = {r.sku: r for r in old}
    out = DiffSummary()
    for nr in new:
        orr = old_by.get(nr.sku)
        if orr is None:
            continue
        sch_changed = _scheme(orr) != _scheme(nr)
        sig_changed = orr.signal != nr.signal
        if sch_changed:
            out.skus_scheme_changed += 1
        if sig_changed:
            out.skus_signal_changed += 1
        if (sch_changed or sig_changed) and len(out.detail) < _DETAIL_CAP:
            out.detail.append(
                {
                    "sku": nr.sku,
                    "old_scheme": _scheme(orr),
                    "new_scheme": _scheme(nr),
                    "old_signal": orr.signal,
                    "new_signal": nr.signal,
                }
            )
    return out
