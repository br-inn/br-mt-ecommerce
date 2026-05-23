"""BrandExtractorService — genera y aplica mapeos de atributos por marca × marketplace.

Patrón inspirado en llm-scraper generate mode (mishushakov/llm-scraper):
en lugar de llamar al LLM en cada scrape, Claude genera el código de extracción
UNA VEZ durante el Bootstrap, y se reutiliza sin LLM en cada monitoring scrape.

Flujo:
  Bootstrap: fetch 3-5 ASINs → raw_pairs → Claude → JSON mapping → DB
  Monitoring: DB → JSON mapping → apply(raw_pairs) → specs canónico
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Canonical spec schema sent to Claude as context
_CANONICAL_SCHEMA = {
    "material": "Material of the valve/fitting body (str, e.g. 'Bronze', 'Stainless Steel 316')",
    "valve_type": "Type of valve (str, e.g. 'Ball Valve', 'Gate Valve', 'Check Valve')",
    "dn": "Nominal diameter / pipe size as string with unit (str, e.g. '1/2\"', '25mm', 'DN25')",
    "pn": "Pressure rating (str, e.g. 'PN16', '16 bar', '232 PSI')",
    "norma": "Standard / certification (str, e.g. 'DIN', 'ANSI', 'BS')",
    "connection_type": "End connection type (str, e.g. 'Threaded', 'Flanged', 'Press Fit')",
    "brand_name": "Manufacturer brand name (str)",
    "model_number": "Model or part number (str)",
    "pressure_max_bar": "Maximum pressure in bar (float)",
    "temp_max_c": "Maximum temperature in Celsius (float)",
    "flow_rate": "Flow rate in m3/h or L/min (float, convert to m3/h if needed)",
}

_SYSTEM_PROMPT = """\
You are a data extraction specialist for industrial product catalogs on Amazon UAE.
Your task: analyze raw Amazon product attribute tables for a specific brand and generate
a JSON mapping that maps Amazon's attribute labels to a canonical schema.

Rules:
- Only include attributes that are reliably present across products of this brand.
- Use the EXACT Amazon label as the key (case-sensitive).
- The value must be a JSON object with:
    "field": one of the canonical field names provided
    "type": one of "str", "float", "int"
    "unit_factor": (optional) float multiplier to convert to canonical unit
    "unit_source": (optional) source unit label, e.g. "PSI" -> converts to bar with factor 0.0689476
- Respond ONLY with valid JSON. No explanation, no markdown fences.
"""


def _build_user_prompt(brand_name: str, marketplace: str, samples: list[dict]) -> str:
    sample_str = json.dumps(samples[:5], indent=2, ensure_ascii=False)
    schema_str = json.dumps(_CANONICAL_SCHEMA, indent=2)
    return (
        f"Brand: {brand_name}\n"
        f"Marketplace: {marketplace}\n\n"
        f"Canonical schema (map TO these fields):\n{schema_str}\n\n"
        f"Sample raw attribute tables from Amazon product pages:\n{sample_str}\n\n"
        "Generate the JSON attribute mapping:"
    )


async def generate_mapping_via_claude(
    brand_name: str,
    marketplace: str,
    sample_raw_pairs: list[dict],  # list of {"label": ..., "value": ...} dicts per ASIN
    model: str = "claude-haiku-4-5-20251001",
) -> dict[str, Any]:
    """Call Claude to generate the JSON attribute mapping for this brand.

    Returns the attribute_map dict or {} on failure.
    """
    import anthropic  # lazy import — not required if feature flag off

    try:
        client = anthropic.Anthropic()
        prompt = _build_user_prompt(brand_name, marketplace, sample_raw_pairs)

        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = message.content[0].text.strip()

        # Strip markdown fences if Claude adds them
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0].strip()

        mapping = json.loads(raw_text)
        if not isinstance(mapping, dict):
            logger.warning("Claude returned non-dict mapping for %s/%s", brand_name, marketplace)
            return {}
        return mapping
    except Exception:
        logger.exception("Claude mapping generation failed for %s/%s", brand_name, marketplace)
        return {}


def apply_mapping(
    attribute_map: dict[str, Any],
    raw_pairs: list[dict],
) -> dict[str, Any]:
    """Apply a JSON attribute_map to a list of raw Amazon attribute pairs.

    Args:
        attribute_map: {"Amazon label": {"field": "canonical", "type": "str|float|int", ...}}
        raw_pairs: [{"label": "Material", "value": "Bronze"}, ...]

    Returns:
        dict with canonical field names and converted values.
    """
    if not attribute_map or not raw_pairs:
        return {}

    pairs_by_label: dict[str, str] = {}
    for pair in raw_pairs:
        label = pair.get("label") or pair.get("key") or ""
        value = pair.get("value") or ""
        if label and value:
            pairs_by_label[label] = str(value).strip()

    result: dict[str, Any] = {}
    for amazon_label, mapping_rule in attribute_map.items():
        if not isinstance(mapping_rule, dict):
            continue
        raw_value = pairs_by_label.get(amazon_label)
        if raw_value is None:
            continue

        field = mapping_rule.get("field")
        dtype = mapping_rule.get("type", "str")
        unit_factor = mapping_rule.get("unit_factor")

        if not field:
            continue

        try:
            if dtype == "float":
                # Extract numeric part (handles "16 bar", "1/2 inch", etc.)
                numeric_str = "".join(c for c in raw_value if c.isdigit() or c in ".,-")
                numeric_str = numeric_str.replace(",", ".")
                converted: Any = float(numeric_str)
                if unit_factor:
                    converted = round(converted * float(unit_factor), 4)
            elif dtype == "int":
                numeric_str = "".join(c for c in raw_value if c.isdigit())
                converted = int(numeric_str) if numeric_str else None
            else:
                converted = raw_value
        except (ValueError, InvalidOperation, AttributeError):
            converted = raw_value  # keep as str on parse failure

        if converted is not None:
            result[field] = converted

    return result


class BrandExtractorService:
    """Service to generate, cache, and apply brand-specific attribute mappings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_mapping(self, brand_id: UUID, marketplace: str) -> dict[str, Any] | None:
        """Load cached attribute_map for brand × marketplace. Returns None if not found."""
        from app.db.models.comparator import BrandExtractor

        result = await self._session.execute(
            select(BrandExtractor).where(
                BrandExtractor.brand_id == brand_id,
                BrandExtractor.marketplace == marketplace,
            )
        )
        extractor = result.scalar_one_or_none()
        if extractor is None:
            return None

        # Update last_used_at (fire-and-forget, no await needed for the update)
        await self._session.execute(
            update(BrandExtractor)
            .where(BrandExtractor.id == extractor.id)
            .values(last_used_at=datetime.now(UTC))
        )
        return extractor.attribute_map or {}

    async def save_mapping(
        self,
        brand_id: UUID,
        marketplace: str,
        attribute_map: dict[str, Any],
        sample_asins: list[str],
        generated_by: str,
    ) -> None:
        """Upsert the attribute_map for brand × marketplace."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.db.models.comparator import BrandExtractor

        now = datetime.now(UTC)
        stmt = pg_insert(BrandExtractor).values(
            brand_id=brand_id,
            marketplace=marketplace,
            attribute_map=attribute_map,
            sample_asins=sample_asins,
            generated_by=generated_by,
            generated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_brand_extractor",
            set_={
                "attribute_map": stmt.excluded.attribute_map,
                "sample_asins": stmt.excluded.sample_asins,
                "generated_by": stmt.excluded.generated_by,
                "generated_at": stmt.excluded.generated_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def record_hit(self, brand_id: UUID, marketplace: str, hit: bool) -> None:
        """Update hit_rate using exponential moving average (α=0.1)."""
        from app.db.models.comparator import BrandExtractor

        result = await self._session.execute(
            select(BrandExtractor).where(
                BrandExtractor.brand_id == brand_id,
                BrandExtractor.marketplace == marketplace,
            )
        )
        ext = result.scalar_one_or_none()
        if ext:
            alpha = Decimal("0.1")
            new_hit_rate = alpha * Decimal(1 if hit else 0) + (1 - alpha) * ext.hit_rate
            ext.hit_rate = new_hit_rate.quantize(Decimal("0.0001"))
            await self._session.flush()

    async def bootstrap(
        self,
        brand_id: UUID,
        brand_name: str,
        marketplace: str,
        sample_raw_pairs: list[dict],
        sample_asins: list[str],
    ) -> dict[str, Any]:
        """Generate mapping via Claude and persist. Returns the generated attribute_map."""
        logger.info(
            "Generating brand extractor for %s/%s (%d samples)",
            brand_name,
            marketplace,
            len(sample_raw_pairs),
        )
        attribute_map = await generate_mapping_via_claude(brand_name, marketplace, sample_raw_pairs)
        if attribute_map:
            await self.save_mapping(
                brand_id=brand_id,
                marketplace=marketplace,
                attribute_map=attribute_map,
                sample_asins=sample_asins,
                generated_by="claude-haiku-4-5-20251001",
            )
            logger.info(
                "Brand extractor saved for %s/%s: %d mappings",
                brand_name,
                marketplace,
                len(attribute_map),
            )
        else:
            logger.warning("Empty mapping generated for %s/%s", brand_name, marketplace)
        return attribute_map
