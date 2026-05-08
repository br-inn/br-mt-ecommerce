# Wave 4 Vocabularios — Implementation Report

**Date:** 2026-05-08  
**Worktree:** `c:\BR-Github\br-mt\br-mt-ecommerce\.claude\worktrees\agent-afffd404dddd10951`

---

## Files Created

| File | Description |
|------|-------------|
| `mt-pricing-backend/alembic/versions/20260508_033_vocabularios.py` | Alembic migration |
| `mt-pricing-backend/app/db/models/vocabularies.py` | ORM models |
| `mt-pricing-backend/app/schemas/vocabularies.py` | Pydantic v2 schemas |
| `mt-pricing-backend/app/repositories/vocabularies.py` | Repositories |
| `mt-pricing-backend/app/services/vocabularies/__init__.py` | Service package |
| `mt-pricing-backend/app/services/vocabularies/vocabulary_service.py` | Services |
| `mt-pricing-backend/app/api/routes/vocabularies.py` | API routes |
| `mt-pricing-backend/tests/unit/services/vocabularies/__init__.py` | Test package |
| `mt-pricing-backend/tests/unit/services/vocabularies/test_vocabulary_service.py` | 25 service unit tests |
| `mt-pricing-backend/tests/unit/schemas/test_vocabularies.py` | 12 schema unit tests |
| `mt-pricing-backend/tests/unit/api/test_vocabularies_api.py` | 12 catalog API unit tests |
| `mt-pricing-backend/tests/unit/api/test_products_vocabularies_api.py` | 11 product vocab API tests |

## Files Modified

| File | Change |
|------|--------|
| `mt-pricing-backend/app/db/models/__init__.py` | Added Certification, Application, ProductCertification, ProductApplication imports + `__all__` |
| `mt-pricing-backend/app/db/models/product.py` | Added `product_certifications` + `product_applications` relationships (selectin lazy) |
| `mt-pricing-backend/app/api/routes/__init__.py` | Wired `vocabularies.router`, `admin_vocab_router`, `products_vocab_router` |

---

## Migration

**Revision ID:** `20260508_033`  
**down_revision:** `20260507_029`  
**Branch:** parallel to Wave 1 (main session will create merge migration)

Tables created:
- `certifications` — 12 rows seeded (CE, WRAS, NSF, KIWA, ACS, ATEX, FM, UL, CSA, ROHS, REACH, ISO9001)
- `applications` — 8 rows seeded (water, gas, oil, food, hvac, fire-fighting, irrigation, industrial)
- `product_certifications` — junction with PDF asset, dates, notes
- `product_applications` — junction with is_primary, position

Indexes: `idx_product_certifications_cert`, `idx_product_applications_app`, `idx_product_applications_primary` (partial)

Permission seeded: `admin:vocabularies` assigned to `ti_integracion` + `admin` roles.

---

## Endpoints

### Public (products:read)
- `GET /api/v1/certifications` — list active certifications
- `GET /api/v1/applications` — list active applications

### Admin (admin:vocabularies)
- `GET/POST /api/v1/admin/certifications`
- `GET/PATCH/DELETE /api/v1/admin/certifications/{cert_id}`
- `GET/POST /api/v1/admin/applications`
- `GET/PATCH/DELETE /api/v1/admin/applications/{app_id}`

### Product sub-resources (products:read / products:write)
- `GET /api/v1/products/{sku}/certifications`
- `POST /api/v1/products/{sku}/certifications` — add one
- `PUT /api/v1/products/{sku}/certifications` — replace all
- `DELETE /api/v1/products/{sku}/certifications/{cert_id}`
- Same shape for `/applications`

---

## Test Output

```
60 passed in 5.83s
```

Command used: `docker exec mt-backend pytest /tmp/tests_vocab/... -q --no-cov`

Note: Tests were run from `/tmp` staging area because Docker bind mount `tests/` is `:ro`. The test files are at the correct paths in the worktree and will be picked up normally by the CI mount.

---

## Deviations

1. **Product model relationships**: Used lazy string forward refs (`"ProductCertification"`, `"ProductApplication"`) instead of imported types to avoid circular import. Works correctly — SQLAlchemy resolves via mapper registry.

2. **Tags (text[])**: Per spec, Wave 2 adds the `text[]` column. Endpoints for tags were deferred (tags column not yet in schema at Wave 4 time). No deviation from spec — spec says "Wave 2 covers the column; here we just expose endpoints" but since the column doesn't exist yet, no tag endpoints were wired.

3. **Product detail eager loading**: The `product_certifications`/`product_applications` relationships are `lazy="selectin"` on Product, meaning they auto-load when product is fetched. This may add latency to product detail endpoints until vocabulary data is populated.

---

## Follow-ups for Main Session

1. **Merge migration**: Create an alembic merge migration joining `20260508_033` and the Wave 1 head.
2. **ProductDetail schema**: Optionally surface `certifications` and `applications` in `ProductDetail` response schema (schemas/products.py).
3. **Tags endpoints**: Once Wave 2 adds `tags text[]` column to products, expose `GET/PUT /products/{sku}/tags`.
4. **permissions_snapshot refresh**: After seeding `admin:vocabularies`, admins may need role re-assignment to pick up the new permission in their `permissions_snapshot` JSONB.
