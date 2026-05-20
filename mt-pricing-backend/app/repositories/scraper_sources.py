"""Repositorio de ScraperSource y sus recetas versionadas."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scraper_sources import (
    ScraperSource,
    ScraperSourceRecipe,
    ScraperSourceTestRun,
)


class ScraperSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        slug: str,
        base_url: str,
        destination_profile: str,
        fetch_mode: str = "static",
        description: str | None = None,
        competitor_brand_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> ScraperSource:
        source = ScraperSource(
            name=name,
            slug=slug,
            base_url=base_url,
            destination_profile=destination_profile,
            fetch_mode=fetch_mode,
            description=description,
            competitor_brand_id=competitor_brand_id,
            created_by=created_by,
            status="draft",
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def get(self, source_id: UUID) -> ScraperSource | None:
        return await self._session.get(ScraperSource, source_id)

    async def get_by_slug(self, slug: str) -> ScraperSource | None:
        result = await self._session.execute(
            select(ScraperSource).where(ScraperSource.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[ScraperSource]:
        result = await self._session.execute(
            select(ScraperSource).order_by(ScraperSource.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_recipe(
        self, source_id: UUID, recipe: dict[str, Any], *, created_by: UUID | None = None
    ) -> ScraperSourceRecipe:
        result = await self._session.execute(
            select(ScraperSourceRecipe.version)
            .where(ScraperSourceRecipe.source_id == source_id)
            .order_by(ScraperSourceRecipe.version.desc())
            .limit(1)
        )
        last_version = result.scalar_one_or_none()
        row = ScraperSourceRecipe(
            source_id=source_id,
            version=(last_version or 0) + 1,
            recipe=recipe,
            created_by=created_by,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_recipe(self, recipe_id: UUID) -> ScraperSourceRecipe | None:
        return await self._session.get(ScraperSourceRecipe, recipe_id)

    async def get_live_recipe(self, source_id: UUID) -> ScraperSourceRecipe | None:
        result = await self._session.execute(
            select(ScraperSourceRecipe).where(
                ScraperSourceRecipe.source_id == source_id,
                ScraperSourceRecipe.is_live.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def set_recipe_live(self, recipe_id: UUID) -> None:
        recipe = await self._session.get(ScraperSourceRecipe, recipe_id)
        if recipe is None:
            raise ValueError(f"recipe {recipe_id} not found")
        await self._session.execute(
            update(ScraperSourceRecipe)
            .where(
                ScraperSourceRecipe.source_id == recipe.source_id,
                ScraperSourceRecipe.is_live.is_(True),
            )
            .values(is_live=False)
        )
        await self._session.flush()
        recipe.is_live = True
        await self._session.flush()

    async def record_test_run(
        self,
        *,
        source_id: UUID,
        recipe_id: UUID,
        test_url: str,
        extracted: list[dict[str, Any]],
        field_results: dict[str, str],
        html_snapshot_ref: str | None = None,
    ) -> ScraperSourceTestRun:
        run = ScraperSourceTestRun(
            source_id=source_id,
            recipe_id=recipe_id,
            test_url=test_url,
            extracted=extracted,
            field_results=field_results,
            html_snapshot_ref=html_snapshot_ref,
        )
        self._session.add(run)
        await self._session.flush()
        return run
