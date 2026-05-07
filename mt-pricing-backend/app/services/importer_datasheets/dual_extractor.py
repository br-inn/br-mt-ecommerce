"""Dual extractor — combina spec_parser regex + vision_extractor (US-1A-06-04-V2).

Estrategia (S5):
1. Ejecuta el extractor regex de S4 (:func:`parse_specs_from_text` sobre
   :func:`extract_text_from_pdf`).
2. Si Vision está habilitado (``MT_LIVE_NETWORK=true`` + provider key), lanza
   :class:`VisionExtractor` en paralelo lógico (mismo PDF).
3. Combina resultados con confidence scoring:
   - Si ambos agree → spec ganador, confidence = max(regex_conf, vision_conf).
   - Si discrepan → vision gana (mayor capacidad semántica) pero confidence
     se penaliza (- 0.2) y se agrega flag ``disagreement=true``.
   - Si sólo uno detecta el spec → ese spec wins, confidence = ese conf.

Outputs en formato compatible con :class:`DatasheetSpecs.to_dict()` para
poder reemplazar el extractor S4 en el applier sin romper el contrato.

Tests inyectan los componentes regex/vision como callables/Protocols para
evitar dependencias en pdfplumber/HTTP.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.services.importer_datasheets.pdf_extractor import (
    PDFExtractionError,
    extract_text_from_pdf,
)
from app.services.importer_datasheets.spec_parser import (
    DatasheetSpecs,
    parse_specs_from_text,
)
from app.services.importer_datasheets.vision_extractor import (
    VisionExtractionResult,
    VisionExtractor,
)

logger = logging.getLogger(__name__)


SPEC_KEYS: tuple[str, ...] = ("dn", "pn", "material", "seal")


@dataclass(slots=True)
class DualExtractionResult:
    """Resultado combinado regex + vision con confidence per-spec."""

    specs: dict[str, Any] = field(default_factory=dict)
    per_spec_confidence: dict[str, float] = field(default_factory=dict)
    disagreement: bool = False
    regex_specs: dict[str, Any] = field(default_factory=dict)
    vision_specs: dict[str, Any] = field(default_factory=dict)
    vision_skipped: bool = False
    vision_skip_reason: str | None = None
    overall_confidence: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "specs": dict(self.specs),
            "per_spec_confidence": dict(self.per_spec_confidence),
            "disagreement": self.disagreement,
            "regex_specs": dict(self.regex_specs),
            "vision_specs": dict(self.vision_specs),
            "vision_skipped": self.vision_skipped,
            "vision_skip_reason": self.vision_skip_reason,
            "overall_confidence": round(self.overall_confidence, 4),
            "error": self.error,
        }


# Type aliases para facilitar mocking (ambos sync/async no importan — los
# wrappers `_run_regex`/`_run_vision` los acomodan).
RegexExtractorCallable = Callable[[bytes], DatasheetSpecs]
VisionExtractCallable = Callable[
    ..., Awaitable[VisionExtractionResult]
]


# Confidence base para regex hits (S4 era binario — encontrado o no, así que
# 0.7 refleja "alta confianza pero no semantic-aware"). Vision aporta el
# `confidence` agregado de su propia heurística.
_REGEX_HIT_CONFIDENCE: float = 0.7
_DISAGREEMENT_PENALTY: float = 0.2


class DualExtractor:
    """Combina regex (S4) + vision (S5) en un único contrato.

    Constructor inyectable::

        DualExtractor(
            regex_extractor=mock_regex,   # bytes → DatasheetSpecs
            vision_extractor=mock_vision, # VisionExtractor mockeado
        )

    Por defecto usa el spec_parser regex y un :class:`VisionExtractor` con
    el client default (controlado por env). Tests siempre inyectan ambos.
    """

    def __init__(
        self,
        *,
        regex_extractor: RegexExtractorCallable | None = None,
        vision_extractor: VisionExtractor | None = None,
    ) -> None:
        self._regex = regex_extractor or _default_regex_extractor
        self._vision = vision_extractor or VisionExtractor()

    async def extract(
        self,
        *,
        pdf_bytes: bytes,
        filename: str = "datasheet.pdf",
    ) -> DualExtractionResult:
        result = DualExtractionResult()

        # 1. Regex extractor
        try:
            regex_specs = self._regex(pdf_bytes)
        except PDFExtractionError as exc:
            logger.warning(
                "dual_extractor: regex extractor failed code=%s msg=%s",
                exc.code,
                exc.message,
            )
            result.error = f"regex_failed:{exc.code}"
            regex_specs = DatasheetSpecs()
        except Exception as exc:  # noqa: BLE001
            logger.exception("dual_extractor: regex extractor exception")
            result.error = f"regex_failed:{type(exc).__name__}"
            regex_specs = DatasheetSpecs()

        regex_dict = regex_specs.to_dict()
        result.regex_specs = regex_dict

        # 2. Vision extractor (best-effort).
        try:
            vision_result = await self._vision.extract(
                pdf_bytes=pdf_bytes, filename=filename
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("dual_extractor: vision extractor exception")
            vision_result = VisionExtractionResult(
                error=f"vision_failed:{type(exc).__name__}"
            )

        result.vision_skipped = vision_result.skipped
        result.vision_skip_reason = vision_result.skip_reason
        result.vision_specs = dict(vision_result.specs)
        if vision_result.error and not result.error:
            # Vision failure is informational — regex still wins.
            logger.info(
                "dual_extractor: vision unavailable (%s)",
                vision_result.error,
            )

        # 3. Combine
        combined: dict[str, Any] = {}
        per_spec_conf: dict[str, float] = {}
        disagreement = False

        for key in SPEC_KEYS:
            r_val = regex_dict.get(key)
            v_val = result.vision_specs.get(key)
            if r_val and v_val:
                # Normaliza a string strip/lower para comparación tolerante.
                if _normalize(r_val) == _normalize(v_val):
                    combined[key] = r_val
                    per_spec_conf[key] = max(
                        _REGEX_HIT_CONFIDENCE,
                        float(vision_result.confidence),
                    )
                else:
                    # Discrepancia: vision gana (semantic-aware), confianza penalizada.
                    combined[key] = v_val
                    per_spec_conf[key] = max(
                        0.0,
                        float(vision_result.confidence) - _DISAGREEMENT_PENALTY,
                    )
                    disagreement = True
            elif r_val:
                combined[key] = r_val
                per_spec_conf[key] = _REGEX_HIT_CONFIDENCE
            elif v_val:
                combined[key] = v_val
                per_spec_conf[key] = float(vision_result.confidence) or 0.5

        # extras (sólo desde vision — regex S4 no produce extras estructurados).
        v_extra = result.vision_specs.get("extra")
        if isinstance(v_extra, dict) and v_extra:
            combined["extra"] = dict(v_extra)

        result.specs = combined
        result.per_spec_confidence = per_spec_conf
        result.disagreement = disagreement
        if per_spec_conf:
            result.overall_confidence = sum(per_spec_conf.values()) / len(
                per_spec_conf
            )
        else:
            result.overall_confidence = 0.0

        logger.info(
            "dual_extractor.extracted",
            extra={
                "filename": filename,
                "specs_count": len(combined),
                "disagreement": disagreement,
                "vision_skipped": result.vision_skipped,
                "overall_confidence": result.overall_confidence,
            },
        )
        return result


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
def _default_regex_extractor(pdf_bytes: bytes) -> DatasheetSpecs:
    """Pipeline S4 default: extract_text_from_pdf → parse_specs_from_text."""
    text = extract_text_from_pdf(pdf_bytes)
    return parse_specs_from_text(text)


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return str(value).strip().lower()
    return value.strip().lower()


__all__ = [
    "DualExtractionResult",
    "DualExtractor",
    "SPEC_KEYS",
]
