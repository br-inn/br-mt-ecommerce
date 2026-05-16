# US-SCR-03-02: Test Suite Completo Módulo Competitor Brands

**Status:** review
**Fecha:** 2026-05-16
**Branch:** main

## Tests creados / ampliados

### Nuevos: `tests/unit/api/test_competitor_brands_api.py`

Tests unitarios del router `app.api.routes.competitor_brands` (sin DB real):

| Test | AC |
|------|-----|
| `test_create_brand_returns_201` | AC-1 |
| `test_create_brand_duplicate_name_returns_409` | AC-1 |
| `test_create_brand_missing_name_returns_422` | AC-1 |
| `test_create_brand_empty_name_returns_422` | AC-1 |
| `test_list_brands_returns_all` | AC-1 |
| `test_list_brands_active_only_filter` | AC-1 |
| `test_list_brands_empty_returns_empty_list` | AC-1 |
| `test_patch_brand_partial_update` | AC-1 |
| `test_patch_brand_not_found_returns_404` | AC-1 |
| `test_run_with_brand_ids_queues_specific_brands` | AC-2 |
| `test_run_without_brand_ids_uses_all_active` | AC-2 |
| `test_run_nothing_to_do_when_no_active_brands` | AC-2 |

**Cobertura route:** 89% (supera AC-3 ≥80%)

### Ampliados: `tests/workers/test_scrape_brand_task.py`

Tests del query builder y tasks de scraping:

| Test | AC |
|------|-----|
| `test_build_brand_query_uses_name_when_no_search_term` | AC-6 |
| `test_build_brand_query_prefers_amazon_search_term` | AC-6 |
| `test_build_brand_query_passes_category_node` | AC-6 |
| `test_build_brand_query_custom_dept` | AC-6 |
| `test_build_brand_query_returns_query_dataclass` | AC-6 |
| `test_serp_url_contains_dept_and_category_node` | AC-6 |
| `test_serp_url_without_category_node_omits_rh_param` | AC-6 |
| `test_scrape_brand_task_run_async_calls_fetcher_with_correct_query` | AC-4 |
| `test_scrape_brands_batch_task_dispatches_one_task_per_brand` | AC-5 |
| `test_scrape_brands_batch_task_returns_empty_when_no_brands` | AC-5 |
| `test_scrape_brands_batch_task_dispatches_with_force_flag` | AC-5 |
| `test_scrape_brands_batch_task_loads_active_brands_when_none` | AC-5 |

## Resultado ejecución

```
24 passed in 52.19s
```

## Tests de integración existentes (no modificados)

`tests/api/test_competitor_brands_crud.py` ya cubre:
- POST 201, 409 (duplicate name)
- GET lista
- PATCH update parcial
- GET 404

Estos tests requieren testcontainer (Postgres efímero) y están marcados `@pytest.mark.integration`.
