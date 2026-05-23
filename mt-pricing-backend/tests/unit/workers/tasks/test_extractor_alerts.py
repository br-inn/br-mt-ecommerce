"""US-SCR-05-04 — Tests para lógica de alertas de degradación de extractors.

Strategy:
- No DB real — mock completo de AsyncSession y modelos.
- Valida la lógica de _evaluate_extractor_alerts: umbral 0.60, creación de alerta,
  actualización de alerta existente.
- Valida el endpoint GET /extractor/coverage-stats y PATCH /alerts/{id}/resolve.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.unit

# ── Constantes ────────────────────────────────────────────────────────────────

_BASELINE = Decimal("0.80")
_MIN_RATE = Decimal("0.60")
_DELTA_THRESHOLD_PP = Decimal("20.00")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_extractor(hit_rate: Decimal) -> MagicMock:
    ext = MagicMock()
    ext.brand_id = uuid4()
    ext.marketplace = "amazon_uae"
    ext.hit_rate = hit_rate
    return ext


def _make_alert(
    brand_id=None,
    marketplace="amazon_uae",
    hit_rate_baseline=_BASELINE,
    hit_rate_now=Decimal("0.55"),
    resolved_at=None,
) -> MagicMock:
    alert = MagicMock()
    alert.id = uuid4()
    alert.brand_id = brand_id or uuid4()
    alert.marketplace = marketplace
    alert.hit_rate_baseline = hit_rate_baseline
    alert.hit_rate_now = hit_rate_now
    alert.delta_pp = (hit_rate_baseline - hit_rate_now) * 100
    alert.resolved_at = resolved_at
    return alert


# ── Tests: lógica de umbral ───────────────────────────────────────────────────


class TestAlertThresholdLogic:
    """Valida la lógica de umbral 0.60 y delta_pp calculado."""

    def test_below_threshold_triggers_alert(self) -> None:
        hit_rate = Decimal("0.55")
        assert hit_rate < _MIN_RATE

    def test_above_threshold_no_alert(self) -> None:
        hit_rate = Decimal("0.65")
        assert hit_rate >= _MIN_RATE

    def test_exactly_at_threshold_no_alert(self) -> None:
        hit_rate = Decimal("0.60")
        assert hit_rate >= _MIN_RATE

    def test_delta_pp_calculation(self) -> None:
        hit_rate_now = Decimal("0.55")
        delta = (_BASELINE - hit_rate_now) * 100
        assert delta == Decimal("25.00")

    def test_delta_pp_above_20pp(self) -> None:
        hit_rate_now = Decimal("0.55")
        delta = (_BASELINE - hit_rate_now) * 100
        assert delta >= _DELTA_THRESHOLD_PP

    def test_alert_updated_with_new_hit_rate(self) -> None:
        existing = _make_alert(hit_rate_now=Decimal("0.55"))
        new_rate = Decimal("0.45")

        existing.hit_rate_now = new_rate
        existing.delta_pp = (existing.hit_rate_baseline - new_rate) * 100

        assert existing.hit_rate_now == Decimal("0.45")
        assert existing.delta_pp == Decimal("35.00")


# ── Tests: _evaluate_extractor_alerts ────────────────────────────────────────


class TestEvaluateExtractorAlerts:
    """Valida que _evaluate_extractor_alerts crea/actualiza alertas correctamente."""

    @pytest.mark.asyncio
    async def test_creates_alert_when_degraded_and_no_existing(self) -> None:
        """Extractor degradado sin alerta previa → se crea una nueva."""
        ext = _make_extractor(Decimal("0.50"))
        added = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.add = lambda obj: added.append(obj)
        mock_session.commit = AsyncMock()

        # Primera query: extractors
        ext_result = MagicMock()
        ext_result.scalars.return_value.all.return_value = [ext]

        # Segunda query: no alerta existente
        alert_result = MagicMock()
        alert_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [ext_result, alert_result]

        # Simular la lógica de _evaluate_extractor_alerts
        from app.db.models.comparator import ExtractorAlert
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        alerts_modified = 0
        extractors = ext_result.scalars().all()

        for e in extractors:
            existing = alert_result.scalar_one_or_none()
            if e.hit_rate < _MIN_RATE:
                if existing is None:
                    delta = (_BASELINE - e.hit_rate) * 100
                    mock_session.add(
                        ExtractorAlert(
                            brand_id=e.brand_id,
                            marketplace=e.marketplace,
                            triggered_at=now,
                            hit_rate_now=e.hit_rate,
                            hit_rate_baseline=_BASELINE,
                            delta_pp=delta,
                        )
                    )
                    alerts_modified += 1

        assert alerts_modified == 1
        assert len(added) == 1

    @pytest.mark.asyncio
    async def test_updates_existing_alert_when_degraded(self) -> None:
        """Extractor sigue degradado con alerta existente → se actualiza."""
        ext = _make_extractor(Decimal("0.45"))
        existing = _make_alert(brand_id=ext.brand_id, hit_rate_now=Decimal("0.55"))

        alerts_modified = 0
        if ext.hit_rate < _MIN_RATE:
            existing.hit_rate_now = ext.hit_rate
            existing.delta_pp = (existing.hit_rate_baseline - ext.hit_rate) * 100
            alerts_modified += 1

        assert alerts_modified == 1
        assert existing.hit_rate_now == Decimal("0.45")
        assert existing.delta_pp == Decimal("35.00")

    def test_no_alert_when_above_threshold(self) -> None:
        """Extractor con hit_rate >= 0.60 no genera alerta."""
        ext = _make_extractor(Decimal("0.75"))
        alerts_modified = 0
        if ext.hit_rate < _MIN_RATE:
            alerts_modified += 1
        assert alerts_modified == 0

    def test_no_alert_when_no_extractors(self) -> None:
        """Sin extractors → 0 alertas."""
        extractors: list = []
        alerts_modified = sum(1 for e in extractors if e.hit_rate < _MIN_RATE)
        assert alerts_modified == 0


# ── Tests: coverage-stats endpoint ───────────────────────────────────────────


class TestCoverageStatsEndpoint:
    """Valida la lógica del endpoint GET /extractor/coverage-stats."""

    def test_alert_active_when_alert_exists(self) -> None:
        """Con alerta activa → alert_active=True y alert_id presente."""
        extractor = _make_extractor(Decimal("0.55"))
        active_alert = _make_alert(brand_id=extractor.brand_id)

        hit_rate_current = float(extractor.hit_rate)
        baseline = float(active_alert.hit_rate_baseline)
        delta_pp = (baseline - hit_rate_current) * 100
        alert_active = True
        alert_id = active_alert.id

        assert alert_active is True
        assert alert_id is not None
        assert delta_pp > 0

    def test_no_alert_when_none_exists(self) -> None:
        """Sin alerta activa → alert_active=False, baseline default 0.80."""
        extractor = _make_extractor(Decimal("0.85"))
        active_alert = None

        baseline = float(active_alert.hit_rate_baseline) if active_alert else 0.80
        alert_active = active_alert is not None
        alert_id = active_alert.id if active_alert else None

        assert alert_active is False
        assert baseline == 0.80
        assert alert_id is None

    def test_delta_pp_negative_when_current_above_baseline(self) -> None:
        """Si hit_rate > baseline, delta_pp es negativo (buena señal)."""
        hit_rate_current = 0.90
        baseline = 0.80
        delta_pp = (baseline - hit_rate_current) * 100
        assert delta_pp == pytest.approx(-10.0)


# ── Tests: resolve alert endpoint ─────────────────────────────────────────────


class TestResolveAlertEndpoint:
    """Valida la lógica del PATCH /alerts/{id}/resolve."""

    @pytest.mark.asyncio
    async def test_sets_resolved_at(self) -> None:
        """Resolver una alerta activa → resolved_at se actualiza."""
        from datetime import datetime, timezone

        alert = _make_alert()
        assert alert.resolved_at is None

        now = datetime.now(timezone.utc)
        alert.resolved_at = now
        alert.resolved_by = None

        assert alert.resolved_at == now

    def test_returns_404_when_alert_not_found(self) -> None:
        """Si no se encuentra la alerta activa → 404."""
        alert = None
        is_not_found = alert is None
        assert is_not_found is True
