# Resumen de Generación de Tests Automatizados

**Fecha:** 2026-05-08
**Modo:** Auto-discover sobre `mt-pricing-backend/`
**Foco:** Cubrir gaps en el módulo GraphRAG (cambios activos sin commitear)
**Framework:** pytest + pytest-asyncio + httpx + testcontainers (ya instalado)

## Mapeo de Cobertura GraphRAG (antes / después)

| Módulo | Antes | Después | Notas |
|---|---|---|---|
| `app/api/routes/graphrag.py` | tests unit existentes ✅ | sin cambio | `tests/unit/api/test_graphrag_api.py` (3 tests) ya cubre `/health` + `/replay` |
| `app/services/graphrag/cdc_dispatcher.py` | tests unit ✅ | sin cambio | `tests/unit/services/graphrag/test_cdc_dispatcher.py` |
| `app/services/graphrag/adapters/neo4j_real.py` | tests integration ✅ | sin cambio | `tests/integration/services/graphrag/test_neo4j_real.py` (10 tests, contract + uniqueness) |
| `app/services/graphrag/adapters/neo4j_stub.py` | tests unit ✅ | sin cambio | `tests/unit/services/graphrag/adapters/test_neo4j_stub.py` |
| `app/services/graphrag/adapters/factory.py` | ❌ **0%** | ✅ **nuevo** | 7 tests unit cubren stub/neo4j/override + shutdown |
| `app/workers/tasks/graphrag.py` | ❌ **0%** | ✅ **70%** | 4 tests unit cubren task + propagación de errores |

## Tests Generados

### Unit Tests

#### [tests/unit/services/graphrag/adapters/test_factory.py](mt-pricing-backend/tests/unit/services/graphrag/adapters/test_factory.py) (7 tests)

- `test_set_default_graph_store_override_takes_priority` — el override (fixture) gana sobre settings
- `test_set_default_graph_store_none_resets_override` — pasar `None` revierte al backend de settings
- `test_get_default_returns_stub_when_backend_stub` — `GRAPHRAG_BACKEND='stub'` → `Neo4jStubGraphStore`
- `test_get_default_initializes_neo4j_driver_with_settings` — `GRAPHRAG_BACKEND='neo4j'` instancia driver con `NEO4J_URI` y cachea el adapter
- `test_shutdown_closes_driver_and_allows_reinit` — `shutdown()` cierra driver y permite re-init
- `test_shutdown_swallows_close_errors` — error en `driver.close()` no propaga (resilient lifespan)
- `test_shutdown_noop_when_driver_not_initialized` — `shutdown()` sin init previo es no-op

#### [tests/unit/workers/test_graphrag_task.py](mt-pricing-backend/tests/unit/workers/test_graphrag_task.py) (4 tests)

- `test_process_cdc_batch_returns_summary_without_outcomes` — task filtra `outcomes` del payload (anti-log-flood)
- `test_process_cdc_batch_default_batch_size` — default `batch_size=100`
- `test_process_cdc_batch_propagates_failures` — excepción en `_run_dispatch` se propaga (Celery retry/dead-letter)
- `test_process_cdc_batch_accepts_zero_results_dataset` — empty dataset retorna conteos en cero

## Resultado de Ejecución

```
docker exec mt-backend pytest tests/unit/workers/test_graphrag_task.py \
                               tests/unit/services/graphrag/adapters/test_factory.py \
                               -x --tb=short

============================= 11 passed in 25.52s ==============================
```

Cobertura específica del módulo modificado:

```
app/workers/tasks/graphrag.py                                   27      8      0      0    70%
```

## Gaps Restantes Conocidos (fuera del scope de esta sesión)

Rutas API sin tests integration dedicados (las funciones internas pueden tener cobertura unit):

- `pricing.py`, `pricing_admin.py`, `pricing_engine.py`, `admin_calibrator.py`
- `costs.py`, `currencies.py`, `fx_rates.py`
- `imports_materials.py`, `imports_datasheets.py`
- `translations_workflow.py`, `audit.py`, `audit_query.py`
- `users.py`, `roles.py`, `jobs.py`, `matches.py`, `channels_mirror.py`
- `admin_flags.py`

> **Recomendación**: priorizar los routes que aún no estén bajo feature flag completo y los que tocaron en S5/S6.

## Próximos Pasos Sugeridos

1. **CI**: integrar `tests/unit/**` y `tests/integration/services/graphrag/**` en el pipeline (los integration ya tienen `@pytest.mark.integration` para selección).
2. **E2E del task Celery**: agregar test integration que enqueue rows reales en `cdc_events`, ejecute la task con `task_always_eager`, y verifique que los nodos llegan al stub/neo4j (cierre del loop end-to-end).
3. **API integration**: si se quiere una capa adicional sobre el unit existente, agregar `tests/integration/test_graphrag_api.py` que use Postgres efímero y verifique permisos `graphrag:admin`.
