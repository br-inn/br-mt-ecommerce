# Scraper Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual JSON-textarea ScraperSource creation dialog with a 3-step AI wizard that fetches a URL, calls Claude Haiku to generate a CSS-selector recipe, lets the user review/edit proposed fields, and creates the source + recipe in one shot.

**Architecture:** New `ScraperAgentService` (backend) wraps `curl_cffi_fetch` + Claude Haiku to return `AnalysisResult`; new `POST /scraper-sources/analyze` endpoint exposes it; frontend `_source-wizard.tsx` replaces `_source-dialog.tsx` with a 3-step flow (URL → AI analysis → review/create). All tests run against real services: real Claude API (`ANTHROPIC_API_KEY`), real PostgreSQL (testcontainers), real HTTP via `http.server` serving HTML fixtures.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy async · anthropic SDK · selectolax · Next.js 16 · React 19 · Shadcn/ui · React Hook Form · TanStack Query · Playwright (e2e)

---

## File Map

```
mt-pricing-backend/
├── app/services/scraper/
│   ├── canonical_fields.py          ← NEW: canonical field schema + validate_recipe()
│   └── agent_service.py             ← NEW: ScraperAgentService, _detect_mode, _generate_recipe
├── app/schemas/scraper_sources.py   ← MODIFY: add AnalyzeRequest, AnalyzeResponse
├── app/api/routes/scraper_sources.py← MODIFY: add POST /scraper-sources/analyze
└── tests/
    ├── conftest.py                  ← MODIFY: add html_fixture_server fixture
    ├── fixtures/html/
    │   ├── generic_serp.html        ← NEW: realistic e-commerce SERP with 3 products
    │   └── js_heavy.html            ← NEW: JS-SPA shell with empty body (headless detection)
    ├── unit/services/scraper/
    │   ├── test_canonical_fields.py ← NEW
    │   ├── test_recipe_extractor.py ← NEW (enhances coverage)
    │   └── test_agent_service.py    ← NEW (real Claude + local HTTP)
    ├── api/
    │   └── test_scraper_agent_api.py← NEW (real DB + Claude + ASGI)
    └── integration/
        └── test_scraper_agent_flow.py← NEW (full wizard flow in real DB)

mt-pricing-frontend/
├── lib/api/endpoints/scraper-sources.ts   ← MODIFY: add AnalyzeRequest/AnalyzeResponse types + analyze()
├── lib/hooks/admin/use-scraper-sources.ts ← MODIFY: add useAnalyzeUrl()
├── app/(app)/admin/scraper/sources/
│   ├── _source-wizard.tsx                 ← NEW: 3-step wizard (replaces _source-dialog)
│   └── _client.tsx                        ← MODIFY: import SourceDialog from wizard
└── tests/e2e/
    └── 22-scraper-wizard.spec.ts          ← NEW: Playwright e2e
```

---

## Task 1: HTML Fixtures + `html_fixture_server` conftest fixture

**Files:**
- Create: `mt-pricing-backend/tests/fixtures/html/generic_serp.html`
- Create: `mt-pricing-backend/tests/fixtures/html/js_heavy.html`
- Modify: `mt-pricing-backend/tests/conftest.py`

- [ ] **Step 1.1: Create `generic_serp.html`**

```html
<!doctype html>
<html>
<head><title>Industrial Valves UAE — Search Results</title></head>
<body>
  <div class="results-header">12 results for "ball valve"</div>
  <div class="product-grid">
    <div class="product-card" data-id="BV-001">
      <a class="card-link" href="/products/BV-001">
        <img class="product-image" src="https://cdn.example.com/img/BV-001.jpg" alt="Ball Valve">
      </a>
      <h3 class="product-title">Brass Ball Valve 1" BSP Full Bore</h3>
      <span class="brand-name">ValveTech</span>
      <div class="price-block">
        <span class="current-price">AED 45.00</span>
        <span class="original-price">AED 65.00</span>
      </div>
      <div class="delivery-info">Delivers in 2-3 days</div>
      <div class="rating-block">
        <span class="rating-score">4.3</span>
        <span class="review-count">127 reviews</span>
      </div>
      <span class="stock-status">In Stock</span>
    </div>
    <div class="product-card" data-id="BV-002">
      <a class="card-link" href="/products/BV-002">
        <img class="product-image" src="https://cdn.example.com/img/BV-002.jpg" alt="Gate Valve">
      </a>
      <h3 class="product-title">Stainless Steel Gate Valve DN50 PN16</h3>
      <span class="brand-name">IndustrialCo</span>
      <div class="price-block">
        <span class="current-price">AED 120.00</span>
      </div>
      <div class="delivery-info">Ships in 1 week</div>
      <div class="rating-block">
        <span class="rating-score">4.7</span>
        <span class="review-count">43 reviews</span>
      </div>
      <span class="stock-status">In Stock</span>
    </div>
    <div class="product-card" data-id="BV-003">
      <a class="card-link" href="/products/BV-003">
        <img class="product-image" src="https://cdn.example.com/img/BV-003.jpg" alt="Check Valve">
      </a>
      <h3 class="product-title">Bronze Check Valve 3/4" NPT</h3>
      <span class="brand-name">ValveTech</span>
      <div class="price-block">
        <span class="current-price">AED 38.50</span>
        <span class="original-price">AED 52.00</span>
      </div>
      <div class="delivery-info">Delivers in 2-3 days</div>
      <div class="rating-block">
        <span class="rating-score">4.1</span>
        <span class="review-count">89 reviews</span>
      </div>
      <span class="stock-status">Low Stock</span>
    </div>
  </div>
</body>
</html>
```

Save to: `mt-pricing-backend/tests/fixtures/html/generic_serp.html`

- [ ] **Step 1.2: Create `js_heavy.html`**

```html
<!doctype html>
<html>
<head><title>Loading...</title></head>
<body>
  <div id="root"></div>
  <script src="/static/main.bundle.js"></script>
</body>
</html>
```

Save to: `mt-pricing-backend/tests/fixtures/html/js_heavy.html`

- [ ] **Step 1.3: Add `html_fixture_server` to root conftest**

Open `mt-pricing-backend/tests/conftest.py`. After the existing imports block (after `import pytest_asyncio`), add:

```python
import http.server
import threading
from pathlib import Path
```

Then at the end of the file (before any existing session-scoped fixtures or after the last fixture), add:

```python
# ---------------------------------------------------------------------------
# Local HTTP server for scraper agent tests — serves tests/fixtures/html/
# ---------------------------------------------------------------------------
_HTML_FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "html"


@pytest.fixture(scope="session")
def html_fixture_server() -> Iterator[str]:
    """Serves tests/fixtures/html/ at http://127.0.0.1:{port}/.

    curl_cffi_fetch runs against this real HTTP server — no patching.
    Requires ANTHROPIC_API_KEY to be set for agent tests.
    """
    fixtures_dir = _HTML_FIXTURES_DIR

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # type: ignore[override]
            path = self.path.lstrip("/") or "index.html"
            file_path = fixtures_dir / path
            if not file_path.exists():
                self.send_response(404)
                self.end_headers()
                return
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args: object) -> None:  # type: ignore[override]
            pass  # silence test output

    server = http.server.HTTPServer(("0.0.0.0", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
```

- [ ] **Step 1.4: Verify fixtures directory structure**

```bash
ls mt-pricing-backend/tests/fixtures/html/
```

Expected output:
```
generic_serp.html  js_heavy.html
```

- [ ] **Step 1.5: Commit**

```bash
git add mt-pricing-backend/tests/fixtures/html/ mt-pricing-backend/tests/conftest.py
git commit -m "test(scraper): add HTML fixtures and html_fixture_server conftest"
```

---

## Task 2: `canonical_fields.py` + Unit Tests

**Files:**
- Create: `mt-pricing-backend/app/services/scraper/canonical_fields.py`
- Create: `mt-pricing-backend/tests/unit/services/scraper/test_canonical_fields.py`

- [ ] **Step 2.1: Write the failing tests first**

Create `mt-pricing-backend/tests/unit/services/scraper/test_canonical_fields.py`:

```python
"""Unit tests for canonical_fields — pure logic, no IO."""
from __future__ import annotations

import json

import pytest

from app.services.scraper.canonical_fields import (
    CANONICAL_FIELDS,
    REQUIRED_FIELDS,
    fields_as_schema_json,
    validate_recipe,
)


def test_required_fields_set():
    assert REQUIRED_FIELDS == {"external_id", "title", "price_aed"}


def test_canonical_fields_count():
    assert len(CANONICAL_FIELDS) == 10


def test_validate_recipe_all_missing():
    missing = validate_recipe({"fields": []})
    assert set(missing) == {"external_id", "title", "price_aed"}


def test_validate_recipe_all_required_present():
    recipe = {
        "fields": [
            {"name": "external_id", "selector": "a", "extract": "attr:href", "type": "str"},
            {"name": "title", "selector": "h2", "extract": "text", "type": "str"},
            {"name": "price_aed", "selector": "span.price", "extract": "text", "type": "currency"},
        ]
    }
    assert validate_recipe(recipe) == []


def test_validate_recipe_partial_missing():
    recipe = {
        "fields": [
            {"name": "title", "selector": "h2", "extract": "text", "type": "str"},
            {"name": "price_aed", "selector": "span", "extract": "text", "type": "currency"},
        ]
    }
    missing = validate_recipe(recipe)
    assert missing == ["external_id"]


def test_fields_as_schema_json_is_valid_json():
    schema_str = fields_as_schema_json()
    data = json.loads(schema_str)
    assert isinstance(data, dict)
    assert "external_id" in data
    assert "price_aed" in data
    assert "title" in data
    assert len(data) == 10
```

- [ ] **Step 2.2: Run tests — verify they FAIL**

```bash
cd mt-pricing-backend && uv run pytest tests/unit/services/scraper/test_canonical_fields.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.scraper.canonical_fields'`

- [ ] **Step 2.3: Create `canonical_fields.py`**

```python
"""Schema canónico de campos para scrapers — todos los adapters deben alinearse a estos campos."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalField:
    name: str
    required: bool
    type: str
    description: str


CANONICAL_FIELDS: list[CanonicalField] = [
    CanonicalField("external_id", True, "str",
                   "Unique product ID on that site (ASIN, SKU, URL path segment)"),
    CanonicalField("title", True, "str", "Product name"),
    CanonicalField("price_aed", True, "currency",
                   "Current price in AED (numeric only, no currency symbol)"),
    CanonicalField("brand", False, "str", "Brand or manufacturer name"),
    CanonicalField("image_url", False, "str", "Main product image URL (absolute)"),
    CanonicalField("delivery_text", False, "str", "Delivery or shipping info text"),
    CanonicalField("rating", False, "float", "Numeric rating score (e.g. 4.5)"),
    CanonicalField("review_count", False, "int", "Number of customer reviews"),
    CanonicalField("availability", False, "str",
                   "Stock status text (e.g. 'In Stock', 'Out of Stock')"),
    CanonicalField("original_price_aed", False, "currency",
                   "Original price before discount in AED"),
]

REQUIRED_FIELDS: set[str] = {f.name for f in CANONICAL_FIELDS if f.required}


def validate_recipe(recipe: dict[str, Any]) -> list[str]:
    """Returns list of required field names missing from the recipe."""
    present = {f["name"] for f in recipe.get("fields", [])}
    return [name for name in sorted(REQUIRED_FIELDS) if name not in present]


def fields_as_schema_json() -> str:
    """JSON string describing all canonical fields — injected into Claude's prompt."""
    return json.dumps(
        {f.name: f"({f.type}) {f.description}" for f in CANONICAL_FIELDS},
        indent=2,
    )
```

- [ ] **Step 2.4: Run tests — verify they PASS**

```bash
cd mt-pricing-backend && uv run pytest tests/unit/services/scraper/test_canonical_fields.py -v
```

Expected: `5 passed`

- [ ] **Step 2.5: Commit**

```bash
git add app/services/scraper/canonical_fields.py tests/unit/services/scraper/test_canonical_fields.py
git commit -m "feat(scraper): add canonical_fields schema + unit tests"
```

---

## Task 3: `recipe_extractor.py` Unit Tests

**Files:**
- Create: `mt-pricing-backend/tests/unit/services/scraper/test_recipe_extractor.py`

- [ ] **Step 3.1: Write tests**

```python
"""Unit tests for recipe_extractor and recipe_transforms — pure logic, no IO."""
from __future__ import annotations

import pytest

from app.services.scraper.recipe_extractor import coerce_type, extract_records, field_results
from app.services.scraper.recipe_transforms import apply_transform

_SERP_HTML = """
<html><body>
  <div class="product">
    <h2 class="title">Widget A</h2>
    <span class="price">AED 49.99</span>
    <a class="link" href="/products/123">View</a>
    <span class="brand">BrandX</span>
    <img class="thumb" src="https://cdn.example.com/img/a.jpg">
    <span class="stock">In Stock</span>
    <span class="rating">4.5</span>
  </div>
  <div class="product">
    <h2 class="title">Widget B</h2>
    <span class="price">AED 99.00</span>
    <a class="link" href="/products/456">View</a>
    <span class="brand">BrandY</span>
    <img class="thumb" src="https://cdn.example.com/img/b.jpg">
    <span class="stock">Out of Stock</span>
    <span class="rating">3.8</span>
  </div>
</body></html>
"""

_RECIPE = {
    "url_templates": {"search": "http://example.com/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "title", "selector": "h2.title", "extract": "text", "type": "str"},
        {"name": "price_aed", "selector": "span.price", "extract": "text", "type": "currency"},
        {
            "name": "external_id",
            "selector": "a.link",
            "extract": "attr:href",
            "type": "str",
            "transform": {"op": "regex_capture", "pattern": r"/products/(\d+)"},
        },
        {"name": "brand", "selector": "span.brand", "extract": "text", "type": "str"},
        {"name": "image_url", "selector": "img.thumb", "extract": "attr:src", "type": "str"},
        {"name": "availability", "selector": "span.stock", "extract": "text", "type": "str"},
        {"name": "rating", "selector": "span.rating", "extract": "text", "type": "float"},
    ],
}


def test_extract_records_count():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert len(records) == 2


def test_extract_records_text_field():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["title"] == "Widget A"
    assert records[1]["title"] == "Widget B"


def test_extract_records_currency():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["price_aed"] == 49.99
    assert records[1]["price_aed"] == 99.0


def test_extract_records_attr_with_transform():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["external_id"] == "123"
    assert records[1]["external_id"] == "456"


def test_extract_records_attr_src():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["image_url"] == "https://cdn.example.com/img/a.jpg"


def test_extract_records_float():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["rating"] == 4.5
    assert records[1]["rating"] == 3.8


def test_extract_missing_selector_returns_none():
    recipe = {
        "list_item_selector": "div.product",
        "fields": [{"name": "missing", "selector": "span.nope", "extract": "text", "type": "str"}],
    }
    records = extract_records(_SERP_HTML, recipe)
    assert all(r["missing"] is None for r in records)


def test_field_results_pass():
    records = extract_records(_SERP_HTML, _RECIPE)
    results = field_results(records, _RECIPE)
    assert results["title"] == "pass"
    assert results["price_aed"] == "pass"
    assert results["external_id"] == "pass"


def test_field_results_fail_missing_selector():
    recipe = {
        "list_item_selector": "div.product",
        "fields": [{"name": "ghost", "selector": "span.ghost", "extract": "text", "type": "str"}],
    }
    records = extract_records(_SERP_HTML, recipe)
    assert field_results(records, recipe)["ghost"] == "fail"


def test_coerce_type_currency_with_symbol():
    assert coerce_type("AED 49.99", "currency") == 49.99


def test_coerce_type_currency_with_comma():
    assert coerce_type("1,250.00", "currency") == 1250.0


def test_coerce_type_currency_empty():
    assert coerce_type("", "currency") is None


def test_coerce_type_float():
    assert coerce_type("4.5", "float") == 4.5


def test_coerce_type_float_invalid():
    assert coerce_type("abc", "float") is None


def test_coerce_type_int():
    assert coerce_type("42", "int") == 42


def test_coerce_type_int_from_float_string():
    assert coerce_type("3.7", "int") == 3


def test_coerce_type_bool_truthy():
    assert coerce_type("In Stock", "bool") is True


def test_coerce_type_bool_falsy():
    assert coerce_type("Out of Stock", "bool") is False


def test_apply_transform_regex_capture():
    result = apply_transform({"op": "regex_capture", "pattern": r"/products/(\d+)"}, "/products/123")
    assert result == "123"


def test_apply_transform_regex_no_match_returns_empty():
    result = apply_transform({"op": "regex_capture", "pattern": r"NOMATCH(\d+)"}, "/products/123")
    assert result == ""


def test_apply_transform_strip_currency():
    result = apply_transform({"op": "strip_currency"}, "AED 49.99")
    assert result == "49.99"


def test_apply_transform_replace():
    result = apply_transform({"op": "replace", "find": "AED ", "replace_with": ""}, "AED 49.99")
    assert result == "49.99"


def test_apply_transform_map_values():
    transform = {"op": "map_values", "mapping": {"In Stock": "available", "Out": "unavailable"}}
    assert apply_transform(transform, "In Stock") == "available"
    assert apply_transform(transform, "Unknown") == "Unknown"


def test_apply_transform_unit_factor():
    result = apply_transform({"op": "unit_factor", "factor": 0.0689476}, "100")
    assert abs(float(result) - 6.89476) < 0.0001


def test_apply_transform_none_is_identity():
    assert apply_transform(None, "hello") == "hello"
```

- [ ] **Step 3.2: Run tests — verify they PASS**

```bash
cd mt-pricing-backend && uv run pytest tests/unit/services/scraper/test_recipe_extractor.py -v
```

Expected: `~22 passed`

- [ ] **Step 3.3: Commit**

```bash
git add tests/unit/services/scraper/test_recipe_extractor.py
git commit -m "test(scraper): comprehensive unit tests for recipe_extractor and transforms"
```

---

## Task 4: `agent_service.py` — Core Implementation

**Files:**
- Create: `mt-pricing-backend/app/services/scraper/agent_service.py`

- [ ] **Step 4.1: Create `agent_service.py`**

```python
"""ScraperAgentService — analiza una URL y genera una receta de scraping via Claude Haiku."""
from __future__ import annotations

import json
import logging
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


def _detect_mode(html: str, url: str) -> Literal["static", "headless", "stealth"]:  # noqa: ARG001
    """Heuristic: inspect HTML body size and anti-bot signals."""
    tree = HTMLParser(html)
    body = tree.body
    if body is None or len(body.text(strip=True)) < 500:
        return "headless"
    cf_signals = ("cloudflare", "perimeterx", "px-captcha", "cf-browser-verification", "__cf_chl")
    html_lower = html.lower()
    if any(sig in html_lower for sig in cf_signals):
        return "stealth"
    return "static"


async def _generate_recipe(
    html: str,
    url: str,
    context: str | None,
    hint: str | None,
) -> dict[str, Any]:
    import anthropic  # lazy import — not needed if feature flag off

    client = anthropic.Anthropic()
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

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
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

        records = extract_records(html, recipe_dict)

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
            warnings.append(
                f"Site requires {detected_mode} rendering — Playwright worker needed"
            )
        for fname in REQUIRED_FIELDS:
            if fname in recipe_field_names and field_conf.get(fname, 1.0) < 0.3:
                warnings.append(
                    f"Field '{fname}' found but low confidence "
                    f"({field_conf[fname]:.0%})"
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
```

- [ ] **Step 4.2: Verify import works**

```bash
cd mt-pricing-backend && uv run python -c "from app.services.scraper.agent_service import ScraperAgentService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4.3: Commit**

```bash
git add app/services/scraper/agent_service.py
git commit -m "feat(scraper): add ScraperAgentService with Claude-powered recipe generation"
```

---

## Task 5: `agent_service.py` Unit Tests (real Claude + local HTTP)

**Files:**
- Create: `mt-pricing-backend/tests/unit/services/scraper/test_agent_service.py`

These tests call the real Claude Haiku API and the local `html_fixture_server`. Requires `ANTHROPIC_API_KEY` in env.

- [ ] **Step 5.1: Write the tests**

```python
"""Tests for ScraperAgentService — real Claude API + local HTTP fixture server.

Requires ANTHROPIC_API_KEY env var.
"""
from __future__ import annotations

import pytest

from app.services.scraper.agent_service import ScraperAgentService, _detect_mode
from app.services.scraper.canonical_fields import REQUIRED_FIELDS


def test_detect_mode_static_with_rich_html():
    html = "<html><body>" + "<p>Product content</p>" * 50 + "</body></html>"
    assert _detect_mode(html, "http://example.com") == "static"


def test_detect_mode_headless_empty_body():
    html = "<html><head><title>App</title></head><body><div id='root'></div></body></html>"
    assert _detect_mode(html, "http://example.com") == "headless"


def test_detect_mode_stealth_cloudflare():
    html = (
        "<html><body>"
        + "<p>x</p>" * 50
        + "<script>__cf_chl_rt_tk='abc'</script>"
        + "</body></html>"
    )
    assert _detect_mode(html, "http://example.com") == "stealth"


def test_detect_mode_headless_none_body():
    html = "<html></html>"
    assert _detect_mode(html, "http://example.com") == "headless"


@pytest.mark.integration
async def test_analyze_returns_required_fields(html_fixture_server: str):
    """Claude analyzes the generic_serp.html fixture and proposes canonical fields."""
    service = ScraperAgentService()
    result = await service.analyze(f"{html_fixture_server}/generic_serp.html")

    assert result.detected_mode == "static"

    recipe_field_names = {f["name"] for f in result.proposed_recipe.get("fields", [])}
    # Claude must propose at least title and price_aed from the fixture HTML
    assert "title" in recipe_field_names, f"title missing from {recipe_field_names}"
    assert "price_aed" in recipe_field_names, f"price_aed missing from {recipe_field_names}"

    # preview_records should reflect the 3 product cards in the fixture
    assert len(result.preview_records) == 3
    assert result.preview_records[0].get("title") is not None

    # proposed_source should have name, slug, base_url
    assert result.proposed_source["base_url"].startswith("http://127.0.0.1")


@pytest.mark.integration
async def test_analyze_detects_headless_for_js_page(html_fixture_server: str):
    """js_heavy.html fixture has empty body — should be detected as headless."""
    service = ScraperAgentService()
    result = await service.analyze(f"{html_fixture_server}/js_heavy.html")
    assert result.detected_mode == "headless"
    assert any("headless" in w for w in result.warnings)


@pytest.mark.integration
async def test_analyze_hint_returns_single_field(html_fixture_server: str):
    """When hint is set, Claude returns exactly one field."""
    service = ScraperAgentService()
    result = await service.analyze(
        f"{html_fixture_server}/generic_serp.html",
        hint="the product delivery time text",
    )
    fields = result.proposed_recipe.get("fields", [])
    assert len(fields) == 1
    assert fields[0].get("selector") is not None
```

- [ ] **Step 5.2: Run unit tests (mode detection) — no Claude needed**

```bash
cd mt-pricing-backend && uv run pytest tests/unit/services/scraper/test_agent_service.py -v -k "not integration"
```

Expected: `4 passed` (the non-integration tests only)

- [ ] **Step 5.3: Run integration tests — requires ANTHROPIC_API_KEY**

```bash
cd mt-pricing-backend && uv run pytest tests/unit/services/scraper/test_agent_service.py -v -m integration
```

Expected: `3 passed` (may take 10-20s per test while Claude responds)

- [ ] **Step 5.4: Commit**

```bash
git add tests/unit/services/scraper/test_agent_service.py
git commit -m "test(scraper): agent_service unit+integration tests with real Claude API"
```

---

## Task 6: Backend Schemas + Route `/analyze`

**Files:**
- Modify: `mt-pricing-backend/app/schemas/scraper_sources.py`
- Modify: `mt-pricing-backend/app/api/routes/scraper_sources.py`

- [ ] **Step 6.1: Add schemas to `scraper_sources.py`**

At the end of `app/schemas/scraper_sources.py`, after the existing `ActivateRequest` class, add:

```python
# ---------------------------------------------------------------------------
# Scraper Agent schemas — POST /scraper-sources/analyze
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=1, description="URL to analyze and generate recipe for")
    context: str | None = Field(default=None, max_length=500,
                                 description="Optional description of the site")
    hint: str | None = Field(default=None, max_length=200,
                              description="If set, find only this one field instead of full recipe")


class AnalyzeResponse(BaseModel):
    detected_mode: str
    proposed_source: dict[str, str]
    proposed_recipe: dict[str, Any]
    field_confidence: dict[str, float]
    preview_records: list[dict[str, Any]]
    missing_required: list[str]
    warnings: list[str]
```

- [ ] **Step 6.2: Add `/analyze` endpoint to `scraper_sources.py` routes**

In `app/api/routes/scraper_sources.py`, add the import at the top (after existing imports):

```python
from app.schemas.scraper_sources import (
    ActivateRequest,
    AnalyzeRequest,
    AnalyzeResponse,
    RecipeRead,
    RecipeSubmit,
    ScraperSourceCreate,
    ScraperSourceRead,
    ScraperSourceUpdate,
    ValidateRequest,
    ValidateResponse,
)
from app.services.scraper.agent_service import ScraperAgentError, ScraperAgentService
```

Then add the new route before the existing `POST /scraper-sources` handler (so the `/analyze` path doesn't conflict with `/{source_id}` patterns). Add after the `router = APIRouter(...)` line and after `_assert_public_url`:

```python
@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_url(
    body: AnalyzeRequest,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
) -> AnalyzeResponse:
    """Fetches the URL, calls Claude to generate a scraping recipe, returns proposal.
    No DB writes — pure analysis for the wizard Step 2 preview."""
    _assert_public_url(body.url)
    service = ScraperAgentService()
    try:
        result = await service.analyze(body.url, context=body.context, hint=body.hint)
    except ScraperAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return AnalyzeResponse(
        detected_mode=result.detected_mode,
        proposed_source=result.proposed_source,
        proposed_recipe=result.proposed_recipe,
        field_confidence=result.field_confidence,
        preview_records=result.preview_records,
        missing_required=result.missing_required,
        warnings=result.warnings,
    )
```

- [ ] **Step 6.3: Verify route appears in OpenAPI**

```bash
cd mt-pricing-backend && uv run python -c "
from app.main import app
routes = [r.path for r in app.routes]
print([r for r in routes if 'analyze' in r])
"
```

Expected: `['/api/v1/scraper-sources/analyze']`

- [ ] **Step 6.4: Regenerate OpenAPI spec (CI requirement)**

```bash
cd mt-pricing-backend && uv run python -m app.scripts.export_openapi
git add _bmad-output/planning-artifacts/mt-api-contract-openapi.json
```

- [ ] **Step 6.5: Commit**

```bash
git add app/schemas/scraper_sources.py app/api/routes/scraper_sources.py \
        _bmad-output/planning-artifacts/mt-api-contract-openapi.json
git commit -m "feat(scraper): add POST /scraper-sources/analyze endpoint + schemas"
```

---

## Task 7: API Tests for `/analyze` Endpoint

**Files:**
- Create: `mt-pricing-backend/tests/api/test_scraper_agent_api.py`

- [ ] **Step 7.1: Write tests following the same pattern as `test_scraper_sources_api.py`**

```python
"""Integration tests for POST /api/v1/scraper-sources/analyze."""
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

os.environ["SUPABASE_JWT_SECRET"] = "test-jwt-secret-deterministic-32chars!"
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")
os.environ["SUPABASE_JWT_VERIFICATION_MODE"] = "hs256"
os.environ["JWT_ALGORITHM"] = "HS256"

try:
    from app.core import config as _cfg

    _cfg.get_settings.cache_clear()
    _cfg.settings = _cfg.get_settings()
except Exception:
    pass

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    import sqlalchemy as _sa
    from alembic.config import Config
    from sqlalchemy import text
    from alembic import command

    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    from app.core import config as _app_cfg

    _app_cfg.get_settings.cache_clear()
    os.environ["DATABASE_URL"] = postgres_container
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url
    _app_cfg.settings = _app_cfg.get_settings()

    import app.api.deps as _deps
    _deps.settings = _app_cfg.settings

    engine = _sa.create_engine(sync_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS auth.users "
                    "(id UUID PRIMARY KEY DEFAULT gen_random_uuid())"
                )
            )
            for fn, ret in (("uid", "UUID"), ("role", "TEXT"), ("jwt", "JSONB")):
                conn.execute(
                    text(
                        f"CREATE OR REPLACE FUNCTION auth.{fn}() RETURNS {ret} "
                        f"AS $$ SELECT NULL::{ret} $$ LANGUAGE sql"
                    )
                )
            conn.commit()
    finally:
        engine.dispose()

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


def _emit_jwt(*, sub: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
            "app_metadata": {"role": "admin"},
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest_asyncio.fixture(scope="module")
async def agent_client(db_session_committed) -> AsyncIterator[AsyncClient]:
    from sqlalchemy import select
    from app.db.models.user import Permission, Role, RolePermission, User

    session = db_session_committed
    perms = []
    for code in ("products:read", "products:write"):
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perms.append(p)
        else:
            perms.append(existing)

    role = Role(code="agent_tester", name="Agent Tester", permissions_snapshot=["products:read"])
    session.add(role)
    await session.flush()
    for p in perms:
        session.add(RolePermission(role_id=role.id, permission_id=p.id))

    uid = uuid4()
    email = f"agent-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="AgentTest", locale="es",
                is_active=True, role_id=role.id)
    session.add(user)
    await session.commit()

    token = _emit_jwt(sub=str(uid), email=email)

    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


@pytest.mark.integration
async def test_analyze_happy_path(agent_client: AsyncClient, html_fixture_server: str):
    url = f"{html_fixture_server}/generic_serp.html"
    resp = await agent_client.post("/api/v1/scraper-sources/analyze", json={"url": url})
    assert resp.status_code == 200
    data = resp.json()
    assert data["detected_mode"] == "static"
    assert "fields" in data["proposed_recipe"]
    assert len(data["proposed_recipe"]["fields"]) > 0
    assert isinstance(data["preview_records"], list)
    assert len(data["preview_records"]) == 3
    assert isinstance(data["field_confidence"], dict)
    assert isinstance(data["missing_required"], list)


@pytest.mark.integration
async def test_analyze_with_hint(agent_client: AsyncClient, html_fixture_server: str):
    url = f"{html_fixture_server}/generic_serp.html"
    resp = await agent_client.post(
        "/api/v1/scraper-sources/analyze",
        json={"url": url, "hint": "the product delivery time"},
    )
    assert resp.status_code == 200
    data = resp.json()
    fields = data["proposed_recipe"].get("fields", [])
    assert len(fields) == 1
    assert fields[0].get("selector") is not None


@pytest.mark.integration
async def test_analyze_blocks_private_ip(agent_client: AsyncClient):
    resp = await agent_client.post(
        "/api/v1/scraper-sources/analyze",
        json={"url": "http://192.168.1.1/products"},
    )
    assert resp.status_code == 422


@pytest.mark.integration
async def test_analyze_requires_auth():
    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon_client:
        resp = await anon_client.post(
            "/api/v1/scraper-sources/analyze", json={"url": "http://example.com"}
        )
    assert resp.status_code in (401, 403)
```

- [ ] **Step 7.2: Run tests**

```bash
cd mt-pricing-backend && uv run pytest tests/api/test_scraper_agent_api.py -v
```

Expected: `4 passed`

- [ ] **Step 7.3: Commit**

```bash
git add tests/api/test_scraper_agent_api.py
git commit -m "test(scraper): API integration tests for /analyze endpoint"
```

---

## Task 8: Full Integration Test — Wizard Flow in Real DB

**Files:**
- Create: `mt-pricing-backend/tests/integration/test_scraper_agent_flow.py`

- [ ] **Step 8.1: Write integration test**

```python
"""End-to-end integration test: analyze → create source → recipe → validate → activate."""
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt

os.environ["SUPABASE_JWT_SECRET"] = "test-jwt-secret-deterministic-32chars!"
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")
os.environ["SUPABASE_JWT_VERIFICATION_MODE"] = "hs256"
os.environ["JWT_ALGORITHM"] = "HS256"

try:
    from app.core import config as _cfg
    _cfg.get_settings.cache_clear()
    _cfg.settings = _cfg.get_settings()
except Exception:
    pass

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"
pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    import sqlalchemy as _sa
    from alembic.config import Config
    from sqlalchemy import text
    from alembic import command

    sync_url = postgres_container.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    from app.core import config as _app_cfg
    _app_cfg.get_settings.cache_clear()
    os.environ["DATABASE_URL"] = postgres_container
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url
    _app_cfg.settings = _app_cfg.get_settings()
    import app.api.deps as _deps
    _deps.settings = _app_cfg.settings

    engine = _sa.create_engine(sync_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            conn.execute(
                text("CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY DEFAULT gen_random_uuid())")
            )
            for fn, ret in (("uid", "UUID"), ("role", "TEXT"), ("jwt", "JSONB")):
                conn.execute(
                    text(
                        f"CREATE OR REPLACE FUNCTION auth.{fn}() RETURNS {ret} "
                        f"AS $$ SELECT NULL::{ret} $$ LANGUAGE sql"
                    )
                )
            conn.commit()
    finally:
        engine.dispose()
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="module")
async def flow_client(db_session_committed) -> AsyncIterator[AsyncClient]:
    from sqlalchemy import select
    from app.db.models.user import Permission, Role, RolePermission, User

    session = db_session_committed
    perms = []
    for code in ("products:read", "products:write"):
        existing = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if existing is None:
            p = Permission(code=code, description=code)
            session.add(p)
            await session.flush()
            perms.append(p)
        else:
            perms.append(existing)

    role = Role(code="flow_tester", name="Flow Tester", permissions_snapshot=["products:read"])
    session.add(role)
    await session.flush()
    for p in perms:
        session.add(RolePermission(role_id=role.id, permission_id=p.id))

    uid = uuid4()
    email = f"flow-{uid.hex[:6]}@mt.ae"
    user = User(id=uid, email=email, full_name="FlowTest", locale="es",
                is_active=True, role_id=role.id)
    session.add(user)
    await session.commit()

    now = int(time.time())
    token = jwt.encode(
        {"sub": str(uid), "aud": "authenticated", "email": email,
         "iat": now, "exp": now + 3600, "app_metadata": {"role": "admin"}},
        JWT_SECRET, algorithm="HS256",
    )

    from app.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


@pytest.mark.integration
async def test_full_wizard_flow(flow_client: AsyncClient, html_fixture_server: str):
    """Simulates the 3-step wizard: analyze → create source → recipe → validate → activate."""
    url = f"{html_fixture_server}/generic_serp.html"

    # Step 1: Analyze
    resp = await flow_client.post("/api/v1/scraper-sources/analyze", json={"url": url})
    assert resp.status_code == 200, resp.text
    analysis = resp.json()
    assert analysis["detected_mode"] == "static"
    assert len(analysis["proposed_recipe"].get("fields", [])) > 0

    # Step 2: Create source (use unique slug to avoid conflicts between test runs)
    unique_suffix = uuid4().hex[:6]
    source_payload = {
        "name": f"Test Site {unique_suffix}",
        "slug": f"test-site-{unique_suffix}",
        "base_url": analysis["proposed_source"]["base_url"],
        "destination_profile": "competitor_price",
        "fetch_mode": analysis["detected_mode"],
    }
    resp = await flow_client.post("/api/v1/scraper-sources", json=source_payload)
    assert resp.status_code == 201, resp.text
    source = resp.json()
    source_id = source["id"]
    assert source["status"] == "draft"

    # Step 3: Create recipe with proposed_recipe (user accepted without edits)
    resp = await flow_client.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json={"recipe": analysis["proposed_recipe"]},
    )
    assert resp.status_code == 201, resp.text
    recipe = resp.json()
    recipe_id = recipe["id"]
    assert recipe["validation_status"] == "unvalidated"

    # Step 4: Validate recipe against original URL
    resp = await flow_client.post(
        f"/api/v1/scraper-sources/{source_id}/validate",
        json={"recipe_id": recipe_id, "test_url": url},
    )
    assert resp.status_code == 200, resp.text
    validation = resp.json()
    assert validation["status"] == "passing", (
        f"Validation failed. field_results: {validation['field_results']}"
    )

    # Step 5: Activate (only allowed when validation_status == "passing")
    resp = await flow_client.post(
        f"/api/v1/scraper-sources/{source_id}/activate",
        json={"recipe_id": recipe_id},
    )
    assert resp.status_code == 200, resp.text
    activated = resp.json()
    assert activated["status"] == "active"
```

- [ ] **Step 8.2: Run test**

```bash
cd mt-pricing-backend && uv run pytest tests/integration/test_scraper_agent_flow.py -v
```

Expected: `1 passed` (may take 20-30s)

- [ ] **Step 8.3: Commit**

```bash
git add tests/integration/test_scraper_agent_flow.py
git commit -m "test(scraper): full wizard integration test — analyze to activate"
```

---

## Task 9: Frontend API Types + `analyzeUrl` Client Function

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts`

- [ ] **Step 9.1: Add types and `analyze` function**

In `lib/api/endpoints/scraper-sources.ts`, after the `ActivateRequest` interface (line ~71) and before the `ScraperSourcesApiError` class, add:

```typescript
export interface RecipeTransformDef {
  op: "regex_capture" | "strip_currency" | "replace" | "map_values" | "unit_factor";
  pattern?: string;
  find?: string;
  replace_with?: string;
  mapping?: Record<string, string>;
  factor?: number;
}

export interface RecipeFieldDef {
  name: string;
  selector: string;
  extract: string;
  type: "str" | "float" | "int" | "currency" | "bool";
  transform: RecipeTransformDef | null;
}

export interface AnalyzeRequest {
  url: string;
  context?: string | null;
  hint?: string | null;
}

export interface AnalyzeResponse {
  detected_mode: "static" | "headless" | "stealth";
  proposed_source: {
    name: string;
    slug: string;
    base_url: string;
  };
  proposed_recipe: {
    url_templates: { search?: string; pdp?: string; list?: string; product?: string };
    list_item_selector: string | null;
    fields: RecipeFieldDef[];
    anti_bot_hints?: Record<string, unknown>;
  };
  field_confidence: Record<string, number>;
  preview_records: Record<string, unknown>[];
  missing_required: string[];
  warnings: string[];
}
```

Then in the `scraperSourcesApi` object, after `activate:`, add:

```typescript
  analyze: (req: AnalyzeRequest): Promise<AnalyzeResponse> =>
    authedFetch<AnalyzeResponse>("/api/v1/scraper-sources/analyze", {
      method: "POST",
      body: JSON.stringify(req),
    }),
```

- [ ] **Step 9.2: Verify TypeScript compiles**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | head -20
```

Expected: no errors related to `scraper-sources.ts`

- [ ] **Step 9.3: Commit**

```bash
git add lib/api/endpoints/scraper-sources.ts
git commit -m "feat(scraper): add AnalyzeRequest/AnalyzeResponse types + analyze() API client"
```

---

## Task 10: `useAnalyzeUrl` React Query Hook

**Files:**
- Modify: `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts`

- [ ] **Step 10.1: Add import and hook**

In `lib/hooks/admin/use-scraper-sources.ts`, add to the import from `scraper-sources`:

```typescript
import {
  scraperSourcesApi,
  type ActivateRequest,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type RecipeCreate,
  type RecipeRead,
  type ScraperSourceCreate,
  type ScraperSourceRead,
  type ScraperSourceUpdate,
  type ValidateRequest,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";
```

Then at the end of the file, add:

```typescript
export function useAnalyzeUrl() {
  return useMutation<AnalyzeResponse, Error, AnalyzeRequest>({
    mutationFn: (req) => scraperSourcesApi.analyze(req),
  });
}
```

- [ ] **Step 10.2: Verify TypeScript compiles**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 10.3: Commit**

```bash
git add lib/hooks/admin/use-scraper-sources.ts
git commit -m "feat(scraper): add useAnalyzeUrl() React Query mutation hook"
```

---

## Task 11: `_source-wizard.tsx` — Full Implementation

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_source-wizard.tsx`

- [ ] **Step 11.1: Create the full wizard component**

```tsx
"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Pencil, Plus, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  scraperSourcesApi,
  ScraperSourcesApiError,
  type AnalyzeResponse,
  type DestinationProfile,
  type RecipeFieldDef,
  type ScraperSourceRead,
} from "@/lib/api/endpoints/scraper-sources";
import { useAnalyzeUrl } from "@/lib/hooks/admin/use-scraper-sources";
import { scraperSourceKeys } from "@/lib/hooks/admin/use-scraper-sources";

// Required fields the user must have before creating
const REQUIRED_FIELD_NAMES = new Set(["external_id", "title", "price_aed"]);

type Step = "url-form" | "analyzing" | "review" | "creating";

const urlFormSchema = z.object({
  url: z.string().url("Ingresa una URL válida (incluye https://)"),
  context: z.string().max(500).optional(),
  destination_profile: z.enum(["competitor_price", "product_data"]),
});
type UrlFormValues = z.infer<typeof urlFormSchema>;

const fieldSchema = z.object({
  name: z
    .string()
    .min(1)
    .max(64)
    .regex(/^[a-z_][a-z0-9_]*$/, "Solo letras minúsculas, números y guión bajo"),
  selector: z.string().min(1, "El selector CSS es requerido"),
  extract: z.string().min(1),
  type: z.enum(["str", "float", "int", "currency", "bool"]),
});
type FieldFormValues = z.infer<typeof fieldSchema>;

interface Props {
  mode: "create" | "edit";
  source?: ScraperSourceRead;
  open: boolean;
  onClose: () => void;
  onSuccess?: (source: ScraperSourceRead) => void;
}

export function SourceDialog({ mode, source, open, onClose, onSuccess }: Props) {
  const qc = useQueryClient();
  const analyzeUrl = useAnalyzeUrl();

  const [step, setStep] = React.useState<Step>("url-form");
  const [analyzeResult, setAnalyzeResult] = React.useState<AnalyzeResponse | null>(null);
  const [originalUrl, setOriginalUrl] = React.useState("");
  const [editedFields, setEditedFields] = React.useState<RecipeFieldDef[]>([]);
  const [destProfile, setDestProfile] = React.useState<DestinationProfile>("competitor_price");
  const [editingIndex, setEditingIndex] = React.useState<number | null>(null);
  const [addingField, setAddingField] = React.useState<"ai" | "manual" | null>(null);
  const [aiHint, setAiHint] = React.useState("");
  const [createError, setCreateError] = React.useState<string | null>(null);

  const urlForm = useForm<UrlFormValues>({
    resolver: zodResolver(urlFormSchema),
    defaultValues: { url: "", context: "", destination_profile: "competitor_price" },
  });

  const fieldForm = useForm<FieldFormValues>({
    resolver: zodResolver(fieldSchema),
    defaultValues: { name: "", selector: "", extract: "text", type: "str" },
  });

  React.useEffect(() => {
    if (!open) {
      setStep("url-form");
      setAnalyzeResult(null);
      setOriginalUrl("");
      setEditedFields([]);
      setEditingIndex(null);
      setAddingField(null);
      setAiHint("");
      setCreateError(null);
      urlForm.reset();
      fieldForm.reset();
    }
  }, [open, urlForm, fieldForm]);

  const missingRequired = REQUIRED_FIELD_NAMES.size > 0
    ? [...REQUIRED_FIELD_NAMES].filter(
        (name) => !editedFields.some((f) => f.name === name),
      )
    : [];

  const canCreate = missingRequired.length === 0;

  // ── Step 1 handler ──────────────────────────────────────────────────────
  const handleAnalyze = async (values: UrlFormValues) => {
    setStep("analyzing");
    setDestProfile(values.destination_profile);
    try {
      const result = await analyzeUrl.mutateAsync({
        url: values.url,
        context: values.context ?? null,
      });
      setAnalyzeResult(result);
      setEditedFields(result.proposed_recipe.fields ?? []);
      setOriginalUrl(values.url);
      setStep("review");
    } catch {
      setStep("url-form");
      toast.error("No se pudo analizar la URL. Verifica que sea accesible y pública.");
    }
  };

  // ── Field editing handlers ───────────────────────────────────────────────
  const handleEditField = (index: number) => {
    const f = editedFields[index]!;
    fieldForm.reset({ name: f.name, selector: f.selector, extract: f.extract, type: f.type });
    setEditingIndex(index);
    setAddingField(null);
  };

  const handleSaveEdit = (values: FieldFormValues) => {
    if (editingIndex === null) return;
    setEditedFields((prev) =>
      prev.map((f, i) =>
        i === editingIndex ? { name: values.name, selector: values.selector,
                               extract: values.extract, type: values.type,
                               transform: f.transform } : f,
      ),
    );
    setEditingIndex(null);
    fieldForm.reset();
  };

  const handleRemoveField = (index: number) => {
    setEditedFields((prev) => prev.filter((_, i) => i !== index));
    if (editingIndex === index) setEditingIndex(null);
  };

  const handleAddManual = (values: FieldFormValues) => {
    setEditedFields((prev) => [
      ...prev,
      { name: values.name, selector: values.selector,
        extract: values.extract, type: values.type, transform: null },
    ]);
    setAddingField(null);
    fieldForm.reset();
  };

  const handleFindWithAI = async () => {
    if (!aiHint.trim()) return;
    try {
      const result = await analyzeUrl.mutateAsync({
        url: originalUrl,
        hint: aiHint.trim(),
      });
      const newField = result.proposed_recipe.fields?.[0];
      if (newField) {
        setEditedFields((prev) => [...prev, newField]);
        setAiHint("");
        setAddingField(null);
        toast.success(`Campo "${newField.name}" agregado`);
      } else {
        toast.error("Claude no encontró un selector para ese campo");
      }
    } catch {
      toast.error("Error al buscar el campo con AI");
    }
  };

  // ── Step 3: Creation flow ────────────────────────────────────────────────
  const handleCreate = async () => {
    if (!analyzeResult || !canCreate) return;
    setStep("creating");
    setCreateError(null);

    const editedRecipe = {
      ...analyzeResult.proposed_recipe,
      fields: editedFields,
    };

    try {
      const newSource = await scraperSourcesApi.create({
        name: analyzeResult.proposed_source.name,
        slug: analyzeResult.proposed_source.slug,
        base_url: analyzeResult.proposed_source.base_url,
        destination_profile: destProfile,
        fetch_mode: analyzeResult.detected_mode,
      });

      const newRecipe = await scraperSourcesApi.createRecipe(newSource.id, {
        recipe: editedRecipe,
      });

      const validation = await scraperSourcesApi.validate(newSource.id, {
        recipe_id: newRecipe.id,
        test_url: originalUrl,
      });

      let finalSource = newSource;
      if (validation.status === "passing") {
        finalSource = await scraperSourcesApi.activate(newSource.id, {
          recipe_id: newRecipe.id,
        });
      }

      await qc.invalidateQueries({ queryKey: scraperSourceKeys.all() });
      onSuccess?.(finalSource);
      toast.success(
        validation.status === "passing"
          ? "Scraper creado y activo"
          : "Scraper creado — activar manualmente cuando la validación pase",
      );
      onClose();
    } catch (err) {
      setStep("review");
      if (err instanceof ScraperSourcesApiError && err.status === 409) {
        setCreateError(
          `El slug "${analyzeResult.proposed_source.slug}" ya existe. ` +
            `Edita manualmente el nombre del source.`,
        );
      } else {
        setCreateError("Error al crear el scraper. Revisa los campos e intenta de nuevo.");
      }
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      {step === "url-form" && (
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Crear scraper con AI</DialogTitle>
          </DialogHeader>
          <form onSubmit={urlForm.handleSubmit(handleAnalyze)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="wiz-url">URL del sitio *</Label>
              <Input
                id="wiz-url"
                placeholder="https://example.com/search?q=ball+valve"
                {...urlForm.register("url")}
              />
              {urlForm.formState.errors.url && (
                <p className="text-xs text-destructive">
                  {urlForm.formState.errors.url.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-ctx">Descripción (opcional)</Label>
              <Input
                id="wiz-ctx"
                placeholder="Ej: Sitio de proveedores industriales UAE"
                {...urlForm.register("context")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Destino</Label>
              <Select
                value={urlForm.watch("destination_profile")}
                onValueChange={(v) =>
                  urlForm.setValue("destination_profile", v as DestinationProfile)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="competitor_price">Precios competidor</SelectItem>
                  <SelectItem value="product_data">Datos de producto</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button type="submit" disabled={urlForm.formState.isSubmitting}>
                Analizar con AI →
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}

      {step === "analyzing" && (
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Analizando sitio...</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            <p className="text-sm text-muted-foreground">Claude está analizando la página…</p>
          </div>
        </DialogContent>
      )}

      {step === "review" && analyzeResult && (
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <div className="flex items-center gap-2 flex-wrap">
              <DialogTitle>Revisar propuesta</DialogTitle>
              <Badge variant="outline" className="text-xs">
                {analyzeResult.detected_mode}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {analyzeResult.proposed_source.name}
              </span>
              <Badge
                variant={canCreate ? "default" : "destructive"}
                className="ml-auto text-xs"
              >
                {REQUIRED_FIELD_NAMES.size - missingRequired.length}/{REQUIRED_FIELD_NAMES.size}{" "}
                requeridos
              </Badge>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {/* Headless/stealth warning */}
            {analyzeResult.detected_mode !== "static" && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>
                  Este sitio requiere navegador headless — el scraper solo funcionará
                  cuando el worker Playwright esté activo.
                </span>
              </div>
            )}

            {/* Claude warnings */}
            {analyzeResult.warnings.length > 0 && (
              <div className="space-y-1">
                {analyzeResult.warnings.map((w, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    ⚠ {w}
                  </p>
                ))}
              </div>
            )}

            {/* Field list */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Campos propuestos
              </p>
              {editedFields.map((f, i) => {
                const isRequired = REQUIRED_FIELD_NAMES.has(f.name);
                const confidence = analyzeResult.field_confidence[f.name] ?? 0;
                const isEditing = editingIndex === i;

                return (
                  <div key={i} className="border rounded-md">
                    <div className="flex items-center gap-2 p-2">
                      {/* Status icon */}
                      {confidence >= 0.7 ? (
                        <Check className="h-4 w-4 text-green-600 shrink-0" />
                      ) : confidence > 0 ? (
                        <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                      ) : (
                        <X className="h-4 w-4 text-destructive shrink-0" />
                      )}
                      <span className="text-sm font-medium w-32 shrink-0">
                        {f.name}
                        {isRequired && (
                          <span className="text-destructive ml-0.5">*</span>
                        )}
                      </span>
                      <span className="text-xs text-muted-foreground truncate flex-1">
                        {f.selector} › {f.extract}
                      </span>
                      <div className="flex items-center gap-1 ml-auto">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={() => (isEditing ? setEditingIndex(null) : handleEditField(i))}
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                          onClick={() => handleRemoveField(i)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>

                    {/* Inline edit form */}
                    {isEditing && (
                      <form
                        onSubmit={fieldForm.handleSubmit(handleSaveEdit)}
                        className="p-2 pt-0 border-t bg-muted/30 space-y-2"
                      >
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label className="text-xs">Campo</Label>
                            <Input className="h-7 text-xs" {...fieldForm.register("name")} />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Selector CSS</Label>
                            <Input className="h-7 text-xs" {...fieldForm.register("selector")} />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Extraer</Label>
                            <Input
                              className="h-7 text-xs"
                              placeholder="text / attr:href / attr:src"
                              {...fieldForm.register("extract")}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Tipo</Label>
                            <Select
                              value={fieldForm.watch("type")}
                              onValueChange={(v) =>
                                fieldForm.setValue("type", v as FieldFormValues["type"])
                              }
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {(["str", "float", "int", "currency", "bool"] as const).map(
                                  (t) => (
                                    <SelectItem key={t} value={t} className="text-xs">
                                      {t}
                                    </SelectItem>
                                  ),
                                )}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        {(fieldForm.formState.errors.name ||
                          fieldForm.formState.errors.selector) && (
                          <p className="text-xs text-destructive">
                            {fieldForm.formState.errors.name?.message ??
                              fieldForm.formState.errors.selector?.message}
                          </p>
                        )}
                        <div className="flex gap-2 justify-end">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 text-xs"
                            type="button"
                            onClick={() => setEditingIndex(null)}
                          >
                            Cancelar
                          </Button>
                          <Button size="sm" className="h-6 text-xs" type="submit">
                            Guardar
                          </Button>
                        </div>
                      </form>
                    )}
                  </div>
                );
              })}

              {/* Add field button / panel */}
              {addingField === null ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full mt-1"
                  onClick={() => {
                    setAddingField("ai");
                    setEditingIndex(null);
                    fieldForm.reset();
                  }}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Agregar campo
                </Button>
              ) : (
                <div className="border rounded-md p-3 space-y-3 bg-muted/20">
                  <RadioGroup
                    value={addingField}
                    onValueChange={(v) => {
                      setAddingField(v as "ai" | "manual");
                      fieldForm.reset();
                    }}
                    className="flex gap-4"
                  >
                    <div className="flex items-center gap-1.5">
                      <RadioGroupItem value="ai" id="add-ai" />
                      <Label htmlFor="add-ai" className="text-sm cursor-pointer">
                        Buscar con AI
                      </Label>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <RadioGroupItem value="manual" id="add-manual" />
                      <Label htmlFor="add-manual" className="text-sm cursor-pointer">
                        Manual
                      </Label>
                    </div>
                  </RadioGroup>

                  {addingField === "ai" && (
                    <div className="flex gap-2">
                      <Input
                        className="h-7 text-sm"
                        placeholder="Ej: la fecha de entrega estimada"
                        value={aiHint}
                        onChange={(e) => setAiHint(e.target.value)}
                      />
                      <Button
                        size="sm"
                        className="h-7 shrink-0"
                        onClick={handleFindWithAI}
                        disabled={!aiHint.trim() || analyzeUrl.isPending}
                      >
                        {analyzeUrl.isPending ? "Buscando…" : "Buscar →"}
                      </Button>
                    </div>
                  )}

                  {addingField === "manual" && (
                    <form
                      onSubmit={fieldForm.handleSubmit(handleAddManual)}
                      className="space-y-2"
                    >
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Campo</Label>
                          <Input className="h-7 text-xs" {...fieldForm.register("name")} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Selector CSS</Label>
                          <Input className="h-7 text-xs" {...fieldForm.register("selector")} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Extraer</Label>
                          <Input
                            className="h-7 text-xs"
                            placeholder="text / attr:href"
                            {...fieldForm.register("extract")}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Tipo</Label>
                          <Select
                            value={fieldForm.watch("type")}
                            onValueChange={(v) =>
                              fieldForm.setValue("type", v as FieldFormValues["type"])
                            }
                          >
                            <SelectTrigger className="h-7 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {(["str", "float", "int", "currency", "bool"] as const).map((t) => (
                                <SelectItem key={t} value={t} className="text-xs">
                                  {t}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="flex gap-2 justify-end">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 text-xs"
                          type="button"
                          onClick={() => setAddingField(null)}
                        >
                          Cancelar
                        </Button>
                        <Button size="sm" className="h-6 text-xs" type="submit">
                          Agregar
                        </Button>
                      </div>
                    </form>
                  )}

                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs text-muted-foreground"
                    onClick={() => setAddingField(null)}
                  >
                    Cancelar
                  </Button>
                </div>
              )}
            </div>

            {/* Preview table */}
            {analyzeResult.preview_records.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Preview ({analyzeResult.preview_records.length} registros)
                </p>
                <div className="overflow-x-auto rounded-md border">
                  <table className="text-xs w-full">
                    <thead className="bg-muted/50">
                      <tr>
                        {editedFields.map((f) => (
                          <th
                            key={f.name}
                            className="px-2 py-1.5 text-left font-medium max-w-[120px] truncate"
                          >
                            {f.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {analyzeResult.preview_records.map((row, i) => (
                        <tr key={i} className="border-t">
                          {editedFields.map((f) => (
                            <td
                              key={f.name}
                              className="px-2 py-1.5 max-w-[120px] truncate text-muted-foreground"
                            >
                              {String(row[f.name] ?? "—")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Create error */}
            {createError && (
              <p className="text-sm text-destructive">{createError}</p>
            )}
          </div>

          <DialogFooter className="border-t pt-3">
            <Button
              variant="outline"
              onClick={() => {
                setStep("url-form");
                setAnalyzeResult(null);
              }}
            >
              ← Volver
            </Button>
            <Button onClick={handleCreate} disabled={!canCreate}>
              Crear scraper →
            </Button>
          </DialogFooter>
        </DialogContent>
      )}

      {step === "creating" && (
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Creando scraper...</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            <p className="text-sm text-muted-foreground">
              Guardando fuente, receta y activando...
            </p>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
```

Save to: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_source-wizard.tsx`

- [ ] **Step 11.2: Verify TypeScript compiles**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep -i "wizard\|source-wizard" | head -10
```

Expected: no errors for the wizard file

- [ ] **Step 11.3: Commit**

```bash
git add app/\(app\)/admin/scraper/sources/_source-wizard.tsx
git commit -m "feat(scraper): add AI-powered 3-step scraper creation wizard"
```

---

## Task 12: Update `_client.tsx` to Use the Wizard

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_client.tsx`

The `_client.tsx` currently imports `SourceDialog` from `./_source-dialog`. The wizard exports the same `SourceDialog` name so the change is a one-line import swap.

- [ ] **Step 12.1: Update the import**

In `app/(app)/admin/scraper/sources/_client.tsx`, find line ~19:

```typescript
import { SourceDialog } from "./_source-dialog";
```

Replace with:

```typescript
import { SourceDialog } from "./_source-wizard";
```

No other changes needed — the wizard exports `SourceDialog` with the same props interface.

- [ ] **Step 12.2: Verify TypeScript compiles**

```bash
cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 12.3: Build frontend**

```bash
cd mt-pricing-frontend && pnpm build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` or similar, no errors

- [ ] **Step 12.4: Commit**

```bash
git add app/\(app\)/admin/scraper/sources/_client.tsx
git commit -m "feat(scraper): wire wizard into scraper sources admin page"
```

---

## Task 13: E2E Playwright Test

**Files:**
- Create: `mt-pricing-frontend/tests/e2e/22-scraper-wizard.spec.ts`

This test runs against the real app (localhost:3000) + real backend (localhost:8000) + real Claude API. The HTML fixture server binds to `0.0.0.0` so it is accessible from Docker containers.

- [ ] **Step 13.1: Create E2E test**

```typescript
/**
 * 22 — Scraper wizard AI-powered creation @critico
 *
 * Flow: open dialog → enter URL (local fixture server) → wait for Claude analysis
 * → verify proposed fields → click "Crear scraper" → assert toast + source in list.
 *
 * Requires:
 *   - App running at PLAYWRIGHT_BASE_URL (default http://localhost:3000)
 *   - Backend at NEXT_PUBLIC_BACKEND_URL with ANTHROPIC_API_KEY set
 *   - Local fixture server for generic_serp.html (started by this test)
 */
import * as http from "node:http";
import * as path from "node:path";
import * as fs from "node:fs";

import { expect, test } from "@playwright/test";
import { loginAsGerente } from "./helpers/auth-as-role";

// ── Local HTML fixture server ──────────────────────────────────────────────
let fixtureServer: http.Server;
let fixtureBaseUrl: string;

const FIXTURES_DIR = path.join(
  __dirname,
  "..",
  "..",
  "..",
  "mt-pricing-backend",
  "tests",
  "fixtures",
  "html",
);

test.beforeAll(async () => {
  await new Promise<void>((resolve) => {
    fixtureServer = http.createServer((req, res) => {
      const filePath = path.join(FIXTURES_DIR, (req.url ?? "/").replace(/^\//, "") || "index.html");
      if (!fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(fs.readFileSync(filePath));
    });
    fixtureServer.listen(0, "0.0.0.0", () => {
      const addr = fixtureServer.address() as { port: number };
      // Use host.docker.internal if backend is in Docker, else 127.0.0.1
      const host = process.env.FIXTURE_SERVER_HOST ?? "127.0.0.1";
      fixtureBaseUrl = `http://${host}:${addr.port}`;
      resolve();
    });
  });
});

test.afterAll(() => {
  fixtureServer.close();
});

// ── Tests ──────────────────────────────────────────────────────────────────
test.describe("Scraper wizard @critico", () => {
  test("creates a scraper via AI wizard and appears in list", async ({ page }) => {
    await loginAsGerente(page);
    await page.goto("/admin/scraper/sources");

    // Open dialog
    await page.getByRole("button", { name: /new source|nueva? source/i }).click();

    // Wizard Step 1 — URL form
    await expect(page.getByText(/crear scraper con ai/i)).toBeVisible({ timeout: 5_000 });
    await page.getByLabel(/url del sitio/i).fill(`${fixtureBaseUrl}/generic_serp.html`);
    await page.getByRole("button", { name: /analizar con ai/i }).click();

    // Wait for analyzing state
    await expect(page.getByText(/claude está analizando/i)).toBeVisible({ timeout: 5_000 });

    // Wait for review state — Claude must respond (up to 60s)
    await expect(page.getByText(/revisar propuesta/i)).toBeVisible({ timeout: 60_000 });

    // Verify at least one proposed field is visible
    await expect(page.getByText("title").first()).toBeVisible({ timeout: 5_000 });

    // Click "Crear scraper"
    await page.getByRole("button", { name: /crear scraper/i }).click();

    // Wait for success toast
    await expect(page.getByText(/scraper creado/i)).toBeVisible({ timeout: 30_000 });

    // Verify source appears in list
    await expect(page.getByText("127.0.0.1").first()).toBeVisible({ timeout: 5_000 });
  });

  test("shows warning banner for headless-detected sites", async ({ page }) => {
    await loginAsGerente(page);
    await page.goto("/admin/scraper/sources");

    await page.getByRole("button", { name: /new source|nueva? source/i }).click();
    await expect(page.getByText(/crear scraper con ai/i)).toBeVisible({ timeout: 5_000 });
    await page.getByLabel(/url del sitio/i).fill(`${fixtureBaseUrl}/js_heavy.html`);
    await page.getByRole("button", { name: /analizar con ai/i }).click();

    // Wait for review
    await expect(page.getByText(/revisar propuesta/i)).toBeVisible({ timeout: 60_000 });

    // Should show headless warning banner
    await expect(page.getByText(/navegador headless/i)).toBeVisible({ timeout: 5_000 });
  });

  test("can add a field manually", async ({ page }) => {
    await loginAsGerente(page);
    await page.goto("/admin/scraper/sources");

    await page.getByRole("button", { name: /new source|nueva? source/i }).click();
    await page.getByLabel(/url del sitio/i).fill(`${fixtureBaseUrl}/generic_serp.html`);
    await page.getByRole("button", { name: /analizar con ai/i }).click();

    await expect(page.getByText(/revisar propuesta/i)).toBeVisible({ timeout: 60_000 });

    // Click "Agregar campo"
    await page.getByRole("button", { name: /agregar campo/i }).click();

    // Switch to Manual mode
    await page.getByLabel(/manual/i).click();

    // Fill in the new field
    await page.getByLabel(/^campo$/i).fill("custom_field");
    await page.getByLabel(/selector css/i).fill("span.custom");
    await page.getByRole("button", { name: /^agregar$/i }).click();

    // Verify the field appears in the list
    await expect(page.getByText("custom_field").first()).toBeVisible({ timeout: 3_000 });
  });
});
```

- [ ] **Step 13.2: Run E2E tests (requires running app)**

```bash
cd mt-pricing-frontend && npx playwright test tests/e2e/22-scraper-wizard.spec.ts --timeout=120000
```

Expected: `3 passed` (may take 1-2 minutes per test with Claude analysis)

- [ ] **Step 13.3: Commit**

```bash
git add tests/e2e/22-scraper-wizard.spec.ts
git commit -m "test(scraper): Playwright e2e tests for AI scraper creation wizard"
```

---

## Task 14: Deploy + Smoke Test

- [ ] **Step 14.1: Redeploy backend**

```bash
docker restart mt-backend
```

- [ ] **Step 14.2: Redeploy frontend**

```bash
docker restart mt-frontend
```

- [ ] **Step 14.3: Smoke test backend health**

```bash
curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live
```

Expected: `{"status":"ok"}` or `200 OK`

- [ ] **Step 14.4: Verify `/analyze` endpoint is live**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:${CADDY_HTTP_PORT:-8081}/api/v1/scraper-sources/analyze \
  -H "Content-Type: application/json" \
  -d '{"url":"http://example.com"}' 
```

Expected: `401` (no auth token → correct behavior, endpoint exists)

- [ ] **Step 14.5: Run full backend test suite to confirm no regressions**

```bash
cd mt-pricing-backend && uv run pytest tests/unit/services/scraper/ tests/api/test_scraper_agent_api.py tests/integration/test_scraper_agent_flow.py -v
```

Expected: all pass

- [ ] **Step 14.6: Merge to main**

```bash
git checkout main && git merge feat/pool-universal-cache --no-ff \
  -m "feat(scraper): AI-powered scraper creation wizard with Claude Haiku"
git push origin main
```

---

## Self-Review Checklist

- [x] **Spec §3.1 `canonical_fields.py`** → Task 2
- [x] **Spec §3.2 `agent_service.py`** → Task 4 + Task 5
- [x] **Spec §3.3 `POST /analyze` endpoint** → Task 6
- [x] **Spec §3.4 Schemas `AnalyzeRequest/Response`** → Task 6
- [x] **Spec §4.1 3-step wizard** → Task 11
- [x] **Spec §4.2 `analyzeUrl()` API client** → Task 9
- [x] **Spec §4.3 `useAnalyzeUrl()` hook** → Task 10
- [x] **Spec §5.1 Unit tests (canonical_fields, recipe_extractor, agent_service)** → Tasks 2, 3, 5
- [x] **Spec §5.2 Integration test (full flow)** → Task 8
- [x] **Spec §5.3 E2E Playwright** → Task 13
- [x] **No mocks** — all tests use real Claude API + local HTTP server + real DB
- [x] **OpenAPI spec regenerated** → Task 6 step 6.4
- [x] **Canonical required fields** — `external_id, title, price_aed` enforced in wizard
- [x] **Headless/stealth detection** — in `_detect_mode`, banner in wizard, `fetch_mode` set on source
- [x] **Add field — AI + Manual modes** → Task 11 (add field panel)
- [x] **Creation flow (all 4 API calls)** → Task 11 `handleCreate`
- [x] **`_client.tsx` wired to wizard** → Task 12
