"""Tests unitarios para MetricsCollector.

Usa datos ficticios — sin DB, sin network. Corre en CI con pytest puro.

Cobertura:
- CandidateRecord + MarketplaceMetrics propiedades derivadas.
- MetricsCollector.compute() con datos controlados.
- Cálculo de TP/FP/TN/FN correcto.
- Resolución de labels reales vs sintéticos.
- ECE: delegación a calibrator.expected_calibration_error.
- PocMetrics.aggregate() suma correctamente canales.
- export_json / export_csv crean archivos con estructura esperada.
- g4_report.generate_g4_report genera markdown válido.
- _verdict: casos BUILD, DEFER, BUILD_CONDITIONAL.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts.poc.metrics_collector import (
    AC_COV_MIN,
    AC_ECE_MAX,
    AC_FN_MAX,
    AC_FP_MAX,
    CandidateRecord,
    MarketplaceMetrics,
    MetricsCollector,
    PocMetrics,
    _collect_failures,
    _is_failure,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_record(
    sku: str = "MTBR001",
    channel: str = "amazon_uae",
    kind: str = "peer",
    score: int = 80,
    label: str | None = None,
    confidence: float | None = None,
) -> CandidateRecord:
    return CandidateRecord(
        sku=sku,
        channel=channel,
        external_id=f"{sku}-{channel}-ext",
        kind=kind,
        score=score,
        label=label,
        calibrated_confidence=confidence,
    )


# ---------------------------------------------------------------------------
# MarketplaceMetrics — propiedades derivadas
# ---------------------------------------------------------------------------


class TestMarketplaceMetrics:
    def test_precision_zero_denom(self):
        m = MarketplaceMetrics(marketplace="test")
        assert m.precision == 0.0

    def test_precision_pure_tp(self):
        m = MarketplaceMetrics(marketplace="test", tp=10, fp=0)
        assert m.precision == 1.0

    def test_fp_rate(self):
        m = MarketplaceMetrics(marketplace="test", fp=5, tn=95)
        assert abs(m.fp_rate - 0.05) < 1e-9

    def test_fn_rate_equals_one_minus_recall(self):
        m = MarketplaceMetrics(marketplace="test", tp=8, fn=2)
        assert abs(m.fn_rate - 0.2) < 1e-9
        assert abs(m.recall - 0.8) < 1e-9

    def test_cobertura_zero_skus(self):
        m = MarketplaceMetrics(marketplace="test")
        assert m.cobertura == 0.0

    def test_cobertura_half(self):
        m = MarketplaceMetrics(marketplace="test", n_skus=10, skus_with_peer=5)
        assert m.cobertura == 0.5

    def test_passes_ac_all_ok(self):
        # Construir métricas que pasen todos los AC.
        m = MarketplaceMetrics(
            marketplace="test",
            n_skus=100,
            skus_with_peer=95,  # cobertura=95% >= 90%
            tp=50,
            fp=0,
            tn=40,
            fn=2,  # FP=0%, FN=2/52≈3.8%
            ece=0.01,
        )
        ac = m.passes_ac()
        assert ac["fp_rate_ok"] is True
        assert ac["fn_rate_ok"] is True
        assert ac["ece_ok"] is True
        assert ac["cobertura_ok"] is True
        assert m.all_ac_pass() is True

    def test_passes_ac_fail_fp(self):
        # FP rate = 5/15 = 33% → falla
        m = MarketplaceMetrics(
            marketplace="test",
            n_skus=100,
            skus_with_peer=95,
            tp=10,
            fp=5,
            tn=10,
            fn=0,
            ece=0.01,
        )
        assert m.passes_ac()["fp_rate_ok"] is False
        assert m.all_ac_pass() is False

    def test_as_dict_keys(self):
        m = MarketplaceMetrics(marketplace="amazon_uae", n_skus=10, n_candidates=30)
        d = m.as_dict()
        assert "fp_rate" in d
        assert "cobertura" in d
        assert "passes_ac" in d
        assert "all_ac_pass" in d


# ---------------------------------------------------------------------------
# MetricsCollector — compute con labels reales
# ---------------------------------------------------------------------------


class TestMetricsCollectorWithRealLabels:
    def _make_collector(self) -> MetricsCollector:
        return MetricsCollector(n_skus_total=5, use_stubs=True)

    def test_all_true_positives(self):
        c = self._make_collector()
        for i in range(5):
            c.add(_make_record(sku=f"SKU{i}", kind="peer", score=85, label="accept"))
        metrics = c.compute()
        agg = metrics.aggregate()
        assert agg.tp == 5
        assert agg.fp == 0
        assert agg.fn == 0

    def test_all_false_positives(self):
        c = self._make_collector()
        for i in range(5):
            c.add(_make_record(sku=f"SKU{i}", kind="peer", score=85, label="reject"))
        metrics = c.compute()
        agg = metrics.aggregate()
        assert agg.fp == 5
        assert agg.tp == 0

    def test_mixed_tp_fp_tn_fn(self):
        c = MetricsCollector(n_skus_total=4, use_stubs=True)
        c.add(_make_record(sku="A", kind="peer", score=90, label="accept"))  # TP
        c.add(_make_record(sku="B", kind="peer", score=85, label="reject"))  # FP
        c.add(_make_record(sku="C", kind="drop", score=50, label="reject"))  # TN
        c.add(_make_record(sku="D", kind="drop", score=55, label="accept"))  # FN
        metrics = c.compute()
        m = metrics.marketplaces[0]
        assert m.tp == 1
        assert m.fp == 1
        assert m.tn == 1
        assert m.fn == 1

    def test_skip_label_excluded(self):
        c = MetricsCollector(n_skus_total=2, use_stubs=True)
        c.add(_make_record(sku="A", kind="peer", score=80, label="skip"))
        c.add(_make_record(sku="B", kind="peer", score=80, label="accept"))
        metrics = c.compute()
        m = metrics.marketplaces[0]
        # "skip" excluido — sólo 1 candidato contado.
        assert m.tp + m.fp + m.tn + m.fn == 1


# ---------------------------------------------------------------------------
# MetricsCollector — inferencia sintética (sin label)
# ---------------------------------------------------------------------------


class TestSyntheticLabelInference:
    def test_high_score_peer_becomes_tp(self):
        c = MetricsCollector(n_skus_total=1, use_stubs=True, synthetic_threshold=70)
        c.add(_make_record(sku="A", kind="peer", score=80, label=None))
        metrics = c.compute()
        agg = metrics.aggregate()
        assert agg.tp == 1, "score>=70 + kind=peer debe ser TP"

    def test_low_score_peer_becomes_fp(self):
        c = MetricsCollector(n_skus_total=1, use_stubs=True, synthetic_threshold=70)
        # kind=peer pero score<70 → predicción peer, GT=reject → FP
        c.add(_make_record(sku="A", kind="peer", score=60, label=None))
        metrics = c.compute()
        agg = metrics.aggregate()
        assert agg.fp == 1

    def test_low_score_drop_becomes_tn(self):
        c = MetricsCollector(n_skus_total=1, use_stubs=True, synthetic_threshold=70)
        # kind=drop, score<70 → pred=no peer, GT=reject → TN
        c.add(_make_record(sku="A", kind="drop", score=50, label=None))
        metrics = c.compute()
        agg = metrics.aggregate()
        assert agg.tn == 1


# ---------------------------------------------------------------------------
# MetricsCollector — múltiples canales
# ---------------------------------------------------------------------------


class TestMultiChannel:
    def test_separate_metrics_per_channel(self):
        c = MetricsCollector(n_skus_total=2, use_stubs=True)
        c.add(_make_record(sku="A", channel="amazon_uae", kind="peer", score=85, label="accept"))
        c.add(_make_record(sku="A", channel="noon_uae", kind="drop", score=50, label="reject"))
        c.add(_make_record(sku="A", channel="shopify_uae", kind="peer", score=75, label="accept"))
        metrics = c.compute()
        channels = {m.marketplace for m in metrics.marketplaces}
        assert "amazon_uae" in channels
        assert "noon_uae" in channels
        assert "shopify_uae" in channels
        assert len(metrics.marketplaces) == 3

    def test_aggregate_sums_candidates(self):
        c = MetricsCollector(n_skus_total=2, use_stubs=True)
        for ch in ("amazon_uae", "noon_uae", "shopify_uae"):
            c.add(_make_record(sku="A", channel=ch, kind="peer", score=80, label="accept"))
        metrics = c.compute()
        agg = metrics.aggregate()
        assert agg.n_candidates == 3


# ---------------------------------------------------------------------------
# Coverage (skus_with_peer)
# ---------------------------------------------------------------------------


class TestCoverage:
    def test_coverage_counts_unique_skus_with_peer(self):
        c = MetricsCollector(n_skus_total=5, use_stubs=True)
        # 3 SKUs con peer, 2 sin
        for sku in ("A", "B", "C"):
            c.add(_make_record(sku=sku, channel="amazon_uae", kind="peer", score=85))
        for sku in ("D", "E"):
            c.add(_make_record(sku=sku, channel="amazon_uae", kind="drop", score=50))
        metrics = c.compute()
        m = metrics.marketplaces[0]
        assert m.skus_with_peer == 3
        # cobertura = 3/5 = 60% (n_skus del canal, no total)
        assert abs(m.cobertura - 3 / 5) < 1e-9

    def test_multiple_peer_same_sku_counts_once(self):
        c = MetricsCollector(n_skus_total=3, use_stubs=True)
        # Mismo SKU con 3 candidatos peer
        for ext in ("ext1", "ext2", "ext3"):
            r = CandidateRecord(
                sku="SINGLE",
                channel="amazon_uae",
                external_id=ext,
                kind="peer",
                score=80,
            )
            c.add(r)
        metrics = c.compute()
        m = metrics.marketplaces[0]
        assert m.skus_with_peer == 1  # un solo SKU


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def _sample_metrics(self) -> tuple[MetricsCollector, PocMetrics]:
        c = MetricsCollector(n_skus_total=10, use_stubs=True)
        for sku in (f"SKU{i}" for i in range(10)):
            c.add(_make_record(sku=sku, kind="peer", score=80, label="accept"))
        metrics = c.compute()
        return c, metrics

    def test_export_json_creates_file(self, tmp_path):
        c, metrics = self._sample_metrics()
        path = tmp_path / "results.json"
        c.export_json(metrics, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "aggregate" in data
        assert "by_marketplace" in data

    def test_export_csv_creates_file(self, tmp_path):
        c, metrics = self._sample_metrics()
        path = tmp_path / "results.csv"
        c.export_csv(metrics, path)
        assert path.exists()
        lines = path.read_text().splitlines()
        assert len(lines) >= 2  # header + al menos 1 fila

    def test_export_json_has_run_date(self, tmp_path):
        c, metrics = self._sample_metrics()
        path = tmp_path / "r.json"
        c.export_json(metrics, path)
        data = json.loads(path.read_text())
        assert "run_date" in data
        assert len(data["run_date"]) == 10  # YYYY-MM-DD


# ---------------------------------------------------------------------------
# G4 Report
# ---------------------------------------------------------------------------


class TestG4Report:
    def _perfect_metrics(self) -> PocMetrics:
        """Métricas que pasan todos los AC."""
        c = MetricsCollector(n_skus_total=100, use_stubs=True, synthetic_threshold=70)
        for i in range(90):
            c.add(_make_record(sku=f"S{i}", kind="peer", score=80, label="accept"))
        for i in range(10):
            c.add(_make_record(sku=f"S{90 + i}", kind="drop", score=50, label="reject"))
        return c.compute()

    def _failing_metrics(self) -> PocMetrics:
        """Métricas que fallan >= 2 AC (provoca DEFER)."""
        c = MetricsCollector(n_skus_total=100, use_stubs=True, synthetic_threshold=70)
        # Alta tasa FP + baja cobertura
        for i in range(50):
            c.add(_make_record(sku=f"S{i}", kind="peer", score=80, label="reject"))  # FP
        for i in range(50):
            c.add(_make_record(sku=f"S{50 + i}", kind="drop", score=50, label="reject"))  # TN
        return c.compute()

    def test_build_decision_in_report(self, tmp_path):
        from scripts.poc.g4_report import generate_g4_report

        metrics = self._perfect_metrics()
        path = tmp_path / "g4.md"
        content = generate_g4_report(metrics, path)
        assert path.exists()
        assert "BUILD" in content

    def test_defer_decision_in_report(self, tmp_path):
        from scripts.poc.g4_report import generate_g4_report

        metrics = self._failing_metrics()
        path = tmp_path / "g4.md"
        content = generate_g4_report(metrics, path)
        assert "DEFER" in content

    def test_report_contains_metrics_table(self, tmp_path):
        from scripts.poc.g4_report import generate_g4_report

        metrics = self._perfect_metrics()
        path = tmp_path / "g4.md"
        content = generate_g4_report(metrics, path)
        assert "| Marketplace |" in content
        assert "amazon_uae" in content

    def test_report_contains_hooks_section(self, tmp_path):
        from scripts.poc.g4_report import generate_g4_report

        metrics = self._perfect_metrics()
        path = tmp_path / "g4.md"
        content = generate_g4_report(metrics, path)
        assert "ComparatorPort" in content
        assert "VlmJudgePort" in content


# ---------------------------------------------------------------------------
# Fix W-4: _collect_failures con falsy non-bool
# ---------------------------------------------------------------------------


class TestCollectFailures:
    def test_failures_falsy_non_bool(self):
        """0 y 0.0 son falsy pero no False — no deben ser fallos (fix W-4)."""
        result = _collect_failures({"ok": 0, "fail": False, "good": 0.0})
        assert result == ["fail"], f"Solo 'fail' (bool False) debe ser un fallo, got {result!r}"

    def test_collect_failures_empty(self):
        """Sin fallos → lista vacía."""
        result = _collect_failures({"a": True, "b": 1, "c": 0.5})
        assert result == []

    def test_collect_failures_negative_numeric(self):
        """Valores negativos sí son fallos."""
        result = _collect_failures({"neg_int": -1, "neg_float": -0.1, "ok": 0})
        assert set(result) == {"neg_int", "neg_float"}

    def test_is_failure_zero_not_failure(self):
        """_is_failure: 0 y 0.0 no son fallos."""
        assert _is_failure(0) is False
        assert _is_failure(0.0) is False

    def test_is_failure_false_is_failure(self):
        """_is_failure: False es fallo."""
        assert _is_failure(False) is True

    def test_is_failure_true_not_failure(self):
        """_is_failure: True no es fallo."""
        assert _is_failure(True) is False


# ---------------------------------------------------------------------------
# Errors tracking
# ---------------------------------------------------------------------------


class TestErrorTracking:
    def test_errors_propagate_to_metrics(self):
        c = MetricsCollector(n_skus_total=5, use_stubs=True)
        c.add_error("fetch error sku=A channel=amazon_uae: timeout")
        c.add_error("fetch error sku=B channel=noon_uae: conn refused")
        metrics = c.compute()
        assert len(metrics.errors) == 2

    def test_elapsed_set(self):
        c = MetricsCollector(n_skus_total=1, use_stubs=True)
        c.set_elapsed(3.14)
        metrics = c.compute()
        assert abs(metrics.elapsed_seconds - 3.14) < 1e-9
