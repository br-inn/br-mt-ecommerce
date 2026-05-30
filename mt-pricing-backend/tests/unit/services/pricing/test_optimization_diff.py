from dataclasses import dataclass

from app.services.pricing.optimization_diff import diff_results


@dataclass
class _R:  # stub con los campos que usa el diff
    sku: str
    fulfillment_scheme: str
    signal: str


def test_diff_counts_scheme_and_signal_changes() -> None:
    old = [_R("A", "CANAL_FULL", "ÓPTIMO"), _R("B", "MERCHANT_MANAGED", "FINO")]
    new = [_R("A", "CANAL_LASTMILE", "ÓPTIMO"), _R("B", "MERCHANT_MANAGED", "FRÁGIL")]
    d = diff_results(old, new)
    assert d.skus_scheme_changed == 1  # A
    assert d.skus_signal_changed == 1  # B
    assert len(d.detail) == 2


def test_diff_no_changes() -> None:
    old = [_R("A", "CANAL_FULL", "ÓPTIMO")]
    new = [_R("A", "CANAL_FULL", "ÓPTIMO")]
    d = diff_results(old, new)
    assert d.skus_scheme_changed == 0 and d.skus_signal_changed == 0 and d.detail == []
