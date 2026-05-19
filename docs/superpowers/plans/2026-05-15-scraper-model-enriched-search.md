# Scraper Model-Enriched Search — Verification & Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer fluir la información del modelo (`product_models.connection_type`, `thread_standard`, `code` + certificados) a través del pipeline de matching para generar queries de búsqueda más precisos y encontrar mejores candidatos en Amazon/Noon UAE.

**Architecture:** El pipeline tiene 4 capas en secuencia: `ProductRepository.get_by_sku()` → `_product_to_dict()` → `QueryBuilder` / `llm_query_generator`. Cada capa necesita un cambio puntual para propagar la info del modelo. El caché de queries LLM en `product_search_queries` debe invalidarse para SKUs con `model_id` poblado (de lo contrario siguen usando queries generados sin contexto del modelo).

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + `selectinload` + pytest (unit, no DB) + Docker local

---

## Mapa de archivos

| Archivo | Cambio |
|---|---|
| `app/repositories/product.py` | Agregar `get_by_sku_for_matching()` con `selectinload(Product.model)` |
| `app/services/matching/match_service.py` | Usar `get_by_sku_for_matching()`; enriquecer `_product_to_dict()` con campos del modelo |
| `app/services/matching/query_builder.py` | Usar `model_connection_type` y `model_thread_standard` en queries |
| `app/services/matching/llm_query_generator.py` | Agregar campos del modelo al `_build_product_summary()` |
| `tests/unit/services/matching/test_query_builder.py` | Tests para queries enriquecidos con datos del modelo |
| `tests/unit/services/matching/test_match_service.py` | Tests para `_product_to_dict()` con `.model` cargado |

---

## Task 1: Agregar `get_by_sku_for_matching()` al repositorio

**Files:**
- Modify: `app/repositories/product.py`
- Test: `tests/unit/services/matching/test_match_service.py`

- [ ] **Step 1.1: Escribir el test que falla**

Leer líneas 1-30 de `tests/unit/services/matching/test_match_service.py` para ver el patrón de mocks existente. Luego agregar al final del archivo:

```python
def test_product_repo_get_by_sku_for_matching_returns_product_with_model() -> None:
    """get_by_sku_for_matching devuelve un producto con .model accesible sin lazy load."""
    from unittest.mock import AsyncMock, MagicMock
    from app.db.models.product_models import ProductModel

    mock_model = MagicMock(spec=ProductModel)
    mock_model.code = "4295"
    mock_model.connection_type = "thread_bsp"
    mock_model.thread_standard = "BSP"

    mock_product = MagicMock()
    mock_product.sku = "MTBR4001050"
    mock_product.model = mock_model

    # Verificar que _product_to_dict accede al modelo sin lanzar LazyLoadError
    from app.services.matching.match_service import MatchService
    result = MatchService._product_to_dict(mock_product)
    assert result["model_code"] == "4295"
    assert result["model_connection_type"] == "thread_bsp"
    assert result["model_thread_standard"] == "BSP"
```

- [ ] **Step 1.2: Ejecutar el test para verificar que falla**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_match_service.py::test_product_repo_get_by_sku_for_matching_returns_product_with_model -v
```

Resultado esperado: `FAILED` — `KeyError: 'model_code'` (el campo no existe en `_product_to_dict` todavía)

- [ ] **Step 1.3: Agregar `get_by_sku_for_matching()` en el repositorio**

En `app/repositories/product.py`, después de `get_by_sku()` (línea 43), agregar:

```python
async def get_by_sku_for_matching(self, sku: str) -> Product | None:
    """Like get_by_sku but eager-loads product.model for matching pipeline."""
    from sqlalchemy.orm import selectinload
    from app.db.models.product_models import ProductModel  # noqa: F401 — needed for selectinload

    stmt = (
        select(Product)
        .options(selectinload(Product.model))
        .where(Product.sku == sku)
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()
```

- [ ] **Step 1.4: Actualizar `match_service.py` para usar el nuevo método**

En `match_service.py`, buscar los 2 usos de `get_by_sku` en `refresh_candidates` (línea ~182) y `refresh_candidates_enhanced` (línea ~460 y ~591). Cambiar cada uno:

```python
# ANTES:
product = await self._products_repo.get_by_sku(sku)

# DESPUÉS (en las 3 ocurrencias):
product = await self._products_repo.get_by_sku_for_matching(sku)
```

- [ ] **Step 1.5: Ejecutar el test (aún fallará por _product_to_dict)**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_match_service.py::test_product_repo_get_by_sku_for_matching_returns_product_with_model -v
```

Resultado esperado: sigue `FAILED` — `KeyError: 'model_code'` — normal, se resuelve en Task 2.

- [ ] **Step 1.6: Commit parcial**

```bash
git add app/repositories/product.py app/services/matching/match_service.py tests/unit/services/matching/test_match_service.py
git commit -m "feat(matching): get_by_sku_for_matching eager-loads Product.model"
```

---

## Task 2: Enriquecer `_product_to_dict()` con campos del modelo

**Files:**
- Modify: `app/services/matching/match_service.py` (método `_product_to_dict`, línea 682)
- Test: `tests/unit/services/matching/test_match_service.py`

- [ ] **Step 2.1: Identificar el bloque `base = {…}` actual**

El método `_product_to_dict` está en `match_service.py:682-730`. El bloque `base = {…}` termina en la línea ~726 con `"product_materials": product_materials`. Vamos a añadir campos del modelo después de ese bloque.

- [ ] **Step 2.2: Agregar extracción del modelo en `_product_to_dict()`**

Reemplazar el bloque de cierre del `else` en `_product_to_dict` para incluir:

```python
            base = {
                "sku": getattr(product, "sku", None),
                "name_en": product_type or erp_name,
                "product_type": product_type,
                "erp_name": erp_name,
                "family": getattr(product, "family", None),
                "subfamily": getattr(product, "subfamily", None),
                "material": getattr(product, "material", None),
                "dn": getattr(product, "dn", None),
                "pn": getattr(product, "pn", None),
                "connection": getattr(product, "connection", None),
                "brand": getattr(product, "brand", None),
                "specs": specs,
                "alloy": alloy_list[0] if alloy_list else None,
                "norma": standards_list[0] if standards_list else None,
                "product_materials": product_materials,
            }

            # model hierarchy — populated when get_by_sku_for_matching() was used
            _model = getattr(product, "model", None)
            if _model is not None:
                base["model_code"] = getattr(_model, "code", None)
                base["model_connection_type"] = getattr(_model, "connection_type", None)
                base["model_thread_standard"] = getattr(_model, "thread_standard", None)
            else:
                base["model_code"] = None
                base["model_connection_type"] = None
                base["model_thread_standard"] = None
```

Reemplazar el bloque `base = {…}` existente (líneas 706-726) con el código anterior.

- [ ] **Step 2.3: Ejecutar el test del Task 1 — ahora debe pasar**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_match_service.py::test_product_repo_get_by_sku_for_matching_returns_product_with_model -v
```

Resultado esperado: `PASSED`

- [ ] **Step 2.4: Verificar que tests existentes siguen pasando**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_match_service.py -v
```

Resultado esperado: todos `PASSED`

- [ ] **Step 2.5: Agregar test para producto sin modelo (model=None)**

En `tests/unit/services/matching/test_match_service.py`:

```python
def test_product_to_dict_without_model_returns_none_model_fields() -> None:
    """Producto sin model_id debe devolver None para los campos del modelo."""
    from unittest.mock import MagicMock
    from app.services.matching.match_service import MatchService

    mock_product = MagicMock()
    mock_product.sku = "MTSS1001025"
    mock_product.model = None  # sin modelo asignado
    mock_product.specs = {}
    mock_product.materials = []
    mock_product.type = "Gate Valve PN16"
    mock_product.erp_name = "Gate Valve SS PN16 DN25"
    mock_product.family = "gate_valve"
    mock_product.subfamily = None
    mock_product.material = "stainless_steel"
    mock_product.dn = "DN25"
    mock_product.pn = "PN16"
    mock_product.connection = "BSP"
    mock_product.brand = "Giacomini"

    result = MatchService._product_to_dict(mock_product)
    assert result["model_code"] is None
    assert result["model_connection_type"] is None
    assert result["model_thread_standard"] is None
    # campos base siguen presentes
    assert result["sku"] == "MTSS1001025"
    assert result["family"] == "gate_valve"
```

- [ ] **Step 2.6: Ejecutar test nuevo**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_match_service.py -v -k "model"
```

Resultado esperado: ambos tests `PASSED`

- [ ] **Step 2.7: Commit**

```bash
git add app/services/matching/match_service.py tests/unit/services/matching/test_match_service.py
git commit -m "feat(matching): _product_to_dict incluye model_code/connection_type/thread_standard"
```

---

## Task 3: Actualizar `QueryBuilder` para usar campos del modelo

**Files:**
- Modify: `app/services/matching/query_builder.py`
- Test: `tests/unit/services/matching/test_query_builder.py`

**Contexto:** `QueryBuilder._build_per_channel()` usa `sku.get("connection")` para la conexión. Si `model_connection_type` tiene valor (p.ej. `"thread_bsp"`), es más fiable que el campo plano `connection` del producto. Además, `model_thread_standard` (p.ej. `"BSP"`, `"NPT"`) puede enriquecer el tier `spec` query con el estándar exacto.

- [ ] **Step 3.1: Escribir el test que falla**

En `tests/unit/services/matching/test_query_builder.py`, agregar:

```python
def test_build_for_sku_uses_model_thread_standard_in_spec_query() -> None:
    """Cuando model_thread_standard está presente, aparece en el spec query."""
    sku = dict(SAMPLE_SKU)
    sku["model_thread_standard"] = "BSP"
    sku["model_connection_type"] = "thread_bsp"

    queries = build_queries(sku)
    spec_q = next(q for q in queries if q.type == "spec")
    assert "BSP" in spec_q.text, f"Expected BSP in spec query, got: {spec_q.text!r}"


def test_build_for_sku_model_fields_none_does_not_crash() -> None:
    """Cuando model_* son None, el builder funciona igual que antes."""
    sku = dict(SAMPLE_SKU)
    sku["model_code"] = None
    sku["model_connection_type"] = None
    sku["model_thread_standard"] = None

    queries = build_queries(sku)
    assert any(q.type == "spec" for q in queries)
```

- [ ] **Step 3.2: Ejecutar el test para verificar que falla**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_query_builder.py::test_build_for_sku_uses_model_thread_standard_in_spec_query -v
```

Resultado esperado: `FAILED` — `AssertionError: Expected BSP in spec query`

- [ ] **Step 3.3: Actualizar `_build_per_channel()` para usar `model_thread_standard`**

En `app/services/matching/query_builder.py`, dentro de `_build_per_channel()`, buscar la sección que construye `norma` (línea ~82 del método):

```python
        norma = (sku.get("norma") or "").strip()
```

Añadir inmediatamente después:

```python
        # model-level fields — more precise than SKU-level when present
        model_thread_standard = (sku.get("model_thread_standard") or "").strip()
        model_connection_type = (sku.get("model_connection_type") or "").strip()
```

Luego en la construcción del tier `spec` (sección `# 4. Spec técnica EN`), cambiar de:

```python
        tokens = [
            material_en or "",
            family_term or "",
            size_token,
            f"PN{pn_clean}" if pn_clean else "",
        ]
        spec_text = _join_tokens(tokens)
```

A:

```python
        # Use model_thread_standard if available (e.g. "BSP", "NPT") — more reliable
        # than the raw connection field which may be a combined string like "BSP M-F".
        thread_token = model_thread_standard or (
            sku.get("connection") or ""
        ).strip().split()[0]  # first word only avoids noise like "BSP M-F PN30"
        tokens = [
            material_en or "",
            family_term or "",
            size_token,
            thread_token or "",
            f"PN{pn_clean}" if pn_clean else "",
        ]
        spec_text = _join_tokens(tokens)
```

- [ ] **Step 3.4: Ejecutar los tests del query builder**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_query_builder.py -v
```

Resultado esperado: todos `PASSED` incluyendo los 2 nuevos.

- [ ] **Step 3.5: Commit**

```bash
git add app/services/matching/query_builder.py tests/unit/services/matching/test_query_builder.py
git commit -m "feat(matching): QueryBuilder usa model_thread_standard en spec query"
```

---

## Task 4: Actualizar `llm_query_generator._build_product_summary()` con contexto del modelo

**Files:**
- Modify: `app/services/matching/llm_query_generator.py`
- Test: `tests/unit/services/matching/` (nuevo archivo)

**Contexto:** `_build_product_summary()` recibe el mismo `product_data` dict de `_product_to_dict()`. Si incluye `model_thread_standard` y `model_code`, Claude Haiku tiene más contexto para generar una query más específica.

- [ ] **Step 4.1: Crear el test**

Crear `tests/unit/services/matching/test_llm_query_generator.py`:

```python
"""Unit tests para llm_query_generator._build_product_summary."""
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit


def test_build_product_summary_includes_model_thread_standard() -> None:
    from app.services.matching.llm_query_generator import _build_product_summary

    product_data = {
        "erp_name": "Ball Valve DN50 BSP",
        "product_type": "Ball Valve M-F PN25",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN25",
        "connection": "BSP",
        "model_thread_standard": "BSP",
        "model_connection_type": "thread_bsp",
        "model_code": "4295",
    }
    summary = _build_product_summary(product_data)
    assert "BSP" in summary
    assert "4295" in summary


def test_build_product_summary_without_model_still_works() -> None:
    from app.services.matching.llm_query_generator import _build_product_summary

    product_data = {
        "erp_name": "Ball Valve DN50 BSP",
        "product_type": "Ball Valve M-F PN25",
        "material": "brass",
        "dn": "DN50",
        "pn": "PN25",
        "connection": "BSP",
        "model_code": None,
        "model_thread_standard": None,
        "model_connection_type": None,
    }
    summary = _build_product_summary(product_data)
    assert "brass" in summary.lower()
    assert "Ball Valve" in summary
```

- [ ] **Step 4.2: Ejecutar el test para verificar que falla**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_llm_query_generator.py -v
```

Resultado esperado: `FAILED` — `AssertionError: assert "4295" in summary`

- [ ] **Step 4.3: Actualizar `_build_product_summary()` para incluir campos del modelo**

En `app/services/matching/llm_query_generator.py`, en `_build_product_summary()`, después de la línea:

```python
    _add("Alloy code", product_data.get("alloy"))
```

Agregar:

```python
    _add("Thread standard", product_data.get("model_thread_standard"))
    _add("Connection type", product_data.get("model_connection_type"))
    _add("Model code", product_data.get("model_code"))
```

- [ ] **Step 4.4: Ejecutar tests**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/test_llm_query_generator.py -v
```

Resultado esperado: ambos `PASSED`

- [ ] **Step 4.5: Commit**

```bash
git add app/services/matching/llm_query_generator.py tests/unit/services/matching/test_llm_query_generator.py
git commit -m "feat(matching): llm_query_generator incluye model_code/thread_standard en prompt"
```

---

## Task 5: Invalidar caché LLM para SKUs con modelo asignado

**Context:** `product_search_queries` cachea la query LLM por `(sku, channel)`. Los SKUs que ahora tienen `model_id` tienen queries generados SIN contexto del modelo. Necesitamos un endpoint o script que invalide esas entradas para que se regeneren en el próximo `refresh`.

**Files:**
- Modify: `app/api/routes/matches.py` (nuevo endpoint de utilidad)
- Test: manual via curl

- [ ] **Step 5.1: Revisar la tabla `product_search_queries`**

```
cd mt-pricing-backend && grep -n "ProductSearchQuery\|product_search_queries" app/db/models/search_query.py | head -20
```

Verificar los campos: debe tener `sku`, `channel`, `query_text`, `created_at`.

- [ ] **Step 5.2: Agregar endpoint `DELETE /matches/cache/model-enriched`**

En `app/api/routes/matches.py`, después del último endpoint existente, agregar:

```python
@router.delete(
    "/cache/model-enriched",
    summary="Invalida caché LLM para SKUs con model_id asignado",
    status_code=200,
)
async def invalidate_model_enriched_cache(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Borra entradas de product_search_queries para SKUs con products.model_id != NULL.

    Fuerza regeneración de queries LLM con el contexto del modelo en el próximo refresh.
    """
    from app.db.models.search_query import ProductSearchQuery
    from app.db.models.product import Product
    from sqlalchemy import delete as sa_delete

    # Subquery: SKUs con model_id asignado
    skus_with_model = select(Product.sku).where(Product.model_id.is_not(None)).scalar_subquery()

    stmt = sa_delete(ProductSearchQuery).where(
        ProductSearchQuery.sku.in_(skus_with_model)
    )
    result = await session.execute(stmt)
    await session.commit()
    return {"deleted_count": result.rowcount}
```

- [ ] **Step 5.3: Verificar que la app arranca con el nuevo endpoint**

```
docker restart mt-backend && sleep 3 && curl -s http://localhost:${CADDY_HTTP_PORT:-8081}/health/live
```

Resultado esperado: `{"status":"ok"}` o similar.

- [ ] **Step 5.4: Verificar que el endpoint aparece en el schema**

```
curl -s http://localhost:${CADDY_HTTP_PORT:-8081}/api/openapi.json | python -c "import sys,json; paths=json.load(sys.stdin)['paths']; [print(p) for p in paths if 'cache' in p]"
```

Resultado esperado: `/api/v1/matches/cache/model-enriched` (o similar según el prefix del router)

- [ ] **Step 5.5: Ejecutar la invalidación en local**

```
curl -s -X DELETE http://localhost:${CADDY_HTTP_PORT:-8081}/api/v1/matches/cache/model-enriched
```

Resultado esperado: `{"deleted_count": N}` donde N ≥ 0.

- [ ] **Step 5.6: Commit**

```bash
git add app/api/routes/matches.py
git commit -m "feat(matches): endpoint para invalidar caché LLM de SKUs con modelo asignado"
```

---

## Task 6: Smoke test end-to-end del pipeline enriquecido

**Context:** Verificar que un SKU con `model_id` asignado genera queries que incluyen el `thread_standard` y que los candidatos retornados tienen mejor relevancia.

- [ ] **Step 6.1: Encontrar un SKU con model_id en la DB local**

```
docker exec mt-backend python -c "
import asyncio
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession)() as s:
        rows = await s.execute(text('SELECT sku, model_id FROM products WHERE model_id IS NOT NULL LIMIT 5'))
        for r in rows:
            print(r)
asyncio.run(main())
"
```

Resultado esperado: lista de SKUs con `model_id`. Si está vacío, usar cualquier SKU de los 5 seed: verificar con `SELECT sku FROM products LIMIT 5`.

- [ ] **Step 6.2: Verificar que `_product_to_dict` incluye campos del modelo para ese SKU**

Usar el SKU encontrado en el paso anterior (ej. `MTBR4001050`):

```
docker exec mt-backend python -c "
import asyncio
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.repositories.product import ProductRepository

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession)() as s:
        repo = ProductRepository(s)
        p = await repo.get_by_sku_for_matching('MTBR4001050')
        from app.services.matching.match_service import MatchService
        d = MatchService._product_to_dict(p)
        print('model_code:', d.get('model_code'))
        print('model_connection_type:', d.get('model_connection_type'))
        print('model_thread_standard:', d.get('model_thread_standard'))
asyncio.run(main())
"
```

Resultado esperado: si el SKU tiene `model_id`, los campos deben tener valores reales. Si `model_id` es NULL, mostrarán `None` — eso es correcto.

- [ ] **Step 6.3: Ejecutar suite completa de tests del módulo matching**

```
cd mt-pricing-backend && python -m pytest tests/unit/services/matching/ -v --tb=short 2>&1 | tail -30
```

Resultado esperado: todos `PASSED`. Si hay fallos en tests NO relacionados con los cambios, investigar antes de continuar.

- [ ] **Step 6.4: Hacer refresh de un SKU via API**

```
SKU=MTBR4001050
curl -s -X POST http://localhost:${CADDY_HTTP_PORT:-8081}/api/v1/matches/${SKU}/refresh \
  -H "Authorization: Bearer <token>" | python -m json.tool | grep -E '"score"|"title"|"channel"' | head -20
```

Resultado esperado: respuesta con candidatos y scores. Si el scraper está activo, habrá candidatos de Amazon/Noon. Si no, el endpoint devolverá candidatos vacíos (status 200 con `refreshed_count: 0`).

- [ ] **Step 6.5: Verificar que la query LLM cacheada incluye thread standard**

```
docker exec mt-backend python -c "
import asyncio
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession)() as s:
        rows = await s.execute(
            text(\"SELECT sku, channel, query_text FROM product_search_queries WHERE sku='MTBR4001050'\")
        )
        for r in rows:
            print(r)
asyncio.run(main())
"
```

Resultado esperado: `query_text` debe contener algo como `"brass ball valve 2 inch BSP industrial"` — con BSP o el estándar del modelo. Si no, ejecutar el DELETE del Task 5 y volver a hacer refresh.

- [ ] **Step 6.6: Commit final (si hubo cambios menores de ajuste)**

```bash
git add .
git commit -m "chore(matching): smoke test verificación pipeline model-enriched"
```

---

## Verificación de cobertura del spec

| Requerimiento | Task que lo implementa |
|---|---|
| Información del modelo fluye al pipeline | Task 1 + Task 2 |
| QueryBuilder usa thread standard del modelo | Task 3 |
| LLM query generator tiene contexto del modelo | Task 4 |
| Caché LLM obsoleto invalidado | Task 5 |
| Pipeline end-to-end verificado | Task 6 |
| Tests cubren product con y sin modelo | Task 2 step 2.5 |
| Tests cubren QueryBuilder con model fields | Task 3 step 3.1 |
| Tests cubren _build_product_summary con model | Task 4 step 4.1 |
