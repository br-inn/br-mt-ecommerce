"""enhanced_match_service.py — Pipeline de 3 capas con LLM y visión para matching mejorado.

Orquesta el matching de productos industriales en tres capas:

  Capa 0: score_match() determinista
    score ≥ 75  → AUTO_VALIDATE (sin LLM)
    score < 30  → DISCARD
    30 ≤ score < 75 → Capa 1

  Capa 1: extract_specs_from_amazon_text() — Claude Haiku 4.5
    Re-run score_match() con specs enriquecidas
    nuevo_score ≥ 70 AND confidence ≥ 0.7 → AUTO_VALIDATE
    else → Capa 2 (solo si hay imágenes)

  Capa 2: compare_product_images() — Claude Haiku 4.5 Vision
    DIFFERENT_TYPE → DISCARD (score = 0)
    SAME_TYPE | UNCERTAIN → HUMAN_QUEUE

Diseño:
  - Si cualquier capa LLM falla → se retorna el resultado de la capa anterior (nunca propaga excepción)
  - Solo como FILTRO NEGATIVO la visión: DIFFERENT_TYPE descarta, SAME_TYPE no auto-valida
  - Método `method` en el resultado describe qué capa tomó la decisión
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.matching.llm_spec_extractor import extract_specs_from_amazon_text
from app.services.matching.match_scorer import score_match
from app.services.matching.ports import CandidateRaw
from app.services.matching.vision_matcher import VisualVerdict, compare_product_images

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds del pipeline
# ---------------------------------------------------------------------------

# Capa 0: decisión solo con scorer determinista
LAYER0_AUTO_VALIDATE_THRESHOLD = 75
LAYER0_DISCARD_THRESHOLD = 30

# Capa 1: umbral para auto-validar tras enriquecimiento LLM
LAYER1_AUTO_VALIDATE_THRESHOLD = 70
LAYER1_MIN_CONFIDENCE = 0.7


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass
class EnhancedMatchResult:
    """Resultado del pipeline de matching mejorado.

    Attributes:
        score: Puntuación final 0-100.
        method: Capa que tomó la decisión:
            "deterministic"  — Capa 0 (sin LLM)
            "llm_enriched"   — Capa 1 (LLM enriqueció specs, nuevo score)
            "vision_rejected" — Capa 2 (visión dijo DIFFERENT_TYPE)
            "human_queue"    — No se pudo decidir automáticamente
        auto_validate: True si el pipeline recomienda validar automáticamente.
        llm_confidence: Confianza del extractor LLM (None si no se usó Capa 1).
        visual_verdict: Veredicto visual como string (None si no se usó Capa 2).
        breakdown: Breakdown del scorer (dimensiones → (matched, pts, max, note)).
        llm_specs: Specs extraídas por LLM (None si no se usó Capa 1).
    """

    score: int
    method: str  # "deterministic" | "llm_enriched" | "vision_rejected" | "human_queue"
    auto_validate: bool
    llm_confidence: float | None = None
    visual_verdict: str | None = None
    breakdown: dict[str, Any] = field(default_factory=dict)
    llm_specs: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


async def enhanced_score(
    product_data: dict[str, Any],
    candidate: CandidateRaw,
    mt_image_url: str | None = None,
) -> EnhancedMatchResult:
    """Ejecuta el pipeline de 3 capas y retorna el resultado del matching.

    Args:
        product_data: Datos del producto MT (salida de MatchService._product_to_dict()).
        candidate: CandidateRaw del fetcher (con title, specs, raw_payload).
        mt_image_url: URL de imagen del producto MT (Supabase Storage). None = sin visión.

    Returns:
        EnhancedMatchResult con la decisión y metadata de trazabilidad.
    """
    # Extraer datos del candidato Amazon
    amazon_title = candidate.title or ""
    amazon_specs = dict(candidate.specs or {})
    # También buscar specs en raw_payload si no están en specs directamente
    if not amazon_specs and candidate.raw_payload:
        amazon_specs = dict(candidate.raw_payload)

    amazon_image_url: str | None = (
        candidate.raw_payload.get("image_url") if candidate.raw_payload else None
    )

    # ─── CAPA 0: Scorer determinista ───
    try:
        layer0_score, layer0_breakdown = score_match(product_data, amazon_specs, amazon_title)
    except Exception as exc:
        logger.exception("enhanced_score: error en score_match (capa 0): %s", exc)
        return EnhancedMatchResult(
            score=0,
            method="deterministic",
            auto_validate=False,
            breakdown={"error": str(exc)},
        )

    # AUTO_VALIDATE: score alto sin necesidad de LLM
    if layer0_score >= LAYER0_AUTO_VALIDATE_THRESHOLD:
        logger.debug(
            "enhanced_score: capa 0 AUTO_VALIDATE score=%d (≥%d)",
            layer0_score,
            LAYER0_AUTO_VALIDATE_THRESHOLD,
        )
        return EnhancedMatchResult(
            score=layer0_score,
            method="deterministic",
            auto_validate=True,
            breakdown=layer0_breakdown,
        )

    # DISCARD: score muy bajo, no vale la pena gastar LLM
    if layer0_score < LAYER0_DISCARD_THRESHOLD:
        logger.debug(
            "enhanced_score: capa 0 DISCARD score=%d (<%d)",
            layer0_score,
            LAYER0_DISCARD_THRESHOLD,
        )
        return EnhancedMatchResult(
            score=layer0_score,
            method="deterministic",
            auto_validate=False,
            breakdown=layer0_breakdown,
        )

    # ─── CAPA 1: Enriquecimiento con LLM ───
    logger.debug("enhanced_score: capa 0 score=%d → enriqueciendo con LLM", layer0_score)

    # Obtener descripción desde raw_payload (guardada por curl_cffi_amazon_uae).
    amazon_description = ""
    if candidate.raw_payload:
        amazon_description = str(
            candidate.raw_payload.get("description_text")
            or candidate.raw_payload.get("description")
            or ""
        )

    try:
        llm_specs = await extract_specs_from_amazon_text(
            amazon_title=amazon_title,
            amazon_description=amazon_description,
            amazon_specs_raw=amazon_specs if amazon_specs else None,
        )
    except Exception as exc:
        # Si LLM falla → mantener resultado de capa 0
        logger.exception("enhanced_score: error en LLM extractor (capa 1): %s", exc)
        return EnhancedMatchResult(
            score=layer0_score,
            method="deterministic",
            auto_validate=False,
            breakdown=layer0_breakdown,
        )

    # Enriquecer amazon_specs con los campos extraídos por LLM
    enriched_specs = dict(amazon_specs)
    llm_dict = llm_specs.model_dump(exclude_none=True)
    llm_confidence = llm_dict.pop("confidence", 0.0)
    enriched_specs.update(llm_dict)

    # Re-run scorer con specs enriquecidas
    try:
        layer1_score, layer1_breakdown = score_match(product_data, enriched_specs, amazon_title)
    except Exception as exc:
        logger.exception("enhanced_score: error en score_match capa 1 (re-run): %s", exc)
        # Fallback al resultado de capa 0
        return EnhancedMatchResult(
            score=layer0_score,
            method="deterministic",
            auto_validate=False,
            breakdown=layer0_breakdown,
            llm_confidence=llm_confidence,
            llm_specs=llm_dict,
        )

    logger.debug("enhanced_score: capa 1 score=%d confidence=%.2f", layer1_score, llm_confidence)

    # AUTO_VALIDATE: score suficientemente alto tras enriquecimiento con confianza alta
    if layer1_score >= LAYER1_AUTO_VALIDATE_THRESHOLD and llm_confidence >= LAYER1_MIN_CONFIDENCE:
        return EnhancedMatchResult(
            score=layer1_score,
            method="llm_enriched",
            auto_validate=True,
            llm_confidence=llm_confidence,
            breakdown=layer1_breakdown,
            llm_specs=llm_dict if llm_dict else None,
        )

    # ─── CAPA 2: Visión (solo si hay imágenes disponibles) ───
    if not mt_image_url or not amazon_image_url:
        logger.debug(
            "enhanced_score: capa 2 omitida (sin imágenes) → HUMAN_QUEUE score=%d", layer1_score
        )
        return EnhancedMatchResult(
            score=layer1_score,
            method="human_queue",
            auto_validate=False,
            llm_confidence=llm_confidence,
            breakdown=layer1_breakdown,
            llm_specs=llm_dict if llm_dict else None,
        )

    logger.debug("enhanced_score: capa 2 → comparando imágenes")

    try:
        visual_verdict, visual_reason = await compare_product_images(mt_image_url, amazon_image_url)
    except Exception as exc:
        # Si visión falla → HUMAN_QUEUE con score de capa 1
        logger.exception("enhanced_score: error en vision_matcher (capa 2): %s", exc)
        return EnhancedMatchResult(
            score=layer1_score,
            method="human_queue",
            auto_validate=False,
            llm_confidence=llm_confidence,
            visual_verdict=VisualVerdict.UNCERTAIN.value,
            breakdown=layer1_breakdown,
            llm_specs=llm_dict if llm_dict else None,
        )

    logger.debug("enhanced_score: visión verdict=%s reason=%s", visual_verdict.value, visual_reason)

    # FILTRO NEGATIVO: solo DIFFERENT_TYPE descarta
    if visual_verdict == VisualVerdict.DIFFERENT_TYPE:
        return EnhancedMatchResult(
            score=0,
            method="vision_rejected",
            auto_validate=False,
            llm_confidence=llm_confidence,
            visual_verdict=visual_verdict.value,
            breakdown=layer1_breakdown,
            llm_specs=llm_dict if llm_dict else None,
        )

    # SAME_TYPE o UNCERTAIN → HUMAN_QUEUE
    return EnhancedMatchResult(
        score=layer1_score,
        method="human_queue",
        auto_validate=False,
        llm_confidence=llm_confidence,
        visual_verdict=visual_verdict.value,
        breakdown=layer1_breakdown,
        llm_specs=llm_dict if llm_dict else None,
    )


__all__ = ["LAYER0_AUTO_VALIDATE_THRESHOLD", "EnhancedMatchResult", "enhanced_score"]
