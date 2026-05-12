"""MetricsCollector — calcula y exporta métricas del POC de matching.

Métricas calculadas:
- precision  = TP / (TP + FP)
- recall     = TP / (TP + FN)
- FP rate    = FP / (FP + TN)
- FN rate    = FN / (TP + FN)   (= 1 - recall)
- ECE        = Expected Calibration Error (via calibrator.expected_calibration_error)
- cobertura  = SKUs con al menos 1 candidato "peer" / total SKUs

Ground-truth:
  - "accept" label en MatchCandidate  → positivo real (TP si kind=peer, FN si kind!=peer)
  - "reject" label en MatchCandidate  → negativo real (FP si kind=peer, TN si kind!=peer)
  - Sin label (pending/skip)          → excluido del cálculo de precision/recall

Para el POC con stubs, los labels se derivan sintéticamente de los scores
usando un umbral configurable (DEFAULT_SYNTHETIC_ACCEPT_THRESHOLD).
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.services.matching.calibrator import expected_calibration_error

logger = logging.getLogger(__name__)

# Umbral sintético: si el score del candidato supera este valor Y el kind
# es "peer", se considera verdadero positivo cuando no hay label real.
DEFAULT_SYNTHETIC_ACCEPT_THRESHOLD = 70

# Umbrales de aceptación (Acceptance Criteria del story)
AC_FP_MAX = 0.02    # FP rate < 2%
AC_FN_MAX = 0.10    # FN rate < 10%
AC_ECE_MAX = 0.05   # ECE < 5%
AC_COV_MIN = 0.90   # cobertura >= 90%


@dataclass
class CandidateRecord:
    """Registro mínimo de un candidato para el cálculo de métricas."""

    sku: str
    channel: str
    external_id: str
    kind: str                        # peer | drop | unknown
    score: int                       # 0-100
    label: str | None = None         # accept | reject | skip | None
    calibrated_confidence: float | None = None


@dataclass
class MarketplaceMetrics:
    """Métricas por marketplace."""

    marketplace: str
    n_skus: int = 0
    n_candidates: int = 0
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    skus_with_peer: int = 0
    ece: float = 0.0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def fp_rate(self) -> float:
        denom = self.fp + self.tn
        return self.fp / denom if denom else 0.0

    @property
    def fn_rate(self) -> float:
        return 1.0 - self.recall if (self.tp + self.fn) > 0 else 0.0

    @property
    def cobertura(self) -> float:
        return self.skus_with_peer / self.n_skus if self.n_skus else 0.0

    def passes_ac(self) -> dict[str, bool]:
        return {
            "fp_rate_ok": self.fp_rate < AC_FP_MAX,
            "fn_rate_ok": self.fn_rate < AC_FN_MAX,
            "ece_ok": self.ece < AC_ECE_MAX,
            "cobertura_ok": self.cobertura >= AC_COV_MIN,
        }

    def all_ac_pass(self) -> bool:
        return all(self.passes_ac().values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "marketplace": self.marketplace,
            "n_skus": self.n_skus,
            "n_candidates": self.n_candidates,
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "fp_rate": round(self.fp_rate, 4),
            "fn_rate": round(self.fn_rate, 4),
            "ece": round(self.ece, 4),
            "cobertura": round(self.cobertura, 4),
            "skus_with_peer": self.skus_with_peer,
            "passes_ac": self.passes_ac(),
            "all_ac_pass": self.all_ac_pass(),
        }


@dataclass
class PocMetrics:
    """Métricas globales del POC (agregado de todos los marketplaces)."""

    run_date: str = field(default_factory=lambda: date.today().isoformat())
    n_skus_total: int = 0
    marketplaces: list[MarketplaceMetrics] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    use_stubs: bool = True
    errors: list[str] = field(default_factory=list)
    # Unión de SKUs con al menos un peer en cualquier canal (para cobertura global correcta).
    unique_skus_with_peer: int = 0

    def aggregate(self) -> MarketplaceMetrics:
        """Métricas globales sumando todos los marketplaces."""
        agg = MarketplaceMetrics(marketplace="ALL")
        agg.n_skus = self.n_skus_total
        for m in self.marketplaces:
            agg.n_candidates += m.n_candidates
            agg.tp += m.tp
            agg.fp += m.fp
            agg.tn += m.tn
            agg.fn += m.fn
        # Cobertura global: unión de SKUs con peer (no suma de por canal, que
        # puede superar 1.0 si el mismo SKU aparece en varios marketplaces).
        agg.skus_with_peer = self.unique_skus_with_peer
        # ECE agregada = media ponderada por candidatos.
        total_cands = sum(m.n_candidates for m in self.marketplaces)
        if total_cands and self.marketplaces:
            agg.ece = sum(
                m.ece * m.n_candidates for m in self.marketplaces
            ) / total_cands
        return agg

    def as_dict(self) -> dict[str, Any]:
        agg = self.aggregate()
        return {
            "run_date": self.run_date,
            "n_skus_total": self.n_skus_total,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "use_stubs": self.use_stubs,
            "errors_count": len(self.errors),
            "errors": self.errors[:20],  # cap para el JSON
            "aggregate": agg.as_dict(),
            "by_marketplace": [m.as_dict() for m in self.marketplaces],
        }


class MetricsCollector:
    """Acumula registros de candidatos y computa métricas finales.

    Uso típico::

        collector = MetricsCollector(n_skus_total=500, use_stubs=True)
        for candidate in candidates:
            collector.add(candidate)
        metrics = collector.compute()
        collector.export_json(metrics, Path("docs/rnd/poc-results-2026-05-12.json"))
        collector.export_csv(metrics, Path("docs/rnd/poc-results-2026-05-12.csv"))
    """

    def __init__(
        self,
        n_skus_total: int,
        *,
        use_stubs: bool = True,
        synthetic_threshold: int = DEFAULT_SYNTHETIC_ACCEPT_THRESHOLD,
    ) -> None:
        self.n_skus_total = n_skus_total
        self.use_stubs = use_stubs
        self.synthetic_threshold = synthetic_threshold
        self._records: list[CandidateRecord] = []
        self._errors: list[str] = []
        self._elapsed: float = 0.0
        self._warned_synthetic: bool = False

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------
    def add(self, record: CandidateRecord) -> None:
        self._records.append(record)

    def add_error(self, msg: str) -> None:
        self._errors.append(msg)

    def set_elapsed(self, seconds: float) -> None:
        self._elapsed = seconds

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------
    def compute(self) -> PocMetrics:
        """Calcula métricas por marketplace y agrega."""
        channels: dict[str, list[CandidateRecord]] = {}
        for r in self._records:
            channels.setdefault(r.channel, []).append(r)

        marketplace_metrics: list[MarketplaceMetrics] = []
        global_skus_with_peer: set[str] = set()
        for channel, records in sorted(channels.items()):
            m = self._compute_for_channel(channel, records)
            marketplace_metrics.append(m)
            global_skus_with_peer.update(r.sku for r in records if r.kind == "peer")

        return PocMetrics(
            n_skus_total=self.n_skus_total,
            marketplaces=marketplace_metrics,
            elapsed_seconds=self._elapsed,
            use_stubs=self.use_stubs,
            errors=list(self._errors),
            unique_skus_with_peer=len(global_skus_with_peer),
        )

    def _compute_for_channel(
        self, channel: str, records: list[CandidateRecord]
    ) -> MarketplaceMetrics:
        m = MarketplaceMetrics(marketplace=channel)
        m.n_candidates = len(records)

        # Número de SKUs únicos en este canal.
        skus = {r.sku for r in records}
        m.n_skus = len(skus)

        # SKUs que tienen al menos un candidato "peer".
        m.skus_with_peer = len({r.sku for r in records if r.kind == "peer"})

        # Clasificación TP/FP/TN/FN.
        # Si hay label real → usarla; si no → inferir sintéticamente.
        predictions: list[float] = []
        labels_bin: list[int] = []

        for r in records:
            label = self._resolve_label(r)
            if label is None:
                continue  # "skip" o sin ground-truth — excluir
            is_positive_pred = r.kind == "peer"
            is_positive_gt = label == "accept"

            if is_positive_pred and is_positive_gt:
                m.tp += 1
            elif is_positive_pred and not is_positive_gt:
                m.fp += 1
            elif not is_positive_pred and not is_positive_gt:
                m.tn += 1
            else:
                m.fn += 1

            # Para ECE: usar calibrated_confidence si existe, sino score/100.
            pred_prob = (
                r.calibrated_confidence
                if r.calibrated_confidence is not None
                else r.score / 100.0
            )
            predictions.append(pred_prob)
            labels_bin.append(1 if is_positive_gt else 0)

        if predictions:
            m.ece = expected_calibration_error(predictions, labels_bin)
        return m

    def _resolve_label(self, r: CandidateRecord) -> str | None:
        """Devuelve "accept" | "reject" | None.

        Prioridad:
        1. Label real del revisor humano.
        2. Inferencia sintética por score + kind (útil para POC con stubs).
        """
        if r.label == "accept":
            return "accept"
        if r.label == "reject":
            return "reject"
        if r.label == "skip":
            return None
        # Sin label → inferencia sintética (warn once — métricas no reflejan GT real).
        if not self._warned_synthetic:
            logger.warning(
                "metrics: usando inferencia sintética de labels (use_stubs=%s) — "
                "métricas no reflejan ground truth real; ignorar FP/FN en modo stub",
                self.use_stubs,
            )
            self._warned_synthetic = True
        if r.score >= self.synthetic_threshold:
            return "accept"
        return "reject"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_json(self, metrics: PocMetrics, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metrics.as_dict(), f, indent=2, ensure_ascii=False)

    def export_csv(self, metrics: PocMetrics, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        agg = metrics.aggregate()
        rows = [m.as_dict() for m in metrics.marketplaces] + [agg.as_dict()]

        flat_keys = [
            "marketplace", "n_skus", "n_candidates",
            "tp", "fp", "tn", "fn",
            "precision", "recall", "fp_rate", "fn_rate",
            "ece", "cobertura", "skus_with_peer", "all_ac_pass",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=flat_keys, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


def _is_failure(v: bool | int | float) -> bool:
    """Determina si un valor de AC representa un fallo (fix W-4: falsy non-bool).

    Regla:
    - bool False  → fallo
    - bool True   → ok
    - int/float < 0 → fallo
    - int/float >= 0 (incl. 0, 0.0) → ok (no son fallos aunque sean falsy)
    """
    if isinstance(v, bool):
        return v is False
    if isinstance(v, (int, float)):
        return v < 0
    return False


def _collect_failures(ac_results: dict[str, bool | int | float]) -> list[str]:
    """Retorna lista de claves de ACs que fallan.

    Usa :func:`_is_failure` para evitar el bug W-4 donde valores falsy
    no-bool (0, 0.0) eran incorrectamente tratados como fallos.

    Args:
        ac_results: Diccionario {nombre_ac: resultado}.

    Returns:
        Lista de nombres de ACs fallidos.
    """
    return [k for k, v in ac_results.items() if _is_failure(v)]


__all__ = [
    "AC_COV_MIN",
    "AC_ECE_MAX",
    "AC_FN_MAX",
    "AC_FP_MAX",
    "CandidateRecord",
    "MarketplaceMetrics",
    "MetricsCollector",
    "PocMetrics",
    "_collect_failures",
    "_is_failure",
]
