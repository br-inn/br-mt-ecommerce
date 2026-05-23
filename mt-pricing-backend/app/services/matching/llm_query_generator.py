"""llm_query_generator.py — LLM-generated Amazon search queries via Claude Haiku.

Instead of rigid rule-based construction, Claude reads the full product data
holistically and generates the most effective Amazon Industrial search query.

Falls back gracefully when ANTHROPIC_API_KEY is absent or the API fails.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert at finding industrial PVF (pipes, valves, fittings) products "
    "on Amazon UAE's Industrial & Scientific department.\n\n"
    "Given a product's technical data, generate the most effective Amazon search query.\n\n"
    "Rules:\n"
    "1. ALWAYS write in English — never Arabic or Spanish.\n"
    "2. Use 5-8 words maximum — focused queries outperform long ones on Amazon.\n"
    "3. Include in priority order: product type (ball valve, gate valve, Y strainer…), "
    'material (brass, stainless steel, cast iron…), size in inches (1/2", 3/4", 1"…), '
    "pressure rating (PN30, PN16…) only when it differentiates the product.\n"
    "4. Always append 'industrial' to anchor results in the correct Amazon segment.\n"
    "5. For M-F (male-female) end connections: include 'male female' — it filters well.\n"
    "6. Omit: house brand codes (MT, Mitsa), catalog/ERP noise (erg., #, codes), "
    "standards (DIN259…) — Amazon does not index those.\n"
    "7. Prefer inch sizes ('1/2 inch', '3/4 inch') over DN metric notation.\n"
)

_TOOL: dict[str, Any] = {
    "name": "generate_search_query",
    "description": (
        "Generate the single most effective Amazon UAE search query "
        "for this industrial PVF product."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Amazon search query — English only, 5-8 words.",
            },
        },
        "required": ["query"],
    },
}


def _build_product_summary(product_data: dict[str, Any]) -> str:
    """Serialize relevant product fields into a compact text for the LLM."""
    lines: list[str] = []

    def _add(label: str, value: Any) -> None:
        v = str(value).strip() if value else ""
        if v:
            lines.append(f"{label}: {v}")

    _add("ERP name", product_data.get("erp_name"))
    _add("Product type", product_data.get("product_type") or product_data.get("name_en"))
    _add("Material", product_data.get("material"))
    _add("Size", product_data.get("dn"))
    _add("Pressure rating", product_data.get("pn"))
    _add("End connection", product_data.get("connection"))
    _add("Alloy code", product_data.get("alloy"))
    _add("Thread standard", product_data.get("model_thread_standard"))
    _add("Connection type", product_data.get("model_connection_type"))
    _add("Model code", product_data.get("model_code"))

    specs = product_data.get("specs") or {}
    _add("Handle color", specs.get("handle_color"))
    _add("Handle material", specs.get("handle_material"))
    apps = specs.get("applications") or []
    if apps:
        _add("Applications", ", ".join(str(a) for a in apps[:3]))

    return "\n".join(lines)


async def generate_amazon_query(product_data: dict[str, Any]) -> str | None:
    """Generate an optimized Amazon Industrial search query using Claude Haiku.

    Args:
        product_data: Product dict from ``MatchService._product_to_dict()``.

    Returns:
        Query string (English, 5-8 words), or ``None`` when the API is
        unavailable or the data is insufficient to produce a useful query.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("llm_query_generator: ANTHROPIC_API_KEY not set — skipping")
        return None

    summary = _build_product_summary(product_data)
    if not summary:
        return None

    user_message = f"Product data:\n{summary}"

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=64,
            temperature=0,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL],  # type: ignore[list-item]
            tool_choice={"type": "tool", "name": "generate_search_query"},
            messages=[{"role": "user", "content": user_message}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "generate_search_query":
                query = str(block.input.get("query") or "").strip()  # type: ignore[union-attr]
                if query:
                    logger.info(
                        "llm_query_generator: generated %r for sku=%s",
                        query,
                        product_data.get("sku"),
                    )
                    return query

        logger.warning("llm_query_generator: model did not invoke tool")
        return None

    except anthropic.APIError as exc:
        logger.exception("llm_query_generator: Anthropic API error: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("llm_query_generator: unexpected error: %s", exc)
        return None


__all__ = ["generate_amazon_query"]
