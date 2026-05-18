"""AI listing content generator using Claude.

Generates listing_title, listing_description, bullet_points[], search_keywords
for Amazon UAE PlumbingFixture category from product technical data.
"""
from dataclasses import dataclass
from typing import Any

import anthropic

_DEFAULT_MODEL = "claude-sonnet-4-6"

_GENERATE_TOOL = {
    "name": "save_amazon_listing",
    "description": "Save the generated Amazon listing content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "listing_title": {
                "type": "string",
                "description": (
                    "Amazon product title. Max 200 chars. "
                    "Format: 'Brand + Product type + Key spec + DN size + Material'. "
                    "Example: 'MT Valves Ball Valve PN30 1/2\" Brass CW617N BSP'"
                ),
            },
            "listing_description": {
                "type": "string",
                "description": (
                    "Long product description for Amazon. Max 2000 chars. "
                    "Include: product type, key technical specs, applications, certifications. "
                    "Plain text only, no HTML."
                ),
            },
            "bullet_points": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 5,
                "maxItems": 5,
                "description": (
                    "Exactly 5 bullet points, each max 100 chars. "
                    "Cover: 1) pressure rating, 2) material, 3) connection type, "
                    "4) temperature range, 5) certifications/standards."
                ),
            },
            "search_keywords": {
                "type": "string",
                "description": (
                    "Backend search keywords, comma-separated, max 250 chars. "
                    "Include synonyms, material names, DN sizes, standards."
                ),
            },
        },
        "required": ["listing_title", "listing_description", "bullet_points", "search_keywords"],
    },
}

_SYSTEM_PROMPT = (
    "You are an expert Amazon marketplace content specialist for industrial valves and fittings. "
    "You write SEO-optimized product listings for the Amazon UAE marketplace (PlumbingFixture category). "
    "Always write in English. Be technically accurate. Prioritize key specs buyers search for."
)


@dataclass
class GeneratedListingContent:
    listing_title: str
    listing_description: str
    bullet_points: list[str]
    search_keywords: str
    ai_model: str = _DEFAULT_MODEL


class AmazonListingGenerator:
    """Generates Amazon listing content using Claude tool_use for structured output."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._client = anthropic.AsyncAnthropic()

    async def generate(self, product_context: dict[str, Any]) -> GeneratedListingContent:
        """Call Claude and return structured listing content."""
        user_prompt = _build_user_prompt(product_context)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=[_GENERATE_TOOL],
            tool_choice={"type": "tool", "name": "save_amazon_listing"},
            messages=[{"role": "user", "content": user_prompt}],
        )

        if response.stop_reason != "tool_use":
            raise ValueError(
                f"Claude did not return tool_use — stop_reason={response.stop_reason!r}. "
                "Check API key and model availability."
            )

        tool_block = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_block is None:
            raise ValueError(
                "Claude did not return tool_use — no tool_use block in response content."
            )
        data = tool_block.input

        return GeneratedListingContent(
            listing_title=data["listing_title"],
            listing_description=data["listing_description"],
            bullet_points=list(data["bullet_points"]),
            search_keywords=data["search_keywords"],
            ai_model=self._model,
        )


def _build_user_prompt(ctx: dict[str, Any]) -> str:
    certifications = ", ".join(ctx.get("certifications", [])) or "not specified"
    return (
        f"Generate an Amazon UAE product listing for this industrial valve/fitting:\n\n"
        f"SKU: {ctx.get('sku', '')}\n"
        f"Family: {ctx.get('family', '')}\n"
        f"DN/Size: {ctx.get('dn', '')}\n"
        f"Material: {ctx.get('material', '')}\n"
        f"Connection type: {ctx.get('connection_type', '')}\n"
        f"Pressure rating: {ctx.get('pressure_rating', '')} bar\n"
        f"Temperature range: {ctx.get('temp_min', '')}°C to {ctx.get('temp_max', '')}°C\n"
        f"Certifications: {certifications}\n"
        f"Technical description: {ctx.get('description_en', '')}\n\n"
        "Use the save_amazon_listing tool to return structured content."
    )
