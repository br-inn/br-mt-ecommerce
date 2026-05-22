from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import ProductTranslation
from app.services.importer.row_writer import TranslationWriter

logger = logging.getLogger(__name__)

_LLM_MODEL = "claude-sonnet-4-6"
_BATCH_SIZE = 20


@dataclass
class CompletionResult:
    completed: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[dict] = field(default_factory=list)


class TranslationCompletionService:
    """Completes missing translations using Claude. Writes via TranslationWriter."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._writer = TranslationWriter()

    async def complete(
        self,
        skus: list[str],
        target_langs: list[str],
        source_lang: str = "en",
        actor_id: UUID | None = None,
    ) -> CompletionResult:
        result = CompletionResult()
        if not skus or not target_langs:
            return result

        # Load source names from DB
        rows = await self._session.execute(
            select(ProductTranslation).where(
                ProductTranslation.sku.in_(skus),
                ProductTranslation.lang == source_lang,
            )
        )
        source_by_sku: dict[str, str] = {
            row.sku: row.name
            for (row,) in rows.all()
            if row.name
        }

        # Process in batches
        for i in range(0, len(skus), _BATCH_SIZE):
            batch = skus[i: i + _BATCH_SIZE]
            batch_context = [
                {"sku": sku, "name": source_by_sku.get(sku, sku)}
                for sku in batch
            ]
            try:
                translations = self._call_llm(batch_context, source_lang, target_langs)
            except Exception as exc:
                logger.warning("LLM error in batch %d: %s", i, exc)
                result.errors += len(batch)
                continue

            for item in translations:
                sku = item.get("sku")
                lang = item.get("lang")
                name = item.get("name")
                if not (sku and lang and name):
                    continue
                try:
                    await self._writer.write(
                        session=self._session,
                        sku=sku,
                        translations={lang: name},
                        locked_fields=set(),
                    )
                    result.completed += 1
                    result.details.append({"sku": sku, "lang": lang, "status": "ai_generated"})
                except Exception as exc:
                    logger.warning("Error writing translation sku=%s lang=%s: %s", sku, lang, exc)
                    result.errors += 1

        return result

    def _call_llm(
        self,
        products: list[dict],
        source_lang: str,
        target_langs: list[str],
    ) -> list[dict]:
        lang_list = ", ".join(target_langs)
        products_text = "\n".join(
            f"  - sku: {p['sku']}, name ({source_lang}): {p['name']}"
            for p in products
        )
        prompt = (
            f"You are a product name translator for an industrial PVF "
            f"(pipes, valves, fittings) catalog.\n\n"
            f"Translate each product name to: {lang_list}.\n"
            f"Keep technical terms (DN25, PN16, ISO, etc.) unchanged.\n"
            f"Products:\n{products_text}\n\n"
            f"Return a JSON array — no markdown, no explanation:\n"
            f'[{{"sku":"<sku>","lang":"<lang>","name":"<translated>"}},...]\n'
            f"Include one entry per (sku, lang) combination."
        )
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=_LLM_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```[^\n]*\n?", "", text, flags=re.MULTILINE).strip()
        text = re.sub(r"```$", "", text).strip()
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, dict)]
