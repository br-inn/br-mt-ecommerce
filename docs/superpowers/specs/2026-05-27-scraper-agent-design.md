# Scraper Agent — Design Spec
**Date**: 2026-05-27  
**Status**: Approved  
**Scope**: AI-powered scraper creation wizard that replaces the manual `_source-dialog.tsx`

---

## 1. Problem Statement

Creating a new `ScraperSource` currently requires the user to manually write a complete recipe JSON (CSS selectors, field mappings, transforms) in a textarea. There is no guidance, no field suggestions, and no live preview. This is error-prone and requires deep knowledge of the target site's DOM.

The goal is an AI agent that analyzes a URL, generates the full recipe automatically using Claude, and lets the user review and adjust before committing.

---

## 2. Architecture Overview

```
Frontend Wizard (_source-wizard.tsx)
        │
        │ POST /api/v1/scraper-sources/analyze
        ▼
ScraperAgentService  (app/services/scraper/agent_service.py)
        │
        ├── curl_cffi_fetch(url)          ← existing
        ├── _detect_mode(html)            ← new (JS heuristics)
        ├── _generate_recipe(html, ctx)   ← new (Claude Haiku 4.5)
        └── extract_records(html, recipe) ← existing
```

**Unchanged**: `GenericConfigurableFetcher`, `recipe_extractor`, DB models for recipes, all existing CRUD endpoints.

**Changed**: The "Create Source" dialog becomes a 3-step wizard.

---

## 3. Backend

### 3.1 New: `app/services/scraper/canonical_fields.py`

Defines the canonical field schema all scrapers must align to:

| Field | Required | Type | Description |
|---|---|---|---|
| `external_id` | Yes | str | Unique product ID on that site (ASIN, SKU, URL path segment) |
| `title` | Yes | str | Product name |
| `price_aed` | Yes | currency | Current price in AED |
| `brand` | Recommended | str | Brand / manufacturer |
| `image_url` | Recommended | str | Main product image URL |
| `delivery_text` | Recommended | str | Delivery / shipping info |
| `rating` | Optional | float | Rating score |
| `review_count` | Optional | int | Number of reviews |
| `availability` | Optional | str | Stock status |
| `original_price_aed` | Optional | currency | Original price before discount |

The module exposes:
- `CANONICAL_FIELDS: list[CanonicalField]` — full schema with descriptions for Claude's prompt
- `REQUIRED_FIELDS: set[str]` — `{external_id, title, price_aed}`
- `validate_recipe(recipe) -> list[str]` — returns list of missing required field names

### 3.2 New: `app/services/scraper/agent_service.py`

```python
@dataclass
class AnalysisResult:
    detected_mode: Literal["static", "headless", "stealth"]
    proposed_source: dict            # name, slug, base_url
    proposed_recipe: dict            # full recipe JSONB
    field_confidence: dict[str, float]
    preview_records: list[dict]      # real extracted records
    missing_required: list[str]      # required fields not found
    warnings: list[str]

class ScraperAgentService:
    async def analyze(url: str, context: str | None = None) -> AnalysisResult
    async def refine_field(html: str, hint: str, recipe: dict) -> RecipeField
    def _detect_mode(html: str, url: str) -> FetchMode
    async def _generate_recipe(html: str, url: str, context: str | None) -> dict
```

**`analyze` flow**:
1. `curl_cffi_fetch(url)` — fetches HTML (reuses existing)
2. `_detect_mode(html, url)` — detects static/headless/stealth
3. `_generate_recipe(html, url, context)` — calls Claude Haiku 4.5
4. `extract_records(html, proposed_recipe)` — runs recipe against real HTML
5. Computes `field_confidence` per field (fraction of preview records with non-null value)
6. Returns `AnalysisResult`

**`refine_field` flow** (for "Find with AI" in wizard):
1. Receives already-fetched `html`, user `hint`, current `recipe`
2. Calls Claude with a short prompt: "Find a CSS selector for: {hint}"
3. Returns a single `RecipeField` to add to the recipe

**Mode detection heuristics** (`_detect_mode`):
- Visible text in `<body>` < 500 chars → `headless`
- Response headers or HTML contains Cloudflare/PerimeterX signals → `stealth`
- Otherwise → `static`
- For `headless`/`stealth`: recipe is still generated from whatever HTML was fetched; `fetch_mode` is set accordingly on the source

**Claude prompt** (`_generate_recipe`):
- Model: `claude-haiku-4-5-20251001`
- System prompt includes the canonical fields schema with descriptions
- User content: truncated HTML (max 40 000 chars) + URL + optional context
- Asks Claude to return a JSON object matching the `Recipe` Pydantic schema
- Output is parsed and validated against `RecipeSubmit` schema; if invalid, raises `ScraperAgentError`

### 3.3 New endpoint: `POST /api/v1/scraper-sources/analyze`

```python
class AnalyzeRequest(BaseModel):
    url: HttpUrl
    context: str | None = None   # max 500 chars, general description
    hint: str | None = None      # max 200 chars, used for "Find with AI" single-field refinement

class AnalyzeResponse(BaseModel):
    detected_mode: str
    proposed_source: dict
    proposed_recipe: dict
    field_confidence: dict[str, float]
    preview_records: list[dict]
    missing_required: list[str]
    warnings: list[str]
```

- Auth: admin required (same as other scraper endpoints)
- No DB writes — pure analysis
- SSRF protection: same allowlist logic as `/validate` (blocks private IPs)
- Returns 422 if URL is unreachable or HTML is empty

### 3.4 Modified: `app/schemas/scraper_sources.py`
Adds `AnalyzeRequest` and `AnalyzeResponse` schemas.

### 3.5 Modified: `app/api/routes/scraper_sources.py`
Adds `POST /scraper-sources/analyze` route using `ScraperAgentService`.

---

## 4. Frontend

### 4.1 New: `_source-wizard.tsx` (replaces `_source-dialog.tsx`)

Same `Dialog` container and Shadcn/ui components. Step indicator at top (`1 → 2 → 3`).

**Step 1 — "Analizar URL"**
- Fields: URL (required), description/context (optional), destination_profile radio
- Button: "Analizar con AI →" → calls `analyzeUrl()` and transitions to loading state
- Loading state: spinner + "Claude está analizando la página…"

**Step 2 — "Revisar propuesta"**
- Header row: detected mode badge + auto-generated name + required fields counter badge
- Fields list: each field shows name, selector preview, extract type, confidence indicator
  - `✓` green = found with confidence ≥ 0.7
  - `⚠` amber = found with confidence < 0.7 or recommended but missing
  - `✕` red = required field not found (blocks "Crear scraper")
  - Each field has `[✎]` (edit inline) and `[✕]` (remove) icon buttons
- Inline edit form (appears below the field row when `[✎]` clicked):
  - Inputs: field name, CSS selector, extract mode (text/html/attr:*), type, transform
  - Buttons: Cancelar / Guardar
- `[+ Agregar campo]` button → opens Add Field panel:
  - Two modes toggled by radio: "Buscar con AI" / "Manual"
  - "Buscar con AI": text input for hint → re-calls `POST /scraper-sources/analyze` with `{url: original_url, hint: user_hint}` → backend re-fetches HTML and returns one `RecipeField` → appended to current list
  - "Manual": same inline form as edit
- Preview table: columns = field names, rows = up to 5 preview records
  - Updates live whenever a field is edited/added/removed (client-side re-extract from cached HTML)
- "Crear scraper →" disabled if any required field is missing
- If mode is headless/stealth: amber banner warning about Playwright worker requirement

**Step 3 — Creation (no visible UI, runs in background)**
Sequential calls:
1. `POST /scraper-sources` → creates source
2. `POST /scraper-sources/{id}/recipes` → saves recipe
3. `POST /scraper-sources/{id}/validate` → validates
4. `POST /scraper-sources/{id}/activate` → activates (only if validation passes)

On any error: shows inline error message in Step 2, does not close dialog.  
On success: closes dialog, invalidates `scraper-sources` query cache, shows toast "Scraper creado y activo".

When `hint` is set in the request, the backend returns only the single best-matching `RecipeField` in `proposed_recipe.fields` (list of one) and skips full recipe generation.

### 4.2 Modified: `lib/api/endpoints/scraper-sources.ts`
Adds:
```typescript
export async function analyzeUrl(req: AnalyzeRequest): Promise<AnalyzeResponse>
// AnalyzeRequest: { url, context?, hint? }
// When hint is set, response has proposed_recipe.fields with exactly 1 entry
```

### 4.3 Modified: `lib/hooks/admin/use-scraper-sources.ts`
Adds `useAnalyzeUrl()` mutation hook (React Query `useMutation`).

---

## 5. Tests

### 5.1 Unit tests — backend

| File | Covers |
|---|---|
| `tests/unit/services/scraper/test_canonical_fields.py` | `validate_recipe`, missing required, field descriptions |
| `tests/unit/services/scraper/test_agent_service.py` | `_detect_mode` heuristics, `_generate_recipe` (Claude mocked), `analyze` full flow, `refine_field` |
| `tests/unit/services/scraper/test_recipe_extractor.py` | `extract_records` with HTML fixtures, `coerce_type` for all types, all transforms |
| `tests/unit/services/scraper/test_source_validation_service.py` | validate with passing/failing HTML fixture, field_results structure |
| `tests/api/test_scraper_agent_api.py` | `/analyze` endpoint: happy path, SSRF block, unreachable URL 422, HTML fixture response |

### 5.2 Integration test — backend

| File | Covers |
|---|---|
| `tests/integration/test_scraper_agent_flow.py` | Full flow with real DB: analyze → create source → create recipe → validate → activate → verify source is active and recipe is_live |

### 5.3 E2E test — frontend

| File | Covers |
|---|---|
| `tests/e2e/admin/scraper-wizard.spec.ts` | Full wizard: open dialog → enter URL → loading state → review fields → edit a field → add a field (manual) → create → toast → source appears in list |

---

## 6. Out of Scope (Future)

- "Find with AI" for field refinement hitting the real Claude API in E2E tests (mocked in tests)
- Headless/stealth fetch in `GenericConfigurableFetcher` (mode is detected and stored but execution falls back to static for now)
- Multi-step pagination support in wizard
- LLM snippets / sandbox execution (Phase 2 of ScraperSources)
