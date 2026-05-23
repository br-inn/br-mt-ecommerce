# Scraper Sources Admin UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/admin/scraper/sources` admin page (master/detail layout) so operators can create, configure, validate and activate generic scraper sources — completing the Scraper Source Builder F1 feature.

**Architecture:** Master/detail single-page layout. Left panel: list of `ScraperSource` records with status badges. Right panel: Tabs (Info / Recipe / Validación). Two minor backend endpoints are missing and must be added first; all existing backend business logic remains unchanged.

**Tech Stack:** Next.js 16 · React 19 · TypeScript · Tailwind v4 · Shadcn/ui (new-york) · @tanstack/react-query · react-hook-form · zod · sonner · FastAPI · SQLAlchemy 2 async · Pydantic

---

## File Map

### Backend (2 files modified)
| File | Change |
|------|--------|
| `mt-pricing-backend/app/schemas/scraper_sources.py` | Add `ScraperSourceUpdate`, add `created_at` to `RecipeRead` |
| `mt-pricing-backend/app/repositories/scraper_sources.py` | Add `list_recipes()` + `update()` |
| `mt-pricing-backend/app/api/routes/scraper_sources.py` | Add `GET /{source_id}/recipes` + `PATCH /{source_id}` |
| `mt-pricing-backend/tests/api/test_scraper_sources_api.py` | Add tests for the two new endpoints |

### Frontend (7 files created, 2 modified)
| File | Responsibility |
|------|---------------|
| `mt-pricing-frontend/messages/en.json` | Add `admin.scraperSources` namespace |
| `mt-pricing-frontend/messages/es.json` | Same in Spanish |
| `mt-pricing-frontend/messages/ar.json` | Same in Arabic |
| `mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts` | Types + authedFetch API client |
| `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts` | React Query hooks (list, create, update, recipes, create-recipe, validate, activate) |
| `mt-pricing-frontend/tests/unit/hooks/use-scraper-sources.test.ts` | Unit tests for hooks |
| `mt-pricing-frontend/components/shell/sidebar.tsx` | +1 nav item in `SECTION_SYS_ADMIN` |
| `mt-pricing-frontend/app/(app)/admin/scraper/sources/page.tsx` | Server component: metadata + RbacGuard |
| `mt-pricing-frontend/app/(app)/admin/scraper/sources/_source-dialog.tsx` | SourceDialog (create + edit modes) |
| `mt-pricing-frontend/app/(app)/admin/scraper/sources/_client.tsx` | Main layout + list panel + source creation |
| `mt-pricing-frontend/app/(app)/admin/scraper/sources/_info-tab.tsx` | Info tab + edit trigger |
| `mt-pricing-frontend/app/(app)/admin/scraper/sources/_recipe-tab.tsx` | Recipe tab + new-version dialog |
| `mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx` | Validate + activate flow |

---

## Task 1 — Backend schemas: ScraperSourceUpdate + created_at on RecipeRead

**Files:**
- Modify: `mt-pricing-backend/app/schemas/scraper_sources.py`

- [ ] **Step 1: Add ScraperSourceUpdate and created_at to RecipeRead**

Open `mt-pricing-backend/app/schemas/scraper_sources.py`. After `ScraperSourceRead` add:

```python
class ScraperSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    base_url: str | None = Field(default=None, min_length=1)
    description: str | None = None
    destination_profile: Literal["competitor_price", "product_data"] | None = None
    fetch_mode: Literal["static", "headless", "stealth"] | None = None
    status: Literal["draft", "testing", "active", "disabled"] | None = None
```

Also update `RecipeRead` to include `created_at`:

```python
class RecipeRead(BaseModel):
    id: UUID
    source_id: UUID
    version: int
    is_live: bool
    validation_status: str
    has_unapproved_snippet: bool
    recipe: dict[str, Any]
    created_at: datetime         # ← add this line

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
git add mt-pricing-backend/app/schemas/scraper_sources.py
git commit -m "feat(scraper): add ScraperSourceUpdate schema + created_at to RecipeRead"
```

---

## Task 2 — Backend repository: list_recipes + update

**Files:**
- Modify: `mt-pricing-backend/app/repositories/scraper_sources.py`

- [ ] **Step 1: Add list_recipes and update methods**

Open `mt-pricing-backend/app/repositories/scraper_sources.py`. Append at the end of `ScraperSourceRepository`:

```python
    async def list_recipes(self, source_id: UUID) -> list[ScraperSourceRecipe]:
        result = await self._session.execute(
            select(ScraperSourceRecipe)
            .where(ScraperSourceRecipe.source_id == source_id)
            .order_by(ScraperSourceRecipe.version.desc())
        )
        return list(result.scalars().all())

    async def update(self, source_id: UUID, **kwargs: Any) -> ScraperSource | None:
        source = await self._session.get(ScraperSource, source_id)
        if source is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(source, key, value)
        await self._session.flush()
        return source
```

Also add `Any` to the imports at the top of the file (it's already imported — verify it's there):
```python
from typing import Any
```

- [ ] **Step 2: Commit**

```bash
git add mt-pricing-backend/app/repositories/scraper_sources.py
git commit -m "feat(scraper): add list_recipes and update to ScraperSourceRepository"
```

---

## Task 3 — Backend routes: GET recipes + PATCH source

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/scraper_sources.py`

- [ ] **Step 1: Import ScraperSourceUpdate**

In the imports block of `scraper_sources.py` (routes), add `ScraperSourceUpdate` to the import from `app.schemas.scraper_sources`:

```python
from app.schemas.scraper_sources import (
    ActivateRequest,
    RecipeRead,
    RecipeSubmit,
    ScraperSourceCreate,
    ScraperSourceRead,
    ScraperSourceUpdate,     # ← add
    ValidateRequest,
    ValidateResponse,
)
```

- [ ] **Step 2: Add GET /{source_id}/recipes endpoint**

After the `get_source` endpoint, add:

```python
@router.get(
    "/{source_id}/recipes",
    response_model=list[RecipeRead],
    operation_id="listScraperSourceRecipes",
)
async def list_source_recipes(
    source_id: UUID,
    _user: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[RecipeRead]:
    repo = ScraperSourceRepository(session)
    if await repo.get(source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return [RecipeRead.model_validate(r) for r in await repo.list_recipes(source_id)]
```

- [ ] **Step 3: Add PATCH /{source_id} endpoint**

After `list_source_recipes`, add:

```python
@router.patch(
    "/{source_id}",
    response_model=ScraperSourceRead,
    operation_id="updateScraperSource",
)
async def update_source(
    source_id: UUID,
    body: ScraperSourceUpdate,
    _user: Annotated[User, Depends(require_permissions("products:write"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScraperSourceRead:
    repo = ScraperSourceRepository(session)
    source = await repo.update(
        source_id,
        **body.model_dump(exclude_none=True),
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    await session.commit()
    return ScraperSourceRead.model_validate(source)
```

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-backend/app/api/routes/scraper_sources.py
git commit -m "feat(scraper): add GET /recipes and PATCH endpoints to scraper-sources router"
```

---

## Task 4 — Backend tests for new endpoints

**Files:**
- Modify: `mt-pricing-backend/tests/api/test_scraper_sources_api.py`

- [ ] **Step 1: Read the existing test file to find the fixture helpers**

Look for how existing tests create a source and build auth headers — you'll reuse those helpers. The key fixture is `postgres_container` (provided by conftest) and the JWT creation pattern at the top of the file.

- [ ] **Step 2: Add tests for PATCH and GET recipes**

Find the end of `test_scraper_sources_api.py` and append:

```python
@pytest.mark.api
async def test_patch_source_updates_fields(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    # Create a source first
    payload = {
        "name": "patch-test",
        "slug": "patch-test",
        "base_url": "https://example.com/s",
        "destination_profile": "competitor_price",
        "fetch_mode": "static",
    }
    r = await async_client.post("/api/v1/scraper-sources", json=payload, headers=admin_headers)
    assert r.status_code == 201
    source_id = r.json()["id"]

    # Patch the name and status
    patch = {"name": "patched-name", "status": "testing"}
    r2 = await async_client.patch(
        f"/api/v1/scraper-sources/{source_id}", json=patch, headers=admin_headers
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["name"] == "patched-name"
    assert data["status"] == "testing"


@pytest.mark.api
async def test_list_recipes_empty_then_populated(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    # Create a source
    payload = {
        "name": "recipe-list-test",
        "slug": "recipe-list-test",
        "base_url": "https://example.com/s",
        "destination_profile": "competitor_price",
        "fetch_mode": "static",
    }
    r = await async_client.post("/api/v1/scraper-sources", json=payload, headers=admin_headers)
    assert r.status_code == 201
    source_id = r.json()["id"]

    # No recipes yet
    r2 = await async_client.get(
        f"/api/v1/scraper-sources/{source_id}/recipes", headers=admin_headers
    )
    assert r2.status_code == 200
    assert r2.json() == []

    # Add a recipe
    recipe_payload = {
        "recipe": {
            "url_templates": {"search": "https://example.com/s?q={query}"},
            "list_item_selector": "div.item",
            "fields": [{"name": "price", "selector": ".price", "type": "currency"}],
        }
    }
    r3 = await async_client.post(
        f"/api/v1/scraper-sources/{source_id}/recipes",
        json=recipe_payload,
        headers=admin_headers,
    )
    assert r3.status_code == 201

    # Now list returns it
    r4 = await async_client.get(
        f"/api/v1/scraper-sources/{source_id}/recipes", headers=admin_headers
    )
    assert r4.status_code == 200
    recipes = r4.json()
    assert len(recipes) == 1
    assert recipes[0]["version"] == 1
    assert "created_at" in recipes[0]
```

- [ ] **Step 3: Run backend tests (CI)**

These tests require a running Postgres container — they run in CI. Push and verify the CI `backend-tests` job passes.

```bash
git add mt-pricing-backend/tests/api/test_scraper_sources_api.py
git commit -m "test(scraper): add PATCH source + GET recipes API tests"
```

---

## Task 5 — i18n keys

**Files:**
- Modify: `mt-pricing-frontend/messages/en.json`
- Modify: `mt-pricing-frontend/messages/es.json`
- Modify: `mt-pricing-frontend/messages/ar.json`

- [ ] **Step 1: Add keys to en.json**

Inside the `"admin"` object of `en.json`, add after the last existing admin entry:

```json
"scraperSources": {
  "title": "Scraper Sources",
  "description": "Manage generic configurable scraper sources and their extraction recipes.",
  "noPermission": "You do not have permission to view this section.",
  "newSource": "New Source",
  "selectSource": "Select a source to view its details.",
  "status": {
    "draft": "Draft",
    "testing": "Testing",
    "active": "Active",
    "disabled": "Disabled",
    "degraded": "Degraded"
  },
  "tabs": {
    "info": "Info",
    "recipe": "Recipe",
    "validation": "Validation"
  },
  "info": {
    "edit": "Edit",
    "editTitle": "Edit Source",
    "createTitle": "New Source",
    "name": "Name",
    "slug": "Slug",
    "slugHint": "Lowercase letters, numbers and hyphens only.",
    "baseUrl": "Base URL",
    "fetchMode": "Fetch mode",
    "destinationProfile": "Destination",
    "descriptionLabel": "Description",
    "save": "Save",
    "saving": "Saving…",
    "cancel": "Cancel",
    "createSuccess": "Source created.",
    "updateSuccess": "Source updated.",
    "errorDuplicateSlug": "That slug is already in use.",
    "errorGeneric": "Something went wrong."
  },
  "recipe": {
    "active": "Active recipe",
    "noRecipe": "No recipe yet.",
    "newVersion": "New version",
    "newVersionTitle": "New recipe version",
    "recipeJson": "Recipe JSON",
    "recipeJsonHint": "Must be valid JSON following the recipe schema.",
    "save": "Save",
    "saving": "Saving…",
    "cancel": "Cancel",
    "saveSuccess": "Recipe saved.",
    "errorInvalidJson": "Invalid JSON — fix before saving.",
    "errorGeneric": "Something went wrong.",
    "history": "Previous versions",
    "version": "v{version}",
    "validationStatus": {
      "unvalidated": "Unvalidated",
      "passing": "Passing",
      "failing": "Failing"
    }
  },
  "validation": {
    "testUrl": "Test URL",
    "testUrlPlaceholder": "https://example.com/page-to-scrape",
    "recipe": "Recipe to test",
    "run": "Test",
    "running": "Testing…",
    "activate": "Activate this recipe",
    "activating": "Activating…",
    "activateSuccess": "Recipe activated. Source is now active.",
    "activateBlocked": "Recipe must be passing to activate.",
    "results": "Results",
    "fieldName": "Field",
    "fieldResult": "Result",
    "fieldValue": "Extracted value",
    "pass": "Pass",
    "errorGeneric": "Something went wrong."
  }
}
```

- [ ] **Step 2: Add same keys to es.json**

In `es.json`, inside `"admin"`, add:

```json
"scraperSources": {
  "title": "Scraper Sources",
  "description": "Gestiona fuentes de scraping genéricas y sus recetas de extracción.",
  "noPermission": "No tienes permisos para ver esta sección.",
  "newSource": "Nueva Source",
  "selectSource": "Selecciona una source para ver su detalle.",
  "status": {
    "draft": "Borrador",
    "testing": "Pruebas",
    "active": "Activa",
    "disabled": "Deshabilitada",
    "degraded": "Degradada"
  },
  "tabs": {
    "info": "Info",
    "recipe": "Recipe",
    "validation": "Validación"
  },
  "info": {
    "edit": "Editar",
    "editTitle": "Editar Source",
    "createTitle": "Nueva Source",
    "name": "Nombre",
    "slug": "Slug",
    "slugHint": "Solo letras minúsculas, números y guiones.",
    "baseUrl": "URL base",
    "fetchMode": "Modo de fetch",
    "destinationProfile": "Destino",
    "descriptionLabel": "Descripción",
    "save": "Guardar",
    "saving": "Guardando…",
    "cancel": "Cancelar",
    "createSuccess": "Source creada.",
    "updateSuccess": "Source actualizada.",
    "errorDuplicateSlug": "Ese slug ya está en uso.",
    "errorGeneric": "Algo salió mal."
  },
  "recipe": {
    "active": "Recipe activa",
    "noRecipe": "Sin recipe todavía.",
    "newVersion": "Nueva versión",
    "newVersionTitle": "Nueva versión de recipe",
    "recipeJson": "JSON de la recipe",
    "recipeJsonHint": "Debe ser JSON válido siguiendo el schema de recipe.",
    "save": "Guardar",
    "saving": "Guardando…",
    "cancel": "Cancelar",
    "saveSuccess": "Recipe guardada.",
    "errorInvalidJson": "JSON inválido — corrige antes de guardar.",
    "errorGeneric": "Algo salió mal.",
    "history": "Versiones anteriores",
    "version": "v{version}",
    "validationStatus": {
      "unvalidated": "Sin validar",
      "passing": "Aprobada",
      "failing": "Fallida"
    }
  },
  "validation": {
    "testUrl": "URL de prueba",
    "testUrlPlaceholder": "https://ejemplo.com/pagina-a-scrapear",
    "recipe": "Recipe a probar",
    "run": "Probar",
    "running": "Probando…",
    "activate": "Activar esta recipe",
    "activating": "Activando…",
    "activateSuccess": "Recipe activada. La source está ahora activa.",
    "activateBlocked": "La recipe debe estar aprobada para activarse.",
    "results": "Resultados",
    "fieldName": "Campo",
    "fieldResult": "Resultado",
    "fieldValue": "Valor extraído",
    "pass": "OK",
    "errorGeneric": "Algo salió mal."
  }
}
```

- [ ] **Step 3: Add to ar.json**

In `ar.json`, inside `"admin"`, add (copy English values — Arabic translation can be done later):

```json
"scraperSources": {
  "title": "Scraper Sources",
  "description": "Manage generic configurable scraper sources and their extraction recipes.",
  "noPermission": "You do not have permission to view this section.",
  "newSource": "New Source",
  "selectSource": "Select a source to view its details.",
  "status": {
    "draft": "Draft",
    "testing": "Testing",
    "active": "Active",
    "disabled": "Disabled",
    "degraded": "Degraded"
  },
  "tabs": { "info": "Info", "recipe": "Recipe", "validation": "Validation" },
  "info": {
    "edit": "Edit", "editTitle": "Edit Source", "createTitle": "New Source",
    "name": "Name", "slug": "Slug", "slugHint": "Lowercase letters, numbers and hyphens only.",
    "baseUrl": "Base URL", "fetchMode": "Fetch mode", "destinationProfile": "Destination",
    "descriptionLabel": "Description", "save": "Save", "saving": "Saving…", "cancel": "Cancel",
    "createSuccess": "Source created.", "updateSuccess": "Source updated.",
    "errorDuplicateSlug": "That slug is already in use.", "errorGeneric": "Something went wrong."
  },
  "recipe": {
    "active": "Active recipe", "noRecipe": "No recipe yet.", "newVersion": "New version",
    "newVersionTitle": "New recipe version", "recipeJson": "Recipe JSON",
    "recipeJsonHint": "Must be valid JSON following the recipe schema.",
    "save": "Save", "saving": "Saving…", "cancel": "Cancel", "saveSuccess": "Recipe saved.",
    "errorInvalidJson": "Invalid JSON — fix before saving.", "errorGeneric": "Something went wrong.",
    "history": "Previous versions", "version": "v{version}",
    "validationStatus": { "unvalidated": "Unvalidated", "passing": "Passing", "failing": "Failing" }
  },
  "validation": {
    "testUrl": "Test URL", "testUrlPlaceholder": "https://example.com/page-to-scrape",
    "recipe": "Recipe to test", "run": "Test", "running": "Testing…",
    "activate": "Activate this recipe", "activating": "Activating…",
    "activateSuccess": "Recipe activated. Source is now active.",
    "activateBlocked": "Recipe must be passing to activate.",
    "results": "Results", "fieldName": "Field", "fieldResult": "Result",
    "fieldValue": "Extracted value", "pass": "Pass", "errorGeneric": "Something went wrong."
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/messages/en.json mt-pricing-frontend/messages/es.json mt-pricing-frontend/messages/ar.json
git commit -m "feat(scraper-sources): add i18n keys for admin UI (en/es/ar)"
```

---

## Task 6 — API client

**Files:**
- Create: `mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts`

- [ ] **Step 1: Create the file**

```typescript
"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export type ScraperSourceStatus = "draft" | "testing" | "active" | "disabled" | "degraded";
export type FetchMode = "static" | "headless" | "stealth";
export type DestinationProfile = "competitor_price" | "product_data";
export type ValidationStatus = "unvalidated" | "passing" | "failing";

export interface ScraperSourceRead {
  id: string;
  name: string;
  slug: string;
  base_url: string;
  description: string | null;
  destination_profile: DestinationProfile;
  fetch_mode: FetchMode;
  status: ScraperSourceStatus;
  competitor_brand_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScraperSourceCreate {
  name: string;
  slug: string;
  base_url: string;
  destination_profile: DestinationProfile;
  fetch_mode: FetchMode;
  description?: string | null;
}

export interface ScraperSourceUpdate {
  name?: string;
  base_url?: string;
  description?: string | null;
  destination_profile?: DestinationProfile;
  fetch_mode?: FetchMode;
  status?: ScraperSourceStatus;
}

export interface RecipeRead {
  id: string;
  source_id: string;
  version: number;
  is_live: boolean;
  validation_status: ValidationStatus;
  has_unapproved_snippet: boolean;
  recipe: Record<string, unknown>;
  created_at: string;
}

export interface RecipeCreate {
  recipe: Record<string, unknown>;
}

export interface ValidateRequest {
  recipe_id: string;
  test_url: string;
}

export interface ValidateResponse {
  status: string;
  field_results: Record<string, string>;
  records: Record<string, unknown>[];
}

export interface ActivateRequest {
  recipe_id: string;
}

export class ScraperSourcesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ScraperSourcesApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new ScraperSourcesApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const scraperSourcesApi = {
  list: (): Promise<ScraperSourceRead[]> =>
    authedFetch<ScraperSourceRead[]>("/api/v1/scraper-sources"),

  create: (req: ScraperSourceCreate): Promise<ScraperSourceRead> =>
    authedFetch<ScraperSourceRead>("/api/v1/scraper-sources", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  update: (id: string, req: ScraperSourceUpdate): Promise<ScraperSourceRead> =>
    authedFetch<ScraperSourceRead>(`/api/v1/scraper-sources/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    }),

  listRecipes: (sourceId: string): Promise<RecipeRead[]> =>
    authedFetch<RecipeRead[]>(`/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/recipes`),

  createRecipe: (sourceId: string, req: RecipeCreate): Promise<RecipeRead> =>
    authedFetch<RecipeRead>(`/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/recipes`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  validate: (sourceId: string, req: ValidateRequest): Promise<ValidateResponse> =>
    authedFetch<ValidateResponse>(`/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/validate`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  activate: (sourceId: string, req: ActivateRequest): Promise<ScraperSourceRead> =>
    authedFetch<ScraperSourceRead>(`/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/activate`, {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
```

- [ ] **Step 2: Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/scraper-sources.ts
git commit -m "feat(scraper-sources): add typed API client"
```

---

## Task 7 — React Query hooks (test-first)

**Files:**
- Create: `mt-pricing-frontend/tests/unit/hooks/use-scraper-sources.test.ts`
- Create: `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts`

- [ ] **Step 1: Write the failing tests**

Create `mt-pricing-frontend/tests/unit/hooks/use-scraper-sources.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import {
  useScraperSources,
  useCreateScraperSource,
  useUpdateScraperSource,
  useScraperSourceRecipes,
  useCreateRecipe,
  useValidateRecipe,
  useActivateSource,
} from "@/lib/hooks/admin/use-scraper-sources";
import {
  scraperSourcesApi,
  type ScraperSourceRead,
  type RecipeRead,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    client,
    Wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client }, children),
  };
}

const SOURCE: ScraperSourceRead = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "test-source",
  slug: "test-source",
  base_url: "https://example.com",
  description: null,
  destination_profile: "competitor_price",
  fetch_mode: "static",
  status: "draft",
  competitor_brand_id: null,
  created_at: "2026-05-24T00:00:00Z",
  updated_at: "2026-05-24T00:00:00Z",
};

const RECIPE: RecipeRead = {
  id: "00000000-0000-0000-0000-000000000002",
  source_id: SOURCE.id,
  version: 1,
  is_live: false,
  validation_status: "unvalidated",
  has_unapproved_snippet: false,
  recipe: { url_templates: { search: "" }, list_item_selector: "", fields: [] },
  created_at: "2026-05-24T00:00:00Z",
};

describe("useScraperSources", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("fetches and returns the sources list", async () => {
    vi.spyOn(scraperSourcesApi, "list").mockResolvedValue([SOURCE]);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(() => useScraperSources(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.id).toBe(SOURCE.id);
  });
});

describe("useCreateScraperSource", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls create and invalidates list query", async () => {
    vi.spyOn(scraperSourcesApi, "create").mockResolvedValue(SOURCE);
    const { Wrapper, client } = createWrapper();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useCreateScraperSource(), { wrapper: Wrapper });
    await result.current.mutateAsync({
      name: "test-source",
      slug: "test-source",
      base_url: "https://example.com",
      destination_profile: "competitor_price",
      fetch_mode: "static",
    });
    expect(invalidate).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: expect.arrayContaining(["scraper-sources"]) }),
    );
  });
});

describe("useScraperSourceRecipes", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("fetches recipes for a source", async () => {
    vi.spyOn(scraperSourcesApi, "listRecipes").mockResolvedValue([RECIPE]);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useScraperSourceRecipes(SOURCE.id),
      { wrapper: Wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0]?.id).toBe(RECIPE.id);
  });

  it("is disabled when sourceId is null", () => {
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useScraperSourceRecipes(null),
      { wrapper: Wrapper },
    );
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useValidateRecipe", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("calls validate with the correct sourceId", async () => {
    const response: ValidateResponse = {
      status: "passing",
      field_results: { price: "pass" },
      records: [],
    };
    const spy = vi.spyOn(scraperSourcesApi, "validate").mockResolvedValue(response);
    const { Wrapper } = createWrapper();
    const { result } = renderHook(
      () => useValidateRecipe(SOURCE.id),
      { wrapper: Wrapper },
    );
    await result.current.mutateAsync({ recipe_id: RECIPE.id, test_url: "https://example.com" });
    expect(spy).toHaveBeenCalledWith(SOURCE.id, {
      recipe_id: RECIPE.id,
      test_url: "https://example.com",
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd mt-pricing-frontend
npx vitest run tests/unit/hooks/use-scraper-sources.test.ts
```

Expected: FAIL — `Cannot find module '@/lib/hooks/admin/use-scraper-sources'`

- [ ] **Step 3: Create the hooks file**

Create `mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts`:

```typescript
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  scraperSourcesApi,
  type ActivateRequest,
  type RecipeCreate,
  type ScraperSourceCreate,
  type ScraperSourceRead,
  type ScraperSourceUpdate,
  type ValidateRequest,
  type ValidateResponse,
  type RecipeRead,
} from "@/lib/api/endpoints/scraper-sources";

const KEYS = {
  all: () => ["scraper-sources"] as const,
  list: () => [...KEYS.all(), "list"] as const,
  recipes: (sourceId: string) => [...KEYS.all(), sourceId, "recipes"] as const,
};

export function useScraperSources() {
  return useQuery({
    queryKey: KEYS.list(),
    queryFn: () => scraperSourcesApi.list(),
    staleTime: 30_000,
  });
}

export function useCreateScraperSource() {
  const qc = useQueryClient();
  return useMutation<ScraperSourceRead, Error, ScraperSourceCreate>({
    mutationFn: (req) => scraperSourcesApi.create(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export function useUpdateScraperSource() {
  const qc = useQueryClient();
  return useMutation<ScraperSourceRead, Error, { id: string; data: ScraperSourceUpdate }>({
    mutationFn: ({ id, data }) => scraperSourcesApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export function useScraperSourceRecipes(sourceId: string | null) {
  return useQuery<RecipeRead[]>({
    queryKey: sourceId ? KEYS.recipes(sourceId) : ["scraper-sources", "__none__", "recipes"],
    queryFn: () => scraperSourcesApi.listRecipes(sourceId!),
    enabled: sourceId !== null,
    staleTime: 60_000,
  });
}

export function useCreateRecipe(sourceId: string) {
  const qc = useQueryClient();
  return useMutation<RecipeRead, Error, RecipeCreate>({
    mutationFn: (req) => scraperSourcesApi.createRecipe(sourceId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.recipes(sourceId) }),
  });
}

export function useValidateRecipe(sourceId: string) {
  return useMutation<ValidateResponse, Error, ValidateRequest>({
    mutationFn: (req) => scraperSourcesApi.validate(sourceId, req),
  });
}

export function useActivateSource(sourceId: string) {
  const qc = useQueryClient();
  return useMutation<ScraperSourceRead, Error, ActivateRequest>({
    mutationFn: (req) => scraperSourcesApi.activate(sourceId, req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export const scraperSourceKeys = KEYS;
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/unit/hooks/use-scraper-sources.test.ts
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/lib/hooks/admin/use-scraper-sources.ts \
        mt-pricing-frontend/tests/unit/hooks/use-scraper-sources.test.ts
git commit -m "feat(scraper-sources): React Query hooks + tests"
```

---

## Task 8 — Sidebar entry

**Files:**
- Modify: `mt-pricing-frontend/components/shell/sidebar.tsx`

- [ ] **Step 1: Add Rss to the lucide-react import**

Find the lucide-react import block. Add `Rss` to the list (keep alphabetical order — insert after `Receipt`):

```typescript
  Receipt,
  Rss,          // ← add
  ScrollText,
```

- [ ] **Step 2: Add nav item to SECTION_SYS_ADMIN**

Find `SECTION_SYS_ADMIN`. Insert the new item after the `Scraper` entry:

```typescript
const SECTION_SYS_ADMIN: readonly NavItem[] = [
  { href: "/admin/usuarios", label: "Usuarios", icon: Users, permissions: ["users:read"] },
  { href: "/admin/jobs", label: "Jobs", icon: Timer, permissions: ["jobs:read"] },
  { href: "/admin/scraper", label: "Scraper", icon: Search, permissions: ["products:read"] },
  { href: "/admin/scraper/sources", label: "Scraper Sources", icon: Rss, permissions: ["admin:read"] },   // ← add
  { href: "/admin/competitor-brands", label: "Marcas competidoras", icon: Building2, permissions: ["admin:read"] },
] as const;
```

- [ ] **Step 3: Commit**

```bash
git add mt-pricing-frontend/components/shell/sidebar.tsx
git commit -m "feat(scraper-sources): add Scraper Sources to sidebar nav"
```

---

## Task 9 — Server page component

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/page.tsx`

- [ ] **Step 1: Create the file**

```typescript
import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { ScraperSourcesClient } from "./_client";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin.scraperSources");
  return { title: t("title") };
}

export default async function ScraperSourcesPage() {
  const t = await getTranslations("admin.scraperSources");

  return (
    <div className="space-y-4 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </header>

      <RbacGuard
        permissions={["admin:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <ScraperSourcesClient />
      </RbacGuard>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/admin/scraper/sources/page.tsx"
git commit -m "feat(scraper-sources): server page component"
```

---

## Task 10 — Source dialog (create + edit)

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_source-dialog.tsx`

This dialog is used in two modes: `"create"` (triggered from the list panel) and `"edit"` (triggered from the Info tab). Both modes share the same form fields and validation.

- [ ] **Step 1: Create the file**

```typescript
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateScraperSource, useUpdateScraperSource } from "@/lib/hooks/admin/use-scraper-sources";
import { ScraperSourcesApiError, type ScraperSourceRead } from "@/lib/api/endpoints/scraper-sources";

const schema = z.object({
  name: z.string().min(1).max(160),
  slug: z
    .string()
    .min(1)
    .max(80)
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers and hyphens only."),
  base_url: z.string().url(),
  destination_profile: z.enum(["competitor_price", "product_data"]),
  fetch_mode: z.enum(["static", "headless", "stealth"]),
  description: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  mode: "create" | "edit";
  source?: ScraperSourceRead;
  open: boolean;
  onClose: () => void;
  onSuccess?: (source: ScraperSourceRead) => void;
}

export function SourceDialog({ mode, source, open, onClose, onSuccess }: Props) {
  const t = useTranslations("admin.scraperSources.info");
  const create = useCreateScraperSource();
  const update = useUpdateScraperSource();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: source?.name ?? "",
      slug: source?.slug ?? "",
      base_url: source?.base_url ?? "",
      destination_profile: source?.destination_profile ?? "competitor_price",
      fetch_mode: source?.fetch_mode ?? "static",
      description: source?.description ?? "",
    },
  });

  React.useEffect(() => {
    if (open) {
      form.reset({
        name: source?.name ?? "",
        slug: source?.slug ?? "",
        base_url: source?.base_url ?? "",
        destination_profile: source?.destination_profile ?? "competitor_price",
        fetch_mode: source?.fetch_mode ?? "static",
        description: source?.description ?? "",
      });
    }
  }, [open, source, form]);

  const onSubmit = async (values: FormValues) => {
    try {
      let result: ScraperSourceRead;
      if (mode === "create") {
        result = await create.mutateAsync(values);
        toast.success(t("createSuccess"));
      } else {
        result = await update.mutateAsync({ id: source!.id, data: values });
        toast.success(t("updateSuccess"));
      }
      onSuccess?.(result);
      onClose();
    } catch (err) {
      if (err instanceof ScraperSourcesApiError && err.status === 409) {
        form.setError("slug", { message: t("errorDuplicateSlug") });
      } else {
        toast.error(t("errorGeneric"));
      }
    }
  };

  const isPending = create.isPending || update.isPending;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? t("createTitle") : t("editTitle")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ss-name">{t("name")}</Label>
            <Input id="ss-name" {...form.register("name")} />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-slug">{t("slug")}</Label>
            <Input
              id="ss-slug"
              {...form.register("slug")}
              disabled={mode === "edit"}
              className={mode === "edit" ? "text-muted-foreground" : ""}
            />
            <p className="text-xs text-muted-foreground">{t("slugHint")}</p>
            {form.formState.errors.slug && (
              <p className="text-xs text-destructive">{form.formState.errors.slug.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-url">{t("baseUrl")}</Label>
            <Input id="ss-url" {...form.register("base_url")} placeholder="https://" />
            {form.formState.errors.base_url && (
              <p className="text-xs text-destructive">{form.formState.errors.base_url.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-dest">{t("destinationProfile")}</Label>
            <Select
              value={form.watch("destination_profile")}
              onValueChange={(v) =>
                form.setValue("destination_profile", v as "competitor_price" | "product_data")
              }
            >
              <SelectTrigger id="ss-dest">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="competitor_price">competitor_price</SelectItem>
                <SelectItem value="product_data">product_data</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-mode">{t("fetchMode")}</Label>
            <Select
              value={form.watch("fetch_mode")}
              onValueChange={(v) => form.setValue("fetch_mode", v as "static")}
            >
              <SelectTrigger id="ss-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="static">static</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-desc">{t("descriptionLabel")}</Label>
            <Input id="ss-desc" {...form.register("description")} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? t("saving") : t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/admin/scraper/sources/_source-dialog.tsx"
git commit -m "feat(scraper-sources): SourceDialog component (create + edit)"
```

---

## Task 11 — Main client layout + list panel

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_client.tsx`

- [ ] **Step 1: Create the file**

```typescript
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils/cn";
import { useScraperSources } from "@/lib/hooks/admin/use-scraper-sources";
import { type ScraperSourceRead, type ScraperSourceStatus } from "@/lib/api/endpoints/scraper-sources";

import { SourceDialog } from "./_source-dialog";
import { InfoTab } from "./_info-tab";
import { RecipeTab } from "./_recipe-tab";
import { ValidationTab } from "./_validation-tab";

const STATUS_VARIANT: Record<ScraperSourceStatus, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  testing: "secondary",
  active: "default",
  disabled: "destructive",
  degraded: "destructive",
};

export function ScraperSourcesClient() {
  const t = useTranslations("admin.scraperSources");
  const tStatus = useTranslations("admin.scraperSources.status");
  const { data: sources = [], isLoading } = useScraperSources();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);

  const selected = sources.find((s) => s.id === selectedId) ?? null;

  return (
    <div className="flex gap-4 h-[calc(100vh-220px)] min-h-[500px]">
      {/* Left panel — source list */}
      <div className="w-64 flex-shrink-0 flex flex-col gap-3">
        <Button size="sm" className="w-full" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          {t("newSource")}
        </Button>

        <div className="flex-1 overflow-y-auto rounded-md border divide-y">
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between p-3">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-5 w-14" />
                </div>
              ))
            : sources.map((source) => (
                <button
                  key={source.id}
                  onClick={() => setSelectedId(source.id)}
                  className={cn(
                    "w-full flex items-center justify-between p-3 text-left text-sm hover:bg-muted/50 transition-colors",
                    selectedId === source.id && "bg-muted font-medium",
                  )}
                >
                  <span className="truncate max-w-[120px]" title={source.name}>
                    {source.name}
                  </span>
                  <Badge variant={STATUS_VARIANT[source.status]} className="ml-2 shrink-0 text-xs">
                    {tStatus(source.status)}
                  </Badge>
                </button>
              ))}
        </div>
      </div>

      {/* Right panel — detail */}
      <div className="flex-1 min-w-0">
        {selected ? (
          <SourceDetail source={selected} />
        ) : (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground border rounded-md">
            {t("selectSource")}
          </div>
        )}
      </div>

      <SourceDialog
        mode="create"
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={(s) => setSelectedId(s.id)}
      />
    </div>
  );
}

function SourceDetail({ source }: { source: ScraperSourceRead }) {
  const t = useTranslations("admin.scraperSources.tabs");

  return (
    <Tabs defaultValue="info" className="h-full flex flex-col">
      <TabsList className="w-fit">
        <TabsTrigger value="info">{t("info")}</TabsTrigger>
        <TabsTrigger value="recipe">{t("recipe")}</TabsTrigger>
        <TabsTrigger value="validation">{t("validation")}</TabsTrigger>
      </TabsList>
      <div className="flex-1 overflow-y-auto mt-4">
        <TabsContent value="info" className="mt-0">
          <InfoTab source={source} />
        </TabsContent>
        <TabsContent value="recipe" className="mt-0">
          <RecipeTab source={source} />
        </TabsContent>
        <TabsContent value="validation" className="mt-0">
          <ValidationTab source={source} />
        </TabsContent>
      </div>
    </Tabs>
  );
}
```

- [ ] **Step 2: Commit (skeleton — tabs will fail until tab files exist)**

```bash
git add "mt-pricing-frontend/app/(app)/admin/scraper/sources/_client.tsx"
git commit -m "feat(scraper-sources): main client layout + source list panel"
```

---

## Task 12 — Info tab

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_info-tab.tsx`

- [ ] **Step 1: Create the file**

```typescript
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type ScraperSourceRead, type ScraperSourceStatus } from "@/lib/api/endpoints/scraper-sources";
import { SourceDialog } from "./_source-dialog";

const STATUS_VARIANT: Record<ScraperSourceStatus, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  testing: "secondary",
  active: "default",
  disabled: "destructive",
  degraded: "destructive",
};

interface Props {
  source: ScraperSourceRead;
}

export function InfoTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.info");
  const tStatus = useTranslations("admin.scraperSources.status");
  const [editOpen, setEditOpen] = React.useState(false);

  return (
    <div className="space-y-4 max-w-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold">{source.name}</span>
          <Badge variant={STATUS_VARIANT[source.status]}>{tStatus(source.status)}</Badge>
        </div>
        <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
          {t("edit")}
        </Button>
      </div>

      <dl className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Slug</dt>
        <dd className="font-mono">{source.slug}</dd>

        <dt className="text-muted-foreground">{t("baseUrl")}</dt>
        <dd className="break-all">{source.base_url}</dd>

        <dt className="text-muted-foreground">{t("fetchMode")}</dt>
        <dd>{source.fetch_mode}</dd>

        <dt className="text-muted-foreground">{t("destinationProfile")}</dt>
        <dd>{source.destination_profile}</dd>

        {source.description && (
          <>
            <dt className="text-muted-foreground">{t("descriptionLabel")}</dt>
            <dd>{source.description}</dd>
          </>
        )}

        <dt className="text-muted-foreground">ID</dt>
        <dd className="font-mono text-xs text-muted-foreground">{source.id}</dd>
      </dl>

      <SourceDialog
        mode="edit"
        source={source}
        open={editOpen}
        onClose={() => setEditOpen(false)}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/admin/scraper/sources/_info-tab.tsx"
git commit -m "feat(scraper-sources): InfoTab with edit dialog"
```

---

## Task 13 — Recipe tab

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_recipe-tab.tsx`

- [ ] **Step 1: Create the file**

```typescript
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Plus, ChevronDown } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  useScraperSourceRecipes,
  useCreateRecipe,
} from "@/lib/hooks/admin/use-scraper-sources";
import { type ScraperSourceRead, type RecipeRead, type ValidationStatus } from "@/lib/api/endpoints/scraper-sources";

const EMPTY_RECIPE = JSON.stringify(
  {
    url_templates: { search: "", pdp: "" },
    list_item_selector: "",
    fields: [{ name: "price", selector: ".price", type: "currency" }],
  },
  null,
  2,
);

const VALIDATION_VARIANT: Record<ValidationStatus, "default" | "secondary" | "destructive" | "outline"> = {
  unvalidated: "outline",
  passing: "default",
  failing: "destructive",
};

interface Props {
  source: ScraperSourceRead;
}

export function RecipeTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.recipe");
  const { data: recipes = [], isLoading } = useScraperSourceRecipes(source.id);
  const [dialogOpen, setDialogOpen] = React.useState(false);

  const liveRecipe = recipes.find((r) => r.is_live) ?? null;
  const previousRecipes = recipes.filter((r) => !r.is_live);

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">{t("active")}</div>;
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{t("active")}</span>
        <Button variant="outline" size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          {t("newVersion")}
        </Button>
      </div>

      {liveRecipe ? (
        <RecipeCard recipe={liveRecipe} />
      ) : (
        <p className="text-sm text-muted-foreground">{t("noRecipe")}</p>
      )}

      {previousRecipes.length > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ChevronDown className="h-3.5 w-3.5" />
            {t("history")}
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {previousRecipes.map((r) => (
              <RecipeCard key={r.id} recipe={r} />
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}

      <NewRecipeDialog
        source={source}
        liveRecipe={liveRecipe}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  );
}

function RecipeCard({ recipe }: { recipe: RecipeRead }) {
  const t = useTranslations("admin.scraperSources.recipe");

  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center gap-2 text-sm">
        <span className="font-mono font-medium">
          {t("version", { version: String(recipe.version) })}
        </span>
        {recipe.is_live && <Badge className="text-xs">live</Badge>}
        <Badge variant={VALIDATION_VARIANT[recipe.validation_status as ValidationStatus]} className="text-xs">
          {t(`validationStatus.${recipe.validation_status}`)}
        </Badge>
        <span className="text-xs text-muted-foreground ml-auto">
          {new Date(recipe.created_at).toLocaleDateString()}
        </span>
      </div>
      <pre className="rounded bg-muted p-3 text-xs overflow-x-auto max-h-48">
        {JSON.stringify(recipe.recipe, null, 2)}
      </pre>
    </div>
  );
}

function NewRecipeDialog({
  source,
  liveRecipe,
  open,
  onClose,
}: {
  source: ScraperSourceRead;
  liveRecipe: RecipeRead | null;
  open: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("admin.scraperSources.recipe");
  const createRecipe = useCreateRecipe(source.id);
  const [json, setJson] = React.useState("");
  const [jsonError, setJsonError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setJson(liveRecipe ? JSON.stringify(liveRecipe.recipe, null, 2) : EMPTY_RECIPE);
      setJsonError(null);
    }
  }, [open, liveRecipe]);

  const handleSave = async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(json);
    } catch {
      setJsonError(t("errorInvalidJson"));
      return;
    }
    setJsonError(null);
    try {
      await createRecipe.mutateAsync({ recipe: parsed as Record<string, unknown> });
      toast.success(t("saveSuccess"));
      onClose();
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("newVersionTitle")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label>{t("recipeJson")}</Label>
          <p className="text-xs text-muted-foreground">{t("recipeJsonHint")}</p>
          <textarea
            value={json}
            onChange={(e) => setJson(e.target.value)}
            className="w-full rounded-md border bg-muted font-mono text-xs p-3 h-72 resize-y focus:outline-none focus:ring-1 focus:ring-ring"
            spellCheck={false}
          />
          {jsonError && <p className="text-xs text-destructive">{jsonError}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={createRecipe.isPending}>
            {t("cancel")}
          </Button>
          <Button onClick={handleSave} disabled={createRecipe.isPending}>
            {createRecipe.isPending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/admin/scraper/sources/_recipe-tab.tsx"
git commit -m "feat(scraper-sources): RecipeTab with new-version dialog"
```

---

## Task 14 — Validation tab

**Files:**
- Create: `mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx`

- [ ] **Step 1: Create the file**

```typescript
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { CheckCircle2, XCircle } from "lucide-react";
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
} from "@/lib/hooks/admin/use-scraper-sources";
import { type ScraperSourceRead, type ValidateResponse } from "@/lib/api/endpoints/scraper-sources";

interface Props {
  source: ScraperSourceRead;
}

export function ValidationTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.validation");
  const { data: recipes = [] } = useScraperSourceRecipes(source.id);
  const validate = useValidateRecipe(source.id);
  const activate = useActivateSource(source.id);

  const [testUrl, setTestUrl] = React.useState("");
  const [recipeId, setRecipeId] = React.useState<string>("");
  const [result, setResult] = React.useState<ValidateResponse | null>(null);

  // Default to the live recipe when recipes load
  React.useEffect(() => {
    if (recipes.length > 0 && !recipeId) {
      const live = recipes.find((r) => r.is_live);
      setRecipeId(live?.id ?? recipes[0]?.id ?? "");
    }
  }, [recipes, recipeId]);

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

  const allPassing = result !== null && Object.values(result.field_results).every((v) => v === "pass");

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
        <Button
          onClick={handleValidate}
          disabled={!testUrl || !recipeId || validate.isPending}
        >
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
            <Badge variant={allPassing ? "default" : "destructive"}>
              {result.status}
            </Badge>
          </div>

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
                    {result.records[0]?.[field] != null
                      ? String(result.records[0][field])
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

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
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/admin/scraper/sources/_validation-tab.tsx"
git commit -m "feat(scraper-sources): ValidationTab — validate + activate flow"
```

---

## Task 15 — TypeScript check + PR

**Files:** all of the above

- [ ] **Step 1: Run TypeScript type check**

```bash
cd mt-pricing-frontend
npx tsc --noEmit
```

Fix any type errors before proceeding. Common issues:
- Missing `Table*` imports from `@/components/ui/table` — verify the component exists. If not, run `npx shadcn@latest add table` first.
- Missing `Collapsible*` — run `npx shadcn@latest add collapsible` if not already installed.

- [ ] **Step 2: Run full frontend test suite**

```bash
npx vitest run
```

Expected: all existing tests + new hook tests pass.

- [ ] **Step 3: Verify Shadcn components are installed**

```bash
ls mt-pricing-frontend/components/ui/table.tsx
ls mt-pricing-frontend/components/ui/collapsible.tsx
```

If either is missing, install:

```bash
cd mt-pricing-frontend
npx shadcn@latest add table collapsible
```

Re-run TypeScript check after installing.

- [ ] **Step 4: Push branch and open PR**

```bash
git checkout -b feature/scraper-sources-admin-ui
git push -u origin feature/scraper-sources-admin-ui
gh pr create \
  --title "feat(scraper-sources): Admin UI — F1 frontend complete" \
  --body "$(cat <<'EOF'
## Summary

- Adds `/admin/scraper/sources` master/detail admin page to manage generic configurable scraper sources
- Adds **Scraper Sources** entry to sidebar under Administración
- Three-tab detail panel: **Info** (view/edit source), **Recipe** (manage versioned recipes), **Validación** (test recipe + activate)
- Adds two missing backend endpoints: `GET /scraper-sources/{id}/recipes` and `PATCH /scraper-sources/{id}`
- Adds i18n keys for en/es/ar

## Test Plan

- [ ] Log in as admin, verify "Scraper Sources" appears in the sidebar
- [ ] Create a new source — verify it appears in the list with `draft` badge
- [ ] Edit the source name — verify the list updates
- [ ] In Recipe tab, create a new version pasting valid JSON — verify it appears
- [ ] In Validation tab, enter a test URL and run — verify field results table appears
- [ ] If all fields pass, click Activate — verify the source badge changes to `active`
- [ ] CI: backend `pytest tests/api/test_scraper_sources_api.py` passes
- [ ] CI: frontend `vitest run tests/unit/hooks/use-scraper-sources.test.ts` passes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** All 12 spec sections covered. `fetch_mode` only shows `static` in the form (F2/F3 omission explicit). Validation tab uses `field_results` dict from `ValidateResponse`. Activate requires `passing` status (enforced by button disabled state + server 409).
- **No placeholders:** All steps contain complete, runnable code.
- **Type consistency:** `ScraperSourceStatus`, `FetchMode`, `DestinationProfile`, `ValidationStatus` defined in Task 6 and imported consistently across Tasks 7–14.
- **RecipeRead.created_at:** Added to schema in Task 1 and used in `RecipeCard` in Task 13.
- **Shadcn `Table` and `Collapsible`:** May need `npx shadcn@latest add` — guarded by Task 15 step 3.
