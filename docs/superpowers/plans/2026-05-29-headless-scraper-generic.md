# Headless Scraper Support for GenericConfigurableFetcher

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `GenericConfigurableFetcher` work for `fetch_mode="headless"/"stealth"` sources (e.g. Noon UAE) by injecting a Patchright html_fetcher, and expose a `POST /run` API endpoint + frontend button so users can trigger scraping after activation.

**Architecture:** A new `playwright_generic.py` module provides `patchright_fetch(url) -> str` using the same `async with async_playwright()` per-call pattern as `patchright_amazon_uae.py` (safe for Celery prefork workers). `GenericConfigurableFetcher.__init__` is updated to use it for headless/stealth sources instead of raising `NotImplementedError`. A new `POST /scraper-sources/{source_id}/run` endpoint dispatches `scrape_source_task` to the `scraper` queue (consumed by the `mt-scraper-worker` container which already has Patchright installed). The frontend adds a "Ejecutar Scraping" section in the Validation tab, visible only when the source is `active`.

**Tech Stack:** Python 3.11, patchright (already in Dockerfile.scraper-worker), FastAPI, Celery (queue: `scraper`), Next.js 16 / React Query, next-intl.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `mt-pricing-backend/app/services/matching/adapters/playwright_generic.py` | Generic `patchright_fetch(url)` html_fetcher |
| Create | `mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py` | Unit tests for patchright_fetch |
| Modify | `mt-pricing-backend/app/services/matching/adapters/generic_configurable.py:52–61` | Use patchright_fetch for headless/stealth |
| Modify | `mt-pricing-backend/app/schemas/scraper_sources.py` | Add RunRequest + RunResponse |
| Modify | `mt-pricing-backend/app/api/routes/scraper_sources.py` | Add POST /{source_id}/run |
| Modify | `mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts` | Add RunRequest/RunResponse types + `run()` |
| Modify | `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts` | Add `useRunScraping()` hook |
| Modify | `mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx` | Add Run Scraping section |
| Modify | `mt-pricing-frontend/messages/es.json` (+ en.json + ar.json) | Add i18n keys |
| Update | `_bmad-output/planning-artifacts/mt-api-contract-openapi.json` | Regenerate after route/schema change |

---

## Task 1: playwright_generic.py — patchright html_fetcher

**Files:**
- Create: `mt-pricing-backend/app/services/matching/adapters/playwright_generic.py`
- Create: `mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py`

- [ ] **Step 1: Write the failing test**

Create `mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py`:

```python
"""Tests for playwright_generic.patchright_fetch."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_patchright_fetch_returns_page_content(monkeypatch):
    """patchright_fetch opens a browser, navigates, and returns page.content()."""
    fake_page = AsyncMock()
    fake_page.content = AsyncMock(return_value="<html><body>rendered</body></html>")
    fake_page.goto = AsyncMock()
    fake_page.close = AsyncMock()

    fake_browser = AsyncMock()
    fake_browser.new_page = AsyncMock(return_value=fake_page)

    fake_launcher = AsyncMock()
    fake_launcher.launch = AsyncMock(return_value=fake_browser)

    fake_pw = MagicMock()
    fake_pw.chromium = fake_launcher

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=fake_pw)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.services.matching.adapters.playwright_generic.async_playwright",
        return_value=mock_ctx,
    ):
        from app.services.matching.adapters.playwright_generic import patchright_fetch

        result = await patchright_fetch("https://www.example.com/products")

    assert result == "<html><body>rendered</body></html>"
    fake_page.goto.assert_awaited_once_with(
        "https://www.example.com/products",
        wait_until="networkidle",
        timeout=pytest.approx(30_000, rel=0.1),
    )
    fake_page.close.assert_awaited_once()
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/scraper/test_playwright_generic.py -v --no-cov
```
Expected: `ModuleNotFoundError` or `ImportError` (file doesn't exist yet).

- [ ] **Step 3: Create playwright_generic.py**

Create `mt-pricing-backend/app/services/matching/adapters/playwright_generic.py`:

```python
"""Generic Patchright html_fetcher for headless/stealth ScraperSources.

Uses async with async_playwright() per call — safe for Celery prefork workers
where each task runs inside a fresh asyncio.run() event loop. The browser is
launched fresh per fetch and closed when done; no module-level singleton.

Env vars (all optional):
    SCRAPER_HEADLESS          "true" (default) or "false"
    SCRAPER_BROWSER_CHANNEL   patchright channel: "chromium" (default), "chrome"
    SCRAPER_TIMEOUT           Navigation timeout in seconds (default 30)
    SCRAPER_PROXY_URL         HTTP/SOCKS5 proxy URL (e.g. "http://user:pass@h:p")

The import of patchright is lazy (inside the function) so the main backend
container, which does not have patchright installed, can import this module
without crashing. Only the mt-scraper-worker container has patchright.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    "--single-process",
    "--disable-setuid-sandbox",
    "--disable-software-rasterizer",
]


async def patchright_fetch(url: str) -> str:
    """Fetch a JS-rendered page with Patchright and return the full HTML string.

    Launches a fresh Chromium browser, navigates to url, waits for
    networkidle (all network requests settle), returns rendered HTML, and
    closes the browser. Suitable for headless and stealth fetch_mode sources.

    Raises:
        ImportError: if patchright is not installed (wrong container).
        Exception: any navigation or browser error propagates to the caller.
    """
    from patchright.async_api import async_playwright  # type: ignore[import]

    headless: bool = os.environ.get("SCRAPER_HEADLESS", "true").strip().lower() != "false"
    channel: str = os.environ.get("SCRAPER_BROWSER_CHANNEL", "chromium")
    timeout_ms: int = int(os.environ.get("SCRAPER_TIMEOUT", "30")) * 1000
    proxy_url: str | None = os.environ.get("SCRAPER_PROXY_URL") or None

    launch_kwargs: dict = {
        "headless": headless,
        "args": _LAUNCH_ARGS,
    }
    if proxy_url:
        launch_kwargs["proxy"] = {"server": proxy_url}

    async with async_playwright() as pw:
        launcher = getattr(pw, channel, pw.chromium)
        browser = await launcher.launch(**launch_kwargs)
        logger.debug("playwright_generic.browser.ready", extra={"channel": channel, "url": url})
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = await page.content()
        finally:
            await page.close()
        await browser.close()

    return html
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/scraper/test_playwright_generic.py -v --no-cov
```
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```
git add mt-pricing-backend/app/services/matching/adapters/playwright_generic.py
git add mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py
git commit -m "feat(scraper): playwright_generic patchright html_fetcher para fuentes headless"
```

---

## Task 2: generic_configurable.py — headless/stealth support

**Files:**
- Modify: `mt-pricing-backend/app/services/matching/adapters/generic_configurable.py:52–61`
- Modify: `mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py` (add integration-adjacent test)

- [ ] **Step 1: Write the failing test**

Add to `mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py`:

```python
def test_generic_configurable_headless_uses_patchright_fetch():
    """GenericConfigurableFetcher.__init__ injects patchright_fetch for headless sources."""
    from unittest.mock import MagicMock

    from app.services.matching.adapters.generic_configurable import GenericConfigurableFetcher
    from app.services.matching.adapters.playwright_generic import patchright_fetch

    fake_source = MagicMock()
    fake_source.fetch_mode = "headless"
    fake_source.slug = "noon-uae"

    fetcher = GenericConfigurableFetcher(
        fake_source,
        {"url_templates": {"search": "https://noon.com/search?q={query}"}, "fields": []},
    )
    assert fetcher._html_fetcher is patchright_fetch


def test_generic_configurable_stealth_uses_patchright_fetch():
    """GenericConfigurableFetcher.__init__ injects patchright_fetch for stealth sources."""
    from unittest.mock import MagicMock

    from app.services.matching.adapters.generic_configurable import GenericConfigurableFetcher
    from app.services.matching.adapters.playwright_generic import patchright_fetch

    fake_source = MagicMock()
    fake_source.fetch_mode = "stealth"
    fake_source.slug = "example-stealth"

    fetcher = GenericConfigurableFetcher(
        fake_source,
        {"url_templates": {"search": "https://example.com/s?q={query}"}, "fields": []},
    )
    assert fetcher._html_fetcher is patchright_fetch
```

- [ ] **Step 2: Run to confirm tests fail**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/scraper/test_playwright_generic.py::test_generic_configurable_headless_uses_patchright_fetch tests/unit/services/scraper/test_playwright_generic.py::test_generic_configurable_stealth_uses_patchright_fetch -v --no-cov
```
Expected: `AssertionError` (currently raises NotImplementedError).

- [ ] **Step 3: Update generic_configurable.py**

Replace the `__init__` method in `mt-pricing-backend/app/services/matching/adapters/generic_configurable.py`. The current block (lines ~52–61) is:

```python
        if html_fetcher is not None:
            self._html_fetcher: HtmlFetcher = html_fetcher
        elif source.fetch_mode == "static":
            self._html_fetcher = curl_cffi_fetch
        else:
            raise NotImplementedError(
                f"fetch_mode {source.fetch_mode!r} no soportado en F1 — solo 'static'"
            )
```

Replace with:

```python
        if html_fetcher is not None:
            self._html_fetcher: HtmlFetcher = html_fetcher
        elif source.fetch_mode == "static":
            self._html_fetcher = curl_cffi_fetch
        elif source.fetch_mode in ("headless", "stealth"):
            from app.services.matching.adapters.playwright_generic import patchright_fetch

            self._html_fetcher = patchright_fetch
        else:
            raise NotImplementedError(
                f"fetch_mode {source.fetch_mode!r} no soportado — modos: static, headless, stealth"
            )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/scraper/test_playwright_generic.py -v --no-cov
```
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```
git add mt-pricing-backend/app/services/matching/adapters/generic_configurable.py
git add mt-pricing-backend/tests/unit/services/scraper/test_playwright_generic.py
git commit -m "feat(scraper): generic_configurable soporta headless/stealth via patchright_fetch"
```

---

## Task 3: Backend — POST /{source_id}/run endpoint

**Files:**
- Modify: `mt-pricing-backend/app/schemas/scraper_sources.py` (end of file)
- Modify: `mt-pricing-backend/app/api/routes/scraper_sources.py` (append after activate_source)
- Modify: `mt-pricing-backend/tests/api/test_scraper_sources_api.py` (append test)

- [ ] **Step 1: Write the failing test**

Append to `mt-pricing-backend/tests/api/test_scraper_sources_api.py`:

```python
@pytest.mark.api
async def test_run_source_dispatches_task(client_rw: AsyncClient) -> None:
    """POST /run on an active source returns a celery_task_id."""
    from unittest.mock import MagicMock, patch

    # Create source
    src = await client_rw.post(
        "/api/v1/scraper-sources",
        json={
            "name": "Run Test",
            "slug": "run-test-source",
            "base_url": "https://example.com",
            "destination_profile": "competitor_price",
            "fetch_mode": "static",
        },
    )
    assert src.status_code == 201, src.text
    source_id = src.json()["id"]

    # Add + validate a recipe so we can activate
    recipe_r = await client_rw.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json={
            "recipe": {
                "url_templates": {"search": "https://example.com/s?q={query}"},
                "list_item_selector": "div.item",
                "fields": [{"name": "title", "selector": "h2"}],
            }
        },
    )
    assert recipe_r.status_code == 201, recipe_r.text
    recipe_id = recipe_r.json()["id"]

    # Manually set validation_status=passing via DB so activate works
    from sqlalchemy import text as sql_text

    await client_rw.app.dependency_overrides  # access session via fixture
    # Patch the repo directly to set passing status
    from app.repositories.scraper_sources import ScraperSourceRepository
    from sqlalchemy.ext.asyncio import AsyncSession

    # Get session from the override
    session: AsyncSession = None  # type: ignore
    async for s in client_rw.app.dependency_overrides[
        __import__("app.api.deps", fromlist=["get_db_session"]).get_db_session
    ]():
        session = s
        break
    repo = ScraperSourceRepository(session)
    recipe_row = await repo.get_recipe(recipe_id)
    recipe_row.validation_status = "passing"
    await session.flush()

    # Activate
    act_r = await client_rw.post(
        f"/api/v1/scraper-sources/{source_id}/activate",
        json={"recipe_id": recipe_id},
    )
    assert act_r.status_code == 200, act_r.text

    # Run — mock celery task so no broker needed
    fake_result = MagicMock()
    fake_result.id = "test-celery-task-id-abc"

    with patch(
        "app.api.routes.scraper_sources.scrape_source_task"
    ) as mock_task:
        mock_task.delay.return_value = fake_result
        run_r = await client_rw.post(
            f"/api/v1/scraper-sources/{source_id}/run",
            json={"search_text": "aspiradoras"},
        )

    assert run_r.status_code == 202, run_r.text
    body = run_r.json()
    assert body["celery_task_id"] == "test-celery-task-id-abc"
    assert body["source_id"] == source_id
    mock_task.delay.assert_called_once_with(source_id, search_text="aspiradoras")
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd mt-pricing-backend
python -m pytest tests/api/test_scraper_sources_api.py::test_run_source_dispatches_task -v --no-cov
```
Expected: `404` (route doesn't exist yet).

- [ ] **Step 3: Add RunRequest + RunResponse schemas**

Append to `mt-pricing-backend/app/schemas/scraper_sources.py`:

```python
class RunRequest(BaseModel):
    search_text: str = Field(min_length=1, max_length=200)


class RunResponse(BaseModel):
    celery_task_id: str
    source_id: UUID
```

- [ ] **Step 4: Add /run endpoint to the route**

Add these imports at the top of `mt-pricing-backend/app/api/routes/scraper_sources.py` (add to the existing schema import block):

```python
from app.schemas.scraper_sources import (
    ActivateRequest,
    AnalyzeRequest,
    AnalyzeResponse,
    RecipeRead,
    RecipeSubmit,
    RunRequest,
    RunResponse,
    ScraperSourceCreate,
    ScraperSourceRead,
    ScraperSourceUpdate,
    ValidateRequest,
    ValidateResponse,
)
```

Then append after `activate_source`:

```python
@router.post(
    "/{source_id}/run",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="runScraperSource",
)
async def run_source(
    source_id: UUID,
    body: RunRequest,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunResponse:
    """Despacha scrape_source_task a la queue 'scraper' para esta source.

    La source debe estar 'active'. El task se ejecuta en el contenedor
    mt-scraper-worker (patchright para headless, curl_cffi para static).
    """
    from app.workers.tasks.scraper import scrape_source_task

    repo = ScraperSourceRepository(session)
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    if source.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="la source debe estar 'active' para ejecutar scraping",
        )
    task = scrape_source_task.delay(str(source_id), search_text=body.search_text)
    return RunResponse(celery_task_id=task.id, source_id=source_id)
```

- [ ] **Step 5: Regenerate OpenAPI spec**

```bash
docker exec mt-backend python -m app.scripts.export_openapi
docker cp mt-backend:/app/_bmad-output/planning-artifacts/mt-api-contract-openapi.json \
  _bmad-output/planning-artifacts/mt-api-contract-openapi.json
```

Expected output: `[export_openapi] wrote ... — 446 paths` (one more than before).

- [ ] **Step 6: Commit**

```
git add mt-pricing-backend/app/schemas/scraper_sources.py
git add mt-pricing-backend/app/api/routes/scraper_sources.py
git add mt-pricing-backend/tests/api/test_scraper_sources_api.py
git add _bmad-output/planning-artifacts/mt-api-contract-openapi.json
git commit -m "feat(scraper): POST /scraper-sources/{id}/run despacha scrape_source_task"
```

---

## Task 4: Frontend — RunRequest type + hook

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts`
- Modify: `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts`

- [ ] **Step 1: Add types and api method**

In `mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts`, add after the `ActivateRequest` interface (around line 72):

```typescript
export interface RunRequest {
  search_text: string;
}

export interface RunResponse {
  celery_task_id: string;
  source_id: string;
}
```

Add to the `scraperSourcesApi` object after `activate`:

```typescript
  run: (sourceId: string, req: RunRequest): Promise<RunResponse> =>
    authedFetch<RunResponse>(
      `/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/run`,
      { method: "POST", body: JSON.stringify(req) },
    ),
```

- [ ] **Step 2: Add useRunScraping hook**

In `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts`:

Add to the imports:
```typescript
import {
  scraperSourcesApi,
  type ActivateRequest,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type RecipeCreate,
  type RecipeRead,
  type RunRequest,
  type RunResponse,
  type ScraperSourceCreate,
  type ScraperSourceRead,
  type ScraperSourceUpdate,
  type ValidateRequest,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";
```

Append at the end of the file:

```typescript
export function useRunScraping(sourceId: string) {
  return useMutation<RunResponse, Error, RunRequest>({
    mutationFn: (req) => scraperSourcesApi.run(sourceId, req),
  });
}
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd mt-pricing-frontend
pnpm tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts
git add mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts
git commit -m "feat(scraper): frontend types RunRequest/RunResponse + useRunScraping hook"
```

---

## Task 5: Frontend — Run Scraping UI in validation tab

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx`
- Modify: `mt-pricing-frontend/messages/es.json`
- Modify: `mt-pricing-frontend/messages/en.json`
- Modify: `mt-pricing-frontend/messages/ar.json`

- [ ] **Step 1: Add i18n keys**

In `mt-pricing-frontend/messages/es.json`, inside `"validation": { ... }` (currently ends at `"errorGeneric": "Algo salió mal."`), add before the closing `}`:

```json
"scrape": "Ejecutar Scraping",
"scraping": "Ejecutando…",
"searchText": "Texto de búsqueda",
"searchTextPlaceholder": "ej. aspiradoras, herramientas",
"scrapeSuccess": "Scraping despachado — revisa los resultados en unos minutos.",
"taskId": "Task ID"
```

In `mt-pricing-frontend/messages/en.json`, same location:

```json
"scrape": "Run Scraping",
"scraping": "Running…",
"searchText": "Search text",
"searchTextPlaceholder": "e.g. vacuum cleaners, tools",
"scrapeSuccess": "Scraping dispatched — check results in a few minutes.",
"taskId": "Task ID"
```

In `mt-pricing-frontend/messages/ar.json`, same location:

```json
"scrape": "تشغيل الاستخراج",
"scraping": "جارٍ التشغيل…",
"searchText": "نص البحث",
"searchTextPlaceholder": "مثال: مكانس كهربائية",
"scrapeSuccess": "تم إرسال مهمة الاستخراج — تحقق من النتائج خلال دقائق.",
"taskId": "معرّف المهمة"
```

- [ ] **Step 2: Update _validation-tab.tsx**

The full updated file for `mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx`:

```tsx
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { CheckCircle2, Info, Play, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useScraperSourceRecipes,
  useValidateRecipe,
  useActivateSource,
  useRunScraping,
} from "@/lib/hooks/admin/use-scraper-sources";
import {
  type ScraperSourceRead,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";

interface Props {
  source: ScraperSourceRead;
}

export function ValidationTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.validation");
  const { data: recipes = [] } = useScraperSourceRecipes(source.id);
  const validate = useValidateRecipe(source.id);
  const activate = useActivateSource(source.id);
  const run = useRunScraping(source.id);

  const [testUrl, setTestUrl] = React.useState("");
  const [selectedRecipeId, setRecipeId] = React.useState<string>("");
  const [result, setResult] = React.useState<ValidateResponse | null>(null);
  const [searchText, setSearchText] = React.useState("");
  const [taskId, setTaskId] = React.useState<string | null>(null);

  // Derive effective recipe: user selection → live recipe → first recipe
  const recipeId =
    selectedRecipeId ||
    recipes.find((r) => r.is_live)?.id ||
    recipes[0]?.id ||
    "";

  const handleValidate = async () => {
    if (!testUrl || !recipeId) return;
    setResult(null);
    try {
      const res = await validate.mutateAsync({ recipe_id: recipeId, test_url: testUrl });
      setResult(res);
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  const handleActivate = async () => {
    if (!recipeId) return;
    try {
      await activate.mutateAsync({ recipe_id: recipeId });
      toast.success(t("activateSuccess"));
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  const handleRun = async () => {
    if (!searchText) return;
    try {
      const res = await run.mutateAsync({ search_text: searchText });
      setTaskId(res.celery_task_id);
      toast.success(t("scrapeSuccess"));
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  const isHeadlessSkipped = result?.status === "headless_skipped";
  const allPassing =
    result !== null &&
    (isHeadlessSkipped ||
      (Object.keys(result.field_results).length > 0 &&
        Object.values(result.field_results).every((v) => v === "pass")));

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
        <div className="space-y-1.5">
          <Label htmlFor="val-url">{t("testUrl")}</Label>
          <Input
            id="val-url"
            value={testUrl}
            onChange={(e) => setTestUrl(e.target.value)}
            placeholder={t("testUrlPlaceholder")}
          />
        </div>
        <Button onClick={handleValidate} disabled={!testUrl || !recipeId || validate.isPending}>
          {validate.isPending ? t("running") : t("run")}
        </Button>
      </div>

      {recipes.length > 0 && (
        <div className="space-y-1.5">
          <Label htmlFor="val-recipe">{t("recipe")}</Label>
          <Select value={recipeId} onValueChange={setRecipeId}>
            <SelectTrigger id="val-recipe" className="w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {recipes.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  v{r.version}
                  {r.is_live ? " (live)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{t("results")}</span>
            <Badge variant={allPassing ? "default" : "destructive"}>{result.status}</Badge>
          </div>

          {isHeadlessSkipped ? (
            <div className="flex gap-2 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Este sitio usa renderizado JavaScript (headless). La validación con curl no puede
                extraer productos — los selectores son correctos y funcionarán con el worker
                Playwright en producción. La recipe ha sido aprobada para activación.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("fieldName")}</TableHead>
                  <TableHead>{t("fieldResult")}</TableHead>
                  <TableHead>{t("fieldValue")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(result.field_results).map(([field, res]) => (
                  <TableRow key={field}>
                    <TableCell className="font-mono text-xs">{field}</TableCell>
                    <TableCell>
                      {res === "pass" ? (
                        <span className="flex items-center gap-1 text-green-600 text-xs">
                          <CheckCircle2 className="h-3.5 w-3.5" /> {t("pass")}
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-destructive text-xs">
                          <XCircle className="h-3.5 w-3.5" /> {res}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {result.records[0]?.[field] != null ? String(result.records[0][field]) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <div className="flex items-center gap-3">
            <Button
              onClick={handleActivate}
              disabled={!allPassing || activate.isPending}
              variant={allPassing ? "default" : "outline"}
            >
              {activate.isPending ? t("activating") : t("activate")}
            </Button>
            {!allPassing && (
              <p className="text-xs text-muted-foreground">{t("activateBlocked")}</p>
            )}
          </div>
        </div>
      )}

      {source.status === "active" && (
        <div className="border-t pt-4 space-y-3">
          <p className="text-sm font-medium flex items-center gap-1.5">
            <Play className="h-4 w-4" />
            {t("scrape")}
          </p>
          <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
            <div className="space-y-1.5">
              <Label htmlFor="search-text">{t("searchText")}</Label>
              <Input
                id="search-text"
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder={t("searchTextPlaceholder")}
              />
            </div>
            <Button onClick={handleRun} disabled={!searchText || run.isPending}>
              {run.isPending ? t("scraping") : t("scrape")}
            </Button>
          </div>
          {taskId && (
            <p className="text-xs text-muted-foreground">
              {t("taskId")}:{" "}
              <code className="font-mono">{taskId}</code>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd mt-pricing-frontend
pnpm tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```
git add mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx
git add mt-pricing-frontend/messages/es.json
git add mt-pricing-frontend/messages/en.json
git add mt-pricing-frontend/messages/ar.json
git commit -m "feat(scraper): Run Scraping UI en validation tab con search_text input"
```

---

## Task 6: PR + deploy

- [ ] **Step 1: Verify all tests pass**

```bash
cd mt-pricing-backend
python -m pytest tests/unit/services/scraper/ -v --no-cov
```
Expected: all pass.

- [ ] **Step 2: Push branch**

```
git push origin fix/scraper-detect-rsc-headless
```

Wait for CI. Only these checks are required for merge:
- `Lint (ruff)` — must pass
- `Typecheck (mypy)` — must pass
- `Detect OpenAPI drift` — must pass (spec was regenerated in Task 3)
- `Static checks (tsc + eslint)` — must pass
- `Conventional commits` — must pass
- `Tests (pytest)` has `continue-on-error: true` (pre-existing flaky DB tests — not a blocker)

- [ ] **Step 3: Start scraper-worker locally to verify end-to-end**

```bash
docker compose --profile scraper -f docker-compose.dev.yml up scraper-worker -d
```

Then trigger a run from the UI on an active source, or via curl:

```bash
curl -X POST http://localhost:8081/api/v1/scraper-sources/<SOURCE_ID>/run \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"search_text": "aspiradoras"}'
```

Expected: `{"celery_task_id": "...", "source_id": "..."}` with HTTP 202.

Check worker logs:
```bash
docker logs mt-scraper-worker -f
```
Expected: `scraper.source_start` and `scraper.source_done` log entries.

---

## Self-Review

**Spec coverage:**
- ✅ `playwright_generic.py` — Task 1
- ✅ `GenericConfigurableFetcher` headless support — Task 2
- ✅ `POST /run` endpoint — Task 3
- ✅ Frontend types + hook — Task 4
- ✅ Frontend Run Scraping UI — Task 5
- ✅ OpenAPI spec — Task 3 Step 5

**Placeholder scan:** None — all steps have concrete code.

**Type consistency:**
- `RunRequest.search_text: str` → used as `body.search_text` in route → `scrape_source_task.delay(str(source_id), search_text=body.search_text)` ✅
- `RunResponse.celery_task_id: str`, `source_id: UUID` → frontend `RunResponse.celery_task_id: string`, `source_id: string` ✅
- `useRunScraping` returns `RunResponse` → `res.celery_task_id` used in `handleRun` ✅
- `patchright_fetch` signature `async def patchright_fetch(url: str) -> str` matches `HtmlFetcher = Callable[[str], Awaitable[str]]` ✅
