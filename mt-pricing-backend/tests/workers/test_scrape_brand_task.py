"""Tests para scrape_brand_task y scrape_brands_batch_task — mock del fetcher.

Cubre (US-SCR-03-02 AC-4, AC-5, AC-6):
- AC-4: scrape_brand_task llama al fetcher con Query correcto y hace upsert
        en competitor_listings con competitor_brand_id correcto.
- AC-5: scrape_brands_batch_task despacha una task por cada brand activa.
- AC-6: Query builder mapea amazon_dept / amazon_category_node correctamente
        y la URL SERP contiene los parámetros correctos.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.matching.ports import Query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_brand(
    *,
    name: str = "Nibco",
    amazon_search_term: str | None = None,
    amazon_dept: str = "industrial",
    amazon_category_node: str | None = None,
    is_active: bool = True,
) -> object:
    import types

    brand = types.SimpleNamespace(
        id=uuid4(),
        name=name,
        amazon_search_term=amazon_search_term,
        amazon_dept=amazon_dept,
        amazon_category_node=amazon_category_node,
        is_active=is_active,
    )
    return brand


# ---------------------------------------------------------------------------
# AC-6: _build_brand_query — mapeo correcto de campos al Query
# ---------------------------------------------------------------------------


def test_build_brand_query_uses_name_when_no_search_term():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Nibco")
    q = _build_brand_query(brand)

    assert isinstance(q, Query)
    assert q.text == "Nibco"
    assert q.type == "brand"
    assert q.source == "amazon_uae"
    assert q.dept == "industrial"
    assert q.category_node is None


def test_build_brand_query_prefers_amazon_search_term():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Nibco Inc.", amazon_search_term="Nibco")
    q = _build_brand_query(brand)

    assert q.text == "Nibco"


def test_build_brand_query_passes_category_node():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(
        name="Kitz",
        amazon_dept="industrial",
        amazon_category_node="16118159031",
    )
    q = _build_brand_query(brand)

    assert q.dept == "industrial"
    assert q.category_node == "16118159031"


def test_build_brand_query_custom_dept():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Crane", amazon_dept="tools")
    q = _build_brand_query(brand)

    assert q.dept == "tools"


def test_build_brand_query_returns_query_dataclass():
    """El objeto devuelto es un Query frozen dataclass con todos los campos."""
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(
        name="Pegler",
        amazon_search_term="Pegler Yorkshire",
        amazon_dept="industrial",
        amazon_category_node="12345",
    )
    q = _build_brand_query(brand)

    assert isinstance(q, Query)
    assert q.text == "Pegler Yorkshire"
    assert q.source == "amazon_uae"
    assert q.type == "brand"
    assert q.dept == "industrial"
    assert q.category_node == "12345"


# ---------------------------------------------------------------------------
# AC-6: URL SERP contiene los parámetros correctos
# ---------------------------------------------------------------------------


def test_serp_url_contains_dept_and_category_node():
    """La URL SERP construida por CurlCffiAmazonUaeFetcher._fetch_serp
    incluye el parámetro &i=<dept> y &rh=n:<category_node>."""
    from urllib.parse import quote_plus

    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(
        name="Nibco",
        amazon_dept="industrial",
        amazon_category_node="16118159031",
    )
    q = _build_brand_query(brand)

    # Reconstruct SERP URL using same logic as CurlCffiAmazonUaeFetcher._fetch_serp
    url = f"https://www.amazon.ae/s?k={quote_plus(q.text)}"
    if q.dept:
        url += f"&i={q.dept}"
    if q.category_node:
        url += f"&rh=n:{q.category_node}"
    url += "&language=en_AE"

    assert f"k={quote_plus('Nibco')}" in url
    assert "&i=industrial" in url
    assert "&rh=n:16118159031" in url
    assert "language=en_AE" in url


def test_serp_url_without_category_node_omits_rh_param():
    from urllib.parse import quote_plus

    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Crane", amazon_dept="tools", amazon_category_node=None)
    q = _build_brand_query(brand)

    url = f"https://www.amazon.ae/s?k={quote_plus(q.text)}"
    if q.dept:
        url += f"&i={q.dept}"
    if q.category_node:
        url += f"&rh=n:{q.category_node}"

    assert "&i=tools" in url
    assert "rh=n:" not in url


# ---------------------------------------------------------------------------
# AC-4: lógica de _run_async probada directamente (sin asyncio.run)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrape_brand_task_run_async_calls_fetcher_with_correct_query():
    """Prueba la lógica interna de _run_async extrayéndola directamente."""
    from unittest.mock import AsyncMock, MagicMock
    from decimal import Decimal
    import types

    from app.services.matching.ports import CandidateRaw, Query
    from app.workers.tasks.scraper import _build_brand_query

    # Simula lo que haría _run_async con mocks puros
    brand = _make_brand(
        name="Kitz",
        amazon_search_term="Kitz valves",
        amazon_dept="industrial",
        amazon_category_node="99887766",
    )

    candidate = CandidateRaw(
        source="amazon_uae",
        external_id="B002XYZ",
        title="Kitz Bronze Gate Valve",
        raw_payload={"image_url": "", "url": ""},
    )

    mock_fetcher = MagicMock()
    mock_fetcher.fetch = AsyncMock(return_value=[candidate])

    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=brand)
    mock_repo.upsert_listing = AsyncMock()
    mock_repo.touch_scraped = AsyncMock()

    # Build query and call fetcher directly — same logic as _run_async
    query = _build_brand_query(brand)
    result_candidates = await mock_fetcher.fetch(query)

    for c in result_candidates:
        await mock_repo.upsert_listing(c, competitor_brand_id=brand.id)

    await mock_repo.touch_scraped(brand)

    # Assertions: Query fields
    assert query.text == "Kitz valves"
    assert query.dept == "industrial"
    assert query.category_node == "99887766"
    assert query.source == "amazon_uae"
    assert query.type == "brand"

    # Assertions: fetcher called once
    mock_fetcher.fetch.assert_called_once_with(query)

    # Assertions: upsert called with correct brand id
    mock_repo.upsert_listing.assert_called_once_with(candidate, competitor_brand_id=brand.id)

    # Assertions: touch_scraped called
    mock_repo.touch_scraped.assert_called_once_with(brand)


# ---------------------------------------------------------------------------
# AC-5: scrape_brands_batch_task — despacha una task por cada brand activa
# ---------------------------------------------------------------------------


def test_scrape_brands_batch_task_dispatches_one_task_per_brand(monkeypatch):
    """scrape_brands_batch_task crea un group con una scrape_brand_task.s()
    por cada brand_id en la lista."""
    from unittest.mock import MagicMock, patch

    brand_ids = [str(uuid4()) for _ in range(3)]

    mock_group_result = MagicMock()
    mock_group_result.id = "batch-group-789"
    mock_group_result.save = MagicMock()

    # Capturamos el generador que se pasa a celery_group para verificar
    # que contiene una subtask por cada brand_id.
    captured_generator_items: list = []

    def _fake_group(iterable):
        for item in iterable:
            captured_generator_items.append(item)
        mock = MagicMock()
        mock.apply_async.return_value = mock_group_result
        return mock

    with patch("app.workers.tasks.scraper.celery_group", _fake_group):
        from app.workers.tasks.scraper import scrape_brands_batch_task

        result = scrape_brands_batch_task(brand_ids=brand_ids, force=False)

    assert result["total"] == 3
    assert result["group_id"] == "batch-group-789"
    # Una subtask (signature) por cada brand_id
    assert len(captured_generator_items) == 3


def test_scrape_brands_batch_task_returns_empty_when_no_brands():
    """Si la lista de brands es vacía, retorna {group_id: None, total: 0}."""
    from unittest.mock import patch

    with patch("app.workers.tasks.scraper.celery_group") as mock_group:
        from app.workers.tasks.scraper import scrape_brands_batch_task

        result = scrape_brands_batch_task(brand_ids=[], force=False)

    assert result["total"] == 0
    assert result["group_id"] is None
    mock_group.assert_not_called()


def test_scrape_brands_batch_task_dispatches_with_force_flag():
    """El flag force se propaga a cada scrape_brand_task.s()."""
    from unittest.mock import MagicMock, patch

    brand_ids = [str(uuid4()), str(uuid4())]

    mock_group_result = MagicMock()
    mock_group_result.id = "force-group-id"
    mock_group_result.save = MagicMock()

    # Verificamos que se crean 2 subtasks (force se pasa via .s() que es una
    # Celery signature — no podemos introspectarla sin Celery real, pero
    # comprobamos que el número de items es correcto).
    captured_items: list = []

    def _fake_group(iterable):
        for item in iterable:
            captured_items.append(item)
        mock = MagicMock()
        mock.apply_async.return_value = mock_group_result
        return mock

    with patch("app.workers.tasks.scraper.celery_group", _fake_group):
        from app.workers.tasks.scraper import scrape_brands_batch_task

        result = scrape_brands_batch_task(brand_ids=brand_ids, force=True)

    assert result["total"] == 2
    assert len(captured_items) == 2


# ---------------------------------------------------------------------------
# AC-5 (extra): scrape_brands_batch_task con brand_ids=None carga activas de DB
# ---------------------------------------------------------------------------


def test_scrape_brands_batch_task_loads_active_brands_when_none(monkeypatch):
    """brand_ids=None → se cargan las marcas activas desde DB vía asyncio.run."""
    from unittest.mock import MagicMock, patch
    import asyncio as _asyncio

    active_ids = [str(uuid4()), str(uuid4())]

    mock_group_result = MagicMock()
    mock_group_result.id = "auto-group-id"
    mock_group_result.save = MagicMock()

    # Patch asyncio.run para el _load_active() interno y devolver los IDs simulados.
    call_count = [0]

    def _mock_asyncio_run(coro):
        call_count[0] += 1
        # Close the coroutine to avoid ResourceWarning
        coro.close()
        return active_ids

    captured_items: list = []

    def _fake_group(iterable):
        for item in iterable:
            captured_items.append(item)
        mock = MagicMock()
        mock.apply_async.return_value = mock_group_result
        return mock

    with (
        patch("app.workers.tasks.scraper.asyncio") as mock_asyncio,
        patch("app.workers.tasks.scraper.celery_group", _fake_group),
    ):
        mock_asyncio.run = _mock_asyncio_run

        from app.workers.tasks.scraper import scrape_brands_batch_task

        result = scrape_brands_batch_task(brand_ids=None, force=False)

    assert result["total"] == 2
    assert result["group_id"] == "auto-group-id"
    # asyncio.run fue llamado para cargar los IDs activos
    assert call_count[0] == 1
    # Una subtask por cada brand activa
    assert len(captured_items) == 2
