"""Servicio de validación de recetas — corre una receta contra una URL de muestra
y registra el resultado por field."""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.scraper_sources import ScraperSourceRepository
from app.services.scraper.recipe_extractor import extract_records, field_results

HtmlFetcher = Callable[[str], Awaitable[str]]


class SourceValidationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ScraperSourceRepository(session)

    async def validate(
        self,
        source_id: UUID,
        recipe_id: UUID,
        test_url: str,
        *,
        html_fetcher: HtmlFetcher,
    ) -> dict[str, Any]:
        """Corre la receta contra ``test_url``, persiste un test run y actualiza
        el ``validation_status`` de la receta. Devuelve records + field_results."""
        recipe_row = await self._repo.get_recipe(recipe_id)
        if recipe_row is None:
            raise ValueError(f"recipe {recipe_id} not found")

        html = await html_fetcher(test_url)
        records = extract_records(html, recipe_row.recipe)
        results = field_results(records, recipe_row.recipe)

        await self._repo.record_test_run(
            source_id=source_id,
            recipe_id=recipe_id,
            test_url=test_url,
            extracted=records,
            field_results=results,
        )

        all_pass = bool(results) and all(v == "pass" for v in results.values())
        recipe_row.validation_status = "passing" if all_pass else "failing"
        await self._session.flush()

        return {
            "records": records,
            "field_results": results,
            "status": recipe_row.validation_status,
        }
