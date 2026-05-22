"""Translation completion + coverage endpoints (PIM import pipeline v2).

Endpoints:
- ``POST /api/v1/products/translations/complete``  — AI-complete missing translations
- ``GET  /api/v1/products/translations/coverage``  — per-lang coverage stats
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.product import Product, ProductTranslation
from app.services.translations.completion_service import (
    CompletionResult,
    TranslationCompletionService,
)

router = APIRouter(prefix="/products/translations", tags=["translations"])

_SUPPORTED_LANGS = ["en", "es", "fr", "de", "it", "pt", "ar"]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CompleteTranslationsRequest(BaseModel):
    skus: list[str]
    target_langs: list[str]
    source_lang: str = "en"


class CompletionResultResponse(BaseModel):
    """Pydantic wrapper for CompletionResult dataclass."""

    completed: int
    skipped: int
    errors: int
    details: list[dict[str, Any]]

    @classmethod
    def from_result(cls, result: CompletionResult) -> CompletionResultResponse:
        return cls(**asdict(result))


class TranslationCoverageResponse(BaseModel):
    total_products: int
    coverage: list[dict[str, Any]]  # [{lang, count, pct}]
    missing_by_lang: dict[str, int]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/complete",
    response_model=CompletionResultResponse,
    summary="AI-complete missing product translations.",
    description=(
        "Triggers the TranslationCompletionService to fill in missing "
        "translations for the given SKUs and target languages using Claude."
    ),
    operation_id="translationsComplete",
)
async def complete_translations(
    body: CompleteTranslationsRequest,
    _: Annotated[object, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CompletionResultResponse:
    service = TranslationCompletionService(session)
    result = await service.complete(
        skus=body.skus,
        target_langs=body.target_langs,
        source_lang=body.source_lang,
        actor_id=None,
    )
    return CompletionResultResponse.from_result(result)


@router.get(
    "/coverage",
    response_model=TranslationCoverageResponse,
    summary="Get per-language translation coverage stats.",
    description=(
        "Returns total product count plus how many products have a non-null "
        "name in each supported language, and how many are missing."
    ),
    operation_id="translationsCoverage",
)
async def get_translation_coverage(
    _: Annotated[object, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TranslationCoverageResponse:
    total_result = await session.execute(select(func.count()).select_from(Product))
    total: int = total_result.scalar_one()

    coverage_rows = await session.execute(
        select(ProductTranslation.lang, func.count().label("cnt"))
        .where(ProductTranslation.name.isnot(None))
        .group_by(ProductTranslation.lang)
    )
    coverage = [
        {
            "lang": lang,
            "count": cnt,
            "pct": round(cnt / total * 100, 1) if total else 0.0,
        }
        for lang, cnt in coverage_rows.all()
    ]
    missing_by_lang = {
        lang: total - next((c["count"] for c in coverage if c["lang"] == lang), 0)
        for lang in _SUPPORTED_LANGS
    }
    return TranslationCoverageResponse(
        total_products=total,
        coverage=coverage,
        missing_by_lang=missing_by_lang,
    )
