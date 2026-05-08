# Wave 7 — Spare Parts Compatibility (M:N) — Implementation Report

**Date:** 2026-05-08
**Worktree:** `.claude/worktrees/agent-a198ee7e0f7765ec6`
**Branch:** main (worktree)

---

## Files Created / Modified

### New Files

| Path | Description |
|------|-------------|
| `mt-pricing-backend/alembic/versions/20260508_035_compatibility.py` | Migration — enum + table |
| `mt-pricing-backend/app/db/models/compatibility.py` | ORM model `ProductCompatibility` |
| `mt-pricing-backend/app/schemas/compatibility.py` | Pydantic V2 schemas |
| `mt-pricing-backend/app/repositories/compatibility.py` | `CompatibilityRepo` |
| `mt-pricing-backend/app/services/compatibility/__init__.py` | Service package exports |
| `mt-pricing-backend/app/services/compatibility/compatibility_service.py` | `CompatibilityService` |
| `mt-pricing-backend/tests/unit/services/compatibility/__init__.py` | Test pkg init |
| `mt-pricing-backend/tests/unit/services/compatibility/test_compatibility_service.py` | 14 unit tests |
| `mt-pricing-backend/tests/unit/schemas/test_compatibility.py` | 9 schema tests |
| `mt-pricing-backend/tests/unit/api/test_compatibility_api.py` | 13 API tests |

### Modified Files

| Path | Change |
|------|--------|
| `mt-pricing-backend/app/db/models/__init__.py` | Added `ProductCompatibility` import + `__all__` entry |
| `mt-pricing-backend/app/db/models/product.py` | Added `compatibilities_outgoing` + `compatibilities_incoming` relationships |
| `mt-pricing-backend/app/api/routes/products.py` | Added 5 compatibility endpoints + DI factory + error helper |

---

## Migration ID

```
revision:      20260508_035
down_revision: 20260507_029
```

**DDL summary:**
- Enum `compatibility_kind`: `spare_part | accessory | replaces | replaced_by | compatible_with`
- Table `product_compatibility` with UUID PK, two FK→products(sku) CASCADE, CHECK no-self-loop, UNIQUE(product_sku, compatible_with_sku, kind), 3 indexes.

---

## Test Output

```
36 passed in 6.91s
```

- `tests/unit/services/compatibility/test_compatibility_service.py` — 14 tests
- `tests/unit/schemas/test_compatibility.py` — 9 tests
- `tests/unit/api/test_compatibility_api.py` — 13 tests

---

## Bidirectional Sync Design

The relation is stored **unidirectionally**. The only pair with automatic sync is `replaces`/`replaced_by`:

- `add_link(A, B, "replaces")` → inserts `(A→replaces→B)` + `(B→replaced_by→A)` if missing.
- `remove_link(A, B, "replaces")` → deletes `(A→replaces→B)` + `(B→replaced_by→A)`.
- Same logic applies when the user starts from the `replaced_by` side.
- `spare_part`, `accessory`, `compatible_with` are strictly unidirectional; inverse view via `GET /compatibility/inverse`.

---

## Endpoints

```
GET    /products/{sku}/compatibility            (products:read)
GET    /products/{sku}/compatibility/inverse    (products:read)
POST   /products/{sku}/compatibility            (products:write)  → 201
DELETE /products/{sku}/compatibility/{csku}/{kind}  (products:write)  → 204
PUT    /products/{sku}/compatibility            (products:write)  → 200 bulk replace
```

---

## Deviations from Spec

- **ORM enum type:** Used `Text` column instead of SQLAlchemy `Enum` mapped type in the ORM model to avoid migration drift. The CHECK constraint is enforced by the DDL enum at the DB level; the Python enum is in the schema layer (`CompatibilityKind`). This is consistent with the pattern used for `data_quality` in `product.py`.
- **`UuidPkMixin`** used in `ProductCompatibility` (provides `id` UUID PK). No `TimestampMixin` since the table only has `created_at` (no `updated_at` by spec).

---

## Follow-ups / Known Gaps

1. **Integration test** with real Postgres testcontainer not yet created (out of scope for unit wave). Recommended for Sprint 8 regression suite.
2. **Admin UI** for managing compatibility links is deferred to the frontend Wave 7 stories.
3. **Bulk import from Excel** (Listado campos — sheet Recambios) is a separate import story.
4. **GraphRAG CDC** for compatibility events not wired (add `CdcEvent` emission in `CompatibilityService.add_link/remove_link` when S8 graphrag integration is done).
5. The `GET /compatibility/inverse` response does not populate `compatible_product` (the product displayed is the origin, not the destination); this is by design but UI should be aware.
