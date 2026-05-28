# Catálogo — Offset Pagination Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace cursor-based infinite-scroll in `/catalogo` with server-side offset pagination (page numbers, total count, prev/next arrows) and debounce facet queries to fix filter UX and slow load times.

**Architecture:** Backend adds `page`/`pages` fields to the `Pagination` generic schema and offset mode to `ProductRepository`; route endpoint passes `page` query param through. Frontend replaces `useInfiniteQuery` with `useQuery + keepPreviousData`, replaces the `Paginator` component with one showing page numbers, and debounces the facet query.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async (backend); Next.js 16 + React Query v5 + nuqs + Tailwind (frontend); pytest + vitest

---

## File Map

**Backend — create/modify:**
- `mt-pricing-backend/app/schemas/common.py` — add `page`/`pages` to `Pagination`
- `mt-pricing-backend/app/repositories/product.py` — add `page` param + offset branch
- `mt-pricing-backend/app/services/products/product_service.py` — pass `page` through
- `mt-pricing-backend/app/api/routes/products.py` — accept `page` query param, return enriched response
- `mt-pricing-backend/tests/api/test_products_offset.py` — **new** test file
- `_bmad-output/planning-artifacts/mt-api-contract-openapi.json` — regenerated

**Frontend — create/modify:**
- `mt-pricing-frontend/lib/api/endpoints/products.ts` — add `page`/`pages` to types + `productsApi.list`
- `mt-pricing-frontend/lib/hooks/products/use-products.ts` — replace `useInfiniteQuery` → `useQuery`
- `mt-pricing-frontend/tests/unit/hooks/use-products.test.ts` — update to match new hook shape
- `mt-pricing-frontend/app/(app)/catalogo/_components/paginator.tsx` — rewrite with page numbers
- `mt-pricing-frontend/lib/hooks/products/use-facets.ts` — add 400ms debounce
- `mt-pricing-frontend/app/(app)/catalogo/page.tsx` — wire page state, update Paginator call

---

## Stream A — Backend (Tasks 1–3)

### Task 1: Extend `Pagination` schema with `page` / `pages`

**Files:**
- Modify: `mt-pricing-backend/app/schemas/common.py`

- [ ] **Step 1.1 — Read current schema**

  Run: `cat mt-pricing-backend/app/schemas/common.py`
  Verify `Pagination` class ends at line ~63 with `page_size: int`.

- [ ] **Step 1.2 — Add `page` and `pages` fields**

  In `mt-pricing-backend/app/schemas/common.py`, replace the `Pagination` class body:

  ```python
  class Pagination(BaseModel, Generic[T]):
      """Envoltorio paginado estándar para listados."""

      model_config = ConfigDict(extra="forbid")

      items: list[T] = Field(description="Página actual de resultados.")
      cursor: Cursor = Field(default_factory=Cursor, description="Cursores de navegación.")
      total: int | None = Field(
          default=None,
          ge=0,
          description="Total absoluto si el endpoint lo expone (puede ser caro).",
      )
      page_size: int = Field(ge=1, le=500, description="Tamaño de página solicitado.")
      page: int | None = Field(default=None, ge=1, description="Página actual (offset mode).")
      pages: int | None = Field(default=None, ge=0, description="Total de páginas (offset mode).")
  ```

- [ ] **Step 1.3 — Verify no existing tests break**

  Run: `cd mt-pricing-backend && uv run pytest tests/ -x -q --tb=short -k "not test_products_offset" 2>&1 | tail -20`
  Expected: all existing tests pass (new fields have `default=None` so backward-compat).

- [ ] **Step 1.4 — Commit**

  ```
  git add mt-pricing-backend/app/schemas/common.py
  git commit -m "feat(catalogo): add page/pages fields to Pagination schema"
  ```

---

### Task 2: Add offset pagination to `ProductRepository`

**Files:**
- Modify: `mt-pricing-backend/app/repositories/product.py`
- Create: `mt-pricing-backend/tests/api/test_products_offset.py`

- [ ] **Step 2.1 — Write failing test first**

  Create `mt-pricing-backend/tests/api/test_products_offset.py`:

  ```python
  """Integration tests for offset (page-based) pagination of GET /products."""
  from __future__ import annotations

  import os
  import time
  from uuid import uuid4

  import pytest
  import pytest_asyncio
  from httpx import ASGITransport, AsyncClient
  from jose import jwt
  from sqlalchemy.ext.asyncio import AsyncSession

  os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
  os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
  os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
  os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-test")

  JWT_SECRET = "test-jwt-secret-deterministic-32chars!"


  def _emit_jwt(*, sub: str, email: str) -> str:
      now = int(time.time())
      return jwt.encode(
          {
              "sub": sub,
              "aud": "authenticated",
              "email": email,
              "iat": now,
              "exp": now + 3600,
              "app_metadata": {"role": "comercial"},
          },
          JWT_SECRET,
          algorithm="HS256",
      )


  # --- fixtures (copied from test_products_cursor.py pattern) ---

  @pytest_asyncio.fixture
  async def db(tmp_path):
      """SQLite async session for offset pagination tests."""
      from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
      from app.db.base import Base

      engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
      async with engine.begin() as conn:
          await conn.run_sync(Base.metadata.create_all)
      factory = async_sessionmaker(engine, expire_on_commit=False)
      async with factory() as session:
          yield session
      await engine.dispose()


  @pytest_asyncio.fixture
  async def client(db):
      from app.main import app
      from app.db.engine import get_sessionmaker
      from sqlalchemy.ext.asyncio import async_sessionmaker

      def override_factory():
          return async_sessionmaker(db.get_bind(), expire_on_commit=False)

      app.dependency_overrides[get_sessionmaker] = override_factory
      async with AsyncClient(
          transport=ASGITransport(app=app), base_url="http://test"
      ) as c:
          yield c
      app.dependency_overrides.clear()


  async def _seed_products(session: AsyncSession, count: int = 5) -> list[str]:
      """Insert `count` products sorted by SKU and return their SKUs."""
      from app.db.models.product import Product
      from app.db.models.user import User

      user = User(
          id=uuid4(),
          email="test@test.com",
          hashed_password="",
          role="admin",
      )
      session.add(user)
      skus = [f"TST-{i:03d}" for i in range(1, count + 1)]
      for sku in skus:
          session.add(
              Product(
                  internal_id=uuid4(),
                  sku=sku,
                  data_quality="partial",
                  lifecycle_status="active",
              )
          )
      await session.commit()
      return skus


  @pytest.mark.asyncio
  async def test_offset_page1_returns_correct_slice(client, db):
      """Page 1 with limit=2 returns first 2 SKUs and total=5."""
      skus = await _seed_products(db, 5)
      token = _emit_jwt(sub=str(uuid4()), email="test@test.com")
      r = await client.get(
          "/api/v1/products?page=1&limit=2",
          headers={"Authorization": f"Bearer {token}"},
      )
      assert r.status_code == 200
      body = r.json()
      assert body["total"] == 5
      assert body["page"] == 1
      assert body["pages"] == 3
      assert body["page_size"] == 2
      returned_skus = [i["sku"] for i in body["items"]]
      assert returned_skus == skus[:2]


  @pytest.mark.asyncio
  async def test_offset_page2_returns_middle_slice(client, db):
      """Page 2 with limit=2 returns SKUs 3-4."""
      skus = await _seed_products(db, 5)
      token = _emit_jwt(sub=str(uuid4()), email="test@test.com")
      r = await client.get(
          "/api/v1/products?page=2&limit=2",
          headers={"Authorization": f"Bearer {token}"},
      )
      assert r.status_code == 200
      body = r.json()
      assert body["page"] == 2
      assert [i["sku"] for i in body["items"]] == skus[2:4]


  @pytest.mark.asyncio
  async def test_offset_last_page_partial(client, db):
      """Last page (page=3, limit=2) returns only 1 item (5th SKU)."""
      skus = await _seed_products(db, 5)
      token = _emit_jwt(sub=str(uuid4()), email="test@test.com")
      r = await client.get(
          "/api/v1/products?page=3&limit=2",
          headers={"Authorization": f"Bearer {token}"},
      )
      assert r.status_code == 200
      body = r.json()
      assert len(body["items"]) == 1
      assert body["items"][0]["sku"] == skus[4]


  @pytest.mark.asyncio
  async def test_cursor_mode_unchanged(client, db):
      """Without ?page=, cursor mode still works and total is null."""
      await _seed_products(db, 3)
      token = _emit_jwt(sub=str(uuid4()), email="test@test.com")
      r = await client.get(
          "/api/v1/products?limit=2",
          headers={"Authorization": f"Bearer {token}"},
      )
      assert r.status_code == 200
      body = r.json()
      assert body["total"] is None
      assert body["page"] is None
      assert body["pages"] is None
      assert len(body["items"]) == 2
      assert body["cursor"]["next"] is not None
  ```

- [ ] **Step 2.2 — Run test to verify it fails**

  Run: `cd mt-pricing-backend && uv run pytest tests/api/test_products_offset.py -x -q 2>&1 | tail -20`
  Expected: FAIL with `assert body["page"] == 1` → `AssertionError` (field is None).

- [ ] **Step 2.3 — Add `page` param to repository**

  In `mt-pricing-backend/app/repositories/product.py`, find the `list_paginated_with_filters` method signature and add `page: int | None = None` after `include_total`:

  ```python
  async def list_paginated_with_filters(
      self,
      *,
      # ... existing params ...
      cursor: str | None = None,
      limit: int = 50,
      include_total: bool = False,
      page: int | None = None,  # <-- ADD THIS
      # ... stage 3 params ...
  ) -> tuple[Sequence[Product], str | None, int | None]:
  ```

- [ ] **Step 2.4 — Force `include_total=True` when offset mode**

  In the same method, find the line `total: int | None = None` (just before the `if include_total:` block) and add the override just before it:

  ```python
  # Offset mode forces a total count so the UI can show page numbers.
  if page is not None:
      include_total = True

  total: int | None = None
  if include_total:
      count_stmt = select(func.count()).select_from(Product)
      if clauses:
          count_stmt = count_stmt.where(and_(*clauses))
      total_res = await self.session.execute(count_stmt)
      total = int(total_res.scalar_one() or 0)
  ```

- [ ] **Step 2.5 — Replace cursor-only tail with offset branch**

  Find the block at the end of the method that starts with `# Cursor — append AL FINAL...` and replace it entirely:

  ```python
  # Cursor — append AL FINAL para que no participe del count(*).
  if page is not None:
      # Offset mode: skip cursor, apply OFFSET.
      offset = (page - 1) * limit
      stmt = stmt.order_by(Product.sku.asc()).limit(limit).offset(offset)
      result = await self.session.execute(stmt)
      rows = list(result.scalars().all())
      return rows, None, total
  else:
      if cursor:
          stmt = stmt.where(Product.sku > cursor)
      stmt = stmt.order_by(Product.sku.asc()).limit(limit + 1)
      result = await self.session.execute(stmt)
      rows = list(result.scalars().all())
      next_cursor: str | None = None
      if len(rows) > limit:
          next_cursor = rows[limit - 1].sku
          rows = rows[:limit]
      return rows, next_cursor, total
  ```

- [ ] **Step 2.6 — Run tests to verify they pass**

  Run: `cd mt-pricing-backend && uv run pytest tests/api/test_products_offset.py -x -q 2>&1 | tail -20`
  Expected: 5 tests PASSED.

- [ ] **Step 2.7 — Verify no regressions**

  Run: `cd mt-pricing-backend && uv run pytest tests/api/test_products_cursor.py tests/api/test_products_filters.py -q 2>&1 | tail -10`
  Expected: all pass.

- [ ] **Step 2.8 — Commit**

  ```
  git add mt-pricing-backend/app/repositories/product.py \
          mt-pricing-backend/tests/api/test_products_offset.py
  git commit -m "feat(catalogo): add offset pagination to ProductRepository"
  ```

---

### Task 3: Wire through service + route + regenerate OpenAPI

**Files:**
- Modify: `mt-pricing-backend/app/services/products/product_service.py`
- Modify: `mt-pricing-backend/app/api/routes/products.py`
- Modify: `_bmad-output/planning-artifacts/mt-api-contract-openapi.json`

- [ ] **Step 3.1 — Add `page` to `ProductService.list_products`**

  In `mt-pricing-backend/app/services/products/product_service.py`, find the `list_products` method signature and add `page: int | None = None` after `include_total`:

  ```python
  async def list_products(
      self,
      *,
      # ... existing params ...
      include_total: bool = False,
      page: int | None = None,  # <-- ADD
      # ... stage 3 params ...
  ) -> tuple[Sequence[Product], str | None, int | None]:
      return await self.products.list_paginated_with_filters(
          # ... existing kwargs ...
          include_total=include_total,
          page=page,  # <-- ADD
          # ... stage 3 kwargs ...
      )
  ```

- [ ] **Step 3.2 — Add `page` query param to route endpoint**

  In `mt-pricing-backend/app/api/routes/products.py`, find the `list_products` route function. Add `import math` at the top of the file if not present. Then add `page` parameter to the function signature (after `include_total`):

  ```python
  page: Annotated[int | None, Query(ge=1, description="Offset page (activates include_total)")] = None,
  ```

- [ ] **Step 3.3 — Pass `page` to service and compute `pages` in response**

  Find the call to `service.list_products(...)` and add `page=page`. Then find the return statement and replace it:

  ```python
  rows, next_sku, total = await service.list_products(
      # ... existing kwargs ...
      include_total=include_total,
      page=page,
      # ...
  )
  ```

  Then, just before `return Pagination[ProductResponse](...)`, add:

  ```python
  pages_count: int | None = None
  if page is not None and total is not None:
      import math as _math
      pages_count = max(1, _math.ceil(total / limit))
  ```

  And update the return statement:

  ```python
  return Pagination[ProductResponse](
      items=items,
      cursor=Cursor(next=encode_sku_cursor(next_sku)),
      page_size=limit,
      total=total,
      page=page,
      pages=pages_count,
  )
  ```

- [ ] **Step 3.4 — Run full backend test suite**

  Run: `cd mt-pricing-backend && uv run pytest tests/ -x -q 2>&1 | tail -20`
  Expected: all tests pass.

- [ ] **Step 3.5 — Regenerate OpenAPI spec**

  Run: `cd mt-pricing-backend && uv run python -m app.scripts.export_openapi`
  Expected: `_bmad-output/planning-artifacts/mt-api-contract-openapi.json` updated.

- [ ] **Step 3.6 — Commit**

  ```
  git add mt-pricing-backend/app/services/products/product_service.py \
          mt-pricing-backend/app/api/routes/products.py \
          _bmad-output/planning-artifacts/mt-api-contract-openapi.json
  git commit -m "feat(catalogo): wire page param through service+route, regenerate OpenAPI"
  ```

---

## Stream B — Frontend (Tasks 4–7)

> These tasks can start in parallel with Stream A Tasks 1-3 since the API contract is already defined above. Tasks 4-6 are independent of the backend being deployed — the types and components can be written against the agreed contract.

---

### Task 4: Update frontend API types and `productsApi.list`

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/products.ts`

- [ ] **Step 4.1 — Add `page`/`per_page` to `ProductFilters`**

  Find `export interface ProductFilters` (line ~556) and add two fields after `tier_code`:

  ```typescript
  export interface ProductFilters {
    // ... existing fields ...
    tier_code?: string | undefined;
    /** Offset pagination: 1-based page number. Activates include_total on backend. */
    page?: number | undefined;
    /** Alias for `limit` used with offset pagination (per_page items per page). */
    per_page?: number | undefined;
  }
  ```

- [ ] **Step 4.2 — Add `page`/`pages` to `ProductListResponse`**

  Find `export interface ProductListResponse` (~line 380):

  ```typescript
  export interface ProductListResponse {
    items: ProductListItem[];
    next_cursor: string | null;
    total: number | null;
    page_size: number;
    /** Current page number in offset mode. Null when using cursor mode. */
    page: number | null;
    /** Total page count in offset mode. Null when using cursor mode. */
    pages: number | null;
  }
  ```

- [ ] **Step 4.3 — Add `page`/`pages` to `BackendPagination` internal interface**

  Find `interface BackendPagination<T>` (~line 654):

  ```typescript
  interface BackendPagination<T> {
    items: T[];
    cursor: { next: string | null; prev?: string | null };
    total: number | null;
    page_size: number;
    page?: number | null;
    pages?: number | null;
  }
  ```

- [ ] **Step 4.4 — Update `productsApi.list` to send `page` and map response**

  Find the `list:` method in `productsApi`. Add `page` and `limit` params to the `buildQuery` call (after existing params). Also update the return mapping:

  ```typescript
  list: async (filters: ProductFilters = {}): Promise<ProductListResponse> => {
    const raw = await authedFetch<BackendPagination<ProductListItem>>(
      `/api/v1/products${buildQuery({
        // ... existing params unchanged ...
        page: filters.page,
        limit: filters.per_page ?? filters.limit,
      })}`,
    );
    return {
      items: raw.items,
      next_cursor: raw.cursor?.next ?? null,
      total: raw.total,
      page_size: raw.page_size,
      page: raw.page ?? null,
      pages: raw.pages ?? null,
    };
  },
  ```

- [ ] **Step 4.5 — Verify TypeScript compiles**

  Run: `cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | head -30`
  Expected: no errors related to the changed types.

- [ ] **Step 4.6 — Commit**

  ```
  git add mt-pricing-frontend/lib/api/endpoints/products.ts
  git commit -m "feat(catalogo): add page/pages to ProductFilters and ProductListResponse"
  ```

---

### Task 5: Replace `useProducts` hook + update its test

**Files:**
- Modify: `mt-pricing-frontend/lib/hooks/products/use-products.ts`
- Modify: `mt-pricing-frontend/tests/unit/hooks/use-products.test.ts`

- [ ] **Step 5.1 — Write failing test for new hook shape**

  Replace `mt-pricing-frontend/tests/unit/hooks/use-products.test.ts` with:

  ```typescript
  import { describe, it, expect, vi, beforeEach } from "vitest";
  import { renderHook, waitFor } from "@testing-library/react";
  import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
  import * as React from "react";

  import { useProducts } from "@/lib/hooks/products/use-products";
  import { productKeys } from "@/lib/hooks/products/query-keys";
  import { productsApi, type ProductListResponse } from "@/lib/api/endpoints/products";

  function createWrapper() {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    return {
      client,
      Wrapper: ({ children }: { children: React.ReactNode }) =>
        React.createElement(QueryClientProvider, { client }, children),
    };
  }

  const baseResponse: ProductListResponse = {
    items: [
      {
        internal_id: "00000000-0000-0000-0000-000000000001",
        sku: "VAL-001",
        family: "valves",
        family_id: null,
        subfamily: null,
        dn: "DN50",
        pn: "PN16",
        material: "steel",
        type: null,
        data_quality: "complete",
        translation_status_es: "approved",
        translation_status_ar: null,
        active: true,
        lifecycle_status: "active",
        primary_image_url: null,
        updated_at: "2026-05-06T12:00:00Z",
        series_id: null,
        material_id: null,
        display_pair_sku: null,
        division_codes: [],
        translations: { en: { name: "Valve" } },
      },
    ],
    next_cursor: null,
    total: 1,
    page_size: 25,
    page: 1,
    pages: 1,
  };

  describe("useProducts", () => {
    beforeEach(() => {
      vi.restoreAllMocks();
    });

    it("calls productsApi.list with the supplied filters and exposes data directly", async () => {
      const spy = vi.spyOn(productsApi, "list").mockResolvedValue(baseResponse);

      const { Wrapper } = createWrapper();
      const { result } = renderHook(
        () => useProducts({ family: "valves", active: true, page: 1 }),
        { wrapper: Wrapper },
      );

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ family: "valves", active: true, page: 1 }),
      );
      // Data is now direct (not nested under .pages[])
      expect(result.current.data?.items[0]?.sku).toBe("VAL-001");
      expect(result.current.data?.page).toBe(1);
      expect(result.current.data?.pages).toBe(1);
    });

    it("uses a stable queryKey derived from filters", () => {
      const key = productKeys.list({ family: "fittings", page: 2 });
      expect(key).toEqual(["products", "list", { family: "fittings", page: 2 }]);
    });
  });
  ```

- [ ] **Step 5.2 — Run test to verify it fails**

  Run: `cd mt-pricing-frontend && pnpm vitest run tests/unit/hooks/use-products.test.ts 2>&1 | tail -20`
  Expected: FAIL — `result.current.data?.items[0]?.sku` returns `undefined` because current hook returns `data.pages[0].items[0]`.

- [ ] **Step 5.3 — Replace hook implementation**

  Rewrite `mt-pricing-frontend/lib/hooks/products/use-products.ts`:

  ```typescript
  "use client";

  import { useQuery, keepPreviousData } from "@tanstack/react-query";
  import {
    productsApi,
    type ProductFilters,
    type ProductListResponse,
  } from "@/lib/api/endpoints/products";
  import { productKeys } from "./query-keys";

  /**
   * Lista paginada de productos con offset pagination.
   *
   * Pasa `page` dentro de `filters` para activar offset mode en el backend.
   * Usa `keepPreviousData` para evitar parpadeo al cambiar de página.
   */
  export function useProducts(filters: ProductFilters = {}) {
    return useQuery<ProductListResponse>({
      queryKey: productKeys.list(filters),
      queryFn: () => productsApi.list(filters),
      staleTime: 30_000,
      placeholderData: keepPreviousData,
    });
  }
  ```

- [ ] **Step 5.4 — Run test to verify it passes**

  Run: `cd mt-pricing-frontend && pnpm vitest run tests/unit/hooks/use-products.test.ts 2>&1 | tail -10`
  Expected: 2 tests PASSED.

- [ ] **Step 5.5 — Commit**

  ```
  git add mt-pricing-frontend/lib/hooks/products/use-products.ts \
          mt-pricing-frontend/tests/unit/hooks/use-products.test.ts
  git commit -m "feat(catalogo): replace useInfiniteQuery with useQuery in useProducts"
  ```

---

### Task 6: Replace `Paginator` component with page-number version

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/paginator.tsx`

- [ ] **Step 6.1 — Rewrite the Paginator component**

  Replace the full content of `mt-pricing-frontend/app/(app)/catalogo/_components/paginator.tsx`:

  ```tsx
  "use client";

  import * as React from "react";
  import { ChevronLeft, ChevronRight, RefreshCcw } from "lucide-react";
  import { MT } from "@/components/mt/tokens";

  interface PaginatorProps {
    page: number;
    pages: number | null;
    total: number | null;
    pageSize: number;
    onPageSize: (size: number) => void;
    onPage: (page: number) => void;
    isFetching?: boolean;
  }

  /**
   * Offset-based paginator: shows page X / Y, total count, prev/next arrows.
   */
  export function Paginator({
    page,
    pages,
    total,
    pageSize,
    onPageSize,
    onPage,
    isFetching = false,
  }: PaginatorProps) {
    const hasPrev = page > 1;
    const hasNext = pages !== null ? page < pages : false;

    return (
      <div
        className="flex items-center justify-between gap-3 border-t px-4 py-1.5 text-[11.5px]"
        style={{ borderColor: MT.border, background: MT.surface, color: MT.ink3 }}
      >
        <span className="mt-mono tabular-nums">
          {total !== null ? (
            <>
              <strong style={{ color: MT.ink }}>{total.toLocaleString()}</strong>{" "}
              resultados
            </>
          ) : null}
        </span>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1">
            <span style={{ color: MT.ink4 }}>por página</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              className="rounded-sm border bg-transparent px-1 py-0.5 text-[11.5px] outline-none"
              style={{ borderColor: MT.border, color: MT.ink }}
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>

          <button
            type="button"
            disabled={!hasPrev || isFetching}
            onClick={() => onPage(page - 1)}
            className="flex size-6 items-center justify-center rounded-sm hover:bg-mt-surface2
                       disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Página anterior"
          >
            <ChevronLeft className="size-3.5" />
          </button>

          <span
            className="mt-mono tabular-nums min-w-[5.5rem] text-center"
            style={{ color: MT.ink }}
          >
            {isFetching ? (
              <RefreshCcw className="inline size-3 animate-spin" />
            ) : (
              <>
                pág. <strong>{page}</strong>
                {pages !== null ? <> / {pages}</> : null}
              </>
            )}
          </span>

          <button
            type="button"
            disabled={!hasNext || isFetching}
            onClick={() => onPage(page + 1)}
            className="flex size-6 items-center justify-center rounded-sm hover:bg-mt-surface2
                       disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Página siguiente"
          >
            <ChevronRight className="size-3.5" />
          </button>
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 6.2 — Verify TypeScript compiles**

  Run: `cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | grep paginator`
  Expected: no errors.

- [ ] **Step 6.3 — Commit**

  ```
  git add mt-pricing-frontend/app/(app)/catalogo/_components/paginator.tsx
  git commit -m "feat(catalogo): replace load-more Paginator with page-number component"
  ```

---

### Task 7: Debounce facets + wire `page.tsx`

**Files:**
- Modify: `mt-pricing-frontend/lib/hooks/products/use-facets.ts`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 7.1 — Add debounce to `useFacets`**

  Replace the full content of `mt-pricing-frontend/lib/hooks/products/use-facets.ts`:

  ```typescript
  "use client";

  import { useQuery } from "@tanstack/react-query";
  import { facetsApi, type FacetsFilters, type FacetsResponse } from "@/lib/api/endpoints/facets";
  import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

  export type { FacetsFilters, FacetsResponse } from "@/lib/api/endpoints/facets";

  const DEFAULT_STALE_MS = 30_000;
  const FACET_DEBOUNCE_MS = 400;

  export function useFacets(filters: FacetsFilters = {}) {
    const debouncedFilters = useDebouncedValue(filters, FACET_DEBOUNCE_MS);
    return useQuery<FacetsResponse>({
      queryKey: ["products", "facets", debouncedFilters],
      queryFn: () => facetsApi.get(debouncedFilters),
      staleTime: DEFAULT_STALE_MS,
      gcTime: 5 * 60_000,
    });
  }
  ```

- [ ] **Step 7.2 — Add `page` URL state to `page.tsx`**

  In `mt-pricing-frontend/app/(app)/catalogo/page.tsx`, find the nuqs import and add `parseAsInteger`:

  ```typescript
  import {
    parseAsString,
    parseAsStringEnum,
    parseAsBoolean,
    parseAsInteger,   // ADD
    useQueryState,
  } from "nuqs";
  ```

  Then, near the other `useQueryState` calls (around line 130), add the page state right after `pageLimit`:

  ```typescript
  const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
  ```

- [ ] **Step 7.3 — Add page-reset effect when filters change**

  After all the filter `useQueryState` declarations and before the `filters` useMemo, add:

  ```typescript
  // Reset to page 1 whenever any filter (not page itself) changes.
  const _filterHash = JSON.stringify({
    debouncedSearch, family, subfamily, typeFilter, quality,
    translationStatus, active, dn, pn, material, division,
    seriesId, materialId, tierCode, pageLimit,
  });
  const _prevFilterHash = React.useRef(_filterHash);
  React.useEffect(() => {
    if (_prevFilterHash.current !== _filterHash) {
      _prevFilterHash.current = _filterHash;
      void setPage(1);
    }
  }, [_filterHash, setPage]);
  ```

- [ ] **Step 7.4 — Add `page` and `per_page` to the `filters` useMemo**

  Find the `filters` useMemo (around line 198). Add `page` and `per_page` inside the returned object, and add `page` to the dependency array:

  ```typescript
  const filters: ProductFilters = React.useMemo(
    () => ({
      // ... existing fields ...
      limit: pageLimit,    // keep existing limit
      per_page: pageLimit, // ADD: explicit offset-mode per_page
      page,                // ADD: current page
    }),
    [
      debouncedSearch,
      // ... existing deps ...
      pageLimit,
      page,  // ADD
    ],
  );
  ```

- [ ] **Step 7.5 — Replace `useProducts` destructuring**

  Find the current destructuring (around line 229):

  ```typescript
  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useProducts(filters);
  ```

  Replace with:

  ```typescript
  const {
    data,
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useProducts(filters);
  ```

- [ ] **Step 7.6 — Update `items` and `total` derivations**

  Find:

  ```typescript
  const items: ProductListItem[] = React.useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );
  const total = data?.pages[0]?.total ?? null;
  ```

  Replace with:

  ```typescript
  const items: ProductListItem[] = data?.items ?? [];
  const total = data?.total ?? null;
  ```

- [ ] **Step 7.7 — Update `Paginator` call**

  Find the `<Paginator .../>` call (around line 1083):

  ```tsx
  <Paginator
    loaded={items.length}
    total={totalFiltered}
    pageSize={pageLimit}
    onPageSize={setPageLimit}
    hasNext={Boolean(hasNextPage)}
    onNext={() => void fetchNextPage()}
    isFetching={isFetchingNextPage}
  />
  ```

  Replace with:

  ```tsx
  <Paginator
    page={page}
    pages={data?.pages ?? null}
    total={totalFiltered}
    pageSize={pageLimit}
    onPageSize={(size) => { setPageLimit(size); void setPage(1); }}
    onPage={(p) => void setPage(p)}
    isFetching={isFetching}
  />
  ```

- [ ] **Step 7.8 — Check for remaining references to old hook output**

  Search for `fetchNextPage`, `hasNextPage`, `isFetchingNextPage`, `data?.pages` in `page.tsx`:

  Run: `grep -n "fetchNextPage\|hasNextPage\|isFetchingNextPage\|data?.pages" mt-pricing-frontend/app/\(app\)/catalogo/page.tsx`
  Expected: no output (all replaced).

- [ ] **Step 7.9 — TypeScript compile check**

  Run: `cd mt-pricing-frontend && pnpm tsc --noEmit 2>&1 | head -30`
  Expected: no errors.

- [ ] **Step 7.10 — Run full frontend test suite**

  Run: `cd mt-pricing-frontend && pnpm vitest run 2>&1 | tail -20`
  Expected: all tests pass. The `use-products.test.ts` now tests the new shape.

- [ ] **Step 7.11 — Restart frontend and verify manually**

  Run: `docker restart mt-frontend`

  Verify at `http://localhost:${CADDY_HTTP_PORT:-8081}/catalogo`:
  - [ ] Page loads showing "X resultados" and "pág. 1 / Y"
  - [ ] Clicking `→` loads page 2; URL has `?page=2`
  - [ ] Changing a filter (e.g., family) resets to `?page=1`
  - [ ] Changing page size (25→50) reloads with page 1
  - [ ] Facet sidebar counts are visible and debounced (no flickering on keystroke)
  - [ ] Browser back button returns to previous page

- [ ] **Step 7.12 — Commit**

  ```
  git add mt-pricing-frontend/lib/hooks/products/use-facets.ts \
          mt-pricing-frontend/app/(app)/catalogo/page.tsx
  git commit -m "feat(catalogo): wire offset pagination in page.tsx + debounce facets"
  ```

---

## Self-Review

### Spec coverage checklist

| Requirement | Task |
|---|---|
| Filters apply to full dataset (not just visible) | Already correct — filters go to backend. Task 7 makes it visible via `total` count |
| Page numbers visible (pág. X / Y) | Task 6 (Paginator) |
| Total result count visible | Task 1 (schema forces `total` when `page` set), Task 7 (display) |
| Filters reset page to 1 | Task 7 step 7.3 |
| Page preserved in URL (shareable) | Task 7 step 7.2 (`useQueryState`) |
| Facet debounce (no keystroke flicker) | Task 7 step 7.1 |
| Backward compat — cursor mode unchanged | Task 2 (offset branch only active when `page` provided) |
| No N+1 queries | Already batch queries — not changed (existing 3 queries are batches, not per-row) |
| OpenAPI spec in sync | Task 3 step 3.5 |
| Existing cursor tests still pass | Task 2 step 2.7 |

### Placeholder scan

No TBD, TODO, or "similar to Task N" patterns in this plan.

### Type consistency

- `ProductListResponse.page: number | null` defined in Task 4, used in Task 5 (test mock) and Task 7 (paginator wiring) ✓
- `PaginatorProps.page: number` defined in Task 6, called with `page={page}` (number) in Task 7 ✓
- `PaginatorProps.onPage: (page: number) => void` defined in Task 6, called with `void setPage(p)` in Task 7 ✓
- `Pagination.page: int | None` defined in Task 1, returned in Task 3, mapped in Task 4 ✓
