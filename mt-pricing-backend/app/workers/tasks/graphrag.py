"""Tasks para la queue `comparator` — GraphRAG CDC dispatcher (US-RND-01-11).

Patrón:
- ``mt.graphrag.process_cdc_batch`` corre cada N segundos (configurable via
  job_definitions cuando US-1A-08-* salga). Por ahora es invocable manual
  o desde ``apply()`` sincrónico en tests.
- Construye un `AsyncSession` propio (las tasks Celery no comparten la
  request scope de FastAPI) y delega en `CdcDispatcher.process_batch`.
- El graph store se resuelve via :func:`get_default_graph_store` del
  factory — stub in-memory o Neo4j real según ``GRAPHRAG_BACKEND``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.services.graphrag.adapters import get_default_graph_store
from app.services.graphrag.cdc_dispatcher import CdcDispatcher
from app.workers.worker import celery_app

logger = structlog.get_logger(__name__)


async def _run_dispatch(batch_size: int) -> dict[str, Any]:
    """Helper async — abre session, despacha batch, commit."""
    from app.db import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            graph = get_default_graph_store()
            dispatcher = CdcDispatcher(session, graph)
            result = await dispatcher.process_batch(batch_size=batch_size)
        return result


@celery_app.task(name="mt.graphrag.process_cdc_batch", bind=True)
def process_cdc_batch(self, batch_size: int = 100) -> dict[str, Any]:  # noqa: ANN001
    """Procesa hasta ``batch_size`` rows pending de ``cdc_events``."""
    try:
        result = asyncio.run(_run_dispatch(batch_size=batch_size))
    except Exception as exc:  # noqa: BLE001
        logger.exception("graphrag.cdc.batch.failed", error=str(exc))
        raise
    logger.info("graphrag.cdc.batch.ok", **result)
    return {
        k: v for k, v in result.items() if k != "outcomes"
    }  # outcomes puede ser grande — log debug only


@celery_app.task(name="mt.graphrag.sync_product_to_kg", bind=True, max_retries=3)
def sync_product_to_kg(self, product_id: str, operation: str = "upsert") -> dict[str, Any]:
    """Sincroniza un producto de Postgres a Neo4j.

    Invocado desde el webhook CDC (POST /internal/cdc/product).
    Retry: 3 intentos, backoff 10s/30s/90s.
    """
    import time

    start = time.time()
    try:
        result = asyncio.run(_sync_product(product_id=product_id, operation=operation))
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "graphrag.sync_product.failed",
            product_id=product_id,
            operation=operation,
            error=str(exc),
        )
        countdown = [10, 30, 90][min(self.request.retries, 2)]
        raise self.retry(exc=exc, countdown=countdown)
    latency_ms = int((time.time() - start) * 1000)
    logger.info(
        "graphrag.sync_product.ok",
        product_id=product_id,
        operation=operation,
        latency_ms=latency_ms,
    )
    return {"product_id": product_id, "operation": operation, "latency_ms": latency_ms}


async def _sync_product(product_id: str, operation: str) -> dict[str, Any]:
    """Helper async para sync_product_to_kg."""
    from app.services.graphrag.ports import GraphNode

    graph = get_default_graph_store()

    if operation == "delete":
        graph.delete_subgraph("Product", product_id)
        return {"action": "deleted"}

    # upsert / insert / update — MERGE en Neo4j
    import datetime

    node = GraphNode(
        label="Product",
        primary_key=product_id,
        properties={
            "product_id": product_id,
            "synced_at": datetime.datetime.utcnow().isoformat(),
        },
    )
    graph.merge_node(node)
    return {"action": "upserted"}


@celery_app.task(name="mt.graphrag.ingest_equivalences_from_pdf", bind=True)
def ingest_equivalences_from_pdf(
    self,
    pdf_path: str,
    *,
    use_fixture: bool = False,
) -> dict[str, Any]:
    """Extrae equivalencias de PDF y sincroniza al KG como EQUIVALENT_TO edges.

    US-F15-01-05 — ingestión fichas técnicas PDF.

    Args:
        pdf_path: Ruta al PDF de ficha técnica.
        use_fixture: Si True, usa datos sintéticos (para tests sin PDF real).
    """
    try:
        result = asyncio.run(_ingest_equivalences(pdf_path=pdf_path, use_fixture=use_fixture))
    except Exception as exc:  # noqa: BLE001
        logger.exception("graphrag.ingest_equivalences.failed", pdf_path=pdf_path, error=str(exc))
        raise
    logger.info("graphrag.ingest_equivalences.ok", **result)
    return result


async def _ingest_equivalences(pdf_path: str, use_fixture: bool) -> dict[str, Any]:
    """Helper async — extrae pares del PDF y hace MERGE en Neo4j."""
    if use_fixture:
        pairs = _load_fixture_equivalences()
    else:
        pairs = _extract_from_pdf(pdf_path)

    graph = get_default_graph_store()
    synced = 0

    for sku_a, sku_b, confidence, source in pairs:
        try:
            from app.services.graphrag.ports import GraphEdge, GraphNode

            graph.merge_node(GraphNode(label="Product", primary_key=sku_a, properties={}))
            graph.merge_node(GraphNode(label="Product", primary_key=sku_b, properties={}))
            edge = GraphEdge(
                src_label="Product",
                src_pk=sku_a,
                type="EQUIVALENT_TO",
                dst_label="Product",
                dst_pk=sku_b,
                properties={"confidence": confidence, "source": source},
            )
            graph.merge_edge(edge)
            synced += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "graphrag.ingest_equivalences.edge_failed sku_a=%s sku_b=%s err=%s",
                sku_a,
                sku_b,
                exc,
            )

    return {"pairs_found": len(pairs), "synced": synced, "pdf_path": pdf_path}


def _extract_from_pdf(pdf_path: str) -> list[tuple[str, str, float, str]]:
    """Extrae pares de equivalencia de un PDF con pdfplumber.

    Soporta patrones: ``SKU-A = SKU-B``, ``SKU-A equiv. SKU-B``, ``SKU-A ↔ SKU-B``.
    """
    import re

    import pdfplumber

    pattern = re.compile(
        r"([A-Z0-9][\w\-\.]+)\s+(?:equiv\.?|=|↔)\s+([A-Z0-9][\w\-\.]+)",
        re.IGNORECASE,
    )
    pairs: list[tuple[str, str, float, str]] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for m in pattern.finditer(text):
                    sku_a, sku_b = m.group(1).upper(), m.group(2).upper()
                    if sku_a != sku_b:
                        pairs.append((sku_a, sku_b, 0.85, "pdf"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("graphrag.extract_pdf.failed path=%s err=%s", pdf_path, exc)

    return pairs


def _load_fixture_equivalences() -> list[tuple[str, str, float, str]]:
    """Equivalencias sintéticas para tests sin PDF real."""
    return [
        ("MT-VALVE-001", "MT-VALVE-002", 0.95, "fixture"),
        ("MT-VALVE-001", "MT-VALVE-003", 0.80, "fixture"),
        ("MT-PUMP-100", "MT-PUMP-101", 0.90, "fixture"),
        ("MT-PUMP-100", "MT-PUMP-102", 0.75, "fixture"),
        ("MT-FITTING-A", "MT-FITTING-B", 0.85, "fixture"),
    ]


@celery_app.task(name="mt.graphrag.kg_integrity_check")
def kg_integrity_check() -> dict[str, Any]:
    """Verifica integridad del KG y persiste resultado. Schedule: 02:00 UTC daily."""
    try:
        result = asyncio.run(_run_kg_integrity_check())
    except Exception as exc:  # noqa: BLE001
        logger.exception("graphrag.kg_integrity.failed", error=str(exc))
        return {"status": "error", "error": str(exc)}

    if result.get("orphan_nodes", 0) > 10 or result.get("cdc_lag_seconds", 0) > 300:
        logger.error(
            "graphrag.kg_integrity.warning",
            orphan_nodes=result.get("orphan_nodes"),
            cdc_lag_seconds=result.get("cdc_lag_seconds"),
        )
        result["status"] = "warning"
    else:
        result["status"] = "ok"

    logger.info("graphrag.kg_integrity.ok", **result)
    return result


async def _run_kg_integrity_check() -> dict[str, Any]:
    """Helper async para kg_integrity_check."""
    from app.db import get_sessionmaker
    from app.db.models.graphrag import KgIntegrityResult

    graph = get_default_graph_store()

    # Métricas básicas (stub retorna zeros)
    node_count = 0
    edge_count = 0
    orphan_nodes = 0

    try:
        driver = getattr(graph, "_driver", None)
        if driver is not None:
            database = getattr(graph, "_database", "neo4j")

            def _query() -> tuple[int, int, int]:
                with driver.session(database=database) as s:
                    nc = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
                    ec = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
                    on = s.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) AS cnt").single()["cnt"]
                    return nc, ec, on

            node_count, edge_count, orphan_nodes = await asyncio.to_thread(_query)
    except Exception as exc:
        logger.warning("graphrag.kg_integrity.neo4j_query_failed: %s", exc)

    # Persistir resultado
    result_data: dict[str, Any] = {
        "node_count": node_count,
        "edge_count": edge_count,
        "orphan_nodes": orphan_nodes,
        "cdc_lag_seconds": 0.0,  # TODO: implementar con consulta Postgres en S11
    }

    try:
        session_factory = get_sessionmaker()
        async with session_factory() as session:
            async with session.begin():
                session.add(KgIntegrityResult(**result_data))
    except Exception as exc:
        logger.warning("graphrag.kg_integrity.persist_failed: %s", exc)

    return result_data


__all__ = [
    "ingest_equivalences_from_pdf",
    "kg_integrity_check",
    "process_cdc_batch",
    "sync_product_to_kg",
]
