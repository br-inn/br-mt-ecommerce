# Catalog Modeling — Execution Report

**Fecha**: 2026-05-08 · **Branch**: `main` · **Commits**: 21 (`1a6d2e8..HEAD`) · **Estado**: ready for review

> Implementación end-to-end de los 10 waves del [master plan](../planning-artifacts/master-plan-catalog-modeling-2026-05-08.md), las 8 decisiones binarias del [asset management spec](../planning-artifacts/arch-asset-management-2026-05-08.md), y la integración de UI con [facets mockup](../planning-artifacts/ux-mockup-catalogo-facets-2026-05-08.md).

---

## 1. Resumen ejecutivo

| Métrica | Valor |
|---|---:|
| Olas implementadas | **10/10** |
| Commits sobre `1a6d2e8` | **21** |
| Archivos modificados/creados | **104** |
| Líneas insertadas | **+17,603** |
| Líneas eliminadas | **-212** |
| Tests cumulativos | **276+** (waves) — 717+ full backend |
| Migrations Alembic aplicadas | **8** |
| Productos preservados | **5,085** intactos |
| BD revision actual | `20260508_041` ✅ |
| TS typecheck frontend | clean ✅ |

---

## 2. Cronología de commits

```
9a23a7b feat(wave10-fe+perf): facet sidebar + paginator + parallel facets compute
0f6b326 feat(wave10): /products/facets endpoint + non-destructive refinements + DN/PN fix
8b28433 feat(wave8): SEO + editorial fields per locale on product_translations
3faa69e feat(wave6): structured tech tables (materials_matrix, dimensions_by_dn, P/T)
b943699 feat(wave5): parent/variant resolver with depth-1 + cycle validation
1cda3c4 feat(wave3): multi-component model — product_materials + product_connections
ca8d38c feat(wave2): lifecycle status + 18 technical scalars + parent/child columns
fd9b36f chore(audit): pre-upgrade SQL dump for waves 1+4+7 migration session
c305095 fix(wave7): use postgresql.ENUM + DO block guard for compatibility_kind
0e107dd feat(catalog): denormalized translation_status_es/_ar + primary_image_url in list
f92bc48 test(wave1): force placeholder Supabase config via monkeypatch.setattr
a343c3a chore(alembic): merge migration unifying waves 1+4+7 heads
8a9eb42 merge: Wave 9 — specs JSON Schema validation per family
1ae0029 merge: Wave 7 — spare parts compatibility (M:N)
204e1b4 merge: Wave 4 — vocabularios M:N (certifications + applications + junctions)
8739e77 merge: Wave 1 — asset unification (product_images → product_assets)
89cb9db feat(wave9): specs JSON Schema validation per family
b438c1f feat(wave7): spare parts compatibility (M:N)
d827229 feat(wave4): vocabularios M:N — certifications + applications + junctions
64be1df docs(wave1): add implementation report for Wave 1 asset unification
09ffe13 feat(wave1): asset unification — product_images → product_assets (10 kinds)
```

---

## 3. Mapeo wave → entregables

| Wave | Backend | Frontend | Tests |
|:---:|---|---|---:|
| **W1** | Migration 030 (rename product_images→product_assets, +10 cols, +blurhash worker), AssetService, 7 endpoints | Stub | 65 |
| **W2** | Migration 037 (lifecycle_status enum, parent_sku, 18 technical scalars, tags array) | – | 23 |
| **W3** | Migration 038 (product_materials + product_connections, trigger denorm, 9 endpoints) | – | 30 |
| **W4** | Migration 033 (certifications + applications + junctions, seed 12+8) | – | 60 |
| **W5** | ParentResolver service + 2 endpoints (cycle/depth validation + fallback resolver) | – | 14 |
| **W6** | Migration 039 (product_tech_tables, per-kind validators, 3 endpoints) | – | 14 |
| **W7** | Migration 035 (product_compatibility, bidirectional sync, 5 endpoints) | – | 36 |
| **W8** | Migration 040 (6 SEO/editorial cols on product_translations) | – | 7 |
| **W9** | Specs JSON Schema (valve_ball, filter, _default) + SpecsValidator + GET endpoint | Stub | 36 |
| **W10** | Migration 041 (6 facet indexes), build_product_clauses, compute_facets parallel, GET /products/facets | FacetSidebar + ActiveFiltersBar + SavedViewsBar + Paginator integrated en /catalogo | 21 |

---

## 4. Cambios estructurales en el modelo

### Tablas nuevas

- `product_assets` (renombrado de `product_images`, ahora 10 kinds)
- `product_materials` (1:N por componente)
- `product_connections` (1:N hasta 8 puertos)
- `certifications` (catálogo cerrado, seed 12)
- `applications` (catálogo cerrado, seed 8)
- `product_certifications` (M:N junction)
- `product_applications` (M:N junction)
- `product_compatibility` (M:N spare parts/replaces)
- `product_tech_tables` (1:N matrix-style data)

### Columnas añadidas a `products` (Wave 2)

`lifecycle_status`, `revision`, `series`, `parent_sku`, `is_parent`, `is_variant`, `dn_real`, `size`, `temp_min_c`, `temp_max_c`, `pressure_max_bar`, `manufacturing_method`, `actuator`, `kv`, `kv2`, `torque_nm`, `iso5211_interface`, `tags[]`, `video_url`, `external_url` (20 columnas)

### Columnas añadidas a `product_translations` (Wave 8)

`meta_title`, `meta_description`, `applications_text`, `technical_limits`, `notes`, `marketing_features` (6 columnas)

### Enums nuevos

`asset_kind`, `asset_status`, `compatibility_kind`, `lifecycle_status`, `component_kind`, `connection_type`, `tech_table_kind`, `tech_table_source` (8 enums)

### Triggers

`trg_product_materials_denorm` — sincroniza `products.material` con `product_materials.body[position=0]`.

---

## 5. Endpoints API añadidos

| Endpoint | Método | Wave | Permission |
|---|:---:|:---:|---|
| `/products/{sku}/assets` | GET | W1 | products:read |
| `/products/{sku}/assets/upload-url` | POST | W1 | products:write |
| `/products/{sku}/assets/{id}/confirm` | POST | W1 | products:write |
| `/products/{sku}/assets/{id}/primary` | PATCH | W1 | products:write |
| `/products/{sku}/assets/{id}/archive` | PATCH | W1 | products:write |
| `/products/{sku}/assets/{id}/restore` | PATCH | W1 | products:write |
| `/products/{sku}/assets/{id}` | DELETE | W1 | products:delete |
| `/products/{sku}/materials` | GET/POST/PUT | W3 | read/write |
| `/products/{sku}/materials/{component}/{position}` | DELETE | W3 | products:write |
| `/products/{sku}/connections` | GET/POST/PUT | W3 | read/write |
| `/products/{sku}/connections/{position}` | DELETE | W3 | products:write |
| `/certifications`, `/applications` | GET | W4 | products:read |
| `/admin/certifications/*`, `/admin/applications/*` | * | W4 | admin:vocabularies |
| `/products/{sku}/certifications`, `/products/{sku}/applications` | * | W4 | products:* |
| `/products/{sku}/resolved` | GET | W5 | products:read |
| `/products/{sku}/parent` | POST | W5 | products:write |
| `/products/{sku}/tech-tables` | GET | W6 | products:read |
| `/products/{sku}/tech-tables/{kind}` | PUT/DELETE | W6 | products:write |
| `/products/{sku}/compatibility[/inverse]` | GET | W7 | products:read |
| `/products/{sku}/compatibility[/{w}/{kind}]` | POST/DELETE/PUT | W7 | products:write |
| `/products/specs/schema` | GET | W9 | products:read |
| `/products/facets` | GET | W10 | products:read |

**Total**: ~30 endpoints nuevos. Backward compat: `/products/{sku}/images/*` proxied como deprecated.

---

## 6. Bugs encontrados y corregidos durante la ejecución

1. **`sa.Enum` ignora `create_type=False`** (W7 migration 035) — solo `postgresql.ENUM` (dialect) lo respeta. Solucionado con `postgresql.ENUM` + DO-block guard idempotente.
2. **`additionalProperties=false` no devolvía nombre de propiedad** (W9 SpecsValidator) — añadida helper `_extract_additional_property` con regex.
3. **AsyncSession concurrency-unsafe** (W10 compute_facets) — pivotado a `engine.connect()` per-dimension.
4. **DN/PN prefix mismatch** (W10) — validators ahora aceptan `15` o `DN15` y normalizan a numérico.
5. **Test isolation env vars** (W1 asset_service) — monkeypatch.setattr en settings.

---

## 7. Riesgos y deuda técnica

| Tema | Estado | Plan |
|---|---|---|
| Perf facets cloud (~1.86s p50) | Aceptado | RTT pooler Supabase. En Hetzner co-located bajará a <150ms. |
| Frontend sidebar ✅ | DONE | Mejoras: drag-handle reorder, search-within-facet en family también. |
| GroupBy (mockup §3) | Diferido | Sprint follow-up; backend ready, FE 1-2 días. |
| Bulk actions toolbar | Diferido | Mockup §2 spec; FE 1 día. |
| AVIF variants | Diferido | Sprint 2 (mockup §3.1) |
| MV `mv_product_facets` | No urgente | Crear cuando ≥50K rows o p95 >300ms |
| Saved views por user (BD) | Sprint 2 | Hoy son system_views hardcoded |
| 9 fallas pre-existentes en `importer_datasheets/test_dual_extractor.py` | No-bloqueante | Test isolation issue Sprint 4/5; no causadas por estos cambios |

---

## 8. Estado de la BD productiva

- 5,085 productos preservados intactos.
- Backfill `lifecycle_status`: 5,085 = `active`.
- 12 certifications + 8 applications seedeadas.
- 0 product_assets / product_materials / product_connections / product_tech_tables / product_compatibility (entries por venir vía importer).

---

## 9. Verificación

```bash
# Backend tests
docker exec mt-backend pytest tests/unit -q --no-cov

# Frontend typecheck
docker exec mt-frontend pnpm tsc --noEmit

# DB head
docker exec mt-backend alembic current
# → 20260508_041 (head)

# Live endpoints (need auth bearer)
curl -sk http://localhost:8081/api/v1/products/facets        # 401 sin token (correcto)
curl -sk http://localhost:8081/api/v1/products?limit=3       # 401 idem
```

---

## 10. Próximos pasos sugeridos

1. **Code review**: sin remote configurado → recomiendo correr **`/ultrareview`** (multi-agent cloud review). El bundling no requiere remote, según el harness.
2. **Configurar git remote** + push de `main` con los 21 commits para audit trail externo.
3. **Sprint 11** (post-review): GroupBy + bulk actions UI + saved views BD.
4. **Importer**: cargar fotos de daterium/mtspain.net + datasheets PDF → poblar `product_assets` y `product_tech_tables`.
5. **Bench facets en Hetzner staging**: validar p95 <150ms con BD co-located.
