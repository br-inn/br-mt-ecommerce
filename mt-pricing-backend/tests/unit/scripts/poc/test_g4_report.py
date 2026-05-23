"""Tests unitarios para g4_report._verdict (fix W-1: boundary configurable).

Cubre:
- test_verdict_boundary_configurable — fail_threshold=1 fuerza DEFER con 2 fallos
- test_verdict_build_conditional — 1 fallo con fail_threshold=2 → BUILD_CONDITIONAL
- test_verdict_build — sin fallos → BUILD
- test_verdict_zero_not_failure — 0 y 0.0 no son fallos (fix W-1)
"""

from __future__ import annotations

from scripts.poc.g4_report import _is_failure, _verdict


class TestVerdictBoundaryConfigurable:
    def test_verdict_boundary_configurable(self):
        """_verdict con fail_threshold=1 y 2 fallos → DEFER."""
        result = _verdict(
            {"ac1": False, "ac2": False, "ac3": True},
            fail_threshold=1,
        )
        assert result == "DEFER"

    def test_verdict_build_conditional(self):
        """_verdict con 1 fallo y fail_threshold=2 → BUILD_CONDITIONAL."""
        result = _verdict(
            {"ac1": False, "ac2": True, "ac3": True},
            fail_threshold=2,
        )
        assert result == "BUILD_CONDITIONAL"

    def test_verdict_build_no_failures(self):
        """_verdict sin fallos → BUILD independiente del threshold."""
        result = _verdict(
            {"ac1": True, "ac2": True, "ac3": True},
            fail_threshold=1,
        )
        assert result == "BUILD"

    def test_verdict_defer_two_failures_default_threshold(self):
        """_verdict con 2 fallos y threshold default (2) → DEFER."""
        result = _verdict(
            {"ac1": False, "ac2": False, "ac3": True},
        )
        assert result == "DEFER"

    def test_verdict_zero_not_counted_as_failure(self):
        """0 y 0.0 son falsy pero no bool False — no deben contar como fallos (fix W-1)."""
        result = _verdict(
            {"ac1": 0, "ac2": 0.0, "ac3": True},
        )
        # 0 y 0.0 no son fallos → BUILD
        assert result == "BUILD"

    def test_verdict_negative_counted_as_failure(self):
        """Valores negativos (int/float) sí deben contar como fallos."""
        result = _verdict(
            {"ac1": -1, "ac2": True, "ac3": True},
            fail_threshold=1,
        )
        assert result == "DEFER"


class TestIsFailure:
    def test_false_is_failure(self):
        assert _is_failure(False) is True

    def test_true_is_not_failure(self):
        assert _is_failure(True) is False

    def test_zero_int_not_failure(self):
        assert _is_failure(0) is False

    def test_zero_float_not_failure(self):
        assert _is_failure(0.0) is False

    def test_positive_int_not_failure(self):
        assert _is_failure(1) is False

    def test_positive_float_not_failure(self):
        assert _is_failure(0.5) is False

    def test_negative_int_is_failure(self):
        assert _is_failure(-1) is True

    def test_negative_float_is_failure(self):
        assert _is_failure(-0.1) is True
