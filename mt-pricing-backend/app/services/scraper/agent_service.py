"""ScraperAgentService — analiza una URL y genera una receta de scraping via Claude Haiku."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from app.services.matching.adapters.generic_configurable import curl_cffi_fetch
from app.services.scraper.canonical_fields import REQUIRED_FIELDS, fields_as_schema_json
from app.services.scraper.recipe_extractor import extract_records

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a web scraping expert. Analyze the HTML of an e-commerce product listing page \
and generate a complete scraping recipe in JSON format.

Canonical fields you MUST try to extract (extract as many as you can find):
{canonical_fields}

The recipe JSON MUST follow this exact structure. Respond ONLY with valid JSON, no markdown:
{{
  "url_templates": {{
    "search": "https://example.com/search?q={{{{query}}}}"
  }},
  "list_item_selector": "CSS selector for the repeating product card container",
  "fields": [
    {{
      "name": "canonical_field_name",
      "selector": "CSS selector RELATIVE to list_item_selector",
      "extract": "text",
      "type": "str",
      "transform": null
    }}
  ]
}}

extract options: "text", "html", "attr:href", "attr:src", "attr:data-id" (any attr name).
type options: "str", "float", "int", "currency" (strips currency symbols), "bool".
transform (add only when needed): {{"op":"regex_capture","pattern":"(\\\\d+)"}}, \
{{"op":"strip_currency"}}, {{"op":"replace","find":"AED ","replace_with":""}}.

Rules:
- list_item_selector must match each repeating product card element.
- All field selectors are relative to list_item_selector (not body).
- url_templates.search must contain {{{{query}}}} as the search placeholder.
- For external_id prefer a data attribute or URL path (use regex_capture transform if needed).
- For price_aed use type "currency".
- Respond ONLY with valid JSON. No explanation, no markdown fences.
"""

_HINT_PROMPT = """\
You are a web scraping expert. Given the HTML below, find a CSS selector for EXACTLY ONE field.

Field to find: {hint}

Respond ONLY with this JSON object (no markdown):
{{
  "name": "field_name_in_snake_case",
  "selector": "CSS selector relative to a product card container",
  "extract": "text",
  "type": "str",
  "transform": null
}}
"""


@dataclass
class AnalysisResult:
    detected_mode: Literal["static", "headless", "stealth"]
    proposed_source: dict[str, str]
    proposed_recipe: dict[str, Any]
    field_confidence: dict[str, float]
    preview_records: list[dict[str, Any]]
    missing_required: list[str]
    warnings: list[str] = field(default_factory=list)


class ScraperAgentError(Exception):
    pass


def _detect_mode(html: str, url: str) -> Literal["static", "headless", "stealth"]:
    """Heuristic: inspect HTML body size and anti-bot signals."""
    tree = HTMLParser(html)
    body = tree.body
    if body is None or len(body.text(strip=True)) < 500:
        return "headless"
    cf_signals = ("cloudflare", "perimeterx", "px-captcha", "cf-browser-verification", "__cf_chl")
    html_lower = html.lower()
    if any(sig in html_lower for sig in cf_signals):
        return "stealth"
    # Detect SPA/RSC pages: body has text (nav/header) but no product-list content.
    # Signal: Next.js RSC flight scripts present but no repeating product containers.
    rsc_signals = ("self.__next_f.push", "__next_f", "self.__next_s")
    if any(sig in html for sig in rsc_signals):
        # Page uses React Server Components streaming — products render client-side
        return "headless"
    return "static"


async def _generate_recipe(
    html: str,
    url: str,
    context: str | None,
    hint: str | None,
) -> dict[str, Any]:
    import anthropic  # lazy import — not needed if feature flag off

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ScraperAgentError("ANTHROPIC_API_KEY no está configurada en el servidor")
    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as exc:
        raise ScraperAgentError(f"Anthropic client init failed: {exc}") from exc

    if hint:
        system = ""
        user_content = _HINT_PROMPT.format(hint=hint) + f"\n\nHTML:\n{html[:40_000]}"
    else:
        system = _SYSTEM_PROMPT.format(canonical_fields=fields_as_schema_json())
        parts = [f"URL: {url}"]
        if context:
            parts.append(f"Context: {context}")
        parts.append(f"\nHTML:\n{html[:40_000]}")
        user_content = "\n".join(parts)

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AuthenticationError as exc:
        raise ScraperAgentError("ANTHROPIC_API_KEY not configured or invalid") from exc
    except anthropic.APIStatusError as exc:
        raise ScraperAgentError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ScraperAgentError(f"Anthropic API unreachable: {exc}") from exc

    raw = msg.content[0].text.strip()

    # Strip markdown fences if Claude wraps output
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScraperAgentError(f"Claude returned invalid JSON: {exc}") from exc


class ScraperAgentService:
    async def analyze(
        self,
        url: str,
        *,
        context: str | None = None,
        hint: str | None = None,
    ) -> AnalysisResult:
        html = await curl_cffi_fetch(url)
        detected_mode = _detect_mode(html, url)
        recipe_dict = await _generate_recipe(html, url, context, hint)

        if hint:
            # Hint mode: wrap single field in a minimal recipe dict for consistency
            if "fields" not in recipe_dict:
                recipe_dict = {"fields": [recipe_dict]}

        # Filter out fields with empty/missing selectors (Claude occasionally generates them)
        valid_fields = [f for f in recipe_dict.get("fields", []) if f.get("selector")]
        recipe_dict = {**recipe_dict, "fields": valid_fields}

        try:
            records = extract_records(html, recipe_dict)
        except (ValueError, Exception) as exc:
            logger.warning("extract_records failed after Claude recipe generation: %s", exc)
            records = []

        field_conf: dict[str, float] = {}
        for f in recipe_dict.get("fields", []):
            name = f["name"]
            if records:
                non_null = sum(1 for r in records if r.get(name) not in (None, ""))
                field_conf[name] = round(non_null / len(records), 2)
            else:
                field_conf[name] = 0.0

        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        name_str = domain.split(".")[0].title()
        slug = re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")
        proposed_source: dict[str, str] = {
            "name": name_str,
            "slug": slug,
            "base_url": f"{parsed.scheme}://{parsed.netloc}",
        }

        recipe_field_names = {f["name"] for f in recipe_dict.get("fields", [])}
        missing = [fname for fname in sorted(REQUIRED_FIELDS) if fname not in recipe_field_names]

        warnings: list[str] = []
        if detected_mode in ("headless", "stealth"):
            warnings.append(f"Site requires {detected_mode} rendering — Playwright worker needed")
        for fname in REQUIRED_FIELDS:
            if fname in recipe_field_names and field_conf.get(fname, 1.0) < 0.3:
                warnings.append(
                    f"Field '{fname}' found but low confidence ({field_conf[fname]:.0%})"
                )

        return AnalysisResult(
            detected_mode=detected_mode,
            proposed_source=proposed_source,
            proposed_recipe=recipe_dict,
            field_confidence=field_conf,
            preview_records=records[:5],
            missing_required=missing,
            warnings=warnings,
        )
